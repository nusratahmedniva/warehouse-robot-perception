using System;
using System.Collections.Generic;
using System.Globalization;
using System.IO;
using System.Security.Cryptography;
using System.Text;
using System.Text.RegularExpressions;
using UnityEngine;

namespace WarehouseAvatar
{
    /// <summary>One final setting of final_v4.json: its workers config and the splits its looks and clips come from (B7).</summary>
    [Serializable]
    public class FinalSettingV4
    {
        public string name = "", workers_config = "", look_split = "", clip_split = "";
        /// <summary>Experiments A/B (2026-11-14, experiments_ab.md section 7): the setting's final experiment config
        /// (Avatar/Config/sessions/final_ab_&lt;setting&gt;.json, <see cref="FinalExperimentV4"/>); "" = a Task 2 setting.</summary>
        public string experiment_config = "";

        public bool IsExperiment => !string.IsNullOrEmpty(experiment_config);
    }

    /// <summary>
    /// One final setting of the experiments A/B (Avatar/Config/sessions/final_ab_&lt;setting&gt;.json; experiments_ab.md section 7): the
    /// experiment, the A2 side, the test looks and clips, and the Python control file the server must run it with. The numbers of the
    /// final (seed, runs, timeout, success radius) are not here: final_plan.json is their only source.
    /// </summary>
    [Serializable]
    public class FinalExperimentV4
    {
        public const string Corridor = "corridor", Turn = "turn", Roadmap = "roadmap";
        public static readonly string[] Sides = { "right", "left" };

        public string experiment = "", a2_side = "", lie_detection = "", python_control = "";
        public List<string> male_looks = new List<string>(), female_looks = new List<string>();
        public List<string> point_clips = new List<string>(), proceed_clips = new List<string>();

        public static FinalExperimentV4 Parse(string json) =>
            JsonUtility.FromJson<FinalExperimentV4>(json ?? "") ?? throw new FormatException("a final experiment config: not a JSON object");

        /// <summary>The final setting this config belongs to: the experiment, plus _right / _left on the turn map.</summary>
        public string SettingName => experiment + (string.IsNullOrEmpty(a2_side) ? "" : "_" + a2_side);

        /// <summary>Anisha's control file (robot_vision-relative, configs/v4/experiments/) of a map, side and lie-detection switch.</summary>
        public static string ExpectedControl(string map, string side, string detection) =>
            $"configs/v4/experiments/control_lie_{detection}{(map == Corridor ? "_a1" : map == Turn ? "_a2_" + side : "")}.json";
    }

    /// <summary>
    /// Assets/WarehouseRobot/Avatar/Config/final_v4.json (Stage F, upgrade_design.md section 13, 2026-11-13): the final settings, the
    /// Unity run-once marker and the B9 freeze list. The numbers of a final come from Python's final_plan.json (<see cref="FinalPlanV4"/>).
    /// </summary>
    [Serializable]
    public class FinalConfigV4
    {
        public const string PythonEvaluationMarker = "FINAL_DONE.json";

        public string final_plan = "", frozen = "", done_file = "", python_run_marker = "";
        public List<FinalSettingV4> settings = new List<FinalSettingV4>();
        /// <summary>The v4 Task 2 finals replaced by the experiments A/B on 2026-11-14 (experiments_ab.md section 7): kept for the record,
        /// never run.</summary>
        public List<FinalSettingV4> superseded_settings = new List<FinalSettingV4>();
        public List<string> freeze_files = new List<string>();

        public static FinalConfigV4 Parse(string json) => JsonUtility.FromJson<FinalConfigV4>(json);

        public FinalSettingV4 Setting(string name) => settings.Find(s => s.name == name);

        public FinalSettingV4 Superseded(string name) => (superseded_settings ?? new List<FinalSettingV4>()).Find(s => s.name == name);

