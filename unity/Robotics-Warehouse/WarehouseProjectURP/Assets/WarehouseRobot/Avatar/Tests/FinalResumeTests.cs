using System;
using System.Collections.Generic;
using System.IO;
using System.Linq;
using System.Text.RegularExpressions;
using NUnit.Framework;
using UnityEngine;
using WarehouseHRI.V4;

namespace WarehouseAvatar.Tests
{
    /// <summary>
    /// experiments_ab.md section 15 addendum 13 (Anisha's AUDIT.md 16.30.1, 16.31.3, 16.31.4): the declared resume of a final on Unity's side.
    /// Each item with its refusal and its acceptance, on synthetic output folders (no Play, no session): the declaration read and checked
    /// (item 2), -startRun in a final only with a declaration (item 1), the start guard with Python's start marker (item 4), the done file of
    /// runs k..N (item 5), the session.json keys (item 3, source check), and Python's marker names.
    /// </summary>
    public class FinalResumeTests
    {
        static string Repo(string rel) => File.ReadAllText(Path.Combine(Application.dataPath, "../../../..", rel));
        static string Project(string rel) => File.ReadAllText(Path.Combine(Application.dataPath, "..", rel));

        const string Setting = "B3";
        const string Part1 = "trials_final_Task2_B3_20261201_100000";
        const string Bridge1 = "bridge_guide_20261201_100000";
        const string Bridge2 = "bridge_guide_20261201_140000";
        const string DeclFolder = "final_interruption_B3_20261201_120000";
        const string Sha = "0123456789abcdef0123456789abcdef0123456789abcdef0123456789abcdef";
        static readonly string[] Goals = { "E5", "E1", "E5", "E2", "E5", "E3", "E5", "E3", "E4", "E3", "E5", "E3", "E5", "E6", "E2", "E5", "E3", "E1", "E4", "E2" };

        string m_Root;

        [SetUp] public void Make() { m_Root = Path.Combine(Path.GetTempPath(), "final_resume_" + Guid.NewGuid().ToString("N")); Directory.CreateDirectory(m_Root); }
        [TearDown] public void Remove() { if (Directory.Exists(m_Root)) Directory.Delete(m_Root, true); }

        string Put(string folder, string file, string text)
        {
            string d = Path.Combine(m_Root, folder);
            Directory.CreateDirectory(d);
            string p = Path.Combine(d, file);
            File.WriteAllText(p, text);
            return p;
        }

        /// <summary>A declaration as final_guard_v4.declare_interruption writes it (json.dumps, indent 2, every field).</summary>
        static string Declaration(string setting = Setting, int run = 4, int seed = 2, IEnumerable<string> goals = null, string sha = Sha) =>
            "{\n  \"setting\": \"" + setting + "\",\n  \"kind\": \"interruption\",\n  \"written\": \"2026-12-01T12:00:00\",\n" +
            $"  \"resume_from_run\": {run},\n  \"interrupted_run\": {run},\n  \"reason\": \"server crash (python312.dll)\",\n" +
            "  \"evidence\": [\n    {\n      \"path\": \"crash/server.err.log\",\n      \"bytes\": 120,\n      \"sha256\": \"ab\"\n    }\n  ],\n" +
            $"  \"frozen_sha256\": \"{sha}\",\n  \"unity_folder\": \"{Part1}\",\n  \"bridge_folder\": \"{Bridge1}\",\n" +
            "  \"outcome_of_interrupted_run\": \"interrupted (infrastructure)\",\n" +
            $"  \"seed\": {seed},\n  \"goal_order\": [\n" + string.Join(",\n", (goals ?? Goals).Select(g => "    \"" + g + "\"")) + "\n  ],\n" +
            "  \"completed_runs\": [\n    1,\n    2,\n    3\n  ]\n}\n";

        static string PyMarker(string setting) => "{\n  \"setting\": \"" + setting + "\",\n  \"kind\": \"x\",\n  \"written\": \"2026-12-01T10:00:00\"\n}\n";

        static FinalConfigV4 Cfg() => new FinalConfigV4 { done_file = "UNITY_FINAL_DONE.json", python_run_marker = "FINAL_RUN_DONE.json" };

