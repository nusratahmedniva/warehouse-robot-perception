using System;
using System.Collections.Generic;
using System.Globalization;
using System.IO;
using System.Linq;
using System.Text;
using Unity.AI.Navigation;
using UnityEditor;
using UnityEditor.SceneManagement;
using UnityEngine;
using UnityEngine.AI;
using WarehouseHRI;
using WarehouseHRI.V4;
using WarehouseRobot.Bridge;
using WarehouseRobot.Scenario;

namespace WarehouseRobot.GroundTruth.EditorTools
{
    /// <summary>
    /// Tools > Warehouse v4 (v4 study, docs/project_flow_v4.md):
    /// - Create v4 Scene: copies Assets/Scenes/WarehouseRobot.unity (v3 study, left unchanged) to WarehouseRobot_v4.unity
    ///   and wires it for v4: the robot loads robot_unity_v4.json and the bridge bridge_unity_v4.json (scene overrides; the
    ///   prefab and the v3 configs are untouched), both robot cameras skip the GroundTruth layer, the HUD is added, the
    ///   v3 TrialRunner is replaced by TrialRunnerV4 and a GroundTruthLayer object is added. Refuses if the scene exists.
    /// - Grid Sensitivity Check: for A to every endpoint, the A* path on the official grid (robot_width_m / 2 +
    ///   safety_margin_per_side_m) and on a grid widened by the AMR NavMesh agent radius; reports whether the path or its
    ///   length differs (report only; the official grid stays as declared).
    /// - Leak Test (Edit Mode): the session leak test from A, into a new outputs folder.
    /// Batch mode: -executeMethod WarehouseRobot.GroundTruth.EditorTools.WarehouseV4Menu.BatchCreateScene / BatchGridCheck /
    /// BatchLeakTest (exit code 0 = done and passed).
    /// </summary>
    public static class WarehouseV4Menu
    {
        const string V3Scene = "Assets/Scenes/WarehouseRobot.unity";
        public const string V4Scene = "Assets/Scenes/WarehouseRobot_v4.unity";
        const string RobotConfigV4 = "Assets/WarehouseRobot/Robot/Config/robot_unity_v4.json";
        const string BridgeConfigV4 = "Assets/WarehouseRobot/Bridge/Config/bridge_unity_v4.json";
        const string RepoRootRelativeToProject = "../../..";
        static readonly CultureInfo Inv = CultureInfo.InvariantCulture;

        // ---------------- scene ----------------

        [MenuItem("Tools/Warehouse v4/Create v4 Scene")]
        public static void CreateScene()
        {
            if (!CreateSceneCore(out string message)) EditorUtility.DisplayDialog("Create v4 Scene", message, "OK");
            else Debug.Log("[WarehouseV4] " + message);
        }

