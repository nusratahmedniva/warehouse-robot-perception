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
using WarehouseAvatar;
using WarehouseAvatar.EditorTools;
using WarehouseHRI.V4;
using WarehouseRobot.Bridge;
using WarehouseRobot.RobotCheck;
using WarehouseRobot.Scenario;
using Object = UnityEngine.Object;

namespace WarehouseRobot.EditorTools
{
    /// <summary>
    /// Answers for Anisha's recovery design (Avatar/Config/experiments_ab.md section 15 addendum 1, item 2; report only, nothing saved):
    /// (a) Tools > Warehouse v4 > Recovery > Reverse Drive Check (Play mode): the v4 scene opened unsaved, TrialRunnerV4 and the bridge
    /// client disabled, ReverseDriveCheck backs the robot up 1.0 m at 0.2 m/s with a development-look worker ahead;
    ///   Unity -projectPath P -executeMethod WarehouseRobot.EditorTools.RecoveryChecksMenu.CommandLineReverse -logFile reverse.log
    /// (b) Tools > Warehouse v4 > Recovery > Side Waypoints (Edit mode, batch): on the v4 scene's NavMesh of the bridge's agent type, for every
    /// road of every experiment map, a point every 0.5 m and a waypoint 1.0 m to each side: on the NavMesh, a complete path, and its length;
    ///   Unity -batchmode -projectPath P -executeMethod WarehouseRobot.EditorTools.RecoveryChecksMenu.BatchSideWaypoints -logFile side.log
    /// Exit code 0 = report written, 1 = failed.
    /// </summary>
    [InitializeOnLoad]
    public static class RecoveryChecksMenu
    {
        const string V4Scene = "Assets/Scenes/WarehouseRobot_v4.unity";
        const string BridgeConfigPath = "Assets/WarehouseRobot/Bridge/Config/bridge_unity_v4.json";
        const string ExperimentsPath = "Assets/WarehouseRobot/Scenario/Config/experiments_ab_unity.json";
        const string ActiveKey = "WarehouseRobot.RecoveryChecks.Active";
        const string QuitKey = "WarehouseRobot.RecoveryChecks.Quit";
        const string DeadlineKey = "WarehouseRobot.RecoveryChecks.Deadline";
        const string DevLook = "sunbox_m_shirt_white";
        const float SampleStepM = 0.5f, SideOffsetM = 1.0f, OnMeshM = 0.05f, MaxPathM = 1.5f, WorkerNearRoadM = 4.0f;
        static readonly CultureInfo Inv = CultureInfo.InvariantCulture;

        static RecoveryChecksMenu()
        {
            if (!SessionState.GetBool(ActiveKey, false)) return;
            EditorApplication.update += Poll;
        }

        // ---------------------------------------------------------------- (a) reverse drive (Play mode)

        [MenuItem("Tools/Warehouse v4/Recovery/Reverse Drive Check")]
        public static void ReverseMenu()
        {
            if (!EditorSceneManager.SaveCurrentModifiedScenesIfUserWantsTo()) return;
            StartReverse(false);
        }

        public static void CommandLineReverse() => StartReverse(true);

        static void StartReverse(bool quit)
        {
            var scene = EditorSceneManager.OpenScene(V4Scene, OpenSceneMode.Single);
            var disabled = new List<string>();
            foreach (var r in Object.FindObjectsByType<TrialRunnerV4>(FindObjectsInactive.Include, FindObjectsSortMode.None)) { r.enabled = false; disabled.Add("TrialRunnerV4 on " + r.name); }
            foreach (var b in Object.FindObjectsByType<RobotBridgeClient>(FindObjectsInactive.Include, FindObjectsSortMode.None)) { b.enabled = false; disabled.Add("RobotBridgeClient on " + b.name); }
            var prefab = AssetDatabase.LoadAssetAtPath<GameObject>(WorkerTemplateMenu.PrefabPath);
            var looks = AssetDatabase.LoadAssetAtPath<TextAsset>(ExperimentLooks.AssetPath);
            var go = new GameObject("ReverseDriveCheck");
            var d = go.AddComponent<ReverseDriveCheck>();
            d.workerPrefab = prefab != null ? prefab.GetComponent<WorkerV4>() : null;
            d.looksConfig = looks;
            d.look = DevLook;
            d.extraSources = Sources(looks);
            d.sceneNote = $"Scene {V4Scene} opened unsaved ({scene.name}); disabled for the check: {string.Join(", ", disabled)}.";
            SessionState.SetBool(ActiveKey, true);
            SessionState.SetBool(QuitKey, quit);
            SessionState.SetFloat(DeadlineKey, (float)EditorApplication.timeSinceStartup + 600f);
            EditorApplication.update -= Poll;
            EditorApplication.update += Poll;
            EditorApplication.EnterPlaymode();
        }

