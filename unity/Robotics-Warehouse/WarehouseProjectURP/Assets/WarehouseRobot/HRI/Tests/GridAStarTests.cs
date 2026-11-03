using System;
using System.Collections.Generic;
using NUnit.Framework;
using UnityEngine;
using WarehouseHRI.V4;

namespace WarehouseHRI.Tests
{
    public class GridAStarTests
    {
        static GroundTruthGrid Grid(params string[] rowsTopIsLastZ)
        {
            // rows given as in grid.json: index = iz (row 0 = smallest z)
            int nz = rowsTopIsLastZ.Length, nx = rowsTopIsLastZ[0].Length;
            var b = new bool[nx * nz];
            for (int iz = 0; iz < nz; iz++)
                for (int ix = 0; ix < nx; ix++) b[iz * nx + ix] = rowsTopIsLastZ[iz][ix] == '1';
            return new GroundTruthGrid(0.5, 0.0, 0.0, nx, nz, b);
        }

        static void AssertLegal(GroundTruthGrid g, List<Vector2Int> path, Vector2Int s, Vector2Int t)
        {
            Assert.AreEqual(s, path[0]);
            Assert.AreEqual(t, path[path.Count - 1]);
            foreach (var c in path) Assert.IsTrue(g.Free(c.x, c.y), $"cell {c} is blocked");
            for (int i = 1; i < path.Count; i++)
            {
                int dx = path[i].x - path[i - 1].x, dz = path[i].y - path[i - 1].y;
                Assert.AreEqual(1, Math.Max(Math.Abs(dx), Math.Abs(dz)), "steps go to a neighbour");
                if (dx != 0 && dz != 0)
                    Assert.IsTrue(g.Free(path[i - 1].x + dx, path[i - 1].y) && g.Free(path[i - 1].x, path[i - 1].y + dz), "no corner cutting");
            }
        }

        [Test]
        public void Straight_CostsOneCellPerStep()
        {
            var g = Grid("00000");
            Assert.IsTrue(GridAStar.TryFind(g, new Vector2Int(0, 0), new Vector2Int(4, 0), out var p, out double len));
            Assert.AreEqual(5, p.Count);
            Assert.AreEqual(4.0, len, 1e-12);
        }

        [Test]
        public void Diagonal_CostsSqrt2()
        {
            var g = Grid("0000", "0000", "0000", "0000");
            Assert.IsTrue(GridAStar.TryFind(g, new Vector2Int(0, 0), new Vector2Int(3, 3), out var p, out double len));
            Assert.AreEqual(3 * Math.Sqrt(2), len, 1e-12);
            Assert.AreEqual(4, p.Count);
            Assert.IsTrue(GridAStar.TryFind(g, new Vector2Int(0, 0), new Vector2Int(3, 1), out _, out len));
            Assert.AreEqual(2 + Math.Sqrt(2), len, 1e-12);   // octile
        }

        [Test]
        public void NoCornerCutting_ThroughABlockedCorner()
        {
            // (1,0) blocked: the diagonal (0,0) -> (1,1) would cut its corner and is not allowed.
            var g = Grid("010", "000");
            Assert.IsTrue(GridAStar.TryFind(g, new Vector2Int(0, 0), new Vector2Int(1, 1), out var p, out double len));
            Assert.AreEqual(2.0, len, 1e-12);
            AssertLegal(g, p, new Vector2Int(0, 0), new Vector2Int(1, 1));
        }

        [Test]
        public void DiagonalGap_IsClosed()
        {
            // Two blocked cells touching only at a corner leave no diagonal passage between them.
            var g = Grid("01", "10");
            Assert.IsFalse(GridAStar.TryFind(g, new Vector2Int(0, 0), new Vector2Int(1, 1), out _, out _));
        }

        [Test]
        public void BlockedEnd_OrNoPath_IsFalse()
        {
            var g = Grid("0100", "0100", "0100");
            Assert.IsFalse(GridAStar.TryFind(g, new Vector2Int(1, 0), new Vector2Int(3, 0), out _, out _));
            Assert.IsFalse(GridAStar.TryFind(g, new Vector2Int(0, 0), new Vector2Int(3, 2), out _, out _));
        }

