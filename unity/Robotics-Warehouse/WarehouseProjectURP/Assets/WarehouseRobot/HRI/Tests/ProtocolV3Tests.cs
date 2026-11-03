using NUnit.Framework;
using UnityEngine;
using WarehouseHRI.V4;

namespace WarehouseHRI.Tests
{
    public class ProtocolV3Tests
    {
        [Test]
        public void ForbiddenKeys_FoundAtAnyDepthAndAnyCase()
        {
            Assert.AreEqual("truth", ProtocolV3.FindForbiddenKey("{\"a\": {\"list\": [{\"truth\": 1}]}}"));
            Assert.AreEqual("True_Gesture", ProtocolV3.FindForbiddenKey("{\"True_Gesture\": \"POINT\"}"));
            Assert.AreEqual("goal_x", ProtocolV3.FindForbiddenKey("{\"pose\": {\"goal_x\": 1.0}}"));
            Assert.AreEqual("b", ProtocolV3.FindForbiddenKey("{\"b\": 2}"));
            foreach (var k in ProtocolV3.TruthKeys) Assert.AreEqual(k, ProtocolV3.FindForbiddenKey("{\"x\": [1, {\"" + k + "\": true}]}"), k);
            foreach (var k in ProtocolV3.GoalKeys) Assert.AreEqual(k, ProtocolV3.FindForbiddenKey("{\"" + k + "\": 0}"), k);
        }

        [Test]
        public void ForbiddenKeys_ValuesAndSimilarKeysAreNotKeys()
        {
            Assert.IsNull(ProtocolV3.FindForbiddenKey("{\"state\": \"truth\", \"text\": \"goal\"}"));
            Assert.IsNull(ProtocolV3.FindForbiddenKey("{\"bearing_deg\": 1, \"is_commander\": true, \"by\": 2, \"goals\": 3}"));
            Assert.IsNull(ProtocolV3.FindForbiddenKey("{\"screen_text\": \"\\\"truth\\\": no\"}"));
            Assert.IsNull(ProtocolV3.FindForbiddenKey(""));
        }

        [Test]
        public void MissingCommandKey_NeedsFovAndHud()
        {
            Assert.IsNull(ProtocolV3.MissingCommandKey("{\"vertical_fov_deg\": -1, \"hud\": {}}"));
            Assert.AreEqual("hud", ProtocolV3.MissingCommandKey("{\"vertical_fov_deg\": -1}"));
            Assert.AreEqual("vertical_fov_deg", ProtocolV3.MissingCommandKey("{\"hud\": {}}"));
            Assert.AreEqual("hud", ProtocolV3.MissingCommandKey("{\"vertical_fov_deg\": -1, \"state\": \"hud\"}"));
        }

        [Test]
        public void Fov_MinusOneKeepsDefault_OtherValuesClamped()
        {
            Assert.IsTrue(ProtocolV3.TryResolveFov(-1f, 60f, 15f, 60f, out float f, out _));
            Assert.AreEqual(60f, f);
            Assert.IsTrue(ProtocolV3.TryResolveFov(30f, 60f, 15f, 60f, out f, out _));
            Assert.AreEqual(30f, f);
            Assert.IsTrue(ProtocolV3.TryResolveFov(5f, 60f, 15f, 60f, out f, out _));
            Assert.AreEqual(15f, f);
            Assert.IsTrue(ProtocolV3.TryResolveFov(120f, 60f, 15f, 60f, out f, out _));
            Assert.AreEqual(60f, f);
        }

        [Test]
        public void Fov_OutsideOpenInterval_IsInvalid()
        {
            foreach (float bad in new[] { 0f, 180f, -5f, 200f, float.NaN, float.PositiveInfinity })
            {
                Assert.IsFalse(ProtocolV3.TryResolveFov(bad, 60f, 15f, 60f, out _, out string error), bad.ToString());
                Assert.IsNotNull(error);
            }
        }

        [Test]
        public void Intrinsics_MatchPythonCheck_AtEveryZoom()
        {
            foreach (float fov in new[] { 60f, 45f, 22.5f, 15f })
            {
                ProtocolV3.Intrinsics(730, 530, fov, out float fx, out float fy, out float cx, out float cy);
                Assert.IsNull(ProtocolV3.IntrinsicsProblem(730, 530, fx, fy, cx, cy, fov, 0.001f), fov.ToString());
                Assert.AreEqual(365f, cx);
                Assert.AreEqual(265f, cy);
            }
            ProtocolV3.Intrinsics(730, 530, 60f, out float fx60, out _, out _, out _);
            Assert.AreEqual(458.99f, fx60, 0.01f);   // CLAUDE.md verified intrinsics at the 60 deg default
        }

        [Test]
        public void Intrinsics_OfAnotherFov_AreRejected()
        {
            ProtocolV3.Intrinsics(730, 530, 60f, out float fx, out float fy, out float cx, out float cy);
            Assert.IsNotNull(ProtocolV3.IntrinsicsProblem(730, 530, fx, fy, cx, cy, 30f, 0.001f));
            Assert.IsNotNull(ProtocolV3.IntrinsicsProblem(730, 530, fx, fy, cx, cy, 180f, 0.001f));
        }

        [Test]
        public void Hud_ParsesPythonBlock()
        {
            const string json = "{\"state\": \"ASK\", \"screen_text\": \"Which direction?\", \"commander_id\": 3, \"gesture\": \"POINT\", " +
                "\"gesture_score\": 0.82, \"gesture_raw\": \"LEFT\", \"gesture_accepted\": \"NONE\", \"point_angle_deg\": -1.0, " +
                "\"people\": [{\"id\": 3, \"bearing_deg\": -12.5, \"distance_m\": 2.1, \"is_commander\": true}, " +
                "{\"id\": 7, \"bearing_deg\": 40.0, \"distance_m\": -1, \"is_commander\": false}], " +
                "\"log\": [{\"dir\": \"in\", \"type\": \"telemetry\", \"seq\": 12, \"text\": \"v 0.50\"}, " +
                "{\"dir\": \"out\", \"type\": \"command\", \"seq\": 12, \"text\": \"ASK\"}]}";
            var hud = JsonUtility.FromJson<HudMsg>(json);
            Assert.AreEqual("ASK", hud.state);
            Assert.AreEqual(3, hud.commander_id);
            Assert.AreEqual(0.82f, hud.gesture_score, 1e-6f);
            Assert.IsTrue(hud.HasPointAngle);      // POINT: -1 is an angle here
            Assert.AreEqual(-1f, hud.point_angle_deg);
            Assert.AreEqual(2, hud.people.Count);
            Assert.IsTrue(hud.people[0].is_commander);
            Assert.AreEqual(-1f, hud.people[1].distance_m);
            Assert.AreEqual(2, hud.log.Count);
            Assert.AreEqual("out", hud.log[1].dir);
            Assert.AreEqual(12, hud.log[1].seq);
        }

        [Test]
        public void Hud_Defaults_AreTheNoneValues()
        {
            var hud = new HudMsg();
            Assert.AreEqual(-1, hud.commander_id);
            Assert.AreEqual("NONE", hud.gesture);
            Assert.IsFalse(hud.HasPointAngle);
            Assert.AreEqual(0, hud.people.Count);
        }
    }
}
