using System;
using System.Collections.Generic;
using System.Diagnostics;
using System.Globalization;
using System.IO;
using System.Linq;
using System.Reflection;
using System.Security.Cryptography;
using System.Text;
using Unity.AI.Navigation;
using UnityEditor;
using UnityEditor.SceneManagement;
using UnityEngine;
using UnityEngine.AI;
using UnityEngine.SceneManagement;
using WarehouseHRI.V4;
using WarehouseRobot.Bridge;
using WarehouseRobot.GroundTruth;
using Debug = UnityEngine.Debug;
using Object = UnityEngine.Object;

namespace WarehouseRobot.EditorTools
{
    /// <summary>
    /// The racks in the robot's NavMesh (Avatar/Config/experiments_ab.md section 15 addendum 2). The v4 scene's NavMesh Surface had "Ignore
    /// NavMesh Obstacles" on, and the generated warehouse carries a NavMeshObstacle on every rack and pallet, so none of them reached the bake.
    /// - Tools > Warehouse v4 > NavMesh > Bake v4 NavMesh: turns that switch off on the v4 Surface and marks the Stations group Not Walkable with a
    ///   NavMeshModifier (its 0.05 m pads are below the bake's height resolution; amendment of addendum 2), builds the NavMesh and saves
    ///   it as a NEW asset (V4Asset) that only the v4 scene uses. Not the Editor's Bake button: it deletes the Surface's current asset first,
    ///   and that asset is the v3 scene's (v1.0 stays reproducible). Refuses when V4Asset exists; checks the v3 scene and asset are unchanged.
    ///   Batch: Unity -batchmode -projectPath P -executeMethod WarehouseRobot.EditorTools.NavMeshV4Menu.BatchBake -logFile bake.log
    /// - Tools > Warehouse v4 > NavMesh > Verify: the declared checks V1 (NavMesh paths between every node and modelled ask position of every
    ///   map never enter an obstacle footprint, are complete, snap within the bridge's distance; negative control), V2 (the NavMesh against the
    ///   ground-truth grid, cell by cell) and V4 (the roadmap builder's node and branch check on every map), into a new outputs folder.
    ///   Batch: ... -executeMethod WarehouseRobot.EditorTools.NavMeshV4Menu.BatchVerify -logFile verify.log
    /// Exit code 0 = done and passed, 1 = failed or refused. Nothing but the bake changes the scene.
    /// </summary>
    public static class NavMeshV4Menu
    {
        public const string V4Scene = "Assets/Scenes/WarehouseRobot_v4.unity";
        public const string V3Scene = "Assets/Scenes/WarehouseRobot.unity";
        public const string V4Asset = "Assets/Scenes/WarehouseRobot_v4/NavMesh-AMR.asset";
        public const string V3Asset = "Assets/Scenes/WarehouseRobot/NavMesh-NavMesh Surface.asset";
        const string StationsGroup = "Stations";
        const string BridgeConfigPath = "Assets/WarehouseRobot/Bridge/Config/bridge_unity_v4.json";
        const string ExperimentsPath = "Assets/WarehouseRobot/Scenario/Config/experiments_ab_unity.json";
        const string SavedGrid = "robot_vision/outputs/trials_development_Task2_A3_20261116_222448/run_001/grid.json";
        const int Runs = 20;
        const float SampleStepM = 0.05f, OnMeshM = 0.05f, NodeOnMeshM = 0.5f, MergeM = 0.01f, RasterM = 0.05f, RasterCapM = 2f;
        static readonly int[] Seeds = { 1, 2 };
        static readonly string[] Males = { "m" }, Females = { "f" };
        static readonly CultureInfo Inv = CultureInfo.InvariantCulture;

        static string ProjectDir => Path.GetFullPath(Path.Combine(Application.dataPath, ".."));
        static string RepoDir => Path.GetFullPath(Path.Combine(ProjectDir, "..", "..", ".."));

        // ---------------------------------------------------------------- bake

        [MenuItem("Tools/Warehouse v4/NavMesh/Bake v4 NavMesh")]
        public static void BakeMenu()
        {
            if (!EditorSceneManager.SaveCurrentModifiedScenesIfUserWantsTo()) return;
            bool ok = Bake(out string message);
            if (ok) Debug.Log("[NavMeshV4] " + message); else Debug.LogError("[NavMeshV4] " + message);
            EditorUtility.DisplayDialog("Bake v4 NavMesh", message, "OK");
        }

        public static void BatchBake()
        {
            bool ok = Bake(out string message);
            if (ok) Debug.Log("[NavMeshV4] " + message); else Debug.LogError("[NavMeshV4] " + message);
            EditorApplication.Exit(ok ? 0 : 1);
        }

