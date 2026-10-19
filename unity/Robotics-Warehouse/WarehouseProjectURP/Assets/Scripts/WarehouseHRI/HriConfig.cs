using System;
using System.IO;
using UnityEngine;

namespace WarehouseHRI
{
    /// <summary>
    /// All thresholds of the guided-robot task, read from StreamingAssets/WarehouseHRI/hri_config.json.
    /// The C# defaults below equal the declared values in that file; they are used only when the file is missing
    /// (logged as a warning) and by the edit-mode tests.
    /// </summary>
    [Serializable]
    public class HriConfig
    {
        public const string RelativePath = "WarehouseHRI/hri_config.json";
        /// <summary>Optional, git-ignored overlay (*.local.json): only the fields it contains replace the main file's.</summary>
        public const string LocalRelativePath = "WarehouseHRI/hri_config.local.json";

        public string label = "defaults compiled into HriConfig.cs";
        public bool frozen;
        public string output_root = "../../../robot_vision/outputs";
        public TrialSettings trials = new TrialSettings();
        public RobotSettings robot = new RobotSettings();
        public BrainSettings brain = new BrainSettings();
        public LinkSettings link = new LinkSettings();
        public CameraSettings cameras = new CameraSettings();
        public TelemetrySettings telemetry = new TelemetrySettings();
        public PerceptionSettings perception = new PerceptionSettings();
        public GestureSweepSettings gesture_sweep = new GestureSweepSettings();

        [Serializable]
        public class PerceptionSettings
        {
            public string mode = "scripted";              // scripted (baseline) | vision (Python replies)
            public float stale_after_s = 0.5f;            // older replies are ignored (no people, gesture NONE)
            public float unknown_person_distance_m = 1.0f; // used for a person whose distance vision could not estimate
            public float chest_height_m = 1.3f;           // pan-tilt aim height above a vision person's feet
        }

        [Serializable]
        public class GestureSweepSettings
        {
            public int repeats = 20;
            public float distance_min_m = 1.7f;
            public float distance_max_m = 2.5f;
            public float view_angle_max_deg = 25f;
            public float worker_yaw_jitter_deg = 15f;
            public float settle_s = 0.6f;
            public float hold_s = 1.5f;
        }

        [Serializable]
        public class TrialSettings
        {
            public string task = "Task2";            // Task1 (straight, FORWARD) or Task2 (guided route)
            public string mode = "development";      // development (dev_seed) or final (final_seed, once)
            public int dev_seed = 1;
            public int final_seed = 2;
            public int trial_count = 10;
            public float timeout_s = 240f;
            public float stuck_s = 8f;
            public float stuck_min_progress_m = 0.25f;
            public float pause_between_trials_s = 1f;
            public float success_radius_m = 0.3f;
        }

        [Serializable]
        public class RobotSettings
        {
            public float width_m = 0.58f;
            public float length_m = 0.89f;
            public float height_m = 0.35f;
            public float ground_clearance_m = 0.025f;
            public float mass_kg = 70f;
            public float max_speed_mps = 1.0f;
            public float max_turn_rate_dps = 60f;
            public float accel_mps2 = 0.5f;
            public float decel_mps2 = 0.5f;
            public float emergency_decel_mps2 = 1.5f;
            public float angular_accel_dps2 = 180f;
            public float lookahead_m = 0.8f;
            public float rotate_in_place_deg = 60f;
            public float turn_gain = 2.0f;
            public float align_tolerance_deg = 5f;
            public float replan_deviation_m = 1.0f;
        }

        [Serializable]
        public class BrainSettings
        {
            public float junction_slow_radius_m = 3f;
            public float junction_speed_scale = 0.4f;
            public float junction_stop_m = 0.3f;
            public float endpoint_stop_m = 0.1f;
            public float approach_distance_m = 2.0f;
            public float approach_tolerance_m = 0.15f;
            public float approach_speed_scale = 0.5f;
            public float scan_min_s = 0.2f;
            public float scan_timeout_s = 5f;
            public float ask_settle_s = 0.5f;
            public float gesture_hold_s = 1.0f;
            public float gesture_window_s = 5f;
            public int max_asks = 2;
            public float execute_align_deg = 15f;
            public float safety_stop_distance_m = 1.2f;
            public float safety_corridor_half_width_m = 0.6f;
            public float person_detection_range_m = 12f;
            public float gesture_read_range_m = 6f;
        }

