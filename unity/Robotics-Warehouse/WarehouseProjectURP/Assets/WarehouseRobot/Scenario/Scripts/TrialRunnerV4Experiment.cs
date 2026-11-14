using System;
using System.Collections.Generic;
using System.Globalization;
using System.IO;
using UnityEngine;
using WarehouseAvatar;
using WarehouseHRI;
using WarehouseHRI.V4;
using WarehouseRobot.GroundTruth;

namespace WarehouseRobot.Scenario
{
    /// <summary>session.json of an experiment session (experiments_ab.md): the Task 2 fields plus what export_csv_v4.py reads
    /// (experiment, set, lie_probability) and the placement record. Task 2 sessions keep writing SessionV4 unchanged.</summary>
    [Serializable]
    class SessionV4AB : SessionV4
    {
        public string experiment, set, map, layout, lie_rule, answer_rule, activation_rule;
        /// <summary>Smoke check only (experiments_ab.md section 3): the male|female looks that replaced the navigation looks; "" otherwise.</summary>
        public string navigation_looks_override = "";
        public float lie_probability;
        public List<string> placement = new List<string>();
        public List<string> workers_plan = new List<string>();
    }

    /// <summary>
    /// Experiments A and B (Avatar/Config/experiments_ab.md sections 3 and 4): TrialRunnerV4's experiment mode, selected by
    /// TrialPlayV4 -experiment A1..B4 (development; -experimentSide right|left for A2/B2), or a final of the new study with TrialPlayV4
    /// -finalSetting A1..B4 (experiments_ab.md section 7: final_v4.json, Avatar/Config/sessions/final_ab_&lt;setting&gt;.json, test looks and
    /// clips only, the seed and numbers of final_plan.json). Instead of the Task 2 commander that moves between stands, every asking node
    /// of the experiment's map has 2 (J1 in A3, A4, B3, B4: 3) workers placed by ExperimentPlanAB under the placement rules; whoever the
    /// robot asks answers (the active worker nearest the pan-tilt camera's axis), a liar (Set B, p = 0.2 per worker per run) always with
    /// the same wrong direction. Workers are active only near the robot (activation window, max_active_avatars). truth.jsonl gets
    /// gesture_truthful (and the extra field active) for every worker. The Task 2 path is unchanged when no experiment is given.
    /// </summary>
    public partial class TrialRunnerV4
    {
#if UNITY_EDITOR
        /// <summary>Editor session key: the experiment (TrialPlayV4 -experiment); "" = the Task 2 session.</summary>
        public const string ExperimentKey = "WarehouseRobot.TrialRunnerV4.Experiment";
        /// <summary>Editor session key: smoke check only (TrialPlayV4 -experimentLooks male|female); "" = the navigation looks of looks_ab.json.</summary>
        public const string ExperimentLooksKey = "WarehouseRobot.TrialRunnerV4.ExperimentLooks";
        /// <summary>Editor session key: development only (TrialPlayV4 -experimentSide right|left): the A2 / B2 turn side instead of
        /// experiments_ab_unity.json a2_sides; "" = a2_sides. A final takes its side from its final config.</summary>
        public const string ExperimentSideKey = "WarehouseRobot.TrialRunnerV4.ExperimentSide";
#endif
        const string ExperimentsAsset = "Assets/WarehouseRobot/Scenario/Config/experiments_ab_unity.json";
        string experimentName = "", expText = "", scenariosText = "", looksAbText = "", looksOverride = "";
        ExperimentsUnityConfig ecfg;
        ExperimentPlanAB eplan;
        ExperimentLooksFile elooks;
        readonly List<string> eGoals = new List<string>();
        readonly List<RunPlanAB> eRuns = new List<RunPlanAB>();
        readonly Dictionary<string, List<string>> eClips = new Dictionary<string, List<string>>();
        readonly List<string> eMales = new List<string>(), eFemales = new List<string>();
        readonly Dictionary<WorkerV4, PlannedWorker> eWorkers = new Dictionary<WorkerV4, PlannedWorker>();
        readonly List<GameObject> eRings = new List<GameObject>();
        RunPlanAB eRun;
        RoadmapV4 eMap;
        WorkerV4 eAsked;
        Transform eGoalMarker;
        string eSplit = "", eLimit = "", eSide = "";
        /// <summary>The session seed of the experiment: final_plan.json final_seed in a final, trials.json dev_seed otherwise.</summary>
        int eSeed;
        Material eTruthfulMat, eLiarMat;