        static bool Bake(out string message)
        {
            if (File.Exists(Path.Combine(ProjectDir, V4Asset))) { message = $"refused: {V4Asset} exists (never overwritten; delete it by hand to rebake)"; return false; }
            string v3AssetBefore = Sha256Lf(Path.Combine(ProjectDir, V3Asset)), v3SceneBefore = Sha256Lf(Path.Combine(ProjectDir, V3Scene));
            var scene = EditorSceneManager.OpenScene(V4Scene, OpenSceneMode.Single);
            var surface = AmrSurface(out string agent, out message);
            if (surface == null) return false;
            if (surface.collectObjects != CollectObjects.All || surface.useGeometry != NavMeshCollectGeometry.RenderMeshes)
            { message = $"refused: the Surface collects {surface.collectObjects} / {surface.useGeometry}, not All / RenderMeshes as declared"; return false; }
            string oldAsset = surface.navMeshData != null ? AssetDatabase.GetAssetPath(surface.navMeshData) : "none";
            var before = SourcesByGroup(surface);
            surface.ignoreNavMeshObstacle = false;
            // amendment (addendum 2): the 0.05 m station pads are below the bake's height resolution, so they are marked Not Walkable
            int notWalkable = NavMesh.GetAreaFromName("Not Walkable");
            var stations = SceneManager.GetActiveScene().GetRootGameObjects().SelectMany(r => r.GetComponentsInChildren<Transform>(true))
                                       .Where(t => t.name == StationsGroup).ToList();
            if (stations.Count != 1 || notWalkable < 0) { message = $"refused: {stations.Count} '{StationsGroup}' objects (one expected) or no 'Not Walkable' area"; return false; }
            var mod = stations[0].GetComponent<NavMeshModifier>();
            if (mod == null) mod = stations[0].gameObject.AddComponent<NavMeshModifier>();
            mod.overrideArea = true;
            mod.area = notWalkable;
            mod.applyToChildren = true;
            mod.ignoreFromBuild = false;
            EditorUtility.SetDirty(mod);
            var after = SourcesByGroup(surface);
            int stationSources = stations[0].GetComponentsInChildren<MeshRenderer>(true).Length;
            if (after.TryGetValue(StationsGroup, out int walkableStations) && walkableStations > 0 ||
                !after.TryGetValue(StationsGroup + " (Not Walkable)", out int nwStations) || nwStations != stationSources)
            { message = $"refused: the Surface's sources do not mark all {stationSources} station meshes Not Walkable"; return false; }
            surface.BuildNavMesh();
            if (surface.navMeshData == null) { message = "failed: BuildNavMesh made no data"; return false; }
            string folder = Path.GetDirectoryName(V4Asset).Replace('\\', '/');
            if (!AssetDatabase.IsValidFolder(folder)) AssetDatabase.CreateFolder(Path.GetDirectoryName(folder).Replace('\\', '/'), Path.GetFileName(folder));
            AssetDatabase.CreateAsset(surface.navMeshData, V4Asset);
            EditorUtility.SetDirty(surface);
            EditorSceneManager.MarkSceneDirty(scene);
            if (!EditorSceneManager.SaveScene(scene)) { message = "failed: could not save " + V4Scene; return false; }
            AssetDatabase.SaveAssets();
            bool v3Same = Sha256Lf(Path.Combine(ProjectDir, V3Asset)) == v3AssetBefore && Sha256Lf(Path.Combine(ProjectDir, V3Scene)) == v3SceneBefore;
            var tri = NavMesh.CalculateTriangulation();

            string outDir = NewOutputFolder("navmesh_v4_bake");
            var md = new StringBuilder();
            md.Append($"# v4 NavMesh bake ({DateTime.Now.ToString("yyyy-MM-dd HH:mm:ss", Inv)})\n\n");
            md.Append("experiments_ab.md section 15 addendum 2. NavMesh Surface '" + surface.name + $"' of {V4Scene}, agent type {agent} " +
                      $"(radius {F(NavMesh.GetSettingsByID(surface.agentTypeID).agentRadius, 2)} m, height {F(NavMesh.GetSettingsByID(surface.agentTypeID).agentHeight, 2)} m, " +
                      $"step {F(NavMesh.GetSettingsByID(surface.agentTypeID).agentClimb, 2)} m), collect {surface.collectObjects}, {surface.useGeometry}. " +
                      "Changed: Ignore NavMesh Obstacles on -> off, and a NavMeshModifier (Not Walkable, children) on the Stations group (amendment). Nothing else.\n\n");
            md.Append($"- old data: `{oldAsset}` (the v3 scene's asset, left in place)\n- new data: `{V4Asset}`, SHA-256 (LF) {Sha256Lf(Path.Combine(ProjectDir, V4Asset))}\n");
            md.Append($"- v3 scene and v3 asset unchanged: {(v3Same ? "yes" : "**NO**")}\n");
            md.Append($"- triangulation of the loaded NavMesh: {tri.vertices.Length} vertices, {tri.indices.Length / 3} triangles\n\n");
            md.Append("| collected meshes by group | before (ignore on) | after (ignore off) |\n|---|---|---|\n");
            foreach (var k in before.Keys.Union(after.Keys).OrderBy(k => k, StringComparer.Ordinal))
                md.Append($"| {k} | {(before.TryGetValue(k, out int b) ? b : 0)} | {(after.TryGetValue(k, out int a) ? a : 0)} |\n");
            WriteNew(Path.Combine(outDir, "report.md"), md.ToString());
            WriteNew(Path.Combine(outDir, "run_info.json"), RunInfo());
            message = $"baked {V4Asset} (sources {before.Values.Sum()} -> {after.Values.Sum()}; Shelves {(after.TryGetValue("Shelves", out int s) ? s : 0)}); " +
                      $"v3 unchanged: {v3Same}; report {Rel(outDir)}";
            return v3Same;
        }

        /// <summary>The meshes the Surface would bake, counted by obstacle group (or by root object for everything else).</summary>
        static Dictionary<string, int> SourcesByGroup(NavMeshSurface surface)
        {
            var mi = typeof(NavMeshSurface).GetMethod("CollectSources", BindingFlags.NonPublic | BindingFlags.Instance);
            var sources = (List<NavMeshBuildSource>)mi.Invoke(surface, null);
            var groups = new HashSet<string> { "Shelves", "FloorBoxes", "Walls", "Stations" };
            var counts = new Dictionary<string, int>();
            foreach (var s in sources)
            {
                string key = "(no component)";
                if (s.component != null)
                {
                    var t = s.component.transform;
                    key = t.root.name;
                    for (var p = t; p != null; p = p.parent) if (groups.Contains(p.name)) { key = p.name; break; }
                }
                if (s.area == NavMesh.GetAreaFromName("Not Walkable")) key += " (Not Walkable)";
                counts[key] = counts.TryGetValue(key, out int n) ? n + 1 : 1;
            }
            return counts;
        }

