using System;
using System.Collections.Generic;
using NUnit.Framework;
using UnityEngine;
using WarehouseHRI.V4;

namespace WarehouseHRI.Tests
{
    public class GroundTruthGridTests
    {
        static List<Vector2> Rect(float x0, float z0, float x1, float z1) =>
            Geometry2D.ConvexHull(new[] { new Vector2(x0, z0), new Vector2(x1, z0), new Vector2(x1, z1), new Vector2(x0, z1) });

        static GroundTruthGrid Open(int nx, int nz, params (int ix, int iz)[] blockedCells)
        {
            var b = new bool[nx * nz];
            foreach (var (ix, iz) in blockedCells) b[iz * nx + ix] = true;
            return new GroundTruthGrid(1.0, 0.0, 0.0, nx, nz, b);
        }

        // ---------------- geometry ----------------

        [Test]
        public void Hull_DropsInteriorAndCollinearPoints_CounterClockwise()
        {
            var hull = Geometry2D.ConvexHull(new[]
            {
                new Vector2(0, 0), new Vector2(2, 0), new Vector2(1, 0), new Vector2(2, 2), new Vector2(0, 2), new Vector2(1, 1),
            });
            Assert.AreEqual(4, hull.Count);
            double area = 0;
            for (int i = 0; i < hull.Count; i++)
            {
                var a = hull[i];
                var b = hull[(i + 1) % hull.Count];
                area += a.x * b.y - b.x * a.y;
            }
            Assert.Greater(area, 0.0);   // counter-clockwise
        }

        [Test]
        public void Distance_InsideIsZero_OutsideToEdgeAndCorner()
        {
            var sq = Rect(0, 0, 2, 2);
            Assert.AreEqual(0.0, Geometry2D.DistanceToConvex(sq, 1, 1));
            Assert.AreEqual(0.0, Geometry2D.DistanceToConvex(sq, 2, 1));            // on the edge
            Assert.AreEqual(0.5, Geometry2D.DistanceToConvex(sq, 2.5, 1), 1e-9);    // edge
            Assert.AreEqual(Math.Sqrt(2), Geometry2D.DistanceToConvex(sq, 3, 3), 1e-9);   // corner
        }

        [Test]
        public void Distance_RotatedBox()
        {
            var diamond = Geometry2D.ConvexHull(new[] { new Vector2(0, -1), new Vector2(1, 0), new Vector2(0, 1), new Vector2(-1, 0) });
            Assert.AreEqual(0.0, Geometry2D.DistanceToConvex(diamond, 0.4f, 0.4f));
            Assert.AreEqual(Math.Sqrt(0.5), Geometry2D.DistanceToConvex(diamond, 1, 1), 1e-6);
        }

        // ---------------- grid ----------------

        [Test]
        public void CellOf_IsFloorLikePython_IncludingNegativeCoordinates()
        {
            var g = new GroundTruthGrid(0.5, -2.0, -12.0, 40, 60, new bool[40 * 60]);
            Assert.AreEqual(new Vector2Int(16, 4), g.CellOf(6.25, -10.0));
            Assert.AreEqual(new Vector2Int(0, 0), g.CellOf(-2.0, -12.0));      // the lower edge belongs to the cell
            Assert.AreEqual(new Vector2Int(-1, -1), g.CellOf(-2.01, -12.01));
            g.Centre(16, 4, out double x, out double z);
            Assert.AreEqual(6.25, x, 1e-12);
            Assert.AreEqual(-9.75, z, 1e-12);
        }

        [Test]
        public void BlockedRows_Row0IsSmallestZ_Index0IsSmallestX()
        {
            var g = Open(3, 2, (2, 0), (0, 1));
            CollectionAssert.AreEqual(new[] { "001", "100" }, g.BlockedRows());
        }

        [Test]
        public void FromFootprints_OriginOnCellMultiple_AndOffFloorBlocked()
        {
            var floor = Rect(-1.2f, -0.7f, 2.9f, 1.4f);
            var g = GroundTruthGrid.FromFootprints(0.5, new List<List<Vector2>> { floor }, new List<List<Vector2>>(), 0.4);
            Assert.AreEqual(-1.5, g.OriginX, 1e-12);
            Assert.AreEqual(-1.0, g.OriginZ, 1e-12);
            Assert.AreEqual(9, g.CellsX);     // -1.5 .. 3.0
            Assert.AreEqual(5, g.CellsZ);     // -1.0 .. 1.5
            Assert.IsTrue(g.Blocked(0, 0));   // centre (-1.25, -0.75): off the floor
            Assert.IsFalse(g.Blocked(4, 2));  // centre (0.75, 0.25): on the floor, no obstacle
        }

