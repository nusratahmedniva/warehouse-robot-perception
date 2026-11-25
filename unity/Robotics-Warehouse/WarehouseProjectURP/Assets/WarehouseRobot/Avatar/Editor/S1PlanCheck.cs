using System;
using System.Collections.Generic;
using System.Globalization;
using System.IO;
using System.Text;
using UnityEditor;
using UnityEngine;
using WarehouseHRI.V4;

namespace WarehouseAvatar.EditorTools
{
    /// <summary>
    /// The plan-only dry check of the post-freeze supplementary experiment S1 (Unity addendum 14): prints the 60 runs (character, setting, run number, plan run,
    /// goal, map, workers, liars) from the finals' plan (final_plan.json seed, the setting's experiment, ExperimentPlanAB) with the S1 guard applied to each
    /// run, and runs nothing: no Play mode, no robot, no server, no perception, no session folder. Positions are not listed (they depend on Unity's free-cell
    /// check in Play); the goals, the workers' nodes, the lies and the route are independent of them.
    ///   Unity -batchmode -quit -projectPath P -executeMethod WarehouseAvatar.EditorTools.S1PlanCheck.PrintBatch -s1PlanOut robot_vision/outputs/s1_plan_&lt;time&gt;.txt
    /// (finals_v4/run_s1.ps1 -Plan does this.) The output file is new (never overwritten).
    /// </summary>
    public static class S1PlanCheck
    {
        static readonly CultureInfo Inv = CultureInfo.InvariantCulture;
        static string RepoRoot => Path.GetFullPath(Path.Combine(Application.dataPath, "..", "../../.."));
        static string Project(string asset) => File.ReadAllText(Path.Combine(Application.dataPath, "..", asset));
        const string FinalAsset = "Assets/WarehouseRobot/Avatar/Config/final_v4.json";
        const string ExperimentsAsset = "Assets/WarehouseRobot/Scenario/Config/experiments_ab_unity.json";

        [MenuItem("Tools/Warehouse v4/S1/Print the 60-run plan (nothing is run)")]
        public static void Print()
        {
            string text = Build(out var problems);
            Debug.Log("[S1PlanCheck]\n" + text);
            if (problems.Count > 0) Debug.LogError("[S1PlanCheck] " + problems.Count + " problem(s): " + string.Join("; ", problems));
        }

        public static void PrintBatch()
        {
            int code = 0;
            try
            {
                string text = Build(out var problems);
                string[] args = Environment.GetCommandLineArgs();
                string outPath = "";
                for (int i = 0; i < args.Length - 1; i++) if (args[i] == "-s1PlanOut") outPath = Path.GetFullPath(Path.Combine(RepoRoot, args[i + 1]));
                if (outPath.Length > 0)
                {
                    Directory.CreateDirectory(Path.GetDirectoryName(outPath));
                    using (var fs = new FileStream(outPath, FileMode.CreateNew, FileAccess.Write)) { var b = new UTF8Encoding(false).GetBytes(text); fs.Write(b, 0, b.Length); }
                }
                Debug.Log("[S1PlanCheck] done" + (problems.Count > 0 ? ": PROBLEMS: " + string.Join("; ", problems) : ": no problem") + (outPath.Length > 0 ? " -> " + outPath : ""));
                if (problems.Count > 0) code = 1;
            }
            catch (Exception e) { Debug.LogException(e); code = 1; }
            EditorApplication.Exit(code);
        }

