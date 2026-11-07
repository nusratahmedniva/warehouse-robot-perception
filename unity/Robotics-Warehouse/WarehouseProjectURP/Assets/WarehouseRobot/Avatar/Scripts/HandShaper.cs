using UnityEngine;

namespace WarehouseAvatar
{
    /// <summary>
    /// Hand orientation and finger shapes applied by script AFTER the Animator (LateUpdate), blended with the animated
    /// hand by a weight. Rig-independent: every axis is measured from the bones (the method of LookPoser and v3
    /// GestureWorker). Finger curls start from the bind pose (straight fingers) and bend each joint toward the palm by its
    /// own angle, so a shape does not depend on what the clip did to the fingers.
    /// </summary>
    public static class HandShaper
    {
        public const int Thumb = LookPoser.Thumb, Index = LookPoser.Index, Middle = LookPoser.Middle, Ring = LookPoser.Ring, Little = LookPoser.Little;

        static readonly HumanBodyBones[] k_FirstFinger = { HumanBodyBones.LeftThumbProximal, HumanBodyBones.RightThumbProximal };

        public static LookPoser.Arm BuildArm(IBoneSource bones, bool right)
        {
            var a = new LookPoser.Arm
            {
                IsRight = right,
                Upper = bones.Get(right ? HumanBodyBones.RightUpperArm : HumanBodyBones.LeftUpperArm),
                Lower = bones.Get(right ? HumanBodyBones.RightLowerArm : HumanBodyBones.LeftLowerArm),
                Hand = bones.Get(right ? HumanBodyBones.RightHand : HumanBodyBones.LeftHand),
                Fingers = new Transform[5][],
            };
            var first = k_FirstFinger[right ? 1 : 0];
            for (int f = 0; f < 5; f++)
            {
                a.Fingers[f] = new Transform[3];
                for (int j = 0; j < 3; j++) a.Fingers[f][j] = bones.Get(first + 3 * f + j);
            }
            return a;
        }

        public static bool Complete(LookPoser.Arm a)
        {
            if (a.Upper == null || a.Lower == null || a.Hand == null) return false;
            for (int f = Index; f <= Little; f++) if (a.Fingers[f][0] == null) return false;
            return true;
        }

        /// <summary>Shoulder to wrist along the bones (upper arm + forearm), in metres.</summary>
        public static float ArmLength(LookPoser.Arm a) =>
            Vector3.Distance(a.Upper.position, a.Lower.position) + Vector3.Distance(a.Lower.position, a.Hand.position);

        /// <summary>Local rotations of every finger bone now (call on the bind pose, before any animation runs).</summary>
        public static Quaternion[][] Capture(LookPoser.Arm a)
        {
            var q = new Quaternion[5][];
            for (int f = 0; f < 5; f++)
            {
                q[f] = new Quaternion[3];
                for (int j = 0; j < 3; j++) q[f][j] = a.Fingers[f][j] != null ? a.Fingers[f][j].localRotation : Quaternion.identity;
            }
            return q;
        }

        /// <summary>
        /// Turn the hand so its fingers point along fingerDir and the palm faces palmWant, then shape the fingers; both
        /// blended from the animated pose by weight (0 = animated, 1 = shaped).
        /// </summary>
        public static void Apply(LookPoser.Arm a, Quaternion[][] bind, HandShapeSpec shape, Vector3 fingerDir, Vector3 palmWant, float weight)
        {
            weight = Mathf.Clamp01(weight);
            if (weight <= 0f || !Complete(a)) return;
            Quaternion animated = a.Hand.rotation;
            var middle = a.Fingers[Middle][0];
            Aim(a.Hand, middle.position, fingerDir);
            AlignPalm(a, fingerDir, palmWant);
            a.Hand.rotation = Quaternion.Slerp(animated, a.Hand.rotation, weight);
            ShapeFingers(a, bind, shape, weight);
        }

        /// <summary>Finger joints from the bind pose, curled per joint toward the palm, spread; blended from the animated locals.</summary>
        public static void ShapeFingers(LookPoser.Arm a, Quaternion[][] bind, HandShapeSpec shape, float weight)
        {
            var animated = Capture(a);
            for (int f = 0; f < 5; f++)
                for (int j = 0; j < 3; j++)
                    if (a.Fingers[f][j] != null) a.Fingers[f][j].localRotation = bind[f][j];
            if (HandAxes(a, out var fingerDir, out var palm))
            {
                Vector3 axis = Vector3.Cross(fingerDir, palm).normalized;
                float sign = Vector3.Dot(Quaternion.AngleAxis(10f, axis) * fingerDir, palm) >= 0f ? 1f : -1f;
                for (int f = 0; f < 5; f++)
                {
                    var deg = shape.Finger(f);
                    for (int j = 0; j < 3; j++)
                        if (a.Fingers[f][j] != null && deg[j] != 0f)
                            a.Fingers[f][j].rotation = Quaternion.AngleAxis(deg[j] * sign, axis) * a.Fingers[f][j].rotation;
                }
                ThumbAcross(a, palm, shape.thumb_across_deg);
                Spread(a, fingerDir, palm, shape.spread_deg);
            }
            for (int f = 0; f < 5; f++)
                for (int j = 0; j < 3; j++)
                    if (a.Fingers[f][j] != null) a.Fingers[f][j].localRotation = Quaternion.Slerp(animated[f][j], a.Fingers[f][j].localRotation, weight);
        }

