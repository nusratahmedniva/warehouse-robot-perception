using System.Collections.Generic;
using System.IO;
using System.Linq;
using NUnit.Framework;
using UnityEngine;
using WarehouseHRI.V4;

namespace WarehouseHRI.Tests
{
    /// <summary>
    /// Avatar/Config/experiments_ab.md section 15 addendum 6 (variant T4): the checkpoint workers. One worker beside every decision branch that
    /// has a valid spot (addendum 5's positions), the next junction's workers on J1 LEFT -> J2 and J2 FORWARD -> J4; honest PROCEED on the
    /// right branch, POINT back on a wrong one, the set's lie probability per worker per run; they answer only on their branch within 3.5 m;
    /// fixed, with the node workers placed around them under every rule.
    /// </summary>
    public class CheckpointWorkersTests
    {
        static readonly string[] Males = { "sunbox_m_a", "sunbox_m_b" };
        static readonly string[] Females = { "sunbox_f_a", "sunbox_f_b" };
        const int Runs = 20;

        /// <summary>Addendum 6's table: branch, s along it, right of the travel direction, the worker's x and z.</summary>
        static readonly (string from, string cmd, string to, float s, float right, float x, float z)[] Table =
        {
            ("J1", "FORWARD", "E1", 15.5f, -4.0f, 2.25f, 15.50f),
            ("J1", "RIGHT", "J3", 6.0f, 4.0f, 12.25f, -4.00f),
            ("J2", "RIGHT", "E2", 15.5f, -4.0f, -10.25f, 15.50f),
            ("J3", "LEFT", "E3", 15.5f, -4.0f, 14.75f, 15.50f),
            ("J3", "RIGHT", "E4", 14.5f, -4.5f, 23.25f, -14.50f),
            ("J4", "RIGHT", "E5", 14.5f, -4.5f, -23.25f, 14.50f),
            ("J4", "LEFT", "E6", 15.5f, -4.0f, -14.75f, -15.50f),
        };

        static string Repo(string rel) => File.ReadAllText(Path.Combine(Application.dataPath, "../../../..", rel));
        static string Project(string rel) => File.ReadAllText(Path.Combine(Application.dataPath, "..", rel));
        static ExperimentsUnityConfig Cfg() => ExperimentsUnityConfig.Parse(Project("Assets/WarehouseRobot/Scenario/Config/experiments_ab_unity.json"));

        static ExperimentPlanAB Plan(string name, ExperimentsUnityConfig cfg = null, string side = null)
        {
            cfg = cfg ?? Cfg();
            if (side != null) cfg.a2_sides = new[] { side };
            var p = ExperimentPlanAB.Build(cfg, name, Repo(cfg.scenarios_ab), Repo(cfg.roadmap_v4), Project, out string error);
            Assert.IsNotNull(p, error);
            return p;
        }

        static RunPlanAB Run(ExperimentPlanAB p, int seed, int run, string goal)
        {
            var r = p.PlanRun(seed, run, goal, Males, Females, null, out string error);
            Assert.IsNotNull(r, error);
            return r;
        }

        static IEnumerable<(string exp, string side)> Settings()
        {
            foreach (var set in new[] { "A", "B" })
            {
                yield return (set + "1", null);
                yield return (set + "2", "right");
                yield return (set + "2", "left");
                yield return (set + "3", null);
                yield return (set + "4", null);
            }
        }

        [Test]
        public void Config_DeclaresTheCheckpoints_AndCopiesPythonsRadius()
        {
            var cfg = Cfg();
            CollectionAssert.IsEmpty(cfg.Validate());
            Assert.IsTrue(cfg.checkpoints.active);
            Assert.AreEqual(3.5f, cfg.checkpoints.answer_radius_m, 1e-6f);
            var ctl = (Dictionary<string, object>)MiniJson.Parse(Repo("robot_vision/configs/v4/control.json"));
            float so = (float)(double)((Dictionary<string, object>)ctl["lie_detection"])["second_opinion_radius_m"];
            Assert.AreEqual(so, cfg.checkpoints.second_opinion_radius_m, 1e-6f, "a copy of control.json lie_detection.second_opinion_radius_m");
            Assert.AreEqual(Table.Length, cfg.checkpoints.positions.Length);
            for (int i = 0; i < Table.Length; i++)
            {
                var d = cfg.checkpoints.positions[i];
                Assert.AreEqual(("roadmap", Table[i].from, Table[i].cmd), (d.map, d.from, d.command), $"entry {i + 1}");
                Assert.AreEqual(Table[i].s, d.s_m, 1e-6f, $"entry {i + 1} s");
                Assert.AreEqual(Table[i].right, d.right_m, 1e-6f, $"entry {i + 1} right");
            }
        }

