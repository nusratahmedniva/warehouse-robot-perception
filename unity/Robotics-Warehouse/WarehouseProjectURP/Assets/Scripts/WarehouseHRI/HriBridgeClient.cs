using System;
using System.Collections.Concurrent;
using System.Collections.Generic;
using System.Diagnostics;
using System.Net.Sockets;
using System.Threading;
using UnityEngine;
using UnityEngine.Rendering;
using Debug = UnityEngine.Debug;

namespace WarehouseHRI
{
    /// <summary>
    /// Step 3: TCP client to the Python bridge (protocol v1, docs/protocol.md). Sends a hello, then every
    /// send_interval_s an observation (robot pose, state, pan yaw, JPEG of the gesture camera and of the 360 deg
    /// panorama). Every frame from Python feeds the PythonLinkWatchdog; perception replies give the round-trip
    /// delay (RttTracker) and Python's inference time.
    ///
    /// SHADOW MODE in Step 3: replies are stored (LatestPerception) but RobotBrain still decides with the
    /// scripted sources. Step 4 adds vision IPersonSource / IGestureSource implementations that read them.
    /// Socket work runs on two background threads; Unity APIs are used only on the main thread.
    /// </summary>
    public class HriBridgeClient : MonoBehaviour
    {
        public bool useConfigFile = true;
        public bool linkEnabled = true;
        public string host = "127.0.0.1";
        public int port = 5050;
        public float sendIntervalS = 0.1f;
        public float connectRetryS = 1f;
        public int jpegQuality = 75;
        public int cam360SendWidth = 1024;
        public bool sendGestureImage = true;
        public bool sendCam360Image = true;
        [Tooltip("Observations waiting to be written above this count are skipped (Python too slow).")]
        public int maxQueued = 3;

        [Header("References")]
        public PythonLinkWatchdog watchdog;
        public DiffDriveRobot robot;
        public RobotBrain brain;
        public PanTiltCamera panTilt;
        public Camera360 cam360;

        static readonly Stopwatch s_Clock = Stopwatch.StartNew();

        readonly ConcurrentQueue<(HriProtocol.Frame frame, long ticks)> m_Inbox = new ConcurrentQueue<(HriProtocol.Frame, long)>();
        readonly ConcurrentQueue<(int seq, byte[] data)> m_Outbox = new ConcurrentQueue<(int, byte[])>();
        readonly AutoResetEvent m_OutSignal = new AutoResetEvent(false);
        readonly List<float> m_TrialInference = new List<float>();
        readonly Dictionary<string, (double sum, int n)> m_TrialModels = new Dictionary<string, (double, int)>();

        Thread m_IoThread, m_WriterThread;
        volatile bool m_Stop, m_Connected, m_HelloAcked;
        volatile string m_ThreadStatus = "starting";
        volatile NetworkStream m_Stream;
        TcpClient m_Client;
        int m_Seq;
        string m_HelloTemplate;
        float m_NextSend;
        Texture2D m_GestureTex, m_PanoTex;
        RenderTexture m_PanoSmall;

        public RttTracker Rtt { get; } = new RttTracker(Stopwatch.Frequency);
        public bool Connected => m_Connected && m_HelloAcked;
        public string Status => !linkEnabled ? "disabled" : m_HelloAcked ? "connected" : m_ThreadStatus;
        public int Sent { get; private set; }
        public int Received { get; private set; }
        public int Skipped { get; private set; }
        public HriProtocol.Perception LatestPerception { get; private set; }
        public string PerceptionLabel { get; private set; } = "";
        public float LastReplyTime { get; private set; } = float.NegativeInfinity;
        public float LastInferenceMs { get; private set; } = float.NaN;

