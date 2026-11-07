using System;
using System.Collections.Generic;
using System.Globalization;
using System.Text;
using UnityEngine;

namespace WarehouseAvatar
{
    /// <summary>
    /// Assets/WarehouseRobot/Avatar/Config/look_check.json (v4 Phase 2A look check). The recordings follow
    /// docs/look_check_v4.md (Anisha's look_check_v4.py reads them). Parse() throws on a file JsonUtility cannot read;
    /// Validate() lists every missing or invalid value (a missing key reads as 0 or empty).
    /// </summary>
    [Serializable]
    public class LookCheckConfig
    {
        public const string Point = "POINT", Wait = "WAIT", Stop = "STOP", None = "NONE";
        public static readonly string[] RequiredCommands = { Point, Wait, Stop };
        public static readonly CultureInfo Inv = CultureInfo.InvariantCulture;

        public string note;
        public LookCheckPaths paths;
        public LookCheckRecording recording;
        public LookCommand[] commands;
        public LookCheckRender render;
        public LookCheckHand hand;
        public LookEntry[] looks;

        public static LookCheckConfig Parse(string json)
        {
            var c = JsonUtility.FromJson<LookCheckConfig>(json);
            if (c == null) throw new InvalidOperationException("look_check.json: not a JSON object");
            return c;
        }

        public List<string> Validate()
        {
            var e = new List<string>();
            if (paths == null || string.IsNullOrEmpty(paths.repo_root_relative_to_unity_project) || string.IsNullOrEmpty(paths.output_root) ||
                string.IsNullOrEmpty(paths.output_prefix) || string.IsNullOrEmpty(paths.robot_unity_config))
                e.Add("paths: repo_root_relative_to_unity_project, output_root, output_prefix and robot_unity_config are required");
            ValidateRecording(e);
            ValidateCommands(e);
            if (render == null) e.Add("render: missing");
            else
            {
                if (!(render.backdrop_behind_person_m > 0f)) e.Add("render.backdrop_behind_person_m must be > 0");
                if (!(render.floor_half_size_m > 0f)) e.Add("render.floor_half_size_m must be > 0");
                if (render.light_euler_deg == null || render.light_euler_deg.Length != 3) e.Add("render.light_euler_deg: three angles required");
                if (render.magenta_tolerance < 0 || render.magenta_tolerance > 127) e.Add("render.magenta_tolerance must be in 0..127");
            }
            if (hand == null) e.Add("hand: missing");
            else if (!(hand.fist_curl_deg > 0f) || !(hand.fist_thumb_curl_deg >= 0f) || hand.relaxed_curl_deg < 0f || hand.relaxed_thumb_curl_deg < 0f ||
                     hand.rest_outward < 0f)
                e.Add("hand: fist_curl_deg must be > 0 and the other angles and rest_outward >= 0");
            if (looks == null || looks.Length == 0) e.Add("looks: empty");
            else
            {
                var ids = new HashSet<string>();
                foreach (var l in looks)
                {
                    if (l == null || string.IsNullOrEmpty(l.id)) { e.Add("looks: an entry has no id"); continue; }
                    if (!ids.Add(l.id)) e.Add($"looks: id '{l.id}' listed twice");
                    if (!IsNamePart(l.id)) e.Add($"looks: id '{l.id}' must use a-z, 0-9 and single inner '_' only (it is the <look> part of the recording names)");
                    if (l.kind != LookEntry.KindPrefab && l.kind != LookEntry.KindSunbox)
                        e.Add($"looks '{l.id}': kind must be '{LookEntry.KindPrefab}' or '{LookEntry.KindSunbox}'");
                    if (string.IsNullOrEmpty(l.asset) || !l.asset.StartsWith("Assets/", StringComparison.Ordinal))
                        e.Add($"looks '{l.id}': asset must be a project path starting with Assets/");
                    if (l.role != LookEntry.RoleCandidate && l.role != LookEntry.RolePipelineTest)
                        e.Add($"looks '{l.id}': role must be '{LookEntry.RoleCandidate}' or '{LookEntry.RolePipelineTest}'");
                    if (l.kind == LookEntry.KindSunbox && (l.sunbox == null || (l.sunbox.gender != "Male" && l.sunbox.gender != "Female")))
                        e.Add($"looks '{l.id}': sunbox.gender must be Male or Female");
                }
            }
            return e;
        }

        void ValidateRecording(List<string> e)
        {
            var r = recording;
            if (r == null) { e.Add("recording: missing"); return; }
            if (string.IsNullOrEmpty(r.folder_name) || !IsNamePart(r.folder_name)) e.Add("recording.folder_name: a-z, 0-9 and '_' only");
            if (r.distances_m == null || r.distances_m.Length == 0) e.Add("recording.distances_m: empty");
            else foreach (var d in r.distances_m) if (!(d > 0f)) e.Add("recording.distances_m: every distance must be > 0");
            if (!(r.vertical_fov_deg > 0f && r.vertical_fov_deg < 180f)) e.Add("recording.vertical_fov_deg must be in (0, 180)");
            if (r.sequence_frames < 10 || r.sequence_frames > 20) e.Add("recording.sequence_frames: docs/look_check_v4.md accepts 10 to 20 frames");
            if (r.arms == null || r.arms.Length != 2 || Array.IndexOf(r.arms, "left") < 0 || Array.IndexOf(r.arms, "right") < 0)
                e.Add("recording.arms must be [\"left\", \"right\"] (the person's own arms)");
        }

