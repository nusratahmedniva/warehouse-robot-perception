using System;
using System.Collections.Generic;
using System.Globalization;
using System.IO;
using System.Linq;
using System.Security.Cryptography;
using System.Text;
using Unity.AI.Navigation;
using UnityEditor;
using UnityEditor.Animations;
using UnityEngine;
using Debug = UnityEngine.Debug;
using Object = UnityEngine.Object;

namespace WarehouseAvatar.EditorTools
{
    /// <summary>
    /// Tools > Warehouse v4 > Workers (v4 Phase 2B):
    /// - Import Mixamo Clips: copies the .fbx files named in worker_v4.json from paths.clip_source_folder (unity/downloads,
    ///   git-ignored) into paths.clip_import_folder (under the git-ignored Assets/ThirdParty/), imports each as Humanoid
    ///   with one clip (root baked into the pose), and writes clip_index.json next to them: per clip its length, the arm it
    ///   raises and when (from its Humanoid muscle curves). Never overwrites a different file of the same name.
    /// - Build Worker Template: the arm mask, the AnimatorController (base layer idle/turn, gesture layer masked to arms and
    ///   hands with one state per Mixamo variant, IK pass on both) and the prefab WorkerV4.prefab. Refuses if any exists.
    /// Batch mode: -executeMethod WarehouseAvatar.EditorTools.WorkerTemplateMenu.BatchImportClips / BatchBuildTemplate.
    /// </summary>
    public static class WorkerTemplateMenu
    {
        public const string ConfigPath = "Assets/WarehouseRobot/Avatar/Config/worker_v4.json";
        public const string AnimationFolder = "Assets/WarehouseRobot/Avatar/Animation";
        public const string MaskPath = AnimationFolder + "/WorkerV4_Arms.mask";
        public const string PrefabFolder = "Assets/WarehouseRobot/Avatar/Prefabs";
        public const string PrefabPath = PrefabFolder + "/WorkerV4.prefab";
        public const string BaseLayerName = "Base", GestureLayerName = "Gesture";
        public static readonly AvatarMaskBodyPart[] MaskParts =
            { AvatarMaskBodyPart.LeftArm, AvatarMaskBodyPart.RightArm, AvatarMaskBodyPart.LeftFingers, AvatarMaskBodyPart.RightFingers };
        static readonly CultureInfo Inv = CultureInfo.InvariantCulture;

        [MenuItem("Tools/Warehouse v4/Workers/Import Mixamo Clips")]
        public static void ImportMenu() => Report("Import Mixamo Clips", ImportClips());

        [MenuItem("Tools/Warehouse v4/Workers/Build Worker Template")]
        public static void BuildMenu() => Report("Build Worker Template", BuildTemplate());

        public static void BatchImportClips() => Batch(ImportClips);
        public static void BatchBuildTemplate() => Batch(BuildTemplate);

        static void Batch(Func<string> action)
        {
            try
            {
                Debug.Log("[WorkerTemplate] " + action());
                EditorApplication.Exit(0);
            }
            catch (Exception e)
            {
                Debug.LogError("[WorkerTemplate] FAILED: " + e);
                EditorApplication.Exit(1);
            }
        }

        static void Report(string title, string message)
        {
            Debug.Log("[WorkerTemplate] " + message);
            EditorUtility.DisplayDialog(title, message.Length > 1500 ? message.Substring(0, 1500) + " ..." : message, "OK");
        }

        public static WorkerV4Config LoadConfig()
        {
            var asset = AssetDatabase.LoadAssetAtPath<TextAsset>(ConfigPath) ?? throw new FileNotFoundException(ConfigPath);
            var cfg = WorkerV4Config.Parse(asset.text);
            var errors = cfg.Validate();
            if (errors.Count > 0) throw new InvalidOperationException(ConfigPath + ":\n  " + string.Join("\n  ", errors));
            return cfg;
        }

        static string ProjectDir => Path.GetDirectoryName(Application.dataPath);
        static string ProjectFile(string assetPath) => Path.Combine(ProjectDir, assetPath);
        static string RepoRoot(WorkerV4Config cfg) => Path.GetFullPath(Path.Combine(ProjectDir, cfg.paths.repo_root_relative_to_unity_project));

