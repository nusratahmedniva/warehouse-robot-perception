using System;
using System.Collections;
using System.Collections.Generic;
using System.Globalization;
using System.IO;
using System.Linq;
using System.Text;
using UnityEngine;
using UnityEngine.Rendering;
using WarehouseAvatar;

namespace WarehouseRobot.AvatarCheck
{
    /// <summary>
    /// Geometric check of the worker template's gestures (Avatar/Config/experiments_ab.md section 10, gesture_geometry.json). Play mode, a
    /// neutral stage built here (grey floor, one directional light): one worker per look, each with a stand-in robot in front, performs every
    /// clip of POINT, PROCEED, WAIT and STOP with both arms. After the worker's LateUpdate (this driver runs late) the rendered shoulder, elbow
    /// and wrist bones are compared with the worker's own goal of that frame (GestureGeometry.Evaluate, the declared tolerance), and the
    /// screenshot looks are rendered from a neutral camera (not the robot cameras' settings). No perception model is run. Writes
    /// robot_vision/outputs/gesture_geometry_[label_]&lt;time&gt;/ (never overwrites): geometry.json, table.md, screens/, config_used/,
    /// run_info.json. Started by GestureGeometryMenu.
    /// </summary>
    [DefaultExecutionOrder(30000)]
    public class GestureGeometryDriver : MonoBehaviour
    {
        public TextAsset geometryConfig;
        public TextAsset extraLooksConfig;
        public WorkerV4 workerPrefab;
        public LookSource[] extraSources = new LookSource[0];
        public string repoRootRelativeToProject = "../../..";

        public const string LooksArg = "-geometryLooks", LabelArg = "-geometryLabel";
        public static readonly string[] Commands = { WorkerV4Config.Point, WorkerV4Config.Proceed, WorkerV4Config.Wait, WorkerV4Config.Stop };

        public string Status { get; private set; } = "idle";
        public string OutputFolder { get; private set; } = "";

        static readonly CultureInfo Inv = CultureInfo.InvariantCulture;
        static readonly UTF8Encoding Utf8 = new UTF8Encoding(false);

        // ---------------------------------------------------------------- report records

        [Serializable]
        public class TakeRecord
        {
            public string command, clip, arm;
            public int take, frames, frames_failed, frames_outside_hold;
            public float point_side_azimuth_deg = -1f, size, swing_hz;
            public float max_elbow_error_deg, max_arm_direction_error_deg, max_forearm_error_deg = -1f;
            public float min_elbow_deg = 999f, max_elbow_deg, min_intended_elbow_deg = 999f, max_intended_elbow_deg;
            public float max_target_shift_m, max_hint_shift_m;
            public bool pass;
            public string first_failure = "";
        }

        [Serializable]
        public class CommandRecord
        {
            public string command;
            public int takes, frames, frames_failed;
            public bool pass;
            public float max_elbow_error_deg, max_arm_direction_error_deg, max_forearm_error_deg = -1f, min_elbow_deg = 999f;
            public float min_intended_elbow_deg = 999f, max_intended_elbow_deg, max_target_shift_m, max_hint_shift_m;
            public string failures = "";
        }

        [Serializable]
        public class LookRecord
        {
            public string id, kind_group, status, problem = "", description = "";
            public float upper_arm_m, forearm_m, arm_m, upper_share, shoulder_width_m, shoulder_height_m, arm_to_shoulder_ratio, height_m;
            public bool pass;
            public List<CommandRecord> commands = new List<CommandRecord>();
            public List<TakeRecord> takes = new List<TakeRecord>();
            public List<string> screens = new List<string>();
        }

        [Serializable] class GeometryFile { public string created_local, label, tolerance; public List<LookRecord> looks = new List<LookRecord>(); }

        [Serializable]
        class RunInfo
        {
            public string created_local, finished_local, label, git_commit, git_branch, unity_version, render_pipeline, graphics_device, status;
            public string geometry_config_sha256, worker_config_sha256, looks_ab_sha256, looks, note;
        }

