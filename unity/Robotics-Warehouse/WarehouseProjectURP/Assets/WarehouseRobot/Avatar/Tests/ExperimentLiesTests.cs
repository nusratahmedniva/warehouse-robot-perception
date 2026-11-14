using System;
using System.IO;
using System.Linq;
using System.Text.RegularExpressions;
using NUnit.Framework;
using UnityEngine;
using WarehouseHRI.V4;

namespace WarehouseAvatar.Tests
{
    /// <summary>
    /// Experiments A and B, lying workers (Avatar/Config/experiments_ab.md section 4): the seeding of the lies (per worker per run), the
    /// rate over many runs, consistency when asked again, the wrong-but-valid branch and the declared fallback, and the truth field
    /// gesture_truthful (docs/protocol_v3.md amendment 4): its line format, its rules, and the forbidden key in messages from Unity.
    /// </summary>
    public class ExperimentLiesTests
    {
        static readonly string[] Males = { "sunbox_m_a", "sunbox_m_b" };
        static readonly string[] Females = { "sunbox_f_a", "sunbox_f_b" };

        static string Project(string rel) => File.ReadAllText(Path.Combine(Application.dataPath, "..", rel));
        static string Repo(string rel) => File.ReadAllText(Path.Combine(Application.dataPath, "../../../..", rel));

