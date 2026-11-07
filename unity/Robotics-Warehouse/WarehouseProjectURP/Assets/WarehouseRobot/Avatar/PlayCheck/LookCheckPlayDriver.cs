using System;
using System.Collections;
using System.Collections.Generic;
using System.Globalization;
using System.IO;
using System.Text;
using System.Threading.Tasks;
using UnityEngine;
using UnityEngine.Experimental.Rendering;
using UnityEngine.Rendering;
using WarehouseAvatar;

namespace WarehouseRobot.AvatarCheck
{
    /// <summary>
    /// v4 Phase 2B Play-mode look check (LookCheckPlay.unity, look_check_play.json): the worker template performs the real
    /// gesture variants in Play mode and the pan-tilt camera settings of robot_unity_v4.json record them in the input
    /// format of docs/look_check_v4.md (Anisha's look_check_v4.py), with the real Unity Time.time of every frame. Six stages
    /// (3 looks x 2 distances) run at once. Writes robot_vision/outputs/look_check_play_&lt;time&gt;/ (never overwrites):
    /// looks_check_&lt;time&gt;/ (recordings only), recordings.jsonl, workers.json, truth/, config_used/, run_info.json.
    /// An engineering check, not an evaluation.
    /// </summary>
    public class LookCheckPlayDriver : MonoBehaviour
    {
        public TextAsset playConfig;
        public TextAsset lookCheckConfig;
        public TextAsset robotConfig;
        public WorkerV4 workerPrefab;
        public Light keyLight;
        public string repoRootRelativeToProject = "../../..";
        public bool runOnStart = true;

        public string Status { get; private set; } = "idle";
        public string OutputFolder { get; private set; } = "";
        public string RecordingFolder { get; private set; } = "";

        static readonly CultureInfo Inv = CultureInfo.InvariantCulture;
        static readonly UTF8Encoding Utf8 = new UTF8Encoding(false);

        [Serializable]
        class PlayConfig
        {
            public PlayOutput output;
            public string[] looks;
            public int seed;
            public float[] point_side_azimuth_deg;
            public int singles_per_group;
            public float[] single_point_side_azimuth_deg;
            public int none_sequences, none_singles;
            public float none_frame_spacing_s, settle_after_hold_s, question_after_request_s, pause_between_s;
            public float face_wait_max_s, phase_wait_max_s, initial_yaw_offset_deg, stage_spacing_m;
        }

        [Serializable] class PlayOutput { public string root, run_prefix, recordings_prefix; }

        [Serializable]
        class RecordingRecord
        {
            public string name, kind, look, command, arm, clip;
            public int worker_id, n_frames, frames_outside_hold, hand_ik_calls;
            public float distance_m, vertical_fov_deg, time_first_s, time_last_s;
            public float speed, size, start_delay_s, hold_s, point_side_azimuth_deg, point_angle_deg;
            public float hand_to_target_max_m = -1f;
        }

        [Serializable]
        class WorkerRecord
        {
            public int worker_id;
            public string look, description, truth_file;
            public float distance_m, arm_length_m, shoulder_width_m, arm_to_shoulder_ratio, height_m, ground_shift_m;
            public int truth_lines;
            public string truth_failed;
        }

        [Serializable] class WorkersFile { public List<WorkerRecord> workers = new List<WorkerRecord>(); }

        [Serializable]
        class RunInfo
        {
            public string created_local, finished_local, git_commit, git_branch, unity_version, render_pipeline, color_space, graphics_device;
            public string play_config_sha256, look_check_sha256, worker_config_sha256, robot_unity_config_sha256, clip_index_sha256;
            public int recordings, frames, frames_outside_hold;
            public string status, note;
        }

        sealed class Stage
        {
            public int Index;
            public string Look;
            public float Distance;
            public Transform Root, Robot;
            public Camera Cam;
            public WorkerV4 Worker;
            public TruthLogger Truth;
            public SeededRandom Rng;
            public RenderTexture Rt;
            public Texture2D Tex;
            public string Error;
            public bool Done;
            public WorkerRecord Record;
        }