        [Test]
        public void Validate_RefusesBadEntries()
        {
            var c = Cfg();
            c.checkpoints.answer_radius_m = 0f;
            Assert.IsTrue(c.Validate().Any(x => x.StartsWith("checkpoints:")));
            c = Cfg();
            c.checkpoints.positions[0].s_m = 0f;
            Assert.IsTrue(c.Validate().Any(x => x.StartsWith("checkpoints:")));
            c = Cfg();
            c.checkpoints.positions[0].command = "";
            Assert.IsTrue(c.Validate().Any(x => x.StartsWith("checkpoints:")));
            c = Cfg();
            c.checkpoints.active = false;
            c.checkpoints.answer_radius_m = 0f;
            CollectionAssert.IsEmpty(c.Validate(), "inactive: not checked");
        }

        [Test]
        public void Positions_AreAddendum5sProposals()
        {
            var p = Plan("A3");
            var cps = p.Checkpoints(p.Map, "roadmap", out string error);
            Assert.IsNull(error);
            Assert.AreEqual(Table.Length, cps.Count);
            for (int i = 0; i < Table.Length; i++)
            {
                var c = cps[i];
                Assert.AreEqual((Table[i].from, Table[i].cmd, Table[i].to), (c.From, c.Command, c.To));
                Assert.Less(ExperimentPlanAB.Flat(c.Position - new Vector3(Table[i].x, 0f, Table[i].z)), 1e-4f, c.Label);
                var a = ExperimentPlanAB.Pos(p.Map.Node(c.From));
                Assert.AreEqual(Table[i].s, ExperimentPlanAB.Flat(c.Anchor - a), 1e-4f, c.Label + ": anchor at s");
                Assert.AreEqual(Mathf.Abs(Table[i].right), ExperimentPlanAB.Flat(c.Position - c.Anchor), 1e-4f, c.Label + ": lateral");
            }
        }

        /// <summary>Item 2: every decision branch of the roadmap has a checkpoint or ends at an asking node; J1 LEFT and J2 FORWARD are the
        /// two without a checkpoint. A missing checkpoint on a branch to an endpoint is refused; maps without a decision junction get none.</summary>
        [Test]
        public void Coverage_EveryDecisionBranch()
        {
            var p = Plan("A3");
            var decision = ExperimentPlanAB.DecisionJunctions(p.Map).Select(n => n.Name).ToList();
            CollectionAssert.AreEqual(new[] { "J1", "J2", "J3", "J4" }, decision);
            var cps = p.Checkpoints(p.Map, "roadmap", out _);
            var asking = ExperimentPlanAB.AskNodes(p.Map).Select(n => n.Name).ToList();
            var byNext = new List<string>();
            foreach (var j in decision)
                foreach (var b in p.Map.Branches[j])
                {
                    bool cp = cps.Any(c => c.From == j && c.Command == b.Key);
                    if (!cp)
                    {
                        Assert.Contains(b.Value, asking, $"{j} {b.Key} -> {b.Value}: covered by the next junction's workers");
                        byNext.Add($"{j} {b.Key} -> {b.Value}");
                    }
                }
            CollectionAssert.AreEquivalent(new[] { "J1 LEFT -> J2", "J2 FORWARD -> J4" }, byNext);
            Assert.AreEqual(9, decision.Sum(j => p.Map.Branches[j].Count));

            var c2 = Cfg();
            c2.checkpoints.positions = c2.checkpoints.positions.Where(d => !(d.from == "J3" && d.command == "LEFT")).ToArray();
            var p2 = Plan("A3", c2);
            Assert.IsNull(p2.Checkpoints(p2.Map, "roadmap", out string why));
            StringAssert.Contains("J3 LEFT -> E3", why);
            Assert.IsNull(p2.PlanRun(1, 1, "E1", Males, Females, null, out why), "a run is refused without full coverage");

            foreach (var (exp, side) in new[] { ("A1", (string)null), ("A2", "right"), ("A2", "left") })
            {
                var q = Plan(exp, null, side);
                var map = q.RunMap(1, 1, out string name);
                CollectionAssert.IsEmpty(ExperimentPlanAB.DecisionJunctions(map), name);
                CollectionAssert.IsEmpty(Run(q, 1, 1, q.Goals(1, 1)[0]).Checkpoints, name + ": no checkpoint");
            }
        }

