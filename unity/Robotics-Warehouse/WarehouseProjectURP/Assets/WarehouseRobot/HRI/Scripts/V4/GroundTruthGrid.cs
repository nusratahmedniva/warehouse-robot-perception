using System;
using System.Collections.Generic;
using System.Text;
using UnityEngine;

namespace WarehouseHRI.V4
{
    /// <summary>2D geometry on the ground plane (x, z), in double precision. Points are Vector2(x, z).</summary>
    public static class Geometry2D
    {
        /// <summary>Convex hull, counter-clockwise, without collinear points (Andrew's monotone chain).</summary>
        public static List<Vector2> ConvexHull(IEnumerable<Vector2> points)
        {
            var pts = new List<Vector2>(points);
            pts.Sort((a, b) => a.x != b.x ? a.x.CompareTo(b.x) : a.y.CompareTo(b.y));
            var unique = new List<Vector2>();
            foreach (var p in pts)
                if (unique.Count == 0 || unique[unique.Count - 1] != p) unique.Add(p);
            if (unique.Count < 3) return unique;
            var hull = new List<Vector2>();
            for (int pass = 0; pass < 2; pass++)
            {
                int start = hull.Count;
                for (int k = 0; k < unique.Count; k++)
                {
                    var p = unique[pass == 0 ? k : unique.Count - 1 - k];
                    while (hull.Count >= start + 2 && Cross(hull[hull.Count - 2], hull[hull.Count - 1], p) <= 0) hull.RemoveAt(hull.Count - 1);
                    hull.Add(p);
                }
                hull.RemoveAt(hull.Count - 1);
            }
            return hull;
        }

        static double Cross(Vector2 o, Vector2 a, Vector2 b) =>
            ((double)a.x - o.x) * ((double)b.y - o.y) - ((double)a.y - o.y) * ((double)b.x - o.x);

        /// <summary>Distance from (px, pz) to a convex polygon (counter-clockwise hull; 1 or 2 points allowed): 0 inside or on it.</summary>
        public static double DistanceToConvex(IList<Vector2> hull, double px, double pz)
        {
            int n = hull.Count;
            if (n == 0) return double.PositiveInfinity;
            if (n == 1) return Hypot(px - hull[0].x, pz - hull[0].y);
            bool inside = n >= 3;
            double best = double.PositiveInfinity;
            for (int i = 0; i < n; i++)
            {
                Vector2 a = hull[i], b = hull[(i + 1) % n];
                double ex = (double)b.x - a.x, ez = (double)b.y - a.y;
                if (ex * (pz - a.y) - ez * (px - a.x) < 0) inside = false;   // right of a CCW edge: outside
                best = Math.Min(best, SegmentDistance(px, pz, a.x, a.y, b.x, b.y));
                if (n == 2) break;
            }
            return inside ? 0.0 : best;
        }

        public static bool InsideConvex(IList<Vector2> hull, double px, double pz) => hull.Count >= 3 && DistanceToConvex(hull, px, pz) == 0.0;

        public static double SegmentDistance(double px, double pz, double ax, double az, double bx, double bz)
        {
            double dx = bx - ax, dz = bz - az, n2 = dx * dx + dz * dz;
            double t = n2 == 0.0 ? 0.0 : Math.Max(0.0, Math.Min(1.0, ((px - ax) * dx + (pz - az) * dz) / n2));
            return Hypot(px - (ax + t * dx), pz - (az + t * dz));
        }

        static double Hypot(double a, double b) => Math.Sqrt(a * a + b * b);
    }