        public List<string> Validate()
        {
            var e = new List<string>();
            if (string.IsNullOrEmpty(final_plan)) e.Add("final_plan: the path of robot_vision/configs/v4/final_plan.json is required");
            if (string.IsNullOrEmpty(frozen)) e.Add("frozen: the path of robot_vision/configs/v4/frozen.json is required");
            if (string.IsNullOrEmpty(done_file)) e.Add("done_file is required");
            else if (string.Equals(done_file, PythonEvaluationMarker, StringComparison.OrdinalIgnoreCase))
                e.Add($"done_file must not be {PythonEvaluationMarker}: Python's final_guard_v4 would take it for the setting's evaluation");
            if (string.IsNullOrEmpty(python_run_marker)) e.Add("python_run_marker is required");
            if (settings == null || settings.Count == 0) e.Add("settings: at least one is required");
            else
            {
                var seen = new HashSet<string>();
                foreach (var s in settings)
                {
                    if (string.IsNullOrEmpty(s.name) || !seen.Add(s.name)) e.Add($"settings: name '{s.name}' is empty or repeated");
                    if (string.IsNullOrEmpty(s.workers_config)) e.Add($"settings {s.name}: workers_config is required");
                    if (string.IsNullOrEmpty(s.look_split) || string.IsNullOrEmpty(s.clip_split)) e.Add($"settings {s.name}: look_split and clip_split are required");
                    if (Superseded(s.name) != null) e.Add($"settings: '{s.name}' is also listed as superseded");
                }
            }
            if (freeze_files == null || freeze_files.Count == 0) e.Add("freeze_files: the B9 list is required");
            return e;
        }
    }

    /// <summary>The values of robot_vision/configs/v4/final_plan.json a Unity final needs (Anisha's file, read only), and its blanks.</summary>
    public sealed class FinalPlanV4
    {
        /// <summary>Keys that must not be null for a final (the plan keys freeze_v4.py also requires).</summary>
        public static readonly string[] RequiredKeys =
            { "task", "final_seed", "runs_per_setting", "timeout_s", "success_radius_m", "test_assignment", "unity_files_and_guard", "acceptance_criteria" };

        public string Task = "";
        public int FinalSeed, RunsPerSetting;
        public float TimeoutS, SuccessRadiusM;
        public readonly List<string> Settings = new List<string>();
        public readonly List<string> Blanks = new List<string>();

        static readonly CultureInfo Inv = CultureInfo.InvariantCulture;

        public static FinalPlanV4 Parse(string json)
        {
            json = json ?? "";
            var p = new FinalPlanV4();
            foreach (var key in RequiredKeys)
            {
                var m = Regex.Match(json, "\"" + key + "\"\\s*:\\s*(null|\"[^\"]*\"|-?[0-9.eE+]+|\\{|\\[|true|false)");
                if (!m.Success || m.Groups[1].Value == "null") p.Blanks.Add(key);
            }
            p.Task = Str(json, "task");
            p.FinalSeed = (int)Num(json, "final_seed");
            p.RunsPerSetting = (int)Num(json, "runs_per_setting");
            p.TimeoutS = (float)Num(json, "timeout_s");
            p.SuccessRadiusM = (float)Num(json, "success_radius_m");
            var block = ObjectBlock(json, "settings");
            if (block != null)
            {
                int depth = 0;
                for (int i = 0; i < block.Length; i++)
                {
                    char c = block[i];
                    if (c == '{') depth++;
                    else if (c == '}') depth--;
                    else if (c == '"' && depth == 0)
                    {
                        var m = Regex.Match(block.Substring(i), "^\"(\\w+)\"\\s*:\\s*\\{");
                        if (m.Success) p.Settings.Add(m.Groups[1].Value);
                        int end = block.IndexOf('"', i + 1);
                        i = end < 0 ? block.Length : end;
                    }
                }
            }
            return p;
        }

        static string Str(string json, string key)
        {
            var m = Regex.Match(json, "\"" + key + "\"\\s*:\\s*\"([^\"]*)\"");
            return m.Success ? m.Groups[1].Value : "";
        }

        static double Num(string json, string key)
        {
            var m = Regex.Match(json, "\"" + key + "\"\\s*:\\s*(-?[0-9.eE+]+)");
            return m.Success && double.TryParse(m.Groups[1].Value, NumberStyles.Float, Inv, out double v) ? v : -1.0;
        }

        /// <summary>The text inside the braces of the object under key (first occurrence), or null.</summary>
        static string ObjectBlock(string json, string key)
        {
            var m = Regex.Match(json, "\"" + key + "\"\\s*:\\s*\\{");
            if (!m.Success) return null;
            int depth = 0;
            for (int i = m.Index + m.Length - 1; i < json.Length; i++)
            {
                if (json[i] == '{') depth++;
                else if (json[i] == '}' && --depth == 0) return json.Substring(m.Index + m.Length, i - m.Index - m.Length);
            }
            return null;
        }
    }

