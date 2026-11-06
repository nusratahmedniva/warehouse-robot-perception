using System.Collections.Generic;
using System.IO;
using NUnit.Framework;
using UnityEngine;

namespace WarehouseAvatar.Tests
{
    /// <summary>A T-pose skeleton facing +Z (right = +X) with every arm and finger bone, as a Humanoid bone source.</summary>
    sealed class TestRig : IBoneSource
    {
        public readonly GameObject Root;
        readonly Dictionary<HumanBodyBones, Transform> m_Bones = new Dictionary<HumanBodyBones, Transform>();

        public TestRig(bool fingers = true)
        {
            Root = new GameObject("TestRig");
            var hips = Add(HumanBodyBones.Hips, Root.transform, new Vector3(0f, 1.0f, 0f));
            var chest = Add(HumanBodyBones.Chest, hips, new Vector3(0f, 1.4f, 0f));
            Add(HumanBodyBones.Head, chest, new Vector3(0f, 1.65f, 0f));
            foreach (bool right in new[] { false, true })
            {
                float s = right ? 1f : -1f;
                var upper = Add(right ? HumanBodyBones.RightUpperArm : HumanBodyBones.LeftUpperArm, chest, new Vector3(0.2f * s, 1.45f, 0f));
                var lower = Add(right ? HumanBodyBones.RightLowerArm : HumanBodyBones.LeftLowerArm, upper, new Vector3(0.48f * s, 1.45f, 0f));
                var hand = Add(right ? HumanBodyBones.RightHand : HumanBodyBones.LeftHand, lower, new Vector3(0.74f * s, 1.45f, 0f));
                if (!fingers) continue;
                // thumb, index, middle, ring, little: base x, z offset (index toward +Z = the front in T-pose);
                // the middle finger lies on the hand axis (wrist -> middle base), as on a real hand
                float[] baseX = { 0.77f, 0.81f, 0.81f, 0.805f, 0.80f };
                float[] z = { 0.045f, 0.02f, 0.0f, -0.02f, -0.04f };
                var first = right ? HumanBodyBones.RightThumbProximal : HumanBodyBones.LeftThumbProximal;
                for (int f = 0; f < 5; f++)
                {
                    Transform parent = hand;
                    for (int j = 0; j < 3; j++)
                        parent = Add(first + 3 * f + j, parent, new Vector3((baseX[f] + 0.03f * j) * s, f == 0 ? 1.44f : 1.45f, z[f]));
                }
            }
        }

        Transform Add(HumanBodyBones b, Transform parent, Vector3 worldPos)
        {
            var t = new GameObject(b.ToString()).transform;
            t.SetParent(parent, false);
            t.position = worldPos;
            m_Bones[b] = t;
            return t;
        }

        public Transform Get(HumanBodyBones bone) => m_Bones.TryGetValue(bone, out var t) ? t : null;
        public Vector3 P(HumanBodyBones b) => m_Bones[b].position;
    }

    public class LookCheckTests
    {
        static readonly LookCheckHand Hand = new LookCheckHand
        {
            fist_curl_deg = 75f, fist_thumb_curl_deg = 40f, relaxed_curl_deg = 25f, relaxed_thumb_curl_deg = 10f, stop_spread_deg = 8f, rest_outward = 0.12f,
        };

        readonly List<GameObject> m_Created = new List<GameObject>();

        TestRig Rig(bool fingers = true)
        {
            var r = new TestRig(fingers);
            m_Created.Add(r.Root);
            return r;
        }

        [TearDown]
        public void TearDown()
        {
            foreach (var go in m_Created) Object.DestroyImmediate(go);
            m_Created.Clear();
        }

        static void AssertDir(Vector3 actual, Vector3 expected, float tolDeg, string what) =>
            Assert.Less(Vector3.Angle(actual, expected), tolDeg, $"{what}: {actual} vs {expected}");

        static Vector3 Arm(TestRig r, bool right) =>
            r.P(right ? HumanBodyBones.RightHand : HumanBodyBones.LeftHand) - r.P(right ? HumanBodyBones.RightUpperArm : HumanBodyBones.LeftUpperArm);

        [Test]
        public void BodyFrame_FromUpperArms()
        {
            var r = Rig();
            new LookPoser(r, Hand).BodyFrame(out var right, out var forward);
            AssertDir(right, Vector3.right, 0.1f, "right");
            AssertDir(forward, Vector3.forward, 0.1f, "forward");
        }

        [Test]
        public void Point_Directions_AreTheRobots()
        {
            var r = Rig();
            var poser = new LookPoser(r, Hand);
            poser.Apply(LookPose.PointLeft);   // robot's left = worker's right arm to the worker's right
            AssertDir(Arm(r, true), Vector3.right, 1f, "point_left right arm");
            Assert.Less(Arm(r, false).normalized.y, -0.9f, "point_left: left arm hangs");
            poser.Apply(LookPose.PointRight);
            AssertDir(Arm(r, false), Vector3.left, 1f, "point_right left arm");
            Assert.Less(Arm(r, true).normalized.y, -0.9f, "point_right: right arm hangs");
            poser.Apply(LookPose.PointUp);
            AssertDir(Arm(r, true), Vector3.up, 1f, "point_up right arm");
        }

