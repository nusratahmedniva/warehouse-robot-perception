using System.Collections.Generic;
using System.IO;
using UnityEditor;
using UnityEditor.AssetImporters;
using UnityEngine;

namespace WarehouseAvatar.EditorTools
{
    /// <summary>
    /// Experiments A/B import (Avatar/Config/experiments_ab.md section 2, "Embedded textures without a file extension"): for a model under
    /// the experiment import folder (Assets/ThirdParty/CharactersV4/, git-ignored) whose material names a base texture Unity could not
    /// resolve, link the texture of that name from the model's Textures/ folder (the importer's extracted images, given their extension by
    /// ExperimentLooksMenu). Runs after the render pipeline's own material-description preprocessor; touches nothing else.
    /// </summary>
    public class ExperimentCharacterPostprocessor : AssetPostprocessor
    {
        public const string Folder = "Assets/ThirdParty/CharactersV4/";
        static readonly string[] Extensions = { ".png", ".jpg", ".jpeg", ".tga" };

        public override int GetPostprocessOrder() => 100;

        /// <summary>experiments_ab.md section 12 addendum 7 decision 2: looks_ab.json rigid_parts, applied on every import of that model (never
        /// by hand): the named materials' vertices bound 100 % to one bone.</summary>
        void OnPostprocessModel(GameObject g)
        {
            if (!assetPath.StartsWith(Folder, System.StringComparison.Ordinal)) return;
            string cfg = Path.Combine(Application.dataPath, "..", ExperimentLooks.AssetPath);
            if (!File.Exists(cfg)) return;
            string id = Path.GetFileNameWithoutExtension(assetPath);
            var looks = ExperimentLooks.Parse(File.ReadAllText(cfg));
            var spec = System.Array.Find(looks.rigid_parts, r => r != null && r.look == id);
            var hands = System.Array.Find(looks.island_hands, r => r != null && r.look == id);
            if (spec == null && hands == null) return;
            var smrs = g.GetComponentsInChildren<SkinnedMeshRenderer>(true);
            foreach (var smr in smrs)
            {
                var names = System.Array.ConvertAll(smr.sharedMaterials, m => m != null ? m.name : "");
                if (spec == null) continue;
                var done = ExperimentLooks.BindRigid(smr.sharedMesh, smr.bones, names, spec);
                if (done.Count > 0) Debug.Log($"[ExperimentLooks] {id}: rigid parts bound to {spec.bone}: {string.Join(", ", done)}");
            }
            if (hands != null && hands.move_joints)
            {
                // section 12 addendum 11: the finger chains moved onto their finger groups' axes, then the moved bones' bind poses recomputed
                var moved = new System.Collections.Generic.List<Transform>();
                foreach (var smr in smrs)
                {
                    var names = System.Array.ConvertAll(smr.sharedMaterials, m => m != null ? m.name : "");
                    var log = IslandHands.AlignChains(smr.sharedMesh, smr.bones, names, hands, smr.transform.worldToLocalMatrix, smr.transform.localToWorldMatrix,
                                                      smr.transform.lossyScale.x, moved);
                    if (log.Count > 0) Debug.Log($"[ExperimentLooks] {id}: chains aligned: {string.Join("; ", log)}");
                }
                foreach (var smr in smrs)
                {
                    var mesh = smr.sharedMesh;
                    var bones = smr.bones;
                    if (mesh == null || bones == null) continue;
                    var bp = mesh.bindposes;
                    for (int i = 0; i < bones.Length && i < bp.Length; i++)
                        if (bones[i] != null && moved.Contains(bones[i])) bp[i] = bones[i].worldToLocalMatrix * smr.transform.localToWorldMatrix;
                    mesh.bindposes = bp;
                }
            }
            foreach (var smr in smrs)
            {
                var names = System.Array.ConvertAll(smr.sharedMaterials, m => m != null ? m.name : "");
                if (hands != null)
                {
                    // section 12 addendum 9: the hands by their mesh islands (the imported hierarchy is at the bind pose here)
                    var bound = IslandHands.Bind(smr.sharedMesh, smr.bones, names, hands, smr.transform.worldToLocalMatrix, smr.transform.lossyScale.x);
                    foreach (var h in bound)
                        Debug.Log($"[ExperimentLooks] {id}: {h.Hand} bound by islands: plate {h.Plate} on the hand bone, fingers {string.Join(", ", h.Fingers)}" +
                                  (h.Problem.Length > 0 ? $"; PROBLEM: {h.Problem}" : ""));
                }
            }
        }

        void OnPreprocessMaterialDescription(MaterialDescription description, Material material, AnimationClip[] clips)
        {
            if (!assetPath.StartsWith(Folder, System.StringComparison.Ordinal)) return;
            if (material.HasProperty("_BaseMap") && material.GetTexture("_BaseMap") != null) return;
            var names = new List<string>();
            description.GetTexturePropertyNames(names);
            foreach (var p in names)
            {
                string lower = p.ToLowerInvariant();
                if (!(lower.Contains("diffuse") || lower.Contains("basecolor") || lower.Contains("albedo") || lower == "maintex")) continue;
                if (!description.TryGetProperty(p, out TexturePropertyDescription t)) continue;
                var tex = t.texture != null ? t.texture : Find(Path.GetDirectoryName(assetPath).Replace('\\', '/') + "/Textures", t.relativePath, t.path);
                if (tex == null) continue;
                if (material.HasProperty("_BaseMap")) material.SetTexture("_BaseMap", tex);
                if (material.HasProperty("_MainTex")) material.SetTexture("_MainTex", tex);
                return;
            }
        }

        static Texture Find(string folder, params string[] refs)
        {
            foreach (var r in refs)
            {
                if (string.IsNullOrEmpty(r)) continue;
                string name = Path.GetFileName(r.Replace('\\', '/'));
                string stem = Path.GetFileNameWithoutExtension(name);
                foreach (var candidate in new[] { name, stem })
                    foreach (var ext in Extensions)
                    {
                        var tex = AssetDatabase.LoadAssetAtPath<Texture>(folder + "/" + Path.GetFileNameWithoutExtension(candidate) + ext);
                        if (tex != null) return tex;
                    }
            }
            return null;
        }
    }
}
