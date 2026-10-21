using UnityEngine;

namespace WarehouseHRI
{
    /// <summary>
    /// The one worker avatar, moved to every junction. Poses the arms in LateUpdate by aiming bones in world space
    /// (Animator.GetBoneTransform), so it works with any Humanoid rig (Mixamo or other) without animation clips.
    /// Without a Humanoid Animator it drives the two placeholder arm pivots instead (capsule placeholder).
    ///
    /// Arm directions are in the worker's body frame. The worker faces the robot, so the robot's LEFT is the
    /// worker's RIGHT: LEFT = right arm level to the worker's right, FORWARD_LEFT = right arm 45 deg up to that
    /// side, FORWARD = right arm straight up, FORWARD_RIGHT / RIGHT = the left arm mirrored, STOP = right arm toward
    /// the robot with an open palm facing it. For every command except STOP the hands are curled into fists, so an
    /// open hand is never shown by accident (MediaPipe would read it as STOP). <see cref="forwardHand"/> can instead
    /// show FORWARD with the index finger extended along the raised arm (the other fingers stay curled; arm angle
    /// unchanged).
    /// </summary>
    public class GestureWorker : MonoBehaviour
    {
        /// <summary>Hand of the raised arm while showing FORWARD.</summary>
        public enum ForwardHand { Fist = 0, IndexFinger = 1 }

        public Animator animator;

        [Header("Placeholder rig (used when there is no Humanoid Animator); local +z points along the arm")]
        public Transform leftArmPivot;
        public Transform rightArmPivot;

        [Header("Facing")]
        [Tooltip("The worker keeps turning to face this transform (the arriving robot).")]
        public Transform faceTarget;
        public float turnSpeedDps = 360f;

        [Header("Hands")]
        public bool curlFingersForDirections = true;
        public float fingerCurlDeg = 75f;
        public float thumbCurlDeg = 40f;
        [Tooltip("FORWARD: fist, or index finger extended along the raised arm (other fingers curled).")]
        public ForwardHand forwardHand = ForwardHand.Fist;
        [Tooltip("Arms hanging down are this far out from the body (fraction of the side vector).")]
        public float restOutward = 0.12f;

        [SerializeField] GestureCommand m_Current = GestureCommand.NONE;

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

        class Arm
        {
            public bool IsRight;
            public Transform Upper, Lower, Hand;
            public Transform[][] Fingers;          // [finger][joint], thumb first; entries may be null
            public Quaternion[][] FingerBindLocal; // open hand captured at start
            public Transform Pivot;                // placeholder
        }

        Arm m_Left, m_Right;
        bool m_Humanoid;

        /// <summary>The command currently shown (scripted). Read only by ScriptedGestureSource and the scoring.</summary>
        public GestureCommand Current => m_Current;
        public bool UsesHumanoidRig => m_Humanoid;

        public Vector3 ChestPosition
        {
            get
            {
                if (m_Humanoid)
                {
                    var chest = animator.GetBoneTransform(HumanBodyBones.UpperChest) ??
                                animator.GetBoneTransform(HumanBodyBones.Chest) ??
                                animator.GetBoneTransform(HumanBodyBones.Spine);
                    if (chest != null) return chest.position;
                }

                return transform.position + Vector3.up * 1.3f;
            }
        }

        void Awake()
        {
            if (animator == null) animator = GetComponentInChildren<Animator>();
            m_Humanoid = animator != null && animator.isHuman && animator.avatar != null;
            if (m_Humanoid)
            {
                m_Left = BuildArm(false);
                m_Right = BuildArm(true);
                if (m_Left.Upper == null || m_Left.Lower == null || m_Left.Hand == null ||
                    m_Right.Upper == null || m_Right.Lower == null || m_Right.Hand == null)
                {
                    Debug.LogWarning($"[WarehouseHRI] {name}: Humanoid rig lacks arm bones; using placeholder pivots.");
                    m_Humanoid = false;
                }
            }

            if (!m_Humanoid)
            {
                m_Left = new Arm { IsRight = false, Pivot = leftArmPivot };
                m_Right = new Arm { IsRight = true, Pivot = rightArmPivot };
                if (leftArmPivot == null || rightArmPivot == null)
                    Debug.LogWarning($"[WarehouseHRI] {name}: no Humanoid Animator and no placeholder arm pivots; arms will not move.");
            }
        }