        /// <summary>Every .fbx the config needs: the idle (and turn) clip, then each Mixamo variant's source.</summary>
        public static List<string> ClipFiles(WorkerV4Config cfg)
        {
            var files = new List<string> { cfg.animation.idle_clip_file };
            if (!string.IsNullOrEmpty(cfg.animation.turn_clip_file)) files.Add(cfg.animation.turn_clip_file);
            foreach (var c in cfg.clips) if (c.IsMixamo && !files.Contains(c.source_file)) files.Add(c.source_file);
            return files;
        }

        // ---------------------------------------------------------------- import

        public static string ImportClips()
        {
            var cfg = LoadConfig();
            string source = Path.Combine(RepoRoot(cfg), cfg.paths.clip_source_folder);
            string dest = cfg.paths.clip_import_folder;
            Directory.CreateDirectory(ProjectFile(dest));
            var files = ClipFiles(cfg);
            var missing = files.Where(f => !File.Exists(Path.Combine(source, f))).ToList();
            if (missing.Count > 0)
                throw new FileNotFoundException($"not in {cfg.paths.clip_source_folder}: {string.Join(", ", missing)} (download them from Mixamo first: FBX for Unity, 30 fps)");

            var index = new ClipIndex();
            var entries = new List<ClipIndexEntry>();
            var log = new StringBuilder();
            foreach (var f in files)
            {
                string src = Path.Combine(source, f), dstAsset = dest + "/" + f, dst = ProjectFile(dstAsset);
                string sha = Sha256(File.ReadAllBytes(src));
                if (File.Exists(dst))
                {
                    if (Sha256(File.ReadAllBytes(dst)) != sha)
                        throw new IOException($"{dstAsset} exists and differs from {cfg.paths.clip_source_folder}/{f}; delete it first to import the new file");
                }
                else File.Copy(src, dst);
                AssetDatabase.ImportAsset(dstAsset, ImportAssetOptions.ForceSynchronousImport);
                bool idle = f == cfg.animation.idle_clip_file || f == cfg.animation.turn_clip_file;
                string stem = Path.GetFileNameWithoutExtension(f);
                ConfigureImporter(dstAsset, stem, idle);
                var clip = AssetDatabase.LoadAllAssetsAtPath(dstAsset).OfType<AnimationClip>().FirstOrDefault(c => !c.name.StartsWith("__preview__", StringComparison.Ordinal))
                           ?? throw new InvalidOperationException($"{dstAsset}: no animation clip after import");
                var e = Analyse(clip, idle);
                e.file = f;
                e.resource = stem;
                e.sha256 = sha;
                entries.Add(e);
                log.Append($"\n  {f}: clip '{clip.name}', {e.length_s.ToString("0.00", Inv)} s" +
                           (idle ? " (idle)" : $", raises the {e.arm} arm (amount {e.raise_amount.ToString("0.00", Inv)}), peak {e.peak_s.ToString("0.00", Inv)} s, release {e.release_s.ToString("0.00", Inv)} s"));
            }
            index.clips = entries.ToArray();
            string indexAsset = dest + "/" + cfg.paths.clip_index_name + ".json";
            File.WriteAllText(ProjectFile(indexAsset), JsonUtility.ToJson(index, true).Replace("\r\n", "\n") + "\n", new UTF8Encoding(false));
            AssetDatabase.ImportAsset(indexAsset, ImportAssetOptions.ForceSynchronousImport);
            return $"{entries.Count} clips imported into {dest} (git-ignored); index {indexAsset}:{log}";
        }

        static void ConfigureImporter(string assetPath, string clipName, bool loop)
        {
            var imp = (ModelImporter)AssetImporter.GetAtPath(assetPath);
            imp.animationType = ModelImporterAnimationType.Human;
            imp.avatarSetup = ModelImporterAvatarSetup.CreateFromThisModel;
            imp.materialImportMode = ModelImporterMaterialImportMode.None;
            imp.importAnimation = true;
            imp.SaveAndReimport();
            var defaults = imp.defaultClipAnimations;
            if (defaults == null || defaults.Length == 0) throw new InvalidOperationException($"{assetPath}: the file has no animation take");
            var c = defaults[0];
            c.name = clipName;
            c.loopTime = loop;
            c.lockRootRotation = true;              // bake root rotation, height and position into the pose:
            c.keepOriginalOrientation = true;       // the worker's root (and the scenario) decides where the body stands
            c.lockRootHeightY = true;
            c.keepOriginalPositionY = false;
            c.heightFromFeet = true;
            c.lockRootPositionXZ = true;
            c.keepOriginalPositionXZ = true;
            imp.clipAnimations = new[] { c };
            imp.SaveAndReimport();
        }

