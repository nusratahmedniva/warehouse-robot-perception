using System.Collections.Generic;
using System.IO;
using System.Linq;
using System.Text.RegularExpressions;
using NUnit.Framework;
using UnityEngine;

namespace WarehouseAvatar.Tests
{
    /// <summary>v4 Phase 3A: the trial workers (data-split guard, per-run looks and clips, the question, bystander stands).</summary>
    public class TrialWorkersV4Tests
    {
        static string ProjectDir => Path.GetDirectoryName(Application.dataPath);
        static string RepoRoot => Path.GetFullPath(Path.Combine(ProjectDir, "../../.."));
        const string TrialWorkersAsset = "Assets/WarehouseRobot/Avatar/Config/trial_workers_v4.json";
        const string WorkerAsset = "Assets/WarehouseRobot/Avatar/Config/worker_v4.json";

        static TrialWorkersConfig LoadTrialWorkers() => TrialWorkersConfig.Parse(File.ReadAllText(Path.Combine(ProjectDir, TrialWorkersAsset)));
        static WorkerV4Config LoadWorkers() => WorkerV4Config.Parse(File.ReadAllText(Path.Combine(ProjectDir, WorkerAsset)));
        static DataSplitsV4 LoadSplits() => DataSplitsV4.Parse(File.ReadAllText(Path.Combine(RepoRoot, LoadTrialWorkers().data_splits)));

        const string Splits = "{\"placeholder\": false, \"looks\": {\"dev_a\": \"development\", \"dev_b\": \"development\", \"test_a\": \"test\"}, " +
                              "\"clips\": {\"point_d\": \"development\", \"point_t\": \"test\"}, \"final_evaluation_splits\": [\"test\"]}";

        // ---------------------------------------------------------------- data splits

        [Test]
        public void Splits_RealFile_HasTheAgreedNames()
        {
            var s = LoadSplits();
            Assert.IsFalse(s.Placeholder);
            CollectionAssert.AreEqual(new[] { "sunbox_f1", "sunbox_m1" }, s.Names(true, "development"));
            CollectionAssert.AreEqual(new[] { "sunbox_f2" }, s.Names(true, "test"));
            CollectionAssert.AreEquivalent(new[] { "point_mixamo_01", "point_ik_01", "wait_ik_01", "wait_raise_01", "stop_ik_01", "stop_ik_03",
                                                   "proceed_ik_01", "proceed_ik_02" }, s.Names(false, "development"));
            CollectionAssert.AreEquivalent(new[] { "point_mixamo_02", "wait_ik_02", "stop_ik_02", "proceed_ik_03" }, s.Names(false, "test"));
            CollectionAssert.AreEqual(new[] { "test" }, s.FinalEvaluationSplits);
        }

        [Test]
        public void Splits_EveryWorkerTemplateLookAndClipIsListed()
        {
            var s = LoadSplits();
            var w = LoadWorkers();
            foreach (var l in w.looks) Assert.IsTrue(s.Looks.ContainsKey(l.id), "look " + l.id);
            foreach (var c in w.clips) Assert.IsTrue(s.Clips.ContainsKey(c.name), "clip " + c.name);
        }

        [Test]
        public void Guard_Development_AcceptsDevelopmentData()
        {
            var s = DataSplitsV4.Parse(Splits);
            Assert.AreEqual("development", s.GuardRun(new[] { "dev_a", "dev_b" }, new[] { "point_d" }, false, out string error), error);
        }

        [Test]
        public void Guard_Development_RefusesTheTestLookTestClipsUnknownNamesAndMixes()
        {
            var s = DataSplitsV4.Parse(Splits);
            string error;
            Assert.IsNull(s.GuardRun(new[] { "test_a" }, new[] { "point_t" }, false, out error));
            StringAssert.Contains("test data", error);
            Assert.IsNull(s.GuardRun(new[] { "dev_a" }, new[] { "point_t" }, false, out error));
            StringAssert.Contains("mixes", error);
            Assert.IsNull(s.GuardRun(new[] { "dev_a", "test_a" }, new[] { "point_d" }, false, out error));
            StringAssert.Contains("mixes", error);
            Assert.IsNull(s.GuardRun(new[] { "dev_c" }, new[] { "point_d" }, false, out error));
            StringAssert.Contains("not listed", error);
            Assert.IsNull(s.GuardRun(new[] { "dev_a" }, new[] { "point_x" }, false, out error));
            StringAssert.Contains("not listed", error);
            Assert.IsNull(s.GuardRun(new[] { "dev_a" }, new[] { "" }, false, out error));
            StringAssert.Contains("no animation clip name", error);
            Assert.IsNull(s.GuardRun(new string[0], new[] { "point_d" }, false, out error));
            StringAssert.Contains("no avatar look", error);
        }

