using UnityEditor;
using UnityEditor.SceneManagement;
using UnityEngine;
using WarehouseRobot.Scenario;

namespace WarehouseRobot.ScenarioEditor
{
    /// <summary>
    /// Gesture PNGs from the pan-tilt camera (GesturePngCapture): "Tools > Warehouse HRI > Save Gesture PNGs (Play mode)"
    /// in a running Play session, or headless:
    ///   Unity -batchmode -projectPath P -executeMethod WarehouseRobot.ScenarioEditor.GesturePngBatch.Run -logFile png.log
    /// (opens the scene, turns the trial runner's autostart off for this Play session only, the scene is not saved).
    /// </summary>
    [InitializeOnLoad]
    public static class GesturePngBatch
    {
        const string ActiveKey = "WarehouseRobot.GesturePngBatch.Active";
        const string DeadlineKey = "WarehouseRobot.GesturePngBatch.Deadline";

        static GesturePngBatch()
        {
            if (SessionState.GetBool(ActiveKey, false)) EditorApplication.update += Poll;
        }

        [MenuItem("Tools/Warehouse HRI/Save Gesture PNGs (Play mode)")]
        public static void Menu()
        {
            if (!EditorApplication.isPlaying)
            {
                EditorUtility.DisplayDialog("Warehouse HRI", "Press Play first (no Python bridge needed), then run Save Gesture PNGs.", "OK");
                return;
            }

            var go = new GameObject("GesturePngCapture");
            go.AddComponent<GesturePngCapture>();
            Debug.Log("[GesturePngCapture] capturing LEFT, FORWARD, RIGHT, STOP (about 5 s); the trial runner is stopped for this Play session.");
        }

        public static void Run()
        {
            EditorSceneManager.OpenScene("Assets/Scenes/WarehouseRobot.unity");
            foreach (var r in Object.FindObjectsByType<TrialRunner>(FindObjectsInactive.Include, FindObjectsSortMode.None)) r.runOnStart = false;
            SessionState.SetBool(ActiveKey, true);
            SessionState.SetFloat(DeadlineKey, (float)EditorApplication.timeSinceStartup + 300f);
            EditorApplication.update += Poll;
            EditorApplication.EnterPlaymode();
        }

        static void Poll()
        {
            if (!SessionState.GetBool(ActiveKey, false)) return;
            if (EditorApplication.timeSinceStartup > SessionState.GetFloat(DeadlineKey, float.MaxValue)) { Finish(1, "timeout"); return; }
            if (!EditorApplication.isPlaying) return;
            var c = Object.FindFirstObjectByType<GesturePngCapture>();
            if (c == null) { new GameObject("GesturePngCapture").AddComponent<GesturePngCapture>(); return; }
            if (c.Done) Finish(c.Error == null ? 0 : 1, c.Error ?? c.Folder);
        }

        static void Finish(int code, string status)
        {
            SessionState.SetBool(ActiveKey, false);
            EditorApplication.update -= Poll;
            Debug.Log($"[GesturePngBatch] finished ({code}): {status}");
            EditorApplication.Exit(code);
        }
    }
}
