using System;
using System.Collections.Generic;
using System.Globalization;
using System.IO;
using System.Linq;
using UnityEditor;
using UnityEditor.SceneManagement;
using UnityEngine;
using WarehouseHRI;

namespace WarehouseRobot.GroundTruth.EditorTools
{
    /// <summary>
    /// Tools > Warehouse v4 > Measure Camera Heights (v4 Phase 2C, report only): opens WarehouseRobot_v4.unity and measures
    /// the robot cameras' heights above the floor in the scene itself: camera world y minus the top of the floor (colliders
    /// tagged placement.floor_tag, found as RobotRig.PlaceOnFloor finds it at Play), next to the values of
    /// robot_unity_v4.json. Also the floor height at every roadmap node (where the robot stops and the workers stand).
    /// Writes robot_vision/outputs/camera_height_v4_&lt;time&gt;/camera_height.json. Changes nothing in the scene.
    /// Batch: -executeMethod WarehouseRobot.GroundTruth.EditorTools.CameraHeightCheckV4.Batch (exit 0 = measured).
    /// </summary>
    public static class CameraHeightCheckV4
    {
        const string RepoRootRelativeToProject = "../../..";

        [Serializable]
        class Camera_
        {
            public string name;
            public float config_height_m, world_y, local_height_in_robot_m;
            public float floor_top_below_camera_y, height_above_floor_below_camera_m;
            public float height_above_floor_after_placement_m;
            public float pitch_deg, roll_deg;
        }

        [Serializable] class NodeFloor { public string node; public float x, z, floor_top_y; public bool found; }

        [Serializable]
        class Report
        {
            public string created, scene, robot_config, floor_tag, git_note;
            public float robot_pivot_y, floor_top_below_robot_y, robot_lossy_scale_y;
            public string floor_collider_below_robot;
            public List<Camera_> cameras = new List<Camera_>();
            public List<NodeFloor> roadmap_floor = new List<NodeFloor>();
            public string method;
        }

        [MenuItem("Tools/Warehouse v4/Measure Camera Heights")]
        public static void Menu()
        {
            if (!EditorSceneManager.SaveCurrentModifiedScenesIfUserWantsTo()) return;
            Measure(out string msg);
            Debug.Log("[CameraHeightV4] " + msg);
            EditorUtility.DisplayDialog("Measure Camera Heights", msg, "OK");
        }

        public static void Batch()
        {
            bool ok;
            string msg;
            try { ok = Measure(out msg); }
            catch (Exception e) { ok = false; msg = e.ToString(); }
            Debug.Log("[CameraHeightV4] " + msg);
            EditorApplication.Exit(ok ? 0 : 1);
        }

