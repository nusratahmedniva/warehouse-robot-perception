using System.IO;
using System.Linq;
using NUnit.Framework;
using UnityEngine;

namespace WarehouseAvatar.Tests
{
    /// <summary>
    /// Arm scaling and its geometric check (Avatar/Config/experiments_ab.md section 10): the rig's proportions, the target formula with the
    /// legacy (Sunbox) and the rig's own split, the two-bone elbow angle, and the declared tolerance (gesture_geometry.json).
    /// </summary>
    public class GestureGeometryTests
    {
        static string Project(string rel) => File.ReadAllText(Path.Combine(Application.dataPath, "..", rel));
        static WorkerV4Config Worker() => WorkerV4Config.Parse(Project("Assets/WarehouseRobot/Avatar/Config/worker_v4.json"));
        static GestureGeometryConfig Geometry() => GestureGeometryConfig.Parse(Project("Assets/WarehouseRobot/Avatar/Config/gesture_geometry.json"));

        static readonly Vector3 S = new Vector3(0.2f, 1.4f, 0f), Side = Vector3.right, Fwd = Vector3.forward;

        [Test]
        public void GeometryConfig_IsValid_AndHoldsTheDeclaredTolerance()
        {
            var g = Geometry();
            CollectionAssert.IsEmpty(g.Validate());
            Assert.AreEqual(10f, g.tolerance.elbow_angle_deg);
            Assert.AreEqual(5f, g.tolerance.arm_direction_deg);
            Assert.AreEqual(10f, g.tolerance.forearm_direction_deg);
            Assert.AreEqual(120f, g.tolerance.no_fold_min_elbow_deg);
            CollectionAssert.AreEquivalent(new[] { "POINT", "STOP" }, g.tolerance.no_fold_commands);
            CollectionAssert.AreEquivalent(new[] { "anime", "cartoon_non_human" }, g.screens.kind_groups);
        }

        [Test]
        public void TwoBoneElbow_StraightRightAngleAndFolded()
        {
            Assert.AreEqual(180f, GestureGeometry.TwoBoneElbowDeg(0.3f, 0.25f, 0.55f), 1e-3f);
            Assert.AreEqual(180f, GestureGeometry.TwoBoneElbowDeg(0.3f, 0.25f, 0.70f), 1e-3f, "out of reach: straight");
            Assert.AreEqual(90f, GestureGeometry.TwoBoneElbowDeg(3f, 4f, 5f), 1e-3f);
            Assert.AreEqual(0f, GestureGeometry.TwoBoneElbowDeg(0.3f, 0.25f, 0.04f), 1e-3f);
            Assert.AreEqual(60f, GestureGeometry.TwoBoneElbowDeg(1f, 1f, 1f), 1e-3f);
        }

        static GeometrySample Sample(string cmd, Vector3 e, Vector3 w, Vector3 target, float upper = 0.3f, float fore = 0.25f) => new GeometrySample
        {
            Command = cmd, S = Vector3.zero, E = e, W = w, Upper = upper, Fore = fore,
            Goal = new GestureGoal { Shoulder = Vector3.zero, Target = target, Valid = true },
        };

        [Test]
        public void Evaluate_StraightPointPasses_FoldedPointFails()
        {
            var tol = Geometry().tolerance;
            var ok = GestureGeometry.Evaluate(Sample("POINT", new Vector3(0.3f, 0f, 0f), new Vector3(0.55f, 0f, 0f), new Vector3(0.55f, 0f, 0f)), tol);
            Assert.IsTrue(ok.Pass, ok.Why);
            Assert.AreEqual(180f, ok.ElbowDeg, 1e-3f);
            // the hand on target but the forearm folded back (an arm whose bones do not match its lengths): the elbow closes to ~33 deg
            Vector3 e = new Vector3(0.3f, 0f, 0f), w = e + Quaternion.AngleAxis(147f, Vector3.forward) * new Vector3(0.25f, 0f, 0f);
            var bad = GestureGeometry.Evaluate(Sample("POINT", e, w, w), tol);
            Assert.IsFalse(bad.Pass);
            Assert.IsTrue(bad.Fold);
            StringAssert.Contains("fold", bad.Why);
            // a wrong direction: the wrist 10 deg off the target's direction
            var off = GestureGeometry.Evaluate(Sample("STOP", e, Quaternion.AngleAxis(10f, Vector3.up) * new Vector3(0.55f, 0f, 0f), new Vector3(0.55f, 0f, 0f)), tol);
            Assert.IsFalse(off.Pass);
            StringAssert.Contains("arm direction", off.Why);
        }

