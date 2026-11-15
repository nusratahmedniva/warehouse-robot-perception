using System;
using System.Collections.Generic;
using System.IO;
using System.Linq;
using NUnit.Framework;
using UnityEngine;

namespace WarehouseAvatar.Tests
{
    /// <summary>The run-once guard of the avatar experiment (Avatar/Config/experiments_ab.md section 10 item 6): every refusal and the run it allows.</summary>
    public class AvatarExperimentGuardTests
    {
        static string Project(string rel) => File.ReadAllText(Path.Combine(Application.dataPath, "..", rel));

        string m_Root;

        [SetUp]
        public void SetUp()
        {
            m_Root = Path.Combine(Path.GetTempPath(), "avatar_guard_" + Guid.NewGuid().ToString("N"));
            Directory.CreateDirectory(m_Root);
        }

        [TearDown]
        public void TearDown()
        {
            if (Directory.Exists(m_Root)) Directory.Delete(m_Root, true);
        }

        static readonly string HashA = new string('a', 64), HashB = new string('b', 64);

        static AvatarExperimentConfig Cfg() => AvatarExperimentConfig.Parse(Project(AvatarExperimentConfig.AssetPath));

        static FinalConfigV4 Finals() => new FinalConfigV4
        {
            final_plan = "p", frozen = "robot_vision/configs/v4/frozen.json", done_file = "UNITY_FINAL_DONE.json", python_run_marker = "FINAL_RUN_DONE.json",
            settings = new List<FinalSettingV4> { new FinalSettingV4 { name = "A1" }, new FinalSettingV4 { name = "B1" } },
            freeze_files = new List<string> { "unity/x/looks_ab.json", "unity/x/avatar_experiment.json" },
        };

        static string Frozen(bool frozen = true, string hashB = null) =>
            "{\"frozen\": " + (frozen ? "true" : "false") + ", \"unity_files\": {\"unity/x/looks_ab.json\": \"" + HashA + "\", \"unity/x/avatar_experiment.json\": \"" + (hashB ?? HashB) + "\"}}";

        static string Sha(string path) => path.EndsWith("looks_ab.json") ? HashA : path.EndsWith("avatar_experiment.json") ? HashB : null;

        void FinalDone(string setting)
        {
            string d = Path.Combine(m_Root, "trials_final_Task2_" + setting);
            Directory.CreateDirectory(d);
            File.WriteAllText(Path.Combine(d, "UNITY_FINAL_DONE.json"), FinalGuardV4.DoneJson(setting, 20, 20, "c", Path.GetFileName(d), "t"));
        }

        List<string> Problems(string part = AvatarExperimentConfig.Play, string frozen = null, bool subset = false) =>
            AvatarExperimentGuard.Problems(Cfg(), part, Finals(), frozen ?? Frozen(), Sha, m_Root, subset);

        [Test]
        public void Config_IsValid_WithItsOwnMarkerNames()
        {
            var c = Cfg();
            CollectionAssert.IsEmpty(c.Validate());
            Assert.AreEqual("-avatarExperiment", c.flag);
            Assert.AreEqual("AVATAR_EXPERIMENT_STARTED.json", c.started_file);
            Assert.AreEqual("AVATAR_EXPERIMENT_DONE.json", c.done_file);
            Assert.IsTrue(c.requires_finals_done);
            Assert.AreEqual("Assets/WarehouseRobot/Avatar/Config/final_v4.json", c.final_config);
            c.done_file = "FINAL_DONE.json";
            StringAssert.Contains("Python's final guard", string.Join("; ", c.Validate()));
        }

        [Test]
        public void Requested_OnlyWithTheFlag()
        {
            Assert.IsTrue(AvatarExperimentGuard.Requested(new[] { "Unity", "-avatarExperiment" }, Cfg()));
            Assert.IsFalse(AvatarExperimentGuard.Requested(new[] { "Unity", "-lookCheckLooks", "a" }, Cfg()));
        }