        // ---------------------------------------------------------------- verify

        [MenuItem("Tools/Warehouse v4/NavMesh/Verify")]
        public static void VerifyMenu()
        {
            if (!EditorSceneManager.SaveCurrentModifiedScenesIfUserWantsTo()) return;
            bool ok = Verify(out string message);
            if (ok) Debug.Log("[NavMeshV4] " + message); else Debug.LogError("[NavMeshV4] " + message);
            EditorUtility.DisplayDialog("Verify v4 NavMesh", message, "OK");
        }

        public static void BatchVerify()
        {
            bool ok = Verify(out string message);
            if (ok) Debug.Log("[NavMeshV4] " + message); else Debug.LogError("[NavMeshV4] " + message);
            EditorApplication.Exit(ok ? 0 : 1);
        }

        sealed class Pt { public string Map, Kind, Origin; public Vector3 P, Snapped; public float Snap = -1f; public int Seen = 1; }
        sealed class Footprint { public string Group; public List<Vector2> Hull; public float MinX, MaxX, MinZ, MaxZ; }

        /// <summary>Distance to the nearest obstacle footprint on a 0.05 m raster (0 inside, capped at 2 m).</summary>
        sealed class Raster
        {
            public float X0, Z0; public int Nx, Nz; public float[] D; public int[] Who;
            public float At(float x, float z, out int who)
            {
                int ix = Mathf.FloorToInt((x - X0) / RasterM), iz = Mathf.FloorToInt((z - Z0) / RasterM);
                who = -1;
                if (ix < 0 || iz < 0 || ix >= Nx || iz >= Nz) return RasterCapM;
                who = Who[iz * Nx + ix];
                return D[iz * Nx + ix];
            }
        }

