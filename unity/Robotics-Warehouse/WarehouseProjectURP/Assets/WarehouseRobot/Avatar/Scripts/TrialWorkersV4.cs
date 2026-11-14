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
        /// <summary>2026-11-12 (upgrade_design.md section 13): the robot's approach to an ask node is the last approach_m of its
        /// arrival road (= hri_control.json drive.junction_slow_radius_m), and along it every bystander must be at least
        /// nearer_margin_m farther from the robot than that node's commander stand. 0 (missing) is refused.</summary>
        public float approach_m;
        public float nearer_margin_m;
    }

    /// <summary>STOP while driving (scenario stop_while_driving, upgrade_design.md section 6).</summary>
    [Serializable]
    public class TrialStopScenario
    {
        public float[] distance_m = new float[0];
        public float[] hold_s = new float[0];
    }

    /// <summary>Assets/WarehouseRobot/Avatar/Config/trial_workers_v4.json: who stands in a v4 trial and what the commander shows.</summary>
    [Serializable]
    public class TrialWorkersConfig
    {
        public const string ScenarioDirection = "direction", ScenarioWaitThenDirection = "wait_then_direction", ScenarioStop = "stop_while_driving";

        public string data_splits = "";
        public string commander_command = "";
        /// <summary>2026-11-12 (upgrade_design.md section 2): shown instead of commander_command when goal B's branch is the
        /// node's FORWARD branch ("PROCEED"; "" = commander_command everywhere, the Phase 3 behaviour).</summary>
        public string forward_command = "";
        /// <summary>direction (default), wait_then_direction (WAIT, then the direction, at every ask) or stop_while_driving.</summary>
        public string scenario = ScenarioDirection;
        public TrialStopScenario stop = new TrialStopScenario();
        public List<string> looks = new List<string>();
        public int commander_worker_id = 1;
        public TrialBystanders bystanders = new TrialBystanders();
        public int max_active_avatars;

        public static TrialWorkersConfig Parse(string json) => JsonUtility.FromJson<TrialWorkersConfig>(json);

        public int ActiveAvatars => 1 + Math.Max(0, bystanders.count);

        /// <summary>The commands the commander may show in this session: the direction, PROCEED, and WAIT or STOP for their scenario.</summary>
        public List<string> CommanderCommands()
        {
            var list = new List<string> { commander_command };
            if (!string.IsNullOrEmpty(forward_command)) list.Add(forward_command);
            if (scenario == ScenarioWaitThenDirection) list.Add(WorkerV4Config.Wait);
            if (scenario == ScenarioStop) list.Add(WorkerV4Config.Stop);
            return list;
        }

        public List<string> Validate()
        {
            var e = new List<string>();
            if (string.IsNullOrEmpty(data_splits)) e.Add("data_splits: the path of robot_vision/configs/v4/data_splits.json is required");
            if (commander_command != WorkerV4Config.Point) e.Add("commander_command must be POINT (the direction toward B; WAIT and STOP are scenarios)");
            if (!string.IsNullOrEmpty(forward_command) && forward_command != WorkerV4Config.Proceed) e.Add("forward_command must be \"\" or PROCEED");
            if (string.IsNullOrEmpty(scenario)) scenario = ScenarioDirection;
            if (scenario != ScenarioDirection && scenario != ScenarioWaitThenDirection && scenario != ScenarioStop)
                e.Add($"scenario must be {ScenarioDirection}, {ScenarioWaitThenDirection} or {ScenarioStop}");
            if (scenario == ScenarioStop && (stop == null || stop.distance_m == null || stop.distance_m.Length != 2 || stop.hold_s == null || stop.hold_s.Length != 2 ||
                                             !(stop.distance_m[0] > 2f && stop.distance_m[0] <= stop.distance_m[1]) || !(stop.hold_s[0] > 0f && stop.hold_s[0] <= stop.hold_s[1])))
                e.Add("stop: distance_m [min, max] with 2 < min <= max and hold_s [min, max] with 0 < min <= max are required for stop_while_driving");
            if (commander_worker_id < 0) e.Add("commander_worker_id must be >= 0");
            if (bystanders == null) { e.Add("bystanders: required"); return e; }
            if (bystanders.count < 0) e.Add("bystanders.count must be >= 0");
            if (bystanders.stands == null || bystanders.count > bystanders.stands.Count) e.Add("bystanders.count is larger than the number of bystanders.stands");
            if (!(bystanders.min_road_clearance_m > 0f)) e.Add("bystanders.min_road_clearance_m must be > 0");
            if (!(bystanders.min_commander_distance_m > 0f)) e.Add("bystanders.min_commander_distance_m must be > 0");
            if (!(bystanders.approach_m > 0f)) e.Add("bystanders.approach_m must be > 0");
            if (!(bystanders.nearer_margin_m > 0f)) e.Add("bystanders.nearer_margin_m must be > 0");
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
        /// <summary>The clips the commander's commands may draw from (worker_v4.json clips of each command, in the run's split).</summary>
        public readonly List<string> AllowedClips = new List<string>();
        readonly Dictionary<string, List<string>> m_ByCommand = new Dictionary<string, List<string>>();

        /// <summary>The allowed clips of one command.</summary>
        public List<string> AllowedFor(string command) => m_ByCommand.TryGetValue(command, out var l) ? l : new List<string>();

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
            // empty = every look of the split that the Task 2 template has (2026-11-14, experiments_ab.md section 7: data_splits.json also
            // lists the experiment looks of looks_ab.json, which only the experiment mode spawns)
            var looks = cfg.looks != null && cfg.looks.Count > 0 ? new List<string>(cfg.looks) : splits.Names(true, mode).FindAll(l => workers.Look(l) != null);
            if (looks.Count == 0) { error = $"data_splits.json has no {mode} look"; return null; }
            foreach (var l in looks)
                if (workers.Look(l) == null) { error = $"look '{l}' is not in worker_v4.json"; return null; }
            var plan = new TrialRunWorkers { CommanderLook = looks[(run - 1) % looks.Count] };
            for (int k = 1; k <= cfg.bystanders.count; k++) plan.BystanderLooks.Add(looks[(run - 1 + k) % looks.Count]);
            foreach (var command in cfg.CommanderCommands())
            {
                var mine = new List<string>();
                foreach (var c in workers.ClipNames(command))
                    if (splits.Clips.TryGetValue(c, out var split) && split == mode) mine.Add(c);
                if (mine.Count == 0) { error = $"no {command} clip of worker_v4.json is a {mode} clip in data_splits.json"; return null; }
                plan.m_ByCommand[command] = mine;
                plan.AllowedClips.AddRange(mine);
            }
            plan.Split = splits.GuardRun(plan.AllLooks(), plan.AllowedClips, false, out error);
            if (plan.Split == null) { error = $"run {run}: {error}"; return null; }
            return plan;
        }

        /// <summary>
        /// Plan run <paramref name="run"/> (1-based) of a FINAL session of <paramref name="setting"/> (Stage F, upgrade_design.md
        /// section 13; B7, pending Anisha): looks from the setting's look_split (config.looks, or every look of that split), rotated
        /// per run as in development; clips: every worker_v4.json clip of each command in the setting's clip_split, which must be a
        /// final-evaluation split (test). Every look must lie in the look split and every clip in the clip split; the names must not
        /// be placeholders. Only TrialRunnerV4's final mode calls it, after the final-run guard.
        /// </summary>
        public static TrialRunWorkers PlanFinal(int run, FinalSettingV4 setting, TrialWorkersConfig cfg, WorkerV4Config workers, DataSplitsV4 splits, out string error)
        {
            error = null;
            if (setting == null) { error = "no final setting"; return null; }
            if (splits.Placeholder) { error = "the look and clip names in configs/v4/data_splits.json are still placeholders"; return null; }
            if (!splits.FinalEvaluationSplits.Contains(setting.clip_split)) { error = $"setting {setting.name}: clip_split '{setting.clip_split}' is not a final-evaluation split"; return null; }
            var looks = cfg.looks != null && cfg.looks.Count > 0 ? new List<string>(cfg.looks) : splits.Names(true, setting.look_split).FindAll(l => workers.Look(l) != null);
            if (looks.Count == 0) { error = $"data_splits.json has no {setting.look_split} look"; return null; }
            foreach (var l in looks)
            {
                if (workers.Look(l) == null) { error = $"look '{l}' is not in worker_v4.json"; return null; }
                if (!splits.Looks.TryGetValue(l, out var ls) || ls != setting.look_split) { error = $"setting {setting.name}: look '{l}' is not a {setting.look_split} look"; return null; }
            }
            var plan = new TrialRunWorkers { CommanderLook = looks[(run - 1) % looks.Count] };
            for (int k = 1; k <= cfg.bystanders.count; k++) plan.BystanderLooks.Add(looks[(run - 1 + k) % looks.Count]);
            foreach (var command in cfg.CommanderCommands())
            {
                var mine = new List<string>();
                foreach (var c in workers.ClipNames(command))
                    if (splits.Clips.TryGetValue(c, out var split) && split == setting.clip_split) mine.Add(c);
                if (mine.Count == 0) { error = $"no {command} clip of worker_v4.json is a {setting.clip_split} clip in data_splits.json"; return null; }
                plan.m_ByCommand[command] = mine;
                plan.AllowedClips.AddRange(mine);
            }
            plan.Split = $"final {setting.name}: looks {setting.look_split}, clips {setting.clip_split}";
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

        public const float ApproachStepM = 0.05f;

        /// <summary>
        /// The smallest (distance to the bystander - distance to the commander stand) over the robot's approach to an ask node:
        /// the last approachM of the road from <paramref name="arrivalFrom"/> to <paramref name="node"/>, sampled every
        /// <see cref="ApproachStepM"/> (both ends included), or the node alone when there is no arrival road (the start node).
        /// Horizontal distances. <paramref name="worst"/> is the point where it is smallest.
        /// </summary>
        public static float NearerMargin(Vector3 bystander, Vector3 commander, Vector3 node, Vector3? arrivalFrom, float approachM, out Vector3 worst)
        {
            var n = new Vector2(node.x, node.z);
            var b = new Vector2(bystander.x, bystander.z);
            var c = new Vector2(commander.x, commander.z);
            var back = Vector2.zero;
            float length = 0f;
            if (arrivalFrom.HasValue)
            {
                back = new Vector2(arrivalFrom.Value.x, arrivalFrom.Value.z) - n;
                length = Mathf.Min(Mathf.Max(0f, approachM), back.magnitude);
                back = back.sqrMagnitude > 1e-12f ? back.normalized : Vector2.zero;
            }
            int steps = Mathf.Max(0, Mathf.RoundToInt(length / ApproachStepM));
            float best = float.PositiveInfinity;
            worst = node;
            for (int i = 0; i <= steps; i++)
            {
                var q = n + back * (steps == 0 ? 0f : length * i / steps);
                float m = Vector2.Distance(q, b) - Vector2.Distance(q, c);
                if (m < best)
                {
                    best = m;
                    worst = new Vector3(q.x, node.y, q.y);
                }
            }
            return best;
        }

        /// <summary>The world direction a POINT shows for a branch: junction to the branch's next node (Python's branch yaw).</summary>
        public static Vector3 BranchDirection(Vector3 junction, Vector3 next) => Vector3.ProjectOnPlane(next - junction, Vector3.up).normalized;
    }
}
