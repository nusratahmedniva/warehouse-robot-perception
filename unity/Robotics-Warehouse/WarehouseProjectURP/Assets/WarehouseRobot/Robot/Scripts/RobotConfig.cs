using System;
using System.Collections.Generic;
using System.IO;
using UnityEngine;

namespace WarehouseRobot
{
    /// <summary>Fields Unity uses from the shared robot_vision/configs/robot.json (the file Python reads too).</summary>
    [Serializable]
    public class SharedRobotConfig
    {
        public float robot_width_m;
        public float robot_length_m;
        public float robot_height_m;
        public float max_speed_mps;
        public float max_accel_mps2;
        public float decel_mps2;
        public float estop_decel_mps2;
        public float max_angular_speed_radps;
        public float max_angular_accel_radps2;
        /// <summary>Read by the v4 ground-truth grid only (widening = robot_width_m / 2 + this).</summary>
        public float safety_margin_per_side_m;
    }

    /// <summary>The zoom block of robot_vision/configs/v4/control.json (Python's zoom rule), read for Unity's clamp.</summary>
    [Serializable]
    public class ZoomRange
    {
        public float fov_default_deg;
        public float fov_min_deg;
        public float fov_max_deg;
    }

    [Serializable]
    class ZoomConfigFile
    {
        public ZoomRange zoom;
    }

    /// <summary>v4 study: the ground-truth layer (docs/project_flow_v4.md, "Ground-truth layer"; docs/protocol_v3.md).</summary>
    [Serializable]
    public class GroundTruthConfig
    {
        public string layer;
        public float cell_size_m;
        public float trail_interval_s;
        public float marker_radius_m;
        public float marker_height_m;
        public float line_width_m;
        public float path_point_size_m;
        public float floor_offset_m;
    }

    /// <summary>The v4 section of robot_unity_v4.json; absent (or enabled false) in the v3 robot_unity.json.</summary>
    [Serializable]
    public class V4RobotConfig
    {
        public bool enabled;
        public string zoom_config;
        public GroundTruthConfig ground_truth;
    }

    [Serializable]
    public class PathsConfig
    {
        public string repo_root_relative_to_unity_project;
        public string robot_config;
    }

    [Serializable]
    public class BodyConfig
    {
        public float ground_clearance_m;
        public float collider_bottom_m;
        public float wheel_radius_m;
        public float wheel_width_m;
        public float mass_kg;
    }

    [Serializable]
    public class MastConfig
    {
        public float radius_m;
        public float forward_offset_m;
    }

    [Serializable]
    public class Camera360Config
    {
        public float height_m;
        public int face_size_px;
        public int width_px;
        public int height_px;
        public float frame_rate_hz;
        public float near_m;
        public float far_m;
    }

    [Serializable]
    public class PanTiltCameraConfig
    {
        public float height_m;
        public int width_px;
        public int height_px;
        public float vertical_fov_deg;
        public float tilt_deg;
        public float near_m;
        public float far_m;
        public float pan_min_deg;
        public float pan_max_deg;
    }

    [Serializable]
    public class DebugConfig
    {
        public float keyboard_pan_speed_dps;
    }

    [Serializable]
    public class PlacementConfig
    {
        public string floor_tag;
        public float ray_start_above_m;
        public float ray_length_m;
    }

    [Serializable]
    public class CollisionsConfig
    {
        public string[] ignore_tags;
        public float merge_recontact_s;
    }

    [Serializable]
    public class ObstaclesConfig
    {
        public string[] groups;
        public bool make_rigidbodies_kinematic;
    }

    /// <summary>Assets/WarehouseRobot/Robot/Config/robot_unity.json.</summary>
    [Serializable]
    public class UnityRobotConfig
    {
        public PathsConfig paths;
        public BodyConfig body;
        public MastConfig mast;
        public Camera360Config camera_360;
        public PanTiltCameraConfig pan_tilt_camera;
        public DebugConfig debug;
        public PlacementConfig placement;
        public CollisionsConfig collisions;
        public ObstaclesConfig obstacles;
        public V4RobotConfig v4;
    }

    /// <summary>
    /// The Unity config plus the shared robot.json it names. Load() throws on a missing file or an invalid value;
    /// a missing JSON key reads as 0 and is caught by Validate().
    /// </summary>
    public class RobotConfig
    {
        public SharedRobotConfig Robot;
        public UnityRobotConfig Unity;
        public string RobotConfigPath;
        /// <summary>Name and text of the Unity config asset this was loaded from (recorded by the v4 trial runner).</summary>
        public string UnityConfigName, UnityConfigText;
        /// <summary>v4 only: Python's zoom range (configs/v4/control.json -> zoom), Unity's clamp for vertical_fov_deg. Null in v3.</summary>
        public ZoomRange Zoom;
        public string ZoomConfigPath;

        /// <summary>True for the v4 study config (robot_unity_v4.json, section v4 with enabled true).</summary>
        public bool IsV4 => Unity.v4 != null && Unity.v4.enabled;

