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
    /// </summary>
    public static class FinalRunGuard
    {
        public const string DoneFile = "FINAL_DONE.json";

        /// <summary>Folder name of an earlier completed final of this task under outputRoot, or null.</summary>
        public static string EarlierFinal(string outputRoot, string task)
        {
            if (string.IsNullOrEmpty(task)) throw new ArgumentException("task is empty", nameof(task));
            if (!Directory.Exists(outputRoot)) return null;
            string prefix = "trials_final_" + task + "_";
            foreach (var d in Directory.GetDirectories(outputRoot, "trials_final_*"))
            {
                string name = Path.GetFileName(d);
                if (name.StartsWith(prefix, StringComparison.OrdinalIgnoreCase) && File.Exists(Path.Combine(d, DoneFile)))
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
