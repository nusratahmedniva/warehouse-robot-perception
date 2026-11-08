using System;
using System.Collections.Generic;
using System.Globalization;
using System.IO;
using System.Linq;
using System.Reflection;
using System.Text.RegularExpressions;
using System.Threading;
using NUnit.Framework;
using UnityEditor;
using UnityEditor.Animations;
using UnityEngine;
using WarehouseHRI.V4;

namespace WarehouseAvatar.Tests
{
    /// <summary>v4 Phase 2B: worker template config, variation, gesture scheduling, hand shapes, truth.jsonl and the forbidden keys.</summary>
    public class WorkerV4Tests
    {
        static string ProjectDir => Path.GetDirectoryName(Application.dataPath);
        static string RepoRoot => Path.GetFullPath(Path.Combine(ProjectDir, "../../.."));
        const string ConfigAsset = "Assets/WarehouseRobot/Avatar/Config/worker_v4.json";
        const string ControllerAsset = "Assets/WarehouseRobot/Avatar/Animation/WorkerV4.controller";
        const string PrefabAsset = "Assets/WarehouseRobot/Avatar/Prefabs/WorkerV4.prefab";

        static WorkerV4Config LoadConfig() => WorkerV4Config.Parse(File.ReadAllText(Path.Combine(ProjectDir, ConfigAsset)));

        readonly List<GameObject> m_Created = new List<GameObject>();
        readonly List<string> m_Files = new List<string>();

        [TearDown]
        public void TearDown()
        {
            foreach (var go in m_Created) UnityEngine.Object.DestroyImmediate(go);
            m_Created.Clear();
            foreach (var f in m_Files) if (File.Exists(f)) File.Delete(f);
            m_Files.Clear();
        }

        string TempFile()
        {
            string f = Path.Combine(Path.GetTempPath(), "worker_v4_test_" + Guid.NewGuid().ToString("N") + ".jsonl");
            m_Files.Add(f);
            return f;
        }

        // ---------------------------------------------------------------- config

        [Test]
        public void Config_IsValid()
        {
            var errors = LoadConfig().Validate();
            Assert.IsEmpty(errors, string.Join("\n", errors));
        }

        [Test]
        public void Config_HasTwoToThreeVariantsPerCommand_WithUniqueNamePerCommand()
        {
            var cfg = LoadConfig();
            foreach (var cmd in WorkerV4Config.Commands)
            {
                var names = cfg.ClipNames(cmd);
                Assert.That(names.Count, Is.InRange(2, 3), cmd);
                foreach (var n in names)
                {
                    Assert.IsTrue(LookCheckConfig.IsNamePart(n), n);
                    StringAssert.StartsWith(cmd.ToLowerInvariant() + "_", n);
                }
            }
            Assert.AreEqual(cfg.clips.Length, cfg.clips.Select(c => c.name).Distinct().Count());
        }

        [Test]
        public void Config_QuestionPrompt_EqualsPythonPrompt()
        {
            var cfg = LoadConfig();
            string text = File.ReadAllText(Path.Combine(RepoRoot, cfg.paths.question_prompt_source));
            var m = Regex.Match(text, "\"prompt\"\\s*:\\s*\"([^\"]*)\"");
            Assert.IsTrue(m.Success, "no prompt in " + cfg.paths.question_prompt_source);
            Assert.AreEqual(m.Groups[1].Value, cfg.question.prompt);
        }

        [Test]
        public void Config_LooksMatchTheLookCheckLooks()
        {
            var worker = LoadConfig();
            var check = LookCheckConfig.Parse(File.ReadAllText(Path.Combine(ProjectDir, "Assets/WarehouseRobot/Avatar/Config/look_check.json")));
            foreach (var l in worker.looks)
            {
                var c = check.looks.FirstOrDefault(x => x.id == l.id);
                Assert.IsNotNull(c, l.id + " is not in look_check.json");
                Assert.AreEqual(JsonUtility.ToJson(c.sunbox), JsonUtility.ToJson(l.sunbox), l.id);
                Assert.AreEqual(c.asset, l.asset, l.id);
                Assert.AreEqual(c.kind, l.kind, l.id);
            }
            CollectionAssert.AreEquivalent(new[] { "sunbox_m1", "sunbox_f1", "sunbox_f2" }, worker.looks.Select(l => l.id).ToArray());
        }

        [Test]
        public void Config_Validate_RefusesBadValues()
        {
            var cfg = LoadConfig();
            cfg.hand_shapes.wait.ring_deg = new float[] { 40, 40, 40 };
            cfg.clips = cfg.clips.Where(c => c.name != "stop_ik_02" && c.name != "stop_ik_03").ToArray();
            cfg.truth_log.interval_s = 0.2f;
            var e = string.Join("\n", cfg.Validate());
            StringAssert.Contains("hand_shapes.wait.ring_deg must be a tight curl", e);
            StringAssert.Contains("STOP needs 2 to 3 variants", e);
            StringAssert.Contains("truth_log.interval_s", e);

            cfg = LoadConfig();
            cfg.clips[0].source_file = "";
            cfg.clips[1].name = "wait_bad";
            cfg.paths.clip_import_folder = "Assets/WarehouseRobot/Clips";
            e = string.Join("\n", cfg.Validate());
            StringAssert.Contains("a mixamo clip needs source_file", e);
            StringAssert.Contains("must start with 'point_'", e);
            StringAssert.Contains("Assets/ThirdParty/", e);
        }

        [Test]
        public void TruthLists_EqualPythonGestureDataConfig()
        {
            string text = File.ReadAllText(Path.Combine(RepoRoot, "robot_vision/configs/v4/gesture_data.json"));
            string[] List(string key)
            {
                var m = Regex.Match(text, "\"" + key + "\"\\s*:\\s*\\[([^\\]]*)\\]");
                Assert.IsTrue(m.Success, key);
                return Regex.Matches(m.Groups[1].Value, "\"([^\"]*)\"").Cast<Match>().Select(x => x.Groups[1].Value).ToArray();
            }
            CollectionAssert.AreEqual(List("commands"), TruthFormat.Commands);
            CollectionAssert.AreEqual(List("arms"), TruthFormat.Arms);
            CollectionAssert.AreEqual(List("phases"), TruthFormat.Phases);
        }