        public static bool CreateSceneCore(out string message)
        {
            if (File.Exists(V4Scene)) { message = V4Scene + " already exists; it is never overwritten (delete it first to rebuild)."; return false; }
            var robotCfg = AssetDatabase.LoadAssetAtPath<TextAsset>(RobotConfigV4);
            var bridgeCfg = AssetDatabase.LoadAssetAtPath<TextAsset>(BridgeConfigV4);
            if (robotCfg == null || bridgeCfg == null) { message = "missing " + RobotConfigV4 + " or " + BridgeConfigV4; return false; }
            int layer = LayerMask.NameToLayer("GroundTruth");
            if (layer < 0) { message = "no layer named GroundTruth (Project Settings > Tags and Layers)"; return false; }
            if (EditorSceneManager.GetActiveScene().isDirty && !Application.isBatchMode &&
                !EditorSceneManager.SaveCurrentModifiedScenesIfUserWantsTo()) { message = "cancelled"; return false; }
            if (!AssetDatabase.CopyAsset(V3Scene, V4Scene)) { message = "could not copy " + V3Scene; return false; }

            var scene = EditorSceneManager.OpenScene(V4Scene, OpenSceneMode.Single);
            var rig = UnityEngine.Object.FindFirstObjectByType<RobotRig>();
            var bridge = UnityEngine.Object.FindFirstObjectByType<RobotBridgeClient>();
            var runner = UnityEngine.Object.FindFirstObjectByType<TrialRunner>();
            if (rig == null || bridge == null || runner == null)
            {
                message = "the copied scene lacks RobotRig, RobotBridgeClient or TrialRunner; " + V4Scene + " left as a plain copy";
                return false;
            }

            rig.Bind(robotCfg);
            PrefabUtility.RecordPrefabInstancePropertyModifications(rig);
            bridge.Bind(bridgeCfg, rig);
            Record(bridge);
            foreach (var cam in new[] { GroundTruthLayer.PanTiltCameraOf(rig), GroundTruthLayer.OmniCameraOf(rig) })
            {
                cam.cullingMask &= ~(1 << layer);
                PrefabUtility.RecordPrefabInstancePropertyModifications(cam);
            }

            var hud = bridge.GetComponent<HudOverlay>() != null ? bridge.GetComponent<HudOverlay>() : bridge.gameObject.AddComponent<HudOverlay>();
            hud.Bind(bridge);
            Record(hud);

            var host = runner.gameObject;
            UnityEngine.Object.DestroyImmediate(runner, true);
            Record(host.AddComponent<TrialRunnerV4>());

            var gtGo = new GameObject("GroundTruthLayer");
            gtGo.AddComponent<GroundTruthLayer>();
            gtGo.AddComponent<TrailRecorder>();

            EditorSceneManager.MarkSceneDirty(scene);
            if (!EditorSceneManager.SaveScene(scene)) { message = "could not save " + V4Scene; return false; }
            message = $"Created {V4Scene}: robot -> {RobotConfigV4}, bridge -> {BridgeConfigV4} (protocol 3), both robot cameras skip " +
                      $"layer GroundTruth ({layer}), HudOverlay added, TrialRunner replaced by TrialRunnerV4, GroundTruthLayer added. {V3Scene} is unchanged.";
            return true;
        }

        static void Record(Component c)
        {
            EditorUtility.SetDirty(c);
            if (PrefabUtility.IsPartOfPrefabInstance(c)) PrefabUtility.RecordPrefabInstancePropertyModifications(c);
        }

        // ---------------- grid sensitivity check ----------------

        [Serializable]
        class PairReport
        {
            public string a, b;
            public bool official_found, alternative_found;
            public double official_length_m = -1, alternative_length_m = -1, length_diff_m = -1;
            public bool same_cells, same_length;
            public string official_problem = "", alternative_problem = "";
        }

        [Serializable]
        class SensitivityReport
        {
            public string scene, robot_config, created;
            public double cell_size_m, official_widening_m, alternative_widening_m;
            public string official_rule = "robot_width_m / 2 + safety_margin_per_side_m (robot.json)";
            public string alternative_rule = "AMR NavMesh agent radius (the agent the robot's NavMesh paths use)";
            public string official_grid, alternative_grid;
            public bool any_difference;
            public List<PairReport> pairs = new List<PairReport>();
            public string note = "Report only: the official grid stays as declared (robot_unity_v4.json v4.ground_truth); a difference is for Nusrat and Anisha to decide on before any freeze.";
        }

        [MenuItem("Tools/Warehouse v4/Grid Sensitivity Check")]
        public static void GridCheck()
        {
            bool ok = GridCheckCore(out string message, out _);
            if (ok) Debug.Log("[WarehouseV4] " + message);
            else Debug.LogError("[WarehouseV4] " + message);
            if (!Application.isBatchMode) EditorUtility.DisplayDialog("Grid Sensitivity Check", message, "OK");
        }

