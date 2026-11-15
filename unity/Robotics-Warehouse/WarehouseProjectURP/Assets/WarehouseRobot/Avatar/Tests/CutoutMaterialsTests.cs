using System.Linq;
using NUnit.Framework;
using UnityEngine;
using UnityEngine.Rendering;

namespace WarehouseAvatar.Tests
{
    /// <summary>Alpha clipping of imported character materials (Avatar/Config/experiments_ab.md section 11 item 4).</summary>
    public class CutoutMaterialsTests
    {
        static Color32[] Texels(int total, int clear) =>
            Enumerable.Range(0, total).Select(i => new Color32(0, 0, 0, (byte)(i < clear ? 0 : 255))).ToArray();

        [Test]
        public void ClearFraction_CountsTexelsBelowHalfAlpha()
        {
            Assert.AreEqual(0f, CutoutMaterials.ClearFraction(Texels(100, 0)));
            Assert.AreEqual(0.25f, CutoutMaterials.ClearFraction(Texels(100, 25)), 1e-6f);
            var edge = new[] { new Color32(0, 0, 0, 127), new Color32(0, 0, 0, 128) };
            Assert.AreEqual(0.5f, CutoutMaterials.ClearFraction(edge), 1e-6f, "127 is below 0.5, 128 is not");
            Assert.AreEqual(0f, CutoutMaterials.ClearFraction(new Color32[0]));
        }

        [Test]
        public void CutoutMask_NeedsAtLeastOneTexelInAThousand()
        {
            Assert.IsFalse(CutoutMaterials.HasCutoutMask(Texels(10000, 9)), "0.09 %: an opaque texture with stray texels");
            Assert.IsTrue(CutoutMaterials.HasCutoutMask(Texels(10000, 10)), "0.1 %");
            Assert.IsTrue(CutoutMaterials.HasCutoutMask(Texels(10000, 9570)), "a VRoid dress texture (95.7 %)");
            Assert.IsFalse(CutoutMaterials.HasCutoutMask(Texels(10000, 0)));
        }

        [Test]
        public void ApplyAlphaClip_SetsUrpAlphaClipping_AndLeavesOtherShadersAlone()
        {
            var lit = Shader.Find("Universal Render Pipeline/Lit");
            Assert.IsNotNull(lit, "URP Lit");
            var m = new Material(lit);
            var other = new Material(Shader.Find("Unlit/Color"));
            try
            {
                Assert.IsTrue(CutoutMaterials.ApplyAlphaClip(m));
                Assert.AreEqual(1f, m.GetFloat("_AlphaClip"));
                Assert.AreEqual(0.5f, m.GetFloat("_Cutoff"));
                Assert.IsTrue(m.IsKeywordEnabled("_ALPHATEST_ON"));
                Assert.AreEqual((int)RenderQueue.AlphaTest, m.renderQueue);
                Assert.AreEqual("TransparentCutout", m.GetTag("RenderType", false));
                Assert.AreEqual(0f, m.GetFloat("_Surface"), "the surface stays opaque (no blending)");
                int queue = other.renderQueue;
                Assert.IsFalse(CutoutMaterials.ApplyAlphaClip(other));
                Assert.AreEqual(queue, other.renderQueue);
                Assert.IsFalse(CutoutMaterials.ApplyAlphaClip(null));
            }
            finally
            {
                Object.DestroyImmediate(m);
                Object.DestroyImmediate(other);
            }
        }
    }
}
