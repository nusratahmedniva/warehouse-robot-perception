using System;
using System.Collections.Generic;
using System.IO;
using System.Linq;
using System.Text;
using System.Text.RegularExpressions;
using NUnit.Framework;
using UnityEngine;

namespace WarehouseAvatar.Tests
{
    /// <summary>
    /// v4 Stage F (2026-11-13, Avatar/Config/upgrade_design.md section 13): final_v4.json, the final session configs, the B9 freeze list,
    /// the final-run guard (FinalGuardV4) and the final plans of the B7 test assignment (pending Anisha). No final is run here.
    /// </summary>
    public class FinalGuardV4Tests
    {
        static string ProjectDir => Path.GetDirectoryName(Application.dataPath);
        static string RepoRoot => Path.GetFullPath(Path.Combine(ProjectDir, "../../.."));
        const string FinalAsset = "Assets/WarehouseRobot/Avatar/Config/final_v4.json";
        const string BaseWorkers = "Assets/WarehouseRobot/Avatar/Config/trial_workers_v4.json";
        static readonly string[] Names = { "zoom_on", "zoom_off", "bystanders", "unseen_look" };

        static FinalConfigV4 Final() => FinalConfigV4.Parse(File.ReadAllText(Path.Combine(ProjectDir, FinalAsset)));
        static TrialWorkersConfig Workers(string asset) => TrialWorkersConfig.Parse(File.ReadAllText(Path.Combine(ProjectDir, asset)));
        static WorkerV4Config Template() => WorkerV4Config.Parse(File.ReadAllText(Path.Combine(ProjectDir, "Assets/WarehouseRobot/Avatar/Config/worker_v4.json")));
        static DataSplitsV4 Splits() => DataSplitsV4.Parse(File.ReadAllText(Path.Combine(RepoRoot, "robot_vision/configs/v4/data_splits.json")));
        static string RealPlan() => File.ReadAllText(Path.Combine(RepoRoot, "robot_vision/configs/v4/final_plan.json"));

        // ---------------------------------------------------------------- final_v4.json and the session configs

        [Test]
        public void Config_IsValid_AndHasTheFourSettingsOfThePythonPlan()
        {
            var f = Final();
            CollectionAssert.IsEmpty(f.Validate(), string.Join("\n", f.Validate()));
            CollectionAssert.AreEqual(Names, f.settings.Select(s => s.name).ToArray());
            CollectionAssert.AreEquivalent(Names, FinalPlanV4.Parse(RealPlan()).Settings, "final_plan.json settings");
            Assert.AreEqual("robot_vision/configs/v4/final_plan.json", f.final_plan);
            Assert.AreEqual("robot_vision/configs/v4/frozen.json", f.frozen);
            Assert.AreEqual("UNITY_FINAL_DONE.json", f.done_file);
            Assert.AreEqual("FINAL_RUN_DONE.json", f.python_run_marker);
        }

        [Test]
        public void Config_B7_DevelopmentLooksForThreeSettings_TheTestLookForUnseenLook_TestClipsEverywhere()
        {
            var f = Final();
            foreach (var n in new[] { "zoom_on", "zoom_off", "bystanders" }) Assert.AreEqual("development", f.Setting(n).look_split, n);
            Assert.AreEqual("test", f.Setting("unseen_look").look_split);
            foreach (var s in f.settings) Assert.AreEqual("test", s.clip_split, s.name);
        }

        [Test]
        public void SessionConfigs_DifferFromTheBaseOnlyInTheBystanderCount()
        {
            var basis = Workers(BaseWorkers);
            foreach (var s in Final().settings)
            {
                Assert.AreEqual($"Assets/WarehouseRobot/Avatar/Config/sessions/final_{s.name}.json", s.workers_config);
                var t = Workers(s.workers_config);
                CollectionAssert.IsEmpty(t.Validate(), s.name);
                Assert.AreEqual(s.name == "bystanders" ? 2 : 0, t.bystanders.count, s.name);
                Assert.AreEqual(TrialWorkersConfig.ScenarioDirection, t.scenario, s.name);
                Assert.AreEqual(basis.commander_command, t.commander_command, s.name);
                Assert.AreEqual(basis.forward_command, t.forward_command, s.name);
                Assert.AreEqual(basis.data_splits, t.data_splits, s.name);
                CollectionAssert.IsEmpty(t.looks, s.name + ": the looks come from the setting's split");
                Assert.AreEqual(JsonUtility.ToJson(basis.bystanders.stands[0]), JsonUtility.ToJson(t.bystanders.stands[0]), s.name);
                Assert.AreEqual(basis.bystanders.stands.Count, t.bystanders.stands.Count, s.name);
                Assert.AreEqual(basis.max_active_avatars, t.max_active_avatars, s.name);
            }
        }