        static bool Verify(out string message)
        {
            var sw = Stopwatch.StartNew();
            EditorSceneManager.OpenScene(V4Scene, OpenSceneMode.Single);
            var surface = AmrSurface(out string agent, out message);
            if (surface == null) return false;
            var filter = new NavMeshQueryFilter { agentTypeID = surface.agentTypeID, areaMask = NavMesh.AllAreas };
            var settings = NavMesh.GetSettingsByID(surface.agentTypeID);
            float snapMax = JsonUtility.FromJson<UnityBridgeConfig>(AssetDatabase.LoadAssetAtPath<TextAsset>(BridgeConfigPath).text).nav.snap_max_distance_m;
            var rig = Object.FindFirstObjectByType<RobotRig>();
            var cfg = rig != null ? rig.Config : null;
            if (cfg == null || !cfg.IsV4) { message = "failed: no v4 robot in " + V4Scene; return false; }

            // the experiment plans: every map, its nodes and the modelled ask positions of every run
            string ecfgText = File.ReadAllText(Path.Combine(ProjectDir, ExperimentsPath));
            var ecfg = ExperimentsUnityConfig.Parse(ecfgText);
            string scen = File.ReadAllText(Path.Combine(RepoDir, ecfg.scenarios_ab)), road = File.ReadAllText(Path.Combine(RepoDir, ecfg.roadmap_v4));
            Func<string, string> read = p => File.ReadAllText(Path.Combine(ProjectDir, p));
            var maps = new SortedDictionary<string, RoadmapV4>(StringComparer.Ordinal);
            var points = new Dictionary<string, Dictionary<(int, int), Pt>>();
            int plans = 0;
            RoadmapV4 physical = null;
            foreach (string layout in new[] { "live", "pending" })
                foreach (var set in new[] { "A", "B" })
                    foreach (var (exp, side) in new[] { (set + "1", (string)null), (set + "2", "right"), (set + "2", "left"), (set + "3", null), (set + "4", null) })
                    {
                        var c = ExperimentsUnityConfig.Parse(ecfgText);
                        if (layout == "pending") c = c.WithClearanceLayout();
                        if (side != null) c.a2_sides = new[] { side };
                        var plan = ExperimentPlanAB.Build(c, exp, scen, road, read, out string error);
                        if (plan == null) { message = $"failed: {layout} {exp}: {error}"; return false; }
                        physical = plan.Physical;
                        var lc = c;
                        string setting = exp + (side != null ? "_" + side : "");
                        foreach (int seed in Seeds)
                        {
                            var goals = plan.Goals(seed, Runs);
                            for (int run = 1; run <= Runs; run++)
                            {
                                var r = plan.PlanRun(seed, run, goals[run - 1], Males, Females, null, out error);
                                if (r == null) { message = $"failed: {layout} {setting} seed {seed} run {run}: {error}"; return false; }
                                plans++;
                                var map = plan.RunMap(seed, run, out string mapName);
                                maps[mapName] = map;
                                foreach (var n in map.Nodes) AddPoint(points, mapName, ExperimentPlanAB.Pos(n), "node", n.Name);
                                foreach (var n in plan.Physical.Nodes) AddPoint(points, mapName, ExperimentPlanAB.Pos(n), "node", "roadmap " + n.Name);
                                foreach (var g in r.Workers.GroupBy(w => w.Node))
                                {
                                    ExperimentPlanAB.DrivableSegments(map, map.Node(g.Key), g.OrderBy(w => w.Slot).Select(w => w.Position).ToList(),
                                                                      lc.ask_standoff_m, lc.reask_shift_m, out var asks);
                                    foreach (var a in asks) AddPoint(points, mapName, a, "ask", $"{layout} {setting} seed {seed} run {run} {g.Key}");
                                }
                            }
                        }
                    }

            float floorY = FloorHeight(cfg, ExperimentPlanAB.Pos(physical.Node(physical.Start)));
            var fps = new List<Footprint>();
            var groupReport = new List<string>();
            var saved = cfg.Unity.obstacles.groups;
            try
            {
                foreach (string g in saved)
                {
                    cfg.Unity.obstacles.groups = new[] { g };
                    foreach (var h in ObstacleFootprints.Obstacles(cfg, rig.transform, floorY, out string rep))
                    {
                        if (h.Count == 0) continue;
                        fps.Add(new Footprint { Group = g, Hull = h, MinX = h.Min(v => v.x), MaxX = h.Max(v => v.x), MinZ = h.Min(v => v.y), MaxZ = h.Max(v => v.y) });
                    }
                    groupReport.Add(g + ": " + fps.Count(f => f.Group == g));
                }
            }
            finally { cfg.Unity.obstacles.groups = saved; }
            var floors = ObstacleFootprints.Floors(cfg.Unity.placement.floor_tag, rig.transform);
            var raster = BuildRaster(fps, floors);

            // ---- V1: paths between every pair of points of a map
            var path = new NavMeshPath();
            var allPts = new List<Pt>();
            foreach (var kv in points)
                foreach (var p in kv.Value.Values)
                {
                    if (NavMesh.SamplePosition(new Vector3(p.P.x, floorY, p.P.z), out var hit, snapMax, filter)) { p.Snapped = hit.position; p.Snap = Flat(hit.position - p.P); }
                    allPts.Add(p);
                }
            var perMap = new List<string>();
            var failures = new List<string>();
            var close = new List<(float d, string line)>();
            long pairs = 0, entered = 0, incomplete = 0, under40 = 0;
            foreach (var kv in points.OrderBy(k => k.Key, StringComparer.Ordinal))
            {
                var pts = kv.Value.Values.Where(p => p.Snap >= 0f).ToList();
                long mPairs = 0, mEntered = 0, mIncomplete = 0, mUnder = 0;
                float mMin = float.MaxValue; string mMinAt = "-";
                for (int i = 0; i < pts.Count; i++)
                    for (int j = i + 1; j < pts.Count; j++)
                    {
                        mPairs++;
                        NavMesh.CalculatePath(pts[i].Snapped, pts[j].Snapped, filter, path);
                        if (path.status != NavMeshPathStatus.PathComplete)
                        {
                            mIncomplete++;
                            if (failures.Count < 200) failures.Add($"{kv.Key},incomplete ({path.status}),{Xz(pts[i].P)},{Xz(pts[j].P)},,");
                            if (path.status == NavMeshPathStatus.PathInvalid) continue;
                        }
                        float least = PathClearance(path.corners, raster, out var at, out int who);
                        if (least < mMin) { mMin = least; mMinAt = $"({F(at.x, 2)}, {F(at.y, 2)}) {(who >= 0 ? fps[who].Group : "-")}"; }
                        if (least <= 0f)
                        {
                            mEntered++;
                            if (failures.Count < 200) failures.Add($"{kv.Key},enters {(who >= 0 ? fps[who].Group : "?")},{Xz(pts[i].P)},{Xz(pts[j].P)},{F(at.x, 2)},{F(at.y, 2)}");
                        }
                        else if (least < 0.40f)
                        {
                            mUnder++;
                            close.Add((least, $"{kv.Key},{Xz(pts[i].P)},{Xz(pts[j].P)},{F(least, 3)},{F(at.x, 2)},{F(at.y, 2)},{(who >= 0 ? fps[who].Group : "-")}"));
                        }
                    }
                pairs += mPairs; entered += mEntered; incomplete += mIncomplete; under40 += mUnder;
                var all = kv.Value.Values.ToList();
                perMap.Add($"| {kv.Key} | {all.Count(p => p.Kind == "node")} | {all.Count(p => p.Kind == "ask")} | {all.Count(p => p.Snap < 0f)} | " +
                           $"{F(all.Where(p => p.Snap >= 0f).Select(p => p.Snap).DefaultIfEmpty(0f).Max(), 3)} | {mPairs} | {mIncomplete} | {mEntered} | " +
                           $"{(mMin == float.MaxValue ? "-" : F(mMin, 3))} at {mMinAt} | {mUnder} |");
            }
            int offMesh = allPts.Count(p => p.Snap < 0f);
            bool v1 = entered == 0 && incomplete == 0 && offMesh == 0;

            // ---- V1 negative control
            var controls = new List<string>();
            bool controlOk = true;
            foreach (var (from, to) in new[] { (new Vector3(6.25f, 0f, -5f), new Vector3(0f, 0f, -5f)), (new Vector3(6.25f, 0f, -15f), new Vector3(12.5f, 0f, -15f)),
                                               (new Vector3(-6.25f, 0f, 15f), new Vector3(-12.5f, 0f, 15f)) })
            {
                bool f1 = NavMesh.SamplePosition(new Vector3(from.x, floorY, from.z), out var hf, 2f, filter);
                bool found = NavMesh.SamplePosition(new Vector3(to.x, floorY, to.z), out var hc, 2f, filter);
                float snap = found ? Flat(hc.position - to) : -1f, len = -1f;
                string st = "no path";
                if (f1 && found)
                {
                    NavMesh.CalculatePath(hf.position, hc.position, filter, path);
                    st = path.status.ToString();
                    if (path.status != NavMeshPathStatus.PathInvalid) len = Length(path.corners);
                }
                bool reach = found && snap <= OnMeshM && st == "PathComplete" && len >= 0f && len <= Flat(to - from) + 0.5f;
                controlOk &= !reach;
                controls.Add($"rack centre ({F(to.x, 2)}, {F(to.z, 2)}) from ({F(from.x, 2)}, {F(from.z, 2)}): " +
                             (found ? $"nearest NavMesh {F(snap, 2)} m away, path {st}{(len >= 0f ? " " + F(len, 2) + " m" : "")}" : "no NavMesh within 2 m") +
                             $" -> {(reach ? "**reachable: the control FAILS**" : "not reachable, as expected")}");
            }
            {
                var a = new Vector3(6.25f, floorY, -5f); var b = new Vector3(-6.25f, floorY, -5f);
                float straight = PathClearance(new[] { a, b }, raster, out _, out int sw0);
                bool ok1 = NavMesh.SamplePosition(a, out var ha, 0.5f, filter) & NavMesh.SamplePosition(b, out var hb, 0.5f, filter);
                float least = -1f, len = -1f;
                string st = "no path";
                if (ok1)
                {
                    NavMesh.CalculatePath(ha.position, hb.position, filter, path);
                    st = path.status.ToString();
                    least = PathClearance(path.corners, raster, out _, out _);
                    len = Length(path.corners);
                }
                bool crossOk = straight <= 0f && st == "PathComplete" && least > 0f;
                controlOk &= crossOk;
                controls.Add($"(6.25, -5) to (-6.25, -5): the straight line {(straight <= 0f ? "crosses " + (sw0 >= 0 ? fps[sw0].Group : "?") : "does NOT cross a footprint")}; " +
                             $"NavMesh path {st}, {F(len, 2)} m (straight 12.50 m), least clearance {F(least, 3)} m -> {(crossOk ? "goes around, as expected" : "**the control FAILS**")}");
            }

            // ---- V2: the NavMesh against the ground-truth grid
            var grid = GroundTruthLayer.BuildGrid(cfg, rig.transform, floorY, cfg.GroundTruthInflationM, out string gridReport);
            if (grid == null) { message = "failed: " + gridReport; return false; }
            int bothFree = 0, bothBlocked = 0, stricter = 0, looser = 0, looserInside = 0;
            var dis = new List<string>();
            var stricterD = new List<float>(); var looserD = new List<float>();
            for (int iz = 0; iz < grid.CellsZ; iz++)
                for (int ix = 0; ix < grid.CellsX; ix++)
                {
                    grid.Centre(ix, iz, out double cx, out double cz);
                    var c = new Vector3((float)cx, floorY, (float)cz);
                    bool on = NavMesh.SamplePosition(c, out var h, 0.5f, filter) && Flat(h.position - c) <= OnMeshM;
                    bool free = grid.Free(ix, iz);
                    if (free && on) { bothFree++; continue; }
                    if (!free && !on) { bothBlocked++; continue; }
                    float d = NearestFootprint(fps, c.x, c.z, out int who);
                    bool onFloor = floors.Any(f => Geometry2D.InsideConvex(f, c.x, c.z));
                    if (free) { stricter++; stricterD.Add(d); }
                    else { looser++; looserD.Add(d); if (d <= 0f) looserInside++; }
                    dis.Add($"{ix},{iz},{F(c.x, 2)},{F(c.z, 2)},{(free ? "grid_free_navmesh_off" : "grid_blocked_navmesh_on")},{F(d, 3)},{(who >= 0 ? fps[who].Group : "-")},{(onFloor ? 1 : 0)}");
                }
            bool v2 = looserInside == 0;
            string savedCompare = CompareSaved(grid);

            // ---- V4: the roadmap builder's check on every map
            var v4Lines = new List<string>();
            bool v4 = true;
            foreach (var kv in maps)
            {
                var problems = new List<string>();
                foreach (var n in kv.Value.Nodes)
                    if (!NavMesh.SamplePosition(new Vector3(n.X, floorY, n.Z), out _, NodeOnMeshM, filter)) problems.Add($"{n.Name} not on the NavMesh within {F(NodeOnMeshM, 1)} m");
                int branches = 0;
                foreach (var b in kv.Value.Branches)
                    foreach (var x in b.Value)
                    {
                        branches++;
                        var from = kv.Value.Node(b.Key); var to = kv.Value.Node(x.Value);
                        if (!NavMesh.CalculatePath(new Vector3(from.X, floorY, from.Z), new Vector3(to.X, floorY, to.Z), filter, path) || path.status != NavMeshPathStatus.PathComplete)
                            problems.Add($"no complete path {b.Key} -> {x.Value}");
                    }
                v4 &= problems.Count == 0;
                v4Lines.Add($"- {kv.Key}: {kv.Value.Nodes.Count} nodes, {branches} branches: {(problems.Count == 0 ? "all on the NavMesh, every branch complete" : "**" + string.Join("; ", problems) + "**")}");
            }

            // ---- report
            bool ok = v1 && controlOk && v2 && v4;
            string outDir = NewOutputFolder("navmesh_v4_check");
            var md = new StringBuilder();
            md.Append($"# v4 NavMesh verification ({DateTime.Now.ToString("yyyy-MM-dd HH:mm:ss", Inv)}): {(ok ? "PASSED" : "**FAILED**")}\n\n");
            md.Append($"experiments_ab.md section 15 addendum 2 (rules declared before the bake). Edit mode, {V4Scene} (not saved); NavMesh Surface '{surface.name}', agent " +
                      $"{agent} (radius {F(settings.agentRadius, 2)} m, height {F(settings.agentHeight, 2)} m), data `{AssetDatabase.GetAssetPath(surface.navMeshData)}`, " +
                      $"Ignore NavMesh Obstacles {(surface.ignoreNavMeshObstacle ? "ON" : "off")}. Floor y {F(floorY, 3)} m. Obstacle footprints (not widened): " +
                      $"{string.Join(", ", groupReport)} ({fps.Count}). Took {F((float)sw.Elapsed.TotalSeconds, 1)} s.\n\n");
            md.Append($"## V1, NavMesh paths: {(v1 ? "passed" : "**FAILED**")}\n\n");
            md.Append($"{plans} planned runs (live and pending layout x 10 Unity settings x seeds 1, 2 x {Runs} runs). Points per map: every node of the map and of the " +
                      $"physical v4 map, and every modelled ask position and re-ask point (item 3b model, standoff {F(ecfg.ask_standoff_m, 1)} m, shift {F(ecfg.reask_shift_m, 1)} m), " +
                      $"merged within {F(MergeM, 2)} m. Each end snapped by the bridge's rule (within {F(snapMax, 1)} m); a path between every pair of points of a map, sampled every " +
                      $"{F(SampleStepM, 2)} m against the footprints (a {F(RasterM, 2)} m distance raster).\n\n");
            md.Append("| map | nodes | ask points | off the NavMesh | largest snap (m) | paths | not complete | entering a footprint | least clearance (m) | paths under 0.40 m |\n|---|---|---|---|---|---|---|---|---|---|\n");
            foreach (var l in perMap) md.Append(l + "\n");
            md.Append($"\nTotal: {allPts.Count} points ({offMesh} off the NavMesh), {pairs} paths, {incomplete} not complete, {entered} entering a footprint, {under40} closer than 0.40 m.\n\n");
            md.Append($"Negative control: {(controlOk ? "passed" : "**FAILED**")}\n\n");
            foreach (var c in controls) md.Append("- " + c + "\n");
            md.Append($"\n## V2, NavMesh against the ground-truth grid: hard rule {(v2 ? "passed" : "**FAILED**")}\n\n");
            md.Append($"Official grid built in Edit mode ({gridReport}). A cell centre is on the NavMesh when the NavMesh lies within {F(OnMeshM, 2)} m horizontally.\n\n");
            md.Append($"| | count |\n|---|---|\n| both free | {bothFree} |\n| both blocked | {bothBlocked} |\n| grid free, off the NavMesh (NavMesh stricter) | {stricter} |\n" +
                      $"| grid blocked, on the NavMesh (NavMesh looser) | {looser} |\n| ... of them inside a footprint (hard rule) | {looserInside} |\n\n");
            md.Append("Distance from the cell centre to the nearest footprint (not widened):\n\n");
            md.Append("| distance (m) | NavMesh stricter | NavMesh looser |\n|---|---|---|\n");
            foreach (var (lo, hi) in new[] { (0f, 0f), (0f, 0.2f), (0.2f, 0.4f), (0.4f, 0.5f), (0.5f, 0.6f), (0.6f, 0.7f), (0.7f, 1f), (1f, 2f), (2f, float.MaxValue) })
            {
                string label = hi == 0f ? "0 (inside)" : hi == float.MaxValue ? $"> {F(lo, 1)}" : $"{F(lo, 1)} to {F(hi, 1)}";
                Func<float, bool> inBin = d => hi == 0f ? d <= 0f : d > lo && d <= hi;
                md.Append($"| {label} | {stricterD.Count(inBin)} | {looserD.Count(inBin)} |\n");
            }
            md.Append($"\nSaved grid: {savedCompare}\n\nEvery disagreeing cell: grid_disagreements.csv.\n\n");
            md.Append($"## V4, the roadmap builder's check on every map: {(v4 ? "passed" : "**FAILED**")}\n\n");
            foreach (var l in v4Lines) md.Append(l + "\n");

            WriteNew(Path.Combine(outDir, "report.md"), md.ToString());
            var pcsv = new StringBuilder("map,kind,x,z,snap_m,merged,first_origin\n");
            foreach (var p in allPts.OrderBy(p => p.Map, StringComparer.Ordinal).ThenBy(p => p.Kind, StringComparer.Ordinal))
                pcsv.Append($"{p.Map},{p.Kind},{F(p.P.x, 3)},{F(p.P.z, 3)},{F(p.Snap, 3)},{p.Seen},{p.Origin}\n");
            WriteNew(Path.Combine(outDir, "points.csv"), pcsv.ToString());
            WriteNew(Path.Combine(outDir, "path_failures.csv"), "map,problem,from_x,from_z,to_x,to_z,at_x,at_z\n" + string.Concat(failures.Select(f => f + "\n")));
            WriteNew(Path.Combine(outDir, "paths_under_040.csv"), "map,from_x,from_z,to_x,to_z,least_clearance_m,at_x,at_z,group\n" +
                                                                  string.Concat(close.OrderBy(c => c.d).Take(5000).Select(c => c.line + "\n")));
            WriteNew(Path.Combine(outDir, "grid_disagreements.csv"), "ix,iz,x,z,class,nearest_footprint_m,group,on_floor\n" + string.Concat(dis.Select(d => d + "\n")));
            WriteNew(Path.Combine(outDir, "run_info.json"), RunInfo());
            message = $"verify {(ok ? "PASSED" : "FAILED")}: V1 {(v1 ? "ok" : "FAILED")} ({pairs} paths, {entered} enter a footprint, {incomplete} incomplete, {offMesh} points off), " +
                      $"control {(controlOk ? "ok" : "FAILED")}, V2 {(v2 ? "ok" : "FAILED")} (stricter {stricter}, looser {looser}), V4 {(v4 ? "ok" : "FAILED")}; report {Rel(outDir)}";
            return ok;
        }

