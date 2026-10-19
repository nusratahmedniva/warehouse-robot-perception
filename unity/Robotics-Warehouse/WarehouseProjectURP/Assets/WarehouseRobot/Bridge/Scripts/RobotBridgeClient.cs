using System;
using System.Collections.Generic;
using System.Diagnostics;
using System.Threading;
using UnityEngine;
using UnityEngine.AI;
using UnityEngine.Rendering;
using Debug = UnityEngine.Debug;

namespace WarehouseRobot.Bridge
{
    /// <summary>
    /// Unity side of the Step 2 bridge (docs/protocol.md). Networking runs on BridgeConnection's threads and JPEG
    /// encoding on FrameEncoder's thread; everything that touches Unity (robot, cameras, NavMesh, GPU readbacks)
    /// happens here on the main thread. Sends hello, telemetry at telemetry_hz and both camera streams at their
    /// configured rates; applies each received command (v, omega -> DiffDriveController, pan -> PanTiltCamera,
    /// target -> NavMesh.CalculatePath); stops the robot when no command arrives for watchdog_timeout_s and when the
    /// connection drops. While the debug keyboard control is on, commands are not applied (keyboard_override).
    /// F3 shows/hides the bridge panel.
    /// </summary>
    [DisallowMultipleComponent]
    public class RobotBridgeClient : MonoBehaviour
    {
        [SerializeField] TextAsset bridgeConfig;
        [SerializeField] RobotRig robot;
        [SerializeField] bool showPanel = true;

        class StreamState
        {
            public int Busy;        // 1 while a readback or encode is in flight (set on main, cleared on encoder thread)
            public float NextTime;
            public int Requested, Encoded, Dropped;
        }

        BridgeConfig cfg;
        BridgeConnection connection;
        FrameEncoder encoder;
        RobotDebugPanel debugPanel;
        int seq;
        float nextTelemetryTime;

        // Command and watchdog state (main thread only).
        bool commandSeen;
        long lastCommandTicks;
        int lastCommandSeq = -1;
        bool watchdogStopped;
        int watchdogCount;
        CommandMsg lastCommand;

        // Navigation.
        bool hasTarget;
        Vector2 target;
        string navStatus = "none";
        readonly List<NavCorner> navCorners = new List<NavCorner>();
        NavMeshPath navPath;
        int agentTypeId;
        bool agentResolved, agentMissingLogged;

        // Round-trip delay: telemetry seq -> Stopwatch timestamp when queued.
        readonly Dictionary<int, long> sentTelemetry = new Dictionary<int, long>();
        int rttSeq = -1;
        float rttMs = -1f, rttMaxMs, rttSumMs;
        int rttCount;

        readonly StreamState stream360 = new StreamState();
        readonly StreamState streamPan = new StreamState();
        string lastLoggedError;

        /// <summary>Set by the scenario (Step 6) when the robot reached the end point; sent as reached_end_point.</summary>
        public bool ReachedEndPoint { get; set; }
        public string State { get; private set; } = "";
        public string ScreenText { get; private set; } = "";
        public bool Connected => connection != null && connection.Connected;
        public float LastRoundTripMs => rttMs;

        public void Bind(TextAsset configAsset, RobotRig robotRig)
        {
            bridgeConfig = configAsset;
            robot = robotRig;
        }

        void Awake()
        {
            try
            {
                cfg = BridgeConfig.Load(bridgeConfig);
            }
            catch (Exception ex)
            {
                Debug.LogError("[RobotBridge] " + ex.Message, this);
                enabled = false;
                return;
            }
            if (robot == null) robot = FindFirstObjectByType<RobotRig>();
            if (robot == null)
            {
                Debug.LogError("[RobotBridge] No robot (RobotRig) in the scene; bridge disabled.", this);
                enabled = false;
                return;
            }
            navPath = new NavMeshPath();
        }

        void Start()
        {
            if (cfg == null) return;
            debugPanel = robot.GetComponent<RobotDebugPanel>();
            if (robot.Drive == null || robot.PanTilt == null || robot.Omni == null)
            {
                Debug.LogError("[RobotBridge] Robot is missing its drive or cameras; bridge disabled.", this);
                enabled = false;
                return;
            }
            if (!SystemInfo.supportsAsyncGPUReadback)
                Debug.LogError("[RobotBridge] AsyncGPUReadback is not supported here; no camera frames will be sent.", this);
            robot.Omni.FrameCaptured += On360Captured;
            RenderPipelineManager.endCameraRendering += OnEndCameraRendering;
            if (cfg.Unity.auto_connect) Connect();
        }

