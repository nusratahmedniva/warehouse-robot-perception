using System;
using System.Collections.Generic;
using System.Globalization;
using System.Text;
using UnityEngine;

namespace WarehouseHRI.V4
{
    /// <summary>
    /// A minimal JSON reader (objects -> Dictionary&lt;string, object&gt; in file order, arrays -> List&lt;object&gt;, numbers ->
    /// double, strings, booleans, null). JsonUtility cannot read objects keyed by name, such as the nodes of
    /// robot_vision/configs/v4/roadmap.json. Throws FormatException on malformed input.
    /// </summary>
    public static class MiniJson
    {
        public static object Parse(string json)
        {
            int i = 0;
            var v = Value(json, ref i);
            Ws(json, ref i);
            if (i != json.Length) throw new FormatException($"JSON: unexpected text at {i}");
            return v;
        }

        static void Ws(string s, ref int i) { while (i < s.Length && char.IsWhiteSpace(s[i])) i++; }

        static object Value(string s, ref int i)
        {
            Ws(s, ref i);
            if (i >= s.Length) throw new FormatException("JSON: unexpected end");
            char c = s[i];
            if (c == '{')
            {
                var d = new Dictionary<string, object>();
                i++;
                Ws(s, ref i);
                if (s[i] == '}') { i++; return d; }
                while (true)
                {
                    Ws(s, ref i);
                    string k = Str(s, ref i);
                    Ws(s, ref i);
                    if (s[i++] != ':') throw new FormatException($"JSON: ':' expected at {i - 1}");
                    d[k] = Value(s, ref i);
                    Ws(s, ref i);
                    if (s[i] == ',') { i++; continue; }
                    if (s[i] == '}') { i++; return d; }
                    throw new FormatException($"JSON: ',' or '}}' expected at {i}");
                }
            }
            if (c == '[')
            {
                var l = new List<object>();
                i++;
                Ws(s, ref i);
                if (s[i] == ']') { i++; return l; }
                while (true)
                {
                    l.Add(Value(s, ref i));
                    Ws(s, ref i);
                    if (s[i] == ',') { i++; continue; }
                    if (s[i] == ']') { i++; return l; }
                    throw new FormatException($"JSON: ',' or ']' expected at {i}");
                }
            }
            if (c == '"') return Str(s, ref i);
            if (s.Length - i >= 4 && string.CompareOrdinal(s, i, "true", 0, 4) == 0) { i += 4; return true; }
            if (s.Length - i >= 5 && string.CompareOrdinal(s, i, "false", 0, 5) == 0) { i += 5; return false; }
            if (s.Length - i >= 4 && string.CompareOrdinal(s, i, "null", 0, 4) == 0) { i += 4; return null; }
            int j = i;
            while (j < s.Length && "+-0123456789.eE".IndexOf(s[j]) >= 0) j++;
            if (j == i) throw new FormatException($"JSON: value expected at {i}");
            var num = double.Parse(s.Substring(i, j - i), NumberStyles.Float, CultureInfo.InvariantCulture);
            i = j;
            return num;
        }

        static string Str(string s, ref int i)
        {
            if (s[i] != '"') throw new FormatException($"JSON: string expected at {i}");
            var sb = new StringBuilder();
            i++;
            while (s[i] != '"')
            {
                if (s[i] == '\\')
                {
                    i++;
                    char e = s[i];
                    if (e == 'u') { sb.Append((char)Convert.ToInt32(s.Substring(i + 1, 4), 16)); i += 4; }
                    else sb.Append(e == 'n' ? '\n' : e == 't' ? '\t' : e == 'r' ? '\r' : e == 'b' ? '\b' : e == 'f' ? '\f' : e);
                }
                else sb.Append(s[i]);
                i++;
            }
            i++;
            return sb.ToString();
        }
    }

    /// <summary>
    /// robot_vision/configs/v4/roadmap.json (P7, P8; Avatar/Config/upgrade_design.md section 6): the v4 map, read by the v4
    /// scene builder and the Edit Mode test that requires the scene's roadmap to equal it. Python reads the same file
    /// (hri_control_v4). Worker stands follow the roadmap rule: corner_offset_m ahead and to the right of the arrival
    /// direction (the start node: its start heading), facing the arriving robot.
    /// </summary>
    public sealed class RoadmapV4
    {
        public const string KindStart = "start", KindJunction = "junction", KindEndpoint = "endpoint";