        static void AddPoint(Dictionary<string, Dictionary<(int, int), Pt>> points, string map, Vector3 p, string kind, string origin)
        {
            if (!points.TryGetValue(map, out var d)) points[map] = d = new Dictionary<(int, int), Pt>();
            var key = (Mathf.RoundToInt(p.x / MergeM), Mathf.RoundToInt(p.z / MergeM));
            if (d.TryGetValue(key, out var have)) { have.Seen++; if (kind == "node" && have.Kind != "node") { have.Kind = kind; have.Origin = origin; } return; }
            d[key] = new Pt { Map = map, Kind = kind, Origin = origin, P = new Vector3(p.x, 0f, p.z) };
        }

        static Raster BuildRaster(List<Footprint> fps, List<List<Vector2>> floors)
        {
            float x0 = floors.SelectMany(f => f).Min(v => v.x) - RasterCapM, x1 = floors.SelectMany(f => f).Max(v => v.x) + RasterCapM;
            float z0 = floors.SelectMany(f => f).Min(v => v.y) - RasterCapM, z1 = floors.SelectMany(f => f).Max(v => v.y) + RasterCapM;
            var r = new Raster { X0 = x0, Z0 = z0, Nx = Mathf.CeilToInt((x1 - x0) / RasterM), Nz = Mathf.CeilToInt((z1 - z0) / RasterM) };
            r.D = Enumerable.Repeat(RasterCapM, r.Nx * r.Nz).ToArray();
            r.Who = Enumerable.Repeat(-1, r.Nx * r.Nz).ToArray();
            for (int k = 0; k < fps.Count; k++)
            {
                var f = fps[k];
                int ix0 = Math.Max(0, Mathf.FloorToInt((f.MinX - RasterCapM - x0) / RasterM)), ix1 = Math.Min(r.Nx - 1, Mathf.CeilToInt((f.MaxX + RasterCapM - x0) / RasterM));
                int iz0 = Math.Max(0, Mathf.FloorToInt((f.MinZ - RasterCapM - z0) / RasterM)), iz1 = Math.Min(r.Nz - 1, Mathf.CeilToInt((f.MaxZ + RasterCapM - z0) / RasterM));
                for (int iz = iz0; iz <= iz1; iz++)
                    for (int ix = ix0; ix <= ix1; ix++)
                    {
                        // the cell's centre; a cell counts as inside when any part of it may be (distance <= half the diagonal)
                        double cx = x0 + (ix + 0.5) * RasterM, cz = z0 + (iz + 0.5) * RasterM;
                        float d = (float)Math.Max(0.0, Geometry2D.DistanceToConvex(f.Hull, cx, cz) - RasterM * 0.70710678);
                        int i = iz * r.Nx + ix;
                        if (d < r.D[i]) { r.D[i] = d; r.Who[i] = k; }
                    }
            }
            return r;
        }

