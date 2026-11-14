using System.Collections.Generic;
using System.Globalization;
using System.IO;
using System.Linq;
using NUnit.Framework;
using UnityEngine;

namespace WarehouseAvatar.Tests
{
    /// <summary>
    /// Hands without a little finger (Avatar/Config/experiments_ab.md section 11 item 3): the worker template accepts them and shapes the
    /// fingers present, and a five-finger hand is shaped exactly as before (golden values computed by the code before the change).
    /// </summary>
    public class HandShapeFingersTests
    {
        static readonly CultureInfo Inv = CultureInfo.InvariantCulture;
        static WorkerV4Config Worker() => WorkerV4Config.Parse(File.ReadAllText(Path.Combine(Application.dataPath, "..", "Assets/WarehouseRobot/Avatar/Config/worker_v4.json")));

        readonly List<GameObject> m_Created = new List<GameObject>();

        [TearDown]
        public void TearDown()
        {
            foreach (var g in m_Created) if (g != null) Object.DestroyImmediate(g);
            m_Created.Clear();
        }

        TestRig Rig(params int[] remove)
        {
            var r = new TestRig();
            m_Created.Add(r.Root);
            foreach (bool right in new[] { false, true })
                foreach (int f in remove)
                {
                    var t = r.Get((right ? HumanBodyBones.RightThumbProximal : HumanBodyBones.LeftThumbProximal) + 3 * f);
                    if (t != null) Object.DestroyImmediate(t.gameObject);   // the finger's whole chain
                }
            return r;
        }

        static HandShapeSpec Shape(WorkerV4Config w, string name) =>
            name == "point" ? w.hand_shapes.point : name == "wait" ? w.hand_shapes.wait : name == "stop" ? w.hand_shapes.stop : w.hand_shapes.proceed;

        /// <summary>Every shape on both hands of a rig, two direction sets, as the template prepares the hands; the finger bases and tips.</summary>
        static List<float> ShapeAll(TestRig rig, WorkerV4Config w)
        {
            var left = HandShaper.BuildArm(rig, false);
            var right = HandShaper.BuildArm(rig, true);
            HandShaper.MirrorRest(right, left);
            var values = new List<float>();
            foreach (var a in new[] { left, right })
            {
                var bind = HandShaper.Capture(a);
                var restHand = a.Hand.localRotation;
                Vector3 side = a.IsRight ? Vector3.right : Vector3.left;
                foreach (var name in new[] { "point", "wait", "stop", "proceed" })
                    foreach (var (fingerDir, palm) in new[] { (Vector3.up, Vector3.forward), (side, Vector3.down) })
                    {
                        a.Hand.localRotation = restHand;
                        for (int f = 0; f < 5; f++) for (int j = 0; j < 3; j++) if (a.Fingers[f][j] != null) a.Fingers[f][j].localRotation = bind[f][j];
                        HandShaper.Apply(a, bind, Shape(w, name), fingerDir, palm, 1f);
                        for (int f = 0; f < 5; f++)
                        {
                            if (a.Fingers[f][0] == null) continue;
                            foreach (var p in new[] { a.Fingers[f][0].position, HandShaper.Tip(a, f) }) values.AddRange(new[] { p.x, p.y, p.z });
                        }
                    }
            }
            return values;
        }

