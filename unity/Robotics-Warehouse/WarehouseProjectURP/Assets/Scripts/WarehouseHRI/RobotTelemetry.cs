using System.IO;
using UnityEngine;

namespace WarehouseHRI
{
    /// <summary>
    /// Time series of one run, one row every interval_s (0.1 s) of simulation time, written to a new CSV file
    /// (never overwritten). Positions are floor coordinates (x, z; y is up); heading is Unity yaw in degrees
    /// (0 = +z, 90 = +x). link = Python bridge up/down/off; inference_ms (Python-side time) and round_trip_ms are
    /// those of the latest perception reply, empty when no reply arrived in the row's interval.
    /// </summary>
    public class RobotTelemetry : MonoBehaviour
    {
        public const string Header =
            "t_s,trial,state,x,z,heading_deg,v_cmd_mps,w_cmd_dps,v_mps,w_dps,speed_meas_mps,turn_meas_dps," +
            "people_detected,gesture_read,safety_stop,safety_reason,watchdog_stop,link,inference_ms,round_trip_ms," +
            "t_sim,perception,yolo_cam360_ms,yolo_gesture_ms,mediapipe_ms,vision_target_distance_m,vision_gesture_source";

        /// <summary>Raised after each row with its t_s, so the scoring side can write a truth row on the same grid.</summary>
        public event System.Action<float> RowWritten;

        public bool useConfigFile = true;
        public float intervalS = 0.1f;
        public DiffDriveRobot robot;
        public RobotBrain brain;
        public HriBridgeClient bridge;

        StreamWriter m_Writer;
        float m_T0, m_Next;
        int m_Trial;

        public bool Recording => m_Writer != null;
        public string FilePath { get; private set; }
        public int Rows { get; private set; }

        void Awake()
        {
            if (robot == null) robot = GetComponent<DiffDriveRobot>();
            if (brain == null) brain = GetComponent<RobotBrain>();
            if (bridge == null) bridge = GetComponent<HriBridgeClient>();
            if (useConfigFile) intervalS = HriConfig.Current.telemetry.interval_s;
        }

        /// <summary>Start a new CSV at <paramref name="path"/> (must not exist).</summary>
        public void Begin(string path, int trial)
        {
            End();
            m_Writer = HriOutput.CreateNewWriter(path);
            m_Writer.WriteLine(Header);
            FilePath = path;
            m_Trial = trial;
            m_T0 = Time.fixedTime;
            m_Next = m_T0;
            Rows = 0;
        }

        public void End()
        {
            if (m_Writer == null) return;
            m_Writer.Dispose();
            m_Writer = null;
        }

        void OnDisable() => End();

        void FixedUpdate()
        {
            if (m_Writer == null || Time.fixedTime + 1e-4f < m_Next) return;
            m_Next += intervalS;
            Write(Time.fixedTime - m_T0);
        }

        void Write(float t)
        {
            var p = transform.position;
            string state = brain != null ? brain.State.ToString() : "";
            bool fresh = bridge != null && Time.time - bridge.LastReplyTime <= intervalS * 1.5f; // a reply in this row's interval
            string row = string.Join(",",
                HriOutput.F(t, "0.00"), m_Trial.ToString(HriOutput.Inv), state,
                HriOutput.F(p.x, "0.000"), HriOutput.F(p.z, "0.000"), HriOutput.F(robot.YawDeg, "0.0"),
                HriOutput.F(robot.CommandedV, "0.000"), HriOutput.F(robot.CommandedW, "0.0"),
                HriOutput.F(robot.V, "0.000"), HriOutput.F(robot.W, "0.0"),
                HriOutput.F(robot.MeasuredSpeed, "0.000"), HriOutput.F(robot.MeasuredTurnRateDps, "0.0"),
                brain != null ? brain.PeopleDetected.ToString(HriOutput.Inv) : "",
                brain != null ? brain.LastRead.ToString() : "",
                brain != null && brain.SafetyStopActive ? "1" : "0",
                HriOutput.Csv(brain != null ? brain.SafetyReason : ""),
                robot.WatchdogStopped ? "1" : "0",
                bridge == null || !bridge.linkEnabled ? "off" : bridge.Connected ? "up" : "down",
                fresh ? HriOutput.F(bridge.LastInferenceMs) : "",   // Python time for the latest reply
                fresh ? HriOutput.F(bridge.Rtt.LastMs) : "",        // round trip of the latest reply
                HriOutput.F(Time.time, "0.000"),
                brain != null && brain.GestureSource != null ? HriOutput.Csv(brain.GestureSource.Label) : "",
                fresh ? HriOutput.F(HriProtocol.ModelMs(bridge.LatestPerception, "yolo11s-pose/cam360")) : "",
                fresh ? HriOutput.F(HriProtocol.ModelMs(bridge.LatestPerception, "yolo11s-pose/gesture")) : "",
                fresh ? HriOutput.F(HriProtocol.ModelMs(bridge.LatestPerception, "mediapipe/stop")) : "",
                fresh && bridge.LatestPerception?.target != null ? HriOutput.F(bridge.LatestPerception.target.distance_m) : "",
                fresh && bridge.LatestPerception?.gesture != null ? bridge.LatestPerception.gesture.source : "");
            m_Writer.WriteLine(row);
            Rows++;
            RowWritten?.Invoke(t);
        }
    }
}
