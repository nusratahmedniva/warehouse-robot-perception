using System;
using System.Collections.Generic;
using System.IO;
using System.Linq;
using NUnit.Framework;
using UnityEngine;
using WarehouseHRI.V4;

namespace WarehouseAvatar.Tests
{
    /// <summary>
    /// The post-freeze supplementary experiment S1 (Anisha's AUDIT.md 16.36 and 16.37; Unity addendum 14 of Avatar/Config/experiments_ab.md, 2026-11-25):
    /// the declared design (four characters, settings A1 / A3 / B3, plan runs, timeout), the GuardRun exception (allowed only in an S1 session for A1, A3 and
    /// B3, refused in every trial, final and development mode), the finals' plan reproduced with the cell's one character, and the run-once guard with its
    /// interruption rule. Nothing is run.
    /// </summary>
    public class S1SupplementaryTests
    {
        static string ProjectDir => Path.GetDirectoryName(Application.dataPath);
        static string RepoRoot => Path.GetFullPath(Path.Combine(ProjectDir, "../../.."));
        const string FinalAsset = "Assets/WarehouseRobot/Avatar/Config/final_v4.json";
        const string ExperimentsAsset = "Assets/WarehouseRobot/Scenario/Config/experiments_ab_unity.json";
        static readonly string[] Characters = { "mixamo_worker", "anime_f_01", "anime_f_02_outfit_short", "cartoon_boxo_01" };
        static readonly string[] Settings = { "A1", "A3", "B3" };
        static readonly string[] TestClips = { "point_mixamo_02", "proceed_ik_03" };

        static string Project(string asset) => File.ReadAllText(Path.Combine(ProjectDir, asset));
        static string Repo(string path) => File.ReadAllText(Path.Combine(RepoRoot, path));
        static S1Config Cfg() => S1Config.Parse(Project(S1Config.AssetPath));
        static FinalConfigV4 Final() => FinalConfigV4.Parse(Project(FinalAsset));
        static FinalPlanV4 FinalPlan() => FinalPlanV4.Parse(Repo("robot_vision/configs/v4/final_plan.json"));
        static FinalExperimentV4 Exp(string setting) => FinalExperimentV4.Parse(Project(Final().Setting(setting).experiment_config));
        static ExperimentsUnityConfig Ecfg() => ExperimentsUnityConfig.Parse(Project(ExperimentsAsset));
        static DataSplitsV4 Splits() => DataSplitsV4.Parse(Repo("robot_vision/configs/v4/data_splits.json"), Project(ExperimentLooks.AssetPath));
        static ExperimentPlanAB Plan(string experiment, out string error)
        {
            var cfg = Ecfg();
            return ExperimentPlanAB.Build(cfg, experiment, Repo(cfg.scenarios_ab), Repo(cfg.roadmap_v4), Project, out error);
        }

        // ---------------------------------------------------------------- the declared design

        [Test]
        public void ShippedConfig_IsValid_AndIsTheDeclaredDesign()
        {
            var c = Cfg();
            CollectionAssert.IsEmpty(c.Validate());
            CollectionAssert.AreEqual(Characters, c.characters);
            CollectionAssert.AreEqual(Settings, c.settings.Select(s => s.name).ToArray());
            CollectionAssert.AreEqual(new[] { 1, 2, 3, 4, 5 }, c.Setting("A1").plan_runs);
            CollectionAssert.AreEqual(new[] { 1, 2, 3, 4, 5 }, c.Setting("A3").plan_runs);
            CollectionAssert.AreEqual(new[] { 5, 7, 8, 10, 11 }, c.Setting("B3").plan_runs);
            Assert.AreEqual(5, c.runs_per_cell);
            Assert.AreEqual(12, c.cell_order.Length, "4 characters x 3 settings");
            Assert.AreEqual(60, c.cell_order.Length * c.runs_per_cell, "60 runs");
            Assert.AreEqual("S1", c.supplementary);
            StringAssert.StartsWith("s1_", c.folder_prefix);
            StringAssert.Contains("AUDIT 16.36", c.amendment);
            foreach (var m in new[] { c.marker_started, c.marker_done, c.marker_invalid }) StringAssert.DoesNotStartWith("FINAL", m.ToUpperInvariant(), "an S1 marker is never a final marker");
        }

