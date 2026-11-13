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
                CollectionAssert.AreEquivalent(new[] { "point_mixamo_01", "point_ik_01" }, p.AllowedFor("POINT"));
                CollectionAssert.AreEquivalent(new[] { "proceed_ik_01", "proceed_ik_02" }, p.AllowedFor("PROCEED"));   // forward_command (2026-11-12)
                CollectionAssert.AreEquivalent(new[] { "point_mixamo_01", "point_ik_01", "proceed_ik_01", "proceed_ik_02" }, p.AllowedClips);
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

        /// <summary>robot_vision/configs/v4/roadmap.json: node positions, arrival nodes (junctions), the start heading's forward
        /// direction (start node), the roads and the worker stand offset.</summary>
        sealed class V4Map
        {
            public readonly Dictionary<string, Vector3> Pos = new Dictionary<string, Vector3>();
            public readonly Dictionary<string, string> From = new Dictionary<string, string>();
            public readonly Dictionary<string, Vector3> StartForward = new Dictionary<string, Vector3>();
            public readonly List<(Vector3, Vector3)> Roads = new List<(Vector3, Vector3)>();
            public float Offset;

            static float F(string s) => float.Parse(s, System.Globalization.CultureInfo.InvariantCulture);

            public static V4Map Load()
            {
                string road = File.ReadAllText(Path.Combine(RepoRoot, "robot_vision/configs/v4/roadmap.json"));
                var map = new V4Map();
                foreach (Match m in Regex.Matches(road, "\"(\\w+)\"\\s*:\\s*\\{\"x\":\\s*(-?[0-9.]+),\\s*\"z\":\\s*(-?[0-9.]+)([^}]*)\\}"))
                {
                    string name = m.Groups[1].Value;
                    map.Pos[name] = new Vector3(F(m.Groups[2].Value), 0f, F(m.Groups[3].Value));
                    var a = Regex.Match(m.Groups[4].Value, "\"arrive_from\"\\s*:\\s*\"(\\w+)\"");
                    if (a.Success) map.From[name] = a.Groups[1].Value;
                    var y = Regex.Match(m.Groups[4].Value, "\"start_yaw_deg\"\\s*:\\s*(-?[0-9.]+)");
                    if (y.Success) map.StartForward[name] = Quaternion.Euler(0f, F(y.Groups[1].Value), 0f) * Vector3.forward;
                }
                var branches = Regex.Match(road, "\"branches\"\\s*:\\s*\\{(.*?\\})\\s*\\}", RegexOptions.Singleline).Groups[1].Value;
                foreach (Match b in Regex.Matches(branches, "\"(\\w+)\"\\s*:\\s*\\{([^}]*)\\}"))
                    foreach (Match n in Regex.Matches(b.Groups[2].Value, "\"\\w+\"\\s*:\\s*\"(\\w+)\""))
                        map.Roads.Add((map.Pos[b.Groups[1].Value], map.Pos[n.Groups[1].Value]));
                map.Offset = F(Regex.Match(road, "\"corner_offset_m\"\\s*:\\s*([0-9.]+)").Groups[1].Value);
                return map;
            }

            public Vector3 Forward(string node) => From.TryGetValue(node, out var f) ? Pos[node] - Pos[f] : StartForward[node];
            public IEnumerable<string> AskNodes => From.Keys.Concat(StartForward.Keys);
            public Vector3 CommanderStand(string node) => TrialWorkerGeometry.Stand(Pos[node], Forward(node), Offset, Offset);
            public Vector3 BystanderStand(BystanderStand s) => TrialWorkerGeometry.Stand(Pos[s.junction], Forward(s.junction), s.ahead_m, s.right_m);

            /// <summary>The smallest nearer margin of p over every ask node's approach (TrialRunnerV4's rule).</summary>
            public float NearerMargin(Vector3 p, float approachM, out string where)
            {
                float best = float.PositiveInfinity;
                where = "";
                foreach (var n in AskNodes)
                {
                    float m = TrialWorkerGeometry.NearerMargin(p, CommanderStand(n), Pos[n], From.TryGetValue(n, out var f) ? Pos[f] : (Vector3?)null, approachM, out var at);
                    if (m < best) { best = m; where = $"{n} at ({at.x:0.00}, {at.z:0.00})"; }
                }
                return best;
            }
        }

        [Test]
        public void Bystanders_V4Map_IsWhatTheStandRulesAreCheckedOn()
        {
            var map = V4Map.Load();
            Assert.AreEqual(10, map.Roads.Count, "A-J1, J1-E1, J1-J3, J1-J2, J2-J4, J2-E2, J3-E3, J3-E4, J4-E5, J4-E6");
            CollectionAssert.AreEquivalent(new[] { "J1", "J2", "J3", "J4", "A" }, map.AskNodes.ToList());
            Assert.AreEqual(2.5f, map.Offset);
            var a = map.CommanderStand("A");
            Assert.AreEqual(8.75f, a.x, 1e-4f, "the start node's stand: 2.5 m ahead (start heading +z) and 2.5 m right");
            Assert.AreEqual(-17.5f, a.z, 1e-4f);
            var j2 = map.CommanderStand("J2");
            Assert.AreEqual(-8.75f, j2.x, 1e-4f);
            Assert.AreEqual(2.5f, j2.z, 1e-4f);
        }

        [Test]
        public void Bystanders_EveryConfiguredStandPassesEveryRule_OnTheV4Map()
        {
            // The same rules TrialRunnerV4 applies at Play (there also: a free grid cell and no collider), on robot_vision/configs/v4/roadmap.json.
            var map = V4Map.Load();
            var c = LoadTrialWorkers();
            Assert.AreEqual(2, c.bystanders.stands.Count, "2026-11-12 (upgrade_design.md section 13): J1 behind-right removed");
            foreach (var s in c.bystanders.stands)
            {
                Assert.IsTrue(map.From.ContainsKey(s.junction), s.junction);
                var p = map.BystanderStand(s);
                string label = $"{s.junction} {s.ahead_m} {s.right_m}";
                foreach (var (a, b) in map.Roads)
                    Assert.GreaterOrEqual(TrialWorkerGeometry.SegmentDistance(p, a, b), c.bystanders.min_road_clearance_m, label);
                foreach (var n in map.AskNodes)
                    Assert.GreaterOrEqual(Vector3.Distance(p, map.CommanderStand(n)), c.bystanders.min_commander_distance_m, label + " to " + n);
                float margin = map.NearerMargin(p, c.bystanders.approach_m, out string where);
                Assert.GreaterOrEqual(margin, c.bystanders.nearer_margin_m, $"{label}: {margin:0.000} m at {where}");
            }
        }

        [Test]
        public void Bystanders_TheStandsOfTheFirstR3Session_AreRefusedByTheNearerRule()
        {
            // trials_development_Task2_20261112_175544: the robot approached the J1 behind-right bystander in 10 of 10 runs.
            var map = V4Map.Load();
            var c = LoadTrialWorkers();
            var old = new[]
            {
                new BystanderStand { junction = "J1", ahead_m = 2.5f, right_m = -2.5f },
                new BystanderStand { junction = "J2", ahead_m = 2.5f, right_m = -2.5f },
                new BystanderStand { junction = "J1", ahead_m = -2.5f, right_m = 2.5f },
            };
            var margins = old.Select(s => map.NearerMargin(map.BystanderStand(s), c.bystanders.approach_m, out _)).ToArray();
            Assert.AreEqual(0f, margins[0], 1e-3f, "J1 ahead-left: a tie with the commander at the node");
            Assert.AreEqual(0f, margins[1], 1e-3f, "J2 ahead-left: a tie with the commander at the node");
            Assert.AreEqual(-3.492f, margins[2], 2e-3f, "J1 behind-right: nearer than the commander 3 m before J1");
            foreach (var m in margins) Assert.Less(m, c.bystanders.nearer_margin_m);
        }

        [Test]
        public void Bystanders_NearerMargin_SamplesTheApproachAndTheStartNode()
        {
            var node = new Vector3(0f, 0f, 0f);
            var from = new Vector3(0f, 0f, -10f);
            var commander = new Vector3(2f, 0f, 2f);
            // straight ahead of the node: always farther than the commander; the smallest margin is at the node
            float m = TrialWorkerGeometry.NearerMargin(new Vector3(0f, 0f, 6f), commander, node, from, 3f, out var at);
            Assert.AreEqual(6f - Mathf.Sqrt(8f), m, 1e-4f);
            Assert.AreEqual(0f, at.z, 1e-4f);
            // behind the node beside the road: nearer than the commander 3 m before the node
            m = TrialWorkerGeometry.NearerMargin(new Vector3(2f, 0f, -2f), commander, node, from, 3f, out at);
            Assert.AreEqual(Vector2.Distance(new Vector2(0f, -3f), new Vector2(2f, -2f)) - Vector2.Distance(new Vector2(0f, -3f), new Vector2(2f, 2f)), m, 1e-4f);
            Assert.AreEqual(-3f, at.z, 1e-4f);
            // the approach never reaches past the previous node
            TrialWorkerGeometry.NearerMargin(new Vector3(2f, 0f, -2f), commander, node, new Vector3(0f, 0f, -1f), 3f, out at);
            Assert.AreEqual(-1f, at.z, 1e-4f);
            // start node: the node only
            m = TrialWorkerGeometry.NearerMargin(new Vector3(2f, 0f, -2f), commander, node, null, 3f, out at);
            Assert.AreEqual(0f, m, 1e-4f);
            Assert.AreEqual(Vector3.zero, at);
        }

        [Test]
        public void Bystanders_ApproachIsTheJunctionSlowRadiusOfPythonsControlConfig()
        {
            // the v4 server drives with configs/hri_control.json (bridge/server.py); the robot slows within junction_slow_radius_m
            string hri = File.ReadAllText(Path.Combine(RepoRoot, "robot_vision/configs/hri_control.json"));
            var m = Regex.Match(hri, "\"junction_slow_radius_m\"\\s*:\\s*([0-9.]+)");
            Assert.IsTrue(m.Success);
            float slow = float.Parse(m.Groups[1].Value, System.Globalization.CultureInfo.InvariantCulture);
            foreach (var asset in new[] { TrialWorkersAsset, "Assets/WarehouseRobot/Avatar/Config/sessions/dev_bystanders.json",
                                          "Assets/WarehouseRobot/Avatar/Config/sessions/dev_stop.json", "Assets/WarehouseRobot/Avatar/Config/sessions/dev_wait_then_direction.json" })
            {
                var c = TrialWorkersConfig.Parse(File.ReadAllText(Path.Combine(ProjectDir, asset)));
                Assert.AreEqual(slow, c.bystanders.approach_m, 1e-6f, asset);
                Assert.AreEqual(1.0f, c.bystanders.nearer_margin_m, 1e-6f, asset + " (declared margin)");
                Assert.AreEqual(2, c.bystanders.stands.Count, asset);
            }
            var bad = LoadTrialWorkers();
            bad.bystanders.approach_m = 0f;
            bad.bystanders.nearer_margin_m = 0f;
            var e = string.Join(" | ", bad.Validate());
            StringAssert.Contains("approach_m", e);
            StringAssert.Contains("nearer_margin_m", e);
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