        /// <summary>
        /// Computed by HandShaper as of e6c6bfd (before section 11), on TestRig with every finger: per hand (left, right), shape (point, wait,
        /// stop, proceed) and direction set (fingers up and palm forward; fingers to the side and palm down), each finger's base and tip (x, y, z).
        /// </summary>
        const string Golden =
            "-0.695000 1.480000 0.010000 -0.704740 1.506760 0.082169 -0.720000 1.520000 0.000000 -0.720000 1.610000 0.000000 -0.740000 1.520000 0.000000 -0.740000 1.485246 -0.004754 -0.760000 1.515000 0.000000 -0.760000 1.480246 -0.004754 -0.780000 1.510000 0.000000 -0.780000 1.475246 -0.004754 " +
            "-0.770000 1.440000 0.045000 -0.796759 1.367831 0.035260 -0.810000 1.450000 0.020000 -0.900000 1.450000 0.020000 -0.810000 1.450000 0.000000 -0.775246 1.454754 0.000000 -0.805000 1.450000 -0.020000 -0.770246 1.454754 -0.020000 -0.800000 1.450000 -0.040000 -0.765246 1.454754 -0.040000 " +
            "-0.695000 1.480000 0.010000 -0.702392 1.492803 0.082732 -0.720000 1.520000 0.000000 -0.720000 1.610000 0.000000 -0.740000 1.520000 0.000000 -0.740000 1.491809 -0.010261 -0.760000 1.515000 0.000000 -0.760000 1.486809 -0.010261 -0.780000 1.510000 0.000000 -0.780000 1.481809 -0.010261 " +
            "-0.770000 1.440000 0.045000 -0.782803 1.367268 0.037608 -0.810000 1.450000 0.020000 -0.900000 1.450000 0.020000 -0.810000 1.450000 0.000000 -0.781809 1.460261 0.000000 -0.805000 1.450000 -0.020000 -0.776809 1.460261 -0.020000 -0.800000 1.450000 -0.040000 -0.771809 1.460261 -0.040000 " +
            "-0.695000 1.480000 0.010000 -0.695000 1.570000 0.010000 -0.720000 1.520000 0.000000 -0.705921 1.608892 0.000000 -0.740000 1.520000 0.000000 -0.740000 1.610000 0.000000 -0.760000 1.515000 0.000000 -0.774079 1.603892 0.000000 -0.780000 1.510000 0.000000 -0.807812 1.595595 0.000000 " +
            "-0.770000 1.440000 0.045000 -0.860000 1.440000 0.045000 -0.810000 1.450000 0.020000 -0.898892 1.450000 0.034079 -0.810000 1.450000 0.000000 -0.900000 1.450000 0.000000 -0.805000 1.450000 -0.020000 -0.893892 1.450000 -0.034079 -0.800000 1.450000 -0.040000 -0.885595 1.450000 -0.067812 " +
            "-0.695000 1.480000 0.010000 -0.702705 1.568071 0.025589 -0.720000 1.520000 0.000000 -0.720000 1.608408 0.015589 -0.740000 1.520000 0.000000 -0.740000 1.608408 0.015589 -0.760000 1.515000 0.000000 -0.760000 1.603408 0.015589 -0.780000 1.510000 0.000000 -0.780000 1.598408 0.015589 " +
            "-0.770000 1.440000 0.045000 -0.858071 1.424411 0.037295 -0.810000 1.450000 0.020000 -0.898408 1.434411 0.020000 -0.810000 1.450000 0.000000 -0.898408 1.434411 0.000000 -0.805000 1.450000 -0.020000 -0.893408 1.434411 -0.020000 -0.800000 1.450000 -0.040000 -0.888408 1.434411 -0.040000 " +
            "0.695000 1.480000 0.010000 0.704740 1.506760 0.082169 0.720000 1.520000 0.000000 0.720000 1.610000 0.000000 0.740000 1.520000 0.000000 0.740000 1.485246 -0.004754 0.760000 1.515000 0.000000 0.760000 1.480246 -0.004754 0.780000 1.510000 0.000000 0.780000 1.475246 -0.004754 " +
            "0.770000 1.440000 0.045000 0.796759 1.367831 0.035260 0.810000 1.450000 0.020000 0.900000 1.450000 0.020000 0.810000 1.450000 0.000000 0.775246 1.454754 0.000000 0.805000 1.450000 -0.020000 0.770246 1.454754 -0.020000 0.800000 1.450000 -0.040000 0.765246 1.454754 -0.040000 " +
            "0.695000 1.480000 0.010000 0.702392 1.492803 0.082732 0.720000 1.520000 0.000000 0.720000 1.610000 0.000000 0.740000 1.520000 0.000000 0.740000 1.491809 -0.010261 0.760000 1.515000 0.000000 0.760000 1.486809 -0.010261 0.780000 1.510000 0.000000 0.780000 1.481809 -0.010261 " +
            "0.770000 1.440000 0.045000 0.782803 1.367268 0.037608 0.810000 1.450000 0.020000 0.900000 1.450000 0.020000 0.810000 1.450000 0.000000 0.781809 1.460261 0.000000 0.805000 1.450000 -0.020000 0.776809 1.460261 -0.020000 0.800000 1.450000 -0.040000 0.771809 1.460261 -0.040000 " +
            "0.695000 1.480000 0.010000 0.695000 1.570000 0.010000 0.720000 1.520000 0.000000 0.705921 1.608892 0.000000 0.740000 1.520000 0.000000 0.740000 1.610000 0.000000 0.760000 1.515000 0.000000 0.774079 1.603892 0.000000 0.780000 1.510000 0.000000 0.807812 1.595595 0.000000 " +
            "0.770000 1.440000 0.045000 0.860000 1.440000 0.045000 0.810000 1.450000 0.020000 0.898892 1.450000 0.034079 0.810000 1.450000 0.000000 0.900000 1.450000 0.000000 0.805000 1.450000 -0.020000 0.893892 1.450000 -0.034079 0.800000 1.450000 -0.040000 0.885595 1.450000 -0.067812 " +
            "0.695000 1.480000 0.010000 0.702705 1.568071 0.025589 0.720000 1.520000 0.000000 0.720000 1.608408 0.015589 0.740000 1.520000 0.000000 0.740000 1.608408 0.015589 0.760000 1.515000 0.000000 0.760000 1.603408 0.015589 0.780000 1.510000 0.000000 0.780000 1.598408 0.015589 " +
            "0.770000 1.440000 0.045000 0.858071 1.424411 0.037295 0.810000 1.450000 0.020000 0.898408 1.434411 0.020000 0.810000 1.450000 0.000000 0.898408 1.434411 0.000000 0.805000 1.450000 -0.020000 0.893408 1.434411 -0.020000 0.800000 1.450000 -0.040000 0.888408 1.434411 -0.040000";

