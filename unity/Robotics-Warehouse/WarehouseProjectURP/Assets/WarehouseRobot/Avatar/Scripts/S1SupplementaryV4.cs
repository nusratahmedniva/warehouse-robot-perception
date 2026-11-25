using System;
using System.Collections.Generic;
using System.Globalization;
using System.IO;
using System.Text.RegularExpressions;
using UnityEngine;

namespace WarehouseAvatar
{
    /// <summary>One S1 setting: its name (A1, A3 or B3) and the plan runs of the final plan (seed 2) that the session drives as run_001..run_005.</summary>
    [Serializable]
    public class S1SettingDef
    {
        public string name = "";
        public int[] plan_runs = new int[0];
    }

    /// <summary>One cell of the S1 matrix: a character and a setting.</summary>
    [Serializable]
    public class S1CellDef
    {
        public string character = "";
        public string setting = "";
    }

    /// <summary>
    /// Avatar/Config/s1_supplementary.json: the post-freeze supplementary experiment S1 (Anisha's AUDIT.md 16.36 and 16.37, Unity addendum 14 of
    /// experiments_ab.md). Four characters, settings A1, A3 and B3, five runs per cell, the plan runs, the order of the twelve cells and the names of the
    /// run-once markers. Exploratory, never pooled with the finals, nothing is set from it.
    /// </summary>
    [Serializable]
    public class S1Config
    {
        public const string AssetPath = "Assets/WarehouseRobot/Avatar/Config/s1_supplementary.json";
        public const string Name = "S1";
        public string note = "", supplementary = "", amendment = "", folder_prefix = "";
        public string[] characters = new string[0];
        public S1SettingDef[] settings = new S1SettingDef[0];
        public int runs_per_cell, timeout_s;
        public S1CellDef[] cell_order = new S1CellDef[0];
        public string marker_started = "", marker_done = "", marker_invalid = "";

        /// <summary>The characters of S1 (the same four as data_splits_v4.SUPPLEMENTARY["S1"], AUDIT.md 16.37): the guard of every other mode refuses them.</summary>
        public static readonly string[] DeclaredCharacters = { "mixamo_worker", "anime_f_01", "anime_f_02_outfit_short", "cartoon_boxo_01" };
        /// <summary>The settings of S1 and their plan runs, declared in AUDIT.md 16.37: A1 and A3 runs 1-5; B3 runs 5, 7, 8, 10, 11 (the 5 lowest B3 plan runs with
        /// a liar at a junction on the planned route, read from the plan only).</summary>
        public static readonly Dictionary<string, int[]> DeclaredPlanRuns = new Dictionary<string, int[]>
        {
            ["A1"] = new[] { 1, 2, 3, 4, 5 }, ["A3"] = new[] { 1, 2, 3, 4, 5 }, ["B3"] = new[] { 5, 7, 8, 10, 11 },
        };

        public static S1Config Parse(string json) =>
            JsonUtility.FromJson<S1Config>(json ?? "") ?? throw new FormatException("s1_supplementary.json: not a JSON object");

        public S1SettingDef Setting(string name) => Array.Find(settings ?? new S1SettingDef[0], s => s != null && s.name == name);

        public List<string> Validate()
        {
            var e = new List<string>();
            if (supplementary != Name) e.Add($"supplementary must be \"{Name}\"");
            if (string.IsNullOrEmpty(amendment)) e.Add("amendment is empty");
            if (string.IsNullOrEmpty(folder_prefix) || !folder_prefix.StartsWith("s1_", StringComparison.Ordinal)) e.Add("folder_prefix must start with s1_");
            if (runs_per_cell != 5) e.Add("runs_per_cell must be 5 (AUDIT.md 16.37)");
            if (timeout_s != 480) e.Add("timeout_s must be 480 (AUDIT.md 16.36)");
            if (characters == null || characters.Length != DeclaredCharacters.Length) e.Add("characters: the four declared looks only");
            else
                for (int i = 0; i < characters.Length; i++)
                    if (characters[i] != DeclaredCharacters[i]) e.Add($"characters[{i}] is '{characters[i]}', declared '{DeclaredCharacters[i]}'");
            if (settings == null || settings.Length != DeclaredPlanRuns.Count) e.Add("settings: A1, A3 and B3 only");
            else
                foreach (var kv in DeclaredPlanRuns)
                {
                    var s = Setting(kv.Key);
                    if (s == null) { e.Add($"settings: {kv.Key} missing"); continue; }
                    if (!SameList(s.plan_runs, kv.Value)) e.Add($"settings {kv.Key}: plan_runs [{string.Join(",", s.plan_runs)}], declared [{string.Join(",", kv.Value)}] (AUDIT.md 16.37)");
                }
            if (string.IsNullOrEmpty(marker_started) || string.IsNullOrEmpty(marker_done) || string.IsNullOrEmpty(marker_invalid)
                || marker_started == marker_done || marker_started == marker_invalid || marker_done == marker_invalid)
                e.Add("marker_started, marker_done and marker_invalid: three different names are required");
            foreach (var m in new[] { marker_started, marker_done, marker_invalid })
                if (!string.IsNullOrEmpty(m) && m.StartsWith("FINAL", StringComparison.OrdinalIgnoreCase)) e.Add($"marker '{m}': an S1 marker never has the name of a final marker");
            int expected = DeclaredCharacters.Length * DeclaredPlanRuns.Count;
            if (cell_order == null || cell_order.Length != expected) e.Add($"cell_order: {expected} cells required");
            else
            {
                var seen = new HashSet<string>();
                foreach (var c in cell_order)
                {
                    string key = c.character + "/" + c.setting;
                    if (Array.IndexOf(DeclaredCharacters, c.character) < 0 || !DeclaredPlanRuns.ContainsKey(c.setting)) e.Add($"cell_order: unknown cell {key}");
                    else if (!seen.Add(key)) e.Add($"cell_order: cell {key} twice");
                }
            }
            return e;
        }

