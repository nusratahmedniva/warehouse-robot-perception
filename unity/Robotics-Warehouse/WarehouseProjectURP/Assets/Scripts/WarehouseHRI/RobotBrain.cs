using System;
using System.Collections.Generic;
using UnityEngine;

namespace WarehouseHRI
{
    public enum BrainState { Idle, Navigate, Scan, Approach, Ask, Read, Execute, Done }

    /// <summary>Per-step time categories of the run log.</summary>
    public enum StepKind { navigate = 0, scan = 1, approach = 2, ask = 3, gesture = 4, execute = 5 }

    [Serializable]
    public class JunctionRecord
    {
        public string junction;
        public string shown = "unknown"; // filled by TrialManager from the scripted worker (scoring only)
        public string read = "NONE";      // what the robot accepted (NONE when nothing was accepted)
        public int asks;
        public string result;             // accepted / rejected_no_branch / aborted
        public float t_start;
        public float t_end;
    }

    /// <summary>
    /// The robot's state machine: Idle -> Navigate -> (junction) Scan -> Approach -> Ask -> Read -> Execute ->
    /// Navigate ... -> Done. It knows the roadmap but never the goal B. People and gestures come only through
    /// IPersonSource and IGestureSource, so Step 3/4 swap in the 360 deg camera + YOLO pose over TCP without editing
    /// this class. With the scripted sources the decisions are a SCRIPTED BASELINE (true positions, scripted poses),
    /// and the run log says so.
    ///
    /// Always active (every physics step, before the state logic): a STOP gesture, a person inside the path
    /// corridor ahead, or the watchdog (Python silent for 0.3 s) stops the robot at once with emergency braking.
    /// The state resumes when the condition clears.
    /// </summary>
    public class RobotBrain : MonoBehaviour
    {
        public DiffDriveRobot robot;
        public PanTiltCamera panTilt;
        [Tooltip("Component implementing IPersonSource (defaults to one on this object).")]
        public MonoBehaviour personSourceBehaviour;
        [Tooltip("Component implementing IGestureSource (defaults to one on this object).")]
        public MonoBehaviour gestureSourceBehaviour;
        public PythonLinkWatchdog watchdog;
        public bool useConfigFile = true;
        public HriConfig.BrainSettings settings = new HriConfig.BrainSettings();

        public const string PromptText = "Which direction?";

        public BrainState State { get; private set; } = BrainState.Idle;
        public string Prompt { get; private set; } = "";
        public RoadNode CurrentNode { get; private set; }
        public RoadNode TargetNode { get; private set; }
        public bool Finished => State == BrainState.Done;
        public bool Aborted { get; private set; }
        public string AbortReason { get; private set; } = "";
        public bool Halted { get; private set; }
        public bool SafetyStopActive { get; private set; }
        public string SafetyReason { get; private set; } = "";
        public GestureCommand LastRead { get; private set; } = GestureCommand.NONE;
        public int PeopleDetected { get; private set; }
        public float SafetyStopSeconds { get; private set; }
        public readonly float[] StepSeconds = new float[6];
        public IPersonSource PersonSource { get; private set; }
        public IGestureSource GestureSource { get; private set; }
        public GestureDialog Dialog { get; private set; }

        /// <summary>Raised when the robot starts driving to a node (TrialManager moves the worker there).</summary>
        public event Action<RoadNode> HeadingTo;
        /// <summary>Raised when a junction dialog ends (accepted or aborted).</summary>
        public event Action<JunctionRecord> JunctionFinished;

        readonly List<PersonObservation> m_People = new List<PersonObservation>();
        PersonObservation m_Target;
        Vector3 m_ApproachPoint;
        bool m_ApproachTurning;
        RoadNode m_Next;
        JunctionRecord m_Record;
        float m_StateStart;

        float Now => Time.time;
        float InState => Now - m_StateStart;

        void Awake()
        {
            if (robot == null) robot = GetComponent<DiffDriveRobot>();
            if (useConfigFile) settings = HriConfig.Current.brain;
            PersonSource = personSourceBehaviour as IPersonSource ?? GetComponent<IPersonSource>();
            GestureSource = gestureSourceBehaviour as IGestureSource ?? GetComponent<IGestureSource>();
            if (PersonSource == null) Debug.LogError("[WarehouseHRI] RobotBrain: no IPersonSource assigned.");
            if (GestureSource == null) Debug.LogError("[WarehouseHRI] RobotBrain: no IGestureSource assigned.");
            Dialog = new GestureDialog(settings.gesture_hold_s, settings.gesture_window_s, settings.max_asks);
        }

