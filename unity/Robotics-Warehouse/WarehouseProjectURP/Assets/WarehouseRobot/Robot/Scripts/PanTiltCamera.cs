using System.Collections.Generic;
using UnityEngine;

namespace WarehouseRobot
{
    /// <summary>
    /// Pan-tilt camera on the mast. This component sits on the pan mount (rotates about the robot's up axis);
    /// the Camera is its child. Image size, vertical FOV, clip planes and tilt (must be 0) come from the config.
    /// At start it proves geometrically that no robot renderer can appear in the image at any pan angle.
    /// </summary>
    [DisallowMultipleComponent]
    public class PanTiltCamera : MonoBehaviour
    {
        [SerializeField] Camera cam;

        PanTiltCameraConfig cfg;

        public Camera Camera => cam;
        public RenderTexture Image { get; private set; }
        /// <summary>Current pan angle in degrees; &gt; 0 = left of the robot's forward axis.</summary>
        public float PanDeg { get; private set; }
        public float PanMinDeg => cfg != null ? cfg.pan_min_deg : 0f;
        public float PanMaxDeg => cfg != null ? cfg.pan_max_deg : 0f;
        public bool Ready => Image != null;

        public void Bind(Camera camera) => cam = camera;

        /// <summary>Set the pan angle (degrees, &gt; 0 = left); clamped to the configured range. Returns the angle applied.</summary>
        public float SetPanDeg(float deg)
        {
            if (cfg == null) return PanDeg;
            PanDeg = Mathf.Clamp(deg, cfg.pan_min_deg, cfg.pan_max_deg);
            transform.localRotation = Quaternion.Euler(0f, -PanDeg, 0f);
            return PanDeg;
        }

        void Awake()
        {
            var rig = GetComponentInParent<RobotRig>();
            var config = rig != null ? rig.Config : null;
            if (config == null || cam == null)
            {
                Debug.LogError("[PanTiltCamera] No robot config or camera; pan-tilt camera disabled.", this);
                enabled = false;
                return;
            }
            cfg = config.Unity.pan_tilt_camera;
            Image = new RenderTexture(cfg.width_px, cfg.height_px, 24, RenderTextureFormat.ARGB32) { name = "PanTiltCameraImage" };
            Image.Create();
            ApplyCameraSettings(cam, cfg);
            cam.targetTexture = Image;
            cam.enabled = true; // saved disabled in the prefab so it never draws to the screen before this point
            SetPanDeg(0f);
        }

        void Start()
        {
            if (cfg == null) return;
            var robot = GetComponentInParent<RobotRig>().transform;
            var problems = SelfVisibilityViolations(robot, cam.transform.position, cfg.vertical_fov_deg, cfg.near_m);
            if (problems.Count == 0)
                Debug.Log("[PanTiltCamera] Self-visibility check passed: no robot part can appear in the image at any pan angle.", this);
            else
                Debug.LogError("[PanTiltCamera] Robot parts can appear in the pan-tilt image: " + string.Join(", ", problems), this);
        }

        void OnDestroy()
        {
            if (Image == null) return;
            if (cam != null) cam.targetTexture = null;
            Image.Release();
            Destroy(Image);
        }

        public static void ApplyCameraSettings(Camera camera, PanTiltCameraConfig c)
        {
            camera.usePhysicalProperties = false;
            camera.fieldOfView = c.vertical_fov_deg; // Unity fieldOfView is vertical
            camera.nearClipPlane = c.near_m;
            camera.farClipPlane = c.far_m;
            camera.aspect = (float)c.width_px / c.height_px;
            camera.allowMSAA = false;
            camera.transform.localPosition = Vector3.zero;
            camera.transform.localRotation = Quaternion.Euler(c.tilt_deg, 0f, 0f);
        }

        /// <summary>
        /// Names of robot renderers that a level camera at cameraPosition could see at some pan angle. With pan about
        /// the robot's up axis and tilt 0, a point at horizontal distance d and height y relative to the camera has
        /// view depth z &lt;= d, so it is never visible if d &lt; near (clipped) or |y| &gt; tan(vfov/2) * d (outside the
        /// vertical field of view). Both regions are convex, so checking the 8 corners of each renderer's oriented
        /// local bounds covers the whole renderer.
        /// </summary>
        public static List<string> SelfVisibilityViolations(Transform robotRoot, Vector3 cameraPosition, float verticalFovDeg, float near)
        {
            float tanHalf = Mathf.Tan(0.5f * verticalFovDeg * Mathf.Deg2Rad);
            Quaternion toRobot = Quaternion.Inverse(robotRoot.rotation);
            var violations = new List<string>();
            foreach (var r in robotRoot.GetComponentsInChildren<Renderer>(true))
            {
                Bounds lb = r.localBounds;
                bool allClipped = true, allBelow = true, allAbove = true;
                for (int i = 0; i < 8; i++)
                {
                    var corner = lb.center + Vector3.Scale(lb.extents, new Vector3((i & 1) == 0 ? -1 : 1, (i & 2) == 0 ? -1 : 1, (i & 4) == 0 ? -1 : 1));
                    Vector3 p = toRobot * (r.transform.TransformPoint(corner) - cameraPosition);
                    float d = new Vector2(p.x, p.z).magnitude;
                    allClipped &= d < near;
                    allBelow &= p.y < -tanHalf * d;
                    allAbove &= p.y > tanHalf * d;
                }
                if (!(allClipped || allBelow || allAbove)) violations.Add(r.name);
            }
            return violations;
        }
    }
}