        /// <summary>Item 1 / 2: an honest worker at a junction the robot reaches on a wrong path points BACK along the arrival road (the
        /// existing TruthfulCommand, unchanged); a liar there shows a valid branch of it.</summary>
        [Test]
        public void NextJunction_PointsBackOnEveryWrongPath()
        {
            var p = Plan("B3");
            var map = p.Map;
            int checkedNodes = 0;
            foreach (var goal in ExperimentPlanAB.Endpoints(map))
                foreach (var j in new[] { "J2", "J3", "J4" })
                {
                    var n = map.Node(j);
                    bool onRoute = map.Branches[j].Any(b => b.Value == goal || ReachesVia(map, b.Value, goal));
                    if (onRoute) continue;
                    Assert.AreEqual(ExperimentPlanAB.Back, ExperimentPlanAB.TruthfulCommand(map, j, goal), $"{j}, goal {goal}");
                    var back = (ExperimentPlanAB.Pos(map.Node(n.ArriveFrom)) - ExperimentPlanAB.Pos(n)).normalized;
                    Assert.Less((ExperimentPlanAB.Direction(map, j, ExperimentPlanAB.Back) - back).magnitude, 1e-4f, $"{j}: toward {n.ArriveFrom}");
                    checkedNodes++;
                }
            Assert.AreEqual(11, checkedNodes, "J2 off-route for E1, E3, E4; J3 for E1, E2, E5, E6; J4 for E1, E2, E3, E4");
            // the planned workers show it too (seed 1, every run), and a liar shows a branch of that junction
            var goals = p.Goals(1, Runs);
            for (int run = 1; run <= Runs; run++)
            {
                var r = Run(p, 1, run, goals[run - 1]);
                foreach (var w in r.Workers.Where(x => x.Node != "A" && x.Node != "J1"))
                {
                    Assert.AreEqual(ExperimentPlanAB.TruthfulCommand(map, w.Node, r.Goal), w.TrueCommand);
                    if (w.TrueCommand == ExperimentPlanAB.Back && w.Liar) Assert.IsTrue(w.ShownIsBranch, $"run {run} worker {w.Id}: a liar shows a branch");
                }
            }
        }

        static bool ReachesVia(RoadmapV4 map, string from, string goal)
        {
            if (from == goal) return true;
            return map.Branches.TryGetValue(from, out var bs) && bs.Any(b => ReachesVia(map, b.Value, goal));
        }

        /// <summary>Item 3: honest PROCEED (FORWARD) on a branch toward the goal, POINT back otherwise; a liar the opposite; ids after the node
        /// workers; looks and gender as declared; the same answer when planned again.</summary>
        [Test]
        public void Commands_LiesAndIds()
        {
            var p = Plan("B3");
            foreach (var goal in ExperimentPlanAB.Endpoints(p.Map))
            {
                var r = Run(p, 1, 3, goal);
                var again = Run(p, 1, 3, goal);
                Assert.AreEqual(Table.Length, r.Checkpoints.Count);
                int maxNode = r.Workers.Max(w => w.Id);
                for (int k = 0; k < r.Checkpoints.Count; k++)
                {
                    var w = r.Checkpoints[k];
                    Assert.AreEqual(maxNode + 1 + k, w.Id, "ids after the node workers, in file order");
                    Assert.AreEqual(k % 2 == 0 ? "male" : "female", w.Gender);
                    var looks = w.Gender == "male" ? Males : Females;
                    Assert.AreEqual(looks[(k / 2 + 3 - 1) % looks.Length], w.Look);
                    bool right = w.Checkpoint.To == goal || ReachesVia(p.Map, w.Checkpoint.To, goal);
                    Assert.AreEqual(right ? ExperimentPlanAB.Forward : ExperimentPlanAB.Back, w.TrueCommand, $"{w.Node}, goal {goal}");
                    string opposite = w.TrueCommand == ExperimentPlanAB.Forward ? ExperimentPlanAB.Back : ExperimentPlanAB.Forward;
                    Assert.AreEqual(w.Liar ? opposite : w.TrueCommand, w.ShownCommand);
                    Assert.IsTrue(w.ShownIsBranch);
                    var o = again.Checkpoints[k];
                    Assert.AreEqual((w.Liar, w.ShownCommand, w.Position), (o.Liar, o.ShownCommand, o.Position), "consistent in the run");
                }
            }
        }