        [Test]
        public void FromFootprints_WidensObstacleByInflation()
        {
            // 6 x 6 m floor, 1 x 1 m box at (2..3, 2..3), widening 0.4 m, 0.5 m cells.
            var floor = Rect(0, 0, 6, 6);
            var box = Rect(2, 2, 3, 3);
            var g = GroundTruthGrid.FromFootprints(0.5, new List<List<Vector2>> { floor }, new List<List<Vector2>> { box }, 0.4);
            for (int iz = 0; iz < g.CellsZ; iz++)
                for (int ix = 0; ix < g.CellsX; ix++)
                {
                    g.Centre(ix, iz, out double cx, out double cz);
                    bool expected = Geometry2D.DistanceToConvex(box, cx, cz) < 0.4;
                    Assert.AreEqual(expected, g.Blocked(ix, iz), $"cell ({ix}, {iz}) centre ({cx}, {cz})");
                }
            Assert.IsTrue(g.Blocked(3, 4));    // centre (1.75, 2.25): 0.25 m from the box
            Assert.IsFalse(g.Blocked(2, 4));   // centre (1.25, 2.25): 0.75 m from the box
        }

        [Test]
        public void FromFootprints_CornerDistanceIsEuclidean()
        {
            var floor = Rect(0, 0, 6, 6);
            var box = Rect(2, 2, 3, 3);
            var g = GroundTruthGrid.FromFootprints(0.5, new List<List<Vector2>> { floor }, new List<List<Vector2>> { box }, 0.4);
            // centre (1.75, 1.75) is sqrt(0.25^2 + 0.25^2) = 0.354 m from the corner (2, 2): blocked at 0.4 m
            Assert.IsTrue(g.Blocked(3, 3));
            var g30 = GroundTruthGrid.FromFootprints(0.5, new List<List<Vector2>> { floor }, new List<List<Vector2>> { box }, 0.3);
            Assert.IsFalse(g30.Blocked(3, 3));
            Assert.IsTrue(g30.Blocked(3, 4));   // 0.25 m from the edge
        }

        [Test]
        public void FromFootprints_ZeroWidening_StillBlocksCellsInsideObstacles()
        {
            var floor = Rect(0, 0, 4, 4);
            var box = Rect(1, 1, 2, 2);
            var g = GroundTruthGrid.FromFootprints(0.5, new List<List<Vector2>> { floor }, new List<List<Vector2>> { box }, 0.0);
            Assert.IsTrue(g.Blocked(2, 2));    // centre (1.25, 1.25) inside the box
            Assert.IsFalse(g.Blocked(1, 1));   // centre (0.75, 0.75) outside
        }

        [Test]
        public void FromFootprints_LargerWideningBlocksASuperset()
        {
            var floor = Rect(0, 0, 10, 10);
            var obstacles = new List<List<Vector2>> { Rect(2, 2, 3, 7), Rect(5.2f, 1, 6.1f, 4.4f), Rect(7, 6, 7.5f, 9) };
            var a = GroundTruthGrid.FromFootprints(0.5, new List<List<Vector2>> { floor }, obstacles, 0.4);
            var b = GroundTruthGrid.FromFootprints(0.5, new List<List<Vector2>> { floor }, obstacles, 0.5);
            for (int iz = 0; iz < a.CellsZ; iz++)
                for (int ix = 0; ix < a.CellsX; ix++)
                    if (a.Blocked(ix, iz)) Assert.IsTrue(b.Blocked(ix, iz));
            Assert.GreaterOrEqual(b.BlockedCount(), a.BlockedCount());
        }

        [Test]
        public void FromFootprints_NeedsAFloor()
        {
            Assert.Throws<ArgumentException>(() => GroundTruthGrid.FromFootprints(0.5, new List<List<Vector2>>(), new List<List<Vector2>>(), 0.4));
        }
    }
}