        List<string> Problems(string declText = null, int startRun = 4, int seed = 2, IList<string> goals = null, string shaNow = Sha, IList<string> freeze = null)
        {
            string file = Put(DeclFolder, FinalResumeV4.Interruption, declText ?? Declaration());
            var d = FinalResumeV4.Read(file, out string f, out string error);
            Assert.IsNotNull(d, error);
            return FinalResumeV4.Problems(d, f, m_Root, Setting, startRun, 20, seed, goals ?? Goals, shaNow, freeze ?? new List<string>());
        }

        [Test]
        public void MarkerNames_AreThoseOfPythonsFinalGuard()
        {
            string py = Repo("robot_vision/final_guard_v4.py");
            foreach (var (kind, file) in new[] { ("run", FinalResumeV4.RunDone), ("evaluation", FinalResumeV4.Evaluated), ("export", FinalResumeV4.Exported),
                                                 ("started", FinalResumeV4.Started), ("interruption", FinalResumeV4.Interruption),
                                                 ("resume", FinalResumeV4.Resume), ("invalid", FinalResumeV4.Invalid) })
                StringAssert.IsMatch("\"" + kind + "\":\\s*\"" + Regex.Escape(file) + "\"", py, kind);
            StringAssert.Contains("--resume-info", py);
        }

        [Test]
        public void Item2_TheDeclarationIsRead_AsFolderOrFile()
        {
            string file = Put(DeclFolder, FinalResumeV4.Interruption, Declaration());
            var a = FinalResumeV4.Read(Path.Combine(m_Root, DeclFolder), out string fa, out _);
            var b = FinalResumeV4.Read(file, out _, out _);
            Assert.AreEqual(file, fa);
            foreach (var d in new[] { a, b })
            {
                Assert.AreEqual(Setting, d.setting);
                Assert.AreEqual(4, d.resume_from_run);
                Assert.AreEqual(2, d.seed);
                CollectionAssert.AreEqual(Goals, d.goal_order);
                Assert.AreEqual(Part1, d.unity_folder);
                Assert.AreEqual(Bridge1, d.bridge_folder);
            }
            Assert.IsNull(FinalResumeV4.Read(Path.Combine(m_Root, "nothing"), out _, out string e1));
            StringAssert.Contains("no FINAL_INTERRUPTION.json", e1);
            Assert.IsNull(FinalResumeV4.Read(Put("x", "other.json", "{}"), out _, out _));
            Assert.IsNull(FinalResumeV4.Read("", out _, out _));
        }

        [Test]
        public void Item2_TheMatchingDeclarationIsAccepted()
        {
            CollectionAssert.IsEmpty(Problems());
        }

        [Test]
        public void Item2_EveryMismatchRefusesTheResume()
        {
            void Refused(List<string> p, string why) { Assert.IsTrue(p.Any(x => x.Contains(why)), why + " not in: " + string.Join(" | ", p)); }
            Refused(Problems(Declaration(setting: "B4")), "is for setting 'B4'");
            Refused(Problems(startRun: 5), "resumes from run 4, -startRun is 5");
            Refused(Problems(seed: 1), "seed 2 is not the session's seed 1");
            var other = Goals.ToList(); other[3] = "E6";
            Refused(Problems(goals: other), "goal order");
            Refused(Problems(goals: Goals.Take(19).ToList()), "goal order");
            Refused(Problems(shaNow: "f" + Sha.Substring(1)), "frozen.json changed");
            Refused(Problems(shaNow: null), "frozen.json changed");
            Refused(Problems(freeze: new List<string> { "freeze file x changed since the freeze" }), "freeze file x changed");
            Refused(Problems(Declaration(run: 25), startRun: 25), "outside 1..20");
        }

        [Test]
        public void Item2_InvalidEvaluatedExportedOrASecondDeclarationRefuse()
        {
            foreach (var (folder, file, why) in new[] { ("final_invalid_B3_x", FinalResumeV4.Invalid, "declared invalid"),
                                                        ("hri_eval_final_v4_B3_x", FinalResumeV4.Evaluated, "evaluated"),
                                                        ("export_csv_v4_final_B3_x", FinalResumeV4.Exported, "exported") })
            {
                Remove(); Make();
                Put(folder, file, PyMarker(Setting));
                Assert.IsTrue(Problems().Any(x => x.Contains(why)), why);
            }
            Remove(); Make();
            Put(folder: "final_interruption_B3_20261201_130000", file: FinalResumeV4.Interruption, text: Declaration());
            Assert.IsTrue(Problems().Any(x => x.Contains("exactly the given one")), "two declarations");
            Remove(); Make();
            Put("final_invalid_B4_x", FinalResumeV4.Invalid, PyMarker("B4"));
            CollectionAssert.IsEmpty(Problems(), "another setting's marker does not count");
        }

