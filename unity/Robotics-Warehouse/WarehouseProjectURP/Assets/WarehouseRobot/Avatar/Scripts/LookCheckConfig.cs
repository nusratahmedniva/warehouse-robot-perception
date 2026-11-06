using System;
using System.Collections.Generic;
using System.Globalization;
using UnityEngine;

namespace WarehouseAvatar
{
    /// <summary>
    /// Assets/WarehouseRobot/Avatar/Config/look_check.json (v4 Phase 2A look check). Parse() throws on a file JsonUtility
    /// cannot read; Validate() lists every missing or invalid value (a missing key reads as 0 or empty).
    /// </summary>
    [Serializable]
    public class LookCheckConfig
    {
        public string note;
        public LookCheckPaths paths;
        public LookCheckRender render;
        public string[] poses;
        public LookCheckHand hand;
        public LookEntry[] looks;

        public static readonly CultureInfo Inv = CultureInfo.InvariantCulture;

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
            if (render == null) e.Add("render: missing");
            else
            {
                if (render.distances_m == null || render.distances_m.Length == 0) e.Add("render.distances_m: empty");
                else foreach (var d in render.distances_m) if (!(d > 0f)) e.Add("render.distances_m: every distance must be > 0");
                if (render.vertical_fovs_deg == null || render.vertical_fovs_deg.Length == 0) e.Add("render.vertical_fovs_deg: empty");
                else foreach (var f in render.vertical_fovs_deg) if (!(f > 0f && f < 180f)) e.Add("render.vertical_fovs_deg: every value must be in (0, 180)");
                if (!(render.backdrop_behind_person_m > 0f)) e.Add("render.backdrop_behind_person_m must be > 0");
                if (!(render.floor_half_size_m > 0f)) e.Add("render.floor_half_size_m must be > 0");
                if (render.light_euler_deg == null || render.light_euler_deg.Length != 3) e.Add("render.light_euler_deg: three angles required");
                if (render.magenta_tolerance < 0 || render.magenta_tolerance > 127) e.Add("render.magenta_tolerance must be in 0..127");
            }
            if (poses == null || poses.Length == 0) e.Add("poses: empty");
            else
            {
                var seen = new HashSet<string>();
                foreach (var p in poses)
                {
                    if (!LookPoses.TryParse(p, out _)) e.Add($"poses: unknown pose '{p}' (known: {string.Join(", ", LookPoses.Names)})");
                    else if (!seen.Add(p)) e.Add($"poses: '{p}' listed twice");
                }
            }
            if (hand == null) e.Add("hand: missing");
            else if (!(hand.fist_curl_deg > 0f) || !(hand.fist_thumb_curl_deg >= 0f) || hand.relaxed_curl_deg < 0f || hand.relaxed_thumb_curl_deg < 0f ||
                     hand.stop_spread_deg < 0f || hand.rest_outward < 0f)
                e.Add("hand: fist_curl_deg must be > 0 and the other angles and rest_outward >= 0");
            if (looks == null || looks.Length == 0) e.Add("looks: empty");
            else
            {
                var ids = new HashSet<string>();
                foreach (var l in looks)
                {
                    if (l == null || string.IsNullOrEmpty(l.id)) { e.Add("looks: an entry has no id"); continue; }
                    if (!ids.Add(l.id)) e.Add($"looks: id '{l.id}' listed twice");
                    if (!IsSafeId(l.id)) e.Add($"looks: id '{l.id}' must use only a-z, 0-9 and '_' (it names files)");
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

        static bool IsSafeId(string id)
        {
            foreach (char ch in id)
                if (!((ch >= 'a' && ch <= 'z') || (ch >= '0' && ch <= '9') || ch == '_')) return false;
            return true;
        }

        /// <summary>Image file name, e.g. "sunbox_m1__wait__d2.0__fov30.png" (invariant culture: never "2,0").</summary>
        public static string ImageName(string lookId, string pose, float distanceM, float fovDeg) =>
            $"{lookId}__{pose}__d{distanceM.ToString("0.0", Inv)}__fov{fovDeg.ToString("0.#", Inv)}.png";

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
    public class LookCheckRender
    {
        public float[] distances_m;
        public float[] vertical_fovs_deg;
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
        public float stop_spread_deg;
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