        // ---------------------------------------------------------------- Play-mode look check config (Phase 2D)

        [Serializable] class PlayVenue { public string scene; public string[] junctions; public float[] approach_bearing_deg; public float distance_tolerance_m, camera_clearance_m; public int max_pose_draws; }
        [Serializable] class PlayTakes { public int sequences_per_group, singles_per_group; public float[] sequence_point_side_azimuth_deg, single_point_side_azimuth_deg; }
        [Serializable] class PlayFile { public string[] looks; public PlayVenue venue; public PlayTakes takes; }

        static PlayFile LoadPlay() => JsonUtility.FromJson<PlayFile>(File.ReadAllText(Path.Combine(ProjectDir, "Assets/WarehouseRobot/Avatar/Config/look_check_play.json")));

        [Test]
        public void PlayConfig_DistanceBandIsPythonsApproachTolerance()
        {
            string text = File.ReadAllText(Path.Combine(RepoRoot, "robot_vision/configs/hri_control.json"));
            var m = Regex.Match(text, "\"approach_tolerance_m\"\\s*:\\s*([0-9.]+)");
            Assert.IsTrue(m.Success, "no approach_tolerance_m in hri_control.json");
            Assert.AreEqual(float.Parse(m.Groups[1].Value, CultureInfo.InvariantCulture), LoadPlay().venue.distance_tolerance_m, 1e-6f);
        }

        [Test]
        public void PlayConfig_VenueIsTheV4SceneAndItsJunctions()
        {
            var play = LoadPlay();
            Assert.AreEqual("Assets/Scenes/WarehouseRobot_v4.unity", play.venue.scene);
            Assert.IsNotNull(AssetDatabase.LoadAssetAtPath<SceneAsset>(play.venue.scene), play.venue.scene);
            string road = File.ReadAllText(Path.Combine(RepoRoot, "robot_vision/configs/roadmap.json"));
            var junctions = Regex.Matches(road, "\"(\\w+)\"\\s*:\\s*\\{[^}]*\"kind\"\\s*:\\s*\"junction\"").Cast<Match>().Select(x => x.Groups[1].Value).ToArray();
            CollectionAssert.AreEquivalent(junctions, play.venue.junctions, "every Task 2 junction, nothing else");
            Assert.That(play.venue.approach_bearing_deg, Has.Length.EqualTo(2));
            Assert.That(play.venue.approach_bearing_deg[0], Is.LessThanOrEqualTo(18f), "the band holds every measured ask (18 to 47 deg)");
            Assert.That(play.venue.approach_bearing_deg[1], Is.GreaterThanOrEqualTo(47f));
            Assert.Greater(play.venue.camera_clearance_m, 0f);
            Assert.GreaterOrEqual(play.venue.max_pose_draws, 1);
        }

        [Test]
        public void PlayConfig_TakesKeepTheLookCheckMinimums_AndEveryLookVisitsEveryJunction()
        {
            var play = LoadPlay();
            var check = LookCheckConfig.Parse(File.ReadAllText(Path.Combine(ProjectDir, "Assets/WarehouseRobot/Avatar/Config/look_check.json")));
            var t = play.takes;
            Assert.GreaterOrEqual(t.sequences_per_group, 2, "docs/look_check_v4.md: at least 2 sequences per group");
            Assert.GreaterOrEqual(t.sequences_per_group, play.venue.junctions.Length, "a sequence at every junction");
            Assert.GreaterOrEqual(t.sequences_per_group * check.recording.sequence_frames + t.singles_per_group, 10, "at least 10 frames per group");
            Assert.AreEqual(11, check.recording.sequence_frames);
            Assert.AreEqual(0f, t.sequence_point_side_azimuth_deg[0], "POINT sequence 1 sideways in the image plane");
            Assert.AreEqual(45f, t.sequence_point_side_azimuth_deg[1], "POINT sequence 2 at 45 deg toward the front");
            Assert.GreaterOrEqual(t.singles_per_group, 5, "docs/look_check_v4.md recommends about 5 singles");
            CollectionAssert.AreEquivalent(LoadConfig().looks.Select(l => l.id), play.looks);
            Assert.GreaterOrEqual(play.looks.Length, play.venue.junctions.Length, "rounds = looks: every look visits every junction");
        }

        // ---------------------------------------------------------------- variation

        [Test]
        public void Variation_IsSeededPerRunAndWorker()
        {
            var cfg = LoadConfig();
            string J(GestureParams p) => JsonUtility.ToJson(p);
            var a = GestureVariation.Draw(SeededRandom.For(1, 3, 2), cfg, "WAIT", "", null, "", 0f);
            var b = GestureVariation.Draw(SeededRandom.For(1, 3, 2), cfg, "WAIT", "", null, "", 0f);
            Assert.AreEqual(J(a), J(b));
            Assert.AreNotEqual(J(a), J(GestureVariation.Draw(SeededRandom.For(1, 3, 3), cfg, "WAIT", "", null, "", 0f)), "another worker");
            Assert.AreNotEqual(J(a), J(GestureVariation.Draw(SeededRandom.For(1, 4, 2), cfg, "WAIT", "", null, "", 0f)), "another run");
            Assert.AreNotEqual(J(a), J(GestureVariation.Draw(SeededRandom.For(2, 3, 2), cfg, "WAIT", "", null, "", 0f)), "another seed");
        }

