using System;
using System.Collections.Generic;
using System.IO;
using System.Linq;
using System.Text;
using UnityEditor;
using UnityEditor.SceneManagement;
using UnityEngine;
using Object = UnityEngine.Object;

namespace WarehouseAvatar.EditorTools
{
    /// <summary>
    /// The Edit-mode pose geometry and the screenshots of looks the worker template cannot spawn (experiments_ab.md section 10 addendum 1).
    /// Every look of looks_ab.json avatar_experiment is posed on the LookCheck stage with every POINT, WAIT, STOP and PROCEED take of
    /// look_check.json, both arms (PROCEED sequences frame by frame); the rendered elbow angle, upper-arm and forearm directions are compared
    /// with the pose's intended ones (LookPoser.Intended) under the declared tolerance of gesture_geometry.json; no fold for the POINT and
    /// STOP poses designed straight. Looks of the screenshot kind groups whose hands the worker template cannot shape are rendered from the
    /// neutral camera of gesture_geometry.json screens. No perception model is run. Writes robot_vision/outputs/pose_geometry_&lt;time&gt;/.
    /// Command line: -executeMethod WarehouseAvatar.EditorTools.LookCheckMenu.BatchPoseGeometry (batch mode works).
    /// </summary>
    public static partial class LookCheckMenu
    {
        public static void BatchPoseGeometry() => Batch(PoseGeometry);

        [MenuItem("Tools/Warehouse v4/Experiments/Run Pose Geometry (Edit mode)")]
        public static void PoseGeometryMenu()
        {
            if (!EditorSceneManager.SaveCurrentModifiedScenesIfUserWantsTo()) return;
            Report("Pose Geometry", PoseGeometry());
        }

        [Serializable]
        class PoseRow
        {
            public string look, command, arm, take;
            public int frames, frames_render_failed, frames_fold;
            public float min_elbow_deg = 999f, min_intended_elbow_deg = 999f, max_elbow_error_deg, max_upper_error_deg, max_forearm_error_deg;
            public bool render_pass = true, pass = true;
        }

        [Serializable]
        class PoseLook
        {
            public string id, kind_group, status, note = "";
            public bool template_can_shape_hands;
            public List<PoseRow> takes = new List<PoseRow>();
            public List<string> screens = new List<string>();
        }

        [Serializable] class PoseFile { public string created_local, git_commit, git_branch, git_status_porcelain, tolerance, note; public List<PoseLook> looks = new List<PoseLook>(); }

        public static readonly string[] PoseCommands = { LookCheckConfig.Point, LookCheckConfig.Wait, LookCheckConfig.Stop, LookCheckConfig.Proceed };

