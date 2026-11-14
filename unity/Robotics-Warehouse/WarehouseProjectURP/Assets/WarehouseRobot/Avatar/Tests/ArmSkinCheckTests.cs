using System.Collections.Generic;
using NUnit.Framework;
using UnityEngine;

namespace WarehouseAvatar.Tests
{
    /// <summary>
    /// Experiments A/B, section 5 of Avatar/Config/experiments_ab.md: the arm-skin probe (ArmSkinCheck) on a synthetic skinned arm, and the
    /// -lookCheckLooks option of the look checks (ExperimentLooks.Subset).
    /// </summary>
    public class ArmSkinCheckTests
    {
        readonly List<Object> m_Made = new List<Object>();

        [TearDown]
        public void TearDown()
        {
            foreach (var o in m_Made) if (o != null) Object.DestroyImmediate(o);
            m_Made.Clear();
        }

        /// <summary>A T-posed left arm (shoulder at x 0.20, elbow 0.48, wrist 0.74, height 1.40 m) and a point mesh along it from x 0.25 to
        /// 0.90 whose every vertex is weighted to <paramref name="weightTo"/> (0 chest, 1 upper arm, 2 forearm, 3 hand).</summary>
        SkinnedMeshRenderer Arm(int weightTo, out Transform upper, out Transform lower, out Transform hand, Vector3 rootPosition = default, float rootYaw = 0f)
        {
            var chest = new GameObject("Chest");
            m_Made.Add(chest);
            chest.transform.SetPositionAndRotation(rootPosition, Quaternion.Euler(0f, rootYaw, 0f));
            upper = new GameObject("UpperArm").transform;
            upper.SetParent(chest.transform, false);
            upper.localPosition = new Vector3(0.20f, 1.40f, 0f);
            lower = new GameObject("LowerArm").transform;
            lower.SetParent(upper, false);
            lower.localPosition = new Vector3(0.28f, 0f, 0f);
            hand = new GameObject("Hand").transform;
            hand.SetParent(lower, false);
            hand.localPosition = new Vector3(0.26f, 0f, 0f);

            var bones = new[] { chest.transform, upper, lower, hand };
            var verts = new List<Vector3>();
            for (int i = 0; i < 400; i++)
            {
                float x = 0.25f + 0.65f * i / 399f;
                float a = i * 2.399f;   // around the arm, 0.03 m off its axis
                verts.Add(new Vector3(x, 1.40f + 0.03f * Mathf.Sin(a), 0.03f * Mathf.Cos(a)));
            }
            var mesh = new Mesh { name = "ArmPoints" };
            m_Made.Add(mesh);
            mesh.SetVertices(verts);
            var idx = new int[verts.Count];
            for (int i = 0; i < idx.Length; i++) idx[i] = i;
            mesh.SetIndices(idx, MeshTopology.Points, 0);
            var w = new BoneWeight[verts.Count];
            for (int i = 0; i < w.Length; i++) w[i] = new BoneWeight { boneIndex0 = weightTo, weight0 = 1f };
            mesh.boneWeights = w;
            var bind = new Matrix4x4[bones.Length];
            for (int b = 0; b < bones.Length; b++) bind[b] = bones[b].worldToLocalMatrix * chest.transform.localToWorldMatrix;
            mesh.bindposes = bind;
            var smr = chest.AddComponent<SkinnedMeshRenderer>();
            smr.bones = bones;
            smr.rootBone = chest.transform;
            smr.sharedMesh = mesh;
            return smr;
        }

        [Test]
        public void MeshWeightedToTheArm_Follows_AndTheBoneIsRestored()
        {
            var smr = Arm(1, out var u, out var l, out var h, new Vector3(3f, 0f, -2f), 30f);
            var rot = u.rotation;
            var r = ArmSkinCheck.MeasureSide(u, l, h, new[] { smr });
            Assert.GreaterOrEqual(r.ArmVertices, ArmSkinCheck.MinArmVertices);
            Assert.Greater(r.HandVertices, 0);
            Assert.AreEqual(r.ArmVertices, r.ArmFollowing);
            Assert.AreEqual(r.HandVertices, r.HandFollowing);
            Assert.Less(r.ArmErrorMedianM, 0.001f);
            Assert.Greater(r.ArmExpectedMoveMedianM, 0.1f);
            Assert.AreEqual(ArmSkinCheck.Follows, r.Verdict);
            Assert.AreEqual(rot, u.rotation, "the upper arm's rotation is restored");
        }

