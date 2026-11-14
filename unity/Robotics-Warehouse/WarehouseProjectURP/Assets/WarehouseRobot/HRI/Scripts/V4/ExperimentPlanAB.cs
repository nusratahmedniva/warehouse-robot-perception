using System;
using System.Collections.Generic;
using UnityEngine;

namespace WarehouseHRI.V4
{
    /// <summary>One experiment of Scenario/Config/experiments_ab_unity.json (A1..A4, B1..B4).</summary>
    [Serializable]
    public class ExperimentDef
    {
        public string name;
        /// <summary>A or B: the set of configs/v4/experiments/scenarios_ab.json (its lie_probability).</summary>
        public string set;
        /// <summary>"1".."4": the scenario of scenarios_ab.json (map, goal, layout).</summary>
        public string scenario;
        /// <summary>Asking nodes with a third worker (Set B needs junctions with 2-3 workers; the same in A and B).</summary>
        public string[] three_worker_nodes = new string[0];
    }

    [Serializable]
    public class SlotDef
    {
        /// <summary>Back along the arrival road from the node (at the start node: behind it, opposite the start heading).</summary>
        public float before_m;
        /// <summary>To the right of the arrival direction (negative = left).</summary>
        public float right_m;
    }

    [Serializable]
    public class MapProposal
    {
        /// <summary>Map name used in place of a scenario's map when the A2 side asks for it.</summary>
        public string name;
        /// <summary>The proposal file (roadmap.json format), project path under Assets/.</summary>
        public string file;
    }

    /// <summary>Scenario/Config/experiments_ab_unity.json (experiments_ab.md sections 3 and 4).</summary>
    [Serializable]
    public class ExperimentsUnityConfig
    {
        public string note;
        public string scenarios_ab;
        public string roadmap_v4;
        public string looks;
        public ExperimentDef[] experiments = new ExperimentDef[0];
        public SlotDef[] junction_slots = new SlotDef[0];
        public SlotDef[] start_slots = new SlotDef[0];
        public float approach_m;
        public float nearer_margin_m;
        /// <summary>The bystander margin of the random layout (experiments_ab.md section 3, conflict with the 6 m square).</summary>
        public float random_nearer_margin_m;
        public int random_max_draws;
        public float ask_max_distance_m;
        public float activation_radius_m;
        public int max_active_avatars;
        public float activation_sample_step_m;
        /// <summary>A2: "right" (Anisha's turn map) and/or "left" (the proposal turn_left), drawn per run when both.</summary>
        public string[] a2_sides = new string[0];
        public MapProposal[] proposals = new MapProposal[0];
        public float[] truthful_rgb = new float[0];
        public float[] liar_rgb = new float[0];

        public static ExperimentsUnityConfig Parse(string json) =>
            JsonUtility.FromJson<ExperimentsUnityConfig>(json ?? "") ?? throw new FormatException("experiments_ab_unity.json: not a JSON object");

        public ExperimentDef Experiment(string name) => Array.Find(experiments ?? new ExperimentDef[0], e => e != null && e.name == name);

        public List<string> Validate()
        {
            var e = new List<string>();
            if (string.IsNullOrEmpty(scenarios_ab) || string.IsNullOrEmpty(roadmap_v4) || string.IsNullOrEmpty(looks)) e.Add("scenarios_ab, roadmap_v4 and looks are required");
            if (experiments == null || experiments.Length == 0) e.Add("experiments: empty");
            else
                foreach (var x in experiments)
                    if (x == null || string.IsNullOrEmpty(x.name) || (x.set != "A" && x.set != "B") || string.IsNullOrEmpty(x.scenario)) e.Add("experiments: every entry needs name, set A or B and scenario");
            if (junction_slots == null || junction_slots.Length < 3 || start_slots == null || start_slots.Length < 3) e.Add("junction_slots and start_slots: 3 slots each");
            if (!(approach_m > 0f) || !(nearer_margin_m > 0f) || !(random_nearer_margin_m > 0f)) e.Add("approach_m, nearer_margin_m and random_nearer_margin_m must be > 0");
            if (random_max_draws < 1) e.Add("random_max_draws must be >= 1");
            if (!(ask_max_distance_m > 0f) || !(activation_radius_m > 0f) || !(activation_sample_step_m > 0f)) e.Add("ask_max_distance_m, activation_radius_m and activation_sample_step_m must be > 0");
            if (max_active_avatars < 1) e.Add("max_active_avatars must be >= 1");
            if (a2_sides == null || a2_sides.Length == 0) e.Add("a2_sides: right and/or left");
            else foreach (var s in a2_sides) if (s != "right" && s != "left") e.Add("a2_sides: right and/or left");
            if (truthful_rgb == null || truthful_rgb.Length != 3 || liar_rgb == null || liar_rgb.Length != 3) e.Add("truthful_rgb and liar_rgb: three numbers each");
            return e;
        }
    }

