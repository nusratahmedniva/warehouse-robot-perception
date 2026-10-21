using System;
using System.Collections.Generic;
using UnityEngine;

namespace WarehouseHRI
{
    /// <summary>robot_vision/configs/task1_route.json (Task 1 only).</summary>
    [Serializable]
    public class Task1RouteConfig
    {
        public int checkpoints = 3;
        public float merge_with_junction_m = 0.5f;
        public float worker_ahead_m = 1f;
        public float worker_right_m = 2.5f;
    }

    /// <summary>One Task 1 worker: the stop it stands at, its floor position and its facing.</summary>
    public struct Task1WorkerStand
    {
        public string Stop;
        public Vector3 Position;
        public Quaternion Rotation;
    }

    public struct Task1Stop
    {
        public string Name;
        public Vector2 Position;   // floor x, z
        public bool IsJunction;    // an existing roadmap junction (kept with its other branches)

        public Task1Stop(string name, Vector2 position, bool isJunction)
        {
            Name = name;
            Position = position;
            IsJunction = isJunction;
        }
    }

    /// <summary>
    /// Task 1 checkpoints (declared design change 2026-10-21), the same rule as robot_vision/task_route.py: the roadmap's
    /// straight line (start, its only branch, then FORWARD at every junction, to an endpoint) is cut into
    /// checkpoints + 1 equal parts; the cut points are checkpoints C1..Cn; one within merge_with_junction_m of a
    /// junction on the line is that junction; every junction on the line is a stop. Apply() adds the checkpoints to the
    /// scene's roadmap for the Play session only (each a junction with one FORWARD branch) and links the stops in
    /// driving order. Workers (2026-10-21, second declared change before any Task 1 final): one standing worker per
    /// stop, WorkerStands() (worker_ahead_m ahead, worker_right_m right of the arrival direction, facing back), built
    /// into the scene by the scenario builder and checked against this rule by the trial runner.
    /// </summary>
    public static class Task1Route
    {
        public const string Prefix = "Task1:";

        /// <summary>start, then its only branch (waypoints) or its FORWARD branch (junctions), to an endpoint.</summary>
        public static List<RoadNode> StraightLine(RoadNode start)
        {
            var line = new List<RoadNode> { start };
            for (var n = start; !n.IsEndpoint;)
            {
                var next = n.IsJunction ? n.Next(GestureCommand.FORWARD) : n.OnlyNext;
                if (next == null || line.Contains(next)) throw new InvalidOperationException($"the straight line from {start.name} ends at {n.name} without an endpoint");
                line.Add(next);
                n = next;
            }

            return line;
        }

        static Vector2 Xz(RoadNode n) => new Vector2(n.Position.x, n.Position.z);

        /// <summary>Every stop on the line, in driving order (the rule above).</summary>
        public static List<Task1Stop> Stops(IList<RoadNode> line, int count, float mergeM)
        {
            if (count < 0) throw new ArgumentException("checkpoints must be >= 0");
            var along = new List<float> { 0f };
            for (int i = 1; i < line.Count; i++) along.Add(along[i - 1] + Vector2.Distance(Xz(line[i - 1]), Xz(line[i])));
            float total = along[along.Count - 1];
            var stops = new List<KeyValuePair<float, Task1Stop>>();
            for (int i = 0; i < line.Count; i++)
                if (line[i].IsJunction) stops.Add(new KeyValuePair<float, Task1Stop>(along[i], new Task1Stop(line[i].name, Xz(line[i]), true)));
            int segments = line.Count - 1;
            for (int k = 1; k <= count; k++)
            {
                float d = total * k / (count + 1);
                int i = 0;
                while (i + 1 < segments && along[i + 1] <= d + 1e-6f) i++;
                float len = along[i + 1] - along[i];
                Vector2 p = Vector2.Lerp(Xz(line[i]), Xz(line[i + 1]), len > 0f ? (d - along[i]) / len : 0f);
                bool merged = false;
                foreach (var s in stops)
                    if (s.Value.IsJunction && Vector2.Distance(s.Value.Position, p) <= mergeM) merged = true;
                if (merged) continue;
                foreach (var n in line)
                    if (Vector2.Distance(Xz(n), p) <= mergeM) throw new InvalidOperationException($"checkpoint C{k} falls on {n.name}, which is not a junction");
                stops.Add(new KeyValuePair<float, Task1Stop>(d, new Task1Stop("C" + k, p, false)));
            }

            stops.Sort((a, b) => a.Key.CompareTo(b.Key));
            var result = new List<Task1Stop>();
            foreach (var s in stops) result.Add(s.Value);
            return result;
        }

