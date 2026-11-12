using System;
using System.Collections.Generic;
using System.Globalization;
using System.IO;
using System.Text;
using System.Text.RegularExpressions;
using UnityEngine;

namespace WarehouseAvatar
{
    /// <summary>One line of run_###/truth.jsonl (docs/protocol_v3.md, "run_###/truth.jsonl"): one worker at one time.</summary>
    public struct TruthRow
    {
        public double TimeS;
        public int WorkerId;
        public string Look;
        public double X, Z;
        public string TrueCommand;      // POINT, WAIT, STOP, NONE
        public double PointAngleDeg;    // relative to the robot's forward axis, + = right; -1 unless POINT
        public string Arm;              // left, right, none
        public string Phase;            // idle, start_delay, gesturing, holding, returning
        public bool IsCommander;
        public string Clip;             // "" when true_command is NONE
        public bool HasAnkle;           // 2026-11-12 (P1): ankle_height_m is written only when true
        public double AnkleHeightM;     // mean height of the two ankle (foot) bones above the worker's floor
        // Extra fields (allowed by docs/protocol_v3.md, ignored by Python): the random parameters of the gesture.
        public bool HasParams;
        public double Speed, Size, StartDelayS, HoldS;
    }

    /// <summary>
    /// Format and rules of truth.jsonl. The rules are those of Python's evaluation loader (robot_vision/gesture_data.py,
    /// configs/v4/gesture_data.json) plus the Unity-side ones of CLAUDE.local.md section 3: the arm is "none" exactly when
    /// the command is NONE, and a clip name is present exactly when a command is performed (Python refuses a gesture
    /// without a clip). Python's lists are repeated here and checked against configs/v4/gesture_data.json by a test.
    /// </summary>
    public static class TruthFormat
    {
        public static readonly string[] Commands = { "POINT", "WAIT", "STOP", "PROCEED", "NONE" };   // PROCEED: 2026-11-12 (upgrade_design.md)
        public static readonly string[] Arms = { "left", "right", "none" };
        public static readonly string[] Phases = { "idle", "start_delay", "gesturing", "holding", "returning" };
        /// <summary>The keys of a line, in order (extra parameter keys follow when the worker performs a gesture).</summary>
        public static readonly string[] Keys = { "time_s", "worker_id", "look", "x", "z", "true_command", "point_angle_deg", "arm", "phase", "is_commander", "clip" };
        public static readonly string[] ParamKeys = { "speed", "size", "start_delay_s", "hold_s" };
        static readonly CultureInfo Inv = CultureInfo.InvariantCulture;

        /// <summary>The rule a single row breaks, or null.</summary>
        public static string Problem(TruthRow r)
        {
            if (double.IsNaN(r.TimeS) || double.IsInfinity(r.TimeS)) return "time_s is not a finite number";
            if (r.WorkerId < 0) return "worker_id must be >= 0";
            if (string.IsNullOrEmpty(r.Look)) return "look is empty";
            if (!LookCheckConfig.IsNamePart(r.Look)) return $"look '{r.Look}' must use a-z, 0-9 and single inner '_' only";
            if (double.IsNaN(r.X) || double.IsInfinity(r.X) || double.IsNaN(r.Z) || double.IsInfinity(r.Z)) return "x or z is not a finite number";
            if (Array.IndexOf(Commands, r.TrueCommand) < 0) return $"true_command '{r.TrueCommand}' is not one of {string.Join(", ", Commands)}";
            if (Array.IndexOf(Arms, r.Arm) < 0) return $"arm '{r.Arm}' is not one of left, right, none";
            if (Array.IndexOf(Phases, r.Phase) < 0) return $"phase '{r.Phase}' is not one of {string.Join(", ", Phases)}";
            if (double.IsNaN(r.PointAngleDeg) || double.IsInfinity(r.PointAngleDeg)) return "point_angle_deg is not a finite number";
            if (r.TrueCommand != "POINT" && r.PointAngleDeg != -1.0) return "point_angle_deg must be -1 unless true_command is POINT";
            if (r.TrueCommand == "POINT" && !(r.PointAngleDeg > -180.0 && r.PointAngleDeg <= 180.0)) return "point_angle_deg must be in (-180, 180]";
            if ((r.TrueCommand == "NONE") != (r.Arm == "none")) return "arm must be 'none' exactly when true_command is NONE";
            bool performing = r.Phase == "gesturing" || r.Phase == "holding" || r.Phase == "returning";
            if ((r.TrueCommand != "NONE") != performing) return "a command is performed exactly in the phases gesturing, holding and returning";
            if ((r.TrueCommand == "NONE") != string.IsNullOrEmpty(r.Clip)) return "clip is required exactly while a command is performed (and empty otherwise)";
            if (!string.IsNullOrEmpty(r.Clip) && !LookCheckConfig.IsNamePart(r.Clip)) return $"clip '{r.Clip}' must use a-z, 0-9 and single inner '_' only";
            if (r.HasAnkle && !(r.AnkleHeightM >= 0.0 && r.AnkleHeightM < 0.5)) return $"ankle_height_m {r.AnkleHeightM} must be in [0, 0.5)";
            return null;
        }

