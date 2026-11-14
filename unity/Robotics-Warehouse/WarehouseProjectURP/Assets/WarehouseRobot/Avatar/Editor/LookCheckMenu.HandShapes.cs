using System;
using System.Collections.Generic;
using System.IO;
using System.Linq;
using System.Text;
using UnityEditor;
using UnityEditor.SceneManagement;
using UnityEngine;

namespace WarehouseAvatar.EditorTools
{
    /// <summary>
    /// The worker template's hand shapes on every look, value for value (experiments_ab.md section 11 item 3): each look of looks_ab.json
    /// avatar_experiment is spawned on the LookCheck stage in its rest pose; the hands are prepared as WorkerV4.Initialize prepares them
    /// (HandShaper.MirrorRest, then Capture) and every hand shape of worker_v4.json is applied to both hands with HandShaper.Apply at weight 1
    /// for two fixed direction sets (fingers up with the palm forward; fingers out to the side with the palm down), each from the rest pose.
    /// Every hand and finger bone's position (relative to the look) and rotation are written with round-trip precision, one line each, to
    /// robot_vision/outputs/hand_shapes_&lt;time&gt;/hand_shapes.txt. With -handShapesBaseline &lt;folder under the output root&gt; the run is
    /// compared with an earlier one line by line (compare.md: per look, lines equal, different, missing; the largest position and angle
    /// difference). No perception model is run.
    /// Command line: -executeMethod WarehouseAvatar.EditorTools.LookCheckMenu.BatchHandShapes [-handShapesBaseline hand_shapes_&lt;time&gt;] [-lookCheckLooks a,b]
    /// </summary>
    public static partial class LookCheckMenu
    {
        public static void BatchHandShapes() => Batch(HandShapes);

        [MenuItem("Tools/Warehouse v4/Experiments/Record Hand Shapes (Edit mode)")]
        public static void HandShapesMenu()
        {
            if (!EditorSceneManager.SaveCurrentModifiedScenesIfUserWantsTo()) return;
            Report("Hand Shapes", HandShapes());
        }

        static readonly string[] k_ShapeNames = { "point", "wait", "stop", "proceed" };

