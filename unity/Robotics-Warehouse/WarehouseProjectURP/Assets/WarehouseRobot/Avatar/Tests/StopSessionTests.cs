using System.Collections.Generic;
using System.IO;
using System.Linq;
using NUnit.Framework;
using UnityEngine;

namespace WarehouseAvatar.Tests
{
    /// <summary>
    /// The STOP session (scenario stop_session; Avatar/Config/experiments_ab.md section 13 part B, declared 2026-11-15): the declared plan
    /// of sessions/dev_stop_session.json (64 runs, exact counts and order), its checks, and that every run uses development looks and
    /// clips only. Nothing is run.
    /// </summary>
    public class StopSessionTests
    {
        static string ProjectDir => Path.GetDirectoryName(Application.dataPath);
        static string RepoRoot => Path.GetFullPath(Path.Combine(ProjectDir, "../../.."));
        const string SessionAsset = "Assets/WarehouseRobot/Avatar/Config/sessions/dev_stop_session.json";

        static TrialWorkersConfig Session() => TrialWorkersConfig.Parse(File.ReadAllText(Path.Combine(ProjectDir, SessionAsset)));
        static WorkerV4Config Template() => WorkerV4Config.Parse(File.ReadAllText(Path.Combine(ProjectDir, "Assets/WarehouseRobot/Avatar/Config/worker_v4.json")));
        static DataSplitsV4 Splits() => DataSplitsV4.Parse(File.ReadAllText(Path.Combine(RepoRoot, "robot_vision/configs/v4/data_splits.json")));
        static TrialWorkersConfig Copy(TrialWorkersConfig c) => TrialWorkersConfig.Parse(JsonUtility.ToJson(c));

        [Test]
        public void SessionConfig_IsValid_AndDeclaresTheSection13Values()
        {
            var c = Session();
            CollectionAssert.IsEmpty(c.Validate(), string.Join(" | ", c.Validate()));
            Assert.AreEqual(TrialWorkersConfig.ScenarioStopSession, c.scenario);
            var s = c.stop_session;
            CollectionAssert.AreEqual(new[] { "sunbox_m1", "sunbox_f1" }, s.looks);
            Assert.AreEqual(5, s.held_stop_per_arm);
            CollectionAssert.AreEqual(new[] { "POINT", "PROCEED", "WAIT" }, s.negative_commands);
            Assert.AreEqual(3, s.negatives_per_arm);
            Assert.AreEqual(3, s.driving_stop_per_look);
            CollectionAssert.AreEqual(new[] { 4.0f, 6.0f }, s.driving_stop_distance_m);
            Assert.AreEqual(1, s.idle_pass_per_look);
            Assert.AreEqual("J1", s.idle_stand.junction);
            Assert.AreEqual(-10.0f, s.idle_stand.ahead_m);
            Assert.AreEqual(1.6f, s.idle_stand.right_m);
            Assert.AreEqual(0, c.bystanders.count);
            Assert.AreEqual(2, c.max_active_avatars);
            CollectionAssert.AreEquivalent(new[] { "POINT", "PROCEED", "WAIT", "STOP" }, c.CommanderCommands());
        }

        [Test]
        public void Plan_SixtyFourRuns_TheDeclaredCounts()
        {
            var items = StopSessionPlan.Items(Session().stop_session);
            Assert.AreEqual(64, items.Count);
            CollectionAssert.AreEqual(Enumerable.Range(1, 64).ToArray(), items.Select(i => i.Run).ToArray());
            foreach (var look in new[] { "sunbox_m1", "sunbox_f1" })
            {
                var mine = items.Where(i => i.Look == look).ToList();
                Assert.AreEqual(32, mine.Count, look);
                foreach (var arm in StopSessionPlan.Arms)
                {
                    Assert.AreEqual(5, mine.Count(i => i.Kind == StopItemKind.Held && i.Command == "STOP" && i.Arm == arm), $"{look} STOP {arm}");
                    foreach (var neg in new[] { "POINT", "PROCEED", "WAIT" })
                        Assert.AreEqual(3, mine.Count(i => i.Kind == StopItemKind.Held && i.Command == neg && i.Arm == arm), $"{look} {neg} {arm}");
                }
                Assert.AreEqual(3, mine.Count(i => i.Kind == StopItemKind.DrivingStop && i.Command == "STOP"), look);
                Assert.AreEqual(1, mine.Count(i => i.Kind == StopItemKind.IdlePass && i.Arm == ""), look);
            }
            Assert.AreEqual(20, items.Count(i => i.Kind == StopItemKind.Held && i.Command == "STOP"));
            Assert.AreEqual(36, items.Count(i => i.Kind == StopItemKind.Held && i.Command != "STOP"));
            Assert.AreEqual(6, items.Count(i => i.Kind == StopItemKind.DrivingStop));
            Assert.AreEqual(2, items.Count(i => i.Kind == StopItemKind.IdlePass));
        }

