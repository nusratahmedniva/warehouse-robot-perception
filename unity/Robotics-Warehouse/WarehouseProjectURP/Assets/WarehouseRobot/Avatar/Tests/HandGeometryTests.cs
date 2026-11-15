using System.Collections.Generic;
using System.IO;
using NUnit.Framework;
using UnityEngine;

namespace WarehouseAvatar.Tests
{
    /// <summary>The hand check of the geometry check (Avatar/Config/experiments_ab.md section 12): palm normals and the WAIT thumb.</summary>
    public class HandGeometryTests
    {
        static GestureGeometryConfig Geometry() => GestureGeometryConfig.Parse(File.ReadAllText(Path.Combine(Application.dataPath, "..", "Assets/WarehouseRobot/Avatar/Config/gesture_geometry.json")));
        static WorkerV4Config Worker() => WorkerV4Config.Parse(File.ReadAllText(Path.Combine(Application.dataPath, "..", "Assets/WarehouseRobot/Avatar/Config/worker_v4.json")));

        readonly List<GameObject> m_Created = new List<GameObject>();

        [TearDown]
        public void TearDown()
        {
            foreach (var g in m_Created) if (g != null) Object.DestroyImmediate(g);
            m_Created.Clear();
        }

        [Test]
        public void Config_HoldsTheDeclaredHandTolerance()
        {
            var t = Geometry().tolerance;
            CollectionAssert.IsEmpty(Geometry().Validate());
            Assert.AreEqual(30f, t.palm_facing_deg);
            CollectionAssert.AreEquivalent(new[] { "STOP", "WAIT" }, t.palm_commands);
            Assert.AreEqual(1.0f, t.thumb_tip_max_palm_lengths);
            Assert.AreEqual(0.0f, t.thumb_palm_side_min);
            Assert.AreEqual(30, t.palm_mesh_min_vertices);
            Assert.AreEqual(0.5f, t.palm_mesh_flatness_max);
            Assert.AreEqual(0.5f, t.palm_hand_weight_min);
        }

        [Test]
        public void Eigen3_FindsTheAxesOfARotatedEllipsoid()
        {
            var q = Quaternion.Euler(25f, 40f, -15f);
            var rot = Matrix4x4.Rotate(q);
            double[] lam = { 9.0, 4.0, 0.25 };
            var m = new double[3, 3];
            for (int i = 0; i < 3; i++)
                for (int j = 0; j < 3; j++)
                    for (int k = 0; k < 3; k++) m[i, j] += rot[i, k] * lam[k] * rot[j, k];
            HandGeometry.Eigen3(m, out var values, out var vectors);
            int lo = 0;
            for (int i = 1; i < 3; i++) if (values[i] < values[lo]) lo = i;
            Assert.AreEqual(0.25, values[lo], 1e-6);
            var v = new Vector3((float)vectors[0, lo], (float)vectors[1, lo], (float)vectors[2, lo]);
            Assert.Greater(Mathf.Abs(Vector3.Dot(v.normalized, q * Vector3.forward)), 0.9999f, "the least-variance axis");
        }

        static List<Vector3> Plate(Vector3 centre, Vector3 a, Vector3 b, float sa, float sb, float thickness, Vector3 n)
        {
            var pts = new List<Vector3>();
            var rnd = new System.Random(3);
            for (int i = 0; i < 12; i++)
                for (int j = 0; j < 10; j++)
                    pts.Add(centre + a * (sa * (i / 11f - 0.5f)) + b * (sb * (j / 9f - 0.5f)) + n * (thickness * ((float)rnd.NextDouble() - 0.5f)));
            return pts;
        }

        [Test]
        public void MeshNormal_IsThePlateNormal_SignedByTheReference_AndUndeterminedForABlob()
        {
            var n = new Vector3(0.2f, 0.3f, -1f).normalized;
            var a = Vector3.Cross(n, Vector3.up).normalized;
            var b = Vector3.Cross(n, a);
            var plate = Plate(new Vector3(1f, 1.4f, 0.5f), a, b, 0.09f, 0.08f, 0.02f, n);
            Assert.IsTrue(HandGeometry.MeshNormal(plate, -n, 30, 0.5f, out var got, out float flat));
            Assert.Less(Vector3.Angle(got, -n), 1.0f, "the plate's normal, on the reference's side");
            Assert.Less(flat, 0.2f);
            var blob = Plate(Vector3.zero, a, b, 0.05f, 0.05f, 0.05f, n);
            Assert.IsFalse(HandGeometry.MeshNormal(blob, n, 30, 0.5f, out _, out flat), "as thick as it is wide: undetermined");
            Assert.IsFalse(HandGeometry.MeshNormal(plate.GetRange(0, 20), n, 30, 0.5f, out _, out _), "fewer than the minimum");
        }

