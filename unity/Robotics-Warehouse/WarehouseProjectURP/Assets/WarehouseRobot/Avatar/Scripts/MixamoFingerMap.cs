using System.Collections.Generic;
using System.Linq;
using System.Text.RegularExpressions;
using UnityEngine;

namespace WarehouseAvatar
{
    /// <summary>
    /// Humanoid finger mapping of a Mixamo-rigged model by its bone names (Avatar/Config/experiments_ab.md section 12 addendum 6, declared
    /// before it was built): Unity's automatic mapping assigned Boxo v3's thumb chain to the little finger. When any mapped finger bone
    /// contradicts Mixamo's names ({Left,Right}Hand{Thumb,Index,Middle,Ring,Pinky}{1,2,3}), every finger entry is replaced by the
    /// name-based one; otherwise nothing changes.
    /// </summary>
    public static class MixamoFingerMap
    {
        static readonly Regex k_Bone = new Regex(@"^mixamorig\d*:(Left|Right)Hand(Thumb|Index|Middle|Ring|Pinky)([123])$");
        static readonly Regex k_Human = new Regex(@"^(Left|Right) (Thumb|Index|Middle|Ring|Little) (Proximal|Intermediate|Distal)$");
        static readonly string[] k_Joints = { "Proximal", "Intermediate", "Distal" };

        /// <summary>The Humanoid finger name a Mixamo bone name stands for ("Left Little Proximal"), or null.</summary>
        public static string HumanName(string bone)
        {
            var m = k_Bone.Match(bone ?? "");
            if (!m.Success) return null;
            string finger = m.Groups[2].Value == "Pinky" ? "Little" : m.Groups[2].Value;
            return $"{m.Groups[1].Value} {finger} {k_Joints[int.Parse(m.Groups[3].Value) - 1]}";
        }

        public static bool IsFinger(string humanName) => k_Human.IsMatch(humanName ?? "");

        /// <summary>
        /// The corrected mapping, or null when the model has no Mixamo finger bones or every mapped finger agrees with the names.
        /// changes lists each corrected or added entry ("Left Little Proximal: mixamorig:LeftHandThumb1 -> (removed)", ...).
        /// </summary>
        public static HumanBone[] Correct(HumanBone[] human, IEnumerable<string> skeletonBones, out List<string> changes)
        {
            changes = new List<string>();
            var expected = new Dictionary<string, string>();
            foreach (var b in skeletonBones ?? Enumerable.Empty<string>())
            {
                var h = HumanName(b);
                if (h != null && !expected.ContainsKey(h)) expected[h] = b;
            }
            if (expected.Count == 0 || human == null) return null;
            var current = human.Where(x => IsFinger(x.humanName)).ToDictionary(x => x.humanName, x => x.boneName);
            bool wrong = current.Any(kv => HumanName(kv.Value) != null && HumanName(kv.Value) != kv.Key)
                         || current.Any(kv => expected.TryGetValue(kv.Key, out var want) && want != kv.Value);
            if (!wrong) return null;
            var result = human.Where(x => !IsFinger(x.humanName)).ToList();
            foreach (var kv in expected.OrderBy(x => x.Key, System.StringComparer.Ordinal))
            {
                var hb = new HumanBone { humanName = kv.Key, boneName = kv.Value };
                hb.limit.useDefaultValues = true;
                result.Add(hb);
                current.TryGetValue(kv.Key, out var was);
                if (was != kv.Value) changes.Add($"{kv.Key}: {(string.IsNullOrEmpty(was) ? "(none)" : was)} -> {kv.Value}");
            }
            foreach (var kv in current.Where(kv => !expected.ContainsKey(kv.Key)).OrderBy(x => x.Key, System.StringComparer.Ordinal))
                changes.Add($"{kv.Key}: {kv.Value} -> (removed)");
            return result.ToArray();
        }
    }
}
