using UnityEngine;

namespace WarehouseHRI
{
    /// <summary>
    /// On-screen display (IMGUI, runtime API): the robot's "Which direction?" prompt, its state, the trial status,
    /// and small previews of the pan-tilt gesture camera and the 360 deg panorama. Optional world-space text above
    /// the robot shows the same prompt to the worker.
    /// </summary>
    public class HriHud : MonoBehaviour
    {
        public RobotBrain brain;
        public PanTiltCamera panTilt;
        public Camera360 cam360;
        public TextMesh robotDisplay;
        public HriBridgeClient bridge;
        public bool showPreviews = true;

        GUIStyle m_Big, m_Small;

        void Update()
        {
            if (robotDisplay != null && brain != null) robotDisplay.text = brain.Prompt;
        }

        void OnGUI()
        {
            if (brain == null) return;
            if (m_Big == null)
            {
                m_Big = new GUIStyle(GUI.skin.label) { fontSize = 28, fontStyle = FontStyle.Bold, alignment = TextAnchor.MiddleCenter };
                m_Small = new GUIStyle(GUI.skin.box) { fontSize = 13, alignment = TextAnchor.UpperLeft, wordWrap = true };
            }

            var tm = TrialManager.Active;
            string text =
                $"State: {brain.State}   node: {(brain.CurrentNode != null ? brain.CurrentNode.name : "-")} -> {(brain.TargetNode != null ? brain.TargetNode.name : "-")}\n" +
                $"People: {brain.PeopleDetected}   gesture read: {brain.LastRead}   " +
                (brain.SafetyStopActive ? $"SAFETY STOP ({brain.SafetyReason})" : "") + "\n" +
                $"Perception: {brain.PersonSource?.Label}\nGestures: {brain.GestureSource?.Label}\n" +
                (bridge != null ? $"Python link: {bridge.Status}  rtt {HriOutput.F(bridge.Rtt.LastMs, "0.0")} ms  {bridge.PerceptionLabel}\n" : "") +
                (tm != null ? $"{tm.Status}\n{tm.LastSummary}" : "");
            GUI.Box(new Rect(10, 10, 560, 130), text, m_Small);

            if (!string.IsNullOrEmpty(brain.Prompt))
                GUI.Label(new Rect(0, Screen.height * 0.12f, Screen.width, 50), brain.Prompt, m_Big);

            if (!showPreviews) return;
            float w = 292f;
            if (panTilt != null && panTilt.Image != null)
                GUI.DrawTexture(new Rect(Screen.width - w - 10, 10, w, w * 530f / 730f), panTilt.Image, ScaleMode.ScaleToFit);
            if (cam360 != null && cam360.Equirect != null)
                GUI.DrawTexture(new Rect(Screen.width - 2 * w - 10, Screen.height - w / 2 - 10, 2 * w, w / 2), cam360.Equirect, ScaleMode.ScaleToFit);
        }
    }
}
