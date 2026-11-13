using System.Collections.Generic;
using UnityEngine;
using WarehouseAvatar;
using WarehouseHRI;
using WarehouseRobot.Bridge;

namespace WarehouseRobot.GroundTruth
{
    /// <summary>
    /// v4 HUD minimaps (2026-11-12, U5; Avatar/Config/upgrade_design.md section 8), drawn in the Game view with IMGUI after every
    /// camera has rendered, so they can never appear in a robot camera image (as the HUD). Since 2026-11-14 (experiments_ab.md
    /// section 3) each panel is rasterised into its own texture and shown with GUI.DrawTexture: the earlier GL lines drawn inside
    /// OnGUI did not use the pixel matrix under URP and appeared as small lines in the 3D view while the panels stayed empty.
    /// - F9 ROBOT minimap (on by default): only what the robot itself knows: the roadmap (its map), its own pose, the people
    ///   its 360 camera detects (from the hud people list: bearing and distance), its current target and the path it plans
    ///   (the NavMesh corners Unity computed for that target). No ground truth.
    /// - F10 GROUND-TRUTH minimap (off by default, clearly labelled): goal B, the optimal path, the true positions of the
    ///   workers (the commander in orange) and the robot's trail; for the people watching, never the robot.
    /// </summary>
    [DisallowMultipleComponent]
    public class MinimapV4 : MonoBehaviour
    {
        public bool showRobotMap = true, showTruthMap;
        public float size = 260f, marginPx = 10f, topPx = 10f;
        public RobotRig robot;
        public RobotBridgeClient bridge;
        public GroundTruthLayer gt;
        public Transform goal;

        Texture2D robotTex, truthTex;
        Color32[] buf;
        int texSize;
        readonly List<RoadNode> nodes = new List<RoadNode>();
        readonly List<Vector3> trail = new List<Vector3>();
        float nextTrail;
        Rect area;
        Vector2 min, max;
        GUIStyle title;

        void Start()
        {
            if (robot == null) robot = FindFirstObjectByType<RobotRig>();
            if (bridge == null) bridge = FindFirstObjectByType<RobotBridgeClient>();
            if (gt == null) gt = FindFirstObjectByType<GroundTruthLayer>();
            nodes.AddRange(FindObjectsByType<RoadNode>(FindObjectsSortMode.None));
            min = new Vector2(float.MaxValue, float.MaxValue);
            max = new Vector2(float.MinValue, float.MinValue);
            foreach (var n in nodes)
            {
                min = Vector2.Min(min, new Vector2(n.Position.x, n.Position.z));
                max = Vector2.Max(max, new Vector2(n.Position.x, n.Position.z));
            }
            min -= Vector2.one * 4f;
            max += Vector2.one * 4f;
        }

        /// <summary>A new trial: the ground-truth minimap's goal and trail start again.</summary>
        public void BeginRun(Transform goalNode)
        {
            goal = goalNode;
            trail.Clear();
        }

        void Update()
        {
            if (robot != null && Time.time >= nextTrail)
            {
                nextTrail = Time.time + 0.2f;
                trail.Add(robot.transform.position);
                if (trail.Count > 5000) trail.RemoveAt(0);
            }
        }

        void OnGUI()
        {
            var e = Event.current;
            if (e.type == EventType.KeyDown && e.keyCode == KeyCode.F9) showRobotMap = !showRobotMap;
            if (e.type == EventType.KeyDown && e.keyCode == KeyCode.F10) showTruthMap = !showTruthMap;
            if (robot == null || nodes.Count == 0) return;
            title ??= new GUIStyle(GUI.skin.label) { fontSize = 12, fontStyle = FontStyle.Bold };
            // top centre: the camera previews (RobotDebugPanel) take the left, the bridge panel and the HUD the right
            int panels = (showRobotMap ? 1 : 0) + (showTruthMap ? 1 : 0);
            float x = 0.5f * (Screen.width - panels * size - (panels - 1) * marginPx), y = topPx;
            if (showRobotMap) { Panel(new Rect(x, y, size, size), "ROBOT MAP (F9): what the robot knows", false); x += size + marginPx; }
            if (showTruthMap) Panel(new Rect(x, y, size, size), "GROUND TRUTH (F10): never seen by the robot", true);
        }