        [Test]
        public void Variation_DrawsStayInTheirRanges_AndUseEveryClipAndArm()
        {
            var cfg = LoadConfig();
            var v = cfg.variation;
            var rng = SeededRandom.For(7, 1, 1);
            var clips = new HashSet<string>();
            var arms = new HashSet<string>();
            for (int i = 0; i < 2000; i++)
            {
                var p = GestureVariation.Draw(rng, cfg, "STOP", "", null, "", 0f);
                Assert.That(p.speed, Is.InRange(v.speed[0], v.speed[1]));
                Assert.That(p.size, Is.InRange(v.size[0], v.size[1]));
                Assert.That(p.start_delay_s, Is.InRange(v.start_delay_s[0], v.start_delay_s[1]));
                Assert.That(p.hold_s, Is.InRange(v.hold_s[0], v.hold_s[1]));
                Assert.That(p.point_elevation_deg, Is.InRange(v.point_elevation_deg[0], v.point_elevation_deg[1]));
                for (int k = 0; k < 3; k++)
                {
                    Assert.That(p.sway_amplitude_m[k], Is.InRange(v.sway_amplitude_m[0], v.sway_amplitude_m[1]));
                    Assert.That(p.sway_frequency_hz[k], Is.InRange(v.sway_frequency_hz[0], v.sway_frequency_hz[1]));
                    Assert.That(p.hold_sway_amplitude_m[k], Is.InRange(v.hold_sway_amplitude_m[0], v.hold_sway_amplitude_m[1]));
                }
                clips.Add(p.clip);
                arms.Add(p.arm);
            }
            CollectionAssert.AreEquivalent(cfg.ClipNames("STOP"), clips);
            CollectionAssert.AreEquivalent(new[] { "left", "right" }, arms);
        }

        [Test]
        public void Hold_SwayUsesTheHoldAmplitudeWhileHeld_AndBlendsWithoutAJump()
        {
            var p = new GestureParams
            {
                size = 1.1f, sway_amplitude_m = new Vector3(0.01f, 0.008f, 0.012f), hold_sway_amplitude_m = Vector3.zero,
                sway_frequency_hz = new Vector3(0.3f, 0.5f, 0.4f), sway_phase_rad = new Vector3(0.2f, 1.1f, 2.0f),
            };
            for (float t = 0f; t < 5f; t += 0.037f)
            {
                Assert.AreEqual(Vector3.zero, GestureVariation.Sway(p, t, 1f), "held (IK weight 1): no sway with a hold amplitude of 0");
                var moving = GestureVariation.Sway(p, t, 0f);
                for (int k = 0; k < 3; k++)
                {
                    float expected = p.sway_amplitude_m[k] * p.size * Mathf.Sin(2f * Mathf.PI * p.sway_frequency_hz[k] * t + p.sway_phase_rad[k]);
                    Assert.AreEqual(expected, moving[k], 1e-6f, "moving: the arm's own sway amplitude");
                    Assert.AreEqual(0.5f * expected, GestureVariation.Sway(p, t, 0.5f)[k], 1e-6f, "in between: blended");
                }
            }
            p.hold_sway_amplitude_m = new Vector3(0.002f, 0.002f, 0.002f);     // a non-zero hold amplitude stays possible
            Assert.Greater(GestureVariation.Sway(p, 0.7f, 1f).magnitude, 0f);
        }

        [Test]
        public void Hold_ConfigValues_AreRequiredAndChecked()
        {
            var cfg = LoadConfig();
            Assert.That(cfg.animation.hold_body_speed, Is.InRange(0f, 1f));
            Assert.AreEqual(2, cfg.variation.hold_sway_amplitude_m.Length);

            cfg.animation.hold_body_speed = 1.5f;
            cfg.variation.hold_sway_amplitude_m = new[] { 0f, 0.2f };
            var e = string.Join("\n", cfg.Validate());
            StringAssert.Contains("animation.hold_body_speed", e);
            StringAssert.Contains("variation.hold_sway_amplitude_m", e);

            // a file without the keys is refused (a missing key would otherwise read as 0, the still hold)
            string text = File.ReadAllText(Path.Combine(ProjectDir, ConfigAsset));
            var speedKey = new Regex("\"hold_body_speed\"\\s*:\\s*[-0-9.]+\\s*,");
            var swayKey = new Regex("\"hold_sway_amplitude_m\"\\s*:\\s*\\[[^\\]]*\\]\\s*,");
            Assert.AreEqual(1, speedKey.Matches(text).Count);
            Assert.AreEqual(1, swayKey.Matches(text).Count);
            text = swayKey.Replace(speedKey.Replace(text, ""), "");
            e = string.Join("\n", WorkerV4Config.Parse(text).Validate());
            StringAssert.Contains("animation.hold_body_speed", e);
            StringAssert.Contains("variation.hold_sway_amplitude_m", e);
        }

        [Test]
        public void Variation_PointUsesTheArmOnThePointedSide()
        {
            var cfg = LoadConfig();
            var rng = SeededRandom.For(1, 1, 1);
            var near = new HashSet<string>();
            for (int i = 0; i < 200; i++)
            {
                Assert.AreEqual("right", GestureVariation.Draw(rng, cfg, "POINT", "", null, "", 70f).arm);
                Assert.AreEqual("left", GestureVariation.Draw(rng, cfg, "POINT", "", null, "", -70f).arm);
                near.Add(GestureVariation.Draw(rng, cfg, "POINT", "", null, "", 10f).arm);
            }
            CollectionAssert.AreEquivalent(new[] { "left", "right" }, near, "near straight ahead either arm");
        }

        [Test]
        public void Variation_ForcedClipAndArm_AndAllowedClips()
        {
            var cfg = LoadConfig();
            var rng = SeededRandom.For(1, 1, 1);
            var p = GestureVariation.Draw(rng, cfg, "POINT", "point_ik_01", null, "left", 70f);
            Assert.AreEqual("point_ik_01", p.clip);
            Assert.AreEqual("left", p.arm);
            for (int i = 0; i < 100; i++)
                Assert.AreEqual("wait_ik_02", GestureVariation.Draw(rng, cfg, "WAIT", "", new[] { "wait_ik_02" }, "", 0f).clip);
            Assert.Throws<ArgumentException>(() => GestureVariation.Draw(rng, cfg, "WAIT", "stop_ik_01", null, "", 0f));
            Assert.Throws<ArgumentException>(() => GestureVariation.Draw(rng, cfg, "WAIT", "", null, "both", 0f));
        }

        // ---------------------------------------------------------------- scheduling

        static GestureTiming Timing() => new GestureTiming { StartDelay = 0.5f, Raise = 1f, Hold = 3f, Return = 0.8f };

        [Test]
        public void Scheduler_NeverStartsBeforeTheQuestionIsVisible()
        {
            var s = new GestureScheduler();
            Assert.IsTrue(s.Request(Timing(), false));
            for (float t = 0f; t < 30f; t += 0.1f) s.Tick(t);
            Assert.AreEqual(WorkerPhase.Idle, s.Phase);
            Assert.IsTrue(s.Pending);
            s.SetQuestionVisible(true, 30f);
            Assert.IsTrue(s.Tick(30f));
            Assert.AreEqual(WorkerPhase.StartDelay, s.Phase);
        }

