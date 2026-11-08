using System;
using System.Collections;
using System.Collections.Generic;
using System.Globalization;
using System.IO;
using System.Text;
using System.Threading.Tasks;
using UnityEngine;
using UnityEngine.Rendering;
using WarehouseAvatar;
using WarehouseHRI;
using WarehouseRobot.Bridge;
using WarehouseRobot.Scenario;

namespace WarehouseRobot.AvatarCheck
{
    /// <summary>
    /// v4 Play-mode look check (look_check_play.json; venue and takes changed in Phase 2D, 2026-11-08, declared in
    /// Avatar/Config/look_check_changes.md before the rerun). The worker template performs the real gesture variants in
    /// Play mode inside WarehouseRobot_v4.unity (its own lights, baked lighting and surroundings; the scene file is not
    /// changed) at the Task 2 worker stands, and cameras with the pan-tilt settings of robot_unity_v4.json record them from
    /// the robot's asking positions, in the input format of docs/look_check_v4.md (Anisha's look_check_v4.py), with the
    /// real Unity Time.time of every frame. LookCheckPlayMenu adds this driver at Play; its Awake switches off the
    /// study's runtime parts (trial runner, bridge, v3 workers, robot body) before they start, so nothing connects to
    /// Python and no session is written.
    /// Every take is an independent performance (its own variation stream and its own camera pose, drawn from a seeded
    /// stream within the declared bearing and distance bands); a 2 m and a 4 m camera on the same bearing record it.
    /// Each round runs one look at each junction at the same time; over the rounds every look visits every junction.
    /// Writes robot_vision/outputs/look_check_play_&lt;time&gt;/ (never overwrites): looks_check_&lt;time&gt;/ (recordings only),
    /// recordings.jsonl, workers.json, truth/, config_used/, run_info.json. An engineering check, not an evaluation.
    /// </summary>
    [DefaultExecutionOrder(-1000)]
    public class LookCheckPlayDriver : MonoBehaviour
    {
        public TextAsset playConfig;
        public TextAsset lookCheckConfig;
        public TextAsset robotConfig;
        public WorkerV4 workerPrefab;
        public string repoRootRelativeToProject = "../../..";
        public bool runOnStart = true;

        public string Status { get; private set; } = "idle";
        public string OutputFolder { get; private set; } = "";
        public string RecordingFolder { get; private set; } = "";
        /// <summary>What Awake switched off in the scene (reported in run_info.json).</summary>
        public string SceneChanges { get; private set; } = "";

        static readonly CultureInfo Inv = CultureInfo.InvariantCulture;
        static readonly UTF8Encoding Utf8 = new UTF8Encoding(false);

        [Serializable]
        public class PlayConfig
        {
            public PlayOutput output;
            public string[] looks;
            public int seed;
            public PlayVenue venue;
            public PlayTakes takes;
            public float settle_after_hold_s, question_after_request_s, pause_between_s;
            public float face_wait_max_s, phase_wait_max_s, initial_yaw_offset_deg;
        }

        [Serializable] public class PlayOutput { public string root, run_prefix, recordings_prefix; }

        [Serializable]
        public class PlayVenue
        {
            public string scene;
            public string[] junctions;
            public float[] approach_bearing_deg;
            public float distance_tolerance_m, camera_clearance_m, head_height_m, hips_height_m;
            public int max_pose_draws;
        }

        [Serializable]
        public class PlayTakes
        {
            public int sequences_per_group, singles_per_group;
            public float[] sequence_point_side_azimuth_deg, single_point_side_azimuth_deg;
        }

        [Serializable]
        class RecordingRecord
        {
            public string name, kind, look, command, arm, clip, junction;
            public int worker_id, take, variation_run, pose_draws, n_frames, frames_outside_hold, hand_ik_calls;
            public float distance_m, camera_distance_m, approach_bearing_deg, camera_x, camera_z, camera_yaw_deg;
            public float vertical_fov_deg, time_first_s, time_last_s;
            public float speed, size, start_delay_s, hold_s, point_side_azimuth_deg, point_angle_deg;
            public float hand_to_target_max_m = -1f;
            /// <summary>Stillness over the recording: the largest distance of the gesturing hand and shoulder from their
            /// positions at the first frame (-1 for NONE).</summary>
            public float hand_motion_max_m = -1f, shoulder_motion_max_m = -1f;
            [NonSerialized] public Vector3 FirstHand, FirstShoulder;
        }