    /// <summary>
    /// The ground-truth floor grid of docs/protocol_v3.md (run_###/grid.json). Cell (ix, iz) covers x in
    /// [origin_x + ix * cell, origin_x + (ix + 1) * cell), the same for z; its centre is half a cell further.
    /// Blocked cells are already widened: a cell is free only if its centre lies on the floor and at least the inflation
    /// distance (robot half-width + safety margin) away from every obstacle footprint, i.e. the robot centred there clears
    /// every rack, box, station and wall by the margin.
    /// </summary>
    public class GroundTruthGrid
    {
        public readonly double CellSize, OriginX, OriginZ;
        public readonly int CellsX, CellsZ;
        public readonly double InflationM;
        readonly bool[] blocked;   // [iz * CellsX + ix]

        public GroundTruthGrid(double cellSize, double originX, double originZ, int cellsX, int cellsZ, bool[] blockedCells, double inflationM = 0.0)
        {
            if (!(cellSize > 0)) throw new ArgumentException("cell size must be > 0");
            if (cellsX <= 0 || cellsZ <= 0) throw new ArgumentException("the grid needs at least one cell");
            if (blockedCells == null || blockedCells.Length != cellsX * cellsZ) throw new ArgumentException("blocked must have cellsX * cellsZ entries");
            CellSize = cellSize;
            OriginX = originX;
            OriginZ = originZ;
            CellsX = cellsX;
            CellsZ = cellsZ;
            InflationM = inflationM;
            blocked = (bool[])blockedCells.Clone();
        }

        public bool Inside(int ix, int iz) => ix >= 0 && ix < CellsX && iz >= 0 && iz < CellsZ;
        public bool Blocked(int ix, int iz) => blocked[iz * CellsX + ix];
        public bool Free(int ix, int iz) => Inside(ix, iz) && !blocked[iz * CellsX + ix];

        /// <summary>The cell of a world point: floor((x - origin_x) / cell_size_m), the same for z (as Python computes it).</summary>
        public Vector2Int CellOf(double x, double z) =>
            new Vector2Int((int)Math.Floor((x - OriginX) / CellSize), (int)Math.Floor((z - OriginZ) / CellSize));

        public void Centre(int ix, int iz, out double x, out double z)
        {
            x = OriginX + (ix + 0.5) * CellSize;
            z = OriginZ + (iz + 0.5) * CellSize;
        }

        /// <summary>blocked_rows of grid.json: CellsZ strings (row 0 = smallest z) of CellsX characters, '1' blocked, '0' free.</summary>
        public List<string> BlockedRows()
        {
            var rows = new List<string>(CellsZ);
            var sb = new StringBuilder(CellsX);
            for (int iz = 0; iz < CellsZ; iz++)
            {
                sb.Clear();
                for (int ix = 0; ix < CellsX; ix++) sb.Append(blocked[iz * CellsX + ix] ? '1' : '0');
                rows.Add(sb.ToString());
            }
            return rows;
        }

        public int BlockedCount()
        {
            int n = 0;
            foreach (bool b in blocked) if (b) n++;
            return n;
        }