    /// <summary>
    /// The Unity final-run guard of the v4 study (B9; upgrade_design.md section 13, Stage F). Every reason a final of a setting is
    /// refused, before anything is written. Pure: the caller reads the files.
    /// </summary>
    public static class FinalGuardV4
    {
        /// <param name="sha256LfOfRepoFile">LF-normalised SHA-256 of a repository file, or null when it does not exist.</param>
        /// <param name="developmentOverride">robot_vision/configs/trials.local.json (the development trial count) exists.</param>
        public static List<string> Problems(FinalConfigV4 cfg, string setting, string finalPlanText, string frozenText,
                                            Func<string, string> sha256LfOfRepoFile, string outputRoot, bool developmentOverride)
        {
            var e = new List<string>();
            foreach (var problem in cfg.Validate()) e.Add("final_v4.json: " + problem);
            var plan = FinalPlanV4.Parse(finalPlanText);
            if (cfg.Setting(setting) == null && cfg.Superseded(setting) != null)
                e.Add($"setting '{setting}' is superseded: the v4 Task 2 finals were replaced by the experiments A/B on 2026-11-14 (experiments_ab.md section 7)");
            else if (cfg.Setting(setting) == null) e.Add($"setting '{setting}' is not in final_v4.json");
            if (!plan.Settings.Contains(setting)) e.Add($"setting '{setting}' is not in final_plan.json");
            foreach (var key in plan.Blanks) e.Add($"final_plan.json: {key} is blank");
            if (!plan.Blanks.Contains("task") && plan.Task != "Task2") e.Add($"final_plan.json: task is '{plan.Task}', the v4 runner runs Task2");
            if (!Regex.IsMatch(frozenText ?? "", "\"frozen\"\\s*:\\s*true")) e.Add("frozen.json: the v4 configs are not frozen");
            foreach (var path in cfg.freeze_files ?? new List<string>())
            {
                string now = sha256LfOfRepoFile(path);
                var rec = Regex.Match(frozenText ?? "", "\"" + Regex.Escape(path) + "\"\\s*:\\s*\"([0-9a-fA-F]{64})\"");
                if (now == null) e.Add($"freeze file {path} is missing");
                else if (!rec.Success) e.Add($"freeze file {path} is not recorded in frozen.json (B9: Anisha adds the Unity files to the freeze)");
                else if (!string.Equals(rec.Groups[1].Value, now, StringComparison.OrdinalIgnoreCase)) e.Add($"freeze file {path} changed since the freeze");
            }
            if (developmentOverride) e.Add("robot_vision/configs/trials.local.json (the development trial count) exists: remove it for a final");
            string earlier = EarlierFinal(outputRoot, setting, cfg);
            if (earlier != null) e.Add($"setting '{setting}' was already run as a final: {earlier}. Finals are run once (declare any repetition in AUDIT.md first)");
            return e;
        }

