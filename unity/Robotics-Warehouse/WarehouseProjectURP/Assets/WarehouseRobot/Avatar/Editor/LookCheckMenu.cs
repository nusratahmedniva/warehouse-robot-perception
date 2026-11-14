using System;
using System.Collections.Generic;
using System.Diagnostics;
using System.Globalization;
using System.IO;
using System.Linq;
using System.Reflection;
using System.Security.Cryptography;
using System.Text;
using System.Text.RegularExpressions;
using UnityEditor;
using UnityEditor.Rendering;
using UnityEditor.Rendering.Universal;
using UnityEditor.SceneManagement;
using UnityEngine;
using UnityEngine.Rendering;
using UnityEngine.SceneManagement;
using WarehouseRobot;
using Debug = UnityEngine.Debug;
using Object = UnityEngine.Object;

namespace WarehouseAvatar.EditorTools
{
    /// <summary>
    /// Tools > Warehouse v4 > Look Check (v4 Phase 2A, before any gesture clip): does each candidate look render in URP,
    /// is it Humanoid with finger bones, and can the existing Python models see it?
    /// - Build LookCheck Scene: Assets/WarehouseRobot/Avatar/LookCheck.unity (refuses if it exists).
    /// - Convert Sunbox Materials to URP: the Sunbox pack ships Built-in Standard materials (magenta under URP); converts
    ///   them in place with URP's own StandardUpgrader (the Render Pipeline Converter's material upgrader). The pack is
    ///   git-ignored, so every machine runs this once after importing it.
    /// - Run Look Check: every look in look_check.json, every command, arm, take and distance, rendered with the pan-tilt
    ///   camera settings of robot_unity_v4.json (PanTiltCamera.ApplyCameraSettings) into a new folder
    ///   robot_vision/outputs/look_check_&lt;time&gt;/ (git-ignored): looks_check/ in the input format of docs/look_check_v4.md
    ///   (Anisha's look_check_v4.py --input), and next to it recordings.jsonl, inventory.json, config_used/, run_info.json
    ///   (git commit). Never overwrites a folder or a file.
    /// Batch mode: -executeMethod WarehouseAvatar.EditorTools.LookCheckMenu.BatchBuildScene / BatchConvertSunbox /
    /// BatchRun (exit code 0 = done).
    /// Third-party code (Sunbox) is reached by reflection only, so this compiles on a machine without the pack.
    /// </summary>
    public static class LookCheckMenu
    {
        public const string ScenePath = "Assets/WarehouseRobot/Avatar/LookCheck.unity";
        public const string ConfigPath = "Assets/WarehouseRobot/Avatar/Config/look_check.json";
        const string SunboxFolder = "Assets/SunboxGames";
        static readonly CultureInfo Inv = CultureInfo.InvariantCulture;
        static readonly UTF8Encoding Utf8 = new UTF8Encoding(false);

        // ---------------------------------------------------------------- menu and batch entry points

        [MenuItem("Tools/Warehouse v4/Look Check/Build LookCheck Scene")]
        public static void BuildSceneMenu() => Report("Build LookCheck Scene", BuildScene());

        [MenuItem("Tools/Warehouse v4/Look Check/Convert Sunbox Materials to URP")]
        public static void ConvertSunboxMenu() => Report("Convert Sunbox Materials", ConvertSunboxMaterials());

        [MenuItem("Tools/Warehouse v4/Look Check/Run Look Check")]
        public static void RunMenu()
        {
            if (!EditorSceneManager.SaveCurrentModifiedScenesIfUserWantsTo()) return;
            Report("Run Look Check", Run());
        }

        [MenuItem("Tools/Warehouse v4/Experiments/Run Look Check (avatar experiment looks)")]
        public static void RunExperimentMenu()
        {
            if (!EditorSceneManager.SaveCurrentModifiedScenesIfUserWantsTo()) return;
            Report("Run Look Check (avatar experiment)", RunExperiment());
        }

        public static void BatchBuildScene() => Batch(BuildScene);
        public static void BatchConvertSunbox() => Batch(ConvertSunboxMaterials);
        public static void BatchRun() => Batch(Run);
        public static void BatchRunExperiment() => Batch(RunExperiment);