        [Test]
        public void ShippedConfig_UsesTheFinalPlansNumbers_AndTheFinalSettingsOfThatName()
        {
            var plan = FinalPlan();
            Assert.AreEqual(2, plan.FinalSeed, "S1 runs the final seed");
            Assert.AreEqual(Cfg().timeout_s, plan.TimeoutS, "the S1 timeout (480 s) is the final plan's");
            Assert.GreaterOrEqual(plan.RunsPerSetting, 11, "the highest plan run (B3: 11) exists in the final plan");
            foreach (var name in Settings)
            {
                var s = Final().Setting(name);
                Assert.IsNotNull(s, name);
                Assert.IsTrue(s.IsExperiment, name);
                Assert.AreEqual(name, Exp(name).experiment, name);
                Assert.AreEqual("Assets/WarehouseRobot/Avatar/Config/trial_workers_v4.json", s.workers_config, name);
            }
            Assert.AreEqual("on", Exp("B3").lie_detection, "S1 B3 runs the final B3 setting: lie handling on");
            Assert.AreEqual("configs/v4/experiments/control_lie_on.json", Exp("B3").python_control);
        }

        [Test]
        public void Validate_RefusesEveryDriftFromTheDeclaredDesign()
        {
            S1Config Fresh() => S1Config.Parse(JsonUtility.ToJson(Cfg()));
            var c = Fresh(); c.characters = c.characters.Take(3).ToArray(); Assert.IsNotEmpty(c.Validate());
            c = Fresh(); c.characters[1] = "sunbox_m_shirt_plaid"; Assert.IsNotEmpty(c.Validate(), "a Sunbox look is not an S1 character");
            c = Fresh(); c.Setting("B3").plan_runs = new[] { 1, 2, 3, 4, 5 }; StringAssert.Contains("declared", string.Join(";", c.Validate()));
            c = Fresh(); c.timeout_s = 240; Assert.IsNotEmpty(c.Validate());
            c = Fresh(); c.runs_per_cell = 10; Assert.IsNotEmpty(c.Validate());
            c = Fresh(); c.supplementary = "S2"; Assert.IsNotEmpty(c.Validate());
            c = Fresh(); c.marker_done = "FINAL_DONE.json"; Assert.IsNotEmpty(c.Validate(), "never a final marker name");
            c = Fresh(); c.marker_done = c.marker_started; Assert.IsNotEmpty(c.Validate());
            c = Fresh(); c.cell_order[1] = c.cell_order[0]; StringAssert.Contains("twice", string.Join(";", c.Validate()));
            c = Fresh(); c.folder_prefix = "trials_final_"; Assert.IsNotEmpty(c.Validate());
        }

        // ---------------------------------------------------------------- the GuardRun exception

        [Test]
        public void GuardRun_S1_AllowsTheFourLooks_OnlyForA1A3B3()
        {
            var splits = Splits();
            foreach (var look in Characters)
                foreach (var setting in Settings)
                {
                    Assert.AreEqual("supplementary_S1", splits.GuardRun(new[] { look, look }, TestClips, false, "S1", setting, out string error), $"{look} {setting}: {error}");
                    Assert.IsNull(error);
                }
        }

        [Test]
        public void GuardRun_S1_RefusesEverythingElse()
        {
            var splits = Splits();
            string error;
            foreach (var setting in new[] { "A2_right", "A4", "B1", "B3_off", "zoom_on", "" })
            {
                Assert.IsNull(splits.GuardRun(new[] { "anime_f_01" }, TestClips, false, "S1", setting, out error), setting);
                StringAssert.Contains("A1, A3 and B3 only", error);
            }
            Assert.IsNull(splits.GuardRun(new[] { "anime_f_01", "cartoon_boxo_01" }, TestClips, false, "S1", "A1", out error));
            StringAssert.Contains("exactly ONE look", error);
            Assert.IsNull(splits.GuardRun(new[] { "sunbox_m_shirt_plaid" }, TestClips, false, "S1", "A1", out error));
            StringAssert.Contains("uses only", error);
            Assert.IsNull(splits.GuardRun(new[] { "anime_f_01", "sunbox_m_shirt_plaid" }, TestClips, false, "S1", "A1", out error), "a Sunbox look next to an S1 look");
            Assert.IsNull(splits.GuardRun(new[] { "anime_f_01" }, TestClips, true, "S1", "A1", out error));
            StringAssert.Contains("not a final", error);
            Assert.IsNull(splits.GuardRun(new[] { "anime_f_01" }, TestClips, false, "S2", "A1", out error));
            StringAssert.Contains("unknown supplementary", error);
            Assert.IsNull(splits.GuardRun(new string[0], TestClips, false, "S1", "A1", out error));
            Assert.IsNull(splits.GuardRun(new[] { "anime_f_01" }, new string[0], false, "S1", "A1", out error));
            StringAssert.Contains("no gesture clip", error);
            Assert.IsNull(splits.GuardRun(new[] { "anime_f_01" }, new[] { "point_mixamo_02", "" }, false, "S1", "A1", out error));
            StringAssert.Contains("no animation clip name", error);
            Assert.IsNull(splits.GuardRun(new[] { "anime_f_01" }, new[] { "point_mixamo_02", "not_a_clip" }, false, "S1", "A1", out error));
            StringAssert.Contains("not listed", error);
            string dev = splits.Clips.First(kv => kv.Value == "development").Key;
            Assert.IsNull(splits.GuardRun(new[] { "anime_f_01" }, new[] { "point_mixamo_02", dev }, false, "S1", "A1", out error), "clips of two roles");
            StringAssert.Contains("mix roles", error);
        }