        [Test]
        public void Point_IndexExtended_OthersCurled()
        {
            var r = Rig();
            new LookPoser(r, Hand).Apply(LookPose.PointUp);
            Vector3 wrist = r.P(HumanBodyBones.RightHand);
            AssertDir(r.P(HumanBodyBones.RightIndexDistal) - r.P(HumanBodyBones.RightIndexProximal), Vector3.up, 2f, "index along the arm");
            float indexReach = Vector3.Distance(r.P(HumanBodyBones.RightIndexDistal), wrist);
            float middleReach = Vector3.Distance(r.P(HumanBodyBones.RightMiddleDistal), wrist);
            Assert.Less(middleReach, indexReach - 0.02f, "middle finger curled");
        }

        [Test]
        public void Wait_ForearmVertical_HandAboveShoulder_IndexUp()
        {
            var r = Rig();
            new LookPoser(r, Hand).Apply(LookPose.Wait);
            AssertDir(r.P(HumanBodyBones.RightHand) - r.P(HumanBodyBones.RightLowerArm), Vector3.up, 1f, "forearm");
            Assert.Greater(r.P(HumanBodyBones.RightHand).y, r.P(HumanBodyBones.RightUpperArm).y, "wrist above the shoulder");
            Vector3 s = r.P(HumanBodyBones.RightUpperArm), e = r.P(HumanBodyBones.RightLowerArm), w = r.P(HumanBodyBones.RightHand);
            Assert.Less(Vector3.Angle(s - e, w - e), 130f, "elbow bent");
            AssertDir(r.P(HumanBodyBones.RightIndexDistal) - r.P(HumanBodyBones.RightIndexProximal), Vector3.up, 5f, "index up");
            Assert.Less(Vector3.Distance(r.P(HumanBodyBones.RightRingDistal), w), Vector3.Distance(r.P(HumanBodyBones.RightIndexDistal), w) - 0.02f, "ring curled");
        }

        [Test]
        public void Stop_PalmTowardTheCamera_FingersUpAndSpread()
        {
            var r = Rig();
            var poser = new LookPoser(r, Hand);
            poser.Apply(LookPose.Stop);
            Assert.Greater(Vector3.Dot(Arm(r, true).normalized, Vector3.forward), 0.8f, "arm toward the camera (+Z)");
            Vector3 fingers = r.P(HumanBodyBones.RightMiddleProximal) - r.P(HumanBodyBones.RightHand);
            AssertDir(fingers, Vector3.up, 2f, "fingers up");
            Assert.IsTrue(LookPoser.PalmNormal(poser.Right, fingers.normalized, out var palm));
            Assert.Greater(Vector3.Dot(palm, Vector3.forward), 0.95f, "palm faces +Z (the camera)");
            Vector3 idx = r.P(HumanBodyBones.RightIndexDistal) - r.P(HumanBodyBones.RightIndexProximal);
            Vector3 lit = r.P(HumanBodyBones.RightLittleDistal) - r.P(HumanBodyBones.RightLittleProximal);
            Assert.Greater(Vector3.Angle(idx, lit), 20f, "index and little finger fanned apart");
        }

        [Test]
        public void Neutral_ArmsDown_AndPosesDoNotAccumulate()
        {
            var r = Rig();
            var poser = new LookPoser(r, Hand);
            poser.Apply(LookPose.Neutral);
            var before = r.P(HumanBodyBones.RightIndexDistal);
            Assert.Less(Arm(r, true).normalized.y, -0.9f);
            Assert.Less(Arm(r, false).normalized.y, -0.9f);
            poser.Apply(LookPose.Stop);
            poser.Apply(LookPose.Wait);
            poser.Apply(LookPose.Neutral);
            Assert.Less(Vector3.Distance(before, r.P(HumanBodyBones.RightIndexDistal)), 1e-4f, "same pose after other poses");
        }

        [Test]
        public void FaceTowards_TurnsTheBodyToThePoint()
        {
            var r = Rig();
            r.Root.transform.position = new Vector3(0f, 0f, 3f);
            var poser = new LookPoser(r, Hand);
            poser.FaceTowards(r.Root.transform, new Vector3(0f, 1.2f, 0f));
            poser.BodyFrame(out _, out var forward);
            AssertDir(forward, Vector3.back, 0.5f, "faces the camera at the origin");
        }

        [Test]
        public void Inventory_CountsFingerBones()
        {
            var full = Rig();
            var row = new LookInventoryRow();
            LookInventory.FillBones(row, full, new LookPoser(full, Hand));
            Assert.AreEqual(30, row.finger_bones_mapped);
            Assert.IsTrue(row.hand_shapes_possible);
            var bare = Rig(fingers: false);
            var row2 = new LookInventoryRow();
            LookInventory.FillBones(row2, bare, new LookPoser(bare, Hand));
            Assert.AreEqual(0, row2.finger_bones_mapped);
            Assert.AreEqual(30, row2.finger_bones_missing.Length);
            Assert.IsFalse(row2.hand_shapes_possible);
        }

