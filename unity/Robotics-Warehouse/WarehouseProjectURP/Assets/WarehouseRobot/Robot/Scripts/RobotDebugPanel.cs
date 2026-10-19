using UnityEngine;

namespace WarehouseRobot
{
    /// <summary>
    /// Testing aid: an on-screen panel with both camera images and the drive state, plus keyboard driving and pan
    /// control behind a toggle that is off by default. F1 shows/hides the panel; F2 or the panel checkbox toggles
    /// keyboard control. With control on: arrow keys drive (up/down = +/- max speed, left/right = turn), Z/X pan
    /// left/right, C centres the pan. Turning control off commands a stop.
    /// </summary>
    [DisallowMultipleComponent]
    public class RobotDebugPanel : MonoBehaviour
    {
        [SerializeField] bool showPanel = true;
        [SerializeField] bool keyboardControl = false;

        RobotRig rig;
        float panSpeedDps;
        bool lastKeyboardControl;

        /// <summary>Turning keyboard control off commands a stop (handled in Update, also for Inspector edits).</summary>
        public bool KeyboardControl
        {
            get => keyboardControl;
            set => keyboardControl = value;
        }

        void Start()
        {
            rig = GetComponent<RobotRig>();
            var cfg = rig != null ? rig.Config : null;
            panSpeedDps = cfg != null ? cfg.Unity.debug.keyboard_pan_speed_dps : 0f;
            lastKeyboardControl = keyboardControl;
        }

        void Update()
        {
            if (Input.GetKeyDown(KeyCode.F1)) showPanel = !showPanel;
            if (Input.GetKeyDown(KeyCode.F2)) keyboardControl = !keyboardControl;
            if (lastKeyboardControl && !keyboardControl && rig != null && rig.Drive != null) rig.Drive.Stop();
            lastKeyboardControl = keyboardControl;
            if (!keyboardControl || rig == null) return;

            var drive = rig.Drive;
            var cfg = rig.Config;
            if (drive != null && drive.Ready && cfg != null)
            {
                float fwd = (Input.GetKey(KeyCode.UpArrow) ? 1f : 0f) - (Input.GetKey(KeyCode.DownArrow) ? 1f : 0f);
                float left = (Input.GetKey(KeyCode.LeftArrow) ? 1f : 0f) - (Input.GetKey(KeyCode.RightArrow) ? 1f : 0f);
                drive.SetCommand(fwd * cfg.Robot.max_speed_mps, left * cfg.Robot.max_angular_speed_radps);
            }

            var pan = rig.PanTilt;
            if (pan != null && pan.Ready)
            {
                float dir = (Input.GetKey(KeyCode.Z) ? 1f : 0f) - (Input.GetKey(KeyCode.X) ? 1f : 0f);
                if (dir != 0f) pan.SetPanDeg(pan.PanDeg + dir * panSpeedDps * Time.deltaTime);
                if (Input.GetKeyDown(KeyCode.C)) pan.SetPanDeg(0f);
            }
        }

        void OnGUI()
        {
            if (!showPanel || rig == null) return;
            const float pad = 8f, line = 20f;
            float w = Mathf.Min(420f, Screen.width * 0.4f);
            float panH = w * 530f / 730f;
            float eqH = w * 0.5f;
            var pan = rig.PanTilt;
            var omni = rig.Omni;
            var drive = rig.Drive;
            var col = rig.Collisions;
            if (pan != null && pan.Ready) panH = w * pan.Image.height / pan.Image.width;
            if (omni != null && omni.Ready) eqH = w * omni.Equirect.height / omni.Equirect.width;

            float h = pad + line + panH + line + eqH + 6f * line + pad;
            GUI.Box(new Rect(pad, pad, w + 2f * pad, h), GUIContent.none);
            float x = 2f * pad, y = 2f * pad;

            GUI.Label(new Rect(x, y, w, line), pan != null && pan.Ready ? $"Pan-tilt camera  pan {pan.PanDeg:F0} deg" : "Pan-tilt camera: not ready");
            y += line;
            if (pan != null && pan.Ready) GUI.DrawTexture(new Rect(x, y, w, panH), pan.Image, ScaleMode.ScaleToFit, false);
            y += panH;

            GUI.Label(new Rect(x, y, w, line), omni != null && omni.Ready ? $"360 camera (world-aligned)  frames {omni.FramesCaptured}" : "360 camera: not ready");
            y += line;
            if (omni != null && omni.Ready) GUI.DrawTexture(new Rect(x, y, w, eqH), omni.Equirect, ScaleMode.ScaleToFit, false);
            y += eqH;

            if (drive != null && drive.Ready)
            {
                GUI.Label(new Rect(x, y, w, line), $"v {drive.V:F2} m/s (cmd {drive.CommandedV:F2})   omega {drive.Omega:F2} rad/s (cmd {drive.CommandedOmega:F2})");
            }
            y += line;
            if (col != null)
            {
                string last = col.Records.Count > 0 ? $"  last: t={col.Records[col.Records.Count - 1].time_s:F1} s {col.Records[col.Records.Count - 1].object_hit}" : "";
                GUI.Label(new Rect(x, y, w, line), $"collisions {col.Records.Count}{last}");
            }
            y += line;

            bool kb = GUI.Toggle(new Rect(x, y, w, line), keyboardControl, " Keyboard control (F2)");
            if (kb != keyboardControl) keyboardControl = kb;
            y += line;
            GUI.Label(new Rect(x, y, w, line), "Arrows drive, Z/X pan left/right, C centre, F1 hide panel");
            y += line;

            GUI.enabled = keyboardControl && pan != null && pan.Ready;
            if (pan != null && pan.Ready)
            {
                float s = GUI.HorizontalSlider(new Rect(x, y + 5f, w, line), pan.PanDeg, pan.PanMaxDeg, pan.PanMinDeg); // left end = left pan
                if (GUI.enabled && !Mathf.Approximately(s, pan.PanDeg)) pan.SetPanDeg(s);
            }
            y += line;
            GUI.enabled = true;
            if (GUI.Button(new Rect(x, y, 120f, line), "Stop robot") && drive != null) drive.Stop();
        }
    }
}