        /// <summary>
        /// Build the grid from footprints (convex hulls on the ground plane). The grid spans the floor footprints, with
        /// the origin on a multiple of the cell size. A cell is free iff its centre lies inside a floor footprint and its
        /// distance to every obstacle footprint is at least inflationM; everything else is blocked.
        /// </summary>
        public static GroundTruthGrid FromFootprints(double cellSize, IList<List<Vector2>> floors, IList<List<Vector2>> obstacles, double inflationM)
        {
            if (!(cellSize > 0)) throw new ArgumentException("cell size must be > 0");
            if (inflationM < 0) throw new ArgumentException("inflation must be >= 0");
            if (floors == null || floors.Count == 0) throw new ArgumentException("no floor footprint: the grid needs the floor");
            double minX = double.PositiveInfinity, minZ = double.PositiveInfinity, maxX = double.NegativeInfinity, maxZ = double.NegativeInfinity;
            foreach (var f in floors)
                foreach (var p in f)
                {
                    minX = Math.Min(minX, p.x); maxX = Math.Max(maxX, p.x);
                    minZ = Math.Min(minZ, p.y); maxZ = Math.Max(maxZ, p.y);
                }
            double ox = Math.Floor(minX / cellSize) * cellSize, oz = Math.Floor(minZ / cellSize) * cellSize;
            int nx = Math.Max(1, (int)Math.Ceiling((maxX - ox) / cellSize));
            int nz = Math.Max(1, (int)Math.Ceiling((maxZ - oz) / cellSize));
            var cells = new bool[nx * nz];

            for (int iz = 0; iz < nz; iz++)
                for (int ix = 0; ix < nx; ix++)
                {
                    double cx = ox + (ix + 0.5) * cellSize, cz = oz + (iz + 0.5) * cellSize;
                    bool onFloor = false;
                    foreach (var f in floors)
                        if (Geometry2D.InsideConvex(f, cx, cz)) { onFloor = true; break; }
                    cells[iz * nx + ix] = !onFloor;
                }

            // Each obstacle blocks only the cells whose centres fall inside its inflated bounding box, then the exact test.
            foreach (var o in obstacles)
            {
                if (o == null || o.Count == 0) continue;
                double bx0 = double.PositiveInfinity, bz0 = double.PositiveInfinity, bx1 = double.NegativeInfinity, bz1 = double.NegativeInfinity;
                foreach (var p in o)
                {
                    bx0 = Math.Min(bx0, p.x); bx1 = Math.Max(bx1, p.x);
                    bz0 = Math.Min(bz0, p.y); bz1 = Math.Max(bz1, p.y);
                }
                int ix0 = Math.Max(0, (int)Math.Floor((bx0 - inflationM - ox) / cellSize - 0.5));
                int ix1 = Math.Min(nx - 1, (int)Math.Ceiling((bx1 + inflationM - ox) / cellSize - 0.5));
                int iz0 = Math.Max(0, (int)Math.Floor((bz0 - inflationM - oz) / cellSize - 0.5));
                int iz1 = Math.Min(nz - 1, (int)Math.Ceiling((bz1 + inflationM - oz) / cellSize - 0.5));
                for (int iz = iz0; iz <= iz1; iz++)
                    for (int ix = ix0; ix <= ix1; ix++)
                    {
                        if (cells[iz * nx + ix]) continue;
                        double cx = ox + (ix + 0.5) * cellSize, cz = oz + (iz + 0.5) * cellSize;
                        double d = Geometry2D.DistanceToConvex(o, cx, cz);
                        if (d == 0.0 || d < inflationM) cells[iz * nx + ix] = true;   // inside always blocks
                    }
            }
            return new GroundTruthGrid(cellSize, ox, oz, nx, nz, cells, inflationM);
        }
    }

    /// <summary>
    /// A* on a GroundTruthGrid exactly as docs/protocol_v3.md states: 8-connected, a straight step costs 1 cell, a
    /// diagonal step sqrt(2) cells and is allowed only when both orthogonal neighbours are free (no corner cutting).
    /// Ties are broken deterministically (lower f, then higher g, then insertion order).
    /// </summary>
    public static class GridAStar
    {
        public const double Sqrt2 = 1.4142135623730951;

        static readonly int[] Dx = { 1, -1, 0, 0, 1, 1, -1, -1 };
        static readonly int[] Dz = { 0, 0, 1, -1, 1, -1, 1, -1 };

