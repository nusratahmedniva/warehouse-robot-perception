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
        /// Make the rest pose of one hand's fingers the mirror image of the other hand's (Phase 2D, 2026-11-08). Every shape
        /// starts from the rest pose, so a rig whose hands are not mirror images at rest gets different shapes on its two
        /// hands. The Sunbox base mesh is such a rig: its left thumb's distal joint lies 17 mm from the mirror image of the
        /// right one's (left thumb straight, right thumb bent at the intermediate joint), so the left WAIT thumb stuck out
        /// sideways and MediaPipe did not read Pointing_Up on any look. Rig-independent: the mirror M maps the hand frame of
        /// <paramref name="from"/> (finger direction, palm normal and their cross product) onto the mirrored frame of
        /// <paramref name="to"/>; the rig's own left/right bone-axis convention C is measured on the finger bones that are
        /// already mirror images (index to little; the same C for all of them), and every finger bone of
        /// <paramref name="to"/> gets the world rotation M * R_from * C, base to tip, so the bones' twist (which turns the
        /// next phalanx) is mirrored too. A rig without one consistent C falls back to aiming each segment along its mirror
        /// image. The finger bases are fixed by the hand bone and stay. Call it on the rest pose, before Capture. Returns the
        /// largest displacement of a joint or fingertip (Tip) in metres (0 for a mirror-symmetric rig), or -1 when a hand
        /// lacks its bones or axes.
        /// </summary>
        public static float MirrorRest(LookPoser.Arm from, LookPoser.Arm to)
        {
            if (!Complete(from) || !Complete(to) || !HandAxes(from, out var fdA, out var palmA) || !HandAxes(to, out var fdB, out var palmB)) return -1f;
            Vector3 sideA = Vector3.Cross(fdA, palmA), sideB = -Vector3.Cross(fdB, palmB);   // a mirror reverses a cross product
            var m = Columns(sideB, fdB, palmB) * Columns(sideA, fdA, palmA).transpose;
            var before = Points(to);
            if (Convention(from, to, m, out var c))
            {
                for (int f = 0; f < 5; f++)
                    for (int j = 0; j < 3; j++)
                        if (from.Fingers[f][j] != null && to.Fingers[f][j] != null)
                            to.Fingers[f][j].rotation = (m * Matrix4x4.Rotate(from.Fingers[f][j].rotation) * c).rotation;
            }
            else
            {
                for (int f = 0; f < 5; f++)
                    for (int j = 0; j < 2; j++)
                    {
                        Transform a0 = from.Fingers[f][j], a1 = from.Fingers[f][j + 1], b0 = to.Fingers[f][j], b1 = to.Fingers[f][j + 1];
                        if (a0 == null || a1 == null || b0 == null || b1 == null) continue;
                        Aim(b0, b1.position, m.MultiplyVector(a1.position - a0.position));
                    }
            }
            var after = Points(to);
            float moved = 0f;
            for (int i = 0; i < after.Count; i++) moved = Mathf.Max(moved, Vector3.Distance(before[i], after[i]));
            return moved;
        }

        static Matrix4x4 Columns(Vector3 a, Vector3 b, Vector3 c)
        {
            var x = Matrix4x4.identity;
            x.SetColumn(0, a);
            x.SetColumn(1, b);
            x.SetColumn(2, c);
            return x;
        }

        /// <summary>Every finger joint and fingertip of a hand, in a fixed order.</summary>
        static System.Collections.Generic.List<Vector3> Points(LookPoser.Arm a)
        {
            var p = new System.Collections.Generic.List<Vector3>();
            for (int f = 0; f < 5; f++)
            {
                for (int j = 0; j < 3; j++) p.Add(a.Fingers[f][j] != null ? a.Fingers[f][j].position : Vector3.zero);
                p.Add(a.Fingers[f][1] != null && a.Fingers[f][2] != null ? Tip(a, f) : Vector3.zero);
            }
            return p;
        }

        /// <summary>The local reflection C with R_to = M * R_from * C on every bone of the index to little fingers (rest pose,
        /// within 0.01 per matrix entry); false if they do not agree.</summary>
        static bool Convention(LookPoser.Arm from, LookPoser.Arm to, Matrix4x4 m, out Matrix4x4 c)
        {
            c = Matrix4x4.identity;
            bool found = false;
            for (int f = Index; f <= Little; f++)
                for (int j = 0; j < 3; j++)
                {
                    Transform a = from.Fingers[f][j], b = to.Fingers[f][j];
                    if (a == null || b == null) continue;
                    var k = Matrix4x4.Rotate(a.rotation).transpose * m.transpose * Matrix4x4.Rotate(b.rotation);
                    if (!found) { c = k; found = true; continue; }
                    for (int i = 0; i < 16; i++) if (Mathf.Abs(k[i] - c[i]) > 0.01f) return false;
                }
            return found;
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
                // only the sideways offset from the middle finger (Phase 2D fix): the part along the fingers (a little finger's
                // base lies ~14 mm behind the middle one's) could flip the sign on one hand, fanning that finger inward
                Vector3 side = Vector3.ProjectOnPlane(Vector3.ProjectOnPlane(root.position - middle.position, palm), fingerDir);
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
            float baseDist = Vector3.Distance(a.Hand.position, f[0].position);
            return baseDist > 1e-6f ? Vector3.Distance(a.Hand.position, Tip(a, finger)) / baseDist : float.NaN;
        }

        /// <summary>The fingertip as TipRatio estimates it: one distal-bone length beyond the distal joint (the finger needs all three bones).</summary>
        public static Vector3 Tip(LookPoser.Arm a, int finger)
        {
            var f = a.Fingers[finger];
            float seg = Vector3.Distance(f[1].position, f[2].position);
            Vector3 along = f[2].rotation * Quaternion.Inverse(f[1].rotation) * (f[2].position - f[1].position);
            return f[2].position + along.normalized * seg;
        }
    }
}
