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

    /// <summary>
    /// experiments_ab.md section 15 addendum 1, item 3b: the layout that keeps the path clearance. active false: the live layout without
    /// the clearance and the ask-zone checks; active true: these junction slots, two workers per node in the listed experiments, and both
    /// checks. Active since addendum 4 (2026-11-18) with layout (i) of addendum 3, as Anisha's scenarios_ab.json.
    /// </summary>
    [Serializable]
    public class ClearanceLayout
    {
        public bool active;
        public SlotDef[] junction_slots = new SlotDef[0];
        /// <summary>Experiments whose three_worker_nodes become empty (A4, B4: 3 random workers at J1 cannot keep the clearance).</summary>
        public string[] two_worker_experiments = new string[0];
    }

    /// <summary>experiments_ab.md section 15 addendum 6 (variant T4): one checkpoint worker beside a decision branch.</summary>
    [Serializable]
    public class CheckpointDef
    {
        /// <summary>The map whose runs get this checkpoint (scenarios_ab.json map name, or roadmap).</summary>
        public string map;
        /// <summary>The decision junction the branch leaves, and the branch command there.</summary>
        public string from, command;
        /// <summary>Along the branch from the junction (the anchor), and to the right of the travel direction (negative = left).</summary>
        public float s_m, right_m;
    }

    /// <summary>Section 15 addendum 6: the checkpoint workers, their answer radius and Unity's copy of Python's second-opinion radius.</summary>
    [Serializable]
    public class CheckpointsConfig
    {
        public bool active;
        public CheckpointDef[] positions = new CheckpointDef[0];
        /// <summary>A checkpoint worker answers only while the robot's centre is this close to it (and on its branch).</summary>
        public float answer_radius_m;
        /// <summary>Copy of configs/v4/control.json lie_detection.second_opinion_radius_m (rule Q1).</summary>
        public float second_opinion_radius_m;
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
        /// <summary>Section 15 addendum 1, item 3a: a worker answers only while the robot's centre is this close to the worker's own node.</summary>
        public float answer_zone_radius_m;
        /// <summary>Item 3b: every modelled ask position lies within answer_zone_radius_m minus this of its node (clearance_layout active only).</summary>
        public float answer_zone_margin_m;
        /// <summary>Item 3b: no worker this close to a segment the robot can drive (clearance_layout active only).</summary>
        public float path_clearance_m;
        /// <summary>Item 3b, the ask-position model: copies of Python's hri_control.json dialog.approach_distance_m and of the v4 controller's
        /// configs/v4/control.json dialog.reask_shift_m (section 15 addendum 3).</summary>
        public float ask_standoff_m;
        public float reask_shift_m;
        public ClearanceLayout clearance_layout = new ClearanceLayout();
        public CheckpointsConfig checkpoints = new CheckpointsConfig();

        public static ExperimentsUnityConfig Parse(string json) =>
            JsonUtility.FromJson<ExperimentsUnityConfig>(json ?? "") ?? throw new FormatException("experiments_ab_unity.json: not a JSON object");

        public ExperimentDef Experiment(string name) => Array.Find(experiments ?? new ExperimentDef[0], e => e != null && e.name == name);

        /// <summary>A copy with the pending layout applied and active (item 3b): what the config becomes when the block is switched on.</summary>
        public ExperimentsUnityConfig WithClearanceLayout()
        {
            var c = Parse(JsonUtility.ToJson(this));
            c.junction_slots = c.clearance_layout.junction_slots;
            foreach (var e in c.experiments)
                if (e != null && Array.IndexOf(c.clearance_layout.two_worker_experiments ?? new string[0], e.name) >= 0) e.three_worker_nodes = new string[0];
            c.clearance_layout.active = true;
            return c;
        }

        public List<string> Validate()
        {
            var e = new List<string>();
            if (string.IsNullOrEmpty(scenarios_ab) || string.IsNullOrEmpty(roadmap_v4) || string.IsNullOrEmpty(looks)) e.Add("scenarios_ab, roadmap_v4 and looks are required");
            if (experiments == null || experiments.Length == 0) e.Add("experiments: empty");
            else
                foreach (var x in experiments)
                    if (x == null || string.IsNullOrEmpty(x.name) || (x.set != "A" && x.set != "B") || string.IsNullOrEmpty(x.scenario)) e.Add("experiments: every entry needs name, set A or B and scenario");
            // section 15 addendum 4: two junction slots suffice (layout (i)); a third only where an experiment keeps a third worker
            bool third = Array.Exists(experiments ?? new ExperimentDef[0], x => x != null && x.three_worker_nodes != null && x.three_worker_nodes.Length > 0);
            bool thirdInBlock = Array.Exists(experiments ?? new ExperimentDef[0], x => x != null && x.three_worker_nodes != null && x.three_worker_nodes.Length > 0
                                                 && Array.IndexOf(clearance_layout?.two_worker_experiments ?? new string[0], x.name) < 0);
            if (junction_slots == null || junction_slots.Length < (third ? 3 : 2)) e.Add($"junction_slots: {(third ? 3 : 2)} slots (3 when an experiment lists three_worker_nodes)");
            if (start_slots == null || start_slots.Length < 3) e.Add("start_slots: 3 slots");
            if (!(approach_m > 0f) || !(nearer_margin_m > 0f) || !(random_nearer_margin_m > 0f)) e.Add("approach_m, nearer_margin_m and random_nearer_margin_m must be > 0");
            if (random_max_draws < 1) e.Add("random_max_draws must be >= 1");
            if (!(ask_max_distance_m > 0f) || !(activation_radius_m > 0f) || !(activation_sample_step_m > 0f)) e.Add("ask_max_distance_m, activation_radius_m and activation_sample_step_m must be > 0");
            if (max_active_avatars < 1) e.Add("max_active_avatars must be >= 1");
            if (a2_sides == null || a2_sides.Length == 0) e.Add("a2_sides: right and/or left");
            else foreach (var s in a2_sides) if (s != "right" && s != "left") e.Add("a2_sides: right and/or left");
            if (truthful_rgb == null || truthful_rgb.Length != 3 || liar_rgb == null || liar_rgb.Length != 3) e.Add("truthful_rgb and liar_rgb: three numbers each");
            if (!(answer_zone_radius_m > 0f)) e.Add("answer_zone_radius_m must be > 0");
            if (!(answer_zone_margin_m >= 0f) || !(answer_zone_margin_m < answer_zone_radius_m)) e.Add("answer_zone_margin_m must be in [0, answer_zone_radius_m)");
            if (!(path_clearance_m > 0f) || !(ask_standoff_m > 0f) || !(reask_shift_m >= 0f)) e.Add("path_clearance_m and ask_standoff_m must be > 0, reask_shift_m >= 0");
            if (clearance_layout == null || clearance_layout.junction_slots == null || clearance_layout.junction_slots.Length < (thirdInBlock ? 3 : 2))
                e.Add($"clearance_layout.junction_slots: {(thirdInBlock ? 3 : 2)} slots (3 when an experiment outside two_worker_experiments lists three_worker_nodes)");
            else foreach (var n in clearance_layout.two_worker_experiments ?? new string[0]) if (Experiment(n) == null) e.Add($"clearance_layout.two_worker_experiments: '{n}' is not an experiment");
            if (checkpoints != null && checkpoints.active)
            {
                if (!(checkpoints.answer_radius_m > 0f) || !(checkpoints.second_opinion_radius_m > 0f)) e.Add("checkpoints: answer_radius_m and second_opinion_radius_m must be > 0");
                foreach (var d in checkpoints.positions ?? new CheckpointDef[0])
                    if (d == null || string.IsNullOrEmpty(d.map) || string.IsNullOrEmpty(d.from) || Array.IndexOf(ExperimentPlanAB.Directions, d.command) < 0 ||
                        d.command == ExperimentPlanAB.Back || !(d.s_m > 0f) || d.right_m == 0f)
                        e.Add("checkpoints: every position needs map, from, a branch command (LEFT, FORWARD, RIGHT), s_m > 0 and right_m != 0");
            }
            return e;
        }
    }

    /// <summary>The placement rule of configs/v4/experiments/scenarios_ab.json (placement_rule) and the layout values of a scenario.</summary>
    public sealed class PlacementRule
    {
        public float MinWorkerSeparationM, MinTurningPointM, MinRoadM, ApproachM, NearerMarginM;
        /// <summary>Section 15 addendum 1, item 3b (0 = off: clearance_layout inactive): the path clearance, the largest distance of an ask
        /// position from its node (answer zone minus margin) and the ask-position model.</summary>
        public float PathClearanceM, AskZoneM, StandoffM, ReaskShiftM;
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
        /// <summary>The shown direction is a branch of the node in the robot's map (false: an impossible direction). A checkpoint worker's
        /// FORWARD (continue) and BACK (return along its branch) both count as a way on.</summary>
        public bool ShownIsBranch;
        /// <summary>Section 15 addendum 6: the branch of a checkpoint worker; null for a node's worker. For a checkpoint, Node is its label
        /// ("J1 RIGHT -> J3"), Slot 0, TrueCommand FORWARD (the branch leads to the goal) or BACK.</summary>
        public CheckpointBranch Checkpoint;
    }

    /// <summary>Section 15 addendum 6: a checkpoint's branch, its anchor (the road point at S) and its worker's position.</summary>
    public sealed class CheckpointBranch
    {
        public string From, Command, To;
        public float S, Right;
        public Vector3 Anchor, Position;
        public string Label => $"{From} {Command} -> {To}";
    }

    public sealed class RunPlanAB
    {
        public int Run;
        public string Goal;
        /// <summary>The map this run uses (A2: turn or turn_left).</summary>
        public string MapName;
        /// <summary>The workers of the asking nodes.</summary>
        public readonly List<PlannedWorker> Workers = new List<PlannedWorker>();
        /// <summary>Section 15 addendum 6: the checkpoint workers (fixed), ids after the node workers'.</summary>
        public readonly List<PlannedWorker> Checkpoints = new List<PlannedWorker>();
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
            if (cfg.clearance_layout != null && cfg.clearance_layout.active) cfg = cfg.WithClearanceLayout();
            var def = cfg.Experiment(experiment);
            if (def == null) { error = $"experiment '{experiment}' is not in experiments_ab_unity.json"; return null; }
            bool clear = cfg.clearance_layout != null && cfg.clearance_layout.active;
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
                        PathClearanceM = clear ? cfg.path_clearance_m : 0f, AskZoneM = clear ? cfg.answer_zone_radius_m - cfg.answer_zone_margin_m : 0f,
                        StandoffM = cfg.ask_standoff_m, ReaskShiftM = cfg.reask_shift_m,
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

        /// <summary>The map name (scenarios_ab.json: corridor, turn or roadmap) of an experiment of the config, or null when the
        /// experiment or its scenario is unknown (experiments_ab.md section 7: the final configs are checked against it).</summary>
        public static string MapOfExperiment(ExperimentsUnityConfig cfg, string scenariosJson, string experiment)
        {
            var def = cfg.Experiment(experiment);
            if (def == null) return null;
            try
            {
                var scen = (Dictionary<string, object>)((Dictionary<string, object>)((Dictionary<string, object>)MiniJson.Parse(scenariosJson))["scenarios"])[def.scenario];
                return (string)scen["map"];
            }
            catch (Exception e) when (e is KeyNotFoundException || e is InvalidCastException || e is FormatException || e is NullReferenceException) { return null; }
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

        /// <summary>
        /// Section 15 addendum 1, item 3c (development only): the goals of TrialPlayV4 -experimentGoals "E5,E6,...", one per run, in place of
        /// the seeded goals. Null and no error when <paramref name="spec"/> is empty (no override). Refused (null with the reason) in a final,
        /// on a fixed-goal map, for a name that is not an endpoint of the map, or for a list whose length is not the number of runs.
        /// </summary>
        public List<string> GoalsOverride(string spec, bool final, int runs, out string error)
        {
            error = null;
            if (string.IsNullOrWhiteSpace(spec)) return null;
            if (final) { error = "-experimentGoals is for development sessions only; a final takes its goals from the seed"; return null; }
            if (Goal != "random_endpoint") { error = $"-experimentGoals: experiment {Def.name} has the fixed goal {Goal} (map {MapName}); only a random-endpoint map takes goals"; return null; }
            var eps = Endpoints(Map);
            var list = new List<string>();
            foreach (var part in spec.Split(','))
            {
                string g = part.Trim();
                if (eps.IndexOf(g) < 0) { error = $"-experimentGoals: '{g}' is not an endpoint of map {MapName} ({string.Join(", ", eps)})"; return null; }
                list.Add(g);
            }
            if (list.Count != runs) { error = $"-experimentGoals: {list.Count} goal(s) for {runs} run(s); give exactly one per run"; return null; }
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
            // section 15 addendum 6: the checkpoints are fixed and planned first; ids follow the node workers' ids
            var cps = Checkpoints(map, mapName, out error);
            if (cps == null) { error = $"run {run}: {error}"; return null; }
            int nodeWorkers = 0;
            foreach (var n in nodes) nodeWorkers += WorkersAt(n.Name);
            for (int c = 0; c < cps.Count; c++)
            {
                var w = new PlannedWorker { Id = nodeWorkers + 1 + c, Node = cps[c].Label, Slot = 0, Position = cps[c].Position, Gender = c % 2 == 0 ? "male" : "female",
                                            Checkpoint = cps[c], TrueCommand = Reaches(map, cps[c].To, goal) ? Forward : Back };
                var looks = w.Gender == "male" ? males : females;
                w.Look = looks[(c / 2 + run - 1) % looks.Count];
                DrawCheckpointLie(w, seed, run, LieProbability);
                plan.Checkpoints.Add(w);
            }
            var placed = new List<PlannedWorker>(plan.Checkpoints);
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
                    string why = NodeProblem(map, node, pos, placed, free);
                    if (why != null) { error = $"run {run}, {node.Name}: fixed slots break a rule: {why}"; return null; }
                }
                else
                {
                    pos = DrawRandom(map, node, k, placed, free, new Rng(seed, run, ni + 1, PlaceSalt), out redraws, out string why);
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
                    placed.Add(w);
                    id++;
                }
            }
            string cpWhy = CheckpointProblem(map, plan, free);
            if (cpWhy != null) { error = $"run {run}: {cpWhy}"; return null; }
            plan.MaxActive = MaxActive(map, placed, Cfg.activation_radius_m, Cfg.activation_sample_step_m);
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
            if (Rule.PathClearanceM > 0f || Rule.AskZoneM > 0f)
            {
                string why = ClearanceProblem(map, node, pos, placed, roads);
                if (why != null) return why;
            }
            return CheckpointsAroundNode(map, node, pos, placed);
        }

        /// <summary>Section 15 addendum 6: the rules between this node's workers and the checkpoints (placed first): 3.0 m from every anchor,
        /// the clearance from every checkpoint's own drive, farther than ask_max_distance_m from every checkpoint ask point and every checkpoint
        /// farther than that from this node's ask points, every checkpoint at least the bystander margin farther than the node's first worker.
        /// (Separation and the clearance of the checkpoints from this node's drives are the existing checks over the placed workers.)</summary>
        string CheckpointsAroundNode(RoadmapV4 map, RoadmapV4.NodeDef node, IList<Vector3> pos, IList<PlannedWorker> placed)
        {
            List<Vector3> nodeAsks = null;
            float clr = Rule.PathClearanceM - 1e-4f;
            foreach (var c in placed)
            {
                if (c.Checkpoint == null) continue;
                if (nodeAsks == null) DrivableSegments(map, node, pos, Rule.StandoffM, Rule.ReaskShiftM, out nodeAsks);
                var drive = CheckpointDrive(map, c.Checkpoint, c.Position, Rule.StandoffM, Rule.ReaskShiftM, out var cpAsks);
                for (int i = 0; i < pos.Count; i++)
                {
                    float d = Flat(pos[i] - c.Checkpoint.Anchor);
                    if (d < Rule.MinTurningPointM) return $"worker {i + 1} is {d:0.00} m from the anchor of checkpoint {c.Node} (< {Rule.MinTurningPointM})";
                    if (Rule.PathClearanceM > 0f)
                        foreach (var s in drive)
                            if (SegmentDistance(pos[i], s.A, s.B) < clr) return $"worker {i + 1} is {SegmentDistance(pos[i], s.A, s.B):0.00} m from {s.Label} (< {Rule.PathClearanceM})";
                    foreach (var q in cpAsks)
                        if (Flat(pos[i] - q) <= Cfg.ask_max_distance_m) return $"worker {i + 1} is {Flat(pos[i] - q):0.00} m from an ask point of checkpoint {c.Node} (<= {Cfg.ask_max_distance_m})";
                }
                foreach (var q in nodeAsks)
                    if (Flat(c.Position - q) <= Cfg.ask_max_distance_m) return $"checkpoint {c.Node} is {Flat(c.Position - q):0.00} m from an ask point of {node.Name} (<= {Cfg.ask_max_distance_m})";
                if (pos.Count > 0)
                {
                    float m = NearerMargin(map, node, c.Position, pos[0]);
                    if (m < Rule.NearerMarginM) return $"checkpoint {c.Node} is only {m:0.00} m farther than {node.Name}'s first worker on the approach (< {Rule.NearerMarginM})";
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

        // ---------------------------------------------------------------- the path clearance (section 15 addendum 1, item 3b)

        /// <summary>A straight piece of the robot's drive (Python's _target: the robot heads for one point at a time).</summary>
        public struct DriveSegment
        {
            public Vector3 A, B;
            public string Label;
        }

        /// <summary>
        /// Item 3b: the segments the robot can drive at one asking node with these workers (in slot order): from the node to the ask position
        /// of each worker in every order (second opinions), including the return to the first worker of an order (the tie rule), and from
        /// every ask position and its re-ask point to the next node of every branch of the node. <paramref name="asks"/>: every modelled ask
        /// position and re-ask point. Roads are not included (Roads()).
        /// </summary>
        public static List<DriveSegment> DrivableSegments(RoadmapV4 map, RoadmapV4.NodeDef node, IList<Vector3> workers, float standoff, float shift,
                                                          out List<Vector3> asks)
        {
            var segs = new List<DriveSegment>();
            asks = new List<Vector3>();
            var c = Pos(node);
            var order = new List<int>();
            for (int i = 0; i < workers.Count; i++) order.Add(i);
            foreach (var perm in Permutations(order))
            {
                var prev = c;
                string from = node.Name;
                for (int k = 0; k <= perm.Count; k++)
                {
                    if (k == perm.Count && perm.Count < 2) break;
                    int i = k < perm.Count ? perm[k] : perm[0];        // after the last: back to the first (tie)
                    var a = AskPosition(workers[i], prev, standoff);
                    segs.Add(new DriveSegment { A = prev, B = a, Label = $"{from} to the ask position of worker {i + 1}{(k == perm.Count ? " (again)" : "")}" });
                    AddPoint(asks, a);
                    AddPoint(asks, ReaskPosition(workers[i], a, standoff, shift));
                    prev = a;
                    from = $"the ask position of worker {i + 1}";
                }
            }
            if (map.Branches.TryGetValue(node.Name, out var branches))
                foreach (var a in asks)
                    foreach (var b in branches)
                        segs.Add(new DriveSegment { A = a, B = Pos(map.Node(b.Value)), Label = $"{node.Name}: ask position ({a.x:0.00}, {a.z:0.00}) to {b.Value} ({b.Key})" });
            return segs;
        }

        /// <summary>Python's re-ask point (hri_control._reposition): <paramref name="shift"/> to the robot's right as it faces the worker,
        /// back onto the standoff circle.</summary>
        public static Vector3 ReaskPosition(Vector3 worker, Vector3 ask, float standoff, float shift)
        {
            if (!(shift > 0f)) return ask;
            var h = new Vector3(worker.x - ask.x, 0f, worker.z - ask.z);
            if (h.sqrMagnitude < 1e-12f) return ask;
            h.Normalize();
            var right = new Vector3(h.z, 0f, -h.x);
            return AskPosition(worker, ask + right * shift, standoff);
        }

        static void AddPoint(List<Vector3> list, Vector3 p)
        {
            foreach (var q in list) if (Flat(q - p) < 1e-3f) return;
            list.Add(p);
        }

        static IEnumerable<List<int>> Permutations(List<int> items)
        {
            if (items.Count <= 1) { yield return new List<int>(items); yield break; }
            for (int i = 0; i < items.Count; i++)
            {
                var rest = new List<int>(items);
                rest.RemoveAt(i);
                foreach (var p in Permutations(rest))
                {
                    p.Insert(0, items[i]);
                    yield return p;
                }
            }
        }

        /// <summary>The first clearance or ask-zone rule the workers of <paramref name="node"/> break with the workers already placed, or null:
        /// every worker (here and placed) keeps PathClearanceM from this node's segments, this node's workers keep it from the roads and from
        /// the segments of every node placed before, and every ask position of this node lies within AskZoneM of it.</summary>
        string ClearanceProblem(RoadmapV4 map, RoadmapV4.NodeDef node, IList<Vector3> pos, IList<PlannedWorker> placed, List<KeyValuePair<Vector3, Vector3>> roads)
        {
            var segs = DrivableSegments(map, node, pos, Rule.StandoffM, Rule.ReaskShiftM, out var asks);
            if (Rule.AskZoneM > 0f)
                foreach (var a in asks)
                    if (Flat(a - Pos(node)) > Rule.AskZoneM + 1e-4f)
                        return $"an ask position ({a.x:0.00}, {a.z:0.00}) is {Flat(a - Pos(node)):0.00} m from {node.Name} (> {Rule.AskZoneM:0.00}, the answer zone minus its margin)";
            if (!(Rule.PathClearanceM > 0f)) return null;
            float clr = Rule.PathClearanceM - 1e-4f;
            for (int i = 0; i < pos.Count; i++)
            {
                foreach (var r in roads)
                    if (SegmentDistance(pos[i], r.Key, r.Value) < clr) return $"worker {i + 1} is {SegmentDistance(pos[i], r.Key, r.Value):0.00} m from a road (< {Rule.PathClearanceM})";
                foreach (var s in segs)
                    if (SegmentDistance(pos[i], s.A, s.B) < clr) return $"worker {i + 1} is {SegmentDistance(pos[i], s.A, s.B):0.00} m from {s.Label} (< {Rule.PathClearanceM})";
            }
            foreach (var q in placed)
                foreach (var s in segs)
                    if (SegmentDistance(q.Position, s.A, s.B) < clr) return $"worker {q.Id} ({q.Node}) is {SegmentDistance(q.Position, s.A, s.B):0.00} m from {s.Label} (< {Rule.PathClearanceM})";
            var nodesBefore = new List<string>();
            foreach (var q in placed) if (q.Checkpoint == null && !nodesBefore.Contains(q.Node)) nodesBefore.Add(q.Node);
            foreach (var name in nodesBefore)
            {
                var theirs = new List<PlannedWorker>();
                foreach (var q in placed) if (q.Checkpoint == null && q.Node == name) theirs.Add(q);
                theirs.Sort((a, b) => a.Slot.CompareTo(b.Slot));
                var wpos = new List<Vector3>();
                foreach (var q in theirs) wpos.Add(q.Position);
                foreach (var s in DrivableSegments(map, map.Node(name), wpos, Rule.StandoffM, Rule.ReaskShiftM, out _))
                    for (int i = 0; i < pos.Count; i++)
                        if (SegmentDistance(pos[i], s.A, s.B) < clr) return $"worker {i + 1} is {SegmentDistance(pos[i], s.A, s.B):0.00} m from {s.Label} (< {Rule.PathClearanceM})";
            }
            return null;
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

        // ---------------------------------------------------------------- checkpoint workers (section 15 addendum 6, variant T4)

        /// <summary>The decision junctions of a map: junctions with two or more branches.</summary>
        public static List<RoadmapV4.NodeDef> DecisionJunctions(RoadmapV4 map)
        {
            var list = new List<RoadmapV4.NodeDef>();
            foreach (var n in map.Nodes)
                if (n.Kind == RoadmapV4.KindJunction && map.Branches.TryGetValue(n.Name, out var bs) && bs.Count >= 2) list.Add(n);
            return list;
        }

        /// <summary>
        /// The checkpoints of a run's map (config order; empty while checkpoints are inactive): each entry must name a branch of a decision
        /// junction of the map, once, inside the branch. Coverage (item 2): every decision branch has a checkpoint or ends at an asking node
        /// (whose honest workers point back); null with the reason otherwise.
        /// </summary>
        public List<CheckpointBranch> Checkpoints(RoadmapV4 map, string mapName, out string error)
        {
            error = null;
            var list = new List<CheckpointBranch>();
            var c = Cfg.checkpoints;
            if (c == null || !c.active) return list;
            var decision = DecisionJunctions(map);
            foreach (var d in c.positions ?? new CheckpointDef[0])
            {
                if (d == null || d.map != mapName) continue;
                if (!decision.Exists(n => n.Name == d.from)) { error = $"checkpoint {d.from} {d.command}: {d.from} is not a decision junction of map {mapName}"; return null; }
                var b = map.Branches[d.from].Find(x => x.Key == d.command);
                if (b.Key == null) { error = $"checkpoint {d.from} {d.command}: no such branch in map {mapName}"; return null; }
                if (list.Exists(x => x.From == d.from && x.Command == d.command)) { error = $"checkpoint {d.from} {d.command}: listed twice"; return null; }
                var a = Pos(map.Node(d.from));
                var e = Pos(map.Node(b.Value));
                if (!(d.s_m > 0f && d.s_m < Flat(e - a))) { error = $"checkpoint {d.from} {d.command}: s_m {d.s_m} is not inside the branch ({Flat(e - a):0.00} m)"; return null; }
                var f = (e - a).normalized;
                var r = Vector3.Cross(Vector3.up, f);
                var anchor = a + f * d.s_m;
                list.Add(new CheckpointBranch { From = d.from, Command = d.command, To = b.Value, S = d.s_m, Right = d.right_m, Anchor = anchor, Position = anchor + r * d.right_m });
            }
            var asking = new HashSet<string>();
            foreach (var n in AskNodes(map)) asking.Add(n.Name);
            foreach (var j in decision)
                foreach (var b in map.Branches[j.Name])
                    if (!list.Exists(x => x.From == j.Name && x.Command == b.Key) && !asking.Contains(b.Value))
                    {
                        error = $"decision branch {j.Name} {b.Key} -> {b.Value} of map {mapName}: no checkpoint and no workers at its end (section 15 addendum 6, item 2)";
                        return null;
                    }
            return list;
        }

        /// <summary>A checkpoint's modelled ask points (from each end of its branch: the ask position at the standoff and its re-ask point) and
        /// its own drive (each end to its ask position; every ask point on to both ends), as addendum 5 item 3c.</summary>
        public static List<DriveSegment> CheckpointDrive(RoadmapV4 map, CheckpointBranch cp, Vector3 worker, float standoff, float shift, out List<Vector3> asks)
        {
            var segs = new List<DriveSegment>();
            asks = new List<Vector3>();
            var ends = new[] { (cp.From, Pos(map.Node(cp.From))), (cp.To, Pos(map.Node(cp.To))) };
            foreach (var (name, x) in ends)
            {
                var a = AskPosition(worker, x, standoff);
                segs.Add(new DriveSegment { A = x, B = a, Label = $"checkpoint {cp.Label}: {name} to its ask position" });
                foreach (var q in new[] { a, ReaskPosition(worker, a, standoff, shift) })
                {
                    AddPoint(asks, q);
                    foreach (var (to, y) in ends)
                        segs.Add(new DriveSegment { A = q, B = y, Label = $"checkpoint {cp.Label}: ask point ({q.x:0.00}, {q.z:0.00}) to {to}" });
                }
            }
            return segs;
        }

        /// <summary>Section 15 addendum 6, item 3: a checkpoint worker answers only while the road of the map nearest to the robot's centre is
        /// its branch (strictly, by more than 0.001 m: silent at a node where roads meet) and the robot's centre is within radius of it.</summary>
        public static bool CheckpointAnswers(RoadmapV4 map, CheckpointBranch cp, Vector3 worker, Vector3 robot, float radius)
        {
            if (Flat(robot - worker) > radius) return false;
            var s = Pos(map.Node(cp.From));
            var e = Pos(map.Node(cp.To));
            float own = SegmentDistance(robot, s, e);
            foreach (var r in Roads(map))
            {
                bool same = (Flat(r.Key - s) < 1e-4f && Flat(r.Value - e) < 1e-4f) || (Flat(r.Key - e) < 1e-4f && Flat(r.Value - s) < 1e-4f);
                if (!same && SegmentDistance(robot, r.Key, r.Value) <= own + 1e-3f) return false;
            }
            return true;
        }

        /// <summary>The world direction a checkpoint worker shows: FORWARD along its branch (PROCEED), BACK toward its junction.</summary>
        public static Vector3 CheckpointDirection(RoadmapV4 map, CheckpointBranch cp, string command)
        {
            var d = Pos(map.Node(cp.To)) - Pos(map.Node(cp.From));
            return (command == Back ? -d : d).normalized;
        }

        /// <summary>The checkpoint's lie: the same per-worker, per-run stream as every worker; a liar shows the opposite (FORWARD and BACK).</summary>
        static void DrawCheckpointLie(PlannedWorker w, int seed, int run, float p)
        {
            var rng = new Rng(seed, run, w.Id, LieSalt);
            w.Liar = rng.NextDouble() < p;
            w.ShownCommand = w.Liar ? (w.TrueCommand == Forward ? Back : Forward) : w.TrueCommand;
            w.ShownIsBranch = true;
        }

        /// <summary>Each checkpoint's own rules once the run's node workers stand (addendum 6 item 4: P1-P10, Q1, Q2), the first broken one or null.</summary>
        string CheckpointProblem(RoadmapV4 map, RunPlanAB plan, Func<Vector3, bool> free)
        {
            if (plan.Checkpoints.Count == 0) return null;
            var turning = new List<Vector3>();
            foreach (var n in AskNodes(map)) turning.Add(Pos(n));
            foreach (var n in AskNodes(Physical)) turning.Add(Pos(n));
            var roads = Roads(map);
            roads.AddRange(Roads(Physical));
            var nodeSegs = new List<DriveSegment>();
            var nodeAsks = new List<Vector3>();
            var names = new List<string>();
            foreach (var q in plan.Workers) if (!names.Contains(q.Node)) names.Add(q.Node);
            foreach (var name in names)
            {
                var theirs = plan.Workers.FindAll(q => q.Node == name);
                theirs.Sort((a, b) => a.Slot.CompareTo(b.Slot));
                nodeSegs.AddRange(DrivableSegments(map, map.Node(name), theirs.ConvertAll(q => q.Position), Rule.StandoffM, Rule.ReaskShiftM, out var a));
                nodeAsks.AddRange(a);
            }
            var everyone = new List<PlannedWorker>(plan.Workers);
            everyone.AddRange(plan.Checkpoints);
            var drives = new Dictionary<int, List<DriveSegment>>();
            var asks = new Dictionary<int, List<Vector3>>();
            foreach (var c in plan.Checkpoints)
            {
                drives[c.Id] = CheckpointDrive(map, c.Checkpoint, c.Position, Rule.StandoffM, Rule.ReaskShiftM, out var a);
                asks[c.Id] = a;
            }
            float clr = Rule.PathClearanceM - 1e-4f;
            foreach (var c in plan.Checkpoints)
            {
                var p = c.Position;
                string me = $"checkpoint {c.Node} at ({p.x:0.00}, {p.z:0.00})";
                foreach (var q in everyone)
                {
                    if (q == c) continue;
                    if (Flat(p - q.Position) < Rule.MinWorkerSeparationM) return $"{me} is {Flat(p - q.Position):0.00} m from worker {q.Id} (< {Rule.MinWorkerSeparationM})";
                    if (Flat(q.Position - c.Checkpoint.Anchor) < Rule.MinTurningPointM) return $"worker {q.Id} is {Flat(q.Position - c.Checkpoint.Anchor):0.00} m from the anchor of {me} (< {Rule.MinTurningPointM})";
                }
                foreach (var t in turning)
                    if (Flat(p - t) < Rule.MinTurningPointM) return $"{me} is {Flat(p - t):0.00} m from an asking node (< {Rule.MinTurningPointM})";
                if (free != null && !free(p)) return $"{me} is on a blocked cell or inside a collider";
                if (Rule.PathClearanceM > 0f)
                {
                    foreach (var r in roads)
                        if (SegmentDistance(p, r.Key, r.Value) < clr) return $"{me} is {SegmentDistance(p, r.Key, r.Value):0.00} m from a road (< {Rule.PathClearanceM})";
                    foreach (var s in nodeSegs)
                        if (SegmentDistance(p, s.A, s.B) < clr) return $"{me} is {SegmentDistance(p, s.A, s.B):0.00} m from {s.Label} (< {Rule.PathClearanceM})";
                    foreach (var o in plan.Checkpoints)
                        if (o != c)
                            foreach (var s in drives[o.Id])
                                if (SegmentDistance(p, s.A, s.B) < clr) return $"{me} is {SegmentDistance(p, s.A, s.B):0.00} m from {s.Label} (< {Rule.PathClearanceM})";
                    foreach (var q in everyone)
                        foreach (var s in drives[c.Id])
                            if (SegmentDistance(q.Position, s.A, s.B) < clr) return $"worker {q.Id} is {SegmentDistance(q.Position, s.A, s.B):0.00} m from {s.Label} (< {Rule.PathClearanceM})";
                }
                foreach (var a in asks[c.Id])
                {
                    if (free != null && !free(a)) return $"{me}: its ask point ({a.x:0.00}, {a.z:0.00}) is on a blocked cell or inside a collider";
                    if (!CheckpointAnswers(map, c.Checkpoint, p, a, Cfg.checkpoints.answer_radius_m)) return $"{me} would not answer at its ask point ({a.x:0.00}, {a.z:0.00})";
                    foreach (var q in everyone)
                        if (q != c && Flat(q.Position - a) <= Cfg.ask_max_distance_m) return $"worker {q.Id} is {Flat(q.Position - a):0.00} m from an ask point of {me} (<= {Cfg.ask_max_distance_m})";
                }
                foreach (var a in nodeAsks)
                    if (Flat(p - a) <= Cfg.ask_max_distance_m) return $"{me} is {Flat(p - a):0.00} m from a node's ask point ({a.x:0.00}, {a.z:0.00}) (<= {Cfg.ask_max_distance_m})";
                RoadmapV4.NodeDef nearest = null;
                foreach (var n in map.Nodes) if (nearest == null || Flat(p - Pos(n)) < Flat(p - Pos(nearest))) nearest = n;
                bool asking = nearest != null && AskNodes(map).Exists(n => n.Name == nearest.Name);
                if (asking && Flat(p - Pos(nearest)) <= Cfg.checkpoints.second_opinion_radius_m)
                    return $"{me} is {Flat(p - Pos(nearest)):0.00} m from {nearest.Name}, its nearest node (<= second_opinion_radius_m {Cfg.checkpoints.second_opinion_radius_m})";
            }
            return null;
        }

        /// <summary>Section 15 addendum 6 (development only): -experimentForceLie NODE:COMMAND. True with node and command null for an empty
        /// spec; false with the reason in a final, or for a spec that is not NODE:COMMAND with COMMAND one of LEFT, FORWARD, RIGHT, BACK.</summary>
        public static bool ParseForceLie(string spec, bool final, out string node, out string command, out string error)
        {
            node = command = error = null;
            if (string.IsNullOrWhiteSpace(spec)) return true;
            if (final) { error = "-experimentForceLie is for development sessions only; a final draws its lies from the seed"; return false; }
            var parts = spec.Trim().Split(':');
            if (parts.Length != 2 || parts[0].Length == 0 || Array.IndexOf(Directions, parts[1]) < 0)
            {
                error = $"-experimentForceLie '{spec}': give NODE:COMMAND, COMMAND one of {string.Join(", ", Directions)} (e.g. J1:RIGHT)";
                return false;
            }
            node = parts[0];
            command = parts[1];
            return true;
        }

        /// <summary>Makes the first worker (slot 1) of an asking node a liar that shows <paramref name="command"/> in this run; the reason
        /// when the node has no workers in the run or the command is its true command, else null.</summary>
        public string ApplyForceLie(RunPlanAB plan, string node, string command)
        {
            var w = plan.Workers.Find(x => x.Node == node && x.Slot == 0);
            if (w == null) return $"-experimentForceLie: {node} is not an asking node of map {plan.MapName}";
            if (w.TrueCommand == command) return $"-experimentForceLie: run {plan.Run} (goal {plan.Goal}): {command} is the true command at {node}";
            var map = plan.MapName != MapName && LeftMap != null ? LeftMap : Map;
            w.Liar = true;
            w.ShownCommand = command;
            w.ShownIsBranch = IsBranch(map, node, command);
            return null;
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

        /// <summary>Section 15 addendum 1, item 3a: a worker answers only while the robot's centre is within <paramref name="radius"/> of the
        /// worker's own node (horizontal); outside it the asked worker shows nothing (NONE).</summary>
        public static bool InAnswerZone(Vector3 robot, Vector3 node, float radius) => Flat(robot - node) <= radius;

        /// <summary>Where Python stands to ask a worker (hri_control dialog.approach_distance_m): <paramref name="standoff"/> from the
        /// worker toward <paramref name="from"/> (the node, or the previous ask position), horizontal.</summary>
        public static Vector3 AskPosition(Vector3 worker, Vector3 from, float standoff)
        {
            var d = new Vector3(from.x - worker.x, 0f, from.z - worker.z);
            if (d.sqrMagnitude < 1e-12f) d = Vector3.right;
            return new Vector3(worker.x, 0f, worker.z) + d.normalized * standoff;
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