        /// <summary>The prefab-kind looks of looks_ab.json as worker sources (the Sunbox looks come with the worker template).</summary>
        static LookSource[] Sources(TextAsset looks)
        {
            var sources = new List<LookSource>();
            if (looks == null) return sources.ToArray();
            foreach (var l in ExperimentLooks.Parse(looks.text).looks)
            {
                if (l == null || l.kind != LookEntry.KindPrefab || sources.Exists(s => s.asset == l.asset)) continue;
                var p = AssetDatabase.LoadAssetAtPath<GameObject>(l.asset);
                if (p == null) continue;
                var mat = string.IsNullOrEmpty(l.material_override) ? null : AssetDatabase.LoadAssetAtPath<Material>(l.material_override);
                sources.Add(new LookSource { asset = l.asset, prefab = p, materialOverride = mat });
            }
            return sources.ToArray();
        }

        static void Poll()
        {
            if (!SessionState.GetBool(ActiveKey, false)) return;
            if (EditorApplication.timeSinceStartup > SessionState.GetFloat(DeadlineKey, float.MaxValue)) { Finish(1, "timeout"); return; }
            if (!EditorApplication.isPlaying) return;
            var d = Object.FindFirstObjectByType<ReverseDriveCheck>();
            if (d == null) return;
            if (d.Status.StartsWith("done", StringComparison.Ordinal)) Finish(0, d.Status + " (" + d.OutputFolder + ")");
            else if (d.Status.StartsWith("failed", StringComparison.Ordinal)) Finish(1, d.Status);
        }

        static void Finish(int code, string status)
        {
            SessionState.SetBool(ActiveKey, false);
            EditorApplication.update -= Poll;
            Debug.Log($"[RecoveryChecks] reverse drive check finished ({code}): {status}");
            if (SessionState.GetBool(QuitKey, false)) EditorApplication.Exit(code);
            else EditorApplication.ExitPlaymode();
        }

        // ---------------------------------------------------------------- (b) side waypoints (Edit mode)

        [Serializable] class NavCfg { public string agent_type = ""; public float snap_max_distance_m; }
        [Serializable] class BridgeUnityNav { public NavCfg nav = new NavCfg(); }

        [MenuItem("Tools/Warehouse v4/Recovery/Side Waypoints (NavMesh)")]
        public static void SideWaypointsMenu()
        {
            if (!EditorSceneManager.SaveCurrentModifiedScenesIfUserWantsTo()) return;
            Debug.Log("[RecoveryChecks] " + SideWaypoints(out _));
        }

        public static void BatchSideWaypoints()
        {
            string msg = SideWaypoints(out bool ok);
            Debug.Log("[RecoveryChecks] " + msg);
            EditorApplication.Exit(ok ? 0 : 1);
        }

        sealed class Row
        {
            public string Map, Road, Side, Status;
            public float S, X, Z, RoadSnap, Wx, Wz, WpSnap, PathLen;
            public bool OnMesh, Reachable;
        }