        [Test]
        public void Scheduler_RunsThePhasesInOrderWithTheirDurations()
        {
            var s = new GestureScheduler();
            s.Request(Timing(), false);
            s.SetQuestionVisible(true, 10f);
            s.Tick(10f);
            int serial = s.Serial;
            (float t, WorkerPhase p)[] expect =
            {
                (10.49f, WorkerPhase.StartDelay), (10.51f, WorkerPhase.Gesturing), (11.49f, WorkerPhase.Gesturing), (11.51f, WorkerPhase.Holding),
                (14.49f, WorkerPhase.Holding), (14.51f, WorkerPhase.Returning), (15.29f, WorkerPhase.Returning), (15.31f, WorkerPhase.Idle),
            };
            foreach (var (t, p) in expect)
            {
                s.Tick(t);
                Assert.AreEqual(p, s.Phase, $"t = {t}");
            }
            Assert.AreEqual(serial + 4, s.Serial, "one serial step per phase change");
            Assert.IsFalse(s.Pending);
        }

        [Test]
        public void Scheduler_WeightEasesInHoldsAndEasesOut()
        {
            var s = new GestureScheduler();
            s.Request(Timing(), true);
            s.Tick(0f);
            s.Tick(0.5f);
            Assert.AreEqual(WorkerPhase.Gesturing, s.Phase);
            Assert.AreEqual(0f, s.Weight(0.5f, "smooth"), 1e-4f);
            Assert.AreEqual(0.5f, s.Weight(1.0f, "smooth"), 1e-4f);
            s.Tick(2f);
            Assert.AreEqual(1f, s.Weight(2f, "smooth"));
            s.Tick(4.9f);
            Assert.AreEqual(WorkerPhase.Returning, s.Phase);
            Assert.Less(s.Weight(5.29f, "quick"), 0.01f);
        }

        [Test]
        public void Scheduler_RefusesASecondRequestWhileBusy_AndCancelDropsAPendingOne()
        {
            var s = new GestureScheduler();
            Assert.IsTrue(s.Request(Timing(), false));
            Assert.IsFalse(s.Request(Timing(), false));
            s.Cancel();
            s.SetQuestionVisible(true, 1f);
            s.Tick(1f);
            Assert.AreEqual(WorkerPhase.Idle, s.Phase);
            Assert.IsTrue(s.Request(Timing(), false));
            s.Tick(1.1f);
            Assert.AreEqual(WorkerPhase.StartDelay, s.Phase, "the question was already visible");
        }

        [Test]
        public void Timing_MixamoUsesTheClipsPeakAndRelease_ScaledBySpeed()
        {
            var spec = new GestureClipSpec { kind = "mixamo" };
            var clip = new ClipIndexEntry { length_s = 3f, peak_s = 1.2f, release_s = 2.0f };
            var t = GestureTiming.For(spec, clip, new GestureParams { speed = 1.25f, start_delay_s = 0.4f, hold_s = 3.5f });
            Assert.AreEqual(0.96f, t.Raise, 1e-5f);
            Assert.AreEqual(0.8f, t.Return, 1e-5f);
            Assert.AreEqual(0.4f, t.StartDelay);
            Assert.AreEqual(3.5f, t.Hold);
            var p = GestureTiming.For(new GestureClipSpec { kind = "procedural", raise_s = 0.8f, return_s = 0.6f }, null, new GestureParams { speed = 0.8f });
            Assert.AreEqual(1.0f, p.Raise, 1e-5f);
            Assert.AreEqual(0.75f, p.Return, 1e-5f);
        }

        [Test]
        public void QuestionPhaseNames_AreTheTruthPhases()
        {
            foreach (WorkerPhase p in Enum.GetValues(typeof(WorkerPhase)))
                CollectionAssert.Contains(TruthFormat.Phases, WorkerPhases.Name(p));
        }

        // ---------------------------------------------------------------- hand shapes

        TestRig Rig()
        {
            var r = new TestRig();
            m_Created.Add(r.Root);
            return r;
        }

        [Test]
        public void HandShape_Wait_IndexStraight_OtherFingersTightlyCurled()
        {
            var cfg = LoadConfig();
            var rig = Rig();
            var arm = HandShaper.BuildArm(rig, true);
            var bind = HandShaper.Capture(arm);
            var toRobot = new Vector3(0f, 0f, -1f);
            HandShaper.Apply(arm, bind, cfg.hand_shapes.wait, Vector3.up, toRobot, 1f);
            Assert.Greater(HandShaper.TipRatio(arm, HandShaper.Index), 1.6f, "index extended (reader: >= 1.6)");
            foreach (int f in new[] { HandShaper.Middle, HandShaper.Ring, HandShaper.Little })
                Assert.Less(HandShaper.TipRatio(arm, f), 1.0f, $"finger {f} tightly curled (reader: curled below 1.2)");
            Assert.IsTrue(HandShaper.HandAxes(arm, out var fingerDir, out var palm));
            Assert.Greater(Vector3.Dot(fingerDir, Vector3.up), 0.99f, "fingers up");
            Assert.Greater(Vector3.Dot(palm, toRobot), 0.99f, "palm toward the robot");
        }

        [Test]
        public void HandShape_Stop_AllFingersStraightAndSpread_PalmToRobot()
        {
            var cfg = LoadConfig();
            var rig = Rig();
            var arm = HandShaper.BuildArm(rig, false);
            var bind = HandShaper.Capture(arm);
            var toRobot = new Vector3(0.3f, 0f, -1f).normalized;
            Vector3 Dir(int f) => (arm.Fingers[f][2].position - arm.Fingers[f][0].position).normalized;
            float before = Vector3.Angle(Dir(HandShaper.Index), Dir(HandShaper.Little));
            HandShaper.Apply(arm, bind, cfg.hand_shapes.stop, Vector3.up, toRobot, 1f);
            for (int f = HandShaper.Index; f <= HandShaper.Little; f++) Assert.Greater(HandShaper.TipRatio(arm, f), 1.6f, $"finger {f} extended");
            Assert.IsTrue(HandShaper.HandAxes(arm, out _, out var palm));
            Assert.Greater(Vector3.Dot(palm, toRobot), 0.99f, "palm toward the robot");
            Assert.Greater(Vector3.Angle(Dir(HandShaper.Index), Dir(HandShaper.Little)), before + 2f * cfg.hand_shapes.stop.spread_deg, "fingers spread");
        }