        /// <summary>The least footprint distance along a polyline sampled every SampleStepM (conservative by half a raster cell).</summary>
        static float PathClearance(Vector3[] corners, Raster r, out Vector2 at, out int who)
        {
            float least = float.MaxValue;
            at = Vector2.zero; who = -1;
            if (corners == null || corners.Length == 0) return least;
            for (int k = 0; k < Math.Max(1, corners.Length - 1); k++)
            {
                var a = corners[k]; var b = corners.Length > 1 ? corners[k + 1] : a;
                float len = Flat(b - a);
                int n = Math.Max(1, Mathf.CeilToInt(len / SampleStepM));
                for (int i = 0; i <= n; i++)
                {
                    var p = Vector3.Lerp(a, b, (float)i / n);
                    float d = r.At(p.x, p.z, out int w);
                    if (d < least) { least = d; at = new Vector2(p.x, p.z); who = w; }
                }
            }
            return least;
        }

        static float NearestFootprint(List<Footprint> fps, float x, float z, out int who)
        {
            double best = double.MaxValue;
            who = -1;
            for (int k = 0; k < fps.Count; k++)
            {
                double d = Geometry2D.DistanceToConvex(fps[k].Hull, x, z);
                if (d < best) { best = d; who = k; }
            }
            return (float)best;
        }