        TestRig Rig()
        {
            var r = new TestRig();
            m_Created.Add(r.Root);
            return r;
        }

        [Test]
        public void Evaluate_StopPalmTowardTheCamera_Passes_PalmSidewaysFails_BonesAndMesh()
        {
            var tol = Geometry().tolerance;
            var rig = Rig();
            var arm = HandShaper.BuildArm(rig, true);
            var bind = HandShaper.Capture(arm);
            var camera = arm.Hand.position + new Vector3(0f, -0.3f, -2f);
            HandShaper.Apply(arm, bind, Worker().hand_shapes.stop, Vector3.up, Vector3.back, 1f);
            var f = HandGeometry.Frame(arm);
            Assert.IsTrue(f.Valid);
            var b = Vector3.Cross(f.Normal, f.FingerDir).normalized;
            var plate = Plate(f.P, f.FingerDir, b, 0.08f, 0.07f, 0.01f, f.Normal);
            var ok = HandGeometry.Evaluate("STOP", f, plate, camera, false, Vector3.zero, tol);
            Assert.IsTrue(ok.Pass, ok.Why);
            Assert.IsTrue(ok.MeshDetermined);
            Assert.Less(ok.BoneAngleDeg, 15f, "the palm faces the horizontal; the camera is a little lower");
            // a mesh plate edge-on to the camera (its normal across the hand) fails even though the bones face it
            var edge = Plate(f.P, f.FingerDir, f.Normal, 0.08f, 0.07f, 0.01f, b);
            var bad = HandGeometry.Evaluate("STOP", f, edge, camera, false, Vector3.zero, tol);
            Assert.IsFalse(bad.Pass);
            StringAssert.Contains("palm (mesh)", bad.Why);
            // the palm turned sideways: the bones fail
            HandShaper.Apply(arm, bind, Worker().hand_shapes.stop, Vector3.up, Vector3.right, 1f);
            var side = HandGeometry.Evaluate("STOP", HandGeometry.Frame(arm), null, camera, false, Vector3.zero, tol);
            Assert.IsFalse(side.Pass);
            StringAssert.Contains("palm (bones)", side.Why);
            Assert.IsFalse(side.MeshDetermined, "no mesh vertices: mesh n/a, never a pass of the mesh part");
        }

        [Test]
        public void Evaluate_WaitThumb_TuckedPasses_SticksOutOrBehindFails()
        {
            var tol = Geometry().tolerance;
            var rig = Rig();
            var arm = HandShaper.BuildArm(rig, true);
            var bind = HandShaper.Capture(arm);
            HandShaper.Apply(arm, bind, Worker().hand_shapes.wait, Vector3.up, Vector3.back, 1f);
            var f = HandGeometry.Frame(arm);
            var camera = f.P + Vector3.back * 2f;
            Vector3 across = (f.OuterBase - f.IndexBase).normalized;
            var tucked = HandGeometry.Evaluate("WAIT", f, null, camera, true, f.P + f.Normal * (0.3f * f.Lp) + across * (0.2f * f.Lp), tol);
            Assert.IsTrue(tucked.Pass, tucked.Why);
            Assert.AreEqual(0.3f, tucked.ThumbSide, 1e-4f);
            var out1 = HandGeometry.Evaluate("WAIT", f, null, camera, true, f.P - across * (1.5f * f.Lp), tol);
            Assert.IsFalse(out1.Pass);
            StringAssert.Contains("thumb sticks out", out1.Why);
            Assert.Less(out1.ThumbAcross, 0f, "outside the index side");
            var behind = HandGeometry.Evaluate("WAIT", f, null, camera, true, f.P - f.Normal * (0.2f * f.Lp), tol);
            Assert.IsFalse(behind.Pass);
            StringAssert.Contains("thumb behind the palm", behind.Why);
            var stop = HandGeometry.Evaluate("STOP", f, null, camera, true, f.P - across * (1.5f * f.Lp), tol);
            Assert.IsTrue(stop.Pass, "the thumb rule is WAIT's only");
        }
    }
}
