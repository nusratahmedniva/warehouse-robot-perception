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
