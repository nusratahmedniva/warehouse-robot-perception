using System;
using System.Collections;
using System.Collections.Generic;
using System.IO;
using UnityEngine;

namespace WarehouseHRI
{
    [Serializable]
    public class StepTimes
    {
        public float navigate, scan, approach, ask, gesture, execute, safety_stop;
    }

    /// <summary>One run of the per-run log (written as run_###.json).</summary>
    [Serializable]
    public class RunRecord
    {
        public int trial;
        public string task, mode;
        public int seed;
        public bool config_frozen;
        public string config_sha256, git_commit, git_branch;
        public string perception_source, gesture_source;
        public string outcome, failure_reason, detail;
        public int successes, trials_so_far;
        public float success_ratio;
        public string a_name, b_name, final_node;
        public float a_x, a_z, b_x, b_z, final_x, final_z;
        public float final_distance_to_b_m, straight_line_m, travelled_m, total_s;
        public StepTimes step_s = new StepTimes();
        public float avg_speed_mps, max_speed_mps, avg_turn_dps, max_turn_dps;
        public List<JunctionRecord> junctions = new List<JunctionRecord>();
        public int collisions, human_collisions;
        public string collided_with = "";
        public float closest_human_m;
        public string closest_human_note = "horizontal distance from the robot collider to the worker's centre axis; true positions (scoring only)";
        public string link_status = "disabled";
        public string link_perception = "";
        public string link_metrics_note = "-1 = no samples (link disabled or no replies). Round trip: observation written -> its perception reply read, Unity clock. Inference: Python-side time per observation (decode + models).";
        public int link_replies;
        public float round_trip_mean_ms = -1f, round_trip_max_ms = -1f;
        public float inference_mean_ms = -1f, inference_max_ms = -1f;
        public string inference_per_model_ms = "";
        public string abort_reason;
        public string telemetry_file;
    }

    /// <summary>
    /// Runs many trials automatically. Each trial: pick goal B with the seeded GoalSequence (dev_seed in
    /// development, final_seed in final mode), reset the robot to A, script the worker at each junction with the
    /// command toward B (RoadNode.CommandToward, scoring side only), let RobotBrain drive, then score from ground
    /// truth and log. Output: a new folder trials_&lt;mode&gt;_&lt;task&gt;_&lt;time&gt;/ with the exact config, session.json
    /// (git commit, seed, labels), results.csv (one row per run), run_###.json and telemetry_run###.csv.
    /// </summary>
    public class TrialManager : MonoBehaviour
    {
        public const string ResultsHeader =
            "trial,task,mode,seed,perception_source,gesture_source,outcome,failure_reason,detail,success_ratio," +
            "a_x,a_z,b_name,b_x,b_z,straight_line_m,travelled_m,total_s,navigate_s,scan_s,approach_s,ask_s," +
            "gesture_s,execute_s,safety_stop_s,avg_speed_mps,max_speed_mps,avg_turn_dps,max_turn_dps," +
            "final_distance_to_b_m,junctions_shown_vs_read,collisions,human_collisions,closest_human_m," +
            "inference_mean_ms,round_trip_mean_ms";

        [Header("Scene references")]
        public DiffDriveRobot robot;
        public RobotBrain brain;
        [Tooltip("Optional: the Python bridge (Step 3).")]
        public HriBridgeClient bridge;
        public RobotTelemetry telemetry;
        public GestureWorker worker;
        public RoadNode startNode;
        [Tooltip("Possible goals B for Task 2 (empty: every endpoint reachable from the start).")]
        public List<RoadNode> endpoints = new List<RoadNode>();
        [Tooltip("Task 1 goal: the endpoint reached by FORWARD from the first junction.")]
        public RoadNode task1Goal;

        [Tooltip("Viewer-only marker moved to goal B each trial (on a layer the robot cameras do not render).")]
        public Transform goalMarker;

        [Header("Run")]
        public bool runOnStart = true;

