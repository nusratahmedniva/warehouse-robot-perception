using System;
using System.Collections.Generic;
using System.IO;
using UnityEngine;
using UnityEngine.Rendering;
using WarehouseHRI.V4;

namespace WarehouseRobot.GroundTruth
{
    /// <summary>
    /// v4 ground-truth layer (docs/project_flow_v4.md "Ground-truth layer", docs/protocol_v3.md "Per-run files Unity
    /// writes"). For us only, never for the robot:
    /// - every object it creates is on the layer v4.ground_truth.layer ("GroundTruth"), which it removes from the culling
    ///   masks of both robot cameras (360 and pan-tilt);
    /// - the 0.5 m floor grid with blocked cells widened by robot_width_m / 2 + safety_margin_per_side_m (robot.json),
    ///   the A* optimal path from A to B (GridAStar: 8-connected, diagonal sqrt(2), no corner cutting), markers at A and B,
    ///   the path as points and a line, and the blocked cells drawn on the floor;
    /// - run_###/grid.json and run_###/optimal_path.json in the formats of docs/protocol_v3.md;
    /// - the leak test: both robot cameras rendered with the layer's renderers on and off from the same pose in the same
    ///   frame, written as lossless PNG pairs (cam360_on.png / cam360_off.png, pan_tilt_on.png / pan_tilt_off.png) and
    ///   compared pixel by pixel; any difference means the robot could see the ground truth. A control render with the
    ///   layer put back into the culling masks must differ, so a pass cannot come from ground truth that is out of view.
    /// Nothing here is sent over the bridge. Unlit materials only, no lights and no shadows, so ground truth cannot
    /// change what the robot cameras see even through lighting.
    /// </summary>
    [DisallowMultipleComponent]
    public class GroundTruthLayer : MonoBehaviour
    {
        public const string LeakPan = "pan_tilt", Leak360 = "cam360";

        RobotRig robot;
        RobotConfig cfg;
        Camera panCam, omniCam;
        GroundTruthConfig gt;
        Transform visuals;
        GameObject runVisuals;
        Material startMat, goalMat, pathMat, pointMat, blockedMat;

        public int Layer { get; private set; } = -1;
        public GroundTruthGrid Grid { get; private set; }
        public string GridReport { get; private set; } = "";
        public float FloorY { get; private set; }
        public bool Ready => Grid != null && Layer >= 0;

        /// <summary>Per-pair result of a leak test.</summary>
        [Serializable]
        public class LeakPair
        {
            public string name;
            public bool passed;
            public int max_diff;
            public int differing_pixels;
            public int width, height;
            /// <summary>Control: pixels that change when the layer is put back into this camera's culling mask (must be &gt; 0,
            /// or the ground truth is not in view and the pair proves nothing). Computed in memory, no image written.</summary>
            public int layer_visible_pixels;
        }

        /// <summary>
        /// Set up for this robot: the layer must exist, the robot config must be the v4 one. Removes the layer from both
        /// robot cameras and builds the grid (floorY = height of the floor under the robot). False with the reason otherwise.
        /// </summary>
        public bool Init(RobotRig robotRig, out string error)
        {
            error = null;
            robot = robotRig;
            cfg = robot != null ? robot.Config : null;
            if (cfg == null) { error = "no robot config"; return false; }
            if (!cfg.IsV4) { error = "the robot does not use the v4 config (robot_unity_v4.json, section v4)"; return false; }
            gt = cfg.Unity.v4.ground_truth;
            Layer = LayerMask.NameToLayer(gt.layer);
            if (Layer < 0) { error = $"no Unity layer named '{gt.layer}' (Project Settings > Tags and Layers)"; return false; }
            // From the components, not RobotRig.PanTilt / Omni: those are set in Awake, and the editor tools run in Edit mode.
            panCam = PanTiltCameraOf(robot);
            omniCam = OmniCameraOf(robot);
            if (panCam == null || omniCam == null)
            {
                error = "the robot is missing a camera";
                return false;
            }
            ExcludeFromRobotCameras();
            FloorY = robot.transform.position.y;
            Grid = BuildGrid(cfg, robot.transform, FloorY, cfg.GroundTruthInflationM, out string report);
            GridReport = report;
            if (Grid == null) { error = report; return false; }
            EnsureVisualRoot();
            return true;
        }

