using UnityEngine;
using UnityEngine.Rendering;

namespace WarehouseAvatar
{
    /// <summary>
    /// Alpha clipping of imported character materials (Avatar/Config/experiments_ab.md section 11 item 4, declared before the change). A VRoid
    /// export keeps each material's cut-out mask in its base texture's alpha channel, but the FBX conversion links it (TransparencyFactor) on
    /// a few face and eye materials only, so the clothing imported Opaque and showed its clear texels (black underneath) as black patches. A
    /// material whose base texture has at least <see cref="MinClearFraction"/> of its texels below alpha <see cref="Cutoff"/> gets URP's
    /// alpha clipping at that cutoff (URP's and glTF's default); the surface stays opaque (no blending).
    /// </summary>
    public static class CutoutMaterials
    {
        public const float Cutoff = 0.5f;
        public const float MinClearFraction = 0.001f;

        /// <summary>The fraction of texels whose alpha lies below the cutoff (alpha byte &lt; 128 = below 0.5).</summary>
        public static float ClearFraction(Color32[] texels)
        {
            if (texels == null || texels.Length == 0) return 0f;
            int clear = 0;
            foreach (var c in texels) if (c.a < 128) clear++;
            return (float)clear / texels.Length;
        }

        public static bool HasCutoutMask(Color32[] texels) => ClearFraction(texels) >= MinClearFraction;

        /// <summary>URP Lit alpha clipping: _AlphaClip on, _Cutoff, the keyword, the AlphaTest queue and the TransparentCutout tag. Returns false
        /// for a material without URP's alpha-clip properties (left unchanged).</summary>
        public static bool ApplyAlphaClip(Material m)
        {
            if (m == null || !m.HasProperty("_AlphaClip") || !m.HasProperty("_Cutoff")) return false;
            m.SetFloat("_AlphaClip", 1f);
            m.SetFloat("_Cutoff", Cutoff);
            m.EnableKeyword("_ALPHATEST_ON");
            m.SetOverrideTag("RenderType", "TransparentCutout");
            m.renderQueue = (int)RenderQueue.AlphaTest;
            return true;
        }
    }
}
