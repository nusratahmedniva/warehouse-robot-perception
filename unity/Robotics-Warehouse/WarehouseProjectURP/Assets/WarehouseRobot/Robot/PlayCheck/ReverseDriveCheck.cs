using System;
using System.Collections;
using System.Collections.Generic;
using System.Globalization;
using System.IO;
using System.Text;
using UnityEngine;
using WarehouseAvatar;

namespace WarehouseRobot.RobotCheck
{
    /// <summary>
    /// Play-mode check for Anisha's recovery question (Avatar/Config/experiments_ab.md section 15 addendum 1, item 2a): does the robot's
    /// DiffDriveController drive backward on a negative v? In a copy of the v4 scene with TrialRunnerV4 and the bridge client disabled
    /// (Robot/Editor/RecoveryChecksMenu.cs), the robot stands at <see cref="start"/>, one worker in a development look stands
    /// <see cref="workerAheadM"/> ahead (centre to centre), and the driver commands v = -<see cref="speedMps"/>, omega = 0 until the robot
    /// has moved <see cref="distanceM"/> backward, then v = 0. No Python, no perception. Writes report.md and samples.csv into a new
    /// folder robot_vision/outputs/reverse_drive_check_&lt;time&gt;/.
    /// </summary>
    public class ReverseDriveCheck : MonoBehaviour
    {
        public WorkerV4 workerPrefab;
        public LookSource[] extraSources = new LookSource[0];
        public TextAsset looksConfig;
        public string look = "sunbox_m_shirt_white";
        public Vector3 start = new Vector3(6.25f, 0f, -10f);
        public float startYawDeg;
        public float workerAheadM = 1.2f;
        public float speedMps = 0.2f;
        public float distanceM = 1.0f;
        public float settleS = 1.0f;
        public float timeoutS = 30f;
        public string sceneNote = "";

        public string Status { get; private set; } = "running";
        public string OutputFolder { get; private set; } = "";

        static readonly CultureInfo Inv = CultureInfo.InvariantCulture;

        struct Sample { public float T, V, X, Z, Yaw; public string Phase; }