        /// <summary>Remove the ground-truth layer from both robot cameras' culling masks.</summary>
        public void ExcludeFromRobotCameras()
        {
            int bit = 1 << Layer;
            panCam.cullingMask &= ~bit;
            omniCam.cullingMask &= ~bit;
        }

        public static Camera PanTiltCameraOf(RobotRig r)
        {
            var c = r.GetComponentInChildren<PanTiltCamera>(true);
            return c != null ? c.Camera : null;
        }

        public static Camera OmniCameraOf(RobotRig r)
        {
            var c = r.GetComponentInChildren<Camera360>(true);
            return c != null ? c.Camera : null;
        }

        public bool RobotCamerasSkipLayer()
        {
            int bit = 1 << Layer;
            return (panCam.cullingMask & bit) == 0 && (omniCam.cullingMask & bit) == 0;
        }

        /// <summary>The grid for this scene and widening, or null (with the reason in report).</summary>
        public static GroundTruthGrid BuildGrid(RobotConfig cfg, Transform robotRoot, float floorY, double inflationM, out string report)
        {
            var floors = ObstacleFootprints.Floors(cfg.Unity.placement.floor_tag, robotRoot);
            if (floors.Count == 0)
            {
                report = $"no floor: no active collider tagged '{cfg.Unity.placement.floor_tag}'";
                return null;
            }
            var obstacles = ObstacleFootprints.Obstacles(cfg, robotRoot, floorY, out string obstacleReport);
            var grid = GroundTruthGrid.FromFootprints(cfg.Unity.v4.ground_truth.cell_size_m, floors, obstacles, inflationM);
            report = $"grid {grid.CellsX} x {grid.CellsZ} cells of {grid.CellSize} m at ({grid.OriginX}, {grid.OriginZ}), " +
                     $"{grid.BlockedCount()} blocked, widening {inflationM:0.000} m; {floors.Count} floor colliders; {obstacleReport}";
            return grid;
        }

        /// <summary>A* from the cell of a to the cell of b; false with the reason when an end is blocked or no path exists.</summary>
        public static bool Plan(GroundTruthGrid grid, Vector3 a, Vector3 b, out List<Vector2Int> cells, out double lengthCells, out string error)
        {
            error = null;
            var sa = grid.CellOf(a.x, a.z);
            var sb = grid.CellOf(b.x, b.z);
            if (!grid.Free(sa.x, sa.y)) error = $"start ({a.x:0.00}, {a.z:0.00}) lies in blocked cell ({sa.x}, {sa.y})";
            else if (!grid.Free(sb.x, sb.y)) error = $"goal ({b.x:0.00}, {b.z:0.00}) lies in blocked cell ({sb.x}, {sb.y})";
            if (error != null)
            {
                cells = null;
                lengthCells = double.NaN;
                return false;
            }
            if (GridAStar.TryFind(grid, sa, sb, out cells, out lengthCells)) return true;
            error = $"no path on the grid from cell ({sa.x}, {sa.y}) to cell ({sb.x}, {sb.y})";
            return false;
        }

        /// <summary>
        /// Write run_###/grid.json and run_###/optimal_path.json for a run from a to b, and draw A, B and the path. The
        /// folder must exist; files are never overwritten.
        /// </summary>
        public OptimalPathFile WriteRun(string runDir, Vector3 a, Vector3 b)
        {
            if (!Plan(Grid, a, b, out var cells, out _, out string error)) throw new InvalidOperationException(error);
            var path = GroundTruthFiles.OptimalPath(Grid, cells);
            GroundTruthFiles.WriteNew(Path.Combine(runDir, "grid.json"), GroundTruthFiles.ToJson(GroundTruthFiles.Grid(Grid, a.x, a.z, b.x, b.z)));
            GroundTruthFiles.WriteNew(Path.Combine(runDir, "optimal_path.json"), GroundTruthFiles.ToJson(path));
            ShowRun(a, b, path);
            return path;
        }

        // ---------------- visuals (GroundTruth layer only) ----------------

