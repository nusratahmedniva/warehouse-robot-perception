using System;
using System.Collections.Generic;
using System.Globalization;
using System.IO;
using System.Linq;
using System.Security.Cryptography;
using System.Text;
using UnityEditor;
using UnityEngine;
using Object = UnityEngine.Object;

namespace WarehouseAvatar.EditorTools
{
    /// <summary>
    /// Tools > Warehouse v4 > Experiments (experiments A and B and the avatar experiment, Avatar/Config/experiments_ab.md section 2):
    /// - Import Characters: copies every character FBX of looks_ab.json paths.characters_source (unity/downloads/characters_v4,
    ///   git-ignored) into paths.import_folder/&lt;id&gt;/ (Assets/ThirdParty/CharactersV4, git-ignored), sets Rig > Humanoid (avatar from
    ///   the model), extracts its materials and textures there, recolours a colourless look by the rules of looks_ab.json "recolour",
    ///   and writes a report (Humanoid, bones and finger bones mapped, materials, recolouring) to a new folder
    ///   robot_vision/outputs/import_characters_&lt;time&gt;/. Never overwrites an imported FBX that differs (refuses instead); never commits.
    /// Command line: -executeMethod WarehouseAvatar.EditorTools.ExperimentLooksMenu.BatchImportCharacters (exit 0 = done).
    /// </summary>
    public static class ExperimentLooksMenu
    {
        static readonly CultureInfo Inv = CultureInfo.InvariantCulture;
        static readonly UTF8Encoding Utf8 = new UTF8Encoding(false);

        [MenuItem("Tools/Warehouse v4/Experiments/Import Characters")]
        public static void ImportMenu()
        {
            string msg;
            try { msg = ImportCharacters(); }
            catch (Exception e) { msg = "FAILED: " + e.Message; }
            Debug.Log("[ExperimentLooks] " + msg);
            EditorUtility.DisplayDialog("Import Characters", msg.Length > 1500 ? msg.Substring(0, 1500) + " ..." : msg, "OK");
        }

        public static void BatchImportCharacters()
        {
            try
            {
                Debug.Log("[ExperimentLooks] " + ImportCharacters());
                EditorApplication.Exit(0);
            }
            catch (Exception e)
            {
                Debug.LogError("[ExperimentLooks] FAILED: " + e);
                EditorApplication.Exit(1);
            }
        }

        /// <summary>Command line: -executeMethod WarehouseAvatar.EditorTools.ExperimentLooksMenu.BatchProbeRigs: the scale and proportions of
        /// every prefab-kind look of looks_ab.json (renderer bounds, Humanoid bone heights, arm length, transform scales), report only.</summary>
        public static void BatchProbeRigs()
        {
            try
            {
                Debug.Log("[ExperimentLooks] " + ProbeRigs());
                EditorApplication.Exit(0);
            }
            catch (Exception e)
            {
                Debug.LogError("[ExperimentLooks] FAILED: " + e);
                EditorApplication.Exit(1);
            }
        }

        [Serializable]
        class RigProbe
        {
            public string id, asset, note = "";
            public float renderer_bounds_height_m, head_minus_foot_m, hips_y_m, arm_length_m, shoulder_width_m, arm_to_shoulder_ratio, human_scale;
            public string root_scale, scales_on_path, arm_bones_skinned;
            public string[] skinned_meshes = new string[0];
        }

        [Serializable] class RigProbeFile { public List<RigProbe> looks = new List<RigProbe>(); }

