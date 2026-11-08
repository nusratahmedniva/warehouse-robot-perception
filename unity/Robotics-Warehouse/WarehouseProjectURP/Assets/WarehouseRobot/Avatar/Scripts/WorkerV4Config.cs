using System;
using System.Collections.Generic;
using UnityEngine;

namespace WarehouseAvatar
{
    /// <summary>
    /// Assets/WarehouseRobot/Avatar/Config/worker_v4.json (v4 Phase 2B): the worker template's looks, gesture clips,
    /// hand shapes, behaviour and the random variation of every gesture. Read by WorkerV4 (runtime) and the Editor tools
    /// (Tools > Warehouse v4 > Workers). Parse() throws on a file JsonUtility cannot read; Validate() lists every missing
    /// or invalid value (a missing key reads as 0 or empty, so every value is checked).
    /// </summary>
    [Serializable]
    public class WorkerV4Config
    {
        public const string Point = LookCheckConfig.Point, Wait = LookCheckConfig.Wait, Stop = LookCheckConfig.Stop, None = LookCheckConfig.None;
        public const string KindMixamo = "mixamo", KindProcedural = "procedural";
        public const string EaseSmooth = "smooth", EaseQuick = "quick";
        public static readonly string[] Commands = { Point, Wait, Stop };

        public string note;
        public WorkerPaths paths;
        public WorkerQuestion question;
        public WorkerBehaviour behaviour;
        public WorkerAnimation animation;
        public WorkerHandShapes hand_shapes;
        public WorkerVariation variation;
        public WorkerLimits limits;
        public WorkerPointing pointing;
        public WorkerTruthLog truth_log;
        public GestureClipSpec[] clips;
        public LookEntry[] looks;

        public static WorkerV4Config Parse(string json)
        {
            var c = JsonUtility.FromJson<WorkerV4Config>(json);
            if (c == null) throw new InvalidOperationException("worker_v4.json: not a JSON object");
            return c;
        }

        public GestureClipSpec Clip(string name)
        {
            if (clips != null) foreach (var c in clips) if (c != null && c.name == name) return c;
            return null;
        }

        public LookEntry Look(string id)
        {
            if (looks != null) foreach (var l in looks) if (l != null && l.id == id) return l;
            return null;
        }

        /// <summary>The clip names of one command, in config order.</summary>
        public List<string> ClipNames(string command)
        {
            var list = new List<string>();
            if (clips != null) foreach (var c in clips) if (c != null && c.command == command) list.Add(c.name);
            return list;
        }

        public List<string> Validate()
        {
            var e = new List<string>();
            if (paths == null || string.IsNullOrEmpty(paths.repo_root_relative_to_unity_project) || string.IsNullOrEmpty(paths.clip_source_folder) ||
                string.IsNullOrEmpty(paths.clip_import_folder) || string.IsNullOrEmpty(paths.clip_resources_path) ||
                string.IsNullOrEmpty(paths.clip_index_name) || string.IsNullOrEmpty(paths.question_prompt_source))
                e.Add("paths: repo_root_relative_to_unity_project, clip_source_folder, clip_import_folder, clip_resources_path, clip_index_name and question_prompt_source are required");
            else
            {
                if (!paths.clip_import_folder.StartsWith("Assets/ThirdParty/", StringComparison.Ordinal))
                    e.Add("paths.clip_import_folder must lie under Assets/ThirdParty/ (git-ignored: Mixamo clips are never committed)");
                if (!paths.clip_import_folder.EndsWith("/Resources/" + paths.clip_resources_path, StringComparison.Ordinal))
                    e.Add("paths.clip_import_folder must end with /Resources/<clip_resources_path> (the worker loads the clips with Resources.Load)");
            }
            if (question == null || string.IsNullOrEmpty(question.prompt)) e.Add("question.prompt: required");
            ValidateBehaviour(e);
            if (animation == null) e.Add("animation: missing");
            else
            {
                if (string.IsNullOrEmpty(animation.idle_clip_file)) e.Add("animation.idle_clip_file: required");
                if (!(animation.gesture_layer_fade_s > 0f)) e.Add("animation.gesture_layer_fade_s must be > 0");
                if (!In01(animation.hold_body_speed)) e.Add("animation.hold_body_speed must be in [0, 1] (0 = the body stands still while a gesture is held)");
                if (string.IsNullOrEmpty(animation.controller) || !animation.controller.StartsWith("Assets/", StringComparison.Ordinal))
                    e.Add("animation.controller must be a project path starting with Assets/");
            }
            ValidateHands(e);
            ValidateVariation(e);
            ValidateLimits(e);
            if (truth_log == null || !(truth_log.interval_s > 0f && truth_log.interval_s <= 0.1f))
                e.Add("truth_log.interval_s must be in (0, 0.1] (docs/protocol_v3.md: a truth line at least every 0.1 s)");
            ValidateClips(e);
            ValidateLooks(e);
            return e;
        }