    /// <summary>The placement rule of configs/v4/experiments/scenarios_ab.json (placement_rule) and the layout values of a scenario.</summary>
    public sealed class PlacementRule
    {
        public float MinWorkerSeparationM, MinTurningPointM, MinRoadM, ApproachM, NearerMarginM;
    }

    /// <summary>One worker of one run: where it stands, its look and what it answers when asked.</summary>
    public sealed class PlannedWorker
    {
        public int Id;
        public string Node;
        /// <summary>0-based slot at its node: slot 0 is the first worker (the one the robot reaches first).</summary>
        public int Slot;
        public Vector3 Position;
        public string Gender;
        public string Look;
        public bool Liar;
        /// <summary>The direction a truthful worker shows here: LEFT, FORWARD, RIGHT (a branch toward B) or BACK.</summary>
        public string TrueCommand;
        /// <summary>The direction this worker shows every time it is asked in the run (TrueCommand unless it lies).</summary>
        public string ShownCommand;
        /// <summary>The shown direction is a branch of the node in the robot's map (false: an impossible direction).</summary>
        public bool ShownIsBranch;
    }

    public sealed class RunPlanAB
    {
        public int Run;
        public string Goal;
        /// <summary>The map this run uses (A2: turn or turn_left).</summary>
        public string MapName;
        public readonly List<PlannedWorker> Workers = new List<PlannedWorker>();
        /// <summary>Per asking node: rejected candidate positions (random layout; 0 for beside).</summary>
        public readonly Dictionary<string, int> Redraws = new Dictionary<string, int>();
        public int MaxActive;
    }

    /// <summary>
    /// Experiments A and B (Avatar/Config/experiments_ab.md sections 3 and 4; AUDIT.md section 16). Pure logic, no scene access: the
    /// maps (Anisha's scenarios_ab.json maps or configs/v4/roadmap.json), the asking nodes, the truthful and lying directions, the
    /// placement of the workers under the rules, the look rotation and the activation window. TrialRunnerV4's experiment mode uses
    /// it; the Edit Mode tests check every rule on the real map files.
    /// </summary>
    public sealed class ExperimentPlanAB
    {
        public const string Left = "LEFT", Forward = "FORWARD", Right = "RIGHT", Back = "BACK";
        public static readonly string[] Directions = { Left, Forward, Right, Back };
        const ulong PlaceSalt = 0x504C414345414231UL, LieSalt = 0x4C49455341423131UL, SideSalt = 0x5349444541423131UL;

        public ExperimentDef Def;
        public ExperimentsUnityConfig Cfg;
        public string MapName, Goal, LayoutKind;
        public RoadmapV4 Map, Physical, LeftMap;
        public float LieProbability, HalfSizeM;
        public PlacementRule Rule;
        int m_People;