        public static string ProbeRigs()
        {
            var f = Load(out _);
            var file = new RigProbeFile();
            foreach (var l in f.looks)
            {
                if (l == null || l.kind != LookEntry.KindPrefab) continue;
                var p = new RigProbe { id = l.id, asset = l.asset };
                file.looks.Add(p);
                var go = AssetDatabase.LoadAssetAtPath<GameObject>(l.asset);
                if (go == null) { p.note = "not installed"; continue; }
                var inst = (GameObject)Object.Instantiate(go);
                try
                {
                    inst.transform.SetPositionAndRotation(Vector3.zero, Quaternion.identity);
                    p.root_scale = inst.transform.localScale.ToString("0.0000");
                    var b = new Bounds();
                    bool any = false;
                    foreach (var r in inst.GetComponentsInChildren<Renderer>(true))
                    {
                        if (r is SkinnedMeshRenderer smr) smr.updateWhenOffscreen = true;
                        if (!any) { b = r.bounds; any = true; } else b.Encapsulate(r.bounds);
                    }
                    p.renderer_bounds_height_m = any ? b.size.y : -1f;
                    var a = inst.GetComponentInChildren<Animator>();
                    if (a == null || a.avatar == null || !a.avatar.isHuman) { p.note = "no Humanoid Animator"; continue; }
                    p.human_scale = a.humanScale;
                    Transform head = a.GetBoneTransform(HumanBodyBones.Head), lf = a.GetBoneTransform(HumanBodyBones.LeftFoot), hips = a.GetBoneTransform(HumanBodyBones.Hips);
                    Transform lu = a.GetBoneTransform(HumanBodyBones.LeftUpperArm), ll = a.GetBoneTransform(HumanBodyBones.LeftLowerArm), lh = a.GetBoneTransform(HumanBodyBones.LeftHand);
                    Transform ru = a.GetBoneTransform(HumanBodyBones.RightUpperArm);
                    if (head != null && lf != null) p.head_minus_foot_m = head.position.y - lf.position.y;
                    if (hips != null) p.hips_y_m = hips.position.y;
                    if (lu != null && ll != null && lh != null) p.arm_length_m = Vector3.Distance(lu.position, ll.position) + Vector3.Distance(ll.position, lh.position);
                    if (lu != null && ru != null) p.shoulder_width_m = Vector3.Distance(lu.position, ru.position);
                    if (p.shoulder_width_m > 0f) p.arm_to_shoulder_ratio = p.arm_length_m / p.shoulder_width_m;
                    var scales = new List<string>();
                    for (var t = hips; t != null && t != inst.transform.parent; t = t.parent) scales.Add($"{t.name} {t.localScale.ToString("0.0000")}");
                    p.scales_on_path = string.Join(" < ", scales);
                    // do the skinned meshes follow the Humanoid arm bones? (a pose moves those transforms only)
                    var skinned = new HashSet<Transform>();
                    var smrs = inst.GetComponentsInChildren<SkinnedMeshRenderer>(true);
                    foreach (var smr in smrs) foreach (var bt in smr.bones) if (bt != null) skinned.Add(bt);
                    var arm = new List<string>();
                    foreach (var hb in new[] { HumanBodyBones.LeftUpperArm, HumanBodyBones.LeftLowerArm, HumanBodyBones.LeftHand, HumanBodyBones.RightUpperArm,
                                               HumanBodyBones.RightLowerArm, HumanBodyBones.RightHand, HumanBodyBones.LeftIndexProximal })
                    {
                        var bt = a.GetBoneTransform(hb);
                        arm.Add($"{hb} {(bt == null ? "unmapped" : skinned.Contains(bt) ? "skinned" : "NOT skinned (" + bt.name + ")")}");
                    }
                    p.arm_bones_skinned = $"{smrs.Length} skinned meshes, {skinned.Count} bones; " + string.Join(", ", arm);
                    // per skinned mesh: its bones that share a name with a Humanoid arm bone but are another transform (a duplicate armature)
                    var mapped = new Dictionary<string, Transform>();
                    for (var hb = HumanBodyBones.Hips; hb < HumanBodyBones.LastBone; hb++) { var bt = a.GetBoneTransform(hb); if (bt != null) mapped[bt.name] = bt; }
                    var per = new List<string>();
                    foreach (var smr in smrs)
                    {
                        int same = 0, dup = 0;
                        foreach (var bt in smr.bones) { if (bt == null) continue; if (mapped.TryGetValue(bt.name, out var m)) { if (m == bt) same++; else dup++; } }
                        var mat = smr.sharedMaterial;
                        string emis = mat != null && mat.HasProperty("_EmissionColor") ? $" emission {mat.GetColor("_EmissionColor")} keyword {mat.IsKeywordEnabled("_EMISSION")}" : "";
                        per.Add($"{smr.name}: {smr.bones.Length} bones, {same} Humanoid, {dup} same-name duplicates, root {(smr.rootBone != null ? smr.rootBone.name : "-")}{emis}");
                    }
                    p.skinned_meshes = per.ToArray();
                }
                finally { Object.DestroyImmediate(inst); }
            }
            var repo = RepoRoot(f);
            string outDir = NewFolder(Path.Combine(repo, f.paths.output_root), "probe_rigs");
            File.WriteAllText(Path.Combine(outDir, "rigs.json"), JsonUtility.ToJson(file, true).Replace("\r\n", "\n") + "\n", Utf8);
            return string.Join("; ", file.looks.Select(x => $"{x.id}: bounds {x.renderer_bounds_height_m:0.000} m, head-foot {x.head_minus_foot_m:0.000} m, arm {x.arm_length_m:0.000} m, " +
                                                            $"shoulders {x.shoulder_width_m:0.000} m, ratio {x.arm_to_shoulder_ratio:0.000}, humanScale {x.human_scale:0.000}; {x.arm_bones_skinned} {x.note}")) +
                   $". {Path.GetRelativePath(repo, outDir).Replace('\\', '/')}/rigs.json";
        }