        bool Experiment => experimentName.Length > 0;

        /// <summary>Setup, experiment mode: the configs, the plan of the experiment and its navigation looks and clips (development:
        /// the development split; a final: its final config's test looks and clips, checked by FinalGuardV4.ExperimentProblems).</summary>
        bool SetupExperiment(string mode, out string error)
        {
            error = null;
            if (!Final && mode != DataSplitsV4.Development) return Fail(out error, $"experiment {experimentName}: development mode only (trials mode '{mode}')");
            try
            {
                expText = File.ReadAllText(Path.Combine(Application.dataPath, "..", ExperimentsAsset));
                ecfg = ExperimentsUnityConfig.Parse(expText);
                scenariosText = File.ReadAllText(RepoFile(ecfg.scenarios_ab));
                looksAbText = File.ReadAllText(Path.Combine(Application.dataPath, "..", ecfg.looks));
                elooks = ExperimentLooks.Parse(looksAbText);
            }
            catch (Exception e) { return Fail(out error, $"cannot read {ExperimentsAsset}, scenarios_ab.json or looks_ab.json: {e.Message}"); }
            // the A2 / B2 side (experiments_ab.md section 7): a final's from its final config, in development -experimentSide; it
            // replaces experiments_ab_unity.json a2_sides for this session only (the file is not changed)
            eSide = Final ? fexp.a2_side ?? "" : "";
#if UNITY_EDITOR
            if (!Final) eSide = UnityEditor.SessionState.GetString(ExperimentSideKey, "");
#endif
            if (eSide.Length > 0)
            {
                if (Array.IndexOf(FinalExperimentV4.Sides, eSide) < 0) return Fail(out error, $"experiment {experimentName}: side '{eSide}' is neither right nor left");
                ecfg.a2_sides = new[] { eSide };
            }
            eplan = ExperimentPlanAB.Build(ecfg, experimentName, scenariosText, roadText,
                                           p => File.ReadAllText(Path.Combine(Application.dataPath, "..", p)), out error);
            if (eplan == null) return false;
            if (eSide.Length > 0 && eplan.MapName != FinalExperimentV4.Turn)
                return Fail(out error, $"experiment {experimentName}: a side (right / left) is for the turn map only; this experiment uses {eplan.MapName}");
            var le = ExperimentLooks.Validate(elooks, workerTemplate.looks);
            if (le.Count > 0) return Fail(out error, "looks_ab.json: " + string.Join("; ", le));
            if (Final)
            {
                var fp = FinalGuardV4.ExperimentProblems(fset, fexp, x => ExperimentPlanAB.MapOfExperiment(ecfg, scenariosText, x), splits, elooks, workerTemplate);
                if (fp.Count > 0) return Fail(out error, $"final {finalSetting} refused: " + string.Join("; ", fp));
            }

            // navigation looks and clips: development = the development split (data_splits.json decides; looks_ab.json's proposed_split
            // is never read here), a final = exactly its final config's test looks and clips
            if (!FinalGuardV4.ExperimentData(Final ? fset : null, fexp, mode, splits, elooks, workerTemplate,
                                             new[] { wcfg.commander_command, wcfg.forward_command }, eMales, eFemales, eClips, out error))
                return Fail(out error, $"experiment {experimentName}: {error}");
#if UNITY_EDITOR
            looksOverride = Final ? "" : UnityEditor.SessionState.GetString(ExperimentLooksKey, "");
#endif
            if (looksOverride.Length > 0)
            {
                // smoke check of the runner (experiments_ab.md section 3): two existing looks, still checked against the splits per run
                var two = looksOverride.Split('|');
                if (two.Length != 2 || ExperimentLooks.Find(workerTemplate, elooks.looks, two[0]) == null || ExperimentLooks.Find(workerTemplate, elooks.looks, two[1]) == null)
                    return Fail(out error, $"-experimentLooks '{looksOverride}': give male|female, two looks of worker_v4.json or looks_ab.json");
                eMales.Clear(); eMales.Add(two[0]);
                eFemales.Clear(); eFemales.Add(two[1]);
            }
            eSeed = Final ? fplan.FinalSeed : cfg.dev_seed;
            eGoals.Clear();
            eGoals.AddRange(eplan.Goals(eSeed, TrialTotal));
            return true;
        }

