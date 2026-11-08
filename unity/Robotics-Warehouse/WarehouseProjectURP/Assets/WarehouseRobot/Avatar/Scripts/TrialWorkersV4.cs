using System;
using System.Collections.Generic;
using System.Text.RegularExpressions;
using UnityEngine;

namespace WarehouseAvatar
{
    /// <summary>
    /// robot_vision/configs/v4/data_splits.json, read by Unity (Anisha's file, read only). Only the flat "looks" and "clips"
    /// objects (name -> split), "final_evaluation_splits" and "placeholder" are read. <see cref="GuardRun"/> is the rule of
    /// Python's data_splits_v4.guard_run, so Unity refuses a run before it is recorded that Python would refuse after.
    /// </summary>
    public sealed class DataSplitsV4
    {
        public const string Development = "development";
        public readonly Dictionary<string, string> Looks = new Dictionary<string, string>(StringComparer.Ordinal);
        public readonly Dictionary<string, string> Clips = new Dictionary<string, string>(StringComparer.Ordinal);
        public readonly List<string> FinalEvaluationSplits = new List<string>();
        public bool Placeholder { get; private set; }

        public static DataSplitsV4 Parse(string json)
        {
            var s = new DataSplitsV4();
            json = json ?? "";
            s.Placeholder = Regex.IsMatch(json, "\"placeholder\"\\s*:\\s*true");
            ReadObject(json, "looks", s.Looks);
            ReadObject(json, "clips", s.Clips);
            var m = Regex.Match(json, "\"final_evaluation_splits\"\\s*:\\s*\\[([^\\]]*)\\]");
            if (m.Success)
                foreach (Match v in Regex.Matches(m.Groups[1].Value, "\"([^\"]+)\"")) s.FinalEvaluationSplits.Add(v.Groups[1].Value);
            return s;
        }

        static void ReadObject(string json, string name, Dictionary<string, string> into)
        {
            var m = Regex.Match(json, "\"" + name + "\"\\s*:\\s*\\{([^}]*)\\}");
            if (!m.Success) return;
            foreach (Match kv in Regex.Matches(m.Groups[1].Value, "\"([^\"]+)\"\\s*:\\s*\"([^\"]*)\"")) into[kv.Groups[1].Value] = kv.Groups[2].Value;
        }

        /// <summary>Names of one kind ("look" or "clip") in one split, in ordinal order.</summary>
        public List<string> Names(bool looks, string split)
        {
            var list = new List<string>();
            foreach (var kv in looks ? Looks : Clips) if (kv.Value == split) list.Add(kv.Key);
            list.Sort(StringComparer.Ordinal);
            return list;
        }

        /// <summary>
        /// The split of a run with these looks and clips, or null with the reason (Python's guard_run): nothing listed, an
        /// empty or unlisted name, a mix of splits, test data outside a final evaluation, a final evaluation on development
        /// data or on placeholder names are refused.
        /// </summary>
        public string GuardRun(IEnumerable<string> looks, IEnumerable<string> clips, bool finalEvaluation, out string error)
        {
            error = null;
            var lk = Sorted(looks);
            var cl = Sorted(clips);
            if (lk.Count == 0) { error = "no avatar look given: the split of a run cannot be checked without it"; return null; }
            var found = new SortedDictionary<string, List<string>>(StringComparer.Ordinal);
            foreach (var (kind, names, table) in new[] { ("look", lk, Looks), ("clip", cl, Clips) })
                foreach (var name in names)
                {
                    if (name == "") { error = "a gesture has no animation clip name (clip is empty): its split is unknown"; return null; }
                    if (!table.TryGetValue(name, out var split)) { error = $"{kind} '{name}' is not listed in configs/v4/data_splits.json (unknown is never assumed to be development)"; return null; }
                    if (!found.TryGetValue(split, out var items)) found[split] = items = new List<string>();
                    items.Add(kind + " " + name);
                }
            if (found.Count > 1)
            {
                var parts = new List<string>();
                foreach (var kv in found) parts.Add(kv.Key + ": " + string.Join(", ", kv.Value));
                error = "run mixes development and test data: " + string.Join("; ", parts);
                return null;
            }
            string only = null;
            foreach (var k in found.Keys) only = k;
            bool test = FinalEvaluationSplits.Contains(only);
            if (test && !finalEvaluation) { error = $"the run uses test data ({string.Join(", ", found[only])}): refused outside the final runs"; return null; }
            if (finalEvaluation && !test) { error = $"a final run must use test data, but the run uses {only} data ({string.Join(", ", found[only])})"; return null; }
            if (finalEvaluation && Placeholder) { error = "the look and clip names in configs/v4/data_splits.json are still placeholders"; return null; }
            return only;
        }