        static ExperimentPlanAB Plan(string name)
        {
            var cfg = ExperimentsUnityConfig.Parse(Project("Assets/WarehouseRobot/Scenario/Config/experiments_ab_unity.json"));
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

        // ---------------------------------------------------------------- lies

        [Test]
        public void Lies_AreSeededPerWorkerAndRun()
        {
            var p = Plan("B3");
            var a = Run(p, 1, 5);
            var b = Run(p, 1, 5);
            CollectionAssert.AreEqual(a.Workers.Select(x => (x.Liar, x.ShownCommand)), b.Workers.Select(x => (x.Liar, x.ShownCommand)), "same seed and run: the same liars");
            bool otherSeed = false, otherRun = false;
            for (int k = 1; k <= 30 && !(otherSeed && otherRun); k++)
            {
                otherSeed |= !Run(p, 1 + k, 5, a.Goal).Workers.Select(x => x.Liar).SequenceEqual(a.Workers.Select(x => x.Liar));
                otherRun |= !Run(p, 1, 5 + k, a.Goal).Workers.Select(x => x.Liar).SequenceEqual(a.Workers.Select(x => x.Liar));
            }
            Assert.IsTrue(otherSeed, "another seed draws other liars");
            Assert.IsTrue(otherRun, "another run draws other liars");
            var c = Run(p, 1, 5, a.Goal == "E1" ? "E2" : "E1");
            CollectionAssert.AreEqual(a.Workers.Select(x => x.Liar), c.Workers.Select(x => x.Liar), "who lies does not depend on the goal or anything else in the run");
            foreach (var n in new[] { "A1", "A2", "A3", "A4" })
                for (int run = 1; run <= 20; run++) Assert.IsFalse(Run(Plan(n), 1, run).Workers.Any(x => x.Liar), $"{n}: Set A, nobody lies");
        }

        [Test]
        public void Lies_RateIsTheSetsProbability()
        {
            foreach (var n in new[] { "B1", "B3" })            // the lie draw does not depend on the layout; B4's random placement is slower to plan
            {
                var p = Plan(n);
                int liars = 0, workers = 0;
                for (int run = 1; run <= 400; run++)
                {
                    var r = Run(p, 1, run);
                    liars += r.Workers.Count(x => x.Liar);
                    workers += r.Workers.Count;
                }
                double rate = (double)liars / workers, sd = Math.Sqrt(0.2 * 0.8 / workers);
                Assert.AreEqual(0.2, rate, 4 * sd, $"{n}: {liars} liars of {workers} workers");
            }
        }

        [Test]
        public void Lies_ShowAWrongValidBranch_OrTheDeclaredFallback_AndAreConsistent()
        {
            int fallback = 0, branch = 0;
            foreach (var n in new[] { "B1", "B2", "B3", "B4" })
            {
                var p = Plan(n);
                for (int run = 1; run <= (p.LayoutKind == "random" ? 40 : 120); run++)
                {
                    var r = Run(p, 1, run);
                    var again = Run(p, 1, run, r.Goal);
                    var map = p.RunMap(1, run, out _);
                    for (int i = 0; i < r.Workers.Count; i++)
                    {
                        var x = r.Workers[i];
                        Assert.AreEqual(x.ShownCommand, again.Workers[i].ShownCommand, "asked again: the same answer");
                        if (!x.Liar) { Assert.AreEqual(x.TrueCommand, x.ShownCommand, "a truthful worker shows the true direction"); continue; }
                        Assert.AreNotEqual(x.TrueCommand, x.ShownCommand, "a lie is never the true direction");
                        bool hasWrongBranch = map.Branches.TryGetValue(x.Node, out var bs) && bs.Any(b => b.Key != x.TrueCommand);
                        if (hasWrongBranch) { Assert.IsTrue(x.ShownIsBranch, $"{n} {x.Node}: a wrong but valid branch"); branch++; }
                        else { CollectionAssert.Contains(ExperimentPlanAB.Directions, x.ShownCommand); Assert.IsFalse(x.ShownIsBranch, "no such branch"); fallback++; }
                    }
                }
            }
            Assert.Greater(branch, 0, "lies at junctions with another branch occur");
            Assert.Greater(fallback, 0, "lies at nodes without another branch occur (A1's A, A2's A and B, the v4 map's A)");
        }

        [Test]
        public void Lies_FallbackDirectionsAreUniformOverTheOtherThree()
        {
            var p = Plan("B1");                      // corridor: A has only FORWARD, so every lie there is LEFT, RIGHT or BACK
            var counts = ExperimentPlanAB.Directions.ToDictionary(d => d, d => 0);
            for (int run = 1; run <= 1500; run++)
                foreach (var x in Run(p, 1, run).Workers.Where(x => x.Liar)) counts[x.ShownCommand]++;
            Assert.AreEqual(0, counts["FORWARD"], "never the true direction");
            int total = counts.Values.Sum();
            foreach (var d in new[] { "LEFT", "RIGHT", "BACK" })
                Assert.AreEqual(total / 3.0, counts[d], 4 * Math.Sqrt(total * (1.0 / 3) * (2.0 / 3)), $"{d}: {counts[d]} of {total}");
        }

        // ---------------------------------------------------------------- the truth field

        static TruthRow Row(string cmd = "POINT", string phase = "holding", bool truthful = true, bool report = true)
        {
            bool none = cmd == "NONE";
            return new TruthRow
            {
                TimeS = 12.5, WorkerId = 3, Look = "sunbox_m_shirt_white", X = 4.25, Z = -3.0, TrueCommand = cmd,
                PointAngleDeg = cmd == "POINT" ? -90.0 : -1.0, Arm = none ? "none" : "right", Phase = phase, IsCommander = !none,
                Clip = none ? "" : "point_ik_01", HasTruthful = report, GestureTruthful = truthful,
            };
        }

        [Test]
        public void TruthLine_GestureTruthfulAfterClip_OnlyWhenReported()
        {
            StringAssert.Contains("\"clip\": \"point_ik_01\", \"gesture_truthful\": false}", TruthFormat.Line(Row(truthful: false)));
            StringAssert.Contains("\"gesture_truthful\": true", TruthFormat.Line(Row()));
            StringAssert.DoesNotContain("gesture_truthful", TruthFormat.Line(Row(report: false)), "Task 2 rows are written as before");
            Assert.AreEqual("{\"time_s\": 12.5000, \"worker_id\": 3, \"look\": \"sunbox_m_shirt_white\", \"x\": 4.250, \"z\": -3.000, \"true_command\": \"POINT\", " +
                            "\"point_angle_deg\": -90.00, \"arm\": \"right\", \"phase\": \"holding\", \"is_commander\": true, \"clip\": \"point_ik_01\"}",
                            TruthFormat.Line(Row(report: false)), "unchanged line without the experiment fields");
            var r = Row(cmd: "NONE", phase: "idle");
            r.HasActive = true;
            r.Active = false;
            StringAssert.EndsWith("\"gesture_truthful\": true, \"active\": false}", TruthFormat.Line(r));
            Assert.IsNull(TruthFormat.Problem(r));
        }

        [Test]
        public void TruthRules_FalseOnlyWhilePerformed_InactiveNeverPerforms()
        {
            Assert.IsNull(TruthFormat.Problem(Row(truthful: false)), "a lie while holding");
            Assert.IsNull(TruthFormat.Problem(Row(cmd: "PROCEED", phase: "gesturing", truthful: false)), "a lying PROCEED (FORWARD)");
            Assert.IsNull(TruthFormat.Problem(Row(phase: "returning", truthful: false)));
            StringAssert.Contains("gesture_truthful", TruthFormat.Problem(Row(cmd: "NONE", phase: "idle", truthful: false)), "nothing shown: true");
            StringAssert.Contains("gesture_truthful", TruthFormat.Problem(Row(cmd: "NONE", phase: "start_delay", truthful: false)));
            var r = Row();
            r.HasActive = true;
            r.Active = false;
            StringAssert.Contains("inactive", TruthFormat.Problem(r));
        }

        [Test]
        public void ForbiddenKey_GestureTruthfulIsRefusedFromUnity_AndEqualsPython()
        {
            CollectionAssert.Contains(ProtocolV3.TruthKeys, "gesture_truthful");
            Assert.AreEqual("Gesture_Truthful", ProtocolV3.FindForbiddenKey("{\"telemetry\": {\"extra\": [{\"Gesture_Truthful\": false}]}}"), "any depth, any case");
            Assert.AreEqual("worker_id", ProtocolV3.FindForbiddenKey(TruthFormat.Line(Row(truthful: false))), "a truth line in a message is refused");
            string py = Repo("robot_vision/bridge/protocol.py");
            StringAssert.Contains("\"gesture_truthful\"", Regex.Match(py, @"TRUTH_KEYS\s*=\s*frozenset\(\{([^}]*)\}\)").Groups[1].Value);
        }
    }
}
