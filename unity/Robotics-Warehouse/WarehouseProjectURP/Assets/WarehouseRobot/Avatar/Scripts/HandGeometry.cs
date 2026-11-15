using System;
using System.Collections.Generic;
using UnityEngine;

namespace WarehouseAvatar
{
    /// <summary>The rendered hand's frame from its bones (experiments_ab.md section 12).</summary>
    public struct PalmFrame
    {
        /// <summary>Palm centre: mean of the hand bone and the index, middle and outermost proximal bones.</summary>
        public Vector3 P;
        /// <summary>Hand bone to middle proximal, unit.</summary>
        public Vector3 FingerDir;
        /// <summary>LookPoser.PalmNormal: the convention the hand shaper aligns.</summary>
        public Vector3 Normal;
        public Vector3 Hand, IndexBase, OuterBase;
        /// <summary>Palm length: hand bone to middle proximal.</summary>
        public float Lp;
        public bool Valid;
    }

    /// <summary>One frame's hand check (section 12). Angles in degrees; -1 = not measured.</summary>
    public struct PalmResult
    {
        public float BoneAngleDeg, MeshAngleDeg, MeshFlatness, ThumbPalmLengths, ThumbSide, ThumbAcross;
        public int MeshVertices;
        public bool MeshDetermined, ThumbMeasured, Pass;
        public string Why;
    }

    /// <summary>
    /// Palm orientation and the WAIT thumb (Avatar/Config/experiments_ab.md section 12, declared before it was built): the palm normal from
    /// the bones and from the skinned mesh against the direction to the robot camera, and whether the WAIT thumb is tucked over the palm.
    /// </summary>
    public static class HandGeometry
    {
        public static PalmFrame Frame(LookPoser.Arm a)
        {
            var f = new PalmFrame();
            if (a.Hand == null || a.Fingers == null) return f;
            var index = a.Fingers[LookPoser.Index][0];
            var middle = a.Fingers[LookPoser.Middle][0];
            var outer = LookPoser.OuterFinger(a);
            if (index == null || middle == null || outer == null) return f;
            f.Hand = a.Hand.position;
            f.IndexBase = index.position;
            f.OuterBase = outer.position;
            Vector3 d = middle.position - f.Hand;
            f.Lp = d.magnitude;
            if (f.Lp < 1e-5f) return f;
            f.FingerDir = d / f.Lp;
            f.P = (f.Hand + index.position + middle.position + outer.position) * 0.25f;
            f.Valid = LookPoser.PalmNormal(a, f.FingerDir, out f.Normal);
            return f;
        }

        /// <summary>The palm region of the skinned mesh: points between the wrist and the finger bases along the finger direction.</summary>
        public static List<Vector3> PalmRegion(IEnumerable<Vector3> handVertices, PalmFrame f)
        {
            var r = new List<Vector3>();
            foreach (var v in handVertices)
            {
                float along = Vector3.Dot(v - f.Hand, f.FingerDir);
                if (along >= 0f && along <= f.Lp) r.Add(v);
            }
            return r;
        }

        /// <summary>The plane fit of the points: the least-variance axis of their covariance, signed to agree with signRef. flatness =
        /// smallest / middle variance. False with fewer than minCount points or flatness above flatnessMax (undetermined).</summary>
        public static bool MeshNormal(IList<Vector3> pts, Vector3 signRef, int minCount, float flatnessMax, out Vector3 normal, out float flatness)
        {
            normal = Vector3.zero;
            flatness = -1f;
            if (pts == null || pts.Count < Math.Max(3, minCount)) return false;
            double mx = 0, my = 0, mz = 0;
            foreach (var p in pts) { mx += p.x; my += p.y; mz += p.z; }
            mx /= pts.Count; my /= pts.Count; mz /= pts.Count;
            var c = new double[3, 3];
            foreach (var p in pts)
            {
                double x = p.x - mx, y = p.y - my, z = p.z - mz;
                c[0, 0] += x * x; c[0, 1] += x * y; c[0, 2] += x * z;
                c[1, 1] += y * y; c[1, 2] += y * z; c[2, 2] += z * z;
            }
            c[1, 0] = c[0, 1]; c[2, 0] = c[0, 2]; c[2, 1] = c[1, 2];
            Eigen3(c, out var values, out var vectors);
            int lo = 0, mid = 0;
            for (int i = 1; i < 3; i++) if (values[i] < values[lo]) lo = i;
            var others = new List<int> { 0, 1, 2 };
            others.Remove(lo);
            mid = values[others[0]] <= values[others[1]] ? others[0] : others[1];
            flatness = values[mid] > 1e-18 ? (float)(values[lo] / values[mid]) : 1f;
            normal = new Vector3((float)vectors[0, lo], (float)vectors[1, lo], (float)vectors[2, lo]).normalized;
            if (Vector3.Dot(normal, signRef) < 0f) normal = -normal;
            return flatness <= flatnessMax;
        }