        [Test]
        public void FiveFingerHand_IsShapedExactlyAsBeforeSection11()
        {
            var now = ShapeAll(Rig(), Worker());
            string written = string.Join(" ", now.Select(v => v.ToString("0.000000", Inv)));
            Assert.IsNotEmpty(Golden, "golden values missing; computed now: " + written);
            var golden = Golden.Split(' ').Select(s => float.Parse(s, Inv)).ToArray();
            Assert.AreEqual(golden.Length, now.Count, "number of values");
            for (int i = 0; i < golden.Length; i++) Assert.AreEqual(golden[i], now[i], 2e-6f, $"value {i}");
        }

        [Test]
        public void HandWithoutLittleFinger_IsAccepted_AndEveryShapeUsesTheFingersPresent()
        {
            var w = Worker();
            var rig = Rig(HandShaper.Little);
            foreach (bool right in new[] { false, true })
            {
                var arm = HandShaper.BuildArm(rig, right);
                Assert.IsTrue(arm.Fingers[HandShaper.Little][0] == null, "no little finger");   // Unity's null: the bone was destroyed
                Assert.IsTrue(HandShaper.Complete(arm), "index, middle and ring present: the template accepts the hand");
                var bind = HandShaper.Capture(arm);
                var toRobot = new Vector3(right ? -0.2f : 0.2f, 0f, -1f).normalized;
                Vector3 Dir(int f) => (arm.Fingers[f][2].position - arm.Fingers[f][0].position).normalized;
                float before = Vector3.Angle(Dir(HandShaper.Index), Dir(HandShaper.Ring));   // the rest pose

                HandShaper.Apply(arm, bind, w.hand_shapes.wait, Vector3.up, toRobot, 1f);
                Assert.Greater(HandShaper.TipRatio(arm, HandShaper.Index), 1.6f, "WAIT: index extended");
                foreach (int f in new[] { HandShaper.Middle, HandShaper.Ring }) Assert.Less(HandShaper.TipRatio(arm, f), 1.0f, $"WAIT: finger {f} curled");
                Assert.IsTrue(HandShaper.HandAxes(arm, out var fingerDir, out var palm), "hand axes from index and ring");
                Assert.Greater(Vector3.Dot(fingerDir, Vector3.up), 0.99f, "WAIT: fingers up");
                Assert.Greater(Vector3.Dot(palm, toRobot), 0.99f, "WAIT: palm toward the robot");

                HandShaper.Apply(arm, bind, w.hand_shapes.stop, Vector3.up, toRobot, 1f);
                for (int f = HandShaper.Index; f <= HandShaper.Ring; f++) Assert.Greater(HandShaper.TipRatio(arm, f), 1.6f, $"STOP: finger {f} extended");
                Assert.IsTrue(HandShaper.HandAxes(arm, out _, out palm));
                Assert.Greater(Vector3.Dot(palm, toRobot), 0.99f, "STOP: palm toward the robot");
                Assert.Greater(Vector3.Angle(Dir(HandShaper.Index), Dir(HandShaper.Ring)), before + 1.5f * w.hand_shapes.stop.spread_deg, "STOP: fingers spread");

                // the thumb swings across the palm toward the outermost finger present (the ring finger here)
                var flat = new HandShapeSpec { thumb_deg = new[] { 0f, 0f, 0f }, index_deg = new[] { 0f, 0f, 0f }, middle_deg = new[] { 0f, 0f, 0f },
                                               ring_deg = new[] { 0f, 0f, 0f }, little_deg = new[] { 0f, 0f, 0f } };
                HandShaper.Apply(arm, bind, flat, Vector3.up, toRobot, 1f);
                float apart = Vector3.Distance(HandShaper.Tip(arm, HandShaper.Thumb), arm.Fingers[HandShaper.Ring][0].position);
                flat.thumb_across_deg = 30f;
                HandShaper.Apply(arm, bind, flat, Vector3.up, toRobot, 1f);
                Assert.Less(Vector3.Distance(HandShaper.Tip(arm, HandShaper.Thumb), arm.Fingers[HandShaper.Ring][0].position), apart, "thumb toward the ring finger");
            }
        }