        sealed class Site
        {
            public int Index;
            public string Look, KindGroup;
            public bool Screens;
            public WorkerV4 Worker;
            public Transform Robot;
            public Camera Cam;
            public RenderTexture Rt;
            public Texture2D Tex;
            public LookRecord Record;
            public bool Done;
            // the take being measured (set by the coroutine, measured in LateUpdate)
            public TakeRecord Take;
            public bool Sampling, Proceed;
            public float SampleFrom, SampleTo;
            public readonly List<float> SampleTimes = new List<float>();
            public int NextSample;
            public float ScreenAt = -1f;
            public string ScreenName;
        }

        GestureGeometryConfig m_Cfg;
        WorkerV4Config m_Worker;
        ExperimentLooksFile m_Looks;
        readonly List<Site> m_Sites = new List<Site>();
        string m_Label = "", m_Stamp;

        void Start() => StartCoroutine(Run());

        string RepoRoot => Path.GetFullPath(Path.Combine(Application.dataPath, "..", repoRootRelativeToProject));

        static string Arg(string name)
        {
            var a = Environment.GetCommandLineArgs();
            int i = Array.IndexOf(a, name);
            return i >= 0 && i + 1 < a.Length && !a[i + 1].StartsWith("-", StringComparison.Ordinal) ? a[i + 1] : null;
        }

        IEnumerator Run()
        {
            yield return null;
            Status = "starting";
            if (geometryConfig == null || workerPrefab == null || extraLooksConfig == null) { Finish("failed: assign geometryConfig, extraLooksConfig and workerPrefab"); yield break; }
            m_Cfg = GestureGeometryConfig.Parse(geometryConfig.text);
            var ce = m_Cfg.Validate();
            if (ce.Count > 0) { Finish("failed: gesture_geometry.json: " + string.Join("; ", ce)); yield break; }
            m_Worker = WorkerV4Config.Parse(workerPrefab.config.text);
            m_Looks = ExperimentLooks.Parse(extraLooksConfig.text);
            var looks = new List<string>(m_Looks.avatar_experiment);
            string want = Arg(LooksArg);
            if (want != null)
            {
                var keep = want.Split(',').Select(x => x.Trim()).Where(x => x.Length > 0).ToList();
                foreach (var k in keep) if (!looks.Contains(k)) { Finish($"failed: {LooksArg}: '{k}' is not in looks_ab.json avatar_experiment"); yield break; }
                looks = looks.Where(keep.Contains).ToList();
            }
            m_Label = Arg(LabelArg) ?? "";
            if (m_Label.Length > 0 && !LookCheckConfig.IsNamePart(m_Label)) { Finish($"failed: {LabelArg} must use a-z, 0-9 and single '_'"); yield break; }

            m_Stamp = DateTime.Now.ToString("yyyyMMdd_HHmmss", Inv);
            OutputFolder = NewFolder(Path.Combine(RepoRoot, m_Cfg.output.root), m_Cfg.output.run_prefix + (m_Label.Length > 0 ? "_" + m_Label : "") + "_" + m_Stamp);
            Directory.CreateDirectory(Path.Combine(OutputFolder, "screens"));
            string used = Path.Combine(OutputFolder, "config_used");
            Directory.CreateDirectory(used);
            WriteNew(Path.Combine(used, "gesture_geometry.json"), geometryConfig.text);
            WriteNew(Path.Combine(used, "worker_v4.json"), workerPrefab.config.text);
            WriteNew(Path.Combine(used, "looks_ab.json"), extraLooksConfig.text);
            var info = new RunInfo { created_local = DateTime.Now.ToString("yyyy-MM-dd'T'HH:mm:ss", Inv), label = m_Label, looks = string.Join(",", looks) };

            QualitySettings.vSyncCount = 0;
            Application.targetFrameRate = 60;
            BuildStage(looks.Count);
            Status = "running";
            for (int i = 0; i < looks.Count; i++) m_Sites.Add(SpawnSite(i, looks[i]));
            foreach (var s in m_Sites) if (s.Worker != null) StartCoroutine(RunSite(s)); else s.Done = true;
            while (!m_Sites.TrueForAll(s => s.Done)) yield return null;

            Status = "writing";
            var file = new GeometryFile
            {
                created_local = info.created_local, label = m_Label,
                tolerance = $"elbow {F(m_Cfg.tolerance.elbow_angle_deg)} deg, arm direction {F(m_Cfg.tolerance.arm_direction_deg)} deg, forearm {F(m_Cfg.tolerance.forearm_direction_deg)} deg, " +
                            $"no fold below {F(m_Cfg.tolerance.no_fold_min_elbow_deg)} deg ({string.Join(", ", m_Cfg.tolerance.no_fold_commands)})",
            };
            foreach (var s in m_Sites) { Summarise(s.Record); file.looks.Add(s.Record); }
            WriteNew(Path.Combine(OutputFolder, "geometry.json"), JsonUtility.ToJson(file, true).Replace("\r\n", "\n") + "\n");
            WriteNew(Path.Combine(OutputFolder, "table.md"), Table(file));
            Git(out info.git_commit, out info.git_branch);
            info.finished_local = DateTime.Now.ToString("yyyy-MM-dd'T'HH:mm:ss", Inv);
            info.unity_version = Application.unityVersion;
            info.render_pipeline = GraphicsSettings.currentRenderPipeline != null ? GraphicsSettings.currentRenderPipeline.name : "built-in";
            info.graphics_device = SystemInfo.graphicsDeviceType + " " + SystemInfo.graphicsDeviceName;
            info.geometry_config_sha256 = Sha256(geometryConfig.text);
            info.worker_config_sha256 = Sha256(workerPrefab.config.text);
            info.looks_ab_sha256 = Sha256(extraLooksConfig.text);
            int failed = file.looks.Count(l => l.status == "ok" && !l.pass), absent = file.looks.Count(l => l.status != "ok");
            info.status = "done";
            info.note = "Geometric check of the worker template's gestures (experiments_ab.md section 10): rendered bones against the worker's own goal; no perception model run. An engineering check.";
            WriteNew(Path.Combine(OutputFolder, "run_info.json"), JsonUtility.ToJson(info, true).Replace("\r\n", "\n") + "\n");
            Finish($"done: {file.looks.Count} looks ({file.looks.Count(l => l.status == "ok" && l.pass)} pass, {failed} fail, {absent} not spawned) in {Path.GetFileName(OutputFolder)}");
        }

