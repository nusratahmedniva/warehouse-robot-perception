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
            fist_curl_deg = 75f, fist_thumb_curl_deg = 40f, relaxed_curl_deg = 25f, relaxed_thumb_curl_deg = 10f, rest_outward = 0.12f,
        };

        static string ConfigFile => Path.Combine(Path.GetDirectoryName(Application.dataPath), "Assets/WarehouseRobot/Avatar/Config/look_check.json");

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

        static PoseSpec Spec(string command, bool right, float az, float el, bool forearmUp = false, float spread = 8f) =>
            new PoseSpec { Command = command, RightArm = right, AzimuthFrontDeg = az, ElevationDeg = el, ForearmUp = forearmUp, SpreadDeg = spread };

        static void AssertDir(Vector3 actual, Vector3 expected, float tolDeg, string what) =>
            Assert.Less(Vector3.Angle(actual, expected), tolDeg, $"{what}: {actual} vs {expected}");

        static HumanBodyBones B(bool right, HumanBodyBones leftBone, HumanBodyBones rightBone) => right ? rightBone : leftBone;

        static Vector3 Arm(TestRig r, bool right) =>
            r.P(B(right, HumanBodyBones.LeftHand, HumanBodyBones.RightHand)) - r.P(B(right, HumanBodyBones.LeftUpperArm, HumanBodyBones.RightUpperArm));

        static Vector3 Forearm(TestRig r, bool right) =>
            r.P(B(right, HumanBodyBones.LeftHand, HumanBodyBones.RightHand)) - r.P(B(right, HumanBodyBones.LeftLowerArm, HumanBodyBones.RightLowerArm));

        [Test]
        public void BodyFrame_FromUpperArms()
        {
            var r = Rig();
            new LookPoser(r, Hand).BodyFrame(out var right, out var forward);
            AssertDir(right, Vector3.right, 0.1f, "right");
            AssertDir(forward, Vector3.forward, 0.1f, "forward");
        }

        [Test]
        public void Point_SidewaysAndFront45_EachOwnArm_OtherArmHangs()
        {
            var r = Rig();
            var poser = new LookPoser(r, Hand);
            poser.Apply(Spec(LookCheckConfig.Point, true, 0f, 0f));          // own right arm out to the own right (image left)
            AssertDir(Arm(r, true), Vector3.right, 1f, "right arm sideways");
            Assert.Less(Arm(r, false).normalized.y, -0.9f, "left arm hangs");
            poser.Apply(Spec(LookCheckConfig.Point, false, 0f, 0f));
            AssertDir(Arm(r, false), Vector3.left, 1f, "left arm sideways");
            Assert.Less(Arm(r, true).normalized.y, -0.9f, "right arm hangs");
            poser.Apply(Spec(LookCheckConfig.Point, true, 45f, 0f));         // 45 deg toward the camera (+Z)
            AssertDir(Arm(r, true), new Vector3(1f, 0f, 1f), 1f, "right arm 45 deg to the front");
            poser.Apply(Spec(LookCheckConfig.Point, false, 30f, 20f));
            AssertDir(Arm(r, false), new Vector3(-Mathf.Cos(30f * Mathf.Deg2Rad) * Mathf.Cos(20f * Mathf.Deg2Rad), Mathf.Sin(20f * Mathf.Deg2Rad),
                                                 Mathf.Sin(30f * Mathf.Deg2Rad) * Mathf.Cos(20f * Mathf.Deg2Rad)), 1f, "azimuth then elevation");
        }

        [Test]
        public void Point_IndexExtended_OthersCurled()
        {
            var r = Rig();
            new LookPoser(r, Hand).Apply(Spec(LookCheckConfig.Point, true, 0f, 0f));
            Vector3 wrist = r.P(HumanBodyBones.RightHand);
            AssertDir(r.P(HumanBodyBones.RightIndexDistal) - r.P(HumanBodyBones.RightIndexProximal), Vector3.right, 2f, "index along the arm");
            float indexReach = Vector3.Distance(r.P(HumanBodyBones.RightIndexDistal), wrist);
            float middleReach = Vector3.Distance(r.P(HumanBodyBones.RightMiddleDistal), wrist);
            Assert.Less(middleReach, indexReach - 0.02f, "middle finger curled");
        }

        [TestCase(true)]
        [TestCase(false)]
        public void Wait_ForearmVertical_HandAboveShoulder_IndexUp(bool right)
        {
            var r = Rig();
            new LookPoser(r, Hand).Apply(Spec(LookCheckConfig.Wait, right, 20f, -22f, forearmUp: true));
            AssertDir(Forearm(r, right), Vector3.up, 1f, "forearm");
            Vector3 s = r.P(B(right, HumanBodyBones.LeftUpperArm, HumanBodyBones.RightUpperArm));
            Vector3 e = r.P(B(right, HumanBodyBones.LeftLowerArm, HumanBodyBones.RightLowerArm));
            Vector3 w = r.P(B(right, HumanBodyBones.LeftHand, HumanBodyBones.RightHand));
            Assert.Greater(w.y, s.y, "wrist above the shoulder");
            Assert.Less(Vector3.Angle(s - e, w - e), 130f, "elbow bent");
            Vector3 idx = r.P(B(right, HumanBodyBones.LeftIndexDistal, HumanBodyBones.RightIndexDistal)) -
                          r.P(B(right, HumanBodyBones.LeftIndexProximal, HumanBodyBones.RightIndexProximal));
            AssertDir(idx, Vector3.up, 5f, "index up");
            Assert.Less(Vector3.Distance(r.P(B(right, HumanBodyBones.LeftRingDistal, HumanBodyBones.RightRingDistal)), w),
                        Vector3.Distance(r.P(B(right, HumanBodyBones.LeftIndexDistal, HumanBodyBones.RightIndexDistal)), w) - 0.02f, "ring curled");
            Assert.Less(Arm(r, !right).normalized.y, -0.9f, "the other arm hangs");
        }

        [TestCase(true, false)]
        [TestCase(false, false)]
        [TestCase(true, true)]
        public void Stop_PalmTowardTheCamera_FingersUpAndSpread(bool right, bool bent)
        {
            var r = Rig();
            var poser = new LookPoser(r, Hand);
            poser.Apply(bent ? Spec(LookCheckConfig.Stop, right, 45f, -40f, forearmUp: true) : Spec(LookCheckConfig.Stop, right, 79f, 14f));
            if (bent) AssertDir(Forearm(r, right), Vector3.up, 1f, "bent: forearm vertical");
            else Assert.Greater(Vector3.Dot(Arm(r, right).normalized, Vector3.forward), 0.8f, "extended toward the camera (+Z)");
            Vector3 fingers = r.P(B(right, HumanBodyBones.LeftMiddleProximal, HumanBodyBones.RightMiddleProximal)) -
                              r.P(B(right, HumanBodyBones.LeftHand, HumanBodyBones.RightHand));
            AssertDir(fingers, Vector3.up, 2f, "fingers up");
            Assert.IsTrue(LookPoser.PalmNormal(right ? poser.Right : poser.Left, fingers.normalized, out var palm));
            Assert.Greater(Vector3.Dot(palm, Vector3.forward), 0.95f, "palm faces +Z (the camera)");
            Vector3 idx = r.P(B(right, HumanBodyBones.LeftIndexDistal, HumanBodyBones.RightIndexDistal)) -
                          r.P(B(right, HumanBodyBones.LeftIndexProximal, HumanBodyBones.RightIndexProximal));
            Vector3 lit = r.P(B(right, HumanBodyBones.LeftLittleDistal, HumanBodyBones.RightLittleDistal)) -
                          r.P(B(right, HumanBodyBones.LeftLittleProximal, HumanBodyBones.RightLittleProximal));
            Assert.AreEqual(24f, Vector3.Angle(idx, lit), 1f, "index and little fanned by 8 + 16 deg");
        }

        [Test]
        public void None_BothArmsHangMirrored_AndPosesDoNotAccumulate()
        {
            var r = Rig();
            var poser = new LookPoser(r, Hand);
            var none = Spec(LookCheckConfig.None, false, 0f, -83f);
            poser.Apply(none);
            var before = r.P(HumanBodyBones.RightIndexDistal);
            Vector3 a = Arm(r, true), b = Arm(r, false);
            Assert.Less(a.normalized.y, -0.9f);
            Assert.Less(b.normalized.y, -0.9f);
            Assert.AreEqual(a.x, -b.x, 1e-4f, "mirrored");
            poser.Apply(Spec(LookCheckConfig.Stop, true, 79f, 14f));
            poser.Apply(Spec(LookCheckConfig.Wait, false, 20f, -22f, forearmUp: true));
            poser.Apply(none);
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
        public void RecordingNames_FollowLookCheckV4_AndAreCultureInvariant()
        {
            var old = System.Threading.Thread.CurrentThread.CurrentCulture;
            try
            {
                System.Threading.Thread.CurrentThread.CurrentCulture = new System.Globalization.CultureInfo("de-DE");
                Assert.AreEqual("sunbox_m1__WAIT__2.0__left_seq1", LookCheckConfig.RecordingName("sunbox_m1", "WAIT", 2.0f, "left", "seq1"));
                Assert.AreEqual("a__NONE__4.0__f3", LookCheckConfig.RecordingName("a", "NONE", 4.0f, "", "f3"));
                Assert.AreEqual("frame_000", LookCheckConfig.FrameStem(0));
                Assert.AreEqual("frame_010", LookCheckConfig.FrameStem(10));
                StringAssert.Contains("\"fx\": 458.99", LookCheckConfig.HeaderJson(730, 530, 60.0, 1.2f, 0, "left", new LookVariant { take = "f1" }));
            }
            finally { System.Threading.Thread.CurrentThread.CurrentCulture = old; }
            // <look>__<command>__<distance>__<take>: exactly four parts
            Assert.AreEqual(4, LookCheckConfig.RecordingName("vrm_seed_san", "STOP", 4f, "right", "seq2").Split(new[] { "__" }, System.StringSplitOptions.None).Length);
        }

        [System.Serializable]
        class Header
        {
            public int version, frame_index, width, height;
            public string type, arm = "absent", encoding;
            public double fx, fy, cx, cy, vertical_fov_deg, pan_deg, tilt_deg, camera_height_m;
        }

        [Test]
        public void HeaderJson_IsTheFramePanTiltHeader_WithArm()
        {
            var v = new LookVariant { take = "seq2", azimuth_front_deg = 45f, forearm_up = false, spread_deg = 0f };
            string json = LookCheckConfig.HeaderJson(730, 530, 60.0, 1.2f, 7, "left", v);
            var h = JsonUtility.FromJson<Header>(json);
            Assert.AreEqual(3, h.version);
            Assert.AreEqual("frame_pan_tilt", h.type);
            Assert.AreEqual(7, h.frame_index);
            Assert.AreEqual(730, h.width);
            Assert.AreEqual(530, h.height);
            Assert.AreEqual(458.993, h.fy, 0.001);   // CLAUDE.md: fx = fy = 458.99 at 60 deg, 530 px high
            Assert.AreEqual(h.fy, h.fx, 1e-9);
            Assert.AreEqual(365.0, h.cx);
            Assert.AreEqual(265.0, h.cy);
            Assert.AreEqual(60.0, h.vertical_fov_deg);
            Assert.AreEqual(1.2, h.camera_height_m, 1e-6);
            Assert.AreEqual("left", h.arm);
            Assert.AreEqual("png", h.encoding);
            StringAssert.DoesNotContain("time_s", json, "no Unity Time.time in an Edit Mode render: the tool's 10 Hz fallback is used");

            string none = LookCheckConfig.HeaderJson(730, 530, 60.0, 1.2f, 0, "", v);
            StringAssert.DoesNotContain("\"arm\"", none, "NONE carries no arm label (an empty one would be refused)");
            foreach (var key in new[] { "goal", "goal_point", "goal_x", "goal_z", "end_point", "end_point_x", "end_point_z", "point_b", "b",
                                        "true_gesture", "true_commander", "commander_truth", "gesture_truth", "worker_label", "truth" })
                StringAssert.DoesNotContain($"\"{key}\"", json.ToLowerInvariant(), "protocol 3 forbidden key");
        }

        [Test]
        public void ShippedConfig_IsValid_AndMatchesLookCheckV4()
        {
            var cfg = LookCheckConfig.Parse(File.ReadAllText(ConfigFile));
            CollectionAssert.IsEmpty(cfg.Validate());
            CollectionAssert.AreEqual(new[] { 2.0f, 4.0f }, cfg.recording.distances_m);
            Assert.AreEqual(60f, cfg.recording.vertical_fov_deg);
            Assert.AreEqual(11, cfg.recording.sequence_frames);
            foreach (var c in cfg.commands)
            {
                int seq = 0, singles = 0;
                foreach (var v in c.variants) { if (v.sequence) seq++; else singles++; }
                Assert.GreaterOrEqual(seq, 2, c.command + ": at least 2 sequences per group");
                Assert.GreaterOrEqual(seq * cfg.recording.sequence_frames + singles, 10, c.command + ": at least 10 frames per group");
            }
        }

        [Test]
        public void Validate_RejectsFormatViolations()
        {
            var cfg = LookCheckConfig.Parse(File.ReadAllText(ConfigFile));
            cfg.looks[0].id = "mixamo__worker";
            cfg.looks[1].id = cfg.looks[2].id;
            cfg.recording.sequence_frames = 9;
            cfg.recording.arms = new[] { "left" };
            cfg.commands[1].variants[0].forearm_up = false;             // WAIT
            cfg.commands[2].variants[1].sequence = false;               // STOP: one sequence left
            cfg.commands[0].variants[1].azimuth_front_deg = 0f;         // POINT: no 45 deg sequence
            cfg.commands[3].command = "WAVE";
            var errors = string.Join("\n", cfg.Validate());
            StringAssert.Contains("'mixamo__worker' must use", errors);
            StringAssert.Contains("listed twice", errors);
            StringAssert.Contains("10 to 20 frames", errors);
            StringAssert.Contains("recording.arms", errors);
            StringAssert.Contains("WAIT seq1: forearm_up must be true", errors);
            StringAssert.Contains("commands STOP: at least 2 sequence takes", errors);
            StringAssert.Contains("one about 45 deg toward the front", errors);
            StringAssert.Contains("unknown command 'WAVE'", errors);

            cfg = LookCheckConfig.Parse(File.ReadAllText(ConfigFile));
            cfg.commands = new[] { cfg.commands[0], cfg.commands[1] };
            StringAssert.Contains("STOP is required", string.Join("\n", cfg.Validate()));
        }

        [Test]
        public void IsNamePart_RejectsDoubleAndEdgeUnderscores()
        {
            Assert.IsTrue(LookCheckConfig.IsNamePart("sunbox_m1"));
            Assert.IsTrue(LookCheckConfig.IsNamePart("seq1"));
            Assert.IsFalse(LookCheckConfig.IsNamePart("a__b"));
            Assert.IsFalse(LookCheckConfig.IsNamePart("_a"));
            Assert.IsFalse(LookCheckConfig.IsNamePart("a_"));
            Assert.IsFalse(LookCheckConfig.IsNamePart("Mixamo"));
            Assert.IsFalse(LookCheckConfig.IsNamePart(""));
        }
    }
}
