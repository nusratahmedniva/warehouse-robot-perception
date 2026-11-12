using System;
using System.Collections.Generic;
using System.Globalization;
using UnityEditor;
using UnityEditor.SceneManagement;
using UnityEngine;
using UnityEngine.SceneManagement;
using WarehouseRobot.Bridge;
using Object = UnityEngine.Object;

namespace WarehouseRobot.EditorTools
{
    /// <summary>
    /// Tools > Warehouse v4 > Build v4 Robot Body (2026-11-12, U1; Avatar/Config/upgrade_design.md section 7 and its
    /// section 13 entry): our own industrial AMR look for the robot of WarehouseRobot_v4.unity, built from Unity primitives
    /// and our own materials (no third-party asset): a rounded chassis (box core with capsule ends), front and rear bumpers
    /// with a yellow strip, side accent stripes, four visible wheels with hubs, a lidar puck, a mast with a base collar, a
    /// status light ring and a forward-facing display (RobotStatusDisplay). Visual only and added to the scene's robot
    /// instance (child "BodyV4" and wheel visuals); the v3 visuals of the instance (red box, plain mast and tyres) are
    /// deactivated. Rigidbody, colliders, NavMesh settings, the drive and both camera mounts and heights are untouched, and
    /// nothing reaches outside the robot's footprint. The prefab and the v3 scene are unchanged. Nothing is saved unless the
    /// pan-tilt self-visibility check passes for every pan, tilt and field of view in range. It also reports how far up the
    /// body reaches in the 360 image (P9: the excluded band is changed only if needed).
    /// Batch: Unity -batchmode -quit -projectPath P -executeMethod WarehouseRobot.EditorTools.RobotV4BodyBuilder.BatchBuild
    /// </summary>
    public static class RobotV4BodyBuilder
    {
        const string V4Scene = "Assets/Scenes/WarehouseRobot_v4.unity";
        const string MaterialsFolder = "Assets/WarehouseRobot/Robot/Materials/V4";
        const string BodyName = "BodyV4";
        static readonly CultureInfo Inv = CultureInfo.InvariantCulture;

        [MenuItem("Tools/Warehouse v4/Build v4 Robot Body")]
        public static void Menu()
        {
            if (SceneManager.GetActiveScene().path != V4Scene) { EditorUtility.DisplayDialog("Build v4 Robot Body", "Open " + V4Scene + " first.", "OK"); return; }
            bool ok = Build(out string report);
            Debug.Log("[RobotV4BodyBuilder] " + report);
            EditorUtility.DisplayDialog("Build v4 Robot Body", (ok ? "Built. Save the scene.\n\n" : "NOT built:\n\n") + report, "OK");
        }

        public static void BatchBuild()
        {
            var scene = EditorSceneManager.OpenScene(V4Scene, OpenSceneMode.Single);
            bool ok = Build(out string report);
            Debug.Log("[RobotV4BodyBuilder] " + report);
            if (!ok || !EditorSceneManager.SaveScene(scene)) { EditorApplication.Exit(1); return; }
            EditorApplication.Exit(0);
        }

        class Mats { public Material Body, Deck, Accent, Bumper, Strip, Tyre, Hub, Marker, Lidar, Metal, Light, Screen; }

