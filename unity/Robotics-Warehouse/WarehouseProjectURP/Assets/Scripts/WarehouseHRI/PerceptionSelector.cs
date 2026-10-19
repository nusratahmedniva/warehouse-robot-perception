using UnityEngine;

namespace WarehouseHRI
{
    /// <summary>
    /// hri_config.json -> perception.mode chooses which sources RobotBrain uses: "scripted" (baselines) or "vision".
    /// Runs before RobotBrain.Awake and only sets the brain's existing interface fields; RobotBrain is not edited.
    /// </summary>
    [DefaultExecutionOrder(-100)]
    public class PerceptionSelector : MonoBehaviour
    {
        public RobotBrain brain;
        public ScriptedPersonSource scriptedPeople;
        public ScriptedGestureSource scriptedGestures;
        public VisionPersonSource visionPeople;
        public VisionGestureSource visionGestures;

        public bool Vision { get; private set; }

        void Awake()
        {
            Vision = HriConfig.Current.IsVision;
            if (brain == null) brain = GetComponent<RobotBrain>();
            if (brain == null) return;
            brain.personSourceBehaviour = Vision ? (MonoBehaviour)visionPeople : scriptedPeople;
            brain.gestureSourceBehaviour = Vision ? (MonoBehaviour)visionGestures : scriptedGestures;
            Debug.Log("[WarehouseHRI] Perception mode: " + (Vision ? "vision" : "scripted baseline"));
        }
    }
}