        [Test]
        public void StartEqualsGoal_IsOneCell()
        {
            var g = Grid("000");
            Assert.IsTrue(GridAStar.TryFind(g, new Vector2Int(1, 0), new Vector2Int(1, 0), out var p, out double len));
            Assert.AreEqual(1, p.Count);
            Assert.AreEqual(0.0, len);
        }

        [Test]
        public void Detour_AroundAWall()
        {
            var g = Grid(
                "00000",
                "01110",
                "00010",
                "00000");
            Assert.IsTrue(GridAStar.TryFind(g, new Vector2Int(2, 2), new Vector2Int(2, 0), out var p, out double len));
            AssertLegal(g, p, new Vector2Int(2, 2), new Vector2Int(2, 0));
            Assert.AreEqual(Dijkstra(g, new Vector2Int(2, 2), new Vector2Int(2, 0)), len, 1e-9);
        }

        [Test]
        public void MatchesBruteForceDijkstra_OnRandomGrids()
        {
            var rng = new System.Random(20261029);
            int compared = 0;
            for (int trial = 0; trial < 300; trial++)
            {
                int nx = rng.Next(2, 16), nz = rng.Next(2, 16);
                var b = new bool[nx * nz];
                double density = rng.NextDouble() * 0.45;
                for (int i = 0; i < b.Length; i++) b[i] = rng.NextDouble() < density;
                var g = new GroundTruthGrid(0.5, 0, 0, nx, nz, b);
                var s = new Vector2Int(rng.Next(nx), rng.Next(nz));
                var t = new Vector2Int(rng.Next(nx), rng.Next(nz));
                double expected = Dijkstra(g, s, t);
                bool found = GridAStar.TryFind(g, s, t, out var p, out double len);
                Assert.AreEqual(!double.IsInfinity(expected), found, $"trial {trial}");
                if (!found) continue;
                compared++;
                Assert.AreEqual(expected, len, 1e-9, $"trial {trial}");
                Assert.AreEqual(len, GridAStar.PathLengthCells(p), 1e-12);
                AssertLegal(g, p, s, t);
            }
            Assert.Greater(compared, 100);
        }

        [Test]
        public void IsDeterministic()
        {
            var g = Grid("000000", "000000", "000000", "000000");
            GridAStar.TryFind(g, new Vector2Int(0, 0), new Vector2Int(5, 3), out var p1, out _);
            GridAStar.TryFind(g, new Vector2Int(0, 0), new Vector2Int(5, 3), out var p2, out _);
            CollectionAssert.AreEqual(p1, p2);
        }

        /// <summary>Plain Dijkstra over every cell with the same moves (the reference for the lengths).</summary>
        static double Dijkstra(GroundTruthGrid g, Vector2Int s, Vector2Int t)
        {
            if (!g.Free(s.x, s.y) || !g.Free(t.x, t.y)) return double.PositiveInfinity;
            int n = g.CellsX * g.CellsZ;
            var dist = new double[n];
            var done = new bool[n];
            for (int i = 0; i < n; i++) dist[i] = double.PositiveInfinity;
            dist[s.y * g.CellsX + s.x] = 0;
            for (int iter = 0; iter < n; iter++)
            {
                int u = -1;
                for (int i = 0; i < n; i++) if (!done[i] && (u < 0 || dist[i] < dist[u])) u = i;
                if (u < 0 || double.IsInfinity(dist[u])) break;
                done[u] = true;
                int ux = u % g.CellsX, uz = u / g.CellsX;
                for (int dx = -1; dx <= 1; dx++)
                    for (int dz = -1; dz <= 1; dz++)
                    {
                        if (dx == 0 && dz == 0) continue;
                        int vx = ux + dx, vz = uz + dz;
                        if (!g.Free(vx, vz)) continue;
                        if (dx != 0 && dz != 0 && !(g.Free(ux + dx, uz) && g.Free(ux, uz + dz))) continue;
                        double w = dx != 0 && dz != 0 ? Math.Sqrt(2) : 1.0;
                        int v = vz * g.CellsX + vx;
                        if (dist[u] + w < dist[v]) dist[v] = dist[u] + w;
                    }
            }
            return dist[t.y * g.CellsX + t.x];
        }
    }
}