        public static bool Build(out string report)
        {
            var rig = Object.FindFirstObjectByType<RobotRig>();
            if (rig == null || rig.Config == null || !rig.Config.IsV4) { report = "no RobotRig with the v4 config in the open scene"; return false; }
            var cfg = rig.Config;
            var root = rig.transform;
            var r = cfg.Robot;
            var b = cfg.Unity.body;
            float w = r.robot_width_m, l = r.robot_length_m, h = r.robot_height_m, wr = b.wheel_radius_m, ww = b.wheel_width_m, clr = b.ground_clearance_m;
            var mount = root.GetComponentInChildren<PanTiltCamera>(true);
            var omni = root.GetComponentInChildren<Camera360>(true);
            if (mount == null || omni == null) { report = "the robot has no pan-tilt mount or 360 camera"; return false; }

            var m = CreateMaterials();
            var old = root.Find(BodyName);
            if (old != null) Object.DestroyImmediate(old.gameObject);
            foreach (var name in new[] { "Body", "Mast" })
            {
                var t = root.Find(name);
                if (t != null) t.gameObject.SetActive(false);                    // v3 visuals of the instance (override; the prefab keeps them)
            }
            var body = new GameObject(BodyName).transform;
            body.SetParent(root, false);

            // chassis: a box core and capsule ends along x (rounded front and back), within the footprint
            float bodyH = h - clr, cy = clr + 0.5f * bodyH, rc = 0.5f * bodyH, coreL = l - 2f * rc, bw = w - 2f * ww - 0.01f;
            Part(PrimitiveType.Cube, "ChassisCore", body, new Vector3(0f, cy, 0f), new Vector3(bw, bodyH, coreL), Quaternion.identity, m.Body);
            foreach (float s in new[] { 1f, -1f })
                Part(PrimitiveType.Capsule, s > 0 ? "ChassisFront" : "ChassisRear", body, new Vector3(0f, cy, s * 0.5f * coreL),
                     new Vector3(bodyH, 0.5f * bw, bodyH), Quaternion.Euler(0f, 0f, 90f), m.Body);
            Part(PrimitiveType.Cube, "Deck", body, new Vector3(0f, h - 0.006f, 0f), new Vector3(bw - 0.02f, 0.012f, coreL + 0.14f), Quaternion.identity, m.Deck);
            // bumpers with a yellow strip, front and rear (in front of the capsule surface at their height, inside l / 2)
            float yb = clr + 0.08f, zb = 0.5f * coreL + Mathf.Sqrt(Mathf.Max(0f, rc * rc - (cy - yb) * (cy - yb))) + 0.012f;
            zb = Mathf.Min(zb, 0.5f * l - 0.016f);
            foreach (float s in new[] { 1f, -1f })
            {
                Part(PrimitiveType.Cube, s > 0 ? "BumperFront" : "BumperRear", body, new Vector3(0f, yb, s * zb), new Vector3(bw - 0.04f, 0.05f, 0.03f), Quaternion.identity, m.Bumper);
                Part(PrimitiveType.Cube, s > 0 ? "BumperStripFront" : "BumperStripRear", body, new Vector3(0f, yb + 0.032f, s * (zb - 0.004f)), new Vector3(bw - 0.06f, 0.012f, 0.03f), Quaternion.identity, m.Strip);
            }
            foreach (float s in new[] { 1f, -1f })
                Part(PrimitiveType.Cube, s > 0 ? "StripeRight" : "StripeLeft", body, new Vector3(s * (0.5f * bw + 0.002f), cy + 0.06f, 0f), new Vector3(0.004f, 0.035f, coreL), Quaternion.identity, m.Accent);

            // wheels: tyre, hub and a white marker per axle (they spin with the axle the drive turns)
            foreach (var axleName in new[] { "Wheel_FL", "Wheel_RL", "Wheel_FR", "Wheel_RR" })
            {
                var axle = root.Find(axleName);
                if (axle == null) { report = "no " + axleName; return false; }
                foreach (var child in new[] { "Tyre", "Marker" }) { var t = axle.Find(child); if (t != null) t.gameObject.SetActive(false); }
                foreach (var child in new[] { "TyreV4", "HubV4", "MarkerV4" }) { var t = axle.Find(child); if (t != null) Object.DestroyImmediate(t.gameObject); }
                float side = axle.localPosition.x < 0f ? -1f : 1f;
                Part(PrimitiveType.Cylinder, "TyreV4", axle, Vector3.zero, new Vector3(2f * wr, 0.5f * ww, 2f * wr), Quaternion.Euler(0f, 0f, 90f), m.Tyre);
                Part(PrimitiveType.Cylinder, "HubV4", axle, new Vector3(side * 0.002f, 0f, 0f), new Vector3(1.1f * wr, 0.5f * ww, 1.1f * wr), Quaternion.Euler(0f, 0f, 90f), m.Hub);
                Part(PrimitiveType.Cube, "MarkerV4", axle, new Vector3(side * (0.5f * ww + 0.003f), 0f, 0f), new Vector3(0.006f, 1.0f * wr, 0.02f), Quaternion.identity, m.Marker);
            }

            // lidar puck near the front of the deck
            Part(PrimitiveType.Cylinder, "LidarBase", body, new Vector3(0f, h + 0.02f, 0.5f * coreL), new Vector3(0.12f, 0.02f, 0.12f), Quaternion.identity, m.Lidar);
            Part(PrimitiveType.Cylinder, "LidarCap", body, new Vector3(0f, h + 0.045f, 0.5f * coreL), new Vector3(0.10f, 0.005f, 0.10f), Quaternion.identity, m.Metal);

            // mast (same place and size as before) with a base collar, and the status light ring
            var mast = cfg.Unity.mast;
            float top = cfg.Unity.camera_360.height_m;
            Part(PrimitiveType.Cylinder, "MastV4", body, new Vector3(0f, 0.5f * (h + top), mast.forward_offset_m), new Vector3(2f * mast.radius_m, 0.5f * (top - h), 2f * mast.radius_m), Quaternion.identity, m.Metal);
            Part(PrimitiveType.Cylinder, "MastCollar", body, new Vector3(0f, h + 0.03f, mast.forward_offset_m), new Vector3(0.08f, 0.03f, 0.08f), Quaternion.identity, m.Deck);
            var ring = Part(PrimitiveType.Cylinder, "StatusRing", body, new Vector3(0f, 0.95f, mast.forward_offset_m), new Vector3(0.11f, 0.0125f, 0.11f), Quaternion.identity, m.Light);
            float frontY = cy + 0.13f, frontZ = 0.5f * coreL + Mathf.Sqrt(Mathf.Max(0f, rc * rc - 0.13f * 0.13f)) + 0.004f;
            var bar = Part(PrimitiveType.Cube, "StatusBar", body, new Vector3(0f, frontY, Mathf.Min(frontZ, 0.5f * l - 0.006f)), new Vector3(0.28f, 0.012f, 0.008f), Quaternion.identity, m.Light);

            // front display: a dark panel with the robot's message, readable from in front of the robot
            float dy = cy + 0.02f, dz = Mathf.Min(0.5f * coreL + Mathf.Sqrt(Mathf.Max(0f, rc * rc - 0.02f * 0.02f)) + 0.006f, 0.5f * l - 0.008f);
            Part(PrimitiveType.Cube, "DisplayPanel", body, new Vector3(0f, dy, dz), new Vector3(0.30f, 0.10f, 0.01f), Quaternion.identity, m.Screen);
            var textGo = new GameObject("DisplayText");
            textGo.transform.SetParent(body, false);
            textGo.transform.localPosition = new Vector3(0f, dy, dz + 0.0055f);
            textGo.transform.localRotation = Quaternion.Euler(0f, 180f, 0f);        // a TextMesh faces -z: turned to face forward
            var tm = textGo.AddComponent<TextMesh>();
            var font = Resources.GetBuiltinResource<Font>("LegacyRuntime.ttf");
            tm.font = font;
            textGo.GetComponent<MeshRenderer>().sharedMaterial = font.material;
            tm.anchor = TextAnchor.MiddleCenter;
            tm.alignment = TextAlignment.Center;
            tm.fontSize = 48;
            tm.characterSize = 0.0045f;
            tm.text = "";

            var status = root.GetComponent<RobotStatusDisplay>() ?? root.gameObject.AddComponent<RobotStatusDisplay>();
            status.bridge = Object.FindFirstObjectByType<RobotBridgeClient>();
            status.lights = new[] { ring.GetComponent<Renderer>(), bar.GetComponent<Renderer>() };
            status.display = tm;

            // checks: nothing outside the footprint; nothing in any view of the pan-tilt camera; the body's reach in the 360 image
            var p = cfg.Unity.pan_tilt_camera;
            var problems = new List<string>();
            foreach (var rend in body.GetComponentsInChildren<Renderer>(true))
            {
                Bounds lb = rend.localBounds;
                for (int i = 0; i < 8; i++)
                {
                    var c = lb.center + Vector3.Scale(lb.extents, new Vector3((i & 1) == 0 ? -1 : 1, (i & 2) == 0 ? -1 : 1, (i & 4) == 0 ? -1 : 1));
                    Vector3 q = root.InverseTransformPoint(rend.transform.TransformPoint(c));
                    if (Mathf.Abs(q.x) > 0.5f * w + 1e-3f || Mathf.Abs(q.z) > 0.5f * l + 1e-3f) { problems.Add(rend.name + " outside the footprint"); break; }
                }
            }
            float vfov = Mathf.Max(p.vertical_fov_deg, mount.FovMaxDeg > 0f ? mount.FovMaxDeg : p.vertical_fov_deg);
            var seen = WarehouseHRI.V4.PanTiltGeometry.SelfVisibilityViolations(root, mount.transform.position, vfov, (float)p.width_px / p.height_px, p.near_m,
                                                                                 p.pan_min_deg, p.pan_max_deg, p.tilt_min_deg, p.tilt_max_deg);
            foreach (var s in seen) problems.Add(s + " visible to the pan-tilt camera");
            if (problems.Count > 0)
            {
                Object.DestroyImmediate(body.gameObject);
                report = "refused: " + string.Join("; ", problems);
                return false;
            }
            float reach = OmniReachDeg(root, omni.transform, cfg.Unity.camera_360.near_m, out string highest);
            int rows = Mathf.CeilToInt((90f + reach) / 180f * cfg.Unity.camera_360.height_px);
            EditorSceneManager.MarkSceneDirty(SceneManager.GetActiveScene());
            report = $"v4 body built ({body.childCount} parts, wheels restyled). Pan-tilt self-visibility: passed for pan {p.pan_min_deg:0}..{p.pan_max_deg:0}, " +
                     $"tilt {p.tilt_min_deg:0}..{p.tilt_max_deg:0} deg, field of view up to {vfov:0} deg. 360 image: the robot reaches up to " +
                     $"{reach.ToString("0.0", Inv)} deg elevation ({highest}), i.e. the bottom {rows} of {cfg.Unity.camera_360.height_px} rows.";
            return true;
        }

