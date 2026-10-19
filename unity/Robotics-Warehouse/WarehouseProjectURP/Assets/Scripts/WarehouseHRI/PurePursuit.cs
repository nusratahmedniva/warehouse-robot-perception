using System.Collections.Generic;
using UnityEngine;

namespace WarehouseHRI
{
    /// <summary>
    /// Pure-pursuit steering on a floor polyline (x, z). Pure function of its inputs so it can be unit-tested and
    /// mirrored later by the Python controller. Sign convention: w &gt; 0 turns right (Unity yaw, +y rotation).
    /// </summary>
    public static class PurePursuit
    {
        public struct Settings
        {
            public float MaxSpeed;          // m/s, already multiplied by the speed scale
            public float MaxTurnRateDeg;    // deg/s
            public float LookAhead;         // m
            public float RotateInPlaceDeg;  // heading error above which v = 0 and the robot turns in place
            public float TurnGain;          // w = gain * error while turning in place
            public float Decel;             // m/s^2, for the slow-down before the end of the path
            public float StopDistance;      // m, arrived when the remaining path is shorter
        }

        public struct Result
        {
            public float V;
            public float WDeg;
            public bool Arrived;
            public float Remaining;     // path length still to go, m
            public Vector2 Target;      // look-ahead point
        }

        public static Vector2 XZ(Vector3 p) => new Vector2(p.x, p.z);

        /// <summary>Signed angle (deg) from heading <paramref name="yawDeg"/> to the direction pos -> target; + = right.</summary>
        public static float HeadingError(Vector2 pos, float yawDeg, Vector2 target)
        {
            Vector2 d = target - pos;
            if (d.sqrMagnitude < 1e-8f) return 0f;
            float targetYaw = Mathf.Atan2(d.x, d.y) * Mathf.Rad2Deg;
            return Mathf.DeltaAngle(yawDeg, targetYaw);
        }

        /// <summary>
        /// One control step. <paramref name="segment"/> is the index of the path segment the robot is on; it only
        /// moves forward, so the robot never steers back to a point it already passed.
        /// </summary>
        public static Result Step(Vector2 pos, float yawDeg, IList<Vector2> path, ref int segment, Settings s)
        {
            var r = new Result();
            if (path == null || path.Count == 0)
            {
                r.Arrived = true;
                return r;
            }

            if (path.Count == 1)
            {
                path = new[] { pos, path[0] };
                segment = 0;
            }

            segment = Mathf.Clamp(segment, 0, path.Count - 2);

            // Advance the segment index while the robot is past the end of the current segment.
            float along;
            while (true)
            {
                Vector2 a = path[segment], b = path[segment + 1];
                Vector2 ab = b - a;
                float len2 = Mathf.Max(ab.sqrMagnitude, 1e-8f);
                along = Mathf.Clamp01(Vector2.Dot(pos - a, ab) / len2);
                if (along >= 1f && segment < path.Count - 2) { segment++; continue; }
                break;
            }

            // Remaining path length from the projection on the current segment.
            Vector2 proj = Vector2.Lerp(path[segment], path[segment + 1], along);
            float remaining = Vector2.Distance(proj, path[segment + 1]);
            for (int i = segment + 1; i < path.Count - 1; i++) remaining += Vector2.Distance(path[i], path[i + 1]);
            Vector2 goal = path[path.Count - 1];
            float toGoal = Vector2.Distance(pos, goal);
            r.Remaining = Mathf.Max(remaining, segment == path.Count - 2 ? toGoal : 0f);

            if (toGoal <= s.StopDistance)
            {
                r.Arrived = true;
                r.Target = goal;
                return r;
            }

            // Look-ahead point: walk L metres along the path from the projection.
            Vector2 target = goal;
            float need = s.LookAhead;
            Vector2 cursor = proj;
            for (int i = segment; i < path.Count - 1; i++)
            {
                Vector2 next = path[i + 1];
                float seg = Vector2.Distance(cursor, next);
                if (seg >= need)
                {
                    target = cursor + (next - cursor) * (need / Mathf.Max(seg, 1e-6f));
                    break;
                }

                need -= seg;
                cursor = next;
            }

            r.Target = target;
            float err = HeadingError(pos, yawDeg, target);
            float ld = Mathf.Max(Vector2.Distance(pos, target), 1e-3f);

            if (Mathf.Abs(err) > s.RotateInPlaceDeg)
            {
                r.V = 0f;
                r.WDeg = Mathf.Clamp(s.TurnGain * err, -s.MaxTurnRateDeg, s.MaxTurnRateDeg);
                return r;
            }

            // Curvature of the arc through the look-ahead point; slow down in sharp turns and before the goal.
            float kappa = 2f * Mathf.Sin(err * Mathf.Deg2Rad) / ld;
            float v = s.MaxSpeed * Mathf.Cos(err * Mathf.Deg2Rad);
            v = Mathf.Min(v, Mathf.Sqrt(2f * Mathf.Max(s.Decel, 0.01f) * Mathf.Max(r.Remaining - s.StopDistance, 0f)) + 0.05f);
            float maxW = s.MaxTurnRateDeg * Mathf.Deg2Rad;
            if (Mathf.Abs(kappa) > 1e-4f) v = Mathf.Min(v, maxW / Mathf.Abs(kappa));
            v = Mathf.Clamp(v, 0f, s.MaxSpeed);
            r.V = v;
            r.WDeg = Mathf.Clamp(v * kappa * Mathf.Rad2Deg, -s.MaxTurnRateDeg, s.MaxTurnRateDeg);
            return r;
        }
    }
}
