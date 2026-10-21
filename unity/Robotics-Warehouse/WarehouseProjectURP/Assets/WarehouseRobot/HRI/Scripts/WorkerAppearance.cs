using System.Collections.Generic;
using System.Security.Cryptography;
using System.Text;
using UnityEngine;
using UnityEngine.Rendering;

namespace WarehouseHRI
{
    /// <summary>
    /// Checks that the worker renders as the textured Mixamo avatar (environment check, 2026-10-21). The trial runner
    /// refuses every session (development, final, any task) while Problems() is not empty: a magenta or untextured
    /// worker is a different stimulus for the person detector and the pose model than the one Task 2 was run with.
    /// Causes it catches: a missing material (the scene references a git-ignored material that does not exist on this
    /// machine), Unity's error shader, a shader with no pass for the active render pipeline (e.g. Built-in Standard under
    /// URP), a material without its base texture (Mixamo textures not extracted), a worker that is not Humanoid.
    /// </summary>
    public static class WorkerAppearance
    {
        public const string ErrorShaderName = "Hidden/InternalErrorShader";
        public const string Fix = "Run Tools > Warehouse HRI > Restore Worker Appearance (Unity, edit mode), then press Play again.";
        static readonly string[] k_BaseTextures = { "_BaseMap", "_MainTex" };
        static readonly HashSet<string> k_SrpLightModes = new HashSet<string> { "", "SRPDefaultUnlit", "UniversalForward", "UniversalForwardOnly" };

        /// <summary>Everything that makes the worker render differently from the textured avatar; empty = fine.</summary>
        public static List<string> Problems(GameObject worker, bool requireHumanoid = true)
        {
            var problems = new List<string>();
            if (worker == null)
            {
                problems.Add("no worker");
                return problems;
            }

            var renderers = worker.GetComponentsInChildren<Renderer>(true);
            if (renderers.Length == 0) problems.Add($"{worker.name}: no renderer");
            bool srp = GraphicsSettings.currentRenderPipeline != null;
            foreach (var r in renderers)
            {
                var mats = r.sharedMaterials;
                if (mats.Length == 0) problems.Add($"{Path(r.transform)}: no material");
                for (int i = 0; i < mats.Length; i++)
                {
                    var m = mats[i];
                    string where = $"{Path(r.transform)} material {i}";
                    if (m == null)
                    {
                        problems.Add($"{where}: missing (renders magenta; the referenced material asset is not on this machine)");
                        continue;
                    }

                    var shader = m.shader;
                    if (shader == null || shader.name == ErrorShaderName)
                    {
                        problems.Add($"{where} '{m.name}': Unity's error shader (renders magenta)");
                        continue;
                    }

                    if (!shader.isSupported) problems.Add($"{where} '{m.name}': shader '{shader.name}' not supported on this GPU");
                    else if (srp && !HasSrpPass(m)) problems.Add($"{where} '{m.name}': shader '{shader.name}' has no pass for the active render pipeline (renders magenta)");
                    if (BaseTexture(m) == null) problems.Add($"{where} '{m.name}': no base texture (Mixamo textures missing or not extracted)");
                }
            }

            if (requireHumanoid)
            {
                var animator = worker.GetComponentInChildren<Animator>(true);
                if (animator == null || animator.avatar == null || !animator.avatar.isHuman)
                    problems.Add($"{worker.name}: no Humanoid avatar (worker.fbx Rig > Animation Type must be Humanoid); the gesture poses need it");
            }

            return problems;
        }

        /// <summary>The material's base colour texture (_BaseMap in URP, _MainTex otherwise), or null.</summary>
        public static Texture BaseTexture(Material m)
        {
            foreach (var p in k_BaseTextures)
                if (m.HasProperty(p) && m.GetTexture(p) != null) return m.GetTexture(p);
            return null;
        }

        static bool HasSrpPass(Material m)
        {
            var tag = new ShaderTagId("LightMode");
            for (int i = 0; i < m.passCount; i++)
                if (k_SrpLightModes.Contains(m.shader.FindPassTagValue(i, tag).name)) return true;
            return false;
        }

        /// <summary>One line per renderer: materials, shaders and base textures (for session.json).</summary>
        public static string Describe(GameObject worker)
        {
            var sb = new StringBuilder();
            if (worker == null) return "";
            foreach (var r in worker.GetComponentsInChildren<Renderer>(true))
            {
                if (sb.Length > 0) sb.Append("; ");
                sb.Append(r.name).Append(": ");
                var parts = new List<string>();
                foreach (var m in r.sharedMaterials)
                {
                    if (m == null) { parts.Add("missing"); continue; }
                    var t = BaseTexture(m);
                    parts.Add($"{m.name} [{(m.shader != null ? m.shader.name : "no shader")}] {(t != null ? $"{t.name} {t.width}x{t.height}" : "no texture")}");
                }
                sb.Append(string.Join(", ", parts));
            }
            return sb.ToString();
        }

        /// <summary>Humanoid mapping as "HumanBone=transform name" lines, in HumanBodyBones order (unmapped bones skipped).</summary>
        public static string BoneMap(Animator animator)
        {
            if (animator == null || !animator.isHuman) return "";
            var sb = new StringBuilder();
            for (var b = HumanBodyBones.Hips; b < HumanBodyBones.LastBone; b++)
            {
                var t = animator.GetBoneTransform(b);
                if (t != null) sb.Append(b).Append('=').Append(t.name).Append('\n');
            }
            return sb.ToString();
        }

        public static string Sha256(string text)
        {
            using (var sha = SHA256.Create())
            {
                var sb = new StringBuilder(64);
                foreach (var x in sha.ComputeHash(new UTF8Encoding(false).GetBytes(text ?? ""))) sb.Append(x.ToString("x2"));
                return sb.ToString();
            }
        }

        static string Path(Transform t)
        {
            var parts = new List<string>();
            for (; t != null; t = t.parent) parts.Add(t.name);
            parts.Reverse();
            return string.Join("/", parts);
        }
    }
}
