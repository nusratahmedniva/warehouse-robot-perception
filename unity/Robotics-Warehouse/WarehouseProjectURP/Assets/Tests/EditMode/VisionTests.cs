using NUnit.Framework;
using UnityEngine;

namespace WarehouseHRI.Tests
{
    public class VisionTests
    {
        [Test]
        public void BearingAndDistanceGiveTheWorldPoint()
        {
            // Robot at (1, 2) heading +z: a person 3 m straight ahead, then 90 deg to the right (+x).
            var ahead = VisionGeometry.WorldPoint(1f, 2f, 0f, 0f, 3f);
            Assert.AreEqual(1f, ahead.x, 1e-4f);
            Assert.AreEqual(5f, ahead.z, 1e-4f);
            var right = VisionGeometry.WorldPoint(1f, 2f, 0f, 90f, 3f);
            Assert.AreEqual(4f, right.x, 1e-4f);
            Assert.AreEqual(2f, right.z, 1e-4f);
            // Heading +x (90): bearing -90 (robot's left) points to +z.
            var left = VisionGeometry.WorldPoint(0f, 0f, 90f, -90f, 2f);
            Assert.AreEqual(0f, left.x, 1e-4f);
            Assert.AreEqual(2f, left.z, 1e-4f);
        }

        [Test]
        public void StaleRepliesAreIgnored()
        {
            Assert.IsTrue(VisionGeometry.Fresh(10.4f, 10f, 0.5f));
            Assert.IsTrue(VisionGeometry.Fresh(10.5f, 10f, 0.5f));
            Assert.IsFalse(VisionGeometry.Fresh(10.6f, 10f, 0.5f));
        }

        [Test]
        public void SweepOrderIsSeededAndBalanced()
        {
            var a = GestureSweep.Order(1, 20);
            CollectionAssert.AreEqual(a, GestureSweep.Order(1, 20));
            CollectionAssert.AreNotEqual(a, GestureSweep.Order(2, 20));
            Assert.AreEqual(140, a.Count);
            foreach (var c in GestureSweep.Commands) Assert.AreEqual(20, a.FindAll(x => x == c).Count, c.ToString());
        }

        [Test]
        public void VisionReplyFieldsParse()
        {
            const string json = "{\"type\":\"perception\",\"v\":1,\"seq\":2,\"t\":1.0,\"ack_seq\":9,\"label\":\"vision\"," +
                                "\"people\":[{\"track_id\":3,\"bearing_deg\":-20.0,\"distance_m\":-1.0,\"distance_source\":\"unknown\",\"confidence\":0.7}]," +
                                "\"target\":{\"track_id\":3,\"bearing_deg\":-20.0,\"distance_m\":-1.0,\"distance_source\":\"unknown\",\"confidence\":0.7}," +
                                "\"gesture\":{\"command\":\"STOP\",\"confidence\":0.7,\"source\":\"mediapipe\",\"why\":\"open palm\",\"right_arm_deg\":-999.0,\"left_arm_deg\":-40.0}," +
                                "\"inference\":[{\"model\":\"yolo11s-pose/cam360\",\"ms\":30.0},{\"model\":\"mediapipe/stop\",\"ms\":12.0}],\"inference_total_ms\":50.0}";
            var p = JsonUtility.FromJson<HriProtocol.Perception>(json);
            Assert.AreEqual(3, p.target.track_id);
            Assert.AreEqual("unknown", p.people[0].distance_source);
            Assert.AreEqual(-1f, p.target.distance_m);
            Assert.AreEqual("mediapipe", p.gesture.source);
            Assert.AreEqual(GestureCommand.STOP, HriProtocol.ParseCommand(p.gesture.command));
            Assert.AreEqual(30f, HriProtocol.ModelMs(p, "yolo11s-pose/cam360"));
            Assert.IsNaN(HriProtocol.ModelMs(p, "yolo11s-pose/gesture"));
        }

        [Test]
        public void VisionModeMakesTheLinkRequired()
        {
            var c = new HriConfig();
            Assert.IsFalse(c.IsVision);
            Assert.IsFalse(c.LinkRequired);
            c.perception.mode = "vision";
            Assert.IsTrue(c.IsVision);
            Assert.IsTrue(c.LinkRequired);
        }
    }
}
