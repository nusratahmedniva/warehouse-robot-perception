using UnityEngine;

namespace WarehouseAvatar
{
    /// <summary>
    /// The LookCheck scene (Assets/WarehouseRobot/Avatar/LookCheck.unity, v4 Phase 2A): references to the config, the
    /// camera standing in for the pan-tilt camera, the light and the place where looks are spawned, plus the look, pose,
    /// distance and field of view to preview. Edit mode only: the Look Check menu (Editor) builds, poses and renders
    /// the looks; this component does nothing in Play mode.
    /// </summary>
    public class LookCheckStage : MonoBehaviour
    {
        public TextAsset config;
        [Tooltip("Stands in for the robot's pan-tilt camera; settings come from robot_unity_v4.json at every preview and render.")]
        public Camera checkCamera;
        public Light keyLight;
        [Tooltip("Parent of the spawned look, the floor and the backdrop (rebuilt at every preview; never saved with the scene).")]
        public Transform stageRoot;

        [Header("Preview (Inspector button 'Show')")]
        public string previewLook = "mixamo_worker";
        public string previewPose = "stop";
        public float previewDistanceM = 2.0f;
        public float previewFovDeg = 60.0f;
    }
}
