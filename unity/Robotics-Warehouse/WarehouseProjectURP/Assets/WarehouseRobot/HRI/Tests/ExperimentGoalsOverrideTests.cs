using System.IO;
using NUnit.Framework;
using UnityEngine;
using WarehouseHRI.V4;

namespace WarehouseHRI.Tests
{
    /// <summary>
    /// Avatar/Config/experiments_ab.md section 15 addendum 1, item 3c: TrialPlayV4 -experimentGoals (development only) replaces the seeded
    /// goals of a random-endpoint experiment, one goal per run, in the given order; refused in a final, on a fixed-goal map, for a name
    /// that is not an endpoint of the map, and for a list whose length is not the number of runs.
    /// </summary>
    public class ExperimentGoalsOverrideTests
    {
        static string Repo(string rel) => File.ReadAllText(Path.Combine(Application.dataPath, "../../../..", rel));
        static string Project(string rel) => File.ReadAllText(Path.Combine(Application.dataPath, "..", rel));

        static ExperimentPlanAB Plan(string name)
        {
            var cfg = ExperimentsUnityConfig.Parse(Project("Assets/WarehouseRobot/Scenario/Config/experiments_ab_unity.json"));
            var p = ExperimentPlanAB.Build(cfg, name, Repo(cfg.scenarios_ab), Repo(cfg.roadmap_v4), Project, out string error);
            Assert.IsNotNull(p, error);
            return p;
        }

        [Test]
        public void NoOverride_KeepsTheSeededGoals()
        {
            Assert.IsNull(Plan("A3").GoalsOverride("", false, 3, out string error));
            Assert.IsNull(error);
            Assert.IsNull(Plan("A3").GoalsOverride("  ", true, 20, out error), "empty in a final: no override, not an error");
            Assert.IsNull(error);
        }

        [Test]
        public void Override_OneGoalPerRun_InTheGivenOrder_SpacesIgnored()
        {
            foreach (var n in new[] { "A3", "A4", "B3", "B4" })
            {
                var g = Plan(n).GoalsOverride("E5, E6,E5", false, 3, out string error);
                Assert.IsNull(error, n);
                CollectionAssert.AreEqual(new[] { "E5", "E6", "E5" }, g, n);
            }
        }

        [Test]
        public void Override_PlansEveryRunWithTheGivenGoal()
        {
            var p = Plan("A3");
            var goals = p.GoalsOverride("E5,E6", false, 2, out string error);
            Assert.IsNull(error);
            for (int run = 1; run <= 2; run++)
            {
                var r = p.PlanRun(1, run, goals[run - 1], new[] { "m1", "m2" }, new[] { "f1", "f2" }, null, out error);
                Assert.IsNotNull(r, error);
                Assert.AreEqual(goals[run - 1], r.Goal);
                Assert.AreEqual("LEFT", r.Workers.Find(w => w.Node == "J1").TrueCommand, "E5 and E6 both lie left of J1");
                Assert.AreEqual(run == 1 ? "RIGHT" : "LEFT", r.Workers.Find(w => w.Node == "J4").TrueCommand, "J4: E5 right, E6 left");
            }
        }

        [Test]
        public void Override_IsRefusedInAFinal()
        {
            Assert.IsNull(Plan("A3").GoalsOverride("E5,E6,E5", true, 3, out string error));
            StringAssert.Contains("development sessions only", error);
        }

        [Test]
        public void Override_IsRefusedOnTheFixedGoalMaps()
        {
            foreach (var n in new[] { "A1", "A2", "B1", "B2" })
            {
                Assert.IsNull(Plan(n).GoalsOverride("B,B,B", false, 3, out string error), n);
                StringAssert.Contains("fixed goal", error, n);
            }
        }

        [Test]
        public void Override_RefusesUnknownNamesAndAWrongCount()
        {
            var p = Plan("A3");
            Assert.IsNull(p.GoalsOverride("E5,J1,E6", false, 3, out string error));
            StringAssert.Contains("'J1' is not an endpoint", error);
            Assert.IsNull(p.GoalsOverride("E5,E7,E6", false, 3, out error));
            StringAssert.Contains("'E7' is not an endpoint", error);
            Assert.IsNull(p.GoalsOverride("E5,,E6", false, 3, out error), "an empty name");
            Assert.IsNotNull(error);
            Assert.IsNull(p.GoalsOverride("E5,E6", false, 3, out error));
            StringAssert.Contains("2 goal(s) for 3 run(s)", error);
            Assert.IsNull(p.GoalsOverride("E5,E6,E5,E6", false, 3, out error));
            StringAssert.Contains("4 goal(s) for 3 run(s)", error);
        }
    }
}