        [Test]
        public void Plan_Order_LooksAlternate_RepetitionsThenDrivesThenIdlePass()
        {
            var items = StopSessionPlan.Items(Session().stop_session);
            for (int i = 0; i < items.Count; i++) Assert.AreEqual(i % 2 == 0 ? "sunbox_m1" : "sunbox_f1", items[i].Look, $"run {i + 1}");
            var m1 = items.Where(i => i.Look == "sunbox_m1").Select(i => i.Describe()).ToArray();
            CollectionAssert.AreEqual(new[]
            {
                "sunbox_m1 held STOP right 1", "sunbox_m1 held STOP left 1", "sunbox_m1 negative POINT right 1", "sunbox_m1 negative POINT left 1",
                "sunbox_m1 negative PROCEED right 1", "sunbox_m1 negative PROCEED left 1", "sunbox_m1 negative WAIT right 1", "sunbox_m1 negative WAIT left 1",
            }, m1.Take(8).ToArray());
            CollectionAssert.AreEqual(new[]
            {
                "sunbox_m1 held STOP right 4", "sunbox_m1 held STOP left 4", "sunbox_m1 held STOP right 5", "sunbox_m1 held STOP left 5",
                "sunbox_m1 driving STOP right 1", "sunbox_m1 driving STOP left 2", "sunbox_m1 driving STOP right 3", "sunbox_m1 idle pass 1",
            }, m1.Skip(24).ToArray());
            var f1Drives = items.Where(i => i.Look == "sunbox_f1" && i.Kind == StopItemKind.DrivingStop).Select(i => i.Arm).ToArray();
            CollectionAssert.AreEqual(new[] { "left", "right", "left" }, f1Drives, "the second look's driving STOPs start with the left arm");
        }

        [Test]
        public void Clip_ByRepetition_AlternatesTheDevelopmentClips()
        {
            var plan = TrialRunWorkers.Plan(1, "development", Session(), Template(), Splits(), out string error, "sunbox_m1");
            Assert.IsNotNull(plan, error);
            CollectionAssert.AreEqual(new[] { "stop_ik_01", "stop_ik_03" }, plan.AllowedFor("STOP"));
            CollectionAssert.AreEqual(new[] { "point_mixamo_01", "point_ik_01" }, plan.AllowedFor("POINT"));
            CollectionAssert.AreEqual(new[] { "proceed_ik_01", "proceed_ik_02" }, plan.AllowedFor("PROCEED"));
            CollectionAssert.AreEqual(new[] { "wait_ik_01", "wait_raise_01" }, plan.AllowedFor("WAIT"));
            var stop = plan.AllowedFor("STOP");
            CollectionAssert.AreEqual(new[] { "stop_ik_01", "stop_ik_03", "stop_ik_01", "stop_ik_03", "stop_ik_01" },
                                      Enumerable.Range(1, 5).Select(r => StopSessionPlan.Clip(stop, r)).ToArray());
            Assert.AreEqual("", StopSessionPlan.Clip(new List<string>(), 1));
        }

        [Test]
        public void EveryRun_DevelopmentLookAndClipsOnly_TheTestLookIsRefused()
        {
            var cfg = Session();
            var splits = Splits();
            foreach (var item in StopSessionPlan.Items(cfg.stop_session))
            {
                var plan = TrialRunWorkers.Plan(item.Run, "development", cfg, Template(), splits, out string error, item.Look);
                Assert.IsNotNull(plan, $"run {item.Run}: {error}");
                Assert.AreEqual(item.Look, plan.CommanderLook, $"run {item.Run}");
                Assert.AreEqual("development", plan.Split, $"run {item.Run}");
                foreach (var c in plan.AllowedClips) Assert.AreEqual("development", splits.Clips[c], c);
            }
            Assert.IsNull(TrialRunWorkers.Plan(1, "development", cfg, Template(), splits, out string refused, "sunbox_f2"));
            StringAssert.Contains("mixes development and test", refused);       // the test look with the session's development clips
            Assert.IsNull(TrialRunWorkers.Plan(1, "final", cfg, Template(), splits, out refused, "sunbox_m1"));
            StringAssert.Contains("development mode only", refused);
        }

        [Test]
        public void Validate_RefusesWhatTheSessionCannotRun()
        {
            string Why(System.Action<TrialWorkersConfig> change) { var c = Copy(Session()); change(c); return string.Join(" | ", c.Validate()); }
            StringAssert.Contains("'STOP' must be POINT, PROCEED or WAIT", Why(c => c.stop_session.negative_commands = new List<string> { "STOP" }));
            StringAssert.Contains("driving_stop_distance_m", Why(c => c.stop_session.driving_stop_distance_m = new[] { 2.0f, 6.0f }));
            StringAssert.Contains("driving_stop_distance_m", Why(c => c.stop_session.driving_stop_distance_m = new[] { 6.0f, 4.0f }));
            StringAssert.Contains("idle_stand: a junction is required", Why(c => c.stop_session.idle_stand.junction = ""));
            StringAssert.Contains("max_active_avatars must be >= 2", Why(c => c.max_active_avatars = 1));
            StringAssert.Contains("forward_command must be PROCEED", Why(c => c.forward_command = ""));
            StringAssert.Contains("bystanders.count must be 0", Why(c => { c.bystanders.count = 1; c.bystanders.stands.Add(new BystanderStand { junction = "J1" }); }));
            StringAssert.Contains("stop_session.looks", Why(c => c.stop_session.looks = new List<string>()));
            StringAssert.Contains("item_timeout_s", Why(c => c.stop_session.item_timeout_s = 0f));
            StringAssert.Contains("point_body_azimuth_deg", Why(c => c.stop_session.point_body_azimuth_deg = 150f));
            // the other scenarios never read the block
            var task2 = Copy(Session());
            task2.scenario = TrialWorkersConfig.ScenarioDirection;
            task2.stop_session = new StopSessionConfig();
            CollectionAssert.IsEmpty(task2.Validate());
            CollectionAssert.AreEquivalent(new[] { "POINT", "PROCEED" }, task2.CommanderCommands());
        }
    }
}