        static string CompareSaved(GroundTruthGrid grid)
        {
            string p = Path.Combine(RepoDir, SavedGrid);
            if (!File.Exists(p)) return $"`{SavedGrid}` not found; not compared.";
            var g = JsonUtility.FromJson<GridFile>(File.ReadAllText(p));
            if (g.cells_x != grid.CellsX || g.cells_z != grid.CellsZ || Math.Abs(g.origin_x - grid.OriginX) > 1e-9 || Math.Abs(g.origin_z - grid.OriginZ) > 1e-9 || Math.Abs(g.cell_size_m - grid.CellSize) > 1e-12)
                return $"`{SavedGrid}` has another shape ({g.cells_x} x {g.cells_z} at ({g.origin_x}, {g.origin_z})); not compared cell by cell.";
            var rows = grid.BlockedRows();
            int diff = 0;
            for (int iz = 0; iz < rows.Count; iz++)
                for (int ix = 0; ix < rows[iz].Length; ix++)
                    if (rows[iz][ix] != g.blocked_rows[iz][ix]) diff++;
            return $"`{SavedGrid}` (Play mode, A3 run 1): {(diff == 0 ? "identical, cell for cell" : diff + " cells differ")}.";
        }

        // ---------------------------------------------------------------- helpers

        static NavMeshSurface AmrSurface(out string agent, out string error)
        {
            error = null;
            agent = JsonUtility.FromJson<UnityBridgeConfig>(AssetDatabase.LoadAssetAtPath<TextAsset>(BridgeConfigPath).text).nav.agent_type;
            string a = agent;
            var surfaces = Object.FindObjectsByType<NavMeshSurface>(FindObjectsInactive.Include, FindObjectsSortMode.None);
            var s = surfaces.Where(x => NavMesh.GetSettingsNameFromID(x.agentTypeID) == a).ToList();
            if (s.Count != 1) { error = $"failed: {s.Count} NavMesh Surfaces of agent type '{agent}' in {V4Scene} (one expected)"; return null; }
            if (!s[0].isActiveAndEnabled) { error = "failed: the NavMesh Surface is disabled"; return null; }
            return s[0];
        }