        [Test]
        public void Guard_Final_NeedsTestDataAndRealNames()
        {
            var s = DataSplitsV4.Parse(Splits);
            Assert.AreEqual("test", s.GuardRun(new[] { "test_a" }, new[] { "point_t" }, true, out string error), error);
            Assert.IsNull(s.GuardRun(new[] { "dev_a" }, new[] { "point_d" }, true, out error));
            var placeholder = DataSplitsV4.Parse(Splits.Replace("\"placeholder\": false", "\"placeholder\": true"));
            Assert.IsNull(placeholder.GuardRun(new[] { "test_a" }, new[] { "point_t" }, true, out error));
            StringAssert.Contains("placeholder", error);
        }

        // ---------------------------------------------------------------- per-run plans

        [Test]
        public void Config_RealFile_IsValid_AndCommanderPoints()
        {
            var c = LoadTrialWorkers();
            Assert.IsEmpty(c.Validate(), string.Join("\n", c.Validate()));
            Assert.AreEqual("POINT", c.commander_command);
            Assert.AreEqual("robot_vision/configs/v4/data_splits.json", c.data_splits);
        }

        [Test]
        public void Config_TooManyAvatars_OrTooFewStands_IsRefused()
        {
            var c = LoadTrialWorkers();
            c.bystanders.count = c.bystanders.stands.Count;
            c.max_active_avatars = c.bystanders.count;
            Assert.IsTrue(c.Validate().Any(e => e.Contains("max_active_avatars")));
            c = LoadTrialWorkers();
            c.bystanders.count = c.bystanders.stands.Count + 1;
            c.max_active_avatars = 99;
            Assert.IsTrue(c.Validate().Any(e => e.Contains("stands")));
            c = LoadTrialWorkers();
            c.commander_command = "WAIT";
            Assert.IsTrue(c.Validate().Any(e => e.Contains("commander_command")));
        }

        [Test]
        public void Plan_RealConfigs_DevelopmentRunsUseOnlyDevelopmentLooksAndClips_RotatingLooks()
        {
            var c = LoadTrialWorkers();
            c.bystanders.count = 2;
            var s = LoadSplits();
            var looks = new List<string>();
            for (int run = 1; run <= 6; run++)
            {
                var p = TrialRunWorkers.Plan(run, "development", c, LoadWorkers(), s, out string error);
                Assert.IsNotNull(p, error);
                Assert.AreEqual("development", p.Split);
                foreach (var l in p.AllLooks()) Assert.AreEqual("development", s.Looks[l], l);
                CollectionAssert.AreEquivalent(new[] { "point_mixamo_01", "point_ik_01" }, p.AllowedClips);
                Assert.AreEqual(2, p.BystanderLooks.Count);
                looks.Add(p.CommanderLook);
            }
            CollectionAssert.AreEqual(new[] { "sunbox_f1", "sunbox_m1", "sunbox_f1", "sunbox_m1", "sunbox_f1", "sunbox_m1" }, looks);
        }

        [Test]
        public void Plan_Development_RefusesTheTestLookEvenWhenTheConfigNamesIt()
        {
            var c = LoadTrialWorkers();
            c.looks = new List<string> { "sunbox_f2" };
            Assert.IsNull(TrialRunWorkers.Plan(1, "development", c, LoadWorkers(), LoadSplits(), out string error));
            StringAssert.Contains("test data", error);
            c.looks = new List<string> { "sunbox_m1", "sunbox_f2" };
            c.bystanders.count = 1;
            Assert.IsNull(TrialRunWorkers.Plan(1, "development", c, LoadWorkers(), LoadSplits(), out error), "a test-look bystander is refused too");
            StringAssert.Contains("mixes", error);
        }

