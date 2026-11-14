using System;
using System.Collections.Generic;
using UnityEditor;
using UnityEditor.SceneManagement;
using UnityEngine;
using WarehouseRobot.AvatarCheck;
using Object = UnityEngine.Object;

namespace WarehouseAvatar.EditorTools
{
    /// <summary>
    /// Tools > Warehouse v4 > Experiments > Run Gesture Geometry Check (experiments_ab.md section 10, gesture_geometry.json): opens a NEW
    /// unsaved scene (nothing on disk changes), adds GestureGeometryDriver with the worker template, looks_ab.json and the prefab of every look
    /// it names, enters Play mode, waits for the driver and leaves Play mode (menu) or quits (command line: exit 0 = done, 1 = failed or
    /// timeout). The driver captures in LateUpdate (no WaitForEndOfFrame), so it also runs with -batchmode:
    ///   Unity -batchmode -projectPath P -executeMethod WarehouseAvatar.EditorTools.GestureGeometryMenu.CommandLineRun
    ///         [-geometryLabel baseline] [-geometryLooks a,b] [-geometryTimeout 3600] -logFile geometry.log
    /// </summary>
    [InitializeOnLoad]
    public static class GestureGeometryMenu
    {
        public const string ConfigPath = "Assets/WarehouseRobot/Avatar/Config/gesture_geometry.json";
        const string ActiveKey = "WarehouseAvatar.GestureGeometry.Active";
        const string QuitKey = "WarehouseAvatar.GestureGeometry.Quit";
        const string DeadlineKey = "WarehouseAvatar.GestureGeometry.Deadline";
        const string AsyncShadersKey = "WarehouseAvatar.GestureGeometry.AsyncShaders";

        static GestureGeometryMenu()
        {
            if (!SessionState.GetBool(ActiveKey, false)) return;
            EditorApplication.update += Poll;
        }

        [MenuItem("Tools/Warehouse v4/Experiments/Run Gesture Geometry Check")]
        public static void RunMenu()
        {
            if (!EditorSceneManager.SaveCurrentModifiedScenesIfUserWantsTo()) return;
            Start(false, 3600f);
        }

        public static void CommandLineRun()
        {
            float timeout = 3600f;
            var args = Environment.GetCommandLineArgs();
            for (int i = 0; i < args.Length - 1; i++)
                if (args[i] == "-geometryTimeout") float.TryParse(args[i + 1], System.Globalization.NumberStyles.Float, System.Globalization.CultureInfo.InvariantCulture, out timeout);
            Start(true, timeout);
        }

        static void Start(bool quit, float timeout)
        {
            var cfg = AssetDatabase.LoadAssetAtPath<TextAsset>(ConfigPath);
            var looks = AssetDatabase.LoadAssetAtPath<TextAsset>(ExperimentLooks.AssetPath);
            var prefab = AssetDatabase.LoadAssetAtPath<GameObject>(WorkerTemplateMenu.PrefabPath);
            if (cfg == null || looks == null || prefab == null || prefab.GetComponent<WorkerV4>() == null)
            {
                Debug.LogError($"[GestureGeometry] missing {ConfigPath}, {ExperimentLooks.AssetPath} or the worker template {WorkerTemplateMenu.PrefabPath}");
                if (quit) EditorApplication.Exit(1);
                return;
            }
            EditorSceneManager.NewScene(NewSceneSetup.EmptyScene, NewSceneMode.Single);
            var go = new GameObject("GestureGeometry");
            var d = go.AddComponent<GestureGeometryDriver>();
            d.geometryConfig = cfg;
            d.extraLooksConfig = looks;
            d.workerPrefab = prefab.GetComponent<WorkerV4>();
            var sources = new List<LookSource>();
            foreach (var l in ExperimentLooks.Parse(looks.text).looks)
            {
                if (l == null || l.kind != LookEntry.KindPrefab || sources.Exists(s => s.asset == l.asset)) continue;
                var p = AssetDatabase.LoadAssetAtPath<GameObject>(l.asset);
                if (p == null) { Debug.LogWarning($"[GestureGeometry] look {l.id}: {l.asset} is not installed"); continue; }
                var mat = string.IsNullOrEmpty(l.material_override) ? null : AssetDatabase.LoadAssetAtPath<Material>(l.material_override);
                sources.Add(new LookSource { asset = l.asset, prefab = p, materialOverride = mat });
            }
            d.extraSources = sources.ToArray();
            // the Editor draws a shader variant still compiling as flat cyan (experiments_ab.md section 5): compile synchronously
            SessionState.SetBool(AsyncShadersKey, ShaderUtil.allowAsyncCompilation);
            ShaderUtil.allowAsyncCompilation = false;
            SessionState.SetBool(ActiveKey, true);
            SessionState.SetBool(QuitKey, quit);
            SessionState.SetFloat(DeadlineKey, (float)EditorApplication.timeSinceStartup + timeout);
            EditorApplication.update -= Poll;
            EditorApplication.update += Poll;
            EditorApplication.EnterPlaymode();
        }

        static void Poll()
        {
            if (!SessionState.GetBool(ActiveKey, false)) return;
            if (EditorApplication.timeSinceStartup > SessionState.GetFloat(DeadlineKey, float.MaxValue)) { Finish(1, "timeout"); return; }
            if (!EditorApplication.isPlaying) return;
            var d = Object.FindFirstObjectByType<GestureGeometryDriver>();
            if (d == null) return;
            if (d.Status.StartsWith("done", StringComparison.Ordinal)) Finish(0, d.Status + " (" + d.OutputFolder + ")");
            else if (d.Status.StartsWith("failed", StringComparison.Ordinal)) Finish(1, d.Status);
        }

        static void Finish(int code, string status)
        {
            SessionState.SetBool(ActiveKey, false);
            EditorApplication.update -= Poll;
            ShaderUtil.allowAsyncCompilation = SessionState.GetBool(AsyncShadersKey, true);
            Debug.Log($"[GestureGeometry] finished ({code}): {status}");
            if (SessionState.GetBool(QuitKey, false)) EditorApplication.Exit(code);
            else EditorApplication.ExitPlaymode();
        }
    }
}