        static float FloorHeight(RobotConfig cfg, Vector3 at)
        {
            Physics.SyncTransforms();
            float best = float.NegativeInfinity;
            foreach (var hit in Physics.RaycastAll(at + Vector3.up * 50f, Vector3.down, 100f, ~0, QueryTriggerInteraction.Ignore))
                if (hit.collider.CompareTag(cfg.Unity.placement.floor_tag)) best = Mathf.Max(best, hit.point.y);
            return float.IsNegativeInfinity(best) ? at.y : best;
        }

        /// <summary>SHA-256 of a file with CRLF read as LF (as freeze_v4.py hashes), lower-case hex.</summary>
        public static string Sha256Lf(string path)
        {
            var bytes = File.ReadAllBytes(path);
            var lf = new List<byte>(bytes.Length);
            for (int i = 0; i < bytes.Length; i++)
                if (!(bytes[i] == (byte)'\r' && i + 1 < bytes.Length && bytes[i + 1] == (byte)'\n')) lf.Add(bytes[i]);
            using (var sha = SHA256.Create()) return string.Concat(sha.ComputeHash(lf.ToArray()).Select(b => b.ToString("x2")));
        }

        static string NewOutputFolder(string prefix)
        {
            string dir = Path.Combine(RepoDir, "robot_vision", "outputs", prefix + "_" + DateTime.Now.ToString("yyyyMMdd_HHmmss", Inv));
            if (Directory.Exists(dir)) throw new IOException(dir + " exists");
            Directory.CreateDirectory(dir);
            return dir;
        }

        static void WriteNew(string path, string text)
        {
            var bytes = new UTF8Encoding(false).GetBytes(text);
            using (var fs = new FileStream(path, FileMode.CreateNew, FileAccess.Write)) fs.Write(bytes, 0, bytes.Length);
        }

        static string RunInfo()
        {
            string commit = Git("rev-parse HEAD").Trim(), status = Git("status --porcelain");
            string v4 = File.Exists(Path.Combine(ProjectDir, V4Asset)) ? Sha256Lf(Path.Combine(ProjectDir, V4Asset)) : "";
            return "{\n" +
                   $"  \"created_local\": \"{DateTime.Now.ToString("yyyy-MM-dd'T'HH:mm:ss", Inv)}\",\n" +
                   $"  \"git_commit\": \"{commit}\",\n" +
                   $"  \"git_status_porcelain\": \"{Esc(status)}\",\n" +
                   $"  \"unity_version\": \"{Application.unityVersion}\",\n" +
                   $"  \"scene\": \"{V4Scene}\",\n" +
                   $"  \"scene_sha256_lf\": \"{Sha256Lf(Path.Combine(ProjectDir, V4Scene))}\",\n" +
                   $"  \"navmesh_asset\": \"{V4Asset}\",\n" +
                   $"  \"navmesh_asset_sha256_lf\": \"{v4}\",\n" +
                   $"  \"v3_navmesh_asset_sha256_lf\": \"{Sha256Lf(Path.Combine(ProjectDir, V3Asset))}\",\n" +
                   $"  \"bridge_config\": \"{BridgeConfigPath}\",\n" +
                   $"  \"experiments_config\": \"{ExperimentsPath}\"\n" +
                   "}\n";
        }

        static string Git(string args)
        {
            try
            {
                var psi = new ProcessStartInfo("git", args)
                {
                    WorkingDirectory = RepoDir, RedirectStandardOutput = true, RedirectStandardError = true, UseShellExecute = false, CreateNoWindow = true,
                };
                using (var p = Process.Start(psi))
                {
                    string output = p.StandardOutput.ReadToEnd();
                    p.WaitForExit(10000);
                    return p.ExitCode == 0 ? output : "unknown";
                }
            }
            catch (Exception e) { return "unknown (" + e.Message + ")"; }
        }

        static string Esc(string s) => s.Replace("\\", "\\\\").Replace("\"", "\\\"").Replace("\r", "").Replace("\n", "\\n");
        static string Rel(string abs) => Path.GetRelativePath(RepoDir, abs).Replace('\\', '/');
        static float Flat(Vector3 v) => new Vector2(v.x, v.z).magnitude;
        static float Length(Vector3[] c) { float l = 0f; for (int k = 1; k < c.Length; k++) l += Vector3.Distance(c[k - 1], c[k]); return l; }
        static string Xz(Vector3 p) => $"{F(p.x, 2)},{F(p.z, 2)}";
        static string F(float v, int d) => v.ToString("F" + d, Inv);
    }
}