        static string SideWaypoints(out bool ok)
        {
            ok = false;
            EditorSceneManager.OpenScene(V4Scene, OpenSceneMode.Single);
            var navText = AssetDatabase.LoadAssetAtPath<TextAsset>(BridgeConfigPath);
            if (navText == null) return "failed: " + BridgeConfigPath + " not found";
            string agent = JsonUtility.FromJson<BridgeUnityNav>(navText.text).nav.agent_type;
            var surface = Object.FindObjectsByType<NavMeshSurface>(FindObjectsInactive.Include, FindObjectsSortMode.None)
                                .FirstOrDefault(s => NavMesh.GetSettingsNameFromID(s.agentTypeID) == agent);
            if (surface == null || surface.navMeshData == null || !surface.isActiveAndEnabled) return $"failed: no baked, enabled NavMesh Surface of agent type '{agent}' in {V4Scene}";
            var filter = new NavMeshQueryFilter { agentTypeID = surface.agentTypeID, areaMask = NavMesh.AllAreas };

            string projectDir = Path.GetFullPath(Path.Combine(Application.dataPath, ".."));
            string repo = Path.GetFullPath(Path.Combine(projectDir, "..", "..", ".."));
            var cfg = ExperimentsUnityConfig.Parse(File.ReadAllText(Path.Combine(projectDir, ExperimentsPath)));
            cfg.a2_sides = new[] { "right", "left" };
            string scen = File.ReadAllText(Path.Combine(repo, cfg.scenarios_ab)), road = File.ReadAllText(Path.Combine(repo, cfg.roadmap_v4));
            Func<string, string> read = p => File.ReadAllText(Path.Combine(projectDir, p));
            var maps = new List<(string name, RoadmapV4 map, ExperimentPlanAB plan, int run)>();
            foreach (var e in new[] { "A1", "A2", "A3" })
            {
                var p = ExperimentPlanAB.Build(cfg, e, scen, road, read, out string error);
                if (p == null) return "failed: " + error;
                maps.Add((p.MapName, p.Map, p, -1));
                if (p.LeftMap != null) maps.Add(("turn_left", p.LeftMap, p, -1));
            }

            var rows = new List<Row>();
            var path = new NavMeshPath();
            foreach (var (name, map, _, _) in maps)
                foreach (var (a, b, label) in UniqueRoads(map))
                {
                    var dir = new Vector3(b.x - a.x, 0f, b.z - a.z);
                    float len = dir.magnitude;
                    dir /= len;
                    var right = Vector3.Cross(Vector3.up, dir);
                    int n = Mathf.FloorToInt(len / SampleStepM + 1e-4f);
                    for (int i = 0; i <= n; i++)
                    {
                        float s = i * SampleStepM;
                        var p = a + dir * s;
                        bool roadOk = NavMesh.SamplePosition(new Vector3(p.x, 0f, p.z), out var hp, 2f, filter);
                        foreach (var (side, sign) in new[] { ("left", -1f), ("right", 1f) })
                        {
                            var w = p + right * (sign * SideOffsetM);
                            var r = new Row { Map = name, Road = label, Side = side, S = s, X = p.x, Z = p.z, Wx = w.x, Wz = w.z, RoadSnap = -1f, WpSnap = -1f, PathLen = -1f, Status = "start_off_navmesh" };
                            if (roadOk) r.RoadSnap = Flat(hp.position - p);
                            if (NavMesh.SamplePosition(new Vector3(w.x, 0f, w.z), out var hw, 2f, filter))
                            {
                                r.WpSnap = Flat(hw.position - w);
                                r.OnMesh = r.WpSnap <= OnMeshM;
                                if (roadOk)
                                {
                                    NavMesh.CalculatePath(hp.position, hw.position, filter, path);
                                    r.Status = path.status == NavMeshPathStatus.PathComplete ? "complete" : path.status == NavMeshPathStatus.PathPartial ? "partial" : "invalid";
                                    if (path.status != NavMeshPathStatus.PathInvalid)
                                    {
                                        float l = 0f;
                                        for (int k = 1; k < path.corners.Length; k++) l += Vector3.Distance(path.corners[k - 1], path.corners[k]);
                                        r.PathLen = l;
                                    }
                                }
                            }
                            else r.Status = "waypoint_off_navmesh";
                            r.Reachable = r.OnMesh && r.Status == "complete" && r.PathLen >= 0f && r.PathLen <= MaxPathM;
                            rows.Add(r);
                        }
                    }
                }

            // where the live beside layout puts its workers along each road (seed 1, run 1; the slots are the same in every run)
            var workerLines = new List<string>();
            foreach (var (name, map, plan, _) in maps)
            {
                if (plan.LayoutKind != "beside") continue;
                int run = 1;
                if (name == "turn_left") run = Enumerable.Range(1, 40).First(x => { plan.RunMap(1, x, out var nm); return nm == "turn_left"; });
                else if (name == "turn") run = Enumerable.Range(1, 40).First(x => { plan.RunMap(1, x, out var nm); return nm == "turn"; });
                string goal = plan.Goals(1, run)[run - 1];
                var rp = plan.PlanRun(1, run, goal, new[] { "m" }, new[] { "f" }, null, out string err);
                if (rp == null) { workerLines.Add($"- {name}: not planned ({err})"); continue; }
                foreach (var (a, b, label) in UniqueRoads(map))
                {
                    var dir = new Vector3(b.x - a.x, 0f, b.z - a.z);
                    float len = dir.magnitude;
                    dir /= len;
                    var right = Vector3.Cross(Vector3.up, dir);
                    var near = new List<string>();
                    foreach (var w in rp.Workers)
                    {
                        var q = w.Position - a;
                        float s = Vector3.Dot(q, dir), lat = Vector3.Dot(q, right);
                        if (s < -1f || s > len + 1f || Mathf.Abs(lat) > WorkerNearRoadM) continue;
                        near.Add($"worker {w.Id} ({w.Node} slot {w.Slot + 1}) {(lat < 0f ? "left" : "right")} {Mathf.Abs(lat).ToString("0.00", Inv)} m at s {s.ToString("0.0", Inv)} m");
                    }
                    workerLines.Add($"- {name} {label}: " + (near.Count > 0 ? string.Join("; ", near) : "no worker within 4 m"));
                }
            }

            string stamp = DateTime.Now.ToString("yyyyMMdd_HHmmss", Inv);
            string outDir = Path.Combine(repo, "robot_vision", "outputs", "navmesh_side_waypoints_" + stamp);
            if (Directory.Exists(outDir)) return "failed: " + outDir + " exists";
            Directory.CreateDirectory(outDir);
            var csv = new StringBuilder("map,road,s_m,x,z,road_snap_m,side,waypoint_x,waypoint_z,waypoint_snap_m,on_navmesh,path_status,path_length_m,reachable\n");
            foreach (var r in rows)
                csv.Append($"{r.Map},{r.Road},{F(r.S, 1)},{F(r.X, 2)},{F(r.Z, 2)},{F(r.RoadSnap, 3)},{r.Side},{F(r.Wx, 2)},{F(r.Wz, 2)},{F(r.WpSnap, 3)},{(r.OnMesh ? 1 : 0)},{r.Status},{F(r.PathLen, 3)},{(r.Reachable ? 1 : 0)}\n");
            var md = new StringBuilder();
            md.Append($"# Side waypoints on the NavMesh ({DateTime.Now.ToString("yyyy-MM-dd HH:mm:ss", Inv)})\n\n");
            md.Append("experiments_ab.md section 15 addendum 1, item 2b (Anisha's recovery: after backing up, a waypoint 1.0 m to the clear side of the road). " +
                      $"Edit mode, {V4Scene} (not saved), NavMesh Surface '{surface.name}' of the bridge's agent type {agent} (bridge_unity_v4.json; radius 0.5 m, " +
                      "so the NavMesh already keeps the robot centre 0.5 m from obstacles). For every road of every experiment map, a point every " +
                      $"{F(SampleStepM, 1)} m from one node to the other (both ends included) and a waypoint {F(SideOffsetM, 1)} m to its left and right (seen " +
                      $"driving from the first node to the second). Reachable = the waypoint is on the NavMesh within {F(OnMeshM, 2)} m (horizontal), the path from " +
                      $"the road point (snapped) is complete and at most {F(MaxPathM, 1)} m long. Static geometry only: workers are not obstacles on the NavMesh " +
                      "(the robot's person-in-path stop is Python's).\n\n");
            md.Append("| map | road | side | points | reachable | not reachable (s along the road, m) | worst reason |\n|---|---|---|---|---|---|---|\n");
            foreach (var g in rows.GroupBy(r => (r.Map, r.Road, r.Side)))
            {
                var list = g.ToList();
                int okN = list.Count(r => r.Reachable);
                var bad = list.Where(r => !r.Reachable).ToList();
                string reason = bad.Count == 0 ? "-" : bad.GroupBy(r => !r.OnMesh ? (r.WpSnap < 0f ? "waypoint off the NavMesh" : $"waypoint {F(bad.Where(x => !x.OnMesh).Max(x => x.WpSnap), 2)} m off the NavMesh (max)") : r.Status != "complete" ? "path " + r.Status : "path longer than " + F(MaxPathM, 1) + " m")
                                                 .OrderByDescending(x => x.Count()).Select(x => $"{x.Key} ({x.Count()})").Aggregate((x, y) => x + "; " + y);
                md.Append($"| {g.Key.Map} | {g.Key.Road} | {g.Key.Side} | {list.Count} | {okN} | {Intervals(bad.Select(r => r.S).ToList())} | {reason} |\n");
            }
            // negative control: the same reachability test toward points the ground-truth grid marks blocked (rack centres) and beyond the
            // south wall, from the nearest aisle point of a road; it must say "not reachable", or the counts above could not fail
            var controls = new List<string>();
            bool controlsOk = true;
            foreach (var (from, c) in new[] { (new Vector3(6.25f, 0f, -5f), new Vector3(0f, 0f, -5f)), (new Vector3(6.25f, 0f, -15f), new Vector3(12.5f, 0f, -15f)),
                                               (new Vector3(-6.25f, 0f, 15f), new Vector3(-12.5f, 0f, 15f)), (new Vector3(6.25f, 0f, -20f), new Vector3(6.25f, 0f, -27.5f)) })
            {
                bool f1 = NavMesh.SamplePosition(from, out var hf, 2f, filter);
                bool found = NavMesh.SamplePosition(c, out var hc, 2f, filter);
                float snap = found ? Flat(hc.position - c) : -1f;
                string st = "no path";
                float len = -1f;
                if (f1 && found)
                {
                    NavMesh.CalculatePath(hf.position, hc.position, filter, path);
                    st = path.status == NavMeshPathStatus.PathComplete ? "complete" : path.status == NavMeshPathStatus.PathPartial ? "partial" : "invalid";
                    if (path.status != NavMeshPathStatus.PathInvalid) { len = 0f; for (int k = 1; k < path.corners.Length; k++) len += Vector3.Distance(path.corners[k - 1], path.corners[k]); }
                }
                bool reach = found && snap <= OnMeshM && st == "complete" && len >= 0f && len <= Flat(c - from) + 0.5f;
                controlsOk &= !reach;
                controls.Add($"({F(from.x, 2)}, {F(from.z, 2)}) to ({F(c.x, 2)}, {F(c.z, 2)}): " +
                             (found ? $"NavMesh {F(snap, 2)} m away (height {F(hc.position.y, 2)} m), path {st}{(len >= 0f ? " " + F(len, 2) + " m" : "")}" : "no NavMesh point within 2 m") +
                             $" -> {(reach ? "**reachable: the control fails**" : "not reachable, as expected")}");
            }
            md.Append("\nNegative control (the same test toward rack centres, which the ground-truth grid marks blocked, and beyond the south wall, " +
                      "from the nearest aisle point of a road): " + string.Join("; ", controls) + ".\n");
            if (!controlsOk) { md.Append("\n**The negative control failed: the reachable counts above are not trustworthy.**\n"); }
            md.Append("\n## Where the beside workers stand along each road (live layout, section 3 slots)\n\n");
            md.Append("Lateral side as seen driving the road from its first node to its second; s = distance along the road from the first node. " +
                      "The clear side near a node is the side without a worker. The pending corner layout (addendum 1, item 3b, as built) puts slot 1 3.5 m before and " +
                      "2.5 m left of each junction, slot 2 4.5 m ahead and 3.5 m right, slot 3 (J1 in A3, B3) 5.0 m ahead and 4.0 m left.\n\n");
            foreach (var l in workerLines) md.Append(l + "\n");
            md.Append($"\nAll {rows.Count} samples: samples.csv.\n");
            File.WriteAllText(Path.Combine(outDir, "samples.csv"), csv.ToString(), new UTF8Encoding(false));
            File.WriteAllText(Path.Combine(outDir, "report.md"), md.ToString(), new UTF8Encoding(false));
            ok = controlsOk;
            return $"side waypoints: {rows.Count} samples, {rows.Count(r => r.Reachable)} reachable; negative control {(controlsOk ? "ok" : "FAILED")}; report {outDir}";
        }

