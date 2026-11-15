using System;
using System.Collections.Generic;
using System.Globalization;
using System.IO;
using System.Text.RegularExpressions;
using UnityEngine;

namespace WarehouseAvatar
{
    /// <summary>Avatar/Config/avatar_experiment.json: the run-once guard of the avatar experiment (experiments_ab.md section 10 item 6).</summary>
    [Serializable]
    public class AvatarExperimentConfig
    {
        public const string Edit = "edit", Play = "play";
        public const string AssetPath = "Assets/WarehouseRobot/Avatar/Config/avatar_experiment.json";

        public string note, flag, final_config, output_root, started_file, done_file;
        public string[] parts = new string[0];
        public bool requires_finals_done;

        public static AvatarExperimentConfig Parse(string json) =>
            JsonUtility.FromJson<AvatarExperimentConfig>(json ?? "") ?? throw new FormatException("avatar_experiment.json: not a JSON object");

        public List<string> Validate()
        {
            var e = new List<string>();
            if (string.IsNullOrEmpty(flag) || !flag.StartsWith("-", StringComparison.Ordinal)) e.Add("flag: the command-line option, e.g. -avatarExperiment");
            if (string.IsNullOrEmpty(final_config)) e.Add("final_config: the path of final_v4.json is required");
            if (string.IsNullOrEmpty(output_root)) e.Add("output_root is required");
            if (string.IsNullOrEmpty(started_file) || string.IsNullOrEmpty(done_file) || started_file == done_file) e.Add("started_file and done_file: two different names are required");
            foreach (var f in new[] { started_file, done_file })
                if (string.Equals(f, FinalConfigV4.PythonEvaluationMarker, StringComparison.OrdinalIgnoreCase) || string.Equals(f, "FINAL_RUN_DONE.json", StringComparison.OrdinalIgnoreCase))
                    e.Add($"'{f}' is a marker of Python's final guard");
            if (parts == null || Array.IndexOf(parts, Edit) < 0 || Array.IndexOf(parts, Play) < 0 || parts.Length != 2) e.Add("parts must be [\"edit\", \"play\"]");
            return e;
        }
    }

    /// <summary>
    /// The run-once guard of the avatar experiment (experiments_ab.md section 10 item 6; replaces section 8 step 6, "no code guard"). An official
    /// run (the config's flag on the command line) of a part (edit or play) is refused unless frozen.json is frozen with every B9 file recorded
    /// and unchanged, every final setting of final_v4.json has Unity's done file (section 8 precondition), no look subset is given, and no
    /// started or done marker of the same part exists in a folder directly under the output root. Pure: the caller reads the files.
    /// </summary>
    public static class AvatarExperimentGuard
    {
        public static bool Requested(string[] args, AvatarExperimentConfig cfg) => args != null && cfg != null && Array.IndexOf(args, cfg.flag) >= 0;

        public static List<string> Problems(AvatarExperimentConfig cfg, string part, FinalConfigV4 finals, string frozenText,
                                            Func<string, string> sha256LfOfRepoFile, string outputRoot, bool subsetGiven)
        {
            var e = new List<string>();
            foreach (var p in cfg.Validate()) e.Add("avatar_experiment.json: " + p);
            if (Array.IndexOf(cfg.parts ?? new string[0], part) < 0) e.Add($"part '{part}' is not edit or play");
            if (finals == null) { e.Add("final_v4.json could not be read"); return e; }
            e.AddRange(FinalGuardV4.FreezeProblems(finals, frozenText, sha256LfOfRepoFile));
            if (cfg.requires_finals_done)
                foreach (var s in finals.settings ?? new List<FinalSettingV4>())
                    if (FinalGuardV4.UnityFinalDone(outputRoot, s.name, finals) == null)
                        e.Add($"final '{s.name}' is not done (no {finals.done_file}): the avatar experiment runs after the last navigation final (section 8)");
            if (subsetGiven) e.Add($"{ExperimentLooks.SubsetArg} is refused: the avatar experiment records its whole look list");
            string earlier = Earlier(outputRoot, part, cfg);
            if (earlier != null) e.Add($"the avatar experiment's {part} part was already run: {earlier}. It runs once (a crashed run counts; declare any repetition first)");
            return e;
        }

        /// <summary>A started or done marker of this part in any folder directly under outputRoot ("folder/file"), or null.</summary>
        public static string Earlier(string outputRoot, string part, AvatarExperimentConfig cfg)
        {
            if (string.IsNullOrEmpty(outputRoot) || !Directory.Exists(outputRoot)) return null;
            foreach (var d in Directory.GetDirectories(outputRoot))
                foreach (var file in new[] { cfg.started_file, cfg.done_file })
                {
                    if (string.IsNullOrEmpty(file)) continue;
                    string p = Path.Combine(d, file);
                    if (!File.Exists(p)) continue;
                    string text;
                    try { text = File.ReadAllText(p); }
                    catch (IOException) { continue; }
                    if (Regex.IsMatch(text, "\"avatar_experiment_part\"\\s*:\\s*\"" + Regex.Escape(part) + "\"")) return Path.GetFileName(d) + "/" + file;
                }
            return null;
        }

        /// <summary>The text of a marker (started or done). No key named "setting" or "final_setting": no final guard ever matches it.</summary>
        public static string MarkerJson(string kind, string part, string commit, string folder, string written, string status = "")
        {
            string Q(string s) => "\"" + (s ?? "").Replace("\\", "\\\\").Replace("\"", "\\\"") + "\"";
            return "{\n" +
                   $"  \"avatar_experiment_part\": {Q(part)},\n" +
                   $"  \"marker\": {Q(kind)},\n" +
                   $"  \"git_commit\": {Q(commit)},\n" +
                   $"  \"folder\": {Q(folder)},\n" +
                   $"  \"written\": {Q(written)},\n" +
                   (status.Length > 0 ? $"  \"status\": {Q(status)},\n" : "") +
                   "  \"note\": \"Run-once marker of the avatar experiment (experiments_ab.md section 10 item 6). This part cannot be run again.\"\n" +
                   "}\n";
        }

        public static string Now() => DateTime.Now.ToString("yyyy-MM-dd'T'HH:mm:ss", CultureInfo.InvariantCulture);
    }
}
