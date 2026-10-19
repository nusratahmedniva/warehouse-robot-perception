using System.Collections.Generic;
using System.IO;
using System.Text;
using NUnit.Framework;
using UnityEngine;

namespace WarehouseHRI.Tests
{
    /// <summary>Protocol v1 framing against the golden frame written by robot_vision (Python).</summary>
    public class HriProtocolTests
    {
        static string FixturePath => Path.GetFullPath(Path.Combine(Application.dataPath, "..", "..", "..", "..",
            "robot_vision", "tests", "fixtures", "hri_frame_v1.frame"));

        static byte[] Golden()
        {
            Assume.That(File.Exists(FixturePath), "golden frame not found at " + FixturePath);
            return File.ReadAllBytes(FixturePath);
        }

        [Test]
        public void GoldenFrameDecodes()
        {
            var data = Golden();
            var frame = HriProtocol.ReadFrame(new MemoryStream(data));
            var env = HriProtocol.Envelope.Parse(frame.HeaderJson);
            Assert.AreEqual("observation", env.type);
            Assert.AreEqual(1, env.v);
            Assert.AreEqual(42, env.seq);
            Assert.AreEqual(2, env.images.Length);
            Assert.AreEqual("gesture", env.images[0].name);
            Assert.AreEqual(12, env.images[0].bytes);
            Assert.AreEqual(530, env.images[0].height);
            var obs = JsonUtility.FromJson<HriProtocol.Observation>(frame.HeaderJson);
            Assert.AreEqual(90f, obs.robot.heading_deg);
            Assert.AreEqual(-12.5f, obs.robot.w_dps);
            Assert.AreEqual("Read", obs.state);
            StringAssert.Contains("µ utf-8 check", frame.HeaderJson);
            CollectionAssert.AreEqual(new byte[] { 0xff, 0xd8, (byte)'3', (byte)'6', (byte)'0' }, frame.Images[1]);
        }

        [Test]
        public void GoldenFrameReEncodesByteForByte()
        {
            var data = Golden();
            var frame = HriProtocol.ReadFrame(new MemoryStream(data));
            CollectionAssert.AreEqual(data, HriProtocol.Encode(frame.HeaderJson, frame.Images));
            Assert.AreEqual(new byte[] { 0, 0, 1, 0x55 }, new[] { data[0], data[1], data[2], data[3] }, "big-endian length 341");
        }

        [Test]
        public void ObservationRoundTrip()
        {
            var obs = new HriProtocol.Observation
            {
                seq = 7, t = 1.25, t_sim = 3f, state = "Navigate", pan_yaw_deg = -10f,
                robot = new HriProtocol.RobotPose { x = 1f, z = 2f, heading_deg = 45f, v = 0.5f, w_dps = 3f },
                images = new[] { new HriProtocol.ImageEntry { name = "gesture", width = 2, height = 2, bytes = 3 } },
            };
            var bytes = HriProtocol.Encode(JsonUtility.ToJson(obs), new List<byte[]> { new byte[] { 1, 2, 3 } });
            var frame = HriProtocol.ReadFrame(new MemoryStream(bytes));
            var back = JsonUtility.FromJson<HriProtocol.Observation>(frame.HeaderJson);
            Assert.AreEqual(7, back.seq);
            Assert.AreEqual(45f, back.robot.heading_deg);
            CollectionAssert.AreEqual(new byte[] { 1, 2, 3 }, frame.Images[0]);
        }

        [Test]
        public void HelloWithoutImagesHasNoPayload()
        {
            var bytes = HriProtocol.Encode(JsonUtility.ToJson(new HriProtocol.Hello { seq = 1 }), null);
            var frame = HriProtocol.ReadFrame(new MemoryStream(bytes));
            Assert.AreEqual(0, frame.Images.Count);
            Assert.AreEqual("hello", HriProtocol.Envelope.Parse(frame.HeaderJson).type);
        }

        [Test]
        public void TruncatedOrInvalidFramesThrow()
        {
            var data = Golden();
            var cut = new byte[data.Length - 1];
            System.Array.Copy(data, cut, cut.Length);
            Assert.Throws<EndOfStreamException>(() => HriProtocol.ReadFrame(new MemoryStream(cut)));
            var wrongVersion = HriProtocol.Encode("{\"type\":\"hello\",\"v\":2,\"seq\":1,\"t\":0}", null);
            Assert.Throws<HriProtocol.ProtocolException>(() => HriProtocol.ReadFrame(new MemoryStream(wrongVersion)));
            var tooLong = new byte[] { 0x7f, 0xff, 0xff, 0xff };
            Assert.Throws<HriProtocol.ProtocolException>(() => HriProtocol.ReadFrame(new MemoryStream(tooLong)));
            var badLength = HriProtocol.Encode(
                "{\"type\":\"observation\",\"v\":1,\"seq\":1,\"t\":0,\"images\":[{\"name\":\"a\",\"bytes\":3}]}",
                new List<byte[]> { new byte[] { 1, 2 } });
            Assert.Throws<HriProtocol.ProtocolException>(() => HriProtocol.ReadFrame(new MemoryStream(badLength)));
        }

        [Test]
        public void PerceptionReplyParses()
        {
            const string json = "{\"type\":\"perception\",\"v\":1,\"seq\":3,\"t\":9.5,\"ack_seq\":42,\"label\":\"stub\"," +
                                "\"people\":[{\"bearing_deg\":12.5,\"distance_m\":4.2,\"confidence\":0.9,\"track_id\":3}]," +
                                "\"gesture\":{\"command\":\"FORWARD_LEFT\",\"confidence\":0.8}," +
                                "\"inference\":[{\"model\":\"yolo\",\"ms\":14.2}],\"inference_total_ms\":15.0}";
            var p = JsonUtility.FromJson<HriProtocol.Perception>(json);
            Assert.AreEqual(42, p.ack_seq);
            Assert.AreEqual(12.5f, p.people[0].bearing_deg);
            Assert.AreEqual(GestureCommand.FORWARD_LEFT, HriProtocol.ParseCommand(p.gesture.command));
            Assert.AreEqual(GestureCommand.NONE, HriProtocol.ParseCommand("MOVE"));
            Assert.AreEqual(15f, p.inference_total_ms);
        }

        [Test]
        public void RttTrackerMeasuresAcknowledgedFramesOnly()
        {
            var r = new RttTracker(1000); // 1 tick = 1 ms
            r.OnSent(1, 100);
            r.OnSent(2, 200);
            Assert.AreEqual(25f, r.OnAck(1, 125));
            Assert.IsNaN(r.OnAck(1, 130), "acknowledged twice");
            Assert.IsNaN(r.OnAck(9, 130), "never sent");
            Assert.AreEqual(75f, r.OnAck(2, 275));
            r.Stats(out var mean, out var max, out var n);
            Assert.AreEqual((50f, 75f, 2), (mean, max, n));
            r.ResetStats();
            r.Stats(out mean, out _, out n);
            Assert.AreEqual(0, n);
            Assert.IsNaN(mean);
        }

        [Test]
        public void Sha256MatchesKnownValue()
        {
            Assert.AreEqual("ba7816bf8f01cfea414140de5dae2223b00361a396177a9cb410ff61f20015ad", HriOutput.Sha256("abc"));
        }
    }
}
