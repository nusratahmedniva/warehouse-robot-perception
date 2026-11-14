using System;
using System.Collections.Generic;
using UnityEngine;

namespace WarehouseAvatar
{
    /// <summary>One held pose: the command, the person's own gesturing arm and the variant's arm direction and hand.</summary>
    public struct PoseSpec
    {
        public string Command;          // LookCheckConfig.Point / Wait / Stop / None
        public bool RightArm;           // the person's own arm; ignored for NONE (both arms hang)
        public float AzimuthFrontDeg;   // 0 = straight out to the person's side (in the image plane), 90 = toward the camera
        public float ElevationDeg;      // above (+) or below (-) horizontal
        public bool ForearmUp;          // the direction is the upper arm's; the forearm is vertical
        public float SpreadDeg;         // STOP: fingers fanned away from the middle finger, per finger
        public float UpperForwardDeg;   // PROCEED: the upper arm this far forward of straight down (elbow 0.08 L out)
        public float ForearmDeg;        // PROCEED: the forearm this far above horizontal, toward the front

        /// <summary>The pose of variant v; PROCEED at its swing's time t (seconds; a single frame uses t 0).</summary>
        public static PoseSpec From(string command, string arm, LookVariant v, double t = 0.0) => new PoseSpec
        {
            Command = command, RightArm = arm == "right", AzimuthFrontDeg = v.azimuth_front_deg, ElevationDeg = v.elevation_deg,
            ForearmUp = v.forearm_up, SpreadDeg = v.spread_deg, UpperForwardDeg = v.upper_forward_deg, ForearmDeg = v.ForearmDeg(t),
        };
    }

    /// <summary>Humanoid bone lookup: an Animator in the Editor, a plain dictionary in the tests.</summary>
    public interface IBoneSource
    {
        Transform Get(HumanBodyBones bone);
    }

    public sealed class AnimatorBones : IBoneSource
    {
        readonly Animator m_Animator;
        public AnimatorBones(Animator animator) { m_Animator = animator; }
        public Transform Get(HumanBodyBones bone) => m_Animator != null && m_Animator.isHuman ? m_Animator.GetBoneTransform(bone) : null;
    }

    /// <summary>
    /// Poses a Humanoid rig for the look check by aiming bones in world space (the method of v3 GestureWorker, which
    /// stays unchanged): no animation clip, any Humanoid rig. Directions are in the body frame measured from the rig
    /// (right = left upper arm to right upper arm, level; forward = right x up), so they do not depend on the model's
    /// import orientation. Left and right are the person's own arms. Apply() always starts from the captured bind
    /// rotations, so poses never accumulate.
    /// </summary>
    public sealed class LookPoser
    {
        public const int Thumb = 0, Index = 1, Middle = 2, Ring = 3, Little = 4;

        static readonly HumanBodyBones[][] k_LeftFingers =
        {
            new[] { HumanBodyBones.LeftThumbProximal, HumanBodyBones.LeftThumbIntermediate, HumanBodyBones.LeftThumbDistal },
            new[] { HumanBodyBones.LeftIndexProximal, HumanBodyBones.LeftIndexIntermediate, HumanBodyBones.LeftIndexDistal },
            new[] { HumanBodyBones.LeftMiddleProximal, HumanBodyBones.LeftMiddleIntermediate, HumanBodyBones.LeftMiddleDistal },
            new[] { HumanBodyBones.LeftRingProximal, HumanBodyBones.LeftRingIntermediate, HumanBodyBones.LeftRingDistal },
            new[] { HumanBodyBones.LeftLittleProximal, HumanBodyBones.LeftLittleIntermediate, HumanBodyBones.LeftLittleDistal },
        };

        static readonly HumanBodyBones[][] k_RightFingers =
        {
            new[] { HumanBodyBones.RightThumbProximal, HumanBodyBones.RightThumbIntermediate, HumanBodyBones.RightThumbDistal },
            new[] { HumanBodyBones.RightIndexProximal, HumanBodyBones.RightIndexIntermediate, HumanBodyBones.RightIndexDistal },
            new[] { HumanBodyBones.RightMiddleProximal, HumanBodyBones.RightMiddleIntermediate, HumanBodyBones.RightMiddleDistal },
            new[] { HumanBodyBones.RightRingProximal, HumanBodyBones.RightRingIntermediate, HumanBodyBones.RightRingDistal },
            new[] { HumanBodyBones.RightLittleProximal, HumanBodyBones.RightLittleIntermediate, HumanBodyBones.RightLittleDistal },
        };

        public sealed class Arm
        {
            public bool IsRight;
            public Transform Upper, Lower, Hand;
            public Transform[][] Fingers;   // [finger][joint], thumb first; entries may be null
        }

