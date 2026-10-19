using UnityEditor;
using UnityEditor.SceneManagement;
using UnityEngine;

namespace WarehouseHRI.EditorTools
{
    /// <summary>
    /// Batch-mode runner: open the scene, press Play, wait until the configured session (trials or GestureSweep)
    /// is done, then quit with exit code 0 (1 on error or timeout). Example (macOS; Windows uses Unity.exe):
    ///   Unity -batchmode -projectPath &lt;project&gt; -executeMethod WarehouseHRI.EditorTools.HriBatchPlay.Run -hriTimeout 1800 -logFile run.log
    /// The Python bridge must already be running when perception.mode is vision.
    /// </summary>
    [InitializeOnLoad]
    public static class HriBatchPlay
    {
        const string ActiveKey = "WarehouseHRI.BatchPlay.Active";
        const string DeadlineKey = "WarehouseHRI.BatchPlay.Deadline";

        static HriBatchPlay()
        {
            // Entering Play mode reloads scripts; this re-attaches the watcher afterwards.
            if (SessionState.GetBool(ActiveKey, false)) EditorApplication.update += Poll;
        }

        public static void Run()
        {
            float timeout = 1800f;
            var args = System.Environment.GetCommandLineArgs();
            for (int i = 0; i < args.Length - 1; i++)
                if (args[i] == "-hriTimeout" && float.TryParse(args[i + 1], System.Globalization.NumberStyles.Float,
                        System.Globalization.CultureInfo.InvariantCulture, out var t)) timeout = t;
            EditorSceneManager.OpenScene(GuidedSceneBuilder.ScenePath);
            SessionState.SetBool(ActiveKey, true);
            SessionState.SetFloat(DeadlineKey, (float)EditorApplication.timeSinceStartup + timeout);
            EditorApplication.update += Poll;
            EditorApplication.EnterPlaymode();
        }

        static void Poll()
        {
            if (!SessionState.GetBool(ActiveKey, false)) return;
            if (EditorApplication.timeSinceStartup > SessionState.GetFloat(DeadlineKey, float.MaxValue))
            {
                Finish(1, "timeout");
                return;
            }

            if (!EditorApplication.isPlaying) return;
            var sweep = Object.FindObjectOfType<GestureSweep>();
            if (sweep != null && sweep.Active)
            {
                if (sweep.Status.StartsWith("GestureSweep done")) Finish(0, sweep.Status);
                else if (sweep.Status.StartsWith("GestureSweep refused")) Finish(1, sweep.Status);
                return;
            }

            var tm = TrialManager.Active;
            if (tm == null) return;
            if (tm.Status.StartsWith("done")) Finish(0, tm.Status);
            else if (tm.Status.StartsWith("not started")) Finish(1, tm.Status);
        }

        static void Finish(int code, string status)
        {
            SessionState.SetBool(ActiveKey, false);
            EditorApplication.update -= Poll;
            Debug.Log($"[WarehouseHRI] BatchPlay finished ({code}): {status}");
            EditorApplication.Exit(code);
        }
    }
}
