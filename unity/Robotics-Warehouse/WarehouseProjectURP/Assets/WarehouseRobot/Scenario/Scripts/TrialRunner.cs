using System;
using System.Collections;
using System.Collections.Generic;
using System.Globalization;
using System.IO;
using System.Security.Cryptography;
using System.Text;
using UnityEngine;
using WarehouseHRI;
using WarehouseRobot.Bridge;

namespace WarehouseRobot.Scenario
{
    [Serializable]
    public class SweepSettings
    {
        public int repeats = 20;
        public float distance_min_m = 1.7f, distance_max_m = 2.5f, view_angle_max_deg = 25f, worker_yaw_jitter_deg = 15f;
        public float settle_s = 0.6f, hold_s = 2f;
    }

    [Serializable]
    public class TrialsConfig
    {
        public string task = "Task2", mode = "development";
        public int dev_seed = 1, final_seed = 2, trial_count = 10;
        public float timeout_s = 240f, stuck_s = 10f, stuck_min_progress_m = 0.25f, success_radius_m = 0.3f;
        public float pause_between_trials_s = 1f, truth_interval_s = 0.1f;
        public string output_root = "outputs";
        public SweepSettings gesture_sweep = new SweepSettings();
        public bool IsFinal => string.Equals(mode, "final", StringComparison.OrdinalIgnoreCase);
        /// <summary>final or replication: final seed, frozen checks, run once per task (FinalRunGuard).</summary>
        public bool FinalRules => FinalRunGuard.FinalRules(mode);
    }

    [Serializable] class FrozenFlag { public bool frozen; }
    [Serializable] class FrozenWeights { public string path = "", sha256 = ""; }
    [Serializable] class FrozenTask { public FrozenWeights route_config = new FrozenWeights(); }
    [Serializable] class FrozenTasks { public FrozenTask Task1 = new FrozenTask(); }
    [Serializable] class FrozenRecord { public FrozenWeights pose_weights = new FrozenWeights(); public FrozenTasks tasks = new FrozenTasks(); }
    [Serializable] class RoadmapMeta { public string start = "A"; public string task1_goal = "E1"; }

    [Serializable]
    public class ShownRecord
    {
        public string junction, shown;
        public float t_placed;
    }

    [Serializable]
    public class TruthRun
    {
        public int trial;
        public string task, mode;
        public int seed;
        public string a_name, b_name;
        public float a_x, a_z, b_x, b_z;
        public string outcome, failure_reason, detail, python_final_state;
        public float final_x, final_z, final_distance_to_b_m, straight_line_m, travelled_m, total_s, t_start, t_end;
        public float avg_speed_mps, max_speed_mps, avg_turn_dps, max_turn_dps;
        public int collisions, human_collisions;
        public string collided_with = "";
        public float closest_human_m = -1f;
        public string closest_human_note = "horizontal distance from the robot's body collider to the worker's centre axis (truth)";
        public List<ShownRecord> shown = new List<ShownRecord>();
        public string truth_file;
    }

    /// <summary>
    /// Step 7 trial runner (scenario side, Unity). Reads robot_vision/configs/trials.json. For each trial it picks goal
    /// B with a seeded generator (dev_seed in development, final_seed in final mode), resets the robot to the roadmap
    /// start, and keeps the one worker at the junction the robot is heading to (the junction named by Python's NavMesh
    /// target), showing the command toward B. Python decides everything; it learns of trials only through telemetry
    /// trial_index / trial_running, never of B. A trial ends when Python reports done or aborted and the robot has
    /// stopped, or on collision, timeout or getting stuck; it is then scored from ground truth. Output (new folder
    /// robot_vision/outputs/trials_mode_task_time/): session.json (git commit, seed, goal order), config_used/,
    /// truth_run###.json and truth_run###.csv (0.1 s), results_unity.csv. Task "GestureSweep" instead keeps the
    /// robot still and has the worker show every command (truth_sweep.csv) for the development gesture evaluation; task
    /// "ForwardHandSweep" (development only, 2026-10-22, AUDIT.md section 9 item 15) shows only FORWARD, once with the fist
    /// and once with the index finger at each placement (truth_sweep.csv column hand).
    /// Since 2026-10-21: every session is refused while the worker does not render as the textured Humanoid avatar
    /// (WorkerAppearance); Task 1 adds the checkpoints of robot_vision/configs/task1_route.json to the roadmap for the
    /// session (Task1Route); trial 1 starts only after Python reports perception_ready, and only if Python's map
    /// (command field route) is the map of this task. Task 1 workers (2026-10-21): one standing worker per stop, from
    /// the scene group WarehouseHRI/Task1Workers (built inactive by Add Worker and Roadmap); a Task 1 session refuses to
    /// start unless those workers stand exactly where task1_route.json puts them, activates them, hides the moved
    /// Task 2 worker, and every Task 1 worker shows FORWARD (the command toward B from its stop) for the whole trial.
    /// Task 2 and the gesture sweep keep the group inactive.
    /// Task 2 workers (2026-10-22, declared design change after the Task 2 final and its replication, AUDIT.md section
    /// 12): the one coded scene worker stands at J1 and a copy of it at every other junction (Task2Workers), each showing
    /// the command toward B for the whole trial (NONE at a junction off the route); before, the one worker was moved to
    /// each junction as the robot headed there. The sweeps still use the one worker alone.
    /// Mode "replication" (2026-10-22): like final (final_seed, trial_count, frozen configs, pose weights, Task 1 route
    /// hash), written to trials_replication_task_time/ with REPLICATION_DONE.json, run once per task; any other mode
    /// than development, final or replication is refused.
    /// </summary>
    public class TrialRunner : MonoBehaviour
    {
        public string repoRootRelativeToProject = "../../..";
        public bool runOnStart = true;

        public string Status { get; private set; } = "idle";
        public int TrialIndex { get; private set; }
        public int TrialTotal { get; private set; }
        public int Successes { get; private set; }
        public int Completed { get; private set; }
        public string CurrentGoal { get; private set; } = "";
        public string LastSummary { get; private set; } = "";
        public string SessionFolder { get; private set; }