        [Test]
        public void Evaluate_WaitForearmMustBeVertical_ProceedForearmMustFollowItsGoal()
        {
            var tol = Geometry().tolerance;
            Vector3 e = new Vector3(0.25f, -0.15f, 0.05f);
            Vector3 w = e + Vector3.up * 0.25f;
            var ok = Sample("WAIT", e, w, w);
            ok.Goal.Target = w;
            Assert.IsTrue(GestureGeometry.Evaluate(ok, tol).Pass);
            var tilted = Sample("WAIT", e, e + Quaternion.AngleAxis(25f, Vector3.forward) * Vector3.up * 0.25f, Vector3.zero);
            tilted.Goal.Target = tilted.W;
            var r = GestureGeometry.Evaluate(tilted, tol);
            Assert.IsFalse(r.Pass);
            StringAssert.Contains("forearm", r.Why);

            var p = Sample("PROCEED", e, e + Vector3.forward * 0.25f, e + Vector3.forward * 0.25f);
            p.Goal.HasElbow = true;
            p.Goal.Elbow = e;
            Assert.IsTrue(GestureGeometry.Evaluate(p, tol).Pass);
            p.Goal.Elbow = e + new Vector3(0f, 0.1f, -0.05f);   // the intended elbow elsewhere: the forearm points the wrong way
            Assert.IsFalse(GestureGeometry.Evaluate(p, tol).Pass);
        }

        /// <summary>The formula of WorkerV4.ComputeTargets before experiments_ab.md section 10 (copied from 085e4ff), sway left out.</summary>
        static (Vector3 target, Vector3 hint) OldFormula(GestureClipSpec spec, WorkerLimits lim, float L, Vector3 s, Vector3 side, Vector3 fwd, Vector3 pointDir,
                                                         float k, float elevation, float phi, float push)
        {
            Vector3 up = Vector3.up;
            switch (spec.command)
            {
                case "POINT":
                {
                    float el = elevation * k;
                    Vector3 d = (Mathf.Cos(el * Mathf.Deg2Rad) * pointDir.normalized + Mathf.Sin(el * Mathf.Deg2Rad) * up).normalized;
                    float reach = Mathf.Clamp(spec.reach, lim.point_reach[0], lim.point_reach[1]);
                    return (s + d * (L * reach), s + d * (0.5f * L) - up * (spec.elbow_down_l * L));
                }
                case "PROCEED":
                {
                    float Lu = 0.53f * L, Lf = 0.47f * L;
                    float au = spec.upper_forward_deg * Mathf.Deg2Rad;
                    Vector3 elbow = s + Lu * (Mathf.Cos(au) * -up + Mathf.Sin(au) * fwd) + side * (0.08f * L);
                    float pr = phi * Mathf.Deg2Rad;
                    return (elbow + (Mathf.Cos(pr) * fwd + Mathf.Sin(pr) * up) * Lf, elbow + side * (0.1f * L) - up * (0.02f * L));
                }
                case "WAIT":
                {
                    float upL = Mathf.Max(spec.hand_up_l * k, lim.wait_min_up_l);
                    Vector3 t = s + L * (side * (spec.hand_side_l * k) + fwd * (spec.hand_forward_l * k) + up * upL);
                    return (t, t - up * (0.5f * L) + side * (spec.elbow_down_l * L));
                }
                default:
                {
                    float az = spec.azimuth_out_deg * Mathf.Deg2Rad, el = spec.elevation_deg * Mathf.Deg2Rad;
                    Vector3 h = Mathf.Cos(az) * fwd + Mathf.Sin(az) * side;
                    Vector3 d = (Mathf.Cos(el) * h + Mathf.Sin(el) * up).normalized;
                    float reach = Mathf.Clamp(spec.reach * k, lim.stop_reach[0], lim.stop_reach[1]);
                    return (s + d * (L * reach) + fwd * push, s + d * (0.5f * L) - up * (spec.elbow_down_l * L) + side * (0.05f * L));
                }
            }
        }

        [Test]
        public void LegacySplit_ReproducesTheFormulaBeforeSection10_ForEveryClip()
        {
            var w = Worker();
            const float L = 0.56f;
            var pointDir = Quaternion.AngleAxis(60f, Vector3.up) * Fwd;
            foreach (var spec in w.clips)
            {
                var g = GestureTargets.Compute(spec, w.limits, ArmSplit.Legacy(L), S, Side, Fwd, pointDir, 1.05f, 8f, 35f, 0.02f);
                var old = OldFormula(spec, w.limits, L, S, Side, Fwd, pointDir, 1.05f, 8f, 35f, spec.command == "STOP" ? 0.02f : 0f);
                Assert.Less(Vector3.Distance(g.Target, old.target), 1e-5f, spec.name + " target");
                Assert.Less(Vector3.Distance(g.Hint, old.hint), 1e-5f, spec.name + " hint");
            }
        }