        void OnDestroy()
        {
            if (robot != null && robot.Omni != null) robot.Omni.FrameCaptured -= On360Captured;
            RenderPipelineManager.endCameraRendering -= OnEndCameraRendering;
            Disconnect();
        }

        public void Connect()
        {
            if (connection != null || cfg == null) return;
            var s = cfg.Shared;
            connection = new BridgeConnection(s.host, s.port, s.max_header_bytes, s.max_attachment_bytes,
                cfg.Unity.reconnect_interval_s, cfg.Unity.connect_timeout_s);
            encoder = new FrameEncoder(connection);
            Debug.Log($"[RobotBridge] Connecting to {connection.Endpoint} (retry every {cfg.Unity.reconnect_interval_s:F1} s)", this);
        }

        public void Disconnect()
        {
            if (connection == null) return;
            bool wasConnected = connection.Connected;
            encoder.Dispose();
            connection.Dispose();
            encoder = null;
            connection = null;
            if (wasConnected) OnDisconnected("disconnected by Unity");
        }

        void Update()
        {
            if (connection == null) return;
            while (connection.TryDequeue(out var e))
            {
                switch (e.Kind)
                {
                    case BridgeEventKind.Connected: OnConnected(e.Text); break;
                    case BridgeEventKind.Disconnected: OnDisconnected(e.Text); break;
                    case BridgeEventKind.Message: OnMessage(e.Message); break;
                }
            }
            while (encoder.TryGetError(out var err)) LogErrorOnce("Frame encoding failed: " + err);

            CheckWatchdog();

            if (connection.Connected && Time.unscaledTime >= nextTelemetryTime)
            {
                nextTelemetryTime = Mathf.Max(nextTelemetryTime + 1f / cfg.Shared.telemetry_hz, Time.unscaledTime);
                SendTelemetry();
            }
            DrawPath();
        }

        // ---------------- connection events ----------------

        void OnConnected(string endpoint)
        {
            Debug.Log($"[RobotBridge] Connected to {endpoint}", this);
            commandSeen = false;
            watchdogStopped = false;
            sentTelemetry.Clear();
            var hello = new HelloMsg
            {
                seq = NextSeq(),
                time_s = Time.time,
                unity_version = Application.unityVersion,
                telemetry_hz = cfg.Shared.telemetry_hz,
                frame_360_hz = cfg.Shared.frame_360_hz,
                frame_pan_tilt_hz = cfg.Shared.frame_pan_tilt_hz,
                watchdog_timeout_s = cfg.Shared.watchdog_timeout_s,
            };
            connection.Send(BridgeProtocol.Frame(JsonUtility.ToJson(hello)));
        }

        void OnDisconnected(string reason)
        {
            bool wasDriving = commandSeen;
            commandSeen = false;
            watchdogStopped = false;
            State = "disconnected";
            ScreenText = "";
            if (robot != null && !KeyboardOverride) robot.Drive.Stop();
            Debug.LogWarning($"[RobotBridge] Disconnected ({reason}); " + (wasDriving ? "robot stopped (v = 0, omega = 0)." : "robot idle."), this);
        }

        void OnMessage(RawMessage msg)
        {
            switch (msg.Envelope.type)
            {
                case "command":
                    ApplyCommand(JsonUtility.FromJson<CommandMsg>(msg.HeaderJson), msg.ReceivedTicks);
                    break;
                case "error":
                    var err = JsonUtility.FromJson<ErrorMsg>(msg.HeaderJson);
                    if (err.fatal) Debug.LogError("[RobotBridge] Python reported a fatal error: " + err.error, this);
                    else Debug.LogWarning("[RobotBridge] Python rejected a message: " + err.error, this);
                    break;
                default:
                    LogErrorOnce($"Unknown message type '{msg.Envelope.type}' from Python (ignored).");
                    break;
            }
        }

        // ---------------- commands and watchdog ----------------

        bool KeyboardOverride => debugPanel != null && debugPanel.KeyboardControl;

