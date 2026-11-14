using System;
using System.Collections;
using System.Collections.Generic;
using System.Globalization;
using System.IO;
using System.Security.Cryptography;
using System.Text;
using UnityEngine;
using WarehouseAvatar;
using WarehouseHRI;
using WarehouseHRI.V4;
using WarehouseRobot.Bridge;
using WarehouseRobot.GroundTruth;

namespace WarehouseRobot.Scenario
{
    [Serializable] class GtEvalConfig { public int leak_max_pixel_diff = -1; }

    /// <summary>Unity's own leak-test result, recorded in session.json (leak_test/ itself holds only the images, for Python's
    /// python gt_path.py leak, which writes leak_test/leak_test.json and refuses to overwrite one).</summary>
    [Serializable]
    public class LeakRecord
    {
        public bool passed;
        public int max_pixel_diff_allowed;
        public string pose = "";
        public List<GroundTruthLayer.LeakPair> pairs = new List<GroundTruthLayer.LeakPair>();
    }

    [Serializable]
    class SessionV4
    {
        public string study = "v4";
        public int protocol_version;
        public string task, mode;
        public int seed, trials;
        public List<string> endpoints = new List<string>();
        public List<string> goal_order = new List<string>();
        public string git_commit, git_branch, unity_version, scene;
        public string trials_config, trials_config_sha256, roadmap_sha256;
        public string robot_unity_config_sha256_lf, shared_bridge_config, zoom_config;
        public float zoom_fov_min_deg, zoom_fov_default_deg, zoom_fov_max_deg;
        public string python_map_required;
        public List<string> workers = new List<string>();
        public string worker_appearance;
        public string worker_config, worker_config_sha256_lf, trial_workers_config, trial_workers_config_sha256_lf;
        public string data_splits, data_splits_sha256_lf, data_split;
        public string commander_command, worker_layout;
        // 2026-11-12 (upgrade_design.md sections 2 and 6): the v4 map, what the commander shows straight on, the scenario, the timeout used
        public string roadmap, forward_command, scenario;
        // Stage F (2026-11-13): the final setting of a final session ("" in development)
        public string final_setting = "";
        public float timeout_s;
        public int bystanders, max_active_avatars;
        public List<string> run_workers = new List<string>();
        public List<string> v3_workers_hidden = new List<string>();
        public string ground_truth_layer;
        public double grid_cell_size_m, grid_widening_m;
        public string grid_widening_rule = "robot_width_m / 2 + safety_margin_per_side_m (robot.json)";
        public string grid_report;
        public LeakRecord leak_test = new LeakRecord();
        public string note = "goal B, the grid, the optimal path, the trail and the worker truth live only in Unity's files (this folder); Python's inference code never receives them";
    }

    /// <summary>
    /// v4 trial runner (used only in WarehouseRobot_v4.unity; the v3 TrialRunner and its scene are unchanged). Task 2,
    /// development mode from trials.json; a final only with TrialPlayV4 -finalSetting NAME (Stage F, 2026-11-13: final_v4.json,
    /// FinalGuardV4, the numbers of final_plan.json, UNITY_FINAL_DONE.json); replication is refused. It reads the same
    /// robot_vision/configs/trials.json (or trials.local.json) and
    /// roadmap.json as v3 (read only; configs/v4/final_plan.json names these very values) and writes the v3 session files
    /// (session.json, config_used/, truth_run###.json/.csv, results_unity.csv, summary_unity.json, so hri_trials.py merges
    /// it as before) plus, per docs/protocol_v3.md:
    /// - leak_test/ (session level, before trial 1): both robot cameras rendered with the ground-truth layer on and off
    ///   from the trial-1 start pose; the session does not start unless every pair is identical
    ///   (configs/v4/gt_eval.json leak_max_pixel_diff); the result goes into session.json;
    /// - run_###/run.json, grid.json, optimal_path.json, trail.csv and truth.jsonl for every trial.
    /// Workers (Phase 3A, trial_workers_v4.json): the v3 GestureWorkers of the scene are hidden at Play; per run a WorkerV4
    /// commander (worker_v4.json template, look and clips from configs/v4/data_splits.json in the session mode's split,
    /// test data refused in development) is spawned at the first junction's stand and moved, once idle, to the stand of
    /// each junction the robot is sent to. It answers every "Which direction?" with a POINT along the branch toward B;
    /// bystanders (optional) stand still and never gesture. TruthLogger writes run_###/truth.jsonl for all of them.
    /// It also refuses a session unless the bridge speaks protocol 3, the robot uses the v4 config, the ground-truth layer
    /// exists and the grid has a path from A to every endpoint.
    /// </summary>
    public partial class TrialRunnerV4 : MonoBehaviour
    {
        public string repoRootRelativeToProject = "../../..";
        public bool runOnStart = true;
        [Tooltip("Assets/WarehouseRobot/Avatar/Prefabs/WorkerV4.prefab")]
        public WorkerV4 workerPrefab;
        [Tooltip("Assets/WarehouseRobot/Avatar/Config/trial_workers_v4.json")]
        public TextAsset workersConfig;

        public string Status { get; private set; } = "idle";
        public int Successes { get; private set; }
        public int Completed { get; private set; }
        public int TrialTotal { get; private set; }
        public string LastSummary { get; private set; } = "";
        public string SessionFolder { get; private set; }

        const string GtEvalFile = "robot_vision/configs/v4/gt_eval.json";
        const string WorkerConfigAsset = "Assets/WarehouseRobot/Avatar/Config/worker_v4.json";
        const string TrialWorkersAsset = "Assets/WarehouseRobot/Avatar/Config/trial_workers_v4.json";
        const string Layout = "one commander at the start node's stand, moved to the stand of each junction the robot is sent to (moved once idle); bystanders fixed";
        const string RoadmapFileV4 = "robot_vision/configs/v4/roadmap.json";            // P7: the v4 map (the v3 roadmap.json is not read)
        const string TrialPlanAsset = "WarehouseRobot/Scenario/Config/trial_plan_v4.json";
        const string ControlFile = "robot_vision/configs/v4/control.json";
#if UNITY_EDITOR
        /// <summary>Editor session key: a session's trial_workers config (TrialPlayV4 -workersConfig); "" = the scene's asset.</summary>
        public const string WorkersOverrideKey = "WarehouseRobot.TrialRunnerV4.WorkersConfig";
        /// <summary>Editor session key: the final setting (TrialPlayV4 -finalSetting); "" = a development session.</summary>
        public const string FinalSettingKey = "WarehouseRobot.TrialRunnerV4.FinalSetting";
#endif
        // Stage F (2026-11-13, upgrade_design.md section 13): a final session of one setting, guarded by FinalGuardV4
        const string FinalConfigAsset = "Assets/WarehouseRobot/Avatar/Config/final_v4.json";
        string finalSetting = "", finalCfgText = "", finalPlanText = "", frozenText = "", fexpText = "";
        FinalConfigV4 fcfg;
        FinalSettingV4 fset;
        FinalPlanV4 fplan;
        /// <summary>Experiments A/B (experiments_ab.md section 7): the final experiment config of an experiment setting; null otherwise.</summary>
        FinalExperimentV4 fexp;
        bool Final => finalSetting.Length > 0;
        [Serializable] class TrialPlanV4 { public float development_timeout_s; }
        [Serializable] class ControlDialog { public string wait_text = ""; }
        [Serializable] class ControlFileV4 { public ControlDialog dialog = new ControlDialog(); }
        string waitText = "", workersText = "", workersSource = "";
        SeededRandom stopRng;
        bool stopShown, thenDirectionPending;
        string thenCommand;
        Vector3 thenDirection;
        static readonly CultureInfo Inv = CultureInfo.InvariantCulture;

