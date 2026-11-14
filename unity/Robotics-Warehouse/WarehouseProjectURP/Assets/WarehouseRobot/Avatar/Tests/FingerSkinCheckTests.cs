using System.Collections.Generic;
using System.Linq;
using NUnit.Framework;
using UnityEngine;

namespace WarehouseAvatar.Tests
{
    /// <summary>The finger skin probe of experiments_ab.md section 10 (FingerSkinCheck) on a synthetic two-finger hand.</summary>
    public class FingerSkinCheckTests
    {
        readonly List<Object> m_Made = new List<Object>();

        [TearDown]
        public void TearDown()
        {
            foreach (var o in m_Made) if (o != null) Object.DestroyImmediate(o);
            m_Made.Clear();
        }

        /// <summary>A hand at the origin with two three-bone fingers along +x, 8 cm apart (z -0.04 and +0.04), and 200 mesh points around
        /// each finger. merged: every point is weighted to finger 1's first bone; otherwise each finger's points to its own first bone.</summary>
        Transform Hand(bool merged, out SkinnedMeshRenderer smr)
        {
            var hand = new GameObject("Hand");
            m_Made.Add(hand);
            var bones = new List<Transform> { hand.transform };
            var firsts = new List<int>();
            foreach (var z in new[] { -0.04f, 0.04f })
            {
                Transform parent = hand.transform;
                for (int j = 0; j < 3; j++)
                {
                    var b = new GameObject($"Finger{(z < 0 ? 1 : 2)}_{j + 1}").transform;
                    b.SetParent(parent, false);
                    b.position = new Vector3(0.05f + 0.04f * j, 0f, z);
                    if (j == 0) firsts.Add(bones.Count);
                    bones.Add(b);
                    parent = b;
                }
            }
            var verts = new List<Vector3>();
            var weights = new List<BoneWeight>();
            for (int f = 0; f < 2; f++)
                for (int i = 0; i < 200; i++)
                {
                    float x = 0.06f + 0.07f * i / 199f, a = i * 2.399f;
                    verts.Add(new Vector3(x, 0.008f * Mathf.Sin(a), (f == 0 ? -0.04f : 0.04f) + 0.008f * Mathf.Cos(a)));
                    weights.Add(new BoneWeight { boneIndex0 = merged ? firsts[0] : firsts[f], weight0 = 1f });
                }
            var mesh = new Mesh { name = "HandPoints" };
            m_Made.Add(mesh);
            mesh.SetVertices(verts);
            mesh.SetIndices(Enumerable.Range(0, verts.Count).ToArray(), MeshTopology.Points, 0);
            mesh.boneWeights = weights.ToArray();
            mesh.bindposes = bones.Select(b => b.worldToLocalMatrix * hand.transform.localToWorldMatrix).ToArray();
            smr = hand.AddComponent<SkinnedMeshRenderer>();
            smr.bones = bones.ToArray();
            smr.rootBone = hand.transform;
            smr.sharedMesh = mesh;
            return hand.transform;
        }

        [Test]
        public void Chains_FollowEachChildOfTheHandDownItsFirstChildren()
        {
            var hand = Hand(false, out _);
            var chains = FingerSkinCheck.Chains(hand);
            Assert.AreEqual(2, chains.Count);
            CollectionAssert.AreEqual(new[] { "Finger1_1", "Finger1_2", "Finger1_3" }, chains[0].Select(t => t.name).ToArray());
        }

        [Test]
        public void FingersWeightedToTheirOwnBones_AreSeparate_AndTheBonesAreRestored()
        {
            var hand = Hand(false, out var smr);
            var rots = FingerSkinCheck.Chains(hand).Select(c => c[0].rotation).ToList();
            var r = FingerSkinCheck.MeasureHand(hand, new[] { smr });
            Assert.AreEqual(2, r.Count);
            foreach (var f in r)
            {
                Assert.AreEqual(200, f.Region, f.Name);
                Assert.AreEqual(FingerSkinCheck.Separate, f.Verdict, f.Name);
                Assert.AreEqual(1f, f.OwnFraction, 1e-6f);
                Assert.AreEqual(0f, f.MaxOtherFraction, 1e-6f);
            }
            CollectionAssert.AreEqual(rots, FingerSkinCheck.Chains(hand).Select(c => c[0].rotation).ToList(), "rotations restored");
        }