        [Test]
        public void Plan_Development_NeverOffersATestClip()
        {
            var s = LoadSplits();
            var p = TrialRunWorkers.Plan(1, "development", LoadTrialWorkers(), LoadWorkers(), s, out string error);
            Assert.IsNotNull(p, error);
            CollectionAssert.DoesNotContain(p.AllowedClips, "point_mixamo_02");
            // with only test POINT clips the plan has nothing to offer
            var onlyTest = DataSplitsV4.Parse(File.ReadAllText(Path.Combine(RepoRoot, LoadTrialWorkers().data_splits))
                .Replace("\"point_mixamo_01\": \"development\"", "\"point_mixamo_01\": \"test\"")
                .Replace("\"point_ik_01\": \"development\"", "\"point_ik_01\": \"test\""));
            Assert.IsNull(TrialRunWorkers.Plan(1, "development", LoadTrialWorkers(), LoadWorkers(), onlyTest, out error));
            StringAssert.Contains("no POINT clip", error);
        }

        [Test]
        public void Plan_FinalAndUnknownModes_AreRefused()
        {
            Assert.IsNull(TrialRunWorkers.Plan(1, "final", LoadTrialWorkers(), LoadWorkers(), LoadSplits(), out string error));
            StringAssert.Contains("development mode only", error);
            Assert.IsNull(TrialRunWorkers.Plan(1, null, LoadTrialWorkers(), LoadWorkers(), LoadSplits(), out error));
        }

        // ---------------------------------------------------------------- the question

        [Test]
        public void Question_AnAskStartsWhenThePromptAppearsOrItsTextChanges()
        {
            var prompt = LoadWorkers().question.prompt;
            Assert.AreEqual("Which direction?", prompt);
            var q = new QuestionWatch(prompt);
            Assert.IsFalse(q.Update(""));
            Assert.IsFalse(q.Update("One moment..."));
            Assert.IsFalse(q.Visible);
            Assert.IsTrue(q.Update("Which direction?"));
            Assert.IsFalse(q.Update("Which direction?"), "the same question on the next command is the same ask");
            Assert.AreEqual(1, q.Ask);
            Assert.IsTrue(q.Update("Which direction? (asking again)"), "the re-ask is a new ask");
            Assert.AreEqual(2, q.Ask);
            Assert.IsFalse(q.Update(null));
            Assert.IsFalse(q.Visible);
            Assert.IsTrue(q.Update("Which direction?"), "asked again after it disappeared");
            Assert.AreEqual(3, q.Ask);
            Assert.IsFalse(q.Update("which direction?"), "the prompt is matched exactly (case included)");
        }

        // ---------------------------------------------------------------- stands and directions

        [Test]
        public void Geometry_StandFollowsTheRoadmapWorkerStandRule()
        {
            // roadmap.json: the worker stands 2.5 m ahead and 2.5 m to the right of the junction (arrival direction)
            var j1 = new Vector3(6.25f, 0f, 0f);
            var p = TrialWorkerGeometry.Stand(j1, Vector3.forward, 2.5f, 2.5f);
            Assert.AreEqual(8.75f, p.x, 1e-4f);
            Assert.AreEqual(2.5f, p.z, 1e-4f);
            var j2 = new Vector3(-6.25f, 0f, 0f);
            p = TrialWorkerGeometry.Stand(j2, Vector3.left, 2.5f, 2.5f);
            Assert.AreEqual(-8.75f, p.x, 1e-4f);
            Assert.AreEqual(2.5f, p.z, 1e-4f);
            Assert.AreEqual(1f, TrialWorkerGeometry.SegmentDistance(new Vector3(1f, 5f, 3f), Vector3.zero, new Vector3(0f, 0f, 10f)), 1e-5f);
            Assert.AreEqual(5f, TrialWorkerGeometry.SegmentDistance(new Vector3(0f, 0f, 15f), Vector3.zero, new Vector3(0f, 0f, 10f)), 1e-5f);
            var d = TrialWorkerGeometry.BranchDirection(j1, new Vector3(-6.25f, 0.3f, 0f));
            Assert.AreEqual(-1f, d.x, 1e-5f);
            Assert.AreEqual(0f, d.y, 1e-5f);
        }