        RobotRig robot;
        RobotBridgeClient bridge;
        GestureWorker worker;
        readonly List<GestureWorker> workers = new List<GestureWorker>();          // the workers of this session
        readonly Dictionary<string, GestureWorker> standingWorkers = new Dictionary<string, GestureWorker>();
        List<Task1WorkerStand> task1Stands;
        readonly Dictionary<string, RoadNode> nodes = new Dictionary<string, RoadNode>();
        TrialsConfig cfg;
        RoadmapMeta meta;
        string repoRoot, outRoot, cfgText, roadText, cfgName = "trials.json";
        string routeText, expectedRoute = "Task2";
        readonly List<string> task1Stops = new List<string>();
        bool IsTask1 => string.Equals(cfg.task, "Task1", StringComparison.OrdinalIgnoreCase);
        bool IsSweep => string.Equals(cfg.task, "GestureSweep", StringComparison.OrdinalIgnoreCase) ||
                        string.Equals(cfg.task, "ForwardHandSweep", StringComparison.OrdinalIgnoreCase);
        const string Task1RouteFile = "robot_vision/configs/task1_route.json";
        static readonly CultureInfo Inv = CultureInfo.InvariantCulture;

        string RepoFile(string rel) => Path.GetFullPath(Path.Combine(repoRoot, rel));

        void Start()
        {
            if (runOnStart) StartCoroutine(Run());
        }

        bool Setup(out string error)
        {
            error = null;
            repoRoot = Path.GetFullPath(Path.Combine(Application.dataPath, "..", repoRootRelativeToProject));
            try
            {
                // A git-ignored trials.local.json (e.g. a short smoke run) replaces trials.json; the file used is saved.
                string local = RepoFile("robot_vision/configs/trials.local.json");
                cfgName = File.Exists(local) ? "trials.local.json" : "trials.json";
                cfgText = File.ReadAllText(RepoFile("robot_vision/configs/" + cfgName));
                roadText = File.ReadAllText(RepoFile("robot_vision/configs/roadmap.json"));
                cfg = JsonUtility.FromJson<TrialsConfig>(cfgText);
                meta = JsonUtility.FromJson<RoadmapMeta>(roadText);
            }
            catch (Exception e)
            {
                error = "cannot read robot_vision/configs/trials.json or roadmap.json: " + e.Message;
                return false;
            }

            robot = FindFirstObjectByType<RobotRig>();
            bridge = FindFirstObjectByType<RobotBridgeClient>();
            worker = FindFirstObjectByType<GestureWorker>();
            nodes.Clear();
            foreach (var n in FindObjectsByType<RoadNode>(FindObjectsSortMode.None)) nodes[n.name] = n;
            if (robot == null || robot.Drive == null || bridge == null || worker == null || !nodes.ContainsKey(meta.start))
                error = "need RobotRig, RobotBridgeClient, GestureWorker and the roadmap (run Tools > Warehouse HRI > Add Worker and Roadmap)";
            else if (cfg.dev_seed == cfg.final_seed) error = "dev_seed and final_seed must differ";
            else if (FinalRunGuard.Mode(cfg.mode) == null)
                error = $"unknown mode '{cfg.mode}' in {cfgName} (development, final or replication)";
            else if (cfg.FinalRules && !(Frozen("robot_vision/configs/hri_control.json") && Frozen("robot_vision/configs/hri_perception.json")))
                error = $"{FinalRunGuard.Mode(cfg.mode)} mode needs frozen hri_control.json and hri_perception.json";
            workers.Clear();
            if (error == null && IsTask1) error = AddTask1Checkpoints() ?? SetupTask1Workers();
            else if (error == null)
            {
                var group = Task1Group();
                if (group != null) group.gameObject.SetActive(false);    // Task 2 / sweep: never the Task 1 workers
                if (IsSweep) workers.Add(worker);                          // the sweeps place the one worker themselves
                else error = SetupTask2Workers();
            }
            if (error == null)
            {
                // Every session, every mode and task: every worker must render as the textured Humanoid avatar.
                foreach (var w in workers)
                {
                    var look = WorkerAppearance.Problems(w.gameObject);
                    if (look.Count > 0) { error = $"worker appearance ({w.name}): " + string.Join("; ", look) + ". " + WorkerAppearance.Fix; break; }
                }
            }
            outRoot = Path.GetFullPath(Path.Combine(repoRoot, "robot_vision", cfg.output_root));
            if (error == null && cfg.FinalRules)
            {
                // Each task's final runs once, and so does its replication; another task's or the other mode's
                // done file does not block it.
                string mode = FinalRunGuard.Mode(cfg.mode);
                string earlier = FinalRunGuard.EarlierRun(outRoot, mode, cfg.task);
                if (earlier != null) error = $"{mode} trials of {cfg.task} already run: {earlier}";
                else error = WeightsProblem() ?? (IsTask1 ? Task1RouteProblem() : null);
            }
            return error == null;
        }

        /// <summary>Task 1: the checkpoints of task1_route.json on the straight line, for this Play session.</summary>
        string AddTask1Checkpoints()
        {
            try
            {
                routeText = File.ReadAllText(RepoFile(Task1RouteFile));
                var rc = JsonUtility.FromJson<Task1RouteConfig>(routeText);
                task1Stands = Task1Route.WorkerStands(nodes[meta.start], rc);     // from the scene roadmap, before Apply
                var stops = Task1Route.Apply(nodes[meta.start], rc, out expectedRoute);
                task1Stops.Clear();
                foreach (var s in stops)
                {
                    nodes[s.name] = s;
                    task1Stops.Add(s.name);
                }

                var line = Task1Route.StraightLine(nodes[meta.start]);
                if (line[line.Count - 1].name != meta.task1_goal)
                    return $"Task 1: the straight line ends at {line[line.Count - 1].name}, not at task1_goal {meta.task1_goal}";
                Debug.Log($"[TrialRunner] Task 1 map {expectedRoute}: stops {string.Join(", ", task1Stops)}");
                return null;
            }
            catch (Exception e)
            {
                return "Task 1 route (" + Task1RouteFile + "): " + e.Message;
            }
        }

