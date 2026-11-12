using System;
using System.Collections.Generic;
using System.Text.RegularExpressions;
using UnityEngine;

namespace WarehouseHRI.V4
{
    /// <summary>One person in the hud block (docs/protocol_v3.md, "The hud object").</summary>
    [Serializable]
    public class HudPerson
    {
        public int id = -1;
        public float bearing_deg;
        public float distance_m = -1f;
        public bool is_commander;
    }

    /// <summary>One message summary in the hud log.</summary>
    [Serializable]
    public class HudLogEntry
    {
        public string dir = "";
        public string type = "";
        public int seq = -1;
        public string text = "";
    }

    /// <summary>
    /// The hud block of a version 3 command: what Unity draws on the heads-up display. Display only: Unity never acts on
    /// it and it never appears in a robot camera image. No nulls arrive (empty values are "", [], -1 or NONE).
    /// </summary>
    [Serializable]
    public class HudMsg
    {
        public string state = "";
        public string screen_text = "";
        public int commander_id = -1;
        public string gesture = "NONE";
        public float gesture_score;
        public string gesture_raw = "NONE";
        public string gesture_accepted = "NONE";
        public float point_angle_deg = -1f;
        public List<HudPerson> people = new List<HudPerson>();
        public List<HudLogEntry> log = new List<HudLogEntry>();

        /// <summary>point_angle_deg is meaningful only while gesture is POINT (-1 is also a possible angle).</summary>
        public bool HasPointAngle => gesture == "POINT";
    }

    /// <summary>
    /// Version 3 rules Unity applies (docs/protocol_v3.md): the zoom request, the pan-tilt intrinsics at render time and
    /// the keys no Unity message may carry. Pure functions, so they are tested in Edit Mode.
    /// </summary>
    public static class ProtocolV3
    {
        public const int Version = 3;

        /// <summary>vertical_fov_deg = -1 in a command: keep the configured default (no zoom).</summary>
        public const float KeepDefaultFov = -1f;

        /// <summary>Goal keys forbidden since version 2 (docs/protocol.md, "Goal B never reaches Python").</summary>
        public static readonly string[] GoalKeys =
            { "goal", "goal_point", "goal_x", "goal_z", "end_point", "end_point_x", "end_point_z", "point_b", "b" };

        /// <summary>Truth keys version 3 adds (docs/protocol_v3.md, "Forbidden keys from Unity"; Python's
        /// bridge/protocol.py TRUTH_KEYS): the six label names of 2026-10-23 and, since 2026-11-08, every field name of
        /// truth.jsonl that no Unity message carries legitimately (time_s, x and z are not in the list).</summary>
        public static readonly string[] TruthKeys =
        {
            "true_gesture", "true_commander", "commander_truth", "gesture_truth", "worker_label", "truth",
            "true_command", "is_commander", "worker_id", "point_angle_deg", "look", "clip", "phase", "arm",
            "ankle_height_m",      // 2026-11-12: the new optional truth.jsonl field (docs/protocol_v3.md amendment 2)
        };

        static readonly Regex KeyPattern = new Regex("\"((?:[^\"\\\\]|\\\\.)*)\"\\s*:", RegexOptions.Compiled);

        /// <summary>
        /// The first JSON key in json (at any depth) that a version 3 Unity message must not carry, compared
        /// case-insensitively as Python does; null if there is none.
        /// </summary>
        public static string FindForbiddenKey(string json)
        {
            if (string.IsNullOrEmpty(json)) return null;
            foreach (Match m in KeyPattern.Matches(json))
            {
                string key = m.Groups[1].Value;
                foreach (var k in GoalKeys)
                    if (string.Equals(key, k, StringComparison.OrdinalIgnoreCase)) return key;
                foreach (var k in TruthKeys)
                    if (string.Equals(key, k, StringComparison.OrdinalIgnoreCase)) return key;
            }
            return null;
        }

        /// <summary>
        /// A version 3 command must carry vertical_fov_deg and hud. JsonUtility fills a missing field with its default,
        /// so their presence is checked on the header text. Returns the missing key, or null.
        /// </summary>
        public static string MissingCommandKey(string headerJson)
        {
            foreach (var key in new[] { "vertical_fov_deg", "hud" })
                if (!Regex.IsMatch(headerJson ?? "", "\"" + key + "\"\\s*:")) return key;
            return null;
        }

        /// <summary>
        /// The field of view to apply for a commanded vertical_fov_deg: -1 keeps defaultDeg; a value in (0, 180) is
        /// clamped to [minDeg, maxDeg]. Anything else is an invalid command (false, with the reason).
        /// </summary>
        public static bool TryResolveFov(float requested, float defaultDeg, float minDeg, float maxDeg, out float applied, out string error)
        {
            applied = defaultDeg;
            error = null;
            if (float.IsNaN(requested) || float.IsInfinity(requested))
            {
                error = "vertical_fov_deg is not a finite number";
                return false;
            }
            if (requested == KeepDefaultFov) return true;
            if (!(requested > 0f && requested < 180f))
            {
                error = $"vertical_fov_deg {requested} must be -1 (keep the default) or in (0, 180)";
                return false;
            }
            applied = Mathf.Clamp(requested, minDeg, maxDeg);
            return true;
        }

        /// <summary>Pinhole intrinsics of a frame rendered with this vertical field of view: fy = (height / 2) / tan(fov / 2), fx = fy, centre.</summary>
        public static void Intrinsics(int width, int height, float verticalFovDeg, out float fx, out float fy, out float cx, out float cy)
        {
            fy = 0.5f * height / Mathf.Tan(0.5f * verticalFovDeg * Mathf.Deg2Rad);
            fx = fy;
            cx = 0.5f * width;
            cy = 0.5f * height;
        }

        /// <summary>
        /// Python's check of a frame_pan_tilt header (docs/protocol_v3.md section 2), so Unity can test what it sends:
        /// null when the intrinsics match the field of view within relTol, else the reason Python would reject it.
        /// </summary>
        public static string IntrinsicsProblem(int width, int height, float fx, float fy, float cx, float cy, float verticalFovDeg, float relTol)
        {
            if (!(verticalFovDeg > 0f && verticalFovDeg < 180f)) return $"vertical_fov_deg {verticalFovDeg} outside (0, 180)";
            double want = 0.5 * height / Math.Tan(0.5 * verticalFovDeg * Math.PI / 180.0);
            bool Close(double got, double expected) => Math.Abs(got - expected) <= relTol * Math.Abs(expected);
            if (!Close(fy, want)) return $"fy {fy} does not match vertical_fov_deg {verticalFovDeg} (expected {want})";
            if (!Close(fx, want)) return $"fx {fx} does not match vertical_fov_deg {verticalFovDeg} (expected {want})";
            if (!Close(cx, 0.5 * width)) return $"cx {cx} is not width / 2";
            if (!Close(cy, 0.5 * height)) return $"cy {cy} is not height / 2";
            return null;
        }
    }
}