        void ValidateCommands(List<string> e)
        {
            if (commands == null || commands.Length == 0) { e.Add("commands: empty"); return; }
            var seen = new HashSet<string>();
            foreach (var c in commands)
            {
                if (c == null || (c.command != Point && c.command != Wait && c.command != Stop && c.command != None))
                {
                    e.Add($"commands: unknown command '{c?.command}' (POINT, WAIT, STOP, NONE; capitals)");
                    continue;
                }
                if (!seen.Add(c.command)) e.Add($"commands: {c.command} listed twice");
                if (c.arm_labelled != (c.command != None)) e.Add($"commands {c.command}: arm_labelled must be {(c.command != None ? "true" : "false")}");
                if (c.variants == null || c.variants.Length == 0) { e.Add($"commands {c.command}: no variants"); continue; }
                var takes = new HashSet<string>();
                int sequences = 0;
                bool sideways = false, front45 = false;
                foreach (var v in c.variants)
                {
                    if (v == null || !IsNamePart(v.take)) { e.Add($"commands {c.command}: take '{v?.take}' must use a-z, 0-9 and single inner '_' only"); continue; }
                    if (!takes.Add(v.take)) e.Add($"commands {c.command}: take '{v.take}' listed twice");
                    if (v.azimuth_front_deg < 0f || v.azimuth_front_deg > 90f) e.Add($"commands {c.command} {v.take}: azimuth_front_deg must be in 0..90");
                    if (v.elevation_deg < -90f || v.elevation_deg > 90f) e.Add($"commands {c.command} {v.take}: elevation_deg must be in -90..90");
                    if (c.command == Wait && !v.forearm_up) e.Add($"commands WAIT {v.take}: forearm_up must be true (forearm vertical)");
                    if ((c.command == Point || c.command == None) && v.forearm_up) e.Add($"commands {c.command} {v.take}: forearm_up must be false (straight arm)");
                    if (c.command == Stop && !(v.spread_deg > 0f)) e.Add($"commands STOP {v.take}: spread_deg must be > 0 (fingers spread)");
                    if (v.sequence)
                    {
                        sequences++;
                        sideways |= Mathf.Abs(v.azimuth_front_deg) < 1e-3f;
                        front45 |= Mathf.Abs(v.azimuth_front_deg - 45f) <= 10f;
                    }
                }
                if (sequences < 2) e.Add($"commands {c.command}: at least 2 sequence takes per command, distance and arm (docs/look_check_v4.md)");
                if (c.command == Point && !(sideways && front45))
                    e.Add("commands POINT: one sequence sideways in the image plane (azimuth 0) and one about 45 deg toward the front are required");
            }
            foreach (var r in RequiredCommands) if (!seen.Contains(r)) e.Add($"commands: {r} is required");
        }

        /// <summary>a-z and 0-9, single '_' only between characters (never "__", which separates the parts of a recording name).</summary>
        public static bool IsNamePart(string s)
        {
            if (string.IsNullOrEmpty(s) || s[0] == '_' || s[s.Length - 1] == '_' || s.Contains("__")) return false;
            foreach (char ch in s)
                if (!((ch >= 'a' && ch <= 'z') || (ch >= '0' && ch <= '9') || ch == '_')) return false;
            return true;
        }

        /// <summary>
        /// docs/look_check_v4.md: &lt;look&gt;__&lt;COMMAND&gt;__&lt;distance_m&gt;__&lt;take&gt;, e.g. "sunbox_m1__WAIT__2.0__left_seq1". The arm is
        /// not part of the format, so a labelled recording's take starts with it; NONE has no arm. Invariant culture.
        /// </summary>
        public static string RecordingName(string look, string command, float distanceM, string arm, string take) =>
            $"{look}__{command}__{distanceM.ToString("0.0", Inv)}__{(string.IsNullOrEmpty(arm) ? take : arm + "_" + take)}";

        /// <summary>Frame file stem inside a sequence folder: frame_000, frame_001, ...</summary>
        public static string FrameStem(int index) => "frame_" + index.ToString("000", Inv);