        void Finish(string status)
        {
            Status = status;
            if (status.StartsWith("done", StringComparison.Ordinal)) Debug.Log("[GestureGeometry] " + status);
            else Debug.LogError("[GestureGeometry] " + status);
        }

        // ---------------------------------------------------------------- stage and sites

        void BuildStage(int count)
        {
            var st = m_Cfg.stage;
            var floor = GameObject.CreatePrimitive(PrimitiveType.Plane);     // 10 m x 10 m at scale 1
            floor.name = "GeometryFloor";
            float length = Mathf.Max(1, count) * st.spacing_m + 20f;
            floor.transform.localScale = new Vector3(length / 10f, 1f, 3f);
            floor.transform.position = new Vector3(0.5f * (count - 1) * st.spacing_m, 0f, 0f);
            var lit = Shader.Find("Universal Render Pipeline/Lit");
            if (lit != null)
            {
                var m = new Material(lit);
                var g = new Color(st.floor_grey, st.floor_grey, st.floor_grey, 1f);
                m.SetColor("_BaseColor", g);
                m.color = g;
                floor.GetComponent<Renderer>().sharedMaterial = m;
            }
            var lightGo = new GameObject("GeometryKeyLight");
            var light = lightGo.AddComponent<Light>();
            light.type = LightType.Directional;
            light.shadows = LightShadows.Soft;
            light.intensity = st.light_intensity;
            lightGo.transform.rotation = Quaternion.Euler(st.light_euler_deg[0], st.light_euler_deg[1], st.light_euler_deg[2]);
            RenderSettings.ambientMode = AmbientMode.Flat;
            RenderSettings.ambientLight = new Color(st.ambient_grey, st.ambient_grey, st.ambient_grey, 1f);
            RenderSettings.skybox = null;
            RenderSettings.fog = false;
        }

