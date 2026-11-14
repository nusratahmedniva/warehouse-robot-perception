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
