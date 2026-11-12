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
        public List<string> freeze_files = new List<string>();

        public static FinalConfigV4 Parse(string json) => JsonUtility.FromJson<FinalConfigV4>(json);

        public FinalSettingV4 Setting(string name) => settings.Find(s => s.name == name);

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
            if (cfg.Setting(setting) == null) e.Add($"setting '{setting}' is not in final_v4.json");
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