        [Test]
        public void LieRate_IsTheSets()
        {
            int lies = 0, n = 0;
            var b = Plan("B3");
            for (int seed = 1; seed <= 25; seed++)
            {
                var goals = b.Goals(seed, Runs);
                for (int run = 1; run <= Runs; run++)
                    foreach (var w in Run(b, seed, run, goals[run - 1]).Checkpoints) { n++; if (w.Liar) lies++; }
            }
            Assert.AreEqual(25 * Runs * Table.Length, n);
            Assert.That((double)lies / n, Is.InRange(0.17, 0.23), $"{lies} of {n}");
            var a = Plan("A3");
            var ga = a.Goals(1, Runs);
            for (int run = 1; run <= Runs; run++) Assert.IsFalse(Run(a, 1, run, ga[run - 1]).Checkpoints.Any(w => w.Liar), "set A: no liar");
        }

        /// <summary>The node workers of the beside layout keep their places, ids, looks and lies with the checkpoints switched on.</summary>
        [Test]
        public void NodeWorkers_UnchangedInTheBesideLayout()
        {
            var off = Cfg();
            off.checkpoints.active = false;
            foreach (var exp in new[] { "A3", "B3" })
            {
                var pOn = Plan(exp);
                var pOff = Plan(exp, off);
                foreach (int seed in new[] { 1, 2 })
                {
                    var goals = pOn.Goals(seed, Runs);
                    for (int run = 1; run <= Runs; run++)
                    {
                        var on = Run(pOn, seed, run, goals[run - 1]);
                        var o = Run(pOff, seed, run, goals[run - 1]);
                        CollectionAssert.IsEmpty(o.Checkpoints);
                        Assert.AreEqual(o.Workers.Count, on.Workers.Count);
                        for (int i = 0; i < on.Workers.Count; i++)
                            Assert.AreEqual((o.Workers[i].Id, o.Workers[i].Node, o.Workers[i].Position, o.Workers[i].Look, o.Workers[i].Liar, o.Workers[i].ShownCommand),
                                            (on.Workers[i].Id, on.Workers[i].Node, on.Workers[i].Position, on.Workers[i].Look, on.Workers[i].Liar, on.Workers[i].ShownCommand),
                                            $"{exp} seed {seed} run {run} worker {i + 1}");
                    }
                }
            }
        }

        [Test]
        public void Direction_ForwardAlongTheBranch_BackTowardItsJunction()
        {
            var p = Plan("B3");
            foreach (var c in p.Checkpoints(p.Map, "roadmap", out _))
            {
                var along = (ExperimentPlanAB.Pos(p.Map.Node(c.To)) - ExperimentPlanAB.Pos(p.Map.Node(c.From))).normalized;
                Assert.Less((ExperimentPlanAB.CheckpointDirection(p.Map, c, ExperimentPlanAB.Forward) - along).magnitude, 1e-5f, c.Label);
                Assert.Less((ExperimentPlanAB.CheckpointDirection(p.Map, c, ExperimentPlanAB.Back) + along).magnitude, 1e-5f, c.Label);
            }
        }

        /// <summary>Item 3: a checkpoint answers at each of its modelled ask points; not at a node where roads meet, not on another road,
        /// not beyond the answer radius.</summary>
        [Test]
        public void AnswerRule_OnItsBranchWithinTheRadius()
        {
            var cfg = Cfg();
            var p = Plan("B3", cfg);
            float radius = cfg.checkpoints.answer_radius_m;
            foreach (var c in p.Checkpoints(p.Map, "roadmap", out _))
            {
                ExperimentPlanAB.CheckpointDrive(p.Map, c, c.Position, cfg.ask_standoff_m, cfg.reask_shift_m, out var asks);
                Assert.AreEqual(4, asks.Count, c.Label + ": ask and re-ask point from each end");
                foreach (var a in asks) Assert.IsTrue(ExperimentPlanAB.CheckpointAnswers(p.Map, c, c.Position, a, radius), $"{c.Label} at its ask point {a}");
                var j = ExperimentPlanAB.Pos(p.Map.Node(c.From));
                Assert.IsFalse(ExperimentPlanAB.CheckpointAnswers(p.Map, c, c.Position, j, 1e6f), c.Label + ": silent at its junction (roads meet)");
                var toward = c.Position + (c.Anchor - c.Position).normalized * (radius + 0.1f);
                Assert.IsFalse(ExperimentPlanAB.CheckpointAnswers(p.Map, c, c.Position, toward, radius), c.Label + ": silent beyond the radius");
            }
            // on another road: the J1 -> E1 checkpoint seen from the A -> J1 road at the same distance
            var e1 = p.Checkpoints(p.Map, "roadmap", out _).Single(c => c.Command == "FORWARD" && c.From == "J1");
            Assert.IsFalse(ExperimentPlanAB.CheckpointAnswers(p.Map, e1, e1.Position, new Vector3(6.25f, 0f, -2.0f), 1e6f), "the robot on A -> J1");
        }

