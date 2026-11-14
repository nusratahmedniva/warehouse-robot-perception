using System.Collections.Generic;
using System.IO;
using System.Linq;
using NUnit.Framework;
using UnityEditor;
using UnityEngine;

namespace WarehouseAvatar.Tests
{
    /// <summary>Boxo's hands bound by their mesh islands (Avatar/Config/experiments_ab.md section 12 addendum 9).</summary>
    public class IslandHandsTests
    {
        readonly List<Object> m_Made = new List<Object>();

        [TearDown]
        public void TearDown()
        {
            foreach (var o in m_Made) if (o != null) Object.DestroyImmediate(o);
            m_Made.Clear();
        }

        static readonly Vector3[] Line = { Vector3.zero, new Vector3(1f, 0f, 0f), new Vector3(2f, 0f, 0f), new Vector3(3f, 0f, 0f) };

        static void AssertWeights(Vector3 q, params (int joint, float w)[] want)
        {
            var got = IslandHands.ChainWeights(q, Line, 0.25f).OrderBy(x => x.joint).ToList();
            var exp = want.OrderBy(x => x.joint).ToList();
            Assert.AreEqual(exp.Count, got.Count, $"at {q}");
            for (int i = 0; i < exp.Count; i++)
            {
                Assert.AreEqual(exp[i].joint, got[i].joint, $"at {q}");
                Assert.AreEqual(exp[i].w, got[i].weight, 1e-5f, $"at {q}");
            }
        }

        [Test]
        public void ChainWeights_SegmentBone_BlendAtInteriorJoints_TipOnTheDistal()
        {
            AssertWeights(new Vector3(0.5f, 0.1f, 0f), (0, 1f));
            AssertWeights(new Vector3(1.0f, 0.1f, 0f), (1, 0.5f), (0, 0.5f));
            AssertWeights(new Vector3(1.1f, 0f, 0f), (1, 0.7f), (0, 0.3f));
            AssertWeights(new Vector3(1.9f, 0f, 0f), (1, 0.7f), (2, 0.3f));
            AssertWeights(new Vector3(2.9f, 0f, 0f), (2, 1f));
            AssertWeights(new Vector3(3.4f, 0f, 0f), (2, 1f));
            AssertWeights(new Vector3(-0.2f, 0f, 0f), (0, 1f));
        }

        [Test]
        public void Match_IsOneToOne_WithTheSmallestTotalCost()
        {
            // greedy would give both groups chain 0; the best one-to-one total is group 0 -> chain 1, group 1 -> chain 0
            var cost = new float[,] { { 1f, 2f, 9f }, { 1.5f, 9f, 9f } };
            CollectionAssert.AreEqual(new[] { 1, 0 }, IslandHands.Match(cost));
        }

        static void Box(List<Vector3> v, List<int> t, Vector3 c, Vector3 size, int n)
        {
            for (int axis = 0; axis < 3; axis++)
                foreach (float side in new[] { -0.5f, 0.5f })
                {
                    int a1 = (axis + 1) % 3, a2 = (axis + 2) % 3, start = v.Count;
                    for (int i = 0; i <= n; i++)
                        for (int j = 0; j <= n; j++)
                        {
                            var p = Vector3.zero;
                            p[axis] = side * size[axis];
                            p[a1] = (i / (float)n - 0.5f) * size[a1];
                            p[a2] = (j / (float)n - 0.5f) * size[a2];
                            v.Add(c + p);
                        }
                    for (int i = 0; i < n; i++)
                        for (int j = 0; j < n; j++) { int q = start + i * (n + 1) + j; t.AddRange(new[] { q, q + 1, q + n + 1, q + 1, q + n + 2, q + n + 1 }); }
                }
        }