        PlayConfig m_Play;
        LookCheckConfig m_Look;
        PanTiltCameraConfig m_Pt;
        WorkerV4Config m_Worker;
        readonly List<Task> m_Writes = new List<Task>();
        readonly List<RecordingRecord> m_Records = new List<RecordingRecord>();
        readonly List<string> m_WriteErrors = new List<string>();
        int m_Frames, m_Outside;
        static string QuickLook()
        {
            var a = Environment.GetCommandLineArgs();
            int i = Array.IndexOf(a, "-lookCheckQuick");
            return i >= 0 && i + 1 < a.Length && !a[i + 1].StartsWith("-") ? a[i + 1] : "sunbox_m1";
        }

        bool m_Quick;   // -lookCheckQuick: diagnostics only (one stage, one gesture per command and arm, every capture logged)
        string m_Stamp;

        void Start()
        {
            if (runOnStart) StartCoroutine(Run());
        }

        string RepoRoot => Path.GetFullPath(Path.Combine(Application.dataPath, "..", repoRootRelativeToProject));

        bool Setup(out string error)
        {
            error = null;
            if (playConfig == null || lookCheckConfig == null || robotConfig == null || workerPrefab == null || keyLight == null)
            {
                error = "assign playConfig, lookCheckConfig, robotConfig, workerPrefab and keyLight (Tools > Warehouse v4 > Look Check > Build LookCheckPlay Scene)";
                return false;
            }
            m_Play = JsonUtility.FromJson<PlayConfig>(playConfig.text);
            m_Look = LookCheckConfig.Parse(lookCheckConfig.text);
            var le = m_Look.Validate();
            if (le.Count > 0) { error = "look_check.json: " + string.Join("; ", le); return false; }
            m_Pt = RobotConfig.Load(robotConfig).Unity.pan_tilt_camera;
            m_Worker = WorkerV4Config.Parse(workerPrefab.config.text);
            var we = m_Worker.Validate();
            if (we.Count > 0) { error = "worker_v4.json: " + string.Join("; ", we); return false; }
            if (m_Play.looks == null || m_Play.looks.Length == 0) { error = "look_check_play.json: no looks"; return false; }
            foreach (var l in m_Play.looks) if (m_Worker.Look(l) == null) { error = $"look_check_play.json: look '{l}' is not in worker_v4.json"; return false; }
            foreach (var cmd in WorkerV4Config.Commands)
                if (m_Worker.ClipNames(cmd).Count < 2) { error = $"worker_v4.json: fewer than 2 variants of {cmd}"; return false; }
            if (m_Play.point_side_azimuth_deg == null || m_Play.point_side_azimuth_deg.Length < m_Worker.ClipNames(WorkerV4Config.Point).Count)
            { error = "look_check_play.json: point_side_azimuth_deg needs one direction per POINT variant"; return false; }
            if (m_Play.single_point_side_azimuth_deg == null || m_Play.single_point_side_azimuth_deg.Length < m_Play.singles_per_group)
            { error = "look_check_play.json: single_point_side_azimuth_deg needs one direction per single"; return false; }
            if (!(m_Worker.variation.hold_s[0] > m_Play.settle_after_hold_s + (m_Look.recording.sequence_frames - 1) * 0.1f + 0.3f))
            { error = "worker_v4.json hold_s is too short for a full sequence inside the hold"; return false; }
            return true;
        }

