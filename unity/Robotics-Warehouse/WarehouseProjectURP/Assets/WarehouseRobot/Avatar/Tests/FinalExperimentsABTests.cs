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
    /// Experiments A/B finals (2026-11-14, Avatar/Config/experiments_ab.md section 7): the nine experiment settings of final_v4.json, their
    /// final configs (sessions/final_ab_&lt;setting&gt;.json), the test looks and clips of a final, and that a development session never
    /// offers a test look or clip. Nothing is run.
    /// </summary>
    public class FinalExperimentsABTests
    {
        static string ProjectDir => Path.GetDirectoryName(Application.dataPath);
        static string RepoRoot => Path.GetFullPath(Path.Combine(ProjectDir, "../../.."));
        const string FinalAsset = "Assets/WarehouseRobot/Avatar/Config/final_v4.json";
        const string BaseWorkers = "Assets/WarehouseRobot/Avatar/Config/trial_workers_v4.json";
        const string ExperimentsAsset = "Assets/WarehouseRobot/Scenario/Config/experiments_ab_unity.json";
        static readonly string[] Names = { "A1", "A2_right", "A2_left", "A3", "A4", "B1", "B2_right", "B3", "B4" };
        static readonly string[] TestLooks = { "sunbox_f_shirt_plaid", "sunbox_m_shirt_plaid" };
        static readonly string[] Commands = { "POINT", "PROCEED" };

        static string Project(string asset) => File.ReadAllText(Path.Combine(ProjectDir, asset));
        static string Repo(string path) => File.ReadAllText(Path.Combine(RepoRoot, path));
        static FinalConfigV4 Final() => FinalConfigV4.Parse(Project(FinalAsset));
        static FinalExperimentV4 Exp(FinalSettingV4 s) => FinalExperimentV4.Parse(Project(s.experiment_config));
        static WorkerV4Config Template() => WorkerV4Config.Parse(Project("Assets/WarehouseRobot/Avatar/Config/worker_v4.json"));
        static DataSplitsV4 Splits() => DataSplitsV4.Parse(Repo("robot_vision/configs/v4/data_splits.json"));
        static ExperimentLooksFile Looks() => ExperimentLooks.Parse(Project(ExperimentLooks.AssetPath));
        static ExperimentsUnityConfig Ecfg() => ExperimentsUnityConfig.Parse(Project(ExperimentsAsset));
        static string Scenarios() => Repo(Ecfg().scenarios_ab);
        static Func<string, string> MapOf() { var c = Ecfg(); var s = Scenarios(); return x => ExperimentPlanAB.MapOfExperiment(c, s, x); }

        static List<string> Problems(FinalSettingV4 s, FinalExperimentV4 x, DataSplitsV4 splits = null) =>
            FinalGuardV4.ExperimentProblems(s, x, MapOf(), splits ?? Splits(), Looks(), Template());

        static FinalExperimentV4 Copy(FinalExperimentV4 x) => FinalExperimentV4.Parse(JsonUtility.ToJson(x));

        // ---------------------------------------------------------------- final_v4.json and the final configs

        [Test]
        public void Settings_AreTheNineExperiments_EachWithItsOwnFinalConfig()
        {
            var f = Final();
            CollectionAssert.AreEqual(Names, f.settings.Select(s => s.name).ToArray());
            foreach (var s in f.settings)
            {
                Assert.IsTrue(s.IsExperiment, s.name);
                Assert.AreEqual($"Assets/WarehouseRobot/Avatar/Config/sessions/final_ab_{s.name}.json", s.experiment_config, s.name);
                Assert.AreEqual(BaseWorkers, s.workers_config, s.name);
                Assert.AreEqual("test", s.look_split, s.name);
                Assert.AreEqual("test", s.clip_split, s.name);
                Assert.AreEqual(s.name, Exp(s).SettingName, s.name + ": the config names its own setting");
                Assert.IsNull(f.Superseded(s.name), s.name);
            }
        }

        [Test]
        public void FinalConfigs_PassEveryCheck_TestLooksAndTestClipsOnly_LieDetectionOn()
        {
            var splits = Splits();
            foreach (var s in Final().settings)
            {
                var x = Exp(s);
                var p = Problems(s, x, splits);
                CollectionAssert.IsEmpty(p, s.name + ": " + string.Join(" | ", p));
                CollectionAssert.AreEqual(new[] { "sunbox_m_shirt_plaid" }, x.male_looks, s.name);
                CollectionAssert.AreEqual(new[] { "sunbox_f_shirt_plaid" }, x.female_looks, s.name);
                CollectionAssert.AreEqual(new[] { "point_mixamo_02" }, x.point_clips, s.name);
                CollectionAssert.AreEqual(new[] { "proceed_ik_03" }, x.proceed_clips, s.name);
                foreach (var l in x.male_looks.Concat(x.female_looks)) Assert.AreEqual("test", splits.Looks[l], l);
                foreach (var c in x.point_clips.Concat(x.proceed_clips)) Assert.AreEqual("test", splits.Clips[c], c);
                Assert.AreEqual("on", x.lie_detection, s.name);
                Assert.AreEqual(s.name.StartsWith("A2") || s.name.StartsWith("B2") ? s.name.Substring(3) : "", x.a2_side, s.name);
            }
        }

        [Test]
        public void FinalConfigs_PythonControlFile_ExistsWithTheExperimentsMapAndLieDetectionOn()
        {
            // the server takes its map from the control file's roadmap key (AUDIT.md 16.12 item 5); "on" = second opinion + reject impossible
            var roadmapOf = new Dictionary<string, string>
            {
                ["A1"] = "configs/v4/experiments/roadmap_a1.json", ["B1"] = "configs/v4/experiments/roadmap_a1.json",
                ["A2_right"] = "configs/v4/experiments/roadmap_a2_right.json", ["B2_right"] = "configs/v4/experiments/roadmap_a2_right.json",
                ["A2_left"] = "configs/v4/experiments/roadmap_a2_left.json",
                ["A3"] = "configs/v4/roadmap.json", ["A4"] = "configs/v4/roadmap.json", ["B3"] = "configs/v4/roadmap.json", ["B4"] = "configs/v4/roadmap.json",
            };
            foreach (var s in Final().settings)
            {
                var x = Exp(s);
                string path = Path.Combine(RepoRoot, "robot_vision", x.python_control);
                Assert.IsTrue(File.Exists(path), s.name + ": " + x.python_control);
                var control = (Dictionary<string, object>)MiniJson.Parse(File.ReadAllText(path));
                Assert.AreEqual(roadmapOf[s.name], control["roadmap"], s.name);
                var lie = (Dictionary<string, object>)control["lie_detection"];
                Assert.AreEqual(true, lie["second_opinion"], s.name);
                Assert.AreEqual(true, lie["reject_impossible"], s.name);
                Assert.AreEqual(false, lie["backtrack"], s.name);
            }
        }

        [Test]
        public void SupersededSessionConfigs_AreKept_AndMarked()
        {
            foreach (var s in Final().superseded_settings)
                StringAssert.Contains("\"session_note\": \"SUPERSEDED on 2026-11-14", Project(s.workers_config), s.name);
            StringAssert.Contains("\"session_note\": \"SUPERSEDED on 2026-11-14", Project("Assets/WarehouseRobot/Avatar/Config/sessions/rehearsal_zoom_on.json"));
        }

        // ---------------------------------------------------------------- the checks of a final experiment config

        [Test]
        public void ExperimentProblems_RefuseDevelopmentData_WrongGender_NoNavigationLook_AndAnUnknownClip()
        {
            var s = Final().Setting("A3");
            var x = Exp(s);
            string Why(Action<FinalExperimentV4> change) { var y = Copy(x); change(y); return string.Join(" | ", Problems(s, y)); }
            StringAssert.Contains("not a test look", Why(y => y.male_looks = new List<string> { "sunbox_m_shirt_white" }));
            StringAssert.Contains("not a test clip", Why(y => y.point_clips = new List<string> { "point_mixamo_01" }));
            StringAssert.Contains("is a female look, listed as male", Why(y => y.male_looks = new List<string> { "sunbox_f_shirt_plaid" }));
            StringAssert.Contains("not a navigation look", Why(y => y.female_looks = new List<string> { "sunbox_f2" }));
            StringAssert.Contains("not a navigation look", Why(y => y.female_looks = new List<string> { "anime_f_01" }));
            StringAssert.Contains("not a POINT clip", Why(y => y.point_clips = new List<string> { "wait_ik_02" }));
            StringAssert.Contains("needs at least one look", Why(y => y.female_looks = new List<string>()));
            StringAssert.Contains("PROCEED needs at least one clip", Why(y => y.proceed_clips = new List<string>()));
        }

        [Test]
        public void ExperimentProblems_RefuseAWrongSideNameControlFileOrSwitch()
        {
            var f = Final();
            string Why(string setting, Action<FinalExperimentV4> change)
            {
                var s = f.Setting(setting);
                var y = Copy(Exp(s));
                change(y);
                return string.Join(" | ", Problems(s, y));
            }
            StringAssert.Contains("a2_side must be right or left", Why("A2_right", y => y.a2_side = ""));
            StringAssert.Contains("a2_side is for the turn map only", Why("A3", y => y.a2_side = "left"));
            StringAssert.Contains("it is the config of setting A2_left, not of A2_right", Why("A2_right", y => { y.a2_side = "left"; y.python_control = "configs/v4/experiments/control_lie_on_a2_left.json"; }));
            StringAssert.Contains("not in experiments_ab_unity.json", Why("A1", y => y.experiment = "C1"));
            StringAssert.Contains("python_control must be configs/v4/experiments/control_lie_on_a1.json", Why("B1", y => y.python_control = "configs/v4/experiments/control_lie_on.json"));
            StringAssert.Contains("python_control must be configs/v4/experiments/control_lie_off.json", Why("B3", y => y.lie_detection = "off"));
            StringAssert.Contains("lie_detection must be on or off", Why("B4", y => y.lie_detection = ""));
            var placeholder = DataSplitsV4.Parse(Repo("robot_vision/configs/v4/data_splits.json").Replace("\"placeholder\": false", "\"placeholder\": true"));
            StringAssert.Contains("placeholders", string.Join(" | ", Problems(f.Setting("A1"), Exp(f.Setting("A1")), placeholder)));
            var dev = new FinalSettingV4 { name = "A1", workers_config = BaseWorkers, experiment_config = f.Setting("A1").experiment_config, look_split = "development", clip_split = "test" };
            StringAssert.Contains("'development' is not a final-evaluation split", string.Join(" | ", Problems(dev, Exp(f.Setting("A1")))));
        }

        [Test]
        public void MapOfExperiment_ReadsScenariosAb()
        {
            var map = MapOf();
            Assert.AreEqual("corridor", map("A1"));
            Assert.AreEqual("turn", map("B2"));
            Assert.AreEqual("roadmap", map("A3"));
            Assert.AreEqual("roadmap", map("B4"));
            Assert.IsNull(map("A9"));
            Assert.AreEqual("configs/v4/experiments/control_lie_on_a2_left.json", FinalExperimentV4.ExpectedControl("turn", "left", "on"));
            Assert.AreEqual("configs/v4/experiments/control_lie_off.json", FinalExperimentV4.ExpectedControl("roadmap", "", "off"));
        }

        // ---------------------------------------------------------------- looks and clips of a session: final vs development

        [Test]
        public void ExperimentData_Final_GivesExactlyTheConfigsTestLooksAndClips()
        {
            foreach (var s in Final().settings)
            {
                var males = new List<string>(); var females = new List<string>(); var clips = new Dictionary<string, List<string>>();
                Assert.IsTrue(FinalGuardV4.ExperimentData(s, Exp(s), "development", Splits(), Looks(), Template(), Commands, males, females, clips, out string error), error);
                CollectionAssert.AreEqual(new[] { "sunbox_m_shirt_plaid" }, males, s.name);
                CollectionAssert.AreEqual(new[] { "sunbox_f_shirt_plaid" }, females, s.name);
                CollectionAssert.AreEqual(new[] { "point_mixamo_02" }, clips["POINT"], s.name);
                CollectionAssert.AreEqual(new[] { "proceed_ik_03" }, clips["PROCEED"], s.name);
                var all = males.Concat(females).ToList();
                Assert.AreEqual("test", Splits().GuardRun(all, clips.Values.SelectMany(c => c), true, out error), error);
                Assert.IsFalse(FinalGuardV4.ExperimentData(s, Exp(s), "development", Splits(), Looks(), Template(), new[] { "POINT", "WAIT" }, males, females, clips, out error));
                StringAssert.Contains("POINT or PROCEED only", error);
            }
        }

        [Test]
        public void ExperimentData_Development_NeverOffersATestLookOrClip_AndTheDevelopmentGuardRefusesThem()
        {
            var splits = Splits();
            var males = new List<string>(); var females = new List<string>(); var clips = new Dictionary<string, List<string>>();
            Assert.IsTrue(FinalGuardV4.ExperimentData(null, null, "development", splits, Looks(), Template(), Commands, males, females, clips, out string error), error);
            CollectionAssert.AreEqual(new[] { "sunbox_m_shirt_white", "sunbox_m_tshirt_black" }, males);
            CollectionAssert.AreEqual(new[] { "sunbox_f_dress_red", "sunbox_f_shirt_white" }, females);
            foreach (var l in males.Concat(females)) Assert.AreEqual("development", splits.Looks[l], l);
            foreach (var c in clips.Values.SelectMany(c => c)) Assert.AreEqual("development", splits.Clips[c], c);
            CollectionAssert.IsEmpty(males.Concat(females).Intersect(TestLooks));

            // what the runner checks on every run of a development session (GuardRun, final evaluation false): the test looks, the
            // test clips and any mix are refused, also through the smoke-check override (-experimentLooks)
            var devClips = clips.Values.SelectMany(c => c).ToList();
            Assert.IsNull(splits.GuardRun(TestLooks, new[] { "point_mixamo_02", "proceed_ik_03" }, false, out error));
            StringAssert.Contains("refused outside the final runs", error);
            Assert.IsNull(splits.GuardRun(TestLooks, devClips, false, out error));
            StringAssert.Contains("mixes development and test", error);
            Assert.IsNull(splits.GuardRun(males.Concat(females), new[] { "point_mixamo_02" }, false, out error));
            StringAssert.Contains("mixes development and test", error);
            // and a final never accepts development data
            Assert.IsNull(splits.GuardRun(males.Concat(females), devClips, true, out error));
            StringAssert.Contains("a final run must use test data", error);
        }

        [Test]
        public void ExperimentData_OutsideAFinal_DevelopmentModeOnly()
        {
            var males = new List<string>(); var females = new List<string>(); var clips = new Dictionary<string, List<string>>();
            Assert.IsFalse(FinalGuardV4.ExperimentData(null, null, "final", Splits(), Looks(), Template(), Commands, males, females, clips, out string error));
            StringAssert.Contains("development mode only", error);
        }

        // ---------------------------------------------------------------- the planned final runs

        static ExperimentPlanAB Plan(string experiment, string side, out string error)
        {
            var cfg = Ecfg();
            if (side.Length > 0) cfg.a2_sides = new[] { side };
            return ExperimentPlanAB.Build(cfg, experiment, Scenarios(), Repo(cfg.roadmap_v4), Project, out error);
        }

        [Test]
        public void FinalRuns_SeedTwo_TwentyRuns_TestLooksOnly_GoalsAsDeclared_SidesAsTheSetting()
        {
            const int seed = 2, runs = 20;
            var declared = "E5 E1 E5 E2 E5 E3 E5 E3 E4 E3 E5 E3 E5 E6 E2 E5 E3 E1 E4 E2".Split(' ');     // experiments_ab.md section 7
            var splits = Splits();
            foreach (var s in Final().settings)
            {
                var x = Exp(s);
                var plan = Plan(x.experiment, x.a2_side, out string error);
                Assert.IsNotNull(plan, s.name + ": " + error);
                var goals = plan.Goals(seed, runs);
                if (plan.MapName == "roadmap") CollectionAssert.AreEqual(declared, goals, s.name);
                for (int run = 1; run <= runs; run++)
                {
                    var r = plan.PlanRun(seed, run, goals[run - 1], x.male_looks, x.female_looks, null, out error);
                    Assert.IsNotNull(r, $"{s.name} run {run}: {error}");
                    if (x.a2_side.Length > 0) Assert.AreEqual(x.a2_side == "left" ? "turn_left" : "turn", r.MapName, $"{s.name} run {run}");
                    var looks = r.Workers.Select(w => w.Look).ToList();
                    CollectionAssert.IsSubsetOf(looks.Distinct().ToList(), TestLooks, $"{s.name} run {run}");
                    Assert.AreEqual("test", splits.GuardRun(looks, x.point_clips.Concat(x.proceed_clips), true, out error), $"{s.name} run {run}: {error}");
                    // declared difference (section 7): with one look per gender the third worker at J1 wears the first worker's look
                    var j1 = r.Workers.Where(w => w.Node == "J1").ToList();
                    if (j1.Count == 3) Assert.AreEqual(j1[0].Look, j1[2].Look, $"{s.name} run {run}");
                }
            }
        }
    }
}