        static bool SameList(int[] a, int[] b)
        {
            if (a == null || a.Length != b.Length) return false;
            for (int i = 0; i < a.Length; i++) if (a[i] != b[i]) return false;
            return true;
        }
    }

    /// <summary>One part (session folder) of an S1 cell found under the output root: what its markers and its truth files say.</summary>
    public class S1CellPart
    {
        public string folder = "", character = "", setting = "";
        public int part = 1;
        public bool done, invalid;
        /// <summary>The run numbers with an outcome (truth_run###.json).</summary>
        public List<int> outcomes = new List<int>();
    }

    /// <summary>The run-once guard of S1 (per character, setting and run) and its interruption rule, as the finals' (AUDIT.md 16.30.1): one resume from the first run
    /// without an outcome, a second interruption makes the cell INVALID. Pure: the caller reads the folders.</summary>
    public static class S1Guard
    {
        public static List<string> Problems(S1Config cfg, string character, string setting, bool resume, IList<S1CellPart> existing,
                                            out int startRun, out string resumeOf, out bool markInvalid)
        {
            var e = new List<string>();
            startRun = 1;
            resumeOf = "";
            markInvalid = false;
            if (cfg == null) { e.Add("no S1 config"); return e; }
            foreach (var p in cfg.Validate()) e.Add("s1_supplementary.json: " + p);
            if (Array.IndexOf(S1Config.DeclaredCharacters, character ?? "") < 0) e.Add($"character '{character}' is not one of {string.Join(", ", S1Config.DeclaredCharacters)}");
            if (!S1Config.DeclaredPlanRuns.ContainsKey(setting ?? "")) e.Add($"setting '{setting}' is not one of A1, A3, B3");
            if (e.Count > 0) return e;
            var mine = new List<S1CellPart>();
            foreach (var p in existing ?? new List<S1CellPart>()) if (p.character == character && p.setting == setting) mine.Add(p);
            mine.Sort((a, b) => a.part.CompareTo(b.part));
            foreach (var p in mine)
                if (p.invalid) { e.Add($"cell {character}/{setting} is INVALID ({p.folder}: a second interruption); it is never rerun"); return e; }
            foreach (var p in mine)
                if (p.done) { e.Add($"cell {character}/{setting} was already run to the end ({p.folder}); it runs once and a repeat is never made"); return e; }
            if (mine.Count == 0)
            {
                if (resume) e.Add($"-s1Resume: cell {character}/{setting} has no earlier session to resume");
                return e;
            }
            if (mine.Count >= 2)
            {
                markInvalid = true;
                e.Add($"cell {character}/{setting} was started twice ({mine[0].folder}, {mine[1].folder}) and the second part has no end: a second interruption makes the cell INVALID; no third part");
                return e;
            }
            var first = mine[0];
            if (!resume)
            {
                e.Add($"cell {character}/{setting} was already started ({first.folder}; a crashed run counts). If the Editor, the server or the machine died before a run finished, " +
                      "resume it ONCE with -s1Resume (the interruption rule of AUDIT.md 16.30.1); otherwise it is never rerun");
                return e;
            }
            int k = 1;
            while (k <= cfg.runs_per_cell && first.outcomes.Contains(k)) k++;
            if (k > cfg.runs_per_cell) { e.Add($"-s1Resume: every run of {first.folder} has an outcome, nothing is interrupted"); return e; }
            startRun = k;
            resumeOf = first.folder;
            return e;
        }

        /// <summary>The text of a started marker. No key named setting or final_setting: no final guard ever matches it. Numbers in invariant culture.</summary>
        public static string StartedJson(S1Config cfg, string character, string setting, int[] planRuns, int part, int resumeFromRun, string resumeOf,
                                         string commit, string folder, string time)
        {
            string P = string.Join(", ", Array.ConvertAll(planRuns, r => r.ToString(CultureInfo.InvariantCulture)));
            return "{\n" +
                   $"  \"supplementary\": {Q(cfg.supplementary)},\n  \"amendment\": {Q(cfg.amendment)},\n  \"status\": \"started\",\n" +
                   $"  \"character\": {Q(character)},\n  \"s1_setting\": {Q(setting)},\n  \"plan_runs\": [{P}],\n  \"part\": {part.ToString(CultureInfo.InvariantCulture)},\n" +
                   $"  \"resume_from_run\": {resumeFromRun.ToString(CultureInfo.InvariantCulture)},\n  \"resume_of\": {Q(resumeOf)},\n" +
                   $"  \"commit\": {Q(commit)},\n  \"folder\": {Q(folder)},\n  \"time\": {Q(time)}\n}}\n";
        }