        /// <summary>v4 ground-truth grid widening: robot half-width plus the safety margin per side (robot.json).</summary>
        public float GroundTruthInflationM => 0.5f * Robot.robot_width_m + Robot.safety_margin_per_side_m;

        public static RobotConfig Load(TextAsset unityConfig)
        {
            if (unityConfig == null)
                throw new InvalidOperationException("No Unity robot config assigned (robot_unity.json).");
            var unity = JsonUtility.FromJson<UnityRobotConfig>(unityConfig.text);
            if (unity == null || unity.paths == null || unity.body == null || unity.mast == null ||
                unity.camera_360 == null || unity.pan_tilt_camera == null || unity.debug == null || unity.placement == null ||
                unity.collisions == null || unity.obstacles == null)
                throw new InvalidOperationException(unityConfig.name + ": missing section (paths, body, mast, camera_360, pan_tilt_camera, debug, placement, collisions, obstacles).");
            if (string.IsNullOrEmpty(unity.paths.repo_root_relative_to_unity_project) || string.IsNullOrEmpty(unity.paths.robot_config))
                throw new InvalidOperationException(unityConfig.name + ": paths.repo_root_relative_to_unity_project and paths.robot_config are required.");

            // Unity project root = parent of Assets; the repo root and robot.json are relative to it (no absolute paths).
            string projectRoot = Path.GetDirectoryName(Application.dataPath);
            string robotPath = Path.GetFullPath(Path.Combine(projectRoot, unity.paths.repo_root_relative_to_unity_project, unity.paths.robot_config));
            if (!File.Exists(robotPath))
                throw new FileNotFoundException("Shared robot config not found (check paths in " + unityConfig.name + ")", robotPath);

            var cfg = new RobotConfig
            {
                Robot = JsonUtility.FromJson<SharedRobotConfig>(File.ReadAllText(robotPath)),
                Unity = unity,
                RobotConfigPath = robotPath,
                UnityConfigName = unityConfig.name,
                UnityConfigText = unityConfig.text,
            };
            if (cfg.IsV4)
            {
                if (string.IsNullOrEmpty(unity.v4.zoom_config) || unity.v4.ground_truth == null)
                    throw new InvalidOperationException(unityConfig.name + ": v4.zoom_config and v4.ground_truth are required when v4.enabled is true.");
                string zoomPath = Path.GetFullPath(Path.Combine(projectRoot, unity.paths.repo_root_relative_to_unity_project, unity.v4.zoom_config));
                if (!File.Exists(zoomPath))
                    throw new FileNotFoundException("v4 zoom config not found (check v4.zoom_config in " + unityConfig.name + ")", zoomPath);
                cfg.Zoom = JsonUtility.FromJson<ZoomConfigFile>(File.ReadAllText(zoomPath))?.zoom;
                cfg.ZoomConfigPath = zoomPath;
                if (cfg.Zoom == null) throw new InvalidOperationException(zoomPath + ": no zoom section");
            }
            var errors = cfg.Validate();
            if (errors.Count > 0)
                throw new InvalidOperationException("Invalid robot config:\n  " + string.Join("\n  ", errors));
            return cfg;
        }

