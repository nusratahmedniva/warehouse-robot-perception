using UnityEngine;

namespace WarehouseHRI.V4
{
    /// <summary>
    /// The v4 robot's status light ring and front display (2026-11-12, U1; Avatar/Config/upgrade_design.md section 7): what
    /// colour and message the robot shows for Python's state string (e.g. "navigate", "read", "navigate (stopped: STOP
    /// gesture)"). Display only, from what Python already sends (state, screen_text, hud.gesture_accepted); pure functions,
    /// tested in Edit Mode.
    /// </summary>
    public static class RobotStatus
    {
        public enum Light { Idle, Driving, Searching, Asking, Stopped }

        public static readonly Color Green = new Color(0.1f, 0.9f, 0.2f), Blue = new Color(0.15f, 0.45f, 1f), Yellow = new Color(1f, 0.8f, 0.05f),
                                     Red = new Color(1f, 0.08f, 0.05f), White = new Color(0.9f, 0.9f, 0.9f);

        /// <summary>green driving (navigate, execute), blue searching or approaching (scan, approach), yellow asking or
        /// reading (ask, read, wait), red stopped (any "(stopped: ...)" state) or aborted, white idle or done.</summary>
        public static Light LightFor(string state)
        {
            string s = (state ?? "").Trim();
            if (s.Contains("stopped") || s.StartsWith("aborted")) return Light.Stopped;
            if (s.StartsWith("navigate") || s.StartsWith("execute")) return Light.Driving;
            if (s.StartsWith("scan") || s.StartsWith("approach")) return Light.Searching;
            if (s.StartsWith("ask") || s.StartsWith("read") || s.StartsWith("wait")) return Light.Asking;
            return Light.Idle;
        }

        public static Color ColorFor(Light l)
        {
            switch (l)
            {
                case Light.Driving: return Green;
                case Light.Searching: return Blue;
                case Light.Asking: return Yellow;
                case Light.Stopped: return Red;
                default: return White;
            }
        }

        /// <summary>The front display's message: Python's screen text when there is one ("Which direction?", "One moment..."),
        /// else a short word for the state ("Going LEFT" with the accepted branch while driving after an answer).</summary>
        public static string MessageFor(string state, string screenText, string accepted)
        {
            if (!string.IsNullOrEmpty(screenText)) return screenText;
            string s = (state ?? "").Trim();
            if (s.Contains("stopped: STOP")) return "STOP";
            if (s.Contains("stopped")) return "Stopped";
            if (s.StartsWith("aborted")) return "Aborted";
            if (s.StartsWith("done")) return "Arrived";
            if (s.StartsWith("navigate") || s.StartsWith("execute"))
                return !string.IsNullOrEmpty(accepted) && accepted != "NONE" && accepted != "WAIT" ? "Going " + accepted : "Driving";
            if (s.StartsWith("scan")) return "Looking for help";
            if (s.StartsWith("approach")) return "Coming over";
            return "";
        }
    }
}
