using System.Collections.Generic;
using UnityEngine;

namespace WarehouseAvatar
{
    /// <summary>
    /// Arm-skin probe (Avatar/Config/experiments_ab.md section 5, declared before it ran): does a look's mesh follow its arm bones? The upper
    /// arm is rotated RotationDeg about the axis perpendicular to the arm and the vertical (the arm swings up) and every skinned mesh is baked
    /// before and after; the arm-region vertices must move with the bone (the rigid rotation that also carries the forearm and hand).
    /// Report only: nothing is changed on the look.
    /// </summary>
    public static class ArmSkinCheck
    {
        public const float RotationDeg = 45f;
        /// <summary>Arm region: within this fraction of the upper-arm length of the forearm or of the distal part of the upper arm.</summary>
        public const float ArmRadiusOfUpperArm = 0.25f;
        /// <summary>The upper-arm part of the arm region starts at this fraction of the way from the shoulder to the elbow.</summary>
        public const float UpperArmFrom = 0.5f;
        /// <summary>Hand region: the remaining vertices within this fraction of the forearm length of the wrist.</summary>
        public const float HandRadiusOfForearm = 0.5f;
        /// <summary>A vertex follows when it lies within this fraction of its expected displacement of the expected position.</summary>
        public const float FollowTolerance = 0.25f;
        public const float PassFraction = 0.95f;
        public const int MinArmVertices = 50;

        public const string Follows = "follows", DoesNotFollow = "does_not_follow", Inconclusive = "inconclusive";

        public enum Region { None, Arm, Hand }

        public sealed class SideResult
        {
            public int ArmVertices, ArmFollowing, HandVertices, HandFollowing;
            public float ArmErrorMedianM, ArmExpectedMoveMedianM;
            public string Verdict;
        }

        public static Region Classify(Vector3 p, Vector3 shoulder, Vector3 elbow, Vector3 wrist)
        {
            float upper = Vector3.Distance(shoulder, elbow), fore = Vector3.Distance(elbow, wrist);
            if (upper <= 0f || fore <= 0f) return Region.None;
            float r = ArmRadiusOfUpperArm * upper;
            if (NearSegment(p, elbow, wrist, 0f, r) || NearSegment(p, shoulder, elbow, UpperArmFrom, r)) return Region.Arm;
            return Vector3.Distance(p, wrist) <= HandRadiusOfForearm * fore ? Region.Hand : Region.None;
        }

        static bool NearSegment(Vector3 p, Vector3 a, Vector3 b, float from, float radius)
        {
            Vector3 ab = b - a;
            float s = Vector3.Dot(p - a, ab) / ab.sqrMagnitude;
            return s >= from && s <= 1f && (p - (a + s * ab)).magnitude <= radius;
        }

        public static bool VertexFollows(Vector3 rest, Vector3 posed, Vector3 expected) =>
            Vector3.Distance(posed, expected) <= FollowTolerance * Vector3.Distance(rest, expected);

        public static string Verdict(int armVertices, int armFollowing) =>
            armVertices < MinArmVertices ? Inconclusive : armFollowing >= PassFraction * armVertices ? Follows : DoesNotFollow;

        /// <summary>Both sides follow: follows; any side does not: does_not_follow; otherwise inconclusive.</summary>
        public static string LookVerdict(IList<string> sides)
        {
            if (sides.Count == 0) return Inconclusive;
            if (sides.Contains(DoesNotFollow)) return DoesNotFollow;
            return sides.Contains(Inconclusive) ? Inconclusive : Follows;
        }

        /// <summary>One side; the upper arm's rotation is restored afterwards.</summary>
        public static SideResult MeasureSide(Transform upper, Transform lower, Transform hand, IList<SkinnedMeshRenderer> meshes)
        {
            var r = new SideResult();
            Vector3 s = upper.position, e = lower.position, w = hand.position;
            Vector3 axis = Vector3.Cross((e - s).normalized, Vector3.up);
            if (axis.sqrMagnitude < 1e-6f) axis = Vector3.Cross((e - s).normalized, Vector3.forward);
            var q = Quaternion.AngleAxis(RotationDeg, axis.normalized);
            var tmp = new Mesh();
            var errors = new List<float>();
            var moves = new List<float>();
            try
            {
                var rest = new List<Vector3[]>();
                foreach (var m in meshes) rest.Add(Bake(m, tmp));
                Quaternion old = upper.rotation;
                upper.rotation = q * old;
                try
                {
                    for (int k = 0; k < meshes.Count; k++)
                    {
                        var posed = Bake(meshes[k], tmp);
                        var before = rest[k];
                        for (int i = 0; i < before.Length && i < posed.Length; i++)
                        {
                            var region = Classify(before[i], s, e, w);
                            if (region == Region.None) continue;
                            Vector3 expected = s + q * (before[i] - s);
                            bool follows = VertexFollows(before[i], posed[i], expected);
                            if (region == Region.Arm)
                            {
                                r.ArmVertices++;
                                if (follows) r.ArmFollowing++;
                                errors.Add(Vector3.Distance(posed[i], expected));
                                moves.Add(Vector3.Distance(before[i], expected));
                            }
                            else
                            {
                                r.HandVertices++;
                                if (follows) r.HandFollowing++;
                            }
                        }
                    }
                }
                finally { upper.rotation = old; }
            }
            finally { Object.DestroyImmediate(tmp); }
            r.ArmErrorMedianM = Median(errors);
            r.ArmExpectedMoveMedianM = Median(moves);
            r.Verdict = Verdict(r.ArmVertices, r.ArmFollowing);
            return r;
        }

        /// <summary>World-space vertices of the mesh as skinned by the bones' current transforms.</summary>
        static Vector3[] Bake(SkinnedMeshRenderer smr, Mesh tmp)
        {
            smr.BakeMesh(tmp, true);   // renderer space, the renderer's scale applied
            var v = tmp.vertices;
            var m = Matrix4x4.TRS(smr.transform.position, smr.transform.rotation, Vector3.one);
            for (int i = 0; i < v.Length; i++) v[i] = m.MultiplyPoint3x4(v[i]);
            return v;
        }

        static float Median(List<float> x)
        {
            if (x.Count == 0) return -1f;
            x.Sort();
            return x.Count % 2 == 1 ? x[x.Count / 2] : 0.5f * (x[x.Count / 2 - 1] + x[x.Count / 2]);
        }
    }
}