        /// <summary>Swing the thumb about the palm normal so its tip moves across the palm toward the little finger.</summary>
        static void ThumbAcross(LookPoser.Arm a, Vector3 palm, float deg)
        {
            var root = a.Fingers[Thumb][0];
            var tip = a.Fingers[Thumb][2] != null ? a.Fingers[Thumb][2] : a.Fingers[Thumb][1];
            var little = a.Fingers[Little][0];
            if (deg <= 0f || root == null || tip == null || little == null) return;
            Vector3 toTip = tip.position - root.position;
            float plus = Vector3.Distance(root.position + Quaternion.AngleAxis(deg, palm) * toTip, little.position);
            float minus = Vector3.Distance(root.position + Quaternion.AngleAxis(-deg, palm) * toTip, little.position);
            root.rotation = Quaternion.AngleAxis(plus <= minus ? deg : -deg, palm) * root.rotation;
        }

        /// <summary>Fan index, ring and little fingers away from the middle finger about the palm normal (deg per finger step).</summary>
        static void Spread(LookPoser.Arm a, Vector3 fingerDir, Vector3 palm, float spreadDeg)
        {
            var middle = a.Fingers[Middle][0];
            if (spreadDeg <= 0f || middle == null) return;
            for (int f = Index; f <= Little; f++)
            {
                if (f == Middle) continue;
                var root = a.Fingers[f][0];
                if (root == null) continue;
                Vector3 side = Vector3.ProjectOnPlane(root.position - middle.position, palm);
                if (side.sqrMagnitude < 1e-10f) continue;
                float deg = spreadDeg * Mathf.Abs(f - Middle);
                float sign = Vector3.Dot(Quaternion.AngleAxis(deg, palm) * fingerDir, side) >= 0f ? 1f : -1f;
                root.rotation = Quaternion.AngleAxis(sign * deg, palm) * root.rotation;
            }
        }

        /// <summary>Rotate bone so the direction bone -> child points along dir.</summary>
        public static void Aim(Transform bone, Vector3 childPosition, Vector3 dir)
        {
            Vector3 cur = childPosition - bone.position;
            if (cur.sqrMagnitude < 1e-8f || dir.sqrMagnitude < 1e-8f) return;
            bone.rotation = Quaternion.FromToRotation(cur, dir) * bone.rotation;
        }

        /// <summary>Twist the hand around the finger axis so the palm faces want.</summary>
        public static void AlignPalm(LookPoser.Arm a, Vector3 fingerDir, Vector3 want)
        {
            if (!LookPoser.PalmNormal(a, fingerDir, out var n)) return;
            Vector3 p = Vector3.ProjectOnPlane(n, fingerDir);
            Vector3 w = Vector3.ProjectOnPlane(want, fingerDir);
            if (p.sqrMagnitude < 1e-6f || w.sqrMagnitude < 1e-6f) return;
            a.Hand.rotation = Quaternion.AngleAxis(Vector3.SignedAngle(p, w, fingerDir), fingerDir) * a.Hand.rotation;
        }

        public static bool HandAxes(LookPoser.Arm a, out Vector3 fingerDir, out Vector3 palm)
        {
            palm = Vector3.zero;
            var mid = a.Fingers[Middle][0];
            fingerDir = mid != null ? mid.position - a.Hand.position : Vector3.zero;
            if (fingerDir.sqrMagnitude < 1e-8f) return false;
            fingerDir.Normalize();
            return LookPoser.PalmNormal(a, fingerDir, out palm);
        }

        /// <summary>
        /// The reader's finger measure (docs/gesture_reader_v4.md): wrist-to-tip over wrist-to-base distance. The tip is
        /// extrapolated one distal-bone length beyond the distal joint along that bone (rigs have no tip bone).
        /// </summary>
        public static float TipRatio(LookPoser.Arm a, int finger)
        {
            var f = a.Fingers[finger];
            if (f[0] == null || f[1] == null || f[2] == null) return float.NaN;
            float seg = Vector3.Distance(f[1].position, f[2].position);
            Vector3 along = f[2].rotation * Quaternion.Inverse(f[1].rotation) * (f[2].position - f[1].position);
            Vector3 tip = f[2].position + along.normalized * seg;
            float baseDist = Vector3.Distance(a.Hand.position, f[0].position);
            return baseDist > 1e-6f ? Vector3.Distance(a.Hand.position, tip) / baseDist : float.NaN;
        }
    }
}