        enum HandShape { Relaxed, Pointing, IndexUp, OpenPalm, Flat }

        /// <summary>PROCEED's flat hand (worker_v4.json hand_shapes.proceed): every joint bent this little toward the palm.</summary>
        const float FlatCurlDeg = 5f;

        readonly LookCheckHand m_Hand;
        readonly List<Transform> m_Bones = new List<Transform>();
        readonly List<Quaternion> m_BindLocal = new List<Quaternion>();

        public Arm Left { get; }
        public Arm Right { get; }
        public bool HasArms => Left.Upper != null && Left.Lower != null && Left.Hand != null &&
                               Right.Upper != null && Right.Lower != null && Right.Hand != null;
        /// <summary>Index, middle, ring and little fingers each have a proximal bone on both hands.</summary>
        public bool HasFingers
        {
            get
            {
                foreach (var a in new[] { Left, Right })
                    for (int f = Index; f <= Little; f++)
                        if (a.Fingers[f][0] == null) return false;
                return true;
            }
        }

        public LookPoser(IBoneSource bones, LookCheckHand hand)
        {
            m_Hand = hand ?? throw new ArgumentNullException(nameof(hand));
            Left = Build(bones, false);
            Right = Build(bones, true);
            foreach (var a in new[] { Left, Right })
            {
                Capture(a.Upper);
                Capture(a.Lower);
                Capture(a.Hand);
                foreach (var finger in a.Fingers) foreach (var t in finger) Capture(t);
            }
        }

        Arm Build(IBoneSource bones, bool right)
        {
            var a = new Arm
            {
                IsRight = right,
                Upper = bones.Get(right ? HumanBodyBones.RightUpperArm : HumanBodyBones.LeftUpperArm),
                Lower = bones.Get(right ? HumanBodyBones.RightLowerArm : HumanBodyBones.LeftLowerArm),
                Hand = bones.Get(right ? HumanBodyBones.RightHand : HumanBodyBones.LeftHand),
            };
            var ids = right ? k_RightFingers : k_LeftFingers;
            a.Fingers = new Transform[ids.Length][];
            for (int f = 0; f < ids.Length; f++)
            {
                a.Fingers[f] = new Transform[3];
                for (int j = 0; j < 3; j++) a.Fingers[f][j] = bones.Get(ids[f][j]);
            }
            return a;
        }

        void Capture(Transform t)
        {
            if (t == null || m_Bones.Contains(t)) return;
            m_Bones.Add(t);
            m_BindLocal.Add(t.localRotation);
        }

        public void ResetToBind()
        {
            for (int i = 0; i < m_Bones.Count; i++) m_Bones[i].localRotation = m_BindLocal[i];
        }

        /// <summary>Worker's right (level, unit) and forward (right x up): from the two upper-arm bones.</summary>
        public void BodyFrame(out Vector3 right, out Vector3 forward)
        {
            right = Vector3.ProjectOnPlane(Right.Upper.position - Left.Upper.position, Vector3.up);
            if (right.sqrMagnitude < 1e-8f) right = Vector3.right;
            right.Normalize();
            forward = Vector3.Cross(right, Vector3.up).normalized;
        }

        /// <summary>World direction for an arm: azimuth from the person's own side toward the front, then elevation.</summary>
        public Vector3 Direction(bool rightArm, float azimuthFrontDeg, float elevationDeg)
        {
            BodyFrame(out var r, out var f);
            Vector3 side = rightArm ? r : -r;
            float az = azimuthFrontDeg * Mathf.Deg2Rad, el = elevationDeg * Mathf.Deg2Rad;
            Vector3 h = Mathf.Cos(az) * side + Mathf.Sin(az) * f;
            return (Mathf.Cos(el) * h + Mathf.Sin(el) * Vector3.up).normalized;
        }

        /// <summary>Hanging arm (v3 GestureWorker rest: down and rest_outward to the side).</summary>
        Vector3 Rest(bool rightArm)
        {
            BodyFrame(out var r, out _);
            return (-Vector3.up + (rightArm ? r : -r) * m_Hand.rest_outward).normalized;
        }