        [Test]
        public void HandShape_Point_IndexAlongTheArm_OthersCurled_AndWeightZeroChangesNothing()
        {
            var cfg = LoadConfig();
            var rig = Rig();
            var arm = HandShaper.BuildArm(rig, true);
            var bind = HandShaper.Capture(arm);
            var before = arm.Hand.GetComponentsInChildren<Transform>().Select(t => t.rotation).ToArray();
            HandShaper.Apply(arm, bind, cfg.hand_shapes.point, Vector3.right, Vector3.down, 0f);
            CollectionAssert.AreEqual(before, arm.Hand.GetComponentsInChildren<Transform>().Select(t => t.rotation).ToArray());
            HandShaper.Apply(arm, bind, cfg.hand_shapes.point, Vector3.right, Vector3.down, 1f);
            Assert.Greater(HandShaper.TipRatio(arm, HandShaper.Index), 1.6f);
            Assert.Less(HandShaper.TipRatio(arm, HandShaper.Ring), 1.0f);
            var index = (arm.Fingers[HandShaper.Index][2].position - arm.Fingers[HandShaper.Index][0].position).normalized;
            Assert.Greater(Vector3.Dot(index, Vector3.right), 0.99f, "index along the arm");
        }

        // ---------------------------------------------------------------- left and right hands (Phase 2D)

        /// <summary>Largest distance (m) between the left hand's joints and fingertips, mirrored across the body's
        /// sagittal plane, and the right hand's, each relative to its own wrist.</summary>
        static float MirrorGap(LookPoser.Arm left, LookPoser.Arm right, Vector3 bodyRight, out string where)
        {
            Vector3 M(Vector3 v) => v - 2f * Vector3.Dot(v, bodyRight) * bodyRight;
            float worst = 0f;
            where = "";
            for (int f = 0; f < 5; f++)
                for (int j = 0; j <= 3; j++)
                {
                    if (left.Fingers[f][Mathf.Min(j, 2)] == null || right.Fingers[f][Mathf.Min(j, 2)] == null) continue;
                    Vector3 l = j < 3 ? left.Fingers[f][j].position : HandShaper.Tip(left, f);
                    Vector3 r = j < 3 ? right.Fingers[f][j].position : HandShaper.Tip(right, f);
                    float gap = Vector3.Distance(M(l - left.Hand.position), r - right.Hand.position);
                    if (gap > worst) { worst = gap; where = $"finger {f} {(j < 3 ? "joint " + j : "tip")}"; }
                }
            return worst;
        }

        /// <summary>Shape both hands with mirror-image targets (WAIT and STOP: fingers up, palm forward; POINT: fingers out to
        /// each side and forward, palm down) and return the mirror gap.</summary>
        static float ShapedGap(WorkerV4Config cfg, string command, LookPoser.Arm left, LookPoser.Arm right, Quaternion[][] bindL,
                               Quaternion[][] bindR, Vector3 bodyRight, out string where)
        {
            Vector3 fwd = Vector3.Cross(bodyRight, Vector3.up).normalized;
            var shape = cfg.hand_shapes.For(command);
            if (command == WorkerV4Config.Point)
            {
                HandShaper.Apply(right, bindR, shape, (bodyRight + fwd).normalized, Vector3.down, 1f);
                HandShaper.Apply(left, bindL, shape, (-bodyRight + fwd).normalized, Vector3.down, 1f);
            }
            else
            {
                HandShaper.Apply(right, bindR, shape, Vector3.up, fwd, 1f);
                HandShaper.Apply(left, bindL, shape, Vector3.up, fwd, 1f);
            }
            return MirrorGap(left, right, bodyRight, out where);
        }

        [Test]
        public void HandShape_LeftIsTheMirrorOfTheRight_EvenWhenTheRigsRestPoseIsNot()
        {
            var cfg = LoadConfig();
            var rig = Rig();
            // break the rig's symmetry as the Sunbox base mesh does: the left thumb bent at its intermediate joint
            var thumb = rig.Get(HumanBodyBones.LeftThumbIntermediate);
            thumb.rotation = Quaternion.AngleAxis(40f, Vector3.up) * thumb.rotation;
            var left = HandShaper.BuildArm(rig, false);
            var right = HandShaper.BuildArm(rig, true);
            var bodyRight = Vector3.right;

            var bindL = HandShaper.Capture(left);
            var bindR = HandShaper.Capture(right);
            float broken = ShapedGap(cfg, WorkerV4Config.Wait, left, right, bindL, bindR, bodyRight, out string where);
            Assert.Greater(broken, 0.005f, "without the fix the asymmetric rest pose gives different hands (the test must see the bug)");

            foreach (var t in rig.Root.GetComponentsInChildren<Transform>()) t.localRotation = Quaternion.identity;
            thumb.rotation = Quaternion.AngleAxis(40f, Vector3.up) * thumb.rotation;
            Assert.Greater(HandShaper.MirrorRest(right, left), 0.005f, "the rest-pose correction is reported");
            bindL = HandShaper.Capture(left);
            Assert.Less(HandShaper.MirrorRest(right, left), 1e-5f, "a mirrored rest pose needs no correction");
            foreach (var cmd in WorkerV4Config.Commands)
            {
                float gap = ShapedGap(cfg, cmd, left, right, bindL, bindR, bodyRight, out where);
                Assert.Less(gap, 0.001f, $"{cmd}: left and right hands differ by {gap * 1000f:0.0} mm at {where} (before the fix {broken * 1000f:0.0} mm)");
            }
        }