        /// <summary>The highest elevation (deg, negative = below the horizon) at which any active robot part beyond the near
        /// plane is seen from the 360 camera: the body occupies the image rows below it. The 360 camera's own head (a sphere
        /// inside its near plane, whose bounding box corners poke out of it) is not counted.</summary>
        static float OmniReachDeg(Transform root, Transform omni, float near, out string which)
        {
            float best = -90f;
            which = "-";
            Vector3 cam = omni.position;
            foreach (var rend in root.GetComponentsInChildren<Renderer>(false))
            {
                if (rend.transform.IsChildOf(omni)) continue;
                Bounds lb = rend.localBounds;
                for (int i = 0; i < 8; i++)
                {
                    var c = lb.center + Vector3.Scale(lb.extents, new Vector3((i & 1) == 0 ? -1 : 1, (i & 2) == 0 ? -1 : 1, (i & 4) == 0 ? -1 : 1));
                    Vector3 d = rend.transform.TransformPoint(c) - cam;
                    if (d.magnitude < near) continue;
                    float e = Mathf.Atan2(d.y, new Vector2(d.x, d.z).magnitude) * Mathf.Rad2Deg;
                    if (e < 0f && e > best) { best = e; which = rend.name; }
                }
            }
            return best;
        }

        static GameObject Part(PrimitiveType type, string name, Transform parent, Vector3 localPosition, Vector3 localScale, Quaternion localRotation, Material material)
        {
            var go = GameObject.CreatePrimitive(type);
            go.name = name;
            Object.DestroyImmediate(go.GetComponent<Collider>());               // visual only: the robot's colliders are unchanged
            go.transform.SetParent(parent, false);
            go.transform.localPosition = localPosition;
            go.transform.localRotation = localRotation;
            go.transform.localScale = localScale;
            go.GetComponent<MeshRenderer>().sharedMaterial = material;
            return go;
        }

