using System;
using System.IO;
using System.Security.Cryptography;
using System.Text;

namespace WarehouseHRI
{
    /// <summary>
    /// Checks made before a final trial session (used by WarehouseRobot.Scenario.TrialRunner). Each task's final runs
    /// once: it is refused only if a trials_final_&lt;same task&gt;_* folder holds FINAL_DONE.json, so the Task 2 final
    /// does not block the Task 1 final. The pose weights must have the sha256 recorded in configs/hri_frozen.json.
    /// Replication mode (2026-10-22, AUDIT.md section 11): a declared rerun of a task's final, with the final seed,
    /// the full trial count and the same frozen checks as a final; it writes trials_replication_&lt;task&gt;_&lt;time&gt;/ and
    /// runs once per task (REPLICATION_DONE.json). It never writes or checks FINAL_DONE.json, so it neither replaces
    /// nor blocks a final.
    /// </summary>
    public static class FinalRunGuard
    {
        public const string DoneFile = "FINAL_DONE.json";
        public const string ReplicationDoneFile = "REPLICATION_DONE.json";
        public const string Development = "development", Final = "final", Replication = "replication";

        /// <summary>The mode in lower case, or null if it is not development, final or replication.</summary>
        public static string Mode(string mode)
        {
            foreach (var m in new[] { Development, Final, Replication })
                if (string.Equals(mode, m, StringComparison.OrdinalIgnoreCase)) return m;
            return null;
        }

        /// <summary>Final and replication: final seed, frozen configs and pose weights checked, run once per task.</summary>
        public static bool FinalRules(string mode) => Mode(mode) == Final || Mode(mode) == Replication;

        /// <summary>The run-once marker a completed session of this mode writes, or null (development).</summary>
        public static string DoneFileFor(string mode) =>
            Mode(mode) == Final ? DoneFile : Mode(mode) == Replication ? ReplicationDoneFile : null;

        /// <summary>Folder name of an earlier completed final of this task under outputRoot, or null.</summary>
        public static string EarlierFinal(string outputRoot, string task) => EarlierRun(outputRoot, Final, task);

        /// <summary>Folder name of an earlier completed replication of this task under outputRoot, or null.</summary>
        public static string EarlierReplication(string outputRoot, string task) => EarlierRun(outputRoot, Replication, task);

        /// <summary>
        /// Folder name of an earlier completed session of this mode (final or replication) and task under outputRoot:
        /// a trials_&lt;mode&gt;_&lt;same task&gt;_* folder holding that mode's done file. Null if none.
        /// </summary>
        public static string EarlierRun(string outputRoot, string mode, string task)
        {
            if (string.IsNullOrEmpty(task)) throw new ArgumentException("task is empty", nameof(task));
            string done = DoneFileFor(mode);
            if (done == null) throw new ArgumentException("only final and replication run once: " + mode, nameof(mode));
            if (!Directory.Exists(outputRoot)) return null;
            string prefix = "trials_" + Mode(mode) + "_" + task + "_";
            foreach (var d in Directory.GetDirectories(outputRoot, "trials_" + Mode(mode) + "_*"))
            {
                string name = Path.GetFileName(d);
                if (name.StartsWith(prefix, StringComparison.OrdinalIgnoreCase) && File.Exists(Path.Combine(d, done)))
                    return name;
            }
            return null;
        }

        public static string Sha256File(string path)
        {
            using (var s = File.OpenRead(path))
            using (var h = SHA256.Create())
            {
                var sb = new StringBuilder(64);
                foreach (byte b in h.ComputeHash(s)) sb.Append(b.ToString("x2"));
                return sb.ToString();
            }
        }

        /// <summary>sha256 of a text file with CRLF read as LF, as the config hashes in hri_frozen.json are taken.</summary>
        public static string Sha256TextLf(string path)
        {
            var bytes = File.ReadAllBytes(path);
            var lf = new System.Collections.Generic.List<byte>(bytes.Length);
            for (int i = 0; i < bytes.Length; i++)
                if (!(bytes[i] == (byte)'\r' && i + 1 < bytes.Length && bytes[i + 1] == (byte)'\n')) lf.Add(bytes[i]);
            using (var h = SHA256.Create())
            {
                var sb = new StringBuilder(64);
                foreach (byte b in h.ComputeHash(lf.ToArray())) sb.Append(b.ToString("x2"));
                return sb.ToString();
            }
        }

        /// <summary>Null when the file exists and has the expected sha256; otherwise the reason to refuse.</summary>
        public static string WeightsProblem(string path, string expectedSha256)
        {
            if (string.IsNullOrEmpty(expectedSha256)) return "no pose weights sha256 recorded in configs/hri_frozen.json";
            if (!File.Exists(path)) return path + " not found";
            string got = Sha256File(path);
            return string.Equals(got, expectedSha256, StringComparison.OrdinalIgnoreCase)
                ? null
                : $"{Path.GetFileName(path)} has sha256 {got}, not the recorded {expectedSha256}";
        }
    }
}