        IEnumerator Run()
        {
            yield return null;
            Status = "starting";
            if (!Setup(out string err)) { Finish("failed: " + err); yield break; }
            m_Stamp = DateTime.Now.ToString("yyyyMMdd_HHmmss", Inv);
            m_Quick = Array.IndexOf(Environment.GetCommandLineArgs(), "-lookCheckQuick") >= 0;
            OutputFolder = NewFolder(Path.Combine(RepoRoot, m_Play.output.root), m_Play.output.run_prefix + (m_Quick ? "_debug_" : "_") + m_Stamp);
            RecordingFolder = Path.Combine(OutputFolder, m_Play.output.recordings_prefix + "_" + m_Stamp);
            Directory.CreateDirectory(RecordingFolder);
            Directory.CreateDirectory(Path.Combine(OutputFolder, "truth"));
            string used = Path.Combine(OutputFolder, "config_used");
            Directory.CreateDirectory(used);
            WriteNew(Path.Combine(used, "look_check_play.json"), playConfig.text);
            WriteNew(Path.Combine(used, "look_check.json"), lookCheckConfig.text);
            WriteNew(Path.Combine(used, "worker_v4.json"), workerPrefab.config.text);
            WriteNew(Path.Combine(used, "robot_unity_v4.json"), robotConfig.text);
            var index = Resources.Load<TextAsset>(m_Worker.paths.clip_resources_path + "/" + m_Worker.paths.clip_index_name);
            if (index != null) WriteNew(Path.Combine(used, "clip_index.json"), index.text);
            var info = new RunInfo { created_local = DateTime.Now.ToString("yyyy-MM-dd'T'HH:mm:ss", Inv) };

            ApplyLighting();
            QualitySettings.vSyncCount = 0;
            Application.targetFrameRate = 60;
            var stages = new List<Stage>();
            foreach (var look in m_Play.looks)
                foreach (var d in m_Look.recording.distances_m)
                {
                    if (m_Quick && (stages.Count > 0 || look != QuickLook())) continue;
                    var st = BuildStage(stages.Count, look, d);
                    if (st.Error != null) { Finish($"failed: stage {look} {d} m: {st.Error}"); yield break; }
                    stages.Add(st);
                }
            Status = "running";
            foreach (var st in stages) StartCoroutine(RunStage(st));
            while (!stages.TrueForAll(s => s.Done)) yield return null;
            foreach (var st in stages) { st.Truth.End(); st.Record.truth_lines = st.Truth.Lines; st.Record.truth_failed = st.Truth.Failed; }

            Status = "writing";
            var all = Task.WhenAll(m_Writes);
            while (!all.IsCompleted) yield return null;
            var lines = new StringBuilder();
            foreach (var r in m_Records) lines.Append(JsonUtility.ToJson(r)).Append('\n');
            WriteNew(Path.Combine(OutputFolder, "recordings.jsonl"), lines.ToString());
            var wf = new WorkersFile();
            foreach (var st in stages) wf.workers.Add(st.Record);
            WriteNew(Path.Combine(OutputFolder, "workers.json"), JsonUtility.ToJson(wf, true).Replace("\r\n", "\n") + "\n");

            var errors = new List<string>();
            foreach (var st in stages) if (st.Error != null) errors.Add($"{st.Look} {st.Distance} m: {st.Error}");
            foreach (var st in stages) if (!string.IsNullOrEmpty(st.Truth.Failed)) errors.Add($"{st.Look} {st.Distance} m truth: {st.Truth.Failed}");
            lock (m_WriteErrors) errors.AddRange(m_WriteErrors);
            Git(out info.git_commit, out info.git_branch);
            info.finished_local = DateTime.Now.ToString("yyyy-MM-dd'T'HH:mm:ss", Inv);
            info.unity_version = Application.unityVersion;
            info.render_pipeline = GraphicsSettings.currentRenderPipeline != null ? GraphicsSettings.currentRenderPipeline.name : "built-in";
            info.color_space = QualitySettings.activeColorSpace.ToString();
            info.graphics_device = SystemInfo.graphicsDeviceType + " " + SystemInfo.graphicsDeviceName;
            info.play_config_sha256 = Sha256(playConfig.text);
            info.look_check_sha256 = Sha256(lookCheckConfig.text);
            info.worker_config_sha256 = Sha256(workerPrefab.config.text);
            info.robot_unity_config_sha256 = Sha256(robotConfig.text);
            info.clip_index_sha256 = index != null ? Sha256(index.text) : "";
            info.recordings = m_Records.Count;
            info.frames = m_Frames;
            info.frames_outside_hold = m_Outside;
            info.status = errors.Count == 0 ? "done" : "done with problems: " + string.Join("; ", errors);
            info.note = "v4 Phase 2B Play-mode look check: an engineering check of the worker template's looks and gestures; not an evaluation.";
            WriteNew(Path.Combine(OutputFolder, "run_info.json"), JsonUtility.ToJson(info, true).Replace("\r\n", "\n") + "\n");
            Finish((errors.Count == 0 ? "done: " : "failed: ") + $"{m_Records.Count} recordings, {m_Frames} frames in {Path.GetFileName(OutputFolder)}" +
                   (errors.Count > 0 ? " - " + string.Join("; ", errors) : ""));
        }