        static HandShapeSpec Straight(float goal) => new HandShapeSpec
        {
            thumb_deg = new[] { 0f, 0f, 0f }, index_deg = new[] { 0f, 0f, 0f }, middle_deg = new[] { 95f, 105f, 75f }, ring_deg = new[] { 95f, 105f, 75f },
            little_deg = new[] { 95f, 105f, 75f }, thumb_tuck_max_palm_lengths = goal, thumb_tuck_side_l = 0.25f,
        };

        static float ThumbLp(LookPoser.Arm a)
        {
            var f = HandGeometry.Frame(a);
            return Vector3.Distance(HandShaper.Tip(a, HandShaper.Thumb), f.P) / f.Lp;
        }

        [Test]
        public void ThumbTuck_TucksAThumbThatSticksOut_OnThePalmSide_ForAnyHandOrientation()
        {
            foreach (bool right in new[] { false, true })
                foreach (int[] remove in new[] { new int[0], new[] { HandShaper.Little } })
                {
                    var rig = Rig(remove);
                    var arm = HandShaper.BuildArm(rig, right);
                    var bind = HandShaper.Capture(arm);
                    var shape = Straight(0.95f);
                    HandShaper.Apply(arm, bind, shape, Vector3.up, Vector3.back, 1f);
                    float before = ThumbLp(arm);
                    Assert.Greater(before, 0.95f, "the straight thumb sticks out");
                    var restHand = arm.Hand.localRotation;
                    arm.Hand.localRotation = restHand;
                    for (int f = 0; f < 5; f++) for (int j = 0; j < 3; j++) if (arm.Fingers[f][j] != null) arm.Fingers[f][j].localRotation = bind[f][j];
                    var tuck = HandShaper.ThumbTuck(arm, bind, shape);
                    Assert.IsTrue(tuck.Active);
                    Assert.AreEqual(before, tuck.BeforeLp, 1e-3f);
                    Assert.LessOrEqual(tuck.AfterLp, 0.95f + 1e-4f);
                    // the tuck holds for any hand orientation (it is relative to the hand)
                    foreach (var (fingerDir, palm) in new[] { (Vector3.up, Vector3.back), (Vector3.up, new Vector3(0.6f, 0f, -0.8f)), (right ? Vector3.right : Vector3.left, Vector3.down) })
                    {
                        HandShaper.Apply(arm, bind, shape, fingerDir, palm, 1f, tuck);
                        Assert.LessOrEqual(ThumbLp(arm), 0.95f + 1e-3f, $"tucked ({fingerDir}, {palm})");
                        var fr = HandGeometry.Frame(arm);
                        Assert.GreaterOrEqual(Vector3.Dot(HandShaper.Tip(arm, HandShaper.Thumb) - fr.P, fr.Normal), 0f, "on the palm side");
                    }
                }
        }