        RobotRig robot;
        RobotBridgeClient bridge;
        GroundTruthLayer gt;
        TrailRecorder trail;
        TruthLogger truthLog;
        RunVisualsV4 visuals;          // U4: trail by state, ask markers, instructed path (GroundTruth layer)
        MinimapV4 minimap;             // U5: the robot's map and the ground-truth map (Game view only)
        Material trailMat;
        readonly Dictionary<string, RoadNode> nodes = new Dictionary<string, RoadNode>();
        TrialsConfig cfg;
        RoadmapMetaV4 meta;
        int leakMaxDiff;
        string repoRoot, outRoot, cfgText, roadText, gtEvalText, splitsText, cfgName = "trials.json";
        const string ExpectedRoute = "Task2";

        // workers
        TrialWorkersConfig wcfg;
        WorkerV4Config workerTemplate;
        DataSplitsV4 splits;
        readonly List<TrialRunWorkers> plans = new List<TrialRunWorkers>();
        readonly List<(RoadNode junction, Vector3 position, Quaternion rotation)> bystanderStands = new List<(RoadNode, Vector3, Quaternion)>();
        readonly List<string> hiddenV3 = new List<string>();
        Transform workersRoot;
        WorkerV4 commander;
        readonly List<WorkerV4> bystanders = new List<WorkerV4>();
        readonly List<WorkerV4> allWorkers = new List<WorkerV4>();
        int spawnedRun = -1, sessionSeed;
        // the commander during a trial
        bool trialActive;
        QuestionWatch question;
        RoadNode goalNode, commanderAt, moveTo;
        int servedAsk;
        TrialRunWorkers runPlan;

        [Serializable] class RoadmapMetaV4 { public string start = "A"; }

        string RepoFile(string rel) => Path.GetFullPath(Path.Combine(repoRoot, rel));

        void Start()
        {
            if (runOnStart) StartCoroutine(Run());
        }

#if UNITY_EDITOR
        // The Editor draws a shader variant that is still compiling as flat cyan (look_check_changes.md, "Fix after the
        // declaration"): a worker spawned per run would reach the robot's cameras cyan. Compile synchronously while the
        // runner exists (an Editor session setting, restored when Play ends).
        bool asyncShaders = true, asyncShadersSet;

        void Awake()
        {
            asyncShaders = UnityEditor.ShaderUtil.allowAsyncCompilation;
            UnityEditor.ShaderUtil.allowAsyncCompilation = false;
            asyncShadersSet = true;
        }

        void OnDestroy()
        {
            if (asyncShadersSet) UnityEditor.ShaderUtil.allowAsyncCompilation = asyncShaders;
        }
#endif

        bool Setup(out string error)
        {
            error = null;
            repoRoot = Path.GetFullPath(Path.Combine(Application.dataPath, "..", repoRootRelativeToProject));
            try
            {
                string local = RepoFile("robot_vision/configs/trials.local.json");
                cfgName = File.Exists(local) ? "trials.local.json" : "trials.json";
                cfgText = File.ReadAllText(RepoFile("robot_vision/configs/" + cfgName));
                roadText = File.ReadAllText(RepoFile(RoadmapFileV4));
                gtEvalText = File.ReadAllText(RepoFile(GtEvalFile));
                cfg = JsonUtility.FromJson<TrialsConfig>(cfgText);
                meta = JsonUtility.FromJson<RoadmapMetaV4>(roadText);
                leakMaxDiff = JsonUtility.FromJson<GtEvalConfig>(gtEvalText).leak_max_pixel_diff;
            }
            catch (Exception e)
            {
                error = "cannot read trials.json, " + RoadmapFileV4 + " or " + GtEvalFile + ": " + e.Message;
                return false;
            }
            if (leakMaxDiff < 0) return Fail(out error, GtEvalFile + " has no leak_max_pixel_diff");
            try
            {
                // development timeout (upgrade_design.md section 6: provisional 420 s until the Stage C rule sets the final one)
                var plan = JsonUtility.FromJson<TrialPlanV4>(File.ReadAllText(Path.Combine(Application.dataPath, TrialPlanAsset)));
                if (!(plan.development_timeout_s > 0f)) return Fail(out error, TrialPlanAsset + ": development_timeout_s must be > 0");
                if (FinalRunGuard.Mode(cfg.mode) == FinalRunGuard.Development) cfg.timeout_s = plan.development_timeout_s;
                waitText = JsonUtility.FromJson<ControlFileV4>(File.ReadAllText(RepoFile(ControlFile))).dialog.wait_text ?? "";
            }
            catch (Exception e) { return Fail(out error, "cannot read " + TrialPlanAsset + " or " + ControlFile + ": " + e.Message); }
#if UNITY_EDITOR
            finalSetting = UnityEditor.SessionState.GetString(FinalSettingKey, "");
            experimentName = UnityEditor.SessionState.GetString(ExperimentKey, "");      // experiments A/B (TrialRunnerV4Experiment.cs)
#endif
            if (Final && !SetupFinal(out error)) return false;

            robot = FindFirstObjectByType<RobotRig>();
            bridge = FindFirstObjectByType<RobotBridgeClient>();
            nodes.Clear();
            foreach (var n in FindObjectsByType<RoadNode>(FindObjectsSortMode.None)) nodes[n.name] = n;
            if (robot == null || robot.Drive == null || bridge == null || !nodes.ContainsKey(meta.start))
                return Fail(out error, "need RobotRig, RobotBridgeClient and the roadmap (run Tools > Warehouse HRI > Add Worker and Roadmap)");
            if (robot.Config == null || !robot.Config.IsV4)
                return Fail(out error, "the robot does not use robot_unity_v4.json (run Tools > Warehouse v4 > Create v4 Scene)");
            if (bridge.ProtocolVersion != BridgeProtocol.Version3)
                return Fail(out error, $"the bridge speaks protocol {bridge.ProtocolVersion}, the v4 study needs 3 (bridge_unity_v4.json -> configs/v4/bridge.json)");
            if (!string.Equals(cfg.task, "Task2", StringComparison.OrdinalIgnoreCase))
                return Fail(out error, $"the v4 runner runs Task2 only (configs/v4/final_plan.json task); {cfgName} says '{cfg.task}'");
            if (FinalRunGuard.Mode(cfg.mode) != FinalRunGuard.Development)
                return Fail(out error, $"v4 {cfg.mode} runs from {cfgName} are refused: {cfgName} keeps mode development; a v4 final starts only with " +
                                       "TrialPlayV4 -finalSetting NAME and its final-run guard (Stage F, upgrade_design.md section 13)");
            if (cfg.dev_seed == cfg.final_seed) return Fail(out error, "dev_seed and final_seed must differ");
            if (Task2Workers.Junctions(nodes.Values, out string problem) == null)
                return Fail(out error, "Task 2 junctions: " + problem + " (run Tools > Warehouse v4 > Build v4 Roadmap)");
            if (nodes[meta.start].kind != RoadNodeKind.Start || nodes[meta.start].workerStand == null)
                return Fail(out error, $"the start node {meta.start} must be a Start node with a worker stand (v4 map, P8: run Tools > Warehouse v4 > Build v4 Roadmap)");

            if (!SetupWorkers(out error)) return false;

            gt = FindFirstObjectByType<GroundTruthLayer>();
            if (gt == null) gt = new GameObject("GroundTruthLayer").AddComponent<GroundTruthLayer>();
            if (!gt.Init(robot, out string gtError)) return Fail(out error, "ground-truth layer: " + gtError);
            Debug.Log("[TrialRunnerV4] " + gt.GridReport);
            foreach (var e in Endpoints())
                if (!GroundTruthLayer.Plan(gt.Grid, nodes[meta.start].Position, nodes[e].Position, out _, out _, out string planError))
                    return Fail(out error, $"ground-truth grid, {meta.start} to {e}: {planError}");
            if (Experiment) { if (!PlanExperimentRuns(out error)) return Fail(out error, $"experiment {experimentName}: {error}"); }
            else if (!CheckBystanderStands(out error)) return false;
            trail = gt.GetComponent<TrailRecorder>();
            if (trail == null) trail = gt.gameObject.AddComponent<TrailRecorder>();
            truthLog = gameObject.AddComponent<TruthLogger>();
            visuals = gt.GetComponent<RunVisualsV4>() ?? gt.gameObject.AddComponent<RunVisualsV4>();
            minimap = FindFirstObjectByType<MinimapV4>() ?? gameObject.AddComponent<MinimapV4>();
            trailMat = GroundTruthLayer.NewMaterial(new Color(1f, 0.3f, 0.9f, 0.95f));
            outRoot = Path.GetFullPath(Path.Combine(repoRoot, "robot_vision", cfg.output_root));
            return true;
        }

