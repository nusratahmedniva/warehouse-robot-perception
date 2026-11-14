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

        /// <summary>The joint lies inside the box of the points in their principal frame (min to max projection on each axis, 1 mm).</summary>
        static void AssertInside(List<Vector3> pts, Transform joint)
        {
            var box = PalmPlate.Shape(pts);
            foreach (var (axis, what) in new[] { (box.Long, "along"), (box.Mid, "across"), (box.Thin, "through") })
            {
                float lo = pts.Min(p => Vector3.Dot(p, axis)), hi = pts.Max(p => Vector3.Dot(p, axis)), j = Vector3.Dot(joint.position, axis);
                Assert.IsTrue(j >= lo - 0.001f && j <= hi + 0.001f, $"{joint.name} {what} its finger: {j:0.0000} not in [{lo:0.0000}, {hi:0.0000}]");
            }
        }

        static IslandHandsSpec Spec() => new IslandHandsSpec
        {
            look = "x", material = "glovemat", hands = new[] { "mixamorig:RightHand" }, weld_m = 0.0001f, contact_m = 0.005f, blend_segments = 0.25f, move_joints = true,
        };

        static (Vector3[] verts, int[] island, List<int> mine) Glove(SyntheticBoxHand h)
        {
            var verts = h.Mesh.vertices;
            var island = PalmPlate.Islands(verts, h.Mesh.GetIndices(0), 0.0001f);
            return (verts, island, Enumerable.Range(0, verts.Length).ToList());
        }

        [Test]
        public void Analyse_ThumbByAxisDeviation_ThenIndexMiddleRingAcrossThePalm_NoDistanceMatching()
        {
            var h = new SyntheticBoxHand();
            try
            {
                var (verts, island, mine) = Glove(h);
                var a = IslandHands.Analyse(verts, island, mine, h.Hand.position, IslandHands.Chains(h.Hand), 0.005f);
                Assert.IsTrue(a.Ok, a.Problem);
                Assert.AreEqual(4, a.Groups.Count);
                foreach (var name in SyntheticBoxHand.Names)
                {
                    int g = Enumerable.Range(0, 4).Single(x => a.Chains[a.ChainOf[x]][0].name.Contains(name));
                    int v0 = h.Finger[name][0];
                    Assert.IsTrue(a.Groups[g].Contains(island[v0]), $"{name}: its own mesh finger, although its chain lies elsewhere");
                }
                int index = Enumerable.Range(0, 4).Single(x => a.Chains[a.ChainOf[x]][0].name.Contains("Index"));
                Assert.AreEqual(0.075f, a.Knuckle[index].x, 0.002f, "the knuckle end is the end nearest the plate");
                Assert.AreEqual(0.1775f, a.Tip[index].x, 0.002f);
            }
            finally { h.Destroy(); }
        }

        [Test]
        public void AlignChains_PutsEveryJointOnItsFingersAxis_InsideTheFinger()
        {
            var h = new SyntheticBoxHand();
            try
            {
                var moved = new List<Transform>();
                var log = IslandHands.AlignChains(h.Mesh, h.Bones, new[] { "glovemat" }, Spec(), Matrix4x4.identity, Matrix4x4.identity, 1f, moved);
                Assert.IsFalse(log.Any(l => l.Contains("PROBLEM")), string.Join("; ", log));
                Assert.AreEqual(16, moved.Count, "four joints of four chains");
                var verts = h.Mesh.vertices;
                foreach (var name in SyntheticBoxHand.Names)
                {
                    var pts = h.Finger[name].Select(i => verts[i]).ToList();
                    foreach (var j in h.Chain(name).Take(3)) AssertInside(pts, j);
                }
            }
            finally { h.Destroy(); }
        }

        [Test]
        public void ReadAssignment_ReadsTheBinding_AndTheComparisonCatchesSwappedFingers()
        {
            var h = new SyntheticBoxHand();
            try
            {
                IslandHands.AlignChains(h.Mesh, h.Bones, new[] { "glovemat" }, Spec(), Matrix4x4.identity, Matrix4x4.identity, 1f, new List<Transform>());
                IslandHands.Bind(h.Mesh, h.Bones, new[] { "glovemat" }, Spec(), Matrix4x4.identity, 1f);
                var pinned = IslandHands.ReadAssignment(h.Mesh, h.Bones, new[] { "glovemat" }, Spec(), 1f);
                Assert.AreEqual(4, pinned.Count);
                foreach (var name in SyntheticBoxHand.Names)
                {
                    var p = pinned.Single(x => x.chain == name);
                    Assert.AreEqual(h.Finger[name].Count, p.vertices, name);
                    Assert.AreEqual(h.Finger[name].Min(), p.first_vertex, name);
                    Assert.AreEqual(h.Finger[name].Max(), p.last_vertex, name);
                }
                CollectionAssert.IsEmpty(IslandHands.CompareAssignment(pinned, IslandHands.ReadAssignment(h.Mesh, h.Bones, new[] { "glovemat" }, Spec(), 1f)));
                // a re-import that swapped index and middle: the comparison names both
                var bw = h.Mesh.boneWeights;
                int[] index = h.Chain("Index").Select(t => System.Array.IndexOf(h.Bones, t)).ToArray(), middle = h.Chain("Middle").Select(t => System.Array.IndexOf(h.Bones, t)).ToArray();
                foreach (int i in h.Finger["Index"]) { bw[i].boneIndex0 = middle[System.Array.IndexOf(index, bw[i].boneIndex0)]; if (bw[i].weight1 > 0f) bw[i].boneIndex1 = middle[System.Array.IndexOf(index, bw[i].boneIndex1)]; }
                foreach (int i in h.Finger["Middle"]) { bw[i].boneIndex0 = index[System.Array.IndexOf(middle, bw[i].boneIndex0)]; if (bw[i].weight1 > 0f) bw[i].boneIndex1 = index[System.Array.IndexOf(middle, bw[i].boneIndex1)]; }
                h.Mesh.boneWeights = bw;
                var diff = IslandHands.CompareAssignment(pinned, IslandHands.ReadAssignment(h.Mesh, h.Bones, new[] { "glovemat" }, Spec(), 1f));
                Assert.IsTrue(diff.Any(d => d.Contains("Index")) && diff.Any(d => d.Contains("Middle")), string.Join("; ", diff));
                Assert.IsFalse(diff.Any(d => d.Contains("Thumb") || d.Contains("Ring")), string.Join("; ", diff));
            }
            finally { h.Destroy(); }
        }

        [Test]
        public void BoxoAssignment_MatchesThePin()
        {
            var f = ExperimentLooks.Parse(File.ReadAllText(Path.Combine(Application.dataPath, "..", ExperimentLooks.AssetPath)));
            var spec = f.island_hands.Single(x => x.look == "cartoon_boxo_01");
            var go = AssetDatabase.LoadAssetAtPath<GameObject>("Assets/ThirdParty/CharactersV4/cartoon_boxo_01/cartoon_boxo_01.fbx");
            if (go == null) Assert.Ignore("Boxo is not imported (third-party folder, git-ignored)");
            var now = new List<PinnedFinger>();
            foreach (var smr in go.GetComponentsInChildren<SkinnedMeshRenderer>(true))
                now.AddRange(IslandHands.ReadAssignment(smr.sharedMesh, smr.bones, smr.sharedMaterials.Select(m => m != null ? m.name : "").ToArray(), spec, smr.transform.lossyScale.x));
            Assert.AreEqual(8, spec.pinned_assignment.Length, "pinned: four chains of two hands; read now: " + string.Join("; ", now));
            var diff = IslandHands.CompareAssignment(spec.pinned_assignment, now);
            CollectionAssert.IsEmpty(diff, "the re-import changed Boxo's finger assignment (addendum 13): " + string.Join("; ", diff));
        }

        [Test]
        public void Bind_AfterAlignment_PlateOnTheHand_EachFingerOnlyOnItsOwnChain()
        {
            var h = new SyntheticBoxHand();
            try
            {
                IslandHands.AlignChains(h.Mesh, h.Bones, new[] { "glovemat" }, Spec(), Matrix4x4.identity, Matrix4x4.identity, 1f, new List<Transform>());
                var b = IslandHands.Bind(h.Mesh, h.Bones, new[] { "glovemat" }, Spec(), Matrix4x4.identity, 1f);
                Assert.AreEqual("", b[0].Problem);
                Assert.AreEqual(h.PlateVertices, b[0].Plate);
                var bw = h.Mesh.boneWeights;
                for (int i = 0; i < h.PlateVertices; i++) Assert.IsTrue(bw[i].boneIndex0 == 0 && bw[i].weight0 == 1f, "plate vertex on the hand");
                foreach (var name in SyntheticBoxHand.Names)
                {
                    var own = h.Chain(name).Select(t => System.Array.IndexOf(h.Bones, t)).ToArray();
                    foreach (int i in h.Finger[name])
                        foreach (var (bi, wt) in new[] { (bw[i].boneIndex0, bw[i].weight0), (bw[i].boneIndex1, bw[i].weight1) })
                            if (wt > 0f) CollectionAssert.Contains(own, bi, $"{name} vertex {i} only on its own chain");
                }
                var audit = IslandHands.Audit(h.Mesh, h.Bones, new[] { "glovemat" }, Spec());
                Assert.AreEqual(0, audit[0].crossed);
                Assert.AreEqual(4, audit[0].chainsUsed);
            }
            finally { h.Destroy(); }
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
            // addendum 11: every finger bends at its own knuckles: joints j0..j2 inside their group's box (principal frame, 1 mm)
            var smr0 = go.GetComponentsInChildren<SkinnedMeshRenderer>(true).First(s => s.sharedMaterials.Any(m => m != null && m.name == spec.material));
            var mesh = smr0.sharedMesh;
            var toWorld = smr0.transform.localToWorldMatrix;
            var world = mesh.vertices.Select(p => toWorld.MultiplyPoint3x4(p)).ToArray();
            var tris = new List<int>();
            var mats = smr0.sharedMaterials;
            for (int sub = 0; sub < mesh.subMeshCount && sub < mats.Length; sub++) if (mats[sub] != null && mats[sub].name == spec.material) tris.AddRange(mesh.GetIndices(sub));
            var island = PalmPlate.Islands(world, tris, spec.weld_m);
            foreach (var handName in spec.hands)
            {
                var hand = smr0.bones.First(b => b != null && b.name == handName);
                var bw = mesh.boneWeights;
                var tree = smr0.bones.Select(b => b != null && (b == hand || b.IsChildOf(hand))).ToArray();
                var mine = tris.Distinct().Where(i => (tree[bw[i].boneIndex0] ? bw[i].weight0 : 0f) + (tree[bw[i].boneIndex1] ? bw[i].weight1 : 0f) >= 0.5f).OrderBy(i => i).ToList();
                var a = IslandHands.Analyse(world, island, mine, hand.position, IslandHands.Chains(hand), spec.contact_m);
                Assert.IsTrue(a.Ok, $"{handName}: {a.Problem}");
                for (int g = 0; g < a.Groups.Count; g++)
                {
                    var pts = mine.Where(i => a.Groups[g].Contains(island[i])).Select(i => world[i]).ToList();
                    foreach (var j in a.Chains[a.ChainOf[g]].Take(3)) AssertInside(pts, j);
                }
            }
        }
    }
}
