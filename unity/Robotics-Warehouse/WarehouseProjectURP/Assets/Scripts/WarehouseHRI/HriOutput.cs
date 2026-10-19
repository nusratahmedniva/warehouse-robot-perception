using System;
using System.Globalization;
using System.IO;
using System.Text;
using UnityEngine;

namespace WarehouseHRI
{
    /// <summary>
    /// Output folders and files. The output root comes from hri_config.json (output_root): a relative value is
    /// resolved against the Unity project folder in the Editor (the folder that contains Assets/) and against the
    /// player's data folder in a build. Every session writes a new timestamped folder; files are created with
    /// FileMode.CreateNew, so an existing file is never overwritten.
    /// </summary>
    public static class HriOutput
    {
        public static readonly CultureInfo Inv = CultureInfo.InvariantCulture;

        /// <summary>The folder relative output paths are resolved against.</summary>
        public static string BaseFolder => Directory.GetParent(Application.dataPath)?.FullName ?? Application.dataPath;

        public static string ResolveRoot(string outputRoot)
        {
            if (string.IsNullOrEmpty(outputRoot)) outputRoot = "outputs";
            return Path.GetFullPath(Path.IsPathRooted(outputRoot) ? outputRoot : Path.Combine(BaseFolder, outputRoot));
        }

        /// <summary>Create a new folder root/prefix_yyyyMMdd_HHmmss (suffix _2, _3 ... if that name exists).</summary>
        public static string CreateSessionFolder(string root, string prefix)
        {
            Directory.CreateDirectory(root);
            string stamp = DateTime.Now.ToString("yyyyMMdd_HHmmss", Inv);
            string path = Path.Combine(root, $"{prefix}_{stamp}");
            for (int i = 2; Directory.Exists(path); i++) path = Path.Combine(root, $"{prefix}_{stamp}_{i}");
            Directory.CreateDirectory(path);
            return path;
        }

        /// <summary>Write a new file; throws IOException if it already exists.</summary>
        public static void WriteNew(string path, string text)
        {
            using (var fs = new FileStream(path, FileMode.CreateNew, FileAccess.Write))
            using (var w = new StreamWriter(fs, new UTF8Encoding(false)))
                w.Write(text);
        }

        /// <summary>Open a new file for appending lines; throws IOException if it already exists.</summary>
        public static StreamWriter CreateNewWriter(string path)
        {
            var fs = new FileStream(path, FileMode.CreateNew, FileAccess.Write);
            return new StreamWriter(fs, new UTF8Encoding(false)) { AutoFlush = true, NewLine = "\n" };
        }

        /// <summary>SHA-256 of a text's UTF-8 bytes, lower-case hex.</summary>
        public static string Sha256(string text)
        {
            using (var sha = System.Security.Cryptography.SHA256.Create())
            {
                var bytes = sha.ComputeHash(new UTF8Encoding(false).GetBytes(text ?? ""));
                var sb = new StringBuilder(bytes.Length * 2);
                foreach (var b in bytes) sb.Append(b.ToString("x2", Inv));
                return sb.ToString();
            }
        }

        public static string F(float x, string format = "0.###") =>
            float.IsNaN(x) || float.IsInfinity(x) ? "" : x.ToString(format, Inv);

        public static string F(double x, string format = "0.###") =>
            double.IsNaN(x) || double.IsInfinity(x) ? "" : x.ToString(format, Inv);

        /// <summary>Quote a CSV field when needed.</summary>
        public static string Csv(string s)
        {
            if (s == null) return "";
            return s.IndexOfAny(new[] { ',', '"', '\n', '\r' }) >= 0 ? "\"" + s.Replace("\"", "\"\"") + "\"" : s;
        }

        /// <summary>A path relative to the output root, with forward slashes (run logs never store absolute paths).</summary>
        public static string Relative(string root, string path)
        {
            string r = Path.GetFullPath(root).TrimEnd(Path.DirectorySeparatorChar, Path.AltDirectorySeparatorChar) + Path.DirectorySeparatorChar;
            string p = Path.GetFullPath(path);
            string rel = p.StartsWith(r, StringComparison.OrdinalIgnoreCase) ? p.Substring(r.Length) : Path.GetFileName(p);
            return rel.Replace('\\', '/');
        }

        /// <summary>
        /// Commit hash and branch read from the .git folder above the project (no git process is started).
        /// Returns "unknown" when no repository is found. Whether the tree has uncommitted changes is not checked.
        /// </summary>
        public static void ReadGit(out string commit, out string branch)
        {
            commit = "unknown";
            branch = "unknown";
            try
            {
                var dir = new DirectoryInfo(BaseFolder);
                string gitDir = null;
                while (dir != null)
                {
                    string candidate = Path.Combine(dir.FullName, ".git");
                    if (Directory.Exists(candidate)) { gitDir = candidate; break; }
                    if (File.Exists(candidate))
                    {
                        string line = File.ReadAllText(candidate).Trim();
                        if (line.StartsWith("gitdir:")) gitDir = Path.GetFullPath(Path.Combine(dir.FullName, line.Substring(7).Trim()));
                        break;
                    }

                    dir = dir.Parent;
                }

                if (gitDir == null) return;
                string head = File.ReadAllText(Path.Combine(gitDir, "HEAD")).Trim();
                if (!head.StartsWith("ref:"))
                {
                    commit = head;
                    branch = "(detached)";
                    return;
                }

                string reference = head.Substring(4).Trim();
                branch = reference.StartsWith("refs/heads/") ? reference.Substring(11) : reference;
                string refFile = Path.Combine(gitDir, reference.Replace('/', Path.DirectorySeparatorChar));
                if (File.Exists(refFile))
                {
                    commit = File.ReadAllText(refFile).Trim();
                    return;
                }

                string packed = Path.Combine(gitDir, "packed-refs");
                if (!File.Exists(packed)) return;
                foreach (var l in File.ReadAllLines(packed))
                {
                    if (l.EndsWith(" " + reference)) { commit = l.Substring(0, l.IndexOf(' ')); return; }
                }
            }
            catch (Exception e)
            {
                Debug.LogWarning($"[WarehouseHRI] Could not read the git commit: {e.Message}");
            }
        }
    }
}