        static bool Fail(out string error, string why)
        {
            error = why;
            return false;
        }

        /// <summary>Stage F: final_v4.json, final_plan.json and frozen.json read; every reason of FinalGuardV4 refuses the session;
        /// the final numbers (timeout, success radius) from final_plan.json replace those of trials.json.</summary>
        bool SetupFinal(out string error)
        {
            error = null;
            try
            {
                finalCfgText = File.ReadAllText(Path.Combine(Application.dataPath, "..", FinalConfigAsset));
                fcfg = FinalConfigV4.Parse(finalCfgText);
                finalPlanText = File.ReadAllText(RepoFile(fcfg.final_plan));
                frozenText = File.ReadAllText(RepoFile(fcfg.frozen));
            }
            catch (Exception e) { return Fail(out error, $"final {finalSetting}: cannot read {FinalConfigAsset}, final_plan.json or frozen.json: {e.Message}"); }
            string outputRoot = Path.GetFullPath(Path.Combine(repoRoot, "robot_vision", cfg.output_root));
            var problems = FinalGuardV4.Problems(fcfg, finalSetting, finalPlanText, frozenText,
                p => { string f = RepoFile(p); return File.Exists(f) ? FinalGuardV4.Sha256Lf(File.ReadAllBytes(f)) : null; },
                outputRoot, cfgName != "trials.json");
#if UNITY_EDITOR
            if (UnityEditor.SessionState.GetString(WorkersOverrideKey, "").Length > 0)
                problems.Add("-workersConfig is refused with -finalSetting (the setting names its workers config)");
#endif
            if (problems.Count > 0) return Fail(out error, $"final {finalSetting} refused: " + string.Join("; ", problems));
            fset = fcfg.Setting(finalSetting);
            fplan = FinalPlanV4.Parse(finalPlanText);
            // experiments A/B (experiments_ab.md section 7): the setting names its experiment, side, looks and clips; nothing of them
            // may come from the command line
            string devArgs = experimentName;
#if UNITY_EDITOR
            devArgs += UnityEditor.SessionState.GetString(ExperimentSideKey, "") + UnityEditor.SessionState.GetString(ExperimentLooksKey, "");
#endif
            if (devArgs.Length > 0)
                return Fail(out error, $"final {finalSetting} refused: -experiment, -experimentSide and -experimentLooks are development options (a final setting names its experiment)");
            if (fset.IsExperiment)
            {
                try
                {
                    fexpText = File.ReadAllText(Path.Combine(Application.dataPath, "..", fset.experiment_config));
                    fexp = FinalExperimentV4.Parse(fexpText);
                }
                catch (Exception e) { return Fail(out error, $"final {finalSetting}: cannot read {fset.experiment_config}: {e.Message}"); }
                experimentName = fexp.experiment ?? "";
                if (experimentName.Length == 0) return Fail(out error, $"final {finalSetting}: {fset.experiment_config} names no experiment");
            }
            cfg.timeout_s = fplan.TimeoutS;
            cfg.success_radius_m = fplan.SuccessRadiusM;
            return true;
        }