        [Test]
        public void BothFingersWeightedToOneBone_AreMerged()
        {
            var hand = Hand(true, out var smr);
            var r = FingerSkinCheck.MeasureHand(hand, new[] { smr });
            Assert.AreEqual(FingerSkinCheck.Merged, r[0].Verdict, "bending finger 1 also moves finger 2");
            Assert.AreEqual(1f, r[0].MaxOtherFraction, 1e-6f);
            Assert.AreEqual(FingerSkinCheck.Merged, r[1].Verdict, "finger 2's own bone moves nothing");
            Assert.AreEqual(0f, r[1].OwnFraction, 1e-6f);
        }

        /// <summary>Addendum 7 decision 4: two finger strips (triangles, each its own island) and a palm plate island weighted to finger 1's
        /// first bone (as Boxo's auto-rigged plate), one sub-mesh of material "glovemat".</summary>
        Transform IslandHand(out SkinnedMeshRenderer smr)
        {
            var hand = Hand(false, out smr);
            var bones = smr.bones;
            int f1 = System.Array.FindIndex(bones, b => b.name == "Finger1_1"), f2 = System.Array.FindIndex(bones, b => b.name == "Finger2_1");
            var verts = new List<Vector3>();
            var weights = new List<BoneWeight>();
            var tris = new List<int>();
            void Strip(float x0, float x1, float z, int bone, int n)
            {
                int start = verts.Count;
                for (int i = 0; i <= n; i++)
                    foreach (var dz in new[] { -0.006f, 0.006f })
                    {
                        verts.Add(new Vector3(Mathf.Lerp(x0, x1, i / (float)n), dz > 0f ? 0.003f : 0f, z + dz));   // tilted: a box with thickness
                        weights.Add(new BoneWeight { boneIndex0 = bone, weight0 = 1f });
                    }
                for (int i = 0; i < n; i++) { int q = start + 2 * i; tris.AddRange(new[] { q, q + 1, q + 2, q + 1, q + 3, q + 2 }); }
            }
            Strip(0.06f, 0.13f, -0.04f, f1, 20);              // finger 1
            Strip(0.06f, 0.13f, 0.04f, f2, 20);               // finger 2
            for (int k = 0; k < 6; k++) Strip(0.0f, 0.045f, -0.05f + 0.02f * k, f1, 12);   // the plate: 6 strips side by side ...
            for (int k = 0; k < 5; k++)                        // ... stitched into one island
                for (int i = 0; i < 12; i++)
                {
                    int a = 42 + 42 + k * 26 + 2 * i + 1, b = 42 + 42 + (k + 1) * 26 + 2 * i;
                    tris.AddRange(new[] { a, b, a + 2, b, b + 2, a + 2 });
                }
            var mesh = smr.sharedMesh;
            mesh.Clear();
            mesh.SetVertices(verts);
            mesh.SetTriangles(tris, 0);
            mesh.boneWeights = weights.ToArray();
            mesh.bindposes = bones.Select(b => b.worldToLocalMatrix * hand.localToWorldMatrix).ToArray();
            var mat = new Material(Shader.Find("Unlit/Color")) { name = "glovemat" };
            m_Made.Add(mat);
            smr.sharedMaterials = new[] { mat };
            return hand;
        }

        [Test]
        public void IslandMode_LeavesThePlateOut_AndMeasuresEachFingerByItsIsland()
        {
            var hand = IslandHand(out var smr);
            var spec = new PalmPlateSpec { look = "x", material = "glovemat", max_dimension_change = 0.05f, weld_m = 0.0001f };
            var islands = FingerSkinCheck.MeasureHand(hand, new[] { smr }, spec);
            Assert.AreEqual(2, islands.Count);
            foreach (var f in islands)
            {
                Assert.AreEqual(42, f.Region, $"{f.Name}: its own strip only (the plate is left out)");
                Assert.AreEqual(1f, f.OwnFraction, 1e-6f, f.Name);
                Assert.AreEqual(0f, f.MaxOtherFraction, 1e-6f, f.Name);
            }
        }

        [Test]
        public void Verdict_NeedsEnoughVertices()
        {
            Assert.AreEqual(FingerSkinCheck.Inconclusive, FingerSkinCheck.Verdict(FingerSkinCheck.MinRegion - 1, 1f, 0f));
            Assert.AreEqual(FingerSkinCheck.Separate, FingerSkinCheck.Verdict(FingerSkinCheck.MinRegion, 0.8f, 0.2f));
            Assert.AreEqual(FingerSkinCheck.Merged, FingerSkinCheck.Verdict(100, 0.79f, 0f));
            Assert.AreEqual(FingerSkinCheck.Merged, FingerSkinCheck.Verdict(100, 1f, 0.21f));
        }
    }
}
