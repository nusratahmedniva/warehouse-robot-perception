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
        public float max_angular_speed_radps;
        public float max_angular_accel_radps2;
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

        public static RobotConfig Load(TextAsset unityConfig)
        {
            if (unityConfig == null)
                throw new InvalidOperationException("No Unity robot config assigned (robot_unity.json).");
            var unity = JsonUtility.FromJson<UnityRobotConfig>(unityConfig.text);
            if (unity == null || unity.paths == null || unity.body == null || unity.mast == null ||
                unity.camera_360 == null || unity.pan_tilt_camera == null || unity.debug == null)
                throw new InvalidOperationException(unityConfig.name + ": missing section (paths, body, mast, camera_360, pan_tilt_camera, debug).");
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
            };
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
            return e;
        }
    }
}
