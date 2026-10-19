using System.Collections;
using System.Collections.Generic;
using System.IO;
using UnityEngine;

namespace WarehouseHRI
{
    /// <summary>
    /// DEVELOPMENT gesture evaluation (hri_config.json -> trials.task = "GestureSweep", development mode only).
    /// The robot stands still; the worker shows each of the seven commands (incl. NONE) gesture_sweep.repeats times in
    /// a seeded random order (dev_seed), at a random distance, view angle and worker yaw. The robot's camera images go
    /// to Python as usual; Unity writes the truth (what was shown, where) to truth_sweep.csv, which only
    /// robot_vision/hri_eval_dev.py reads. RobotBrain is not used (no decisions), so the result is the vision
    /// reading per frame, independent of the 1.0 s hold rule.
    /// </summary>
    public class GestureSweep : MonoBehaviour
    {
        public DiffDriveRobot robot;
        public GestureWorker worker;
        public PanTiltCamera panTilt;
        public HriBridgeClient bridge;
        public TrialManager trialManager;
        [Tooltip("Where the worker stands during the sweep (defaults to the worker's position at start).")]
        public Transform stand;

        public static readonly GestureCommand[] Commands =
        {
            GestureCommand.NONE, GestureCommand.LEFT, GestureCommand.FORWARD_LEFT, GestureCommand.FORWARD,
            GestureCommand.FORWARD_RIGHT, GestureCommand.RIGHT, GestureCommand.STOP,
        };

        public bool Active { get; private set; }
        public string Status { get; private set; } = "";
        public string SessionFolder { get; private set; }

        void Awake()
        {
            Active = string.Equals(HriConfig.Current.trials.task, "GestureSweep", System.StringComparison.OrdinalIgnoreCase);
            if (Active && trialManager != null) trialManager.runOnStart = false; // the sweep replaces the trials
        }

        void Start()
        {
            if (Active) StartCoroutine(Run());
        }

        /// <summary>Seeded sample order: every command 'repeats' times, shuffled (Fisher-Yates on GoalSequence).</summary>
        public static List<GestureCommand> Order(int seed, int repeats)
        {
            var list = new List<GestureCommand>();
            for (int r = 0; r < repeats; r++) list.AddRange(Commands);
            var rng = new GoalSequence(seed);
            for (int i = list.Count - 1; i > 0; i--)
            {
                int j = rng.NextInt(i + 1);
                (list[i], list[j]) = (list[j], list[i]);
            }

            return list;
        }

        static float Uniform(GoalSequence rng, float a, float b) => a + (b - a) * (float)((rng.NextUInt64() >> 11) * (1.0 / (1UL << 53)));

        IEnumerator Run()
        {
            var cfg = HriConfig.Current;
            var s = cfg.gesture_sweep;
            if (cfg.IsFinal)
            {
                Status = "GestureSweep refused: it is a development evaluation (trials.mode must be development)";
                Debug.LogError("[WarehouseHRI] " + Status);
                yield break;
            }

            string root = HriOutput.ResolveRoot(cfg.output_root);
            SessionFolder = HriOutput.CreateSessionFolder(root, "gestures_sweep_development");
            string configText = HriConfig.SourceText ?? JsonUtility.ToJson(cfg, true);
            HriOutput.WriteNew(Path.Combine(SessionFolder, "hri_config.json"), configText);
            if (HriConfig.LocalText != null) HriOutput.WriteNew(Path.Combine(SessionFolder, "hri_config.local.json"), HriConfig.LocalText);
            HriOutput.ReadGit(out var commit, out var branch);
            int seed = cfg.trials.dev_seed;
            HriOutput.WriteNew(Path.Combine(SessionFolder, "session.json"),
                "{\n  \"task\": \"GestureSweep\",\n  \"mode\": \"development\",\n" +
                $"  \"seed\": {seed},\n  \"config_sha256\": \"{HriOutput.Sha256(HriConfig.EffectiveText)}\",\n" +
                $"  \"git_commit\": \"{commit}\",\n  \"git_branch\": \"{branch}\",\n" +
                $"  \"perception_mode\": \"{(cfg.IsVision ? "vision" : "scripted-gesture baseline")}\",\n" +
                $"  \"samples\": {Commands.Length * s.repeats}\n}}\n");
            using (var truth = HriOutput.CreateNewWriter(Path.Combine(SessionFolder, "truth_sweep.csv")))
            {
                truth.WriteLine("sample,gesture_shown,t_start,t_end,distance_m,view_angle_deg,worker_yaw_offset_deg,worker_x,worker_z,robot_x,robot_z,robot_heading_deg");
                if (bridge != null && bridge.linkEnabled)
                {
                    Status = "GestureSweep: waiting for the Python bridge";
                    while (!bridge.Connected) yield return null;
                }

                Vector3 w0 = stand != null ? stand.position : worker.transform.position;
                float baseYaw = stand != null ? stand.eulerAngles.y : worker.transform.eulerAngles.y;
                worker.faceTarget = null;
                var order = Order(seed, s.repeats);
                var rng = new GoalSequence(seed ^ 0x5eed);
                for (int i = 0; i < order.Count; i++)
                {
                    float d = Uniform(rng, s.distance_min_m, s.distance_max_m);
                    float view = Uniform(rng, -s.view_angle_max_deg, s.view_angle_max_deg);
                    float jitter = Uniform(rng, -s.worker_yaw_jitter_deg, s.worker_yaw_jitter_deg);
                    // Robot on a circle around the worker, view angle measured from the worker's base facing.
                    Vector3 dir = Quaternion.Euler(0f, baseYaw + view, 0f) * Vector3.forward;
                    Vector3 rp = w0 + dir * d;
                    rp.y = robot.transform.position.y;
                    robot.Teleport(rp, Quaternion.LookRotation(-dir).eulerAngles.y);
                    worker.transform.SetPositionAndRotation(w0, Quaternion.Euler(0f, baseYaw + view + jitter, 0f));
                    worker.Show(order[i]);
                    panTilt.AimAt(worker.ChestPosition);
                    Status = $"GestureSweep {i + 1}/{order.Count}: {order[i]} at {d:0.00} m";
                    float t0 = Time.time + s.settle_s;
                    while (Time.time < t0) yield return null;
                    float t1 = t0 + s.hold_s;
                    while (Time.time < t1) yield return null;
                    truth.WriteLine(string.Join(",", (i + 1).ToString(HriOutput.Inv), order[i].ToString(),
                        HriOutput.F(t0, "0.000"), HriOutput.F(t1, "0.000"), HriOutput.F(d, "0.000"), HriOutput.F(view, "0.0"),
                        HriOutput.F(jitter, "0.0"), HriOutput.F(w0.x, "0.000"), HriOutput.F(w0.z, "0.000"),
                        HriOutput.F(rp.x, "0.000"), HriOutput.F(rp.z, "0.000"), HriOutput.F(robot.YawDeg, "0.0")));
                }
            }

            worker.Show(GestureCommand.NONE);
            Status = "GestureSweep done";
            Debug.Log($"[WarehouseHRI] GestureSweep done: {HriOutput.Relative(root, SessionFolder)}");
        }
    }
}