        public static string DoneJson(S1Config cfg, string character, string setting, int runs, int successes, string commit, string folder, string time) =>
            "{\n" +
            $"  \"supplementary\": {Q(cfg.supplementary)},\n  \"status\": \"done\",\n  \"character\": {Q(character)},\n  \"s1_setting\": {Q(setting)},\n" +
            $"  \"runs\": {runs.ToString(CultureInfo.InvariantCulture)},\n  \"successes\": {successes.ToString(CultureInfo.InvariantCulture)},\n" +
            $"  \"commit\": {Q(commit)},\n  \"folder\": {Q(folder)},\n  \"time\": {Q(time)}\n}}\n";

        public static string InvalidJson(S1Config cfg, string character, string setting, string reason, string time) =>
            "{\n" +
            $"  \"supplementary\": {Q(cfg.supplementary)},\n  \"status\": \"invalid\",\n  \"character\": {Q(character)},\n  \"s1_setting\": {Q(setting)},\n" +
            $"  \"reason\": {Q(reason)},\n  \"time\": {Q(time)}\n}}\n";

        /// <summary>The text of an S1 session's shader_warm_up.jsonl (Unity addendum 14, after addendum 12): one JSON line per warm-up record, as the look checks write it.</summary>
        public static string WarmUpJsonl(IEnumerable<ShaderWarmUpRecord> records)
        {
            var sb = new System.Text.StringBuilder();
            foreach (var r in records ?? new List<ShaderWarmUpRecord>()) sb.Append(JsonUtility.ToJson(r)).Append('\n');
            return sb.ToString();
        }

        /// <summary>What is wrong with an S1 session's warm-up: a cell has ONE look, so exactly one record, of the cell's character, part session, status done. Empty = fine.</summary>
        public static List<string> WarmUpProblems(IList<ShaderWarmUpRecord> records, string character)
        {
            var e = new List<string>();
            if (records == null || records.Count != 1) { e.Add($"the shader warm-up made {(records == null ? 0 : records.Count)} record(s), a cell has exactly one look ({character})"); return e; }
            var r = records[0];
            if (r.looks != character) e.Add($"the warm-up drew look '{r.looks}', the cell's character is '{character}'");
            if (r.part != ShaderWarmUpRecord.Session) e.Add($"the warm-up record has part '{r.part}', not '{ShaderWarmUpRecord.Session}'");
            if (r.status != ShaderWarmUpRecord.StatusDone) e.Add($"the warm-up of {character} ended '{r.status}', not '{ShaderWarmUpRecord.StatusDone}'");
            return e;
        }

        static string Q(string s) => "\"" + (s ?? "").Replace("\\", "\\\\").Replace("\"", "\\\"").Replace("\n", " ") + "\"";

        /// <summary>The cells under <paramref name="outputRoot"/>: every folder directly under it whose name starts with the S1 prefix and that holds a started marker.</summary>
        public static List<S1CellPart> Scan(string outputRoot, S1Config cfg)
        {
            var list = new List<S1CellPart>();
            if (string.IsNullOrEmpty(outputRoot) || !Directory.Exists(outputRoot)) return list;
            foreach (var d in Directory.GetDirectories(outputRoot))
            {
                string name = Path.GetFileName(d);
                if (!name.StartsWith(cfg.folder_prefix, StringComparison.Ordinal)) continue;
                string started = Path.Combine(d, cfg.marker_started);
                if (!File.Exists(started)) continue;
                string text = File.ReadAllText(started);
                var p = new S1CellPart
                {
                    folder = name, character = Field(text, "character"), setting = Field(text, "s1_setting"),
                    part = int.TryParse(Field(text, "part"), NumberStyles.None, CultureInfo.InvariantCulture, out int n) ? n : 1,
                    done = File.Exists(Path.Combine(d, cfg.marker_done)), invalid = File.Exists(Path.Combine(d, cfg.marker_invalid)),
                };
                foreach (var f in Directory.GetFiles(d, "truth_run*.json"))
                {
                    var m = Regex.Match(Path.GetFileName(f), @"^truth_run(\d{3})\.json$");
                    if (m.Success) p.outcomes.Add(int.Parse(m.Groups[1].Value, CultureInfo.InvariantCulture));
                }
                list.Add(p);
            }
            return list;
        }

        static string Field(string json, string key)
        {
            var m = Regex.Match(json, "\"" + Regex.Escape(key) + "\"\\s*:\\s*(?:\"([^\"]*)\"|(-?\\d+))");
            return m.Success ? (m.Groups[1].Success ? m.Groups[1].Value : m.Groups[2].Value) : "";
        }
    }
}
