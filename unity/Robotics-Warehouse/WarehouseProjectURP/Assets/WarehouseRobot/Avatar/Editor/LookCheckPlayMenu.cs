using System;
using System.IO;
using UnityEditor;
using UnityEditor.SceneManagement;
using UnityEngine;
using WarehouseRobot.AvatarCheck;
using Object = UnityEngine.Object;

namespace WarehouseAvatar.EditorTools
{
    /// <summary>
    /// Tools > Warehouse v4 > Look Check > Build LookCheckPlay Scene / Run Play-Mode Look Check (v4 Phase 2B): the look
    /// check recorded in Play mode with the worker template (LookCheckPlayDriver). The run enters Play mode, waits until the
    /// driver is done and leaves Play mode (menu) or quits (command line, exit 0 = done, 1 = failed or timeout). Run it
    /// WITHOUT -batchmode (the capture waits for the end of rendered frames):
    ///   Unity -projectPath P -executeMethod WarehouseAvatar.EditorTools.LookCheckPlayMenu.CommandLineRun -lookCheckTimeout 3600 -logFile play.log
    /// </summary>
    [InitializeOnLoad]
    public static class LookCheckPlayMenu
    {
        public const string ScenePath = "Assets/WarehouseRobot/Avatar/LookCheckPlay.unity";
        const string PlayConfigPath = "Assets/WarehouseRobot/Avatar/Config/look_check_play.json";
        const string ActiveKey = "WarehouseAvatar.LookCheckPlay.Active";
        const string QuitKey = "WarehouseAvatar.LookCheckPlay.Quit";
        const string DeadlineKey = "WarehouseAvatar.LookCheckPlay.Deadline";

        static LookCheckPlayMenu()
        {
            if (SessionState.GetBool(ActiveKey, false)) EditorApplication.update += Poll;
        }

        [MenuItem("Tools/Warehouse v4/Look Check/Build LookCheckPlay Scene")]
        public static void BuildMenu()
        {
            string msg = BuildScene();
            Debug.Log("[LookCheckPlay] " + msg);
            EditorUtility.DisplayDialog("Build LookCheckPlay Scene", msg, "OK");
        }

        [MenuItem("Tools/Warehouse v4/Look Check/Run Play-Mode Look Check")]
        public static void RunMenu()
        {
            if (!EditorSceneManager.SaveCurrentModifiedScenesIfUserWantsTo()) return;
            Start(false, 3600f);
        }

        public static void BatchBuildScene()
        {
            try { Debug.Log("[LookCheckPlay] " + BuildScene()); EditorApplication.Exit(0); }
            catch (Exception e) { Debug.LogError("[LookCheckPlay] FAILED: " + e); EditorApplication.Exit(1); }
        }

        public static void CommandLineRun()
        {
            float timeout = 3600f;
            var args = Environment.GetCommandLineArgs();
            for (int i = 0; i < args.Length - 1; i++)
                if (args[i] == "-lookCheckTimeout") float.TryParse(args[i + 1], System.Globalization.NumberStyles.Float, System.Globalization.CultureInfo.InvariantCulture, out timeout);
            Start(true, timeout);
        }

        public static string BuildScene()
        {
            if (File.Exists(Path.Combine(Path.GetDirectoryName(Application.dataPath), ScenePath))) throw new InvalidOperationException(ScenePath + " exists; delete it first to rebuild it");
            var prefab = AssetDatabase.LoadAssetAtPath<GameObject>(WorkerTemplateMenu.PrefabPath)
                         ?? throw new FileNotFoundException(WorkerTemplateMenu.PrefabPath + " missing: run Tools > Warehouse v4 > Workers > Build Worker Template first");
            var scene = EditorSceneManager.NewScene(NewSceneSetup.EmptyScene, NewSceneMode.Single);
            var go = new GameObject("LookCheckPlay");
            var d = go.AddComponent<LookCheckPlayDriver>();
            d.playConfig = Load(PlayConfigPath);
            d.lookCheckConfig = Load(LookCheckMenu.ConfigPath);
            d.robotConfig = Load("Assets/WarehouseRobot/Robot/Config/robot_unity_v4.json");
            d.workerPrefab = prefab.GetComponent<WorkerV4>();
            var lightGo = new GameObject("KeyLight");
            lightGo.transform.SetParent(go.transform, false);
            d.keyLight = lightGo.AddComponent<Light>();
            d.keyLight.type = LightType.Directional;
            if (!EditorSceneManager.SaveScene(scene, ScenePath)) throw new IOException("could not save " + ScenePath);
            return "Saved " + ScenePath + ". Run it with Tools > Warehouse v4 > Look Check > Run Play-Mode Look Check.";
        }

        static TextAsset Load(string path) => AssetDatabase.LoadAssetAtPath<TextAsset>(path) ?? throw new FileNotFoundException(path);

        static void Start(bool quit, float timeout)
        {
            if (!File.Exists(Path.Combine(Path.GetDirectoryName(Application.dataPath), ScenePath)))
            {
                Debug.LogError("[LookCheckPlay] " + ScenePath + " missing: Build LookCheckPlay Scene first");
                if (quit) EditorApplication.Exit(1);
                return;
            }
            EditorSceneManager.OpenScene(ScenePath, OpenSceneMode.Single);
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
            var d = Object.FindFirstObjectByType<LookCheckPlayDriver>();
            if (d == null) return;
            if (d.Status.StartsWith("done")) Finish(0, d.Status + " (" + d.OutputFolder + ")");
            else if (d.Status.StartsWith("failed")) Finish(1, d.Status);
        }

        static void Finish(int code, string status)
        {
            SessionState.SetBool(ActiveKey, false);
            EditorApplication.update -= Poll;
            Debug.Log($"[LookCheckPlay] finished ({code}): {status}");
            if (SessionState.GetBool(QuitKey, false)) EditorApplication.Exit(code);
            else EditorApplication.ExitPlaymode();
        }
    }
}