        public static TrialManager Active { get; private set; }
        public bool Running { get; private set; }
        public string SessionFolder { get; private set; }
        public int TrialIndex { get; private set; }
        public int TrialTotal { get; private set; }
        public int Successes { get; private set; }
        public string LastSummary { get; private set; } = "";
        public RoadNode CurrentGoal { get; private set; }
        /// <summary>Trials finished so far in this session (the success ratio is Successes / CompletedTrials).</summary>
        public int CompletedTrials { get; private set; }
        /// <summary>Junction dialogs finished in the current trial (shown = scripted, read = what the robot accepted).</summary>
        public IReadOnlyList<JunctionRecord> CurrentRecords => m_Records;

        /// <summary>The command the worker was scripted to show at a junction in this trial (display and scoring only).</summary>
        public GestureCommand ShownAt(RoadNode junction) =>
            junction != null && m_Shown.TryGetValue(junction.name, out var c) ? c : GestureCommand.NONE;
        public string Status { get; private set; } = "idle";

        HriConfig m_Cfg;
        string m_Root, m_ConfigSha, m_Commit, m_Branch;
        StreamWriter m_Results;
        readonly Dictionary<string, GestureCommand> m_Shown = new Dictionary<string, GestureCommand>();
        readonly List<JunctionRecord> m_Records = new List<JunctionRecord>();
        int m_Collisions, m_HumanCollisions;
        Collider m_RobotCollider;

        void OnEnable() => Active = this;

        void OnDisable()
        {
            if (Active == this) Active = null;
            m_Results?.Dispose();
            m_Results = null;
        }

        IEnumerator Start()
        {
            if (!runOnStart) yield break;
            yield return null; // let every Awake/Start run and physics settle for a frame
            yield return RunSession();
        }

        /// <summary>Stop after the current trial (used by the gesture pose test).</summary>
        public void StopSession()
        {
            StopAllCoroutines();
            if (brain != null && !brain.Finished) brain.Halt("session stopped");
            if (telemetry != null) telemetry.End();
            m_Results?.Dispose();
            m_Results = null;
            Running = false;
            Status = "stopped";
        }

        bool Validate(out string error)
        {
            error = null;
            if (robot == null || brain == null || worker == null || startNode == null) error = "robot, brain, worker and startNode must be assigned";
            else if (m_Cfg.trials.dev_seed == m_Cfg.trials.final_seed) error = "dev_seed and final_seed must differ";
            else if (m_Cfg.link.enabled && m_Cfg.link.link_required && (bridge == null || !bridge.linkEnabled))
                error = "link_required is true but no HriBridgeClient is wired to the TrialManager; run Tools > Warehouse HRI > Build Guided Scene again";
            else if (m_Cfg.IsFinal && !m_Cfg.frozen) error ="final mode requires \"frozen\": true in hri_config.json (freeze thresholds after the development trials)";
            return error == null;
        }

