using System.Collections.Generic;
using System.IO;
using System.Linq;
using NUnit.Framework;
using UnityEngine;
using WarehouseHRI.V4;

namespace WarehouseHRI.Tests
{
    /// <summary>
    /// Avatar/Config/experiments_ab.md section 15 addendum 1, item 3b: no worker within path_clearance_m (1.0 m) of a segment the robot can
    /// drive, and every modelled ask position inside its node's answer zone minus the margin. The layout that meets it (corner slots, two
    /// workers at J1 in A4 and B4) is PENDING in experiments_ab_unity.json clearance_layout (active false) until Anisha's scenarios_ab.json
    /// carries it; these tests apply it with WithClearanceLayout() and plan every run of seed 1 and seed 2 of every setting.
    /// </summary>
    public class ExperimentClearanceTests
    {
        static readonly string[] Males = { "sunbox_m_a", "sunbox_m_b" };
        static readonly string[] Females = { "sunbox_f_a", "sunbox_f_b" };
        const int Runs = 20;

        static string Repo(string rel) => File.ReadAllText(Path.Combine(Application.dataPath, "../../../..", rel));
        static string Project(string rel) => File.ReadAllText(Path.Combine(Application.dataPath, "..", rel));
        static ExperimentsUnityConfig Cfg() => ExperimentsUnityConfig.Parse(Project("Assets/WarehouseRobot/Scenario/Config/experiments_ab_unity.json"));

        static ExperimentPlanAB Plan(string name, ExperimentsUnityConfig cfg)
        {
            var p = ExperimentPlanAB.Build(cfg, name, Repo(cfg.scenarios_ab), Repo(cfg.roadmap_v4), Project, out string error);
            Assert.IsNotNull(p, error);
            return p;
        }

        /// <summary>Every Unity setting of the final matrix (the _off settings plan exactly as their on twins).</summary>
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
        public void Config_DeclaresTheRuleAndKeepsTheLayoutPending()
        {
            var cfg = Cfg();
            CollectionAssert.IsEmpty(cfg.Validate());
            Assert.AreEqual(1.0f, cfg.path_clearance_m, 1e-6f);
            Assert.AreEqual(0.5f, cfg.answer_zone_margin_m, 1e-6f);
            Assert.AreEqual(2.0f, cfg.ask_standoff_m, 1e-6f, "Python's dialog.approach_distance_m");
            Assert.AreEqual(0.4f, cfg.reask_shift_m, 1e-6f, "Python's dialog.reask_shift_m");
            Assert.IsFalse(cfg.clearance_layout.active, "PENDING: Anisha's scenarios_ab.json still has the section 3 slots (her MatchesUnity test)");
            var s = cfg.clearance_layout.junction_slots;
            Assert.AreEqual(new[] { 3.5f, 2.5f, -4.5f, 3.5f, -5.0f, -4.0f }, new[] { s[0].before_m, -s[0].right_m, s[1].before_m, s[1].right_m, s[2].before_m, s[2].right_m });
            CollectionAssert.AreEquivalent(new[] { "A4", "B4" }, cfg.clearance_layout.two_worker_experiments);
            var on = cfg.WithClearanceLayout();
            Assert.IsTrue(on.clearance_layout.active);
            Assert.AreSame(on.junction_slots, on.clearance_layout.junction_slots);
            CollectionAssert.IsEmpty(on.Experiment("A4").three_worker_nodes);
            CollectionAssert.AreEqual(new[] { "J1" }, on.Experiment("A3").three_worker_nodes, "A3 and B3 keep 3 at J1 (slot 3)");
            CollectionAssert.AreEqual(new[] { "J1" }, cfg.Experiment("A4").three_worker_nodes, "the live config is not changed");
            Assert.AreEqual(0f, Plan("A3", cfg).Rule.PathClearanceM, "inactive: no clearance check at Play");
            Assert.AreEqual(1f, Plan("A3", on).Rule.PathClearanceM, 1e-6f);
            Assert.AreEqual(5.5f, Plan("A3", on).Rule.AskZoneM, 1e-6f, "6.0 m zone minus 0.5 m");
        }

        [Test]
        public void PendingLayout_EverySeed1AndSeed2Plan_OfEverySetting_KeepsEveryRule()
        {
            int plans = 0;
            foreach (var (exp, side) in Settings())
            {
                var cfg = Cfg().WithClearanceLayout();
                if (side != null) cfg.a2_sides = new[] { side };
                var p = Plan(exp, cfg);
                foreach (int seed in new[] { 1, 2 })
                {
                    var goals = p.Goals(seed, Runs);
                    for (int run = 1; run <= Runs; run++)
                    {
                        string what = $"{exp}{(side != null ? "_" + side : "")} seed {seed} run {run}";
                        var r = p.PlanRun(seed, run, goals[run - 1], Males, Females, null, out string error);
                        Assert.IsNotNull(r, $"{what}: {error}");
                        plans++;
                        var map = p.RunMap(seed, run, out string mapName);
                        if (side != null) Assert.AreEqual(side == "left" ? "turn_left" : "turn", mapName, what);
                        CheckEveryRule(p, map, r, what);
                        if (exp.EndsWith("4")) Assert.AreEqual(2, r.Workers.Count(x => x.Node == "J1"), what + ": two at J1");
                        if (exp.EndsWith("3")) Assert.AreEqual(3, r.Workers.Count(x => x.Node == "J1"), what + ": three at J1");
                    }
                }
            }
            Assert.AreEqual(10 * 2 * Runs, plans);
        }