        [Test]
        public void Config_RefusesPythonsEvaluationMarkerAsTheUnityDoneFile()
        {
            var f = Final();
            f.done_file = "FINAL_DONE.json";
            StringAssert.Contains("final_guard_v4", string.Join(" | ", f.Validate()));
        }

        // ---------------------------------------------------------------- B9 freeze list

        [Test]
        public void FreezeList_ListsTheV4SceneConfigsAndFinalSessions_AndEveryFileExists()
        {
            var f = Final();
            const string P = "unity/Robotics-Warehouse/WarehouseProjectURP/";
            var expect = new List<string>
            {
                P + "Assets/Scenes/WarehouseRobot_v4.unity",
                P + "Assets/WarehouseRobot/Bridge/Config/bridge_unity_v4.json",
                P + "Assets/WarehouseRobot/Robot/Config/robot_unity_v4.json",
                P + "Assets/WarehouseRobot/Avatar/Config/worker_v4.json",
                P + "Assets/WarehouseRobot/Avatar/Prefabs/WorkerV4.prefab",
                P + BaseWorkers,
                P + FinalAsset,
                P + "Assets/WarehouseRobot/Scenario/Config/trial_plan_v4.json",
            };
            foreach (var s in f.settings) expect.Add(P + s.workers_config);
            CollectionAssert.AreEquivalent(expect, f.freeze_files);
            foreach (var path in f.freeze_files) Assert.IsTrue(File.Exists(Path.Combine(RepoRoot, path)), path);
        }

        // ---------------------------------------------------------------- final_plan.json

        const string FilledPlan = "{\"task\": \"Task2\", \"final_seed\": 2, \"final_seed_note\": \"x\", \"runs_per_setting\": 20, \"timeout_s\": 270, " +
                                  "\"timeout_s_source\": \"1.5 x\", \"success_radius_m\": 0.3, \"settings\": {\"zoom_on\": {\"zoom\": true, \"bystanders\": null}, " +
                                  "\"zoom_off\": {\"zoom\": false}, \"bystanders\": {\"bystanders\": true}, \"unseen_look\": {\"zoom\": null}}, " +
                                  "\"settings_note\": \"n\", \"test_assignment\": {\"zoom_on\": \"x\"}, \"unity_files_and_guard\": \"listed\", " +
                                  "\"acceptance_criteria\": [\"a\"]}";

        [Test]
        public void Plan_ParsesTheNumbersSettingsAndBlanks()
        {
            var p = FinalPlanV4.Parse(FilledPlan);
            Assert.AreEqual("Task2", p.Task);
            Assert.AreEqual(2, p.FinalSeed);
            Assert.AreEqual(20, p.RunsPerSetting);
            Assert.AreEqual(270f, p.TimeoutS);
            Assert.AreEqual(0.3f, p.SuccessRadiusM, 1e-6f);
            CollectionAssert.AreEqual(Names, p.Settings);
            CollectionAssert.IsEmpty(p.Blanks);
            var blank = FinalPlanV4.Parse(FilledPlan.Replace("\"test_assignment\": {\"zoom_on\": \"x\"}", "\"test_assignment\": null")
                                                    .Replace("\"runs_per_setting\": 20, ", ""));
            CollectionAssert.AreEquivalent(new[] { "test_assignment", "runs_per_setting" }, blank.Blanks);
        }

        [Test]
        public void Plan_TheRealFileParses_AndItsKnownBlanksAreSeen()
        {
            var p = FinalPlanV4.Parse(RealPlan());
            Assert.AreEqual("Task2", p.Task);
            Assert.Greater(p.RunsPerSetting, 0);
            Assert.Greater(p.TimeoutS, 0f);
            Assert.Greater(p.SuccessRadiusM, 0f);
            // the plan's own blanks (null in the file) are blanks here too
            foreach (var key in FinalPlanV4.RequiredKeys)
                Assert.AreEqual(Regex.IsMatch(RealPlan(), "\"" + key + "\"\\s*:\\s*null"), p.Blanks.Contains(key), key);
        }

