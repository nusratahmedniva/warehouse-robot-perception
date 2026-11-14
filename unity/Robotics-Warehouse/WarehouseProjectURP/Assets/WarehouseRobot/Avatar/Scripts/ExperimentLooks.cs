using System;
using System.Collections.Generic;
using UnityEngine;

namespace WarehouseAvatar
{
    /// <summary>
    /// One look of Avatar/Config/looks_ab.json (experiments A and B and the avatar experiment, experiments_ab.md section 2): a
    /// worker_v4.json look entry plus what the experiments report about it. Extra fields are ignored where a plain LookEntry is read.
    /// </summary>
    [Serializable]
    public class ExperimentLook : LookEntry
    {
        public const string Realistic = "realistic_human", Stylised = "stylised_human", Anime = "anime", Cartoon = "cartoon_non_human", Mannequin = "mannequin";
        public static readonly string[] KindGroups = { Realistic, Stylised, Anime, Cartoon, Mannequin };

        /// <summary>realistic_human, stylised_human, anime, cartoon_non_human or mannequin.</summary>
        public string kind_group;
        /// <summary>male, female or none.</summary>
        public string gender;
        /// <summary>The person (one identity, e.g. "sunbox"); with gender and costume it makes the look's name.</summary>
        public string person;
        /// <summary>The costume and colour part of the name, e.g. "shirt_white".</summary>
        public string costume;
        /// <summary>A navigation look of Sets A and B (human-like only).</summary>
        public bool navigation;
        /// <summary>Proposed split (development or test) for Anisha's data_splits.json; "" = not a navigation look. A proposal, never read as a split.</summary>
        public string proposed_split;
        /// <summary>The licence status as checked (e.g. "Unity Asset Store EULA", "not verified: SOURCES.txt missing").</summary>
        public string licence;
    }

    [Serializable]
    public class ExperimentLookPaths
    {
        public string repo_root_relative_to_unity_project;
        /// <summary>Repository folder with the character FBX files (git-ignored downloads).</summary>
        public string characters_source;
        /// <summary>Project folder the import copies them into (git-ignored, Assets/ThirdParty/...).</summary>
        public string import_folder;
        public string output_root;
    }

    /// <summary>A recolouring rule: a material whose name contains one of the keywords gets this colour (cartoon_boxo_01).</summary>
    [Serializable]
    public class RecolourRule
    {
        public string[] keywords = new string[0];
        public float[] rgb = new float[0];
    }

    [Serializable]
    public class RecolourSpec
    {
        public string look;
        /// <summary>A material counts as colourless when it has no base texture and its base colour has a saturation below this.</summary>
        public float colourless_saturation_max;
        public RecolourRule[] rules = new RecolourRule[0];
    }

    [Serializable]
    public class ExperimentLooksFile
    {
        public string note;
        public ExperimentLookPaths paths;
        public RecolourSpec[] recolour = new RecolourSpec[0];
        /// <summary>Every look the experiments use that worker_v4.json does not define.</summary>
        public ExperimentLook[] looks = new ExperimentLook[0];
        /// <summary>The avatar experiment (look check only, no navigation runs): ids of looks_ab.json or worker_v4.json, in order.</summary>
        public string[] avatar_experiment = new string[0];
    }

    public static class ExperimentLooks
    {
        public const string AssetPath = "Assets/WarehouseRobot/Avatar/Config/looks_ab.json";

        public static ExperimentLooksFile Parse(string json)
        {
            var f = JsonUtility.FromJson<ExperimentLooksFile>(json ?? "");
            if (f == null) throw new InvalidOperationException("looks_ab.json: not a JSON object");
            f.looks = f.looks ?? new ExperimentLook[0];
            f.avatar_experiment = f.avatar_experiment ?? new string[0];
            return f;
        }