        /// <summary>False when the check could not run. anyDifference: the alternative grid changes a path or a length.</summary>
        public static bool GridCheckCore(out string message, out bool anyDifference)
        {
            anyDifference = false;
            if (!Context(out var rig, out var cfg, out var nodes, out string start, out message)) return false;
            float floorY = FloorHeight(cfg, nodes[start].Position);
            double official = cfg.GroundTruthInflationM;
            if (!AgentRadius(out float radius, out message)) return false;

            var gOfficial = GroundTruthLayer.BuildGrid(cfg, rig.transform, floorY, official, out string rOfficial);
            var gAlt = GroundTruthLayer.BuildGrid(cfg, rig.transform, floorY, radius, out string rAlt);
            if (gOfficial == null || gAlt == null) { message = rOfficial; return false; }

            string folder = NewOutputFolder("gt_grid_check");
            var report = new SensitivityReport
            {
                scene = EditorSceneManager.GetActiveScene().path, robot_config = cfg.UnityConfigName, created = DateTime.Now.ToString("s", Inv),
                cell_size_m = gOfficial.CellSize, official_widening_m = official, alternative_widening_m = radius,
                official_grid = rOfficial, alternative_grid = rAlt,
            };
            var lines = new List<string>();
            foreach (var e in nodes.Values.Where(n => n.IsEndpoint).Select(n => n.name).OrderBy(n => n, StringComparer.Ordinal))
            {
                Vector3 a = nodes[start].Position, b = nodes[e].Position;
                var pr = new PairReport { a = start, b = e };
                pr.official_found = GroundTruthLayer.Plan(gOfficial, a, b, out var c1, out double l1, out string p1);
                pr.alternative_found = GroundTruthLayer.Plan(gAlt, a, b, out var c2, out double l2, out string p2);
                pr.official_problem = p1 ?? "";
                pr.alternative_problem = p2 ?? "";
                if (pr.official_found) pr.official_length_m = l1 * gOfficial.CellSize;
                if (pr.alternative_found) pr.alternative_length_m = l2 * gAlt.CellSize;
                pr.same_cells = pr.official_found && pr.alternative_found && c1.SequenceEqual(c2);
                pr.same_length = pr.official_found && pr.alternative_found && Math.Abs(pr.official_length_m - pr.alternative_length_m) < 1e-9;
                if (pr.official_found && pr.alternative_found) pr.length_diff_m = pr.alternative_length_m - pr.official_length_m;
                report.pairs.Add(pr);
                anyDifference |= !(pr.same_cells && pr.same_length);
                foreach (var (tag, g, ok, cells) in new[] { ("official", gOfficial, pr.official_found, c1), ("alternative", gAlt, pr.alternative_found, c2) })
                {
                    string dir = Path.Combine(folder, $"{start}_to_{e}_{tag}");
                    Directory.CreateDirectory(dir);
                    GroundTruthFiles.WriteNew(Path.Combine(dir, "grid.json"), GroundTruthFiles.ToJson(GroundTruthFiles.Grid(g, a.x, a.z, b.x, b.z)));
                    if (ok) GroundTruthFiles.WriteNew(Path.Combine(dir, "optimal_path.json"), GroundTruthFiles.ToJson(GroundTruthFiles.OptimalPath(g, cells)));
                }
                lines.Add($"{start} to {e}: official {(pr.official_found ? pr.official_length_m.ToString("0.000", Inv) + " m" : "NO PATH (" + p1 + ")")}, " +
                          $"alternative {(pr.alternative_found ? pr.alternative_length_m.ToString("0.000", Inv) + " m" : "NO PATH (" + p2 + ")")}, " +
                          $"same cells {pr.same_cells}, same length {pr.same_length}");
            }
            report.any_difference = anyDifference;
            GroundTruthFiles.WriteNew(Path.Combine(folder, "report.json"), JsonUtility.ToJson(report, true).Replace("\r\n", "\n") + "\n");
            message = $"Grid sensitivity check (official widening {official:0.000} m vs AMR agent radius {radius:0.000} m): " +
                      (anyDifference ? "PATHS OR LENGTHS DIFFER" : "no path or length differs") + ".\n" + string.Join("\n", lines) +
                      $"\nOfficial: {rOfficial}\nAlternative: {rAlt}\nFolder: {folder}";
            return true;
        }