        [Test]
        public void GuardRun_WithoutS1_StillRefusesTheFourLooks_InTrialFinalAndDevelopmentModes()
        {
            var splits = Splits();
            foreach (var look in Characters)
            {
                Assert.IsTrue(splits.AvatarExperimentLooks.Contains(look), look);
                // a development session (final evaluation false) and a final (true), with test clips, development clips, and no clips
                foreach (bool final in new[] { false, true })
                    foreach (var clips in new[] { TestClips, splits.Clips.Where(kv => kv.Value == "development").Select(kv => kv.Key).Take(2).ToArray() })
                    {
                        Assert.IsNull(splits.GuardRun(new[] { look }, clips, final, out string error), $"{look} final {final}");
                        StringAssert.Contains("avatar-experiment look", error);
                    }
                // the overload with no supplementary is the same refusal
                Assert.IsNull(splits.GuardRun(new[] { look }, TestClips, false, null, "A1", out string e2), look);
                StringAssert.Contains("avatar-experiment look", e2);
                // a Sunbox final look is never changed by this
                Assert.IsNull(splits.GuardRun(new[] { look, "sunbox_m_shirt_plaid" }, TestClips, true, out string e3));
                StringAssert.Contains("avatar-experiment look", e3);
            }
            Assert.AreEqual("test", splits.GuardRun(new[] { "sunbox_m_shirt_plaid", "sunbox_f_shirt_plaid" }, TestClips, true, out string ok), ok, "the finals' own guard is unchanged");
        }

        [Test]
        public void S1Looks_AreExactlyThePythonGuardsSupplementaryLooks()
        {
            CollectionAssert.AreEqual(Characters, DataSplitsV4.S1Looks);
            CollectionAssert.AreEqual(Settings, DataSplitsV4.S1Settings);
            string py = Repo("robot_vision/data_splits_v4.py");
            foreach (var look in Characters) StringAssert.Contains($"\"{look}\"", py, "Python's SUPPLEMENTARY[\"S1\"]");
        }

        // ---------------------------------------------------------------- the finals' plan, with the cell's one character

        [Test]
        public void PlanRuns_AreTheFinalPlansRuns_GoalsPositionsAndLiesUnchanged_AllWorkersInTheCharacter()
        {
            const int seed = 2;
            var plan = FinalPlan();
            foreach (var setting in Settings)
            {
                var x = Exp(setting);
                var p = Plan(x.experiment, out string error);
                Assert.IsNotNull(p, setting + ": " + error);
                var goals = p.Goals(seed, plan.RunsPerSetting);
                foreach (var character in Characters)
                    foreach (int run in Cfg().Setting(setting).plan_runs)
                    {
                        var final = p.PlanRun(seed, run, goals[run - 1], x.male_looks, x.female_looks, null, out error);
                        var s1 = p.PlanRun(seed, run, goals[run - 1], new[] { character }, new[] { character }, null, out error);
                        Assert.IsNotNull(final, $"{setting} run {run}: {error}");
                        Assert.IsNotNull(s1, $"{setting} run {run} {character}: {error}");
                        Assert.AreEqual(final.Goal, s1.Goal);
                        Assert.AreEqual(final.MapName, s1.MapName);
                        Assert.AreEqual(final.Workers.Count, s1.Workers.Count);
                        for (int i = 0; i < final.Workers.Count; i++)
                        {
                            var a = final.Workers[i]; var b = s1.Workers[i];
                            string id = $"{setting} run {run} worker {a.Id} {character}";
                            Assert.AreEqual(character, b.Look, id);
                            Assert.AreEqual((a.Id, a.Node, a.Slot, a.Position, a.Liar, a.TrueCommand, a.ShownCommand, a.ShownIsBranch),
                                            (b.Id, b.Node, b.Slot, b.Position, b.Liar, b.TrueCommand, b.ShownCommand, b.ShownIsBranch), id + ": nothing but the look changes");
                        }
                    }
            }
        }