        void EnsureVisualRoot()
        {
            if (visuals != null) return;
            var go = new GameObject("GroundTruth (not visible to the robot)") { layer = Layer };
            go.transform.SetParent(transform, false);
            visuals = go.transform;
            startMat = NewMaterial(new Color(0.1f, 1f, 0.3f, 0.9f));
            goalMat = NewMaterial(new Color(1f, 0.8f, 0.1f, 0.9f));
            pathMat = NewMaterial(new Color(0.2f, 0.7f, 1f, 0.9f));
            pointMat = NewMaterial(new Color(1f, 1f, 1f, 0.95f));
            blockedMat = NewMaterial(new Color(1f, 0.15f, 0.1f, 0.25f));
            var blocked = MeshObject("Blocked cells", BlockedCellsMesh(Grid, FloorY + gt.floor_offset_m), blockedMat);
            blocked.transform.SetParent(visuals, false);
        }

        /// <summary>Unlit, unshadowed material for ground-truth drawing (Sprites/Default renders in URP and blends alpha).</summary>
        public static Material NewMaterial(Color color)
        {
            Shader shader = null;
            foreach (var name in new[] { "Sprites/Default", "Universal Render Pipeline/Unlit", "Unlit/Color" })
            {
                shader = Shader.Find(name);
                if (shader != null) break;
            }
            return new Material(shader) { color = color, name = "GroundTruth" };
        }

        /// <summary>A child object on the ground-truth layer with this mesh; no collider, no shadows.</summary>
        GameObject MeshObject(string name, Mesh mesh, Material mat)
        {
            var go = new GameObject(name) { layer = Layer };
            go.AddComponent<MeshFilter>().sharedMesh = mesh;
            var r = go.AddComponent<MeshRenderer>();
            Unshadowed(r, mat);
            return go;
        }

        public static void Unshadowed(Renderer r, Material mat)
        {
            r.sharedMaterial = mat;
            r.shadowCastingMode = ShadowCastingMode.Off;
            r.receiveShadows = false;
            r.lightProbeUsage = LightProbeUsage.Off;
            r.reflectionProbeUsage = ReflectionProbeUsage.Off;
        }

        /// <summary>Draw A, B and the optimal path between them without writing any file (the leak test pose).</summary>
        public void Show(Vector3 a, Vector3 b)
        {
            if (!Plan(Grid, a, b, out var cells, out _, out string error)) throw new InvalidOperationException(error);
            ShowRun(a, b, GroundTruthFiles.OptimalPath(Grid, cells));
        }

        void ShowRun(Vector3 a, Vector3 b, OptimalPathFile path)
        {
            if (runVisuals != null) Destroy(runVisuals);
            runVisuals = new GameObject("Run") { layer = Layer };
            runVisuals.transform.SetParent(visuals, false);
            float y = FloorY + gt.floor_offset_m;
            Marker("A (start)", new Vector3(a.x, y, a.z), startMat).transform.SetParent(runVisuals.transform, true);
            Marker("B (goal)", new Vector3(b.x, y, b.z), goalMat).transform.SetParent(runVisuals.transform, true);

            var line = new GameObject("Optimal path line") { layer = Layer };
            line.transform.SetParent(runVisuals.transform, false);
            var lr = line.AddComponent<LineRenderer>();
            Unshadowed(lr, pathMat);
            lr.useWorldSpace = true;
            lr.widthMultiplier = gt.line_width_m;
            lr.positionCount = path.points.Count;
            for (int i = 0; i < path.points.Count; i++) lr.SetPosition(i, new Vector3((float)path.points[i].x, y + 0.005f, (float)path.points[i].z));

            var pts = new List<Vector3>();
            foreach (var p in path.points) pts.Add(new Vector3((float)p.x, y + 0.01f, (float)p.z));
            MeshObject("Optimal path points", QuadsMesh(pts, gt.path_point_size_m), pointMat).transform.SetParent(runVisuals.transform, false);
        }