        void ValidateBehaviour(List<string> e)
        {
            var b = behaviour;
            if (b == null) { e.Add("behaviour: missing"); return; }
            if (!(b.notice_distance_m > 0f)) e.Add("behaviour.notice_distance_m must be > 0");
            if (!(b.turn_speed_deg_per_s > 0f)) e.Add("behaviour.turn_speed_deg_per_s must be > 0");
            if (!(b.face_tolerance_deg > 0f && b.face_tolerance_deg < 45f)) e.Add("behaviour.face_tolerance_deg must be in (0, 45)");
            if (!(b.turn_start_deg >= b.face_tolerance_deg)) e.Add("behaviour.turn_start_deg must be >= face_tolerance_deg");
            if (b.look_at == null) e.Add("behaviour.look_at: missing");
            else
            {
                var l = b.look_at;
                if (!In01(l.weight) || !In01(l.body) || !In01(l.head) || !In01(l.eyes) || !In01(l.clamp)) e.Add("behaviour.look_at: weight, body, head, eyes and clamp must be in [0, 1]");
                if (!(l.fade_s > 0f)) e.Add("behaviour.look_at.fade_s must be > 0");
            }
        }

        void ValidateHands(List<string> e)
        {
            var h = hand_shapes;
            if (h == null) { e.Add("hand_shapes: missing"); return; }
            void Shape(string name, HandShapeSpec s, bool straightIndex, bool straightOthers)
            {
                if (s == null) { e.Add($"hand_shapes.{name}: missing"); return; }
                if (!Joints(s.thumb_deg)) e.Add($"hand_shapes.{name}.thumb_deg: three angles in [0, 120] required");
                if (s.thumb_across_deg < 0f || s.thumb_across_deg > 90f) e.Add($"hand_shapes.{name}.thumb_across_deg must be in [0, 90]");
                foreach (var (finger, a) in new[] { ("index", s.index_deg), ("middle", s.middle_deg), ("ring", s.ring_deg), ("little", s.little_deg) })
                {
                    if (!Joints(a)) { e.Add($"hand_shapes.{name}.{finger}_deg: three angles in [0, 120] required"); continue; }
                    bool straight = finger == "index" ? straightIndex : straightOthers;
                    float sum = a[0] + a[1] + a[2];
                    if (straight && sum > 15f) e.Add($"hand_shapes.{name}.{finger}_deg must stay straight (sum <= 15 deg)");
                    if (!straight && sum < 180f) e.Add($"hand_shapes.{name}.{finger}_deg must be a tight curl (sum >= 180 deg)");
                }
                if (s.spread_deg < 0f || s.spread_deg > 20f) e.Add($"hand_shapes.{name}.spread_deg must be in [0, 20]");
            }
            Shape("point", h.point, true, false);
            Shape("wait", h.wait, true, false);
            Shape("stop", h.stop, true, true);
            if (h.stop != null && !(h.stop.spread_deg > 0f)) e.Add("hand_shapes.stop.spread_deg must be > 0 (fingers spread)");
        }

        void ValidateVariation(List<string> e)
        {
            var v = variation;
            if (v == null) { e.Add("variation: missing"); return; }
            Range(e, "variation.speed", v.speed, 0.2f, 5f);
            Range(e, "variation.size", v.size, 0.2f, 5f);
            Range(e, "variation.start_delay_s", v.start_delay_s, 0f, 10f);
            Range(e, "variation.hold_s", v.hold_s, 0.5f, 30f);
            Range(e, "variation.point_elevation_deg", v.point_elevation_deg, -30f, 45f);
            Range(e, "variation.sway_amplitude_m", v.sway_amplitude_m, 0f, 0.05f);
            Range(e, "variation.sway_frequency_hz", v.sway_frequency_hz, 0.01f, 3f);
            Range(e, "variation.hold_sway_amplitude_m", v.hold_sway_amplitude_m, 0f, 0.05f);
            if (!In01(v.left_arm_probability)) e.Add("variation.left_arm_probability must be in [0, 1]");
            if (v.point_either_arm_within_deg < 0f || v.point_either_arm_within_deg > 90f) e.Add("variation.point_either_arm_within_deg must be in [0, 90]");
        }