        [Test]
        public void LiesOff_InA1AndA3_LiesOn_InB3()
        {
            Assert.AreEqual(0f, Plan("A1", out _).LieProbability);
            Assert.AreEqual(0f, Plan("A3", out _).LieProbability);
            Assert.Greater(Plan("B3", out _).LieProbability, 0f);
            foreach (var setting in new[] { "A1", "A3" })
            {
                var p = Plan(setting, out _);
                var goals = p.Goals(2, 20);
                for (int run = 1; run <= 5; run++)
                    Assert.IsFalse(p.PlanRun(2, run, goals[run - 1], new[] { "anime_f_01" }, new[] { "anime_f_01" }, null, out _).Workers.Any(w => w.Liar), $"{setting} run {run}");
            }
        }

        [Test]
        public void B3PlanRuns_AreTheFiveLowestWithALiarAtAJunctionOnThePlannedRoute_ReadFromThePlanOnly()
        {
            const int seed = 2;
            var p = Plan("B3", out string error);
            Assert.IsNotNull(p, error);
            var x = Exp("B3");
            var goals = p.Goals(seed, FinalPlan().RunsPerSetting);
            var runsWithRouteLiar = new List<int>();
            for (int run = 1; run <= FinalPlan().RunsPerSetting; run++)
            {
                var r = p.PlanRun(seed, run, goals[run - 1], x.male_looks, x.female_looks, null, out error);
                var map = p.RunMap(seed, run, out _);
                bool liarOnRoute = r.Workers.Any(w => w.Liar && w.Node != map.Start && ExperimentPlanAB.TruthfulCommand(map, w.Node, r.Goal) != ExperimentPlanAB.Back);
                if (liarOnRoute) runsWithRouteLiar.Add(run);
            }
            CollectionAssert.AreEqual(new[] { 5, 7, 8, 10, 11 }, runsWithRouteLiar.Take(5).ToArray(), "AUDIT.md 16.37: 5, 7, 8, 10, 11");
            CollectionAssert.AreEqual(Cfg().Setting("B3").plan_runs, runsWithRouteLiar.Take(5).ToArray());
        }

        // ---------------------------------------------------------------- the run-once guard and the interruption rule

        static S1CellPart Part(string character, string setting, int part, bool done = false, bool invalid = false, params int[] outcomes) =>
            new S1CellPart { folder = $"s1_{character}_{setting}_{part}", character = character, setting = setting, part = part, done = done, invalid = invalid, outcomes = outcomes.ToList() };

        static List<string> Check(string character, string setting, bool resume, out int startRun, out string resumeOf, out bool markInvalid, params S1CellPart[] existing) =>
            S1Guard.Problems(Cfg(), character, setting, resume, existing, out startRun, out resumeOf, out markInvalid);

        [Test]
        public void Guard_FreshCell_Starts_AtRunOne()
        {
            CollectionAssert.IsEmpty(Check("anime_f_01", "A1", false, out int k, out string of, out bool inv, Part("anime_f_01", "A3", 1), Part("mixamo_worker", "A1", 1, done: true)));
            Assert.AreEqual(1, k); Assert.AreEqual("", of); Assert.IsFalse(inv);
        }

        [Test]
        public void Guard_RefusesUnknownCharacterAndSetting()
        {
            StringAssert.Contains("not one of", string.Join(";", Check("sunbox_m_shirt_plaid", "A1", false, out _, out _, out _)));
            StringAssert.Contains("not one of", string.Join(";", Check("anime_f_01", "A2_right", false, out _, out _, out _)));
            StringAssert.Contains("not one of", string.Join(";", Check("anime_f_01", "B3_off", false, out _, out _, out _)));
        }

        [Test]
        public void Guard_StartedCell_IsNotStartedAgain_ACrashedRunCounts()
        {
            var e = Check("anime_f_01", "A1", false, out _, out _, out _, Part("anime_f_01", "A1", 1, false, false, 1, 2));
            StringAssert.Contains("already started", string.Join(";", e));
            StringAssert.Contains("-s1Resume", string.Join(";", e));
        }

