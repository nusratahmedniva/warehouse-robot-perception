using System;
using System.Collections.Generic;
using System.IO;
using UnityEngine;
using WarehouseAvatar;
using WarehouseHRI.V4;
using WarehouseRobot.GroundTruth;

namespace WarehouseRobot.Scenario
{
    /// <summary>session.json of an S1 session: the experiment session's fields plus what marks it as the post-freeze supplementary experiment
    /// (Anisha's AUDIT.md 16.36 and 16.37, Unity addendum 14 of experiments_ab.md): supplementary "S1", the amendment, the character, the setting, the
    /// plan runs (run_001.. are these plan runs of the final plan, seed 2), the part of the cell and the hashes of the S1 configs.</summary>
    [Serializable]
    class SessionV4S1 : SessionV4AB
    {
        public string supplementary = "", amendment = "", s1_character = "", s1_setting = "", s1_cell_marker = "";
        public List<int> plan_runs = new List<int>();
        /// <summary>1 = the cell's first session, 2 = its one resume (the interruption rule of AUDIT.md 16.30.1).</summary>
        public int s1_part = 1;
        public List<string> s1_config_hashes = new List<string>();
        public string s1_note = "post-freeze, exploratory, never pooled with the finals; no frozen match is required and no FINAL_* marker is written (AUDIT.md 16.36, 16.37)";
    }

    /// <summary>
    /// Post-freeze supplementary experiment S1 (Anisha's AUDIT.md 16.36 and 16.37; Unity addendum 14 of Avatar/Config/experiments_ab.md): the experiment
    /// setting A1, A3 or B3 of the finals (same seed 2, goals, worker positions, lie schedule and test gesture clips, its plan runs as run_001..005) with ALL
    /// workers wearing ONE of four characters. Started by TrialPlayV4 -s1Character NAME -s1Setting A1|A3|B3 (-s1Resume once after an infrastructure interruption).
    /// A development-type session (mode development, no frozen match, no final marker) that reads the finals' configs for its setting; its own run-once
    /// markers (S1Guard) live in its session folder, whose name starts with s1_.
    /// </summary>
    public partial class TrialRunnerV4
    {
#if UNITY_EDITOR
        /// <summary>Editor session keys (TrialPlayV4 -s1Character, -s1Setting, -s1Resume).</summary>
        public const string S1CharacterKey = "WarehouseRobot.TrialRunnerV4.S1Character";
        public const string S1SettingKey = "WarehouseRobot.TrialRunnerV4.S1Setting";
        public const string S1ResumeKey = "WarehouseRobot.TrialRunnerV4.S1Resume";
#endif
        string s1Character = "", s1Setting = "", s1CfgText = "", s1ResumeOf = "";
        bool s1Resume;
        S1Config s1Cfg;
        int[] s1PlanRuns = new int[0];
        int s1StartRun = 1, s1Part = 1;

        /// <summary>The cell's look source(s), resolved once in <see cref="UseS1Character"/>.</summary>
        readonly List<LookSource> s1Sources = new List<LookSource>();

        /// <summary>S1: add the cell's look source to THIS worker instance (never to the prefab asset).</summary>
        void AddS1Sources(WorkerV4 w) { if (S1 && w != null) w.lookSources = S1Sources.Merge(w.lookSources, s1Sources); }

        bool S1 => s1Character.Length > 0 || s1Setting.Length > 0;

        /// <summary>The plan run of the final plan that session run <paramref name="run"/> drives (S1: the setting's declared list; otherwise the run itself).</summary>
        int PlanRunOf(int run) => S1 && run >= 1 && run <= s1PlanRuns.Length ? s1PlanRuns[run - 1] : run;