        /// <summary>The scene's Task 1 worker group (WarehouseHRI/Task1Workers, saved inactive), or null.</summary>
        static Transform Task1Group()
        {
            foreach (var go in UnityEngine.SceneManagement.SceneManager.GetActiveScene().GetRootGameObjects())
                if (go.name == "WarehouseHRI") return go.transform.Find(Task1Route.WorkersGroup);
            return null;
        }

        /// <summary>
        /// Task 1: the scene's Task 1 workers must be exactly those of task1_route.json (one per stop, at its stand), else
        /// the scene is stale and the session is refused. Activates them and hides the moved Task 2 worker.
        /// </summary>
        string SetupTask1Workers()
        {
            const string rebuild = "run Tools > Warehouse HRI > Add Worker and Roadmap (edit mode), save the scene, press Play again";
            var group = Task1Group();
            if (group == null) return "Task 1: no WarehouseHRI/" + Task1Route.WorkersGroup + " in the scene: " + rebuild;
            var names = new List<string>();
            foreach (Transform c in group) names.Add(c.name);
            var want = new List<string>();
            foreach (var s in task1Stands) want.Add(Task1Route.WorkerName(s.Stop));
            if (string.Join(",", names) != string.Join(",", want))
                return $"Task 1 workers in the scene ({string.Join(", ", names)}) are not those of {Task1RouteFile} ({string.Join(", ", want)}): {rebuild}";
            standingWorkers.Clear();
            foreach (var s in task1Stands)
            {
                var t = group.Find(Task1Route.WorkerName(s.Stop));
                var gw = t.GetComponent<GestureWorker>();
                Vector3 d = t.position - s.Position;
                d.y = 0f;
                if (gw == null) return $"Task 1 worker {t.name} has no GestureWorker: {rebuild}";
                if (d.magnitude > 0.01f || Quaternion.Angle(t.rotation, s.Rotation) > 1f)
                    return $"Task 1 worker {t.name} stands at ({t.position.x:0.00}, {t.position.z:0.00}), {Task1RouteFile} puts it at ({s.Position.x:0.00}, {s.Position.z:0.00}): {rebuild}";
                standingWorkers[s.Stop] = gw;
            }

            group.gameObject.SetActive(true);
            worker.gameObject.SetActive(false);      // Task 1 has a standing worker per stop instead of the moved one
            foreach (var s in task1Stands)
            {
                var gw = standingWorkers[s.Stop];
                workers.Add(gw);
                string blocked = StandBlocked(gw);
                if (blocked != null) return $"Task 1 worker at {s.Stop}: overlaps {blocked}";
            }

            Debug.Log($"[TrialRunner] Task 1 workers: {string.Join(", ", want)} (moved Task 2 worker hidden)");
            return null;
        }

        /// <summary>
        /// Task 2 (2026-10-22, declared design change, AUDIT.md section 12): one standing worker per junction. The one
        /// coded scene worker stands at the first junction and a copy of it (Instantiate: same avatar, material, poses
        /// and code) at every other, each at its junction's workerStand (roadmap rule, unchanged). Before: the one
        /// worker was moved to each junction as the robot headed there (the Task 2 final and its replication).
        /// </summary>
        string SetupTask2Workers()
        {
            var junctions = Task2Workers.Junctions(nodes.Values, out string problem);
            if (junctions == null) return "Task 2 workers: " + problem + " (run Tools > Warehouse HRI > Add Worker and Roadmap)";
            standingWorkers.Clear();
            for (int i = 0; i < junctions.Count; i++)
            {
                var j = junctions[i];
                var gw = i == 0 ? worker : Instantiate(worker, worker.transform.parent);
                if (i > 0) gw.name = Task2Workers.CopyName(worker.name, j.name);
                gw.PlaceAt(j.workerStand);
                standingWorkers[j.name] = gw;
                workers.Add(gw);
                string blocked = StandBlocked(gw);
                if (blocked != null) return $"Task 2 worker at {j.name}: overlaps {blocked}";
            }

            Debug.Log($"[TrialRunner] Task 2 workers: {string.Join(", ", workers.ConvertAll(w => w.name))} (one per junction)");
            return null;
        }

        /// <summary>Name of a scene collider this worker stands in (racks, walls), or null.</summary>
        string StandBlocked(GestureWorker w)
        {
            Physics.SyncTransforms();
            Vector3 p = w.transform.position;
            foreach (var c in Physics.OverlapCapsule(p + Vector3.up * 0.4f, p + Vector3.up * 1.6f, 0.25f, ~0, QueryTriggerInteraction.Ignore))
                if (!c.transform.IsChildOf(w.transform) && !c.transform.IsChildOf(robot.transform)) return c.name;
            return null;
        }

        /// <summary>Task 1 final: task1_route.json must have the sha256 recorded in hri_frozen.json (LF-normalised).</summary>
        string Task1RouteProblem()
        {
            FrozenRecord rec;
            try { rec = JsonUtility.FromJson<FrozenRecord>(File.ReadAllText(RepoFile("robot_vision/configs/hri_frozen.json"))); }
            catch (Exception e) { return "cannot read robot_vision/configs/hri_frozen.json: " + e.Message; }
            var rc = rec?.tasks?.Task1?.route_config;
            if (rc == null || string.IsNullOrEmpty(rc.sha256)) return "no tasks.Task1.route_config in robot_vision/configs/hri_frozen.json";
            string got = FinalRunGuard.Sha256TextLf(RepoFile(rc.path));
            return string.Equals(got, rc.sha256, StringComparison.OrdinalIgnoreCase) ? null
                : $"{rc.path} has sha256 {got}, not the recorded {rc.sha256}";
        }