        public void Apply(PoseSpec p)
        {
            ResetToBind();
            if (!HasArms) return;
            BodyFrame(out _, out var forward);
            if (p.Command == LookCheckConfig.None)
            {
                foreach (var arm in new[] { Left, Right })
                {
                    var d = Direction(arm.IsRight, p.AzimuthFrontDeg, p.ElevationDeg);
                    PoseArm(arm, d, d, HandShape.Relaxed, 0f, forward);
                }
                return;
            }
            Arm g = p.RightArm ? Right : Left, other = p.RightArm ? Left : Right;
            var rest = Rest(other.IsRight);
            PoseArm(other, rest, rest, HandShape.Relaxed, 0f, forward);
            Intended(p, out var dir, out var fore);
            switch (p.Command)
            {
                case LookCheckConfig.Point: PoseArm(g, dir, fore, HandShape.Pointing, 0f, forward); break;
                case LookCheckConfig.Wait: PoseArm(g, dir, fore, HandShape.IndexUp, 0f, forward); break;
                case LookCheckConfig.Stop: PoseArm(g, dir, fore, HandShape.OpenPalm, p.SpreadDeg, forward); break;
                case LookCheckConfig.Proceed: PoseArm(g, dir, fore, HandShape.Flat, 0f, forward); break;
                default: throw new ArgumentException($"unknown command '{p.Command}'");
            }
        }

        /// <summary>
        /// The intended directions of the gesturing arm of pose p (experiments_ab.md section 10: the Edit-mode geometry): upper arm (shoulder to
        /// elbow) and forearm (elbow to wrist). PROCEED (addendum 1): the upper arm straight down turned UpperForwardDeg toward the front with
        /// the elbow 0.08 L out to the side (the worker's PROCEED), the forearm ForearmDeg above horizontal toward the front.
        /// </summary>
        public void Intended(PoseSpec p, out Vector3 upper, out Vector3 fore)
        {
            if (p.Command == LookCheckConfig.Proceed)
            {
                BodyFrame(out var r, out var f);
                Arm g = p.RightArm ? Right : Left;
                Vector3 side = p.RightArm ? r : -r;
                float lu = Vector3.Distance(g.Upper.position, g.Lower.position), L = lu + Vector3.Distance(g.Lower.position, g.Hand.position);
                float au = p.UpperForwardDeg * Mathf.Deg2Rad, ph = p.ForearmDeg * Mathf.Deg2Rad;
                upper = (lu * (Mathf.Cos(au) * Vector3.down + Mathf.Sin(au) * f) + side * (0.08f * L)).normalized;
                fore = (Mathf.Cos(ph) * f + Mathf.Sin(ph) * Vector3.up).normalized;
                return;
            }
            upper = Direction(p.RightArm, p.AzimuthFrontDeg, p.ElevationDeg);
            fore = p.Command == LookCheckConfig.Wait || p.ForearmUp ? Vector3.up : upper;
        }

        void PoseArm(Arm arm, Vector3 upperDir, Vector3 foreDir, HandShape shape, float spreadDeg, Vector3 forward)
        {
            Aim(arm.Upper, arm.Lower.position, upperDir);
            Aim(arm.Lower, arm.Hand.position, foreDir);
            Transform middle = arm.Fingers[Middle][0];
            switch (shape)
            {
                case HandShape.OpenPalm:
                    if (middle != null) Aim(arm.Hand, middle.position, Vector3.up);     // fingers up
                    AlignPalm(arm, Vector3.up, forward);                               // palm toward the camera (the body faces it)
                    Spread(arm, forward, spreadDeg);
                    break;
                case HandShape.IndexUp:
                    if (middle != null) Aim(arm.Hand, middle.position, Vector3.up);
                    AlignPalm(arm, Vector3.up, forward);
                    Curl(arm, m_Hand.fist_curl_deg, m_Hand.fist_thumb_curl_deg, Index);
                    break;
                case HandShape.Flat:
                {
                    // PROCEED (the worker's shape): fingers along the forearm and together, the palm toward the body
                    if (middle != null) Aim(arm.Hand, middle.position, foreDir);
                    BodyFrame(out var bodyRight, out _);
                    Vector3 palm = Vector3.Cross(foreDir, bodyRight);
                    if (palm.sqrMagnitude < 1e-6f) palm = Vector3.up;
                    AlignPalm(arm, foreDir, palm.normalized);
                    Curl(arm, FlatCurlDeg, FlatCurlDeg, -1);
                    break;
                }
                default:
                    if (middle != null) Aim(arm.Hand, middle.position, foreDir);       // straight wrist
                    BodyFrame(out var r, out _);
                    Vector3 want = Vector3.ProjectOnPlane(-Vector3.up, foreDir);
                    if (want.sqrMagnitude < 1e-3f) want = arm.IsRight ? -r : r;         // arm vertical: palm inward
                    AlignPalm(arm, foreDir, want.normalized);
                    if (shape == HandShape.Pointing) Curl(arm, m_Hand.fist_curl_deg, m_Hand.fist_thumb_curl_deg, Index);
                    else Curl(arm, m_Hand.relaxed_curl_deg, m_Hand.relaxed_thumb_curl_deg, -1);
                    break;
            }
        }