        /// <summary>Command line: -executeMethod WarehouseAvatar.EditorTools.ExperimentLooksMenu.BatchProbeArmSkin: does the mesh of every
        /// prefab-kind look of looks_ab.json follow its Humanoid arm bones (ArmSkinCheck, experiments_ab.md section 5), report only.</summary>
        public static void BatchProbeArmSkin()
        {
            try
            {
                Debug.Log("[ExperimentLooks] " + ProbeArmSkin());
                EditorApplication.Exit(0);
            }
            catch (Exception e)
            {
                Debug.LogError("[ExperimentLooks] FAILED: " + e);
                EditorApplication.Exit(1);
            }
        }

        [Serializable]
        class ArmSkinSide
        {
            public string side, verdict;
            public int arm_vertices, arm_following, hand_vertices, hand_following;
            public float arm_following_fraction, hand_following_fraction, arm_error_median_m, arm_expected_move_median_m;
        }

        [Serializable]
        class ArmSkinLook
        {
            public string id, asset, asset_sha256, verdict, note = "";
            public int skinned_meshes;
            public List<ArmSkinSide> sides = new List<ArmSkinSide>();
        }

        [Serializable] class ArmSkinFile { public string created_local, rule; public List<ArmSkinLook> looks = new List<ArmSkinLook>(); }

        public static string ProbeArmSkin()
        {
            var f = Load(out _);
            var file = new ArmSkinFile
            {
                created_local = DateTime.Now.ToString("yyyy-MM-dd'T'HH:mm:ss", Inv),
                rule = $"experiments_ab.md section 5: upper arm rotated {ArmSkinCheck.RotationDeg.ToString("0", Inv)} deg; a vertex follows within " +
                       $"{ArmSkinCheck.FollowTolerance.ToString("0.00", Inv)} of its expected displacement; a side follows at >= {ArmSkinCheck.PassFraction.ToString("0.00", Inv)} " +
                       $"of its arm-region vertices (at least {ArmSkinCheck.MinArmVertices})",
            };
            foreach (var l in f.looks)
            {
                if (l == null || l.kind != LookEntry.KindPrefab) continue;
                var p = new ArmSkinLook { id = l.id, asset = l.asset, verdict = ArmSkinCheck.Inconclusive };
                file.looks.Add(p);
                string path = Path.Combine(Application.dataPath, "..", l.asset);
                var go = AssetDatabase.LoadAssetAtPath<GameObject>(l.asset);
                if (go == null || !File.Exists(path)) { p.note = "not installed"; continue; }
                p.asset_sha256 = Sha256(File.ReadAllBytes(path));
                var inst = (GameObject)Object.Instantiate(go);
                try
                {
                    inst.transform.SetPositionAndRotation(Vector3.zero, Quaternion.identity);
                    var a = inst.GetComponentInChildren<Animator>();
                    if (a == null || a.avatar == null || !a.avatar.isHuman) { p.note = "no Humanoid Animator"; continue; }
                    var smrs = inst.GetComponentsInChildren<SkinnedMeshRenderer>(true);
                    p.skinned_meshes = smrs.Length;
                    var verdicts = new List<string>();
                    foreach (bool left in new[] { true, false })
                    {
                        Transform u = a.GetBoneTransform(left ? HumanBodyBones.LeftUpperArm : HumanBodyBones.RightUpperArm);
                        Transform lo = a.GetBoneTransform(left ? HumanBodyBones.LeftLowerArm : HumanBodyBones.RightLowerArm);
                        Transform h = a.GetBoneTransform(left ? HumanBodyBones.LeftHand : HumanBodyBones.RightHand);
                        string side = left ? "left" : "right";
                        if (u == null || lo == null || h == null) { p.note += $" {side} arm bones not mapped."; verdicts.Add(ArmSkinCheck.Inconclusive); continue; }
                        var r = ArmSkinCheck.MeasureSide(u, lo, h, smrs);
                        p.sides.Add(new ArmSkinSide
                        {
                            side = side, verdict = r.Verdict, arm_vertices = r.ArmVertices, arm_following = r.ArmFollowing,
                            hand_vertices = r.HandVertices, hand_following = r.HandFollowing,
                            arm_following_fraction = r.ArmVertices > 0 ? (float)r.ArmFollowing / r.ArmVertices : -1f,
                            hand_following_fraction = r.HandVertices > 0 ? (float)r.HandFollowing / r.HandVertices : -1f,
                            arm_error_median_m = r.ArmErrorMedianM, arm_expected_move_median_m = r.ArmExpectedMoveMedianM,
                        });
                        verdicts.Add(r.Verdict);
                    }
                    p.verdict = ArmSkinCheck.LookVerdict(verdicts);
                    p.note = p.note.Trim();
                }
                finally { Object.DestroyImmediate(inst); }
            }
            var repo = RepoRoot(f);
            string outDir = NewFolder(Path.Combine(repo, f.paths.output_root), "probe_arm_skin");
            File.WriteAllText(Path.Combine(outDir, "arm_skin.json"), JsonUtility.ToJson(file, true).Replace("\r\n", "\n") + "\n", Utf8);
            return string.Join("; ", file.looks.Select(x => $"{x.id} ({(x.asset_sha256 ?? "").Substring(0, Math.Min(8, (x.asset_sha256 ?? "").Length))}): {x.verdict} [" +
                                                            string.Join(", ", x.sides.Select(s => $"{s.side} arm {s.arm_following}/{s.arm_vertices}, hand {s.hand_following}/{s.hand_vertices}")) +
                                                            $"] {x.note}")) +
                   $". {Path.GetRelativePath(repo, outDir).Replace('\\', '/')}/arm_skin.json";
        }