        static bool Measure(out string message)
        {
            if (EditorSceneManager.GetActiveScene().path != WarehouseV4Menu.V4Scene) EditorSceneManager.OpenScene(WarehouseV4Menu.V4Scene, OpenSceneMode.Single);
            var rig = UnityEngine.Object.FindFirstObjectByType<RobotRig>();
            var cfg = rig != null ? rig.Config : null;
            if (rig == null || cfg == null || !cfg.IsV4) { message = "no RobotRig with robot_unity_v4.json in " + WarehouseV4Menu.V4Scene; return false; }
            string tag = cfg.Unity.placement.floor_tag;
            Physics.SyncTransforms();

            var r = new Report
            {
                created = DateTime.Now.ToString("yyyy-MM-ddTHH:mm:ss", CultureInfo.InvariantCulture),
                scene = WarehouseV4Menu.V4Scene, robot_config = cfg.UnityConfigName, floor_tag = tag,
                robot_pivot_y = rig.transform.position.y, robot_lossy_scale_y = rig.transform.lossyScale.y,
                git_note = "the scene and configs of the working tree at the time of the run",
                method = "floor top = nearest hit of a downward ray (from placement.ray_start_above_m above the point, " +
                         "placement.ray_length_m long) on a collider tagged floor_tag that is not the robot's own, exactly as " +
                         "RobotRig.PlaceOnFloor. height_above_floor_below_camera_m = camera world y - floor top straight " +
                         "below the camera, in the scene as saved. height_above_floor_after_placement_m = the same after RobotRig.Awake " +
                         "puts the robot pivot on the floor below it (pivot y := floor top), i.e. what the camera has at Play.",
            };
            var place = cfg.Unity.placement;
            if (!FloorTop(place, rig.transform.position, rig.transform, out float robotFloor, out string floorName))
            {
                message = $"no collider tagged '{tag}' below the robot";
                return false;
            }
            r.floor_top_below_robot_y = robotFloor;
            r.floor_collider_below_robot = floorName;
            float placeShift = robotFloor - r.robot_pivot_y;

            void Add(string name, Transform t, float configHeight)
            {
                if (t == null) return;
                // the cameras sit on the mast above the robot's footprint: the floor below them is the robot's floor
                var e = t.eulerAngles;
                r.cameras.Add(new Camera_
                {
                    name = name, config_height_m = configHeight, world_y = t.position.y,
                    local_height_in_robot_m = rig.transform.InverseTransformPoint(t.position).y,
                    floor_top_below_camera_y = robotFloor, height_above_floor_below_camera_m = t.position.y - robotFloor,
                    height_above_floor_after_placement_m = t.position.y + placeShift - robotFloor,
                    pitch_deg = Mathf.DeltaAngle(0f, e.x), roll_deg = Mathf.DeltaAngle(0f, e.z),
                });
            }
            // RobotRig.PanTilt / Omni are set in Awake (Play only): look the cameras up directly
            var panTilt = rig.GetComponentInChildren<PanTiltCamera>(true);
            var omni = rig.GetComponentInChildren<Camera360>(true);
            Add("pan_tilt_camera", panTilt != null && panTilt.Camera != null ? panTilt.Camera.transform : null, cfg.Unity.pan_tilt_camera.height_m);
            Add("camera_360", omni != null ? omni.transform : null, cfg.Unity.camera_360.height_m);
            if (r.cameras.Count == 0) { message = "the robot has no cameras"; return false; }

            foreach (var n in UnityEngine.Object.FindObjectsByType<RoadNode>(FindObjectsSortMode.None).OrderBy(n => n.name, StringComparer.Ordinal))
                r.roadmap_floor.Add(new NodeFloor
                {
                    node = n.name, x = n.Position.x, z = n.Position.z,
                    found = FloorTop(place, n.Position, rig.transform, out float y, out _), floor_top_y = y,
                });

            string root = Path.GetFullPath(Path.Combine(Application.dataPath, "..", RepoRootRelativeToProject, "robot_vision", "outputs"));
            string dir = Path.Combine(root, "camera_height_v4_" + DateTime.Now.ToString("yyyyMMdd_HHmmss", CultureInfo.InvariantCulture));
            for (int i = 2; Directory.Exists(dir); i++) dir = Path.Combine(root, $"camera_height_v4_{DateTime.Now:yyyyMMdd_HHmmss}_{i}");
            Directory.CreateDirectory(dir);
            string file = Path.Combine(dir, "camera_height.json");
            using (var fs = new FileStream(file, FileMode.CreateNew))
            using (var w = new StreamWriter(fs, new System.Text.UTF8Encoding(false)))
                w.Write(JsonUtility.ToJson(r, true).Replace("\r\n", "\n") + "\n");

            var pt = r.cameras[0];
            message = string.Format(CultureInfo.InvariantCulture,
                "pan-tilt camera {0:F4} m above the floor at Play ({1:F4} m in the saved scene; config {2:F2} m); written to {3}",
                pt.height_above_floor_after_placement_m, pt.height_above_floor_below_camera_m, pt.config_height_m, file);
            return true;
        }

        /// <summary>
        /// Top of the floor below a point, found exactly as RobotRig.PlaceOnFloor finds it: a ray from ray_start_above_m above
        /// the point, ray_length_m down, the nearest hit on a collider with the floor tag that is not part of the robot.
        /// </summary>
        static bool FloorTop(PlacementConfig p, Vector3 at, Transform robot, out float y, out string colliderName)
        {
            y = -1f;
            colliderName = "";
            float best = float.PositiveInfinity;
            foreach (var hit in Physics.RaycastAll(at + Vector3.up * p.ray_start_above_m, Vector3.down, p.ray_length_m, ~0, QueryTriggerInteraction.Ignore))
            {
                if (hit.collider.transform.IsChildOf(robot) || hit.collider.gameObject.tag != p.floor_tag) continue;
                if (hit.distance < best) { best = hit.distance; y = hit.point.y; colliderName = hit.collider.name; }
            }
            return !float.IsPositiveInfinity(best);
        }
    }
}