        Arm BuildArm(bool right)
        {
            var a = new Arm
            {
                IsRight = right,
                Upper = animator.GetBoneTransform(right ? HumanBodyBones.RightUpperArm : HumanBodyBones.LeftUpperArm),
                Lower = animator.GetBoneTransform(right ? HumanBodyBones.RightLowerArm : HumanBodyBones.LeftLowerArm),
                Hand = animator.GetBoneTransform(right ? HumanBodyBones.RightHand : HumanBodyBones.LeftHand),
            };
            var ids = right ? k_RightFingers : k_LeftFingers;
            a.Fingers = new Transform[ids.Length][];
            a.FingerBindLocal = new Quaternion[ids.Length][];
            for (int f = 0; f < ids.Length; f++)
            {
                a.Fingers[f] = new Transform[3];
                a.FingerBindLocal[f] = new Quaternion[3];
                for (int j = 0; j < 3; j++)
                {
                    var t = animator.GetBoneTransform(ids[f][j]);
                    a.Fingers[f][j] = t;
                    a.FingerBindLocal[f][j] = t != null ? t.localRotation : Quaternion.identity;
                }
            }

            return a;
        }

        /// <summary>Show a command (scripted). NONE = both arms down.</summary>
        public void Show(GestureCommand command) => m_Current = command;

        /// <summary>Stand at <paramref name="stand"/> (position and facing).</summary>
        public void PlaceAt(Transform stand)
        {
            if (stand == null) return;
            transform.SetPositionAndRotation(stand.position, Quaternion.Euler(0f, stand.eulerAngles.y, 0f));
        }

        /// <summary>Turn (yaw only) to face <paramref name="point"/> at once.</summary>
        public void FaceTowards(Vector3 point)
        {
            Vector3 d = point - transform.position;
            d.y = 0f;
            if (d.sqrMagnitude > 1e-6f) transform.rotation = Quaternion.LookRotation(d, Vector3.up);
        }

        void Update()
        {
            if (faceTarget == null) return;
            Vector3 d = faceTarget.position - transform.position;
            d.y = 0f;
            if (d.sqrMagnitude < 1e-6f) return;
            var want = Quaternion.LookRotation(d, Vector3.up);
            transform.rotation = Quaternion.RotateTowards(transform.rotation, want, turnSpeedDps * Time.deltaTime);
        }

        void LateUpdate() => ApplyPose();

        /// <summary>World directions of the left and right arm for a command, in this worker's body frame.</summary>
        public void ArmDirections(GestureCommand c, out Vector3 left, out Vector3 right)
        {
            Vector3 f = transform.forward, r = transform.right, u = Vector3.up;
            Vector3 restL = (-u - r * restOutward).normalized;
            Vector3 restR = (-u + r * restOutward).normalized;
            left = restL;
            right = restR;
            switch (c)
            {
                case GestureCommand.LEFT: right = r; break;                              // robot's left = worker's right
                case GestureCommand.FORWARD_LEFT: right = (r + u).normalized; break;
                case GestureCommand.FORWARD: right = u; break;
                case GestureCommand.FORWARD_RIGHT: left = (-r + u).normalized; break;
                case GestureCommand.RIGHT: left = -r; break;
                case GestureCommand.STOP: right = (f + 0.25f * u + 0.2f * r).normalized; break;
            }
        }

        void ApplyPose()
        {
            ArmDirections(m_Current, out var dl, out var dr);
            bool stop = m_Current == GestureCommand.STOP;
            // FORWARD raises the right arm; only that hand can show the index finger.
            bool finger = m_Current == GestureCommand.FORWARD && forwardHand == ForwardHand.IndexFinger;
            PoseArm(m_Left, dl, false, false);
            PoseArm(m_Right, dr, stop, finger);
        }