        // ---------------- leak test in edit mode ----------------

        [MenuItem("Tools/Warehouse v4/Leak Test (Edit Mode)")]
        public static void LeakTest()
        {
            bool ok = LeakTestCore(out string message, out bool passed);
            if (ok && passed) Debug.Log("[WarehouseV4] " + message);
            else Debug.LogError("[WarehouseV4] " + message);
            if (!Application.isBatchMode) EditorUtility.DisplayDialog("Leak Test", message, "OK");
        }

        public static bool LeakTestCore(out string message, out bool passed)
        {
            passed = false;
            if (!Context(out var rig, out var cfg, out var nodes, out string start, out message)) return false;
            var gtRead = File.ReadAllText(RepoFile("robot_vision/configs/v4/gt_eval.json"));
            int maxDiff = JsonUtility.FromJson<GtEvalLeak>(gtRead).leak_max_pixel_diff;
            if (maxDiff < 0) { message = "configs/v4/gt_eval.json has no leak_max_pixel_diff"; return false; }

            var startNode = nodes[start];
            var first = startNode.OnlyNext;
            var goal = nodes.Values.Where(n => n.IsEndpoint).OrderBy(n => n.name, StringComparer.Ordinal).FirstOrDefault();
            if (goal == null) { message = "no endpoint in the roadmap"; return false; }
            var keepPos = rig.transform.position;
            var keepRot = rig.transform.rotation;
            var pan = GroundTruthLayer.PanTiltCameraOf(rig);
            var omni = GroundTruthLayer.OmniCameraOf(rig);
            int keepPanMask = pan.cullingMask, keepOmniMask = omni.cullingMask;
            var tmp = new GameObject("GroundTruthLayer (leak test, temporary)") { hideFlags = HideFlags.DontSave };
            try
            {
                Vector3 a = startNode.Position;
                float yaw = first != null ? Mathf.Atan2(first.Position.x - a.x, first.Position.z - a.z) * Mathf.Rad2Deg : 0f;
                rig.transform.SetPositionAndRotation(new Vector3(a.x, FloorHeight(cfg, a), a.z), Quaternion.Euler(0f, yaw, 0f));
                var gt = tmp.AddComponent<GroundTruthLayer>();
                if (!gt.Init(rig, out string err)) { message = "ground-truth layer: " + err; return false; }
                gt.Show(a, goal.Position);
                string folder = Path.Combine(NewOutputFolder("gt_leak_check"), GroundTruthFiles.LeakFolder);
                passed = gt.LeakTest(folder, maxDiff, out var pairs);
                message = $"Leak test (edit mode, robot at {start} facing {(first != null ? first.name : "-")}, ground truth to {goal.name}): " +
                          (passed ? "PASSED" : "FAILED") + "; " +
                          string.Join("; ", pairs.Select(p => $"{p.name} {p.width}x{p.height} max diff {p.max_diff}, {p.differing_pixels} pixels differ " +
                                                              $"(control: layer visible in {p.layer_visible_pixels} pixels when unmasked)")) +
                          $". Folder: {folder}";
                return true;
            }
            finally
            {
                UnityEngine.Object.DestroyImmediate(tmp);
                rig.transform.SetPositionAndRotation(keepPos, keepRot);
                pan.cullingMask = keepPanMask;
                omni.cullingMask = keepOmniMask;
            }
        }

        [Serializable] class GtEvalLeak { public int leak_max_pixel_diff = -1; }
        [Serializable] class RoadmapStart { public string start = "A"; }

        // ---------------- batch mode ----------------

        public static void BatchCreateScene() => Exit(CreateSceneCore(out string m), m);

        public static void BatchGridCheck()
        {
            OpenV4();
            bool ran = GridCheckCore(out string m, out bool diff);
            Exit(ran, m, diff ? 3 : 0);
        }

        public static void BatchLeakTest()
        {
            OpenV4();
            bool ran = LeakTestCore(out string m, out bool passed);
            Exit(ran, m, passed ? 0 : 4);
        }