        /// <summary>
        /// Experiments A/B (2026-11-14, experiments_ab.md section 2): the same look check on every look of looks_ab.json
        /// avatar_experiment, each defined in looks_ab.json, worker_v4.json or look_check.json (first found), into a new folder
        /// look_check_ab_&lt;time&gt;/; looks_ab.json and worker_v4.json are copied to config_used/. look_check.json is not changed.
        /// </summary>
        public static string RunExperiment()
        {
            var ab = ExperimentLooksMenu.Load(out string abText);
            var workerAsset = AssetDatabase.LoadAssetAtPath<TextAsset>(WorkerTemplateMenu.ConfigPath) ?? throw new FileNotFoundException(WorkerTemplateMenu.ConfigPath);
            var worker = WorkerV4Config.Parse(workerAsset.text);
            var errors = ExperimentLooks.Validate(ab, worker.looks);
            if (errors.Count > 0) throw new InvalidOperationException("looks_ab.json: " + string.Join("; ", errors));
            // experiments_ab.md section 5: -lookCheckLooks <id>[,<id>...] keeps those looks (recorded in run_info.json looks_subset)
            var subset = ExperimentLooks.Subset(Environment.GetCommandLineArgs(), ab.avatar_experiment, out string subsetError);
            if (subsetError != null) throw new ArgumentException(subsetError);
            return Run(cfg =>
            {
                var looks = new List<LookEntry>();
                foreach (var id in subset ?? ab.avatar_experiment)
                    looks.Add(ab.looks.FirstOrDefault(l => l.id == id) ?? worker.Look(id) ?? cfg.looks.FirstOrDefault(l => l.id == id)
                              ?? throw new ArgumentException($"look '{id}' is defined nowhere"));
                cfg.looks = looks.ToArray();
                cfg.paths.output_prefix = cfg.paths.output_prefix + "_ab";
            }, new Dictionary<string, string> { { "looks_ab.json", abText }, { "worker_v4.json", workerAsset.text } },
               subset != null ? string.Join(",", subset) : "");
        }

        static void Batch(Func<string> action)
        {
            try
            {
                Debug.Log("[LookCheck] " + action());
                EditorApplication.Exit(0);
            }
            catch (Exception e)
            {
                Debug.LogError("[LookCheck] FAILED: " + e);
                EditorApplication.Exit(1);
            }
        }

        static void Report(string title, string message)
        {
            Debug.Log("[LookCheck] " + message);
            EditorUtility.DisplayDialog(title, message.Length > 1500 ? message.Substring(0, 1500) + " ..." : message, "OK");
        }

        // ---------------------------------------------------------------- scene

        public static string BuildScene()
        {
            if (File.Exists(ProjectFile(ScenePath))) throw new InvalidOperationException(ScenePath + " exists; delete it first to rebuild it");
            var cfgAsset = AssetDatabase.LoadAssetAtPath<TextAsset>(ConfigPath) ?? throw new FileNotFoundException(ConfigPath);
            var cfg = LoadConfig(cfgAsset);
            var scene = EditorSceneManager.NewScene(NewSceneSetup.EmptyScene, NewSceneMode.Single);

            var stageGo = new GameObject("LookCheckStage");
            var stage = stageGo.AddComponent<LookCheckStage>();
            stage.config = cfgAsset;
            var mount = new GameObject("PanTiltMount");
            mount.transform.SetParent(stageGo.transform, false);
            var camGo = new GameObject("PanTiltCamera_LookCheck");
            camGo.transform.SetParent(mount.transform, false);
            stage.checkCamera = camGo.AddComponent<Camera>();
            var lightGo = new GameObject("KeyLight");
            lightGo.transform.SetParent(stageGo.transform, false);
            stage.keyLight = lightGo.AddComponent<Light>();
            stage.keyLight.type = LightType.Directional;
            stage.keyLight.shadows = LightShadows.Soft;
            var root = new GameObject("StageRoot");
            root.transform.SetParent(stageGo.transform, false);
            stage.stageRoot = root.transform;
            ApplyStage(stage, cfg, LoadPanTilt(cfg), cfg.recording.distances_m[0], cfg.recording.vertical_fov_deg);
            if (!EditorSceneManager.SaveScene(scene, ScenePath)) throw new IOException("could not save " + ScenePath);
            return "Saved " + ScenePath + ". Open it, select LookCheckStage and press Show in the Inspector to preview a look.";
        }