        Site SpawnSite(int index, string look)
        {
            var entry = m_Looks.looks.FirstOrDefault(l => l != null && l.id == look);
            var s = new Site
            {
                Index = index, Look = look, KindGroup = entry != null ? entry.kind_group : ExperimentLook.Stylised,
                Record = new LookRecord { id = look, kind_group = entry != null ? entry.kind_group : ExperimentLook.Stylised, status = "ok" },
            };
            s.Screens = m_Cfg.screens.kind_groups != null && Array.IndexOf(m_Cfg.screens.kind_groups, s.KindGroup) >= 0;
            var stand = new Vector3(index * m_Cfg.stage.spacing_m, 0f, 0f);
            s.Robot = new GameObject($"Robot_{look}").transform;
            s.Robot.position = stand + Vector3.forward * m_Cfg.stage.robot_distance_m + Vector3.up * 1.2f;
            var w = Instantiate(workerPrefab);
            w.name = "WorkerV4_" + look;
            w.lookId = look;
            w.workerId = index + 1;
            w.robot = s.Robot;
            w.robotEye = s.Robot;
            w.extraLooks = new List<LookEntry>(m_Looks.looks);
            var sources = new List<LookSource>(w.lookSources);
            sources.AddRange(extraSources);
            w.lookSources = sources.ToArray();
            w.transform.SetPositionAndRotation(stand, Quaternion.LookRotation(Vector3.forward, Vector3.up));
            if (!w.Initialize())
            {
                s.Record.status = "not_spawned";
                s.Record.problem = w.Problem;
                Destroy(w.gameObject);
                return s;
            }
            s.Worker = w;
            s.Record.description = w.LookDescription;
            if (s.Screens)
            {
                var sc = m_Cfg.screens;
                var camGo = new GameObject($"ScreenCamera_{look}");
                s.Cam = camGo.AddComponent<Camera>();
                s.Cam.enabled = false;
                s.Cam.fieldOfView = sc.vertical_fov_deg;
                s.Cam.nearClipPlane = 0.05f;
                s.Cam.farClipPlane = 50f;
                s.Cam.clearFlags = CameraClearFlags.SolidColor;
                float b = m_Cfg.stage.backdrop_grey;
                s.Cam.backgroundColor = new Color(b, b, b, 1f);
                s.Rt = new RenderTexture(sc.width_px, sc.height_px, 24, RenderTextureFormat.ARGB32) { name = "Screen_" + look, antiAliasing = 4 };
                s.Rt.Create();
                s.Tex = new Texture2D(sc.width_px, sc.height_px, TextureFormat.RGB24, false);
            }
            return s;
        }

        IEnumerator RunSite(Site s)
        {
            var w = s.Worker;
            yield return new WaitForSeconds(0.5f);
            if (LookInventory.MeshExtentY(w.LookInstance, out float bottom, out float top))
            {
                w.transform.position -= new Vector3(0f, bottom, 0f);       // stand on the floor (as the look checks)
                s.Record.height_m = (float)Math.Round(top - bottom, 3);
            }
            var p = w.Proportions;
            s.Record.upper_arm_m = R4(p.upper_m);
            s.Record.forearm_m = R4(p.forearm_m);
            s.Record.arm_m = R4(p.Arm);
            s.Record.upper_share = p.Arm > 0f ? R4(p.upper_m / p.Arm) : -1f;
            s.Record.shoulder_width_m = R4(p.shoulder_width_m);
            s.Record.shoulder_height_m = R4(p.shoulder_height_m);
            s.Record.arm_to_shoulder_ratio = p.shoulder_width_m > 0f ? R4(p.Arm / p.shoulder_width_m) : -1f;
            if (s.Cam != null) PlaceScreenCamera(s);
            int take = 0;
            foreach (var cmd in Commands)
            {
                var clips = m_Worker.ClipNames(cmd);
                var azimuths = cmd == WorkerV4Config.Point ? m_Cfg.stage.point_side_azimuth_deg : new[] { -1f };
                foreach (var arm in new[] { "left", "right" })
                {
                    bool first = true;
                    foreach (var clip in clips)
                        foreach (var az in azimuths)
                        {
                            yield return Perform(s, cmd, clip, arm, az, ++take, first && s.Cam != null);
                            first = false;
                        }
                }
            }
            s.Done = true;
        }

        void PlaceScreenCamera(Site s)
        {
            var sc = m_Cfg.screens;
            var w = s.Worker.transform;
            var dir = Quaternion.AngleAxis(sc.azimuth_right_deg, Vector3.up) * w.forward;   // toward the worker's right (seen from the front: camera on its right side)
            var pos = w.position + dir * sc.distance_m + Vector3.up * sc.height_m;
            var aim = w.position + Vector3.up * (sc.aim_height_of_body * Mathf.Max(0.5f, s.Record.height_m));
            s.Cam.transform.SetPositionAndRotation(pos, Quaternion.LookRotation(aim - pos, Vector3.up));
        }