        void Finish(string status)
        {
            Status = status;
            if (status.StartsWith("done")) Debug.Log("[LookCheckPlay] " + status);
            else Debug.LogError("[LookCheckPlay] " + status);
        }

        // ---------------------------------------------------------------- stage

        void ApplyLighting()
        {
            var r = m_Look.render;
            keyLight.type = LightType.Directional;
            keyLight.shadows = LightShadows.Soft;
            keyLight.transform.rotation = Quaternion.Euler(r.light_euler_deg[0], r.light_euler_deg[1], r.light_euler_deg[2]);
            keyLight.intensity = r.light_intensity;
            RenderSettings.ambientMode = AmbientMode.Flat;
            RenderSettings.ambientLight = Grey(r.ambient_grey);
            RenderSettings.skybox = null;
            RenderSettings.fog = false;
        }

        static Color Grey(float g) => new Color(g, g, g, 1f);

        Stage BuildStage(int index, string look, float distance)
        {
            var st = new Stage { Index = index, Look = look, Distance = distance };
            var root = new GameObject($"Stage_{look}_{distance.ToString("0.0", Inv)}m").transform;
            root.position = new Vector3(index * m_Play.stage_spacing_m, 0f, 0f);
            st.Root = root;
            BuildBackdrop(root, distance);
            st.Robot = new GameObject("Robot").transform;               // stands in for the robot: forward +Z
            st.Robot.SetParent(root, false);
            var mount = new GameObject("PanTiltMount");                   // the camera height lives on the mount:
            mount.transform.SetParent(st.Robot, false);                   // ApplyCameraSettings zeroes the camera's own
            mount.transform.localPosition = new Vector3(0f, m_Pt.height_m, 0f);   // local position (as on the robot)
            var camGo = new GameObject("PanTiltCamera");
            camGo.transform.SetParent(mount.transform, false);
            st.Cam = camGo.AddComponent<Camera>();
            PanTiltCamera.ApplyCameraSettings(st.Cam, m_Pt);
            st.Cam.fieldOfView = m_Look.recording.vertical_fov_deg;
            st.Cam.clearFlags = CameraClearFlags.SolidColor;
            st.Cam.backgroundColor = Grey(m_Look.render.backdrop_grey);
            st.Cam.enabled = false;                                       // rendered on demand only
            st.Rt = new RenderTexture(m_Pt.width_px, m_Pt.height_px, 24, RenderTextureFormat.ARGB32) { name = "LookCheckPlay_" + index };
            st.Rt.Create();
            st.Tex = new Texture2D(m_Pt.width_px, m_Pt.height_px, TextureFormat.RGBA32, false);

            var w = Instantiate(workerPrefab, root);
            w.name = "WorkerV4_" + look;
            w.lookId = look;
            w.workerId = index + 1;
            w.robot = st.Robot;
            w.robotEye = st.Cam.transform;
            w.transform.localPosition = new Vector3(0f, 0f, distance);
            w.transform.localRotation = Quaternion.Euler(0f, 180f + m_Play.initial_yaw_offset_deg, 0f);
            if (!w.Initialize()) { st.Error = w.Problem; return st; }
            w.SetRun(m_Play.seed, 1);
            st.Worker = w;
            st.Rng = SeededRandom.For(m_Play.seed, 1000 + index, w.workerId);
            st.Truth = root.gameObject.AddComponent<TruthLogger>();
            string truthName = $"{look}__{distance.ToString("0.0", Inv)}.jsonl";
            st.Truth.Begin(Path.Combine(OutputFolder, "truth", truthName), new[] { w }, m_Worker.truth_log.interval_s);
            st.Record = new WorkerRecord { worker_id = w.workerId, look = look, description = w.LookDescription, distance_m = distance, truth_file = "truth/" + truthName };
            return st;
        }