        public static ExperimentLooksFile Load(out string text)
        {
            var asset = AssetDatabase.LoadAssetAtPath<TextAsset>(ExperimentLooks.AssetPath) ?? throw new FileNotFoundException(ExperimentLooks.AssetPath);
            text = asset.text;
            return ExperimentLooks.Parse(text);
        }

        public static string RepoRoot(ExperimentLooksFile f) =>
            Path.GetFullPath(Path.Combine(Application.dataPath, "..", f.paths.repo_root_relative_to_unity_project));

        [Serializable]
        class CharacterReport
        {
            public string id, source_file, source_sha256, asset, status, note = "";
            public bool copied, humanoid, avatar_valid;
            public int human_bones_mapped, finger_bones_mapped;
            public float bone_height_first_m, bone_height_m, human_scale_first, human_scale;
            public string[] finger_bones_missing = new string[0];
            public string[] materials = new string[0];
            public string[] recoloured = new string[0];
            public string[] colourless_unmatched = new string[0];
        }

        [Serializable] class ImportReport { public string created_local, unity_version, render_pipeline; public List<CharacterReport> characters = new List<CharacterReport>(); }

        public static string ImportCharacters()
        {
            var f = Load(out string text);
            if (f.paths == null || string.IsNullOrEmpty(f.paths.characters_source) || string.IsNullOrEmpty(f.paths.import_folder))
                throw new InvalidOperationException("looks_ab.json: paths.characters_source and paths.import_folder are required");
            if (!f.paths.import_folder.StartsWith("Assets/ThirdParty/", StringComparison.Ordinal))
                throw new InvalidOperationException("looks_ab.json paths.import_folder must lie under Assets/ThirdParty/ (git-ignored: character files are never committed)");
            string repo = RepoRoot(f);
            string src = Path.Combine(repo, f.paths.characters_source);
            if (!Directory.Exists(src)) throw new DirectoryNotFoundException(src);
            var report = new ImportReport
            {
                created_local = DateTime.Now.ToString("yyyy-MM-dd'T'HH:mm:ss", Inv), unity_version = Application.unityVersion,
                render_pipeline = UnityEngine.Rendering.GraphicsSettings.currentRenderPipeline != null ? UnityEngine.Rendering.GraphicsSettings.currentRenderPipeline.name : "built-in",
            };
            foreach (string fbx in Directory.GetFiles(src, "*.fbx").OrderBy(p => p, StringComparer.Ordinal))
                report.characters.Add(ImportOne(f, fbx));
            AssetDatabase.SaveAssets();

            string outDir = NewFolder(Path.Combine(repo, f.paths.output_root), "import_characters");
            File.WriteAllText(Path.Combine(outDir, "report.json"), JsonUtility.ToJson(report, true).Replace("\r\n", "\n") + "\n", Utf8);
            File.WriteAllText(Path.Combine(outDir, "looks_ab.json"), text, Utf8);
            return $"{report.characters.Count} characters: " +
                   string.Join("; ", report.characters.Select(c => $"{c.id} {c.status} (humanoid {c.humanoid}, bones {c.human_bones_mapped}, fingers {c.finger_bones_mapped}/30" +
                                                                    (c.recoloured.Length > 0 ? $", recoloured {c.recoloured.Length}" : "") + ")")) +
                   $". Report: {Path.GetRelativePath(repo, outDir).Replace('\\', '/')}/report.json";
        }

