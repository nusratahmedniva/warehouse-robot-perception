using System;
using System.Collections.Generic;
using UnityEngine;
using UnityEngine.AI;

namespace WarehouseHRI
{
    /// <summary>
    /// Differential-drive robot on a Rigidbody, commanded only by forward speed v (m/s) and turn rate w (deg/s,
    /// + = right). The body is planar: roll, pitch and height are frozen and gravity is off, so cameras on the robot
    /// stay level and the collider (lifted by its ground clearance) touches only real obstacles, never the floor. Works with any body mesh: the
    /// physics is the Rigidbody + collider on this object; wheel transforms are optional and only spun for show.
    /// GoTo() follows NavMesh path corners with pure pursuit (straight line when there is no NavMesh); obstacle
    /// avoidance therefore comes from the NavMesh map, not from the cameras.
    /// </summary>
    [RequireComponent(typeof(Rigidbody))]
    public class DiffDriveRobot : MonoBehaviour
    {
        [Header("Limits (overwritten from hri_config.json when useConfigFile is on)")]
        public bool useConfigFile = true;
        public float maxSpeedMps = 1.0f;
        public float maxTurnRateDps = 60f;
        public float accelMps2 = 0.5f;
        public float decelMps2 = 0.5f;
        public float emergencyDecelMps2 = 1.5f;
        public float angularAccelDps2 = 180f;

        [Header("Pure pursuit")]
        public float lookAheadM = 0.8f;
        public float rotateInPlaceDeg = 60f;
        public float turnGain = 2f;
        public float alignToleranceDeg = 5f;
        public float replanDeviationM = 1f;

        [Header("Wheels (optional, visual only)")]
        public Transform[] leftWheels = new Transform[0];
        public Transform[] rightWheels = new Transform[0];
        [Tooltip("Local axis each wheel spins around.")]
        public Vector3 wheelSpinAxis = Vector3.right;
        public float wheelRadiusM = 0.1f;
        public float trackWidthM = 0.5f;

        [Header("Watchdog (Unity stops the robot itself when Python is silent)")]
        public PythonLinkWatchdog watchdog;

        /// <summary>Raised for every collision that is not floor contact.</summary>
        public event Action<Collision> Collided;

        enum Mode { Manual, Path, Turn }

        Rigidbody m_Body;
        Mode m_Mode = Mode.Manual;
        float m_CmdV, m_CmdW, m_V, m_W;
        bool m_Emergency;
        readonly List<Vector2> m_Path = new List<Vector2>();
        int m_Segment;
        float m_StopDistance, m_SpeedScale = 1f;
        Vector3 m_Goal, m_TurnPoint;
        NavMeshPath m_NavPath;

        /// <summary>Applied forward speed (m/s) after acceleration limits.</summary>
        public float V => m_V;
        /// <summary>Applied turn rate (deg/s, + = right) after acceleration limits.</summary>
        public float W => m_W;
        /// <summary>Commanded forward speed before acceleration limits.</summary>
        public float CommandedV => m_CmdV;
        public float CommandedW => m_CmdW;
        public bool Arrived { get; private set; }
        public bool Aligned { get; private set; }
        public bool UsedNavMesh { get; private set; }
        public bool WatchdogStopped { get; private set; }
        public IReadOnlyList<Vector2> Path => m_Path;
        public float YawDeg => transform.eulerAngles.y;
        public Vector2 PositionXZ => new Vector2(transform.position.x, transform.position.z);
        public Rigidbody Body => m_Body != null ? m_Body : (m_Body = GetComponent<Rigidbody>());

        /// <summary>Measured horizontal speed of the Rigidbody, m/s.</summary>
        public float MeasuredSpeed
        {
            get { var v = Body.velocity; v.y = 0f; return v.magnitude; }
        }

        /// <summary>Measured turn rate of the Rigidbody, deg/s (+ = right).</summary>
        public float MeasuredTurnRateDps => Body.angularVelocity.y * Mathf.Rad2Deg;

        public const RigidbodyConstraints PlanarConstraints =
            RigidbodyConstraints.FreezePositionY | RigidbodyConstraints.FreezeRotationX | RigidbodyConstraints.FreezeRotationZ;

        void Awake()
        {
            m_Body = GetComponent<Rigidbody>();
            m_Body.constraints = PlanarConstraints;
            m_Body.useGravity = false;
            m_Body.interpolation = RigidbodyInterpolation.Interpolate;
            m_NavPath = new NavMeshPath();
            if (useConfigFile) ApplyConfig(HriConfig.Current.robot);
        }

