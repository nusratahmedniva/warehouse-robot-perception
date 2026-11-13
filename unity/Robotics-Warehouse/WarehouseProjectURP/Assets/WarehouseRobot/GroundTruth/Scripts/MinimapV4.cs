using System.Collections.Generic;
using UnityEngine;
using WarehouseAvatar;
using WarehouseHRI;
using WarehouseRobot.Bridge;

namespace WarehouseRobot.GroundTruth
{
    /// <summary>
    /// v4 HUD minimaps (2026-11-12, U5; Avatar/Config/upgrade_design.md section 8), drawn in the Game view with IMGUI and GL
    /// after every camera has rendered, so they can never appear in a robot camera image (as the HUD).
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

        static Material lineMat;
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
            area = new Rect(r.x + 6f, r.y + 22f, r.width - 12f, r.height - 28f);
            if (Event.current.type != EventType.Repaint) return;
            if (lineMat == null)
            {
                lineMat = new Material(Shader.Find("Hidden/Internal-Colored")) { hideFlags = HideFlags.HideAndDontSave };
                lineMat.SetInt("_ZTest", (int)UnityEngine.Rendering.CompareFunction.Always);
            }
            GL.PushMatrix();
            lineMat.SetPass(0);
            GL.LoadPixelMatrix();
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
            GL.PopMatrix();
        }

        Vector2 Px(Vector3 w)
        {
            float u = Mathf.InverseLerp(min.x, max.x, w.x), v = Mathf.InverseLerp(min.y, max.y, w.z);
            float s = Mathf.Min(area.width, area.height);
            float ox = area.x + 0.5f * (area.width - s), oy = area.y + 0.5f * (area.height - s);
            // GL pixel space: y up from the bottom of the screen; GUI space: y down from the top
            return new Vector2(ox + u * s, Screen.height - (oy + (1f - v) * s));
        }

        void Line(Vector3 a, Vector3 b, Color c)
        {
            GL.Begin(GL.LINES);
            GL.Color(c);
            var pa = Px(a);
            var pb = Px(b);
            GL.Vertex3(pa.x, pa.y, 0f);
            GL.Vertex3(pb.x, pb.y, 0f);
            GL.End();
        }

        void Dot(Vector3 w, Color c, float r)
        {
            var p = Px(w);
            GL.Begin(GL.QUADS);
            GL.Color(c);
            GL.Vertex3(p.x - r, p.y - r, 0f);
            GL.Vertex3(p.x + r, p.y - r, 0f);
            GL.Vertex3(p.x + r, p.y + r, 0f);
            GL.Vertex3(p.x - r, p.y + r, 0f);
            GL.End();
        }
    }
}