        public static string PoseGeometry()
        {
            var cfgAsset = AssetDatabase.LoadAssetAtPath<TextAsset>(ConfigPath) ?? throw new FileNotFoundException(ConfigPath);
            var cfg = LoadConfig(cfgAsset);
            var geoAsset = AssetDatabase.LoadAssetAtPath<TextAsset>(GestureGeometryMenu.ConfigPath) ?? throw new FileNotFoundException(GestureGeometryMenu.ConfigPath);
            var geo = GestureGeometryConfig.Parse(geoAsset.text);
            var ge = geo.Validate();
            if (ge.Count > 0) throw new InvalidOperationException("gesture_geometry.json: " + string.Join("; ", ge));
            var ab = ExperimentLooksMenu.Load(out string abText);
            var workerAsset = AssetDatabase.LoadAssetAtPath<TextAsset>(WorkerTemplateMenu.ConfigPath) ?? throw new FileNotFoundException(WorkerTemplateMenu.ConfigPath);
            var worker = WorkerV4Config.Parse(workerAsset.text);
            var subset = ExperimentLooks.Subset(Environment.GetCommandLineArgs(), ab.avatar_experiment, out string subsetError);
            if (subsetError != null) throw new ArgumentException(subsetError);
            if (!File.Exists(ProjectFile(ScenePath))) throw new FileNotFoundException(ScenePath + " missing: run Build LookCheck Scene first");
            EditorSceneManager.OpenScene(ScenePath, OpenSceneMode.Single);
            var stage = Object.FindObjectOfType<LookCheckStage>() ?? throw new InvalidOperationException("no LookCheckStage in " + ScenePath);
            var pt = LoadPanTilt(cfg);
            string repo = RepoRoot(cfg);
            string outDir = NewOutputFolder(Path.Combine(repo, cfg.paths.output_root), "pose_geometry");
            Directory.CreateDirectory(Path.Combine(outDir, "screens"));
            Directory.CreateDirectory(Path.Combine(outDir, "config_used"));
            WriteNew(Path.Combine(outDir, "config_used", "look_check.json"), cfgAsset.text);
            WriteNew(Path.Combine(outDir, "config_used", "gesture_geometry.json"), geoAsset.text);
            WriteNew(Path.Combine(outDir, "config_used", "looks_ab.json"), abText);
            var tol = geo.tolerance;
            string status = Git(repo, "status --porcelain");
            var file = new PoseFile
            {
                created_local = DateTime.Now.ToString("yyyy-MM-dd'T'HH:mm:ss", Inv), git_commit = Git(repo, "rev-parse HEAD").Trim(),
                git_branch = Git(repo, "rev-parse --abbrev-ref HEAD").Trim(), git_status_porcelain = status,
                tolerance = $"elbow {tol.elbow_angle_deg.ToString(Inv)} deg, upper-arm direction {tol.arm_direction_deg.ToString(Inv)} deg, forearm {tol.forearm_direction_deg.ToString(Inv)} deg; " +
                            $"no fold below {tol.no_fold_min_elbow_deg.ToString(Inv)} deg for {string.Join(", ", tol.no_fold_commands)} poses designed straight",
                note = "Edit-mode pose geometry (experiments_ab.md section 10 addendum 1): LookPoser poses of look_check.json against their intended directions; no perception model run.",
            };
            var camGo = new GameObject("NeutralScreenCamera");
            try
            {
                var cam = camGo.AddComponent<Camera>();
                cam.enabled = false;
                cam.fieldOfView = geo.screens.vertical_fov_deg;
                cam.nearClipPlane = 0.05f;
                cam.clearFlags = CameraClearFlags.SolidColor;
                cam.backgroundColor = Grey(geo.stage.backdrop_grey);
                foreach (var id in subset ?? ab.avatar_experiment)
                {
                    var entry = ab.looks.FirstOrDefault(l => l.id == id) ?? worker.Look(id) ?? cfg.looks.FirstOrDefault(l => l.id == id)
                                ?? throw new ArgumentException($"look '{id}' is defined nowhere");
                    var kind = (entry as ExperimentLook)?.kind_group ?? ExperimentLook.Stylised;
                    var pl = new PoseLook { id = id, kind_group = kind };
                    file.looks.Add(pl);
                    ClearStage(stage);
                    var spawned = Spawn(entry, stage.stageRoot, cfg);
                    pl.status = spawned.Row.status;
                    pl.note = spawned.Row.note;
                    if (spawned.Root == null || spawned.Poser == null || !spawned.Poser.HasArms) continue;
                    BuildBackdrop(stage, cfg, cfg.recording.distances_m[0]);
                    Place(spawned, stage, cfg.recording.distances_m[0]);
                    ApplyStage(stage, cfg, pt, cfg.recording.distances_m[0], cfg.recording.vertical_fov_deg);
                    var poser = spawned.Poser;
                    pl.template_can_shape_hands = HandShaper.Complete(HandShaper.BuildArm(new PoserBones(poser), false)) && HandShaper.Complete(HandShaper.BuildArm(new PoserBones(poser), true));
                    foreach (var c in cfg.commands.Where(x => PoseCommands.Contains(x.command)))
                        foreach (var arm in cfg.recording.arms)
                            foreach (var v in c.variants)
                            {
                                var row = new PoseRow { look = id, command = c.command, arm = arm, take = v.take };
                                pl.takes.Add(row);
                                int n = c.command == LookCheckConfig.Proceed && v.sequence ? cfg.recording.proceed_sequence_frames : 1;
                                for (int i = 0; i < n; i++)
                                {
                                    var spec = PoseSpec.From(c.command, arm, v, i / 10.0);
                                    poser.Apply(spec);
                                    Measure(poser, spec, tol, row);
                                }
                            }
                    if (!pl.template_can_shape_hands && geo.screens.kind_groups.Contains(kind))
                        foreach (var c in new[] { LookCheckConfig.Point, LookCheckConfig.Proceed, LookCheckConfig.Wait, LookCheckConfig.Stop })
                            foreach (var arm in cfg.recording.arms)
                            {
                                var v = cfg.commands.Single(x => x.command == c).variants.Single(x => x.take == "seq1");
                                double t = c == LookCheckConfig.Proceed && v.swing_hz > 0f ? 0.5 / v.swing_hz : 0.0;   // PROCEED: the top of the swing
                                poser.Apply(PoseSpec.From(c, arm, v, t));
                                string name = $"{id}__{c}__{arm}.png";
                                poser.BodyFrame(out _, out var bodyForward);
                                AimNeutral(cam, spawned.Root.transform, bodyForward, geo.screens, LookInventory.Height(spawned.Root));
                                Render(cam, geo.screens.width_px, geo.screens.height_px, out byte[] png);
                                WriteNew(Path.Combine(outDir, "screens", name), png);
                                pl.screens.Add("screens/" + name);
                            }
                }
            }
            finally
            {
                Object.DestroyImmediate(camGo);
                ClearStage(stage);
            }
            WriteNew(Path.Combine(outDir, "geometry.json"), JsonUtility.ToJson(file, true).Replace("\r\n", "\n") + "\n");
            WriteNew(Path.Combine(outDir, "table.md"), PoseTable(file));
            string rel = Path.GetRelativePath(repo, outDir).Replace('\\', '/');
            return $"{file.looks.Count} looks: " + string.Join("; ", file.looks.Select(l => $"{l.id} {(l.takes.Count == 0 ? l.status : l.takes.All(t => t.render_pass) ? "rendering ok" : "rendering FAILS")}" +
                                                                                          $"{(l.takes.Any(t => t.frames_fold > 0) ? " (fold flags)" : "")}{(l.screens.Count > 0 ? $", {l.screens.Count} screens" : "")}")) + $". {rel}";
        }