        /// <summary>Camera (pan-tilt settings, fov replaced), light and ambient for one render.</summary>
        static void ApplyStage(LookCheckStage stage, LookCheckConfig cfg, PanTiltCameraConfig pt, float distanceM, float fovDeg)
        {
            var r = cfg.render;
            stage.checkCamera.transform.parent.localPosition = new Vector3(0f, pt.height_m, 0f);
            stage.checkCamera.transform.parent.localRotation = Quaternion.identity;
            PanTiltCamera.ApplyCameraSettings(stage.checkCamera, pt);
            stage.checkCamera.fieldOfView = fovDeg;
            stage.checkCamera.clearFlags = CameraClearFlags.SolidColor;
            stage.checkCamera.backgroundColor = Grey(r.backdrop_grey);
            stage.keyLight.transform.localRotation = Quaternion.Euler(r.light_euler_deg[0], r.light_euler_deg[1], r.light_euler_deg[2]);
            stage.keyLight.intensity = r.light_intensity;
            RenderSettings.ambientMode = AmbientMode.Flat;
            RenderSettings.ambientLight = Grey(r.ambient_grey);
            RenderSettings.skybox = null;
            RenderSettings.fog = false;
        }

        static Color Grey(float g) => new Color(g, g, g, 1f);

        // ---------------------------------------------------------------- Sunbox materials

        public static string ConvertSunboxMaterials()
        {
            if (!AssetDatabase.IsValidFolder(SunboxFolder)) return SunboxFolder + " not found (Sunbox pack not imported): nothing to convert.";
            var upgraders = new List<MaterialUpgrader> { new StandardUpgrader("Standard"), new StandardUpgrader("Standard (Specular setup)") };
            var names = new HashSet<string> { "Standard", "Standard (Specular setup)" };
            int converted = 0, other = 0;
            var log = new StringBuilder();
            foreach (var guid in AssetDatabase.FindAssets("t:Material", new[] { SunboxFolder }))
            {
                string path = AssetDatabase.GUIDToAssetPath(guid);
                var m = AssetDatabase.LoadAssetAtPath<Material>(path);
                if (m == null || m.shader == null) continue;
                if (!names.Contains(m.shader.name)) { other++; continue; }
                MaterialUpgrader.Upgrade(m, upgraders, MaterialUpgrader.UpgradeFlags.None);
                EditorUtility.SetDirty(m);
                converted++;
                log.Append(Path.GetFileName(path)).Append(' ');
            }
            AssetDatabase.SaveAssets();
            return $"Sunbox materials converted to URP Lit: {converted}; already other shaders: {other}. {log}";
        }

        // ---------------------------------------------------------------- preview (Inspector)

        public static string Show(LookCheckStage stage)
        {
            var cfg = LoadConfig(stage.config);
            var pt = LoadPanTilt(cfg);
            var look = cfg.looks.FirstOrDefault(l => l.id == stage.previewLook)
                       ?? throw new ArgumentException($"look '{stage.previewLook}' is not in {ConfigPath}");
            var cmd = cfg.commands.FirstOrDefault(c => c.command == stage.previewCommand)
                      ?? throw new ArgumentException($"command '{stage.previewCommand}' is not in {ConfigPath} (POINT, WAIT, STOP, NONE)");
            var v = cmd.variants.FirstOrDefault(x => x.take == stage.previewTake)
                    ?? throw new ArgumentException($"{cmd.command} has no take '{stage.previewTake}' in {ConfigPath}");
            string arm = cmd.arm_labelled ? stage.previewArm : "";
            if (cmd.arm_labelled && Array.IndexOf(cfg.recording.arms, arm) < 0) throw new ArgumentException($"arm '{arm}' must be left or right");
            ClearStage(stage);
            BuildBackdrop(stage, cfg, stage.previewDistanceM);
            var spawned = Spawn(look, stage.stageRoot, cfg);
            if (spawned.Root == null) return $"{look.id}: {spawned.Row.status} ({spawned.Row.note})";
            Place(spawned, stage, stage.previewDistanceM);
            spawned.Poser?.Apply(PoseSpec.From(cmd.command, arm, v));
            ApplyStage(stage, cfg, pt, stage.previewDistanceM, cfg.recording.vertical_fov_deg);
            MarkDontSave(stage.stageRoot);
            SceneView.RepaintAll();
            return $"{LookCheckConfig.RecordingName(look.id, cmd.command, stage.previewDistanceM, arm, v.take)} " +
                   $"(select PanTiltCamera_LookCheck for the camera preview). Status: {spawned.Row.status}.";
        }

