using System;
using UnityEditor;
using UnityEditor.SceneManagement;
using UnityEngine;
using UnityEngine.SceneManagement;
using WarehouseRobot.AvatarCheck;
using Object = UnityEngine.Object;

namespace WarehouseAvatar.EditorTools
{
    /// <summary>
    /// Tools > Warehouse v4 > Look Check > Run Play-Mode Look Check (v4 Phase 2B; since Phase 2D, 2026-11-08, in the study
    /// scene, look_check_changes.md): opens the venue scene of look_check_play.json (WarehouseRobot_v4.unity), enters Play
    /// mode and adds LookCheckPlayDriver when the scene has loaded (after Awake, before any Start; the scene file is never
    /// changed), waits until the driver is done and leaves Play mode (menu) or quits (command line, exit 0 = done,
    /// 1 = failed or timeout). Run it WITHOUT -batchmode (the capture waits for the end of rendered frames):
    ///   Unity -projectPath P -executeMethod WarehouseAvatar.EditorTools.LookCheckPlayMenu.CommandLineRun -lookCheckTimeout 3600 -logFile play.log
    /// </summary>
    [InitializeOnLoad]
    public static class LookCheckPlayMenu
    {
        const string PlayConfigPath = "Assets/WarehouseRobot/Avatar/Config/look_check_play.json";
        /// <summary>Experiments A/B (2026-11-14, experiments_ab.md section 2): the same check on every look of the avatar experiment.</summary>
        const string PlayConfigPathAB = "Assets/WarehouseRobot/Avatar/Config/look_check_play_ab.json";
        const string ConfigKey = "WarehouseAvatar.LookCheckPlay.Config";
        const string RobotConfigPath = "Assets/WarehouseRobot/Robot/Config/robot_unity_v4.json";
        const string ActiveKey = "WarehouseAvatar.LookCheckPlay.Active";
        const string InjectedKey = "WarehouseAvatar.LookCheckPlay.Injected";
        const string QuitKey = "WarehouseAvatar.LookCheckPlay.Quit";
        const string DeadlineKey = "WarehouseAvatar.LookCheckPlay.Deadline";
        const string AsyncShadersKey = "WarehouseAvatar.LookCheckPlay.AsyncShaders";

        [Serializable] class VenueOnly { public LookCheckPlayDriver.PlayVenue venue; }

        static LookCheckPlayMenu()
        {
            if (!SessionState.GetBool(ActiveKey, false)) return;
            EditorApplication.update += Poll;
            SceneManager.sceneLoaded += OnSceneLoaded;
        }

        [MenuItem("Tools/Warehouse v4/Look Check/Run Play-Mode Look Check")]
        public static void RunMenu()
        {
            if (!EditorSceneManager.SaveCurrentModifiedScenesIfUserWantsTo()) return;
            Start(false, 3600f, PlayConfigPath);
        }

        [MenuItem("Tools/Warehouse v4/Experiments/Run Play-Mode Look Check (avatar experiment looks)")]
        public static void RunMenuAB()
        {
            if (!EditorSceneManager.SaveCurrentModifiedScenesIfUserWantsTo()) return;
            Start(false, 3600f * 3f, PlayConfigPathAB);
        }

        public static void CommandLineRun()
        {
            float timeout = 3600f;
            var args = Environment.GetCommandLineArgs();
            for (int i = 0; i < args.Length - 1; i++)
                if (args[i] == "-lookCheckTimeout") float.TryParse(args[i + 1], System.Globalization.NumberStyles.Float, System.Globalization.CultureInfo.InvariantCulture, out timeout);
            Start(true, timeout, PlayConfigPath);
        }

        /// <summary>Command line, experiments A/B: -executeMethod WarehouseAvatar.EditorTools.LookCheckPlayMenu.CommandLineRunAB -lookCheckTimeout S.</summary>
        public static void CommandLineRunAB()
        {
            float timeout = 3600f * 3f;
            var args = Environment.GetCommandLineArgs();
            for (int i = 0; i < args.Length - 1; i++)
                if (args[i] == "-lookCheckTimeout") float.TryParse(args[i + 1], System.Globalization.NumberStyles.Float, System.Globalization.CultureInfo.InvariantCulture, out timeout);
            Start(true, timeout, PlayConfigPathAB);
        }

        static string ActiveConfig() => SessionState.GetString(ConfigKey, PlayConfigPath);

        static TextAsset Load(string path) => AssetDatabase.LoadAssetAtPath<TextAsset>(path);

        static string VenueScene()
        {
            var cfg = Load(ActiveConfig());
            return cfg != null ? JsonUtility.FromJson<VenueOnly>(cfg.text)?.venue?.scene : null;
        }