        public static string Build(out List<string> problems)
        {
            problems = new List<string>();
            var s1 = S1Config.Parse(Project(S1Config.AssetPath));
            foreach (var p in s1.Validate()) problems.Add("s1_supplementary.json: " + p);
            var finals = FinalConfigV4.Parse(Project(FinalAsset));
            var plan = FinalPlanV4.Parse(File.ReadAllText(Path.Combine(RepoRoot, "robot_vision/configs/v4/final_plan.json")));
            var ecfg = ExperimentsUnityConfig.Parse(Project(ExperimentsAsset));
            string scenarios = File.ReadAllText(Path.Combine(RepoRoot, ecfg.scenarios_ab));
            string roadmap = File.ReadAllText(Path.Combine(RepoRoot, ecfg.roadmap_v4));
            var splits = DataSplitsV4.Parse(File.ReadAllText(Path.Combine(RepoRoot, "robot_vision/configs/v4/data_splits.json")), Project(ExperimentLooks.AssetPath));
            var sb = new StringBuilder();
            sb.Append("S1 plan (nothing is run): ").Append(s1.amendment).Append("; seed ").Append(plan.FinalSeed.ToString(Inv)).Append(", timeout ")
              .Append(s1.timeout_s.ToString(Inv)).Append(" s, ").Append(s1.runs_per_cell.ToString(Inv)).Append(" runs per cell, ").Append(s1.cell_order.Length.ToString(Inv)).Append(" cells\n");
            sb.Append("plan run = the run of the final plan (seed ").Append(plan.FinalSeed.ToString(Inv)).Append("); run = run_### of the S1 session. Positions are not listed (Play-time free-cell check).\n");
            sb.Append("character | setting | run | plan run | goal | map | workers | liars (node, worker, shows, true, on route) | guard\n");
            int rows = 0, liarRuns = 0;
            foreach (var cell in s1.cell_order)
            {
                var def = s1.Setting(cell.setting);
                var fs = finals.Setting(cell.setting);
                if (def == null || fs == null || !fs.IsExperiment) { problems.Add($"{cell.character}/{cell.setting}: no setting"); continue; }
                var fx = FinalExperimentV4.Parse(Project(fs.experiment_config));
                var p = ExperimentPlanAB.Build(ecfg, fx.experiment, scenarios, roadmap, Project, out string error);
                if (p == null) { problems.Add($"{cell.setting}: {error}"); continue; }
                var goals = p.Goals(plan.FinalSeed, plan.RunsPerSetting);
                for (int i = 0; i < def.plan_runs.Length; i++)
                {
                    int planRun = def.plan_runs[i];
                    var r = p.PlanRun(plan.FinalSeed, planRun, goals[planRun - 1], new[] { cell.character }, new[] { cell.character }, null, out error);
                    if (r == null) { problems.Add($"{cell.character}/{cell.setting} plan run {planRun}: {error}"); continue; }
                    var map = p.RunMap(plan.FinalSeed, planRun, out _);
                    var liars = new List<string>();
                    var looks = new List<string>();
                    foreach (var w in r.Workers)
                    {
                        looks.Add(w.Look);
                        if (!w.Liar) continue;
                        bool onRoute = w.Node != map.Start && ExperimentPlanAB.TruthfulCommand(map, w.Node, r.Goal) != ExperimentPlanAB.Back;
                        liars.Add($"{w.Node} #{w.Id.ToString(Inv)} shows {w.ShownCommand} (true {w.TrueCommand}){(onRoute ? " ON ROUTE" : " off route")}");
                    }
                    if (liars.Count > 0) liarRuns++;
                    if (fx.lie_detection != "on" && cell.setting == "B3") problems.Add("B3 is not the lie-handling-on setting");
                    if (cell.setting != "B3" && liars.Count > 0) problems.Add($"{cell.character}/{cell.setting} plan run {planRun}: a liar in a lies-off setting");
                    var clips = new List<string>(fx.point_clips);
                    clips.AddRange(fx.proceed_clips);
                    string guard = splits.GuardRun(looks, clips, false, S1Config.Name, cell.setting, out error) ?? "REFUSED: " + error;
                    if (guard.StartsWith("REFUSED")) problems.Add($"{cell.character}/{cell.setting} plan run {planRun}: {guard}");
                    sb.Append(cell.character).Append(" | ").Append(cell.setting).Append(" | ").Append((i + 1).ToString(Inv)).Append(" | ").Append(planRun.ToString(Inv)).Append(" | ")
                      .Append(r.Goal).Append(" | ").Append(r.MapName).Append(" | ").Append(r.Workers.Count.ToString(Inv)).Append(" | ")
                      .Append(liars.Count == 0 ? "none" : string.Join("; ", liars)).Append(" | ").Append(guard).Append('\n');
                    rows++;
                }
            }
            sb.Append("rows: ").Append(rows.ToString(Inv)).Append(" (expected ").Append((s1.cell_order.Length * s1.runs_per_cell).ToString(Inv)).Append("); runs with a liar: ").Append(liarRuns.ToString(Inv)).Append('\n');
            if (rows != s1.cell_order.Length * s1.runs_per_cell) problems.Add($"{rows} rows, expected {s1.cell_order.Length * s1.runs_per_cell}");
            sb.Append(problems.Count == 0 ? "no problem\n" : "PROBLEMS: " + string.Join("; ", problems) + "\n");
            return sb.ToString();
        }
    }
}