        /// <summary>The worker template, trial_workers_v4.json and the data splits; the v3 workers hidden; every run planned
        /// (looks and clips) and checked against the splits before anything is written.</summary>
        bool SetupWorkers(out string error)
        {
            error = null;
            if (workerPrefab == null || workerPrefab.config == null || workersConfig == null)
                return Fail(out error, "TrialRunnerV4 needs workerPrefab (WorkerV4.prefab) and workersConfig (trial_workers_v4.json)");
            workerTemplate = WorkerV4Config.Parse(workerPrefab.config.text);
            var templateErrors = workerTemplate.Validate();
            if (templateErrors.Count > 0) return Fail(out error, "worker_v4.json: " + string.Join("; ", templateErrors));
            workersText = workersConfig.text;
            workersSource = TrialWorkersAsset;
            if (Final)
            {
                // the setting's declared final workers config (final_v4.json, Avatar/Config/sessions/final_<setting>.json)
                try { workersText = File.ReadAllText(Path.Combine(Application.dataPath, "..", fset.workers_config)); workersSource = fset.workers_config; }
                catch (Exception e) { return Fail(out error, "cannot read the final workers config " + fset.workers_config + ": " + e.Message); }
            }
#if UNITY_EDITOR
            string over = Final ? "" : UnityEditor.SessionState.GetString(WorkersOverrideKey, "");
            if (over.Length > 0)
            {
                // a declared session config (Avatar/Config/sessions/), given by TrialPlayV4 -workersConfig
                try { workersText = File.ReadAllText(Path.Combine(Application.dataPath, "..", over)); workersSource = over; }
                catch (Exception e) { return Fail(out error, "cannot read the session workers config " + over + ": " + e.Message); }
            }
#endif
            wcfg = TrialWorkersConfig.Parse(workersText);
            var errors = wcfg.Validate();
            if (errors.Count > 0) return Fail(out error, "trial_workers_v4.json: " + string.Join("; ", errors));
            try { splitsText = File.ReadAllText(RepoFile(wcfg.data_splits)); }
            catch (Exception e) { return Fail(out error, "cannot read " + wcfg.data_splits + ": " + e.Message); }
            splits = DataSplitsV4.Parse(splitsText);

            string mode = FinalRunGuard.Mode(cfg.mode);
            TrialTotal = Final ? fplan.RunsPerSetting : Mathf.Max(1, cfg.trial_count);
            plans.Clear();
            if (Experiment && !SetupExperiment(mode, out error)) return false;
            for (int run = 1; run <= TrialTotal && !Experiment; run++)
            {
                string planError;
                var plan = Final ? TrialRunWorkers.PlanFinal(run, fset, wcfg, workerTemplate, splits, out planError)
                                 : TrialRunWorkers.Plan(run, mode, wcfg, workerTemplate, splits, out planError);
                if (plan == null) return Fail(out error, "worker looks and clips: " + planError);
                plans.Add(plan);
            }

            int otherAvatars = 0;
            foreach (var w in FindObjectsByType<WorkerV4>(FindObjectsSortMode.None)) if (w.isActiveAndEnabled) otherAvatars++;
            if (!Experiment && otherAvatars + wcfg.ActiveAvatars > wcfg.max_active_avatars)
                return Fail(out error, $"{otherAvatars} WorkerV4 already active in the scene + {wcfg.ActiveAvatars} trial workers > max_active_avatars {wcfg.max_active_avatars}");
            if (Experiment && otherAvatars > 0)
                return Fail(out error, $"{otherAvatars} WorkerV4 already active in the scene: an experiment counts its own workers against max_active_avatars {ecfg.max_active_avatars}");

            hiddenV3.Clear();
            foreach (var g in FindObjectsByType<GestureWorker>(FindObjectsInactive.Include, FindObjectsSortMode.None))
            {
                if (g.gameObject.activeSelf) hiddenV3.Add(g.name);
                g.gameObject.SetActive(false);
            }
            workersRoot = new GameObject("WorkersV4").transform;
            return true;
        }

        /// <summary>The bystander stands of the config: on a free grid cell, clear of colliders, the roads and every commander stand,
        /// and farther than the commander along the approach to every ask node.</summary>
        bool CheckBystanderStands(out string error)
        {
            error = null;
            bystanderStands.Clear();
            var b = wcfg.bystanders;
            for (int k = 0; k < b.count; k++)
            {
                var s = b.stands[k];
                string label = $"bystander {k + 1} ({s.junction}, ahead {s.ahead_m.ToString("0.00", Inv)} m, right {s.right_m.ToString("0.00", Inv)} m)";
                if (!nodes.TryGetValue(s.junction, out var j) || !j.IsJunction) return Fail(out error, label + ": no such junction");
                var from = ArrivalNode(j);
                if (from == null) return Fail(out error, label + ": no road arrives at " + j.name);
                Vector3 arrival = j.Position - from.Position;
                Vector3 p = TrialWorkerGeometry.Stand(j.Position, arrival, s.ahead_m, s.right_m);
                p.y = j.workerStand != null ? j.workerStand.position.y : j.Position.y;
                foreach (var a in nodes.Values)
                    foreach (var br in a.branches)
                    {
                        if (br == null || br.next == null) continue;
                        float d = TrialWorkerGeometry.SegmentDistance(p, a.Position, br.next.Position);
                        if (d < b.min_road_clearance_m)
                            return Fail(out error, $"{label}: {d.ToString("0.00", Inv)} m from the road {a.name}-{br.next.name} (< min_road_clearance_m)");
                    }
                foreach (var a in nodes.Values)
                {
                    if (!a.IsAskNode || a.workerStand == null) continue;          // junctions and the start node A
                    Vector3 d = a.workerStand.position - p;
                    d.y = 0f;
                    if (d.magnitude < b.min_commander_distance_m)
                        return Fail(out error, $"{label}: {d.magnitude.ToString("0.00", Inv)} m from the commander stand of {a.name} (< min_commander_distance_m)");
                    // 2026-11-12 (upgrade_design.md section 13): the robot approaches the nearest person it sees, so along its
                    // approach to every ask node the bystander must be nearer_margin_m farther away than that node's commander stand.
                    var arriveFrom = ArrivalNode(a);
                    float margin = TrialWorkerGeometry.NearerMargin(p, a.workerStand.position, a.Position,
                        arriveFrom != null ? arriveFrom.Position : (Vector3?)null, b.approach_m, out var at);
                    if (margin < b.nearer_margin_m)
                        return Fail(out error, $"{label}: on the approach to {a.name}, at ({at.x.ToString("0.00", Inv)}, {at.z.ToString("0.00", Inv)}), only " +
                                               $"{margin.ToString("0.00", Inv)} m farther than the commander stand (< nearer_margin_m {b.nearer_margin_m.ToString("0.00", Inv)})");
                }
                var cell = gt.Grid.CellOf(p.x, p.z);
                if (!gt.Grid.Free(cell.x, cell.y)) return Fail(out error, label + ": on a blocked cell of the ground-truth grid");
                if (Physics.CheckCapsule(p + Vector3.up * 0.35f, p + Vector3.up * 1.55f, 0.3f, ~0, QueryTriggerInteraction.Ignore))
                    return Fail(out error, label + ": inside a collider");
                Vector3 face = j.Position - p;
                face.y = 0f;
                bystanderStands.Add((j, p, Quaternion.LookRotation(face.sqrMagnitude > 1e-6f ? face : Vector3.forward, Vector3.up)));
            }
            return true;
        }

        RoadNode ArrivalNode(RoadNode junction)
        {
            foreach (var n in nodes.Values)
                foreach (var br in n.branches)
                    if (br != null && br.next == junction) return n;
            return null;
        }

        List<string> Endpoints()
        {
            var endpoints = new List<string>();
            foreach (var kv in nodes) if (kv.Value.IsEndpoint) endpoints.Add(kv.Key);
            endpoints.Sort(StringComparer.Ordinal);
            return endpoints;
        }

