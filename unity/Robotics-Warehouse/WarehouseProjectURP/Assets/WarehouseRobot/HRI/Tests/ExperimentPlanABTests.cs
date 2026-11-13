using System;
using System.Collections.Generic;
using System.IO;
using System.Linq;
using NUnit.Framework;
using UnityEngine;
using WarehouseHRI.V4;

namespace WarehouseHRI.Tests
{
    /// <summary>
    /// Experiments A and B (Avatar/Config/experiments_ab.md sections 3 and 4): ExperimentPlanAB on the real config and map files
    /// (Scenario/Config/experiments_ab_unity.json, Anisha's configs/v4/experiments/scenarios_ab.json and configs/v4/roadmap.json, the
    /// turn_left proposal): every placement rule on every run, the truthful and lying directions, the lie seeding, rate and consistency,
    /// the look rotation and the activation limit.
    /// </summary>
    public class ExperimentPlanABTests
    {
        static readonly string[] Males = { "sunbox_m_a", "sunbox_m_b" };
        static readonly string[] Females = { "sunbox_f_a", "sunbox_f_b" };
        static readonly string[] Names = { "A1", "A2", "A3", "A4", "B1", "B2", "B3", "B4" };

        static string Repo(string rel) => File.ReadAllText(Path.Combine(Application.dataPath, "../../../..", rel));
        static string Project(string rel) => File.ReadAllText(Path.Combine(Application.dataPath, "..", rel));
        static ExperimentsUnityConfig Cfg() => ExperimentsUnityConfig.Parse(Project("Assets/WarehouseRobot/Scenario/Config/experiments_ab_unity.json"));

        static ExperimentPlanAB Plan(string name, ExperimentsUnityConfig cfg = null)
        {
            cfg = cfg ?? Cfg();
            var p = ExperimentPlanAB.Build(cfg, name, Repo(cfg.scenarios_ab), Repo(cfg.roadmap_v4), Project, out string error);
            Assert.IsNotNull(p, error);
            return p;
        }

        static RunPlanAB Run(ExperimentPlanAB p, int seed, int run, string goal = null)
        {
            goal = goal ?? p.Goals(seed, run)[run - 1];
            var r = p.PlanRun(seed, run, goal, Males, Females, null, out string error);
            Assert.IsNotNull(r, error);
            return r;
        }

        [Test]
        public void Config_IsValidAndEveryExperimentBuildsFromTheRealFiles()
        {
            var cfg = Cfg();
            CollectionAssert.IsEmpty(cfg.Validate());
            CollectionAssert.AreEquivalent(Names, cfg.experiments.Select(e => e.name));
            foreach (var n in Names)
            {
                var p = Plan(n, cfg);
                Assert.AreEqual(n[0] == 'A' ? 0f : 0.2f, p.LieProbability, 1e-6f, n + ": the set's lie_probability of scenarios_ab.json");
                CollectionAssert.IsEmpty(p.Map.LabelProblems(), n + ": branch labels match the geometry");
                Assert.AreEqual(3f, p.Rule.MinWorkerSeparationM, 1e-6f);
                Assert.AreEqual(3f, p.Rule.MinTurningPointM, 1e-6f);
            }
            Assert.AreEqual("corridor", Plan("A1").MapName);
            Assert.AreEqual("turn", Plan("A2").MapName);
            Assert.AreEqual("roadmap", Plan("A3").MapName);
            Assert.AreEqual("random", Plan("A4").LayoutKind);
            Assert.AreEqual(1f, Plan("A3").Rule.NearerMarginM, 1e-6f, "beside: the bystander margin of trial_workers_v4.json");
            Assert.AreEqual(0.25f, Plan("A4").Rule.NearerMarginM, 1e-6f, "random: the declared default (experiments_ab.md section 3)");
        }