        // ---------------------------------------------------------------- the guard

        sealed class Repo : IDisposable
        {
            public readonly string Root = Path.Combine(Path.GetTempPath(), "final_guard_v4_" + Guid.NewGuid().ToString("N"));
            public readonly Dictionary<string, string> Hash = new Dictionary<string, string>();
            public string Outputs => Path.Combine(Root, "outputs");
            public Repo() { Directory.CreateDirectory(Outputs); }
            public string Sha(string path) => Hash.TryGetValue(path, out var h) ? h : null;
            public void Marker(string folder, string file, string text)
            {
                Directory.CreateDirectory(Path.Combine(Outputs, folder));
                File.WriteAllText(Path.Combine(Outputs, folder, file), text);
            }
            public void Dispose() { if (Directory.Exists(Root)) Directory.Delete(Root, true); }
        }

        static FinalConfigV4 SmallConfig() => FinalConfigV4.Parse(
            "{\"final_plan\": \"p.json\", \"frozen\": \"f.json\", \"done_file\": \"UNITY_FINAL_DONE.json\", \"python_run_marker\": \"FINAL_RUN_DONE.json\", " +
            "\"settings\": [{\"name\": \"zoom_on\", \"workers_config\": \"w.json\", \"look_split\": \"development\", \"clip_split\": \"test\"}, " +
            "{\"name\": \"unseen_look\", \"workers_config\": \"u.json\", \"look_split\": \"test\", \"clip_split\": \"test\"}], " +
            "\"freeze_files\": [\"unity/a.json\", \"unity/b.unity\"]}");

        static string Frozen(Repo r, bool frozen = true) =>
            "{\"frozen\": " + (frozen ? "true" : "false") + ", \"sha256\": {\"robot_vision/configs/v4/bridge.json\": \"" + new string('0', 64) + "\"}, " +
            "\"unity_files\": {" + string.Join(", ", r.Hash.Select(kv => $"\"{kv.Key}\": \"{kv.Value}\"")) + "}}";

        static Repo FreshRepo()
        {
            var r = new Repo();
            r.Hash["unity/a.json"] = FinalGuardV4.Sha256Lf(Encoding.UTF8.GetBytes("{}\n"));
            r.Hash["unity/b.unity"] = FinalGuardV4.Sha256Lf(Encoding.UTF8.GetBytes("scene\n"));
            return r;
        }

        [Test]
        public void Guard_EverythingInPlace_AllowsTheFinal()
        {
            using (var r = FreshRepo())
            {
                var p = FinalGuardV4.Problems(SmallConfig(), "zoom_on", FilledPlan, Frozen(r), r.Sha, r.Outputs, false);
                CollectionAssert.IsEmpty(p, string.Join("\n", p));
            }
        }

        [Test]
        public void Guard_RefusesUnknownSettingsBlanksAndAnUnfrozenStudy()
        {
            using (var r = FreshRepo())
            {
                string Why(string setting, string plan, string frozen) =>
                    string.Join(" | ", FinalGuardV4.Problems(SmallConfig(), setting, plan, frozen, r.Sha, r.Outputs, false));
                StringAssert.Contains("not in final_v4.json", Why("bystanders", FilledPlan, Frozen(r)));
                StringAssert.Contains("not in final_plan.json", Why("zoom_on", FilledPlan.Replace("\"zoom_on\": {\"zoom\"", "\"other\": {\"zoom\""), Frozen(r)));
                StringAssert.Contains("test_assignment is blank", Why("zoom_on", FilledPlan.Replace("\"test_assignment\": {\"zoom_on\": \"x\"}", "\"test_assignment\": null"), Frozen(r)));
                StringAssert.Contains("unity_files_and_guard is blank", Why("zoom_on", FilledPlan.Replace("\"unity_files_and_guard\": \"listed\"", "\"unity_files_and_guard\": null"), Frozen(r)));
                StringAssert.Contains("not frozen", Why("zoom_on", FilledPlan, Frozen(r, false)));
                StringAssert.Contains("runs Task2", Why("zoom_on", FilledPlan.Replace("\"Task2\"", "\"Task1\""), Frozen(r)));
            }
        }