        IEnumerator Start()
        {
            var robot = FindFirstObjectByType<RobotRig>();
            if (robot == null || robot.Drive == null) { Status = "failed: no robot (RobotRig with DiffDriveController) in the scene"; yield break; }
            var drive = robot.Drive;
            var rb = robot.GetComponent<Rigidbody>();
            float y = robot.transform.position.y;
            var rot = Quaternion.Euler(0f, startYawDeg, 0f);
            drive.ResetMotion();
            var pos = new Vector3(start.x, y, start.z);
            if (rb != null) { rb.position = pos; rb.rotation = rot; rb.velocity = Vector3.zero; rb.angularVelocity = Vector3.zero; }
            robot.transform.SetPositionAndRotation(pos, rot);

            Vector3 fwd0 = rot * Vector3.forward;
            WorkerV4 w = null;
            string workerNote;
            if (workerPrefab != null)
            {
                w = Instantiate(workerPrefab);
                w.name = "WorkerV4_" + look;
                w.lookId = look;
                w.workerId = 1;
                w.robot = robot.transform;
                w.robotEye = robot.PanTilt != null ? robot.PanTilt.transform : robot.transform;
                if (looksConfig != null) w.extraLooks = new List<LookEntry>(ExperimentLooks.Parse(looksConfig.text).looks);
                var sources = new List<LookSource>(w.lookSources);
                sources.AddRange(extraSources);
                w.lookSources = sources.ToArray();
                var wp = new Vector3(pos.x, 0f, pos.z) + fwd0 * workerAheadM;
                wp.y = FloorY(wp, y);
                w.transform.SetPositionAndRotation(wp, Quaternion.LookRotation(-fwd0, Vector3.up));
                if (!w.Initialize())
                {
                    Status = $"failed: worker {look} not spawned: {w.Problem}";
                    yield break;
                }
                workerNote = $"{look} ({w.LookDescription}) at ({F(wp.x)}, {F(wp.z)}), {F(workerAheadM)} m ahead centre to centre, facing the robot";
            }
            else workerNote = "none (no worker template)";

            float t0 = Time.time;
            while (Time.time - t0 < settleS) yield return new WaitForFixedUpdate();
            Vector3 p0 = robot.transform.position;
            float yaw0 = robot.transform.eulerAngles.y;
            int collisions0 = robot.Collisions != null ? robot.Collisions.Records.Count : 0;
            var samples = new List<Sample>();
            float tStart = Time.time, tSpeed = -1f, tStopCmd = -1f, minV = 0f, dAtStop = 0f;
            float minWorkerM = w != null ? Flat(w.transform.position - p0) : -1f;

            // reverse until distanceM backward (or the timeout), then v = 0 until standstill
            while (true)
            {
                drive.SetCommand(-speedMps, 0f);
                yield return new WaitForFixedUpdate();
                var s = Take(robot, tStart, "reverse");
                samples.Add(s);
                minV = Mathf.Min(minV, drive.V);
                if (tSpeed < 0f && drive.V <= -0.99f * speedMps) tSpeed = s.T;
                if (w != null) minWorkerM = Mathf.Min(minWorkerM, Flat(w.transform.position - robot.transform.position));
                float back = Vector3.Dot(robot.transform.position - p0, -fwd0);
                if (back >= distanceM) { dAtStop = back; tStopCmd = s.T; break; }
                if (s.T > timeoutS) { Status = $"failed: moved only {F(back)} m backward in {F(timeoutS)} s (V {drive.V.ToString("0.000", Inv)} m/s)"; break; }
            }
            float tHold = Time.time;
            while (Time.time - tHold < 5f)
            {
                drive.SetCommand(0f, 0f);
                yield return new WaitForFixedUpdate();
                samples.Add(Take(robot, tStart, "stop"));
                if (Mathf.Abs(drive.V) < 1e-4f && Time.time - tHold > 0.5f) break;
            }
            Vector3 p1 = robot.transform.position;
            Vector3 d = p1 - p0;
            float backFinal = Vector3.Dot(d, -fwd0);
            float lateral = Vector3.Dot(d, Vector3.Cross(Vector3.up, fwd0));
            float yawChange = Mathf.DeltaAngle(yaw0, robot.transform.eulerAngles.y);
            int collisions = (robot.Collisions != null ? robot.Collisions.Records.Count : 0) - collisions0;
            bool ok = Status == "running" && Mathf.Abs(backFinal - distanceM) < 0.1f && Mathf.Abs(lateral) < 0.02f && Mathf.Abs(yawChange) < 0.5f && collisions == 0;

            var cfg = robot.Config;
            var sb = new StringBuilder();
            sb.Append($"# Reverse drive check ({DateTime.Now.ToString("yyyy-MM-dd HH:mm:ss", Inv)})\n\n");
            sb.Append("experiments_ab.md section 15 addendum 1, item 2a (Anisha's recovery: back up 1.0 m at 0.2 m/s). Play mode, a copy of the v4 scene with " +
                      "TrialRunnerV4 and the bridge client disabled (no Python, no perception, nothing saved). The command goes to " +
                      "DiffDriveController.SetCommand(v, omega) as the bridge client passes Python's command (RobotBridgeClient: robot.Drive.SetCommand(cmd.v, cmd.omega)).\n\n");
            if (sceneNote.Length > 0) sb.Append(sceneNote + "\n\n");
            sb.Append($"- Robot config: max_speed_mps {F(cfg.Robot.max_speed_mps)}, max_accel_mps2 {F(cfg.Robot.max_accel_mps2)}, decel_mps2 {F(cfg.Robot.decel_mps2)} " +
                      "(SetCommand clamps v to +-max_speed_mps; FixedUpdate sets the body velocity to forward x V, so a negative V drives backward).\n");
            sb.Append($"- Start ({F(p0.x)}, {F(p0.z)}), heading {F(yaw0)} deg; worker: {workerNote}.\n");
            sb.Append($"- Command v = {F(-speedMps)} m/s, omega = 0 until {F(distanceM)} m backward, then v = 0.\n\n");
            sb.Append("| quantity | value |\n|---|---|\n");
            sb.Append($"| result | {(ok ? "PASS: drives backward as commanded" : "CHECK: " + (Status == "running" ? "see the values" : Status))} |\n");
            sb.Append($"| time to reach 0.99 x {F(speedMps)} m/s backward | {(tSpeed >= 0f ? F(tSpeed) + " s" : "not reached")} |\n");
            sb.Append($"| most negative V (the signed speed telemetry sends as v) | {minV.ToString("0.0000", Inv)} m/s |\n");
            sb.Append($"| backward distance when v = 0 was commanded | {dAtStop.ToString("0.000", Inv)} m (t {F(tStopCmd)} s) |\n");
            sb.Append($"| backward distance at standstill | {backFinal.ToString("0.000", Inv)} m (overshoot {(backFinal - dAtStop).ToString("0.000", Inv)} m) |\n");
            sb.Append($"| lateral drift | {lateral.ToString("0.0000", Inv)} m |\n");
            sb.Append($"| heading change | {yawChange.ToString("0.000", Inv)} deg |\n");
            sb.Append($"| robot centre to worker centre: before / closest / after | {(w != null ? $"{F(Flat(w.transform.position - p0))} / {F(minWorkerM)} / {F(Flat(w.transform.position - p1))} m" : "-")} |\n");
            sb.Append($"| collisions recorded | {collisions} |\n");
            sb.Append($"| fixed steps sampled | {samples.Count} (fixed dt {F(Time.fixedDeltaTime)} s) |\n\n");
            sb.Append("PASS rule (declared with the check): within 0.1 m of the distance, lateral drift under 0.02 m, heading change under 0.5 deg, no collision.\n");
            var csv = new StringBuilder("t_s,phase,v_mps,x,z,yaw_deg\n");
            foreach (var s in samples)
                csv.Append($"{s.T.ToString("0.000", Inv)},{s.Phase},{s.V.ToString("0.0000", Inv)},{s.X.ToString("0.0000", Inv)},{s.Z.ToString("0.0000", Inv)},{s.Yaw.ToString("0.000", Inv)}\n");

            try
            {
                string root = Path.GetFullPath(Path.Combine(Application.dataPath, "..", "..", "..", "..", "robot_vision", "outputs"));
                OutputFolder = Path.Combine(root, "reverse_drive_check_" + DateTime.Now.ToString("yyyyMMdd_HHmmss", Inv));
                if (Directory.Exists(OutputFolder)) { Status = "failed: " + OutputFolder + " exists"; yield break; }
                Directory.CreateDirectory(OutputFolder);
                WriteNew(Path.Combine(OutputFolder, "report.md"), sb.ToString());
                WriteNew(Path.Combine(OutputFolder, "samples.csv"), csv.ToString());
            }
            catch (Exception e) { Status = "failed: cannot write the report: " + e.Message; yield break; }
            Debug.Log("[ReverseDriveCheck]\n" + sb);
            if (Status == "running") Status = ok ? "done: PASS" : "done: CHECK";
        }

        static Sample Take(RobotRig robot, float tStart, string phase) => new Sample
        {
            T = Time.time - tStart, V = robot.Drive.V, X = robot.transform.position.x, Z = robot.transform.position.z,
            Yaw = robot.transform.eulerAngles.y, Phase = phase,
        };

        static float FloorY(Vector3 p, float fallback)
        {
            return Physics.Raycast(new Vector3(p.x, fallback + 2f, p.z), Vector3.down, out var hit, 10f, ~0, QueryTriggerInteraction.Ignore) ? hit.point.y : 0f;
        }

        static float Flat(Vector3 v) => new Vector2(v.x, v.z).magnitude;
        static string F(float v) => v.ToString("0.00", Inv);

        static void WriteNew(string path, string text)
        {
            using (var fs = new FileStream(path, FileMode.CreateNew, FileAccess.Write))
            {
                var b = new UTF8Encoding(false).GetBytes(text);
                fs.Write(b, 0, b.Length);
            }
        }
    }
}