        /// <summary>Build the plan of one experiment from the config texts; null with the reason when anything is missing or inconsistent.</summary>
        public static ExperimentPlanAB Build(ExperimentsUnityConfig cfg, string experiment, string scenariosJson, string roadmapJson,
                                             Func<string, string> readProjectFile, out string error)
        {
            error = null;
            var ce = cfg.Validate();
            if (ce.Count > 0) { error = "experiments_ab_unity.json: " + string.Join("; ", ce); return null; }
            var def = cfg.Experiment(experiment);
            if (def == null) { error = $"experiment '{experiment}' is not in experiments_ab_unity.json"; return null; }
            try
            {
                var root = (Dictionary<string, object>)MiniJson.Parse(scenariosJson);
                var sets = (Dictionary<string, object>)root["sets"];
                var scen = (Dictionary<string, object>)((Dictionary<string, object>)root["scenarios"])[def.scenario];
                var layout = (Dictionary<string, object>)scen["layout"];
                var pr = (Dictionary<string, object>)root["placement_rule"];
                var p = new ExperimentPlanAB
                {
                    Def = def, Cfg = cfg, MapName = (string)scen["map"], Goal = (string)scen["goal"], LayoutKind = (string)layout["kind"],
                    LieProbability = (float)(double)((Dictionary<string, object>)sets[def.set])["lie_probability"],
                    Physical = RoadmapV4.Parse(roadmapJson),
                    Rule = new PlacementRule
                    {
                        MinWorkerSeparationM = (float)(double)pr["min_worker_separation_m"], MinTurningPointM = (float)(double)pr["min_turning_point_m"],
                        MinRoadM = layout.TryGetValue("min_road_m", out var mr) ? (float)(double)mr : 0f,
                        ApproachM = cfg.approach_m, NearerMarginM = (string)layout["kind"] == "random" ? cfg.random_nearer_margin_m : cfg.nearer_margin_m,
                    },
                    HalfSizeM = layout.TryGetValue("half_size_m", out var hs) ? (float)(double)hs : 0f,
                    m_People = (int)(double)layout["people"],
                };
                p.Map = p.MapName == "roadmap" ? p.Physical : RoadmapV4.FromObject((Dictionary<string, object>)((Dictionary<string, object>)root["maps"])[p.MapName]);
                if (p.MapName == "turn" && Array.IndexOf(cfg.a2_sides, "left") >= 0)
                {
                    var prop = Array.Find(cfg.proposals ?? new MapProposal[0], x => x != null && x.name == "turn_left");
                    if (prop == null) { error = "a2_sides lists left but proposals has no turn_left"; return null; }
                    p.LeftMap = RoadmapV4.Parse(readProjectFile(prop.file));
                }
                if (p.LayoutKind != "beside" && p.LayoutKind != "random") { error = $"layout '{p.LayoutKind}' is neither beside nor random"; return null; }
                if (p.LayoutKind == "random" && !(p.HalfSizeM > 0f)) { error = "layout random needs half_size_m"; return null; }
                if (p.m_People < 1) { error = "layout people must be >= 1"; return null; }
                return p;
            }
            catch (Exception e) when (e is KeyNotFoundException || e is InvalidCastException || e is FormatException || e is NullReferenceException)
            {
                error = $"scenarios_ab.json or a map file does not hold what experiment {experiment} needs: {e.Message}";
                return null;
            }
        }

        // ---------------------------------------------------------------- maps

        /// <summary>The asking nodes of a map: the start node, then every junction, in file order.</summary>
        public static List<RoadmapV4.NodeDef> AskNodes(RoadmapV4 map)
        {
            var list = new List<RoadmapV4.NodeDef>();
            foreach (var n in map.Nodes) if (n.Name == map.Start) list.Add(n);
            foreach (var n in map.Nodes) if (n.Kind == RoadmapV4.KindJunction) list.Add(n);
            return list;
        }

        public static List<string> Endpoints(RoadmapV4 map)
        {
            var list = new List<string>();
            foreach (var n in map.Nodes) if (n.Kind == RoadmapV4.KindEndpoint) list.Add(n.Name);
            list.Sort(StringComparer.Ordinal);
            return list;
        }

        public static Vector3 Pos(RoadmapV4.NodeDef n) => new Vector3(n.X, 0f, n.Z);

        /// <summary>Every road of a map as a segment (node to each branch's next node).</summary>
        public static List<KeyValuePair<Vector3, Vector3>> Roads(RoadmapV4 map)
        {
            var list = new List<KeyValuePair<Vector3, Vector3>>();
            foreach (var kv in map.Branches)
                foreach (var b in kv.Value) list.Add(new KeyValuePair<Vector3, Vector3>(Pos(map.Node(kv.Key)), Pos(map.Node(b.Value))));
            return list;
        }