        /// <summary>After the ground-truth grid exists: every run planned (positions on free cells clear of colliders), each run's looks
        /// and clips checked against the splits, every goal reachable on the grid.</summary>
        bool PlanExperimentRuns(out string error)
        {
            error = null;
            eRuns.Clear();
            Func<Vector3, bool> free = p =>
            {
                var c = gt.Grid.CellOf(p.x, p.z);
                return gt.Grid.Free(c.x, c.y) && !Physics.CheckCapsule(p + Vector3.up * 0.35f, p + Vector3.up * 1.55f, 0.3f, ~0, QueryTriggerInteraction.Ignore);
            };
            for (int run = 1; run <= TrialTotal; run++)
            {
                var plan = eplan.PlanRun(eSeed, run, eGoals[run - 1], eMales, eFemales, free, out error);
                if (plan == null) return false;
                var map = eplan.RunMap(eSeed, run, out _);
                var looks = new List<string>();
                foreach (var w in plan.Workers) looks.Add(w.Look);
                var clips = new List<string>();
                foreach (var kv in eClips) clips.AddRange(kv.Value);
                string split = splits.GuardRun(looks, clips, Final, out error);       // a final: wholly test; development: never test
                if (split == null) { error = $"run {run}: {error}"; return false; }
                eSplit = split;
                var a = ExperimentPlanAB.Pos(map.Node(map.Start));
                var g = ExperimentPlanAB.Pos(map.Node(plan.Goal));
                foreach (var n in map.Nodes)
                {
                    var c = gt.Grid.CellOf(n.X, n.Z);
                    if (!gt.Grid.Free(c.x, c.y)) { error = $"run {run}: node {n.Name} of map {plan.MapName} is on a blocked cell of the ground-truth grid"; return false; }
                }
                if (!GroundTruthLayer.Plan(gt.Grid, a, g, out _, out _, out string planError)) { error = $"run {run}: ground-truth grid, A to {plan.Goal}: {planError}"; return false; }
                eRuns.Add(plan);
            }
            return true;
        }

        Vector3 GoalPosition(string goal, int run)
        {
            if (!Experiment) return nodes[goal].Position;
            var map = eplan.RunMap(eSeed, run, out _);
            var n = map.Node(ExperimentPlanAB.GoalOn(map, goal));
            return new Vector3(n.X, nodes[meta.start].Position.y, n.Z);
        }

        /// <summary>Robot to A; the run's workers spawned (once per run) at their planned places with their looks and lies; the stand rings drawn.</summary>
        bool ResetForExperimentTrial(int run, out string error)
        {
            error = null;
            var start = nodes[meta.start];
            Teleport(new Vector3(start.Position.x, robot.transform.position.y, start.Position.z), start.transform.eulerAngles.y);
            bridge.ReachedEndPoint = false;
            if (spawnedRun == run) return true;
            DestroyWorkers();
            eRun = eRuns[run - 1];
            eMap = eplan.RunMap(eSeed, run, out _);
            eAsked = null;
            eLimit = "";
            eWorkers.Clear();
            float y = start.workerStand != null ? start.workerStand.position.y : start.Position.y;
            var extra = new List<LookEntry>(elooks.looks);
            if (eTruthfulMat == null)
            {
                eTruthfulMat = GroundTruthLayer.NewMaterial(new Color(ecfg.truthful_rgb[0], ecfg.truthful_rgb[1], ecfg.truthful_rgb[2], 0.9f));
                eLiarMat = GroundTruthLayer.NewMaterial(new Color(ecfg.liar_rgb[0], ecfg.liar_rgb[1], ecfg.liar_rgb[2], 0.9f));
            }
            foreach (var pw in eRun.Workers)
            {
                var p = new Vector3(pw.Position.x, y, pw.Position.z);
                var node = ExperimentPlanAB.Pos(eMap.Node(pw.Node));
                var face = new Vector3(node.x - p.x, 0f, node.z - p.z);
                var w = Spawn($"WorkerV4_{pw.Node}_{pw.Slot + 1}", pw.Look, pw.Id, p, Quaternion.LookRotation(face.sqrMagnitude > 1e-6f ? face : Vector3.forward, Vector3.up),
                              run, out error, x => { x.extraLooks = extra; x.ReportTruthful = true; x.ReportActive = true; });
                if (w == null) return false;
                eWorkers[w] = pw;
                eRings.Add(Ring(p, pw.Liar ? eLiarMat : eTruthfulMat, $"Stand {pw.Id} {pw.Node} {(pw.Liar ? "LIAR shows " + pw.ShownCommand : "truthful")}"));
            }
            if (eGoalMarker == null) eGoalMarker = new GameObject("ExperimentGoal").transform;
            eGoalMarker.position = GoalPosition(eRun.Goal, run);
            spawnedRun = run;
            return true;
        }

