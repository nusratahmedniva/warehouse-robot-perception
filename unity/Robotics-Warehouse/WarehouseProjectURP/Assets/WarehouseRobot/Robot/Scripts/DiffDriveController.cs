using UnityEngine;

namespace WarehouseRobot
{
    /// <summary>
    /// Differential drive on a Rigidbody: follows the commanded forward speed v (m/s) and turn rate omega (rad/s,
    /// &gt; 0 = left / counter-clockwise from above) within the limits of robot.json. Speeding up uses max_accel_mps2,
    /// slowing down (and the first half of a reversal) uses decel_mps2. Wheels are visual only (no WheelColliders);
    /// each side spins at its rim speed / wheel radius, i.e. v / r when driving straight.
    /// </summary>
    [RequireComponent(typeof(Rigidbody))]
    [DisallowMultipleComponent]
    public class DiffDriveController : MonoBehaviour
    {
        [SerializeField] Transform[] leftWheels = new Transform[0];
        [SerializeField] Transform[] rightWheels = new Transform[0];

        Rigidbody body;
        SharedRobotConfig limits;
        float wheelRadius;
        float trackWidth;
        float leftSpinDeg, rightSpinDeg;

        /// <summary>Last command after clamping to the maximum speeds.</summary>
        public float CommandedV { get; private set; }
        public float CommandedOmega { get; private set; }
        /// <summary>Speed and turn rate currently applied (after the acceleration limits).</summary>
        public float V { get; private set; }
        public float Omega { get; private set; }
        public bool Ready => limits != null;

        public void SetWheels(Transform[] left, Transform[] right)
        {
            leftWheels = left;
            rightWheels = right;
        }

        /// <summary>Command a forward speed (m/s) and turn rate (rad/s, &gt; 0 = left). Values beyond the limits are clamped.</summary>
        public void SetCommand(float v, float omega)
        {
            if (!Ready) return;
            CommandedV = Mathf.Clamp(v, -limits.max_speed_mps, limits.max_speed_mps);
            CommandedOmega = Mathf.Clamp(omega, -limits.max_angular_speed_radps, limits.max_angular_speed_radps);
        }

        /// <summary>Command zero; the robot brakes at decel_mps2 (the value the look-ahead assumes).</summary>
        public void Stop()
        {
            CommandedV = 0f;
            CommandedOmega = 0f;
        }

        void Awake()
        {
            body = GetComponent<Rigidbody>();
            var rig = GetComponent<RobotRig>();
            var cfg = rig != null ? rig.Config : null;
            if (cfg == null)
            {
                Debug.LogError("[DiffDriveController] No robot config; drive disabled.", this);
                enabled = false;
                return;
            }
            limits = cfg.Robot;
            wheelRadius = cfg.Unity.body.wheel_radius_m;
            trackWidth = cfg.Robot.robot_width_m - cfg.Unity.body.wheel_width_m;
        }

        void FixedUpdate()
        {
            float dt = Time.fixedDeltaTime;
            V = RampSpeed(V, CommandedV, limits.max_accel_mps2, limits.decel_mps2, dt);
            Omega = RampSpeed(Omega, CommandedOmega, limits.max_angular_accel_radps2, limits.max_angular_accel_radps2, dt);

            Vector3 forward = Vector3.ProjectOnPlane(body.rotation * Vector3.forward, Vector3.up).normalized;
            body.velocity = forward * V;
            body.angularVelocity = new Vector3(0f, -Omega, 0f); // Unity +Y rotation is clockwise from above
        }

        void Update()
        {
            float half = 0.5f * trackWidth * Omega;
            leftSpinDeg = Spin(leftWheels, leftSpinDeg, V - half);
            rightSpinDeg = Spin(rightWheels, rightSpinDeg, V + half);
        }

        float Spin(Transform[] wheels, float angleDeg, float rimSpeed)
        {
            angleDeg = Mathf.Repeat(angleDeg + rimSpeed / wheelRadius * Mathf.Rad2Deg * Time.deltaTime, 360f);
            foreach (var w in wheels)
                if (w != null) w.localRotation = Quaternion.Euler(angleDeg, 0f, 0f); // +X rotation rolls the top forward
            return angleDeg;
        }

        /// <summary>
        /// One step toward target: accel while |speed| grows in the same direction, decel while it shrinks.
        /// A sign change first brakes to zero at decel.
        /// </summary>
        public static float RampSpeed(float current, float target, float accel, float decel, float dt)
        {
            if (current * target < 0f)
                return Mathf.MoveTowards(current, 0f, decel * dt);
            if (Mathf.Abs(target) < Mathf.Abs(current))
                return Mathf.MoveTowards(current, target, decel * dt);
            return Mathf.MoveTowards(current, target, accel * dt);
        }
    }
}
