using System.Globalization;
using UnityEngine;
using WarehouseHRI.V4;

namespace WarehouseRobot.Bridge
{
    /// <summary>
    /// v4 heads-up display (docs/project_flow_v4.md "Heads-up display"; docs/protocol_v3.md "The hud object"): one
    /// always-on panel with what Python sends in the hud block of each command: state, screen text, the people the robot
    /// sees (bearing, distance, commander), the gesture class with its score, the raw and accepted gesture, the commander,
    /// the POINT angle and the message log. Display only. It is drawn with IMGUI in OnGUI, which paints the game view
    /// after every camera has rendered; the robot cameras render into their own render textures, so the panel can never
    /// appear in a robot camera image (the leak test checks the ground-truth layer the same way). F4 shows/hides it.
    /// </summary>
    [DisallowMultipleComponent]
    public class HudOverlay : MonoBehaviour
    {
        [SerializeField] RobotBridgeClient bridge;
        [SerializeField] bool showPanel = true;
        [SerializeField] float width = 380f;
        [SerializeField] float top = 340f;   // below the bridge panel (RobotBridgeClient, top right)

        static readonly CultureInfo Inv = CultureInfo.InvariantCulture;
        GUIStyle label, header;

        public void Bind(RobotBridgeClient client) => bridge = client;

        void Awake()
        {
            if (bridge == null) bridge = GetComponent<RobotBridgeClient>();
            if (bridge == null) bridge = FindFirstObjectByType<RobotBridgeClient>();
        }

        void OnGUI()
        {
            if (Event.current.type == EventType.KeyDown && Event.current.keyCode == KeyCode.F4) showPanel = !showPanel;
            if (!showPanel || bridge == null) return;
            label ??= new GUIStyle(GUI.skin.label) { fontSize = 12, wordWrap = false, clipping = TextClipping.Clip };
            header ??= new GUIStyle(label) { fontStyle = FontStyle.Bold };

            const float pad = 8f, line = 16f;
            float x = Screen.width - width - pad, y = top;
            float height = Mathf.Max(6f * line, Screen.height - top - pad);
            GUI.Box(new Rect(x - pad, y, width + pad, height), GUIContent.none);
            y += pad / 2f;
            float bottom = top + height - line;
            bool Line(string text, GUIStyle style = null)
            {
                if (y > bottom) return false;
                GUI.Label(new Rect(x, y, width, line), text, style ?? label);
                y += line;
                return true;
            }

            var hud = bridge.Hud;
            Line("HUD (F4)  protocol " + bridge.ProtocolVersion + (bridge.Connected ? "" : "  - not connected"), header);
            if (hud == null)
            {
                Line(bridge.ProtocolVersion == 3 ? "no command with a hud block yet" : "protocol 2: no hud block (v3 study)");
                return;
            }

            Line("State: " + hud.state);
            Line("Screen: " + (hud.screen_text.Length > 0 ? "\"" + hud.screen_text + "\"" : "-"));
            Line("Commander: " + (hud.commander_id >= 0 ? "#" + hud.commander_id.ToString(Inv) : "none"));
            Line("Gesture: " + hud.gesture + "  score " + hud.gesture_score.ToString("0.00", Inv) +
                 (hud.HasPointAngle ? "  angle " + hud.point_angle_deg.ToString("+0;-0;0", Inv) + " deg" : ""));
            Line("Reading now: " + hud.gesture_raw + "   accepted: " + hud.gesture_accepted);

            Line("People (" + hud.people.Count.ToString(Inv) + ")", header);
            foreach (var p in hud.people)
            {
                string d = p.distance_m < 0f ? "? m" : p.distance_m.ToString("0.0", Inv) + " m";
                if (!Line((p.is_commander ? "> " : "  ") + "#" + p.id.ToString(Inv) + "  bearing " +
                          p.bearing_deg.ToString("+0;-0;0", Inv) + " deg  " + d + (p.is_commander ? "  COMMANDER" : ""))) return;
            }

            Line("Messages (in = Unity -> Python, out = Python -> Unity)", header);
            foreach (var m in hud.log)
                if (!Line(m.dir + " #" + m.seq.ToString(Inv) + " " + m.type + ": " + m.text)) return;
        }
    }
}