        IEnumerator Perform(Site s, string cmd, string clip, string arm, float sideAz, int take, bool screen)
        {
            var w = s.Worker;
            var st = m_Cfg.stage;
            w.SetRun(st.seed, take);
            w.BodyFrame(out _, out var fwd);
            float bodyAz = (arm == "right" ? 1f : -1f) * (90f - Mathf.Max(0f, sideAz));
            var req = new GestureRequest { Command = cmd, Clip = clip, Arm = arm, PointDirection = Quaternion.AngleAxis(bodyAz, Vector3.up) * fwd };
            var rec = new TakeRecord { command = cmd, clip = clip, arm = arm, take = take, point_side_azimuth_deg = cmd == WorkerV4Config.Point ? sideAz : -1f, pass = true };
            s.Record.takes.Add(rec);
            w.IsCommander = true;
            if (!w.Request(req, out string error)) { rec.pass = false; rec.first_failure = "request refused: " + error; w.IsCommander = false; yield break; }
            yield return new WaitForSeconds(st.question_after_request_s);
            w.SetQuestionVisible(true);
            float until = Time.time + st.phase_wait_max_s;
            while (w.Phase != WorkerPhase.Holding && Time.time < until) yield return null;
            if (w.Phase != WorkerPhase.Holding) { rec.pass = false; rec.first_failure = "never reached the hold"; w.SetQuestionVisible(false); w.IsCommander = false; yield break; }
            float hold0 = Time.time;
            rec.size = w.Current.size;
            rec.swing_hz = w.Current.swing_hz;
            s.Take = rec;
            s.Proceed = cmd == WorkerV4Config.Proceed;
            s.SampleTimes.Clear();
            s.NextSample = 0;
            if (s.Proceed)
            {
                s.SampleFrom = hold0 + st.settle_after_hold_s;
                s.SampleTo = s.SampleFrom + st.proceed_window_s;
            }
            else
            {
                float a = hold0 + st.settle_after_hold_s, b = hold0 + Mathf.Max(st.settle_after_hold_s, w.Current.hold_s - 0.3f);
                for (int i = 0; i < st.hold_frames; i++) s.SampleTimes.Add(Mathf.Lerp(a, b, i / (float)(st.hold_frames - 1)));
                s.SampleFrom = a;
                s.SampleTo = b;
            }
            if (screen)
            {
                s.ScreenAt = s.Proceed && w.Current.swing_hz > 0f ? hold0 + 0.5f / w.Current.swing_hz : hold0 + 0.5f * w.Current.hold_s;
                s.ScreenName = $"{s.Look}__{cmd}__{arm}.png";
            }
            s.Sampling = true;
            while (s.Sampling || s.ScreenAt >= 0f) yield return null;
            s.Take = null;
            while (w.Phase != WorkerPhase.Idle && Time.time < until + 30f) yield return null;
            w.SetQuestionVisible(false);
            w.IsCommander = false;
            yield return new WaitForSeconds(st.pause_between_s);
        }

        /// <summary>After every worker's LateUpdate: measure the takes due now and render the screenshots due now.</summary>
        void LateUpdate()
        {
            float t = Time.time;
            foreach (var s in m_Sites)
            {
                if (s.Worker == null) continue;
                if (s.Sampling && s.Take != null)
                {
                    bool due = s.Proceed ? t >= s.SampleFrom && t <= s.SampleTo : s.NextSample < s.SampleTimes.Count && t >= s.SampleTimes[s.NextSample];
                    if (due)
                    {
                        Measure(s);
                        if (!s.Proceed) s.NextSample++;
                    }
                    if (s.Proceed ? t > s.SampleTo : s.NextSample >= s.SampleTimes.Count) s.Sampling = false;
                }
                if (s.ScreenAt >= 0f && t >= s.ScreenAt)
                {
                    Screenshot(s);
                    s.ScreenAt = -1f;
                }
            }
        }