        string WeightsProblem()
        {
            FrozenRecord rec;
            try { rec = JsonUtility.FromJson<FrozenRecord>(File.ReadAllText(RepoFile("robot_vision/configs/hri_frozen.json"))); }
            catch (Exception e) { return "cannot read robot_vision/configs/hri_frozen.json: " + e.Message; }
            if (rec?.pose_weights == null || string.IsNullOrEmpty(rec.pose_weights.path))
                return "no pose_weights entry in robot_vision/configs/hri_frozen.json";
            return FinalRunGuard.WeightsProblem(RepoFile(rec.pose_weights.path), rec.pose_weights.sha256);
        }

        bool Frozen(string rel)
        {
            try { return JsonUtility.FromJson<FrozenFlag>(File.ReadAllText(RepoFile(rel))).frozen; }
            catch (Exception) { return false; }
        }

        IEnumerator Run()
        {
            yield return null;
            if (!Setup(out var error))
            {
                Status = "not started: " + error;
                Debug.LogError("[TrialRunner] " + error);
                yield break;
            }

            string mode = FinalRunGuard.Mode(cfg.mode);
            int seed = cfg.FinalRules ? cfg.final_seed : cfg.dev_seed;
            bool handSweep = string.Equals(cfg.task, "ForwardHandSweep", StringComparison.OrdinalIgnoreCase);
            bool sweep = handSweep || string.Equals(cfg.task, "GestureSweep", StringComparison.OrdinalIgnoreCase);
            if (sweep && cfg.FinalRules)
            {
                Status = $"not started: {cfg.task} is development only";
                yield break;
            }

            SessionFolder = NewFolder(handSweep ? "forward_hand_sweep_development" : sweep ? "gestures_sweep_development" : $"trials_{mode}_{cfg.task}");
            Directory.CreateDirectory(Path.Combine(SessionFolder, "config_used"));
            WriteNew(Path.Combine(SessionFolder, "config_used", cfgName), cfgText);
            WriteNew(Path.Combine(SessionFolder, "config_used", "roadmap.json"), roadText);
            ReadGit(out var commit, out var branch);
            var endpoints = new List<string>();
            foreach (var kv in nodes) if (kv.Value.IsEndpoint) endpoints.Add(kv.Key);
            endpoints.Sort(StringComparer.Ordinal);
            TrialTotal = handSweep ? 2 * cfg.gesture_sweep.repeats
                : sweep ? GestureSweepOrder.Commands.Length * cfg.gesture_sweep.repeats : Mathf.Max(1, cfg.trial_count);
            var preview = new List<string>();
            var gp = new GoalSequence(seed);
            for (int i = 0; i < TrialTotal && !sweep; i++)
                preview.Add(IsTask1 ? meta.task1_goal : endpoints[gp.NextGoalIndex(endpoints.Count)]);
            if (IsTask1) WriteNew(Path.Combine(SessionFolder, "config_used", "task1_route.json"), routeText);
            var animator = workers[0].GetComponentInChildren<Animator>();
            string boneMap = WorkerAppearance.BoneMap(animator);
            var looks = new List<string>();
            var placedWorkers = new List<string>();
            foreach (var w in workers)
            {
                looks.Add(w.name + ": " + WorkerAppearance.Describe(w.gameObject));
                placedWorkers.Add($"{w.name} ({w.transform.position.x.ToString("0.00", Inv)}, {w.transform.position.z.ToString("0.00", Inv)})");
            }
            WriteNew(Path.Combine(SessionFolder, "session.json"),
                "{\n" + $"  \"task\": \"{cfg.task}\",\n  \"mode\": \"{mode}\",\n  \"seed\": {seed},\n" +
                $"  \"trials\": {TrialTotal},\n  \"endpoints\": [{Quote(endpoints)}],\n  \"goal_order\": [{Quote(preview)}],\n" +
                $"  \"git_commit\": \"{commit}\",\n  \"git_branch\": \"{branch}\",\n  \"unity_version\": \"{Application.unityVersion}\",\n" +
                $"  \"trials_config_sha256\": \"{Sha256(cfgText)}\",\n  \"roadmap_sha256\": \"{Sha256(roadText)}\",\n" +
                (IsTask1 ? $"  \"task1_stops\": [{Quote(task1Stops)}],\n  \"task1_route_sha256_lf\": \"{Sha256(routeText.Replace("\r\n", "\n"))}\",\n" : "") +
                $"  \"python_map_required\": \"{(sweep ? "" : expectedRoute)}\",\n" +
                $"  \"worker_model_sha256\": \"{WorkerModelSha256()}\",\n" +
                $"  \"worker_avatar_bone_map_sha256\": \"{WorkerAppearance.Sha256(boneMap)}\",\n" +
                $"  \"worker_avatar_bones\": {boneMap.Split('\n').Length - 1},\n" +
                $"  \"workers\": [{Quote(placedWorkers)}],\n" +
                $"  \"worker_appearance\": \"{JsonEscape(string.Join(" | ", looks))}\",\n" +
                "  \"note\": \"goal B lives only in Unity (this folder); Python never receives it\"\n}\n");

            Status = "waiting for the Python bridge";
            while (!bridge.Connected) yield return null;
            // Trial 1 starts only when Python has warmed up its models and processed a frame of each camera
            // (the first-call stalls otherwise hit the 0.3 s watchdog during trial 1; infrastructure, 2026-10-21).
            float waitStart = Time.realtimeSinceStartup;
            while (!bridge.PythonPerceptionReady)
            {
                Status = bridge.Connected ? $"waiting for Python: perception ready ({Time.realtimeSinceStartup - waitStart:0} s)" : "waiting for the Python bridge";
                yield return null;
            }

            Debug.Log($"[TrialRunner] Python perception ready after {Time.realtimeSinceStartup - waitStart:0.0} s; Python map {bridge.PythonRoute}");
            if (!sweep && bridge.PythonRoute != expectedRoute)
            {
                string why = $"Python's map is '{bridge.PythonRoute}' but {cfg.task} needs '{expectedRoute}': restart the server with " +
                             $"python -m bridge.server --mode guide --perception vision --task {(IsTask1 ? "Task1" : "Task2")}";
                Status = "not started: " + why;
                Debug.LogError("[TrialRunner] " + why);
                WriteNew(Path.Combine(SessionFolder, "NOT_STARTED.txt"), why + "\n");
                yield break;
            }

            yield return new WaitForSeconds(0.5f);

            if (handSweep) yield return HandSweep(seed);
            else if (sweep) yield return Sweep(seed);
            else yield return Trials(seed, mode, endpoints);
        }