        /// <summary>LookPoser's arms as a bone source for HandShaper.BuildArm (does the template's hand check pass for this rig?).</summary>
        sealed class PoserBones : IBoneSource
        {
            readonly Dictionary<HumanBodyBones, Transform> m = new Dictionary<HumanBodyBones, Transform>();
            public PoserBones(LookPoser p)
            {
                foreach (var a in new[] { p.Left, p.Right })
                {
                    m[a.IsRight ? HumanBodyBones.RightUpperArm : HumanBodyBones.LeftUpperArm] = a.Upper;
                    m[a.IsRight ? HumanBodyBones.RightLowerArm : HumanBodyBones.LeftLowerArm] = a.Lower;
                    m[a.IsRight ? HumanBodyBones.RightHand : HumanBodyBones.LeftHand] = a.Hand;
                    var first = a.IsRight ? HumanBodyBones.RightThumbProximal : HumanBodyBones.LeftThumbProximal;
                    for (int f = 0; f < 5; f++) for (int j = 0; j < 3; j++) m[first + 3 * f + j] = a.Fingers[f][j];
                }
            }
            public Transform Get(HumanBodyBones b) => m.TryGetValue(b, out var t) ? t : null;
        }

        static void Measure(LookPoser poser, PoseSpec spec, GeometryTolerance tol, PoseRow row)
        {
            var a = spec.RightArm ? poser.Right : poser.Left;
            poser.Intended(spec, out var upper, out var fore);
            Vector3 s = a.Upper.position, e = a.Lower.position, w = a.Hand.position;
            float elbow = GestureGeometry.InteriorDeg(s, e, w), intended = 180f - Vector3.Angle(upper, fore);
            float eErr = Mathf.Abs(elbow - intended), uErr = Vector3.Angle(e - s, upper), fErr = Vector3.Angle(w - e, fore);
            bool render = eErr <= tol.elbow_angle_deg && uErr <= tol.arm_direction_deg && fErr <= tol.forearm_direction_deg;
            bool straight = intended >= tol.no_fold_min_elbow_deg;      // designed straight (the bent STOP takes are bent by design)
            bool fold = tol.no_fold_commands.Contains(spec.Command) && straight && elbow < tol.no_fold_min_elbow_deg;
            row.frames++;
            row.min_elbow_deg = Mathf.Min(row.min_elbow_deg, (float)Math.Round(elbow, 2));
            row.min_intended_elbow_deg = Mathf.Min(row.min_intended_elbow_deg, (float)Math.Round(intended, 2));
            row.max_elbow_error_deg = Mathf.Max(row.max_elbow_error_deg, (float)Math.Round(eErr, 2));
            row.max_upper_error_deg = Mathf.Max(row.max_upper_error_deg, (float)Math.Round(uErr, 2));
            row.max_forearm_error_deg = Mathf.Max(row.max_forearm_error_deg, (float)Math.Round(fErr, 2));
            if (!render) { row.frames_render_failed++; row.render_pass = false; }
            if (fold) row.frames_fold++;
            row.pass = row.render_pass && row.frames_fold == 0;
        }

