using UnityEngine;

namespace WarehouseHRI
{
    /// <summary>
    /// Pose check by eye (added by "Tools > Warehouse HRI > Gesture Pose Test" in Play mode): cycles the worker
    /// through the six shown commands, holdS seconds each, with NONE in between, and labels the current one.
    /// </summary>
    public class GesturePoseCycler : MonoBehaviour
    {
        public GestureWorker worker;
        public float holdS = 2.5f;
        public bool noneBetween = true;

        int m_Step;
        float m_Next;
        GUIStyle m_Style;

        public GestureCommand Showing => worker != null ? worker.Current : GestureCommand.NONE;

        void OnEnable()
        {
            if (worker == null) worker = GetComponent<GestureWorker>();
            m_Step = 0;
            m_Next = 0f;
        }

        void Update()
        {
            if (worker == null || Time.time < m_Next) return;
            int n = GestureCommands.Shown.Length;
            int slots = noneBetween ? 2 * n : n;
            int s = m_Step % slots;
            var c = noneBetween ? (s % 2 == 0 ? GestureCommands.Shown[s / 2] : GestureCommand.NONE) : GestureCommands.Shown[s];
            worker.Show(c);
            m_Next = Time.time + (c == GestureCommand.NONE ? holdS * 0.4f : holdS);
            m_Step++;
        }

        void OnGUI()
        {
            if (m_Style == null) m_Style = new GUIStyle(GUI.skin.box) { fontSize = 24, alignment = TextAnchor.MiddleCenter };
            GUI.Box(new Rect(Screen.width * 0.5f - 220, Screen.height - 70, 440, 50),
                $"Pose test: {Showing}  (robot's point of view)", m_Style);
        }
    }
}