        [Test]
        public void EveryRun_ObeysEveryPlacementRule_AndTheActiveAvatarLimit()
        {
            foreach (var n in Names)
            {
                var p = Plan(n);
                for (int run = 1; run <= 20; run++)
                {
                    var r = Run(p, 1, run);
                    var map = p.RunMap(1, run, out _);
                    var w = r.Workers;
                    for (int i = 0; i < w.Count; i++)
                        for (int j = i + 1; j < w.Count; j++)
                            Assert.GreaterOrEqual(ExperimentPlanAB.Flat(w[i].Position - w[j].Position), 3f - 1e-4f, $"{n} run {run}: workers {w[i].Id} and {w[j].Id}");
                    var turning = ExperimentPlanAB.AskNodes(map).Concat(ExperimentPlanAB.AskNodes(p.Physical));
                    foreach (var x in w)
                        foreach (var t in turning)
                            Assert.GreaterOrEqual(ExperimentPlanAB.Flat(x.Position - ExperimentPlanAB.Pos(t)), 3f - 1e-4f, $"{n} run {run}: worker {x.Id} and {t.Name}");
                    foreach (var g in w.GroupBy(x => x.Node))
                    {
                        var node = map.Node(g.Key);
                        var first = g.Single(x => x.Slot == 0);
                        foreach (var x in g.Where(x => x.Slot > 0))
                            Assert.GreaterOrEqual(p.NearerMargin(map, node, x.Position, first.Position), p.Rule.NearerMarginM - 1e-4f, $"{n} run {run}: bystander rule at {g.Key}");
                        Assert.AreEqual(p.WorkersAt(g.Key), g.Count(), $"{n}: workers at {g.Key}");
                    }
                    if (p.LayoutKind == "random")
                        foreach (var x in w)
                            foreach (var road in ExperimentPlanAB.Roads(map).Concat(ExperimentPlanAB.Roads(p.Physical)))
                                Assert.GreaterOrEqual(ExperimentPlanAB.SegmentDistance(x.Position, road.Key, road.Value), 1f - 1e-4f, $"{n} run {run}: road clearance");
                    Assert.LessOrEqual(r.MaxActive, 6, $"{n} run {run}: active avatars");
                    CollectionAssert.AreEquivalent(ExperimentPlanAB.AskNodes(map).Select(x => x.Name), r.Redraws.Keys, "redraws logged per node");
                }
            }
        }

        [Test]
        public void Beside_UsesTheDeclaredSlots_ThreeAtJ1InA3AndB3()
        {
            var a1 = Run(Plan("A1"), 1, 1);
            Assert.AreEqual(2, a1.Workers.Count);
            Assert.AreEqual(new Vector3(4.25f, 0f, -23f), a1.Workers[0].Position);
            Assert.AreEqual(new Vector3(10.25f, 0f, -23f), a1.Workers[1].Position);
            var a3 = Run(Plan("A3"), 1, 1);
            Assert.AreEqual(11, a3.Workers.Count, "2 at A, J2, J3, J4 and 3 at J1");
            var j1 = a3.Workers.Where(x => x.Node == "J1").OrderBy(x => x.Slot).Select(x => x.Position).ToList();
            Assert.AreEqual(new Vector3(4.25f, 0f, -3f), j1[0]);
            Assert.AreEqual(new Vector3(8.25f, 0f, -5.5f), j1[1]);
            Assert.AreEqual(new Vector3(4.25f, 0f, -6f), j1[2]);
            var j2 = a3.Workers.Where(x => x.Node == "J2").OrderBy(x => x.Slot).Select(x => x.Position).ToList();
            Assert.AreEqual(-3.25f, j2[0].x, 1e-4f, "J2 is reached heading west: slot 1 is 3 m east of it, 2 m to the robot's left (south)");
            Assert.AreEqual(-2f, j2[0].z, 1e-4f);
            CollectionAssert.AreEqual(Enumerable.Range(1, 11), a3.Workers.Select(x => x.Id));
            Assert.IsTrue(a3.Redraws.Values.All(v => v == 0), "beside: no draws");
        }

        [Test]
        public void Random_IsSeeded_AndLogsRedraws()
        {
            var p = Plan("A4");
            var a = Run(p, 1, 3);
            var b = Run(p, 1, 3);
            CollectionAssert.AreEqual(a.Workers.Select(x => x.Position), b.Workers.Select(x => x.Position), "the same seed and run give the same placement");
            var c = Run(p, 1, 4, a.Goal);
            Assert.AreNotEqual(a.Workers[0].Position, c.Workers[0].Position, "another run draws another placement");
            Assert.Greater(a.Redraws.Values.Sum(), 0, "a 6 m square under these rules needs redraws, and they are counted");
            foreach (var x in a.Workers)
            {
                var node = ExperimentPlanAB.Pos(p.Map.Node(x.Node));
                Assert.LessOrEqual(Mathf.Abs(x.Position.x - node.x), 3f + 1e-4f);
                Assert.LessOrEqual(Mathf.Abs(x.Position.z - node.z), 3f + 1e-4f);
            }
        }