        IEnumerator Run()
        {
            yield return null;
            if (!Setup(out var error))
            {
                Status = "not started: " + error;
                Debug.LogError("[TrialRunnerV4] " + error);
                yield break;
            }

            string mode = Final ? FinalRunGuard.Final : FinalRunGuard.Mode(cfg.mode);
            int seed = Final ? fplan.FinalSeed : cfg.dev_seed;
            sessionSeed = seed;
            var endpoints = Endpoints();
            var order = new List<string>();
            var gp = new GoalSequence(seed);
            for (int i = 0; i < TrialTotal; i++) order.Add(endpoints[gp.NextGoalIndex(endpoints.Count)]);
            if (Experiment) { order = new List<string>(eGoals); endpoints = ExperimentPlanAB.Endpoints(eplan.Map); }

            SessionFolder = NewFolder(Final ? $"trials_final_{cfg.task}_{finalSetting}" : Experiment ? $"trials_{mode}_{cfg.task}_{experimentName}" : $"trials_{mode}_{cfg.task}");
            string used = Path.Combine(SessionFolder, "config_used");
            Directory.CreateDirectory(used);
            GroundTruthFiles.WriteNew(Path.Combine(used, cfgName), cfgText);
            GroundTruthFiles.WriteNew(Path.Combine(used, "roadmap.json"), roadText);
            GroundTruthFiles.WriteNew(Path.Combine(used, "trial_plan_v4.json"), File.ReadAllText(Path.Combine(Application.dataPath, TrialPlanAsset)));
            GroundTruthFiles.WriteNew(Path.Combine(used, "gt_eval.json"), gtEvalText);
            string robotUnityText = robot.Config.UnityConfigText;
            GroundTruthFiles.WriteNew(Path.Combine(used, robot.Config.UnityConfigName + ".json"), robotUnityText);
            GroundTruthFiles.WriteNew(Path.Combine(used, "control_zoom_source.json"), File.ReadAllText(robot.Config.ZoomConfigPath));
            GroundTruthFiles.WriteNew(Path.Combine(used, "worker_v4.json"), workerPrefab.config.text);
            GroundTruthFiles.WriteNew(Path.Combine(used, "trial_workers_v4.json"), workersText);
            GroundTruthFiles.WriteNew(Path.Combine(used, "data_splits.json"), splitsText);
            WriteExperimentConfigs(used);
            if (Final)
            {
                GroundTruthFiles.WriteNew(Path.Combine(used, "final_v4.json"), finalCfgText);
                GroundTruthFiles.WriteNew(Path.Combine(used, "final_plan.json"), finalPlanText);
                GroundTruthFiles.WriteNew(Path.Combine(used, "frozen.json"), frozenText);
            }

            // Leak test from the pose of trial 1's start (run 1's workers in place), with trial 1's ground truth drawn (A, B, path) and the blocked cells.
            if (!ResetForTrial(order[0], 1, out error))
            {
                Status = "not started: " + error;
                Debug.LogError("[TrialRunnerV4] " + error);
                GroundTruthFiles.WriteNew(Path.Combine(SessionFolder, "NOT_STARTED.txt"), error + "\n");
                yield break;
            }
            var a = nodes[meta.start].Position;
            gt.Show(a, GoalPosition(order[0], 1));
            yield return new WaitForEndOfFrame();
            var leak = new LeakRecord { max_pixel_diff_allowed = leakMaxDiff, pose = PoseText() };
            bridge.FramesPaused = true;
            try { leak.passed = gt.LeakTest(Path.Combine(SessionFolder, GroundTruthFiles.LeakFolder), leakMaxDiff, out leak.pairs); }
            finally { bridge.FramesPaused = false; }

            ReadGit(out var commit, out var branch);
            // the same fields in the same order as before (JsonUtility writes them in declaration order); an experiment session
            // writes its subclass SessionV4AB with the experiment's fields after them (TrialRunnerV4Experiment.cs)
            var session = NewSessionRecord();
            session.protocol_version = bridge.ProtocolVersion; session.task = cfg.task; session.mode = mode; session.seed = seed; session.trials = TrialTotal;
            session.endpoints = endpoints; session.goal_order = order; session.git_commit = commit; session.git_branch = branch;
            session.unity_version = Application.unityVersion; session.scene = gameObject.scene.name;
            session.trials_config = cfgName; session.trials_config_sha256 = Sha256(cfgText); session.roadmap_sha256 = Sha256(roadText);
            session.robot_unity_config_sha256_lf = Sha256(robotUnityText.Replace("\r\n", "\n"));
            session.shared_bridge_config = Relative(BridgeSharedPath()); session.zoom_config = Relative(robot.Config.ZoomConfigPath);
            session.zoom_fov_min_deg = robot.PanTilt.FovMinDeg; session.zoom_fov_default_deg = robot.PanTilt.DefaultFovDeg; session.zoom_fov_max_deg = robot.PanTilt.FovMaxDeg;
            session.python_map_required = ExpectedRoute;
            session.worker_appearance = string.Join(" | ", allWorkers.ConvertAll(w => w.name + ": " + w.LookDescription));
            session.worker_config = WorkerConfigAsset; session.worker_config_sha256_lf = Sha256(workerPrefab.config.text.Replace("\r\n", "\n"));
            session.trial_workers_config = workersSource; session.trial_workers_config_sha256_lf = Sha256(workersText.Replace("\r\n", "\n"));
            session.roadmap = Experiment && eplan.MapName != "roadmap" ? ecfg.scenarios_ab + " maps." + eplan.MapName : RoadmapFileV4;
            session.forward_command = wcfg.forward_command; session.scenario = Experiment ? "experiment_" + experimentName : wcfg.scenario; session.timeout_s = cfg.timeout_s;
            session.data_splits = wcfg.data_splits; session.data_splits_sha256_lf = Sha256(splitsText.Replace("\r\n", "\n"));
            session.data_split = Experiment ? eSplit : plans[0].Split;
            session.commander_command = wcfg.commander_command;
            session.worker_layout = Experiment ? $"experiment {experimentName}: {eplan.LayoutKind} layout, workers at every asking node, anyone asked answers (experiments_ab.md section 3)" : Layout;
            session.bystanders = Experiment ? 0 : wcfg.bystanders.count; session.max_active_avatars = Experiment ? ecfg.max_active_avatars : wcfg.max_active_avatars;
            session.v3_workers_hidden = new List<string>(hiddenV3);
            session.ground_truth_layer = robot.Config.Unity.v4.ground_truth.layer; session.final_setting = finalSetting;
            session.grid_cell_size_m = gt.Grid.CellSize; session.grid_widening_m = gt.Grid.InflationM; session.grid_report = gt.GridReport;
            session.leak_test = leak;
            foreach (var w in allWorkers)
                session.workers.Add($"{w.name} worker_id {w.workerId} ({w.transform.position.x.ToString("0.00", Inv)}, {w.transform.position.z.ToString("0.00", Inv)})");
            for (int i = 0; i < plans.Count && !Experiment; i++)
                session.run_workers.Add($"run {i + 1}: commander {plans[i].CommanderLook}" +
                                        (plans[i].BystanderLooks.Count > 0 ? "; bystanders " + string.Join(", ", plans[i].BystanderLooks) : "") +
                                        $"; clips {string.Join(", ", plans[i].AllowedClips)} ({plans[i].Split})");
            GroundTruthFiles.WriteNew(Path.Combine(SessionFolder, "session.json"), JsonUtility.ToJson(session, true).Replace("\r\n", "\n") + "\n");

            if (!leak.passed)
            {
                string why = "leak test failed: a robot camera image changes when the ground-truth layer is shown, or the control " +
                             "found the layer out of view (" +
                             string.Join(", ", leak.pairs.ConvertAll(p => $"{p.name} max diff {p.max_diff}, {p.differing_pixels} pixels, " +
                                                                          $"control {p.layer_visible_pixels} pixels")) +
                             $"); see {GroundTruthFiles.LeakFolder}/. No run starts.";
                Status = "not started: " + why;
                Debug.LogError("[TrialRunnerV4] " + why);
                GroundTruthFiles.WriteNew(Path.Combine(SessionFolder, "NOT_STARTED.txt"), why + "\n");
                yield break;
            }
            Debug.Log("[TrialRunnerV4] Leak test passed: both robot camera images identical with the ground-truth layer on and off.");

            Status = "waiting for the Python bridge";
            while (!bridge.Connected) yield return null;
            float waitStart = Time.realtimeSinceStartup;
            while (!bridge.PythonPerceptionReady)
            {
                Status = bridge.Connected ? $"waiting for Python: perception ready ({Time.realtimeSinceStartup - waitStart:0} s)" : "waiting for the Python bridge";
                yield return null;
            }
            if (bridge.PythonRoute != ExpectedRoute)
            {
                string why = $"Python's map is '{bridge.PythonRoute}' but Task2 needs '{ExpectedRoute}': restart the server with " +
                             "python -m bridge.server --config configs/v4/bridge.json --mode guide --task Task2 ...";
                Status = "not started: " + why;
                Debug.LogError("[TrialRunnerV4] " + why);
                GroundTruthFiles.WriteNew(Path.Combine(SessionFolder, "NOT_STARTED.txt"), why + "\n");
                yield break;
            }

            yield return new WaitForSeconds(0.5f);
            yield return Trials(seed, mode, order);
        }