        static CharacterReport ImportOne(ExperimentLooksFile f, string fbx)
        {
            string id = Path.GetFileNameWithoutExtension(fbx);
            var r = new CharacterReport { id = id, source_file = Path.GetFileName(fbx), source_sha256 = Sha256(File.ReadAllBytes(fbx)) };
            if (!LookCheckConfig.IsNamePart(id)) { r.status = "refused"; r.note = "the file name is not a look id (a-z, 0-9, single '_')"; return r; }
            string folder = f.paths.import_folder + "/" + id;
            r.asset = folder + "/" + id + ".fbx";
            string dest = Path.Combine(Application.dataPath, "..", r.asset);
            Directory.CreateDirectory(Path.GetDirectoryName(dest));
            if (File.Exists(dest))
            {
                if (Sha256(File.ReadAllBytes(dest)) != r.source_sha256) { r.status = "refused"; r.note = r.asset + " exists and differs from the download (never overwritten)"; return r; }
            }
            else
            {
                File.Copy(fbx, dest);
                r.copied = true;
            }
            AssetDatabase.ImportAsset(r.asset, ImportAssetOptions.ForceSynchronousImport);
            var imp = AssetImporter.GetAtPath(r.asset) as ModelImporter ?? throw new InvalidOperationException(r.asset + " is not a model");
            bool changed = false;
            if (imp.animationType != ModelImporterAnimationType.Human) { imp.animationType = ModelImporterAnimationType.Human; changed = true; }
            if (imp.avatarSetup != ModelImporterAvatarSetup.CreateFromThisModel) { imp.avatarSetup = ModelImporterAvatarSetup.CreateFromThisModel; changed = true; }
            if (imp.materialImportMode == ModelImporterMaterialImportMode.None) { imp.materialImportMode = ModelImporterMaterialImportMode.ImportViaMaterialDescription; changed = true; }
            if (changed) imp.SaveAndReimport();

            // textures and materials next to the model, so they can be recoloured and inspected
            string texDir = folder + "/Textures";
            if (!AssetDatabase.IsValidFolder(texDir)) AssetDatabase.CreateFolder(folder, "Textures");
            int texturesBefore = ImageFiles(texDir);
            imp.ExtractTextures(texDir);
            string matDir = folder + "/Materials";
            if (!AssetDatabase.IsValidFolder(matDir)) AssetDatabase.CreateFolder(folder, "Materials");
            int renamed = GiveExtensions(texDir);
            int extracted = Math.Max(0, ImageFiles(texDir) - texturesBefore);
            if (renamed > 0 || extracted > 0)
            {
                // experiments_ab.md section 2: images without a file extension get the extension of their format; the materials are then
                // re-created so ExperimentCharacterPostprocessor can link the textures (the earlier extracted copies are forgotten, not the
                // recoloured ones). Section 5 addendum: also when this import extracted the textures (the model's first import saw none)
                if (renamed > 0) r.note += $" {renamed} extracted images had no file extension and were given the extension of their format.";
                if (extracted > 0) r.note += $" {extracted} textures extracted by this import: materials re-created to link them.";
                AssetDatabase.Refresh(ImportAssetOptions.ForceSynchronousImport);
                foreach (var kv in imp.GetExternalObjectMap().ToList())
                {
                    string p = kv.Value != null ? AssetDatabase.GetAssetPath(kv.Value) : "";
                    if (kv.Key.type != typeof(Material) || !p.StartsWith(matDir + "/", StringComparison.Ordinal)) continue;
                    imp.RemoveRemap(kv.Key);
                    AssetDatabase.DeleteAsset(p);
                }
                imp.SaveAndReimport();
            }
            foreach (var m in AssetDatabase.LoadAllAssetsAtPath(r.asset).OfType<Material>().ToList())
            {
                string mp = matDir + "/" + Safe(m.name) + ".mat";
                if (File.Exists(Path.Combine(Application.dataPath, "..", mp))) continue;
                string err = AssetDatabase.ExtractAsset(m, mp);
                if (!string.IsNullOrEmpty(err)) r.note += $" material {m.name}: {err}.";
            }
            AssetDatabase.WriteImportSettingsIfDirty(r.asset);
            AssetDatabase.ImportAsset(r.asset, ImportAssetOptions.ForceUpdate | ImportAssetOptions.ForceSynchronousImport);
            // experiments_ab.md section 2, emission: pure-white emission without an emission map is an export artefact (a white glow)
            int unlit = 0;
            foreach (var guid in AssetDatabase.FindAssets("t:Material", new[] { matDir }))
            {
                var m = AssetDatabase.LoadAssetAtPath<Material>(AssetDatabase.GUIDToAssetPath(guid));
                if (m == null || !m.HasProperty("_EmissionColor") || !m.IsKeywordEnabled("_EMISSION")) continue;
                var e = m.GetColor("_EmissionColor");
                bool map = m.HasProperty("_EmissionMap") && m.GetTexture("_EmissionMap") != null;
                if (map || e.r < 0.99f || e.g < 0.99f || e.b < 0.99f) continue;
                m.SetColor("_EmissionColor", Color.black);
                m.DisableKeyword("_EMISSION");
                m.globalIlluminationFlags = MaterialGlobalIlluminationFlags.EmissiveIsBlack;
                EditorUtility.SetDirty(m);
                unlit++;
            }
            if (unlit > 0) { AssetDatabase.SaveAssets(); r.note += $" Emission switched off on {unlit} materials (pure white, no emission map)."; }

            var spec = f.recolour?.FirstOrDefault(x => x != null && x.look == id);
            if (spec != null) Recolour(spec, matDir, r);
            FixUnitScale(r);

            var go = AssetDatabase.LoadAssetAtPath<GameObject>(r.asset);
            var avatar = AssetDatabase.LoadAllAssetsAtPath(r.asset).OfType<Avatar>().FirstOrDefault();
            r.humanoid = avatar != null && avatar.isHuman;
            r.avatar_valid = avatar != null && avatar.isValid;
            if (go != null && r.humanoid)
            {
                var inst = (GameObject)Object.Instantiate(go);
                try
                {
                    var animator = inst.GetComponentInChildren<Animator>();
                    if (animator != null && animator.avatar == null) animator.avatar = avatar;
                    if (animator != null)
                    {
                        int mapped = 0;
                        for (var b = HumanBodyBones.Hips; b < HumanBodyBones.LastBone; b++) if (animator.GetBoneTransform(b) != null) mapped++;
                        r.human_bones_mapped = mapped;
                        var missing = LookInventory.FingerBones.Where(b => animator.GetBoneTransform(b) == null).Select(b => b.ToString()).ToArray();
                        r.finger_bones_mapped = LookInventory.FingerBones.Length - missing.Length;
                        r.finger_bones_missing = missing;
                    }
                    r.materials = inst.GetComponentsInChildren<Renderer>(true).SelectMany(x => x.sharedMaterials)
                        .Where(m => m != null).Select(m => $"{m.name} [{(m.shader != null ? m.shader.name : "no shader")}]").Distinct().ToArray();
                }
                finally { Object.DestroyImmediate(inst); }
            }
            r.status = !r.humanoid ? "not_humanoid" : !r.avatar_valid ? "avatar_invalid" : "ok";
            r.note = r.note.Trim();
            return r;
        }