        public IEnumerator RunSession()
        {
            m_Cfg = HriConfig.Current;
            if (!Validate(out var error))
            {
                Status = "not started: " + error;
                Debug.LogError("[WarehouseHRI] TrialManager: " + error);
                yield break;
            }

            if (endpoints.Count == 0) endpoints = startNode.ReachableEndpoints();
            bool task1 = string.Equals(m_Cfg.trials.task, "Task1", StringComparison.OrdinalIgnoreCase);
            if (task1 && task1Goal == null)
            {
                Status = "not started: Task1 needs task1Goal";
                Debug.LogError("[WarehouseHRI] TrialManager: Task1 needs task1Goal.");
                yield break;
            }

            m_Root = HriOutput.ResolveRoot(m_Cfg.output_root);
            string mode = m_Cfg.IsFinal ? "final" : "development";
            if (m_Cfg.IsFinal && FinalAlreadyRun(m_Root, out var previous))
            {
                Status = "not started: final trials already run (" + previous + ")";
                Debug.LogError("[WarehouseHRI] Final trials run only once; found " + previous);
                yield break;
            }

            string configText = HriConfig.SourceText ?? JsonUtility.ToJson(m_Cfg, true);
            m_ConfigSha = HriOutput.Sha256(configText);
            HriOutput.ReadGit(out m_Commit, out m_Branch);
            int seed = m_Cfg.ActiveSeed;
            string task = task1 ? "Task1" : "Task2";
            SessionFolder = HriOutput.CreateSessionFolder(m_Root, $"trials_{mode}_{task}");
            HriOutput.WriteNew(Path.Combine(SessionFolder, "hri_config.json"), configText);
            HriOutput.WriteNew(Path.Combine(SessionFolder, "session.json"), SessionJson(mode, task, seed));
            m_Results = HriOutput.CreateNewWriter(Path.Combine(SessionFolder, "results.csv"));
            m_Results.WriteLine(ResultsHeader);

            Running = true;
            Successes = 0;
            CompletedTrials = 0;
            TrialTotal = Mathf.Max(1, m_Cfg.trials.trial_count);
            var goals = new GoalSequence(seed);
            Debug.Log($"[WarehouseHRI] Session {HriOutput.Relative(m_Root, SessionFolder)}: {task}, {mode}, seed {seed}, {TrialTotal} trials, " +
                      $"perception: {brain.PersonSource?.Label}, gestures: {brain.GestureSource?.Label}");

            for (int i = 1; i <= TrialTotal; i++)
            {
                TrialIndex = i;
                CurrentGoal = task1 ? task1Goal : endpoints[goals.NextGoalIndex(endpoints.Count)];
                yield return RunTrial(i, task, mode, seed, CurrentGoal);
                yield return new WaitForSeconds(m_Cfg.trials.pause_between_trials_s);
            }

            var summary = $"{{\n  \"trials\": {TrialTotal},\n  \"successes\": {Successes},\n  \"success_ratio\": {HriOutput.F((float)Successes / TrialTotal, "0.####")},\n  \"mode\": \"{mode}\",\n  \"task\": \"{task}\",\n  \"seed\": {seed}\n}}\n";
            HriOutput.WriteNew(Path.Combine(SessionFolder, "summary.json"), summary);
            if (m_Cfg.IsFinal) HriOutput.WriteNew(Path.Combine(SessionFolder, "FINAL_DONE.json"), summary);
            m_Results.Dispose();
            m_Results = null;
            Running = false;
            Status = $"done: {Successes}/{TrialTotal} SUCCESS";
            Debug.Log($"[WarehouseHRI] Session finished: {Successes}/{TrialTotal} SUCCESS. Folder: {HriOutput.Relative(m_Root, SessionFolder)}");
        }

        static bool FinalAlreadyRun(string root, out string folder)
        {
            folder = null;
            if (!Directory.Exists(root)) return false;
            foreach (var d in Directory.GetDirectories(root, "trials_final_*"))
            {
                if (File.Exists(Path.Combine(d, "FINAL_DONE.json")))
                {
                    folder = Path.GetFileName(d);
                    return true;
                }
            }

            return false;
        }

        string SessionJson(string mode, string task, int seed)
        {
            var preview = GoalSequence.Preview(seed, endpoints.Count, Mathf.Max(1, m_Cfg.trials.trial_count));
            var names = new List<string>();
            foreach (var e in endpoints) names.Add("\"" + e.name + "\"");
            return "{\n" +
                   $"  \"task\": \"{task}\",\n  \"mode\": \"{mode}\",\n  \"seed\": {seed},\n" +
                   $"  \"config_frozen\": {(m_Cfg.frozen ? "true" : "false")},\n  \"config_sha256\": \"{m_ConfigSha}\",\n" +
                   $"  \"git_commit\": \"{m_Commit}\",\n  \"git_branch\": \"{m_Branch}\",\n" +
                   "  \"git_dirty\": \"not checked\",\n" +
                   $"  \"unity_version\": \"{Application.unityVersion}\",\n  \"platform\": \"{Application.platform}\",\n" +
                   $"  \"perception_source\": \"{brain.PersonSource?.Label}\",\n  \"gesture_source\": \"{brain.GestureSource?.Label}\",\n" +
                   "  \"obstacle_avoidance\": \"NavMesh map (AI Navigation), not the cameras\",\n" +
                   $"  \"endpoints\": [{string.Join(", ", names)}],\n" +
                   $"  \"goal_index_preview\": [{string.Join(", ", preview)}]\n" +
                   "}\n";
        }