        /// <summary>
        /// Experiments A/B (experiments_ab.md section 7): every reason the final experiment config <paramref name="x"/> of setting
        /// <paramref name="s"/> is refused. <paramref name="mapOfExperiment"/>: the map of an experiment of experiments_ab_unity.json
        /// (corridor, turn or roadmap), null when unknown. Test looks and test clips only: every look a navigation look of looks_ab.json
        /// of the listed gender in the setting's look split, every clip a worker_v4.json clip of its command in the clip split, both
        /// final-evaluation splits, and the whole set passing <see cref="DataSplitsV4.GuardRun"/> as a final.
        /// </summary>
        public static List<string> ExperimentProblems(FinalSettingV4 s, FinalExperimentV4 x, Func<string, string> mapOfExperiment,
                                                      DataSplitsV4 splits, ExperimentLooksFile looks, WorkerV4Config template)
        {
            var e = new List<string>();
            string where = s != null ? s.experiment_config : "?";
            if (s == null || !s.IsExperiment) { e.Add($"setting '{s?.name}' has no experiment_config"); return e; }
            if (x == null) { e.Add($"{where}: missing or not a JSON object"); return e; }
            string map = mapOfExperiment(x.experiment ?? "");
            if (map == null) { e.Add($"{where}: experiment '{x.experiment}' is not in experiments_ab_unity.json"); return e; }
            if (map == FinalExperimentV4.Turn) { if (Array.IndexOf(FinalExperimentV4.Sides, x.a2_side) < 0) e.Add($"{where}: a2_side must be right or left on the turn map"); }
            else if (!string.IsNullOrEmpty(x.a2_side)) e.Add($"{where}: a2_side is for the turn map only (experiment {x.experiment} uses {map})");
            if (x.SettingName != s.name) e.Add($"{where}: it is the config of setting {x.SettingName}, not of {s.name}");
            if (x.lie_detection != "on" && x.lie_detection != "off") e.Add($"{where}: lie_detection must be on or off");
            else
            {
                string want = FinalExperimentV4.ExpectedControl(map, x.a2_side, x.lie_detection);
                if (x.python_control != want) e.Add($"{where}: python_control must be {want} (map {map}, lie detection {x.lie_detection})");
            }
            if (splits.Placeholder) e.Add("data_splits.json: the look and clip names are still placeholders");
            foreach (var split in new[] { s.look_split, s.clip_split })
                if (!splits.FinalEvaluationSplits.Contains(split)) e.Add($"setting {s.name}: '{split}' is not a final-evaluation split");
            var all = new List<string>();
            foreach (var (gender, ids) in new[] { ("male", x.male_looks), ("female", x.female_looks) })
            {
                if (ids == null || ids.Count == 0) { e.Add($"{where}: {gender}_looks needs at least one look"); continue; }
                foreach (var id in ids)
                {
                    var l = Array.Find(looks?.looks ?? new ExperimentLook[0], k => k != null && k.id == id);
                    if (l == null || !l.navigation) e.Add($"{where}: '{id}' is not a navigation look of looks_ab.json");
                    else if (l.gender != gender) e.Add($"{where}: '{id}' is a {l.gender} look, listed as {gender}");
                    if (!splits.Looks.TryGetValue(id, out var sp) || sp != s.look_split) e.Add($"{where}: look '{id}' is not a {s.look_split} look in data_splits.json");
                    all.Add(id);
                }
            }
            var clips = new List<string>();
            foreach (var (command, names) in new[] { (WorkerV4Config.Point, x.point_clips), (WorkerV4Config.Proceed, x.proceed_clips) })
            {
                if (names == null || names.Count == 0) { e.Add($"{where}: {command} needs at least one clip"); continue; }
                foreach (var c in names)
                {
                    if (!template.ClipNames(command).Contains(c)) e.Add($"{where}: '{c}' is not a {command} clip of worker_v4.json");
                    if (!splits.Clips.TryGetValue(c, out var sp) || sp != s.clip_split) e.Add($"{where}: clip '{c}' is not a {s.clip_split} clip in data_splits.json");
                    clips.Add(c);
                }
            }
            if (e.Count == 0 && splits.GuardRun(all, clips, true, out string guard) == null) e.Add($"{where}: {guard}");
            return e;
        }