        /// <summary>
        /// The arm a clip raises and when, from its Humanoid muscle curves "Arm Down-Up" and "Arm Front-Back": the raise
        /// is the distance of the two muscles from their first-frame values. peak_s: first time the raise reaches 90 per
        /// cent of its largest value; release_s: the last time it is still there.
        /// </summary>
        public static ClipIndexEntry Analyse(AnimationClip clip, bool idle)
        {
            var e = new ClipIndexEntry { clip_name = clip.name, length_s = clip.length, arm = "" };
            if (idle) return e;
            var bindings = AnimationUtility.GetCurveBindings(clip);
            AnimationCurve Curve(string muscle)
            {
                foreach (var b in bindings) if (b.propertyName == muscle) return AnimationUtility.GetEditorCurve(clip, b);
                return null;
            }
            float best = -1f;
            foreach (var side in new[] { "Left", "Right" })
            {
                var du = Curve(side + " Arm Down-Up");
                var fb = Curve(side + " Arm Front-Back");
                if (du == null || fb == null) continue;
                var samples = Raise(du, fb, clip.length, out float max);
                if (max <= best) continue;
                best = max;
                e.arm = side.ToLowerInvariant();
                e.raise_amount = max;
                float dt = clip.length / (samples.Length - 1);
                int first = Array.FindIndex(samples, x => x >= 0.9f * max), last = Array.FindLastIndex(samples, x => x >= 0.9f * max);
                e.peak_s = first * dt;
                e.release_s = last * dt;
            }
            if (best < 0f) throw new InvalidOperationException($"clip '{clip.name}' has no Humanoid arm muscle curves (import it as Humanoid)");
            return e;
        }

        static float[] Raise(AnimationCurve du, AnimationCurve fb, float length, out float max)
        {
            int n = Mathf.Max(2, Mathf.CeilToInt(length * 120f) + 1);
            var r = new float[n];
            float du0 = du.Evaluate(0f), fb0 = fb.Evaluate(0f);
            max = 0f;
            for (int i = 0; i < n; i++)
            {
                float t = length * i / (n - 1);
                float a = du.Evaluate(t) - du0, b = fb.Evaluate(t) - fb0;
                r[i] = Mathf.Sqrt(a * a + b * b);
                max = Mathf.Max(max, r[i]);
            }
            return r;
        }

        // ---------------------------------------------------------------- template