        static IEnumerable<(Vector3 a, Vector3 b, string label)> UniqueRoads(RoadmapV4 map)
        {
            var seen = new HashSet<string>();
            foreach (var kv in map.Branches)
                foreach (var b in kv.Value)
                {
                    string key = string.CompareOrdinal(kv.Key, b.Value) < 0 ? kv.Key + "|" + b.Value : b.Value + "|" + kv.Key;
                    if (!seen.Add(key)) continue;
                    yield return (ExperimentPlanAB.Pos(map.Node(kv.Key)), ExperimentPlanAB.Pos(map.Node(b.Value)), $"{kv.Key}-{b.Value}");
                }
        }

        static string Intervals(List<float> s)
        {
            if (s.Count == 0) return "-";
            s.Sort();
            var parts = new List<string>();
            float lo = s[0], hi = s[0];
            for (int i = 1; i <= s.Count; i++)
            {
                if (i < s.Count && s[i] - hi <= SampleStepM + 1e-3f) { hi = s[i]; continue; }
                parts.Add(lo == hi ? F(lo, 1) : $"{F(lo, 1)}-{F(hi, 1)}");
                if (i < s.Count) lo = hi = s[i];
            }
            return string.Join(", ", parts);
        }

        static float Flat(Vector3 v) => new Vector2(v.x, v.z).magnitude;
        static string F(float v, int d) => v.ToString("F" + d, Inv);
    }
}
