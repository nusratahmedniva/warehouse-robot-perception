using System;
using System.Collections.Generic;
using System.IO;
using System.Text.RegularExpressions;
using UnityEngine;

namespace WarehouseAvatar
{
    /// <summary>The fields Unity reads from Python's declaration of an interruption (robot_vision/final_guard_v4.py declare_interruption,
    /// FINAL_INTERRUPTION.json; AUDIT.md 16.30.1). Other fields (evidence, reason, completed runs) are not read here.</summary>
    [Serializable]
    public class FinalInterruptionV4
    {
        public string setting = "", kind = "", reason = "", unity_folder = "", bridge_folder = "", frozen_sha256 = "";
        public int resume_from_run = -1, interrupted_run = -1;
        public int seed = int.MinValue;
        public List<string> goal_order = new List<string>();
    }

    /// <summary>
    /// Avatar/Config/experiments_ab.md section 15 addendum 13 (Anisha's AUDIT.md 16.30.1, 16.31.3 and 16.31.4): a final that an infrastructure
    /// failure interrupted is resumed ONCE from run k, only after Python's declaration (final_guard_v4.py --declare-interruption) and only when
    /// it matches: the setting, k, the seed, the full goal order, the frozen hashes now; and never after the setting was declared invalid,
    /// evaluated or exported. Pure: the caller reads the session's numbers. The marker names are those of Python's final_guard_v4.MARKERS
    /// (each keyed "setting"); a test compares them with that file.
    /// </summary>
    public static class FinalResumeV4
    {
        public const string Started = "FINAL_SETTING.json", RunDone = "FINAL_RUN_DONE.json", Interruption = "FINAL_INTERRUPTION.json",
                            Resume = "FINAL_RESUME.json", Invalid = "FINAL_INVALID.json", Evaluated = "FINAL_DONE.json", Exported = "FINAL_EXPORT_DONE.json";

        /// <summary>Folder names directly under <paramref name="outputRoot"/> whose <paramref name="file"/> names this setting under the key
        /// "setting" (Python's markers; Unity's done file uses final_setting and never matches), in ordinal order.</summary>
        public static List<string> Markers(string outputRoot, string file, string setting)
        {
            var found = new List<string>();
            if (string.IsNullOrEmpty(outputRoot) || !Directory.Exists(outputRoot)) return found;
            var dirs = Directory.GetDirectories(outputRoot);
            Array.Sort(dirs, StringComparer.Ordinal);
            foreach (var d in dirs)
            {
                string p = Path.Combine(d, file);
                if (!File.Exists(p)) continue;
                string text;
                try { text = File.ReadAllText(p); }
                catch (IOException) { continue; }
                if (Regex.IsMatch(text, "\"setting\"\\s*:\\s*\"" + Regex.Escape(setting) + "\"")) found.Add(Path.GetFileName(d));
            }
            return found;
        }

        /// <summary>The declaration given as its folder or its FINAL_INTERRUPTION.json; null with the reason.</summary>
        public static FinalInterruptionV4 Read(string path, out string file, out string error)
        {
            file = null;
            error = null;
            if (string.IsNullOrEmpty(path)) { error = "no declaration given"; return null; }
            file = Directory.Exists(path) ? Path.Combine(path, Interruption) : path;
            if (Path.GetFileName(file) != Interruption || !File.Exists(file)) { error = $"{path}: no {Interruption} there"; return null; }
            try
            {
                var d = JsonUtility.FromJson<FinalInterruptionV4>(File.ReadAllText(file));
                if (d == null) error = $"{file}: not a JSON object";
                return d;
            }
            catch (Exception e)
            {
                error = $"{file}: unreadable ({e.Message})";
                return null;
            }
        }

        /// <summary>
        /// 16.31.3 item 2: every reason Unity refuses to start the declared resume. <paramref name="goalOrder"/>: the full order Unity planned
        /// for all <paramref name="runs"/> runs; <paramref name="frozenSha256LfNow"/>: frozen.json now (LF); <paramref name="freezeProblems"/>:
        /// FinalGuardV4.FreezeProblems now. A second resume is refused by Python's server at its start (it writes FINAL_RESUME.json before Unity
        /// starts, so Unity does not look for it).
        /// </summary>
        public static List<string> Problems(FinalInterruptionV4 d, string declarationFile, string outputRoot, string setting, int startRun, int runs,
                                            int seed, IList<string> goalOrder, string frozenSha256LfNow, IList<string> freezeProblems)
        {
            var e = new List<string>();
            if (d == null || string.IsNullOrEmpty(declarationFile)) { e.Add("no declared interruption (FINAL_INTERRUPTION.json)"); return e; }
            string full = Path.GetFullPath(declarationFile);
            string folder = Path.GetFileName(Path.GetDirectoryName(full));
            string parent = Path.GetDirectoryName(Path.GetDirectoryName(full));
            if (!string.Equals(Norm(parent), Norm(outputRoot), StringComparison.OrdinalIgnoreCase))
                e.Add($"the declaration {folder} is not in a folder directly under the output root");
            var declarations = Markers(outputRoot, Interruption, setting);
            if (declarations.Count != 1 || declarations[0] != folder)
                e.Add($"the declarations of {setting} under the output root are [{string.Join(", ", declarations)}]: exactly the given one ({folder}) is required");
            if (d.setting != setting) e.Add($"the declaration is for setting '{d.setting}', this final is '{setting}'");
            if (d.resume_from_run != startRun) e.Add($"the declaration resumes from run {d.resume_from_run}, -startRun is {startRun}");
            if (d.resume_from_run < 1 || d.resume_from_run > runs) e.Add($"the declaration's run {d.resume_from_run} is outside 1..{runs}");
            if (d.seed != seed) e.Add($"the declaration's seed {d.seed} is not the session's seed {seed}");
            if (!SameOrder(d.goal_order, goalOrder))
                e.Add($"the declaration's goal order [{string.Join(",", d.goal_order ?? new List<string>())}] is not the session's [{string.Join(",", goalOrder ?? new List<string>())}]");
            if (string.IsNullOrEmpty(d.unity_folder) || string.IsNullOrEmpty(d.bridge_folder)) e.Add("the declaration names no part-1 Unity or bridge folder");
            if (!string.Equals(d.frozen_sha256 ?? "", frozenSha256LfNow ?? "", StringComparison.OrdinalIgnoreCase) || string.IsNullOrEmpty(frozenSha256LfNow))
                e.Add("configs/v4/frozen.json changed since the interruption was declared (or cannot be read): no resume");
            if (freezeProblems != null) foreach (var p in freezeProblems) e.Add(p);
            foreach (var (file, what) in new[] { (Invalid, "declared invalid"), (Evaluated, "evaluated"), (Exported, "exported") })
            {
                var m = Markers(outputRoot, file, setting);
                if (m.Count > 0) e.Add($"{setting} was already {what} ({m[0]}/{file}): no resume");
            }
            return e;
        }

        static bool SameOrder(IList<string> a, IList<string> b)
        {
            if (a == null || b == null || a.Count != b.Count || a.Count == 0) return false;
            for (int i = 0; i < a.Count; i++) if (a[i] != b[i]) return false;
            return true;
        }

        static string Norm(string p) => string.IsNullOrEmpty(p) ? "" : Path.GetFullPath(p).TrimEnd(Path.DirectorySeparatorChar, Path.AltDirectorySeparatorChar);
    }
}