        void Awake()
        {
            if (useConfigFile)
            {
                var l = HriConfig.Current.link;
                linkEnabled = l.enabled;
                host = l.host;
                port = l.port;
                sendIntervalS = l.send_interval_s;
                connectRetryS = l.connect_retry_s;
                jpegQuality = l.jpeg_quality;
                cam360SendWidth = l.cam360_send_width_px;
                sendGestureImage = l.send_gesture_image;
                sendCam360Image = l.send_cam360_image;
            }

            if (robot == null) robot = GetComponent<DiffDriveRobot>();
            if (brain == null) brain = GetComponent<RobotBrain>();
            if (watchdog == null) watchdog = GetComponent<PythonLinkWatchdog>();
        }

        void Start()
        {
            if (!linkEnabled) return;
            m_HelloTemplate = JsonUtility.ToJson(BuildHello());
            m_Stop = false;
            m_IoThread = new Thread(IoLoop) { IsBackground = true, Name = "HriBridge-IO" };
            m_WriterThread = new Thread(WriterLoop) { IsBackground = true, Name = "HriBridge-Writer" };
            m_IoThread.Start();
            m_WriterThread.Start();
        }

        HriProtocol.Hello BuildHello()
        {
            var cfg = HriConfig.Current.cameras;
            float fy = cfg.gesture_height_px * 0.5f / Mathf.Tan(cfg.gesture_vfov_deg * 0.5f * Mathf.Deg2Rad);
            int panoW = cam360SendWidth;
            return new HriProtocol.Hello
            {
                unity_version = Application.unityVersion,
                config_sha256 = HriOutput.Sha256(HriConfig.SourceText ?? JsonUtility.ToJson(HriConfig.Current)),
                perception_mode = (brain != null ? $"{brain.PersonSource?.Label} / {brain.GestureSource?.Label}" : "") +
                                  " (link in shadow mode, Step 3)",
                gesture_camera = new HriProtocol.CameraInfo
                {
                    width = cfg.gesture_width_px, height = cfg.gesture_height_px, vfov_deg = cfg.gesture_vfov_deg,
                    fx = fy, fy = fy, cx = cfg.gesture_width_px * 0.5f, cy = cfg.gesture_height_px * 0.5f,
                    height_m = cfg.gesture_height_m,
                },
                cam360 = new HriProtocol.Cam360Info
                {
                    width = panoW, height = panoW / 2, height_m = cfg.cam360_height_m, plus_x_column = Camera360.PlusXColumn,
                },
            };
        }

        // ---------- background threads (no Unity APIs) ----------

        void IoLoop()
        {
            while (!m_Stop)
            {
                TcpClient client = null;
                try
                {
                    m_ThreadStatus = $"connecting to {host}:{port}";
                    client = new TcpClient { NoDelay = true };
                    var connect = client.ConnectAsync(host, port);
                    if (!connect.Wait(TimeSpan.FromSeconds(Math.Max(0.2, connectRetryS))) || !client.Connected)
                        throw new SocketException((int)SocketError.TimedOut);
                    m_Client = client;
                    m_HelloAcked = false;
                    while (m_Outbox.TryDequeue(out _)) { }
                    Interlocked.Exchange(ref m_Seq, 0);
                    m_Stream = client.GetStream();
                    m_Connected = true;
                    m_ThreadStatus = "waiting for hello_ack";
                    int helloSeq = Interlocked.Increment(ref m_Seq);
                    var hello = JsonUtility.FromJson<HriProtocol.Hello>(m_HelloTemplate);
                    hello.seq = helloSeq;
                    hello.t = Now();
                    Enqueue(helloSeq, HriProtocol.Encode(JsonUtility.ToJson(hello), null), false);
                    while (!m_Stop)
                    {
                        var frame = HriProtocol.ReadFrame(m_Stream);
                        m_Inbox.Enqueue((frame, s_Clock.ElapsedTicks));
                    }
                }
                catch (Exception e)
                {
                    if (!m_Stop) m_ThreadStatus = "disconnected: " + (e.InnerException?.Message ?? e.Message);
                }
                finally
                {
                    m_Connected = false;
                    m_HelloAcked = false;
                    m_Stream = null;
                    try { client?.Close(); } catch (Exception) { /* closing anyway */ }
                }

                for (int i = 0; i < 10 && !m_Stop; i++) Thread.Sleep((int)(Math.Max(0.2, connectRetryS) * 100));
            }
        }