        [Test]
        public void Guard_FinishedCell_IsNeverRepeated_EvenWithResume()
        {
            foreach (bool resume in new[] { false, true })
                StringAssert.Contains("already run to the end", string.Join(";", Check("cartoon_boxo_01", "B3", resume, out _, out _, out _, Part("cartoon_boxo_01", "B3", 1, done: true, outcomes: new[] { 1, 2, 3, 4, 5 }))));
        }

        [Test]
        public void Guard_Resume_Once_FromTheFirstRunWithoutAnOutcome()
        {
            var e = Check("anime_f_01", "A3", true, out int k, out string of, out bool inv, Part("anime_f_01", "A3", 1, false, false, 1, 2, 3));
            CollectionAssert.IsEmpty(e);
            Assert.AreEqual(4, k, "runs 1-3 have an outcome, run 4 was interrupted");
            Assert.AreEqual("s1_anime_f_01_A3_1", of);
            Assert.IsFalse(inv);
            // an interrupted first run: resume from run 1
            Check("anime_f_01", "A3", true, out k, out _, out _, Part("anime_f_01", "A3", 1));
            Assert.AreEqual(1, k);
        }

        [Test]
        public void Guard_Resume_NeedsAnInterruption()
        {
            StringAssert.Contains("no earlier session", string.Join(";", Check("anime_f_01", "A1", true, out _, out _, out _)));
            StringAssert.Contains("nothing is interrupted", string.Join(";", Check("anime_f_01", "A1", true, out _, out _, out _, Part("anime_f_01", "A1", 1, false, false, 1, 2, 3, 4, 5))));
        }

        [Test]
        public void Guard_ASecondInterruption_MakesTheCellInvalid_NoThirdPart()
        {
            var parts = new[] { Part("anime_f_01", "B3", 1, false, false, 1, 2), Part("anime_f_01", "B3", 2, false, false, 3) };
            foreach (bool resume in new[] { false, true })
            {
                var e = Check("anime_f_01", "B3", resume, out _, out _, out bool inv, parts);
                StringAssert.Contains("second interruption", string.Join(";", e));
                Assert.IsTrue(inv, "the runner writes the invalid marker");
            }
            StringAssert.Contains("INVALID", string.Join(";", Check("anime_f_01", "B3", true, out _, out _, out _, Part("anime_f_01", "B3", 2, false, true))));
        }

        [Test]
        public void Markers_AreNeverFinalMarkers_AndTheScanReadsThem()
        {
            var cfg = Cfg();
            string started = S1Guard.StartedJson(cfg, "anime_f_01", "B3", new[] { 5, 7, 8, 10, 11 }, 2, 4, "s1_anime_f_01_B3_x", "abc", "s1_anime_f_01_B3_y", "2026-11-26T10:00:00");
            string done = S1Guard.DoneJson(cfg, "anime_f_01", "B3", 5, 3, "abc", "s1_anime_f_01_B3_y", "t");
            string invalid = S1Guard.InvalidJson(cfg, "anime_f_01", "B3", "a \"quoted\" reason", "t");
            foreach (var m in new[] { started, done, invalid })
            {
                StringAssert.DoesNotContain("\"setting\"", m, "a final guard's key never appears");
                StringAssert.DoesNotContain("\"final_setting\"", m);
                StringAssert.DoesNotContain(",\n}", m);
                Assert.DoesNotThrow(() => JsonUtility.FromJson<S1Marker>(m), m);
            }
            StringAssert.Contains("\"plan_runs\": [5, 7, 8, 10, 11]", started);
            StringAssert.Contains("\"resume_from_run\": 4", started);

            string root = Path.Combine(Path.GetTempPath(), "s1_scan_" + Guid.NewGuid().ToString("N"));
            try
            {
                string d1 = Path.Combine(root, "s1_anime_f_01_B3_20261126_100000");
                Directory.CreateDirectory(d1);
                File.WriteAllText(Path.Combine(d1, cfg.marker_started), S1Guard.StartedJson(cfg, "anime_f_01", "B3", new[] { 5, 7, 8, 10, 11 }, 1, 0, "", "abc", Path.GetFileName(d1), "t"));
                File.WriteAllText(Path.Combine(d1, "truth_run001.json"), "{}");
                File.WriteAllText(Path.Combine(d1, "truth_run002.json"), "{}");
                Directory.CreateDirectory(Path.Combine(root, "trials_final_Task2_B3_20261123_175422"));      // a finals folder is never read as an S1 cell
                File.WriteAllText(Path.Combine(root, "trials_final_Task2_B3_20261123_175422", cfg.marker_started), "{}");
                Directory.CreateDirectory(Path.Combine(root, "s1_no_marker"));
                var found = S1Guard.Scan(root, cfg);
                Assert.AreEqual(1, found.Count);
                Assert.AreEqual(("anime_f_01", "B3", 1, false, false), (found[0].character, found[0].setting, found[0].part, found[0].done, found[0].invalid));
                CollectionAssert.AreEquivalent(new[] { 1, 2 }, found[0].outcomes);
                File.WriteAllText(Path.Combine(d1, cfg.marker_done), done);
                Assert.IsTrue(S1Guard.Scan(root, cfg)[0].done);
            }
            finally { if (Directory.Exists(root)) Directory.Delete(root, true); }
        }

