using System.Collections.Generic;
using System.IO;
using System.Linq;
using System.Text.RegularExpressions;
using NUnit.Framework;
using UnityEngine;

namespace WarehouseAvatar.Tests
{
    /// <summary>
    /// PROCEED in the look-check recordings (Avatar/Config/experiments_ab.md section 10 item 5 and addendum 1): the Edit-mode posed swing
    /// (look_check.json, LookPoser) and the Play-mode block of look_check_play_ab.json.
    /// </summary>
    public class ProceedLookCheckTests
    {
        static string Project(string rel) => File.ReadAllText(Path.Combine(Application.dataPath, "..", rel));
        static LookCheckConfig Config() => LookCheckConfig.Parse(Project("Assets/WarehouseRobot/Avatar/Config/look_check.json"));

        static readonly LookCheckHand Hand = new LookCheckHand
        {
            fist_curl_deg = 75f, fist_thumb_curl_deg = 40f, relaxed_curl_deg = 25f, relaxed_thumb_curl_deg = 10f, rest_outward = 0.12f,
        };

        readonly List<GameObject> m_Created = new List<GameObject>();

        [TearDown]
        public void TearDown()
        {
            foreach (var go in m_Created) Object.DestroyImmediate(go);
            m_Created.Clear();
        }

        [Test]
        public void LookCheckJson_HasTheDeclaredProceedTakes_AndIsValid()
        {
            var cfg = Config();
            CollectionAssert.IsEmpty(cfg.Validate());
            Assert.AreEqual(21, cfg.recording.proceed_sequence_frames, "2.0 s at 10 Hz");
            Assert.AreEqual(11, cfg.recording.sequence_frames, "the held-pose sequences are unchanged");
            var p = cfg.commands.Single(c => c.command == LookCheckConfig.Proceed);
            Assert.AreEqual(LookCheckConfig.Proceed, cfg.commands[cfg.commands.Length - 1].command, "PROCEED comes last; the other commands keep their places");
            Assert.IsTrue(p.arm_labelled);
            var seq1 = p.variants.Single(v => v.take == "seq1");
            Assert.IsTrue(seq1.sequence);
            Assert.AreEqual(new[] { 15f, -20f, 60f, 1.5f }, new[] { seq1.upper_forward_deg, seq1.swing_low_deg, seq1.swing_high_deg, seq1.swing_hz });
            var seq2 = p.variants.Single(v => v.take == "seq2");
            Assert.AreEqual(new[] { 35f, 0f, 75f, 1.5f }, new[] { seq2.upper_forward_deg, seq2.swing_low_deg, seq2.swing_high_deg, seq2.swing_hz });
            CollectionAssert.AreEqual(new[] { -20f, 0f, 20f, 40f, 60f }, p.variants.Where(v => !v.sequence).Select(v => v.ForearmDeg(0.0)).ToArray());
        }

        [Test]
        public void ForearmFollowsTheWorkersSwingLaw()
        {
            var v = Config().commands.Single(c => c.command == LookCheckConfig.Proceed).variants.Single(x => x.take == "seq1");
            Assert.AreEqual(-20f, v.ForearmDeg(0.0), 1e-4f);
            Assert.AreEqual(60f, v.ForearmDeg(1.0 / 3.0), 1e-3f, "top of the swing at half a period of 1.5 Hz");
            Assert.AreEqual(20f, v.ForearmDeg(1.0 / 6.0), 1e-3f);
            Assert.AreEqual(-20f, v.ForearmDeg(2.0 / 3.0), 1e-3f);
            // the 21 frames of a sequence cover the reader's 2.0 s window
            Assert.AreEqual(2.0, (Config().recording.proceed_sequence_frames - 1) / 10.0, 1e-9);
        }

        [Test]
        public void Validate_RefusesABadProceedTake()
        {
            var cfg = Config();
            var p = cfg.commands.Single(c => c.command == LookCheckConfig.Proceed);
            p.variants[0].swing_hz = 0f;
            p.variants[1].forearm_up = true;
            p.variants[2].swing_low_deg = 30f;
            p.variants[2].swing_high_deg = 10f;
            cfg.recording.proceed_sequence_frames = 11;
            var e = string.Join("\n", cfg.Validate());
            StringAssert.Contains("PROCEED seq1: a sequence swings", e);
            StringAssert.Contains("PROCEED seq2: forearm_up must be false", e);
            StringAssert.Contains("PROCEED f1: swing_low_deg <= swing_high_deg", e);
            StringAssert.Contains("proceed_sequence_frames", e);
        }