        void BuildBackdrop(Transform root, float distance)
        {
            var r = m_Look.render;
            var lit = Shader.Find("Universal Render Pipeline/Lit");
            var floor = GameObject.CreatePrimitive(PrimitiveType.Quad);
            floor.name = "Floor";
            floor.transform.SetParent(root, false);
            floor.transform.localPosition = new Vector3(0f, 0f, r.floor_half_size_m * 0.5f);
            floor.transform.localRotation = Quaternion.Euler(90f, 0f, 0f);
            floor.transform.localScale = new Vector3(2f * r.floor_half_size_m, 2f * r.floor_half_size_m, 1f);
            floor.GetComponent<Renderer>().sharedMaterial = new Material(lit) { color = Grey(r.floor_grey), name = "LookCheckFloor" };
            var wall = GameObject.CreatePrimitive(PrimitiveType.Quad);
            wall.name = "Backdrop";
            wall.transform.SetParent(root, false);
            float h = 4f * r.floor_half_size_m;
            wall.transform.localPosition = new Vector3(0f, 0.5f * h, distance + r.backdrop_behind_person_m);
            wall.transform.localScale = new Vector3(4f * r.floor_half_size_m, h, 1f);
            wall.GetComponent<Renderer>().sharedMaterial = new Material(lit) { color = Grey(r.backdrop_grey), name = "LookCheckBackdrop" };
            foreach (var go in new[] { floor, wall }) Destroy(go.GetComponent<Collider>());
        }

        // ---------------------------------------------------------------- one stage's recordings

        IEnumerator RunStage(Stage st)
        {
            var w = st.Worker;
            yield return new WaitForSeconds(0.5f);
            // Stand the look on the floor (as the Edit-mode check): the lowest mesh point at the floor.
            if (LookInventory.MeshExtentY(w.LookInstance, out float bottom, out float top))
            {
                st.Record.ground_shift_m = -(bottom - st.Root.position.y);
                w.transform.position -= new Vector3(0f, bottom - st.Root.position.y, 0f);
                st.Record.height_m = (float)Math.Round(top - bottom, 3);
            }
            Measure(st);
            yield return WaitFacing(st);

            float d = st.Distance;
            for (int k = 1; k <= m_Play.none_sequences; k++)
                yield return CaptureIdle(st, LookCheckConfig.RecordingName(st.Look, LookCheckConfig.None, d, "", "seq" + k), m_Look.recording.sequence_frames, 0.1f);
            for (int k = 1; k <= m_Play.none_singles; k++)
            {
                yield return new WaitForSeconds(m_Play.none_frame_spacing_s);
                yield return CaptureIdle(st, LookCheckConfig.RecordingName(st.Look, LookCheckConfig.None, d, "", "f" + k), 1, 0f);
            }
            foreach (var cmd in WorkerV4Config.Commands)
            {
                var clips = m_Worker.ClipNames(cmd);
                foreach (var arm in m_Look.recording.arms)
                {
                    for (int i = 0; i < (m_Quick ? 1 : clips.Count) && st.Error == null; i++)
                        yield return Perform(st, cmd, arm, clips[i], m_Play.point_side_azimuth_deg[i], false,
                                             LookCheckConfig.RecordingName(st.Look, cmd, d, arm, clips[i]));
                    for (int k = 0; k < (m_Quick ? 0 : m_Play.singles_per_group) && st.Error == null; k++)
                    {
                        string clip = clips[k % clips.Count];
                        yield return Perform(st, cmd, arm, clip, m_Play.single_point_side_azimuth_deg[k], true,
                                             LookCheckConfig.RecordingName(st.Look, cmd, d, arm, $"f{k + 1}_{clip}"));
                    }
                }
            }
            st.Done = true;
        }

