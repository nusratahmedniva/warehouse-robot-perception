using System;
using System.Collections.Generic;
using System.IO;
using System.Text;

namespace WarehouseHRI
{
    /// <summary>
    /// Unity side of protocol v1 (docs/protocol.md): a frame is a uint32 big-endian header length, the UTF-8 JSON
    /// header, then for each entry of header.images a uint32 big-endian length and the image bytes. Same framing
    /// as robot_vision/hri_protocol.py; the golden frame robot_vision/tests/fixtures/hri_frame_v1.frame is
    /// decoded and re-encoded byte-for-byte by the tests on both sides. The only Unity API used is JsonUtility,
    /// which may be called from background threads, so this runs on the bridge's socket threads.
    /// </summary>
    public static class HriProtocol
    {
        public const int Version = 1;
        public const int MaxHeader = 1 << 20;
        public const int MaxImage = 16 << 20;

        public class Frame
        {
            public string HeaderJson;
            public List<byte[]> Images = new List<byte[]>();
        }

        public class ProtocolException : IOException
        {
            public ProtocolException(string message) : base(message) { }
        }

        public static byte[] Encode(string headerJson, IList<byte[]> images) =>
            Encode(new UTF8Encoding(false).GetBytes(headerJson), images);

        public static byte[] Encode(byte[] header, IList<byte[]> images)
        {
            if (header.Length > MaxHeader) throw new ProtocolException($"header too large: {header.Length}");
            int total = 4 + header.Length;
            if (images != null)
                foreach (var img in images)
                {
                    if (img.Length > MaxImage) throw new ProtocolException($"image too large: {img.Length}");
                    total += 4 + img.Length;
                }

            var buf = new byte[total];
            int pos = 0;
            PutU32(buf, ref pos, (uint)header.Length);
            Buffer.BlockCopy(header, 0, buf, pos, header.Length);
            pos += header.Length;
            if (images != null)
                foreach (var img in images)
                {
                    PutU32(buf, ref pos, (uint)img.Length);
                    Buffer.BlockCopy(img, 0, buf, pos, img.Length);
                    pos += img.Length;
                }

            return buf;
        }

        static void PutU32(byte[] b, ref int pos, uint v)
        {
            b[pos++] = (byte)(v >> 24);
            b[pos++] = (byte)(v >> 16);
            b[pos++] = (byte)(v >> 8);
            b[pos++] = (byte)v;
        }

        static uint ReadU32(Stream s)
        {
            var b = ReadExact(s, 4);
            return ((uint)b[0] << 24) | ((uint)b[1] << 16) | ((uint)b[2] << 8) | b[3];
        }

        static byte[] ReadExact(Stream s, int n)
        {
            var buf = new byte[n];
            int got = 0;
            while (got < n)
            {
                int r = s.Read(buf, got, n - got);
                if (r <= 0) throw new EndOfStreamException("connection closed");
                got += r;
            }

            return buf;
        }

        /// <summary>Read one complete frame (blocking).</summary>
        public static Frame ReadFrame(Stream s)
        {
            uint hlen = ReadU32(s);
            if (hlen > MaxHeader) throw new ProtocolException($"header length {hlen} exceeds {MaxHeader}");
            var frame = new Frame { HeaderJson = new UTF8Encoding(false, true).GetString(ReadExact(s, (int)hlen)) };
            var env = Envelope.Parse(frame.HeaderJson);
            if (env.v != Version) throw new ProtocolException($"protocol version {env.v}, expected {Version}");
            if (env.images != null)
                foreach (var e in env.images)
                {
                    uint n = ReadU32(s);
                    if (n > MaxImage || n != e.bytes) throw new ProtocolException($"image '{e.name}': length {n}, header says {e.bytes}");
                    frame.Images.Add(ReadExact(s, (int)n));
                }

            return frame;
        }

        // ---------- messages (field names as on the wire; JsonUtility) ----------

        [Serializable]
        public class ImageEntry
        {
            public string name;
            public string format = "jpeg";
            public int width;
            public int height;
            public int bytes;
            /// <summary>cam360 only: elevation of the image's top and bottom edges (a horizon band of the panorama).</summary>
            public float elevation_top_deg = 90f;
            public float elevation_bottom_deg = -90f;
        }

        /// <summary>Fields every message has (plus images/ack_seq when present), parsed first to dispatch.</summary>
        [Serializable]
        public class Envelope
        {
            public string type;
            public int v;
            public int seq;
            public double t;
            public int ack_seq;
            public ImageEntry[] images;

            public static Envelope Parse(string json)
            {
                Envelope e;
                try { e = UnityEngine.JsonUtility.FromJson<Envelope>(json); }
                catch (Exception ex) { throw new ProtocolException("bad JSON header: " + ex.Message); }
                if (e == null || string.IsNullOrEmpty(e.type)) throw new ProtocolException("header has no 'type'");
                return e;
            }
        }