        static List<string> Sorted(IEnumerable<string> names)
        {
            var set = new SortedSet<string>(StringComparer.Ordinal);
            if (names != null) foreach (var n in names) set.Add(n ?? "");
            return new List<string>(set);
        }
    }

    /// <summary>One bystander stand: a junction and an offset in that junction's arrival frame (as the roadmap's worker stand).</summary>
    [Serializable]
    public class BystanderStand
    {
        public string junction = "";
        public float ahead_m, right_m;
    }

    [Serializable]
    public class TrialBystanders
    {
        public int count;
        public List<BystanderStand> stands = new List<BystanderStand>();
        public float min_road_clearance_m = 1.5f;
        public float min_commander_distance_m = 2.5f;
    }

    /// <summary>Assets/WarehouseRobot/Avatar/Config/trial_workers_v4.json: who stands in a v4 trial and what the commander shows.</summary>
    [Serializable]
    public class TrialWorkersConfig
    {
        public string data_splits = "";
        public string commander_command = "";
        public List<string> looks = new List<string>();
        public int commander_worker_id = 1;
        public TrialBystanders bystanders = new TrialBystanders();
        public int max_active_avatars;

        public static TrialWorkersConfig Parse(string json) => JsonUtility.FromJson<TrialWorkersConfig>(json);

        public int ActiveAvatars => 1 + Math.Max(0, bystanders.count);

        public List<string> Validate()
        {
            var e = new List<string>();
            if (string.IsNullOrEmpty(data_splits)) e.Add("data_splits: the path of robot_vision/configs/v4/data_splits.json is required");
            if (commander_command != WorkerV4Config.Point) e.Add("commander_command must be POINT (WAIT and STOP scripts are Phase 3B)");
            if (commander_worker_id < 0) e.Add("commander_worker_id must be >= 0");
            if (bystanders == null) { e.Add("bystanders: required"); return e; }
            if (bystanders.count < 0) e.Add("bystanders.count must be >= 0");
            if (bystanders.stands == null || bystanders.count > bystanders.stands.Count) e.Add("bystanders.count is larger than the number of bystanders.stands");
            if (!(bystanders.min_road_clearance_m > 0f)) e.Add("bystanders.min_road_clearance_m must be > 0");
            if (!(bystanders.min_commander_distance_m > 0f)) e.Add("bystanders.min_commander_distance_m must be > 0");
            if (max_active_avatars < 1) e.Add("max_active_avatars must be >= 1");
            else if (ActiveAvatars > max_active_avatars) e.Add($"1 commander + {bystanders.count} bystanders = {ActiveAvatars} avatars, more than max_active_avatars {max_active_avatars}");
            return e;
        }
    }

    /// <summary>The workers of one run: the commander's look, each bystander's look and the clips a gesture may use.</summary>
    public sealed class TrialRunWorkers
    {
        public string Split;
        public string CommanderLook;
        public readonly List<string> BystanderLooks = new List<string>();
        /// <summary>The clips the commander's command may draw from (worker_v4.json clips of the command, in the run's split).</summary>
        public readonly List<string> AllowedClips = new List<string>();

        public IEnumerable<string> AllLooks()
        {
            yield return CommanderLook;
            foreach (var l in BystanderLooks) yield return l;
        }

