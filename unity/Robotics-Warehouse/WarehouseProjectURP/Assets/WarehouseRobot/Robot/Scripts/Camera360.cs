using System;
using UnityEngine;
using UnityEngine.Rendering;

namespace WarehouseRobot
{
    /// <summary>
    /// 360-degree camera on top of the mast: renders a cubemap (Camera.RenderToCubemap) and converts it to an
    /// equirectangular image (RenderTexture.ConvertToEquirect) at the configured frame rate. The camera component
    /// stays disabled so it never draws to the screen. RenderToCubemap renders world-axis faces, so the image is
    /// world-aligned: it does not rotate when the robot turns.
    /// </summary>
    [DisallowMultipleComponent]
    public class Camera360 : MonoBehaviour
    {
        [SerializeField] Camera cam;

        Camera360Config cfg;
        RenderTexture cubemap;
        float nextCaptureTime;
        bool reportedFailure;

        public RenderTexture Equirect { get; private set; }
        public int FramesCaptured { get; private set; }
        /// <summary>Time.time of the last successful capture (-1 before the first).</summary>
        public float LastCaptureTime { get; private set; } = -1f;
        public float FrameRateHz => cfg != null ? cfg.frame_rate_hz : 0f;
        public bool Ready => Equirect != null;
        public event Action<Camera360> FrameCaptured;

        public void Bind(Camera camera) => cam = camera;

        void Awake()
        {
            var rig = GetComponentInParent<RobotRig>();
            var config = rig != null ? rig.Config : null;
            if (config == null || cam == null)
            {
                Debug.LogError("[Camera360] No robot config or camera; 360 camera disabled.", this);
                enabled = false;
                return;
            }
            cfg = config.Unity.camera_360;
            ApplyCameraSettings(cam, cfg);
            cubemap = new RenderTexture(cfg.face_size_px, cfg.face_size_px, 24, RenderTextureFormat.ARGB32)
            {
                dimension = TextureDimension.Cube,
                name = "Camera360Cubemap",
            };
            cubemap.Create();
            Equirect = new RenderTexture(cfg.width_px, cfg.height_px, 0, RenderTextureFormat.ARGB32) { name = "Camera360Equirect" };
            Equirect.Create();
        }

        void LateUpdate()
        {
            if (Time.time < nextCaptureTime) return;
            float period = 1f / cfg.frame_rate_hz;
            nextCaptureTime = Mathf.Max(nextCaptureTime + period, Time.time);
            Capture();
        }

        /// <summary>Render one frame now. Returns false (and logs once) if Unity refuses the cubemap render.</summary>
        public bool Capture()
        {
            if (!Ready) return false;
            if (!cam.RenderToCubemap(cubemap, 63))
            {
                if (!reportedFailure)
                    Debug.LogError("[Camera360] Camera.RenderToCubemap returned false; no 360 image is produced.", this);
                reportedFailure = true;
                return false;
            }
            cubemap.ConvertToEquirect(Equirect, Camera.MonoOrStereoscopicEye.Mono);
            FramesCaptured++;
            LastCaptureTime = Time.time;
            FrameCaptured?.Invoke(this);
            return true;
        }

        void OnDestroy()
        {
            foreach (var rt in new[] { cubemap, Equirect })
            {
                if (rt == null) continue;
                rt.Release();
                Destroy(rt);
            }
        }

        public static void ApplyCameraSettings(Camera camera, Camera360Config c)
        {
            camera.enabled = false;
            camera.nearClipPlane = c.near_m;
            camera.farClipPlane = c.far_m;
            camera.allowMSAA = false;
        }
    }
}