        [Test]
        public void EveryLook_LeftAndRightHandShapes_AreMirrorImages()
        {
            // Phase 2D bug: WAIT with the left arm read 0.00 on every look (the Sunbox rest pose's left thumb is not the
            // mirror of the right one, so the left WAIT thumb stuck out and MediaPipe did not call it Pointing_Up).
            var cfg = LoadConfig();
            var w = AssetDatabase.LoadAssetAtPath<GameObject>(PrefabAsset).GetComponent<WorkerV4>();
            int checkedLooks = 0;
            foreach (var look in cfg.looks)
            {
                var prefab = w.lookSources.FirstOrDefault(s => s.asset == look.asset)?.prefab;
                if (prefab == null) continue;
                var inst = UnityEngine.Object.Instantiate(prefab);
                try
                {
                    var animator = look.kind == LookEntry.KindSunbox ? SunboxLookApplier.Apply(inst, look.sunbox, out _) : inst.GetComponentInChildren<Animator>();
                    HumanAvatarFix.Apply(animator);
                    var bones = new AnimatorBones(animator);
                    var left = HandShaper.BuildArm(bones, false);
                    var right = HandShaper.BuildArm(bones, true);
                    var bodyRight = Vector3.ProjectOnPlane(right.Upper.position - left.Upper.position, Vector3.up).normalized;
                    float restGap = MirrorGap(left, right, bodyRight, out string restWhere);
                    Assert.GreaterOrEqual(HandShaper.MirrorRest(right, left), 0f, look.id);        // as WorkerV4.Initialize
                    Assert.Less(MirrorGap(left, right, bodyRight, out string where), 0.001f, $"{look.id} rest pose after the fix: {where}");
                    var bindL = HandShaper.Capture(left);
                    var bindR = HandShaper.Capture(right);
                    foreach (var cmd in WorkerV4Config.Commands)
                    {
                        float gap = ShapedGap(cfg, cmd, left, right, bindL, bindR, bodyRight, out where);
                        Assert.Less(gap, 0.001f, $"{look.id} {cmd}: left and right hands differ by {gap * 1000f:0.0} mm at {where} " +
                                                 $"(rest pose before the fix: {restGap * 1000f:0.0} mm at {restWhere})");
                        for (int f = 0; f < 5; f++)
                            Assert.AreEqual(HandShaper.TipRatio(right, f), HandShaper.TipRatio(left, f), 0.02f, $"{look.id} {cmd} finger {f} tip ratio");
                    }
                    checkedLooks++;
                }
                finally { UnityEngine.Object.DestroyImmediate(inst); }
            }
            if (checkedLooks == 0) Assert.Ignore("no look asset installed (third-party, git-ignored)");
        }

        // ---------------------------------------------------------------- truth.jsonl

        static TruthRow Row(double t = 12.5, int worker = 1, string cmd = "POINT", string arm = "right", string phase = "holding", string clip = "point_mixamo_01",
                            double angle = -35.25, bool commander = true, string look = "sunbox_m1") => new TruthRow
        {
            TimeS = t, WorkerId = worker, Look = look, X = 6.25, Z = -10.0, TrueCommand = cmd, PointAngleDeg = angle, Arm = arm, Phase = phase,
            IsCommander = commander, Clip = clip,
        };

        static TruthRow Idle(double t, int worker, bool commander = false) =>
            Row(t, worker, "NONE", "none", "idle", "", -1.0, commander, worker == 1 ? "sunbox_m1" : "sunbox_f1");

        [Test]
        public void TruthLine_HasTheProtocolKeysInOrder_InvariantCulture()
        {
            var previous = Thread.CurrentThread.CurrentCulture;
            try
            {
                Thread.CurrentThread.CurrentCulture = new CultureInfo("de-DE");    // writes 6,250 if any number used the current culture
                var r = Row();
                r.HasParams = true; r.Speed = 1.1; r.Size = 0.95; r.StartDelayS = 0.4; r.HoldS = 3.2;
                string line = TruthFormat.Line(r);
                Assert.AreEqual("{\"time_s\": 12.5000, \"worker_id\": 1, \"look\": \"sunbox_m1\", \"x\": 6.250, \"z\": -10.000, \"true_command\": \"POINT\", " +
                                "\"point_angle_deg\": -35.25, \"arm\": \"right\", \"phase\": \"holding\", \"is_commander\": true, \"clip\": \"point_mixamo_01\", " +
                                "\"speed\": 1.100, \"size\": 0.950, \"start_delay_s\": 0.400, \"hold_s\": 3.200}", line);
                var keys = Regex.Matches(line, "\"([a-z_]+)\":").Cast<Match>().Select(m => m.Groups[1].Value).ToArray();
                CollectionAssert.AreEqual(TruthFormat.Keys.Concat(TruthFormat.ParamKeys).ToArray(), keys);
                StringAssert.Contains("\"point_angle_deg\": -1,", TruthFormat.Line(Idle(1.0, 1)));
            }
            finally { Thread.CurrentThread.CurrentCulture = previous; }
        }

        [Test]
        public void TruthRow_Rules()
        {
            Assert.IsNull(TruthFormat.Problem(Row()));
            Assert.IsNull(TruthFormat.Problem(Idle(1, 1)));
            Assert.IsNull(TruthFormat.Problem(Row(cmd: "WAIT", clip: "wait_ik_01", angle: -1, phase: "gesturing")));
            Assert.IsNull(TruthFormat.Problem(Row(cmd: "NONE", arm: "none", phase: "start_delay", clip: "", angle: -1)));
            StringAssert.Contains("true_command", TruthFormat.Problem(Row(cmd: "LEFT")));
            StringAssert.Contains("arm", TruthFormat.Problem(Row(arm: "both")));
            StringAssert.Contains("phase", TruthFormat.Problem(Row(phase: "pointing")));
            StringAssert.Contains("-1 unless", TruthFormat.Problem(Row(cmd: "WAIT", clip: "wait_ik_01", angle: 20)));
            StringAssert.Contains("(-180, 180]", TruthFormat.Problem(Row(angle: -180)));
            StringAssert.Contains("clip is required", TruthFormat.Problem(Row(clip: "")));
            StringAssert.Contains("clip is required", TruthFormat.Problem(Row(cmd: "NONE", arm: "none", phase: "idle", angle: -1, clip: "wait_ik_01")));
            StringAssert.Contains("arm must be 'none'", TruthFormat.Problem(Row(arm: "none")));
            StringAssert.Contains("phases gesturing", TruthFormat.Problem(Row(phase: "idle")));
            StringAssert.Contains("phases gesturing", TruthFormat.Problem(Row(cmd: "NONE", arm: "none", angle: -1, clip: "", phase: "holding")));
            StringAssert.Contains("look", TruthFormat.Problem(Row(look: "")));
            StringAssert.Contains("look", TruthFormat.Problem(Row(look: "Sunbox M1")));
            StringAssert.Contains("worker_id", TruthFormat.Problem(Row(worker: -1)));
            StringAssert.Contains("time_s", TruthFormat.Problem(Row(t: double.NaN)));
        }