        void Measure(Site s)
        {
            var w = s.Worker;
            var rec = s.Take;
            if (w.Phase != WorkerPhase.Holding) { rec.frames_outside_hold++; return; }
            bool right = rec.arm == "right";
            var a = w.Animator;
            Transform up = a.GetBoneTransform(right ? HumanBodyBones.RightUpperArm : HumanBodyBones.LeftUpperArm);
            Transform lo = a.GetBoneTransform(right ? HumanBodyBones.RightLowerArm : HumanBodyBones.LeftLowerArm);
            Transform hand = a.GetBoneTransform(right ? HumanBodyBones.RightHand : HumanBodyBones.LeftHand);
            var g = w.Goal;
            var x = new GeometrySample { Command = rec.command, S = up.position, E = lo.position, W = hand.position, Goal = g, Upper = w.Proportions.upper_m, Fore = w.Proportions.forearm_m };
            var r = GestureGeometry.Evaluate(x, m_Cfg.tolerance);
            rec.frames++;
            rec.max_elbow_error_deg = Mathf.Max(rec.max_elbow_error_deg, R2(r.ElbowErrorDeg));
            rec.max_arm_direction_error_deg = Mathf.Max(rec.max_arm_direction_error_deg, R2(r.ArmDirectionErrorDeg));
            if (r.ForearmErrorDeg >= 0f) rec.max_forearm_error_deg = Mathf.Max(rec.max_forearm_error_deg, R2(r.ForearmErrorDeg));
            rec.min_elbow_deg = Mathf.Min(rec.min_elbow_deg, R2(r.ElbowDeg));
            rec.max_elbow_deg = Mathf.Max(rec.max_elbow_deg, R2(r.ElbowDeg));
            rec.min_intended_elbow_deg = Mathf.Min(rec.min_intended_elbow_deg, R2(r.IntendedElbowDeg));
            rec.max_intended_elbow_deg = Mathf.Max(rec.max_intended_elbow_deg, R2(r.IntendedElbowDeg));
            var legacy = w.LegacyGoal;
            rec.max_target_shift_m = Mathf.Max(rec.max_target_shift_m, R4(Vector3.Distance(g.Target, legacy.Target)));
            rec.max_hint_shift_m = Mathf.Max(rec.max_hint_shift_m, R4(Vector3.Distance(g.Hint, legacy.Hint)));
            if (!r.Pass)
            {
                rec.frames_failed++;
                rec.pass = false;
                if (rec.first_failure.Length == 0)
                    rec.first_failure = $"{r.Why}: elbow {F(r.ElbowDeg)} vs {F(r.IntendedElbowDeg)} deg, arm direction {F(r.ArmDirectionErrorDeg)} deg" +
                                        (r.ForearmErrorDeg >= 0f ? $", forearm {F(r.ForearmErrorDeg)} deg" : "");
            }
        }

        void Screenshot(Site s)
        {
            var prev = RenderTexture.active;
            s.Cam.targetTexture = s.Rt;
            s.Cam.Render();
            RenderTexture.active = s.Rt;
            s.Tex.ReadPixels(new Rect(0, 0, s.Rt.width, s.Rt.height), 0, 0, false);
            s.Tex.Apply(false);
            s.Cam.targetTexture = null;
            RenderTexture.active = prev;
            WriteNew(Path.Combine(OutputFolder, "screens", s.ScreenName), s.Tex.EncodeToPNG());
            s.Record.screens.Add("screens/" + s.ScreenName);
        }

        // ---------------------------------------------------------------- summary

        static void Summarise(LookRecord l)
        {
            l.pass = l.status == "ok";
            foreach (var cmd in Commands)
            {
                var takes = l.takes.Where(x => x.command == cmd).ToList();
                if (takes.Count == 0) continue;
                var c = new CommandRecord { command = cmd, takes = takes.Count, pass = true };
                foreach (var t in takes)
                {
                    c.frames += t.frames;
                    c.frames_failed += t.frames_failed;
                    if (!t.pass || t.frames == 0) c.pass = false;
                    if (!t.pass) c.failures += (c.failures.Length > 0 ? "; " : "") + $"{t.arm} {t.clip}" + (t.point_side_azimuth_deg >= 0f ? $" az {F(t.point_side_azimuth_deg)}" : "") + $": {t.first_failure}";
                    else if (t.frames == 0) c.failures += (c.failures.Length > 0 ? "; " : "") + $"{t.arm} {t.clip}: no frame measured";
                    c.max_elbow_error_deg = Mathf.Max(c.max_elbow_error_deg, t.max_elbow_error_deg);
                    c.max_arm_direction_error_deg = Mathf.Max(c.max_arm_direction_error_deg, t.max_arm_direction_error_deg);
                    c.max_forearm_error_deg = Mathf.Max(c.max_forearm_error_deg, t.max_forearm_error_deg);
                    c.min_elbow_deg = Mathf.Min(c.min_elbow_deg, t.min_elbow_deg);
                    c.min_intended_elbow_deg = Mathf.Min(c.min_intended_elbow_deg, t.min_intended_elbow_deg);
                    c.max_intended_elbow_deg = Mathf.Max(c.max_intended_elbow_deg, t.max_intended_elbow_deg);
                    c.max_target_shift_m = Mathf.Max(c.max_target_shift_m, t.max_target_shift_m);
                    c.max_hint_shift_m = Mathf.Max(c.max_hint_shift_m, t.max_hint_shift_m);
                }
                l.commands.Add(c);
                if (!c.pass) l.pass = false;
            }
        }

