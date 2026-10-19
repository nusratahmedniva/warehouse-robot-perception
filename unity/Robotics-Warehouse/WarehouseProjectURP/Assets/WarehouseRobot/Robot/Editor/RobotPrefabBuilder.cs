using System;
using UnityEditor;
using UnityEngine;
using Object = UnityEngine.Object;

namespace WarehouseRobot.EditorTools
{
    /// <summary>
    /// Menu "Warehouse Robot > Build Robot Prefab": builds the robot from robot_unity.json and the shared robot.json
    /// and saves it as Assets/WarehouseRobot/Robot/Prefabs/WarehouseRobot.prefab (materials in Robot/Materials).
    /// Run it again after any config change; placed instances update with the prefab.
    /// </summary>
    public static class RobotPrefabBuilder
    {
        // Unity asset paths (project-relative, the same on every OS).
        const string RobotFolder = "Assets/WarehouseRobot/Robot";
        const string ConfigAssetPath = RobotFolder + "/Config/robot_unity.json";
        const string MaterialsFolder = RobotFolder + "/Materials";
        const string PrefabsFolder = RobotFolder + "/Prefabs";
        const string PrefabPath = PrefabsFolder + "/WarehouseRobot.prefab";
        const string Title = "Build Robot Prefab";

        [MenuItem("Warehouse Robot/Build Robot Prefab")]
        public static void BuildPrefab()
        {
            var configAsset = AssetDatabase.LoadAssetAtPath<TextAsset>(ConfigAssetPath);
            RobotConfig cfg;
            try
            {
                cfg = RobotConfig.Load(configAsset);
            }
            catch (Exception ex)
            {
                Fail(ex.Message);
                return;
            }

            EnsureFolder(MaterialsFolder);
            EnsureFolder(PrefabsFolder);
            var mats = new Materials
            {
                Body = GetOrCreateMaterial("RobotBody_Red", new Color(0.80f, 0.05f, 0.05f)),
                Wheel = GetOrCreateMaterial("RobotWheel_Dark", new Color(0.08f, 0.08f, 0.08f)),
                Mast = GetOrCreateMaterial("RobotMast_Grey", new Color(0.55f, 0.55f, 0.55f)),
                Marker = GetOrCreateMaterial("RobotWheelMarker_White", new Color(0.95f, 0.95f, 0.95f)),
            };

            var root = new GameObject("WarehouseRobot");
            try
            {
                var panCamera = Build(root, cfg, configAsset, mats);
                var p = cfg.Unity.pan_tilt_camera;
                var problems = PanTiltCamera.SelfVisibilityViolations(root.transform, panCamera.transform.position, p.vertical_fov_deg, p.near_m);
                if (problems.Count > 0)
                {
                    Fail("Robot parts would appear in the pan-tilt camera image: " + string.Join(", ", problems) + ". Prefab not saved.");
                    return;
                }
                var prefab = PrefabUtility.SaveAsPrefabAsset(root, PrefabPath, out bool saved);
                if (!saved)
                {
                    Fail("Could not save " + PrefabPath);
                    return;
                }
                Debug.Log($"[RobotPrefabBuilder] Saved {PrefabPath} from {cfg.RobotConfigPath} and {ConfigAssetPath}. " +
                          "Pan-tilt self-visibility check passed.");
                Selection.activeObject = prefab;
                EditorGUIUtility.PingObject(prefab);
            }
            finally
            {
                Object.DestroyImmediate(root);
            }
        }

        class Materials
        {
            public Material Body, Wheel, Mast, Marker;
        }