        [Test]
        public void TruthWriter_WritesFrames_AndRefusesBrokenOnes()
        {
            string path = TempFile();
            using (var w = new TruthFileWriter(path))
            {
                w.WriteFrame(new[] { Idle(1.0, 1, true), Idle(1.0, 2) });
                w.WriteFrame(new[] { Idle(1.0, 1, true), Idle(1.0, 2) });        // same time_s: not written twice
                w.WriteFrame(new[] { Row(1.05, 1, look: "sunbox_m1"), Idle(1.05, 2) });
                Assert.Throws<InvalidOperationException>(() => w.WriteFrame(new[] { Idle(1.1, 1, true), Idle(1.1, 2, true) }), "two commanders");
                Assert.Throws<InvalidOperationException>(() => w.WriteFrame(new[] { Idle(1.0, 1), Idle(1.0, 2) }), "time backwards");
                Assert.Throws<InvalidOperationException>(() => w.WriteFrame(new[] { Idle(1.2, 1) }), "a worker missing");
                var other = Idle(1.2, 2);
                other.Look = "sunbox_f2";
                Assert.Throws<InvalidOperationException>(() => w.WriteFrame(new[] { Idle(1.2, 1), other }), "look changed");
                Assert.Throws<InvalidOperationException>(() => w.WriteFrame(new[] { Row(1.2, 1, clip: ""), Idle(1.2, 2) }), "clip missing");
                Assert.Throws<InvalidOperationException>(() => w.WriteFrame(new[] { Idle(1.2, 1), Idle(1.25, 2) }), "one time_s per frame");
                Assert.AreEqual(4, w.Lines);
                Assert.AreEqual(2, w.Frames);
            }
            var lines = File.ReadAllLines(path);
            Assert.AreEqual(4, lines.Length);
            Assert.IsFalse(File.ReadAllText(path).Contains("\r"), "LF line ends");
            Assert.Throws<IOException>(() => new TruthFileWriter(path).Dispose(), "CreateNew: never overwritten");
        }

        [Test]
        public void PointAngle_IsRelativeToTheRobotsForwardAxis_PositiveToTheRight()
        {
            Assert.AreEqual(90.0, TruthFormat.PointAngle(Vector3.forward, Vector3.right), 1e-4);
            Assert.AreEqual(-90.0, TruthFormat.PointAngle(Vector3.forward, Vector3.left), 1e-4);
            Assert.AreEqual(180.0, TruthFormat.PointAngle(Vector3.forward, Vector3.back), 1e-4);
            Assert.AreEqual(45.0, TruthFormat.PointAngle(Vector3.right, new Vector3(1f, 0.5f, -1f)), 1e-3, "robot facing +x; only the horizontal part counts");
        }

        [Test]
        public void DataSplits_UnlistedNamesAreReported()
        {
            string text = File.ReadAllText(Path.Combine(RepoRoot, "robot_vision/configs/v4/data_splits.json"));
            var missing = TruthFormat.Unlisted(new[] { "sunbox_m1", "placeholder_look_dev_1" }, new[] { "point_mixamo_01", "placeholder_point_dev_1", "" }, text, out bool placeholder);
            // Since 2026-11-08 the file lists the real names (AUDIT.md 14.16) and no placeholder names.
            CollectionAssert.DoesNotContain(missing, "look sunbox_m1");
            CollectionAssert.DoesNotContain(missing, "clip point_mixamo_01");
            CollectionAssert.Contains(missing, "look placeholder_look_dev_1");
            CollectionAssert.Contains(missing, "clip placeholder_point_dev_1");
            Assert.AreEqual(Regex.IsMatch(text, "\"placeholder\"\\s*:\\s*true"), placeholder);
        }

        // ---------------------------------------------------------------- forbidden keys

        // 2026-11-08: the truth.jsonl field names (look, clip, arm, phase, worker_id, ...) became forbidden keys too, so a
        // worker's truth that ever reached a Unity message is refused. Avatar data types may carry those names (they ARE
        // the truth); what they must never carry is a goal key or a Color (whose 'b' would make a message look like goal B).

        [Test]
        public void ForbiddenKeys_NoAvatarDataTypeHasAColorOrAGoalKeyFieldName()
        {
            var problems = new List<string>();
            foreach (var t in typeof(WorkerV4).Assembly.GetTypes())
            {
                if (!t.IsDefined(typeof(SerializableAttribute), false) || t.IsEnum) continue;
                foreach (var f in t.GetFields(BindingFlags.Instance | BindingFlags.Public | BindingFlags.NonPublic))
                {
                    if (f.FieldType == typeof(Color) || f.FieldType == typeof(Color32)) problems.Add($"{t.Name}.{f.Name} is a Color (serialises a key 'b')");
                    if (ProtocolV3.GoalKeys.Any(k => string.Equals(k, f.Name, StringComparison.OrdinalIgnoreCase))) problems.Add($"{t.Name}.{f.Name} is a goal key");
                }
            }
            Assert.IsEmpty(problems, string.Join("\n", problems));
        }

        [Test]
        public void ForbiddenKeys_WorkerTruthIsCaught_TheTemplateConfigIsNot()
        {
            var cfg = LoadConfig();
            var p = GestureVariation.Draw(SeededRandom.For(1, 1, 1), cfg, "POINT", "", null, "", 40f);
            Assert.IsNotNull(ProtocolV3.FindForbiddenKey(JsonUtility.ToJson(p)), "a gesture's parameters (clip, arm) are truth");
            Assert.AreEqual("worker_id", ProtocolV3.FindForbiddenKey(TruthFormat.Line(Row())), "a truth line in a message is refused at its first key after time_s");
            Assert.IsNull(ProtocolV3.FindForbiddenKey(JsonUtility.ToJson(cfg)), "the template config is not truth");
        }