        /// <summary>
        /// The navigation looks and the clips per command of an experiment session (experiments_ab.md sections 3 and 7). A final
        /// (<paramref name="s"/> and <paramref name="x"/> given, after <see cref="ExperimentProblems"/>): exactly the config's looks and
        /// clips. Development (<paramref name="s"/> null, <paramref name="mode"/> development): every navigation look of looks_ab.json and
        /// every worker_v4.json clip that data_splits.json puts in the development split, so a test look or clip is never offered.
        /// False with the reason when a gender or a command has nothing.
        /// </summary>
        public static bool ExperimentData(FinalSettingV4 s, FinalExperimentV4 x, string mode, DataSplitsV4 splits, ExperimentLooksFile looks,
                                          WorkerV4Config template, IEnumerable<string> commands, List<string> males, List<string> females,
                                          Dictionary<string, List<string>> clips, out string error)
        {
            error = null;
            males.Clear();
            females.Clear();
            clips.Clear();
            bool final = s != null;
            if (final && x == null) { error = $"final {s.name}: no final experiment config"; return false; }
            if (!final && mode != DataSplitsV4.Development) { error = $"an experiment outside a final runs in development mode only (mode '{mode}')"; return false; }
            if (final)
            {
                males.AddRange(x.male_looks);
                females.AddRange(x.female_looks);
            }
            else
                foreach (var l in looks.looks)
                    if (l != null && l.navigation && splits.Looks.TryGetValue(l.id, out var sp) && sp == mode)
                        (l.gender == "male" ? males : females).Add(l.id);
            males.Sort(StringComparer.Ordinal);
            females.Sort(StringComparer.Ordinal);
            if (males.Count == 0 || females.Count == 0)
            {
                error = $"no {(final ? s.look_split : mode)} navigation look of a {(males.Count == 0 ? "male" : "female")} worker" +
                        (final ? $" in {s.experiment_config}" : " in data_splits.json: Anisha adds the names (experiments_ab.md section 2) before an experiment session");
                return false;
            }
            foreach (var command in commands)
            {
                if (string.IsNullOrEmpty(command)) continue;
                var mine = new List<string>();
                if (final)
                {
                    if (command == WorkerV4Config.Point) mine.AddRange(x.point_clips);
                    else if (command == WorkerV4Config.Proceed) mine.AddRange(x.proceed_clips);
                    else { error = $"final {s.name}: an experiment worker shows POINT or PROCEED only, not {command}"; return false; }
                }
                else
                    foreach (var c in template.ClipNames(command))
                        if (splits.Clips.TryGetValue(c, out var split) && split == mode) mine.Add(c);
                if (mine.Count == 0) { error = $"no {command} clip of worker_v4.json is a {(final ? s.clip_split : mode)} clip"; return false; }
                clips[command] = mine;
            }
            return true;
        }

        /// <summary>A marker of an earlier final of this setting in any folder directly under outputRoot: Unity's done file
        /// (key final_setting) or Python's run marker (key setting). "folder/file", or null.</summary>
        public static string EarlierFinal(string outputRoot, string setting, FinalConfigV4 cfg)
        {
            if (string.IsNullOrEmpty(outputRoot) || !Directory.Exists(outputRoot)) return null;
            foreach (var d in Directory.GetDirectories(outputRoot))
            {
                foreach (var (file, key) in new[] { (cfg.done_file, "final_setting"), (cfg.python_run_marker, "setting") })
                {
                    if (string.IsNullOrEmpty(file)) continue;
                    string p = Path.Combine(d, file);
                    if (!File.Exists(p)) continue;
                    string text;
                    try { text = File.ReadAllText(p); }
                    catch (IOException) { continue; }
                    if (Regex.IsMatch(text, "\"" + key + "\"\\s*:\\s*\"" + Regex.Escape(setting) + "\""))
                        return Path.GetFileName(d) + "/" + file;
                }
            }
            return null;
        }

        /// <summary>The text of Unity's done file (no key named "setting": Python's markers never match it).</summary>
        public static string DoneJson(string setting, int runs, int successes, string commit, string folder, string written)
        {
            string Q(string s) => "\"" + (s ?? "").Replace("\\", "\\\\").Replace("\"", "\\\"") + "\"";
            return "{\n" +
                   $"  \"final_setting\": {Q(setting)},\n" +
                   $"  \"runs\": {runs.ToString(CultureInfo.InvariantCulture)},\n" +
                   $"  \"successes\": {successes.ToString(CultureInfo.InvariantCulture)},\n" +
                   $"  \"git_commit\": {Q(commit)},\n" +
                   $"  \"folder\": {Q(folder)},\n" +
                   $"  \"written\": {Q(written)},\n" +
                   "  \"note\": \"Unity's run-once marker of a completed v4 final session (upgrade_design.md section 13, Stage F). The setting cannot be run again.\"\n" +
                   "}\n";
        }

        /// <summary>SHA-256 (lower-case hex) of the bytes with CRLF read as LF, as freeze_v4.py hashes files.</summary>
        public static string Sha256Lf(byte[] bytes)
        {
            var lf = new List<byte>(bytes.Length);
            for (int i = 0; i < bytes.Length; i++)
                if (!(bytes[i] == (byte)'\r' && i + 1 < bytes.Length && bytes[i + 1] == (byte)'\n')) lf.Add(bytes[i]);
            using (var h = SHA256.Create())
            {
                var sb = new StringBuilder(64);
                foreach (byte b in h.ComputeHash(lf.ToArray())) sb.Append(b.ToString("x2"));
                return sb.ToString();
            }
        }
    }
}