        string BridgeSharedPath() => RepoFile("robot_vision/configs/v4/bridge.json");

        string Relative(string full)
        {
            string root = repoRoot.TrimEnd(Path.DirectorySeparatorChar, Path.AltDirectorySeparatorChar) + Path.DirectorySeparatorChar;
            return full.StartsWith(root, StringComparison.OrdinalIgnoreCase) ? full.Substring(root.Length).Replace('\\', '/') : Path.GetFileName(full);
        }

        string PoseText()
        {
            var p = robot.transform.position;
            return $"{meta.start}: x {p.x.ToString("0.000", Inv)}, z {p.z.ToString("0.000", Inv)}, yaw {robot.transform.eulerAngles.y.ToString("0.0", Inv)} deg";
        }

        /// <summary>Robot to A facing its start heading (the Start node's rotation, P8); run's workers spawned (once per run):
        /// the commander at the start node's stand (it answers the first ask there), the bystanders at theirs.</summary>
        bool ResetForTrial(string goal, int run, out string error)
        {
            error = null;
            if (Experiment) return ResetForExperimentTrial(run, out error);
            var start = nodes[meta.start];
            Vector3 a = start.Position;
            float yaw = start.transform.eulerAngles.y;
            Teleport(new Vector3(a.x, robot.transform.position.y, a.z), yaw);
            bridge.ReachedEndPoint = false;
            goalNode = nodes[goal];
            if (spawnedRun == run) return true;

            DestroyWorkers();
            runPlan = plans[run - 1];
            commander = Spawn("WorkerV4_Commander", runPlan.CommanderLook, wcfg.commander_worker_id, start.workerStand.position, start.workerStand.rotation, run, out error);
            if (commander == null) return false;
            commander.IsCommander = true;
            commanderAt = start;
            stopRng = SeededRandom.For(sessionSeed, run, 9973);         // the STOP scenario's own stream (distance never drawn: first moment in range)
            stopShown = thenDirectionPending = false;
            for (int k = 0; k < bystanderStands.Count; k++)
            {
                var s = bystanderStands[k];
                var w = Spawn($"WorkerV4_Bystander_{k + 1}", runPlan.BystanderLooks[k], wcfg.commander_worker_id + k + 1, s.position, s.rotation, run, out error);
                if (w == null) return false;
                bystanders.Add(w);
            }
            spawnedRun = run;
            return true;
        }

        WorkerV4 Spawn(string name, string look, int id, Vector3 position, Quaternion rotation, int run, out string error, Action<WorkerV4> prepare = null)
        {
            error = null;
            var w = Instantiate(workerPrefab, position, rotation, workersRoot);
            w.name = name;
            w.lookId = look;
            w.workerId = id;
            w.robot = robot.transform;
            w.robotEye = robot.PanTilt != null ? robot.PanTilt.transform : null;
            w.SetRun(sessionSeed, run);
            prepare?.Invoke(w);
            allWorkers.Add(w);
            if (w.Initialize()) return w;
            error = $"{name} (look {look}): {w.Problem}";
            return null;
        }

        void DestroyWorkers()
        {
            foreach (var w in allWorkers) if (w != null) Destroy(w.gameObject);
            allWorkers.Clear();
            DestroyExperimentExtras();
            bystanders.Clear();
            commander = null;
            commanderAt = moveTo = null;
            spawnedRun = -1;
        }

        // ---------------- the commander (every frame of a trial) ----------------

        void Update()
        {
            if (Experiment) { UpdateExperiment(); return; }
            if (!trialActive || commander == null || !commander.Ready) return;
            question.Update(bridge.ScreenText);
            if (moveTo != null && !commander.Busy)
            {
                commander.transform.SetPositionAndRotation(moveTo.workerStand.position, moveTo.workerStand.rotation);
                commanderAt = moveTo;
                moveTo = null;
            }
            UpdateStopScenario();
            // "One moment..." (Python's wait text) continues the ask: the direction that follows a WAIT belongs to it
            bool waiting = waitText.Length > 0 && bridge.ScreenText == waitText;
            if (!question.Visible && !waiting)
            {
                commander.SetQuestionVisible(false);
                // a gesture that has not started belongs to the question that is gone (a STOP shown while driving does not)
                if (!(commander.Busy && commander.Current.command == WorkerV4Config.Stop)) commander.CancelPending();
                thenDirectionPending = false;
                return;
            }
            commander.SetQuestionVisible(true);
            if (thenDirectionPending && !commander.Busy && moveTo == null)
            {
                // wait_then_direction: the WAIT has returned; now the direction, within the same ask (IgnoreQuestion: the
                // question appeared before the WAIT, so the gesture still starts after it)
                thenDirectionPending = false;
                Show(thenCommand, thenDirection, true, "after the WAIT");
                return;
            }
            if (servedAsk == question.Ask || moveTo != null || commander.Busy || commanderAt == null) return;
            servedAsk = question.Ask;
            var cmd = commanderAt.CommandToward(goalNode);
            var next = commanderAt.Next(cmd);
            if (next == null)
            {
                Debug.LogError($"[TrialRunnerV4] ask {question.Ask} at {commanderAt.name}: no branch leads to {goalNode.name}; the commander shows nothing");
                return;
            }
            // PROCEED for the branch straight ahead (upgrade_design.md section 2), POINT (option A stance) otherwise
            string direction = cmd == GestureCommand.FORWARD && !string.IsNullOrEmpty(wcfg.forward_command) ? wcfg.forward_command : wcfg.commander_command;
            Vector3 dir = TrialWorkerGeometry.BranchDirection(commanderAt.Position, next.Position);
            if (wcfg.scenario == TrialWorkersConfig.ScenarioWaitThenDirection)
            {
                thenCommand = direction;
                thenDirection = dir;
                thenDirectionPending = Show(WorkerV4Config.Wait, dir, false, $"first, then {direction} toward {cmd}");
                return;
            }
            Show(direction, dir, false, cmd.ToString());
        }

