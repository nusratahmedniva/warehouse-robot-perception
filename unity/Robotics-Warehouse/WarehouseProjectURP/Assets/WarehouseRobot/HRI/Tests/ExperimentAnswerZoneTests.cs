using System.Collections.Generic;
using System.IO;
using System.Linq;
using NUnit.Framework;
using UnityEngine;
using WarehouseHRI.V4;

namespace WarehouseHRI.Tests
{
    /// <summary>
    /// Avatar/Config/experiments_ab.md section 15 addendum 1, item 3a: a worker answers only while the robot is within answer_zone_radius_m
    /// (6.0 m) of the worker's own node; outside it, NONE. The zone covers the live layout's ask positions (first ask and second opinions,
    /// with the 0.5 m margin of item 3b) and the zones of two asking nodes never overlap, on every map.
    /// </summary>
    public class ExperimentAnswerZoneTests
    {
        static readonly string[] Males = { "sunbox_m_a", "sunbox_m_b" };
        static readonly string[] Females = { "sunbox_f_a", "sunbox_f_b" };
        const float Margin = 0.5f, Standoff = 2.0f;

        static string Repo(string rel) => File.ReadAllText(Path.Combine(Application.dataPath, "../../../..", rel));
        static string Project(string rel) => File.ReadAllText(Path.Combine(Application.dataPath, "..", rel));
        static ExperimentsUnityConfig Cfg() => ExperimentsUnityConfig.Parse(Project("Assets/WarehouseRobot/Scenario/Config/experiments_ab_unity.json"));

        static ExperimentPlanAB Plan(string name, ExperimentsUnityConfig cfg)
        {
            var p = ExperimentPlanAB.Build(cfg, name, Repo(cfg.scenarios_ab), Repo(cfg.roadmap_v4), Project, out string error);
            Assert.IsNotNull(p, error);
            return p;
        }

        [Test]
        public void Config_HoldsTheDeclaredRadius()
        {
            var cfg = Cfg();
            CollectionAssert.IsEmpty(cfg.Validate());
            Assert.AreEqual(6.0f, cfg.answer_zone_radius_m, 1e-6f);
            var bad = Cfg();
            bad.answer_zone_radius_m = 0f;
            CollectionAssert.IsNotEmpty(bad.Validate(), "a zone of 0 m is refused");
        }

        [Test]
        public void InAnswerZone_IsTheHorizontalDistanceToTheWorkersOwnNode()
        {
            var j2 = new Vector3(-6.25f, 0f, 0f);
            Assert.IsTrue(ExperimentPlanAB.InAnswerZone(new Vector3(-6.25f + 6f, 3f, 0f), j2, 6f), "on the border (height ignored): inside");
            Assert.IsFalse(ExperimentPlanAB.InAnswerZone(new Vector3(-6.25f + 6.01f, 0f, 0f), j2, 6f));
            // A3 run 1 of step 5 (section 15): the asks a J2 worker answered while Python was still deciding J1
            Assert.IsFalse(ExperimentPlanAB.InAnswerZone(new Vector3(1.2f, 0f, 1.5f), j2, 6f), "136-146 s, 7.6 m from J2: now NONE");
            Assert.IsTrue(ExperimentPlanAB.InAnswerZone(new Vector3(-1.6f, 0f, -0.7f), j2, 6f),
                          "159 s, 4.7 m from J2: still answered (not covered by the zone; Python's search must stay near its node)");
        }

        [Test]
        public void AskPosition_IsTheStandoffTowardWhereTheRobotComesFrom()
        {
            var a = ExperimentPlanAB.AskPosition(new Vector3(8.25f, 0f, -5.5f), new Vector3(6.25f, 0f, 0f), 2f);
            Assert.AreEqual(2f, ExperimentPlanAB.Flat(a - new Vector3(8.25f, 0f, -5.5f)), 1e-4f);
            Assert.AreEqual(3.85f, ExperimentPlanAB.Flat(a - new Vector3(6.25f, 0f, 0f)), 0.01f, "5.85 m from the node, 2.0 m toward it");
        }

        /// <summary>Every ask position of a node's own workers, first ask from the node and second opinions from another worker's ask
        /// position (every order), lies within the radius minus the margin, on every map of the live layout (seed 1 and 2, 20 runs).</summary>
        [Test]
        public void LiveLayout_EveryOwnAskPositionLiesInsideItsZone()
        {
            var cfg = Cfg();
            cfg.a2_sides = new[] { "right", "left" };
            foreach (var n in new[] { "A1", "A2", "A3", "A4" })
            {
                var p = Plan(n, cfg);
                foreach (int seed in new[] { 1, 2 })
                {
                    var goals = p.Goals(seed, 20);
                    for (int run = 1; run <= 20; run++)
                    {
                        var r = p.PlanRun(seed, run, goals[run - 1], Males, Females, null, out string error);
                        Assert.IsNotNull(r, error);
                        var map = p.RunMap(seed, run, out _);
                        foreach (var g in r.Workers.GroupBy(x => x.Node))
                        {
                            var c = ExperimentPlanAB.Pos(map.Node(g.Key));
                            var ws = g.OrderBy(x => x.Slot).Select(x => x.Position).ToList();
                            foreach (var w in ws)
                            {
                                var first = ExperimentPlanAB.AskPosition(w, c, Standoff);
                                Assert.LessOrEqual(ExperimentPlanAB.Flat(first - c), cfg.answer_zone_radius_m - Margin, $"{n} seed {seed} run {run} {g.Key}: first ask");
                                foreach (var o in ws.Where(o => o != w))
                                {
                                    var second = ExperimentPlanAB.AskPosition(w, ExperimentPlanAB.AskPosition(o, c, Standoff), Standoff);
                                    Assert.LessOrEqual(ExperimentPlanAB.Flat(second - c), cfg.answer_zone_radius_m - Margin, $"{n} seed {seed} run {run} {g.Key}: second opinion");
                                }
                            }
                        }
                    }
                }
            }
        }

        [Test]
        public void ZonesOfTwoAskingNodes_NeverOverlap_OnAnyMap()
        {
            var cfg = Cfg();
            cfg.a2_sides = new[] { "right", "left" };
            var maps = new List<RoadmapV4>();
            foreach (var n in new[] { "A1", "A2", "A3" })
            {
                var p = Plan(n, cfg);
                maps.Add(p.Map);
                if (p.LeftMap != null) maps.Add(p.LeftMap);
            }
            Assert.AreEqual(4, maps.Count, "corridor, turn, turn_left, roadmap");
            foreach (var m in maps)
            {
                var nodes = ExperimentPlanAB.AskNodes(m);
                for (int i = 0; i < nodes.Count; i++)
                    for (int j = i + 1; j < nodes.Count; j++)
                        Assert.Greater(ExperimentPlanAB.Flat(ExperimentPlanAB.Pos(nodes[i]) - ExperimentPlanAB.Pos(nodes[j])), 2f * cfg.answer_zone_radius_m,
                                       $"{nodes[i].Name} and {nodes[j].Name}");
            }
        }
    }
}