        public void ApplyConfig(HriConfig.RobotSettings r)
        {
            maxSpeedMps = r.max_speed_mps;
            maxTurnRateDps = r.max_turn_rate_dps;
            accelMps2 = r.accel_mps2;
            decelMps2 = r.decel_mps2;
            emergencyDecelMps2 = r.emergency_decel_mps2;
            angularAccelDps2 = r.angular_accel_dps2;
            lookAheadM = r.lookahead_m;
            rotateInPlaceDeg = r.rotate_in_place_deg;
            turnGain = r.turn_gain;
            alignToleranceDeg = r.align_tolerance_deg;
            replanDeviationM = r.replan_deviation_m;
        }

        /// <summary>Direct command (used by Python steering in Step 5). Clamped to the limits.</summary>
        public void SetCommand(float v, float wDeg)
        {
            m_Mode = Mode.Manual;
            m_Emergency = false;
            Arrived = false;
            m_CmdV = Mathf.Clamp(v, -maxSpeedMps, maxSpeedMps);
            m_CmdW = Mathf.Clamp(wDeg, -maxTurnRateDps, maxTurnRateDps);
        }

        /// <summary>Command zero speed. Emergency stops brake with the emergency deceleration.</summary>
        public void Stop(bool emergency = false)
        {
            m_Mode = Mode.Manual;
            m_CmdV = 0f;
            m_CmdW = 0f;
            m_Emergency = emergency;
        }

        /// <summary>
        /// Drive to <paramref name="target"/> along NavMesh path corners (straight line if no NavMesh path exists),
        /// stopping within <paramref name="stopDistance"/>. Returns true when a NavMesh path was found.
        /// </summary>
        public bool GoTo(Vector3 target, float stopDistance, float speedScale = 1f)
        {
            m_Goal = target;
            m_StopDistance = Mathf.Max(0.01f, stopDistance);
            m_SpeedScale = Mathf.Clamp01(speedScale);
            m_Emergency = false;
            Arrived = false;
            Plan();
            m_Mode = Mode.Path;
            return UsedNavMesh;
        }

        public void SetSpeedScale(float speedScale) => m_SpeedScale = Mathf.Clamp01(speedScale);

        /// <summary>Turn in place until facing <paramref name="point"/> (see Aligned).</summary>
        public void TurnToward(Vector3 point)
        {
            m_TurnPoint = point;
            m_Mode = Mode.Turn;
            m_Emergency = false;
            Aligned = false;
            Arrived = false;
        }

        /// <summary>Place the robot (trial reset). Velocities are zeroed.</summary>
        public void Teleport(Vector3 position, float yawDeg)
        {
            Stop();
            m_V = 0f;
            m_W = 0f;
            Arrived = false;
            Aligned = false;
            Body.velocity = Vector3.zero;
            Body.angularVelocity = Vector3.zero;
            Body.position = position;
            Body.rotation = Quaternion.Euler(0f, yawDeg, 0f);
            transform.SetPositionAndRotation(position, Quaternion.Euler(0f, yawDeg, 0f));
        }

        void Plan()
        {
            m_Path.Clear();
            m_Segment = 0;
            UsedNavMesh = false;
            Vector3 from = transform.position;
            if (NavMesh.SamplePosition(from, out var a, 2f, NavMesh.AllAreas) &&
                NavMesh.SamplePosition(m_Goal, out var b, 2f, NavMesh.AllAreas) &&
                NavMesh.CalculatePath(a.position, b.position, NavMesh.AllAreas, m_NavPath) &&
                m_NavPath.status == NavMeshPathStatus.PathComplete)
            {
                UsedNavMesh = true;
                m_Path.Add(PurePursuit.XZ(from));
                var corners = m_NavPath.corners;
                for (int i = 1; i < corners.Length; i++) m_Path.Add(PurePursuit.XZ(corners[i]));
                // The NavMesh snaps the goal; end exactly at the requested point when it is close.
                if (Vector2.Distance(m_Path[m_Path.Count - 1], PurePursuit.XZ(m_Goal)) < 0.5f)
                    m_Path[m_Path.Count - 1] = PurePursuit.XZ(m_Goal);
            }
            else
            {
                m_Path.Add(PurePursuit.XZ(from));
                m_Path.Add(PurePursuit.XZ(m_Goal));
            }
        }

        float DistanceToPath(Vector2 p)
        {
            if (m_Path.Count < 2) return 0f;
            int i = Mathf.Clamp(m_Segment, 0, m_Path.Count - 2);
            Vector2 a = m_Path[i], b = m_Path[i + 1], ab = b - a;
            float t = Mathf.Clamp01(Vector2.Dot(p - a, ab) / Mathf.Max(ab.sqrMagnitude, 1e-8f));
            return Vector2.Distance(p, a + ab * t);
        }