        [Test]
        public void Item2_ADeclarationOutsideTheOutputRootIsRefused()
        {
            string nested = Path.Combine(m_Root, "elsewhere", DeclFolder);
            Directory.CreateDirectory(nested);
            string file = Path.Combine(nested, FinalResumeV4.Interruption);
            File.WriteAllText(file, Declaration());
            var d = FinalResumeV4.Read(file, out string f, out _);
            var p = FinalResumeV4.Problems(d, f, m_Root, Setting, 4, 20, 2, Goals, Sha, new List<string>());
            Assert.IsTrue(p.Any(x => x.Contains("not in a folder directly under the output root")), string.Join(" | ", p));
            Assert.IsTrue(FinalResumeV4.Problems(null, null, m_Root, Setting, 4, 20, 2, Goals, Sha, null).Any(x => x.Contains("no declared interruption")));
        }

        [Test]
        public void Item1_StartRunInAFinal_OnlyWithADeclaration()
        {
            Assert.IsFalse(SessionResumeV4.Parse("4", 20, true, false, out _, out string e1), "no declaration");
            StringAssert.Contains("refused in a final", e1);
            StringAssert.Contains("--declare-interruption", e1);
            Assert.IsFalse(SessionResumeV4.Parse("4", 20, true, out _, out _), "the old call: no declaration");
            Assert.IsTrue(SessionResumeV4.Parse("4", 20, true, true, out int k, out string e2), e2);
            Assert.AreEqual(4, k);
            Assert.IsFalse(SessionResumeV4.Parse("", 20, true, true, out _, out string e3), "a declared resume needs k");
            StringAssert.Contains("needs -startRun k", e3);
            Assert.IsFalse(SessionResumeV4.Parse("21", 20, true, true, out _, out _), "range");
            Assert.IsTrue(SessionResumeV4.Parse("", 20, true, false, out k, out _));
            Assert.AreEqual(1, k, "a fresh final");
            Assert.IsTrue(SessionResumeV4.Parse("3", 5, false, false, out k, out _), "development unchanged");
            Assert.AreEqual(3, k);
        }

        [Test]
        public void Item4_TheStartGuard_StartMarkerWithoutDeclarationRefuses_TheDeclaredPart1IsAccepted()
        {
            var cfg = Cfg();
            Put(Bridge2, FinalResumeV4.Started, PyMarker(Setting));                  // this session's own server (written before Unity starts)
            Assert.IsNull(FinalGuardV4.EarlierFinal(m_Root, Setting, cfg, Bridge2, null), "a fresh final: only its own server's start marker");
            Assert.AreEqual(Bridge2 + "/" + FinalResumeV4.Started, FinalGuardV4.EarlierFinal(m_Root, Setting, cfg, null, null), "without -bridgeFolder it counts");
            Put(Bridge1, FinalResumeV4.Started, PyMarker(Setting));                  // a hard crash: started, no FINAL_RUN_DONE.json
            Assert.AreEqual(Bridge1 + "/" + FinalResumeV4.Started, FinalGuardV4.EarlierFinal(m_Root, Setting, cfg, Bridge2, null), "a silent restart is refused");
            var decl = JsonUtility.FromJson<FinalInterruptionV4>(Declaration());
            Assert.IsNull(FinalGuardV4.EarlierFinal(m_Root, Setting, cfg, Bridge2, decl), "the declared part 1 is accepted");
            Put(Bridge1, FinalResumeV4.RunDone, PyMarker(Setting));                  // a clean server exit after Unity died
            Assert.IsNull(FinalGuardV4.EarlierFinal(m_Root, Setting, cfg, Bridge2, decl));
            Assert.IsNotNull(FinalGuardV4.EarlierFinal(m_Root, Setting, cfg, Bridge2, null));
            Put("bridge_guide_20261201_090000", FinalResumeV4.Started, PyMarker(Setting));
            Assert.AreEqual("bridge_guide_20261201_090000/" + FinalResumeV4.Started, FinalGuardV4.EarlierFinal(m_Root, Setting, cfg, Bridge2, decl),
                            "a start marker that is not the declaration's part 1");
            Remove(); Make();
            Put(Part1, "UNITY_FINAL_DONE.json", FinalGuardV4.DoneJson(Setting, 20, 15, "abc", Part1, "2026-12-01T13:00:00"));
            Assert.AreEqual(Part1 + "/UNITY_FINAL_DONE.json", FinalGuardV4.EarlierFinal(m_Root, Setting, cfg, Bridge2, decl), "a complete session is never resumed");
            Remove(); Make();
            Put(Bridge1, FinalResumeV4.Started, PyMarker("B4"));
            Assert.IsNull(FinalGuardV4.EarlierFinal(m_Root, Setting, cfg, Bridge2, null), "another setting");
        }

