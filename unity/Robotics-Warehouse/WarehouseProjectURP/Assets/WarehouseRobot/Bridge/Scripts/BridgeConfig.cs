using System;
using System.Collections.Generic;
using System.IO;
using UnityEngine;

namespace WarehouseRobot.Bridge
{
    /// <summary>Fields Unity uses from the shared robot_vision/configs/bridge.json (the file the Python server reads).</summary>
    [Serializable]
    public class SharedBridgeConfig
    {
        public int protocol_version;
        public string host;
        public int port;
        public float telemetry_hz;
        public float frame_360_hz;
        public float frame_pan_tilt_hz;
        public int jpeg_quality;
        public float watchdog_timeout_s;
        public int max_header_bytes;
        public int max_attachment_bytes;
        public int max_pending_frames;
    }

    [Serializable]
    public class BridgePathsConfig
    {
        public string repo_root_relative_to_unity_project;
        public string bridge_config;
    }

    [Serializable]
    public class BridgeNavConfig
    {
        public string agent_type;
        public float sample_radius_m;
    }

    [Serializable]
    public class Bridge360Config
    {
        public float centre_world_yaw_deg;
        public string centre_yaw_status;
    }

    /// <summary>Assets/WarehouseRobot/Bridge/Config/bridge_unity.json.</summary>
    [Serializable]
    public class UnityBridgeConfig
    {
        public BridgePathsConfig paths;
        public bool auto_connect;
        public float reconnect_interval_s;
        public float connect_timeout_s;
        public BridgeNavConfig nav;
        public Bridge360Config camera_360;
        public bool flip_rows;
    }

    /// <summary>The Unity bridge config plus the shared bridge.json it names. Load() throws on any problem.</summary>
    public class BridgeConfig
    {
        public SharedBridgeConfig Shared;
        public UnityBridgeConfig Unity;
        public string SharedConfigPath;

        public static BridgeConfig Load(TextAsset unityConfig)
        {
            if (unityConfig == null)
                throw new InvalidOperationException("No Unity bridge config assigned (bridge_unity.json).");
            var unity = JsonUtility.FromJson<UnityBridgeConfig>(unityConfig.text);
            if (unity == null || unity.paths == null || unity.nav == null || unity.camera_360 == null)
                throw new InvalidOperationException(unityConfig.name + ": missing section (paths, nav, camera_360).");
            if (string.IsNullOrEmpty(unity.paths.repo_root_relative_to_unity_project) || string.IsNullOrEmpty(unity.paths.bridge_config))
                throw new InvalidOperationException(unityConfig.name + ": paths.repo_root_relative_to_unity_project and paths.bridge_config are required.");

            // Unity project root = parent of Assets; the repo root and bridge.json are relative to it (no absolute paths).
            string projectRoot = Path.GetDirectoryName(Application.dataPath);
            string sharedPath = Path.GetFullPath(Path.Combine(projectRoot, unity.paths.repo_root_relative_to_unity_project, unity.paths.bridge_config));
            if (!File.Exists(sharedPath))
                throw new FileNotFoundException("Shared bridge config not found (check paths in " + unityConfig.name + ")", sharedPath);

            var cfg = new BridgeConfig
            {
                Shared = JsonUtility.FromJson<SharedBridgeConfig>(File.ReadAllText(sharedPath)),
                Unity = unity,
                SharedConfigPath = sharedPath,
            };
            var errors = cfg.Validate();
            if (errors.Count > 0)
                throw new InvalidOperationException("Invalid bridge config:\n  " + string.Join("\n  ", errors));
            return cfg;
        }

        public List<string> Validate()
        {
            var e = new List<string>();
            void Positive(string name, float value)
            {
                if (!(value > 0f)) e.Add(name + " must be > 0 (got " + value + ")");
            }

            var s = Shared;
            if (s.protocol_version != BridgeProtocol.Version)
                e.Add($"bridge.json protocol_version {s.protocol_version}, but this Unity code speaks {BridgeProtocol.Version}");
            if (string.IsNullOrEmpty(s.host)) e.Add("bridge.json host is required");
            if (s.port < 1 || s.port > 65535) e.Add("bridge.json port must be 1..65535");
            Positive("bridge.json telemetry_hz", s.telemetry_hz);
            Positive("bridge.json frame_360_hz", s.frame_360_hz);
            Positive("bridge.json frame_pan_tilt_hz", s.frame_pan_tilt_hz);
            Positive("bridge.json watchdog_timeout_s", s.watchdog_timeout_s);
            Positive("bridge.json max_header_bytes", s.max_header_bytes);
            Positive("bridge.json max_attachment_bytes", s.max_attachment_bytes);
            Positive("bridge.json max_pending_frames", s.max_pending_frames);
            if (s.jpeg_quality < 1 || s.jpeg_quality > 100) e.Add("bridge.json jpeg_quality must be 1..100");

            var u = Unity;
            Positive("reconnect_interval_s", u.reconnect_interval_s);
            Positive("connect_timeout_s", u.connect_timeout_s);
            if (string.IsNullOrEmpty(u.nav.agent_type)) e.Add("nav.agent_type is required");
            Positive("nav.sample_radius_m", u.nav.sample_radius_m);
            if (u.camera_360.centre_yaw_status != "assumed_unverified" && u.camera_360.centre_yaw_status != "verified")
                e.Add("camera_360.centre_yaw_status must be assumed_unverified or verified");
            return e;
        }
    }
}