        [Serializable]
        class WorkerRecord
        {
            public int worker_id, round;
            public string look, junction, description, truth_file;
            public float stand_x, stand_z, arm_length_m, shoulder_width_m, arm_to_shoulder_ratio, height_m, ground_shift_m;
            public int truth_lines;
            public string truth_failed;
        }

        [Serializable] class WorkersFile { public List<WorkerRecord> workers = new List<WorkerRecord>(); }

        [Serializable]
        class RunInfo
        {
            public string created_local, finished_local, git_commit, git_branch, unity_version, render_pipeline, color_space, graphics_device;
            public string scene, scene_changes_in_play_mode;
            public string play_config_sha256, look_check_sha256, worker_config_sha256, robot_unity_config_sha256, clip_index_sha256;
            public int recordings, frames, frames_outside_hold;
            public string status, note;
        }

        /// <summary>One camera of a site: the nominal distance it stands for (2.0 or 4.0 m) and its render targets.</summary>
        sealed class SiteCamera
        {
            public float Nominal;
            public Transform Mount;
            public Camera Cam;
            public RenderTexture Rt;
            public Texture2D Tex;
            public float Distance;      // drawn for the current take
        }

        /// <summary>A Task 2 junction's worker stand with its cameras; a new worker (look) per round.</summary>
        sealed class Site
        {
            public int Index;
            public string Junction;
            public Vector3 Stand, Facing;   // stand on the floor; horizontal unit facing (toward the arriving robot)
            public float Side;              // +1 / -1: the junction lies on this side of Facing (bearings turn toward it)
            public Transform Root, Robot;
            public List<SiteCamera> Cams = new List<SiteCamera>();
            public SeededRandom PoseRng;
            public float Bearing;
            public int PoseDraws;
            // per round
            public string Look;
            public int Round;
            public WorkerV4 Worker;
            public TruthLogger Truth;
            public WorkerRecord Record;
            public int VariationRun;
            public string Error;
            public bool Done;
        }

        PlayConfig m_Play;
        LookCheckConfig m_Look;
        PanTiltCameraConfig m_Pt;
        WorkerV4Config m_Worker;
        readonly List<Task> m_Writes = new List<Task>();
        readonly List<RecordingRecord> m_Records = new List<RecordingRecord>();
        readonly List<WorkerRecord> m_WorkerRecords = new List<WorkerRecord>();
        readonly List<string> m_WriteErrors = new List<string>();
        int m_Frames, m_Outside;
        bool m_Quick;   // -lookCheckQuick: diagnostics only (one round, one take per command and arm, every capture logged)
        string m_Stamp;

        static string QuickLook()
        {
            var a = Environment.GetCommandLineArgs();
            int i = Array.IndexOf(a, "-lookCheckQuick");
            return i >= 0 && i + 1 < a.Length && !a[i + 1].StartsWith("-") ? a[i + 1] : "sunbox_m1";
        }

        void Awake() => SceneChanges = PrepareScene();

        /// <summary>
        /// Play mode only: switch off the v4 study's runtime parts before their Start, so the scene is only the venue
        /// (its lights and surroundings). The obstacle colliders built by the robot's ColliderSetup in Awake stay.
        /// </summary>
        public static string PrepareScene()
        {
            var done = new List<string>();
            foreach (var r in FindObjectsByType<TrialRunnerV4>(FindObjectsInactive.Include, FindObjectsSortMode.None))
            {
                r.runOnStart = false;
                r.enabled = false;
                done.Add("TrialRunnerV4 off");
            }
            foreach (var b in FindObjectsByType<RobotBridgeClient>(FindObjectsInactive.Include, FindObjectsSortMode.None))
            {
                b.enabled = false;
                done.Add("RobotBridgeClient off");
            }
            foreach (var g in FindObjectsByType<GestureWorker>(FindObjectsInactive.Include, FindObjectsSortMode.None))
            {
                g.gameObject.SetActive(false);
                done.Add($"v3 worker '{g.name}' hidden");
            }
            foreach (var r in FindObjectsByType<RobotRig>(FindObjectsInactive.Include, FindObjectsSortMode.None))
            {
                r.gameObject.SetActive(false);
                done.Add($"robot '{r.name}' hidden");
            }
            return string.Join("; ", done);
        }

        void Start()
        {
            if (runOnStart) StartCoroutine(Run());
        }

        string RepoRoot => Path.GetFullPath(Path.Combine(Application.dataPath, "..", repoRootRelativeToProject));