        [Test]
        public void TruthfulCommand_IsTheBranchTowardB_OrBackWhereNoneLeads()
        {
            var map = Plan("A3").Map;
            Assert.AreEqual("FORWARD", ExperimentPlanAB.TruthfulCommand(map, "A", "E1"));
            Assert.AreEqual("FORWARD", ExperimentPlanAB.TruthfulCommand(map, "J1", "E1"));
            Assert.AreEqual("BACK", ExperimentPlanAB.TruthfulCommand(map, "J2", "E1"), "J2 cannot lead to E1 (AUDIT.md 16.11 item 4)");
            Assert.AreEqual("LEFT", ExperimentPlanAB.TruthfulCommand(map, "J1", "E5"));
            Assert.AreEqual("FORWARD", ExperimentPlanAB.TruthfulCommand(map, "J2", "E5"));
            Assert.AreEqual("RIGHT", ExperimentPlanAB.TruthfulCommand(map, "J4", "E5"));
            Assert.AreEqual("RIGHT", ExperimentPlanAB.TruthfulCommand(map, "J3", "E4"));
            var turn = Plan("A2").Map;
            Assert.AreEqual("RIGHT", ExperimentPlanAB.TruthfulCommand(turn, "B", "C"));
            Assert.AreEqual("FORWARD", ExperimentPlanAB.TruthfulCommand(Plan("A1").Map, "A", "B"));
        }

        [Test]
        public void Direction_BranchesPointToTheirNextNode_OtherCommandsTurnTheArrivalHeading()
        {
            var map = Plan("A3").Map;
            AssertDir(new Vector3(-1f, 0f, 0f), ExperimentPlanAB.Direction(map, "J1", "LEFT"));
            AssertDir(new Vector3(0f, 0f, 1f), ExperimentPlanAB.Direction(map, "J1", "FORWARD"));
            AssertDir(new Vector3(0f, 0f, -1f), ExperimentPlanAB.Direction(map, "J1", "BACK"), "BACK = the arrival road");
            AssertDir(new Vector3(1f, 0f, 0f), ExperimentPlanAB.Direction(map, "A", "RIGHT"), "no RIGHT branch at A: the start heading turned right");
            AssertDir(new Vector3(-1f, 0f, 0f), ExperimentPlanAB.Direction(map, "J3", "BACK"), "J3 is reached heading east: BACK is west");
            AssertDir(new Vector3(0f, 0f, 1f), ExperimentPlanAB.Direction(map, "J3", "LEFT"), "J3 LEFT is its branch to E3 (north)");
        }

        static void AssertDir(Vector3 expected, Vector3 actual, string what = "") => Assert.Less(Vector3.Angle(expected, actual), 0.01f, what);

        [Test]
        public void Looks_MaleFirstFemaleNext_DifferWithinANodeAndBetweenNeighbours()
        {
            var r = Run(Plan("A3"), 1, 2);
            foreach (var g in r.Workers.GroupBy(x => x.Node))
            {
                var ws = g.OrderBy(x => x.Slot).ToList();
                Assert.AreEqual("male", ws[0].Gender);
                Assert.AreEqual("female", ws[1].Gender);
                Assert.AreEqual(ws.Count, ws.Select(x => x.Look).Distinct().Count(), "no two workers of a node wear the same look");
            }
            string first(string node) => r.Workers.Single(x => x.Node == node && x.Slot == 0).Look;
            Assert.AreNotEqual(first("A"), first("J1"), "neighbouring nodes differ");
            Assert.AreNotEqual(first("J1"), first("J2"));
            Assert.IsTrue(r.Workers.All(x => (x.Gender == "male" ? Males : Females).Contains(x.Look)), "only the given development looks");
        }

        [Test]
        public void Goals_FixedForA1A2_FromTheGoalSequenceForA3A4()
        {
            CollectionAssert.AreEqual(Enumerable.Repeat("B", 3), Plan("A1").Goals(1, 3));
            CollectionAssert.AreEqual(Enumerable.Repeat("C", 3), Plan("A2").Goals(1, 3));
            var eps = new List<string> { "E1", "E2", "E3", "E4", "E5", "E6" };
            var g = new GoalSequence(1);
            var expected = Enumerable.Range(0, 5).Select(_ => eps[g.NextGoalIndex(eps.Count)]).ToList();
            CollectionAssert.AreEqual(expected, Plan("A3").Goals(1, 5));
        }

