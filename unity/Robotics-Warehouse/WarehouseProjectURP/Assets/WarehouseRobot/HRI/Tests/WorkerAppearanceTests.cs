using System.Collections.Generic;
using NUnit.Framework;
using UnityEngine;

namespace WarehouseHRI.Tests
{
    /// <summary>The worker appearance check that refuses trial sessions (missing material, error shader, no texture).</summary>
    public class WorkerAppearanceTests
    {
        readonly List<Object> m_Created = new List<Object>();

        GameObject Worker(Material material)
        {
            var go = GameObject.CreatePrimitive(PrimitiveType.Capsule);
            Object.DestroyImmediate(go.GetComponent<Collider>());
            go.GetComponent<Renderer>().sharedMaterial = material;
            m_Created.Add(go);
            return go;
        }

        Material Mat(string shader, bool texture)
        {
            var s = Shader.Find(shader);
            Assert.IsNotNull(s, shader);
            var m = new Material(s);
            m_Created.Add(m);
            if (texture)
            {
                var t = new Texture2D(4, 4);
                m_Created.Add(t);
                m.SetTexture(m.HasProperty("_BaseMap") ? "_BaseMap" : "_MainTex", t);
            }
            return m;
        }

        [TearDown]
        public void Clean()
        {
            foreach (var o in m_Created) Object.DestroyImmediate(o);
            m_Created.Clear();
        }

        [Test]
        public void TexturedUrpLitPasses()
        {
            Assert.IsEmpty(WorkerAppearance.Problems(Worker(Mat("Universal Render Pipeline/Lit", true)), requireHumanoid: false));
        }

        [Test]
        public void MissingMaterialIsRefused()
        {
            var p = WorkerAppearance.Problems(Worker(null), requireHumanoid: false);
            Assert.AreEqual(1, p.Count);
            StringAssert.Contains("missing", p[0]);
        }

        [Test]
        public void ErrorShaderIsRefused()
        {
            var p = WorkerAppearance.Problems(Worker(Mat(WorkerAppearance.ErrorShaderName, false)), requireHumanoid: false);
            Assert.IsTrue(p.Exists(x => x.Contains("error shader")), string.Join("; ", p));
        }

        [Test]
        public void UntexturedMaterialIsRefused()
        {
            var p = WorkerAppearance.Problems(Worker(Mat("Universal Render Pipeline/Lit", false)), requireHumanoid: false);
            Assert.IsTrue(p.Exists(x => x.Contains("no base texture")), string.Join("; ", p));
        }

        [Test]
        public void BuiltInStandardShaderUnderUrpIsRefused()
        {
            if (UnityEngine.Rendering.GraphicsSettings.currentRenderPipeline == null) Assert.Ignore("no render pipeline asset active");
            var p = WorkerAppearance.Problems(Worker(Mat("Standard", true)), requireHumanoid: false);
            Assert.IsTrue(p.Exists(x => x.Contains("no pass for the active render pipeline")), string.Join("; ", p));
        }

        [Test]
        public void NonHumanoidIsRefused()
        {
            var p = WorkerAppearance.Problems(Worker(Mat("Universal Render Pipeline/Lit", true)));
            Assert.IsTrue(p.Exists(x => x.Contains("Humanoid")), string.Join("; ", p));
        }

        [Test]
        public void NoWorkerIsRefused()
        {
            Assert.IsNotEmpty(WorkerAppearance.Problems(null));
        }
    }
}