        // ---------------------------------------------------------------- run

        public static string Run() => Run(null, null);

        static string Run(Action<LookCheckConfig> adjust, Dictionary<string, string> extraConfigs, string looksSubset = "")
        {
            var cfgAsset = AssetDatabase.LoadAssetAtPath<TextAsset>(ConfigPath) ?? throw new FileNotFoundException(ConfigPath);
            var cfg = LoadConfig(cfgAsset);
            adjust?.Invoke(cfg);
            var pt = LoadPanTilt(cfg);
            if (!File.Exists(ProjectFile(ScenePath))) throw new FileNotFoundException(ScenePath + " missing: run Build LookCheck Scene first");
            EditorSceneManager.OpenScene(ScenePath, OpenSceneMode.Single);
            var stage = Object.FindObjectOfType<LookCheckStage>() ?? throw new InvalidOperationException("no LookCheckStage in " + ScenePath);

            string repo = RepoRoot(cfg);
            string outDir = NewOutputFolder(Path.Combine(repo, cfg.paths.output_root), cfg.paths.output_prefix);
            string recDir = Path.Combine(outDir, cfg.recording.folder_name);   // recordings only: look_check_v4.py --input
            Directory.CreateDirectory(recDir);
            Directory.CreateDirectory(Path.Combine(outDir, "config_used"));
            WriteNew(Path.Combine(outDir, "config_used", "look_check.json"), cfgAsset.text);
            var robotAsset = AssetDatabase.LoadAssetAtPath<TextAsset>(cfg.paths.robot_unity_config);
            WriteNew(Path.Combine(outDir, "config_used", Path.GetFileName(cfg.paths.robot_unity_config)), robotAsset.text);
            if (extraConfigs != null) foreach (var kv in extraConfigs) WriteNew(Path.Combine(outDir, "config_used", kv.Key), kv.Value);

            float fov = cfg.recording.vertical_fov_deg;
            var rest = new PoseSpec { Command = LookCheckConfig.None, ElevationDeg = -Mathf.Atan2(1f, cfg.hand.rest_outward) * Mathf.Rad2Deg };
            var rows = new List<LookInventoryRow>();
            var lines = new StringBuilder();
            int recordings = 0, frames = 0;
            foreach (var look in cfg.looks)
            {
                ClearStage(stage);
                var spawned = Spawn(look, stage.stageRoot, cfg);
                rows.Add(spawned.Row);
                if (spawned.Root == null || spawned.Poser == null || !spawned.Poser.HasArms) continue;
                int maxMagenta = 0;
                bool measured = false;
                foreach (float d in cfg.recording.distances_m)
                {
                    ClearBackdrop(stage);
                    BuildBackdrop(stage, cfg, d);
                    Place(spawned, stage, d);
                    if (!measured)
                    {
                        spawned.Poser.Apply(rest);
                        spawned.Row.height_m = LookInventory.Height(spawned.Root);
                        measured = true;
                    }
                    ApplyStage(stage, cfg, pt, d, fov);
                    foreach (var c in cfg.commands)
                        foreach (string arm in c.arm_labelled ? cfg.recording.arms : new[] { "" })
                            foreach (var v in c.variants)
                            {
                                spawned.Poser.Apply(PoseSpec.From(c.command, arm, v));
                                var px = Render(stage.checkCamera, pt.width_px, pt.height_px, out byte[] png);
                                int magenta = LookInventory.MagentaPixels(px, cfg.render.magenta_tolerance);
                                maxMagenta = Mathf.Max(maxMagenta, magenta);
                                string name = LookCheckConfig.RecordingName(look.id, c.command, d, arm, v.take);
                                int n = v.sequence ? cfg.recording.sequence_frames : 1;
                                if (v.sequence)
                                {
                                    string seqDir = Path.Combine(recDir, name);
                                    if (Directory.Exists(seqDir)) throw new IOException(seqDir + " exists");
                                    Directory.CreateDirectory(seqDir);
                                    for (int i = 0; i < n; i++)          // a held pose: the same render for every frame of the second
                                    {
                                        string stem = Path.Combine(seqDir, LookCheckConfig.FrameStem(i));
                                        WriteNew(stem + ".png", png);
                                        WriteNew(stem + ".json", LookCheckConfig.HeaderJson(pt.width_px, pt.height_px, fov, pt.height_m, i, arm, v));
                                    }
                                }
                                else
                                {
                                    WriteNew(Path.Combine(recDir, name + ".png"), png);
                                    WriteNew(Path.Combine(recDir, name + ".json"), LookCheckConfig.HeaderJson(pt.width_px, pt.height_px, fov, pt.height_m, 0, arm, v));
                                }
                                lines.Append(JsonUtility.ToJson(new RecordingRecord
                                {
                                    name = name, kind = v.sequence ? "sequence" : "frame", look = look.id, family = look.family, role = look.role,
                                    command = c.command, arm = arm, take = v.take, distance_m = d, vertical_fov_deg = fov, n_frames = n,
                                    azimuth_front_deg = v.azimuth_front_deg, elevation_deg = v.elevation_deg, forearm_up = v.forearm_up,
                                    spread_deg = v.spread_deg, magenta_pixels = magenta,
                                })).Append('\n');
                                recordings++;
                                frames += n;
                            }
                }
                spawned.Row.magenta_pixels = maxMagenta;
                spawned.Row.renders_in_urp = spawned.Row.material_problems.Length == 0 && maxMagenta == 0;
            }
            ClearStage(stage);
            WriteNew(Path.Combine(outDir, "recordings.jsonl"), lines.ToString());
            WriteNew(Path.Combine(outDir, "inventory.json"), JsonUtility.ToJson(new InventoryFile { looks = rows.ToArray() }, true));
            WriteNew(Path.Combine(outDir, "run_info.json"), JsonUtility.ToJson(RunInfo(repo, cfgAsset.text, robotAsset.text, looksSubset), true));
            string rel = Path.GetRelativePath(repo, recDir).Replace('\\', '/');
            return $"{recordings} recordings ({frames} frames) of {rows.Count(r => r.status == "ok")} usable looks ({rows.Count} listed) in {rel}. " +
                   string.Join("; ", rows.Select(r => $"{r.id}: {r.status}")) +
                   $". Next, from robot_vision/: look_check_v4.py --input {Path.GetRelativePath(Path.Combine(repo, "robot_vision"), recDir).Replace('\\', '/')}";
        }

