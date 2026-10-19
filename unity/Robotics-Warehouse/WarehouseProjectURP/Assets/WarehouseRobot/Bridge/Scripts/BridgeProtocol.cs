using System;
using System.Collections.Generic;
using System.IO;
using System.Text;
using UnityEngine;

namespace WarehouseRobot.Bridge
{
    /// <summary>
    /// docs/protocol.md: 4-byte big-endian header length + UTF-8 JSON header + attachments (sizes in the header).
    /// Thread-safe (JsonUtility.ToJson/FromJson are marked ThreadSafe), so the network and encoder threads use it.
    /// </summary>
    public static class BridgeProtocol
    {
        public const int Version = 2;

        /// <summary>Frame a header (whose attachments list must already match) and its attachments.</summary>
        public static byte[] Frame(string headerJson, params byte[][] attachments)
        {
            byte[] header = Encoding.UTF8.GetBytes(headerJson);
            int total = 4 + header.Length;
            foreach (var a in attachments) total += a.Length;
            var buffer = new byte[total];
            buffer[0] = (byte)(header.Length >> 24);
            buffer[1] = (byte)(header.Length >> 16);
            buffer[2] = (byte)(header.Length >> 8);
            buffer[3] = (byte)header.Length;
            Buffer.BlockCopy(header, 0, buffer, 4, header.Length);
            int offset = 4 + header.Length;
            foreach (var a in attachments)
            {
                Buffer.BlockCopy(a, 0, buffer, offset, a.Length);
                offset += a.Length;
            }
            return buffer;
        }

        /// <summary>
        /// Read one message. Returns null on a clean end of stream between messages; throws BridgeFramingException
        /// (or BridgeVersionException) when the stream cannot be trusted any more.
        /// </summary>
        public static RawMessage Read(Stream stream, int maxHeaderBytes, int maxAttachmentBytes)
        {
            var prefix = new byte[4];
            int got = ReadUpTo(stream, prefix, 4);
            if (got == 0) return null;
            if (got < 4) throw new BridgeFramingException("stream ended inside the length prefix");
            uint n = ((uint)prefix[0] << 24) | ((uint)prefix[1] << 16) | ((uint)prefix[2] << 8) | prefix[3];
            if (n == 0 || n > (uint)maxHeaderBytes)
                throw new BridgeFramingException($"header length {n} outside 1..{maxHeaderBytes}");

            var headerBytes = new byte[n];
            if (ReadUpTo(stream, headerBytes, (int)n) < n) throw new BridgeFramingException("stream ended inside a header");
            string json;
            Envelope env;
            try
            {
                json = new UTF8Encoding(false, true).GetString(headerBytes);
                env = JsonUtility.FromJson<Envelope>(json);
            }
            catch (Exception ex)
            {
                throw new BridgeFramingException("header is not valid UTF-8 JSON: " + ex.Message);
            }
            if (env == null || env.attachments == null)
                throw new BridgeFramingException("header has no attachments list");
            if (env.version != Version)
                throw new BridgeVersionException($"protocol version {env.version}, expected {Version}");

            long total = 0;
            var names = new HashSet<string>();
            foreach (var a in env.attachments)
            {
                if (a == null || string.IsNullOrEmpty(a.name) || a.size < 0 || !names.Add(a.name))
                    throw new BridgeFramingException("bad attachment entry");
                total += a.size;
            }
            if (total > maxAttachmentBytes)
                throw new BridgeFramingException($"attachments total {total} bytes > max_attachment_bytes {maxAttachmentBytes}");

            var data = new byte[env.attachments.Count][];
            for (int i = 0; i < data.Length; i++)
            {
                data[i] = new byte[env.attachments[i].size];
                if (ReadUpTo(stream, data[i], data[i].Length) < data[i].Length)
                    throw new BridgeFramingException("stream ended inside an attachment");
            }
            return new RawMessage { HeaderJson = json, Envelope = env, Attachments = data };
        }

        static int ReadUpTo(Stream stream, byte[] buffer, int count)
        {
            int read = 0;
            while (read < count)
            {
                int n = stream.Read(buffer, read, count - read);
                if (n <= 0) break;
                read += n;
            }
            return read;
        }
    }

