using System.Globalization;
using System.IO;
using UnityEditor;
using UnityEditor.SceneManagement;
using UnityEngine;
using WarehouseRobot.Bridge;
using WarehouseRobot.Scenario;

namespace WarehouseRobot.ScenarioEditor
{
    /// <summary>
    /// v4 study: command-line Play session of WarehouseRobot_v4.unity (the v3 TrialBatchPlay and its scene are unchanged).
    /// Opens the v4 scene, presses Play, waits until TrialRunnerV4 is done and quits (exit 0; 1 when the runner did not
    /// start, or on timeout). The Python bridge must already run with configs/v4/bridge.json. Run it WITHOUT -batchmode
    /// to see the HUD: IMGUI (HudOverlay) is not drawn in batch mode. With -checkDir D it also saves, into D, a Game view
    /// screenshot and the hud block (JSON) the first time the HUD lists a person and the first time it shows screen text
    /// (D absolute, or relative to the repository root, e.g. robot_vision/outputs/v4_play_check_20261103_215431).
    ///   Unity -projectPath P -executeMethod WarehouseRobot.ScenarioEditor.TrialPlayV4.Run -trialTimeout 1800 -checkDir D -logFile run.log
    /// </summary>
    [InitializeOnLoad]
    public static class TrialPlayV4
    {
        const string Scene = "Assets/Scenes/WarehouseRobot_v4.unity";
        const string ActiveKey = "WarehouseRobot.TrialPlayV4.Active";
        const string DeadlineKey = "WarehouseRobot.TrialPlayV4.Deadline";
        const string CheckDirKey = "WarehouseRobot.TrialPlayV4.CheckDir";
        const string RepoRootRelativeToProject = "../../..";
        static bool shotPeople, shotText;

        static string RepoRoot => Path.GetFullPath(Path.Combine(Application.dataPath, "..", RepoRootRelativeToProject));

        static TrialPlayV4()
        {
            if (SessionState.GetBool(ActiveKey, false)) EditorApplication.update += Poll;
        }

        public static void Run()
        {
            float timeout = 1800f;
            string checkDir = "";
            var args = System.Environment.GetCommandLineArgs();
            for (int i = 0; i < args.Length - 1; i++)
            {
                if (args[i] == "-trialTimeout") float.TryParse(args[i + 1], NumberStyles.Float, CultureInfo.InvariantCulture, out timeout);
                if (args[i] == "-checkDir") checkDir = Path.GetFullPath(Path.Combine(RepoRoot, args[i + 1]));   // relative = to the repo root
            }
            if (checkDir.Length > 0) Directory.CreateDirectory(checkDir);
            EditorSceneManager.OpenScene(Scene);
            SessionState.SetBool(ActiveKey, true);
            SessionState.SetFloat(DeadlineKey, (float)EditorApplication.timeSinceStartup + timeout);
            SessionState.SetString(CheckDirKey, checkDir);
            EditorApplication.update += Poll;
            EditorApplication.EnterPlaymode();
        }

        static void Poll()
        {
            if (!SessionState.GetBool(ActiveKey, false)) return;
            if (EditorApplication.timeSinceStartup > SessionState.GetFloat(DeadlineKey, float.MaxValue)) { Finish(1, "timeout"); return; }
            if (!EditorApplication.isPlaying) return;
            var r = Object.FindFirstObjectByType<TrialRunnerV4>();
            if (r == null) return;
            Capture(Object.FindFirstObjectByType<RobotBridgeClient>());
            if (r.Status.StartsWith("done")) Finish(0, r.Status + " (" + r.SessionFolder + ")");
            else if (r.Status.StartsWith("not started")) Finish(1, r.Status);
        }

        static void Capture(RobotBridgeClient bridge)
        {
            string dir = SessionState.GetString(CheckDirKey, "");
            var hud = bridge != null ? bridge.Hud : null;
            if (dir.Length == 0 || hud == null) return;
            if (!shotPeople && hud.people.Count > 0) shotPeople = Save(dir, "hud_people", hud);
            if (!shotText && hud.screen_text.Length > 0) shotText = Save(dir, "hud_screen_text", hud);
        }

        static bool Save(string dir, string name, WarehouseHRI.V4.HudMsg hud)
        {
            ScreenCapture.CaptureScreenshot(Path.Combine(dir, name + ".png"));   // the Game view, HUD included
            File.WriteAllText(Path.Combine(dir, name + ".json"), JsonUtility.ToJson(hud, true) + "\n");
            Debug.Log($"[TrialPlayV4] saved {name} (state {hud.state}, {hud.people.Count} people, screen \"{hud.screen_text}\")");
            return true;
        }

        static void Finish(int code, string status)
        {
            SessionState.SetBool(ActiveKey, false);
            EditorApplication.update -= Poll;
            Debug.Log($"[TrialPlayV4] finished ({code}): {status}");
            EditorApplication.Exit(code);
        }
    }
}