        /// <summary>Builds the robot under root (pivot on the ground below the body centre) and returns the pan-tilt Camera.</summary>
        static Camera Build(GameObject root, RobotConfig cfg, TextAsset configAsset, Materials mats)
        {
            var r = cfg.Robot;
            var b = cfg.Unity.body;
            float w = r.robot_width_m, l = r.robot_length_m, h = r.robot_height_m;
            float wr = b.wheel_radius_m, ww = b.wheel_width_m;

            // Physics: one box over the whole footprint (wheels included), floating at collider_bottom_m. Gravity off and
            // Y position / X-Z rotation frozen keep the robot planar and its cameras level.
            var rb = root.AddComponent<Rigidbody>();
            rb.mass = b.mass_kg;
            rb.useGravity = false;
            rb.drag = 0f;
            rb.angularDrag = 0f;
            rb.interpolation = RigidbodyInterpolation.Interpolate;
            rb.collisionDetectionMode = CollisionDetectionMode.Continuous;
            rb.constraints = RigidbodyConstraints.FreezePositionY | RigidbodyConstraints.FreezeRotationX | RigidbodyConstraints.FreezeRotationZ;
            var box = root.AddComponent<BoxCollider>();
            box.center = new Vector3(0f, 0.5f * (b.collider_bottom_m + h), 0f);
            box.size = new Vector3(w, h - b.collider_bottom_m, l);

            root.AddComponent<RobotRig>().Bind(configAsset);

            // Body box between the wheels.
            Part(PrimitiveType.Cube, "Body", root.transform, new Vector3(0f, 0.5f * (b.ground_clearance_m + h), 0f),
                new Vector3(w - 2f * ww, h - b.ground_clearance_m, l), Quaternion.identity, mats.Body);

            // Four visual wheels, outer faces flush with robot_width_m. Each axle transform spins about its local X.
            var left = new Transform[2];
            var right = new Transform[2];
            float zWheel = 0.5f * l - wr;
            string[] names = { "Wheel_FL", "Wheel_RL", "Wheel_FR", "Wheel_RR" };
            for (int i = 0; i < 4; i++)
            {
                float side = i < 2 ? -1f : 1f; // -X = left
                float z = i % 2 == 0 ? zWheel : -zWheel;
                var axle = new GameObject(names[i]).transform;
                axle.SetParent(root.transform, false);
                axle.localPosition = new Vector3(side * (0.5f * w - 0.5f * ww), wr, z);
                Part(PrimitiveType.Cylinder, "Tyre", axle, Vector3.zero, new Vector3(2f * wr, 0.5f * ww, 2f * wr), Quaternion.Euler(0f, 0f, 90f), mats.Wheel);
                Part(PrimitiveType.Cube, "Marker", axle, new Vector3(side * (0.5f * ww + 0.003f), 0f, 0f), new Vector3(0.006f, 1.6f * wr, 0.03f), Quaternion.identity, mats.Marker);
                if (side < 0f) left[i] = axle; else right[i - 2] = axle;
            }
            var drive = root.AddComponent<DiffDriveController>();
            drive.SetWheels(left, right);

            // Mast from the body top to the 360 camera.
            var m = cfg.Unity.mast;
            var c360 = cfg.Unity.camera_360;
            var p = cfg.Unity.pan_tilt_camera;
            Part(PrimitiveType.Cylinder, "Mast", root.transform, new Vector3(0f, 0.5f * (h + c360.height_m), m.forward_offset_m),
                new Vector3(2f * m.radius_m, 0.5f * (c360.height_m - h), 2f * m.radius_m), Quaternion.identity, mats.Mast);

            // Pan-tilt camera: the mount pans, the camera is its level child. The small housing lies inside the near plane.
            var mount = new GameObject("PanTiltMount");
            mount.transform.SetParent(root.transform, false);
            mount.transform.localPosition = new Vector3(0f, p.height_m, m.forward_offset_m);
            var panCamGo = new GameObject("PanTiltCamera");
            panCamGo.transform.SetParent(mount.transform, false);
            var panCam = panCamGo.AddComponent<Camera>();
            PanTiltCamera.ApplyCameraSettings(panCam, p);
            panCam.enabled = false; // enabled at runtime once its render texture is assigned, so it never draws to the screen
            mount.AddComponent<PanTiltCamera>().Bind(panCam);
            float housing = 0.8f * p.near_m;
            Part(PrimitiveType.Cube, "PanTiltHousing", mount.transform, Vector3.zero, new Vector3(0.6f * housing, 0.5f * housing, 0.6f * housing), Quaternion.identity, mats.Wheel);

            // 360 camera on top of the mast; its head sphere lies inside the near plane.
            var omniGo = new GameObject("Camera360");
            omniGo.transform.SetParent(root.transform, false);
            omniGo.transform.localPosition = new Vector3(0f, c360.height_m, m.forward_offset_m);
            var omniCam = omniGo.AddComponent<Camera>();
            Camera360.ApplyCameraSettings(omniCam, c360);
            omniGo.AddComponent<Camera360>().Bind(omniCam);
            float head = 1.6f * c360.near_m;
            Part(PrimitiveType.Sphere, "Camera360Head", omniGo.transform, Vector3.zero, new Vector3(head, head, head), Quaternion.identity, mats.Wheel);

            root.AddComponent<CollisionRecorder>();
            root.AddComponent<RobotDebugPanel>();
            return panCam;
        }

        static GameObject Part(PrimitiveType type, string name, Transform parent, Vector3 localPosition, Vector3 localScale, Quaternion localRotation, Material material)
        {
            var go = GameObject.CreatePrimitive(type);
            go.name = name;
            Object.DestroyImmediate(go.GetComponent<Collider>()); // visual only; the root BoxCollider is the robot's collider
            go.transform.SetParent(parent, false);
            go.transform.localPosition = localPosition;
            go.transform.localRotation = localRotation;
            go.transform.localScale = localScale;
            go.GetComponent<MeshRenderer>().sharedMaterial = material;
            return go;
        }

        static Material GetOrCreateMaterial(string name, Color color)
        {
            string path = MaterialsFolder + "/" + name + ".mat";
            var mat = AssetDatabase.LoadAssetAtPath<Material>(path);
            if (mat == null)
            {
                var shader = Shader.Find("Universal Render Pipeline/Lit");
                if (shader == null) throw new InvalidOperationException("URP Lit shader not found.");
                mat = new Material(shader) { name = name };
                AssetDatabase.CreateAsset(mat, path);
            }
            if (mat.HasProperty("_BaseColor")) mat.SetColor("_BaseColor", color);
            else mat.color = color;
            EditorUtility.SetDirty(mat);
            AssetDatabase.SaveAssets();
            return mat;
        }

        static void EnsureFolder(string assetPath)
        {
            if (AssetDatabase.IsValidFolder(assetPath)) return;
            int slash = assetPath.LastIndexOf('/');
            string parent = assetPath.Substring(0, slash);
            EnsureFolder(parent);
            AssetDatabase.CreateFolder(parent, assetPath.Substring(slash + 1));
        }

        static void Fail(string message)
        {
            Debug.LogError("[RobotPrefabBuilder] " + message);
            EditorUtility.DisplayDialog(Title, message, "OK");
        }
    }
}