        void ApplyCommand(CommandMsg cmd, long receivedTicks)
        {
            if (!(IsFinite(cmd.v) && IsFinite(cmd.omega) && IsFinite(cmd.pan_deg) && IsFinite(cmd.target_x) && IsFinite(cmd.target_z)))
            {
                LogErrorOnce("Command with a non-finite number ignored.");
                return;
            }
            lastCommand = cmd;
            lastCommandSeq = cmd.seq;
            lastCommandTicks = receivedTicks;
            commandSeen = true;
            if (watchdogStopped)
            {
                watchdogStopped = false;
                Debug.Log("[RobotBridge] Commands resumed; watchdog released.", this);
            }

            if (cmd.reply_to >= 0 && sentTelemetry.TryGetValue(cmd.reply_to, out long sentTicks))
            {
                sentTelemetry.Remove(cmd.reply_to);
                rttSeq = cmd.reply_to;
                rttMs = (float)((receivedTicks - sentTicks) * 1000.0 / Stopwatch.Frequency);
                rttCount++;
                rttSumMs += rttMs;
                rttMaxMs = Mathf.Max(rttMaxMs, rttMs);
            }

            if (!KeyboardOverride)
            {
                robot.Drive.SetCommand(cmd.v, cmd.omega);
                robot.PanTilt.SetPanDeg(cmd.pan_deg);
            }
            hasTarget = cmd.has_target;
            target = new Vector2(cmd.target_x, cmd.target_z);
            State = cmd.state ?? "";
            ScreenText = cmd.screen_text ?? "";
        }

        void CheckWatchdog()
        {
            if (!commandSeen || watchdogStopped || KeyboardOverride) return;
            double silent = (Stopwatch.GetTimestamp() - lastCommandTicks) / (double)Stopwatch.Frequency;
            if (silent <= cfg.Shared.watchdog_timeout_s) return;
            robot.Drive.Stop();
            watchdogStopped = true;
            watchdogCount++;
            Debug.LogWarning($"[RobotBridge] Watchdog: no command for {silent:F2} s (limit {cfg.Shared.watchdog_timeout_s:F2} s) -> v = 0, omega = 0 (stop #{watchdogCount}).", this);
        }

        // ---------------- telemetry and navigation ----------------

        void SendTelemetry()
        {
            UpdateNavPath();
            var drive = robot.Drive;
            var t = new TelemetryMsg
            {
                seq = NextSeq(),
                time_s = Time.time,
                pose = CurrentPose(),
                v = drive.V,
                omega = drive.Omega,
                v_cmd = drive.CommandedV,
                omega_cmd = drive.CommandedOmega,
                pan_deg = robot.PanTilt.PanDeg,
                collision_count = robot.Collisions != null ? robot.Collisions.Records.Count : 0,
                reached_end_point = ReachedEndPoint,
                nav_has_target = hasTarget,
                nav_target_x = target.x,
                nav_target_z = target.y,
                nav_status = navStatus,
                nav_corners = navCorners,
                last_command_seq = lastCommandSeq,
                rtt_telemetry_seq = rttSeq,
                rtt_ms = rttMs,
                watchdog_stopped = watchdogStopped,
                watchdog_count = watchdogCount,
                keyboard_override = KeyboardOverride,
            };
            connection.Send(BridgeProtocol.Frame(JsonUtility.ToJson(t)));
            long now = Stopwatch.GetTimestamp();
            sentTelemetry[t.seq] = now;
            if (sentTelemetry.Count > 200) // unanswered entries older than 10 s
            {
                var old = new List<int>();
                foreach (var kv in sentTelemetry)
                    if (now - kv.Value > 10 * Stopwatch.Frequency) old.Add(kv.Key);
                foreach (var k in old) sentTelemetry.Remove(k);
            }
        }

        PoseMsg CurrentPose()
        {
            var p = robot.transform.position;
            return new PoseMsg { x = p.x, z = p.z, yaw_deg = robot.transform.eulerAngles.y };
        }