        /// <summary>Start a run at <paramref name="start"/> (point A).</summary>
        public void Begin(RoadNode start)
        {
            Aborted = false;
            Halted = false;
            AbortReason = "";
            SafetyStopActive = false;
            SafetyReason = "";
            SafetyStopSeconds = 0f;
            LastRead = GestureCommand.NONE;
            Prompt = "";
            Array.Clear(StepSeconds, 0, StepSeconds.Length);
            Dialog.Reset();
            if (panTilt != null) panTilt.ResetForward();
            Arrive(start);
        }

        /// <summary>Stop now and end the run (collision, timeout or stuck detected by the trial manager).</summary>
        public void Halt(string reason)
        {
            Halted = true;
            if (string.IsNullOrEmpty(AbortReason)) AbortReason = reason;
            if (robot != null) robot.Stop(true);
            Prompt = "";
            SetState(BrainState.Done);
        }

        void SetState(BrainState s)
        {
            State = s;
            m_StateStart = Now;
        }

        void Arrive(RoadNode node)
        {
            CurrentNode = node;
            if (node == null)
            {
                Abort("no start node");
                return;
            }

            switch (node.kind)
            {
                case RoadNodeKind.Endpoint:
                    robot.Stop();
                    SetState(BrainState.Done);
                    break;
                case RoadNodeKind.Junction:
                    robot.Stop();
                    Dialog.Reset();
                    SetState(BrainState.Scan);
                    break;
                default:
                    var next = node.OnlyNext;
                    if (next == null) Abort($"dead end at {node.name}");
                    else StartNavigate(next);
                    break;
            }
        }

        void StartNavigate(RoadNode node)
        {
            TargetNode = node;
            HeadingTo?.Invoke(node);
            robot.GoTo(node.Position, node.IsEndpoint ? settings.endpoint_stop_m : settings.junction_stop_m, 1f);
            SetState(BrainState.Navigate);
        }

        void Abort(string reason)
        {
            Aborted = true;
            AbortReason = reason;
            if (robot != null) robot.Stop();
            Prompt = "";
            if (panTilt != null) panTilt.ResetForward();
            if (m_Record != null) FinishRecord("aborted");
            SetState(BrainState.Done);
        }

        void FinishRecord(string result)
        {
            m_Record.result = result;
            m_Record.asks = Dialog.AskCount;
            m_Record.read = Dialog.Accepted.ToString();
            m_Record.t_end = Now;
            var r = m_Record;
            m_Record = null;
            JunctionFinished?.Invoke(r);
        }

        void FixedUpdate()
        {
            if (State == BrainState.Idle || State == BrainState.Done || robot == null) return;
            float dt = Time.fixedDeltaTime;
            StepSeconds[(int)StepOf(State)] += dt;

            // Perception (the scripted baseline or, from Step 4, vision).
            PersonSource?.Detect(transform.position, m_People);
            PeopleDetected = m_People.Count;
            int nearest = NearestIndex();
            var readFrom = State == BrainState.Read || State == BrainState.Ask ? m_Target.Worker
                : nearest >= 0 ? m_People[nearest].Worker : null;
            GestureCommand now = GestureSource != null ? GestureSource.Read(readFrom) : GestureCommand.NONE;
            LastRead = now;

            // Always-active safety.
            string reason = SafetyCheck(now);
            if (reason != null)
            {
                if (!SafetyStopActive) robot.Stop(true);
                SafetyStopActive = true;
                SafetyReason = reason;
                SafetyStopSeconds += dt;
                robot.Stop(true);
                return;
            }

            if (SafetyStopActive)
            {
                SafetyStopActive = false;
                SafetyReason = "";
                Resume();
            }

            Tick(now);
        }

        static StepKind StepOf(BrainState s)
        {
            switch (s)
            {
                case BrainState.Scan: return StepKind.scan;
                case BrainState.Approach: return StepKind.approach;
                case BrainState.Ask: return StepKind.ask;
                case BrainState.Read: return StepKind.gesture;
                case BrainState.Execute: return StepKind.execute;
                default: return StepKind.navigate;
            }
        }

        int NearestIndex()
        {
            int best = -1;
            for (int i = 0; i < m_People.Count; i++)
                if (best < 0 || m_People[i].Distance < m_People[best].Distance) best = i;
            return best;
        }

        /// <summary>Null when the robot may move, else the reason it must stop now.</summary>
        string SafetyCheck(GestureCommand now)
        {
            if (now == GestureCommand.STOP) return "STOP gesture";
            if (watchdog != null && watchdog.ShouldStop) return "watchdog: Python silent";
            Vector3 f = transform.forward, r = transform.right;
            foreach (var p in m_People)
            {
                if (InPath(transform.position, f, r, p.Position, settings.safety_stop_distance_m,
                        settings.safety_corridor_half_width_m))
                    return "person in path";
            }

            return null;
        }