        void OnHeadingTo(RoadNode node)
        {
            if (node == null || !node.IsJunction) return;
            // Scripted scenario side: the one worker moves to this junction and shows the way to B.
            var shown = node.CommandToward(CurrentGoal);
            m_Shown[node.name] = shown;
            worker.PlaceAt(node.workerStand != null ? node.workerStand : node.transform);
            worker.Show(shown);
        }

        void OnJunctionFinished(JunctionRecord r)
        {
            r.shown = m_Shown.TryGetValue(r.junction, out var s) ? s.ToString() : "unknown";
            m_Records.Add(r);
        }

        bool m_Collided;
        string m_CollidedWith = "";

        void OnCollided(Collision c)
        {
            m_Collisions++;
            if (c.collider != null && m_CollidedWith.Length == 0) m_CollidedWith = c.collider.name;
            if (c.collider != null && c.collider.GetComponentInParent<GestureWorker>() != null) m_HumanCollisions++;
            m_Collided = true;
        }

        IEnumerator RunTrial(int index, string task, string mode, int seed, RoadNode goal)
        {
            Status = $"trial {index}/{TrialTotal}, goal {goal.name}";
            m_Shown.Clear();
            m_Records.Clear();
            m_Collisions = 0;
            m_HumanCollisions = 0;
            m_Collided = false;
            m_CollidedWith = "";
            m_RobotCollider = robot.GetComponent<Collider>();
            if (goalMarker != null) goalMarker.position = goal.Position;

            // Reset to A, facing the first road.
            Vector3 a = startNode.Position;
            var first = startNode.OnlyNext;
            float yaw = first != null ? Mathf.Atan2(first.Position.x - a.x, first.Position.z - a.z) * Mathf.Rad2Deg : startNode.transform.eulerAngles.y;
            robot.Teleport(a, yaw);
            worker.Show(GestureCommand.NONE);
            worker.faceTarget = robot.transform;

            if (bridge != null && bridge.linkEnabled && m_Cfg.link.link_required)
            {
                Status = $"trial {index}/{TrialTotal}: waiting for the Python bridge ({bridge.Status})";
                while (!bridge.Connected) yield return null;
                yield return new WaitForSeconds(0.5f); // let replies flow before the watchdog matters
            }

            if (bridge != null) bridge.ResetTrialStats();
            brain.HeadingTo += OnHeadingTo;
            brain.JunctionFinished += OnJunctionFinished;
            robot.Collided += OnCollided;

            string telemetryPath = Path.Combine(SessionFolder, $"telemetry_run{index:000}.csv");
            if (telemetry != null) telemetry.Begin(telemetryPath, index);

            yield return new WaitForFixedUpdate();
            float t0 = Time.fixedTime;
            brain.Begin(startNode);

            Vector3 last = robot.transform.position;
            float travelled = 0f, speedSum = 0f, speedMax = 0f, turnSum = 0f, turnMax = 0f, closest = float.PositiveInfinity;
            int samples = 0;
            float progressTime = t0;
            Vector3 progressPos = last;
            float progressYaw = robot.YawDeg;
            bool timedOut = false, stuck = false;

            while (true)
            {
                yield return new WaitForFixedUpdate();
                float now = Time.fixedTime;
                Vector3 p = robot.transform.position;
                Vector3 step = p - last;
                step.y = 0f;
                travelled += step.magnitude;
                last = p;
                float sp = robot.MeasuredSpeed, tr = Mathf.Abs(robot.MeasuredTurnRateDps);
                speedSum += sp;
                turnSum += tr;
                speedMax = Mathf.Max(speedMax, sp);
                turnMax = Mathf.Max(turnMax, tr);
                samples++;
                closest = Mathf.Min(closest, HumanDistance());

                bool wantsToMove = Mathf.Abs(robot.CommandedV) > 0.05f || Mathf.Abs(robot.CommandedW) > 5f;
                Vector3 moved = p - progressPos;
                moved.y = 0f;
                if (!wantsToMove || brain.SafetyStopActive || moved.magnitude >= m_Cfg.trials.stuck_min_progress_m ||
                    Mathf.Abs(Mathf.DeltaAngle(progressYaw, robot.YawDeg)) >= 20f)
                {
                    progressTime = now;
                    progressPos = p;
                    progressYaw = robot.YawDeg;
                }

                if (brain.Finished) break;
                if (m_Collided) { brain.Halt("collision"); break; }
                if (now - t0 > m_Cfg.trials.timeout_s) { timedOut = true; brain.Halt("timeout"); break; }
                if (now - progressTime > m_Cfg.trials.stuck_s) { stuck = true; brain.Halt("stuck"); break; }
            }

            float total = Time.fixedTime - t0;
            if (telemetry != null) telemetry.End();
            brain.HeadingTo -= OnHeadingTo;
            brain.JunctionFinished -= OnJunctionFinished;
            robot.Collided -= OnCollided;

            // Scoring from ground truth (never fed back to the robot).
            Vector2 fin = robot.PositionXZ, b = PurePursuit.XZ(goal.Position);
            var score = TrialScoring.Score(fin, b, brain.Finished && !brain.Halted, m_Collided, stuck, timedOut,
                brain.Aborted, brain.AbortReason, m_Cfg.trials.success_radius_m);
            if (score.Outcome == TrialOutcome.SUCCESS) Successes++;
            CompletedTrials = index;
            if (m_Collided && m_CollidedWith.Length > 0) score.Detail = "collision with " + m_CollidedWith;

            var rec = new RunRecord
            {
                trial = index, task = task, mode = mode, seed = seed, config_frozen = m_Cfg.frozen,
                config_sha256 = m_ConfigSha, git_commit = m_Commit, git_branch = m_Branch,
                perception_source = brain.PersonSource?.Label, gesture_source = brain.GestureSource?.Label,
                outcome = score.Outcome.ToString(), failure_reason = score.Reason.ToString(), detail = score.Detail,
                successes = Successes, trials_so_far = index, success_ratio = (float)Successes / index,
                a_name = startNode.name, a_x = a.x, a_z = a.z, b_name = goal.name, b_x = b.x, b_z = b.y,
                final_x = fin.x, final_z = fin.y,
                final_node = brain.CurrentNode != null ? brain.CurrentNode.name : "",
                final_distance_to_b_m = Vector2.Distance(fin, b),
                straight_line_m = Vector2.Distance(PurePursuit.XZ(a), b), travelled_m = travelled, total_s = total,
                avg_speed_mps = samples > 0 ? speedSum / samples : 0f, max_speed_mps = speedMax,
                avg_turn_dps = samples > 0 ? turnSum / samples : 0f, max_turn_dps = turnMax,
                collisions = m_Collisions, human_collisions = m_HumanCollisions, collided_with = m_CollidedWith,
                closest_human_m = float.IsInfinity(closest) ? -1f : closest,
                abort_reason = brain.AbortReason,
                telemetry_file = HriOutput.Relative(m_Root, telemetryPath),
            };
            var st = brain.StepSeconds;
            rec.step_s = new StepTimes
            {
                navigate = st[(int)StepKind.navigate], scan = st[(int)StepKind.scan], approach = st[(int)StepKind.approach],
                ask = st[(int)StepKind.ask], gesture = st[(int)StepKind.gesture], execute = st[(int)StepKind.execute],
                safety_stop = brain.SafetyStopSeconds,
            };
            rec.junctions.AddRange(m_Records);
            if (bridge != null && bridge.linkEnabled)
            {
                bridge.Rtt.Stats(out var rttMean, out var rttMax, out var rttN);
                bridge.InferenceStats(out var infMean, out var infMax, out var infN, out var perModel);
                rec.link_status = (m_Cfg.link.link_required ? "required" : "shadow") + ", " + bridge.Status;
                rec.link_perception = bridge.PerceptionLabel;
                rec.link_replies = rttN;
                rec.round_trip_mean_ms = rttN > 0 ? rttMean : -1f;
                rec.round_trip_max_ms = rttN > 0 ? rttMax : -1f;
                rec.inference_mean_ms = infN > 0 ? infMean : -1f;
                rec.inference_max_ms = infN > 0 ? infMax : -1f;
                rec.inference_per_model_ms = perModel;
            }

            HriOutput.WriteNew(Path.Combine(SessionFolder, $"run_{index:000}.json"), JsonUtility.ToJson(rec, true));
            m_Results.WriteLine(CsvRow(rec));
            LastSummary = $"trial {index}: {rec.outcome} {(rec.failure_reason == "none" ? "" : rec.failure_reason + " ")}({rec.detail}); " +
                          $"ratio {Successes}/{index}";
            Debug.Log("[WarehouseHRI] " + LastSummary);
        }

