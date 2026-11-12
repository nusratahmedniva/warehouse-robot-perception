using System.Collections.Generic;
using System.IO;
using System.Text;
using Unity.AI.Navigation;
using UnityEditor;
using UnityEditor.SceneManagement;
using UnityEngine;
using UnityEngine.AI;
using UnityEngine.SceneManagement;
using WarehouseHRI.V4;

namespace WarehouseHRI.EditorTools
{
    /// <summary>
    /// Tools > Warehouse v4 > Build v4 Roadmap (2026-11-12, P7 and P8; Avatar/Config/upgrade_design.md section 6): replaces
    /// the roadmap of WarehouseRobot_v4.unity (the v3 copy's A, J1, J2, E1-E4) with robot_vision/configs/v4/roadmap.json:
    /// A (kind Start, rotated to its start heading, with a worker stand), J1-J4 with worker stands, E1-E6, and the branches
    /// of the file (their labels are checked against the geometry, the rule of the v3 builder). Every node and branch is
    /// checked on the AMR NavMesh; nothing is saved if a check fails. Only the v4 scene is touched (the v3 scene keeps its
    /// roadmap). The Edit Mode test RoadmapV4Tests requires the saved scene and the file to be identical.
    /// Batch: Unity -batchmode -quit -projectPath P -executeMethod WarehouseHRI.EditorTools.RoadmapV4Builder.BatchBuild
    /// </summary>
    public static class RoadmapV4Builder
    {
        public const string V4Scene = "Assets/Scenes/WarehouseRobot_v4.unity";
        public const string RoadmapFile = "robot_vision/configs/v4/roadmap.json";
        public const string RoadmapRootName = "Roadmap";

        public static string RepoFile(string rel) => Path.GetFullPath(Path.Combine(Application.dataPath, "../../../..", rel));

        [MenuItem("Tools/Warehouse v4/Build v4 Roadmap")]
        public static void Menu()
        {
            if (SceneManager.GetActiveScene().path != V4Scene) { EditorUtility.DisplayDialog("Build v4 Roadmap", "Open " + V4Scene + " first.", "OK"); return; }
            bool ok = Build(out string report);
            Debug.Log("[RoadmapV4Builder] " + report);
            EditorUtility.DisplayDialog("Build v4 Roadmap", ok ? "Built. Save the scene.\n\n" + report : "NOT built:\n\n" + report, "OK");
        }

        public static void BatchBuild()
        {
            var scene = EditorSceneManager.OpenScene(V4Scene, OpenSceneMode.Single);
            bool ok = Build(out string report);
            Debug.Log("[RoadmapV4Builder] " + report);
            if (!ok) { EditorApplication.Exit(1); return; }
            if (!EditorSceneManager.SaveScene(scene)) { Debug.LogError("[RoadmapV4Builder] could not save " + V4Scene); EditorApplication.Exit(1); return; }
            EditorApplication.Exit(0);
        }

        /// <summary>Rebuilds the roadmap in the open scene; false (and nothing changed) when a check fails.</summary>
        public static bool Build(out string report)
        {
            var log = new StringBuilder();
            RoadmapV4 map;
            try { map = RoadmapV4.Parse(File.ReadAllText(RepoFile(RoadmapFile))); }
            catch (System.Exception e) { report = "cannot read " + RoadmapFile + ": " + e.Message; return false; }
            var labels = map.LabelProblems();
            if (labels.Count > 0) { report = "branch labels do not match the geometry: " + string.Join("; ", labels); return false; }

            GameObject root = null;
            foreach (var go in SceneManager.GetActiveScene().GetRootGameObjects())
                if (go.name == HriScenarioBuilder.RootName) root = go;
            if (root == null) { report = "no " + HriScenarioBuilder.RootName + " root in the scene"; return false; }
            var old = root.transform.Find(RoadmapRootName);
            float y = 0f;
            if (old != null)
            {
                var a = old.Find(map.Start);
                if (a != null) y = a.position.y;
            }

            // NavMesh check before anything changes
            int agent = int.MinValue;
            foreach (var surface in Object.FindObjectsOfType<NavMeshSurface>())
                if (surface.navMeshData != null) { agent = surface.agentTypeID; break; }
            if (agent == int.MinValue) { report = "no NavMesh Surface with baked data in the scene"; return false; }
            var filter = new NavMeshQueryFilter { agentTypeID = agent, areaMask = NavMesh.AllAreas };
            var problems = new List<string>();
            foreach (var n in map.Nodes)
                if (!NavMesh.SamplePosition(new Vector3(n.X, y, n.Z), out _, 0.5f, filter)) problems.Add($"{n.Name} not on the AMR NavMesh (0.5 m)");
            foreach (var kv in map.Branches)
                foreach (var b in kv.Value)
                {
                    var from = map.Node(kv.Key);
                    var to = map.Node(b.Value);
                    var path = new NavMeshPath();
                    if (!NavMesh.CalculatePath(new Vector3(from.X, y, from.Z), new Vector3(to.X, y, to.Z), filter, path) || path.status != NavMeshPathStatus.PathComplete)
                        problems.Add($"no complete NavMesh path {kv.Key} -> {b.Value}");
                }
            if (problems.Count > 0) { report = "NavMesh: " + string.Join("; ", problems); return false; }

            if (old != null) Object.DestroyImmediate(old.gameObject);
            var roadmap = new GameObject(RoadmapRootName).transform;
            roadmap.SetParent(root.transform, false);
            var nodes = new Dictionary<string, RoadNode>();
            foreach (var n in map.Nodes)
            {
                var go = new GameObject(n.Name);
                go.transform.SetParent(roadmap, false);
                go.transform.position = new Vector3(n.X, y, n.Z);
                if (n.HasStartYaw) go.transform.rotation = Quaternion.Euler(0f, n.StartYawDeg, 0f);
                var rn = go.AddComponent<RoadNode>();
                rn.kind = n.Kind == RoadmapV4.KindStart ? RoadNodeKind.Start : n.Kind == RoadmapV4.KindJunction ? RoadNodeKind.Junction : RoadNodeKind.Endpoint;
                nodes[n.Name] = rn;
                if (rn.IsAskNode)
                {
                    map.Stand(n, y, out var pos, out var rot);
                    var stand = new GameObject("WorkerStand").transform;
                    stand.SetParent(go.transform, false);
                    stand.SetPositionAndRotation(pos, rot);
                    rn.workerStand = stand;
                }
            }
            foreach (var kv in map.Branches)
            {
                var rn = nodes[kv.Key];
                rn.branches = new List<RoadBranch>();
                foreach (var b in kv.Value)
                    rn.branches.Add(new RoadBranch { command = (GestureCommand)System.Enum.Parse(typeof(GestureCommand), b.Key), next = nodes[b.Value] });
                log.Append(kv.Key).Append('[').Append(string.Join(", ", kv.Value.ConvertAll(b => b.Key + "->" + b.Value))).Append("] ");
            }
            foreach (var rn in nodes.Values) EditorUtility.SetDirty(rn);
            EditorSceneManager.MarkSceneDirty(SceneManager.GetActiveScene());
            report = $"v4 roadmap built from {RoadmapFile} at floor y {y:0.000}: {log}; every node and branch on the AMR NavMesh.";
            return true;
        }
    }
}
