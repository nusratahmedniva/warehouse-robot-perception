using System.IO;
using System.Linq;
using NUnit.Framework;
using UnityEngine;

namespace WarehouseAvatar.Tests
{
    /// <summary>Boxo's rigid torso (Avatar/Config/experiments_ab.md section 12 addendum 7 decision 2).</summary>
    public class RigidPartsTests
    {
        static ExperimentLooksFile Looks() => ExperimentLooks.Parse(File.ReadAllText(Path.Combine(Application.dataPath, "..", ExperimentLooks.AssetPath)));

        [Test]
        public void RigidPartsRule_IsBoxosOnly_WithHisBodyMaterials()
        {
            var f = Looks();
            Assert.AreEqual(1, f.rigid_parts.Length, "only Boxo: every five-finger look keeps its weights");
            var r = f.rigid_parts[0];
            Assert.AreEqual("cartoon_boxo_01", r.look);
            Assert.AreEqual("mixamorig:Spine2", r.bone);
            CollectionAssert.AreEquivalent(new[] { "bodymat", "vestmat", "stripemat", "eye_whitemat", "pupilmat", "mouthmat", "helmetmat" }, r.materials);
            foreach (var keep in new[] { "limbmat", "glovemat", "trousersmat", "bootmat" }) CollectionAssert.DoesNotContain(r.materials, keep);
        }

        [Test]
        public void BindRigid_BindsOnlyTheNamedMaterials_ToTheBone()
        {
            var mesh = new Mesh();
            var bones = new[] { new GameObject("mixamorig:Hips").transform, new GameObject("mixamorig:Spine2").transform, new GameObject("mixamorig:LeftArm").transform };
            try
            {
                mesh.vertices = Enumerable.Range(0, 6).Select(i => new Vector3(i, 0f, 0f)).ToArray();
                mesh.subMeshCount = 2;
                mesh.SetTriangles(new[] { 0, 1, 2 }, 0);
                mesh.SetTriangles(new[] { 3, 4, 5 }, 1);
                var arm = new BoneWeight { boneIndex0 = 2, weight0 = 0.6f, boneIndex1 = 1, weight1 = 0.4f };
                mesh.boneWeights = Enumerable.Repeat(arm, 6).ToArray();
                var spec = new RigidPartsSpec { look = "x", bone = "mixamorig:Spine2", materials = new[] { "vestmat" } };
                var done = ExperimentLooks.BindRigid(mesh, bones, new[] { "vestmat (Instance)", "limbmat" }, spec);
                CollectionAssert.AreEqual(new[] { "vestmat 3" }, done);
                var bw = mesh.boneWeights;
                for (int i = 0; i < 3; i++) { Assert.AreEqual(1, bw[i].boneIndex0); Assert.AreEqual(1f, bw[i].weight0); Assert.AreEqual(0f, bw[i].weight1); }
                for (int i = 3; i < 6; i++) { Assert.AreEqual(2, bw[i].boneIndex0); Assert.AreEqual(0.6f, bw[i].weight0, 1e-6f); }
                CollectionAssert.IsEmpty(ExperimentLooks.BindRigid(mesh, bones, new[] { "vestmat", "limbmat" }, new RigidPartsSpec { bone = "mixamorig:Neck", materials = new[] { "vestmat" } }),
                                         "an absent bone changes nothing");
            }
            finally
            {
                Object.DestroyImmediate(mesh);
                foreach (var b in bones) Object.DestroyImmediate(b.gameObject);
            }
        }
    }
}
