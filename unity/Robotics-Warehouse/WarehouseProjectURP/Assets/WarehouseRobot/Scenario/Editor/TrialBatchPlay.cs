using UnityEditor;
using UnityEditor.SceneManagement;
using UnityEngine;
using WarehouseRobot.Scenario;

namespace WarehouseRobot.ScenarioEditor
{
    /// <summary>
    /// Batch-mode runner for the trials: open the scene, press Play, wait until the TrialRunner is done, quit (exit 0;
    /// 1 on error or timeout). The Python bridge must already run (python -m bridge.server --mode guide --perception vision).
    ///   Unity -batchmode -projectPath P -executeMethod WarehouseRobot.ScenarioEditor.TrialBatchPlay.Run -trialTimeout 3600 -logFile run.log
    /// </summary>
    [InitializeOnLoad]
    public static class TrialBatchPlay
    {
        const string ActiveKey = "WarehouseRobot.TrialBatchPlay.Active";
        const string DeadlineKey = "WarehouseRobot.TrialBatchPlay.Deadline";

        static TrialBatchPlay()
        {
            if (SessionState.GetBool(ActiveKey, false)) EditorApplication.update += Poll;
        }

        public static void Run()
        {
            float timeout = 3600f;
            var args = System.Environment.GetCommandLineArgs();
            for (int i = 0; i < args.Length - 1; i++)
                if (args[i] == "-trialTimeout") float.TryParse(args[i + 1], System.Globalization.NumberStyles.Float,
                    System.Globalization.CultureInfo.InvariantCulture, out timeout);
            EditorSceneManager.OpenScene("Assets/Scenes/WarehouseRobot.unity");
            SessionState.SetBool(ActiveKey, true);
            SessionState.SetFloat(DeadlineKey, (float)EditorApplication.timeSinceStartup + timeout);
            EditorApplication.update += Poll;
            EditorApplication.EnterPlaymode();
        }

        static void Poll()
        {
            if (!SessionState.GetBool(ActiveKey, false)) return;
            if (EditorApplication.timeSinceStartup > SessionState.GetFloat(DeadlineKey, float.MaxValue)) { Finish(1, "timeout"); return; }
            if (!EditorApplication.isPlaying) return;
            var r = Object.FindFirstObjectByType<TrialRunner>();
            if (r == null) return;
            if (r.Status.StartsWith("done")) Finish(0, r.Status);
            else if (r.Status.StartsWith("not started")) Finish(1, r.Status);
        }

        static void Finish(int code, string status)
        {
            SessionState.SetBool(ActiveKey, false);
            EditorApplication.update -= Poll;
            Debug.Log($"[TrialBatchPlay] finished ({code}): {status}");
            EditorApplication.Exit(code);
        }
    }
}