        /// <summary>Path of cells from start to goal (both included) and its length in cells; false if either end is blocked or there is no path.</summary>
        public static bool TryFind(GroundTruthGrid grid, Vector2Int start, Vector2Int goal, out List<Vector2Int> path, out double lengthCells)
        {
            path = null;
            lengthCells = double.NaN;
            if (!grid.Free(start.x, start.y) || !grid.Free(goal.x, goal.y)) return false;
            int n = grid.CellsX * grid.CellsZ;
            var g = new double[n];
            var came = new int[n];
            var closed = new bool[n];
            for (int i = 0; i < n; i++) { g[i] = double.PositiveInfinity; came[i] = -1; }
            int Index(int x, int z) => z * grid.CellsX + x;
            double H(int x, int z)
            {
                int dx = Math.Abs(x - goal.x), dz = Math.Abs(z - goal.y);
                return (dx + dz) + (Sqrt2 - 2.0) * Math.Min(dx, dz);   // octile distance: admissible and consistent
            }

            var open = new MinHeap();
            int s = Index(start.x, start.y), target = Index(goal.x, goal.y);
            g[s] = 0.0;
            open.Push(H(start.x, start.y), 0.0, s);
            while (open.Count > 0)
            {
                open.Pop(out _, out double gc, out int cur);
                if (closed[cur]) continue;
                closed[cur] = true;
                if (cur == target) break;
                int cx = cur % grid.CellsX, cz = cur / grid.CellsX;
                for (int k = 0; k < 8; k++)
                {
                    int nx = cx + Dx[k], nz = cz + Dz[k];
                    if (!grid.Free(nx, nz)) continue;
                    bool diagonal = Dx[k] != 0 && Dz[k] != 0;
                    if (diagonal && !(grid.Free(cx + Dx[k], cz) && grid.Free(cx, cz + Dz[k]))) continue;
                    int ni = Index(nx, nz);
                    double ng = gc + (diagonal ? Sqrt2 : 1.0);
                    if (ng < g[ni] - 1e-12)
                    {
                        g[ni] = ng;
                        came[ni] = cur;
                        open.Push(ng + H(nx, nz), ng, ni);
                    }
                }
            }
            if (!closed[target]) return false;
            path = new List<Vector2Int>();
            for (int c = target; c != -1; c = came[c]) path.Add(new Vector2Int(c % grid.CellsX, c / grid.CellsX));
            path.Reverse();
            lengthCells = PathLengthCells(path);
            return true;
        }

        /// <summary>Sum of the step costs of a path of neighbouring cells (1 straight, sqrt(2) diagonal).</summary>
        public static double PathLengthCells(IList<Vector2Int> cells)
        {
            double len = 0.0;
            for (int i = 1; i < cells.Count; i++)
            {
                int dx = Math.Abs(cells[i].x - cells[i - 1].x), dz = Math.Abs(cells[i].y - cells[i - 1].y);
                len += dx != 0 && dz != 0 ? Sqrt2 : dx + dz;
            }
            return len;
        }

        /// <summary>Binary min-heap on (f, -g, insertion order).</summary>
        sealed class MinHeap
        {
            struct Item { public double F, G; public long Order; public int Cell; }
            readonly List<Item> items = new List<Item>();
            long counter;
            public int Count => items.Count;

            static bool Less(Item a, Item b) =>
                a.F != b.F ? a.F < b.F : a.G != b.G ? a.G > b.G : a.Order < b.Order;

            public void Push(double f, double g, int cell)
            {
                items.Add(new Item { F = f, G = g, Order = counter++, Cell = cell });
                int i = items.Count - 1;
                while (i > 0)
                {
                    int p = (i - 1) / 2;
                    if (!Less(items[i], items[p])) break;
                    (items[i], items[p]) = (items[p], items[i]);
                    i = p;
                }
            }

            public void Pop(out double f, out double g, out int cell)
            {
                var top = items[0];
                f = top.F; g = top.G; cell = top.Cell;
                var last = items[items.Count - 1];
                items.RemoveAt(items.Count - 1);
                if (items.Count == 0) return;
                items[0] = last;
                int i = 0;
                while (true)
                {
                    int l = 2 * i + 1, r = l + 1, m = i;
                    if (l < items.Count && Less(items[l], items[m])) m = l;
                    if (r < items.Count && Less(items[r], items[m])) m = r;
                    if (m == i) break;
                    (items[i], items[m]) = (items[m], items[i]);
                    i = m;
                }
            }
        }
    }
}