        void Measure(Stage st)
        {
            var a = st.Worker.Animator;
            Transform B(HumanBodyBones b) => a.GetBoneTransform(b);
            float shoulder = Vector3.Distance(B(HumanBodyBones.LeftUpperArm).position, B(HumanBodyBones.RightUpperArm).position);
            st.Record.arm_length_m = (float)Math.Round(st.Worker.ArmLength, 4);
            st.Record.shoulder_width_m = (float)Math.Round(shoulder, 4);
            st.Record.arm_to_shoulder_ratio = shoulder > 0f ? (float)Math.Round(st.Worker.ArmLength / shoulder, 3) : -1f;
        }

        IEnumerator WaitFacing(Stage st)
        {
            float until = Time.time + m_Play.face_wait_max_s;
            yield return null;
            while (Time.time < until && (st.Worker.Turning || !st.Worker.Noticed)) yield return null;
            yield return new WaitForSeconds(0.3f);
        }

        IEnumerator CaptureIdle(Stage st, string name, int frames, float spacing)
        {
            var rec = NewRecord(st, name, LookCheckConfig.None, "", "", frames);
            string seqDir = frames > 1 ? Path.Combine(RecordingFolder, name) : null;
            if (seqDir != null) Directory.CreateDirectory(seqDir);
            float t0 = Time.time;
            for (int i = 0; i < frames; i++)
            {
                while (Time.time < t0 + i * spacing) yield return null;
                yield return new WaitForEndOfFrame();
                Capture(st, rec, seqDir, i, "");
            }
            m_Records.Add(rec);
        }

        IEnumerator Perform(Stage st, string cmd, string arm, string clip, float sideAz, bool single, string name)
        {
            var w = st.Worker;
            yield return WaitFacing(st);
            w.BodyFrame(out _, out var fwd);
            float bodyAz = (arm == "right" ? 1f : -1f) * (90f - sideAz);
            var req = new GestureRequest
            {
                Command = cmd, Clip = clip, Arm = arm, PointDirection = Quaternion.AngleAxis(bodyAz, Vector3.up) * fwd,
            };
            w.IsCommander = true;
            if (!w.Request(req, out string error)) { st.Error = $"{name}: {error}"; w.IsCommander = false; yield break; }
            yield return new WaitForSeconds(m_Play.question_after_request_s);
            w.SetQuestionVisible(true);                                       // "Which direction?" appears
            float until = Time.time + m_Play.phase_wait_max_s;
            while (w.Phase != WorkerPhase.Holding && Time.time < until) yield return null;
            if (w.Phase != WorkerPhase.Holding) { st.Error = $"{name}: the worker never reached its hold"; yield break; }
            float holdStart = Time.time;
            int ikBefore = w.HandIkCalls;
            var rec = NewRecord(st, name, cmd, arm, clip, single ? 1 : m_Look.recording.sequence_frames);
            rec.point_side_azimuth_deg = cmd == WorkerV4Config.Point ? sideAz : -1f;
            var p = w.Current;
            rec.speed = p.speed; rec.size = p.size; rec.start_delay_s = p.start_delay_s; rec.hold_s = p.hold_s;
            if (single)
            {
                float lo = m_Play.settle_after_hold_s, hi = Mathf.Max(lo, p.hold_s - 0.3f);
                float at = holdStart + lo + (float)st.Rng.NextDouble() * (hi - lo);
                while (Time.time < at) yield return null;
                yield return new WaitForEndOfFrame();
                Capture(st, rec, null, 0, arm);
            }
            else
            {
                string seqDir = Path.Combine(RecordingFolder, name);
                Directory.CreateDirectory(seqDir);
                float t0 = holdStart + m_Play.settle_after_hold_s;
                for (int i = 0; i < m_Look.recording.sequence_frames; i++)
                {
                    while (Time.time < t0 + i * 0.1f) yield return null;
                    yield return new WaitForEndOfFrame();
                    Capture(st, rec, seqDir, i, arm);
                }
            }
            rec.hand_ik_calls = w.HandIkCalls - ikBefore;
            if (rec.hand_ik_calls == 0) { st.Error = $"{name}: Humanoid IK never set the hand (OnAnimatorIK not called)"; yield break; }
            m_Records.Add(rec);
            while (w.Phase != WorkerPhase.Idle && Time.time < until + 30f) yield return null;
            w.SetQuestionVisible(false);
            w.IsCommander = false;
            yield return new WaitForSeconds(m_Play.pause_between_s);
        }