        // ---------------- trials ----------------

        IEnumerator Trials(int seed, string mode, List<string> endpoints)
        {
            var goals = new GoalSequence(seed);
            bool task1 = string.Equals(cfg.task, "Task1", StringComparison.OrdinalIgnoreCase);
            using (var results = NewWriter(Path.Combine(SessionFolder, "results_unity.csv")))
            {
                results.WriteLine("trial,b_name,outcome,failure_reason,detail,final_distance_to_b_m,total_s,travelled_m,collisions,closest_human_m,python_final_state");
                for (int i = 1; i <= TrialTotal; i++)
                {
                    TrialIndex = i;
                    CurrentGoal = task1 ? meta.task1_goal : endpoints[goals.NextGoalIndex(endpoints.Count)];
                    TruthRun rec = null;
                    yield return OneTrial(i, seed, mode, CurrentGoal, r => rec = r);
                    Completed = i;
                    if (rec.outcome == "SUCCESS") Successes++;
                    results.WriteLine(string.Join(",", i.ToString(Inv), rec.b_name, rec.outcome, rec.failure_reason, Csv(rec.detail),
                        F(rec.final_distance_to_b_m), F(rec.total_s), F(rec.travelled_m), rec.collisions.ToString(Inv),
                        F(rec.closest_human_m), Csv(rec.python_final_state)));
                    LastSummary = $"trial {i}: {rec.outcome} {(rec.failure_reason == "none" ? "" : rec.failure_reason)} ({rec.detail}); {Successes}/{i}";
                    Debug.Log("[TrialRunner] " + LastSummary);
                    yield return new WaitForSeconds(cfg.pause_between_trials_s);
                }
            }

            string summary = $"{{\n  \"trials\": {TrialTotal},\n  \"successes\": {Successes},\n  \"mode\": \"{mode}\",\n  \"task\": \"{cfg.task}\",\n  \"seed\": {seed}\n}}\n";
            WriteNew(Path.Combine(SessionFolder, "summary_unity.json"), summary);
            string doneFile = FinalRunGuard.DoneFileFor(mode);      // FINAL_DONE.json / REPLICATION_DONE.json
            if (doneFile != null) WriteNew(Path.Combine(SessionFolder, doneFile), summary);
            Status = $"done: {Successes}/{TrialTotal} SUCCESS";
            Debug.Log($"[TrialRunner] {Status}. Folder: {Path.GetFileName(SessionFolder)}");
        }