        /// <summary>One JSON line (no newline). Numbers in invariant culture: time_s 4 decimals, x and z 3, angle 2.</summary>
        public static string Line(TruthRow r)
        {
            var sb = new StringBuilder(256);
            sb.Append("{\"time_s\": ").Append(r.TimeS.ToString("0.0000", Inv));
            sb.Append(", \"worker_id\": ").Append(r.WorkerId.ToString(Inv));
            sb.Append(", \"look\": \"").Append(r.Look).Append('"');
            sb.Append(", \"x\": ").Append(r.X.ToString("0.000", Inv));
            sb.Append(", \"z\": ").Append(r.Z.ToString("0.000", Inv));
            sb.Append(", \"true_command\": \"").Append(r.TrueCommand).Append('"');
            sb.Append(", \"point_angle_deg\": ").Append(r.PointAngleDeg == -1.0 ? "-1" : r.PointAngleDeg.ToString("0.00", Inv));
            sb.Append(", \"arm\": \"").Append(r.Arm).Append('"');
            sb.Append(", \"phase\": \"").Append(r.Phase).Append('"');
            sb.Append(", \"is_commander\": ").Append(r.IsCommander ? "true" : "false");
            sb.Append(", \"clip\": \"").Append(r.Clip ?? "").Append('"');
            if (r.HasAnkle) sb.Append(", \"ankle_height_m\": ").Append(r.AnkleHeightM.ToString("0.0000", Inv));
            if (r.HasParams)
            {
                sb.Append(", \"speed\": ").Append(r.Speed.ToString("0.000", Inv));
                sb.Append(", \"size\": ").Append(r.Size.ToString("0.000", Inv));
                sb.Append(", \"start_delay_s\": ").Append(r.StartDelayS.ToString("0.000", Inv));
                sb.Append(", \"hold_s\": ").Append(r.HoldS.ToString("0.000", Inv));
            }
            return sb.Append('}').ToString();
        }

        /// <summary>A POINT direction relative to the robot's forward axis (+ = right, seen from above), in (-180, 180].</summary>
        public static double PointAngle(Vector3 robotForward, Vector3 pointDirection)
        {
            Vector3 f = Vector3.ProjectOnPlane(robotForward, Vector3.up), d = Vector3.ProjectOnPlane(pointDirection, Vector3.up);
            if (f.sqrMagnitude < 1e-10f || d.sqrMagnitude < 1e-10f) return double.NaN;
            double a = Vector3.SignedAngle(f, d, Vector3.up);
            if (a <= -180.0) a += 360.0;
            return a;
        }

        /// <summary>
        /// Looks and clips of the rows that robot_vision/configs/v4/data_splits.json does not list (Python refuses an
        /// unlisted name). The file maps names to splits; only its "looks" and "clips" objects are read.
        /// </summary>
        public static List<string> Unlisted(IEnumerable<string> looks, IEnumerable<string> clips, string dataSplitsJson, out bool placeholder)
        {
            placeholder = Regex.IsMatch(dataSplitsJson ?? "", "\"placeholder\"\\s*:\\s*true");
            var listedLooks = ObjectKeys(dataSplitsJson, "looks");
            var listedClips = ObjectKeys(dataSplitsJson, "clips");
            var missing = new List<string>();
            foreach (var l in looks) if (!string.IsNullOrEmpty(l) && !listedLooks.Contains(l) && !missing.Contains("look " + l)) missing.Add("look " + l);
            foreach (var c in clips) if (!string.IsNullOrEmpty(c) && !listedClips.Contains(c) && !missing.Contains("clip " + c)) missing.Add("clip " + c);
            return missing;
        }