        [Serializable]
        public class LinkSettings
        {
            public float watchdog_s = 0.3f;
            public bool link_required;
            public bool enabled = true;
            public string host = "127.0.0.1";
            public int port = 5050;
            public float send_interval_s = 0.1f;
            public float connect_retry_s = 1f;
            public int jpeg_quality = 90;
            public int cam360_send_width_px = 2048;
            public float cam360_band_top_deg = 30f;
            public float cam360_band_bottom_deg = -60f;
            public bool send_gesture_image = true;
            public bool send_cam360_image = true;
        }

        [Serializable]
        public class CameraSettings
        {
            public float cam360_interval_s = 0.1f;
            public int cam360_face_px = 512;
            public int cam360_equirect_width_px = 2048;
            public float cam360_height_m = 1.5f;
            public int gesture_width_px = 730;
            public int gesture_height_px = 530;
            public float gesture_vfov_deg = 60f;
            public float gesture_height_m = 1.2f;
            public float pan_speed_dps = 120f;
        }

        [Serializable]
        public class TelemetrySettings
        {
            public float interval_s = 0.1f;
        }

        static HriConfig s_Current;
        static string s_SourceText;
        static string s_LocalText;

        /// <summary>Full path of the config file (StreamingAssets).</summary>
        public static string FilePath => Path.Combine(Application.streamingAssetsPath, RelativePath);

        /// <summary>The config text as read from disk (null when the file is missing), copied into every run folder.</summary>
        public static string SourceText
        {
            get { _ = Current; return s_SourceText; }
        }

        /// <summary>The local overlay's text, or null when there is none (copied into every run folder too).</summary>
        public static string LocalText
        {
            get { _ = Current; return s_LocalText; }
        }

        public static string LocalFilePath => Path.Combine(Application.streamingAssetsPath, LocalRelativePath);

        public static HriConfig Current
        {
            get
            {
                if (s_Current == null)
                {
                    s_Current = Load(FilePath, out s_SourceText);
                    s_LocalText = null;
                    if (File.Exists(LocalFilePath))
                    {
                        s_LocalText = File.ReadAllText(LocalFilePath);
                        JsonUtility.FromJsonOverwrite(s_LocalText, s_Current);
                        Debug.Log("[WarehouseHRI] Config overlay applied: " + LocalRelativePath);
                    }
                }

                return s_Current;
            }
        }

        /// <summary>Text hashed and saved as "the exact config": main file plus the overlay, if any.</summary>
        public static string EffectiveText => (SourceText ?? "") + (LocalText != null ? "\n// hri_config.local.json overlay:\n" + LocalText : "");

        /// <summary>Re-read the file on next access (TrialManager calls this at the start of a session).</summary>
        public static void Reload()
        {
            s_Current = null;
            s_SourceText = null;
            s_LocalText = null;
        }

        public static HriConfig Load(string path, out string text)
        {
            text = null;
            if (!File.Exists(path))
            {
                Debug.LogWarning($"[WarehouseHRI] Config not found at {path}; using compiled defaults.");
                return new HriConfig();
            }

            text = File.ReadAllText(path);
            var cfg = FromJson(text);
            return cfg;
        }

        public static HriConfig FromJson(string json)
        {
            var cfg = new HriConfig();
            JsonUtility.FromJsonOverwrite(json, cfg);
            return cfg;
        }

        /// <summary>Seed for the configured mode: dev_seed for development, final_seed for final.</summary>
        public int ActiveSeed => IsFinal ? trials.final_seed : trials.dev_seed;

        public bool IsFinal => string.Equals(trials.mode, "final", StringComparison.OrdinalIgnoreCase);

        /// <summary>Decisions use the Python vision replies (else the scripted baselines).</summary>
        public bool IsVision => string.Equals(perception.mode, "vision", StringComparison.OrdinalIgnoreCase);

        /// <summary>The robot must stop when Python is silent: configured, and always in vision mode.</summary>
        public bool LinkRequired => link.link_required || IsVision;
    }
}