        IEnumerator OneTrial(int index, int seed, string mode, string goal, Action<TruthRun> done)
        {
            var start = nodes[meta.start];
            var first = start.OnlyNext;
            Vector3 a = start.Position;
            float yaw = first != null ? Mathf.Atan2(first.Position.x - a.x, first.Position.z - a.z) * Mathf.Rad2Deg : start.transform.eulerAngles.y;
            Teleport(new Vector3(a.x, robot.transform.position.y, a.z), yaw);
            bridge.ReachedEndPoint = false;
            var shown = new List<ShownRecord>();
            var placed = new HashSet<string>();
            foreach (var w in workers) w.faceTarget = robot.transform;
            if (IsTask1)
                foreach (var st in task1Stands)              // standing workers: back to the stand, show the command toward B
                {
                    var w = standingWorkers[st.Stop];
                    w.transform.SetPositionAndRotation(st.Position, st.Rotation);
                    w.Show(nodes[st.Stop].CommandToward(nodes[goal]));
                }
            else
                foreach (var kv in standingWorkers)          // Task 2: each junction's worker at its stand (NONE off the route)
                {
                    kv.Value.PlaceAt(nodes[kv.Key].workerStand);
                    kv.Value.Show(nodes[kv.Key].CommandToward(nodes[goal]));
                }
            if (first != null && first.IsJunction) Place(first, goal, shown, placed);
            int collisionBase = robot.Collisions != null ? robot.Collisions.Records.Count : 0;
            var body = robot.GetComponent<Collider>();
            if (body == null) body = robot.GetComponentInChildren<Collider>();

            string truthPath = Path.Combine(SessionFolder, $"truth_run{index:000}.csv");
            var truth = NewWriter(truthPath);
            truth.WriteLine("time_s,robot_x,robot_z,robot_yaw_deg,v_mps,omega_radps,worker_x,worker_z,worker_yaw_deg,gesture_shown,closest_human_m,collisions,python_state");
            bridge.TrialIndex = index;
            bridge.TrialRunning = true;
            yield return new WaitForFixedUpdate();
            float t0 = Time.time, nextTruth = t0;
            Vector3 last = robot.transform.position, progressPos = last;
            float progressTime = t0, travelled = 0f, speedSum = 0f, speedMax = 0f, turnSum = 0f, turnMax = 0f, closest = float.PositiveInfinity;
            int samples = 0;
            string end = null;
            while (end == null)
            {
                yield return new WaitForFixedUpdate();
                float now = Time.time;
                var p = robot.transform.position;
                Vector3 step = p - last;
                step.y = 0f;
                travelled += step.magnitude;
                last = p;
                float sp = Mathf.Abs(robot.Drive.V), tr = Mathf.Abs(robot.Drive.Omega) * Mathf.Rad2Deg;
                speedSum += sp; turnSum += tr; speedMax = Mathf.Max(speedMax, sp); turnMax = Mathf.Max(turnMax, tr); samples++;
                float hd = HumanDistance(body);
                closest = Mathf.Min(closest, hd);
                if (bridge.HasTarget)
                    foreach (var kv in nodes)
                        if (kv.Value.IsJunction && !placed.Contains(kv.Key) &&
                            Vector2.Distance(bridge.Target, new Vector2(kv.Value.Position.x, kv.Value.Position.z)) < 0.5f)
                            Place(kv.Value, goal, shown, placed);
                if (now >= nextTruth)
                {
                    nextTruth += cfg.truth_interval_s;
                    var nw = NearestWorker(p);              // Task 1: the nearest of the standing workers
                    var w = nw.transform;
                    truth.WriteLine(string.Join(",", F(now, "0.000"), F(p.x, "0.000"), F(p.z, "0.000"), F(robot.transform.eulerAngles.y, "0.0"),
                        F(robot.Drive.V, "0.000"), F(robot.Drive.Omega, "0.000"), F(w.position.x, "0.000"), F(w.position.z, "0.000"),
                        F(w.eulerAngles.y, "0.0"), nw.Current.ToString(), F(hd, "0.000"),
                        ((robot.Collisions != null ? robot.Collisions.Records.Count : 0) - collisionBase).ToString(Inv), Csv(bridge.State)));
                }

                bool wantsToMove = Mathf.Abs(robot.Drive.CommandedV) > 0.05f;
                Vector3 moved = p - progressPos;
                moved.y = 0f;
                if (!wantsToMove || moved.magnitude >= cfg.stuck_min_progress_m) { progressTime = now; progressPos = p; }
                string st = bridge.State ?? "";
                if (robot.Collisions != null && robot.Collisions.Records.Count > collisionBase) end = "collision";
                else if ((st.StartsWith("done") || st.StartsWith("aborted")) && Mathf.Abs(robot.Drive.V) < 0.02f) end = st.StartsWith("done") ? "done" : "aborted";
                else if (now - t0 > cfg.timeout_s) end = "timeout";
                else if (now - progressTime > cfg.stuck_s) end = "stuck";
                else if (!bridge.Connected) { Status = $"trial {index}: Python disconnected, waiting"; }
                else Status = $"trial {index}/{TrialTotal}: goal {goal}, Python {st}";
            }

            bridge.TrialRunning = false;
            robot.Drive.Stop();
            truth.Dispose();
            var gpos = nodes[goal].Position;
            var fin = robot.transform.position;
            float dist = Vector2.Distance(new Vector2(fin.x, fin.z), new Vector2(gpos.x, gpos.z));
            var rec = new TruthRun
            {
                trial = index, task = cfg.task, mode = mode, seed = seed, a_name = meta.start, b_name = goal,
                a_x = a.x, a_z = a.z, b_x = gpos.x, b_z = gpos.z, python_final_state = bridge.State,
                final_x = fin.x, final_z = fin.z, final_distance_to_b_m = dist,
                straight_line_m = Vector2.Distance(new Vector2(a.x, a.z), new Vector2(gpos.x, gpos.z)), travelled_m = travelled,
                t_start = t0, t_end = Time.time, total_s = Time.time - t0,
                avg_speed_mps = samples > 0 ? speedSum / samples : 0f, max_speed_mps = speedMax,
                avg_turn_dps = samples > 0 ? turnSum / samples : 0f, max_turn_dps = turnMax,
                closest_human_m = float.IsInfinity(closest) ? -1f : closest, shown = shown,
                truth_file = Path.GetFileName(truthPath),
            };
            if (robot.Collisions != null)
                for (int k = collisionBase; k < robot.Collisions.Records.Count; k++)
                {
                    var c = robot.Collisions.Records[k];
                    rec.collisions++;
                    if (c.object_path != null && c.object_path.Contains("Worker")) rec.human_collisions++;
                    if (rec.collided_with.Length == 0) rec.collided_with = c.object_path;
                }

            Score(rec, end, dist);
            bridge.ReachedEndPoint = rec.outcome == "SUCCESS";
            WriteNew(Path.Combine(SessionFolder, $"truth_run{index:000}.json"), JsonUtility.ToJson(rec, true));
            done(rec);
        }

        void Score(TruthRun r, string end, float dist)
        {
            string F3(float x) => x.ToString("0.000", Inv);
            switch (end)
            {
                case "collision": Fail(r, "collision", "collision with " + r.collided_with); break;
                case "stuck": Fail(r, "stuck", "no progress while driving"); break;
                case "timeout": Fail(r, "timeout", "trial time limit reached"); break;
                case "aborted": Fail(r, "aborted", r.python_final_state); break;
                default:
                    if (dist <= cfg.success_radius_m) { r.outcome = "SUCCESS"; r.failure_reason = "none"; r.detail = "stopped " + F3(dist) + " m from B"; }
                    else Fail(r, "wrong_goal", "stopped " + F3(dist) + " m from B (> " + F3(cfg.success_radius_m) + " m)");
                    break;
            }
        }

        static void Fail(TruthRun r, string reason, string detail)
        {
            r.outcome = "FAILURE";
            r.failure_reason = reason;
            r.detail = detail;
        }

        /// <summary>
        /// The robot heads to this junction. Task 1 and Task 2 workers already stand at every stop / junction (since
        /// 2026-10-22 for Task 2), so only what that worker shows is recorded (t_placed = when the robot started heading
        /// there); a junction without a standing worker gets the one worker moved there, as before.
        /// </summary>
        void Place(RoadNode junction, string goal, List<ShownRecord> shown, HashSet<string> placed)
        {
            placed.Add(junction.name);
            var cmd = junction.CommandToward(nodes[goal]);
            if (standingWorkers.TryGetValue(junction.name, out var standing)) cmd = standing.Current;
            else
            {
                worker.PlaceAt(junction.workerStand != null ? junction.workerStand : junction.transform);
                worker.Show(cmd);
            }
            shown.Add(new ShownRecord { junction = junction.name, shown = cmd.ToString(), t_placed = Time.time });
        }

        GestureWorker NearestWorker(Vector3 p)
        {
            GestureWorker best = workers[0];
            float bd = float.PositiveInfinity;
            foreach (var w in workers)
            {
                Vector3 d = w.transform.position - p;
                d.y = 0f;
                if (d.sqrMagnitude < bd) { bd = d.sqrMagnitude; best = w; }
            }

            return best;
        }