        GameObject Ring(Vector3 p, Material mat, string name)
        {
            var go = GameObject.CreatePrimitive(PrimitiveType.Cylinder);
            go.name = name;
            Destroy(go.GetComponent<Collider>());
            go.layer = gt.Layer;
            go.transform.SetParent(workersRoot, false);
            go.transform.position = new Vector3(p.x, gt.FloorY + 0.015f, p.z);
            go.transform.localScale = new Vector3(0.9f, 0.005f, 0.9f);
            GroundTruthLayer.Unshadowed(go.GetComponent<Renderer>(), mat);
            return go;
        }

        void DestroyExperimentExtras()
        {
            foreach (var r in eRings) if (r != null) Destroy(r);
            eRings.Clear();
            eWorkers.Clear();
            eAsked = null;
        }

        /// <summary>Every frame of an experiment trial: the activation window, then who answers a new ask and what it shows.</summary>
        void UpdateExperiment()
        {
            if (!trialActive || eRun == null) return;
            var rp = robot.transform.position;
            int active = 0;
            foreach (var kv in eWorkers)
            {
                var w = kv.Key;
                if (w == null) continue;
                bool want = ExperimentPlanAB.Active(rp, w.transform.position, ecfg.activation_radius_m) || (w.gameObject.activeSelf && w.Busy);
                if (w.gameObject.activeSelf != want) w.gameObject.SetActive(want);
                if (want) active++;
            }
            if (active > ecfg.max_active_avatars && eLimit.Length == 0)
            {
                eLimit = $"{active} workers active at once at ({rp.x.ToString("0.0", Inv)}, {rp.z.ToString("0.0", Inv)}), more than max_active_avatars {ecfg.max_active_avatars}";
                Debug.LogError("[TrialRunnerV4] " + eLimit);
            }
            question.Update(bridge.ScreenText);
            bool waiting = waitText.Length > 0 && bridge.ScreenText == waitText;
            if (!question.Visible && !waiting)
            {
                foreach (var w in eWorkers.Keys)
                    if (w != null && w.gameObject.activeSelf) { w.SetQuestionVisible(false); w.CancelPending(); }
                if (eAsked != null && !eAsked.Busy) { eAsked.IsCommander = false; eAsked = null; }
                return;
            }
            if (eAsked != null) eAsked.SetQuestionVisible(true);
            if (servedAsk == question.Ask) return;
            if (eAsked != null && eAsked.Busy) return;                // the last answer has not returned yet: this ask waits for it
            var cam = robot.PanTilt != null ? robot.PanTilt.transform : robot.transform;
            var heads = new List<KeyValuePair<int, Vector3>>();
            var byId = new Dictionary<int, WorkerV4>();
            foreach (var kv in eWorkers)
                if (kv.Key != null && kv.Key.gameObject.activeSelf && kv.Key.Ready)
                {
                    heads.Add(new KeyValuePair<int, Vector3>(kv.Value.Id, kv.Key.transform.position + Vector3.up * 1.6f));
                    byId[kv.Value.Id] = kv.Key;
                }
            servedAsk = question.Ask;
            int id = ExperimentPlanAB.ChooseAsked(cam.position, cam.forward, heads, ecfg.ask_max_distance_m);
            if (id < 0)
            {
                Debug.LogWarning($"[TrialRunnerV4] ask {question.Ask}: no active worker within {ecfg.ask_max_distance_m.ToString("0.0", Inv)} m of the robot answers");
                return;
            }
            if (eAsked != null && eAsked != byId[id]) eAsked.IsCommander = false;
            eAsked = byId[id];
            eAsked.IsCommander = true;
            eAsked.SetQuestionVisible(true);
            var pw = eWorkers[eAsked];
            string gesture = pw.ShownCommand == ExperimentPlanAB.Forward && !string.IsNullOrEmpty(wcfg.forward_command) ? wcfg.forward_command : wcfg.commander_command;
            var dir = ExperimentPlanAB.Direction(eMap, pw.Node, pw.ShownCommand);
            var req = new GestureRequest { Command = gesture, AllowedClips = eClips[gesture], PointDirection = dir, Lie = pw.Liar };
            if (!eAsked.Request(req, out string err))
            {
                Debug.LogError($"[TrialRunnerV4] ask {question.Ask}: worker {pw.Id} cannot show {gesture} ({pw.ShownCommand}): {err}");
                return;
            }
            eAskRecords.Add(new ShownRecord { junction = pw.Node, shown = pw.ShownCommand + (pw.Liar ? " (lie)" : ""), t_placed = Time.time });
            Debug.Log($"[TrialRunnerV4] ask {question.Ask} at {pw.Node} (\"{bridge.ScreenText}\"): worker {pw.Id} {pw.Look} shows {gesture} {pw.ShownCommand}" +
                      $"{(pw.Liar ? $" (LIE; true {pw.TrueCommand})" : "")} with {eAsked.Current.clip}, {eAsked.Current.arm} arm");
        }