        void Panel(Rect r, string label, bool truth)
        {
            GUI.Box(r, GUIContent.none);
            GUI.Label(new Rect(r.x + 4f, r.y + 2f, r.width - 8f, 18f), label, title);
            var full = new Rect(r.x + 6f, r.y + 22f, r.width - 12f, r.height - 28f);
            float side = Mathf.Min(full.width, full.height);
            var target = new Rect(full.x + 0.5f * (full.width - side), full.y + 0.5f * (full.height - side), side, side);
            if (Event.current.type != EventType.Repaint) return;
            int texPx = Mathf.Max(16, Mathf.RoundToInt(side));
            if (texSize != texPx || buf == null)
            {
                texSize = texPx;
                buf = new Color32[texPx * texPx];
                if (robotTex != null) Destroy(robotTex);
                if (truthTex != null) Destroy(truthTex);
                robotTex = truthTex = null;
            }
            ref Texture2D tex = ref truth ? ref truthTex : ref robotTex;
            if (tex == null) tex = new Texture2D(texPx, texPx, TextureFormat.RGBA32, false) { filterMode = FilterMode.Point, wrapMode = TextureWrapMode.Clamp, hideFlags = HideFlags.HideAndDontSave };
            area = new Rect(0f, 0f, texPx, texPx);                   // pixel space of the texture (y up)
            var clear = new Color32(20, 22, 28, 220);
            for (int i = 0; i < buf.Length; i++) buf[i] = clear;
            // the roadmap (the robot's map; also drawn under the ground truth for orientation)
            foreach (var n in nodes)
                foreach (var b in n.branches)
                    if (b != null && b.next != null) Line(n.Position, b.next.Position, new Color(0.7f, 0.7f, 0.7f));
            foreach (var n in nodes) Dot(n.Position, n.IsEndpoint ? new Color(0.9f, 0.6f, 0.2f) : n.IsAskNode ? Color.yellow : Color.white, 2.5f);
            Vector3 rp = robot.transform.position;
            float yaw = robot.transform.eulerAngles.y;
            if (!truth)
            {
                if (bridge != null)
                {
                    var corners = bridge.NavCorners;
                    for (int i = 0; i + 1 < corners.Count; i++)
                        Line(new Vector3(corners[i].x, 0f, corners[i].z), new Vector3(corners[i + 1].x, 0f, corners[i + 1].z), new Color(0.2f, 0.8f, 1f));
                    if (bridge.HasTarget) Dot(new Vector3(bridge.Target.x, 0f, bridge.Target.y), new Color(0.2f, 0.8f, 1f), 4f);
                    var hud = bridge.Hud;
                    if (hud != null)
                        foreach (var p in hud.people)
                        {
                            if (p.distance_m < 0f) continue;
                            float a = (yaw + p.bearing_deg) * Mathf.Deg2Rad;
                            var w = rp + new Vector3(Mathf.Sin(a), 0f, Mathf.Cos(a)) * p.distance_m;
                            Dot(w, p.is_commander ? new Color(1f, 0.55f, 0f) : new Color(0.3f, 1f, 0.4f), 4f);
                        }
                }
            }
            else
            {
                if (gt != null)
                {
                    var path = gt.LastPathPoints;
                    for (int i = 0; i + 1 < path.Count; i++) Line(path[i], path[i + 1], new Color(1f, 0.3f, 0.9f));
                }
                for (int i = 0; i + 1 < trail.Count; i++) Line(trail[i], trail[i + 1], new Color(0.2f, 1f, 0.3f));
                foreach (var w in FindObjectsByType<WorkerV4>(FindObjectsSortMode.None))
                    Dot(w.transform.position, w.IsCommander ? new Color(1f, 0.55f, 0f) : new Color(0.6f, 0.6f, 1f), 4f);
                if (goal != null) Dot(goal.position, Color.red, 6f);
            }
            // the robot: a dot and its heading
            Dot(rp, Color.cyan, 4.5f);
            Line(rp, rp + Quaternion.Euler(0f, yaw, 0f) * Vector3.forward * 2.5f, Color.cyan);
            tex.SetPixels32(buf);
            tex.Apply(false);
            GUI.DrawTexture(target, tex, ScaleMode.StretchToFill, true);
        }

        /// <summary>World x, z to the panel texture's pixels (x right, y up), the map's extent fitted into the square.</summary>
        Vector2 Px(Vector3 w)
        {
            float u = Mathf.InverseLerp(min.x, max.x, w.x), v = Mathf.InverseLerp(min.y, max.y, w.z);
            return new Vector2(u * (area.width - 1f), v * (area.height - 1f));
        }

        void Plot(int x, int y, Color32 c)
        {
            if (x < 0 || y < 0 || x >= texSize || y >= texSize) return;
            buf[y * texSize + x] = c;
        }

        void Line(Vector3 a, Vector3 b, Color c)
        {
            var pa = Px(a);
            var pb = Px(b);
            Color32 c32 = c;
            int steps = Mathf.Max(1, Mathf.CeilToInt(Mathf.Max(Mathf.Abs(pb.x - pa.x), Mathf.Abs(pb.y - pa.y))));
            for (int i = 0; i <= steps; i++)
            {
                var p = Vector2.Lerp(pa, pb, (float)i / steps);
                int x = Mathf.RoundToInt(p.x), y = Mathf.RoundToInt(p.y);
                Plot(x, y, c32);
                Plot(x + 1, y, c32);              // 2 px wide, readable at panel size
                Plot(x, y + 1, c32);
            }
        }

        void Dot(Vector3 w, Color c, float r)
        {
            var p = Px(w);
            Color32 c32 = c;
            int x0 = Mathf.RoundToInt(p.x), y0 = Mathf.RoundToInt(p.y), rr = Mathf.Max(1, Mathf.RoundToInt(r));
            for (int y = y0 - rr; y <= y0 + rr; y++)
                for (int x = x0 - rr; x <= x0 + rr; x++) Plot(x, y, c32);
        }

        void OnDestroy()
        {
            if (robotTex != null) Destroy(robotTex);
            if (truthTex != null) Destroy(truthTex);
        }
    }
}