        /// <summary>experiments_ab.md section 2, unit scale: a Humanoid model whose head-to-foot bone height lies outside [0.5, 2.5] m
        /// gets the importer scale factor (power of ten) that brings it inside; nothing else is changed. Idempotent: a model already
        /// inside is left alone.</summary>
        static void FixUnitScale(CharacterReport r)
        {
            float h = BoneHeight(r.asset);
            r.bone_height_first_m = h;
            r.bone_height_m = h;
            var imp = (ModelImporter)AssetImporter.GetAtPath(r.asset);
            if (h > 0f && (h < 0.5f || h > 2.5f))
            {
                float factor = Mathf.Pow(10f, Mathf.Round(Mathf.Log10(1.5f / h)));
                imp.globalScale = imp.globalScale * factor;
                imp.SaveAndReimport();
                r.bone_height_m = BoneHeight(r.asset);
                r.note += $" Unit scale: head-to-foot {h.ToString("0.000", Inv)} m -> importer scale factor x{factor.ToString("0.###", Inv)} (globalScale {imp.globalScale.ToString("0.###", Inv)}), now {r.bone_height_m.ToString("0.000", Inv)} m.";
            }
            // The Humanoid avatar keeps the skeleton description of the import it was built in: after a scale change it describes a
            // 1/100 skeleton and Mecanim poses the model 100 times too high at Play (humanScale ~100). Rebuild it from the scaled model.
            float hs = HumanScale(r.asset);
            r.human_scale_first = hs;
            r.human_scale = hs;
            if (imp.globalScale != 1f && hs > 0f && (hs < 0.5f || hs > 2f))
            {
                imp.animationType = ModelImporterAnimationType.Generic;
                imp.humanDescription = new HumanDescription();
                imp.SaveAndReimport();
                imp.animationType = ModelImporterAnimationType.Human;
                imp.avatarSetup = ModelImporterAvatarSetup.CreateFromThisModel;
                imp.SaveAndReimport();
                r.human_scale = HumanScale(r.asset);
                r.note += $" Humanoid avatar rebuilt from the scaled model: humanScale {hs.ToString("0.000", Inv)} -> {r.human_scale.ToString("0.000", Inv)}.";
            }
        }