        [Serializable]
        class S1Marker { public string supplementary, status, character, s1_setting; }

        // ---------------------------------------------------------------- the shader warm-up of an S1 session

        static ShaderWarmUpRecord Rec(string look, string status = "done", string part = "session") => new ShaderWarmUpRecord { part = part, looks = look, clock = "Time.time", status = status, renders = 5 };

        [Test]
        public void WarmUp_EveryWorkerOfEveryPlannedRun_IsTheCellsOneCharacter_SoTheSessionDrawsExactlyThatLookBeforeRunOne()
        {
            foreach (var setting in Settings)
            {
                var x = Exp(setting);
                var p = Plan(x.experiment, out string error);
                var goals = p.Goals(2, FinalPlan().RunsPerSetting);
                foreach (var character in Characters)
                {
                    var looks = new List<string>();
                    foreach (int run in Cfg().Setting(setting).plan_runs)
                        looks.AddRange(p.PlanRun(2, run, goals[run - 1], new[] { character }, new[] { character }, null, out error).Workers.Select(w => w.Look));
                    CollectionAssert.AreEqual(new[] { character }, ShaderWarmUp.SessionLooks(looks), $"{setting} {character}: the look list the runner warms up (WarmUpLooks)");
                }
            }
        }

        [Test]
        public void WarmUpJsonl_IsOneJsonLinePerRecord_LikeTheLookChecks()
        {
            var a = Rec("anime_f_01");
            string text = S1Guard.WarmUpJsonl(new[] { a });
            Assert.AreEqual(JsonUtility.ToJson(a) + "\n", text);
            Assert.AreEqual("shader_warm_up.jsonl", ShaderWarmUp.RecordFile);
            Assert.AreEqual("", S1Guard.WarmUpJsonl(new ShaderWarmUpRecord[0]));
            Assert.AreEqual("anime_f_01", JsonUtility.FromJson<ShaderWarmUpRecord>(text.TrimEnd('\n')).looks);
        }

        [Test]
        public void WarmUpProblems_ACellNeedsExactlyOneDoneSessionRecordOfItsCharacter()
        {
            CollectionAssert.IsEmpty(S1Guard.WarmUpProblems(new[] { Rec("cartoon_boxo_01") }, "cartoon_boxo_01"));
            StringAssert.Contains("0 record", string.Join(";", S1Guard.WarmUpProblems(new ShaderWarmUpRecord[0], "anime_f_01")));
            StringAssert.Contains("2 record", string.Join(";", S1Guard.WarmUpProblems(new[] { Rec("anime_f_01"), Rec("anime_f_01") }, "anime_f_01")));
            StringAssert.Contains("drew look", string.Join(";", S1Guard.WarmUpProblems(new[] { Rec("sunbox_m_shirt_plaid") }, "anime_f_01")));
            StringAssert.Contains("part", string.Join(";", S1Guard.WarmUpProblems(new[] { Rec("anime_f_01", part: "play") }, "anime_f_01")));
            foreach (var status in new[] { "timed_out", "not_in_view", "" })
                StringAssert.Contains("not 'done'", string.Join(";", S1Guard.WarmUpProblems(new[] { Rec("anime_f_01", status) }, "anime_f_01")), status);
        }

