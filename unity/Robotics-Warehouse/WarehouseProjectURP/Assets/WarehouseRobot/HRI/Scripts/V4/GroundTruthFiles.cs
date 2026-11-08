using System;
using System.Collections.Generic;
using System.Globalization;
using System.IO;
using System.Text;
using UnityEngine;

namespace WarehouseHRI.V4
{
    [Serializable]
    public class XZ
    {
        public double x, z;
    }

    [Serializable]
    public class CellIndex
    {
        public int ix, iz;
    }

    /// <summary>run_###/grid.json (docs/protocol_v3.md). Field order is the JSON key order.</summary>
    [Serializable]
    public class GridFile
    {
        public double cell_size_m;
        public double origin_x;
        public double origin_z;
        public int cells_x;
        public int cells_z;
        public List<string> blocked_rows = new List<string>();
        public XZ start = new XZ();
        public XZ goal = new XZ();
    }

    /// <summary>run_###/optimal_path.json (docs/protocol_v3.md).</summary>
    [Serializable]
    public class OptimalPathFile
    {
        public double length_m;
        public List<CellIndex> cells = new List<CellIndex>();
        public List<XZ> points = new List<XZ>();
    }

    /// <summary>run_###/run.json (docs/protocol_v3.md).</summary>
    [Serializable]
    public class RunFile
    {
        public double run_start_s;
    }

    /// <summary>
    /// The per-run ground-truth files Unity writes into the trial session folder (docs/protocol_v3.md, "Per-run files
    /// Unity writes"). They are never sent over the bridge. Every file is created once and never overwritten.
    /// </summary>
    public static class GroundTruthFiles
    {
        public const string TrailHeader = "time_s,x,z,yaw_deg";
        public const string LeakFolder = "leak_test";
        /// <summary>run_###/truth.jsonl: one line per worker per truth frame (docs/protocol_v3.md), written by TruthLogger.</summary>
        public const string TruthFile = "truth.jsonl";
        static readonly CultureInfo Inv = CultureInfo.InvariantCulture;

        /// <summary>run_### with the trial number zero-padded to 3, as in truth_run###.json.</summary>
        public static string RunFolderName(int trial)
        {
            if (trial < 1) throw new ArgumentOutOfRangeException(nameof(trial), "trials are numbered from 1");
            return "run_" + trial.ToString("000", Inv);
        }

        public static GridFile Grid(GroundTruthGrid grid, double startX, double startZ, double goalX, double goalZ)
        {
            return new GridFile
            {
                cell_size_m = grid.CellSize,
                origin_x = grid.OriginX,
                origin_z = grid.OriginZ,
                cells_x = grid.CellsX,
                cells_z = grid.CellsZ,
                blocked_rows = grid.BlockedRows(),
                start = new XZ { x = startX, z = startZ },
                goal = new XZ { x = goalX, z = goalZ },
            };
        }

        /// <summary>optimal_path.json for a path of cells: centres as points, length_m = (sum of step costs) x cell size.</summary>
        public static OptimalPathFile OptimalPath(GroundTruthGrid grid, IList<Vector2Int> cells)
        {
            var f = new OptimalPathFile { length_m = GridAStar.PathLengthCells(cells) * grid.CellSize };
            foreach (var c in cells)
            {
                grid.Centre(c.x, c.y, out double x, out double z);
                f.cells.Add(new CellIndex { ix = c.x, iz = c.y });
                f.points.Add(new XZ { x = x, z = z });
            }
            return f;
        }

        public static string ToJson(object file) => JsonUtility.ToJson(file, true).Replace("\r\n", "\n") + "\n";

        /// <summary>One trail.csv row: time_s, x, z, yaw_deg, each with 3 decimals (invariant culture).</summary>
        public static string TrailRow(double timeS, double x, double z, double yawDeg) =>
            string.Join(",", timeS.ToString("0.000", Inv), x.ToString("0.000", Inv), z.ToString("0.000", Inv), yawDeg.ToString("0.000", Inv));

        /// <summary>Write a new UTF-8 (no BOM) text file; throws IOException if it already exists (never overwrites).</summary>
        public static void WriteNew(string path, string text)
        {
            using (var fs = new FileStream(path, FileMode.CreateNew, FileAccess.Write))
            using (var w = new StreamWriter(fs, new UTF8Encoding(false))) w.Write(text);
        }

        public static void WriteNew(string path, byte[] bytes)
        {
            using (var fs = new FileStream(path, FileMode.CreateNew, FileAccess.Write)) fs.Write(bytes, 0, bytes.Length);
        }
    }

    /// <summary>Pixel comparison of one leak-test pair (layer on vs off), as Python's gt_path.leak_test does it.</summary>
    public static class LeakCompare
    {
        public struct Result
        {
            public bool SameSize;
            public int MaxDiff;            // largest absolute per-channel difference (r, g, b, a)
            public int DifferingPixels;
            public bool Passed(int maxPixelDiff) => SameSize && MaxDiff <= maxPixelDiff;
        }

        public static Result Compare(Color32[] on, int onWidth, int onHeight, Color32[] off, int offWidth, int offHeight)
        {
            var r = new Result { SameSize = onWidth == offWidth && onHeight == offHeight && on != null && off != null && on.Length == off.Length };
            if (!r.SameSize) { r.MaxDiff = int.MaxValue; return r; }
            for (int i = 0; i < on.Length; i++)
            {
                Color32 a = on[i], b = off[i];
                int d = Math.Max(Math.Max(Math.Abs(a.r - b.r), Math.Abs(a.g - b.g)), Math.Max(Math.Abs(a.b - b.b), Math.Abs(a.a - b.a)));
                if (d > 0) r.DifferingPixels++;
                if (d > r.MaxDiff) r.MaxDiff = d;
            }
            return r;
        }
    }
}
