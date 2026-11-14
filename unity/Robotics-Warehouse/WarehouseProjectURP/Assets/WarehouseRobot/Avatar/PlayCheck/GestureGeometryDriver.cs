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
            public int take, frames, frames_failed, frames_render_failed, frames_fold, frames_outside_hold;
            public float point_side_azimuth_deg = -1f, size, swing_hz;
            public float max_elbow_error_deg, max_arm_direction_error_deg, max_forearm_error_deg = -1f;
            public float min_elbow_deg = 999f, max_elbow_deg, min_intended_elbow_deg = 999f, max_intended_elbow_deg;
            public float max_target_shift_m, max_hint_shift_m;
            public bool pass, render_pass = true;
            public string first_failure = "";
            // section 12: palm orientation and the WAIT thumb (STOP and WAIT takes); -1 = not measured
            public bool hand_checked, hand_pass = true;
            public int hand_frames, hand_frames_failed, hand_frames_mesh_na, min_palm_vertices = -1;
            public float max_palm_bone_deg = -1f, max_palm_mesh_deg = -1f, max_palm_mesh_flatness = -1f, max_thumb_palm_lengths = -1f;
            public float min_thumb_side = 999f, min_thumb_across = 999f, max_thumb_across = -999f;
            public string hand_first_failure = "";
            /// <summary>Section 12 addendum 1 (diagnostic, first measured frame): the mesh palm normal of each sub-mesh's palm vertices.</summary>
            public string palm_mesh_groups = "";
            // section 12 addendum 5: skinning (forearm volume, torso rigidity); -1 / 999 = not measured
            public bool skin_pass = true;
            public int skin_frames, skin_frames_failed, skin_forearm_na, forearm_vertices, forearm_bands, torso_vertices;
            public float min_forearm_ratio = 999f, max_torso_percentile_m = -1f, max_torso_max_m = -1f;
            public string skin_first_failure = "";
            /// <summary>Addendum 7: max_torso_percentile_m and max_torso_max_m are the torso core's; the whole torso's p95 is information.</summary>
            public int torso_core_vertices;
            public float max_torso_all_percentile_m = -1f;
        }

        [Serializable]
        public class CommandRecord
        {
            public string command;
            public int takes, frames, frames_failed, frames_render_failed, frames_fold;
            /// <summary>pass = render_pass and no fold frame (experiments_ab.md section 10 addendum 2: rendering and design reported apart).</summary>
            public bool pass, render_pass;
            public float max_elbow_error_deg, max_arm_direction_error_deg, max_forearm_error_deg = -1f, min_elbow_deg = 999f;
            public float min_intended_elbow_deg = 999f, max_intended_elbow_deg, max_target_shift_m, max_hint_shift_m;
            public string failures = "";
            // section 12
            public bool hand_checked, hand_pass = true;
            public int hand_frames, hand_frames_failed, hand_frames_mesh_na, min_palm_vertices = -1;
            public float max_palm_bone_deg = -1f, max_palm_mesh_deg = -1f, max_palm_mesh_flatness = -1f, max_thumb_palm_lengths = -1f;
            public float min_thumb_side = 999f, min_thumb_across = 999f, max_thumb_across = -999f;
            public string hand_failures = "";
            // section 12 addendum 5
            public bool skin_pass = true;
            public int skin_frames, skin_frames_failed, skin_forearm_na, forearm_vertices, torso_vertices;
            public float min_forearm_ratio = 999f, max_torso_percentile_m = -1f, max_torso_max_m = -1f;
            public string skin_failures = "";
            public int torso_core_vertices;
            public float max_torso_all_percentile_m = -1f;
        }

        [Serializable]
        public class LookRecord
        {
            public string id, kind_group, status, problem = "", description = "";
            public float upper_arm_m, forearm_m, arm_m, upper_share, shoulder_width_m, shoulder_height_m, arm_to_shoulder_ratio, height_m;
            public bool pass;
            /// <summary>Section 12: every STOP and WAIT take passes the hand check (palm toward the robot camera; WAIT thumb tucked).</summary>
            public bool hand_pass;
            public int palm_vertices_left, palm_vertices_right;
            /// <summary>Section 12 addendum 5: every take passes the skinning checks.</summary>
            public bool skin_pass;
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
            // section 12: the hands as the template builds them, and each hand's palm vertices (renderer, vertex indices)
            public LookPoser.Arm ArmL, ArmR;
            public List<KeyValuePair<SkinnedMeshRenderer, int[]>> PalmL, PalmR;
            public readonly Dictionary<SkinnedMeshRenderer, Mesh> Baked = new Dictionary<SkinnedMeshRenderer, Mesh>();
            /// <summary>Each vertex's "renderer/material" (the first sub-mesh using it), for the diagnostic of addendum 1.</summary>
            public readonly Dictionary<SkinnedMeshRenderer, string[]> SubMeshLabels = new Dictionary<SkinnedMeshRenderer, string[]>();
            // section 12 addendum 5: the skinning sets and the take's reference (the idle pose before its request)
            public List<SkinPart> ForearmL, ForearmR, Torso;
            public int[] RefBands;
            public float[] RefRadii;
            public Vector3[] RefTorso;
            public bool[] RefTorsoCore;     // addendum 7: outside both shoulder zones at the reference
            public readonly List<float> SkinTimes = new List<float>();
            public int NextSkin;
        }

        /// <summary>The vertices of one skinned mesh in a skinning set, with each vertex's dominant bone.</summary>
        sealed class SkinPart
        {
            public SkinnedMeshRenderer Smr;
            public int[] Idx;
            public Transform[] Bone;
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
            WriteNew(Path.Combine(OutputFolder, "hand_table.md"), HandTable(file, m_Cfg.tolerance));
            WriteNew(Path.Combine(OutputFolder, "skin_table.md"), SkinTable(file, m_Cfg.skinning));
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
            Finish($"done: {file.looks.Count} looks ({file.looks.Count(l => l.status == "ok" && l.pass)} pass, {failed} fail, {absent} not spawned; " +
                   $"hand check {file.looks.Count(l => l.hand_pass)} pass: {string.Join(", ", file.looks.Where(l => l.status == "ok" && !l.hand_pass).Select(l => l.id).DefaultIfEmpty("no failure"))}; " +
                   $"skinning {file.looks.Count(l => l.skin_pass)} pass: {string.Join(", ", file.looks.Where(l => l.status == "ok" && !l.skin_pass).Select(l => l.id).DefaultIfEmpty("no failure"))}) in {Path.GetFileName(OutputFolder)}");
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
            var bones = new AnimatorBones(w.Animator);
            s.ArmL = HandShaper.BuildArm(bones, false);
            s.ArmR = HandShaper.BuildArm(bones, true);
            s.PalmL = PalmVertices(w.LookInstance, s.ArmL.Hand, m_Cfg.tolerance.palm_hand_weight_min);
            s.PalmR = PalmVertices(w.LookInstance, s.ArmR.Hand, m_Cfg.tolerance.palm_hand_weight_min);
            s.Record.palm_vertices_left = s.PalmL.Sum(kv => kv.Value.Length);
            s.Record.palm_vertices_right = s.PalmR.Sum(kv => kv.Value.Length);
            var sk = m_Cfg.skinning;
            Transform lowerL = w.Animator.GetBoneTransform(HumanBodyBones.LeftLowerArm), lowerR = w.Animator.GetBoneTransform(HumanBodyBones.RightLowerArm);
            var torsoBones = new HashSet<Transform>(sk.torso_bones.Select(b => w.Animator.GetBoneTransform((HumanBodyBones)Enum.Parse(typeof(HumanBodyBones), b))).Where(t => t != null));
            s.ForearmL = DominantSet(w.LookInstance, t => t == lowerL, sk.forearm_weight_min);
            s.ForearmR = DominantSet(w.LookInstance, t => t == lowerR, sk.forearm_weight_min);
            s.Torso = DominantSet(w.LookInstance, torsoBones.Contains, sk.torso_weight_min);
            foreach (var smr in s.PalmL.Concat(s.PalmR).Select(kv => kv.Key).Distinct())
            {
                var mesh = smr.sharedMesh;
                var label = new string[mesh.vertexCount];
                var mats = smr.sharedMaterials;
                for (int sub = mesh.subMeshCount - 1; sub >= 0; sub--)     // the lowest sub-mesh using a vertex wins
                {
                    string name = $"{smr.name}/{(sub < mats.Length && mats[sub] != null ? mats[sub].name.Replace(" (Instance)", "") : "sub" + sub)}";
                    foreach (int i in mesh.GetTriangles(sub)) label[i] = name;
                }
                for (int i = 0; i < label.Length; i++) if (label[i] == null) label[i] = smr.name + "/none";
                s.SubMeshLabels[smr] = label;
            }
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
            SkinReference(s, arm == "right");       // section 12 addendum 5: the idle pose just before the request
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
            s.SkinTimes.Clear();
            s.NextSkin = 0;
            if (s.Proceed)
            {
                s.SampleFrom = hold0 + st.settle_after_hold_s;
                s.SampleTo = s.SampleFrom + st.proceed_window_s;
                int n = m_Cfg.skinning.proceed_frames;
                for (int i = 0; i < n; i++) s.SkinTimes.Add(Mathf.Lerp(s.SampleFrom, s.SampleTo - 0.05f, i / (float)(n - 1)));   // the last inside the window
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
            if (!r.RenderPass) { rec.frames_render_failed++; rec.render_pass = false; }
            if (r.Fold) rec.frames_fold++;
            if (!r.Pass)
            {
                rec.frames_failed++;
                rec.pass = false;
                if (rec.first_failure.Length == 0)
                    rec.first_failure = $"{r.Why}: elbow {F(r.ElbowDeg)} vs {F(r.IntendedElbowDeg)} deg, arm direction {F(r.ArmDirectionErrorDeg)} deg" +
                                        (r.ForearmErrorDeg >= 0f ? $", forearm {F(r.ForearmErrorDeg)} deg" : "");
            }
            var pc = m_Cfg.tolerance.palm_commands;
            if (pc != null && Array.IndexOf(pc, rec.command) >= 0) MeasureHand(s, rec, right);
            // section 12 addendum 5: skinning on the hold frames; PROCEED on proceed_frames frames evenly over its window
            if (!s.Proceed) MeasureSkin(s, rec, right);
            else if (s.NextSkin < s.SkinTimes.Count && Time.time >= s.SkinTimes[s.NextSkin])
            {
                MeasureSkin(s, rec, right);
                while (s.NextSkin < s.SkinTimes.Count && Time.time >= s.SkinTimes[s.NextSkin]) s.NextSkin++;
            }
        }

        /// <summary>Section 12: the gesturing hand's palm normal (bones; skinned mesh) against the robot camera, and the WAIT thumb.</summary>
        void MeasureHand(Site s, TakeRecord rec, bool right)
        {
            var arm = right ? s.ArmR : s.ArmL;
            var set = right ? s.PalmR : s.PalmL;
            var f = HandGeometry.Frame(arm);
            var verts = new List<Vector3>();
            var groups = new Dictionary<string, List<Vector3>>();   // section 12 addendum 1 (diagnostic): the palm region per sub-mesh
            if (f.Valid)
                foreach (var kv in set)
                {
                    var smr = kv.Key;
                    if (smr == null) continue;
                    if (!s.Baked.TryGetValue(smr, out var mesh)) s.Baked[smr] = mesh = new Mesh();
                    smr.BakeMesh(mesh, true);   // renderer space, the renderer's scale applied
                    var v = mesh.vertices;
                    var m = Matrix4x4.TRS(smr.transform.position, smr.transform.rotation, Vector3.one);
                    var label = s.SubMeshLabels.TryGetValue(smr, out var l) ? l : null;
                    foreach (int i in kv.Value)
                    {
                        if (i >= v.Length) continue;
                        var p = m.MultiplyPoint3x4(v[i]);
                        verts.Add(p);
                        if (rec.hand_frames > 0 || label == null) continue;      // the first measured frame of each take
                        string key = label[i];
                        if (!groups.TryGetValue(key, out var g)) groups[key] = g = new List<Vector3>();
                        g.Add(p);
                    }
                }
            var region = HandGeometry.PalmRegion(verts, f);
            if (rec.hand_frames == 0 && groups.Count > 0)
            {
                var parts = new List<string>();
                foreach (var kv in groups.OrderByDescending(x => x.Value.Count))
                {
                    var gr = HandGeometry.PalmRegion(kv.Value, f);
                    bool ok = HandGeometry.MeshNormal(gr, f.Normal, 3, 1f, out var gn, out float gf);
                    parts.Add($"{kv.Key}: {gr.Count} v" + (ok ? $", {F(Vector3.Angle(gn, s.Robot.position - f.P))} deg, flatness {gf.ToString("0.00", Inv)}" : ""));
                }
                rec.palm_mesh_groups = string.Join("; ", parts);
            }
            var th = arm.Fingers[HandShaper.Thumb];
            bool hasTip = th[1] != null && th[2] != null;
            var r = HandGeometry.Evaluate(rec.command, f, region, s.Robot.position, hasTip, hasTip ? HandShaper.Tip(arm, HandShaper.Thumb) : Vector3.zero, m_Cfg.tolerance);
            rec.hand_checked = true;
            rec.hand_frames++;
            if (r.BoneAngleDeg >= 0f) rec.max_palm_bone_deg = Mathf.Max(rec.max_palm_bone_deg, R2(r.BoneAngleDeg));
            rec.min_palm_vertices = rec.min_palm_vertices < 0 ? r.MeshVertices : Math.Min(rec.min_palm_vertices, r.MeshVertices);
            if (r.MeshFlatness >= 0f) rec.max_palm_mesh_flatness = Mathf.Max(rec.max_palm_mesh_flatness, R4(r.MeshFlatness));
            if (r.MeshDetermined) rec.max_palm_mesh_deg = Mathf.Max(rec.max_palm_mesh_deg, R2(r.MeshAngleDeg));
            else rec.hand_frames_mesh_na++;
            if (r.ThumbMeasured)
            {
                rec.max_thumb_palm_lengths = Mathf.Max(rec.max_thumb_palm_lengths, R4(r.ThumbPalmLengths));
                rec.min_thumb_side = Mathf.Min(rec.min_thumb_side, R4(r.ThumbSide));
                if (!float.IsNaN(r.ThumbAcross))
                {
                    rec.min_thumb_across = Mathf.Min(rec.min_thumb_across, R4(r.ThumbAcross));
                    rec.max_thumb_across = Mathf.Max(rec.max_thumb_across, R4(r.ThumbAcross));
                }
            }
            if (!r.Pass)
            {
                rec.hand_frames_failed++;
                rec.hand_pass = false;
                if (rec.hand_first_failure.Length == 0)
                    rec.hand_first_failure = $"{r.Why}: palm bones {F(r.BoneAngleDeg)} deg, mesh {(r.MeshDetermined ? F(r.MeshAngleDeg) + " deg" : "n/a")}" +
                                             (r.ThumbMeasured ? $", thumb {r.ThumbPalmLengths.ToString("0.00", Inv)} Lp, side {r.ThumbSide.ToString("0.00", Inv)} Lp" : "");
            }
        }

        /// <summary>Section 12 addendum 5: the vertices of every skinned mesh of the look whose largest bone weight is on a bone that pick
        /// accepts and at least minWeight, each with that bone.</summary>
        static List<SkinPart> DominantSet(GameObject look, Func<Transform, bool> pick, float minWeight)
        {
            var list = new List<SkinPart>();
            if (look == null) return list;
            foreach (var smr in look.GetComponentsInChildren<SkinnedMeshRenderer>(true))
            {
                var mesh = smr.sharedMesh;
                var bones = smr.bones;
                if (mesh == null || bones == null) continue;
                var ok = bones.Select(b => b != null && pick(b)).ToArray();
                if (!ok.Any(x => x)) continue;
                var bw = mesh.boneWeights;
                var idx = new List<int>();
                var bone = new List<Transform>();
                for (int i = 0; i < bw.Length; i++)
                {
                    var b = bw[i];
                    int best = b.boneIndex0;
                    float wt = b.weight0;
                    if (b.weight1 > wt) { best = b.boneIndex1; wt = b.weight1; }
                    if (b.weight2 > wt) { best = b.boneIndex2; wt = b.weight2; }
                    if (b.weight3 > wt) { best = b.boneIndex3; wt = b.weight3; }
                    if (best < 0 || best >= ok.Length || !ok[best] || wt < minWeight) continue;
                    idx.Add(i);
                    bone.Add(bones[best]);
                }
                if (idx.Count > 0) list.Add(new SkinPart { Smr = smr, Idx = idx.ToArray(), Bone = bone.ToArray() });
            }
            return list;
        }

        /// <summary>The world positions of a skinning set's vertices now (each renderer baked once per call through the site's cache).</summary>
        static List<Vector3> Positions(Site s, List<SkinPart> set, Dictionary<SkinnedMeshRenderer, Vector3[]> frame)
        {
            var pts = new List<Vector3>();
            foreach (var part in set)
            {
                if (part.Smr == null) continue;
                if (!frame.TryGetValue(part.Smr, out var v))
                {
                    if (!s.Baked.TryGetValue(part.Smr, out var mesh)) s.Baked[part.Smr] = mesh = new Mesh();
                    part.Smr.BakeMesh(mesh, true);
                    var m = Matrix4x4.TRS(part.Smr.transform.position, part.Smr.transform.rotation, Vector3.one);
                    v = mesh.vertices;
                    for (int i = 0; i < v.Length; i++) v[i] = m.MultiplyPoint3x4(v[i]);
                    frame[part.Smr] = v;
                }
                foreach (int i in part.Idx) pts.Add(i < v.Length ? v[i] : Vector3.zero);
            }
            return pts;
        }

        static List<Vector3> TorsoLocal(List<Vector3> pts, List<SkinPart> set)
        {
            var r = new List<Vector3>(pts.Count);
            int k = 0;
            foreach (var part in set)
                for (int j = 0; j < part.Idx.Length; j++, k++)
                    r.Add(part.Bone[j] != null ? SkinGeometry.InBone(pts[k], part.Bone[j].position, part.Bone[j].rotation) : pts[k]);
            return r;
        }

        /// <summary>Section 12 addendum 5: the take's reference, the idle pose just before its request.</summary>
        void SkinReference(Site s, bool right)
        {
            var sk = m_Cfg.skinning;
            var frame = new Dictionary<SkinnedMeshRenderer, Vector3[]>();
            var a = s.Worker.Animator;
            Vector3 e = a.GetBoneTransform(right ? HumanBodyBones.RightLowerArm : HumanBodyBones.LeftLowerArm).position;
            Vector3 wr = a.GetBoneTransform(right ? HumanBodyBones.RightHand : HumanBodyBones.LeftHand).position;
            var fore = Positions(s, right ? s.ForearmR : s.ForearmL, frame);
            s.RefBands = SkinGeometry.Bands(fore, e, wr, sk.forearm_bands, sk.forearm_min_band_vertices);
            s.RefRadii = SkinGeometry.BandRadii(fore, s.RefBands, sk.forearm_bands, e, wr);
            var torsoWorld = Positions(s, s.Torso, frame);
            s.RefTorso = TorsoLocal(torsoWorld, s.Torso).ToArray();
            var shoulders = new[] { a.GetBoneTransform(HumanBodyBones.LeftUpperArm).position, a.GetBoneTransform(HumanBodyBones.RightUpperArm).position };
            s.RefTorsoCore = SkinGeometry.CoreMask(torsoWorld, shoulders, sk.torso_core_shoulder_zone_lu * s.Worker.Proportions.upper_m);
        }

        /// <summary>Section 12 addendum 5: one frame's skinning checks against the take's reference.</summary>
        void MeasureSkin(Site s, TakeRecord rec, bool right)
        {
            var sk = m_Cfg.skinning;
            var frame = new Dictionary<SkinnedMeshRenderer, Vector3[]>();
            var a = s.Worker.Animator;
            Vector3 e = a.GetBoneTransform(right ? HumanBodyBones.RightLowerArm : HumanBodyBones.LeftLowerArm).position;
            Vector3 wr = a.GetBoneTransform(right ? HumanBodyBones.RightHand : HumanBodyBones.LeftHand).position;
            var fore = Positions(s, right ? s.ForearmR : s.ForearmL, frame);
            float ratio = s.RefBands != null ? SkinGeometry.MinRatio(s.RefRadii, SkinGeometry.BandRadii(fore, s.RefBands, sk.forearm_bands, e, wr)) : float.NaN;
            var torso = TorsoLocal(Positions(s, s.Torso, frame), s.Torso);
            var disp = new List<float>(torso.Count);
            var core = new List<float>(torso.Count);
            for (int i = 0; i < torso.Count && s.RefTorso != null && i < s.RefTorso.Length; i++)
            {
                float d = Vector3.Distance(torso[i], s.RefTorso[i]);
                disp.Add(d);
                if (s.RefTorsoCore != null && i < s.RefTorsoCore.Length && s.RefTorsoCore[i]) core.Add(d);
            }
            // addendum 7: the rule applies to the torso core; the whole torso is reported as information
            float pAll = SkinGeometry.Percentile(disp, sk.torso_percentile);
            float p = SkinGeometry.Percentile(core, sk.torso_percentile), max = core.Count > 0 ? core.Max() : float.NaN;
            rec.skin_frames++;
            rec.forearm_vertices = fore.Count;
            rec.forearm_bands = s.RefBands != null ? s.RefBands.Where(b => b >= 0).Distinct().Count() : 0;
            rec.torso_vertices = torso.Count;
            rec.torso_core_vertices = core.Count;
            if (!float.IsNaN(pAll)) rec.max_torso_all_percentile_m = Mathf.Max(rec.max_torso_all_percentile_m, R4(pAll));
            var why = new List<string>();
            if (float.IsNaN(ratio)) { rec.skin_forearm_na++; why.Add("forearm not measurable"); }
            else
            {
                rec.min_forearm_ratio = Mathf.Min(rec.min_forearm_ratio, R4(ratio));
                if (ratio < sk.forearm_min_ratio) why.Add("forearm loses volume");
            }
            if (!float.IsNaN(p))
            {
                rec.max_torso_percentile_m = Mathf.Max(rec.max_torso_percentile_m, R4(p));
                rec.max_torso_max_m = Mathf.Max(rec.max_torso_max_m, R4(max));
                if (!(p < sk.torso_max_displacement_m)) why.Add("torso deforms");
            }
            else why.Add("torso not measurable");
            if (why.Count > 0)
            {
                rec.skin_frames_failed++;
                rec.skin_pass = false;
                if (rec.skin_first_failure.Length == 0)
                    rec.skin_first_failure = $"{string.Join(", ", why)}: forearm {(float.IsNaN(ratio) ? "n/a" : ratio.ToString("0.00", Inv))}, torso p{sk.torso_percentile} " +
                                             $"{(float.IsNaN(p) ? "n/a" : (p * 100f).ToString("0.00", Inv) + " cm")}, max {(float.IsNaN(max) ? "n/a" : (max * 100f).ToString("0.00", Inv) + " cm")}";
            }
        }

        /// <summary>The vertices of every skinned mesh of the look whose largest bone weight is on this hand bone and at least minWeight.</summary>
        static List<KeyValuePair<SkinnedMeshRenderer, int[]>> PalmVertices(GameObject look, Transform hand, float minWeight)
        {
            var list = new List<KeyValuePair<SkinnedMeshRenderer, int[]>>();
            if (look == null || hand == null) return list;
            foreach (var smr in look.GetComponentsInChildren<SkinnedMeshRenderer>(true))
            {
                var mesh = smr.sharedMesh;
                var bones = smr.bones;
                if (mesh == null || bones == null) continue;
                int hi = Array.IndexOf(bones, hand);
                if (hi < 0) continue;
                var bw = mesh.boneWeights;
                var idx = new List<int>();
                for (int i = 0; i < bw.Length; i++)
                {
                    var b = bw[i];
                    int best = b.boneIndex0;
                    float w = b.weight0;
                    if (b.weight1 > w) { best = b.boneIndex1; w = b.weight1; }
                    if (b.weight2 > w) { best = b.boneIndex2; w = b.weight2; }
                    if (b.weight3 > w) { best = b.boneIndex3; w = b.weight3; }
                    if (best == hi && w >= minWeight) idx.Add(i);
                }
                if (idx.Count > 0) list.Add(new KeyValuePair<SkinnedMeshRenderer, int[]>(smr, idx.ToArray()));
            }
            return list;
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
                var c = new CommandRecord { command = cmd, takes = takes.Count, pass = true, render_pass = true };
                foreach (var t in takes)
                {
                    c.frames += t.frames;
                    c.frames_failed += t.frames_failed;
                    c.frames_render_failed += t.frames_render_failed;
                    c.frames_fold += t.frames_fold;
                    if (!t.pass || t.frames == 0) c.pass = false;
                    if (!t.render_pass || t.frames == 0) c.render_pass = false;
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
                    c.skin_frames += t.skin_frames;
                    c.skin_frames_failed += t.skin_frames_failed;
                    c.skin_forearm_na += t.skin_forearm_na;
                    c.forearm_vertices = Math.Max(c.forearm_vertices, t.forearm_vertices);
                    c.torso_vertices = Math.Max(c.torso_vertices, t.torso_vertices);
                    c.min_forearm_ratio = Mathf.Min(c.min_forearm_ratio, t.min_forearm_ratio);
                    c.max_torso_percentile_m = Mathf.Max(c.max_torso_percentile_m, t.max_torso_percentile_m);
                    c.max_torso_max_m = Mathf.Max(c.max_torso_max_m, t.max_torso_max_m);
                    c.torso_core_vertices = Math.Max(c.torso_core_vertices, t.torso_core_vertices);
                    c.max_torso_all_percentile_m = Mathf.Max(c.max_torso_all_percentile_m, t.max_torso_all_percentile_m);
                    if (!t.skin_pass || t.skin_frames == 0)
                    {
                        c.skin_pass = false;
                        c.skin_failures += (c.skin_failures.Length > 0 ? "; " : "") + $"{t.arm} {t.clip}: " + (t.skin_frames == 0 ? "no frame measured" : t.skin_first_failure);
                    }
                    if (!t.hand_checked) continue;
                    c.hand_checked = true;
                    c.hand_frames += t.hand_frames;
                    c.hand_frames_failed += t.hand_frames_failed;
                    c.hand_frames_mesh_na += t.hand_frames_mesh_na;
                    if (!t.hand_pass || t.hand_frames == 0)
                    {
                        c.hand_pass = false;
                        c.hand_failures += (c.hand_failures.Length > 0 ? "; " : "") + $"{t.arm} {t.clip}: " + (t.hand_frames == 0 ? "no frame measured" : t.hand_first_failure);
                    }
                    c.min_palm_vertices = c.min_palm_vertices < 0 ? t.min_palm_vertices : Math.Min(c.min_palm_vertices, t.min_palm_vertices);
                    c.max_palm_bone_deg = Mathf.Max(c.max_palm_bone_deg, t.max_palm_bone_deg);
                    c.max_palm_mesh_deg = Mathf.Max(c.max_palm_mesh_deg, t.max_palm_mesh_deg);
                    c.max_palm_mesh_flatness = Mathf.Max(c.max_palm_mesh_flatness, t.max_palm_mesh_flatness);
                    c.max_thumb_palm_lengths = Mathf.Max(c.max_thumb_palm_lengths, t.max_thumb_palm_lengths);
                    c.min_thumb_side = Mathf.Min(c.min_thumb_side, t.min_thumb_side);
                    c.min_thumb_across = Mathf.Min(c.min_thumb_across, t.min_thumb_across);
                    c.max_thumb_across = Mathf.Max(c.max_thumb_across, t.max_thumb_across);
                }
                l.commands.Add(c);
                if (!c.pass) l.pass = false;
            }
            l.hand_pass = l.status == "ok" && l.commands.Any(c => c.hand_checked) && l.commands.Where(c => c.hand_checked).All(c => c.hand_pass);
            l.skin_pass = l.status == "ok" && l.commands.Count > 0 && l.commands.All(c => c.skin_pass);
        }

        /// <summary>Section 12 addendum 5: the skinning checks per look and command.</summary>
        static string SkinTable(GeometryFile f, GeometrySkinning sk)
        {
            var sb = new StringBuilder();
            sb.Append($"# Skinning check: forearm volume and torso rigidity ({(f.label.Length > 0 ? f.label + ", " : "")}{f.created_local})\n\n");
            sb.Append($"experiments_ab.md section 12 addendum 5. Reference: the idle pose just before each take's request. Forearm: vertices bound mainly to the gesturing LowerArm " +
                      $"(>= {sk.forearm_weight_min.ToString("0.0#", Inv)}) in {sk.forearm_bands} bands along elbow to wrist (bands under {sk.forearm_min_band_vertices} vertices skipped); " +
                      $"each band's mean distance from the elbow-to-wrist line over its reference; the narrowest must keep >= {sk.forearm_min_ratio.ToString("0.00", Inv)}. " +
                      $"Torso: vertices bound mainly to {string.Join(", ", sk.torso_bones)} (>= {sk.torso_weight_min.ToString("0.0#", Inv)}), each in its own bone's frame; " +
                      $"the rule (addendum 7) applies to the torso core (outside {sk.torso_core_shoulder_zone_lu.ToString("0.0#", Inv)} Lu of both UpperArm bones): " +
                      $"core p{sk.torso_percentile} displacement < {(sk.torso_max_displacement_m * 100f).ToString("0.00#", Inv)} cm; the whole torso's p{sk.torso_percentile} is information. " +
                      "Worst values over every measured frame of every take, both arms.\n\n");
            sb.Append("| look | kind | command | frames | forearm vertices | forearm narrowest band (ratio, min) | torso vertices (core) | torso core p" + sk.torso_percentile + " max (cm) | torso core max (cm) | whole torso p" + sk.torso_percentile + " (cm, info) | pass |\n");
            sb.Append("|---|---|---|---|---|---|---|---|---|---|---|\n");
            foreach (var l in f.looks)
            {
                if (l.status != "ok") { sb.Append($"| {l.id} | {l.kind_group} | {l.status} | | | | | | | no |\n"); continue; }
                foreach (var c in l.commands)
                    sb.Append($"| {l.id} | {l.kind_group} | {c.command} | {c.skin_frames} | {c.forearm_vertices} | {(c.min_forearm_ratio < 900f ? c.min_forearm_ratio.ToString("0.00", Inv) : "n/a")} | " +
                              $"{c.torso_vertices} ({c.torso_core_vertices}) | {(c.max_torso_percentile_m >= 0f ? (c.max_torso_percentile_m * 100f).ToString("0.00", Inv) : "n/a")} | " +
                              $"{(c.max_torso_max_m >= 0f ? (c.max_torso_max_m * 100f).ToString("0.00", Inv) : "n/a")} | " +
                              $"{(c.max_torso_all_percentile_m >= 0f ? (c.max_torso_all_percentile_m * 100f).ToString("0.00", Inv) : "n/a")} | {(c.skin_pass ? "yes" : "**no**")} |\n");
            }
            var fails = f.looks.Where(l => l.status == "ok").SelectMany(l => l.commands.Where(c => !c.skin_pass).Select(c => $"- {l.id} {c.command}: {c.skin_failures}")).ToList();
            if (fails.Count > 0) sb.Append("\nFailures (first failing frame of each failing take):\n\n").Append(string.Join("\n", fails)).Append('\n');
            return sb.ToString();
        }

        /// <summary>Section 12: the hand check per look and command (palm toward the robot camera; WAIT thumb tucked).</summary>
        static string HandTable(GeometryFile f, GeometryTolerance tol)
        {
            var sb = new StringBuilder();
            sb.Append($"# Hand check: palm orientation and the WAIT thumb ({(f.label.Length > 0 ? f.label + ", " : "")}{f.created_local})\n\n");
            sb.Append($"experiments_ab.md section 12. Palm normal within {F(tol.palm_facing_deg)} deg of the robot camera (the stand-in robot's eye), from the bones " +
                      $"(LookPoser.PalmNormal) and from the skinned mesh (plane fit of the vertices bound mainly to the Hand bone, weight >= {tol.palm_hand_weight_min.ToString("0.0#", Inv)}, " +
                      $"between wrist and finger bases; n/a below {tol.palm_mesh_min_vertices} vertices or above flatness {tol.palm_mesh_flatness_max.ToString("0.0#", Inv)}). " +
                      $"WAIT thumb tucked: tip within {tol.thumb_tip_max_palm_lengths.ToString("0.0#", Inv)} palm lengths (Lp) of the palm centre and at least " +
                      $"{tol.thumb_palm_side_min.ToString("0.0#", Inv)} Lp on the palm side; 'across' is reported only (0 at the index base, 1 at the outermost base). " +
                      "Worst values over every measured hold frame of every take, both arms.\n\n");
            sb.Append("| look | kind | command | frames | palm vs camera, bones max (deg) | mesh max (deg) | mesh n/a frames | palm vertices min | flatness max | thumb tip max (Lp) | thumb palm side min (Lp) | thumb across | pass |\n");
            sb.Append("|---|---|---|---|---|---|---|---|---|---|---|---|---|\n");
            foreach (var l in f.looks)
            {
                if (l.status != "ok") { sb.Append($"| {l.id} | {l.kind_group} | {l.status} | | | | | | | | | | no |\n"); continue; }
                foreach (var c in l.commands.Where(x => x.hand_checked))
                {
                    bool wait = c.command == WorkerV4Config.Wait;
                    sb.Append($"| {l.id} | {l.kind_group} | {c.command} | {c.hand_frames} | {F(c.max_palm_bone_deg)} | {(c.max_palm_mesh_deg >= 0f ? F(c.max_palm_mesh_deg) : "n/a")} | " +
                              $"{(c.hand_frames_mesh_na == 0 ? "0" : $"**{c.hand_frames_mesh_na}**")} | {c.min_palm_vertices} | {(c.max_palm_mesh_flatness >= 0f ? c.max_palm_mesh_flatness.ToString("0.000", Inv) : "-")} | " +
                              $"{(wait && c.max_thumb_palm_lengths >= 0f ? c.max_thumb_palm_lengths.ToString("0.00", Inv) : "-")} | {(wait && c.min_thumb_side < 900f ? c.min_thumb_side.ToString("0.00", Inv) : "-")} | " +
                              $"{(wait && c.min_thumb_across < 900f ? $"{c.min_thumb_across.ToString("0.00", Inv)} to {c.max_thumb_across.ToString("0.00", Inv)}" : "-")} | {(c.hand_pass ? "yes" : "**no**")} |\n");
                }
            }
            var fails = f.looks.Where(l => l.status == "ok").SelectMany(l => l.commands.Where(c => c.hand_checked && !c.hand_pass).Select(c => $"- {l.id} {c.command}: {c.hand_failures}")).ToList();
            if (fails.Count > 0) sb.Append("\nFailures (first failing frame of each failing take):\n\n").Append(string.Join("\n", fails)).Append('\n');
            var diag = f.looks.Where(l => l.status == "ok").SelectMany(l => l.takes.Where(t => t.palm_mesh_groups.Length > 0)
                                                                                   .GroupBy(t => t.command + " " + t.arm).Select(g => g.First())
                                                                                   .Select(t => $"- {l.id} {t.command} {t.arm} ({t.clip}): {t.palm_mesh_groups}")).ToList();
            if (diag.Count > 0)
                sb.Append("\nDiagnostic (section 12 addendum 1, not a pass rule): the mesh palm normal of each sub-mesh's palm vertices against the camera, " +
                          "first measured frame of the first take per command and arm:\n\n").Append(string.Join("\n", diag)).Append('\n');
            return sb.ToString();
        }

        static string Table(GeometryFile f)
        {
            var sb = new StringBuilder();
            sb.Append($"# Gesture geometry ({(f.label.Length > 0 ? f.label + ", " : "")}{f.created_local})\n\n");
            sb.Append($"Tolerance: {f.tolerance}. Worst values over every measured frame of every take (both arms, every clip).\n\n");
            sb.Append("| look | kind | upper / fore (m) | upper share | shoulders (m) | arm / shoulders | command | takes | frames | elbow rendered min (deg) | elbow intended (deg) | elbow err max | arm dir err max | forearm err max | target shift vs old (m) | rendering | no fold (frames below) | pass |\n");
            sb.Append("|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|\n");
            foreach (var l in f.looks)
            {
                if (l.status != "ok") { sb.Append($"| {l.id} | {l.kind_group} | | | | | {l.status}: {l.problem} | | | | | | | | | | | no |\n"); continue; }
                foreach (var c in l.commands)
                    sb.Append($"| {l.id} | {l.kind_group} | {F3(l.upper_arm_m)} / {F3(l.forearm_m)} | {F3(l.upper_share)} | {F3(l.shoulder_width_m)} | {F3(l.arm_to_shoulder_ratio)} | {c.command} | {c.takes} | {c.frames} | " +
                              $"{F(c.min_elbow_deg)} | {F(c.min_intended_elbow_deg)} to {F(c.max_intended_elbow_deg)} | {F(c.max_elbow_error_deg)} | {F(c.max_arm_direction_error_deg)} | " +
                              $"{(c.max_forearm_error_deg >= 0f ? F(c.max_forearm_error_deg) : "-")} | {F3(c.max_target_shift_m)} | {(c.render_pass ? "ok" : "**fails**")} | " +
                              $"{(c.frames_fold == 0 ? "ok" : $"**{c.frames_fold}**")} | {(c.pass ? "yes" : "**no**")} |\n");
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