        void PoseArm(Arm arm, Vector3 dir, bool openPalmTowardRobot, bool extendIndex)
        {
            if (arm == null) return;
            if (!m_Humanoid)
            {
                if (arm.Pivot != null) arm.Pivot.rotation = Quaternion.LookRotation(dir, PerpendicularUp(dir));
                return;
            }

            // Open hand first (bind pose), so curling never accumulates over frames.
            for (int f = 0; f < arm.Fingers.Length; f++)
                for (int j = 0; j < 3; j++)
                    if (arm.Fingers[f][j] != null) arm.Fingers[f][j].localRotation = arm.FingerBindLocal[f][j];

            Aim(arm.Upper, arm.Lower.position, dir);
            Aim(arm.Lower, arm.Hand.position, dir);

            Vector3 r = transform.right;
            Transform middle = arm.Fingers[2][0];
            if (openPalmTowardRobot)
            {
                if (middle != null) Aim(arm.Hand, middle.position, Vector3.up);       // fingers up
                AlignPalm(arm, Vector3.up, transform.forward);                         // palm toward the robot
            }
            else
            {
                if (middle != null) Aim(arm.Hand, middle.position, dir);              // straight wrist
                Vector3 want = Vector3.ProjectOnPlane(-Vector3.up, dir);
                if (want.sqrMagnitude < 1e-3f) want = arm.IsRight ? -r : r;          // arm vertical: palm inward
                AlignPalm(arm, dir, want.normalized);
                if (curlFingersForDirections) CurlFingers(arm, extendIndex);
            }
        }

        /// <summary>Rotate <paramref name="bone"/> so the direction bone -> child points along dir.</summary>
        static void Aim(Transform bone, Vector3 childPosition, Vector3 dir)
        {
            Vector3 cur = childPosition - bone.position;
            if (cur.sqrMagnitude < 1e-8f) return;
            bone.rotation = Quaternion.FromToRotation(cur, dir) * bone.rotation;
        }

        /// <summary>Direction the palm faces, from the index and little finger positions.</summary>
        static bool PalmNormal(Arm arm, Vector3 fingerDir, out Vector3 normal)
        {
            normal = Vector3.zero;
            var index = arm.Fingers[1][0];
            var little = arm.Fingers[4][0];
            if (index == null || little == null) return false;
            Vector3 s = little.position - index.position;
            normal = arm.IsRight ? Vector3.Cross(s, fingerDir) : Vector3.Cross(fingerDir, s);
            if (normal.sqrMagnitude < 1e-8f) return false;
            normal.Normalize();
            return true;
        }

        /// <summary>Twist the hand around the finger axis so the palm faces <paramref name="want"/>.</summary>
        static void AlignPalm(Arm arm, Vector3 fingerDir, Vector3 want)
        {
            if (!PalmNormal(arm, fingerDir, out var n)) return;
            Vector3 a = Vector3.ProjectOnPlane(n, fingerDir);
            Vector3 b = Vector3.ProjectOnPlane(want, fingerDir);
            if (a.sqrMagnitude < 1e-6f || b.sqrMagnitude < 1e-6f) return;
            float angle = Vector3.SignedAngle(a, b, fingerDir);
            arm.Hand.rotation = Quaternion.AngleAxis(angle, fingerDir) * arm.Hand.rotation;
        }

        /// <summary>
        /// Curl every finger toward the palm (a fist): each joint bends by its angle about one hand axis
        /// (finger direction x palm normal), so the result does not depend on the rig's bone axes. With
        /// <paramref name="extendIndex"/> the index finger keeps its bind pose (straight, along the arm).
        /// </summary>
        void CurlFingers(Arm arm, bool extendIndex = false)
        {
            Vector3 fingerDir = arm.Fingers[2][0] != null ? (arm.Fingers[2][0].position - arm.Hand.position) : Vector3.zero;
            if (fingerDir.sqrMagnitude < 1e-8f) return;
            fingerDir.Normalize();
            if (!PalmNormal(arm, fingerDir, out var palm)) return;
            Vector3 axis = Vector3.Cross(fingerDir, palm).normalized;
            // Pick the rotation sign that moves the fingertips toward the palm side.
            float sign = Vector3.Dot(Quaternion.AngleAxis(10f, axis) * fingerDir, palm) >= 0f ? 1f : -1f;
            for (int f = 0; f < arm.Fingers.Length; f++)
            {
                if (extendIndex && f == 1) continue;
                float deg = (f == 0 ? thumbCurlDeg : fingerCurlDeg) * sign;
                var q = Quaternion.AngleAxis(deg, axis);
                for (int j = 0; j < 3; j++)
                {
                    var bone = arm.Fingers[f][j];
                    if (bone != null) bone.rotation = q * bone.rotation; // children follow, so the curl adds up
                }
            }
        }

        static Vector3 PerpendicularUp(Vector3 dir)
        {
            Vector3 up = Vector3.ProjectOnPlane(Vector3.up, dir);
            return up.sqrMagnitude > 1e-4f ? up.normalized : Vector3.forward;
        }
    }
}