        public List<string> Validate()
        {
            var e = new List<string>();
            void Positive(string name, float value)
            {
                if (!(value > 0f)) e.Add(name + " must be > 0 (got " + value + ")");
            }

            var r = Robot;
            Positive("robot.json robot_width_m", r.robot_width_m);
            Positive("robot.json robot_length_m", r.robot_length_m);
            Positive("robot.json robot_height_m", r.robot_height_m);
            Positive("robot.json max_speed_mps", r.max_speed_mps);
            Positive("robot.json max_accel_mps2", r.max_accel_mps2);
            Positive("robot.json decel_mps2", r.decel_mps2);
            Positive("robot.json estop_decel_mps2", r.estop_decel_mps2);
            if (r.estop_decel_mps2 < r.decel_mps2) e.Add("robot.json estop_decel_mps2 must be >= decel_mps2");
            Positive("robot.json max_angular_speed_radps", r.max_angular_speed_radps);
            Positive("robot.json max_angular_accel_radps2", r.max_angular_accel_radps2);

            var b = Unity.body;
            Positive("body.ground_clearance_m", b.ground_clearance_m);
            Positive("body.collider_bottom_m", b.collider_bottom_m);
            Positive("body.wheel_radius_m", b.wheel_radius_m);
            Positive("body.wheel_width_m", b.wheel_width_m);
            Positive("body.mass_kg", b.mass_kg);
            if (b.ground_clearance_m >= r.robot_height_m) e.Add("body.ground_clearance_m must be below robot_height_m");
            if (b.collider_bottom_m >= r.robot_height_m) e.Add("body.collider_bottom_m must be below robot_height_m");
            if (2f * b.wheel_width_m >= r.robot_width_m) e.Add("2 * body.wheel_width_m must be below robot_width_m");
            if (2f * b.wheel_radius_m > r.robot_length_m / 2f) e.Add("body.wheel_radius_m too large for robot_length_m");

            Positive("mast.radius_m", Unity.mast.radius_m);
            if (Mathf.Abs(Unity.mast.forward_offset_m) > r.robot_length_m / 2f) e.Add("mast.forward_offset_m lies outside the body");

            var p = Unity.pan_tilt_camera;
            Positive("pan_tilt_camera.height_m", p.height_m);
            Positive("pan_tilt_camera.width_px", p.width_px);
            Positive("pan_tilt_camera.height_px", p.height_px);
            Positive("pan_tilt_camera.vertical_fov_deg", p.vertical_fov_deg);
            Positive("pan_tilt_camera.near_m", p.near_m);
            if (p.vertical_fov_deg >= 180f) e.Add("pan_tilt_camera.vertical_fov_deg must be < 180");
            // far_m is a render distance only (no rendered depth is used); whether it reaches the whole scene is
            // checked at Play by RobotRig against the scene diagonal, since the config cannot know the scene.
            if (p.far_m <= p.near_m) e.Add("pan_tilt_camera.far_m must exceed near_m");
            if (p.tilt_deg != 0f) e.Add("pan_tilt_camera.tilt_deg must be 0: the lower-bound person distance assumes a level camera");
            if (p.pan_min_deg >= p.pan_max_deg) e.Add("pan_tilt_camera.pan_min_deg must be below pan_max_deg");
            if (p.height_m <= r.robot_height_m) e.Add("pan_tilt_camera.height_m must be above robot_height_m");

            var c = Unity.camera_360;
            Positive("camera_360.height_m", c.height_m);
            Positive("camera_360.face_size_px", c.face_size_px);
            Positive("camera_360.width_px", c.width_px);
            Positive("camera_360.height_px", c.height_px);
            Positive("camera_360.frame_rate_hz", c.frame_rate_hz);
            Positive("camera_360.near_m", c.near_m);
            if (c.far_m <= c.near_m) e.Add("camera_360.far_m must exceed near_m");
            if (c.width_px != 2 * c.height_px) e.Add("camera_360 equirectangular image must be 2:1 (width_px = 2 * height_px)");
            if (c.height_m <= p.height_m) e.Add("camera_360.height_m must be above pan_tilt_camera.height_m (360 camera on top of the mast)");

            Positive("debug.keyboard_pan_speed_dps", Unity.debug.keyboard_pan_speed_dps);

            var pl = Unity.placement;
            if (string.IsNullOrEmpty(pl.floor_tag)) e.Add("placement.floor_tag is required");
            Positive("placement.ray_start_above_m", pl.ray_start_above_m);
            if (pl.ray_length_m <= pl.ray_start_above_m) e.Add("placement.ray_length_m must exceed ray_start_above_m");
            if (Unity.collisions.ignore_tags == null) e.Add("collisions.ignore_tags is required (may be empty)");
            if (Unity.collisions.merge_recontact_s < 0f) e.Add("collisions.merge_recontact_s must be >= 0");
            if (Unity.obstacles.groups == null) e.Add("obstacles.groups is required (may be empty)");
            if (IsV4) ValidateV4(e);
            return e;
        }

        void ValidateV4(List<string> e)
        {
            var z = Zoom;
            if (z == null) { e.Add("v4: zoom range not loaded"); return; }
            if (!(z.fov_min_deg > 0f)) e.Add("v4 zoom fov_min_deg must be > 0");
            if (!(z.fov_max_deg < 180f)) e.Add("v4 zoom fov_max_deg must be < 180");
            if (!(z.fov_min_deg <= z.fov_default_deg && z.fov_default_deg <= z.fov_max_deg))
                e.Add("v4 zoom: fov_min_deg <= fov_default_deg <= fov_max_deg required");
            if (Mathf.Abs(z.fov_default_deg - Unity.pan_tilt_camera.vertical_fov_deg) > 1e-4f)
                e.Add($"v4 zoom fov_default_deg {z.fov_default_deg} differs from pan_tilt_camera.vertical_fov_deg {Unity.pan_tilt_camera.vertical_fov_deg}");
            var g = Unity.v4.ground_truth;
            if (string.IsNullOrEmpty(g.layer)) e.Add("v4.ground_truth.layer is required");
            if (!(g.cell_size_m > 0f)) e.Add("v4.ground_truth.cell_size_m must be > 0");
            if (!(g.trail_interval_s > 0f)) e.Add("v4.ground_truth.trail_interval_s must be > 0");
            if (!(g.marker_radius_m > 0f && g.marker_height_m > 0f && g.line_width_m > 0f && g.path_point_size_m > 0f))
                e.Add("v4.ground_truth marker_radius_m, marker_height_m, line_width_m and path_point_size_m must be > 0");
            if (g.floor_offset_m < 0f) e.Add("v4.ground_truth.floor_offset_m must be >= 0");
            if (Robot.safety_margin_per_side_m < 0f) e.Add("robot.json safety_margin_per_side_m must be >= 0 (v4 grid widening)");
        }
    }
}