        [Test]
        public void Poser_ProceedPutsTheUpperArmDownAndForwardAndTheForearmAtItsAngle()
        {
            var rig = new TestRig();
            m_Created.Add(rig.Root);
            var poser = new LookPoser(rig, Hand);
            foreach (bool right in new[] { true, false })
                foreach (float phi in new[] { -20f, 0f, 40f, 75f })
                {
                    var spec = new PoseSpec { Command = LookCheckConfig.Proceed, RightArm = right, UpperForwardDeg = 15f, ForearmDeg = phi };
                    poser.Apply(spec);
                    poser.Intended(spec, out var upper, out var fore);
                    Vector3 s = rig.P(right ? HumanBodyBones.RightUpperArm : HumanBodyBones.LeftUpperArm);
                    Vector3 e = rig.P(right ? HumanBodyBones.RightLowerArm : HumanBodyBones.LeftLowerArm);
                    Vector3 w = rig.P(right ? HumanBodyBones.RightHand : HumanBodyBones.LeftHand);
                    Assert.Less(Vector3.Angle(e - s, upper), 0.5f, $"upper arm {right} {phi}");
                    Assert.Less(Vector3.Angle(w - e, fore), 0.5f, $"forearm {right} {phi}");
                    Assert.Less(upper.y, -0.9f, "upper arm points down");
                    Assert.Greater(upper.z, 0.2f, "and a little forward");
                    Assert.Greater(Vector3.Dot(upper, right ? Vector3.right : Vector3.left), 0f, "elbow out to its own side");
                    Assert.AreEqual(phi, Mathf.Asin(fore.y) * Mathf.Rad2Deg, 0.01f);
                    Assert.Greater(fore.z, 0f, "forearm toward the front");
                    Vector3 other = rig.P(right ? HumanBodyBones.LeftHand : HumanBodyBones.RightHand) - rig.P(right ? HumanBodyBones.LeftUpperArm : HumanBodyBones.RightUpperArm);
                    Assert.Less(other.normalized.y, -0.9f, "the other arm hangs");
                }
        }

        [Test]
        public void Poser_IntendedOfTheHeldPoses_IsWhatApplyAims()
        {
            var rig = new TestRig();
            m_Created.Add(rig.Root);
            var poser = new LookPoser(rig, Hand);
            foreach (var spec in new[]
            {
                new PoseSpec { Command = LookCheckConfig.Point, RightArm = true, AzimuthFrontDeg = 45f, ElevationDeg = 10f },
                new PoseSpec { Command = LookCheckConfig.Wait, RightArm = false, AzimuthFrontDeg = 20f, ElevationDeg = -22f, ForearmUp = true },
                new PoseSpec { Command = LookCheckConfig.Stop, RightArm = true, AzimuthFrontDeg = 45f, ElevationDeg = -40f, ForearmUp = true, SpreadDeg = 8f },
            })
            {
                poser.Apply(spec);
                poser.Intended(spec, out var upper, out var fore);
                bool r = spec.RightArm;
                Vector3 s = rig.P(r ? HumanBodyBones.RightUpperArm : HumanBodyBones.LeftUpperArm), e = rig.P(r ? HumanBodyBones.RightLowerArm : HumanBodyBones.LeftLowerArm);
                Vector3 w = rig.P(r ? HumanBodyBones.RightHand : HumanBodyBones.LeftHand);
                Assert.Less(Vector3.Angle(e - s, upper), 0.5f, spec.Command);
                Assert.Less(Vector3.Angle(w - e, fore), 0.5f, spec.Command);
            }
        }

        [Test]
        public void PlayConfigAB_RecordsProceedWith21FrameSequences_ThePhase2ConfigDoesNot()
        {
            string ab = Project("Assets/WarehouseRobot/Avatar/Config/look_check_play_ab.json");
            StringAssert.IsMatch("\"proceed\": \\{\"record\": true, \"sequence_frames\": 21,", ab);
            StringAssert.DoesNotContain("\"proceed\"", Project("Assets/WarehouseRobot/Avatar/Config/look_check_play.json"));
            var worker = WorkerV4Config.Parse(Project("Assets/WarehouseRobot/Avatar/Config/worker_v4.json"));
            Assert.GreaterOrEqual(worker.ClipNames(WorkerV4Config.Proceed).Count, 2, "two PROCEED variants at least, as for the other commands");
            float settle = float.Parse(Regex.Match(ab, "\"settle_after_hold_s\": ([0-9.]+)").Groups[1].Value, System.Globalization.CultureInfo.InvariantCulture);
            Assert.Greater(worker.variation.hold_s[0], settle + 20 * 0.1f + 0.3f, "a 21-frame sequence fits inside the shortest swing");
        }
    }
}