        [Test]
        public void Bystanders_EveryConfiguredStandIsClearOfTheRoadsAndTheCommanderStands()
        {
            // The same rule TrialRunnerV4 applies at Play (there also: a free grid cell and no collider), on robot_vision/configs/roadmap.json.
            string road = File.ReadAllText(Path.Combine(RepoRoot, "robot_vision/configs/roadmap.json"));
            var pos = new Dictionary<string, Vector3>();
            var from = new Dictionary<string, string>();
            foreach (Match m in Regex.Matches(road, "\"(\\w+)\"\\s*:\\s*\\{\"x\":\\s*(-?[0-9.]+),\\s*\"z\":\\s*(-?[0-9.]+)([^}]*)\\}"))
            {
                pos[m.Groups[1].Value] = new Vector3(float.Parse(m.Groups[2].Value, System.Globalization.CultureInfo.InvariantCulture), 0f,
                                                     float.Parse(m.Groups[3].Value, System.Globalization.CultureInfo.InvariantCulture));
                var a = Regex.Match(m.Groups[4].Value, "\"arrive_from\"\\s*:\\s*\"(\\w+)\"");
                if (a.Success) from[m.Groups[1].Value] = a.Groups[1].Value;
            }
            var roads = new List<(Vector3, Vector3)>();
            var branches = Regex.Match(road, "\"branches\"\\s*:\\s*\\{(.*?\\})\\s*\\}", RegexOptions.Singleline).Groups[1].Value;
            foreach (Match b in Regex.Matches(branches, "\"(\\w+)\"\\s*:\\s*\\{([^}]*)\\}"))
                foreach (Match n in Regex.Matches(b.Groups[2].Value, "\"\\w+\"\\s*:\\s*\"(\\w+)\""))
                    roads.Add((pos[b.Groups[1].Value], pos[n.Groups[1].Value]));
            Assert.AreEqual(6, roads.Count, "A-J1, J1-E1, J1-E2, J1-J2, J2-E3, J2-E4");
            Assert.AreEqual(2, from.Count, "J1 and J2 have arrive_from");
            var commanderStands = from.Keys.Select(j => TrialWorkerGeometry.Stand(pos[j], pos[j] - pos[from[j]], 2.5f, 2.5f)).ToList();

            var c = LoadTrialWorkers();
            Assert.AreEqual(3, c.bystanders.stands.Count);
            foreach (var s in c.bystanders.stands)
            {
                Assert.IsTrue(from.ContainsKey(s.junction), s.junction);
                var p = TrialWorkerGeometry.Stand(pos[s.junction], pos[s.junction] - pos[from[s.junction]], s.ahead_m, s.right_m);
                foreach (var (a, b) in roads)
                    Assert.GreaterOrEqual(TrialWorkerGeometry.SegmentDistance(p, a, b), c.bystanders.min_road_clearance_m, $"{s.junction} {s.ahead_m} {s.right_m}");
                foreach (var cs in commanderStands)
                    Assert.GreaterOrEqual(Vector3.Distance(p, cs), c.bystanders.min_commander_distance_m, $"{s.junction} {s.ahead_m} {s.right_m}");
            }
        }

        // ---------------------------------------------------------------- truth with bystanders

        [Test]
        public void Truth_ACommanderAndBystanders_FormValidFrames_WithOneCommander()
        {
            string path = Path.Combine(Path.GetTempPath(), "trial_workers_v4_test_" + System.Guid.NewGuid().ToString("N") + ".jsonl");
            try
            {
                using (var w = new TruthFileWriter(path))
                {
                    TruthRow Row(int id, bool commander, string cmd, string phase) => new TruthRow
                    {
                        TimeS = 10.0, WorkerId = id, Look = id == 1 ? "sunbox_m1" : "sunbox_f1", X = id, Z = 2.5,
                        TrueCommand = cmd, PointAngleDeg = cmd == "POINT" ? -80.0 : -1.0, Arm = cmd == "NONE" ? "none" : "right",
                        Phase = phase, IsCommander = commander, Clip = cmd == "NONE" ? "" : "point_ik_01",
                    };
                    w.WriteFrame(new[] { Row(1, true, "POINT", "holding"), Row(2, false, "NONE", "idle"), Row(3, false, "NONE", "idle") });
                    Assert.Throws<System.InvalidOperationException>(() =>
                        w.WriteFrame(new[] { Row(1, true, "POINT", "holding"), Row(2, true, "NONE", "idle"), Row(3, false, "NONE", "idle") }));
                }
                var lines = File.ReadAllLines(path);
                Assert.AreEqual(3, lines.Length);
                Assert.AreEqual(1, lines.Count(l => l.Contains("\"is_commander\": true")));
            }
            finally
            {
                if (File.Exists(path)) File.Delete(path);
            }
        }
    }
}