        static void OpenV4()
        {
            if (EditorSceneManager.GetActiveScene().path != V4Scene) EditorSceneManager.OpenScene(V4Scene, OpenSceneMode.Single);
        }

        static void Exit(bool ok, string message, int codeIfOk = 0)
        {
            Debug.Log("[WarehouseV4] " + message);
            if (Application.isBatchMode) EditorApplication.Exit(ok ? codeIfOk : 2);
        }

        // ---------------- helpers ----------------

        static string RepoRoot => Path.GetFullPath(Path.Combine(Application.dataPath, "..", RepoRootRelativeToProject));
        static string RepoFile(string rel) => Path.GetFullPath(Path.Combine(RepoRoot, rel));

        /// <summary>The open scene's robot (with the v4 config), its roadmap and the roadmap start name.</summary>
        static bool Context(out RobotRig rig, out RobotConfig cfg, out Dictionary<string, RoadNode> nodes, out string start, out string error)
        {
            error = null;
            cfg = null;
            nodes = new Dictionary<string, RoadNode>();
            start = JsonUtility.FromJson<RoadmapStart>(File.ReadAllText(RepoFile("robot_vision/configs/roadmap.json"))).start;
            rig = UnityEngine.Object.FindFirstObjectByType<RobotRig>();
            foreach (var n in UnityEngine.Object.FindObjectsByType<RoadNode>(FindObjectsSortMode.None)) nodes[n.name] = n;
            if (rig == null || !nodes.ContainsKey(start)) { error = "open " + V4Scene + " (needs the robot and the roadmap)"; return false; }
            cfg = rig.Config;
            if (cfg == null || !cfg.IsV4) { error = "the robot in the open scene does not load robot_unity_v4.json (open " + V4Scene + ")"; cfg = null; return false; }
            return true;
        }

        /// <summary>Height of the floor (collider tagged placement.floor_tag) under a point, as RobotRig places the robot.</summary>
        static float FloorHeight(RobotConfig cfg, Vector3 at)
        {
            Physics.SyncTransforms();
            float best = float.NegativeInfinity;
            foreach (var hit in Physics.RaycastAll(at + Vector3.up * 50f, Vector3.down, 100f, ~0, QueryTriggerInteraction.Ignore))
                if (hit.collider.CompareTag(cfg.Unity.placement.floor_tag)) best = Mathf.Max(best, hit.point.y);
            return float.IsNegativeInfinity(best) ? at.y : best;
        }

        /// <summary>Radius of the NavMesh agent type the bridge plans with (bridge_unity_v4.json nav.agent_type).</summary>
        static bool AgentRadius(out float radius, out string error)
        {
            radius = 0f;
            error = null;
            var cfgAsset = AssetDatabase.LoadAssetAtPath<TextAsset>(BridgeConfigV4);
            string agent = JsonUtility.FromJson<UnityBridgeConfig>(cfgAsset.text).nav.agent_type;
            var surface = UnityEngine.Object.FindObjectsByType<NavMeshSurface>(FindObjectsInactive.Include, FindObjectsSortMode.None)
                .FirstOrDefault(s => NavMesh.GetSettingsNameFromID(s.agentTypeID) == agent);
            if (surface == null) { error = $"no NavMesh Surface with agent type '{agent}' in the scene"; return false; }
            radius = NavMesh.GetSettingsByID(surface.agentTypeID).agentRadius;
            return true;
        }

        static string NewOutputFolder(string prefix)
        {
            string root = RepoFile("robot_vision/outputs");
            Directory.CreateDirectory(root);
            string stamp = DateTime.Now.ToString("yyyyMMdd_HHmmss", Inv);
            string path = Path.Combine(root, $"{prefix}_{stamp}");
            for (int i = 2; Directory.Exists(path); i++) path = Path.Combine(root, $"{prefix}_{stamp}_{i}");
            Directory.CreateDirectory(path);
            return path;
        }
    }
}