        [Test]
        public void MagentaPixels_CountsOnlyErrorMagenta()
        {
            var px = new[] { new Color32(255, 0, 255, 255), new Color32(250, 10, 248, 255), new Color32(255, 105, 180, 255), new Color32(128, 128, 128, 255) };
            Assert.AreEqual(2, LookInventory.MagentaPixels(px, 16));
            Assert.AreEqual(1, LookInventory.MagentaPixels(px, 0));
        }

        [Test]
        public void MaterialProblems_FlagsMissingMaterial_SkipsInactive()
        {
            var go = GameObject.CreatePrimitive(PrimitiveType.Cube);
            m_Created.Add(go);
            go.GetComponent<Renderer>().sharedMaterial = null;
            Assert.AreEqual(1, LookInventory.MaterialProblems(go, out _).Count);
            go.SetActive(false);
            var parent = new GameObject("P");
            m_Created.Add(parent);
            go.transform.SetParent(parent.transform);
            Assert.AreEqual(0, LookInventory.MaterialProblems(parent, out _).Count, "inactive renderers are not drawn");
        }

        [Test]
        public void MeshExtentY_UsesVertices_AndHeightIsAboveTheRoot()
        {
            var root = new GameObject("Root");
            m_Created.Add(root);
            var cube = GameObject.CreatePrimitive(PrimitiveType.Cube);
            cube.transform.SetParent(root.transform, false);
            cube.transform.localPosition = new Vector3(0f, 1f, 0f);
            cube.transform.localScale = new Vector3(0.5f, 2f, 0.5f);
            cube.transform.localRotation = Quaternion.Euler(0f, 45f, 0f);
            Assert.IsTrue(LookInventory.MeshExtentY(root, out float lo, out float hi));
            Assert.AreEqual(0f, lo, 1e-4f);
            Assert.AreEqual(2f, hi, 1e-4f);
            root.transform.position = new Vector3(0f, 0.5f, 0f);
            Assert.AreEqual(2f, LookInventory.Height(root), 1e-4f);
            cube.SetActive(false);
            Assert.IsFalse(LookInventory.MeshExtentY(root, out _, out _), "no active mesh");
        }

        [Test]
        public void ImageName_And_Intrinsics_AreCultureInvariant()
        {
            var old = System.Threading.Thread.CurrentThread.CurrentCulture;
            try
            {
                System.Threading.Thread.CurrentThread.CurrentCulture = new System.Globalization.CultureInfo("de-DE");
                Assert.AreEqual("sunbox_m1__wait__d2.0__fov30.png", LookCheckConfig.ImageName("sunbox_m1", "wait", 2.0f, 30f));
                Assert.AreEqual("a__stop__d3.0__fov60.png", LookCheckConfig.ImageName("a", "stop", 3.0f, 60f));
            }
            finally { System.Threading.Thread.CurrentThread.CurrentCulture = old; }
            LookCheckConfig.Intrinsics(730, 530, 60.0, out double fx, out double fy, out double cx, out double cy);
            Assert.AreEqual(458.993, fy, 0.001);   // CLAUDE.md: fx = fy = 458.99 at 60 deg, 530 px high
            Assert.AreEqual(fy, fx);
            Assert.AreEqual(365.0, cx);
            Assert.AreEqual(265.0, cy);
        }

        [Test]
        public void ShippedConfig_IsValid()
        {
            string path = Path.Combine(Path.GetDirectoryName(Application.dataPath), "Assets/WarehouseRobot/Avatar/Config/look_check.json");
            var cfg = LookCheckConfig.Parse(File.ReadAllText(path));
            CollectionAssert.IsEmpty(cfg.Validate());
            CollectionAssert.AreEqual(new[] { "neutral", "point_left", "point_right", "point_up", "wait", "stop" }, cfg.poses);
        }

        [Test]
        public void Validate_RejectsDuplicatesUnknownPosesAndBadIds()
        {
            string path = Path.Combine(Path.GetDirectoryName(Application.dataPath), "Assets/WarehouseRobot/Avatar/Config/look_check.json");
            var cfg = LookCheckConfig.Parse(File.ReadAllText(path));
            cfg.poses = new[] { "neutral", "neutral", "wave" };
            cfg.looks[1].id = cfg.looks[0].id;
            cfg.looks[2].id = "Bad Id";
            cfg.looks[3].kind = "vroid";
            cfg.render.distances_m = new[] { 2f, 0f };
            var errors = string.Join("\n", cfg.Validate());
            StringAssert.Contains("'neutral' listed twice", errors);
            StringAssert.Contains("unknown pose 'wave'", errors);
            StringAssert.Contains("listed twice", errors);
            StringAssert.Contains("'Bad Id' must use only", errors);
            StringAssert.Contains("kind must be", errors);
            StringAssert.Contains("every distance must be > 0", errors);
        }
    }
}