        [Serializable]
        class RecordingRecord
        {
            public string name, kind, look, family, role, command, arm, take;
            public float distance_m, vertical_fov_deg, azimuth_front_deg, elevation_deg, spread_deg;
            public bool forearm_up;
            public int n_frames, magenta_pixels;
        }

        [Serializable] class InventoryFile { public LookInventoryRow[] looks; }

        [Serializable]
        class RunInfoRecord
        {
            public string created_local, git_commit, git_branch, git_status_porcelain, unity_version, render_pipeline, color_space, graphics_device;
            public string univrm_packages, look_check_sha256, robot_unity_config_sha256, note;
            /// <summary>experiments_ab.md section 5: the looks kept by -lookCheckLooks ("" = the whole list).</summary>
            public string looks_subset;
            public bool git_dirty;
        }

        static RunInfoRecord RunInfo(string repo, string cfgText, string robotText, string looksSubset)
        {
            string status = Git(repo, "status --porcelain");
            return new RunInfoRecord
            {
                created_local = DateTime.Now.ToString("yyyy-MM-dd'T'HH:mm:ss", Inv),
                git_commit = Git(repo, "rev-parse HEAD").Trim(),
                git_branch = Git(repo, "rev-parse --abbrev-ref HEAD").Trim(),
                git_status_porcelain = status,
                git_dirty = status.Trim().Length > 0,
                unity_version = Application.unityVersion,
                render_pipeline = GraphicsSettings.currentRenderPipeline != null ? GraphicsSettings.currentRenderPipeline.name : "built-in",
                color_space = QualitySettings.activeColorSpace.ToString(),
                graphics_device = SystemInfo.graphicsDeviceType + " " + SystemInfo.graphicsDeviceName,
                univrm_packages = UniVrmPackages(),
                look_check_sha256 = Sha256(cfgText),
                robot_unity_config_sha256 = Sha256(robotText),
                note = "v4 Phase 2A look check: a development check of which looks the existing models can see; not an evaluation.",
                looks_subset = looksSubset ?? "",
            };
        }