        void WriterLoop()
        {
            while (!m_Stop)
            {
                m_OutSignal.WaitOne(100);
                while (m_Outbox.TryDequeue(out var item))
                {
                    var stream = m_Stream;
                    if (stream == null || !m_Connected) continue;
                    try
                    {
                        if (item.seq > 0) Rtt.OnSent(item.seq, s_Clock.ElapsedTicks);
                        stream.Write(item.data, 0, item.data.Length);
                    }
                    catch (Exception e)
                    {
                        m_ThreadStatus = "write failed: " + e.Message;
                        try { m_Client?.Close(); } catch (Exception) { /* reader thread reconnects */ }
                    }
                }
            }
        }

        void Enqueue(int seq, byte[] data, bool trackRtt)
        {
            m_Outbox.Enqueue((trackRtt ? seq : 0, data));
            m_OutSignal.Set();
        }

        static double Now() => s_Clock.Elapsed.TotalSeconds;

        // ---------- main thread ----------

        void Update()
        {
            if (!linkEnabled) return;
            while (m_Inbox.TryDequeue(out var item)) Handle(item.frame, item.ticks);
            if (Connected && Time.time >= m_NextSend)
            {
                m_NextSend = Time.time + sendIntervalS;
                SendObservation();
            }
        }

        void Handle(HriProtocol.Frame frame, long ticks)
        {
            Received++;
            if (watchdog != null) watchdog.NotifyMessageReceived();
            HriProtocol.Envelope env;
            try { env = HriProtocol.Envelope.Parse(frame.HeaderJson); }
            catch (Exception e)
            {
                Debug.LogWarning("[WarehouseHRI] Bridge: bad message from Python: " + e.Message);
                return;
            }

            switch (env.type)
            {
                case "hello_ack":
                    m_HelloAcked = true;
                    Debug.Log($"[WarehouseHRI] Bridge connected to {host}:{port}.");
                    break;
                case "perception":
                    var p = JsonUtility.FromJson<HriProtocol.Perception>(frame.HeaderJson);
                    Rtt.OnAck(p.ack_seq, ticks);
                    LatestPerception = p;
                    PerceptionLabel = p.label ?? "";
                    LastReplyTime = Time.time;
                    LastInferenceMs = p.inference_total_ms;
                    m_TrialInference.Add(p.inference_total_ms);
                    if (p.inference != null)
                        foreach (var m in p.inference)
                        {
                            m_TrialModels.TryGetValue(m.model, out var acc);
                            m_TrialModels[m.model] = (acc.sum + m.ms, acc.n + 1);
                        }

                    break;
                case "heartbeat":
                case "command": // reserved for Step 5; ignored in Step 3
                    break;
                default:
                    Debug.LogWarning($"[WarehouseHRI] Bridge: unknown message type '{env.type}'.");
                    break;
            }
        }