        [Test]
        public void Item5_TheDoneFileNamesTheRunsItCovers()
        {
            string full = FinalGuardV4.DoneJson(Setting, 20, 18, "abc", "trials_final_Task2_B3_a", "2026-12-01T10:00:00");
            StringAssert.Contains("\"start_run\": 1", full);
            StringAssert.Contains("\"runs_driven\": 20", full);
            StringAssert.Contains("\"resume_from_run\": 0", full);
            string part2 = FinalGuardV4.DoneJson(Setting, 20, 15, "abc", "trials_final_Task2_B3_b", "2026-12-01T16:00:00", 4, 4, Part1);
            StringAssert.Contains("\"runs\": 20", part2);
            StringAssert.Contains("\"start_run\": 4", part2);
            StringAssert.Contains("\"runs_driven\": 17", part2);
            StringAssert.Contains("\"resume_from_run\": 4", part2);
            StringAssert.Contains("\"resume_of\": \"" + Part1 + "\"", part2);
            StringAssert.Contains("\"successes\": 15", part2);
            foreach (var t in new[] { full, part2 })
            {
                StringAssert.DoesNotContain("\"setting\"", t, "Python's marker scan never reads Unity's done file");
                Assert.IsNotNull(JsonUtility.FromJson<FinalInterruptionV4>(t), "valid JSON");
            }
        }

        [Test]
        public void Item3_TheRunnerWritesTheResumeKeys_ChecksBeforeAnyFolder_AndNeedsItsServerFolder()
        {
            string r = Project("Assets/WarehouseRobot/Scenario/Scripts/TrialRunnerV4.cs");
            StringAssert.Contains("public int resume_from_run;", r);
            StringAssert.Contains("public string resume_of = \"\";", r);
            StringAssert.Contains("session.resume_from_run = resumeDecl != null ? startRun : 0;", r);
            StringAssert.Contains("session.resume_of = resumeDecl != null ? resumeDecl.unity_folder : \"\";", r);
            StringAssert.Contains("session.start_run = startRun;", r);
            int run = r.IndexOf("IEnumerator Run()", StringComparison.Ordinal);
            int check = r.IndexOf("FinalResumeV4.Problems(", run, StringComparison.Ordinal);
            int folder = r.IndexOf("SessionFolder = NewFolder(", run, StringComparison.Ordinal);
            Assert.That(check > run && check < folder, "the declaration is checked before the session folder is made (a refusal writes nothing)");
            StringAssert.Contains("-bridgeFolder (the server's run folder, passed by run_session_v4.ps1) is required in a final", r);
            StringAssert.Contains("SessionResumeV4.Parse(startText, TrialTotal, Final, resumeDecl != null,", r);
            StringAssert.Contains("startRun, resumeDecl != null ? startRun : 0, resumeDecl != null ? resumeDecl.unity_folder : \"\")", r);
            string play = Project("Assets/WarehouseRobot/Scenario/Editor/TrialPlayV4.cs");
            foreach (var want in new[] { "\"-resumeMarker\"", "\"-bridgeFolder\"", "SessionState.SetString(TrialRunnerV4.ResumeMarkerKey, \"\");",
                                         "SessionState.SetString(TrialRunnerV4.BridgeFolderKey, \"\");" })
                StringAssert.Contains(want, play);
        }
    }
}