        RecordingRecord NewRecord(Stage st, string name, string cmd, string arm, string clip, int frames) => new RecordingRecord
        {
            name = name, kind = frames > 1 ? "sequence" : "frame", look = st.Look, command = cmd, arm = arm, clip = clip,
            worker_id = st.Worker.workerId, n_frames = frames, distance_m = st.Distance, vertical_fov_deg = m_Look.recording.vertical_fov_deg,
            point_side_azimuth_deg = -1f, point_angle_deg = -1f, time_first_s = -1f, time_last_s = -1f,
        };

        // ---------------------------------------------------------------- capture

        /// <summary>Render the stage camera now (end of frame: after the Animator, IK and the hand shapes) and queue the PNG and header.</summary>
        void Capture(Stage st, RecordingRecord rec, string seqDir, int frameIndex, string arm)
        {
            var w = st.Worker;
            float t = Time.time;
            bool held = rec.command == LookCheckConfig.None ? w.Phase == WorkerPhase.Idle : w.Phase == WorkerPhase.Holding;
            if (!held) { rec.frames_outside_hold++; m_Outside++; }
            if (rec.time_first_s < 0f) rec.time_first_s = t;
            rec.time_last_s = t;
            var truth = w.Truth(t);
            if (m_Quick) Debug.Log($"[LookCheckPlay] {rec.name} frame {frameIndex}: {w.DebugState()}");
            if (rec.command == WorkerV4Config.Point) rec.point_angle_deg = (float)truth.PointAngleDeg;
            if (rec.command != LookCheckConfig.None) rec.hand_to_target_max_m = Mathf.Max(rec.hand_to_target_max_m, w.HandToTargetM);

            var prevTarget = st.Cam.targetTexture;
            var prevActive = RenderTexture.active;
            st.Cam.targetTexture = st.Rt;
            st.Cam.Render();
            RenderTexture.active = st.Rt;
            st.Tex.ReadPixels(new Rect(0, 0, st.Rt.width, st.Rt.height), 0, 0, false);
            st.Tex.Apply(false);
            st.Cam.targetTexture = prevTarget;
            RenderTexture.active = prevActive;
            byte[] raw = st.Tex.GetRawTextureData();
            var fmt = st.Tex.graphicsFormat;
            int width = st.Rt.width, height = st.Rt.height;
            string stem = seqDir != null ? Path.Combine(seqDir, LookCheckConfig.FrameStem(frameIndex)) : Path.Combine(RecordingFolder, rec.name);
            string header = Header(st, frameIndex, t, arm, rec, truth);
            m_Frames++;
            m_Writes.Add(Task.Run(() =>
            {
                try
                {
                    byte[] png = ImageConversion.EncodeArrayToPNG(raw, fmt, (uint)width, (uint)height);
                    WriteNew(stem + ".png", png);
                    WriteNew(stem + ".json", header);
                }
                catch (Exception e)
                {
                    lock (m_WriteErrors) m_WriteErrors.Add(stem + ": " + e.Message);
                }
            }));
        }

