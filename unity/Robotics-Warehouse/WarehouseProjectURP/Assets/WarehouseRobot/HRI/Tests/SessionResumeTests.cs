using System.Collections.Generic;
using System.Globalization;
using System.IO;
using System.Linq;
using System.Text;
using NUnit.Framework;
using UnityEngine;
using WarehouseHRI.V4;

namespace WarehouseHRI.Tests
{
    /// <summary>
    /// A session that starts at run k (Avatar/Config/experiments_ab.md section 15 addendum 10): on the real config and map files, runs k..N of
    /// a resumed session (a fresh ExperimentPlanAB that plans only those runs, from the goals of all N runs) equal the same runs of a full
    /// session (another fresh ExperimentPlanAB planning runs 1..N in order) field by field: goal, map, redraws, max active, and every worker's
    /// id, node, slot, position, gender, look, lie, true and shown command. Plus the -startRun rule (SessionResumeV4).
    /// </summary>
    public class SessionResumeTests
    {
        static readonly string[] Males = { "sunbox_m_a", "sunbox_m_b" };
        static readonly string[] Females = { "sunbox_f_a", "sunbox_f_b" };
        static readonly string[] Names = { "A1", "A2", "A3", "A4", "B1", "B2", "B3", "B4" };
        static readonly CultureInfo Inv = CultureInfo.InvariantCulture;

        static string Repo(string rel) => File.ReadAllText(Path.Combine(Application.dataPath, "../../../..", rel));
        static string Project(string rel) => File.ReadAllText(Path.Combine(Application.dataPath, "..", rel));

        /// <summary>A fresh planner from the files, as a new Unity session builds it.</summary>
        static ExperimentPlanAB Fresh(string name)
        {
            var cfg = ExperimentsUnityConfig.Parse(Project("Assets/WarehouseRobot/Scenario/Config/experiments_ab_unity.json"));
            var p = ExperimentPlanAB.Build(cfg, name, Repo(cfg.scenarios_ab), Repo(cfg.roadmap_v4), Project, out string error);
            Assert.IsNotNull(p, error);
            return p;
        }

        /// <summary>Runs <paramref name="first"/>..<paramref name="runs"/> of a session of <paramref name="runs"/> runs, each described in full.</summary>
        static List<string> Session(string name, int seed, int runs, int first)
        {
            var p = Fresh(name);
            var goals = p.Goals(seed, runs);                       // the goals of ALL runs, as TrialRunnerV4 draws them
            var list = new List<string>();
            for (int run = first; run <= runs; run++)
            {
                var r = p.PlanRun(seed, run, goals[run - 1], Males, Females, null, out string error);
                Assert.IsNotNull(r, $"{name} seed {seed} run {run}: {error}");
                list.Add(Describe(r));
            }
            return list;
        }

        static string Describe(RunPlanAB r)
        {
            var sb = new StringBuilder();
            sb.Append($"run {r.Run}, goal {r.Goal}, map {r.MapName}, max active {r.MaxActive}, redraws");
            foreach (var kv in r.Redraws.OrderBy(kv => kv.Key, System.StringComparer.Ordinal)) sb.Append($" {kv.Key}={kv.Value}");
            foreach (var w in r.Workers)
                sb.Append($"\n  worker {w.Id}: {w.Node} slot {w.Slot} ({w.Position.x.ToString("R", Inv)}, {w.Position.y.ToString("R", Inv)}, " +
                          $"{w.Position.z.ToString("R", Inv)}) {w.Gender} {w.Look} liar {w.Liar} true {w.TrueCommand} shown {w.ShownCommand} branch {w.ShownIsBranch}");
            return sb.ToString();
        }

        [Test]
        public void ResumedSession_RunsKToN_AreThoseOfTheFullSession()
        {
            int compared = 0;
            foreach (var name in Names)
                foreach (int seed in new[] { 1, 2 })
                    foreach (var (runs, starts) in new[] { (3, new[] { 2, 3 }), (20, new[] { 2, 11, 20 }) })
                    {
                        var full = Session(name, seed, runs, 1);
                        foreach (int k in starts)
                        {
                            var resumed = Session(name, seed, runs, k);
                            Assert.AreEqual(runs - k + 1, resumed.Count);
                            for (int i = 0; i < resumed.Count; i++, compared++)
                                Assert.AreEqual(full[k - 1 + i], resumed[i], $"{name} seed {seed}, {runs} runs, resumed at {k}: run {k + i}");
                        }
                    }
            Assert.AreEqual(8 * 2 * ((2 + 1) + (19 + 10 + 1)), compared);
        }

        [Test]
        public void ResumedSession_ExperimentsWithLiars_StillDrawLiars()
        {
            // the comparison above covers the lies only if some are drawn: Set B (p = 0.2) over 20 runs has liars
            foreach (var name in new[] { "B1", "B2", "B3", "B4" })
                Assert.IsTrue(Session(name, 1, 20, 1).Any(d => d.Contains("liar True")), name + ": no liar in 20 runs");
        }

        [Test]
        public void StartRun_Rule()
        {
            Assert.IsTrue(SessionResumeV4.Parse("", 20, false, out int k, out _));
            Assert.AreEqual(1, k, "no -startRun = a full session");
            Assert.IsTrue(SessionResumeV4.Parse(null, 20, false, out k, out _));
            Assert.AreEqual(1, k);
            Assert.IsTrue(SessionResumeV4.Parse("1", 20, false, out k, out _));
            Assert.AreEqual(1, k);
            Assert.IsTrue(SessionResumeV4.Parse(" 7 ", 20, false, out k, out _));
            Assert.AreEqual(7, k);
            Assert.IsTrue(SessionResumeV4.Parse("20", 20, false, out k, out _));
            Assert.AreEqual(20, k);
            foreach (var bad in new[] { "0", "21", "-1", "+2", "2.0", "x", "1e1" })
            {
                Assert.IsFalse(SessionResumeV4.Parse(bad, 20, false, out k, out string error), bad);
                Assert.IsNotEmpty(error, bad);
                Assert.AreEqual(1, k, bad + ": a refusal leaves no start run");
            }
            Assert.IsFalse(SessionResumeV4.Parse("1", 20, true, out _, out string finalError), "any -startRun is refused in a final");
            StringAssert.Contains("refused in a final", finalError);
            Assert.IsFalse(SessionResumeV4.Parse("2", 20, true, out _, out _));
            Assert.IsTrue(SessionResumeV4.Parse("", 20, true, out k, out _), "a final without -startRun runs as before");
            Assert.AreEqual(1, k);
        }
    }
}