        void ValidateLimits(List<string> e)
        {
            var l = limits;
            if (l == null) { e.Add("limits: missing"); return; }
            Range(e, "limits.point_reach", l.point_reach, 0.9f, 1.0f);
            Range(e, "limits.stop_reach", l.stop_reach, 0.7f, 1.0f);
            if (!(l.wait_min_up_l > 0f)) e.Add("limits.wait_min_up_l must be > 0 (the WAIT hand stays above the shoulder)");
            if (!(l.point_max_body_azimuth_deg > 0f && l.point_max_body_azimuth_deg <= 150f)) e.Add("limits.point_max_body_azimuth_deg must be in (0, 150]");
            var p = pointing;
            if (p == null) { e.Add("pointing: missing (Avatar/Config/pointing_design.md)"); return; }
            if (!(p.arm_target_body_azimuth_deg > 0f && p.arm_target_body_azimuth_deg <= l.point_max_body_azimuth_deg))
                e.Add("pointing.arm_target_body_azimuth_deg must be in (0, limits.point_max_body_azimuth_deg]");
            if (p.stand_angle_max_deg < 0f || p.stand_angle_max_deg > 45f) e.Add("pointing.stand_angle_max_deg must be in [0, 45]");
            if (p.torso_turn_max_deg < 0f || p.torso_turn_max_deg > 60f) e.Add("pointing.torso_turn_max_deg must be in [0, 60]");
        }

        void ValidateClips(List<string> e)
        {
            if (clips == null || clips.Length == 0) { e.Add("clips: empty"); return; }
            var names = new HashSet<string>();
            var perCommand = new Dictionary<string, int>();
            foreach (var c in clips)
            {
                if (c == null || !LookCheckConfig.IsNamePart(c.name)) { e.Add($"clips: name '{c?.name}' must use a-z, 0-9 and single inner '_' only"); continue; }
                if (!names.Add(c.name)) e.Add($"clips: '{c.name}' listed twice");
                if (Array.IndexOf(Commands, c.command) < 0) { e.Add($"clips '{c.name}': command must be POINT, WAIT or STOP"); continue; }
                if (!c.name.StartsWith(c.command.ToLowerInvariant() + "_", StringComparison.Ordinal))
                    e.Add($"clips '{c.name}': the name must start with '{c.command.ToLowerInvariant()}_' (one clip name per command)");
                perCommand[c.command] = (perCommand.TryGetValue(c.command, out int n) ? n : 0) + 1;
                if (c.kind == KindMixamo)
                {
                    if (string.IsNullOrEmpty(c.source_file) || !c.source_file.EndsWith(".fbx", StringComparison.OrdinalIgnoreCase))
                        e.Add($"clips '{c.name}': a mixamo clip needs source_file (an .fbx in paths.clip_source_folder)");
                }
                else if (c.kind == KindProcedural)
                {
                    if (!string.IsNullOrEmpty(c.source_file)) e.Add($"clips '{c.name}': a procedural clip has no source_file");
                    if (!(c.raise_s > 0f) || !(c.return_s > 0f)) e.Add($"clips '{c.name}': raise_s and return_s must be > 0");
                }
                else e.Add($"clips '{c.name}': kind must be '{KindMixamo}' or '{KindProcedural}'");
                if (c.ease != EaseSmooth && c.ease != EaseQuick) e.Add($"clips '{c.name}': ease must be '{EaseSmooth}' or '{EaseQuick}'");
                if (c.elbow_down_l < 0f || c.elbow_down_l > 0.5f) e.Add($"clips '{c.name}': elbow_down_l must be in [0, 0.5]");
                switch (c.command)
                {
                    case Point:
                        if (!(c.reach >= 0.9f && c.reach <= 1.0f)) e.Add($"clips '{c.name}': POINT reach must be in [0.9, 1.0] (a straight arm)");
                        break;
                    case Stop:
                        if (!(c.reach >= 0.7f && c.reach <= 1.0f)) e.Add($"clips '{c.name}': STOP reach must be in [0.7, 1.0] (an extended arm)");
                        if (c.azimuth_out_deg < 0f || c.azimuth_out_deg > 30f) e.Add($"clips '{c.name}': STOP azimuth_out_deg must be in [0, 30] (forward, toward the robot)");
                        if (Mathf.Abs(c.elevation_deg) > 20f) e.Add($"clips '{c.name}': STOP elevation_deg must be within +-20 (shoulder height)");
                        if (c.push_l < 0f || c.push_l > 0.2f) e.Add($"clips '{c.name}': push_l must be in [0, 0.2]");
                        break;
                    case Wait:
                        if (!(c.hand_up_l > 0f)) e.Add($"clips '{c.name}': WAIT hand_up_l must be > 0 (hand above the shoulder)");
                        if (!(c.hand_side_l >= 0f) || !(c.hand_forward_l >= 0f)) e.Add($"clips '{c.name}': WAIT hand_side_l and hand_forward_l must be >= 0");
                        break;
                }
            }
            foreach (var cmd in Commands)
            {
                int n = perCommand.TryGetValue(cmd, out int k) ? k : 0;
                if (n < 2 || n > 3) e.Add($"clips: {cmd} needs 2 to 3 variants (has {n})");
            }
        }