        /// <summary>Eigen-decomposition of a symmetric 3x3 matrix (cyclic Jacobi); vectors in columns.</summary>
        public static void Eigen3(double[,] m, out double[] values, out double[,] vectors)
        {
            var a = (double[,])m.Clone();
            var v = new double[3, 3] { { 1, 0, 0 }, { 0, 1, 0 }, { 0, 0, 1 } };
            for (int sweep = 0; sweep < 50; sweep++)
            {
                double off = Math.Abs(a[0, 1]) + Math.Abs(a[0, 2]) + Math.Abs(a[1, 2]);
                if (off < 1e-30) break;
                for (int p = 0; p < 2; p++)
                    for (int q = p + 1; q < 3; q++)
                    {
                        if (Math.Abs(a[p, q]) < 1e-300) continue;
                        double theta = (a[q, q] - a[p, p]) / (2.0 * a[p, q]);
                        double t = Math.Sign(theta) / (Math.Abs(theta) + Math.Sqrt(theta * theta + 1.0));
                        if (theta == 0.0) t = 1.0;
                        double cs = 1.0 / Math.Sqrt(t * t + 1.0), sn = t * cs;
                        for (int k = 0; k < 3; k++)
                        {
                            double akp = a[k, p], akq = a[k, q];
                            a[k, p] = cs * akp - sn * akq;
                            a[k, q] = sn * akp + cs * akq;
                        }
                        for (int k = 0; k < 3; k++)
                        {
                            double apk = a[p, k], aqk = a[q, k];
                            a[p, k] = cs * apk - sn * aqk;
                            a[q, k] = sn * apk + cs * aqk;
                        }
                        for (int k = 0; k < 3; k++)
                        {
                            double vkp = v[k, p], vkq = v[k, q];
                            v[k, p] = cs * vkp - sn * vkq;
                            v[k, q] = sn * vkp + cs * vkq;
                        }
                    }
            }
            values = new[] { a[0, 0], a[1, 1], a[2, 2] };
            vectors = v;
        }

        /// <summary>
        /// The hand check of one frame: palm normals (bones; mesh when determined) against camera - P within tol.palm_facing_deg; for WAIT
        /// the thumb tip tucked (|tip - P| &lt;= thumb_tip_max_palm_lengths Lp and (tip - P) . n / Lp &gt;= thumb_palm_side_min).
        /// </summary>
        public static PalmResult Evaluate(string command, PalmFrame f, IList<Vector3> palmVertices, Vector3 camera, bool hasThumbTip, Vector3 thumbTip, GeometryTolerance tol)
        {
            var r = new PalmResult { BoneAngleDeg = -1f, MeshAngleDeg = -1f, MeshFlatness = -1f, ThumbPalmLengths = -1f, ThumbSide = float.NaN, ThumbAcross = float.NaN };
            var why = new List<string>();
            if (!f.Valid)
            {
                r.Why = "hand frame not measurable";
                return r;
            }
            Vector3 toCam = camera - f.P;
            r.BoneAngleDeg = Vector3.Angle(f.Normal, toCam);
            if (!(r.BoneAngleDeg <= tol.palm_facing_deg)) why.Add("palm (bones)");
            r.MeshVertices = palmVertices != null ? palmVertices.Count : 0;
            r.MeshDetermined = MeshNormal(palmVertices, f.Normal, tol.palm_mesh_min_vertices, tol.palm_mesh_flatness_max, out var n, out r.MeshFlatness);
            if (r.MeshDetermined)
            {
                r.MeshAngleDeg = Vector3.Angle(n, toCam);
                if (!(r.MeshAngleDeg <= tol.palm_facing_deg)) why.Add("palm (mesh)");
            }
            if (command == WorkerV4Config.Wait)
            {
                if (!hasThumbTip) why.Add("thumb not measurable");
                else
                {
                    r.ThumbMeasured = true;
                    r.ThumbPalmLengths = Vector3.Distance(thumbTip, f.P) / f.Lp;
                    r.ThumbSide = Vector3.Dot(thumbTip - f.P, f.Normal) / f.Lp;
                    Vector3 across = f.OuterBase - f.IndexBase;
                    r.ThumbAcross = across.sqrMagnitude > 1e-10f ? Vector3.Dot(thumbTip - f.IndexBase, across) / across.sqrMagnitude : float.NaN;
                    if (!(r.ThumbPalmLengths <= tol.thumb_tip_max_palm_lengths)) why.Add("thumb sticks out");
                    if (!(r.ThumbSide >= tol.thumb_palm_side_min)) why.Add("thumb behind the palm");
                }
            }
            r.Pass = why.Count == 0;
            r.Why = string.Join(", ", why);
            return r;
        }
    }
}