        [Test]
        public void ThumbTuck_LeavesAThumbWithinTheGoalUntouched_AndIsOffAtZero()
        {
            var w = Worker();
            var rig = Rig();
            var arm = HandShaper.BuildArm(rig, true);
            var bind = HandShaper.Capture(arm);
            var wide = Straight(5f);
            Assert.IsFalse(HandShaper.ThumbTuck(arm, bind, wide).Active, "already within 5 palm lengths");
            Assert.IsFalse(HandShaper.ThumbTuck(arm, bind, Straight(0f)).Active, "0 = off");
            Assert.IsFalse(HandShaper.ThumbTuck(arm, bind, w.hand_shapes.stop).Active, "only WAIT carries a goal");
            CollectionAssert.AreEqual(bind.SelectMany(x => x), HandShaper.Capture(arm).SelectMany(x => x), "the bones are restored");
            Assert.AreEqual(0.95f, w.hand_shapes.wait.thumb_tuck_max_palm_lengths);
            Assert.AreEqual(0.25f, w.hand_shapes.wait.thumb_tuck_side_l);
            foreach (var s in new[] { w.hand_shapes.point, w.hand_shapes.stop, w.hand_shapes.proceed }) Assert.AreEqual(0f, s.thumb_tuck_max_palm_lengths);
        }

        [Test]
        public void HandWithoutRingFinger_IsRefused()
        {
            var rig = Rig(HandShaper.Ring, HandShaper.Little);
            Assert.IsFalse(HandShaper.Complete(HandShaper.BuildArm(rig, false)));
            Assert.IsFalse(HandShaper.Complete(HandShaper.BuildArm(rig, true)));
            var noMiddle = Rig(HandShaper.Middle);
            Assert.IsFalse(HandShaper.Complete(HandShaper.BuildArm(noMiddle, true)), "the middle finger gives the hand's axis");
        }

        [Test]
        public void PalmNormal_UsesTheOutermostFingerPresent()
        {
            var five = Rig();
            var four = Rig(HandShaper.Little);
            foreach (bool right in new[] { false, true })
            {
                var a5 = HandShaper.BuildArm(five, right);
                var a4 = HandShaper.BuildArm(four, right);
                Assert.IsTrue(LookPoser.PalmNormal(a5, Vector3.right, out var n5));
                Assert.IsTrue(LookPoser.PalmNormal(a4, Vector3.right, out var n4));
                Assert.Greater(Vector3.Dot(n5, n4), 0.99f, "index-to-ring gives the palm side index-to-little gives");
            }
        }
    }
}