        /// <summary>The branch command of <paramref name="node"/> whose roads lead to <paramref name="goal"/>, or BACK when none does
        /// (a truthful worker at a node that cannot lead to B points back along the arrival road, AUDIT.md 16.11 item 4).</summary>
        public static string TruthfulCommand(RoadmapV4 map, string node, string goal)
        {
            if (!map.Branches.TryGetValue(node, out var branches)) return Back;
            foreach (var b in branches) if (Reaches(map, b.Value, goal)) return b.Key;
            return Back;
        }

        static bool Reaches(RoadmapV4 map, string from, string goal)
        {
            var seen = new HashSet<string>();
            var stack = new Stack<string>();
            stack.Push(from);
            while (stack.Count > 0)
            {
                string n = stack.Pop();
                if (n == goal) return true;
                if (!seen.Add(n) || !map.Branches.TryGetValue(n, out var bs)) continue;
                foreach (var b in bs) stack.Push(b.Value);
            }
            return false;
        }

        public static bool IsBranch(RoadmapV4 map, string node, string command) =>
            map.Branches.TryGetValue(node, out var bs) && bs.Exists(b => b.Key == command);

        /// <summary>The world direction (horizontal, unit) a command shows at a node: toward the branch's next node when the node has
        /// that branch, else the arrival heading turned by LEFT -90, FORWARD 0, RIGHT +90, BACK 180 degrees (seen from above).</summary>
        public static Vector3 Direction(RoadmapV4 map, string node, string command)
        {
            var n = map.Node(node);
            if (map.Branches.TryGetValue(node, out var bs))
                foreach (var b in bs)
                    if (b.Key == command)
                    {
                        var next = map.Node(b.Value);
                        return new Vector3(next.X - n.X, 0f, next.Z - n.Z).normalized;
                    }
            float turn = command == Left ? -90f : command == Right ? 90f : command == Back ? 180f : 0f;
            return (Quaternion.AngleAxis(turn, Vector3.up) * map.ArrivalHeading(n)).normalized;
        }

        // ---------------------------------------------------------------- the runs

        /// <summary>The goal of every run: the scenario's fixed goal, or (random_endpoint) the session's goal generator over the map's
        /// endpoints (GoalSequence(seed), the Task 2 order).</summary>
        public List<string> Goals(int seed, int runs)
        {
            var list = new List<string>();
            if (Goal != "random_endpoint") { for (int i = 0; i < runs; i++) list.Add(Goal); return list; }
            var eps = Endpoints(Map);
            var g = new GoalSequence(seed);
            for (int i = 0; i < runs; i++) list.Add(eps[g.NextGoalIndex(eps.Count)]);
            return list;
        }

        /// <summary>The map of one run: A2 draws its side (right / left) from the seeded stream when both are listed.</summary>
        public RoadmapV4 RunMap(int seed, int run, out string name)
        {
            name = MapName;
            if (LeftMap == null) return Map;
            bool right = Array.IndexOf(Cfg.a2_sides, "right") >= 0;
            if (!right) { name = "turn_left"; return LeftMap; }
            if (new Rng(seed, run, 0, SideSalt).NextDouble() < 0.5) return Map;
            name = "turn_left";
            return LeftMap;
        }

        /// <summary>The goal of a run on its map (A2 left: the proposal's endpoint).</summary>
        public static string GoalOn(RoadmapV4 map, string goal) => map.Node(goal) != null ? goal : Endpoints(map).Count == 1 ? Endpoints(map)[0] : goal;

        public int WorkersAt(string node) => m_People + (Array.IndexOf(Def.three_worker_nodes ?? new string[0], node) >= 0 ? 1 : 0);

