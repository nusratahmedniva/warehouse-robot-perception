using System;
using System.Collections.Generic;
using System.IO;
using NUnit.Framework;
using UnityEngine;

namespace WarehouseAvatar.Tests
{
    /// <summary>
    /// v4 completion, Stage U3 (2026-11-12; Avatar/Config/upgrade_design.md sections 2 and 6): the PROCEED variants and hand
    /// shape, the unchanged random streams of the other commands, the truth field ankle_height_m, and the trial scenarios
    /// (PROCEED for the branch straight ahead, WAIT then the direction, STOP while driving) with their session configs.
    /// </summary>
    public class UpgradeV4Tests
    {
        static string ProjectDir => Path.GetDirectoryName(Application.dataPath);
        static string RepoRoot => Path.GetFullPath(Path.Combine(ProjectDir, "../../.."));
        static WorkerV4Config Workers() => WorkerV4Config.Parse(File.ReadAllText(Path.Combine(ProjectDir, "Assets/WarehouseRobot/Avatar/Config/worker_v4.json")));
        static TrialWorkersConfig Trial(string asset) => TrialWorkersConfig.Parse(File.ReadAllText(Path.Combine(ProjectDir, asset)));
        static DataSplitsV4 Splits() => DataSplitsV4.Parse(File.ReadAllText(Path.Combine(RepoRoot, "robot_vision/configs/v4/data_splits.json")));
        const string Sessions = "Assets/WarehouseRobot/Avatar/Config/sessions/";

        [Test]
        public void WorkerConfig_HasThreeProceedVariantsWithFingersTogether()
        {
            var w = Workers();
            CollectionAssert.IsEmpty(w.Validate());
            CollectionAssert.AreEqual(new[] { "proceed_ik_01", "proceed_ik_02", "proceed_ik_03" }, w.ClipNames(WorkerV4Config.Proceed));
            Assert.LessOrEqual(w.hand_shapes.proceed.spread_deg, 3f, "fingers together: never an open-palm STOP");
            Assert.AreSame(w.hand_shapes.proceed, w.hand_shapes.For(WorkerV4Config.Proceed));
            var s = Splits();
            Assert.AreEqual("development", s.Clips["proceed_ik_01"]);
            Assert.AreEqual("development", s.Clips["proceed_ik_02"]);
            Assert.AreEqual("test", s.Clips["proceed_ik_03"]);
            foreach (var c in w.clips)
                if (c.command == WorkerV4Config.Proceed) Assert.Less(c.swing_low_deg, c.swing_high_deg, c.name);
        }

        [Test]
        public void WorkerConfig_RefusesAnOpenProceedHandAndABadSwing()
        {
            var w = Workers();
            w.hand_shapes.proceed.spread_deg = 9f;
            w.clips[w.clips.Length - 1].swing_high_deg = w.clips[w.clips.Length - 1].swing_low_deg;
            var e = string.Join(" | ", w.Validate());
            StringAssert.Contains("hand_shapes.proceed.spread_deg", e);
            StringAssert.Contains("swing_low_deg < swing_high_deg", e);
        }

        [Test]
        public void Variation_ProceedAddsItsRateLastAndLeavesTheOtherStreamsAlone()
        {
            var w = Workers();
            foreach (var cmd in WorkerV4Config.Commands)
            {
                var a = GestureVariation.Draw(SeededRandom.For(1, 3, 1), w, cmd, "", null, "", 0f);
                Assert.AreEqual(0f, a.swing_hz, cmd);
            }
            var p = GestureVariation.Draw(SeededRandom.For(1, 3, 1), w, WorkerV4Config.Proceed, "", new List<string> { "proceed_ik_01" }, "", 0f);
            Assert.GreaterOrEqual(p.swing_hz, w.variation.proceed_rate_hz[0]);
            Assert.LessOrEqual(p.swing_hz, w.variation.proceed_rate_hz[1]);
            Assert.AreEqual("proceed_ik_01", p.clip);
            // the other draws of a PROCEED request are the same as those of any other command with the same stream
            var q = GestureVariation.Draw(SeededRandom.For(1, 3, 1), w, WorkerV4Config.Wait, "", null, "", 0f);
            Assert.AreEqual(q.speed, p.speed);
            Assert.AreEqual(q.hold_s, p.hold_s);
        }