        /// <summary>The frame_pan_tilt header of protocol 3 for this render (docs/look_check_v4.md), with the real Time.time.</summary>
        string Header(Stage st, int frameIndex, float t, string arm, RecordingRecord rec, TruthRow truth)
        {
            int w = m_Pt.width_px, h = m_Pt.height_px;
            double fov = m_Look.recording.vertical_fov_deg;
            LookCheckConfig.Intrinsics(w, h, fov, out double fx, out double fy, out double cx, out double cy);
            string N(double x) => x.ToString("R", Inv);
            string F(float x) => x.ToString("R", Inv);
            var p = st.Robot.position;
            var sb = new StringBuilder();
            sb.Append("{\n  \"version\": 3,\n  \"type\": \"frame_pan_tilt\",\n");
            sb.Append($"  \"time_s\": {N(t)},\n");
            sb.Append($"  \"frame_index\": {frameIndex.ToString(Inv)},\n");
            sb.Append($"  \"width\": {w.ToString(Inv)},\n  \"height\": {h.ToString(Inv)},\n");
            sb.Append($"  \"fx\": {N(fx)},\n  \"fy\": {N(fy)},\n  \"cx\": {N(cx)},\n  \"cy\": {N(cy)},\n");
            sb.Append($"  \"vertical_fov_deg\": {N(fov)},\n  \"pan_deg\": 0.0,\n  \"tilt_deg\": 0.0,\n");
            sb.Append($"  \"camera_height_m\": {F(m_Pt.height_m)},\n");
            sb.Append($"  \"pose\": {{\"x\": {N(p.x)}, \"z\": {N(p.z)}, \"yaw_deg\": 0.0}},\n");
            sb.Append("  \"encoding\": \"png\",\n");
            if (!string.IsNullOrEmpty(arm)) sb.Append($"  \"arm\": \"{arm}\",\n");
            sb.Append($"  \"look_check_play\": {{\"worker_id\": {st.Worker.workerId.ToString(Inv)}, \"variant\": \"{rec.clip}\", \"phase\": \"{truth.Phase}\", " +
                      $"\"speed\": {N(Math.Round(rec.speed, 4))}, \"size\": {N(Math.Round(rec.size, 4))}}}\n");
            sb.Append("}\n");
            return sb.ToString();
        }

        // ---------------------------------------------------------------- files

        static string NewFolder(string root, string name)
        {
            Directory.CreateDirectory(root);
            string path = Path.Combine(root, name);
            for (int i = 2; Directory.Exists(path); i++) path = Path.Combine(root, $"{name}_{i}");
            Directory.CreateDirectory(path);
            return path;
        }

        static void WriteNew(string path, string text) => WriteNew(path, Utf8.GetBytes(text));

        static void WriteNew(string path, byte[] bytes)
        {
            using (var fs = new FileStream(path, FileMode.CreateNew, FileAccess.Write)) fs.Write(bytes, 0, bytes.Length);
        }

        static string Sha256(string text)
        {
            using (var sha = System.Security.Cryptography.SHA256.Create())
            {
                var sb = new StringBuilder();
                foreach (var b in sha.ComputeHash(Utf8.GetBytes(text))) sb.Append(b.ToString("x2", Inv));
                return sb.ToString();
            }
        }

        void Git(out string commit, out string branch)
        {
            commit = branch = "unknown";
            try
            {
                string gitDir = Path.Combine(RepoRoot, ".git");
                string head = File.ReadAllText(Path.Combine(gitDir, "HEAD")).Trim();
                if (!head.StartsWith("ref:")) { commit = head; branch = "(detached)"; return; }
                string reference = head.Substring(4).Trim();
                branch = reference.StartsWith("refs/heads/") ? reference.Substring(11) : reference;
                string refFile = Path.Combine(gitDir, reference.Replace('/', Path.DirectorySeparatorChar));
                if (File.Exists(refFile)) { commit = File.ReadAllText(refFile).Trim(); return; }
                string packed = Path.Combine(gitDir, "packed-refs");
                if (File.Exists(packed))
                    foreach (var l in File.ReadAllLines(packed))
                        if (l.EndsWith(" " + reference)) { commit = l.Substring(0, l.IndexOf(' ')); return; }
            }
            catch (Exception e)
            {
                Debug.LogWarning("[LookCheckPlay] could not read the git commit: " + e.Message);
            }
        }

        void OnDestroy()
        {
            foreach (var t in FindObjectsByType<TruthLogger>(FindObjectsSortMode.None)) t.End();
        }
    }
}