        public sealed class NodeDef
        {
            public string Name, Kind, ArriveFrom;
            public float X, Z;
            public float StartYawDeg;
            public bool HasStartYaw;
        }

        public string Start;
        public float CornerOffsetM;
        public readonly List<NodeDef> Nodes = new List<NodeDef>();
        /// <summary>Per node, in file order: (command name, next node).</summary>
        public readonly Dictionary<string, List<KeyValuePair<string, string>>> Branches = new Dictionary<string, List<KeyValuePair<string, string>>>();

        public NodeDef Node(string name) => Nodes.Find(n => n.Name == name);

        public static RoadmapV4 Parse(string json) =>
            FromObject(MiniJson.Parse(json) as Dictionary<string, object> ?? throw new FormatException("roadmap: not an object"));

        /// <summary>A map object of the roadmap format (also the maps of configs/v4/experiments/scenarios_ab.json, 2026-11-14).</summary>
        public static RoadmapV4 FromObject(Dictionary<string, object> root)
        {
            var r = new RoadmapV4 { Start = (string)root["start"] };
            r.CornerOffsetM = (float)(double)((Dictionary<string, object>)root["worker_stand"])["corner_offset_m"];
            foreach (var kv in (Dictionary<string, object>)root["nodes"])
            {
                var n = (Dictionary<string, object>)kv.Value;
                var d = new NodeDef { Name = kv.Key, X = (float)(double)n["x"], Z = (float)(double)n["z"], Kind = (string)n["kind"] };
                if (n.TryGetValue("arrive_from", out var a)) d.ArriveFrom = (string)a;
                if (n.TryGetValue("start_yaw_deg", out var y)) { d.StartYawDeg = (float)(double)y; d.HasStartYaw = true; }
                r.Nodes.Add(d);
            }
            foreach (var kv in (Dictionary<string, object>)root["branches"])
            {
                var list = new List<KeyValuePair<string, string>>();
                foreach (var b in (Dictionary<string, object>)kv.Value) list.Add(new KeyValuePair<string, string>(b.Key, (string)b.Value));
                r.Branches[kv.Key] = list;
            }
            return r;
        }

        /// <summary>The robot's heading when it reaches the node (unit, horizontal): arrive_from -> node, or the start heading.</summary>
        public Vector3 ArrivalHeading(NodeDef n)
        {
            if (!string.IsNullOrEmpty(n.ArriveFrom))
            {
                var p = Node(n.ArriveFrom);
                return new Vector3(n.X - p.X, 0f, n.Z - p.Z).normalized;
            }
            return Quaternion.Euler(0f, n.StartYawDeg, 0f) * Vector3.forward;
        }

        /// <summary>The worker stand of a start node or junction: (position on the floor at y, rotation facing the arriving robot).</summary>
        public void Stand(NodeDef n, float y, out Vector3 position, out Quaternion rotation)
        {
            Vector3 arrive = ArrivalHeading(n);
            Vector3 right = Vector3.Cross(Vector3.up, arrive);
            position = new Vector3(n.X, y, n.Z) + (arrive + right) * CornerOffsetM;
            rotation = Quaternion.LookRotation(-arrive, Vector3.up);
        }

        /// <summary>Branch labels that do not match the geometry (the turn from the arrival heading), as "J1 LEFT -> J2".</summary>
        public List<string> LabelProblems()
        {
            var bad = new List<string>();
            foreach (var kv in Branches)
            {
                var n = Node(kv.Key);
                Vector3 arrive = ArrivalHeading(n);
                foreach (var b in kv.Value)
                {
                    var next = Node(b.Value);
                    float turn = Vector3.SignedAngle(arrive, new Vector3(next.X - n.X, 0f, next.Z - n.Z), Vector3.up);
                    if (GestureCommands.FromTurnAngle(turn).ToString() != b.Key) bad.Add($"{kv.Key} {b.Key} -> {b.Value}");
                }
            }
            return bad;
        }
    }
}
