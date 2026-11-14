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
    /// -workersConfig F (2026-11-12): a declared session config instead of trial_workers_v4.json, F relative to the Unity project
    /// (e.g. Assets/WarehouseRobot/Avatar/Config/sessions/dev_bystanders.json); TrialRunnerV4 records which one it used.
    /// -finalSetting NAME (2026-11-13, Stage F): a FINAL session of that setting (zoom_on, zoom_off, bystanders, zoom_on_repeat), refused
    /// by TrialRunnerV4's final-run guard unless the v4 configs and the B9 files are frozen, the plan has no blank, the development
    /// override is absent and the setting has not run before. The Python server must run with --final-setting NAME.
    /// -experiment NAME (2026-11-14, experiments A and B, Avatar/Config/experiments_ab.md): a DEVELOPMENT session of experiment A1..A4 or
    /// B1..B4 (Scenario/Config/experiments_ab_unity.json); refused together with -finalSetting. -experimentLooks MALE|FEMALE: smoke check of the
    /// runner only, two existing development looks instead of the navigation looks (experiments_ab.md section 3). -experimentSide right|left
    /// (2026-11-14, development only): the A2 / B2 turn side for the session (experiments_ab.md section 7). Since 2026-11-14 the final
    /// settings are the experiments (A1, A2_right, A2_left, A3, A4, B1, B2_right, B3, B4; final_v4.json): -finalSetting A2_left runs the
    /// final of A2 with the left turn; zoom_on, zoom_off, bystanders and zoom_on_repeat are superseded and refused.
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
        static int shotTrials;
        static double exitAt = -1;
        static int exitCode;
        static string exitStatus;

        static string RepoRoot => Path.GetFullPath(Path.Combine(Application.dataPath, "..", RepoRootRelativeToProject));

        static TrialPlayV4()
        {
            if (SessionState.GetBool(ActiveKey, false)) EditorApplication.update += Poll;
        }

        public static void Run()
        {
            float timeout = 1800f;
            string checkDir = "", workers = "", finalSetting = "", experiment = "", experimentLooks = "", experimentSide = "";
            var args = System.Environment.GetCommandLineArgs();
            for (int i = 0; i < args.Length - 1; i++)
            {
                if (args[i] == "-trialTimeout") float.TryParse(args[i + 1], NumberStyles.Float, CultureInfo.InvariantCulture, out timeout);
                if (args[i] == "-checkDir") checkDir = Path.GetFullPath(Path.Combine(RepoRoot, args[i + 1]));   // relative = to the repo root
                if (args[i] == "-workersConfig") workers = args[i + 1];
                if (args[i] == "-finalSetting") finalSetting = args[i + 1];
                if (args[i] == "-experiment") experiment = args[i + 1];
                if (args[i] == "-experimentLooks") experimentLooks = args[i + 1];
                if (args[i] == "-experimentSide") experimentSide = args[i + 1];
            }
            SessionState.SetString(TrialRunnerV4.WorkersOverrideKey, workers);
            SessionState.SetString(TrialRunnerV4.FinalSettingKey, finalSetting);
            SessionState.SetString(TrialRunnerV4.ExperimentKey, experiment);
            SessionState.SetString(TrialRunnerV4.ExperimentLooksKey, experimentLooks);
            SessionState.SetString(TrialRunnerV4.ExperimentSideKey, experimentSide);
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
            // 2026-11-12 (U6): with -checkDir, a Game view screenshot at the end of every trial (trail, ask markers, minimap, HUD)
            // and at the end of the session; the exit waits 3 s so the last screenshot is written
            string dir = SessionState.GetString(CheckDirKey, "");
            if (dir.Length > 0 && r.Completed > shotTrials)
            {
                shotTrials = r.Completed;
                ScreenCapture.CaptureScreenshot(Path.Combine(dir, $"trial_{shotTrials:000}_end.png"));
            }
            if (exitAt > 0)
            {
                if (EditorApplication.timeSinceStartup >= exitAt) Finish(exitCode, exitStatus);
                return;
            }
            if (r.Status.StartsWith("done")) Delayed(dir, 0, r.Status + " (" + r.SessionFolder + ")");
            else if (r.Status.StartsWith("not started") || r.Status.StartsWith("stopped")) Delayed(dir, 1, r.Status);
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

        static void Delayed(string dir, int code, string status)
        {
            if (dir.Length > 0) ScreenCapture.CaptureScreenshot(Path.Combine(dir, "session_end.png"));
            exitCode = code;
            exitStatus = status;
            exitAt = EditorApplication.timeSinceStartup + 3.0;
        }

        static void Finish(int code, string status)
        {
            SessionState.SetBool(ActiveKey, false);
            SessionState.SetString(TrialRunnerV4.WorkersOverrideKey, "");
            SessionState.SetString(TrialRunnerV4.FinalSettingKey, "");
            SessionState.SetString(TrialRunnerV4.ExperimentKey, "");
            SessionState.SetString(TrialRunnerV4.ExperimentLooksKey, "");
            SessionState.SetString(TrialRunnerV4.ExperimentSideKey, "");
            EditorApplication.update -= Poll;
            Debug.Log($"[TrialPlayV4] finished ({code}): {status}");
            EditorApplication.Exit(code);
        }
    }
}