        /// <summary>
        /// Plan run <paramref name="run"/> (1-based) of a session in <paramref name="mode"/>. Looks: config.looks, or every
        /// look of the mode's split when empty, rotated per run (commander looks[(run - 1) mod n], bystander k
        /// looks[(run - 1 + k) mod n]). Clips: every worker_v4.json clip of the commander's command that lies in the split.
        /// The whole plan is then checked by <see cref="DataSplitsV4.GuardRun"/>; null with the reason if anything is refused.
        /// </summary>
        public static TrialRunWorkers Plan(int run, string mode, TrialWorkersConfig cfg, WorkerV4Config workers, DataSplitsV4 splits, out string error)
        {
            error = null;
            if (mode != DataSplitsV4.Development) { error = $"mode '{mode}': the v4 trial workers run in development mode only (the final-run guard is Phase 4)"; return null; }
            var looks = cfg.looks != null && cfg.looks.Count > 0 ? new List<string>(cfg.looks) : splits.Names(true, mode);
            if (looks.Count == 0) { error = $"data_splits.json has no {mode} look"; return null; }
            foreach (var l in looks)
                if (workers.Look(l) == null) { error = $"look '{l}' is not in worker_v4.json"; return null; }
            var plan = new TrialRunWorkers { CommanderLook = looks[(run - 1) % looks.Count] };
            for (int k = 1; k <= cfg.bystanders.count; k++) plan.BystanderLooks.Add(looks[(run - 1 + k) % looks.Count]);
            foreach (var c in workers.ClipNames(cfg.commander_command))
                if (splits.Clips.TryGetValue(c, out var split) && split == mode) plan.AllowedClips.Add(c);
            if (plan.AllowedClips.Count == 0) { error = $"no {cfg.commander_command} clip of worker_v4.json is a {mode} clip in data_splits.json"; return null; }
            plan.Split = splits.GuardRun(plan.AllLooks(), plan.AllowedClips, false, out error);
            if (plan.Split == null) { error = $"run {run}: {error}"; return null; }
            return plan;
        }
    }

    /// <summary>
    /// Watches the screen text of Python's commands for the question (worker_v4.json question.prompt, "Which direction?",
    /// possibly followed by " (asking again)"). An ask starts when the question appears or its text changes (a re-ask);
    /// <see cref="Ask"/> counts them.
    /// </summary>
    public sealed class QuestionWatch
    {
        readonly string m_Prompt;
        string m_Last = "";
        public bool Visible { get; private set; }
        public int Ask { get; private set; }

        public QuestionWatch(string prompt) => m_Prompt = prompt ?? "";

        /// <summary>The screen text of the current command; true when a new ask starts with it.</summary>
        public bool Update(string screenText)
        {
            bool visible = m_Prompt.Length > 0 && screenText != null && screenText.StartsWith(m_Prompt, StringComparison.Ordinal);
            bool started = visible && (!Visible || screenText != m_Last);
            if (started) Ask++;
            Visible = visible;
            m_Last = visible ? screenText : "";
            return started;
        }

        public void Reset()
        {
            Visible = false;
            m_Last = "";
        }
    }

    /// <summary>Plane geometry of the trial workers (x, z on the floor).</summary>
    public static class TrialWorkerGeometry
    {
        /// <summary>A stand ahead_m along the arrival direction and right_m to its right (seen from above, Unity yaw).</summary>
        public static Vector3 Stand(Vector3 junction, Vector3 arrivalDirection, float aheadM, float rightM)
        {
            var f = Vector3.ProjectOnPlane(arrivalDirection, Vector3.up).normalized;
            var r = Vector3.Cross(Vector3.up, f);
            return junction + f * aheadM + r * rightM;
        }

        /// <summary>Horizontal distance from p to the segment a-b.</summary>
        public static float SegmentDistance(Vector3 p, Vector3 a, Vector3 b)
        {
            var p2 = new Vector2(p.x, p.z);
            var a2 = new Vector2(a.x, a.z);
            var ab = new Vector2(b.x, b.z) - a2;
            float t = ab.sqrMagnitude > 1e-12f ? Mathf.Clamp01(Vector2.Dot(p2 - a2, ab) / ab.sqrMagnitude) : 0f;
            return Vector2.Distance(p2, a2 + t * ab);
        }

        /// <summary>The world direction a POINT shows for a branch: junction to the branch's next node (Python's branch yaw).</summary>
        public static Vector3 BranchDirection(Vector3 junction, Vector3 next) => Vector3.ProjectOnPlane(next - junction, Vector3.up).normalized;
    }
}