        static HashSet<string> ObjectKeys(string json, string name)
        {
            var keys = new HashSet<string>();
            var m = Regex.Match(json ?? "", "\"" + name + "\"\\s*:\\s*\\{([^}]*)\\}");
            if (!m.Success) return keys;
            foreach (Match k in Regex.Matches(m.Groups[1].Value, "\"([^\"]+)\"\\s*:")) keys.Add(k.Groups[1].Value);
            return keys;
        }
    }

    /// <summary>
    /// Writes one truth.jsonl, created once (FileMode.CreateNew, never overwritten), one frame at a time. A frame is one
    /// line per worker at one time_s. Refuses (throws) any row or frame that breaks a rule, before anything is written:
    /// the single-row rules, time going backwards for a worker, a worker changing its look, a worker missing from a frame,
    /// or more than one commander at one time_s.
    /// </summary>
    public sealed class TruthFileWriter : IDisposable
    {
        readonly StreamWriter m_Writer;
        readonly Dictionary<int, string> m_Looks = new Dictionary<int, string>();
        readonly Dictionary<int, double> m_LastTime = new Dictionary<int, double>();
        readonly HashSet<int> m_Workers = new HashSet<int>();
        public string Path { get; }
        public int Lines { get; private set; }
        public int Frames { get; private set; }

        public TruthFileWriter(string path)
        {
            Path = path;
            m_Writer = new StreamWriter(new FileStream(path, FileMode.CreateNew, FileAccess.Write), new UTF8Encoding(false)) { NewLine = "\n" };
        }

        public void WriteFrame(IList<TruthRow> rows)
        {
            if (rows == null || rows.Count == 0) throw new ArgumentException("a frame needs one row per worker");
            int commanders = 0;
            var seen = new HashSet<int>();
            double t = rows[0].TimeS;
            foreach (var r in rows)
            {
                string p = TruthFormat.Problem(r);
                if (p != null) throw new InvalidOperationException($"truth.jsonl: worker {r.WorkerId} at {r.TimeS}: {p}");
                if (r.TimeS != t) throw new InvalidOperationException("truth.jsonl: every row of a frame has the same time_s");
                if (!seen.Add(r.WorkerId)) throw new InvalidOperationException($"truth.jsonl: worker {r.WorkerId} twice in one frame");
                if (m_Looks.TryGetValue(r.WorkerId, out var look) && look != r.Look)
                    throw new InvalidOperationException($"truth.jsonl: worker {r.WorkerId} changes its look from '{look}' to '{r.Look}'");
                if (m_LastTime.TryGetValue(r.WorkerId, out var last) && r.TimeS < last)
                    throw new InvalidOperationException($"truth.jsonl: time_s goes backwards for worker {r.WorkerId} ({last} -> {r.TimeS})");
                if (r.IsCommander) commanders++;
            }
            if (commanders > 1) throw new InvalidOperationException($"truth.jsonl: {commanders} commanders at time_s {t} (at most one)");
            if (Frames > 0 && !seen.SetEquals(m_Workers)) throw new InvalidOperationException("truth.jsonl: every frame lists the same workers (every worker in the scene)");
            if (Frames > 0 && t == m_LastTime[rows[0].WorkerId]) return;   // one frame per time_s
            foreach (var r in rows)
            {
                m_Looks[r.WorkerId] = r.Look;
                m_LastTime[r.WorkerId] = r.TimeS;
                m_Workers.Add(r.WorkerId);
                m_Writer.Write(TruthFormat.Line(r));
                m_Writer.Write('\n');
                Lines++;
            }
            Frames++;
        }

        public void Flush() => m_Writer.Flush();

        public void Dispose() => m_Writer.Dispose();
    }
}