        void UpdateNavPath()
        {
            navCorners.Clear();
            if (!hasTarget) { navStatus = "none"; return; }
            if (!ResolveAgentType()) { navStatus = "no_agent_type"; return; }
            var filter = new NavMeshQueryFilter { agentTypeID = agentTypeId, areaMask = NavMesh.AllAreas };
            float radius = cfg.Unity.nav.sample_radius_m;
            Vector3 from = robot.transform.position;
            if (!NavMesh.SamplePosition(from, out var start, radius, filter)) { navStatus = "start_off_navmesh"; return; }
            if (!NavMesh.SamplePosition(new Vector3(target.x, from.y, target.y), out var end, radius, filter)) { navStatus = "target_off_navmesh"; return; }
            NavMesh.CalculatePath(start.position, end.position, filter, navPath);
            navStatus = navPath.status == NavMeshPathStatus.PathComplete ? "complete"
                : navPath.status == NavMeshPathStatus.PathPartial ? "partial" : "invalid";
            if (navStatus == "invalid") return;
            foreach (var c in navPath.corners) navCorners.Add(new NavCorner { x = c.x, z = c.z });
        }

        bool ResolveAgentType()
        {
            if (agentResolved) return true;
            string name = cfg.Unity.nav.agent_type;
            for (int i = 0; i < NavMesh.GetSettingsCount(); i++)
            {
                int id = NavMesh.GetSettingsByIndex(i).agentTypeID;
                if (NavMesh.GetSettingsNameFromID(id) == name)
                {
                    agentTypeId = id;
                    agentResolved = true;
                    return true;
                }
            }
            if (!agentMissingLogged) Debug.LogError($"[RobotBridge] NavMesh agent type '{name}' not found (bridge_unity.json nav.agent_type).", this);
            agentMissingLogged = true;
            return false;
        }

        void DrawPath()
        {
            if (navCorners.Count == 0) return;
            float y = robot.transform.position.y + 0.05f;
            var prev = new Vector3(robot.transform.position.x, y, robot.transform.position.z);
            foreach (var c in navCorners)
            {
                var p = new Vector3(c.x, y, c.z);
                Debug.DrawLine(prev, p, Color.cyan); // Scene view / gizmos only; never in the robot's camera images
                prev = p;
            }
        }

        // ---------------- camera frames ----------------

        bool FrameDue(StreamState s, float hz)
        {
            if (connection == null || !connection.Connected || !SystemInfo.supportsAsyncGPUReadback) return false;
            if (Time.unscaledTime < s.NextTime) return false;
            if (Volatile.Read(ref s.Busy) != 0 || connection.PendingFrames >= cfg.Shared.max_pending_frames)
            {
                s.Dropped++;
                return false;
            }
            s.NextTime = Mathf.Max(s.NextTime + 1f / hz, Time.unscaledTime);
            return true;
        }

        void On360Captured(Camera360 omni)
        {
            if (!FrameDue(stream360, cfg.Shared.frame_360_hz)) return;
            var c = cfg.Unity.camera_360;
            var meta = new Frame360Msg
            {
                seq = NextSeq(),
                time_s = Time.time,
                frame_index = stream360.Requested,
                width = omni.Equirect.width,
                height = omni.Equirect.height,
                camera_height_m = omni.transform.position.y - robot.transform.position.y,
                centre_world_yaw_deg = c.centre_world_yaw_deg,
                centre_yaw_status = c.centre_yaw_status,
                pose = CurrentPose(),
            };
            RequestFrame(stream360, omni.Equirect, size => HeaderWithImage(meta, meta.attachments, size));
        }

        void OnEndCameraRendering(ScriptableRenderContext context, Camera cam)
        {
            var pan = robot != null ? robot.PanTilt : null;
            if (pan == null || !pan.Ready || cam != pan.Camera) return;
            if (!FrameDue(streamPan, cfg.Shared.frame_pan_tilt_hz)) return;
            var img = pan.Image;
            float fy = 0.5f * img.height / Mathf.Tan(0.5f * cam.fieldOfView * Mathf.Deg2Rad);
            var meta = new FramePanTiltMsg
            {
                seq = NextSeq(),
                time_s = Time.time,
                frame_index = streamPan.Requested,
                width = img.width,
                height = img.height,
                fx = fy,
                fy = fy,
                cx = 0.5f * img.width,
                cy = 0.5f * img.height,
                vertical_fov_deg = cam.fieldOfView,
                pan_deg = pan.PanDeg,
                tilt_deg = robot.Config.Unity.pan_tilt_camera.tilt_deg,
                camera_height_m = cam.transform.position.y - robot.transform.position.y,
                pose = CurrentPose(),
            };
            RequestFrame(streamPan, img, size => HeaderWithImage(meta, meta.attachments, size));
        }