        static Mats CreateMaterials()
        {
            EnsureFolder(MaterialsFolder);
            return new Mats
            {
                Body = Mat("RobotV4_Body", new Color(0.88f, 0.89f, 0.9f), 0.45f),
                Deck = Mat("RobotV4_Deck", new Color(0.22f, 0.24f, 0.27f), 0.3f),
                Accent = Mat("RobotV4_Accent", new Color(1f, 0.45f, 0.05f), 0.4f),
                Bumper = Mat("RobotV4_Bumper", new Color(0.06f, 0.06f, 0.07f), 0.2f),
                Strip = Mat("RobotV4_Strip", new Color(1f, 0.82f, 0.05f), 0.4f),
                Tyre = Mat("RobotV4_Tyre", new Color(0.05f, 0.05f, 0.05f), 0.15f),
                Hub = Mat("RobotV4_Hub", new Color(0.55f, 0.57f, 0.6f), 0.6f),
                Marker = Mat("RobotV4_Marker", new Color(0.95f, 0.95f, 0.95f), 0.3f),
                Lidar = Mat("RobotV4_Lidar", new Color(0.08f, 0.08f, 0.1f), 0.7f),
                Metal = Mat("RobotV4_Metal", new Color(0.62f, 0.64f, 0.67f), 0.75f),
                Light = Mat("RobotV4_Light", new Color(0.9f, 0.9f, 0.9f), 0.5f, true),
                Screen = Mat("RobotV4_Screen", new Color(0.03f, 0.04f, 0.06f), 0.8f),
            };
        }

        static Material Mat(string name, Color color, float smoothness, bool emissive = false)
        {
            string path = MaterialsFolder + "/" + name + ".mat";
            var mat = AssetDatabase.LoadAssetAtPath<Material>(path);
            if (mat == null)
            {
                var shader = Shader.Find("Universal Render Pipeline/Lit") ?? throw new InvalidOperationException("URP Lit shader not found.");
                mat = new Material(shader) { name = name };
                AssetDatabase.CreateAsset(mat, path);
            }
            mat.SetColor("_BaseColor", color);
            if (mat.HasProperty("_Smoothness")) mat.SetFloat("_Smoothness", smoothness);
            if (emissive)
            {
                mat.EnableKeyword("_EMISSION");
                mat.SetColor("_EmissionColor", color);
                mat.globalIlluminationFlags = MaterialGlobalIlluminationFlags.None;     // lights nothing in the scene
            }
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
    }
}
