using System;
using System.Collections.Generic;
using UnityEngine;

namespace WarehouseAvatar
{
    /// <summary>experiments_ab.md section 12 addendum 7 decision 3: looks_ab.json palm_plates, a box-shaped palm plate measured as a plate.</summary>
    [Serializable]
    public class PalmPlateSpec
    {
        public string look, material;
        public float max_dimension_change, weld_m;
    }

    /// <summary>The plate's principal axes (PCA): unit axes sorted by extent, thinnest first; the extents along them; the centre.</summary>
    public struct PlateShape
    {
        public Vector3 Centre, Thin, Mid, Long;
        public float ThinExtent, MidExtent, LongExtent;
        public bool Valid;
        public float[] Extents => new[] { ThinExtent, MidExtent, LongExtent };
    }

    /// <summary>
    /// Mesh islands and box-plate geometry (addendum 7 decisions 3 and 4, declared before they were built): islands from the triangles with
    /// the vertices welded by position; the plate is the island with the largest box volume; its thinnest principal axis is the palm normal,
    /// and its sorted extents must stay within max_dimension_change of the rest plate's.
    /// </summary>
    public static class PalmPlate
    {
        /// <summary>The island of every vertex (vertices sharing a triangle, or lying within weld of each other, are one island); -1 for a
        /// vertex no triangle uses.</summary>
        public static int[] Islands(IList<Vector3> verts, IList<int> triangles, float weld)
        {
            int n = verts.Count;
            var parent = new int[n];
            for (int i = 0; i < n; i++) parent[i] = i;
            int Find(int x) { while (parent[x] != x) { parent[x] = parent[parent[x]]; x = parent[x]; } return x; }
            void Union(int a, int b) { a = Find(a); b = Find(b); if (a != b) parent[a] = b; }
            var used = new bool[n];
            for (int t = 0; t + 2 < triangles.Count; t += 3)
            {
                int a = triangles[t], b = triangles[t + 1], c = triangles[t + 2];
                if (a >= n || b >= n || c >= n) continue;
                used[a] = used[b] = used[c] = true;
                Union(a, b);
                Union(b, c);
            }
            float w = Mathf.Max(weld, 1e-7f);
            var cell = new Dictionary<(long, long, long), int>();
            for (int i = 0; i < n; i++)
            {
                if (!used[i]) continue;
                var key = ((long)Math.Round(verts[i].x / w), (long)Math.Round(verts[i].y / w), (long)Math.Round(verts[i].z / w));
                if (cell.TryGetValue(key, out int j)) Union(i, j); else cell[key] = i;
            }
            var id = new int[n];
            var map = new Dictionary<int, int>();
            for (int i = 0; i < n; i++)
            {
                if (!used[i]) { id[i] = -1; continue; }
                int r = Find(i);
                if (!map.TryGetValue(r, out int k)) map[r] = k = map.Count;
                id[i] = k;
            }
            return id;
        }

        /// <summary>The principal axes and extents of the points (PCA of their covariance), thinnest first.</summary>
        public static PlateShape Shape(IList<Vector3> pts)
        {
            var s = new PlateShape();
            if (pts == null || pts.Count < 4) return s;
            Vector3 c = Vector3.zero;
            foreach (var p in pts) c += p;
            c /= pts.Count;
            var m = new double[3, 3];
            foreach (var p in pts)
            {
                double x = p.x - c.x, y = p.y - c.y, z = p.z - c.z;
                m[0, 0] += x * x; m[0, 1] += x * y; m[0, 2] += x * z; m[1, 1] += y * y; m[1, 2] += y * z; m[2, 2] += z * z;
            }
            m[1, 0] = m[0, 1]; m[2, 0] = m[0, 2]; m[2, 1] = m[1, 2];
            HandGeometry.Eigen3(m, out _, out var vec);
            var axes = new List<(Vector3 axis, float extent)>();
            for (int k = 0; k < 3; k++)
            {
                var a = new Vector3((float)vec[0, k], (float)vec[1, k], (float)vec[2, k]).normalized;
                float lo = float.MaxValue, hi = float.MinValue;
                foreach (var p in pts) { float d = Vector3.Dot(p - c, a); lo = Mathf.Min(lo, d); hi = Mathf.Max(hi, d); }
                axes.Add((a, hi - lo));
            }
            axes.Sort((u, v) => u.extent.CompareTo(v.extent));
            s.Centre = c;
            s.Thin = axes[0].axis; s.ThinExtent = axes[0].extent;
            s.Mid = axes[1].axis; s.MidExtent = axes[1].extent;
            s.Long = axes[2].axis; s.LongExtent = axes[2].extent;
            s.Valid = s.ThinExtent > 0f;
            return s;
        }

        /// <summary>The largest relative change of the sorted extents against the rest plate's (0.05 = 5 %).</summary>
        public static float MaxDimensionChange(PlateShape now, PlateShape rest)
        {
            float m = 0f;
            var a = now.Extents;
            var b = rest.Extents;
            for (int i = 0; i < 3; i++) m = Mathf.Max(m, b[i] > 1e-9f ? Mathf.Abs(a[i] / b[i] - 1f) : float.PositiveInfinity);
            return m;
        }

        /// <summary>The island (among the given vertex indices) with the largest box volume (product of its PCA extents); -1 if none.</summary>
        public static int LargestIsland(IList<Vector3> verts, int[] island, IEnumerable<int> candidates)
        {
            var groups = new Dictionary<int, List<Vector3>>();
            foreach (int i in candidates)
            {
                if (i < 0 || i >= island.Length || island[i] < 0) continue;
                if (!groups.TryGetValue(island[i], out var g)) groups[island[i]] = g = new List<Vector3>();
                g.Add(verts[i]);
            }
            int best = -1;
            float bestVol = -1f;
            foreach (var kv in groups)
            {
                var sh = Shape(kv.Value);
                if (!sh.Valid) continue;
                float vol = sh.ThinExtent * sh.MidExtent * sh.LongExtent;
                if (vol > bestVol) { bestVol = vol; best = kv.Key; }
            }
            return best;
        }
    }
}
