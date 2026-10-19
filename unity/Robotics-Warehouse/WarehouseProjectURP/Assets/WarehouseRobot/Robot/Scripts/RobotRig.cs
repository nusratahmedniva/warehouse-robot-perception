using System;
using UnityEngine;

namespace WarehouseRobot
{
    /// <summary>
    /// Root of the robot prefab: loads the config once for all robot components and checks at start that the
    /// prefab still matches it (rebuild the prefab after a config change).
    /// </summary>
    [DisallowMultipleComponent]
    public class RobotRig : MonoBehaviour
    {
        [SerializeField] TextAsset unityConfig;

        RobotConfig config;
        bool loadFailed;

        public DiffDriveController Drive { get; private set; }
        public PanTiltCamera PanTilt { get; private set; }
        public Camera360 Omni { get; private set; }
        public CollisionRecorder Collisions { get; private set; }

        /// <summary>Null when the config failed to load (the error is logged once).</summary>
        public RobotConfig Config
        {
            get
            {
                if (config == null && !loadFailed)
                {
                    try { config = RobotConfig.Load(unityConfig); }
                    catch (Exception ex)
                    {
                        loadFailed = true;
                        Debug.LogError("[RobotRig] " + ex.Message, this);
                    }
                }
                return config;
            }
        }

        public void Bind(TextAsset configAsset) => unityConfig = configAsset;

        void Awake()
        {
            Drive = GetComponent<DiffDriveController>();
            PanTilt = GetComponentInChildren<PanTiltCamera>(true);
            Omni = GetComponentInChildren<Camera360>(true);
            Collisions = GetComponent<CollisionRecorder>();
        }

        void Start()
        {
            var cfg = Config;
            if (cfg == null) return;
            const float tol = 0.001f;
            void CheckHeight(string name, Transform t, float expected)
            {
                if (t == null) { Debug.LogError("[RobotRig] " + name + " missing; rebuild the prefab.", this); return; }
                float h = transform.InverseTransformPoint(t.position).y;
                if (Mathf.Abs(h - expected) > tol)
                    Debug.LogError($"[RobotRig] {name} is at {h:F3} m, config says {expected:F3} m; rebuild the prefab (Warehouse Robot > Build Robot Prefab).", this);
            }
            CheckHeight("Pan-tilt camera", PanTilt != null ? PanTilt.transform : null, cfg.Unity.pan_tilt_camera.height_m);
            CheckHeight("360 camera", Omni != null ? Omni.transform : null, cfg.Unity.camera_360.height_m);

            var box = GetComponent<BoxCollider>();
            var expectedSize = new Vector3(cfg.Robot.robot_width_m, cfg.Robot.robot_height_m - cfg.Unity.body.collider_bottom_m, cfg.Robot.robot_length_m);
            if (box == null || (box.size - expectedSize).sqrMagnitude > tol * tol)
                Debug.LogError("[RobotRig] Body collider does not match robot.json; rebuild the prefab.", this);
            if (Vector3.Angle(transform.up, Vector3.up) > 0.01f)
                Debug.LogError("[RobotRig] Robot must be placed level (rotation X = Z = 0) so the cameras stay level.", this);

            CheckFarClipCoversScene(cfg);
        }

        /// <summary>
        /// far_m is a render distance only (v3 takes distance from flat-floor geometry, not rendered depth). It must
        /// reach across the whole scene, or distant walls and the ceiling render as skybox: compare it with the
        /// diagonal of the bounds of every renderer outside the robot (an upper bound on any in-scene distance).
        /// </summary>
        void CheckFarClipCoversScene(RobotConfig cfg)
        {
            bool any = false;
            var scene = new Bounds();
            foreach (var r in FindObjectsByType<Renderer>(FindObjectsSortMode.None))
            {
                if (!r.enabled || r.transform.IsChildOf(transform)) continue;
                if (any) scene.Encapsulate(r.bounds);
                else { scene = r.bounds; any = true; }
            }
            if (!any) return;
            float diagonal = scene.size.magnitude;
            void Check(string name, float farM)
            {
                if (farM < diagonal)
                    Debug.LogWarning($"[RobotRig] {name} far clip {farM:F0} m is shorter than the scene diagonal {diagonal:F1} m; distant geometry may render as skybox (raise far_m in robot_unity.json).", this);
                else
                    Debug.Log($"[RobotRig] {name} far clip {farM:F0} m covers the scene diagonal {diagonal:F1} m.", this);
            }
            Check("Pan-tilt camera", cfg.Unity.pan_tilt_camera.far_m);
            Check("360 camera", cfg.Unity.camera_360.far_m);
        }
    }
}
