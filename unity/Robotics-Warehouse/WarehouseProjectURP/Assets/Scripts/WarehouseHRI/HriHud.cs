using System.Text;
using UnityEngine;

namespace WarehouseHRI
{
    /// <summary>
    /// Viewer overlay (IMGUI, Game view only; never in the robot's camera images): robot state, current junction,
    /// gesture shown (scripted) vs read (by the robot), goal B with an on-screen "B" label, running success ratio,
    /// Python link and camera view. Also the large "Which direction?" prompt and optional previews of the gesture
    /// camera and the 360 deg panorama (H toggles them). Goal and "shown" come from the scenario side
    /// (TrialManager) and are shown to the viewer only; the robot never reads them.
    /// </summary>
    public class HriHud : MonoBehaviour
    {
        public RobotBrain brain;
        public PanTiltCamera panTilt;
        public Camera360 cam360;
        public TextMesh robotDisplay;
        public HriBridgeClient bridge;
        public FollowCamera followCamera;
        public bool showPreviews = true;
        public KeyCode togglePreviewsKey = KeyCode.H;

        GUIStyle m_Big, m_Panel, m_Goal;
        readonly StringBuilder m_Sb = new StringBuilder();

        void Update()
        {
            if (robotDisplay != null && brain != null) robotDisplay.text = brain.Prompt;
            if (Input.GetKeyDown(togglePreviewsKey)) showPreviews = !showPreviews;
        }

        /// <summary>Junction the robot is at (dialog states) or heading to; null between other nodes.</summary>
        RoadNode CurrentJunction()
        {
            if (brain.CurrentNode != null && brain.CurrentNode.IsJunction &&
                brain.State >= BrainState.Scan && brain.State <= BrainState.Execute) return brain.CurrentNode;
            return brain.TargetNode != null && brain.TargetNode.IsJunction ? brain.TargetNode : null;
        }

        void OnGUI()
        {
            if (brain == null) return;
            if (m_Big == null)
            {
                m_Big = new GUIStyle(GUI.skin.label) { fontSize = 28, fontStyle = FontStyle.Bold, alignment = TextAnchor.MiddleCenter };
                m_Panel = new GUIStyle(GUI.skin.box) { fontSize = 14, alignment = TextAnchor.UpperLeft, richText = true, padding = new RectOffset(8, 8, 6, 6) };
                m_Goal = new GUIStyle(GUI.skin.label) { fontSize = 18, fontStyle = FontStyle.Bold, alignment = TextAnchor.MiddleCenter, richText = true };
            }

            var tm = TrialManager.Active;
            var sb = m_Sb;
            sb.Clear();
            sb.Append("<b>State</b>  ").Append(brain.State);
            if (brain.SafetyStopActive) sb.Append("  <color=#ff5050>STOP: ").Append(brain.SafetyReason).Append("</color>");
            sb.Append('\n');

            var j = CurrentJunction();
            sb.Append("<b>Junction</b>  ").Append(j != null ? j.name : "-");
            if (j != null && j != brain.CurrentNode) sb.Append(" (approaching)");
            sb.Append('\n');

            string shown = tm != null && j != null ? tm.ShownAt(j).ToString() : "-";
            string read = brain.State == BrainState.Read || brain.State == BrainState.Ask ? brain.LastRead + " (reading)"
                : brain.State == BrainState.Execute ? brain.Dialog.Accepted.ToString() : "-";
            sb.Append("<b>Gesture</b>  shown ").Append(shown).Append("  |  read ").Append(read).Append('\n');
            if (tm != null && tm.CurrentRecords.Count > 0)
            {
                sb.Append("   done: ");
                foreach (var r in tm.CurrentRecords) sb.Append(r.junction).Append(' ').Append(r.shown).Append('>').Append(r.read).Append("  ");
                sb.Append('\n');
            }

            if (tm != null && tm.CurrentGoal != null)
            {
                Vector3 g = tm.CurrentGoal.Position;
                Vector3 d = g - brain.transform.position;
                d.y = 0f;
                sb.Append("<b>Goal B</b>  ").Append(tm.CurrentGoal.name).Append(" (")
                  .Append(HriOutput.F(g.x, "0.0")).Append(", ").Append(HriOutput.F(g.z, "0.0")).Append(")  ")
                  .Append(HriOutput.F(d.magnitude, "0.0")).Append(" m away\n");
                int done = tm.CompletedTrials;
                sb.Append("<b>Success</b>  ").Append(tm.Successes).Append('/').Append(done)
                  .Append(done > 0 ? $" ({HriOutput.F(100f * tm.Successes / done, "0")} %)" : "")
                  .Append("   trial ").Append(tm.TrialIndex).Append('/').Append(tm.TrialTotal).Append('\n');
            }
            else if (tm != null) sb.Append(tm.Status).Append('\n');

            if (bridge != null && bridge.linkEnabled)
                sb.Append("<b>Python</b>  ").Append(bridge.Status).Append("  rtt ").Append(HriOutput.F(bridge.Rtt.LastMs, "0.0")).Append(" ms\n");
            sb.Append("<size=11>decisions: ").Append(brain.GestureSource?.Label).Append(" | view: ")
              .Append(followCamera != null ? followCamera.ModeLabel + " (C)" : "-").Append(" | previews (H)</size>");

            GUI.Box(new Rect(10, 10, 430, 150), sb.ToString(), m_Panel);

            if (!string.IsNullOrEmpty(brain.Prompt))
                GUI.Label(new Rect(0, Screen.height * 0.12f, Screen.width, 50), brain.Prompt, m_Big);

            DrawGoalLabel(tm);

            if (!showPreviews) return;
            float w = 292f;
            if (panTilt != null && panTilt.Image != null)
                GUI.DrawTexture(new Rect(Screen.width - w - 10, 10, w, w * 530f / 730f), panTilt.Image, ScaleMode.ScaleToFit);
            if (cam360 != null && cam360.Equirect != null)
                GUI.DrawTexture(new Rect(Screen.width - 2 * w - 10, Screen.height - w / 2 - 10, 2 * w, w / 2), cam360.Equirect, ScaleMode.ScaleToFit);
        }

        /// <summary>A "B" label over the goal in the Game view (hidden in the gesture-camera view, like the marker).</summary>
        void DrawGoalLabel(TrialManager tm)
        {
            if (tm == null || tm.CurrentGoal == null || followCamera == null || followCamera.mode == FollowCameraMode.GestureCamera) return;
            var cam = followCamera.ViewCamera;
            Vector3 sp = cam.WorldToScreenPoint(tm.CurrentGoal.Position + Vector3.up * 2.3f);
            if (sp.z <= 0f) return;
            GUI.Label(new Rect(sp.x - 40, Screen.height - sp.y - 15, 80, 30), "<color=#ffb000>B</color>", m_Goal);
        }
    }
}