        // ---------------------------------------------------------------- spawning

        sealed class Spawned
        {
            public GameObject Root;     // the container placed on the floor; the look is its child
            public LookPoser Poser;
            public LookInventoryRow Row;
        }

        static Spawned Spawn(LookEntry look, Transform parent, LookCheckConfig cfg)
        {
            var row = new LookInventoryRow { id = look.id, family = look.family, role = look.role, source = look.source, asset = look.asset };
            var result = new Spawned { Row = row };
            var asset = AssetDatabase.LoadAssetAtPath<GameObject>(look.asset);
            if (asset == null && look.asset.EndsWith(".vrm", StringComparison.OrdinalIgnoreCase))
                asset = AssetDatabase.LoadAssetAtPath<GameObject>(Path.ChangeExtension(look.asset, ".prefab"));  // UniVRM 0.x prefab importer
            if (asset == null)
            {
                row.status = "not_installed";
                row.note = $"{look.asset} not in the project (third-party, git-ignored: import it first)";
                return result;
            }
            row.installed = true;
            var container = new GameObject("Look_" + look.id);
            container.transform.SetParent(parent, false);
            var inst = (GameObject)Object.Instantiate(asset, container.transform);
            inst.name = asset.name;
            inst.transform.localPosition = Vector3.zero;
            inst.transform.localRotation = Quaternion.identity;
            result.Root = container;

            Animator animator;
            try
            {
                animator = look.kind == LookEntry.KindSunbox ? ApplySunbox(inst, look.sunbox, row) : inst.GetComponentInChildren<Animator>();
                if (!string.IsNullOrEmpty(look.material_override)) OverrideMaterial(inst, look.material_override, row);
            }
            catch (Exception e)
            {
                row.status = "load_failed";
                row.note += (e is TargetInvocationException && e.InnerException != null ? e.InnerException : e).Message;
                return result;
            }
            // Edit mode has no player loop between renders: without this a skinned mesh keeps the first pose it was skinned
            // in. Set after the customisation, which creates the Sunbox clothing meshes.
            foreach (var smr in inst.GetComponentsInChildren<SkinnedMeshRenderer>(true))
            {
                smr.forceMatrixRecalculationPerRender = true;
                smr.updateWhenOffscreen = true;
            }

            row.material_problems = LookInventory.MaterialProblems(container, out var shaders).ToArray();
            row.shaders = shaders;
            row.humanoid = animator != null && animator.avatar != null && animator.avatar.isHuman;
            if (!row.humanoid)
            {
                row.status = "not_humanoid";
                row.note += " No Humanoid avatar (Rig > Animation Type must be Humanoid).";
                return result;
            }
            var bones = new AnimatorBones(animator);
            result.Poser = new LookPoser(bones, cfg.hand);
            LookInventory.FillBones(row, bones, result.Poser);
            row.status = result.Poser.HasArms ? "ok" : "no_arm_bones";
            row.note = row.note.Trim();
            return result;
        }

        /// <summary>The Sunbox avatar customised by reflection (SunboxLookApplier, shared with WorkerV4); returns the active base's Animator.</summary>
        static Animator ApplySunbox(GameObject inst, SunboxLook s, LookInventoryRow row)
        {
            var animator = SunboxLookApplier.Apply(inst, s, out string description);
            row.note = description;
            return animator;
        }

        static void OverrideMaterial(GameObject inst, string path, LookInventoryRow row)
        {
            var mat = AssetDatabase.LoadAssetAtPath<Material>(path);
            if (mat == null)
            {
                row.note += $" material_override {path} not found (v3: Tools > Warehouse HRI > Restore Worker Appearance creates it).";
                return;
            }
            foreach (var r in inst.GetComponentsInChildren<Renderer>(true))
            {
                var mats = new Material[Mathf.Max(1, r.sharedMaterials.Length)];
                for (int i = 0; i < mats.Length; i++) mats[i] = mat;
                r.sharedMaterials = mats;
            }
        }