        public static string RouteId(IList<Task1Stop> stops)
        {
            var names = new List<string>();
            foreach (var s in stops) names.Add(s.Name);
            return Prefix + string.Join(",", names);
        }

        /// <summary>A worker stand: aheadM ahead of the node and rightM to the right of the arrival direction, facing back.</summary>
        public static void StandPose(Vector3 node, Vector3 previous, float aheadM, float rightM, out Vector3 position, out Quaternion rotation)
        {
            Vector3 arrive = node - previous;
            arrive.y = 0f;
            arrive.Normalize();
            Vector3 right = Vector3.Cross(Vector3.up, arrive);
            position = node + arrive * aheadM + right * rightM;
            rotation = Quaternion.LookRotation(-arrive, Vector3.up);
        }

        /// <summary>
        /// The Task 1 workers, one per stop in driving order (scenario side only; same rule as
        /// task_route.task1_worker_stands). Reads the scene roadmap, changes nothing. Height: the start node's.
        /// </summary>
        public static List<Task1WorkerStand> WorkerStands(RoadNode start, Task1RouteConfig cfg)
        {
            var line = StraightLine(start);
            var stops = Stops(line, cfg.checkpoints, cfg.merge_with_junction_m);
            var result = new List<Task1WorkerStand>();
            float y = start.Position.y;
            Vector3 previous = start.Position;
            foreach (var s in stops)
            {
                var node = new Vector3(s.Position.x, y, s.Position.y);
                StandPose(node, previous, cfg.worker_ahead_m, cfg.worker_right_m, out var p, out var r);
                result.Add(new Task1WorkerStand { Stop = s.Name, Position = p, Rotation = r });
                previous = node;
            }

            return result;
        }

        /// <summary>Scene name of the Task 1 worker standing at a stop (under WarehouseHRI/Task1Workers).</summary>
        public static string WorkerName(string stop) => "Worker_" + stop;
        public const string WorkersGroup = "Task1Workers";

        /// <summary>
        /// Adds the checkpoints to the scene (siblings of the start node) and links start -> stops -> endpoint by FORWARD.
        /// Returns the stop nodes in driving order. Call once per Play session (the scene is not saved).
        /// </summary>
        public static List<RoadNode> Apply(RoadNode start, Task1RouteConfig cfg, out string routeId)
        {
            var line = StraightLine(start);
            var stops = Stops(line, cfg.checkpoints, cfg.merge_with_junction_m);
            routeId = RouteId(stops);
            var chain = new List<RoadNode> { start };
            var created = new HashSet<RoadNode>();
            foreach (var s in stops)
            {
                RoadNode node = null;
                if (s.IsJunction)
                    foreach (var n in line) if (n.name == s.Name) node = n;
                if (node == null)
                {
                    var go = new GameObject(s.Name);
                    go.transform.SetParent(start.transform.parent, false);
                    go.transform.position = new Vector3(s.Position.x, start.Position.y, s.Position.y);
                    node = go.AddComponent<RoadNode>();
                    node.kind = RoadNodeKind.Junction;
                    created.Add(node);
                }

                chain.Add(node);
            }

            chain.Add(line[line.Count - 1]);
            for (int i = 0; i + 1 < chain.Count; i++)
            {
                var node = chain[i];
                var next = chain[i + 1];
                if (i == 0 || created.Contains(node))
                {
                    var cmd = i == 0 && node.branches.Count == 1 && node.branches[0] != null ? node.branches[0].command : GestureCommand.FORWARD;
                    node.branches = new List<RoadBranch> { new RoadBranch { command = cmd, next = next } };
                }
                else
                {
                    bool set = false;
                    foreach (var b in node.branches)
                        if (b != null && b.command == GestureCommand.FORWARD) { b.next = next; set = true; }
                    if (!set) node.branches.Add(new RoadBranch { command = GestureCommand.FORWARD, next = next });
                }

            }

            return chain.GetRange(1, chain.Count - 2);
        }
    }
}