        [Test]
        public void RigSplit_PlacesTheProceedElbowOnTheUpperArmAndTheHandOnTheForearm_ForAnyProportions()
        {
            var w = Worker();
            foreach (var share in new[] { 0.45f, 0.53f, 0.62f })
            {
                var p = new ArmProportions { upper_m = 0.44f * share, forearm_m = 0.44f * (1f - share), shoulder_width_m = 0.2f, shoulder_height_m = 1.3f };
                var a = ArmSplit.Rig(p);
                foreach (var spec in w.clips.Where(c => c.command == "PROCEED"))
                    foreach (var phi in new[] { -20f, 0f, 40f, 75f })
                    {
                        var g = GestureTargets.Compute(spec, w.limits, a, S, Side, Fwd, Fwd, 1f, 0f, phi, 0f);
                        Assert.IsTrue(g.HasElbow);
                        Assert.AreEqual(p.upper_m, Vector3.Distance(g.Elbow, S), 1e-5f, $"{spec.name} share {share}: elbow at the upper arm's length");
                        Assert.AreEqual(p.forearm_m, Vector3.Distance(g.Target, g.Elbow), 1e-5f, $"{spec.name} share {share}: hand at the forearm's length");
                    }
                // hints: POINT and STOP at the upper arm along the arm, WAIT the forearm below the hand
                var point = w.clips.First(c => c.command == "POINT");
                var gp = GestureTargets.Compute(point, w.limits, a, S, Side, Fwd, Side, 1f, 0f, 0f, 0f);
                Assert.AreEqual(p.upper_m, Vector3.Dot(gp.Hint - S, Side), 1e-5f);
                var wait = w.clips.First(c => c.command == "WAIT");
                var gw = GestureTargets.Compute(wait, w.limits, a, S, Side, Fwd, Fwd, 1f, 0f, 0f, 0f);
                Assert.AreEqual(-p.forearm_m, Vector3.Dot(gw.Hint - gw.Target, Vector3.up), 1e-5f);
            }
        }

        [Test]
        public void RigSplit_EqualsLegacyTargets_ExceptProceed()
        {
            var w = Worker();
            var p = new ArmProportions { upper_m = 0.30f, forearm_m = 0.26f };
            foreach (var spec in w.clips.Where(c => c.command != "PROCEED"))
            {
                var rig = GestureTargets.Compute(spec, w.limits, ArmSplit.Rig(p), S, Side, Fwd, Side, 1f, 5f, 0f, 0f);
                var old = GestureTargets.Compute(spec, w.limits, ArmSplit.Legacy(p.Arm), S, Side, Fwd, Side, 1f, 5f, 0f, 0f);
                Assert.Less(Vector3.Distance(rig.Target, old.Target), 1e-6f, spec.name + ": the hand target depends on L only");
            }
        }

        [Test]
        public void Proportions_AreMeasuredFromTheBones()
        {
            var root = new GameObject("root").transform;
            try
            {
                LookPoser.Arm Arm(float x, float sign)
                {
                    Transform T(string n, Vector3 p) { var t = new GameObject(n).transform; t.SetParent(root, false); t.position = p; return t; }
                    return new LookPoser.Arm
                    {
                        Upper = T("u", new Vector3(sign * x, 1.40f, 0f)), Lower = T("l", new Vector3(sign * (x + 0.28f), 1.40f, 0f)),
                        Hand = T("h", new Vector3(sign * (x + 0.28f + 0.24f), 1.40f, 0f)),
                    };
                }
                var p = ArmProportions.Measure(Arm(0.1f, -1f), Arm(0.1f, 1f), root);
                Assert.AreEqual(0.28f, p.upper_m, 1e-5f);
                Assert.AreEqual(0.24f, p.forearm_m, 1e-5f);
                Assert.AreEqual(0.52f, p.Arm, 1e-5f);
                Assert.AreEqual(0.2f, p.shoulder_width_m, 1e-5f);
                Assert.AreEqual(1.4f, p.shoulder_height_m, 1e-5f);
            }
            finally { Object.DestroyImmediate(root.gameObject); }
        }
    }
}