        void Teleport(Vector3 pos, float yawDeg)
        {
            var rb = robot.GetComponent<Rigidbody>();
            robot.Drive.ResetMotion();
            var rot = Quaternion.Euler(0f, yawDeg, 0f);
            if (rb != null)
            {
                rb.position = pos;
                rb.rotation = rot;
            }

            robot.transform.SetPositionAndRotation(pos, rot);
        }

        /// <summary>Horizontal distance from the robot's body to the nearest worker's centre axis (every worker of the session).</summary>
        float HumanDistance(Collider body)
        {
            float best = float.PositiveInfinity;
            foreach (var wk in workers)
            {
                Vector3 w = wk.transform.position;
                Vector3 from = robot.transform.position;
                if (body != null)
                {
                    w.y = body.bounds.center.y;
                    from = body.ClosestPoint(w);
                }

                Vector3 d = w - from;
                d.y = 0f;
                best = Mathf.Min(best, d.magnitude);
            }

            return best;
        }

        // ---------------- gesture sweep (development) ----------------

        /// <summary>One sweep placement: the robot at distance D and view angle View from J1's worker stand, facing the worker.</summary>
        struct SweepPlace
        {
            public float D, View, Jitter, RobotYaw;
            public Vector3 Worker, Robot;
        }

        const string PlaceHeader = "distance_m,view_angle_deg,worker_yaw_offset_deg,worker_x,worker_z,robot_x,robot_z,robot_yaw_deg";

        SweepPlace NextPlace(GoalSequence rng, Vector3 w0, float baseYaw)
        {
            var s = cfg.gesture_sweep;
            var p = new SweepPlace
            {
                D = rng.Uniform(s.distance_min_m, s.distance_max_m),
                View = rng.Uniform(-s.view_angle_max_deg, s.view_angle_max_deg),
                Jitter = rng.Uniform(-s.worker_yaw_jitter_deg, s.worker_yaw_jitter_deg),
                Worker = w0,
            };
            Vector3 dir = Quaternion.Euler(0f, baseYaw + p.View, 0f) * Vector3.forward;
            p.Robot = w0 + dir * p.D;
            p.Robot.y = robot.transform.position.y;
            p.RobotYaw = Quaternion.LookRotation(-dir).eulerAngles.y;
            return p;
        }

        void Place(SweepPlace p, float baseYaw)
        {
            Teleport(p.Robot, p.RobotYaw);
            worker.transform.SetPositionAndRotation(p.Worker, Quaternion.Euler(0f, baseYaw + p.View + p.Jitter, 0f));
        }

        static string PlaceCsv(SweepPlace p) => string.Join(",", F(p.D, "0.000"), F(p.View, "0.0"), F(p.Jitter, "0.0"),
            F(p.Worker.x, "0.000"), F(p.Worker.z, "0.000"), F(p.Robot.x, "0.000"), F(p.Robot.z, "0.000"), F(p.RobotYaw, "0.0"));

        void SweepStand(out Vector3 w0, out float baseYaw)
        {
            var j1 = nodes.ContainsKey("J1") ? nodes["J1"] : null;
            Transform stand = j1 != null && j1.workerStand != null ? j1.workerStand : worker.transform;
            w0 = stand.position;
            baseYaw = stand.eulerAngles.y;
            worker.faceTarget = null;
            bridge.TrialIndex = -1;
            bridge.TrialRunning = false;
        }

        IEnumerator Hold(SweepSettings s, Action<float, float> window)
        {
            float t0 = Time.time + s.settle_s;
            while (Time.time < t0) yield return null;
            float t1 = t0 + s.hold_s;
            while (Time.time < t1) yield return null;
            window(t0, t1);
        }

        IEnumerator Sweep(int seed)
        {
            var s = cfg.gesture_sweep;
            SweepStand(out var w0, out float baseYaw);
            var order = GestureSweepOrder.Order(seed, s.repeats);
            var rng = new GoalSequence(seed ^ 0x5eed);
            using (var truth = NewWriter(Path.Combine(SessionFolder, "truth_sweep.csv")))
            {
                truth.WriteLine("sample,gesture_shown,t_start,t_end," + PlaceHeader);
                for (int i = 0; i < order.Count; i++)
                {
                    TrialIndex = i + 1;
                    var p = NextPlace(rng, w0, baseYaw);
                    Place(p, baseYaw);
                    worker.Show(order[i]);
                    Status = $"GestureSweep {i + 1}/{order.Count}: {order[i]} at {p.D:0.00} m";
                    float t0 = 0f, t1 = 0f;
                    yield return Hold(s, (a, b) => { t0 = a; t1 = b; });
                    truth.WriteLine(string.Join(",", (i + 1).ToString(Inv), order[i].ToString(), F(t0, "0.000"), F(t1, "0.000"), PlaceCsv(p)));
                }
            }

            worker.Show(GestureCommand.NONE);
            Status = "done: GestureSweep";
            Debug.Log($"[TrialRunner] {Status}. Folder: {Path.GetFileName(SessionFolder)}");
        }