        [Test]
        public void AllowedOnlyAfterTheFreezeAndTheFinals()
        {
            FinalDone("A1");
            FinalDone("B1");
            CollectionAssert.IsEmpty(Problems());
            CollectionAssert.IsEmpty(Problems(AvatarExperimentConfig.Edit));
        }

        [Test]
        public void Refused_WhenNotFrozen_OrAFrozenFileChanged()
        {
            FinalDone("A1");
            FinalDone("B1");
            StringAssert.Contains("not frozen", string.Join("; ", Problems(frozen: Frozen(false))));
            StringAssert.Contains("avatar_experiment.json changed since the freeze", string.Join("; ", Problems(frozen: Frozen(true, new string('c', 64)))));
            StringAssert.Contains("not recorded in frozen.json", string.Join("; ", Problems(frozen: "{\"frozen\": true}")));
        }

        [Test]
        public void Refused_BeforeTheLastFinal()
        {
            FinalDone("A1");
            var p = string.Join("; ", Problems());
            StringAssert.Contains("final 'B1' is not done", p);
            StringAssert.DoesNotContain("final 'A1'", p);
        }

        [Test]
        public void Refused_WithALookSubset()
        {
            FinalDone("A1");
            FinalDone("B1");
            StringAssert.Contains("-lookCheckLooks is refused", string.Join("; ", Problems(subset: true)));
        }

        [Test]
        public void EachPartRunsOnce_AStartedMarkerCounts()
        {
            FinalDone("A1");
            FinalDone("B1");
            var cfg = Cfg();
            string run = Path.Combine(m_Root, "look_check_play_ab_20261201_100000");
            Directory.CreateDirectory(run);
            File.WriteAllText(Path.Combine(run, cfg.started_file), AvatarExperimentGuard.MarkerJson("started", "play", "abc", "look_check_play_ab_20261201_100000", "t"));
            StringAssert.Contains("already run: look_check_play_ab_20261201_100000/AVATAR_EXPERIMENT_STARTED.json", string.Join("; ", Problems()));
            CollectionAssert.IsEmpty(Problems(AvatarExperimentConfig.Edit), "the other part is not blocked");
            string edit = Path.Combine(m_Root, "look_check_ab_20261201_090000");
            Directory.CreateDirectory(edit);
            File.WriteAllText(Path.Combine(edit, cfg.done_file), AvatarExperimentGuard.MarkerJson("done", "edit", "abc", "look_check_ab_20261201_090000", "t", "done"));
            StringAssert.Contains("edit part was already run", string.Join("; ", Problems(AvatarExperimentConfig.Edit)));
        }

        [Test]
        public void Marker_NamesItsPart_AndNoFinalGuardKey()
        {
            string m = AvatarExperimentGuard.MarkerJson("done", "edit", "abc", "f", "t", "done");
            StringAssert.Contains("\"avatar_experiment_part\": \"edit\"", m);
            StringAssert.DoesNotContain("\"setting\"", m);
            StringAssert.DoesNotContain("\"final_setting\"", m);
            // a final guard never takes it for a final: no setting of final_v4.json matches it
            string d = Path.Combine(m_Root, "x");
            Directory.CreateDirectory(d);
            File.WriteAllText(Path.Combine(d, "UNITY_FINAL_DONE.json"), m);
            Assert.IsNull(FinalGuardV4.UnityFinalDone(m_Root, "A1", Finals()));
        }

        [Test]
        public void FinalGuardFreezeRule_IsShared_AndUnchanged()
        {
            var f = Finals();
            CollectionAssert.IsEmpty(FinalGuardV4.FreezeProblems(f, Frozen(), Sha));
            Assert.AreEqual(1, FinalGuardV4.FreezeProblems(f, Frozen(false), Sha).Count);
            Assert.IsTrue(FinalGuardV4.FreezeProblems(f, Frozen(), p => p.EndsWith("looks_ab.json") ? null : Sha(p)).Any(x => x.Contains("is missing")));
        }
    }
}