        /// <summary>Items 4 and 5: every run of seeds 1 and 2 of every Unity setting is planned with the checkpoints, and the rules hold again
        /// when re-checked here independently; at most 6 active avatars; the random layouts' redraws are logged.</summary>
        [Test]
        public void EveryRun_IsPlanned_AndEveryCheckpointRuleHolds()
        {
            var cfg = Cfg();
            var summary = new List<string>();
            foreach (var (exp, side) in Settings())
            {
                var p = Plan(exp, Cfg(), side);
                int maxActive = 0, redraws = 0, cps = 0;
                foreach (int seed in new[] { 1, 2 })
                {
                    var goals = p.Goals(seed, Runs);
                    for (int run = 1; run <= Runs; run++)
                    {
                        var r = Run(p, seed, run, goals[run - 1]);
                        var map = p.RunMap(seed, run, out string mapName);
                        string what = $"{exp}{(side != null ? "_" + side : "")} seed {seed} run {run}";
                        Assert.AreEqual(mapName == "roadmap" ? Table.Length : 0, r.Checkpoints.Count, what);
                        var all = r.Workers.Concat(r.Checkpoints).ToList();
                        Assert.AreEqual(ExperimentPlanAB.MaxActive(map, all, cfg.activation_radius_m, cfg.activation_sample_step_m), r.MaxActive, what + ": MaxActive counts every worker");
                        Assert.LessOrEqual(r.MaxActive, cfg.max_active_avatars, what);
                        maxActive = Mathf.Max(maxActive, r.MaxActive);
                        redraws += r.Redraws.Values.Sum();
                        cps += r.Checkpoints.Count;
                        RecheckCheckpoints(cfg, p, map, r, what);
                    }
                }
                summary.Add($"{exp}{(side != null ? "_" + side : "")}: checkpoints {cps}, max active {maxActive}, redraws {redraws}");
            }
            Debug.Log("[CheckpointWorkersTests] " + string.Join("; ", summary));
        }