        /// <summary>The file's rules. <paramref name="baseLooks"/> = worker_v4.json's looks: an id may not be defined in both.</summary>
        public static List<string> Validate(ExperimentLooksFile f, IList<LookEntry> baseLooks)
        {
            var e = new List<string>();
            var ids = new HashSet<string>(StringComparer.Ordinal);
            var baseIds = new HashSet<string>(StringComparer.Ordinal);
            if (baseLooks != null) foreach (var b in baseLooks) if (b != null) baseIds.Add(b.id);
            foreach (var l in f.looks)
            {
                if (l == null || string.IsNullOrEmpty(l.id)) { e.Add("looks: an entry has no id"); continue; }
                if (!ids.Add(l.id)) e.Add($"looks: '{l.id}' listed twice");
                if (baseIds.Contains(l.id)) e.Add($"looks: '{l.id}' is already defined in worker_v4.json (never redefine a look)");
                if (!LookCheckConfig.IsNamePart(l.id)) e.Add($"looks '{l.id}': a-z, 0-9 and single inner '_' only");
                if (l.kind != LookEntry.KindPrefab && l.kind != LookEntry.KindSunbox) e.Add($"looks '{l.id}': kind must be prefab or sunbox");
                if (string.IsNullOrEmpty(l.asset) || !l.asset.StartsWith("Assets/", StringComparison.Ordinal)) e.Add($"looks '{l.id}': asset must start with Assets/");
                if (l.kind == LookEntry.KindSunbox && (l.sunbox == null || (l.sunbox.gender != "Male" && l.sunbox.gender != "Female")))
                    e.Add($"looks '{l.id}': sunbox.gender must be Male or Female");
                if (Array.IndexOf(ExperimentLook.KindGroups, l.kind_group) < 0) e.Add($"looks '{l.id}': kind_group must be one of {string.Join(", ", ExperimentLook.KindGroups)}");
                if (l.gender != "male" && l.gender != "female" && l.gender != "none") e.Add($"looks '{l.id}': gender must be male, female or none");
                if (l.kind == LookEntry.KindSunbox && l.gender != l.sunbox?.gender?.ToLowerInvariant()) e.Add($"looks '{l.id}': gender differs from sunbox.gender");
                if (l.navigation)
                {
                    if (l.kind_group != ExperimentLook.Realistic && l.kind_group != ExperimentLook.Stylised) e.Add($"looks '{l.id}': navigation looks are human-like only");
                    if (l.proposed_split != "development" && l.proposed_split != "test") e.Add($"looks '{l.id}': a navigation look needs proposed_split development or test");
                    string expected = $"{l.person}_{(l.gender == "male" ? "m" : "f")}_{l.costume}";
                    if (l.id != expected) e.Add($"looks '{l.id}': the name must encode person, gender and costume ('{expected}')");
                }
                else if (!string.IsNullOrEmpty(l.proposed_split)) e.Add($"looks '{l.id}': proposed_split is for navigation looks only");
            }
            var exp = new HashSet<string>(StringComparer.Ordinal);
            foreach (var id in f.avatar_experiment)
            {
                if (!exp.Add(id)) e.Add($"avatar_experiment: '{id}' listed twice");
                if (!ids.Contains(id) && !baseIds.Contains(id)) e.Add($"avatar_experiment: '{id}' is defined neither here nor in worker_v4.json");
            }
            int devM = 0, devF = 0, testM = 0, testF = 0;
            foreach (var l in f.looks)
                if (l != null && l.navigation)
                {
                    bool m = l.gender == "male";
                    if (l.proposed_split == "development") { if (m) devM++; else devF++; }
                    else if (l.proposed_split == "test") { if (m) testM++; else testF++; }
                }
            if (devM < 1 || devF < 1) e.Add("navigation looks: at least one male and one female development look");
            if (testM < 1 || testF < 1) e.Add("navigation looks: at least one male and one female look unseen until the finals (proposed_split test)");
            return e;
        }

        /// <summary>A look by id: worker_v4.json first, then looks_ab.json (null if neither has it).</summary>
        public static LookEntry Find(WorkerV4Config cfg, IList<LookEntry> extra, string id)
        {
            var l = cfg?.Look(id);
            if (l != null || extra == null) return l;
            foreach (var x in extra) if (x != null && x.id == id) return x;
            return null;
        }

        public const string SubsetArg = "-lookCheckLooks";

        /// <summary>experiments_ab.md section 5: the looks of <paramref name="looks"/> named by the command-line option -lookCheckLooks
        /// &lt;id&gt;[,&lt;id&gt;...], in the list's order; null when the option is absent or on an error (a name not in the list, no value).</summary>
        public static string[] Subset(string[] args, IList<string> looks, out string error)
        {
            error = null;
            int i = Array.IndexOf(args ?? new string[0], SubsetArg);
            if (i < 0) return null;
            if (i + 1 >= args.Length || args[i + 1].StartsWith("-", StringComparison.Ordinal)) { error = SubsetArg + " needs <id>[,<id>...]"; return null; }
            var want = new HashSet<string>(StringComparer.Ordinal);
            foreach (var part in args[i + 1].Split(',')) if (part.Trim().Length > 0) want.Add(part.Trim());
            foreach (var w in want)
                if (looks == null || !looks.Contains(w)) { error = $"{SubsetArg}: '{w}' is not in the run's look list"; return null; }
            if (want.Count == 0) { error = SubsetArg + " needs <id>[,<id>...]"; return null; }
            var keep = new List<string>();
            foreach (var l in looks) if (want.Contains(l) && !keep.Contains(l)) keep.Add(l);
            return keep.ToArray();
        }

        /// <summary>The navigation looks of one gender and proposed split, in name order (the look rotation of experiments_ab.md section 3).</summary>
        public static List<string> Navigation(ExperimentLooksFile f, string gender, string split)
        {
            var list = new List<string>();
            foreach (var l in f.looks) if (l != null && l.navigation && l.gender == gender && l.proposed_split == split) list.Add(l.id);
            list.Sort(StringComparer.Ordinal);
            return list;
        }
    }
}