        static float HumanScale(string asset)
        {
            var go = AssetDatabase.LoadAssetAtPath<GameObject>(asset);
            if (go == null) return -1f;
            var inst = (GameObject)Object.Instantiate(go);
            try
            {
                var a = inst.GetComponentInChildren<Animator>();
                return a != null && a.avatar != null && a.avatar.isHuman ? a.humanScale : -1f;
            }
            finally { Object.DestroyImmediate(inst); }
        }

        /// <summary>Head bone minus left foot bone height of the model as imported (metres), -1 without a Humanoid avatar.</summary>
        static float BoneHeight(string asset)
        {
            var go = AssetDatabase.LoadAssetAtPath<GameObject>(asset);
            if (go == null) return -1f;
            var inst = (GameObject)Object.Instantiate(go);
            try
            {
                var a = inst.GetComponentInChildren<Animator>();
                if (a == null || a.avatar == null || !a.avatar.isHuman) return -1f;
                Transform head = a.GetBoneTransform(HumanBodyBones.Head), foot = a.GetBoneTransform(HumanBodyBones.LeftFoot);
                return head != null && foot != null ? head.position.y - foot.position.y : -1f;
            }
            finally { Object.DestroyImmediate(inst); }
        }

        /// <summary>Colourless materials of the model (no base texture, base colour saturation at most the spec's limit) get a new URP Lit
        /// material of the first rule whose keyword is in the material's name, remapped on the model importer.</summary>
        static void Recolour(RecolourSpec spec, string matDir, CharacterReport r)
        {
            var lit = Shader.Find("Universal Render Pipeline/Lit") ?? throw new InvalidOperationException("URP Lit shader not found");
            var imp = (ModelImporter)AssetImporter.GetAtPath(r.asset);
            var done = new List<string>();
            var unmatched = new List<string>();
            string recDir = Path.GetDirectoryName(matDir).Replace('\\', '/') + "/Recoloured";
            // the model's source materials: those remapped to extracted .mat files and any still embedded
            var sources = new Dictionary<string, Material>(StringComparer.Ordinal);
            foreach (var kv in imp.GetExternalObjectMap())
                if (kv.Key.type == typeof(Material)) sources[kv.Key.name] = kv.Value as Material;
            foreach (var m in AssetDatabase.LoadAllAssetsAtPath(r.asset).OfType<Material>())
                if (!sources.ContainsKey(m.name)) sources[m.name] = m;
            foreach (var kv in sources.OrderBy(x => x.Key, StringComparer.Ordinal))
            {
                string name = kv.Key;
                if (kv.Value != null && AssetDatabase.GetAssetPath(kv.Value).StartsWith(recDir + "/", StringComparison.Ordinal))
                {
                    done.Add($"{name} (recoloured earlier)");
                    continue;
                }
                if (!Colourless(kv.Value, spec.colourless_saturation_max)) continue;
                string lower = name.ToLowerInvariant();
                var rule = spec.rules.FirstOrDefault(x => x.keywords.Any(k => lower.Contains(k.ToLowerInvariant())));
                if (rule == null || rule.rgb.Length != 3) { unmatched.Add(name); continue; }
                if (!AssetDatabase.IsValidFolder(recDir)) AssetDatabase.CreateFolder(Path.GetDirectoryName(recDir).Replace('\\', '/'), "Recoloured");
                string path = recDir + "/" + Safe(name) + ".mat";
                var mat = AssetDatabase.LoadAssetAtPath<Material>(path);
                if (mat == null)
                {
                    mat = new Material(lit) { name = name };
                    var c = new Color(rule.rgb[0], rule.rgb[1], rule.rgb[2], 1f);
                    mat.SetColor("_BaseColor", c);
                    mat.color = c;
                    AssetDatabase.CreateAsset(mat, path);
                }
                imp.AddRemap(new AssetImporter.SourceAssetIdentifier(typeof(Material), name), mat);
                done.Add($"{name} -> rgb({string.Join(", ", rule.rgb.Select(v => v.ToString("0.00", Inv)))})");
            }
            if (done.Count > 0) imp.SaveAndReimport();
            r.recoloured = done.ToArray();
            r.colourless_unmatched = unmatched.ToArray();
        }