        void SendObservation()
        {
            if (m_Outbox.Count >= maxQueued)
            {
                Skipped++;
                return;
            }

            var obs = new HriProtocol.Observation
            {
                seq = Interlocked.Increment(ref m_Seq),
                t = Now(),
                t_sim = Time.time,
                state = brain != null ? brain.State.ToString() : "",
                pan_yaw_deg = panTilt != null ? panTilt.CurrentYawDeg : 0f,
            };
            if (robot != null)
            {
                var p = robot.transform.position;
                obs.robot = new HriProtocol.RobotPose { x = p.x, z = p.z, heading_deg = robot.YawDeg, v = robot.V, w_dps = robot.W };
            }

            var entries = new List<HriProtocol.ImageEntry>();
            var images = new List<byte[]>();
            bool gfx = SystemInfo.graphicsDeviceType != GraphicsDeviceType.Null;
            if (gfx && sendGestureImage && panTilt != null && panTilt.Image != null)
                AddImage("gesture", panTilt.Image, ref m_GestureTex, entries, images);
            if (gfx && sendCam360Image && cam360 != null && cam360.Equirect != null)
            {
                if (m_PanoSmall == null)
                {
                    m_PanoSmall = new RenderTexture(cam360SendWidth, cam360SendWidth / 2, 0, RenderTextureFormat.ARGB32) { name = "Cam360_Send" };
                    m_PanoSmall.Create();
                }

                Graphics.Blit(cam360.Equirect, m_PanoSmall);
                AddImage("cam360", m_PanoSmall, ref m_PanoTex, entries, images);
            }

            obs.images = entries.ToArray();
            Enqueue(obs.seq, HriProtocol.Encode(JsonUtility.ToJson(obs), images), true);
            Sent++;
        }

        void AddImage(string name, RenderTexture rt, ref Texture2D tex, List<HriProtocol.ImageEntry> entries, List<byte[]> images)
        {
            if (tex == null || tex.width != rt.width || tex.height != rt.height)
                tex = new Texture2D(rt.width, rt.height, TextureFormat.RGB24, false);
            var prev = RenderTexture.active;
            RenderTexture.active = rt;
            tex.ReadPixels(new Rect(0, 0, rt.width, rt.height), 0, 0, false);
            RenderTexture.active = prev;
            byte[] jpg = tex.EncodeToJPG(jpegQuality);
            entries.Add(new HriProtocol.ImageEntry { name = name, width = rt.width, height = rt.height, bytes = jpg.Length });
            images.Add(jpg);
        }

        /// <summary>Start per-trial statistics (TrialManager calls this when a trial starts).</summary>
        public void ResetTrialStats()
        {
            Rtt.ResetStats();
            m_TrialInference.Clear();
            m_TrialModels.Clear();
        }

        /// <summary>Per-trial inference statistics: mean and max total ms, and "model:mean_ms" per model.</summary>
        public void InferenceStats(out float mean, out float max, out int n, out string perModel)
        {
            n = m_TrialInference.Count;
            mean = float.NaN;
            max = float.NaN;
            if (n > 0)
            {
                double sum = 0;
                max = float.MinValue;
                foreach (var x in m_TrialInference)
                {
                    sum += x;
                    max = Mathf.Max(max, x);
                }

                mean = (float)(sum / n);
            }

            var parts = new List<string>();
            foreach (var kv in m_TrialModels)
                parts.Add(kv.Key + ":" + HriOutput.F(kv.Value.sum / Math.Max(1, kv.Value.n), "0.###"));
            perModel = string.Join(";", parts);
        }

        void OnDestroy() => Shutdown("play mode stopped");

        void OnApplicationQuit() => Shutdown("application quit");

        void Shutdown(string reason)
        {
            if (m_IoThread == null) return;
            if (m_Connected)
            {
                // Through the writer thread, so it never interleaves with a frame being written.
                var bye = new HriProtocol.Bye { seq = Interlocked.Increment(ref m_Seq), t = Now(), reason = reason };
                Enqueue(bye.seq, HriProtocol.Encode(JsonUtility.ToJson(bye), null), false);
                for (int i = 0; i < 20 && !m_Outbox.IsEmpty; i++) Thread.Sleep(10);
            }

            m_Stop = true;
            m_OutSignal.Set();
            try { m_Client?.Close(); } catch (Exception) { /* closing anyway */ }
            m_IoThread.Join(1000);
            m_WriterThread?.Join(1000);
            m_IoThread = null;
            m_WriterThread = null;
            if (m_PanoSmall != null) m_PanoSmall.Release();
        }
    }
}