        void ValidateLooks(List<string> e)
        {
            if (looks == null || looks.Length == 0) { e.Add("looks: empty"); return; }
            var ids = new HashSet<string>();
            foreach (var l in looks)
            {
                if (l == null || !LookCheckConfig.IsNamePart(l.id)) { e.Add($"looks: id '{l?.id}' must use a-z, 0-9 and single inner '_' only"); continue; }
                if (!ids.Add(l.id)) e.Add($"looks: '{l.id}' listed twice");
                if (l.kind != LookEntry.KindSunbox && l.kind != LookEntry.KindPrefab) e.Add($"looks '{l.id}': kind must be sunbox or prefab");
                if (string.IsNullOrEmpty(l.asset) || !l.asset.StartsWith("Assets/", StringComparison.Ordinal)) e.Add($"looks '{l.id}': asset must start with Assets/");
                if (l.kind == LookEntry.KindSunbox && (l.sunbox == null || (l.sunbox.gender != "Male" && l.sunbox.gender != "Female")))
                    e.Add($"looks '{l.id}': sunbox.gender must be Male or Female");
            }
        }

        static bool In01(float x) => x >= 0f && x <= 1f;

        static bool Joints(float[] a)
        {
            if (a == null || a.Length != 3) return false;
            foreach (var x in a) if (!(x >= 0f && x <= 120f)) return false;
            return true;
        }

        static void Range(List<string> e, string name, float[] r, float lo, float hi)
        {
            if (r == null || r.Length != 2) { e.Add($"{name}: [min, max] required"); return; }
            if (!(r[0] >= lo && r[1] <= hi && r[0] <= r[1])) e.Add($"{name}: [min, max] with {lo} <= min <= max <= {hi}");
        }
    }

    [Serializable]
    public class WorkerPaths
    {
        public string repo_root_relative_to_unity_project;
        public string clip_source_folder;
        public string clip_import_folder;
        public string clip_resources_path;
        public string clip_index_name;
        public string question_prompt_source;
    }

    [Serializable]
    public class WorkerQuestion
    {
        public string prompt;
    }

    [Serializable]
    public class WorkerBehaviour
    {
        public float notice_distance_m;
        public float turn_speed_deg_per_s;
        public float turn_start_deg;
        public float face_tolerance_deg;
        public WorkerLookAt look_at;
    }

    [Serializable]
    public class WorkerLookAt
    {
        public float weight, body, head, eyes, clamp, fade_s;
    }

    [Serializable]
    public class WorkerAnimation
    {
        public string idle_clip_file;
        public string turn_clip_file;
        public float gesture_layer_fade_s;
        public string controller;
        /// <summary>Animator speed while a gesture is held (0 = the body stands still). -1 until read, so a missing key is refused.</summary>
        public float hold_body_speed = -1f;
    }

    /// <summary>Finger curls per joint (proximal, intermediate, distal), in degrees toward the palm; spread between fingers.</summary>
    [Serializable]
    public class HandShapeSpec
    {
        public float[] thumb_deg;
        public float thumb_across_deg;
        public float[] index_deg;
        public float[] middle_deg;
        public float[] ring_deg;
        public float[] little_deg;
        public float spread_deg;

        public float[] Finger(int f)
        {
            switch (f)
            {
                case HandShaper.Thumb: return thumb_deg;
                case HandShaper.Index: return index_deg;
                case HandShaper.Middle: return middle_deg;
                case HandShaper.Ring: return ring_deg;
                default: return little_deg;
            }
        }
    }

    [Serializable]
    public class WorkerHandShapes
    {
        public HandShapeSpec point;
        public HandShapeSpec wait;
        public HandShapeSpec stop;

        public HandShapeSpec For(string command) => command == WorkerV4Config.Point ? point : command == WorkerV4Config.Wait ? wait : stop;
    }