        [Test]
        public void Truth_AnkleHeightIsWrittenOnlyWhenKnownAndChecked()
        {
            var r = new TruthRow
            {
                TimeS = 1.0, WorkerId = 1, Look = "sunbox_m1", TrueCommand = "PROCEED", PointAngleDeg = -1.0, Arm = "right",
                Phase = "holding", Clip = "proceed_ik_01",
            };
            Assert.IsNull(TruthFormat.Problem(r));
            StringAssert.DoesNotContain("ankle_height_m", TruthFormat.Line(r));
            r.HasAnkle = true;
            r.AnkleHeightM = 0.0812;
            StringAssert.Contains("\"ankle_height_m\": 0.0812", TruthFormat.Line(r));
            r.AnkleHeightM = 0.7;
            StringAssert.Contains("ankle_height_m", TruthFormat.Problem(r));
        }

        [Test]
        public void TrialWorkers_ForwardCommandAndScenarios()
        {
            var c = Trial("Assets/WarehouseRobot/Avatar/Config/trial_workers_v4.json");
            CollectionAssert.IsEmpty(c.Validate());
            Assert.AreEqual(WorkerV4Config.Proceed, c.forward_command);
            Assert.AreEqual(TrialWorkersConfig.ScenarioDirection, c.scenario);
            CollectionAssert.AreEqual(new[] { "POINT", "PROCEED" }, c.CommanderCommands());
            c.scenario = "dance";
            StringAssert.Contains("scenario must be", string.Join(" | ", c.Validate()));
            c.scenario = TrialWorkersConfig.ScenarioStop;
            c.stop.hold_s = new float[0];
            StringAssert.Contains("stop:", string.Join(" | ", c.Validate()));
            c.forward_command = "WAIT";
            StringAssert.Contains("forward_command", string.Join(" | ", c.Validate()));
        }

        [Test]
        public void SessionConfigs_DifferFromTheBaseOnlyInTheirOption()
        {
            var basis = Trial("Assets/WarehouseRobot/Avatar/Config/trial_workers_v4.json");
            var expect = new Dictionary<string, Action<TrialWorkersConfig>>
            {
                { "dev_bystanders.json", t => Assert.AreEqual(2, t.bystanders.count) },   // 3 -> 2 on 2026-11-12 (upgrade_design.md section 13)
                { "dev_wait_then_direction.json", t => Assert.AreEqual(TrialWorkersConfig.ScenarioWaitThenDirection, t.scenario) },
                { "dev_stop.json", t => Assert.AreEqual(TrialWorkersConfig.ScenarioStop, t.scenario) },
            };
            var w = Workers();
            var s = Splits();
            foreach (var kv in expect)
            {
                var t = Trial(Sessions + kv.Key);
                CollectionAssert.IsEmpty(t.Validate(), kv.Key);
                kv.Value(t);
                Assert.AreEqual(basis.forward_command, t.forward_command, kv.Key);
                Assert.AreEqual(basis.commander_command, t.commander_command, kv.Key);
                Assert.AreEqual(basis.data_splits, t.data_splits, kv.Key);
                var plan = TrialRunWorkers.Plan(1, "development", t, w, s, out string error);
                Assert.IsNotNull(plan, kv.Key + ": " + error);
                foreach (var cmd in t.CommanderCommands()) CollectionAssert.IsNotEmpty(plan.AllowedFor(cmd), kv.Key + " " + cmd);
                foreach (var clip in plan.AllowedClips) Assert.AreEqual("development", s.Clips[clip], kv.Key + " " + clip);
            }
        }
    }
}