        /// <summary>
        /// The header JSON next to every PNG (docs/look_check_v4.md): the bridge's frame_pan_tilt header fields of protocol 3
        /// (docs/protocol_v3.md section 2) for this render, plus "arm" (the person's own gesturing arm) when given and the
        /// pose variant (ignored by the tool). time_s is left out: an Edit Mode render has no Unity Time.time.
        /// </summary>
        public static string HeaderJson(int width, int height, double fovDeg, float cameraHeightM, int frameIndex, string arm, LookVariant v)
        {
            Intrinsics(width, height, fovDeg, out double fx, out double fy, out double cx, out double cy);
            string N(double x) => x.ToString("R", Inv);
            string F(float x) => x.ToString("R", Inv);   // config floats as written (1.2, not 1.2000000476837158)
            var sb = new StringBuilder();
            sb.Append("{\n");
            sb.Append("  \"version\": 3,\n  \"type\": \"frame_pan_tilt\",\n");
            sb.Append($"  \"frame_index\": {frameIndex.ToString(Inv)},\n");
            sb.Append($"  \"width\": {width.ToString(Inv)},\n  \"height\": {height.ToString(Inv)},\n");
            sb.Append($"  \"fx\": {N(fx)},\n  \"fy\": {N(fy)},\n  \"cx\": {N(cx)},\n  \"cy\": {N(cy)},\n");
            sb.Append($"  \"vertical_fov_deg\": {N(fovDeg)},\n");
            sb.Append("  \"pan_deg\": 0.0,\n  \"tilt_deg\": 0.0,\n");
            sb.Append($"  \"camera_height_m\": {F(cameraHeightM)},\n");
            sb.Append("  \"pose\": {\"x\": 0.0, \"z\": 0.0, \"yaw_deg\": 0.0},\n");
            sb.Append("  \"encoding\": \"png\",\n");
            if (!string.IsNullOrEmpty(arm)) sb.Append($"  \"arm\": \"{arm}\",\n");
            sb.Append($"  \"look_check_variant\": {{\"take\": \"{v.take}\", \"azimuth_front_deg\": {F(v.azimuth_front_deg)}, " +
                      $"\"elevation_deg\": {F(v.elevation_deg)}, \"forearm_up\": {(v.forearm_up ? "true" : "false")}, \"spread_deg\": {F(v.spread_deg)}}}\n");
            sb.Append("}\n");
            return sb.ToString();
        }

        /// <summary>
        /// Pinhole intrinsics of a frame rendered with vertical field of view fovDeg (docs/protocol_v3.md, frame_pan_tilt):
        /// fy = (height / 2) / tan(fov / 2), fx = fy, cx = width / 2, cy = height / 2. Computed in double.
        /// </summary>
        public static void Intrinsics(int width, int height, double fovDeg, out double fx, out double fy, out double cx, out double cy)
        {
            fy = 0.5 * height / Math.Tan(0.5 * fovDeg * Math.PI / 180.0);
            fx = fy;
            cx = 0.5 * width;
            cy = 0.5 * height;
        }
    }

    [Serializable]
    public class LookCheckPaths
    {
        public string repo_root_relative_to_unity_project;
        public string output_root;
        public string output_prefix;
        public string robot_unity_config;
    }

    [Serializable]
    public class LookCheckRecording
    {
        public string folder_name;
        public float[] distances_m;
        public float vertical_fov_deg;
        public int sequence_frames;
        public string[] arms;
    }

    [Serializable]
    public class LookCommand
    {
        public string command;
        public bool arm_labelled;
        public LookVariant[] variants;
    }

    /// <summary>One held pose. Directions in the worker's body frame: see look_check.json commands_note.</summary>
    [Serializable]
    public class LookVariant
    {
        public string take;
        public bool sequence;
        public float azimuth_front_deg;
        public float elevation_deg;
        public bool forearm_up;
        public float spread_deg;
    }

    [Serializable]
    public class LookCheckRender
    {
        public float backdrop_behind_person_m;
        public float floor_half_size_m;
        public float floor_grey;
        public float backdrop_grey;
        public float[] light_euler_deg;
        public float light_intensity;
        public float ambient_grey;
        public int magenta_tolerance;
    }

    [Serializable]
    public class LookCheckHand
    {
        public float fist_curl_deg;
        public float fist_thumb_curl_deg;
        public float relaxed_curl_deg;
        public float relaxed_thumb_curl_deg;
        public float rest_outward;
    }

    [Serializable]
    public class LookEntry
    {
        public const string KindPrefab = "prefab", KindSunbox = "sunbox";
        public const string RoleCandidate = "candidate", RolePipelineTest = "pipeline_test_only";

        public string id;
        public string family;
        public string role;
        public string source;
        /// <summary>prefab: any GameObject asset (FBX, prefab, imported .vrm); sunbox: the Sunbox Avatar prefab, customised.</summary>
        public string kind;
        public string asset;
        /// <summary>Optional material put on every renderer slot (the v3 worker's URP material); "" = keep the asset's.</summary>
        public string material_override;
        public SunboxLook sunbox;
    }

    [Serializable]
    public class SunboxLook
    {
        public string gender;
        public int skin;
        public int hair_style;
        public int hair_material;
        public int facial_hair_style;
        public SunboxClothing[] clothing;
    }

    [Serializable]
    public class SunboxClothing
    {
        public string name;
        public int variation;
    }
}
