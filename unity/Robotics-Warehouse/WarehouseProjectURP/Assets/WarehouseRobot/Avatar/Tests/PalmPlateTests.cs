using System.Collections.Generic;
using System.IO;
using System.Linq;
using NUnit.Framework;
using UnityEngine;

namespace WarehouseAvatar.Tests
{
    /// <summary>Box palm plates and mesh islands (Avatar/Config/experiments_ab.md section 12 addendum 7 decisions 3 and 4).</summary>
    public class PalmPlateTests
    {
        /// <summary>A box of size sx x sy x sz at c as a welded-by-position grid: each face its own vertices (hard edges, as an FBX splits them).</summary>
        static void Box(List<Vector3> v, List<int> t, Vector3 c, Vector3 size, int n)
        {
            for (int axis = 0; axis < 3; axis++)
                foreach (float side in new[] { -0.5f, 0.5f })
                {
                    int a1 = (axis + 1) % 3, a2 = (axis + 2) % 3;
                    int start = v.Count;
                    for (int i = 0; i <= n; i++)
                        for (int j = 0; j <= n; j++)
                        {
                            var p = Vector3.zero;
                            p[axis] = side * size[axis];
                            p[a1] = (i / (float)n - 0.5f) * size[a1];
                            p[a2] = (j / (float)n - 0.5f) * size[a2];
                            v.Add(c + p);
                        }
                    for (int i = 0; i < n; i++)
                        for (int j = 0; j < n; j++)
                        {
                            int q = start + i * (n + 1) + j;
                            t.AddRange(new[] { q, q + 1, q + n + 1, q + 1, q + n + 2, q + n + 1 });
                        }
                }
        }

        [Test]
        public void Islands_WeldHardEdgedFaces_AndKeepSeparatePartsApart_LargestIsThePlate()
        {
            var v = new List<Vector3>();
            var t = new List<int>();
            Box(v, t, Vector3.zero, new Vector3(0.12f, 0.045f, 0.21f), 4);                     // the plate
            int plateEnd = v.Count;
            Box(v, t, new Vector3(0.13f, 0f, 0.075f), new Vector3(0.15f, 0.04f, 0.04f), 3);    // a finger, apart from the plate
            var island = PalmPlate.Islands(v, t, 0.0001f);
            Assert.AreEqual(1, island.Take(plateEnd).Distinct().Count(), "the six hard-edged faces weld into one island");
            Assert.AreNotEqual(island[0], island[plateEnd], "the finger is its own island");
            Assert.AreEqual(island[0], PalmPlate.LargestIsland(v, island, Enumerable.Range(0, v.Count)), "the plate has the largest box volume");
        }

        [Test]
        public void Shape_ThinnestAxisIsThePlateNormal_AndTheShapeRuleCatchesASquash()
        {
            var v = new List<Vector3>();
            Box(v, new List<int>(), Vector3.zero, new Vector3(0.12f, 0.045f, 0.21f), 4);
            var rest = PalmPlate.Shape(v);
            Assert.Greater(Mathf.Abs(Vector3.Dot(rest.Thin, Vector3.up)), 0.999f, "thinnest axis = the plate's normal");
            Assert.AreEqual(0.045f, rest.ThinExtent, 1e-4f);
            Assert.AreEqual(0.21f, rest.LongExtent, 1e-4f);
            // turned and moved rigidly: the same shape, the normal turns with it
            var q = Quaternion.Euler(80f, 20f, -35f);
            var turned = v.Select(p => q * p + new Vector3(1f, 1.5f, 0.3f)).ToList();
            var now = PalmPlate.Shape(turned);
            Assert.Less(PalmPlate.MaxDimensionChange(now, rest), 1e-3f);
            Assert.Greater(Mathf.Abs(Vector3.Dot(now.Thin, q * Vector3.up)), 0.999f);
            // squashed by 10 % along its long side: fails a 5 % rule
            var squashed = v.Select(p => new Vector3(p.x, p.y, p.z * 0.9f)).ToList();
            Assert.Greater(PalmPlate.MaxDimensionChange(PalmPlate.Shape(squashed), rest), 0.05f);
        }

        [Test]
        public void PalmPlatesRule_IsBoxosOnly()
        {
            var f = ExperimentLooks.Parse(File.ReadAllText(Path.Combine(Application.dataPath, "..", ExperimentLooks.AssetPath)));
            Assert.AreEqual(1, f.palm_plates.Length, "only Boxo: five-finger looks keep the hand-bound mesh normal");
            Assert.AreEqual("cartoon_boxo_01", f.palm_plates[0].look);
            Assert.AreEqual("glovemat", f.palm_plates[0].material);
            Assert.AreEqual(0.05f, f.palm_plates[0].max_dimension_change, 1e-6f);
        }
    }
}
