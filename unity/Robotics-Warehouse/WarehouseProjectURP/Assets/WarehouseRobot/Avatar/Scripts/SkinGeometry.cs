using System;
using System.Collections.Generic;
using UnityEngine;

namespace WarehouseAvatar
{
    /// <summary>gesture_geometry.json skinning: the declared limits of the skinning checks (experiments_ab.md section 12 addendum 5).</summary>
    [Serializable]
    public class GeometrySkinning
    {
        public int forearm_bands, forearm_min_band_vertices, torso_percentile, proceed_frames;
        public float forearm_min_ratio, forearm_weight_min, torso_weight_min, torso_max_displacement_m;
        /// <summary>Addendum 7: the shoulder zone left out of the torso core, as a fraction of the rig's own upper-arm length.</summary>
        public float torso_core_shoulder_zone_lu;
        public string[] torso_bones;

        public List<string> Validate()
        {
            var e = new List<string>();
            if (forearm_bands < 1) e.Add("skinning.forearm_bands must be >= 1");
            if (forearm_min_band_vertices < 3) e.Add("skinning.forearm_min_band_vertices must be >= 3");
            if (!(forearm_min_ratio > 0f && forearm_min_ratio <= 1f)) e.Add("skinning.forearm_min_ratio must be in (0, 1]");
            if (!(forearm_weight_min > 0f && forearm_weight_min <= 1f) || !(torso_weight_min > 0f && torso_weight_min <= 1f)) e.Add("skinning weights must be in (0, 1]");
            if (torso_bones == null || torso_bones.Length == 0) e.Add("skinning.torso_bones missing");
            else foreach (var b in torso_bones) if (!Enum.TryParse(b, out HumanBodyBones _)) e.Add($"skinning.torso_bones: '{b}' is not a HumanBodyBones name");
            if (torso_percentile < 50 || torso_percentile > 100) e.Add("skinning.torso_percentile must be in [50, 100]");
            if (!(torso_max_displacement_m > 0f)) e.Add("skinning.torso_max_displacement_m must be > 0");
            if (proceed_frames < 2) e.Add("skinning.proceed_frames must be >= 2");
            if (!(torso_core_shoulder_zone_lu > 0f && torso_core_shoulder_zone_lu < 2f)) e.Add("skinning.torso_core_shoulder_zone_lu must be in (0, 2)");
            return e;
        }
    }

    /// <summary>
    /// The skinning checks (experiments_ab.md section 12 addendum 5, declared before they were built): the forearm keeps its volume (each band
    /// of forearm vertices keeps its mean distance from the elbow-to-wrist line) and the torso does not deform (its vertices, each in its own
    /// dominant bone's frame, stay where they were before the take).
    /// </summary>
    public static class SkinGeometry
    {
        /// <summary>Distance of p from the line through a and b (a == b: distance from a).</summary>
        public static float LineDistance(Vector3 p, Vector3 a, Vector3 b)
        {
            Vector3 d = b - a;
            if (d.sqrMagnitude < 1e-12f) return Vector3.Distance(p, a);
            return Vector3.Cross(p - a, d.normalized).magnitude;
        }

        /// <summary>Each point's band (0..bands-1) by its position along elbow e to wrist w (0 to 1); -1 outside. Bands with fewer than
        /// minCount points are dropped (every point of them gets -1).</summary>
        public static int[] Bands(IList<Vector3> pts, Vector3 e, Vector3 w, int bands, int minCount)
        {
            var band = new int[pts.Count];
            var count = new int[bands];
            Vector3 d = w - e;
            float len2 = d.sqrMagnitude;
            for (int i = 0; i < pts.Count; i++)
            {
                float t = len2 > 1e-12f ? Vector3.Dot(pts[i] - e, d) / len2 : -1f;
                int k = t >= 0f && t <= 1f ? Mathf.Min(bands - 1, (int)(t * bands)) : -1;
                band[i] = k;
                if (k >= 0) count[k]++;
            }
            for (int i = 0; i < band.Length; i++) if (band[i] >= 0 && count[band[i]] < minCount) band[i] = -1;
            return band;
        }

        /// <summary>Mean distance of each band's points from the line e-w; NaN for an empty band.</summary>
        public static float[] BandRadii(IList<Vector3> pts, int[] band, int bands, Vector3 e, Vector3 w)
        {
            var sum = new double[bands];
            var n = new int[bands];
            for (int i = 0; i < pts.Count; i++)
            {
                if (band[i] < 0) continue;
                sum[band[i]] += LineDistance(pts[i], e, w);
                n[band[i]]++;
            }
            var r = new float[bands];
            for (int k = 0; k < bands; k++) r[k] = n[k] > 0 ? (float)(sum[k] / n[k]) : float.NaN;
            return r;
        }

        /// <summary>The smallest now / reference ratio over the bands present in both (NaN if none).</summary>
        public static float MinRatio(float[] reference, float[] now)
        {
            float m = float.NaN;
            for (int k = 0; k < reference.Length && k < now.Length; k++)
            {
                if (float.IsNaN(reference[k]) || float.IsNaN(now[k]) || reference[k] <= 1e-9f) continue;
                float q = now[k] / reference[k];
                if (float.IsNaN(m) || q < m) m = q;
            }
            return m;
        }

        /// <summary>A point in a bone's frame without the bone's scale (metres preserved).</summary>
        public static Vector3 InBone(Vector3 p, Vector3 bonePosition, Quaternion boneRotation) => Quaternion.Inverse(boneRotation) * (p - bonePosition);

        /// <summary>Addendum 7: true for a point of the torso core, i.e. farther than radius from every shoulder (UpperArm bone) position.</summary>
        public static bool[] CoreMask(IList<Vector3> pts, IList<Vector3> shoulders, float radius)
        {
            var core = new bool[pts.Count];
            for (int i = 0; i < pts.Count; i++)
            {
                core[i] = true;
                foreach (var s in shoulders) if (Vector3.Distance(pts[i], s) <= radius) { core[i] = false; break; }
            }
            return core;
        }

        /// <summary>The p-th percentile (nearest rank) of the values; NaN when empty.</summary>
        public static float Percentile(List<float> values, float p)
        {
            if (values == null || values.Count == 0) return float.NaN;
            var s = new List<float>(values);
            s.Sort();
            int rank = Mathf.Clamp(Mathf.CeilToInt(p / 100f * s.Count), 1, s.Count);
            return s[rank - 1];
        }
    }
}