        /// <summary>
        /// Plan one run: every worker's position (beside slots or seeded random draws, all rules checked), look, lie and the direction
        /// it shows. <paramref name="males"/>, <paramref name="females"/>: the development navigation looks of each gender in name order.
        /// <paramref name="free"/>: Unity's own check of a position (free grid cell, no collider); null = everywhere free (tests).
        /// Null with the reason when a rule cannot be met.
        /// </summary>
        public RunPlanAB PlanRun(int seed, int run, string goal, IList<string> males, IList<string> females, Func<Vector3, bool> free, out string error)
        {
            error = null;
            var map = RunMap(seed, run, out string mapName);
            goal = GoalOn(map, goal);
            var plan = new RunPlanAB { Run = run, Goal = goal, MapName = mapName };
            if (map.Node(goal) == null) { error = $"goal {goal} is not a node of map {mapName}"; return null; }
            if (males == null || males.Count == 0 || females == null || females.Count == 0) { error = "a male and a female navigation look are needed"; return null; }
            var nodes = AskNodes(map);
            int id = 1;
            for (int ni = 0; ni < nodes.Count; ni++)
            {
                var node = nodes[ni];
                int k = WorkersAt(node.Name);
                List<Vector3> pos;
                int redraws = 0;
                if (LayoutKind == "beside")
                {
                    var slots = node.Name == map.Start ? Cfg.start_slots : Cfg.junction_slots;
                    if (k > slots.Length) { error = $"{node.Name}: {k} workers but {slots.Length} slots"; return null; }
                    pos = new List<Vector3>();
                    for (int s = 0; s < k; s++) pos.Add(SlotPosition(map, node, slots[s]));
                    string why = NodeProblem(map, node, pos, plan.Workers, free);
                    if (why != null) { error = $"run {run}, {node.Name}: fixed slots break a rule: {why}"; return null; }
                }
                else
                {
                    pos = DrawRandom(map, node, k, plan.Workers, free, new Rng(seed, run, ni + 1, PlaceSalt), out redraws, out string why);
                    if (pos == null) { error = $"run {run}, {node.Name}: no placement within {Cfg.random_max_draws} draws ({why})"; return null; }
                }
                plan.Redraws[node.Name] = redraws;
                string truthful = TruthfulCommand(map, node.Name, goal);
                for (int s = 0; s < k; s++)
                {
                    var w = new PlannedWorker { Id = id, Node = node.Name, Slot = s, Position = pos[s], Gender = s % 2 == 0 ? "male" : "female", TrueCommand = truthful };
                    var looks = w.Gender == "male" ? males : females;
                    w.Look = looks[(ni + run - 1 + s / 2) % looks.Count];
                    DrawLie(map, w, seed, run, LieProbability);
                    plan.Workers.Add(w);
                    id++;
                }
            }
            plan.MaxActive = MaxActive(map, plan.Workers, Cfg.activation_radius_m, Cfg.activation_sample_step_m);
            if (plan.MaxActive > Cfg.max_active_avatars)
            {
                error = $"run {run}: up to {plan.MaxActive} workers would be active at once (> max_active_avatars {Cfg.max_active_avatars})";
                return null;
            }
            return plan;
        }

        /// <summary>A slot of a node in its arrival frame: before_m back along the arrival road (start node: behind it), right_m to the right.</summary>
        public static Vector3 SlotPosition(RoadmapV4 map, RoadmapV4.NodeDef node, SlotDef slot)
        {
            Vector3 f = map.ArrivalHeading(node);
            Vector3 r = Vector3.Cross(Vector3.up, f);
            return Pos(node) - f * slot.before_m + r * slot.right_m;
        }

        List<Vector3> DrawRandom(RoadmapV4 map, RoadmapV4.NodeDef node, int k, List<PlannedWorker> placed, Func<Vector3, bool> free, Rng rng,
                                 out int redraws, out string lastWhy)
        {
            redraws = 0;
            lastWhy = "";
            var c = Pos(node);
            for (int draw = 0; draw < Cfg.random_max_draws; draw++)
            {
                var pos = new List<Vector3>();
                for (int s = 0; s < k; s++)
                    pos.Add(c + new Vector3(((float)rng.NextDouble() * 2f - 1f) * HalfSizeM, 0f, ((float)rng.NextDouble() * 2f - 1f) * HalfSizeM));
                // slot 0 = the worker nearest the node (the robot reaches it first); the bystander rule is checked against it
                pos.Sort((a, b) => (a - c).sqrMagnitude.CompareTo((b - c).sqrMagnitude));
                lastWhy = NodeProblem(map, node, pos, placed, free);
                if (lastWhy == null) return pos;
                redraws++;
            }
            return null;
        }