        /// <summary>Pure rule: the person is ahead within <paramref name="ahead"/> m and inside the corridor half-width.</summary>
        public static bool InPath(Vector3 robot, Vector3 forward, Vector3 right, Vector3 person, float ahead, float halfWidth)
        {
            Vector3 d = person - robot;
            d.y = 0f;
            float a = Vector3.Dot(d, forward);
            float l = Mathf.Abs(Vector3.Dot(d, right));
            return a > 0f && a <= ahead && l <= halfWidth;
        }

        void Resume()
        {
            switch (State)
            {
                case BrainState.Navigate:
                    robot.GoTo(TargetNode.Position, TargetNode.IsEndpoint ? settings.endpoint_stop_m : settings.junction_stop_m, 1f);
                    break;
                case BrainState.Approach:
                    if (m_ApproachTurning) robot.TurnToward(m_Target.Position);
                    else robot.GoTo(m_ApproachPoint, settings.approach_tolerance_m, settings.approach_speed_scale);
                    break;
                case BrainState.Execute:
                    robot.TurnToward(m_Next.Position);
                    break;
            }
        }

        void Tick(GestureCommand now)
        {
            switch (State)
            {
                case BrainState.Navigate:
                {
                    Vector3 d = TargetNode.Position - transform.position;
                    d.y = 0f;
                    bool slow = TargetNode.IsJunction && d.magnitude < settings.junction_slow_radius_m;
                    robot.SetSpeedScale(slow ? settings.junction_speed_scale : 1f);
                    if (robot.Arrived && Mathf.Abs(robot.V) < 0.02f && Mathf.Abs(robot.W) < 1f) Arrive(TargetNode);
                    break;
                }

                case BrainState.Scan:
                {
                    robot.Stop();
                    if (InState < settings.scan_min_s) break;
                    int i = NearestIndex();
                    if (i >= 0)
                    {
                        m_Target = m_People[i];
                        Vector3 away = transform.position - m_Target.Position;
                        away.y = 0f;
                        if (away.sqrMagnitude < 1e-4f) away = -transform.forward;
                        m_ApproachPoint = m_Target.Position + away.normalized * settings.approach_distance_m;
                        m_ApproachPoint.y = transform.position.y;
                        m_ApproachTurning = false;
                        m_Record = new JunctionRecord { junction = CurrentNode.name, t_start = Now };
                        robot.GoTo(m_ApproachPoint, settings.approach_tolerance_m, settings.approach_speed_scale);
                        SetState(BrainState.Approach);
                    }
                    else if (InState >= settings.scan_timeout_s)
                    {
                        Abort($"no person found at {CurrentNode.name}");
                    }

                    break;
                }

                case BrainState.Approach:
                    if (!m_ApproachTurning && robot.Arrived && Mathf.Abs(robot.V) < 0.02f)
                    {
                        m_ApproachTurning = true;
                        robot.TurnToward(m_Target.Position);
                    }
                    else if (m_ApproachTurning && robot.Aligned)
                    {
                        StartAsk();
                    }

                    break;

                case BrainState.Ask:
                    robot.Stop();
                    if (panTilt != null) panTilt.AimAt(m_Target.Chest);
                    if (InState >= settings.ask_settle_s && (panTilt == null || panTilt.IsAimed)) SetState(BrainState.Read);
                    break;

                case BrainState.Read:
                {
                    robot.Stop();
                    var ev = Dialog.Update(now, Now);
                    if (ev == DialogEvent.Accepted)
                    {
                        var next = CurrentNode.Next(Dialog.Accepted);
                        if (next != null)
                        {
                            FinishRecord("accepted");
                            Prompt = "";
                            if (panTilt != null) panTilt.ResetForward();
                            m_Next = next;
                            robot.TurnToward(next.Position);
                            SetState(BrainState.Execute);
                            break;
                        }

                        ev = Dialog.Reject(); // a direction with no branch here: same as unclear
                    }

                    if (ev == DialogEvent.AskAgain) StartAsk();
                    else if (ev == DialogEvent.Abort) Abort($"gesture unclear after {Dialog.AskCount} asks at {CurrentNode.name}");
                    break;
                }

                case BrainState.Execute:
                    if (robot.Aligned || Mathf.Abs(PurePursuit.HeadingError(robot.PositionXZ, robot.YawDeg,
                            PurePursuit.XZ(m_Next.Position))) <= settings.execute_align_deg && Mathf.Abs(robot.W) < 5f)
                        StartNavigate(m_Next);
                    break;
            }
        }

        void StartAsk()
        {
            robot.Stop();
            Dialog.BeginAsk(Now);
            Prompt = Dialog.AskCount > 1 ? PromptText + " (asking again)" : PromptText;
            if (panTilt != null) panTilt.AimAt(m_Target.Chest);
            SetState(BrainState.Ask);
        }
    }
}