    public class BridgeFramingException : Exception
    {
        public BridgeFramingException(string message) : base(message) { }
    }

    public class BridgeVersionException : BridgeFramingException
    {
        public BridgeVersionException(string message) : base(message) { }
    }

    public class RawMessage
    {
        public string HeaderJson;
        public Envelope Envelope;
        public byte[][] Attachments;
        /// <summary>System.Diagnostics.Stopwatch timestamp when the message was fully received.</summary>
        public long ReceivedTicks;
    }

    // ---- Message types (field names are the JSON keys in docs/protocol.md; JsonUtility keeps declaration order) ----

    [Serializable]
    public class AttachmentSpec
    {
        public string name;
        public int size;
    }

    [Serializable]
    public class Envelope
    {
        public int version = -1;
        public string type;
        public int seq;
        public List<AttachmentSpec> attachments;
    }

    [Serializable]
    public class PoseMsg
    {
        public float x;
        public float z;
        public float yaw_deg;
    }

    [Serializable]
    public class NavCorner
    {
        public float x;
        public float z;
    }

    [Serializable]
    public class HelloMsg
    {
        public int version = BridgeProtocol.Version;
        public string type = "hello";
        public int seq;
        public List<AttachmentSpec> attachments = new List<AttachmentSpec>();
        public float time_s;
        public string client = "unity";
        public string unity_version;
        public float telemetry_hz;
        public float frame_360_hz;
        public float frame_pan_tilt_hz;
        public float watchdog_timeout_s;
    }

    [Serializable]
    public class TelemetryMsg
    {
        public int version = BridgeProtocol.Version;
        public string type = "telemetry";
        public int seq;
        public List<AttachmentSpec> attachments = new List<AttachmentSpec>();
        public float time_s;
        public PoseMsg pose = new PoseMsg();
        public float v;
        public float omega;
        public float v_cmd;
        public float omega_cmd;
        public float pan_deg;
        public int collision_count;
        public bool reached_end_point;
        public bool nav_has_target;
        public float nav_target_x;
        public float nav_target_z;
        public string nav_status = "none";
        public float nav_start_snap_m = -1f;
        public float nav_target_snap_m = -1f;
        public List<NavCorner> nav_corners = new List<NavCorner>();
        public int last_command_seq = -1;
        public int rtt_telemetry_seq = -1;
        public float rtt_ms = -1f;
        public bool watchdog_stopped;
        public int watchdog_count;
        public bool keyboard_override;
        public bool estop;
        public int frames_360_sent;
        public int frames_360_dropped;
        public int frames_pan_tilt_sent;
        public int frames_pan_tilt_dropped;
    }

    [Serializable]
    public class Frame360Msg
    {
        public int version = BridgeProtocol.Version;
        public string type = "frame_360";
        public int seq;
        public List<AttachmentSpec> attachments = new List<AttachmentSpec>();
        public float time_s;
        public int frame_index;
        public int width;
        public int height;
        public float camera_height_m;
        public float centre_world_yaw_deg;
        public PoseMsg pose = new PoseMsg();
        public string encoding = "jpeg";
    }

    [Serializable]
    public class FramePanTiltMsg
    {
        public int version = BridgeProtocol.Version;
        public string type = "frame_pan_tilt";
        public int seq;
        public List<AttachmentSpec> attachments = new List<AttachmentSpec>();
        public float time_s;
        public int frame_index;
        public int width;
        public int height;
        public float fx;
        public float fy;
        public float cx;
        public float cy;
        public float vertical_fov_deg;
        public float pan_deg;
        public float tilt_deg;
        public float camera_height_m;
        public PoseMsg pose = new PoseMsg();
        public string encoding = "jpeg";
    }

    [Serializable]
    public class CommandMsg
    {
        public int version;
        public string type;
        public int seq;
        public int reply_to = -1;
        public float v;
        public float omega;
        public float pan_deg;
        public bool has_target;
        public float target_x;
        public float target_z;
        public string state = "";
        public string screen_text = "";
    }

    [Serializable]
    public class ErrorMsg
    {
        public int version;
        public string type;
        public int seq;
        public string error;
        public bool fatal;
    }
}