        /// <summary>The first rule the workers of one node break (with the workers already placed at other nodes), or null.</summary>
        public string NodeProblem(RoadmapV4 map, RoadmapV4.NodeDef node, IList<Vector3> pos, IList<PlannedWorker> placed, Func<Vector3, bool> free)
        {
            var turning = new List<RoadmapV4.NodeDef>(AskNodes(map));
            foreach (var n in AskNodes(Physical)) turning.Add(n);
            var roads = Roads(map);
            roads.AddRange(Roads(Physical));
            for (int i = 0; i < pos.Count; i++)
            {
                var p = pos[i];
                foreach (var q in placed)
                    if (Flat(p - q.Position) < Rule.MinWorkerSeparationM) return $"worker {i + 1} is {Flat(p - q.Position):0.00} m from worker {q.Id} (< {Rule.MinWorkerSeparationM})";
                for (int j = 0; j < i; j++)
                    if (Flat(p - pos[j]) < Rule.MinWorkerSeparationM) return $"workers {j + 1} and {i + 1} are {Flat(p - pos[j]):0.00} m apart (< {Rule.MinWorkerSeparationM})";
                foreach (var t in turning)
                    if (Flat(p - Pos(t)) < Rule.MinTurningPointM) return $"worker {i + 1} is {Flat(p - Pos(t)):0.00} m from {t.Name} (< {Rule.MinTurningPointM})";
                if (Rule.MinRoadM > 0f)
                    foreach (var r in roads)
                        if (SegmentDistance(p, r.Key, r.Value) < Rule.MinRoadM) return $"worker {i + 1} is {SegmentDistance(p, r.Key, r.Value):0.00} m from a road (< {Rule.MinRoadM})";
                if (free != null && !free(p)) return $"worker {i + 1} at ({p.x:0.00}, {p.z:0.00}) is on a blocked cell or inside a collider";
                if (i > 0)
                {
                    float m = NearerMargin(map, node, pos[i], pos[0]);
                    if (m < Rule.NearerMarginM) return $"worker {i + 1} is only {m:0.00} m farther than the first worker on the approach (< {Rule.NearerMarginM})";
                }
            }
            return null;
        }

        /// <summary>The bystander rule (TrialWorkerGeometry.NearerMargin): the smallest (distance to <paramref name="other"/> - distance to
        /// <paramref name="first"/>) over the last approach_m of the arrival road up to the node, sampled every 0.05 m; at the start node,
        /// at the node alone.</summary>
        public float NearerMargin(RoadmapV4 map, RoadmapV4.NodeDef node, Vector3 other, Vector3 first)
        {
            var n = Pos(node);
            float length = 0f;
            Vector3 back = Vector3.zero;
            if (!string.IsNullOrEmpty(node.ArriveFrom))
            {
                back = Pos(map.Node(node.ArriveFrom)) - n;
                length = Mathf.Min(Rule.ApproachM, back.magnitude);
                back = back.normalized;
            }
            int steps = Mathf.Max(0, Mathf.RoundToInt(length / 0.05f));
            float best = float.PositiveInfinity;
            for (int i = 0; i <= steps; i++)
            {
                var q = n + back * (steps == 0 ? 0f : length * i / steps);
                best = Mathf.Min(best, Flat(q - other) - Flat(q - first));
            }
            return best;
        }

        static void DrawLie(RoadmapV4 map, PlannedWorker w, int seed, int run, float p)
        {
            var rng = new Rng(seed, run, w.Id, LieSalt);
            w.Liar = rng.NextDouble() < p;
            w.ShownCommand = w.TrueCommand;
            if (w.Liar)
            {
                var wrong = new List<string>();
                if (map.Branches.TryGetValue(w.Node, out var bs)) foreach (var b in bs) if (b.Key != w.TrueCommand) wrong.Add(b.Key);
                if (wrong.Count == 0)                       // no wrong valid branch: AUDIT.md 16.2 decision 2 (any other direction)
                    foreach (var d in Directions) if (d != w.TrueCommand) wrong.Add(d);
                w.ShownCommand = wrong[rng.Index(wrong.Count)];
            }
            w.ShownIsBranch = IsBranch(map, w.Node, w.ShownCommand);
        }