        [Test]
        public void Guard_RefusesAFreezeFileThatIsMissingUnrecordedOrChanged()
        {
            using (var r = FreshRepo())
            {
                string frozen = Frozen(r);
                var missing = new Dictionary<string, string>(r.Hash) { ["unity/a.json"] = null };
                StringAssert.Contains("unity/a.json is missing", string.Join(" | ",
                    FinalGuardV4.Problems(SmallConfig(), "zoom_on", FilledPlan, frozen, p => missing[p], r.Outputs, false)));
                string unrecorded = frozen.Replace("\"unity/b.unity\"", "\"unity/other.unity\"");
                StringAssert.Contains("unity/b.unity is not recorded", string.Join(" | ",
                    FinalGuardV4.Problems(SmallConfig(), "zoom_on", FilledPlan, unrecorded, r.Sha, r.Outputs, false)));
                var changed = new Dictionary<string, string>(r.Hash) { ["unity/b.unity"] = FinalGuardV4.Sha256Lf(Encoding.UTF8.GetBytes("scene edited\n")) };
                StringAssert.Contains("unity/b.unity changed since the freeze", string.Join(" | ",
                    FinalGuardV4.Problems(SmallConfig(), "zoom_on", FilledPlan, frozen, p => changed[p], r.Outputs, false)));
            }
        }

        [Test]
        public void Guard_RefusesTheDevelopmentOverride()
        {
            using (var r = FreshRepo())
                StringAssert.Contains("trials.local.json", string.Join(" | ",
                    FinalGuardV4.Problems(SmallConfig(), "zoom_on", FilledPlan, Frozen(r), r.Sha, r.Outputs, true)));
        }

        [Test]
        public void Guard_RunsEachSettingOnce_UnityOrPythonMarker_OtherSettingsUnaffected()
        {
            using (var r = FreshRepo())
            {
                var cfg = SmallConfig();
                r.Marker("trials_final_Task2_unseen_look_20261201_100000", "UNITY_FINAL_DONE.json", FinalGuardV4.DoneJson("unseen_look", 20, 18, "abc", "x", "t"));
                CollectionAssert.IsEmpty(FinalGuardV4.Problems(cfg, "zoom_on", FilledPlan, Frozen(r), r.Sha, r.Outputs, false), "another setting's marker");
                StringAssert.Contains("already run as a final", string.Join(" | ",
                    FinalGuardV4.Problems(cfg, "unseen_look", FilledPlan, Frozen(r), r.Sha, r.Outputs, false)));
                r.Marker("bridge_guide_20261201_090000", "FINAL_RUN_DONE.json", "{\"setting\": \"zoom_on\", \"kind\": \"run\"}");
                StringAssert.Contains("bridge_guide_20261201_090000/FINAL_RUN_DONE.json", string.Join(" | ",
                    FinalGuardV4.Problems(cfg, "zoom_on", FilledPlan, Frozen(r), r.Sha, r.Outputs, false)));
            }
        }

        [Test]
        public void DoneFile_NamesTheSettingUnderAKeyPythonsMarkerScanNeverReads()
        {
            string text = FinalGuardV4.DoneJson("zoom_on", 20, 19, "abc123", "trials_final_Task2_zoom_on_x", "2026-12-01T10:00:00");
            StringAssert.Contains("\"final_setting\": \"zoom_on\"", text);
            StringAssert.DoesNotContain("\"setting\"", text);
            StringAssert.Contains("\"runs\": 20", text);
            StringAssert.Contains("\"successes\": 19", text);
        }

        [Test]
        public void Sha256Lf_ReadsCrlfAsLf_AsFreezeV4Does()
        {
            Assert.AreEqual(FinalGuardV4.Sha256Lf(Encoding.UTF8.GetBytes("a\nb\n")), FinalGuardV4.Sha256Lf(Encoding.UTF8.GetBytes("a\r\nb\r\n")));
            Assert.AreEqual("e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855", FinalGuardV4.Sha256Lf(new byte[0]));
        }

        [Test]
        public void Guard_TheRealRepositoryRefusesEveryFinalToday()
        {
            // not frozen and blanks open (B7, B9, B11): no final can start before Anisha's freeze
            var f = Final();
            string frozen = File.ReadAllText(Path.Combine(RepoRoot, f.frozen));
            if (Regex.IsMatch(frozen, "\"frozen\"\\s*:\\s*true")) Assert.Ignore("frozen.json is frozen: this test documents the state before the freeze");
            foreach (var n in Names)
            {
                var p = FinalGuardV4.Problems(f, n, RealPlan(), frozen,
                    path => File.Exists(Path.Combine(RepoRoot, path)) ? FinalGuardV4.Sha256Lf(File.ReadAllBytes(Path.Combine(RepoRoot, path))) : null,
                    Path.Combine(Path.GetTempPath(), "final_guard_v4_no_outputs"), false);
                StringAssert.Contains("not frozen", string.Join(" | ", p), n);
            }
        }

