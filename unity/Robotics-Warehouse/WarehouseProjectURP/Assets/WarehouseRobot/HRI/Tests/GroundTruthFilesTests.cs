using System;
using System.Collections.Generic;
using System.Globalization;
using System.IO;
using System.Threading;
using NUnit.Framework;
using UnityEngine;
using WarehouseHRI.V4;

namespace WarehouseHRI.Tests
{
    public class GroundTruthFilesTests
    {
        string m_Dir;

        [SetUp]
        public void SetUp()
        {
            m_Dir = Path.Combine(Path.GetTempPath(), "GroundTruthFilesTests_" + Guid.NewGuid().ToString("N"));
            Directory.CreateDirectory(m_Dir);
        }

        [TearDown]
        public void TearDown()
        {
            if (Directory.Exists(m_Dir)) Directory.Delete(m_Dir, true);
        }

        [Test]
        public void RunFolder_IsZeroPaddedToThree()
        {
            Assert.AreEqual("run_001", GroundTruthFiles.RunFolderName(1));
            Assert.AreEqual("run_020", GroundTruthFiles.RunFolderName(20));
            Assert.AreEqual("run_1000", GroundTruthFiles.RunFolderName(1000));
            Assert.Throws<ArgumentOutOfRangeException>(() => GroundTruthFiles.RunFolderName(0));
        }

        [Test]
        public void Trail_HeaderAndRow_AsSpecified_InAnyCulture()
        {
            Assert.AreEqual("time_s,x,z,yaw_deg", GroundTruthFiles.TrailHeader);
            var keep = Thread.CurrentThread.CurrentCulture;
            try
            {
                Thread.CurrentThread.CurrentCulture = new CultureInfo("de-DE");   // decimal comma must not leak in
                Assert.AreEqual("123.456,6.250,-10.000,0.000", GroundTruthFiles.TrailRow(123.456, 6.25, -10.0, 0.0));
                Assert.AreEqual("0.100,-1.235,1.000,359.500", GroundTruthFiles.TrailRow(0.1, -1.2346, 0.99951, 359.5));
            }
            finally
            {
                Thread.CurrentThread.CurrentCulture = keep;
            }
        }

        [Test]
        public void GridFile_HasTheSpecifiedKeysAndRows()
        {
            var b = new bool[4 * 3];
            b[0 * 4 + 1] = true;
            b[2 * 4 + 3] = true;
            var g = new GroundTruthGrid(0.5, -2.0, -12.0, 4, 3, b);
            string json = GroundTruthFiles.ToJson(GroundTruthFiles.Grid(g, 6.25, -10.0, 1.0, 2.0));
            StringAssert.Contains("\"cell_size_m\": 0.5", json);
            StringAssert.Contains("\"origin_x\": -2.0", json);
            StringAssert.Contains("\"cells_x\": 4", json);
            StringAssert.Contains("\"cells_z\": 3", json);
            Assert.Less(json.IndexOf("\"cell_size_m\"", StringComparison.Ordinal), json.IndexOf("\"blocked_rows\"", StringComparison.Ordinal));
            Assert.IsFalse(json.Contains("\r"));
            var back = JsonUtility.FromJson<GridFile>(json);
            CollectionAssert.AreEqual(new[] { "0100", "0000", "0001" }, back.blocked_rows);
            Assert.AreEqual(6.25, back.start.x);
            Assert.AreEqual(-10.0, back.start.z);
            Assert.AreEqual(1.0, back.goal.x);
            Assert.AreEqual(2.0, back.goal.z);
        }

        [Test]
        public void OptimalPath_LengthFromCells_PointsAreCentres()
        {
            var g = new GroundTruthGrid(0.5, -2.0, -12.0, 10, 10, new bool[100]);
            var cells = new List<Vector2Int> { new Vector2Int(1, 1), new Vector2Int(2, 2), new Vector2Int(3, 2), new Vector2Int(4, 2) };
            var f = GroundTruthFiles.OptimalPath(g, cells);
            Assert.AreEqual((Math.Sqrt(2) + 2) * 0.5, f.length_m, 1e-12);
            Assert.AreEqual(4, f.cells.Count);
            Assert.AreEqual(2, f.cells[1].ix);
            Assert.AreEqual(2, f.cells[1].iz);
            Assert.AreEqual(-1.25, f.points[0].x, 1e-12);
            Assert.AreEqual(-11.25, f.points[0].z, 1e-12);
            var back = JsonUtility.FromJson<OptimalPathFile>(GroundTruthFiles.ToJson(f));
            Assert.AreEqual(f.length_m, back.length_m, 1e-12);
            Assert.AreEqual(4, back.points.Count);
        }

        [Test]
        public void RunFile_HasRunStart()
        {
            string json = GroundTruthFiles.ToJson(new RunFile { run_start_s = 123.456 });
            StringAssert.Contains("\"run_start_s\": 123.456", json);
        }

        [Test]
        public void WriteNew_NeverOverwrites()
        {
            string p = Path.Combine(m_Dir, "grid.json");
            GroundTruthFiles.WriteNew(p, "first");
            Assert.Throws<IOException>(() => GroundTruthFiles.WriteNew(p, "second"));
            Assert.AreEqual("first", File.ReadAllText(p));
        }

        // ---------------- leak comparison ----------------

        static Color32[] Image(int n, byte v)
        {
            var a = new Color32[n];
            for (int i = 0; i < n; i++) a[i] = new Color32(v, v, v, 255);
            return a;
        }

        [Test]
        public void Leak_IdenticalImagesPass()
        {
            var r = LeakCompare.Compare(Image(12, 7), 4, 3, Image(12, 7), 4, 3);
            Assert.IsTrue(r.Passed(0));
            Assert.AreEqual(0, r.MaxDiff);
            Assert.AreEqual(0, r.DifferingPixels);
        }

        [Test]
        public void Leak_OneChannelOfOnePixelFails()
        {
            var on = Image(12, 7);
            on[5].b = 8;
            var r = LeakCompare.Compare(on, 4, 3, Image(12, 7), 4, 3);
            Assert.IsFalse(r.Passed(0));
            Assert.IsTrue(r.Passed(1));
            Assert.AreEqual(1, r.MaxDiff);
            Assert.AreEqual(1, r.DifferingPixels);
            var alpha = Image(12, 7);
            alpha[0].a = 0;
            Assert.IsFalse(LeakCompare.Compare(alpha, 4, 3, Image(12, 7), 4, 3).Passed(0));
        }

        [Test]
        public void Leak_DifferentSizesFail()
        {
            Assert.IsFalse(LeakCompare.Compare(Image(12, 7), 4, 3, Image(12, 7), 3, 4).Passed(0));
            Assert.IsFalse(LeakCompare.Compare(Image(12, 7), 4, 3, Image(9, 7), 3, 3).Passed(255));
        }
    }
}