        [Test]
        public void ForbiddenKeys_ATruthRowWrappedAsTruthInAMessageIsCaught()
        {
            string line = TruthFormat.Line(Row());
            Assert.AreEqual("truth", ProtocolV3.FindForbiddenKey("{\"type\": \"telemetry\", \"extra\": [{\"truth\": " + line + "}]}"));
            Assert.AreEqual("TRUE_GESTURE", ProtocolV3.FindForbiddenKey("{\"a\": {\"b2\": {\"TRUE_GESTURE\": \"POINT\"}}}"));
        }

        // ---------------------------------------------------------------- generated assets

        [Test]
        public void Controller_MatchesTheConfig()
        {
            var cfg = LoadConfig();
            Assert.AreEqual(ControllerAsset, cfg.animation.controller);
            var ctl = AssetDatabase.LoadAssetAtPath<AnimatorController>(ControllerAsset);
            Assert.IsNotNull(ctl, ControllerAsset + " missing (Tools > Warehouse v4 > Workers > Build Worker Template)");
            var layers = ctl.layers;
            Assert.AreEqual(2, layers.Length);
            Assert.AreEqual("Base", layers[0].name);
            Assert.AreEqual("Gesture", layers[1].name);
            Assert.IsTrue(layers[0].iKPass && layers[1].iKPass, "IK pass on both layers");
            Assert.AreEqual(AnimatorLayerBlendingMode.Override, layers[1].blendingMode);
            var mask = layers[1].avatarMask;
            Assert.IsNotNull(mask);
            var parts = new[] { AvatarMaskBodyPart.LeftArm, AvatarMaskBodyPart.RightArm, AvatarMaskBodyPart.LeftFingers, AvatarMaskBodyPart.RightFingers };
            for (var part = AvatarMaskBodyPart.Root; part < AvatarMaskBodyPart.LastBodyPart; part++)
                Assert.AreEqual(Array.IndexOf(parts, part) >= 0, mask.GetHumanoidBodyPartActive(part), part.ToString());
            var baseStates = layers[0].stateMachine.states.Select(s => s.state).ToList();
            Assert.AreEqual("placeholder_idle", baseStates.Single(s => s.name == "Idle").motion.name);
            Assert.AreEqual("placeholder_turn", baseStates.Single(s => s.name == "Turn").motion.name);
            var gesture = layers[1].stateMachine.states.Select(s => s.state).Where(s => s.name.StartsWith(WorkerV4.GestureStatePrefix)).ToList();
            CollectionAssert.AreEquivalent(cfg.clips.Where(c => c.IsMixamo).Select(c => WorkerV4.GestureStatePrefix + c.name), gesture.Select(s => s.name));
            foreach (var s in gesture)
            {
                Assert.AreEqual(WorkerV4.PlaceholderName(s.name.Substring(2)), s.motion.name);
                Assert.IsTrue(s.mirrorParameterActive && s.mirrorParameter == WorkerV4.ParamMirror, s.name);
                Assert.IsTrue(s.speedParameterActive && s.speedParameter == WorkerV4.ParamGestureSpeed, s.name);
            }
            var names = ctl.parameters.Select(p => p.name).ToArray();
            CollectionAssert.IsSubsetOf(new[] { WorkerV4.ParamTurning, WorkerV4.ParamMirror, WorkerV4.ParamGestureSpeed }, names);
        }

        [Test]
        public void EveryLook_HumanoidAvatarMatchesTheSceneAfterTheFix()
        {
            // Humanoid IK lands where asked only if the Avatar describes the armature as it is in the scene (the Sunbox
            // female's Avatar says scale 1 for an armature scaled 0.7312: hands stopped at 0.73 of every target).
            var cfg = LoadConfig();
            var w = AssetDatabase.LoadAssetAtPath<GameObject>(PrefabAsset).GetComponent<WorkerV4>();
            int checkedLooks = 0;
            foreach (var look in cfg.looks)
            {
                var prefab = w.lookSources.FirstOrDefault(s => s.asset == look.asset)?.prefab;
                if (prefab == null) continue;
                var inst = UnityEngine.Object.Instantiate(prefab);
                try
                {
                    var animator = look.kind == LookEntry.KindSunbox ? SunboxLookApplier.Apply(inst, look.sunbox, out _) : inst.GetComponentInChildren<Animator>();
                    HumanAvatarFix.Apply(animator);
                    Assert.IsTrue(animator.avatar.isHuman && animator.avatar.isValid, look.id);
                    CollectionAssert.IsEmpty(HumanAvatarFix.Mismatches(animator), look.id);
                    Assert.IsNotNull(animator.GetBoneTransform(HumanBodyBones.RightHand), look.id);
                    checkedLooks++;
                }
                finally { UnityEngine.Object.DestroyImmediate(inst); }
            }
            if (checkedLooks == 0) Assert.Ignore("no look asset installed (third-party, git-ignored)");
        }

        [Test]
        public void Prefab_IsOneTemplateForEveryLook()
        {
            var cfg = LoadConfig();
            var go = AssetDatabase.LoadAssetAtPath<GameObject>(PrefabAsset);
            Assert.IsNotNull(go, PrefabAsset + " missing");
            StringAssert.Contains("Worker", go.name, "collision records find workers by name");
            var w = go.GetComponent<WorkerV4>();
            Assert.IsNotNull(w);
            Assert.AreEqual(ConfigAsset, AssetDatabase.GetAssetPath(w.config));
            Assert.AreEqual(ControllerAsset, AssetDatabase.GetAssetPath(w.controller));
            Assert.IsNotNull(cfg.Look(w.lookId));
            CollectionAssert.IsSubsetOf(cfg.looks.Select(l => l.asset).Distinct(), w.lookSources.Select(s => s.asset));
            Assert.IsNotNull(go.GetComponent<CapsuleCollider>());
            Assert.AreEqual(0, go.transform.childCount, "no look is baked into the template (it is spawned from the config at Play)");
        }
    }
}
