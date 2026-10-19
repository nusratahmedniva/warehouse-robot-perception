using UnityEngine;

namespace WarehouseHRI
{
    /// <summary>
    /// SCRIPTED-GESTURE BASELINE: returns the pose the worker was scripted to show. This is not vision and measures
    /// no gesture recognition; every run that uses it is labelled so in its log. Step 4 replaces it with the
    /// Python YOLO-pose + MediaPipe reader over TCP (another IGestureSource), without editing RobotBrain.
    /// </summary>
    public class ScriptedGestureSource : MonoBehaviour, IGestureSource
    {
        public const string BaselineLabel = "scripted-gesture baseline";

        [Tooltip("Read the worker's pose only within this horizontal distance (m), like a camera with limited range.")]
        public float maxRangeM = 6f;

        public bool useConfigFile = true;

        public string Label => BaselineLabel;

        void Awake()
        {
            if (useConfigFile) maxRangeM = HriConfig.Current.brain.gesture_read_range_m;
        }

        public GestureCommand Read(GestureWorker worker)
        {
            if (worker == null) return GestureCommand.NONE;
            Vector3 d = worker.transform.position - transform.position;
            d.y = 0f;
            return d.magnitude <= maxRangeM ? worker.Current : GestureCommand.NONE;
        }
    }
}