        static string Table(GeometryFile f)
        {
            var sb = new StringBuilder();
            sb.Append($"# Gesture geometry ({(f.label.Length > 0 ? f.label + ", " : "")}{f.created_local})\n\n");
            sb.Append($"Tolerance: {f.tolerance}. Worst values over every measured frame of every take (both arms, every clip).\n\n");
            sb.Append("| look | kind | upper / fore (m) | upper share | shoulders (m) | arm / shoulders | command | takes | frames | elbow rendered min (deg) | elbow intended (deg) | elbow err max | arm dir err max | forearm err max | target shift vs old (m) | pass |\n");
            sb.Append("|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|\n");
            foreach (var l in f.looks)
            {
                if (l.status != "ok") { sb.Append($"| {l.id} | {l.kind_group} | | | | | {l.status}: {l.problem} | | | | | | | | | no |\n"); continue; }
                foreach (var c in l.commands)
                    sb.Append($"| {l.id} | {l.kind_group} | {F3(l.upper_arm_m)} / {F3(l.forearm_m)} | {F3(l.upper_share)} | {F3(l.shoulder_width_m)} | {F3(l.arm_to_shoulder_ratio)} | {c.command} | {c.takes} | {c.frames} | " +
                              $"{F(c.min_elbow_deg)} | {F(c.min_intended_elbow_deg)} to {F(c.max_intended_elbow_deg)} | {F(c.max_elbow_error_deg)} | {F(c.max_arm_direction_error_deg)} | " +
                              $"{(c.max_forearm_error_deg >= 0f ? F(c.max_forearm_error_deg) : "-")} | {F3(c.max_target_shift_m)} | {(c.pass ? "yes" : "**no**")} |\n");
            }
            var fails = f.looks.Where(l => l.status == "ok").SelectMany(l => l.commands.Where(c => !c.pass).Select(c => $"- {l.id} {c.command}: {c.failures}")).ToList();
            if (fails.Count > 0) sb.Append("\nFailures (first failing frame of each failing take):\n\n").Append(string.Join("\n", fails)).Append('\n');
            return sb.ToString();
        }

        static float R2(float x) => (float)Math.Round(x, 2);
        static float R4(float x) => (float)Math.Round(x, 4);
        static string F(float x) => x.ToString("0.0", Inv);
        static string F3(float x) => x.ToString("0.000", Inv);

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
                if (!head.StartsWith("ref:", StringComparison.Ordinal)) { commit = head; branch = "(detached)"; return; }
                string reference = head.Substring(4).Trim();
                branch = reference.StartsWith("refs/heads/", StringComparison.Ordinal) ? reference.Substring(11) : reference;
                string refFile = Path.Combine(gitDir, reference.Replace('/', Path.DirectorySeparatorChar));
                if (File.Exists(refFile)) { commit = File.ReadAllText(refFile).Trim(); return; }
                string packed = Path.Combine(gitDir, "packed-refs");
                if (File.Exists(packed))
                    foreach (var l in File.ReadAllLines(packed))
                        if (l.EndsWith(" " + reference, StringComparison.Ordinal)) { commit = l.Substring(0, l.IndexOf(' ')); return; }
            }
            catch (Exception e)
            {
                Debug.LogWarning("[GestureGeometry] could not read the git commit: " + e.Message);
            }
        }
    }
}