        /// <summary>A checkpoint marker: a flat disc on the floor, a thin pole and a ball on top. Colliders removed at once.</summary>
        GameObject Marker(string name, Vector3 floorPoint, Material mat)
        {
            var root = new GameObject(name) { layer = Layer };
            root.transform.position = floorPoint;
            float r = gt.marker_radius_m, h = gt.marker_height_m;
            void Part(PrimitiveType type, Vector3 localPos, Vector3 scale)
            {
                var p = GameObject.CreatePrimitive(type);
                DestroyImmediate(p.GetComponent<Collider>());     // never an obstacle, never a physics contact
                p.layer = Layer;
                p.transform.SetParent(root.transform, false);
                p.transform.localPosition = localPos;
                p.transform.localScale = scale;
                Unshadowed(p.GetComponent<Renderer>(), mat);
            }
            Part(PrimitiveType.Cylinder, new Vector3(0f, 0.005f, 0f), new Vector3(2f * r, 0.005f, 2f * r));
            Part(PrimitiveType.Cylinder, new Vector3(0f, 0.5f * h, 0f), new Vector3(0.1f * r, 0.5f * h, 0.1f * r));
            Part(PrimitiveType.Sphere, new Vector3(0f, h, 0f), new Vector3(0.6f * r, 0.6f * r, 0.6f * r));
            return root;
        }

        static Mesh BlockedCellsMesh(GroundTruthGrid g, float y)
        {
            var centres = new List<Vector3>();
            for (int iz = 0; iz < g.CellsZ; iz++)
                for (int ix = 0; ix < g.CellsX; ix++)
                    if (g.Blocked(ix, iz))
                    {
                        g.Centre(ix, iz, out double x, out double z);
                        centres.Add(new Vector3((float)x, y, (float)z));
                    }
            return QuadsMesh(centres, (float)g.CellSize * 0.96f);
        }

        /// <summary>One mesh of horizontal squares (side size) centred on the given points, facing up.</summary>
        static Mesh QuadsMesh(List<Vector3> centres, float size)
        {
            var v = new List<Vector3>(centres.Count * 4);
            var tri = new List<int>(centres.Count * 6);
            float h = 0.5f * size;
            foreach (var c in centres)
            {
                int i = v.Count;
                v.Add(c + new Vector3(-h, 0f, -h));
                v.Add(c + new Vector3(-h, 0f, h));
                v.Add(c + new Vector3(h, 0f, h));
                v.Add(c + new Vector3(h, 0f, -h));
                tri.AddRange(new[] { i, i + 1, i + 2, i, i + 2, i + 3 });
            }
            var m = new Mesh { name = "GroundTruthQuads", indexFormat = IndexFormat.UInt32 };
            m.SetVertices(v);
            m.SetTriangles(tri, 0);
            m.RecalculateBounds();
            return m;
        }

        // ---------------- leak test ----------------

        /// <summary>
        /// Render both robot cameras from their current pose with every renderer on this layer on, then off (same frame:
        /// nothing moves in between), write the PNG pairs into folder and compare them pixel by pixel. Then, as a control,
        /// render once more with the layer in both culling masks (in memory only, no PNG: Python compares every _on/_off
        /// pair). The renderers and masks are restored afterwards. Passes only if every pair is identical within
        /// maxPixelDiff and the control shows the layer in every camera.
        /// </summary>
        public bool LeakTest(string folder, int maxPixelDiff, out List<LeakPair> pairs) =>
            LeakTest(panCam, omniCam, cfg, Layer, folder, maxPixelDiff, out pairs);

        public static bool LeakTest(Camera panCam, Camera omniCam, RobotConfig cfg, int layer, string folder, int maxPixelDiff, out List<LeakPair> pairs)
        {
            Directory.CreateDirectory(folder);
            var gtRenderers = new List<Renderer>();
            foreach (var r in FindObjectsByType<Renderer>(FindObjectsInactive.Exclude, FindObjectsSortMode.InstanceID))
                if (r.gameObject.layer == layer && r.enabled) gtRenderers.Add(r);

            Color32[] panOn, panOff, eqOn, eqOff, panVisible, eqVisible;
            int bit = 1 << layer, panMask = panCam.cullingMask, omniMask = omniCam.cullingMask;
            try
            {
                panOn = RenderPanTilt(panCam, cfg);
                eqOn = Render360(omniCam, cfg);
                foreach (var r in gtRenderers) r.enabled = false;
                panOff = RenderPanTilt(panCam, cfg);
                eqOff = Render360(omniCam, cfg);
                foreach (var r in gtRenderers) r.enabled = true;
                panCam.cullingMask = panMask | bit;
                omniCam.cullingMask = omniMask | bit;
                panVisible = RenderPanTilt(panCam, cfg);
                eqVisible = Render360(omniCam, cfg);
            }
            finally
            {
                foreach (var r in gtRenderers) r.enabled = true;
                panCam.cullingMask = panMask;
                omniCam.cullingMask = omniMask;
            }

            int pw = cfg.Unity.pan_tilt_camera.width_px, ph = cfg.Unity.pan_tilt_camera.height_px;
            int ew = cfg.Unity.camera_360.width_px, eh = cfg.Unity.camera_360.height_px;
            pairs = new List<LeakPair>
            {
                Pair(Leak360, eqOn, eqOff, eqVisible, ew, eh, folder, maxPixelDiff),
                Pair(LeakPan, panOn, panOff, panVisible, pw, ph, folder, maxPixelDiff),
            };
            bool passed = gtRenderers.Count > 0;      // nothing on the layer would test nothing
            foreach (var p in pairs) passed &= p.passed;
            return passed;
        }

