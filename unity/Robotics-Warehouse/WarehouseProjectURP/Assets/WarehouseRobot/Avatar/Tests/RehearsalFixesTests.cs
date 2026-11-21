using System;
using System.IO;
using System.Linq;
using NUnit.Framework;
using UnityEngine;

namespace WarehouseAvatar.Tests
{
    /// <summary>
    /// experiments_ab.md section 15 addendum 11 (2026-11-21): the Play look check's shader warm-up rule and error-shader pixel count, the
    /// avatar-experiment look role (refused by every trial session, kept by the avatar experiment) and the Edit-mode record's clip and pose.
    /// Nothing is run.
    /// </summary>
    public class RehearsalFixesTests
    {
        static string Project(string rel) => File.ReadAllText(Path.Combine(Application.dataPath, "..", rel));
        static string Repo(string rel) => File.ReadAllText(Path.Combine(Application.dataPath, "../../../..", rel));
        static string SplitsText() => Repo("robot_vision/configs/v4/data_splits.json");
        static string LooksAbText() => Project(ExperimentLooks.AssetPath);
        static WorkerV4Config Worker() => WorkerV4Config.Parse(Project("Assets/WarehouseRobot/Avatar/Config/worker_v4.json"));

        /// <summary>The six looks of the avatar experiment that are in no split of data_splits.json (addendum 11 item 2).</summary>
        static readonly string[] AvatarOnly =
            { "mixamo_worker", "sunbox_m2", "anime_f_01", "anime_f_02_outfit_short", "anime_f_03_bangs_parted", "cartoon_boxo_01" };

        static byte[] Pixels(params (byte r, byte g, byte b, byte a)[] px)
        {
            var buf = new byte[px.Length * 4];
            for (int i = 0; i < px.Length; i++) { buf[4 * i] = px[i].r; buf[4 * i + 1] = px[i].g; buf[4 * i + 2] = px[i].b; buf[4 * i + 3] = px[i].a; }
            return buf;
        }

        // ---------------------------------------------------------------- item 1: warm-up

        [Test]
        public void ErrorShaderPixels_CountsExactCyanAndMagentaOnly()
        {
            var buf = Pixels((0, 255, 255, 255), (0, 255, 255, 0), (255, 0, 255, 255), (1, 255, 255, 255), (0, 254, 255, 255),
                             (0, 255, 254, 255), (255, 1, 255, 255), (254, 0, 255, 255), (255, 255, 255, 255), (0, 0, 0, 255));
            ShaderWarmUp.ErrorShaderPixels(buf, out int magenta, out int cyan);
            Assert.AreEqual(2, cyan, "alpha is ignored, near-cyan is not counted");
            Assert.AreEqual(1, magenta, "near-magenta is not counted");
            ShaderWarmUp.ErrorShaderPixels(new byte[0], out magenta, out cyan);
            Assert.AreEqual(0, magenta + cyan);
            Assert.Throws<ArgumentException>(() => ShaderWarmUp.ErrorShaderPixels(new byte[7], out _, out _));
            Assert.Throws<ArgumentException>(() => ShaderWarmUp.ErrorShaderPixels(null, out _, out _));
        }

        [Test]
        public void WarmUpRule_NeedsEnoughCleanRendersAndNothingCompiling_AndFailsAfterTheLimit()
        {
            Assert.AreEqual(3, ShaderWarmUp.MinRenders);
            Assert.AreEqual(2, ShaderWarmUp.CleanRenders);
            Assert.AreEqual(120f, ShaderWarmUp.MaxSeconds);
            Assert.AreEqual(ShaderWarmUp.State.Done, ShaderWarmUp.Next(3, 2, false, 0.1f));
            Assert.AreEqual(ShaderWarmUp.State.Done, ShaderWarmUp.Next(9, 3, false, 119f));
            Assert.AreEqual(ShaderWarmUp.State.Continue, ShaderWarmUp.Next(2, 2, false, 0.1f), "too few renders");
            Assert.AreEqual(ShaderWarmUp.State.Continue, ShaderWarmUp.Next(5, 1, false, 1f), "the last render was the first clean one");
            Assert.AreEqual(ShaderWarmUp.State.Continue, ShaderWarmUp.Next(5, 0, false, 1f), "a render with cyan or magenta");
            Assert.AreEqual(ShaderWarmUp.State.Continue, ShaderWarmUp.Next(5, 5, true, 1f), "a shader still compiling");
            Assert.AreEqual(ShaderWarmUp.State.TimedOut, ShaderWarmUp.Next(500, 0, false, 120f));
            Assert.AreEqual(ShaderWarmUp.State.TimedOut, ShaderWarmUp.Next(500, 5, true, 130f));
            Assert.AreEqual(ShaderWarmUp.State.Done, ShaderWarmUp.Next(500, 5, false, 130f), "done wins over the limit");
        }

        // ---------------------------------------------------------------- item 2: the avatar-experiment role