        public static bool Colourless(Material m, float saturationMax)
        {
            if (m == null) return true;
            Texture tex = m.HasProperty("_BaseMap") ? m.GetTexture("_BaseMap") : m.HasProperty("_MainTex") ? m.GetTexture("_MainTex") : null;
            if (tex != null) return false;
            Color c = m.HasProperty("_BaseColor") ? m.GetColor("_BaseColor") : m.HasProperty("_Color") ? m.GetColor("_Color") : Color.white;
            Color.RGBToHSV(c, out _, out float s, out _);
            return s <= saturationMax;
        }

        /// <summary>Files of an asset folder without an extension that are PNG or JPEG images (by their magic bytes) get that extension; the
        /// old .meta is removed so Unity imports them as textures. Returns how many were renamed.</summary>
        static int GiveExtensions(string assetFolder)
        {
            string dir = Path.Combine(Application.dataPath, "..", assetFolder);
            if (!Directory.Exists(dir)) return 0;
            int n = 0;
            foreach (var f in Directory.GetFiles(dir))
            {
                if (Path.GetExtension(f).Length > 0) continue;
                var head = new byte[4];
                using (var s = File.OpenRead(f)) if (s.Read(head, 0, 4) < 4) continue;
                string ext = head[0] == 0x89 && head[1] == 0x50 && head[2] == 0x4E && head[3] == 0x47 ? ".png"
                           : head[0] == 0xFF && head[1] == 0xD8 && head[2] == 0xFF ? ".jpg" : "";
                if (ext.Length == 0 || File.Exists(f + ext)) continue;
                File.Move(f, f + ext);
                if (File.Exists(f + ".meta")) File.Delete(f + ".meta");
                n++;
            }
            return n;
        }

        /// <summary>Image files (any file but .meta) in an asset folder; 0 if it does not exist.</summary>
        static int ImageFiles(string assetFolder)
        {
            string dir = Path.Combine(Application.dataPath, "..", assetFolder);
            return Directory.Exists(dir) ? Directory.GetFiles(dir).Count(p => !p.EndsWith(".meta", StringComparison.Ordinal)) : 0;
        }

        static string Safe(string name) => new string(name.Select(ch => Path.GetInvalidFileNameChars().Contains(ch) ? '_' : ch).ToArray());

        static string Sha256(byte[] b)
        {
            using (var h = SHA256.Create()) return string.Concat(h.ComputeHash(b).Select(x => x.ToString("x2")));
        }

        static string NewFolder(string root, string prefix)
        {
            string stamp = DateTime.Now.ToString("yyyyMMdd_HHmmss", Inv);
            string dir = Path.Combine(root, prefix + "_" + stamp);
            for (int i = 1; Directory.Exists(dir); i++) dir = Path.Combine(root, $"{prefix}_{stamp}_{i}");
            Directory.CreateDirectory(dir);
            return dir;
        }
    }
}