        /// <summary>Every refusal of an S1 session, then the cell's configs read: s1_supplementary.json, the finals' final_v4.json, final_plan.json and the
        /// setting's final experiment config; the timeout (480 s, the final plan's), the seed (the final plan's 2) and the success radius of the finals.</summary>
        bool SetupS1(out string error)
        {
            error = null;
            if (s1Character.Length == 0 || s1Setting.Length == 0) return Fail(out error, "S1 needs both -s1Character and -s1Setting");
#if UNITY_EDITOR
            string other = finalSetting + experimentName
                + UnityEditor.SessionState.GetString(WorkersOverrideKey, "") + UnityEditor.SessionState.GetString(ExperimentLooksKey, "")
                + UnityEditor.SessionState.GetString(ExperimentSideKey, "") + UnityEditor.SessionState.GetString(ExperimentGoalsKey, "")
                + UnityEditor.SessionState.GetString(StartRunKey, "") + UnityEditor.SessionState.GetString(ResumeMarkerKey, "")
                + UnityEditor.SessionState.GetString(BridgeFolderKey, "");
            if (other.Length > 0)
                return Fail(out error, "S1 refused: -finalSetting, -experiment, -workersConfig, -experimentLooks, -experimentSide, -experimentGoals, -startRun, -resumeMarker and -bridgeFolder " +
                                       "are not S1 options (S1 is a session of its own; an interruption is resumed with -s1Resume)");
#endif
            try
            {
                s1CfgText = File.ReadAllText(Path.Combine(Application.dataPath, "..", S1Config.AssetPath));
                s1Cfg = S1Config.Parse(s1CfgText);
                finalCfgText = File.ReadAllText(Path.Combine(Application.dataPath, "..", FinalConfigAsset));
                fcfg = FinalConfigV4.Parse(finalCfgText);
                finalPlanText = File.ReadAllText(RepoFile(fcfg.final_plan));
                fplan = FinalPlanV4.Parse(finalPlanText);
            }
            catch (Exception e) { return Fail(out error, $"S1: cannot read s1_supplementary.json, final_v4.json or final_plan.json: {e.Message}"); }
            string outputRoot = Path.GetFullPath(Path.Combine(repoRoot, "robot_vision", cfg.output_root));
            var existing = S1Guard.Scan(outputRoot, s1Cfg);
            var problems = S1Guard.Problems(s1Cfg, s1Character, s1Setting, s1Resume, existing, out s1StartRun, out s1ResumeOf, out bool markInvalid);
            if (markInvalid) WriteS1Invalid(outputRoot, existing, string.Join("; ", problems));
            if (problems.Count > 0) return Fail(out error, "S1 refused: " + string.Join("; ", problems));
            s1Part = s1Resume ? 2 : 1;
            s1PlanRuns = (int[])S1Config.DeclaredPlanRuns[s1Setting].Clone();
            fset = fcfg.Setting(s1Setting);
            if (fset == null || !fset.IsExperiment) return Fail(out error, $"S1: '{s1Setting}' is not an experiment setting of final_v4.json");
            try
            {
                fexpText = File.ReadAllText(Path.Combine(Application.dataPath, "..", fset.experiment_config));
                fexp = FinalExperimentV4.Parse(fexpText);
            }
            catch (Exception e) { return Fail(out error, $"S1: cannot read {fset.experiment_config}: {e.Message}"); }
            experimentName = fexp.experiment ?? "";
            if (experimentName != s1Setting) return Fail(out error, $"S1: {fset.experiment_config} names experiment '{experimentName}', S1 setting is '{s1Setting}'");
            if (s1Setting == "B3" && fexp.lie_detection != "on") return Fail(out error, "S1 B3 runs with lie handling ON (the final B3 setting): its config has lie_detection '" + fexp.lie_detection + "'");
            if (fplan.TimeoutS != s1Cfg.timeout_s) return Fail(out error, $"S1: the timeout is {s1Cfg.timeout_s} s, final_plan.json says {fplan.TimeoutS} s (S1 uses the finals' numbers)");
            if (fplan.FinalSeed != 2) return Fail(out error, $"S1 runs seed 2, final_plan.json final_seed is {fplan.FinalSeed}");
            int max = 0;
            foreach (var p in s1PlanRuns) max = Math.Max(max, p);
            if (max > fplan.RunsPerSetting) return Fail(out error, $"S1: plan run {max} is beyond the final plan's {fplan.RunsPerSetting} runs");
            cfg.timeout_s = s1Cfg.timeout_s;
            cfg.success_radius_m = fplan.SuccessRadiusM;
            Debug.Log($"[TrialRunnerV4] S1 cell {s1Character}/{s1Setting}: plan runs [{string.Join(", ", s1PlanRuns)}] of the final plan (seed {fplan.FinalSeed}), part {s1Part}" +
                      (s1Part == 2 ? $", resumed from run {s1StartRun} of {s1ResumeOf}" : "") + $", timeout {cfg.timeout_s.ToString("0", Inv)} s, no frozen match, no FINAL marker");
            return true;
        }

        /// <summary>The goals of S1's runs: the final plan's goal of each plan run (the final plan's own 20-run sequence, seed 2).</summary>
        List<string> S1Goals()
        {
            var full = eplan.Goals(eSeed, fplan.RunsPerSetting);
            var goals = new List<string>();
            foreach (var p in s1PlanRuns) goals.Add(full[p - 1]);
            return goals;
        }

        /// <summary>S1: every worker of the cell wears the cell's one character; the test clips of the setting's final config stay.</summary>
        bool UseS1Character(out string error)
        {
            error = null;
            if (ExperimentLooks.Find(workerTemplate, elooks.looks, s1Character) == null)
                return Fail(out error, $"S1: character '{s1Character}' is neither a look of worker_v4.json nor of looks_ab.json");
            // the look's prefab (and material override) is resolved here, as LookCheckPlayMenu.AddExperimentLooks does for the avatar experiment: WorkerV4.prefab lists Sunbox only
            var entry = ExperimentLooks.Find(workerTemplate, elooks.looks, s1Character);
            s1Sources.Clear();
            if (entry.kind == LookEntry.KindPrefab)
            {
#if UNITY_EDITOR
                var prefab = UnityEditor.AssetDatabase.LoadAssetAtPath<GameObject>(entry.asset);
                if (prefab == null)
                    return Fail(out error, $"S1: the prefab of {s1Character} ({entry.asset}) cannot be loaded: it is third-party and git-ignored. Put the file at unity/Robotics-Warehouse/WarehouseProjectURP/{entry.asset}, " +
                                           "open the project in the Unity Editor once so that it is imported (its .meta file is in git), then start the cell again. Nothing is rebuilt: the worker template is not changed");
                var mat = string.IsNullOrEmpty(entry.material_override) ? null : UnityEditor.AssetDatabase.LoadAssetAtPath<Material>(entry.material_override);
                if (!string.IsNullOrEmpty(entry.material_override) && mat == null) return Fail(out error, $"S1: the material override {entry.material_override} of {s1Character} cannot be loaded");
                s1Sources.Add(new LookSource { asset = entry.asset, prefab = prefab, materialOverride = mat });
#endif
            }
            eMales.Clear(); eMales.Add(s1Character);
            eFemales.Clear(); eFemales.Add(s1Character);
            return true;
        }