        static string HeaderWithImage(object meta, List<AttachmentSpec> attachments, int size)
        {
            attachments.Clear();
            attachments.Add(new AttachmentSpec { name = "image", size = size });
            return JsonUtility.ToJson(meta); // runs on the encoder thread (ToJson is thread-safe)
        }

        void RequestFrame(StreamState s, RenderTexture rt, Func<int, string> header)
        {
            Interlocked.Exchange(ref s.Busy, 1);
            s.Requested++;
            int w = rt.width, h = rt.height;
            AsyncGPUReadback.Request(rt, 0, TextureFormat.RGBA32, req =>
            {
                if (req.hasError || encoder == null || connection == null || !connection.Connected)
                {
                    if (req.hasError) s.Dropped++;
                    Interlocked.Exchange(ref s.Busy, 0);
                    return;
                }
                encoder.Enqueue(new FrameEncoder.Job
                {
                    Rgba = req.GetData<byte>().ToArray(),
                    Width = w,
                    Height = h,
                    FlipRows = cfg.Unity.flip_rows, // EncodeArrayToJPG takes Unity's bottom-up rows, like Texture2D
                    Quality = cfg.Shared.jpeg_quality,
                    HeaderForImageSize = header,
                    Done = () => { Interlocked.Increment(ref s.Encoded); Interlocked.Exchange(ref s.Busy, 0); },
                });
            });
        }

        // ---------------- helpers and panel ----------------

        int NextSeq() => seq++;

        static bool IsFinite(float f) => !float.IsNaN(f) && !float.IsInfinity(f);

        void LogErrorOnce(string text)
        {
            if (text == lastLoggedError) return;
            lastLoggedError = text;
            Debug.LogError("[RobotBridge] " + text, this);
        }

        GUIStyle screenStyle;

        void OnGUI()
        {
            if (Event.current.type == EventType.KeyDown && Event.current.keyCode == KeyCode.F3) showPanel = !showPanel;
            if (!string.IsNullOrEmpty(ScreenText))
            {
                screenStyle ??= new GUIStyle(GUI.skin.box) { fontSize = 28, alignment = TextAnchor.MiddleCenter, wordWrap = true };
                float w = Mathf.Min(700f, Screen.width - 40f);
                GUI.Box(new Rect((Screen.width - w) / 2f, Screen.height - 110f, w, 70f), ScreenText, screenStyle);
            }
            if (!showPanel || cfg == null) return;

            const float line = 20f, pad = 8f, width = 360f;
            float x = Screen.width - width - pad, y = pad;
            GUI.Box(new Rect(x - pad, y, width + pad, 12f * line + 2f * pad), GUIContent.none);
            y += pad;
            void Line(string text)
            {
                GUI.Label(new Rect(x, y, width, line), text);
                y += line;
            }

            string status = connection == null ? "off" : connection.Connected ? "connected to " + connection.Endpoint
                : "connecting to " + connection.Endpoint + (connection.LastConnectError != null ? " (" + connection.LastConnectError + ")" : "");
            Line("Bridge: " + status);
            Line($"State: {State}");
            Line(lastCommand != null ? $"Command #{lastCommand.seq}: v {lastCommand.v:F2}  omega {lastCommand.omega:F2}  pan {lastCommand.pan_deg:F0}" : "Command: none yet");
            Line(rttCount > 0 ? $"Round trip: last {rttMs:F1} ms  mean {rttSumMs / rttCount:F1}  max {rttMaxMs:F1}  (n {rttCount})" : "Round trip: -");
            Line($"Watchdog stops: {watchdogCount}" + (watchdogStopped ? "  (holding stop)" : "") + (KeyboardOverride ? "  [keyboard override]" : ""));
            Line($"Nav: {navStatus}" + (hasTarget ? $"  target ({target.x:F1}, {target.y:F1})  corners {navCorners.Count}" : ""));
            Line($"360 frames: sent {stream360.Encoded}  dropped {stream360.Dropped}");
            Line($"Pan-tilt frames: sent {streamPan.Encoded}  dropped {streamPan.Dropped}");
            Line($"Telemetry seq {seq}   F3 hides this panel");
            y += 4f;
            if (connection == null)
            {
                if (GUI.Button(new Rect(x, y, 120f, line), "Connect")) Connect();
            }
            else if (GUI.Button(new Rect(x, y, 120f, line), "Disconnect")) Disconnect();
        }
    }
}