        [Test]
        public void ChooseAsked_TheWorkerNearestTheCameraAxisWithinRange()
        {
            var heads = new List<KeyValuePair<int, Vector3>>
            {
                new KeyValuePair<int, Vector3>(1, new Vector3(2f, 1.6f, 0.3f)),
                new KeyValuePair<int, Vector3>(2, new Vector3(1.5f, 1.6f, 2.5f)),
                new KeyValuePair<int, Vector3>(3, new Vector3(8f, 1.6f, 0f)),
            };
            Assert.AreEqual(1, ExperimentPlanAB.ChooseAsked(Vector3.zero, Vector3.right, heads, 3.5f));
            Assert.AreEqual(2, ExperimentPlanAB.ChooseAsked(Vector3.zero, new Vector3(1f, 0f, 1.5f), heads, 3.5f));
            Assert.AreEqual(-1, ExperimentPlanAB.ChooseAsked(new Vector3(0f, 0f, -20f), Vector3.right, heads, 3.5f), "nobody close: nobody answers");
        }

        [Test]
        public void TurnLeftProposal_IsTheMirrorOfAnishasTurnMap()
        {
            var cfg = Cfg();
            var turn = Plan("A2", cfg).Map;
            var left = RoadmapV4.Parse(Project(cfg.proposals.Single(x => x.name == "turn_left").file));
            CollectionAssert.IsEmpty(left.LabelProblems());
            Assert.AreEqual(turn.Start, left.Start);
            foreach (var n in turn.Nodes)
            {
                var m = left.Node(n.Name);
                Assert.IsNotNull(m, n.Name);
                Assert.AreEqual(n.Kind, m.Kind, n.Name);
                Assert.AreEqual(n.Z, m.Z, 1e-4f, n.Name);
                Assert.AreEqual(6.25f - (n.X - 6.25f), m.X, 1e-4f, n.Name + ": mirrored about the corridor x = 6.25");
            }
            Assert.AreEqual("LEFT", left.Branches["B"].Single().Key);
            Assert.AreEqual("RIGHT", turn.Branches["B"].Single().Key);
            var both = Cfg();
            both.a2_sides = new[] { "right", "left" };
            var p = Plan("A2", both);
            var sides = Enumerable.Range(1, 40).Select(run => { p.RunMap(1, run, out var name); return name; }).Distinct().ToList();
            CollectionAssert.AreEquivalent(new[] { "turn", "turn_left" }, sides, "both listed: drawn per run");
            var r = p.PlanRun(1, sides.Count > 0 ? Enumerable.Range(1, 40).First(run => { p.RunMap(1, run, out var nm); return nm == "turn_left"; }) : 1, "C", Males, Females, null, out string error);
            Assert.IsNotNull(r, error);
            Assert.AreEqual("LEFT", r.Workers.Single(x => x.Node == "B" && x.Slot == 0).TrueCommand);
        }

        [Test]
        public void ExperimentMaps_LieInsideTheWarehouseAndOnItsAisles()
        {
            // Every node of the experiment maps lies inside the walls (+-26 m) and on an aisle line of the v4 map (x or z of one of its
            // nodes); Unity also refuses at Play any node or worker on a blocked cell of the ground-truth grid (TrialRunnerV4).
            var cfg = Cfg();
            var phys = Plan("A3", cfg).Physical;
            var xs = phys.Nodes.Select(n => n.X).Distinct().ToList();
            var zs = phys.Nodes.Select(n => n.Z).Distinct().ToList();
            var maps = new List<RoadmapV4> { Plan("A1", cfg).Map, Plan("A2", cfg).Map, RoadmapV4.Parse(Project(cfg.proposals[0].file)) };
            foreach (var m in maps)
                foreach (var n in m.Nodes)
                {
                    Assert.Less(Mathf.Abs(n.X), 26.5f, n.Name);
                    Assert.Less(Mathf.Abs(n.Z), 26.5f, n.Name);
                    Assert.IsTrue(xs.Any(x => Mathf.Abs(x - n.X) < 1e-4f) || zs.Any(z => Mathf.Abs(z - n.Z) < 1e-4f), n.Name + " on an aisle line");
                }
        }
    }
}