        /// <summary>Stand the look on the floor at distanceM in front of the camera, facing it.</summary>
        static void Place(Spawned s, LookCheckStage stage, float distanceM)
        {
            s.Poser?.ResetToBind();
            var root = s.Root.transform;
            root.position = new Vector3(0f, 0f, distanceM);
            root.rotation = Quaternion.identity;
            Vector3 cam = stage.checkCamera.transform.parent.position;
            if (s.Poser != null && s.Poser.HasArms) s.Poser.FaceTowards(root, cam);
            if (LookInventory.MeshExtentY(s.Root, out float bottom, out _)) root.position -= new Vector3(0f, bottom, 0f);
        }

        // ---------------------------------------------------------------- stage geometry and rendering

        const string BackdropName = "Backdrop", FloorName = "Floor";

        static void BuildBackdrop(LookCheckStage stage, LookCheckConfig cfg, float distanceM)
        {
            var r = cfg.render;
            var lit = Shader.Find("Universal Render Pipeline/Lit") ?? throw new InvalidOperationException("URP Lit shader not found");
            var floor = GameObject.CreatePrimitive(PrimitiveType.Quad);
            floor.name = FloorName;
            floor.transform.SetParent(stage.stageRoot, false);
            floor.transform.SetPositionAndRotation(new Vector3(0f, 0f, r.floor_half_size_m * 0.5f), Quaternion.Euler(90f, 0f, 0f));
            floor.transform.localScale = new Vector3(2f * r.floor_half_size_m, 2f * r.floor_half_size_m, 1f);
            floor.GetComponent<Renderer>().sharedMaterial = new Material(lit) { color = Grey(r.floor_grey), name = "LookCheckFloor" };
            var wall = GameObject.CreatePrimitive(PrimitiveType.Quad);
            wall.name = BackdropName;
            wall.transform.SetParent(stage.stageRoot, false);
            float h = 4f * r.floor_half_size_m;
            wall.transform.SetPositionAndRotation(new Vector3(0f, 0.5f * h, distanceM + r.backdrop_behind_person_m), Quaternion.identity);
            wall.transform.localScale = new Vector3(4f * r.floor_half_size_m, h, 1f);
            wall.GetComponent<Renderer>().sharedMaterial = new Material(lit) { color = Grey(r.backdrop_grey), name = "LookCheckBackdrop" };
            foreach (var go in new[] { floor, wall }) Object.DestroyImmediate(go.GetComponent<Collider>());
        }

        static void ClearBackdrop(LookCheckStage stage)
        {
            foreach (Transform c in stage.stageRoot.Cast<Transform>().ToList())
                if (c.name == BackdropName || c.name == FloorName) Object.DestroyImmediate(c.gameObject);
        }

        static void ClearStage(LookCheckStage stage)
        {
            foreach (Transform c in stage.stageRoot.Cast<Transform>().ToList()) Object.DestroyImmediate(c.gameObject);
        }

        static void MarkDontSave(Transform t)
        {
            foreach (Transform c in t.Cast<Transform>())
                foreach (var x in c.GetComponentsInChildren<Transform>(true)) x.gameObject.hideFlags = HideFlags.DontSave;
        }

        /// <summary>One frame as the pan-tilt camera renders it (ARGB32 target with depth, as PanTiltCamera); PNG and pixels.</summary>
        static Color32[] Render(Camera cam, int w, int h, out byte[] png)
        {
            var rt = new RenderTexture(w, h, 24, RenderTextureFormat.ARGB32) { name = "LookCheckImage" };
            var tex = new Texture2D(w, h, TextureFormat.RGBA32, false);
            var previousActive = RenderTexture.active;
            var previousTarget = cam.targetTexture;
            try
            {
                rt.Create();
                cam.targetTexture = rt;
                cam.Render();
                RenderTexture.active = rt;
                tex.ReadPixels(new Rect(0, 0, w, h), 0, 0, false);
                tex.Apply(false);
                png = tex.EncodeToPNG();
                return tex.GetPixels32();
            }
            finally
            {
                cam.targetTexture = previousTarget;
                RenderTexture.active = previousActive;
                rt.Release();
                Object.DestroyImmediate(rt);
                Object.DestroyImmediate(tex);
            }
        }

