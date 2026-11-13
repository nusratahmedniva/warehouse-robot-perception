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
        ZoomRange zoom;   // v4 only (robot_unity_v4.json); null in v3: the field of view stays at the default

        public Camera Camera => cam;
        public RenderTexture Image { get; private set; }
        /// <summary>Current pan angle in degrees; &gt; 0 = left of the robot's forward axis.</summary>
        public float PanDeg { get; private set; }
        public float PanMinDeg => cfg != null ? cfg.pan_min_deg : 0f;
        public float PanMaxDeg => cfg != null ? cfg.pan_max_deg : 0f;
        public bool Ready => Image != null;
        /// <summary>Configured vertical field of view (pan_tilt_camera.vertical_fov_deg): the unzoomed view.</summary>
        public float DefaultFovDeg => cfg != null ? cfg.vertical_fov_deg : 0f;
        /// <summary>Zoom range (v4: configs/v4/control.json -> zoom); without zoom both equal the default.</summary>
        public float FovMinDeg => zoom != null ? zoom.fov_min_deg : DefaultFovDeg;
        public float FovMaxDeg => zoom != null ? zoom.fov_max_deg : DefaultFovDeg;
        /// <summary>Vertical field of view the camera renders with now.</summary>
        public float FovDeg => cam != null ? cam.fieldOfView : 0f;
        /// <summary>Current tilt in degrees, &gt; 0 = up (v4, P6); the configured default (0, level) in v3.</summary>
        public float TiltDeg { get; private set; }
        public float DefaultTiltDeg => cfg != null ? cfg.tilt_deg : 0f;
        /// <summary>Tilt range (v4: robot_unity_v4.json pan_tilt_camera.tilt_min_deg / tilt_max_deg); without it both equal the default.</summary>
        public float TiltMinDeg => cfg != null && zoom != null ? cfg.tilt_min_deg : DefaultTiltDeg;
        public float TiltMaxDeg => cfg != null && zoom != null ? cfg.tilt_max_deg : DefaultTiltDeg;

        public void Bind(Camera camera) => cam = camera;

        /// <summary>Set the pan angle (degrees, &gt; 0 = left); clamped to the configured range. Returns the angle applied.</summary>
        public float SetPanDeg(float deg)
        {
            if (cfg == null) return PanDeg;
            PanDeg = Mathf.Clamp(deg, cfg.pan_min_deg, cfg.pan_max_deg);
            transform.localRotation = Quaternion.Euler(0f, -PanDeg, 0f);
            return PanDeg;
        }

        /// <summary>
        /// Zoom (v4): set the vertical field of view in degrees, clamped to [FovMinDeg, FovMaxDeg]. Takes effect from the
        /// next render; every frame_pan_tilt header reports the field of view and intrinsics it was rendered with.
        /// Returns the value applied.
        /// </summary>
        public float SetFovDeg(float deg)
        {
            if (cfg == null || cam == null) return FovDeg;
            cam.fieldOfView = Mathf.Clamp(deg, FovMinDeg, FovMaxDeg);
            return cam.fieldOfView;
        }

        /// <summary>
        /// Tilt (v4, P6): degrees, &gt; 0 = up, clamped to [TiltMinDeg, TiltMaxDeg]. The camera turns about its own x axis on
        /// the pan mount; takes effect from the next render, whose frame_pan_tilt header reports it. Returns the value applied.
        /// </summary>
        public float SetTiltDeg(float deg)
        {
            if (cfg == null || cam == null) return TiltDeg;
            TiltDeg = Mathf.Clamp(deg, TiltMinDeg, TiltMaxDeg);
            cam.transform.localRotation = Quaternion.Euler(-TiltDeg, 0f, 0f);     // Unity: + x rotation pitches down
            return TiltDeg;
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
            zoom = config.IsV4 ? config.Zoom : null;
            Image = new RenderTexture(cfg.width_px, cfg.height_px, 24, RenderTextureFormat.ARGB32) { name = "PanTiltCameraImage" };
            Image.Create();
            ApplyCameraSettings(cam, cfg);
            cam.targetTexture = Image;
            cam.enabled = true; // saved disabled in the prefab so it never draws to the screen before this point
            SetPanDeg(0f);
            TiltDeg = cfg.tilt_deg;
        }

        void Start()
        {
            if (cfg == null) return;
            var robot = GetComponentInParent<RobotRig>().transform;
            // The widest view the camera can take (the zoom range never exceeds it in v3: no zoom), at every tilt it can take.
            float vfov = Mathf.Max(cfg.vertical_fov_deg, FovMaxDeg);
            var problems = TiltMaxDeg > TiltMinDeg || TiltMinDeg != 0f
                ? WarehouseHRI.V4.PanTiltGeometry.SelfVisibilityViolations(robot, transform.position, vfov, (float)cfg.width_px / cfg.height_px, cfg.near_m,
                                                 cfg.pan_min_deg, cfg.pan_max_deg, TiltMinDeg, TiltMaxDeg)
                : SelfVisibilityViolations(robot, cam.transform.position, vfov, cfg.near_m);
            if (problems.Count == 0)
                Debug.Log($"[PanTiltCamera] Self-visibility check passed: no robot part can appear in the image at any pan angle and tilt {TiltMinDeg:0}..{TiltMaxDeg:0} deg.", this);
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