        /// <summary>
        /// FORWARD hand sweep (development, AUDIT.md section 9 item 15): 'repeats' placements drawn as in the gesture
        /// sweep; at each, FORWARD is shown with the fist and with the index finger (seeded order), with the settle and
        /// hold of the gesture sweep. The worker's own forwardHand is restored afterwards.
        /// </summary>
        IEnumerator HandSweep(int seed)
        {
            var s = cfg.gesture_sweep;
            SweepStand(out var w0, out float baseYaw);
            var hands = ForwardHandSweepOrder.Order(seed, s.repeats);
            var rng = new GoalSequence(seed ^ 0x5eed);
            var keep = worker.forwardHand;
            var p = default(SweepPlace);
            using (var truth = NewWriter(Path.Combine(SessionFolder, "truth_sweep.csv")))
            {
                truth.WriteLine("sample,pair,gesture_shown,hand,t_start,t_end," + PlaceHeader);
                for (int i = 0; i < hands.Count; i++)
                {
                    TrialIndex = i + 1;
                    if (i % 2 == 0)
                    {
                        p = NextPlace(rng, w0, baseYaw);
                        Place(p, baseYaw);
                    }

                    string hand = ForwardHandSweepOrder.Label(hands[i]);
                    worker.forwardHand = hands[i];
                    worker.Show(GestureCommand.FORWARD);
                    Status = $"ForwardHandSweep {i + 1}/{hands.Count}: FORWARD {hand} at {p.D:0.00} m";
                    float t0 = 0f, t1 = 0f;
                    yield return Hold(s, (a, b) => { t0 = a; t1 = b; });
                    truth.WriteLine(string.Join(",", (i + 1).ToString(Inv), (i / 2 + 1).ToString(Inv), "FORWARD", hand,
                        F(t0, "0.000"), F(t1, "0.000"), PlaceCsv(p)));
                }
            }

            worker.forwardHand = keep;
            worker.Show(GestureCommand.NONE);
            Status = "done: ForwardHandSweep";
            Debug.Log($"[TrialRunner] {Status}. Folder: {Path.GetFileName(SessionFolder)}");
        }

        // ---------------- files ----------------

        string NewFolder(string prefix)
        {
            Directory.CreateDirectory(outRoot);
            string stamp = DateTime.Now.ToString("yyyyMMdd_HHmmss", Inv);
            string path = Path.Combine(outRoot, $"{prefix}_{stamp}");
            for (int i = 2; Directory.Exists(path); i++) path = Path.Combine(outRoot, $"{prefix}_{stamp}_{i}");
            Directory.CreateDirectory(path);
            return path;
        }

        static void WriteNew(string path, string text)
        {
            using (var fs = new FileStream(path, FileMode.CreateNew, FileAccess.Write))
            using (var w = new StreamWriter(fs, new UTF8Encoding(false))) w.Write(text);
        }

        static StreamWriter NewWriter(string path) =>
            new StreamWriter(new FileStream(path, FileMode.CreateNew, FileAccess.Write), new UTF8Encoding(false)) { AutoFlush = true, NewLine = "\n" };

        static string F(float x, string fmt = "0.###") => float.IsNaN(x) || float.IsInfinity(x) ? "" : x.ToString(fmt, Inv);
        static string Csv(string s) => s == null ? "" : s.IndexOfAny(new[] { ',', '"', '\n' }) >= 0 ? "\"" + s.Replace("\"", "\"\"") + "\"" : s;
        static string Quote(List<string> xs) => xs.Count == 0 ? "" : "\"" + string.Join("\", \"", xs) + "\"";
        static string JsonEscape(string s) => (s ?? "").Replace("\\", "\\\\").Replace("\"", "\\\"").Replace("\n", "\\n");

        /// <summary>sha256 of the git-ignored worker.fbx, so sessions on different machines can be compared.</summary>
        static string WorkerModelSha256()
        {
            string p = Path.Combine(Application.dataPath, "WarehouseRobot", "Characters", "worker.fbx");
            try { return File.Exists(p) ? FinalRunGuard.Sha256File(p) : "missing"; }
            catch (Exception e) { return "unreadable: " + JsonEscape(e.Message); }
        }

        static string Sha256(string text)
        {
            using (var sha = SHA256.Create())
            {
                var sb = new StringBuilder();
                foreach (var b in sha.ComputeHash(new UTF8Encoding(false).GetBytes(text))) sb.Append(b.ToString("x2", Inv));
                return sb.ToString();
            }
        }

        void ReadGit(out string commit, out string branch)
        {
            commit = branch = "unknown";
            try
            {
                string gitDir = Path.Combine(repoRoot, ".git");
                if (File.Exists(gitDir))
                {
                    string line = File.ReadAllText(gitDir).Trim();
                    if (line.StartsWith("gitdir:")) gitDir = Path.GetFullPath(Path.Combine(repoRoot, line.Substring(7).Trim()));
                }

                if (!Directory.Exists(gitDir)) return;
                string head = File.ReadAllText(Path.Combine(gitDir, "HEAD")).Trim();
                if (!head.StartsWith("ref:")) { commit = head; branch = "(detached)"; return; }
                string reference = head.Substring(4).Trim();
                branch = reference.StartsWith("refs/heads/") ? reference.Substring(11) : reference;
                // a worktree keeps refs in the main repository's .git (commondir)
                string common = File.Exists(Path.Combine(gitDir, "commondir"))
                    ? Path.GetFullPath(Path.Combine(gitDir, File.ReadAllText(Path.Combine(gitDir, "commondir")).Trim())) : gitDir;
                foreach (var dir in new[] { gitDir, common })
                {
                    string refFile = Path.Combine(dir, reference.Replace('/', Path.DirectorySeparatorChar));
                    if (File.Exists(refFile)) { commit = File.ReadAllText(refFile).Trim(); return; }
                    string packed = Path.Combine(dir, "packed-refs");
                    if (!File.Exists(packed)) continue;
                    foreach (var l in File.ReadAllLines(packed))
                        if (l.EndsWith(" " + reference)) { commit = l.Substring(0, l.IndexOf(' ')); return; }
                }
            }
            catch (Exception e)
            {
                Debug.LogWarning("[TrialRunner] could not read the git commit: " + e.Message);
            }
        }

        void OnGUI()
        {
            if (Status == "idle") return;
            GUI.Box(new Rect(10, Screen.height - 70, 520, 60),
                $"{Status}\n{(Completed > 0 ? $"success {Successes}/{Completed}  " : "")}{LastSummary}");
        }
    }

    /// <summary>Seeded order of the gesture sweep: every command 'repeats' times, shuffled (Fisher-Yates on GoalSequence).</summary>
    public static class GestureSweepOrder
    {
        public static readonly GestureCommand[] Commands =
        {
            GestureCommand.NONE, GestureCommand.LEFT, GestureCommand.FORWARD_LEFT, GestureCommand.FORWARD,
            GestureCommand.FORWARD_RIGHT, GestureCommand.RIGHT, GestureCommand.STOP,
        };

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
    }
}