        [Test]
        public void TheRunner_WritesTheS1WarmUpRecord_AfterTheWarmUp_BeforeTheErrorCheck_TheLeakTestAndRunOne()
        {
            string runner = Project("Assets/WarehouseRobot/Scenario/Scripts/TrialRunnerV4.cs");
            int run = runner.IndexOf("IEnumerator Run()", StringComparison.Ordinal);
            int warm = runner.IndexOf("yield return WarmUpSessionLooks();", run, StringComparison.Ordinal);
            int write = runner.IndexOf("if (S1) WriteS1Warm();", run, StringComparison.Ordinal);
            int check = runner.IndexOf("if (warmUpError != null)", run, StringComparison.Ordinal);
            int reset = runner.IndexOf("if (!ResetForTrial(order[startRun - 1], startRun, out error))", run, StringComparison.Ordinal);
            int leak = runner.IndexOf("gt.LeakTest(", run, StringComparison.Ordinal);
            Assert.Greater(write, warm, "after the warm-up");
            Assert.Greater(check, write, "before the error check, so a refused or failed warm-up is still logged and stops the session");
            Assert.Greater(reset, check);
            Assert.Greater(leak, reset);
            string s1 = Project("Assets/WarehouseRobot/Scenario/Scripts/TrialRunnerV4S1.cs");
            StringAssert.Contains("ShaderWarmUp.RecordFile", s1);
            StringAssert.Contains("warmUpError = string.Join", s1, "a problem stops the cell before any run");
            // the finals' path is untouched: no other session kind writes the file
            StringAssert.DoesNotContain("WriteS1Warm", Project("Assets/WarehouseRobot/Scenario/Scripts/TrialRunnerV4Experiment.cs"));
        }
        // ---------------------------------------------------------------- the look sources (the template lists Sunbox only) and a refused start

        [Test]
        public void TheWorkerTemplate_ListsSunboxOnly_SoS1AddsEachCharactersSourceToItsOwnWorker()
        {
            var template = Project("Assets/WarehouseRobot/Avatar/Prefabs/WorkerV4.prefab");
            StringAssert.Contains("Assets/SunboxGames/Avatars/Prefabs/Avatar.prefab", template);
            foreach (var character in Characters) StringAssert.DoesNotContain(character, template);
            StringAssert.DoesNotContain("Characters/worker.fbx", template, "the frozen template has no source for mixamo_worker: the avatar experiment adds it at spawn, S1 does the same");
            // the frozen template is not edited: its LF hash is the one frozen.json records
            string frozen = Repo("robot_vision/configs/v4/frozen.json");
            string hash = FinalGuardV4.Sha256Lf(File.ReadAllBytes(Path.Combine(ProjectDir, "Assets/WarehouseRobot/Avatar/Prefabs/WorkerV4.prefab")));
            StringAssert.Contains(hash, frozen, "WorkerV4.prefab is unchanged");
        }

        [Test]
        public void EveryCharacter_IsAPrefabLookOfLooksAb_WithItsFbxPrefabResolvableWhenInstalled()
        {
            var looks = ExperimentLooks.Parse(Project(ExperimentLooks.AssetPath));
            var template = WorkerV4Config.Parse(Project("Assets/WarehouseRobot/Avatar/Config/worker_v4.json"));
            foreach (var character in Characters)
            {
                var entry = ExperimentLooks.Find(template, looks.looks, character);
                Assert.IsNotNull(entry, character);
                Assert.AreEqual(LookEntry.KindPrefab, entry.kind, character);
                StringAssert.EndsWith(".fbx", entry.asset, character);
                if (!File.Exists(Path.Combine(ProjectDir, entry.asset))) { Debug.LogWarning($"{character}: {entry.asset} is not installed here (third-party, git-ignored)"); continue; }
                Assert.IsNotNull(UnityEditor.AssetDatabase.LoadAssetAtPath<GameObject>(entry.asset), $"{character}: {entry.asset} is imported and loads as a prefab");
                if (!string.IsNullOrEmpty(entry.material_override))
                    Assert.IsNotNull(UnityEditor.AssetDatabase.LoadAssetAtPath<Material>(entry.material_override), $"{character}: {entry.material_override}");
            }
        }

        [Test]
        public void S1Sources_Merge_AddsOncePerAsset_AndNeverChangesTheInput()
        {
            var sunbox = new LookSource { asset = "Assets/SunboxGames/Avatars/Prefabs/Avatar.prefab" };
            var existing = new[] { sunbox };
            var add = new[] { new LookSource { asset = "Assets/WarehouseRobot/Characters/worker.fbx" }, new LookSource { asset = "Assets/WarehouseRobot/Characters/worker.fbx" }, sunbox };
            var merged = S1Sources.Merge(existing, add);
            CollectionAssert.AreEqual(new[] { sunbox.asset, "Assets/WarehouseRobot/Characters/worker.fbx" }, merged.Select(s => s.asset).ToArray());
            Assert.AreEqual(1, existing.Length, "the template's array is not changed");
            Assert.AreEqual(1, S1Sources.Merge(null, new[] { sunbox }).Length);
            Assert.AreEqual(1, S1Sources.Merge(existing, null).Length);
        }