        public static string HandShapes()
        {
            var cfgAsset = AssetDatabase.LoadAssetAtPath<TextAsset>(ConfigPath) ?? throw new FileNotFoundException(ConfigPath);
            var cfg = LoadConfig(cfgAsset);
            var workerAsset = AssetDatabase.LoadAssetAtPath<TextAsset>(WorkerTemplateMenu.ConfigPath) ?? throw new FileNotFoundException(WorkerTemplateMenu.ConfigPath);
            var worker = WorkerV4Config.Parse(workerAsset.text);
            var ab = ExperimentLooksMenu.Load(out _);
            var args = Environment.GetCommandLineArgs();
            var subset = ExperimentLooks.Subset(args, ab.avatar_experiment, out string subsetError);
            if (subsetError != null) throw new ArgumentException(subsetError);
            string baseline = "";
            for (int i = 0; i < args.Length - 1; i++) if (args[i] == "-handShapesBaseline") baseline = args[i + 1];
            if (!File.Exists(ProjectFile(ScenePath))) throw new FileNotFoundException(ScenePath + " missing: run Build LookCheck Scene first");
            string repo = RepoRoot(cfg);
            string root = Path.Combine(repo, cfg.paths.output_root);
            string baselineFile = baseline.Length > 0 ? Path.Combine(root, baseline, "hand_shapes.txt") : "";
            if (baselineFile.Length > 0 && !File.Exists(baselineFile)) throw new FileNotFoundException(baselineFile);
            EditorSceneManager.OpenScene(ScenePath, OpenSceneMode.Single);
            var stage = UnityEngine.Object.FindObjectOfType<LookCheckStage>() ?? throw new InvalidOperationException("no LookCheckStage in " + ScenePath);

            var lines = new List<string>();
            var summary = new StringBuilder();
            summary.Append("# Hand shapes (Edit mode)\n\n");
            summary.Append($"Commit {Git(repo, "rev-parse HEAD").Trim()} on {Git(repo, "rev-parse --abbrev-ref HEAD").Trim()}; working tree " +
                           $"{(Git(repo, "status --porcelain").Trim().Length == 0 ? "clean" : "with changes")}; {DateTime.Now.ToString("yyyy-MM-dd'T'HH:mm:ss", Inv)}.\n\n");
            summary.Append("| look | template accepts both hands | fingers per hand (left / right) | rest mirrored (mm) | lines | WAIT thumb tucked, left | right |\n|---|---|---|---|---|---|---|\n");
            foreach (var id in subset ?? ab.avatar_experiment)
            {
                var entry = ab.looks.FirstOrDefault(l => l.id == id) ?? worker.Look(id) ?? cfg.looks.FirstOrDefault(l => l.id == id)
                            ?? throw new ArgumentException($"look '{id}' is defined nowhere");
                ClearStage(stage);
                var spawned = Spawn(entry, stage.stageRoot, cfg);
                if (spawned.Root == null || spawned.Poser == null || !spawned.Poser.HasArms)
                {
                    summary.Append($"| {id} | {spawned.Row.status} | - | - | 0 |\n");
                    continue;
                }
                var bones = new PoserBones(spawned.Poser);
                var left = HandShaper.BuildArm(bones, false);
                var right = HandShaper.BuildArm(bones, true);
                bool complete = HandShaper.Complete(left) && HandShaper.Complete(right);
                float mirrored = HandShaper.MirrorRest(right, left);    // as WorkerV4.Initialize
                var arms = new[] { left, right };
                var bind = arms.Select(HandShaper.Capture).ToArray();
                // section 12 addendum 2: the WAIT thumb tucked per rig, as WorkerV4.Initialize does
                var tucks = new[] { HandShaper.ThumbTuck(left, bind[0], worker.hand_shapes.wait), HandShaper.ThumbTuck(right, bind[1], worker.hand_shapes.wait) };
                var restHand = arms.Select(a => a.Hand.localRotation).ToArray();
                var look = spawned.Root.transform;
                int before = lines.Count;
                for (int k = 0; k < 2; k++)
                {
                    var a = arms[k];
                    Vector3 side = (a.IsRight ? 1f : -1f) * look.right;
                    var directions = new[] { ("up_palm_forward", look.up, look.forward), ("side_palm_down", side, -look.up) };
                    foreach (var name in k_ShapeNames)
                    {
                        var shape = name == "point" ? worker.hand_shapes.point : name == "wait" ? worker.hand_shapes.wait
                                  : name == "stop" ? worker.hand_shapes.stop : worker.hand_shapes.proceed;
                        foreach (var (dirName, fingerDir, palm) in directions)
                        {
                            a.Hand.localRotation = restHand[k];
                            for (int f = 0; f < 5; f++) for (int j = 0; j < 3; j++) if (a.Fingers[f][j] != null) a.Fingers[f][j].localRotation = bind[k][f][j];
                            HandShaper.Apply(a, bind[k], shape, fingerDir, palm, 1f, name == "wait" ? tucks[k] : null);
                            string key = $"{id}|{(a.IsRight ? "right" : "left")}|{name}|{dirName}";
                            lines.Add(Line(key + "|hand", look, a.Hand));
                            for (int f = 0; f < 5; f++)
                                for (int j = 0; j < 3; j++)
                                    if (a.Fingers[f][j] != null) lines.Add(Line($"{key}|f{f}j{j}", look, a.Fingers[f][j]));
                        }
                    }
                    a.Hand.localRotation = restHand[k];
                    for (int f = 0; f < 5; f++) for (int j = 0; j < 3; j++) if (a.Fingers[f][j] != null) a.Fingers[f][j].localRotation = bind[k][f][j];
                }
                int Fingers(LookPoser.Arm a) => Enumerable.Range(0, 5).Count(f => a.Fingers[f][0] != null);
                string Tuck(HandShaper.ThumbTuckResult t) => !t.Active ? $"no ({t.BeforeLp.ToString("0.00", Inv)} Lp)" :
                    $"{t.BeforeLp.ToString("0.00", Inv)} -> {t.AfterLp.ToString("0.00", Inv)} Lp (swing {t.Swing.ToString("0.000", Inv)}, curl {t.CurlDeg.ToString("0.0", Inv)} deg)";
                summary.Append($"| {id} | {(complete ? "yes" : "no")} | {Fingers(left)} / {Fingers(right)} | " +
                               $"{(mirrored < 0f ? "-" : (mirrored * 1000f).ToString("0.000", Inv))} | {lines.Count - before} | {Tuck(tucks[0])} | {Tuck(tucks[1])} |\n");
            }
            ClearStage(stage);

            string outDir = NewOutputFolder(root, "hand_shapes");
            WriteNew(Path.Combine(outDir, "hand_shapes.txt"), string.Join("\n", lines) + "\n");
            WriteNew(Path.Combine(outDir, "worker_v4.json"), workerAsset.text);
            string result = $"{lines.Count} lines";
            if (baselineFile.Length > 0)
            {
                string compare = Compare(File.ReadAllLines(baselineFile), lines, baseline, out string brief);
                WriteNew(Path.Combine(outDir, "compare.md"), compare);
                result += "; " + brief;
            }
            WriteNew(Path.Combine(outDir, "summary.md"), summary.ToString());
            return $"{result}. {Path.GetRelativePath(repo, outDir).Replace('\\', '/')}";
        }