        static LeakPair Pair(string name, Color32[] on, Color32[] off, Color32[] visible, int w, int h, string folder, int maxPixelDiff)
        {
            GroundTruthFiles.WriteNew(Path.Combine(folder, name + "_on.png"), Png(on, w, h));
            GroundTruthFiles.WriteNew(Path.Combine(folder, name + "_off.png"), Png(off, w, h));
            var c = LeakCompare.Compare(on, w, h, off, w, h);
            int shown = LeakCompare.Compare(visible, w, h, off, w, h).DifferingPixels;
            return new LeakPair
            {
                name = name, passed = c.Passed(maxPixelDiff) && shown > 0, max_diff = c.MaxDiff, differing_pixels = c.DifferingPixels,
                width = w, height = h, layer_visible_pixels = shown,
            };
        }

        static byte[] Png(Color32[] px, int w, int h)
        {
            var tex = new Texture2D(w, h, TextureFormat.RGBA32, false);
            try
            {
                tex.SetPixels32(px);
                tex.Apply(false);
                return tex.EncodeToPNG();
            }
            finally
            {
                DestroyImmediate(tex);
            }
        }

        /// <summary>The pan-tilt camera as it renders now (its own culling mask and field of view), into a temporary texture.</summary>
        static Color32[] RenderPanTilt(Camera cam, RobotConfig cfg)
        {
            var c = cfg.Unity.pan_tilt_camera;
            var rt = RenderTexture.GetTemporary(c.width_px, c.height_px, 24, RenderTextureFormat.ARGB32);
            var previous = cam.targetTexture;
            try
            {
                cam.targetTexture = rt;
                cam.Render();
                return Read(rt);
            }
            finally
            {
                cam.targetTexture = previous;
                RenderTexture.ReleaseTemporary(rt);
            }
        }

        /// <summary>The 360 camera as Camera360 renders it (cubemap, then equirectangular), into temporary textures.</summary>
        static Color32[] Render360(Camera omniCam, RobotConfig cfg)
        {
            var c = cfg.Unity.camera_360;
            var cube = new RenderTexture(c.face_size_px, c.face_size_px, 24, RenderTextureFormat.ARGB32) { dimension = TextureDimension.Cube };
            var eq = new RenderTexture(c.width_px, c.height_px, 0, RenderTextureFormat.ARGB32);
            var active = RenderTexture.active;     // ConvertToEquirect leaves eq active; restored before eq is released
            try
            {
                cube.Create();
                eq.Create();
                if (!omniCam.RenderToCubemap(cube, 63)) throw new InvalidOperationException("RenderToCubemap failed");
                cube.ConvertToEquirect(eq, Camera.MonoOrStereoscopicEye.Mono);
                return Read(eq);
            }
            finally
            {
                RenderTexture.active = active;
                cube.Release();
                eq.Release();
                DestroyImmediate(cube);
                DestroyImmediate(eq);
            }
        }

        static Color32[] Read(RenderTexture rt)
        {
            var previous = RenderTexture.active;
            var tex = new Texture2D(rt.width, rt.height, TextureFormat.RGBA32, false);
            try
            {
                RenderTexture.active = rt;
                tex.ReadPixels(new Rect(0, 0, rt.width, rt.height), 0, 0, false);
                tex.Apply(false);
                return tex.GetPixels32();
            }
            finally
            {
                RenderTexture.active = previous;
                DestroyImmediate(tex);
            }
        }
    }
}
