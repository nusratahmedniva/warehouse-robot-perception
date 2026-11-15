using System;
using System.IO;
using UnityEditor;
using UnityEngine;

namespace WarehouseAvatar.EditorTools
{
    /// <summary>
    /// The Editor side of the avatar experiment's run-once guard (experiments_ab.md section 10 item 6, AvatarExperimentGuard): reads
    /// avatar_experiment.json, final_v4.json and frozen.json, hashes the B9 files, and refuses an official run (the config's flag on the
    /// command line) with every reason. Without the flag nothing is checked: the look checks stay engineering checks.
    /// </summary>
    public static class AvatarExperimentGate
    {
        const string RepoFromProject = "../../..";

        public static string RepoRoot => Path.GetFullPath(Path.Combine(Application.dataPath, "..", RepoFromProject));

        public static AvatarExperimentConfig Load()
        {
            var asset = AssetDatabase.LoadAssetAtPath<TextAsset>(AvatarExperimentConfig.AssetPath) ?? throw new FileNotFoundException(AvatarExperimentConfig.AssetPath);
            return AvatarExperimentConfig.Parse(asset.text);
        }

        /// <summary>The config when this run is an official avatar-experiment run (its flag is on the command line), else null.</summary>
        public static AvatarExperimentConfig Requested()
        {
            var cfg = Load();
            return AvatarExperimentGuard.Requested(Environment.GetCommandLineArgs(), cfg) ? cfg : null;
        }

        public static string OutputRoot(AvatarExperimentConfig cfg) => Path.GetFullPath(Path.Combine(RepoRoot, cfg.output_root));

        /// <summary>Throws with every reason the official run of this part is refused.</summary>
        public static void Check(AvatarExperimentConfig cfg, string part, bool subsetGiven)
        {
            var finalsAsset = AssetDatabase.LoadAssetAtPath<TextAsset>(cfg.final_config);
            var finals = finalsAsset != null ? FinalConfigV4.Parse(finalsAsset.text) : null;
            string frozenPath = finals != null && !string.IsNullOrEmpty(finals.frozen) ? Path.Combine(RepoRoot, finals.frozen) : "";
            string frozenText = frozenPath.Length > 0 && File.Exists(frozenPath) ? File.ReadAllText(frozenPath) : "";
            var problems = AvatarExperimentGuard.Problems(cfg, part, finals, frozenText,
                p => { string f = Path.Combine(RepoRoot, p); return File.Exists(f) ? FinalGuardV4.Sha256Lf(File.ReadAllBytes(f)) : null; },
                OutputRoot(cfg), subsetGiven);
            if (problems.Count > 0)
                throw new InvalidOperationException($"avatar experiment ({part}) refused:\n  " + string.Join("\n  ", problems));
        }

        /// <summary>Writes a marker into the run's folder (never overwrites).</summary>
        public static void WriteMarker(AvatarExperimentConfig cfg, string folder, bool done, string part, string commit, string status = "")
        {
            string file = Path.Combine(folder, done ? cfg.done_file : cfg.started_file);
            byte[] bytes = new System.Text.UTF8Encoding(false).GetBytes(AvatarExperimentGuard.MarkerJson(done ? "done" : "started", part, commit, Path.GetFileName(folder), AvatarExperimentGuard.Now(), status));
            using (var fs = new FileStream(file, FileMode.CreateNew, FileAccess.Write)) fs.Write(bytes, 0, bytes.Length);
        }
    }
}