        bool Setup(out string error)
        {
            error = null;
            if (playConfig == null || lookCheckConfig == null || robotConfig == null || workerPrefab == null)
            {
                error = "assign playConfig, lookCheckConfig, robotConfig and workerPrefab (Tools > Warehouse v4 > Look Check > Run Play-Mode Look Check adds the driver)";
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
            var pe = Validate(m_Play, m_Worker, m_Look);
            if (pe.Count > 0) { error = "look_check_play.json: " + string.Join("; ", pe); return false; }
            if (gameObject.scene.path != m_Play.venue.scene) { error = $"the driver runs in {m_Play.venue.scene}, not in '{gameObject.scene.path}'"; return false; }
            return true;
        }

        /// <summary>The play config's own rules (also used by the Edit Mode tests through the JSON).</summary>
        static List<string> Validate(PlayConfig p, WorkerV4Config w, LookCheckConfig look)
        {
            var e = new List<string>();
            if (p.looks == null || p.looks.Length == 0) e.Add("no looks");
            else foreach (var l in p.looks) if (w.Look(l) == null) e.Add($"look '{l}' is not in worker_v4.json");
            foreach (var cmd in WorkerV4Config.Commands)
                if (w.ClipNames(cmd).Count < 2) e.Add($"worker_v4.json: fewer than 2 variants of {cmd}");
            var v = p.venue;
            if (v == null || string.IsNullOrEmpty(v.scene)) { e.Add("venue.scene missing"); return e; }
            if (v.junctions == null || v.junctions.Length == 0) e.Add("venue.junctions missing");
            if (v.approach_bearing_deg == null || v.approach_bearing_deg.Length != 2 || !(v.approach_bearing_deg[0] >= 0f) ||
                !(v.approach_bearing_deg[1] > v.approach_bearing_deg[0]) || v.approach_bearing_deg[1] > 90f)
                e.Add("venue.approach_bearing_deg must be [low, high] within 0..90");
            if (!(v.distance_tolerance_m >= 0f && v.distance_tolerance_m < 0.5f)) e.Add("venue.distance_tolerance_m must be 0 to 0.5");
            if (!(v.camera_clearance_m > 0f)) e.Add("venue.camera_clearance_m must be > 0");
            if (!(v.head_height_m > v.hips_height_m && v.hips_height_m > 0f)) e.Add("venue.head_height_m and hips_height_m");
            if (v.max_pose_draws < 1) e.Add("venue.max_pose_draws must be >= 1");
            var t = p.takes;
            if (t == null) { e.Add("takes missing"); return e; }
            int nj = v.junctions != null ? Math.Max(1, v.junctions.Length) : 1;
            if (t.sequences_per_group < 2) e.Add("takes.sequences_per_group must be >= 2 (docs/look_check_v4.md)");
            if (t.sequences_per_group < nj) e.Add("takes.sequences_per_group must give every junction a sequence");
            if (t.sequences_per_group + t.singles_per_group < 10) e.Add("a group needs at least 10 frames");
            if (t.sequence_point_side_azimuth_deg == null || t.sequence_point_side_azimuth_deg.Length < t.sequences_per_group)
                e.Add("takes.sequence_point_side_azimuth_deg needs one direction per sequence");
            if (t.single_point_side_azimuth_deg == null || t.single_point_side_azimuth_deg.Length == 0)
                e.Add("takes.single_point_side_azimuth_deg missing");
            if (!(w.variation.hold_s[0] > p.settle_after_hold_s + (look.recording.sequence_frames - 1) * 0.1f + 0.3f))
                e.Add("worker_v4.json hold_s is too short for a full sequence inside the hold");
            return e;
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

            QualitySettings.vSyncCount = 0;
            Application.targetFrameRate = 60;
            var sites = new List<Site>();
            foreach (var j in m_Play.venue.junctions)
            {
                var site = BuildSite(sites.Count, j, out string siteError);
                if (site == null) { Finish($"failed: junction {j}: {siteError}"); yield break; }
                sites.Add(site);
            }
            Status = "running";
            var looks = m_Play.looks;
            int rounds = m_Quick ? 1 : looks.Length;
            for (int round = 0; round < rounds; round++)
            {
                foreach (var s in sites)
                {
                    string look = m_Quick ? QuickLook() : looks[(round + s.Index) % looks.Length];
                    if (!SpawnWorker(s, round, look)) { Finish($"failed: {look} at {s.Junction}: {s.Error}"); yield break; }
                }
                foreach (var s in sites) StartCoroutine(RunSite(s, sites.Count));
                while (!sites.TrueForAll(s => s.Done)) yield return null;
                foreach (var s in sites)
                {
                    s.Truth.End();
                    s.Record.truth_lines = s.Truth.Lines;
                    s.Record.truth_failed = s.Truth.Failed;
                    m_WorkerRecords.Add(s.Record);
                    if (s.Error != null) { Finish($"failed: {s.Look} at {s.Junction}: {s.Error}"); yield break; }
                    Destroy(s.Truth);
                    Destroy(s.Worker.gameObject);
                }
                yield return null;
            }

            Status = "writing";
            var all = Task.WhenAll(m_Writes);
            while (!all.IsCompleted) yield return null;
            var lines = new StringBuilder();
            foreach (var r in m_Records) lines.Append(JsonUtility.ToJson(r)).Append('\n');
            WriteNew(Path.Combine(OutputFolder, "recordings.jsonl"), lines.ToString());
            var wf = new WorkersFile { workers = m_WorkerRecords };
            WriteNew(Path.Combine(OutputFolder, "workers.json"), JsonUtility.ToJson(wf, true).Replace("\r\n", "\n") + "\n");

            var errors = new List<string>();
            foreach (var w in m_WorkerRecords) if (!string.IsNullOrEmpty(w.truth_failed)) errors.Add($"{w.look} at {w.junction} truth: {w.truth_failed}");
            lock (m_WriteErrors) errors.AddRange(m_WriteErrors);
            Git(out info.git_commit, out info.git_branch);
            info.finished_local = DateTime.Now.ToString("yyyy-MM-dd'T'HH:mm:ss", Inv);
            info.unity_version = Application.unityVersion;
            info.render_pipeline = GraphicsSettings.currentRenderPipeline != null ? GraphicsSettings.currentRenderPipeline.name : "built-in";
            info.color_space = QualitySettings.activeColorSpace.ToString();
            info.graphics_device = SystemInfo.graphicsDeviceType + " " + SystemInfo.graphicsDeviceName;
            info.scene = gameObject.scene.path;
            info.scene_changes_in_play_mode = SceneChanges;
            info.play_config_sha256 = Sha256(playConfig.text);
            info.look_check_sha256 = Sha256(lookCheckConfig.text);
            info.worker_config_sha256 = Sha256(workerPrefab.config.text);
            info.robot_unity_config_sha256 = Sha256(robotConfig.text);
            info.clip_index_sha256 = index != null ? Sha256(index.text) : "";
            info.recordings = m_Records.Count;
            info.frames = m_Frames;
            info.frames_outside_hold = m_Outside;
            info.status = errors.Count == 0 ? "done" : "done with problems: " + string.Join("; ", errors);
            info.note = "v4 Play-mode look check in WarehouseRobot_v4.unity at the Task 2 worker stands (Phase 2D, look_check_changes.md): an engineering check of the worker template's looks and gestures; not an evaluation.";
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

        // ---------------------------------------------------------------- sites

        Site BuildSite(int index, string junction, out string error)
        {
            error = null;
            RoadNode node = null;
            foreach (var n in FindObjectsByType<RoadNode>(FindObjectsSortMode.None)) if (n.name == junction) node = n;
            if (node == null || !node.IsJunction || node.workerStand == null) { error = "no junction with a worker stand of that name in the scene"; return null; }
            var stand = node.workerStand;
            var facing = Vector3.ProjectOnPlane(stand.forward, Vector3.up).normalized;
            var toJunction = Vector3.ProjectOnPlane(node.transform.position - stand.position, Vector3.up);
            var site = new Site
            {
                Index = index, Junction = junction, Stand = stand.position, Facing = facing,
                Side = Vector3.SignedAngle(facing, toJunction, Vector3.up) >= 0f ? 1f : -1f,
                PoseRng = SeededRandom.For(m_Play.seed, 5000 + index, 1),
            };
            site.Root = new GameObject($"LookCheckSite_{junction}").transform;
            site.Robot = new GameObject("Robot").transform;               // stands in for the asking robot (the 2 m camera's floor point)
            site.Robot.SetParent(site.Root, false);
            foreach (float d in m_Look.recording.distances_m)
            {
                var c = new SiteCamera { Nominal = d };
                c.Mount = new GameObject($"PanTiltMount_{d.ToString("0.0", Inv)}m").transform;
                c.Mount.SetParent(site.Root, false);
                var camGo = new GameObject("PanTiltCamera");
                camGo.transform.SetParent(c.Mount, false);
                c.Cam = camGo.AddComponent<Camera>();
                PanTiltCamera.ApplyCameraSettings(c.Cam, m_Pt);          // local position zero, level: the height is the mount's
                c.Cam.fieldOfView = m_Look.recording.vertical_fov_deg;
                c.Cam.enabled = false;                                    // rendered on demand only
                c.Rt = new RenderTexture(m_Pt.width_px, m_Pt.height_px, 24, RenderTextureFormat.ARGB32) { name = $"LookCheck_{junction}_{d}" };
                c.Rt.Create();
                c.Tex = new Texture2D(m_Pt.width_px, m_Pt.height_px, TextureFormat.RGBA32, false);
                site.Cams.Add(c);
            }
            return site;
        }

        bool SpawnWorker(Site s, int round, string look)
        {
            s.Look = look;
            s.Round = round;
            s.Done = false;
            s.Error = null;
            var w = Instantiate(workerPrefab, s.Root);
            w.name = "WorkerV4_" + look;
            w.lookId = look;
            w.workerId = round * m_Play.venue.junctions.Length + s.Index + 1;
            w.robot = s.Robot;
            w.robotEye = s.Cams[0].Cam.transform;
            w.transform.position = s.Stand;
            w.transform.rotation = Quaternion.LookRotation(Quaternion.AngleAxis(m_Play.initial_yaw_offset_deg, Vector3.up) * s.Facing, Vector3.up);
            if (!w.Initialize()) { s.Error = w.Problem; return false; }
            s.Worker = w;
            s.VariationRun = 0;
            s.Truth = s.Root.gameObject.AddComponent<TruthLogger>();
            string truthName = $"{look}__{s.Junction.ToLowerInvariant()}.jsonl";
            s.Truth.Begin(Path.Combine(OutputFolder, "truth", truthName), new[] { w }, m_Worker.truth_log.interval_s);
            s.Record = new WorkerRecord
            {
                worker_id = w.workerId, round = round + 1, look = look, junction = s.Junction, description = w.LookDescription,
                truth_file = "truth/" + truthName, stand_x = s.Stand.x, stand_z = s.Stand.z,
            };
            return true;
        }

        /// <summary>
        /// Draw this take's camera pose: a bearing toward the junction side and one distance per camera within the
        /// declared bands; redrawn until both cameras are clear of every collider and see the person's head and hips.
        /// </summary>
        bool PlaceCameras(Site s)
        {
            var v = m_Play.venue;
            for (int draw = 1; draw <= v.max_pose_draws; draw++)
            {
                float bearing = Mathf.Lerp(v.approach_bearing_deg[0], v.approach_bearing_deg[1], (float)s.PoseRng.NextDouble());
                var dir = Quaternion.AngleAxis(s.Side * bearing, Vector3.up) * s.Facing;
                bool ok = true;
                foreach (var c in s.Cams)
                {
                    c.Distance = c.Nominal + v.distance_tolerance_m * (2f * (float)s.PoseRng.NextDouble() - 1f);
                    var floor = s.Stand + dir * c.Distance;
                    c.Mount.SetPositionAndRotation(floor + Vector3.up * m_Pt.height_m, Quaternion.LookRotation(-dir, Vector3.up));
                    if (!Clear(s, c.Mount.position)) ok = false;
                }
                if (!ok) continue;
                s.Bearing = bearing;
                s.PoseDraws = draw;
                var near = s.Cams[0];
                s.Robot.SetPositionAndRotation(s.Stand + dir * near.Distance, Quaternion.LookRotation(-dir, Vector3.up));
                return true;
            }
            s.Error = $"no clear camera pose in {v.max_pose_draws} draws";
            return false;
        }

        bool Clear(Site s, Vector3 cam)
        {
            var v = m_Play.venue;
            foreach (var c in Physics.OverlapSphere(cam, v.camera_clearance_m, ~0, QueryTriggerInteraction.Ignore))
                if (!Mine(s, c)) return false;
            foreach (float h in new[] { v.head_height_m, v.hips_height_m })
            {
                Vector3 to = s.Stand + Vector3.up * h;
                foreach (var hit in Physics.RaycastAll(cam, to - cam, Vector3.Distance(cam, to), ~0, QueryTriggerInteraction.Ignore))
                    if (!Mine(s, hit.collider)) return false;
            }
            return true;
        }

        static bool Mine(Site s, Collider c) => s.Worker != null && c.transform.IsChildOf(s.Worker.transform);

        IEnumerator RunSite(Site s, int junctionCount)
        {
            var w = s.Worker;
            yield return new WaitForSeconds(0.5f);
            // Stand the look on the floor (as the Edit-mode check): the lowest mesh point at the stand's height.
            if (LookInventory.MeshExtentY(w.LookInstance, out float bottom, out float top))
            {
                s.Record.ground_shift_m = -(bottom - s.Stand.y);
                w.transform.position -= new Vector3(0f, bottom - s.Stand.y, 0f);
                s.Record.height_m = (float)Math.Round(top - bottom, 3);
            }
            Measure(s);
            var t = m_Play.takes;
            int takes = m_Quick ? junctionCount : t.sequences_per_group + t.singles_per_group;
            for (int take = 0; take < takes && s.Error == null; take++)
            {
                if (!Mine(take, s.Index, junctionCount)) continue;
                if (!PlaceCameras(s)) break;
                yield return WaitFacing(s);
                yield return CaptureIdle(s, take);
            }
            foreach (var cmd in WorkerV4Config.Commands)
            {
                var clips = m_Worker.ClipNames(cmd);
                foreach (var arm in m_Look.recording.arms)
                    for (int take = 0; take < takes && s.Error == null; take++)
                        if (Mine(take, s.Index, junctionCount)) yield return Perform(s, cmd, arm, clips, take);
            }
            s.Done = true;
        }

        /// <summary>Takes are shared out over the junctions: sequence i and single k go to junction i (k) modulo their number.</summary>
        bool Mine(int take, int site, int junctions)
        {
            int seqs = m_Quick ? junctions : m_Play.takes.sequences_per_group;
            int k = take < seqs ? take : take - seqs;
            return k % junctions == site;
        }

        bool IsSequence(int take) => take < (m_Quick ? m_Play.venue.junctions.Length : m_Play.takes.sequences_per_group);

        string TakeName(Site s, int take, string clip)
        {
            int seqs = m_Quick ? m_Play.venue.junctions.Length : m_Play.takes.sequences_per_group;
            string label = IsSequence(take) ? $"s{take + 1}" : $"f{take - seqs + 1}";
            return $"{label}_{s.Junction.ToLowerInvariant()}" + (string.IsNullOrEmpty(clip) ? "" : "_" + clip);
        }

        void Measure(Site s)
        {
            var a = s.Worker.Animator;
            Transform B(HumanBodyBones b) => a.GetBoneTransform(b);
            float shoulder = Vector3.Distance(B(HumanBodyBones.LeftUpperArm).position, B(HumanBodyBones.RightUpperArm).position);
            s.Record.arm_length_m = (float)Math.Round(s.Worker.ArmLength, 4);
            s.Record.shoulder_width_m = (float)Math.Round(shoulder, 4);
            s.Record.arm_to_shoulder_ratio = shoulder > 0f ? (float)Math.Round(s.Worker.ArmLength / shoulder, 3) : -1f;
        }

        IEnumerator WaitFacing(Site s)
        {
            float until = Time.time + m_Play.face_wait_max_s;
            yield return null;
            while (Time.time < until && (s.Worker.Turning || !s.Worker.Noticed)) yield return null;
            yield return new WaitForSeconds(0.3f);
        }

        IEnumerator CaptureIdle(Site s, int take)
        {
            bool seq = IsSequence(take);
            int frames = seq ? m_Look.recording.sequence_frames : 1;
            var recs = NewRecords(s, LookCheckConfig.None, "", "", TakeName(s, take, ""), take, frames);
            float t0 = Time.time;
            for (int i = 0; i < frames; i++)
            {
                while (Time.time < t0 + i * 0.1f) yield return null;
                yield return new WaitForEndOfFrame();
                for (int c = 0; c < recs.Count; c++) Capture(s, s.Cams[c], recs[c], seq, i, "");
            }
            m_Records.AddRange(recs);
        }

        IEnumerator Perform(Site s, string cmd, string arm, IList<string> clips, int take)
        {
            var w = s.Worker;
            var t = m_Play.takes;
            bool seq = IsSequence(take);
            int seqs = m_Quick ? m_Play.venue.junctions.Length : t.sequences_per_group;
            int k = seq ? take : take - seqs;
            string clip = clips[k % clips.Count];
            float sideAz = seq ? t.sequence_point_side_azimuth_deg[take % t.sequence_point_side_azimuth_deg.Length]
                               : t.single_point_side_azimuth_deg[k % t.single_point_side_azimuth_deg.Length];
            if (!PlaceCameras(s)) yield break;
            yield return WaitFacing(s);
            w.SetRun(m_Play.seed, ++s.VariationRun);                          // an independent variation stream per take
            w.BodyFrame(out _, out var fwd);
            float bodyAz = (arm == "right" ? 1f : -1f) * (90f - sideAz);
            var req = new GestureRequest { Command = cmd, Clip = clip, Arm = arm, PointDirection = Quaternion.AngleAxis(bodyAz, Vector3.up) * fwd };
            w.IsCommander = true;
            string name = TakeName(s, take, clip);
            if (!w.Request(req, out string error)) { s.Error = $"{cmd} {arm} {name}: {error}"; w.IsCommander = false; yield break; }
            yield return new WaitForSeconds(m_Play.question_after_request_s);
            w.SetQuestionVisible(true);                                       // "Which direction?" appears
            float until = Time.time + m_Play.phase_wait_max_s;
            while (w.Phase != WorkerPhase.Holding && Time.time < until) yield return null;
            if (w.Phase != WorkerPhase.Holding) { s.Error = $"{cmd} {arm} {name}: the worker never reached its hold"; yield break; }
            float holdStart = Time.time;
            int ikBefore = w.HandIkCalls;
            int frames = seq ? m_Look.recording.sequence_frames : 1;
            var recs = NewRecords(s, cmd, arm, clip, name, take, frames);
            var p = w.Current;
            foreach (var rec in recs)
            {
                rec.point_side_azimuth_deg = cmd == WorkerV4Config.Point ? sideAz : -1f;
                rec.speed = p.speed; rec.size = p.size; rec.start_delay_s = p.start_delay_s; rec.hold_s = p.hold_s;
                rec.variation_run = s.VariationRun;
            }
            if (!seq)
            {
                float lo = m_Play.settle_after_hold_s, hi = Mathf.Max(lo, p.hold_s - 0.3f);
                float at = holdStart + lo + (float)s.PoseRng.NextDouble() * (hi - lo);
                while (Time.time < at) yield return null;
                yield return new WaitForEndOfFrame();
                for (int c = 0; c < recs.Count; c++) Capture(s, s.Cams[c], recs[c], false, 0, arm);
            }
            else
            {
                float t0 = holdStart + m_Play.settle_after_hold_s;
                for (int i = 0; i < frames; i++)
                {
                    while (Time.time < t0 + i * 0.1f) yield return null;
                    yield return new WaitForEndOfFrame();
                    for (int c = 0; c < recs.Count; c++) Capture(s, s.Cams[c], recs[c], true, i, arm);
                }
            }
            foreach (var rec in recs)
            {
                rec.hand_ik_calls = w.HandIkCalls - ikBefore;
                if (rec.hand_ik_calls == 0) { s.Error = $"{rec.name}: Humanoid IK never set the hand (OnAnimatorIK not called)"; yield break; }
            }
            m_Records.AddRange(recs);
            while (w.Phase != WorkerPhase.Idle && Time.time < until + 30f) yield return null;
            w.SetQuestionVisible(false);
            w.IsCommander = false;
            yield return new WaitForSeconds(m_Play.pause_between_s);
        }

        /// <summary>One record per camera (nominal distance) for this take.</summary>
        List<RecordingRecord> NewRecords(Site s, string cmd, string arm, string clip, string take, int takeIndex, int frames)
        {
            var list = new List<RecordingRecord>();
            foreach (var c in s.Cams)
            {
                var cam = c.Cam.transform;
                list.Add(new RecordingRecord
                {
                    name = LookCheckConfig.RecordingName(s.Look, cmd, c.Nominal, arm, take), kind = frames > 1 ? "sequence" : "frame",
                    look = s.Look, command = cmd, arm = arm, clip = clip, junction = s.Junction, worker_id = s.Worker.workerId, take = takeIndex + 1,
                    pose_draws = s.PoseDraws, n_frames = frames, distance_m = c.Nominal, camera_distance_m = (float)Math.Round(c.Distance, 3),
                    approach_bearing_deg = (float)Math.Round(s.Bearing, 2), camera_x = cam.position.x, camera_z = cam.position.z,
                    camera_yaw_deg = cam.eulerAngles.y, vertical_fov_deg = m_Look.recording.vertical_fov_deg,
                    point_side_azimuth_deg = -1f, point_angle_deg = -1f, time_first_s = -1f, time_last_s = -1f,
                });
            }
            return list;
        }

        // ---------------------------------------------------------------- capture

        /// <summary>Render one camera now (end of frame: after the Animator, IK and the hand shapes) and queue the PNG and header.</summary>
        void Capture(Site s, SiteCamera c, RecordingRecord rec, bool sequence, int frameIndex, string arm)
        {
            var w = s.Worker;
            float t = Time.time;
            bool held = rec.command == LookCheckConfig.None ? w.Phase == WorkerPhase.Idle : w.Phase == WorkerPhase.Holding;
            if (!held) { rec.frames_outside_hold++; m_Outside++; }
            if (rec.time_first_s < 0f) rec.time_first_s = t;
            rec.time_last_s = t;
            var truth = w.Truth(t);
            if (m_Quick) Debug.Log($"[LookCheckPlay] {rec.name} frame {frameIndex}: {w.DebugState()}");
            if (rec.command == WorkerV4Config.Point) rec.point_angle_deg = (float)truth.PointAngleDeg;
            if (rec.command != LookCheckConfig.None) rec.hand_to_target_max_m = Mathf.Max(rec.hand_to_target_max_m, w.HandToTargetM);
            if (rec.command != LookCheckConfig.None && w.GestureArmPositions(out var shoulder, out var hand))
            {
                if (frameIndex == 0) { rec.FirstHand = hand; rec.FirstShoulder = shoulder; rec.hand_motion_max_m = 0f; rec.shoulder_motion_max_m = 0f; }
                rec.hand_motion_max_m = Mathf.Max(rec.hand_motion_max_m, Vector3.Distance(hand, rec.FirstHand));
                rec.shoulder_motion_max_m = Mathf.Max(rec.shoulder_motion_max_m, Vector3.Distance(shoulder, rec.FirstShoulder));
            }

            var prevActive = RenderTexture.active;
            c.Cam.targetTexture = c.Rt;
            c.Cam.Render();
            RenderTexture.active = c.Rt;
            c.Tex.ReadPixels(new Rect(0, 0, c.Rt.width, c.Rt.height), 0, 0, false);
            c.Tex.Apply(false);
            c.Cam.targetTexture = null;
            RenderTexture.active = prevActive;
            byte[] raw = c.Tex.GetRawTextureData();
            var fmt = c.Tex.graphicsFormat;
            int width = c.Rt.width, height = c.Rt.height;
            string seqDir = sequence ? Path.Combine(RecordingFolder, rec.name) : null;
            if (seqDir != null && frameIndex == 0) Directory.CreateDirectory(seqDir);
            string stem = seqDir != null ? Path.Combine(seqDir, LookCheckConfig.FrameStem(frameIndex)) : Path.Combine(RecordingFolder, rec.name);
            string header = Header(s, c, frameIndex, t, arm, rec, truth);
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
        string Header(Site s, SiteCamera c, int frameIndex, float t, string arm, RecordingRecord rec, TruthRow truth)
        {
            int w = m_Pt.width_px, h = m_Pt.height_px;
            double fov = m_Look.recording.vertical_fov_deg;
            LookCheckConfig.Intrinsics(w, h, fov, out double fx, out double fy, out double cx, out double cy);
            string N(double x) => x.ToString("R", Inv);
            string F(float x) => x.ToString("R", Inv);
            var p = c.Cam.transform.position;
            var sb = new StringBuilder();
            sb.Append("{\n  \"version\": 3,\n  \"type\": \"frame_pan_tilt\",\n");
            sb.Append($"  \"time_s\": {N(t)},\n");
            sb.Append($"  \"frame_index\": {frameIndex.ToString(Inv)},\n");
            sb.Append($"  \"width\": {w.ToString(Inv)},\n  \"height\": {h.ToString(Inv)},\n");
            sb.Append($"  \"fx\": {N(fx)},\n  \"fy\": {N(fy)},\n  \"cx\": {N(cx)},\n  \"cy\": {N(cy)},\n");
            sb.Append($"  \"vertical_fov_deg\": {N(fov)},\n  \"pan_deg\": 0.0,\n  \"tilt_deg\": 0.0,\n");
            sb.Append($"  \"camera_height_m\": {F(m_Pt.height_m)},\n");
            sb.Append($"  \"pose\": {{\"x\": {N(p.x)}, \"z\": {N(p.z)}, \"yaw_deg\": {N(c.Cam.transform.eulerAngles.y)}}},\n");
            sb.Append("  \"encoding\": \"png\",\n");
            if (!string.IsNullOrEmpty(arm)) sb.Append($"  \"arm\": \"{arm}\",\n");
            sb.Append($"  \"look_check_play\": {{\"worker_id\": {s.Worker.workerId.ToString(Inv)}, \"variant\": \"{rec.clip}\", \"phase\": \"{truth.Phase}\", " +
                      $"\"speed\": {N(Math.Round(rec.speed, 4))}, \"size\": {N(Math.Round(rec.size, 4))}, \"junction\": \"{s.Junction}\", " +
                      $"\"camera_distance_m\": {N(rec.camera_distance_m)}, \"approach_bearing_deg\": {N(rec.approach_bearing_deg)}}}\n");
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