        readonly List<ShownRecord> eAskRecords = new List<ShownRecord>();

        /// <summary>RunVisualsV4 in experiment mode: the node of the current ask, its true command and the answering worker's lie.</summary>
        string ExperimentAskNode() => eAsked != null && eWorkers.TryGetValue(eAsked, out var pw) ? pw.Node : "";
        string ExperimentTrueCommand() => eAsked != null && eWorkers.TryGetValue(eAsked, out var pw) ? pw.TrueCommand : "NONE";
        int ExperimentLie() => eAsked != null && eWorkers.TryGetValue(eAsked, out var pw) ? (pw.Liar ? 1 : 0) : -1;
        string ExperimentShown() => eAsked != null && eWorkers.TryGetValue(eAsked, out var pw) ? pw.ShownCommand : "-";

        SessionV4 NewSessionRecord()
        {
            if (!Experiment) return new SessionV4();
            var s = new SessionV4AB
            {
                experiment = experimentName, set = eplan.Def.set, lie_probability = eplan.LieProbability, map = eplan.MapName, layout = eplan.LayoutKind,
                lie_rule = "per worker per run (seeded by session seed, run, worker id), consistent when asked again; a wrong valid branch, else (no other branch) " +
                           "another of LEFT/FORWARD/RIGHT/BACK (AUDIT.md 16.2 decision 2); experiments_ab.md section 4",
                answer_rule = $"the active worker within {ecfg.ask_max_distance_m.ToString("0.0", Inv)} m nearest the pan-tilt camera axis answers a new ask",
                activation_rule = $"active within {ecfg.activation_radius_m.ToString("0.0", Inv)} m of the robot or while gesturing; max {ecfg.max_active_avatars}",
                navigation_looks_override = looksOverride,
            };
            foreach (var r in eRuns)
            {
                var parts = new List<string>();
                foreach (var kv in r.Redraws) parts.Add($"{kv.Key} {kv.Value}");
                s.placement.Add($"run {r.Run}: map {r.MapName}, goal {r.Goal}, redraws {string.Join(", ", parts)}, max active {r.MaxActive}");
                foreach (var w in r.Workers)
                    s.workers_plan.Add($"run {r.Run} worker {w.Id}: {w.Node} slot {w.Slot + 1}, {w.Look}, ({w.Position.x.ToString("0.00", Inv)}, {w.Position.z.ToString("0.00", Inv)}), " +
                                       (w.Liar ? $"LIAR shows {w.ShownCommand}{(w.ShownIsBranch ? "" : " (no such branch)")} (true {w.TrueCommand})" : $"truthful {w.TrueCommand}"));
            }
            return s;
        }

        void WriteExperimentConfigs(string used)
        {
            if (!Experiment) return;
            GroundTruthFiles.WriteNew(Path.Combine(used, "experiments_ab_unity.json"), expText);
            GroundTruthFiles.WriteNew(Path.Combine(used, "scenarios_ab.json"), scenariosText);
            GroundTruthFiles.WriteNew(Path.Combine(used, "looks_ab.json"), looksAbText);
            if (Final) GroundTruthFiles.WriteNew(Path.Combine(used, Path.GetFileName(fset.experiment_config)), fexpText);
        }
    }
}
