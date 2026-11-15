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
    /// The palm probe (Avatar/Config/experiments_ab.md section 12 addendum 2, decisions 2 and 3), Edit mode, report only. Every look of
    /// looks_ab.json avatar_experiment is spawned on the LookCheck stage; each hand is shaped as the worker template shapes it (STOP and WAIT,
    /// the WAIT thumb tucked per rig) with the fingers up and the palm toward a camera point 2.0 m in front of the look at 1.2 m height. Then:
    /// - the palm normal from the bones and from the skinned mesh, (a) every vertex bound mainly to the Hand bone (as the Play check) and (b)
    ///   only the vertices of a sub-mesh whose material name contains "SKIN" (sleeve and cuff excluded), each against the camera under
    ///   gesture_geometry.json's palm rule;
    /// - per hand, the share of the palm-region vertices (and of the glove material's vertices, "glove") bound to the Hand bone with weight
    ///   >= 0.95: (nearly) all means the mesh palm turns exactly with the bone frame.
    /// The sub-mesh of each vertex is read from the mesh's index data (how it was read is reported). No perception model is run. Writes
    /// robot_vision/outputs/palm_probe_&lt;time&gt;/ (palm_probe.md, palm_probe.json).
    /// Command line: -executeMethod WarehouseAvatar.EditorTools.LookCheckMenu.BatchPalmProbe [-lookCheckLooks a,b]
    /// </summary>
    public static partial class LookCheckMenu
    {
        public static void BatchPalmProbe() => Batch(PalmProbe);

        [MenuItem("Tools/Warehouse v4/Experiments/Run Palm Probe (Edit mode)")]
        public static void PalmProbeMenu()
        {
            if (!EditorSceneManager.SaveCurrentModifiedScenesIfUserWantsTo()) return;
            Report("Palm Probe", PalmProbe());
        }

        public const float RigidWeight = 0.95f;

        [Serializable]
        class PalmProbeRow
        {
            public string look, command, arm, index_source = "";
            public float bone_deg = -1f, mesh_all_deg = -1f, mesh_all_flatness = -1f, mesh_skin_deg = -1f, mesh_skin_flatness = -1f, mesh_glove_deg = -1f, mesh_glove_flatness = -1f;
            public int mesh_all_vertices, mesh_skin_vertices, region_vertices, region_rigid, glove_vertices, glove_rigid, glove_region_vertices, glove_region_rigid;
            public bool mesh_all_pass, mesh_skin_pass, mesh_glove_pass, bone_pass;
            public string skin_materials = "";
        }

        [Serializable] class PalmProbeFile { public string created_local, git_commit, git_status_porcelain, rule; public List<PalmProbeRow> rows = new List<PalmProbeRow>(); }

        public static string PalmProbe()
        {
            var cfgAsset = AssetDatabase.LoadAssetAtPath<TextAsset>(ConfigPath) ?? throw new FileNotFoundException(ConfigPath);
            var cfg = LoadConfig(cfgAsset);
            var geo = GestureGeometryConfig.Parse((AssetDatabase.LoadAssetAtPath<TextAsset>(GestureGeometryMenu.ConfigPath) ?? throw new FileNotFoundException(GestureGeometryMenu.ConfigPath)).text);
            var tol = geo.tolerance;
            var worker = WorkerV4Config.Parse((AssetDatabase.LoadAssetAtPath<TextAsset>(WorkerTemplateMenu.ConfigPath) ?? throw new FileNotFoundException(WorkerTemplateMenu.ConfigPath)).text);
            var ab = ExperimentLooksMenu.Load(out _);
            var subset = ExperimentLooks.Subset(Environment.GetCommandLineArgs(), ab.avatar_experiment, out string subsetError);
            if (subsetError != null) throw new ArgumentException(subsetError);
            if (!File.Exists(ProjectFile(ScenePath))) throw new FileNotFoundException(ScenePath + " missing: run Build LookCheck Scene first");
            EditorSceneManager.OpenScene(ScenePath, OpenSceneMode.Single);
            var stage = Object.FindObjectOfType<LookCheckStage>() ?? throw new InvalidOperationException("no LookCheckStage in " + ScenePath);
            string repo = RepoRoot(cfg);
            var file = new PalmProbeFile
            {
                created_local = DateTime.Now.ToString("yyyy-MM-dd'T'HH:mm:ss", Inv), git_commit = Git(repo, "rev-parse HEAD").Trim(), git_status_porcelain = Git(repo, "status --porcelain"),
                rule = $"palm within {tol.palm_facing_deg.ToString("0.#", Inv)} deg of the camera; mesh normal: >= {tol.palm_mesh_min_vertices} vertices, flatness <= {tol.palm_mesh_flatness_max.ToString("0.0#", Inv)}; " +
                       $"hand-bound = largest weight on the Hand bone and >= {tol.palm_hand_weight_min.ToString("0.0#", Inv)}; rigid = Hand-bone weight >= {RigidWeight.ToString("0.00", Inv)}",
            };
            foreach (var id in subset ?? ab.avatar_experiment)
            {
                var entry = ab.looks.FirstOrDefault(l => l.id == id) ?? worker.Look(id) ?? cfg.looks.FirstOrDefault(l => l.id == id)
                            ?? throw new ArgumentException($"look '{id}' is defined nowhere");
                ClearStage(stage);
                var spawned = Spawn(entry, stage.stageRoot, cfg);
                if (spawned.Root == null || spawned.Poser == null || !spawned.Poser.HasArms) continue;
                var look = spawned.Root.transform;
                Vector3 camera = look.position + look.forward * 2.0f + Vector3.up * 1.2f;
                var bones = new PoserBones(spawned.Poser);
                var arms = new[] { HandShaper.BuildArm(bones, false), HandShaper.BuildArm(bones, true) };
                HandShaper.MirrorRest(arms[1], arms[0]);                                     // as WorkerV4.Initialize
                var bind = arms.Select(HandShaper.Capture).ToArray();
                var rest = arms.Select(a => a.Hand.localRotation).ToArray();
                var tucks = new[] { HandShaper.ThumbTuck(arms[0], bind[0], worker.hand_shapes.wait), HandShaper.ThumbTuck(arms[1], bind[1], worker.hand_shapes.wait) };
                var smrs = look.GetComponentsInChildren<SkinnedMeshRenderer>(true);
                var labels = smrs.ToDictionary(s => s, s => SubMeshMaterials(s, out _));
                foreach (var cmd in new[] { WorkerV4Config.Stop, WorkerV4Config.Wait })
                    for (int k = 0; k < 2; k++)
                    {
                        var a = arms[k];
                        a.Hand.localRotation = rest[k];
                        for (int f = 0; f < 5; f++) for (int j = 0; j < 3; j++) if (a.Fingers[f][j] != null) a.Fingers[f][j].localRotation = bind[k][f][j];
                        var shape = worker.hand_shapes.For(cmd);
                        Vector3 palm = Vector3.ProjectOnPlane(camera - a.Hand.position, Vector3.up);   // as WorkerV4: horizontal toward the robot eye
                        HandShaper.Apply(a, bind[k], shape, Vector3.up, palm.normalized, 1f, cmd == WorkerV4Config.Wait ? tucks[k] : null);
                        var row = new PalmProbeRow { look = id, command = cmd, arm = a.IsRight ? "right" : "left" };
                        Measure(a, smrs, labels, camera, tol, row);
                        file.rows.Add(row);
                    }
            }
            ClearStage(stage);
            string outDir = NewOutputFolder(Path.Combine(repo, cfg.paths.output_root), "palm_probe");
            WriteNew(Path.Combine(outDir, "palm_probe.json"), JsonUtility.ToJson(file, true).Replace("\r\n", "\n") + "\n");
            WriteNew(Path.Combine(outDir, "palm_probe.md"), ProbeTable(file));
            var lines = file.rows.GroupBy(r => r.look).Select(g =>
                $"{g.Key}: bones {(g.All(r => r.bone_pass) ? "ok" : "FAIL")}, mesh all {(g.All(r => r.mesh_all_pass) ? "ok" : "fail")}, mesh skin " +
                $"{(g.All(r => r.mesh_skin_vertices == 0) ? "n/a" : g.All(r => r.mesh_skin_pass) ? "ok" : "fail")}, rigid {g.Sum(r => r.region_rigid)}/{g.Sum(r => r.region_vertices)}");
            return string.Join("; ", lines) + $". {Path.GetRelativePath(repo, outDir).Replace('\\', '/')}";
        }

        /// <summary>Each vertex's material name (the lowest sub-mesh using it), read from the mesh's index data; "" when none.</summary>
        static string[] SubMeshMaterials(SkinnedMeshRenderer smr, out string source)
        {
            var mesh = smr.sharedMesh;
            source = "none";
            if (mesh == null) return new string[0];
            var label = new string[mesh.vertexCount];
            var mats = smr.sharedMaterials;
            int read = 0;
            for (int sub = mesh.subMeshCount - 1; sub >= 0; sub--)
            {
                string name = sub < mats.Length && mats[sub] != null ? mats[sub].name.Replace(" (Instance)", "") : "sub" + sub;
                var idx = mesh.GetIndices(sub);
                read += idx.Length;
                foreach (int i in idx) if (i < label.Length) label[i] = name;
            }
            source = $"{mesh.subMeshCount} sub-meshes, {read} indices (Mesh.GetIndices, readable {mesh.isReadable})";
            for (int i = 0; i < label.Length; i++) if (label[i] == null) label[i] = "";
            return label;
        }

        static void Measure(LookPoser.Arm a, SkinnedMeshRenderer[] smrs, Dictionary<SkinnedMeshRenderer, string[]> labels, Vector3 camera, GeometryTolerance tol, PalmProbeRow row)
        {
            var f = HandGeometry.Frame(a);
            if (!f.Valid) return;
            row.bone_deg = R2(Vector3.Angle(f.Normal, camera - f.P));
            row.bone_pass = row.bone_deg <= tol.palm_facing_deg;
            var all = new List<Vector3>();
            var skin = new List<Vector3>();
            var gloveRegion = new List<Vector3>();   // addendum 4: mesh (c), the glove plate whatever its weights
            var skinMats = new HashSet<string>();
            foreach (var smr in smrs)
            {
                var mesh = smr.sharedMesh;
                var bones = smr.bones;
                if (mesh == null || bones == null) continue;
                int hi = Array.IndexOf(bones, a.Hand);
                if (hi < 0) continue;
                // addendum 4 correction: the bones of this hand (the hand bone and every bone below it) decide whose glove a vertex is
                var tree = new bool[bones.Length];
                for (int t = 0; t < bones.Length; t++) tree[t] = bones[t] != null && (bones[t] == a.Hand || bones[t].IsChildOf(a.Hand));
                row.index_source += (row.index_source.Length > 0 ? "; " : "") + smr.name + ": ";
                SubMeshMaterials(smr, out string src);
                row.index_source += src;
                var baked = new Mesh();
                try
                {
                    smr.BakeMesh(baked, true);
                    var v = baked.vertices;
                    var m = Matrix4x4.TRS(smr.transform.position, smr.transform.rotation, Vector3.one);
                    var bw = mesh.boneWeights;
                    var lab = labels[smr];
                    for (int i = 0; i < bw.Length && i < v.Length; i++)
                    {
                        var b = bw[i];
                        float handW = (b.boneIndex0 == hi ? b.weight0 : 0f) + (b.boneIndex1 == hi ? b.weight1 : 0f) + (b.boneIndex2 == hi ? b.weight2 : 0f) + (b.boneIndex3 == hi ? b.weight3 : 0f);
                        float top = Mathf.Max(Mathf.Max(b.weight0, b.weight1), Mathf.Max(b.weight2, b.weight3));
                        Vector3 p = m.MultiplyPoint3x4(v[i]);
                        float along = Vector3.Dot(p - f.Hand, f.FingerDir);
                        bool region = along >= 0f && along <= f.Lp;
                        string mat = i < lab.Length ? lab[i] : "";
                        float treeW = (tree[b.boneIndex0] ? b.weight0 : 0f) + (tree[b.boneIndex1] ? b.weight1 : 0f) + (tree[b.boneIndex2] ? b.weight2 : 0f) + (tree[b.boneIndex3] ? b.weight3 : 0f);
                        bool glove = mat.IndexOf("glove", StringComparison.OrdinalIgnoreCase) >= 0 && treeW >= 0.5f;
                        if (glove)
                        {
                            row.glove_vertices++;
                            if (handW >= RigidWeight) row.glove_rigid++;
                            if (region) { row.glove_region_vertices++; gloveRegion.Add(p); if (handW >= RigidWeight) row.glove_region_rigid++; }
                        }
                        bool handBound = handW >= tol.palm_hand_weight_min && handW >= top - 1e-6f;
                        if (!handBound || !region) continue;
                        row.region_vertices++;
                        if (handW >= RigidWeight) row.region_rigid++;
                        all.Add(p);
                        if (mat.IndexOf("SKIN", StringComparison.OrdinalIgnoreCase) >= 0) { skin.Add(p); skinMats.Add(mat); }
                    }
                }
                finally { Object.DestroyImmediate(baked); }
            }
            row.mesh_all_vertices = all.Count;
            row.mesh_skin_vertices = skin.Count;
            row.skin_materials = string.Join(", ", skinMats.OrderBy(x => x));
            if (HandGeometry.MeshNormal(all, f.Normal, tol.palm_mesh_min_vertices, tol.palm_mesh_flatness_max, out var na, out float fa)) { row.mesh_all_deg = R2(Vector3.Angle(na, camera - f.P)); row.mesh_all_pass = row.mesh_all_deg <= tol.palm_facing_deg; }
            row.mesh_all_flatness = (float)Math.Round(fa, 3);
            if (HandGeometry.MeshNormal(skin, f.Normal, tol.palm_mesh_min_vertices, tol.palm_mesh_flatness_max, out var ns, out float fs)) { row.mesh_skin_deg = R2(Vector3.Angle(ns, camera - f.P)); row.mesh_skin_pass = row.mesh_skin_deg <= tol.palm_facing_deg; }
            row.mesh_skin_flatness = (float)Math.Round(fs, 3);
            if (HandGeometry.MeshNormal(gloveRegion, f.Normal, tol.palm_mesh_min_vertices, tol.palm_mesh_flatness_max, out var ng, out float fg)) { row.mesh_glove_deg = R2(Vector3.Angle(ng, camera - f.P)); row.mesh_glove_pass = row.mesh_glove_deg <= tol.palm_facing_deg; }
            row.mesh_glove_flatness = (float)Math.Round(fg, 3);
        }

        static float R2(float x) => (float)Math.Round(x, 2);

        static string ProbeTable(PalmProbeFile f)
        {
            var sb = new StringBuilder();
            sb.Append($"# Palm probe (Edit mode, {f.created_local}, commit {f.git_commit.Substring(0, Math.Min(7, f.git_commit.Length))})\n\n");
            sb.Append($"experiments_ab.md section 12 addendum 2. Rule: {f.rule}. Hands shaped as the worker template shapes them (WAIT thumb tucked), fingers up, palm toward a camera point 2.0 m in front at 1.2 m. " +
                      "Mesh (a) = every hand-bound palm-region vertex (as the Play check); mesh (b) = only vertices of a material named *SKIN*; mesh (c) (addendum 4, diagnostic) = the palm-region vertices of a material named *glove*, whatever their bone weights. -1 / n/a = undetermined.\n\n");
            sb.Append("| look | command | arm | bones (deg) | mesh (a) all (deg) | (a) vertices | (a) flatness | mesh (b) skin (deg) | (b) vertices | (b) flatness | palm-region vertices rigid (>= 0.95) | glove rigid, all | glove rigid, palm region | mesh (c) glove plate (deg) | (c) flatness |\n");
            sb.Append("|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|\n");
            string D(float x) => x < 0f ? "n/a" : x.ToString("0.0", Inv);
            string Share(int a, int n) => n == 0 ? "-" : $"{a}/{n} ({(100.0 * a / n).ToString("0.0", Inv)} %)";
            foreach (var r in f.rows)
                sb.Append($"| {r.look} | {r.command} | {r.arm} | {D(r.bone_deg)} | {D(r.mesh_all_deg)} | {r.mesh_all_vertices} | {r.mesh_all_flatness.ToString("0.00", Inv)} | {D(r.mesh_skin_deg)} | {r.mesh_skin_vertices} | " +
                          $"{(r.mesh_skin_flatness >= 0f ? r.mesh_skin_flatness.ToString("0.00", Inv) : "-")} | {Share(r.region_rigid, r.region_vertices)} | {Share(r.glove_rigid, r.glove_vertices)} | {Share(r.glove_region_rigid, r.glove_region_vertices)} | " +
                          $"{(r.glove_region_vertices > 0 ? D(r.mesh_glove_deg) : "-")} | {(r.glove_region_vertices > 0 && r.mesh_glove_flatness >= 0f ? r.mesh_glove_flatness.ToString("0.00", Inv) : "-")} |\n");
            sb.Append("\nIndex data per look (how the sub-mesh of each vertex was read):\n\n");
            foreach (var g in f.rows.GroupBy(r => r.look)) sb.Append($"- {g.Key}: {g.First().index_source}; skin materials: {(g.First().skin_materials.Length > 0 ? g.First().skin_materials : "none")}\n");
            return sb.ToString();
        }
    }
}
