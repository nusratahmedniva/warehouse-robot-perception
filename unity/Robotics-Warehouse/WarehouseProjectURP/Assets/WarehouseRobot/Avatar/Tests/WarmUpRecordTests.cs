using System;
using System.Collections.Generic;
using System.IO;
using System.Linq;
using System.Text.RegularExpressions;
using NUnit.Framework;
using UnityEngine;

namespace WarehouseAvatar.Tests
{
    /// <summary>
    /// experiments_ab.md section 15 addendum 12 (2026-11-21): the warm-up record and its tracker, the per-recording compile flag of the Edit
    /// rows, the helpers of the session warm-up, a source check that the session warm-up draws no seeded stream and runs after the plans and
    /// before the leak test, and the data_splits.json role avatar_experiment. Nothing is run.
    /// </summary>
    public class WarmUpRecordTests
    {
        static string Project(string rel) => File.ReadAllText(Path.Combine(Application.dataPath, "..", rel));
        static string Repo(string rel) => File.ReadAllText(Path.Combine(Application.dataPath, "../../../..", rel));

        [Test]
        public void Tracker_FillsTheRecord_FirstAndLastCompile_CompilingAtEnd_Done()
        {
            var rec = new ShaderWarmUpRecord { part = ShaderWarmUpRecord.Play, round = 11, looks = "J2: anime_f_01 (worker 22)", clock = ShaderWarmUpRecord.ClockTime };
            var t = new ShaderWarmUpTracker(rec, 5124.0, 100.0, true, "2026-11-21T16:40:00.000");
            Assert.AreEqual(5124.0, rec.time_start_s);
            Assert.IsTrue(rec.compiling_at_start);
            Assert.AreEqual(ShaderWarmUp.State.Continue, t.AfterRender(23930, true, 5124.1, 100.1, "a"));
            Assert.AreEqual(ShaderWarmUp.State.Continue, t.AfterRender(21114, true, 5124.2, 100.2, "b"));
            Assert.AreEqual(ShaderWarmUp.State.Continue, t.AfterRender(0, false, 5124.3, 100.3, "c"), "only one clean render after the last dirty one");
            Assert.AreEqual(-1.0, rec.time_end_s);
            Assert.AreEqual(ShaderWarmUp.State.Done, t.AfterRender(0, false, 5124.4, 100.4, "d"));
            Assert.AreEqual(4, rec.renders);
            Assert.AreEqual(2, rec.last_clean_streak);
            Assert.AreEqual(23930 + 21114, rec.error_pixels_seen);
            Assert.AreEqual(5124.1, rec.compile_seen_first_s, 1e-9);
            Assert.AreEqual(5124.2, rec.compile_seen_last_s, 1e-9);
            Assert.IsFalse(rec.compiling_at_end);
            Assert.AreEqual(5124.4, rec.time_end_s, 1e-9);
            Assert.AreEqual("d", rec.ended_local);
            Assert.AreEqual(ShaderWarmUpRecord.StatusDone, rec.status);
            Assert.AreEqual(-1, rec.look_pixels);
        }

        [Test]
        public void Tracker_TimesOutOnRealTime_NeverCompiling_KeepsMinusOne()
        {
            var rec = new ShaderWarmUpRecord { part = ShaderWarmUpRecord.Session };
            var t = new ShaderWarmUpTracker(rec, 10.0, 0.0, false, "x");
            Assert.AreEqual(ShaderWarmUp.State.Continue, t.AfterRender(5, false, 10.1, 60.0, "y"));
            Assert.AreEqual(ShaderWarmUp.State.TimedOut, t.AfterRender(5, false, 10.2, 120.0, "z"));
            Assert.AreEqual(ShaderWarmUpRecord.StatusTimedOut, rec.status);
            Assert.AreEqual(-1.0, rec.compile_seen_first_s);
            Assert.AreEqual(-1.0, rec.compile_seen_last_s);
            Assert.AreEqual(0, rec.last_clean_streak);
        }

        [Test]
        public void Record_JsonHasTheDeclaredFieldsInOrder()
        {
            string json = JsonUtility.ToJson(new ShaderWarmUpRecord());
            string[] keys = { "part", "round", "looks", "stands", "cameras", "clock", "time_start_s", "time_end_s", "started_local", "ended_local",
                              "compiling_at_start", "compile_seen_first_s", "compile_seen_last_s", "compiling_at_end", "renders", "last_clean_streak",
                              "error_pixels_seen", "look_pixels", "status" };
            int at = -1;
            foreach (var k in keys)
            {
                int i = json.IndexOf("\"" + k + "\":", StringComparison.Ordinal);
                Assert.Greater(i, at, $"{k}: {json}");
                at = i;
            }
            Assert.AreEqual("shader_warm_up.jsonl", ShaderWarmUp.RecordFile);
            foreach (var bad in new[] { "\"goal", "\"truth", "\"b\":" }) StringAssert.DoesNotContain(bad, json);
        }