        [Serializable]
        public class CameraInfo
        {
            public int width, height;
            public float vfov_deg, fx, fy, cx, cy, height_m;
        }

        [Serializable]
        public class Cam360Info
        {
            public int width, height;
            public float height_m;
            public string projection = "equirect_world_aligned";
            public string plus_x_column;
        }

        [Serializable]
        public class Hello
        {
            public string type = "hello";
            public int v = Version;
            public int seq;
            public double t;
            public string client = "unity";
            public string unity_version;
            public string config_sha256;
            public string perception_mode;
            public CameraInfo gesture_camera;
            public Cam360Info cam360;
        }

        [Serializable]
        public class RobotPose
        {
            public float x, z, heading_deg, v, w_dps;
        }

        [Serializable]
        public class Observation
        {
            public string type = "observation";
            public int v = Version;
            public int seq;
            public double t;
            public float t_sim;
            public RobotPose robot = new RobotPose();
            public string state;
            public float pan_yaw_deg;
            public ImageEntry[] images = new ImageEntry[0];
        }

        [Serializable]
        public class Bye
        {
            public string type = "bye";
            public int v = Version;
            public int seq;
            public double t;
            public string reason;
        }

        /// <summary>One person seen by vision. distance_m = -1: unknown (distance_source "unknown").</summary>
        [Serializable]
        public class PersonReport
        {
            public float bearing_deg, distance_m, confidence;
            public int track_id = -1;
            public string distance_source = "";
        }

        [Serializable]
        public class GestureReport
        {
            public string command = "NONE";
            public float confidence;
            public string source = "";          // arm | mediapipe | none
            public string why = "";
            public float right_arm_deg = -999f, left_arm_deg = -999f;
        }

        [Serializable]
        public class ModelTime
        {
            public string model;
            public float ms;
        }

        [Serializable]
        public class Perception
        {
            public string type;
            public int v, seq, ack_seq;
            public double t;
            public string label;
            public PersonReport[] people = new PersonReport[0];
            /// <summary>The chosen (nearest) person; track_id -1 when there is none.</summary>
            public PersonReport target = new PersonReport();
            public GestureReport gesture = new GestureReport();
            public ModelTime[] inference = new ModelTime[0];
            public float inference_total_ms;
        }

        /// <summary>Time of one model in a reply, or NaN when that model did not run.</summary>
        public static float ModelMs(Perception p, string model)
        {
            if (p?.inference == null) return float.NaN;
            foreach (var m in p.inference) if (m.model == model) return m.ms;
            return float.NaN;
        }

        /// <summary>Gesture command from its wire name (NONE for anything unknown).</summary>
        public static GestureCommand ParseCommand(string s) =>
            Enum.TryParse<GestureCommand>(s, false, out var c) ? c : GestureCommand.NONE;
    }

    /// <summary>
    /// Round-trip delay per acknowledged observation: send time recorded when the frame is written, receive time
    /// when the reply is read, both from one Stopwatch (thread-safe). Pure class, unit-tested.
    /// </summary>
    public class RttTracker
    {
        readonly Dictionary<int, long> m_Sent = new Dictionary<int, long>();
        readonly object m_Lock = new object();
        readonly List<float> m_Samples = new List<float>();
        public readonly long TicksPerSecond;

        public RttTracker(long ticksPerSecond) => TicksPerSecond = ticksPerSecond;

        public float LastMs { get; private set; } = float.NaN;
        public int Count { get { lock (m_Lock) return m_Samples.Count; } }

        public void OnSent(int seq, long ticks)
        {
            lock (m_Lock)
            {
                m_Sent[seq] = ticks;
                if (m_Sent.Count > 1000) m_Sent.Clear(); // replies stopped; do not grow forever
            }
        }

        /// <summary>Returns the delay in ms, or NaN when the seq was never sent (or already acknowledged).</summary>
        public float OnAck(int ackSeq, long ticks)
        {
            lock (m_Lock)
            {
                if (!m_Sent.TryGetValue(ackSeq, out var sent)) return float.NaN;
                m_Sent.Remove(ackSeq);
                float ms = (float)((ticks - sent) * 1000.0 / TicksPerSecond);
                m_Samples.Add(ms);
                LastMs = ms;
                return ms;
            }
        }

        /// <summary>Mean and max since the last reset (NaN when there are no samples).</summary>
        public void Stats(out float mean, out float max, out int n)
        {
            lock (m_Lock)
            {
                n = m_Samples.Count;
                mean = float.NaN;
                max = float.NaN;
                if (n == 0) return;
                double sum = 0;
                max = float.MinValue;
                foreach (var s in m_Samples)
                {
                    sum += s;
                    if (s > max) max = s;
                }

                mean = (float)(sum / n);
            }
        }

        public void ResetStats()
        {
            lock (m_Lock) m_Samples.Clear();
        }
    }
}
