using System.Collections.Generic;
using System.IO;
using System.Linq;
using NUnit.Framework;
using UnityEngine;

namespace WarehouseAvatar.Tests
{
    /// <summary>The skinning checks (Avatar/Config/experiments_ab.md section 12 addendum 5) on synthetic meshes.</summary>
    public class SkinGeometryTests
    {
        static GestureGeometryConfig Geometry() => GestureGeometryConfig.Parse(File.ReadAllText(Path.Combine(Application.dataPath, "..", "Assets/WarehouseRobot/Avatar/Config/gesture_geometry.json")));

        [Test]
        public void Config_HoldsTheDeclaredSkinningLimits()
        {
            var g = Geometry();
            CollectionAssert.IsEmpty(g.Validate());
            var s = g.skinning;
            Assert.AreEqual(5, s.forearm_bands);
            Assert.AreEqual(8, s.forearm_min_band_vertices);
            Assert.AreEqual(0.70f, s.forearm_min_ratio, 1e-6f);
            Assert.AreEqual(0.5f, s.forearm_weight_min);
            CollectionAssert.AreEqual(new[] { "Hips", "Spine", "Chest", "UpperChest" }, s.torso_bones);
            Assert.AreEqual(0.5f, s.torso_weight_min);
            Assert.AreEqual(95, s.torso_percentile);
            Assert.AreEqual(0.02125f, s.torso_max_displacement_m, 1e-6f, "addendum 8: worst core p95 of the professionally rigged looks x 1.25");
            Assert.AreEqual(5, s.proceed_frames);
            Assert.AreEqual(0.4f, s.torso_core_shoulder_zone_lu, 1e-6f, "addendum 7: the shoulder zone");
        }

        [Test]
        public void CoreMask_LeavesOutTheShoulderZones()
        {
            var shoulders = new[] { new Vector3(-0.17f, 1.45f, 0f), new Vector3(0.17f, 1.45f, 0f) };
            var pts = new[] { new Vector3(0f, 1.2f, 0.1f), new Vector3(0.15f, 1.40f, 0.05f), new Vector3(-0.2f, 1.5f, 0f), new Vector3(0.05f, 1.45f, 0.1f) };
            var core = SkinGeometry.CoreMask(pts, shoulders, 0.4f * 0.28f);
            CollectionAssert.AreEqual(new[] { true, false, false, true }, core);
        }

        /// <summary>A tube from e to w, radius r(t) along it, 12 points per ring, 21 rings.</summary>
        static List<Vector3> Tube(Vector3 e, Vector3 w, System.Func<float, float> r)
        {
            var pts = new List<Vector3>();
            Vector3 d = (w - e).normalized, a = Vector3.Cross(d, Vector3.up).sqrMagnitude > 1e-6f ? Vector3.Cross(d, Vector3.up).normalized : Vector3.right;
            Vector3 b = Vector3.Cross(d, a);
            for (int k = 0; k <= 20; k++)
            {
                float t = k / 20f;
                for (int i = 0; i < 12; i++)
                {
                    float ang = i * Mathf.PI * 2f / 12f;
                    pts.Add(Vector3.Lerp(e, w, t) + r(t) * (Mathf.Cos(ang) * a + Mathf.Sin(ang) * b));
                }
            }
            return pts;
        }

        [Test]
        public void ForearmBands_KeepVolumeUnderABend_AndCatchACone()
        {
            Vector3 e0 = new Vector3(0f, 1.2f, 0f), w0 = new Vector3(0f, 0.95f, 0f);
            var rest = Tube(e0, w0, t => 0.04f);
            var band = SkinGeometry.Bands(rest, e0, w0, 5, 8);
            Assert.AreEqual(5, band.Where(x => x >= 0).Distinct().Count(), "five bands");
            var r0 = SkinGeometry.BandRadii(rest, band, 5, e0, w0);
            foreach (var r in r0) Assert.AreEqual(0.04f, r, 1e-4f);
            // the same tube raised (forearm up): the same vertices in the same order keep their radius
            Vector3 e1 = new Vector3(0.3f, 1.4f, 0.1f), w1 = e1 + new Vector3(0f, 0.25f, 0.02f);
            var raised = Tube(e1, w1, t => 0.04f);
            Assert.AreEqual(1f, SkinGeometry.MinRatio(r0, SkinGeometry.BandRadii(raised, band, 5, e1, w1)), 1e-3f);
            // v2's collapse: the tube narrows into a cone toward the wrist
            var cone = Tube(e1, w1, t => 0.04f * (1f - 0.8f * t));
            float ratio = SkinGeometry.MinRatio(r0, SkinGeometry.BandRadii(cone, band, 5, e1, w1));
            Assert.Less(ratio, 0.70f, "a cone fails the check");
            // too few vertices in a band: the band is skipped
            var sparse = SkinGeometry.Bands(rest.Take(30).ToList(), e0, w0, 5, 8);
            Assert.IsTrue(sparse.All(x => x <= 0), "only the first band has enough points");
            Assert.IsNaN(SkinGeometry.MinRatio(new[] { float.NaN }, new[] { 1f }));
        }

        [Test]
        public void TorsoInBoneFrame_IgnoresRigidBoneMotion_AndMeasuresDeformation()
        {
            Vector3 bonePos = new Vector3(0f, 1.3f, 0f);
            Quaternion boneRot = Quaternion.Euler(0f, 10f, 0f);
            Vector3 p = new Vector3(0.1f, 1.35f, 0.12f);
            var before = SkinGeometry.InBone(p, bonePos, boneRot);
            // the spine turns and leans: the vertex rides along rigidly
            Quaternion turn = Quaternion.Euler(5f, 30f, 0f);
            Vector3 moved = bonePos + new Vector3(0.02f, 0f, 0f) + turn * (p - bonePos);
            var after = SkinGeometry.InBone(moved, bonePos + new Vector3(0.02f, 0f, 0f), turn * boneRot);
            Assert.Less(Vector3.Distance(before, after), 1e-5f, "rigid motion is not deformation");
            // pulled 2 cm by an arm bone: measured as 2 cm
            var pulled = SkinGeometry.InBone(p + new Vector3(0.02f, 0f, 0f), bonePos, boneRot);
            Assert.AreEqual(0.02f, Vector3.Distance(before, pulled), 1e-5f);
        }

        [Test]
        public void Percentile_IsNearestRank()
        {
            var v = Enumerable.Range(1, 100).Select(i => i / 1000f).ToList();
            Assert.AreEqual(0.095f, SkinGeometry.Percentile(v, 95f), 1e-6f);
            Assert.AreEqual(0.1f, SkinGeometry.Percentile(v, 100f), 1e-6f);
            Assert.AreEqual(0.005f, SkinGeometry.Percentile(new List<float> { 0.005f }, 95f), 1e-6f);
            Assert.IsNaN(SkinGeometry.Percentile(new List<float>(), 95f));
            Assert.AreEqual(0.6f, SkinGeometry.LineDistance(new Vector3(0.6f, 0.5f, 0f), Vector3.zero, Vector3.up), 1e-6f);
        }
    }
}
