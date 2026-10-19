using UnityEngine;

namespace WarehouseHRI
{
    /// <summary>
    /// VISION gesture source: the command in the latest Python reply (arm direction from YOLO11s-pose keypoints,
    /// STOP from MediaPipe via the gesture adapter). NONE when the reply is stale. The worker argument (scripted
    /// truth) is ignored. The 1.0 s hold rule stays in RobotBrain.
    /// </summary>
    public class VisionGestureSource : MonoBehaviour, IGestureSource
    {
        public HriBridgeClient bridge;
        public bool useConfigFile = true;
        public float staleAfterS = 0.5f;

        public string Label => "vision (YOLO11s-pose arm direction + MediaPipe STOP)";

        void Awake()
        {
            if (bridge == null) bridge = GetComponent<HriBridgeClient>();
            if (useConfigFile) staleAfterS = HriConfig.Current.perception.stale_after_s;
        }

        public GestureCommand Read(GestureWorker worker)
        {
            var r = bridge != null ? bridge.LatestPerception : null;
            if (r?.gesture == null || !VisionGeometry.Fresh(Time.time, bridge.LastReplyTime, staleAfterS)) return GestureCommand.NONE;
            return HriProtocol.ParseCommand(r.gesture.command);
        }
    }
}