        // ---------------------------------------------------------------- config, files, git

        static LookCheckConfig LoadConfig(TextAsset asset)
        {
            if (asset == null) throw new FileNotFoundException(ConfigPath);
            var cfg = LookCheckConfig.Parse(asset.text);
            var errors = cfg.Validate();
            if (errors.Count > 0) throw new InvalidOperationException(ConfigPath + ":\n  " + string.Join("\n  ", errors));
            return cfg;
        }

        static PanTiltCameraConfig LoadPanTilt(LookCheckConfig cfg)
        {
            var asset = AssetDatabase.LoadAssetAtPath<TextAsset>(cfg.paths.robot_unity_config)
                        ?? throw new FileNotFoundException(cfg.paths.robot_unity_config);
            return RobotConfig.Load(asset).Unity.pan_tilt_camera;
        }

        static string ProjectFile(string assetPath) => Path.Combine(Path.GetDirectoryName(Application.dataPath), assetPath);

        static string RepoRoot(LookCheckConfig cfg) =>
            Path.GetFullPath(Path.Combine(Path.GetDirectoryName(Application.dataPath), cfg.paths.repo_root_relative_to_unity_project));

        static string NewOutputFolder(string root, string prefix)
        {
            Directory.CreateDirectory(root);
            string stamp = DateTime.Now.ToString("yyyyMMdd_HHmmss", Inv);
            string path = Path.Combine(root, $"{prefix}_{stamp}");
            for (int i = 2; Directory.Exists(path); i++) path = Path.Combine(root, $"{prefix}_{stamp}_{i}");
            Directory.CreateDirectory(path);
            return path;
        }

        static void WriteNew(string path, string text) => WriteNew(path, Utf8.GetBytes(text));

        static void WriteNew(string path, byte[] bytes)
        {
            using (var fs = new FileStream(path, FileMode.CreateNew, FileAccess.Write)) fs.Write(bytes, 0, bytes.Length);
        }

        static string Git(string repo, string args)
        {
            try
            {
                var psi = new ProcessStartInfo("git", args)
                {
                    WorkingDirectory = repo, RedirectStandardOutput = true, RedirectStandardError = true, UseShellExecute = false, CreateNoWindow = true,
                };
                using (var p = Process.Start(psi))
                {
                    string output = p.StandardOutput.ReadToEnd();
                    p.WaitForExit(10000);
                    return p.ExitCode == 0 ? output : "unknown";
                }
            }
            catch (Exception e)
            {
                return "unknown (" + e.Message + ")";
            }
        }

        /// <summary>com.vrmc.* entries of Packages/packages-lock.json (version URL and commit hash).</summary>
        static string UniVrmPackages()
        {
            string lockPath = Path.Combine(Path.GetDirectoryName(Application.dataPath), "Packages", "packages-lock.json");
            if (!File.Exists(lockPath)) return "";
            string text = File.ReadAllText(lockPath);
            var parts = new List<string>();
            foreach (Match m in Regex.Matches(text, "\"(com\\.vrmc\\.[a-z.]+)\":\\s*\\{\\s*\"version\":\\s*\"([^\"]+)\"[\\s\\S]*?\"hash\":\\s*\"([0-9a-f]+)\""))
                parts.Add($"{m.Groups[1].Value} {m.Groups[2].Value} ({m.Groups[3].Value})");
            return string.Join("; ", parts);
        }

        static string Sha256(string text)
        {
            using (var sha = SHA256.Create())
                return string.Concat(sha.ComputeHash(Utf8.GetBytes(text)).Select(b => b.ToString("x2", Inv)));
        }
    }

    [CustomEditor(typeof(LookCheckStage))]
    public class LookCheckStageEditor : UnityEditor.Editor
    {
        public override void OnInspectorGUI()
        {
            DrawDefaultInspector();
            EditorGUILayout.Space();
            if (GUILayout.Button("Show"))
            {
                try { Debug.Log("[LookCheck] " + LookCheckMenu.Show((LookCheckStage)target)); }
                catch (Exception e) { Debug.LogError("[LookCheck] " + e.Message); }
            }
            EditorGUILayout.HelpBox("Spawns the preview look (not saved with the scene). The full check: Tools > Warehouse v4 > Look Check > Run Look Check.", MessageType.None);
        }
    }
}