        /// <summary>An independent check of a planned run: separation, turning points, bystander margin, clearance from every road and every
        /// drivable segment of every node, ask positions inside the zone, the active-avatar limit.</summary>
        static void CheckEveryRule(ExperimentPlanAB p, RoadmapV4 map, RunPlanAB r, string what)
        {
            var w = r.Workers;
            for (int i = 0; i < w.Count; i++)
                for (int j = i + 1; j < w.Count; j++)
                    Assert.GreaterOrEqual(ExperimentPlanAB.Flat(w[i].Position - w[j].Position), 3f - 1e-4f, $"{what}: workers {w[i].Id} and {w[j].Id}");
            foreach (var x in w)
                foreach (var t in ExperimentPlanAB.AskNodes(map).Concat(ExperimentPlanAB.AskNodes(p.Physical)))
                    Assert.GreaterOrEqual(ExperimentPlanAB.Flat(x.Position - ExperimentPlanAB.Pos(t)), 3f - 1e-4f, $"{what}: worker {x.Id} and {t.Name}");
            var segs = new List<(Vector3 a, Vector3 b, string label)>();
            foreach (var road in ExperimentPlanAB.Roads(map).Concat(ExperimentPlanAB.Roads(p.Physical))) segs.Add((road.Key, road.Value, "a road"));
            foreach (var g in w.GroupBy(x => x.Node))
            {
                var node = map.Node(g.Key);
                var ordered = g.OrderBy(x => x.Slot).ToList();
                foreach (var x in ordered.Skip(1))
                    Assert.GreaterOrEqual(p.NearerMargin(map, node, x.Position, ordered[0].Position), p.Rule.NearerMarginM - 1e-4f, $"{what}: bystander rule at {g.Key}");
                var nodeSegs = ExperimentPlanAB.DrivableSegments(map, node, ordered.Select(x => x.Position).ToList(), 2f, 0.4f, out var asks);
                foreach (var s in nodeSegs) segs.Add((s.A, s.B, s.Label));
                foreach (var a in asks)
                    Assert.LessOrEqual(ExperimentPlanAB.Flat(a - ExperimentPlanAB.Pos(node)), 5.5f + 1e-4f, $"{what}: ask position at {g.Key} outside the zone");
            }
            foreach (var x in w)
                foreach (var s in segs)
                    Assert.GreaterOrEqual(ExperimentPlanAB.SegmentDistance(x.Position, s.a, s.b), 1f - 1e-4f, $"{what}: worker {x.Id} ({x.Node}) and {s.label}");
            Assert.LessOrEqual(r.MaxActive, 6, $"{what}: active avatars");
        }

        [Test]
        public void DrivableSegments_CoverEveryOrderTheTieAndEveryBranch()
        {
            var p = Plan("A3", Cfg());
            var j1 = p.Map.Node("J1");
            var ws = new List<Vector3> { new Vector3(4.25f, 0f, -3f), new Vector3(8.25f, 0f, -5.5f) };
            var segs = ExperimentPlanAB.DrivableSegments(p.Map, j1, ws, 2f, 0.4f, out var asks);
            // two orders x (2 approaches + the return to the first) = 6 approach segments; every ask position and re-ask point to E1, J3, J2
            Assert.AreEqual(6, segs.Count(s => s.Label.Contains("to the ask position")));
            Assert.AreEqual(asks.Count * 3, segs.Count(s => s.Label.StartsWith("J1: ask position")));
            var first = ExperimentPlanAB.AskPosition(ws[1], ExperimentPlanAB.Pos(j1), 2f);
            Assert.IsTrue(asks.Any(a => ExperimentPlanAB.Flat(a - first) < 1e-3f), "worker 2 asked first from the node");
            var reask = ExperimentPlanAB.ReaskPosition(ws[1], first, 2f, 0.4f);
            Assert.AreEqual(2f, ExperimentPlanAB.Flat(reask - ws[1]), 1e-4f, "the re-ask point is back on the 2.0 m circle");
            Assert.IsTrue(asks.Any(a => ExperimentPlanAB.Flat(a - reask) < 1e-3f));
        }

        /// <summary>The live (section 3) slots break the rule: A3 run 2 of step 5 left J1's slot-2 ask position (6.3, -5.3, logged) for J3 and
        /// stopped behind J3's slot-2 worker (13.25, -2.0), 0.31 m from the straight line (0.33 m off the driven trail); with the clearance
        /// switched on for the live slots the plan is refused.</summary>
        [Test]
        public void LiveSlots_WithTheClearance_AreRefused_TheA3Run2Geometry()
        {
            Assert.AreEqual(0.31f, ExperimentPlanAB.SegmentDistance(new Vector3(13.25f, 0f, -2f), new Vector3(6.3f, 0f, -5.3f), new Vector3(18.75f, 0f, 0f)), 0.01f, "far inside the 1.0 m clearance");
            var cfg = Cfg();
            cfg.clearance_layout.junction_slots = cfg.junction_slots;
            cfg.clearance_layout.two_worker_experiments = new string[0];
            var p = Plan("A3", cfg.WithClearanceLayout());
            var r = p.PlanRun(1, 1, "E1", Males, Females, null, out string error);
            Assert.IsNull(r);
            StringAssert.Contains("fixed slots break a rule", error);
            StringAssert.Contains("(< 1)", error);
        }

        [Test]
        public void LiveConfig_PlansAsBefore_WithoutTheClearance()
        {
            var cfg = Cfg();
            var r = Plan("A3", cfg).PlanRun(1, 1, "E1", Males, Females, null, out string error);
            Assert.IsNotNull(r, error);
            Assert.AreEqual(new Vector3(8.25f, 0f, -5.5f), r.Workers.Single(x => x.Node == "J1" && x.Slot == 1).Position, "section 3 slot 2");
        }
    }
}