        [Test]
        public void AvatarExperimentLooks_AreRefusedInEveryTrialSession()
        {
            var splits = DataSplitsV4.Parse(SplitsText(), LooksAbText());
            CollectionAssert.AreEquivalent(AvatarOnly, splits.AvatarExperimentLooks);
            foreach (var id in AvatarOnly)
                foreach (bool final in new[] { false, true })
                {
                    Assert.IsNull(splits.GuardRun(new[] { id }, new[] { "point_ik_01" }, final, out string error), $"{id} alone, final {final}");
                    StringAssert.Contains("avatar-experiment look", error);
                    Assert.IsNull(splits.GuardRun(new[] { "sunbox_m1", id }, new string[0], final, out error), $"{id} beside sunbox_m1, final {final}");
                    StringAssert.Contains(id, error);
                }
            // Anisha's case: the look is listed in data_splits.json (as she will list the avatar-experiment looks); still refused
            string listed = SplitsText().Replace("\"looks\": {", "\"looks\": {\n    \"anime_f_01\": \"development\",\n    \"sunbox_m2\": \"test\",");
            var withListed = DataSplitsV4.Parse(listed, LooksAbText());
            Assert.AreEqual("development", DataSplitsV4.Parse(listed).GuardRun(new[] { "anime_f_01" }, new string[0], false, out _),
                            "without the roles a listed look would pass: the finding");
            Assert.IsNull(withListed.GuardRun(new[] { "anime_f_01" }, new string[0], false, out string e1));
            StringAssert.Contains("avatar-experiment look", e1);
            Assert.IsNull(withListed.GuardRun(new[] { "sunbox_m2" }, new string[0], true, out string e2));
            StringAssert.Contains("avatar-experiment look", e2);
        }

        [Test]
        public void TheAvatarExperimentKeepsItsLooks_AndTheNavigationLooksPassAsBefore()
        {
            var f = ExperimentLooks.Parse(LooksAbText());
            var worker = Worker();
            CollectionAssert.IsEmpty(ExperimentLooks.Validate(f, worker.looks));
            var plain = DataSplitsV4.Parse(SplitsText());
            foreach (var id in f.avatar_experiment)
            {
                var look = f.looks.FirstOrDefault(l => l.id == id);
                bool listed = plain.Looks.ContainsKey(id);
                if (look == null) { Assert.IsTrue(listed, $"{id} (worker_v4.json) is in a split"); continue; }
                Assert.AreEqual(listed ? LookEntry.RoleCandidate : LookEntry.RoleAvatarExperiment, look.role, id);
            }
            foreach (var l in f.looks.Where(l => l.role == LookEntry.RoleAvatarExperiment))
                CollectionAssert.Contains(f.avatar_experiment, l.id, "every avatar-experiment look is recorded by the avatar experiment");
            var splits = DataSplitsV4.Parse(SplitsText(), LooksAbText());
            foreach (var l in f.looks.Where(l => l.navigation))
            {
                string expected = plain.Looks[l.id];
                string clip = expected == "test" ? "point_mixamo_02" : "point_ik_01";
                Assert.AreEqual(expected, splits.GuardRun(new[] { l.id }, new[] { clip }, expected == "test", out string error), $"{l.id}: {error}");
            }
            Assert.AreEqual("development", splits.GuardRun(new[] { "sunbox_m1", "sunbox_f1" }, new[] { "wait_ik_01" }, false, out _));
        }

        [Test]
        public void LooksAbRoleRules_AreValidated()
        {
            var worker = Worker();
            var f = ExperimentLooks.Parse(LooksAbText());
            f.looks.Single(l => l.id == "anime_f_01").role = "pipeline_test_only";
            f.looks.First(l => l.navigation).role = LookEntry.RoleAvatarExperiment;
            var e = ExperimentLooks.Validate(f, worker.looks);
            Assert.IsTrue(e.Any(x => x.Contains("'anime_f_01': role must be")), string.Join("; ", e));
            Assert.IsTrue(e.Any(x => x.Contains("a navigation look never has role avatar_experiment")), string.Join("; ", e));
            var g = ExperimentLooks.Parse(LooksAbText());
            g.avatar_experiment = g.avatar_experiment.Where(id => id != "sunbox_m2").ToArray();
            e = ExperimentLooks.Validate(g, worker.looks);
            Assert.IsTrue(e.Any(x => x.Contains("'sunbox_m2': role avatar_experiment but not in the avatar_experiment list")), string.Join("; ", e));
        }

        // ---------------------------------------------------------------- item 3: the Edit record

        [Test]
        public void EditRecord_HasClipEmptyAndPosePosed_AfterTheEarlierFields()
        {
            var r = new LookCheckEditRecord
            {
                name = "sunbox_m1__POINT__2.0__left_seq1", kind = "sequence", look = "sunbox_m1", family = "sunbox", role = "candidate",
                command = "POINT", arm = "left", take = "seq1", distance_m = 2f, vertical_fov_deg = 60f, n_frames = 11,
            };
            string json = JsonUtility.ToJson(r);
            StringAssert.Contains("\"clip\":\"\"", json);
            StringAssert.Contains("\"pose\":\"posed\"", json);
            string[] keys = { "name", "kind", "look", "family", "role", "command", "arm", "take", "distance_m", "vertical_fov_deg", "azimuth_front_deg",
                              "elevation_deg", "spread_deg", "forearm_up", "n_frames", "magenta_pixels", "clip", "pose" };
            int at = -1;
            foreach (var k in keys)
            {
                int i = json.IndexOf("\"" + k + "\":", StringComparison.Ordinal);
                Assert.Greater(i, at, $"{k} in order: {json}");
                at = i;
            }
        }
    }
}