        [Test]
        public void Bind_PlateOnTheHand_EachFingerOnlyOnItsOwnChain()
        {
            var hand = new GameObject("mixamorig:RightHand").transform;
            m_Made.Add(hand.gameObject);
            var bones = new List<Transform> { hand };
            foreach (var (name, z) in new[] { ("Index", -0.04f), ("Middle", 0.04f) })
            {
                Transform parent = hand;
                for (int j = 1; j <= 4; j++)
                {
                    var b = new GameObject($"mixamorig:RightHand{name}{j}").transform;
                    b.SetParent(parent, false);
                    b.position = new Vector3(0.07f + 0.03f * (j - 1), 0f, z);
                    bones.Add(b);
                    parent = b;
                }
            }
            var v = new List<Vector3>();
            var t = new List<int>();
            Box(v, t, new Vector3(0.03f, 0f, 0f), new Vector3(0.08f, 0.03f, 0.14f), 3);              // the plate
            int plateEnd = v.Count;
            foreach (var z in new[] { -0.04f, 0.04f })
            {
                Box(v, t, new Vector3(0.115f, 0f, z), new Vector3(0.09f, 0.02f, 0.02f), 3);         // the finger
                Box(v, t, new Vector3(0.165f, 0f, z), new Vector3(0.015f, 0.015f, 0.015f), 2);      // its tip, touching
            }
            var mesh = new Mesh();
            m_Made.Add(mesh);
            mesh.SetVertices(v);
            mesh.SetTriangles(t, 0);
            // the auto-rigger's spread: everything on the index finger's first bone
            mesh.boneWeights = Enumerable.Repeat(new BoneWeight { boneIndex0 = 1, weight0 = 1f }, v.Count).ToArray();
            var spec = new IslandHandsSpec { look = "x", material = "glovemat", hands = new[] { "mixamorig:RightHand" }, weld_m = 0.0001f, contact_m = 0.005f, blend_segments = 0.25f };
            var b0 = IslandHands.Bind(mesh, bones.ToArray(), new[] { "glovemat" }, spec, Matrix4x4.identity, 1f);
            Assert.AreEqual("", b0[0].Problem);
            Assert.AreEqual(plateEnd, b0[0].Plate, "the whole plate on the hand bone");
            var bw = mesh.boneWeights;
            for (int i = 0; i < plateEnd; i++) Assert.IsTrue(bw[i].boneIndex0 == 0 && bw[i].weight0 == 1f, "plate vertex on the hand");
            int[] index = { 1, 2, 3 }, middle = { 5, 6, 7 };
            for (int i = plateEnd; i < v.Count; i++)
            {
                var own = v[i].z < 0f ? index : middle;
                var w = bw[i];
                foreach (var (bi, wt) in new[] { (w.boneIndex0, w.weight0), (w.boneIndex1, w.weight1) })
                    if (wt > 0f) CollectionAssert.Contains(own, bi, $"vertex {i} only on its own chain");
            }
            var audit = IslandHands.Audit(mesh, bones.ToArray(), new[] { "glovemat" }, spec);
            Assert.AreEqual(0, audit[0].crossed);
            Assert.AreEqual(plateEnd, audit[0].onHand);
            Assert.AreEqual(v.Count - plateEnd, audit[0].oneChain);
            Assert.AreEqual(2, audit[0].chainsUsed, "both chains get their finger");
        }

        [Test]
        public void IslandHandsRule_IsBoxosOnly_AndTheImportedBoxoHasNoCrossFingerWeights()
        {
            var f = ExperimentLooks.Parse(File.ReadAllText(Path.Combine(Application.dataPath, "..", ExperimentLooks.AssetPath)));
            Assert.AreEqual(1, f.island_hands.Length, "only Boxo: five-finger looks keep their weights");
            var spec = f.island_hands[0];
            Assert.AreEqual("cartoon_boxo_01", spec.look);
            var go = AssetDatabase.LoadAssetAtPath<GameObject>("Assets/ThirdParty/CharactersV4/cartoon_boxo_01/cartoon_boxo_01.fbx");
            if (go == null) Assert.Ignore("Boxo is not imported (third-party folder, git-ignored)");
            int hands = 0;
            foreach (var smr in go.GetComponentsInChildren<SkinnedMeshRenderer>(true))
                foreach (var a in IslandHands.Audit(smr.sharedMesh, smr.bones, smr.sharedMaterials.Select(m => m != null ? m.name : "").ToArray(), spec))
                {
                    hands++;
                    Assert.AreEqual(0, a.crossed, $"{a.hand}: no vertex across parts");
                    Assert.Greater(a.onHand, 0, $"{a.hand}: the plate on the hand bone");
                    Assert.Greater(a.oneChain, 0, $"{a.hand}: the fingers on their chains");
                    Assert.AreEqual(a.chains, a.chainsUsed, $"{a.hand}: every chain gets its finger (addendum 10)");
                }
            Assert.AreEqual(2, hands);
        }
    }
}