        static string Line(string key, Transform look, Transform bone)
        {
            Vector3 p = look.InverseTransformPoint(bone.position);
            Quaternion q = Quaternion.Inverse(look.rotation) * bone.rotation;
            string R(float v) => v.ToString("R", Inv);
            return $"{key}\t{R(p.x)} {R(p.y)} {R(p.z)} {R(q.x)} {R(q.y)} {R(q.z)} {R(q.w)}";
        }

        /// <summary>Line-by-line comparison of two hand_shapes.txt files, per look.</summary>
        static string Compare(IEnumerable<string> baseline, List<string> now, string baselineName, out string brief)
        {
            Dictionary<string, string> Map(IEnumerable<string> ls) => ls.Where(l => l.Contains('\t')).ToDictionary(l => l.Split('\t')[0], l => l.Split('\t')[1]);
            var a = Map(baseline);
            var b = Map(now);
            var looks = a.Keys.Concat(b.Keys).Select(k => k.Split('|')[0]).Distinct().ToList();
            var sb = new StringBuilder();
            sb.Append($"# Hand shapes compared with {baselineName}\n\nA line is equal when its seven numbers are identical as written (round-trip precision).\n\n");
            sb.Append("| look | lines equal | different | only in baseline | only now | largest position difference (m) | largest angle difference (deg) | identical |\n|---|---|---|---|---|---|---|---|\n");
            var identical = new List<string>();
            var differ = new List<string>();
            foreach (var look in looks)
            {
                var keys = a.Keys.Concat(b.Keys).Where(k => k.Split('|')[0] == look).Distinct().ToList();
                int eq = 0, diff = 0, onlyA = 0, onlyB = 0;
                float dp = 0f, da = 0f;
                foreach (var k in keys)
                {
                    bool inA = a.TryGetValue(k, out var va), inB = b.TryGetValue(k, out var vb);
                    if (!inA) { onlyB++; continue; }
                    if (!inB) { onlyA++; continue; }
                    if (va == vb) { eq++; continue; }
                    diff++;
                    var x = va.Split(' ').Select(s => float.Parse(s, Inv)).ToArray();
                    var y = vb.Split(' ').Select(s => float.Parse(s, Inv)).ToArray();
                    dp = Mathf.Max(dp, Vector3.Distance(new Vector3(x[0], x[1], x[2]), new Vector3(y[0], y[1], y[2])));
                    da = Mathf.Max(da, Quaternion.Angle(new Quaternion(x[3], x[4], x[5], x[6]), new Quaternion(y[3], y[4], y[5], y[6])));
                }
                bool same = diff == 0 && onlyA == 0 && onlyB == 0;
                (same ? identical : differ).Add(look);
                sb.Append($"| {look} | {eq} | {diff} | {onlyA} | {onlyB} | {dp.ToString("0.000000", Inv)} | {da.ToString("0.0000", Inv)} | {(same ? "yes" : "**no**")} |\n");
            }
            brief = $"identical to {baselineName}: {identical.Count} looks; different: {(differ.Count == 0 ? "none" : string.Join(", ", differ))}";
            return sb.ToString();
        }
    }
}