        /// <summary>A worker is active (rendered and animated) while the robot is within the activation radius of it.</summary>
        public static bool Active(Vector3 robot, Vector3 worker, float radius) => Flat(worker - robot) <= radius;

        /// <summary>The most workers within the activation radius of any point of any road of the map (sampled every step metres): the
        /// robot drives along the roads, so this bounds the avatars active at once (the asking positions lie within 2 m of a road).</summary>
        public static int MaxActive(RoadmapV4 map, IList<PlannedWorker> workers, float radius, float step)
        {
            int best = 0;
            foreach (var r in Roads(map))
            {
                float len = Flat(r.Value - r.Key);
                int n = Mathf.Max(1, Mathf.CeilToInt(len / step));
                for (int i = 0; i <= n; i++)
                {
                    var q = Vector3.Lerp(r.Key, r.Value, (float)i / n);
                    int count = 0;
                    foreach (var w in workers) if (Active(q, w.Position, radius)) count++;
                    best = Mathf.Max(best, count);
                }
            }
            return best;
        }

        /// <summary>Who answers a new ask: the worker within maxDist of the camera with the smallest angle between the camera's
        /// forward axis and the direction to the worker's head (horizontal); -1 when nobody is that close.</summary>
        public static int ChooseAsked(Vector3 camera, Vector3 cameraForward, IList<KeyValuePair<int, Vector3>> heads, float maxDist)
        {
            int best = -1;
            float bestAngle = float.PositiveInfinity;
            var f = new Vector3(cameraForward.x, 0f, cameraForward.z);
            foreach (var h in heads)
            {
                var d = new Vector3(h.Value.x - camera.x, 0f, h.Value.z - camera.z);
                if (d.magnitude > maxDist) continue;
                float a = f.sqrMagnitude > 1e-8f && d.sqrMagnitude > 1e-8f ? Vector3.Angle(f, d) : 0f;
                if (a < bestAngle) { bestAngle = a; best = h.Key; }
            }
            return best;
        }

        public static float Flat(Vector3 v) => new Vector2(v.x, v.z).magnitude;

        public static float SegmentDistance(Vector3 p, Vector3 a, Vector3 b)
        {
            var p2 = new Vector2(p.x, p.z);
            var a2 = new Vector2(a.x, a.z);
            var ab = new Vector2(b.x, b.z) - a2;
            float t = ab.sqrMagnitude > 1e-12f ? Mathf.Clamp01(Vector2.Dot(p2 - a2, ab) / ab.sqrMagnitude) : 0f;
            return Vector2.Distance(p2, a2 + t * ab);
        }

        /// <summary>A SplitMix64 stream seeded by (session seed, run, index, salt): the same numbers in every process.</summary>
        public sealed class Rng
        {
            ulong m_State;

            public Rng(int seed, int run, int index, ulong salt) => m_State = Mix(Mix(Mix(salt ^ (ulong)(uint)seed) ^ (ulong)(uint)run) ^ (ulong)(uint)index);

            static ulong Mix(ulong z)
            {
                unchecked
                {
                    z += 0x9E3779B97F4A7C15UL;
                    z = (z ^ (z >> 30)) * 0xBF58476D1CE4E5B9UL;
                    z = (z ^ (z >> 27)) * 0x94D049BB133111EBUL;
                    return z ^ (z >> 31);
                }
            }

            public ulong NextULong()
            {
                unchecked
                {
                    m_State += 0x9E3779B97F4A7C15UL;
                    ulong z = m_State;
                    z = (z ^ (z >> 30)) * 0xBF58476D1CE4E5B9UL;
                    z = (z ^ (z >> 27)) * 0x94D049BB133111EBUL;
                    return z ^ (z >> 31);
                }
            }

            /// <summary>Uniform in [0, 1).</summary>
            public double NextDouble() => (NextULong() >> 11) * (1.0 / 9007199254740992.0);

            public int Index(int count) => Math.Min(count - 1, (int)(NextDouble() * count));
        }
    }
}