        void FixedUpdate()
        {
            float dt = Time.fixedDeltaTime;
            Vector2 pos = PositionXZ;

            switch (m_Mode)
            {
                case Mode.Path:
                    if (DistanceToPath(pos) > replanDeviationM) Plan();
                    var s = new PurePursuit.Settings
                    {
                        MaxSpeed = maxSpeedMps * m_SpeedScale, MaxTurnRateDeg = maxTurnRateDps, LookAhead = lookAheadM,
                        RotateInPlaceDeg = rotateInPlaceDeg, TurnGain = turnGain, Decel = decelMps2,
                        StopDistance = m_StopDistance,
                    };
                    var r = PurePursuit.Step(pos, YawDeg, m_Path, ref m_Segment, s);
                    if (r.Arrived)
                    {
                        Arrived = true;
                        Stop();
                    }
                    else
                    {
                        m_CmdV = r.V;
                        m_CmdW = r.WDeg;
                    }

                    break;

                case Mode.Turn:
                    float err = PurePursuit.HeadingError(pos, YawDeg, PurePursuit.XZ(m_TurnPoint));
                    if (Mathf.Abs(err) <= alignToleranceDeg && Mathf.Abs(m_W) < 5f)
                    {
                        Aligned = true;
                        m_CmdV = 0f;
                        m_CmdW = 0f;
                    }
                    else
                    {
                        m_CmdV = 0f;
                        m_CmdW = Mathf.Clamp(turnGain * err, -maxTurnRateDps, maxTurnRateDps);
                    }

                    break;
            }

            // Watchdog: Unity stops the robot by itself when Python has been silent too long.
            WatchdogStopped = watchdog != null && watchdog.ShouldStop;
            float cmdV = WatchdogStopped ? 0f : m_CmdV;
            float cmdW = WatchdogStopped ? 0f : m_CmdW;
            bool emergency = m_Emergency || WatchdogStopped;

            float dec = emergency ? emergencyDecelMps2 : decelMps2;
            float rate = Mathf.Abs(cmdV) > Mathf.Abs(m_V) ? accelMps2 : dec;
            m_V = Mathf.MoveTowards(m_V, cmdV, rate * dt);
            float angRate = emergency ? angularAccelDps2 * 3f : angularAccelDps2;
            m_W = Mathf.MoveTowards(m_W, cmdW, angRate * dt);

            Vector3 fwd = transform.forward;
            fwd.y = 0f;
            fwd.Normalize();
            Body.velocity = new Vector3(fwd.x * m_V, 0f, fwd.z * m_V);
            Body.angularVelocity = new Vector3(0f, m_W * Mathf.Deg2Rad, 0f);

            SpinWheels(dt);
        }

        void SpinWheels(float dt)
        {
            if (wheelRadiusM <= 0f) return;
            float wRad = m_W * Mathf.Deg2Rad;
            // Turning right (w > 0): the left wheels roll faster than the right ones.
            float vl = m_V + wRad * trackWidthM * 0.5f;
            float vr = m_V - wRad * trackWidthM * 0.5f;
            float degL = vl / wheelRadiusM * Mathf.Rad2Deg * dt;
            float degR = vr / wheelRadiusM * Mathf.Rad2Deg * dt;
            foreach (var t in leftWheels) if (t != null) t.Rotate(wheelSpinAxis, degL, Space.Self);
            foreach (var t in rightWheels) if (t != null) t.Rotate(wheelSpinAxis, degR, Space.Self);
        }

        void OnCollisionEnter(Collision collision)
        {
            // Floor contact (all normals pointing up) is not a collision.
            bool floorOnly = true;
            for (int i = 0; i < collision.contactCount; i++)
            {
                if (collision.GetContact(i).normal.y < 0.7f)
                {
                    floorOnly = false;
                    break;
                }
            }

            if (!floorOnly) Collided?.Invoke(collision);
        }

        void OnDrawGizmosSelected()
        {
            if (m_Path.Count < 2) return;
            Gizmos.color = Color.cyan;
            float y = transform.position.y + 0.05f;
            for (int i = 0; i < m_Path.Count - 1; i++)
                Gizmos.DrawLine(new Vector3(m_Path[i].x, y, m_Path[i].y), new Vector3(m_Path[i + 1].x, y, m_Path[i + 1].y));
        }
    }
}