        SessionV4AB CopyToS1Record(SessionV4AB ab) => new SessionV4S1
        {
            experiment = ab.experiment, set = ab.set, map = ab.map, layout = ab.layout, lie_rule = ab.lie_rule, answer_rule = ab.answer_rule,
            activation_rule = ab.activation_rule, navigation_looks_override = ab.navigation_looks_override, goals_override = ab.goals_override,
            clearance_rule = ab.clearance_rule, lie_probability = ab.lie_probability,
        };

        void FillS1Session(SessionV4 session)
        {
            var s = (SessionV4S1)session;
            s.supplementary = s1Cfg.supplementary; s.amendment = s1Cfg.amendment; s.s1_character = s1Character; s.s1_setting = s1Setting;
            s.plan_runs = new List<int>(s1PlanRuns); s.s1_part = s1Part; s.s1_cell_marker = s1Cfg.marker_started;
            s.s1_config_hashes.Add("s1_supplementary.json " + Sha256(s1CfgText.Replace("\r\n", "\n")));
            s.s1_config_hashes.Add("final_v4.json " + Sha256(finalCfgText.Replace("\r\n", "\n")));
            s.s1_config_hashes.Add("final_plan.json " + Sha256(finalPlanText.Replace("\r\n", "\n")));
            s.s1_config_hashes.Add(Path.GetFileName(fset.experiment_config) + " " + Sha256(fexpText.Replace("\r\n", "\n")));
        }

        void WriteS1Configs(string used)
        {
            GroundTruthFiles.WriteNew(Path.Combine(used, "s1_supplementary.json"), s1CfgText);
            GroundTruthFiles.WriteNew(Path.Combine(used, "final_v4.json"), finalCfgText);
            GroundTruthFiles.WriteNew(Path.Combine(used, "final_plan.json"), finalPlanText);
        }

        /// <summary>S1 (addendum 14, after addendum 12): the cell's shader warm-up record into shader_warm_up.jsonl of the session folder (as the look checks write it; also after a
        /// failed warm-up) and the check that the cell's one look was drawn and compiled; a problem becomes warmUpError, so no run starts.</summary>
        void WriteS1Warm()
        {
            GroundTruthFiles.WriteNew(Path.Combine(SessionFolder, ShaderWarmUp.RecordFile), S1Guard.WarmUpJsonl(sessionWarmUps));
            if (warmUpError != null) return;
            var problems = S1Guard.WarmUpProblems(sessionWarmUps, s1Character);
            if (problems.Count > 0) warmUpError = string.Join("; ", problems);
        }

        void WriteS1Started()
        {
            ReadGit(out var commit, out _);
            GroundTruthFiles.WriteNew(Path.Combine(SessionFolder, s1Cfg.marker_started),
                S1Guard.StartedJson(s1Cfg, s1Character, s1Setting, s1PlanRuns, s1Part, s1Part == 2 ? s1StartRun : 0, s1ResumeOf, commit,
                                    Path.GetFileName(SessionFolder), DateTime.Now.ToString("s", Inv)));
        }

        void WriteS1Done()
        {
            ReadGit(out var commit, out _);
            GroundTruthFiles.WriteNew(Path.Combine(SessionFolder, s1Cfg.marker_done),
                S1Guard.DoneJson(s1Cfg, s1Character, s1Setting, TrialTotal - startRun + 1, Successes, commit, Path.GetFileName(SessionFolder), DateTime.Now.ToString("s", Inv)));
        }

        /// <summary>A third start of a cell whose second part has no end: the cell is INVALID (a second interruption), reported, never rerun.</summary>
        void WriteS1Invalid(string outputRoot, List<S1CellPart> existing, string reason)
        {
            S1CellPart last = null;
            foreach (var p in existing) if (p.character == s1Character && p.setting == s1Setting && (last == null || p.part > last.part)) last = p;
            if (last == null) return;
            string file = Path.Combine(outputRoot, last.folder, s1Cfg.marker_invalid);
            if (File.Exists(file)) return;
            GroundTruthFiles.WriteNew(file, S1Guard.InvalidJson(s1Cfg, s1Character, s1Setting, reason, DateTime.Now.ToString("s", Inv)));
        }
    }
}