        /// <summary>The neutral screenshot camera (gesture_geometry.json screens): distance_m in front of the look, azimuth_right_deg toward its
        /// right, at height_m, aimed at aim_height_of_body x its height.</summary>
        static void AimNeutral(Camera cam, Transform look, Vector3 bodyForward, GeometryScreens sc, float height)
        {
            var dir = Quaternion.AngleAxis(sc.azimuth_right_deg, Vector3.up) * bodyForward;
            var pos = look.position + dir * sc.distance_m + Vector3.up * sc.height_m;
            var aim = look.position + Vector3.up * (sc.aim_height_of_body * Mathf.Max(0.5f, height));
            cam.transform.SetPositionAndRotation(pos, Quaternion.LookRotation(aim - pos, Vector3.up));
        }

        static string PoseTable(PoseFile f)
        {
            var sb = new StringBuilder();
            sb.Append($"# Pose geometry, Edit mode ({f.created_local}, {f.git_commit})\n\nTolerance: {f.tolerance}. Worst values per look and command over every take, frame and arm.\n\n");
            sb.Append("| look | kind | template shapes hands | command | takes | frames | elbow rendered min | elbow intended min | elbow err max | upper-arm err max | forearm err max | rendering | no fold | screens |\n");
            sb.Append("|---|---|---|---|---|---|---|---|---|---|---|---|---|---|\n");
            foreach (var l in f.looks)
            {
                if (l.takes.Count == 0) { sb.Append($"| {l.id} | {l.kind_group} | | {l.status} {l.note} | | | | | | | | | | |\n"); continue; }
                foreach (var cmd in PoseCommands)
                {
                    var t = l.takes.Where(x => x.command == cmd).ToList();
                    if (t.Count == 0) continue;
                    string D(float x) => x.ToString("0.0", Inv);
                    sb.Append($"| {l.id} | {l.kind_group} | {(l.template_can_shape_hands ? "yes" : "no")} | {cmd} | {t.Count} | {t.Sum(x => x.frames)} | " +
                              $"{D(t.Min(x => x.min_elbow_deg))} | {D(t.Min(x => x.min_intended_elbow_deg))} | {D(t.Max(x => x.max_elbow_error_deg))} | {D(t.Max(x => x.max_upper_error_deg))} | " +
                              $"{D(t.Max(x => x.max_forearm_error_deg))} | {(t.All(x => x.render_pass) ? "ok" : "**fails**")} | {(t.All(x => x.frames_fold == 0) ? "ok" : $"**{t.Sum(x => x.frames_fold)}**")} | " +
                              $"{l.screens.Count(s => s.Contains("__" + cmd + "__"))} |\n");
                }
            }
            return sb.ToString();
        }
    }
}