        [Test]
        public void MeshWeightedToTheForearmAndHand_StillFollows_TheyAreChildrenOfTheUpperArm()
        {
            var smr = Arm(2, out var u, out var l, out var h);
            Assert.AreEqual(ArmSkinCheck.Follows, ArmSkinCheck.MeasureSide(u, l, h, new[] { smr }).Verdict);
        }

        [Test]
        public void MeshWeightedToTheChest_DoesNotFollow()
        {
            var smr = Arm(0, out var u, out var l, out var h);
            var r = ArmSkinCheck.MeasureSide(u, l, h, new[] { smr });
            Assert.AreEqual(0, r.ArmFollowing);
            Assert.AreEqual(ArmSkinCheck.DoesNotFollow, r.Verdict);
        }

        [Test]
        public void Regions_Verdicts()
        {
            Vector3 s = new Vector3(0.2f, 1.4f, 0f), e = new Vector3(0.48f, 1.4f, 0f), w = new Vector3(0.74f, 1.4f, 0f);
            Assert.AreEqual(ArmSkinCheck.Region.Arm, ArmSkinCheck.Classify(new Vector3(0.6f, 1.43f, 0f), s, e, w), "forearm");
            Assert.AreEqual(ArmSkinCheck.Region.Arm, ArmSkinCheck.Classify(new Vector3(0.40f, 1.4f, 0.05f), s, e, w), "distal upper arm");
            Assert.AreEqual(ArmSkinCheck.Region.None, ArmSkinCheck.Classify(new Vector3(0.25f, 1.4f, 0f), s, e, w), "near the shoulder");
            Assert.AreEqual(ArmSkinCheck.Region.None, ArmSkinCheck.Classify(new Vector3(0.6f, 1.2f, 0f), s, e, w), "off the arm (torso side)");
            Assert.AreEqual(ArmSkinCheck.Region.Hand, ArmSkinCheck.Classify(new Vector3(0.84f, 1.4f, 0f), s, e, w), "hand");
            Assert.AreEqual(ArmSkinCheck.Inconclusive, ArmSkinCheck.Verdict(ArmSkinCheck.MinArmVertices - 1, ArmSkinCheck.MinArmVertices - 1));
            Assert.AreEqual(ArmSkinCheck.Follows, ArmSkinCheck.Verdict(100, 95));
            Assert.AreEqual(ArmSkinCheck.DoesNotFollow, ArmSkinCheck.Verdict(100, 94));
            Assert.AreEqual(ArmSkinCheck.Follows, ArmSkinCheck.LookVerdict(new[] { ArmSkinCheck.Follows, ArmSkinCheck.Follows }));
            Assert.AreEqual(ArmSkinCheck.DoesNotFollow, ArmSkinCheck.LookVerdict(new[] { ArmSkinCheck.Follows, ArmSkinCheck.DoesNotFollow }));
            Assert.AreEqual(ArmSkinCheck.Inconclusive, ArmSkinCheck.LookVerdict(new[] { ArmSkinCheck.Follows, ArmSkinCheck.Inconclusive }));
            Assert.AreEqual(ArmSkinCheck.Inconclusive, ArmSkinCheck.LookVerdict(new string[0]));
        }

        [Test]
        public void LookSubset_KeepsTheListOrder_RefusesUnknownNames_AbsentMeansAll()
        {
            var list = new[] { "mixamo_worker", "sunbox_m1", "anime_f_01", "cartoon_boxo_01" };
            Assert.IsNull(ExperimentLooks.Subset(new[] { "Unity.exe", "-batchmode" }, list, out string e0));
            Assert.IsNull(e0);
            CollectionAssert.AreEqual(new[] { "anime_f_01", "cartoon_boxo_01" },
                ExperimentLooks.Subset(new[] { "Unity.exe", ExperimentLooks.SubsetArg, "cartoon_boxo_01,anime_f_01" }, list, out string e1));
            Assert.IsNull(e1);
            CollectionAssert.AreEqual(new[] { "anime_f_01" }, ExperimentLooks.Subset(new[] { ExperimentLooks.SubsetArg, "anime_f_01", "-quit" }, list, out _));
            Assert.IsNull(ExperimentLooks.Subset(new[] { ExperimentLooks.SubsetArg, "anime_f_01,mannequin_01" }, list, out string e2));
            StringAssert.Contains("mannequin_01", e2);
            Assert.IsNull(ExperimentLooks.Subset(new[] { ExperimentLooks.SubsetArg, "-quit" }, list, out string e3));
            Assert.IsNotNull(e3);
            Assert.IsNull(ExperimentLooks.Subset(new[] { ExperimentLooks.SubsetArg }, list, out string e4));
            Assert.IsNotNull(e4);
        }
    }
}