        bool Show(string command, Vector3 direction, bool ignoreQuestion, string what, float holdS = 0f)
        {
            var req = new GestureRequest
            {
                Command = command, AllowedClips = runPlan.AllowedFor(command), PointDirection = direction,
                IgnoreQuestion = ignoreQuestion, HoldS = holdS,
            };
            if (!commander.Request(req, out string error))
            {
                Debug.LogError($"[TrialRunnerV4] ask {question.Ask} at {commanderAt.name}: the commander cannot show {command} ({what}): {error}");
                return false;
            }
            Debug.Log($"[TrialRunnerV4] ask {question.Ask} at {commanderAt.name} (\"{bridge.ScreenText}\"): commander {commander.lookId} shows {command} " +
                      $"({what}) with {commander.Current.clip}, {commander.Current.arm} arm");
            return true;
        }

        /// <summary>stop_while_driving (upgrade_design.md section 6): once per run, while the robot drives toward the node where
        /// the commander already stands and is between stop.distance_m from it (and the commander has noticed it), the
        /// commander shows STOP for a hold drawn from stop.hold_s, then lowers it.</summary>
        void UpdateStopScenario()
        {
            if (wcfg.scenario != TrialWorkersConfig.ScenarioStop || stopShown || moveTo != null || commander.Busy || commanderAt == null) return;
            string st = bridge.State ?? "";
            if (!st.StartsWith("navigate") || !commander.Noticed) return;
            Vector3 d = commander.transform.position - robot.transform.position;
            d.y = 0f;
            float dist = d.magnitude;
            if (dist < wcfg.stop.distance_m[0] || dist > wcfg.stop.distance_m[1]) return;
            stopShown = true;
            float hold = stopRng.Range(wcfg.stop.hold_s);
            Show(WorkerV4Config.Stop, Vector3.zero, true, $"STOP while driving, {dist.ToString("0.0", Inv)} m, hold {hold.ToString("0.0", Inv)} s", hold);
        }

        // ---------------- trials (scoring and truth files as the v3 TrialRunner) ----------------

        IEnumerator Trials(int seed, string mode, List<string> order)
        {
            using (var results = NewWriter(Path.Combine(SessionFolder, "results_unity.csv")))
            {
                results.WriteLine("trial,b_name,outcome,failure_reason,detail,final_distance_to_b_m,total_s,travelled_m,collisions,closest_human_m,python_final_state");
                for (int i = 1; i <= TrialTotal; i++)
                {
                    TruthRun rec = null;
                    string error = null;
                    yield return OneTrial(i, seed, mode, order[i - 1], r => rec = r, e => error = e);
                    if (error != null)
                    {
                        Status = "stopped: " + error;
                        Debug.LogError("[TrialRunnerV4] " + error);
                        GroundTruthFiles.WriteNew(Path.Combine(SessionFolder, "STOPPED.txt"), error + "\n");
                        yield break;
                    }
                    Completed = i;
                    if (rec.outcome == "SUCCESS") Successes++;
                    results.WriteLine(string.Join(",", i.ToString(Inv), rec.b_name, rec.outcome, rec.failure_reason, Csv(rec.detail),
                        F(rec.final_distance_to_b_m), F(rec.total_s), F(rec.travelled_m), rec.collisions.ToString(Inv),
                        F(rec.closest_human_m), Csv(rec.python_final_state)));
                    LastSummary = $"trial {i}: {rec.outcome} {(rec.failure_reason == "none" ? "" : rec.failure_reason)} ({rec.detail}); {Successes}/{i}";
                    Debug.Log("[TrialRunnerV4] " + LastSummary);
                    yield return new WaitForSeconds(cfg.pause_between_trials_s);
                }
            }

            string summary = $"{{\n  \"study\": \"v4\",\n  \"trials\": {TrialTotal},\n  \"successes\": {Successes},\n  \"mode\": \"{mode}\",\n  \"task\": \"{cfg.task}\",\n  \"seed\": {seed}\n}}\n";
            GroundTruthFiles.WriteNew(Path.Combine(SessionFolder, "summary_unity.json"), summary);
            if (Final && Completed == TrialTotal)
            {
                // Stage F: the setting's run-once marker, written last (a session that stops early writes none)
                ReadGit(out var commit, out _);
                GroundTruthFiles.WriteNew(Path.Combine(SessionFolder, fcfg.done_file),
                    FinalGuardV4.DoneJson(finalSetting, TrialTotal, Successes, commit, Path.GetFileName(SessionFolder), DateTime.Now.ToString("s", Inv)));
            }
            Status = $"done: {Successes}/{TrialTotal} SUCCESS";
            Debug.Log($"[TrialRunnerV4] {Status}. Folder: {Path.GetFileName(SessionFolder)}");
        }