        float HumanDistance()
        {
            if (worker == null) return float.PositiveInfinity;
            Vector3 w = worker.transform.position;
            Vector3 from = robot.transform.position;
            if (m_RobotCollider != null)
            {
                w.y = m_RobotCollider.bounds.center.y;
                from = m_RobotCollider.ClosestPoint(w);
            }

            Vector3 d = w - from;
            d.y = 0f;
            return d.magnitude;
        }

        static string CsvRow(RunRecord r)
        {
            var j = new List<string>();
            foreach (var x in r.junctions) j.Add($"{x.junction}:{x.shown}>{x.read}(asks {x.asks})");
            var s = r.step_s;
            return string.Join(",",
                r.trial.ToString(HriOutput.Inv), r.task, r.mode, r.seed.ToString(HriOutput.Inv),
                HriOutput.Csv(r.perception_source), HriOutput.Csv(r.gesture_source),
                r.outcome, r.failure_reason, HriOutput.Csv(r.detail), HriOutput.F(r.success_ratio, "0.####"),
                HriOutput.F(r.a_x), HriOutput.F(r.a_z), r.b_name, HriOutput.F(r.b_x), HriOutput.F(r.b_z),
                HriOutput.F(r.straight_line_m), HriOutput.F(r.travelled_m), HriOutput.F(r.total_s, "0.00"),
                HriOutput.F(s.navigate, "0.00"), HriOutput.F(s.scan, "0.00"), HriOutput.F(s.approach, "0.00"),
                HriOutput.F(s.ask, "0.00"), HriOutput.F(s.gesture, "0.00"), HriOutput.F(s.execute, "0.00"),
                HriOutput.F(s.safety_stop, "0.00"),
                HriOutput.F(r.avg_speed_mps), HriOutput.F(r.max_speed_mps), HriOutput.F(r.avg_turn_dps, "0.0"),
                HriOutput.F(r.max_turn_dps, "0.0"), HriOutput.F(r.final_distance_to_b_m),
                HriOutput.Csv(string.Join("; ", j)), r.collisions.ToString(HriOutput.Inv),
                r.human_collisions.ToString(HriOutput.Inv), HriOutput.F(r.closest_human_m),
                r.inference_mean_ms >= 0f ? HriOutput.F(r.inference_mean_ms) : "",
                r.round_trip_mean_ms >= 0f ? HriOutput.F(r.round_trip_mean_ms) : "");
        }
    }
}