        static void RecheckCheckpoints(ExperimentsUnityConfig cfg, ExperimentPlanAB p, RoadmapV4 map, RunPlanAB r, string what)
        {
            if (r.Checkpoints.Count == 0) return;
            var all = r.Workers.Concat(r.Checkpoints).ToList();
            var roads = ExperimentPlanAB.Roads(map).Concat(ExperimentPlanAB.Roads(p.Physical)).ToList();
            var nodeSegs = new List<ExperimentPlanAB.DriveSegment>();
            var nodeAsks = new List<Vector3>();
            foreach (var g in r.Workers.GroupBy(w => w.Node))
            {
                nodeSegs.AddRange(ExperimentPlanAB.DrivableSegments(map, map.Node(g.Key), g.OrderBy(w => w.Slot).Select(w => w.Position).ToList(),
                                                                   cfg.ask_standoff_m, cfg.reask_shift_m, out var a));
                nodeAsks.AddRange(a);
            }
            var drive = r.Checkpoints.ToDictionary(c => c.Id, c => ExperimentPlanAB.CheckpointDrive(map, c.Checkpoint, c.Position, cfg.ask_standoff_m, cfg.reask_shift_m, out _));
            var cpAsks = r.Checkpoints.ToDictionary(c => c.Id, c => { ExperimentPlanAB.CheckpointDrive(map, c.Checkpoint, c.Position, cfg.ask_standoff_m, cfg.reask_shift_m, out var a); return a; });
            var turning = ExperimentPlanAB.AskNodes(map).Concat(ExperimentPlanAB.AskNodes(p.Physical)).Select(ExperimentPlanAB.Pos).ToList();
            const float eps = 1e-4f;
            foreach (var c in r.Checkpoints)
            {
                string me = $"{what}: checkpoint {c.Node}";
                foreach (var q in all.Where(q => q != c)) Assert.GreaterOrEqual(ExperimentPlanAB.Flat(c.Position - q.Position), 3f - eps, $"{me} and worker {q.Id}: separation");
                foreach (var t in turning) Assert.GreaterOrEqual(ExperimentPlanAB.Flat(c.Position - t), 3f - eps, $"{me}: turning point");
                foreach (var q in all.Where(q => q != c)) Assert.GreaterOrEqual(ExperimentPlanAB.Flat(q.Position - c.Checkpoint.Anchor), 3f - eps, $"{me}: worker {q.Id} near its anchor");
                foreach (var s in roads) Assert.GreaterOrEqual(ExperimentPlanAB.SegmentDistance(c.Position, s.Key, s.Value), 1f - eps, $"{me}: road");
                foreach (var s in nodeSegs) Assert.GreaterOrEqual(ExperimentPlanAB.SegmentDistance(c.Position, s.A, s.B), 1f - eps, $"{me}: {s.Label}");
                foreach (var o in r.Checkpoints.Where(o => o != c))
                    foreach (var s in drive[o.Id]) Assert.GreaterOrEqual(ExperimentPlanAB.SegmentDistance(c.Position, s.A, s.B), 1f - eps, $"{me}: drive of {o.Node}");
                foreach (var q in all)
                    foreach (var s in drive[c.Id]) Assert.GreaterOrEqual(ExperimentPlanAB.SegmentDistance(q.Position, s.A, s.B), 1f - eps, $"{me}: worker {q.Id} on its own drive ({s.Label})");
                foreach (var a in cpAsks[c.Id])
                {
                    Assert.IsTrue(ExperimentPlanAB.CheckpointAnswers(map, c.Checkpoint, c.Position, a, cfg.checkpoints.answer_radius_m), $"{me}: answers at its ask point");
                    foreach (var q in all.Where(q => q != c)) Assert.Greater(ExperimentPlanAB.Flat(q.Position - a), cfg.ask_max_distance_m, $"{me}: worker {q.Id} could answer its ask");
                }
                foreach (var a in nodeAsks) Assert.Greater(ExperimentPlanAB.Flat(c.Position - a), cfg.ask_max_distance_m, $"{me}: could answer a node ask");
                var nearest = map.Nodes.OrderBy(n => ExperimentPlanAB.Flat(c.Position - ExperimentPlanAB.Pos(n))).First();
                if (ExperimentPlanAB.AskNodes(map).Any(n => n.Name == nearest.Name))
                    Assert.Greater(ExperimentPlanAB.Flat(c.Position - ExperimentPlanAB.Pos(nearest)), cfg.checkpoints.second_opinion_radius_m, $"{me}: inside {nearest.Name}'s second-opinion radius");
                foreach (var g in r.Workers.GroupBy(w => w.Node))
                {
                    var first = g.Single(w => w.Slot == 0);
                    Assert.GreaterOrEqual(p.NearerMargin(map, map.Node(g.Key), c.Position, first.Position), p.Rule.NearerMarginM - eps, $"{me}: nearer than {g.Key}'s first worker");
                }
            }
        }

        /// <summary>The development-only option -experimentForceLie NODE:COMMAND.</summary>
        [Test]
        public void ForceLie_DevelopmentOnly()
        {
            Assert.IsTrue(ExperimentPlanAB.ParseForceLie("", false, out string node, out string cmd, out string error));
            Assert.IsNull(node);
            Assert.IsNull(error);
            Assert.IsTrue(ExperimentPlanAB.ParseForceLie("J1:RIGHT", false, out node, out cmd, out error));
            Assert.AreEqual(("J1", "RIGHT"), (node, cmd));
            Assert.IsFalse(ExperimentPlanAB.ParseForceLie("J1:RIGHT", true, out _, out _, out error));
            StringAssert.Contains("development", error);
            Assert.IsFalse(ExperimentPlanAB.ParseForceLie("J1-RIGHT", false, out _, out _, out error));
            Assert.IsFalse(ExperimentPlanAB.ParseForceLie("J1:UP", false, out _, out _, out error));

            var p = Plan("B3");
            var r = Run(p, 1, 1, "E1");
            Assert.IsNull(p.ApplyForceLie(r, "J1", "RIGHT"));
            var w = r.Workers.Single(x => x.Node == "J1" && x.Slot == 0);
            Assert.AreEqual((true, "RIGHT", "FORWARD", true), (w.Liar, w.ShownCommand, w.TrueCommand, w.ShownIsBranch));
            StringAssert.Contains("true command", p.ApplyForceLie(Run(p, 1, 1, "E1"), "J1", "FORWARD"));
            StringAssert.Contains("not an asking node", p.ApplyForceLie(Run(p, 1, 1, "E1"), "E1", "LEFT"));
        }
    }
}