        [Test]
        public void TheRunner_AddsTheSourceToTheWarmUpWorker_AndToEverySpawnedWorker_NeverToThePrefab()
        {
            string warm = Project("Assets/WarehouseRobot/Scenario/Scripts/TrialRunnerV4WarmUp.cs");
            string exp = Project("Assets/WarehouseRobot/Scenario/Scripts/TrialRunnerV4Experiment.cs");
            string s1 = Project("Assets/WarehouseRobot/Scenario/Scripts/TrialRunnerV4S1.cs");
            int init = warm.IndexOf("w.Initialize()", StringComparison.Ordinal);
            Assert.Greater(init, warm.IndexOf("AddS1Sources(w);", StringComparison.Ordinal), "before the warm-up worker is initialised");
            Assert.GreaterOrEqual(warm.IndexOf("AddS1Sources(w);", StringComparison.Ordinal), 0);
            StringAssert.Contains("AddS1Sources(x);", exp, "the spawn of an experiment worker (prepare runs before Initialize)");
            StringAssert.Contains("w.lookSources = S1Sources.Merge(w.lookSources", s1, "the instance's array");
            StringAssert.DoesNotContain("workerPrefab.lookSources", s1, "the prefab's list is never written");
            StringAssert.DoesNotContain("SaveAssets", s1);
            StringAssert.DoesNotContain("PrefabUtility", s1);
        }

        [Test]
        public void ARefusedStart_NoRunBegan_IsNotAStartedCell()
        {
            var cfg = Cfg();
            string root = Path.Combine(Path.GetTempPath(), "s1_refused_" + Guid.NewGuid().ToString("N"));
            try
            {
                string refused = Path.Combine(root, "s1_mixamo_worker_A1_20261125_205027");
                Directory.CreateDirectory(refused);
                File.WriteAllText(Path.Combine(refused, cfg.marker_started), S1Guard.StartedJson(cfg, "mixamo_worker", "A1", new[] { 1, 2, 3, 4, 5 }, 1, 0, "", "abc", Path.GetFileName(refused), "t"));
                File.WriteAllText(Path.Combine(refused, "shader_warm_up.jsonl"), "{}\n");
                File.WriteAllText(Path.Combine(refused, S1Guard.NotStartedFile), "shader warm-up: look mixamo_worker: not installed");
                Assert.AreEqual("NOT_STARTED.txt", S1Guard.NotStartedFile);
                Assert.AreEqual(0, S1Guard.Scan(root, cfg).Count, "the folder is kept, but it does not count as a start");
                CollectionAssert.IsEmpty(S1Guard.Problems(cfg, "mixamo_worker", "A1", false, S1Guard.Scan(root, cfg), out int k, out _, out _));
                Assert.AreEqual(1, k);
                StringAssert.Contains("no earlier session", string.Join(";", S1Guard.Problems(cfg, "mixamo_worker", "A1", true, S1Guard.Scan(root, cfg), out _, out _, out _)));
                // a folder where a run began (no NOT_STARTED.txt) still blocks a second start
                string began = Path.Combine(root, "s1_mixamo_worker_A1_20261125_210000");
                Directory.CreateDirectory(began);
                File.WriteAllText(Path.Combine(began, cfg.marker_started), S1Guard.StartedJson(cfg, "mixamo_worker", "A1", new[] { 1, 2, 3, 4, 5 }, 1, 0, "", "abc", Path.GetFileName(began), "t"));
                Assert.AreEqual(1, S1Guard.Scan(root, cfg).Count);
                StringAssert.Contains("already started", string.Join(";", S1Guard.Problems(cfg, "mixamo_worker", "A1", false, S1Guard.Scan(root, cfg), out _, out _, out _)));
            }
            finally { if (Directory.Exists(root)) Directory.Delete(root, true); }
            StringAssert.Contains("NOT_STARTED.txt", File.ReadAllText(Path.Combine(RepoRoot, "finals_v4/run_s1.ps1")), "the launcher reads the same rule");
        }
        // ---------------------------------------------------------------- nothing frozen is touched

        [Test]
        public void TheS1Config_IsNotAFrozenFile_AndTheFrozenRecordNamesNoS1File()
        {
            string frozen = Repo("robot_vision/configs/v4/frozen.json");
            StringAssert.DoesNotContain("s1_supplementary", frozen);
            Assert.IsFalse(Final().freeze_files.Any(f => f.Contains("s1_supplementary")), "S1 adds nothing to the freeze list");
        }
    }
}