        static void Start(bool quit, float timeout, string playConfig)
        {
            SessionState.SetString(ConfigKey, playConfig);
            string scene = VenueScene();
            if (string.IsNullOrEmpty(scene) || AssetDatabase.LoadAssetAtPath<SceneAsset>(scene) == null)
            {
                Debug.LogError($"[LookCheckPlay] venue scene '{scene}' of {ActiveConfig()} not found");
                if (quit) EditorApplication.Exit(1);
                return;
            }
            EditorSceneManager.OpenScene(scene, OpenSceneMode.Single);
            SessionState.SetBool(ActiveKey, true);
            SessionState.SetBool(InjectedKey, false);
            SessionState.SetBool(QuitKey, quit);
            SessionState.SetFloat(DeadlineKey, (float)EditorApplication.timeSinceStartup + timeout);
            EditorApplication.update -= Poll;
            EditorApplication.update += Poll;
            SceneManager.sceneLoaded -= OnSceneLoaded;
            SceneManager.sceneLoaded += OnSceneLoaded;   // without a domain reload the static constructor does not run again
            EditorApplication.EnterPlaymode();
        }

        /// <summary>Play mode: add the driver once the venue scene has loaded (its Awake switches off the study's runtime parts).</summary>
        static void OnSceneLoaded(Scene scene, LoadSceneMode mode)
        {
            if (!Application.isPlaying || !SessionState.GetBool(ActiveKey, false) || SessionState.GetBool(InjectedKey, false)) return;
            if (scene.path != VenueScene()) return;
            SessionState.SetBool(InjectedKey, true);
            // The Editor draws a shader variant that is still compiling as flat cyan (0, 255, 255); the scene's lights
            // need variants the Editor had not compiled yet, so the first takes of the Phase 2D smoke run showed a cyan
            // person. Compile synchronously while the check runs (an Editor session setting, restored in Finish).
            SessionState.SetBool(AsyncShadersKey, ShaderUtil.allowAsyncCompilation);
            ShaderUtil.allowAsyncCompilation = false;
            var prefab = AssetDatabase.LoadAssetAtPath<GameObject>(WorkerTemplateMenu.PrefabPath);
            var go = new GameObject("LookCheckPlay");
            SceneManager.MoveGameObjectToScene(go, scene);
            var d = go.AddComponent<LookCheckPlayDriver>();
            d.playConfig = Load(ActiveConfig());
            if (ActiveConfig() == PlayConfigPathAB) AddExperimentLooks(d);
            d.lookCheckConfig = Load(LookCheckMenu.ConfigPath);
            d.robotConfig = Load(RobotConfigPath);
            d.workerPrefab = prefab != null ? prefab.GetComponent<WorkerV4>() : null;
            Debug.Log("[LookCheckPlay] driver added to " + scene.path + "; in Play mode: " + d.SceneChanges);
        }

        /// <summary>looks_ab.json and the prefab (and material override) of each of its looks, resolved here because the driver has no AssetDatabase.</summary>
        static void AddExperimentLooks(LookCheckPlayDriver d)
        {
            d.extraLooksConfig = Load(ExperimentLooks.AssetPath);
            if (d.extraLooksConfig == null) return;
            var sources = new System.Collections.Generic.List<LookSource>();
            foreach (var l in ExperimentLooks.Parse(d.extraLooksConfig.text).looks)
            {
                if (l == null || l.kind != LookEntry.KindPrefab || sources.Exists(s => s.asset == l.asset)) continue;
                var prefab = AssetDatabase.LoadAssetAtPath<GameObject>(l.asset);
                if (prefab == null) { Debug.LogWarning($"[LookCheckPlay] look {l.id}: {l.asset} is not installed"); continue; }
                var mat = string.IsNullOrEmpty(l.material_override) ? null : AssetDatabase.LoadAssetAtPath<Material>(l.material_override);
                sources.Add(new LookSource { asset = l.asset, prefab = prefab, materialOverride = mat });
            }
            d.extraSources = sources.ToArray();
        }

        static void Poll()
        {
            if (!SessionState.GetBool(ActiveKey, false)) return;
            if (EditorApplication.timeSinceStartup > SessionState.GetFloat(DeadlineKey, float.MaxValue)) { Finish(1, "timeout"); return; }
            if (!EditorApplication.isPlaying) return;
            var d = Object.FindFirstObjectByType<LookCheckPlayDriver>();
            if (d == null) return;
            if (d.Status.StartsWith("done")) Finish(0, d.Status + " (" + d.OutputFolder + ")");
            else if (d.Status.StartsWith("failed")) Finish(1, d.Status);
        }

        static void Finish(int code, string status)
        {
            SessionState.SetBool(ActiveKey, false);
            EditorApplication.update -= Poll;
            SceneManager.sceneLoaded -= OnSceneLoaded;
            ShaderUtil.allowAsyncCompilation = SessionState.GetBool(AsyncShadersKey, true);
            Debug.Log($"[LookCheckPlay] finished ({code}): {status}");
            if (SessionState.GetBool(QuitKey, false)) EditorApplication.Exit(code);
            else EditorApplication.ExitPlaymode();
        }
    }
}