        // ---------------------------------------------------------------- final plans (B7)

        [Test]
        public void PlanFinal_DevelopmentLookSettings_AlternateTheDevelopmentLooks_WithTestClipsOnly()
        {
            var s = Splits();
            foreach (var name in new[] { "zoom_on", "zoom_off", "bystanders" })
            {
                var setting = Final().Setting(name);
                var looks = new List<string>();
                for (int run = 1; run <= 4; run++)
                {
                    var p = TrialRunWorkers.PlanFinal(run, setting, Workers(setting.workers_config), Template(), s, out string error);
                    Assert.IsNotNull(p, name + ": " + error);
                    foreach (var l in p.AllLooks()) Assert.AreEqual("development", s.Looks[l], $"{name} run {run} look {l}");
                    foreach (var c in p.AllowedClips) Assert.AreEqual("test", s.Clips[c], $"{name} clip {c}");
                    CollectionAssert.AreEquivalent(new[] { "point_mixamo_02" }, p.AllowedFor("POINT"), name);
                    CollectionAssert.AreEquivalent(new[] { "proceed_ik_03" }, p.AllowedFor("PROCEED"), name);
                    Assert.AreEqual(name == "bystanders" ? 2 : 0, p.BystanderLooks.Count, name);
                    looks.Add(p.CommanderLook);
                }
                CollectionAssert.AreEqual(new[] { "sunbox_f1", "sunbox_m1", "sunbox_f1", "sunbox_m1" }, looks, name);
            }
        }

        [Test]
        public void PlanFinal_UnseenLook_UsesTheTestLookAndTestClips()
        {
            var s = Splits();
            var setting = Final().Setting("unseen_look");
            var p = TrialRunWorkers.PlanFinal(1, setting, Workers(setting.workers_config), Template(), s, out string error);
            Assert.IsNotNull(p, error);
            Assert.AreEqual("sunbox_f2", p.CommanderLook);
            foreach (var c in p.AllowedClips) Assert.AreEqual("test", s.Clips[c], c);
        }

        [Test]
        public void PlanFinal_RefusesALookOutsideTheSettingsSplit_DevelopmentClips_AndPlaceholders()
        {
            var s = Splits();
            var setting = Final().Setting("zoom_on");
            var w = Workers(setting.workers_config);
            w.looks = new List<string> { "sunbox_f2" };
            Assert.IsNull(TrialRunWorkers.PlanFinal(1, setting, w, Template(), s, out string error));
            StringAssert.Contains("not a development look", error);
            var devClips = new FinalSettingV4 { name = "x", workers_config = setting.workers_config, look_split = "development", clip_split = "development" };
            Assert.IsNull(TrialRunWorkers.PlanFinal(1, devClips, Workers(setting.workers_config), Template(), s, out error));
            StringAssert.Contains("not a final-evaluation split", error);
            var placeholder = DataSplitsV4.Parse(File.ReadAllText(Path.Combine(RepoRoot, "robot_vision/configs/v4/data_splits.json"))
                .Replace("\"placeholder\": false", "\"placeholder\": true"));
            Assert.IsNull(TrialRunWorkers.PlanFinal(1, setting, Workers(setting.workers_config), Template(), placeholder, out error));
            StringAssert.Contains("placeholders", error);
        }

        [Test]
        public void Development_StillRefusesTheTestLookAndTestClips_TheFinalPlansAreFinalOnly()
        {
            // outside final mode nothing changes: the development plan refuses the final settings' test data
            var setting = Final().Setting("unseen_look");
            Assert.IsNull(TrialRunWorkers.Plan(1, "development", Workers(setting.workers_config).WithLooks("sunbox_f2"), Template(), Splits(), out string error));
            StringAssert.Contains("test data", error);
            Assert.IsNull(TrialRunWorkers.Plan(1, "final", Workers(setting.workers_config), Template(), Splits(), out error));
            StringAssert.Contains("development mode only", error);
        }
    }

    static class TrialWorkersTestExtensions
    {
        public static TrialWorkersConfig WithLooks(this TrialWorkersConfig c, params string[] looks)
        {
            c.looks = new List<string>(looks);
            return c;
        }
    }
}