        [Test]
        public void EditRecord_CarriesCyanAndTheCompileFlagPerFrame()
        {
            var r = new LookCheckEditRecord { name = "anime_f_01__NONE__2.0__seq1", n_frames = 11, cyan_pixels = 7, shaders_compiling = true };
            r.shaders_compiling_frames.AddRange(new[] { 0, 1, 2 });
            string json = JsonUtility.ToJson(r);
            StringAssert.Contains("\"cyan_pixels\":7", json);
            StringAssert.Contains("\"shaders_compiling\":true", json);
            StringAssert.Contains("\"shaders_compiling_frames\":[0,1,2]", json);
            Assert.Greater(json.IndexOf("\"shaders_compiling\"", StringComparison.Ordinal), json.IndexOf("\"pose\"", StringComparison.Ordinal));
            StringAssert.Contains("\"shaders_compiling_frames\":[]", JsonUtility.ToJson(new LookCheckEditRecord()));
        }

        [Test]
        public void SessionHelpers_DifferingPixels_FreeLayer_SessionLooks()
        {
            var a = new byte[] { 1, 2, 3, 255, 9, 9, 9, 255, 0, 0, 0, 0 };
            var b = new byte[] { 1, 2, 3, 0, 9, 8, 9, 255, 0, 0, 0, 255 };
            Assert.AreEqual(1, ShaderWarmUp.DifferingPixels(a, b), "alpha ignored");
            Assert.AreEqual(0, ShaderWarmUp.DifferingPixels(a, a));
            Assert.Throws<ArgumentException>(() => ShaderWarmUp.DifferingPixels(a, new byte[8]));
            Assert.AreEqual(31, ShaderWarmUp.FreeLayer(i => i == 8 ? "GroundTruth" : ""));
            Assert.AreEqual(29, ShaderWarmUp.FreeLayer(i => i >= 30 ? "x" + i : ""));
            Assert.AreEqual(-1, ShaderWarmUp.FreeLayer(i => "named"));
            Assert.AreEqual(8, ShaderWarmUp.FreeLayer(i => i == 8 ? "" : "named"));
            CollectionAssert.AreEqual(new[] { "sunbox_f1", "sunbox_m1", "sunbox_m_shirt_white" },
                                      ShaderWarmUp.SessionLooks(new[] { "sunbox_m1", "", null, "sunbox_m_shirt_white", "sunbox_f1", "sunbox_m1" }));
            CollectionAssert.IsEmpty(ShaderWarmUp.SessionLooks(null));
            ShaderWarmUp.ErrorShaderPixels(new[] { new Color32(0, 255, 255, 255), new Color32(255, 0, 255, 0), new Color32(0, 255, 254, 255) },
                                           out int magenta, out int cyan);
            Assert.AreEqual(1, magenta);
            Assert.AreEqual(1, cyan);
        }

        [Test]
        public void SessionWarmUp_DrawsNoSeededStream_RunsAfterThePlansAndBeforeTheLeakTest()
        {
            string warm = Project("Assets/WarehouseRobot/Scenario/Scripts/TrialRunnerV4WarmUp.cs");
            foreach (var bad in new[] { "SeededRandom", "Random.", "SetRun(", "allWorkers", "PlanRun(", "Plan(", "GoalSequence", "DrawLie" })
                StringAssert.DoesNotContain(bad, warm, $"the session warm-up must not use {bad}");
            string runner = Project("Assets/WarehouseRobot/Scenario/Scripts/TrialRunnerV4.cs");
            int run = runner.IndexOf("IEnumerator Run()", StringComparison.Ordinal);
            int folder = runner.IndexOf("SessionFolder = NewFolder(", run, StringComparison.Ordinal);
            int warmUp = runner.IndexOf("yield return WarmUpSessionLooks();", run, StringComparison.Ordinal);
            int reset = runner.IndexOf("if (!ResetForTrial(order[startRun - 1], startRun, out error))", run, StringComparison.Ordinal);
            int leak = runner.IndexOf("gt.LeakTest(", run, StringComparison.Ordinal);
            Assert.Greater(folder, run);
            Assert.Greater(warmUp, folder, "after the session folder exists (NOT_STARTED.txt)");
            Assert.Greater(reset, warmUp, "before any run's workers are spawned");
            Assert.Greater(leak, reset);
            int setup = runner.IndexOf("if (!Setup(out var error))", run, StringComparison.Ordinal);
            Assert.That(setup > run && setup < warmUp, "the plans are made in Setup, before the warm-up");
            StringAssert.Contains("session.shader_warm_up = new List<ShaderWarmUpRecord>(sessionWarmUps);", runner);
        }

        [Test]
        public void DataSplitsRole_AvatarExperiment_IsRefusedFromDataSplitsAlone()
        {
            string text = Repo("robot_vision/configs/v4/data_splits.json");
            string marked = RehearsalFixesTests.SetLookRole(text, "sunbox_m_shirt_white", DataSplitsV4.AvatarExperimentRole);
            var s = DataSplitsV4.Parse(marked);
            CollectionAssert.Contains(s.AvatarExperimentLooks, "sunbox_m_shirt_white");
            Assert.IsNull(s.GuardRun(new[] { "sunbox_m_shirt_white" }, new[] { "point_ik_01" }, false, out string error));
            StringAssert.Contains("avatar-experiment look", error);
            Assert.IsNull(s.GuardRun(new[] { "sunbox_m_shirt_white" }, new[] { "point_mixamo_02" }, true, out error));
            StringAssert.Contains("avatar-experiment look", error);
            Assert.AreEqual("development", s.GuardRun(new[] { "sunbox_m1" }, new[] { "point_ik_01" }, false, out _), "other looks unchanged");
        }
    }
}