        IEnumerator OneTrial(int index, int seed, string mode, string goal, Action<TruthRun> done, Action<string> failed)
        {
            if (!ResetForTrial(goal, index, out string resetError)) { failed($"trial {index}: workers: {resetError}"); yield break; }
            yield return null;                                       // the workers' Start and first Update before the run starts
            Vector3 a = nodes[meta.start].Position, gpos = GoalPosition(goal, index);
            var shown = new List<ShownRecord>();
            var placed = new HashSet<string>();
            eAskRecords.Clear();
            if (!Experiment) Place(nodes[meta.start], shown, placed);                // the commander answers the first ask at A (P8)
            int collisionBase = robot.Collisions != null ? robot.Collisions.Records.Count : 0;
            var body = robot.GetComponent<Collider>();
            if (body == null) body = robot.GetComponentInChildren<Collider>();

            string runDir = Path.Combine(SessionFolder, GroundTruthFiles.RunFolderName(index));
            Directory.CreateDirectory(runDir);
            gt.WriteRun(runDir, a, gpos);                           // grid.json, optimal_path.json; draws A, B and the path

            string truthPath = Path.Combine(SessionFolder, $"truth_run{index:000}.csv");
            var truth = NewWriter(truthPath);
            truth.WriteLine("time_s,robot_x,robot_z,robot_yaw_deg,v_mps,omega_radps,worker_x,worker_z,worker_yaw_deg,gesture_shown,closest_human_m,collisions,python_state");
            bridge.TrialIndex = index;
            bridge.TrialRunning = true;
            yield return new WaitForFixedUpdate();
            float t0 = Time.time, nextTruth = t0;
            GroundTruthFiles.WriteNew(Path.Combine(runDir, "run.json"), GroundTruthFiles.ToJson(new RunFile { run_start_s = t0 }));
            var g = robot.Config.Unity.v4.ground_truth;
            trail.Begin(robot.transform, runDir, g.trail_interval_s, gt.Layer, trailMat, g.line_width_m, gt.FloorY + g.floor_offset_m + 0.01f);
            truthLog.Begin(Path.Combine(runDir, GroundTruthFiles.TruthFile), allWorkers, workerTemplate.truth_log.interval_s);
            question = new QuestionWatch(workerTemplate.question.prompt);
            servedAsk = 0;
            visuals.Begin(gt, robot, bridge, Experiment ? null : goalNode, workerTemplate.question.prompt, () => commanderAt,
                          () => commander != null && commander.CurrentSpec != null ? commander.Current.command : "-");
            if (Experiment) visuals.SetExperiment(ExperimentAskNode, ExperimentTrueCommand, ExperimentLie, ExperimentShown);
            minimap.BeginRun(Experiment ? eGoalMarker : goalNode.transform);
            trialActive = true;

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
                if (!Experiment && bridge.HasTarget)
                    foreach (var kv in nodes)
                        if (kv.Value.IsJunction && !placed.Contains(kv.Key) &&
                            Vector2.Distance(bridge.Target, new Vector2(kv.Value.Position.x, kv.Value.Position.z)) < 0.5f)
                            Place(kv.Value, shown, placed);
                if (now >= nextTruth)
                {
                    nextTruth += cfg.truth_interval_s;
                    var nw = NearestWorker(p);
                    var w = nw.transform;
                    truth.WriteLine(string.Join(",", F(now, "0.000"), F(p.x, "0.000"), F(p.z, "0.000"), F(robot.transform.eulerAngles.y, "0.0"),
                        F(robot.Drive.V, "0.000"), F(robot.Drive.Omega, "0.000"), F(w.position.x, "0.000"), F(w.position.z, "0.000"),
                        F(w.eulerAngles.y, "0.0"), nw.Truth(now).TrueCommand, F(hd, "0.000"),
                        ((robot.Collisions != null ? robot.Collisions.Records.Count : 0) - collisionBase).ToString(Inv), Csv(bridge.State)));
                }
                if (truthLog.Failed.Length > 0) { end = "truth_log"; break; }

                bool wantsToMove = Mathf.Abs(robot.Drive.CommandedV) > 0.05f;
                Vector3 moved = p - progressPos;
                moved.y = 0f;
                if (!wantsToMove || moved.magnitude >= cfg.stuck_min_progress_m) { progressTime = now; progressPos = p; }
                string st = bridge.State ?? "";
                if (robot.Collisions != null && robot.Collisions.Records.Count > collisionBase) end = "collision";
                else if ((st.StartsWith("done") || st.StartsWith("aborted")) && Mathf.Abs(robot.Drive.V) < 0.02f) end = st.StartsWith("done") ? "done" : "aborted";
                else if (now - t0 > cfg.timeout_s) end = "timeout";
                else if (now - progressTime > cfg.stuck_s) end = "stuck";
                else if (!bridge.Connected) Status = $"trial {index}: Python disconnected, waiting";
                else Status = $"trial {index}/{TrialTotal}: goal {goal}, Python {st}";
            }

            trialActive = false;
            visuals.End();
            if (commander != null) { commander.SetQuestionVisible(false); commander.CancelPending(); }
            if (Experiment)
                foreach (var w in allWorkers) if (w != null && w.gameObject.activeSelf) { w.SetQuestionVisible(false); w.CancelPending(); }
            bridge.TrialRunning = false;
            robot.Drive.Stop();
            trail.End();
            truthLog.End();
            truth.Dispose();
            if (end == "truth_log" || truthLog.Failed.Length > 0) { failed($"trial {index}: truth.jsonl refused a row: {truthLog.Failed}"); yield break; }
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
                closest_human_m = float.IsInfinity(closest) ? -1f : closest, shown = Experiment ? new List<ShownRecord>(eAskRecords) : shown,
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
            if (Experiment && eLimit.Length > 0) rec.detail += "; " + eLimit;
            bridge.ReachedEndPoint = rec.outcome == "SUCCESS";
            GroundTruthFiles.WriteNew(Path.Combine(SessionFolder, $"truth_run{index:000}.json"), JsonUtility.ToJson(rec, true));
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

        /// <summary>The robot is sent to this junction: record the branch toward B the commander will show there, and move
        /// the commander to its stand (at once if idle, else as soon as it is).</summary>
        void Place(RoadNode junction, List<ShownRecord> shown, HashSet<string> placed)
        {
            placed.Add(junction.name);
            shown.Add(new ShownRecord { junction = junction.name, shown = junction.CommandToward(goalNode).ToString(), t_placed = Time.time });
            if (commanderAt != junction && junction.workerStand != null) moveTo = junction;
        }

        WorkerV4 NearestWorker(Vector3 p)
        {
            WorkerV4 best = allWorkers[0];
            float bd = float.PositiveInfinity;
            foreach (var w in allWorkers)
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

        float HumanDistance(Collider body)
        {
            float best = float.PositiveInfinity;
            foreach (var wk in allWorkers)
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

        static StreamWriter NewWriter(string path) =>
            new StreamWriter(new FileStream(path, FileMode.CreateNew, FileAccess.Write), new UTF8Encoding(false)) { AutoFlush = true, NewLine = "\n" };

        static string F(float x, string fmt = "0.###") => float.IsNaN(x) || float.IsInfinity(x) ? "" : x.ToString(fmt, Inv);
        static string Csv(string s) => s == null ? "" : s.IndexOfAny(new[] { ',', '"', '\n' }) >= 0 ? "\"" + s.Replace("\"", "\"\"") + "\"" : s;

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
                Debug.LogWarning("[TrialRunnerV4] could not read the git commit: " + e.Message);
            }
        }

        void OnGUI()
        {
            if (Status == "idle") return;
            GUI.Box(new Rect(10, Screen.height - 70, 520, 60),
                $"v4 {Status}\n{(Completed > 0 ? $"success {Successes}/{Completed}  " : "")}{LastSummary}");
        }
    }
}