        /// <summary>Rotate bone so the direction bone -> child points along dir.</summary>
        static void Aim(Transform bone, Vector3 childPosition, Vector3 dir)
        {
            Vector3 cur = childPosition - bone.position;
            if (cur.sqrMagnitude < 1e-8f || dir.sqrMagnitude < 1e-8f) return;
            bone.rotation = Quaternion.FromToRotation(cur, dir) * bone.rotation;
        }

        /// <summary>Direction the palm faces, from the index and little finger bases (v3 GestureWorker convention).</summary>
        public static bool PalmNormal(Arm arm, Vector3 fingerDir, out Vector3 normal)
        {
            normal = Vector3.zero;
            var index = arm.Fingers[Index][0];
            var little = arm.Fingers[Little][0];
            if (index == null || little == null) return false;
            Vector3 s = little.position - index.position;
            normal = arm.IsRight ? Vector3.Cross(s, fingerDir) : Vector3.Cross(fingerDir, s);
            if (normal.sqrMagnitude < 1e-8f) return false;
            normal.Normalize();
            return true;
        }

        /// <summary>Twist the hand around the finger axis so the palm faces want.</summary>
        static void AlignPalm(Arm arm, Vector3 fingerDir, Vector3 want)
        {
            if (!PalmNormal(arm, fingerDir, out var n)) return;
            Vector3 a = Vector3.ProjectOnPlane(n, fingerDir);
            Vector3 b = Vector3.ProjectOnPlane(want, fingerDir);
            if (a.sqrMagnitude < 1e-6f || b.sqrMagnitude < 1e-6f) return;
            arm.Hand.rotation = Quaternion.AngleAxis(Vector3.SignedAngle(a, b, fingerDir), fingerDir) * arm.Hand.rotation;
        }

        /// <summary>
        /// Curl every finger except keepStraight toward the palm about one hand axis (finger direction x palm normal),
        /// rig-independent (v3 GestureWorker.CurlFingers). Each joint bends by the angle; children follow, so it adds up.
        /// </summary>
        static void Curl(Arm arm, float fingerDeg, float thumbDeg, int keepStraight)
        {
            if (!HandAxes(arm, out var fingerDir, out var palm)) return;
            Vector3 axis = Vector3.Cross(fingerDir, palm).normalized;
            float sign = Vector3.Dot(Quaternion.AngleAxis(10f, axis) * fingerDir, palm) >= 0f ? 1f : -1f;
            for (int f = 0; f < arm.Fingers.Length; f++)
            {
                if (f == keepStraight) continue;
                var q = Quaternion.AngleAxis((f == Thumb ? thumbDeg : fingerDeg) * sign, axis);
                for (int j = 0; j < 3; j++)
                    if (arm.Fingers[f][j] != null) arm.Fingers[f][j].rotation = q * arm.Fingers[f][j].rotation;
            }
        }

        /// <summary>Fan index, ring and little fingers away from the middle finger about the palm normal (deg per finger step).</summary>
        static void Spread(Arm arm, Vector3 palmWant, float spreadDeg)
        {
            if (spreadDeg <= 0f || !HandAxes(arm, out var fingerDir, out _)) return;
            var middle = arm.Fingers[Middle][0];
            Vector3 n = palmWant.normalized;
            for (int f = Index; f <= Little; f++)
            {
                if (f == Middle) continue;
                var root = arm.Fingers[f][0];
                if (root == null) continue;
                Vector3 side = Vector3.ProjectOnPlane(root.position - middle.position, n);
                if (side.sqrMagnitude < 1e-10f) continue;
                float deg = spreadDeg * Mathf.Abs(f - Middle);
                float sign = Vector3.Dot(Quaternion.AngleAxis(deg, n) * fingerDir, side) >= 0f ? 1f : -1f;
                root.rotation = Quaternion.AngleAxis(sign * deg, n) * root.rotation;
            }
        }

        static bool HandAxes(Arm arm, out Vector3 fingerDir, out Vector3 palm)
        {
            palm = Vector3.zero;
            var mid = arm.Fingers[Middle][0];
            fingerDir = mid != null ? mid.position - arm.Hand.position : Vector3.zero;
            if (fingerDir.sqrMagnitude < 1e-8f) return false;
            fingerDir.Normalize();
            return PalmNormal(arm, fingerDir, out palm);
        }

        /// <summary>Turn root (yaw only) so the body faces the point (e.g. the camera).</summary>
        public void FaceTowards(Transform root, Vector3 point)
        {
            BodyFrame(out _, out var f);
            Vector3 want = Vector3.ProjectOnPlane(point - root.position, Vector3.up);
            if (want.sqrMagnitude < 1e-8f) return;
            float yaw = Vector3.SignedAngle(f, want, Vector3.up);
            root.rotation = Quaternion.AngleAxis(yaw, Vector3.up) * root.rotation;
        }
    }
}