        public static string BuildTemplate()
        {
            var cfg = LoadConfig();
            string controllerPath = cfg.animation.controller;
            foreach (var p in new[] { MaskPath, controllerPath, PrefabPath })
                if (File.Exists(ProjectFile(p))) throw new InvalidOperationException(p + " exists; delete the template assets first to rebuild them");
            EnsureFolder(AnimationFolder);
            EnsureFolder(PrefabFolder);

            var mask = new AvatarMask { name = "WorkerV4_Arms" };
            for (var part = AvatarMaskBodyPart.Root; part < AvatarMaskBodyPart.LastBodyPart; part++)
                mask.SetHumanoidBodyPartActive(part, Array.IndexOf(MaskParts, part) >= 0);
            AssetDatabase.CreateAsset(mask, MaskPath);

            var ctl = AnimatorController.CreateAnimatorControllerAtPath(controllerPath);
            ctl.AddParameter(WorkerV4.ParamTurning, AnimatorControllerParameterType.Bool);
            ctl.AddParameter(WorkerV4.ParamMirror, AnimatorControllerParameterType.Bool);
            ctl.AddParameter(new AnimatorControllerParameter { name = WorkerV4.ParamGestureSpeed, type = AnimatorControllerParameterType.Float, defaultFloat = 1f });

            AnimationClip Placeholder(string role)
            {
                var clip = new AnimationClip { name = WorkerV4.PlaceholderName(role) };
                AssetDatabase.AddObjectToAsset(clip, ctl);
                return clip;
            }

            var layers = ctl.layers;
            layers[0].name = BaseLayerName;
            layers[0].iKPass = true;
            ctl.layers = layers;
            var baseSm = ctl.layers[0].stateMachine;
            var idle = baseSm.AddState("Idle");
            idle.motion = Placeholder("idle");
            var turn = baseSm.AddState("Turn");
            turn.motion = Placeholder("turn");
            baseSm.defaultState = idle;
            var toTurn = idle.AddTransition(turn);
            toTurn.AddCondition(AnimatorConditionMode.If, 0f, WorkerV4.ParamTurning);
            toTurn.hasExitTime = false;
            toTurn.duration = 0.2f;
            var toIdle = turn.AddTransition(idle);
            toIdle.AddCondition(AnimatorConditionMode.IfNot, 0f, WorkerV4.ParamTurning);
            toIdle.hasExitTime = false;
            toIdle.duration = 0.25f;

            var gestureSm = new AnimatorStateMachine { name = GestureLayerName, hideFlags = HideFlags.HideInHierarchy };
            AssetDatabase.AddObjectToAsset(gestureSm, ctl);
            ctl.AddLayer(new AnimatorControllerLayer
            {
                name = GestureLayerName, defaultWeight = 0f, avatarMask = mask, blendingMode = AnimatorLayerBlendingMode.Override,
                iKPass = true, stateMachine = gestureSm,
            });
            gestureSm.defaultState = gestureSm.AddState("Rest");
            var states = new List<string>();
            foreach (var c in cfg.clips)
            {
                if (!c.IsMixamo) continue;
                var s = gestureSm.AddState(WorkerV4.GestureStatePrefix + c.name);
                s.motion = Placeholder(c.name);
                s.speedParameterActive = true;
                s.speedParameter = WorkerV4.ParamGestureSpeed;
                s.mirrorParameterActive = true;
                s.mirrorParameter = WorkerV4.ParamMirror;
                states.Add(s.name);
            }
            EditorUtility.SetDirty(ctl);

            var go = new GameObject("WorkerV4");
            try
            {
                var w = go.AddComponent<WorkerV4>();
                w.config = AssetDatabase.LoadAssetAtPath<TextAsset>(ConfigPath);
                w.controller = ctl;
                w.lookId = cfg.looks[0].id;
                var sources = new List<LookSource>();
                var notInstalled = new List<string>();
                foreach (var asset in cfg.looks.Select(l => l.asset).Distinct())
                {
                    var prefab = AssetDatabase.LoadAssetAtPath<GameObject>(asset);
                    if (prefab == null) notInstalled.Add(asset);
                    sources.Add(new LookSource { asset = asset, prefab = prefab });
                }
                w.lookSources = sources.ToArray();
                var capsule = go.AddComponent<CapsuleCollider>();        // as the v3 workers (HriScenarioBuilder)
                capsule.radius = 0.3f;
                capsule.height = 1.8f;
                capsule.center = new Vector3(0f, 0.9f, 0f);
                go.AddComponent<NavMeshModifier>().ignoreFromBuild = true;
                PrefabUtility.SaveAsPrefabAsset(go, PrefabPath);
                AssetDatabase.SaveAssets();
                return $"Built {MaskPath}, {controllerPath} (gesture states: {string.Join(", ", states)}) and {PrefabPath}." +
                       (notInstalled.Count > 0 ? $" Not installed (the look's prefab reference stays empty): {string.Join(", ", notInstalled)}." : "");
            }
            finally
            {
                Object.DestroyImmediate(go);
            }
        }

        static void EnsureFolder(string assetFolder)
        {
            if (AssetDatabase.IsValidFolder(assetFolder)) return;
            string parent = Path.GetDirectoryName(assetFolder).Replace('\\', '/');
            EnsureFolder(parent);
            AssetDatabase.CreateFolder(parent, Path.GetFileName(assetFolder));
        }

        static string Sha256(byte[] bytes)
        {
            using (var sha = SHA256.Create()) return string.Concat(sha.ComputeHash(bytes).Select(b => b.ToString("x2", Inv)));
        }
    }
}