    /// <summary>[min, max] ranges drawn uniformly per gesture (seeded per run and worker).</summary>
    [Serializable]
    public class WorkerVariation
    {
        public float[] speed;
        public float[] size;
        public float[] start_delay_s;
        public float[] hold_s;
        public float left_arm_probability;
        public float[] point_elevation_deg;
        public float point_either_arm_within_deg;
        public float[] sway_amplitude_m;
        public float[] sway_frequency_hz;
        public float[] hold_sway_amplitude_m;
    }

    /// <summary>Clamps that keep every varied gesture inside its command's definition (docs/gesture_reader_v4.md poses).</summary>
    [Serializable]
    public class WorkerLimits
    {
        public float[] point_reach;
        public float[] stop_reach;
        public float wait_min_up_l;
        public float point_max_body_azimuth_deg;
    }

    /// <summary>Option A for POINT (Avatar/Config/pointing_design.md, 2026-11-09): an angled stance and a torso turn toward
    /// the pointed direction, so a branch behind the worker is shown without the body-azimuth clamp. 0 and 0 = Phase 3A.</summary>
    [Serializable]
    public class WorkerPointing
    {
        public float arm_target_body_azimuth_deg;
        public float stand_angle_max_deg;
        public float torso_turn_max_deg;
    }

    /// <summary>One POINT split into stance, torso turn and arm (signed degrees, + = the worker's right, all relative to
    /// the body front at the request). Shown = the direction the arm actually shows after the body-azimuth clamp.</summary>
    public struct PointingSplit
    {
        public float Stand, Torso, Arm, Shown;

        /// <summary>need = |alpha| - arm target; the stance takes up to stand_angle_max_deg of it, the torso up to
        /// torso_turn_max_deg of the rest; the arm keeps what is left, clamped to maxArmDeg from the turned chest.</summary>
        public static PointingSplit For(float alphaDeg, WorkerPointing p, float maxArmDeg)
        {
            float a = Mathf.Abs(alphaDeg), sign = alphaDeg < 0f ? -1f : 1f;
            float need = p != null ? Mathf.Max(0f, a - p.arm_target_body_azimuth_deg) : 0f;
            float stand = p != null ? Mathf.Min(need, p.stand_angle_max_deg) : 0f;
            float torso = p != null ? Mathf.Min(need - stand, p.torso_turn_max_deg) : 0f;
            float arm = Mathf.Min(a - stand - torso, maxArmDeg);
            return new PointingSplit { Stand = sign * stand, Torso = sign * torso, Arm = sign * arm, Shown = sign * (stand + torso + arm) };
        }
    }

    [Serializable]
    public class WorkerTruthLog
    {
        public float interval_s;
    }

    /// <summary>
    /// One gesture variant ("clip" in truth.jsonl and data_splits.json). mixamo: a Mixamo clip on the gesture layer, its
    /// timing from the clip, the hand steered by IK; procedural: Humanoid IK only. Lengths with suffix _l are fractions of
    /// the worker's own arm length (shoulder to wrist), so a variant fits every look.
    /// </summary>
    [Serializable]
    public class GestureClipSpec
    {
        public string name;
        public string command;
        public string kind;
        public string source_file;
        public float raise_s;
        public float return_s;
        public string ease;
        public float reach;
        public float elevation_deg;
        public float azimuth_out_deg;
        public float hand_side_l;
        public float hand_forward_l;
        public float hand_up_l;
        public float push_l;
        public float elbow_down_l;
        public string why;

        public bool IsMixamo => kind == WorkerV4Config.KindMixamo;
    }

    /// <summary>Generated by Tools > Warehouse v4 > Workers > Import Mixamo Clips into the (git-ignored) import folder.</summary>
    [Serializable]
    public class ClipIndex
    {
        public ClipIndexEntry[] clips = new ClipIndexEntry[0];

        public ClipIndexEntry Find(string file)
        {
            foreach (var c in clips) if (c != null && string.Equals(c.file, file, StringComparison.OrdinalIgnoreCase)) return c;
            return null;
        }
    }

    [Serializable]
    public class ClipIndexEntry
    {
        /// <summary>The source .fbx file name (as in worker_v4.json source_file / idle_clip_file).</summary>
        public string file;
        public string resource;
        public string clip_name;
        public float length_s;
        /// <summary>The arm the clip raises ("left", "right"), from its Humanoid muscle curves; "" for the idle clip.</summary>
        public string arm;
        /// <summary>The arm reaches 90 per cent of its largest raise here; the worker freezes the clip here for the hold.</summary>
        public float peak_s;
        /// <summary>Last time the arm is still at 90 per cent of its raise; the return resumes the clip from here.</summary>
        public float release_s;
        public float raise_amount;
        public string sha256;
    }
}
