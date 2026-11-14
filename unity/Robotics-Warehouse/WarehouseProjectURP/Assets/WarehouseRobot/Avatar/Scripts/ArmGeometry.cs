using System;
using System.Collections.Generic;
using UnityEngine;

namespace WarehouseAvatar
{
    /// <summary>
    /// A rig's own arm proportions (Avatar/Config/experiments_ab.md section 10, declared before it was built), measured once in the rest
    /// pose before any animation: upper arm (UpperArm to LowerArm bone), forearm (LowerArm to Hand), shoulder width (between the two
    /// upper-arm bones) and shoulder height (upper-arm bones above the worker's root). Means of the two sides.
    /// </summary>
    [Serializable]
    public struct ArmProportions
    {
        public float upper_m, forearm_m, shoulder_width_m, shoulder_height_m;

        /// <summary>Shoulder to wrist along the bones (WorkerV4.ArmLength).</summary>
        public float Arm => upper_m + forearm_m;

        public static ArmProportions Measure(LookPoser.Arm left, LookPoser.Arm right, Transform root)
        {
            float U(LookPoser.Arm a) => Vector3.Distance(a.Upper.position, a.Lower.position);
            float F(LookPoser.Arm a) => Vector3.Distance(a.Lower.position, a.Hand.position);
            float y = root != null ? root.position.y : 0f;
            return new ArmProportions
            {
                upper_m = 0.5f * (U(left) + U(right)),
                forearm_m = 0.5f * (F(left) + F(right)),
                shoulder_width_m = Vector3.Distance(left.Upper.position, right.Upper.position),
                shoulder_height_m = 0.5f * (left.Upper.position.y + right.Upper.position.y) - y,
            };
        }
    }

    /// <summary>
    /// The lengths the gesture targets use (experiments_ab.md section 10). <see cref="Legacy"/>: the split used before section 10, Sunbox's
    /// (PROCEED upper arm 0.53 L and forearm 0.47 L; the POINT and STOP elbow hints 0.5 L along the arm; the WAIT hint 0.5 L below the hand).
    /// <see cref="Rig"/>: the rig's own upper arm and forearm.
    /// </summary>
    public struct ArmSplit
    {
        public float L, ProceedUpper, ProceedFore, HintAlong, HintBelow;
        /// <summary>PROCEED's elbow lies exactly ProceedUpper from the shoulder (its sideways offset included); false = the legacy formula,
        /// whose sideways offset put it ~0.5 % farther.</summary>
        public bool ElbowOnUpperArm;

        public static ArmSplit Legacy(float armLength) => new ArmSplit
        {
            L = armLength, ProceedUpper = 0.53f * armLength, ProceedFore = 0.47f * armLength, HintAlong = 0.5f * armLength, HintBelow = 0.5f * armLength,
        };

        public static ArmSplit Rig(ArmProportions p) => new ArmSplit
        {
            L = p.Arm, ProceedUpper = p.upper_m, ProceedFore = p.forearm_m, HintAlong = p.upper_m, HintBelow = p.forearm_m, ElbowOnUpperArm = true,
        };
    }

    /// <summary>One frame's IK goal of the gesturing arm (world): hand target, elbow hint and, for PROCEED, the intended elbow.</summary>
    public struct GestureGoal
    {
        public Vector3 Shoulder, Target, Hint, Elbow;
        public bool HasElbow, Valid;
    }

    /// <summary>
    /// The hand target and elbow hint of every command (the formula of WorkerV4.ComputeTargets, worker_v4.json clips and limits), pure so
    /// the old and the new split can be compared. The sway is added by the caller.
    /// </summary>
    public static class GestureTargets
    {
        /// <param name="s">the shoulder (upper-arm bone) the target is measured from</param>
        /// <param name="side">level unit vector out of the gesturing arm's side</param>
        /// <param name="fwd">level unit vector the body faces</param>
        /// <param name="pointDir">POINT: the horizontal direction shown</param>
        /// <param name="size">the gesture's drawn size</param>
        /// <param name="pointElevationDeg">POINT: the drawn elevation (before the size)</param>
        /// <param name="proceedPhiDeg">PROCEED: the forearm's angle above horizontal now</param>
        /// <param name="stopPushM">STOP: the push toward the robot now, metres</param>
        public static GestureGoal Compute(GestureClipSpec spec, WorkerLimits lim, ArmSplit a, Vector3 s, Vector3 side, Vector3 fwd, Vector3 pointDir,
                                          float size, float pointElevationDeg, float proceedPhiDeg, float stopPushM)
        {
            var g = new GestureGoal { Shoulder = s, Valid = true };
            Vector3 up = Vector3.up;
            float L = a.L, k = size;
            switch (spec.command)
            {
                case WorkerV4Config.Point:
                {
                    float el = pointElevationDeg * k;
                    Vector3 d = (Mathf.Cos(el * Mathf.Deg2Rad) * pointDir.normalized + Mathf.Sin(el * Mathf.Deg2Rad) * up).normalized;
                    float reach = Mathf.Clamp(spec.reach, lim.point_reach[0], lim.point_reach[1]);
                    g.Target = s + d * (L * reach);
                    g.Hint = s + d * a.HintAlong - up * (spec.elbow_down_l * L);
                    break;
                }
                case WorkerV4Config.Proceed:
                {
                    // the elbow bent below the shoulder, the forearm at proceedPhiDeg above horizontal toward the front
                    float au = spec.upper_forward_deg * Mathf.Deg2Rad;
                    Vector3 upperDir = Mathf.Cos(au) * -up + Mathf.Sin(au) * fwd;
                    // the elbow a little out to the side (0.08 L); the rig split keeps it at the upper arm's length from the shoulder
                    g.Elbow = a.ElbowOnUpperArm
                        ? s + a.ProceedUpper * (a.ProceedUpper * upperDir + side * (0.08f * L)).normalized
                        : s + a.ProceedUpper * upperDir + side * (0.08f * L);
                    g.HasElbow = true;
                    float pr = proceedPhiDeg * Mathf.Deg2Rad;
                    g.Target = g.Elbow + (Mathf.Cos(pr) * fwd + Mathf.Sin(pr) * up) * a.ProceedFore;
                    g.Hint = g.Elbow + side * (0.1f * L) - up * (0.02f * L);
                    break;
                }
                case WorkerV4Config.Wait:
                {
                    float upL = Mathf.Max(spec.hand_up_l * k, lim.wait_min_up_l);
                    g.Target = s + L * (side * (spec.hand_side_l * k) + fwd * (spec.hand_forward_l * k) + up * upL);
                    g.Hint = g.Target - up * a.HintBelow + side * (spec.elbow_down_l * L);   // forearm vertical, elbow out
                    break;
                }
                default:
                {
                    float az = spec.azimuth_out_deg * Mathf.Deg2Rad, el = spec.elevation_deg * Mathf.Deg2Rad;
                    Vector3 h = Mathf.Cos(az) * fwd + Mathf.Sin(az) * side;
                    Vector3 d = (Mathf.Cos(el) * h + Mathf.Sin(el) * up).normalized;
                    float reach = Mathf.Clamp(spec.reach * k, lim.stop_reach[0], lim.stop_reach[1]);
                    g.Target = s + d * (L * reach) + fwd * stopPushM;
                    g.Hint = s + d * a.HintAlong - up * (spec.elbow_down_l * L) + side * (0.05f * L);
                    break;
                }
            }
            return g;
        }
    }

    /// <summary>Avatar/Config/gesture_geometry.json: the declared tolerance of the geometric check and the stage it runs on.</summary>
    [Serializable]
    public class GestureGeometryConfig
    {
        public string note;
        public GeometryTolerance tolerance;
        public GeometryStage stage;
        public GeometryScreens screens;
        public GeometryOutput output;

        public static GestureGeometryConfig Parse(string json) =>
            JsonUtility.FromJson<GestureGeometryConfig>(json ?? "") ?? throw new FormatException("gesture_geometry.json: not a JSON object");

        public List<string> Validate()
        {
            var e = new List<string>();
            var t = tolerance;
            if (t == null) e.Add("tolerance missing");
            else
            {
                if (!(t.elbow_angle_deg > 0f) || !(t.arm_direction_deg > 0f) || !(t.forearm_direction_deg > 0f)) e.Add("tolerance: every angle must be > 0");
                if (!(t.no_fold_min_elbow_deg > 0f && t.no_fold_min_elbow_deg < 180f)) e.Add("tolerance.no_fold_min_elbow_deg must be in (0, 180)");
                if (t.no_fold_commands == null || t.no_fold_commands.Length == 0) e.Add("tolerance.no_fold_commands missing");
            }
            var s = stage;
            if (s == null) e.Add("stage missing");
            else
            {
                if (!(s.spacing_m > 0f) || !(s.robot_distance_m > 0f)) e.Add("stage.spacing_m and robot_distance_m must be > 0");
                if (s.hold_frames < 2) e.Add("stage.hold_frames must be >= 2");
                if (!(s.proceed_window_s > 0f)) e.Add("stage.proceed_window_s must be > 0");
                if (s.point_side_azimuth_deg == null || s.point_side_azimuth_deg.Length == 0) e.Add("stage.point_side_azimuth_deg missing");
            }
            if (screens == null || screens.width_px < 64 || screens.height_px < 64 || !(screens.vertical_fov_deg > 0f)) e.Add("screens: size and field of view");
            if (output == null || string.IsNullOrEmpty(output.root) || string.IsNullOrEmpty(output.run_prefix)) e.Add("output.root and run_prefix required");
            return e;
        }
    }

    [Serializable]
    public class GeometryTolerance
    {
        public float elbow_angle_deg, arm_direction_deg, forearm_direction_deg, no_fold_min_elbow_deg;
        public string[] no_fold_commands;
    }

    [Serializable]
    public class GeometryStage
    {
        public int seed, hold_frames;
        public float spacing_m, robot_distance_m, settle_after_hold_s, question_after_request_s, pause_between_s, phase_wait_max_s, proceed_window_s;
        public float[] point_side_azimuth_deg;
        public float floor_grey, backdrop_grey, ambient_grey, light_intensity;
        public float[] light_euler_deg;
    }

    [Serializable]
    public class GeometryScreens
    {
        public string[] kind_groups;
        public float distance_m, azimuth_right_deg, height_m, vertical_fov_deg, aim_height_of_body;
        public int width_px, height_px;
    }

    [Serializable]
    public class GeometryOutput { public string root, run_prefix; }

    /// <summary>One measured frame: the rendered joints and the worker's own goal of that frame.</summary>
    public struct GeometrySample
    {
        public string Command;
        public Vector3 S, E, W;          // rendered shoulder (UpperArm), elbow (LowerArm), wrist (Hand)
        public GestureGoal Goal;
        public float Upper, Fore;        // the rig's own segment lengths
    }

    public struct GeometryResult
    {
        public float ElbowDeg, IntendedElbowDeg, ElbowErrorDeg, ArmDirectionErrorDeg, ForearmErrorDeg;   // ForearmErrorDeg -1 = not measured
        public bool Fold, Pass;
        public string Why;
    }

    /// <summary>The geometric check of experiments_ab.md section 10: rendered pose against the intended pose, within the declared tolerance.</summary>
    public static class GestureGeometry
    {
        /// <summary>Interior angle at b between a and c, degrees (180 = straight).</summary>
        public static float InteriorDeg(Vector3 a, Vector3 b, Vector3 c) => Vector3.Angle(a - b, c - b);

        /// <summary>The elbow's interior angle of a two-bone arm (upper, fore) whose shoulder-to-wrist distance is d; 180 when d is out of
        /// reach, 0 when d is at most |upper - fore|.</summary>
        public static float TwoBoneElbowDeg(float upper, float fore, float d)
        {
            if (upper <= 0f || fore <= 0f) return float.NaN;
            if (d >= upper + fore) return 180f;
            if (d <= Mathf.Abs(upper - fore)) return 0f;
            double c = (upper * (double)upper + fore * (double)fore - d * (double)d) / (2.0 * upper * fore);
            return (float)(Math.Acos(Math.Max(-1.0, Math.Min(1.0, c))) * 180.0 / Math.PI);
        }

        public static GeometryResult Evaluate(GeometrySample x, GeometryTolerance tol)
        {
            var r = new GeometryResult { ForearmErrorDeg = -1f };
            var g = x.Goal;
            r.ElbowDeg = InteriorDeg(x.S, x.E, x.W);
            r.IntendedElbowDeg = TwoBoneElbowDeg(x.Upper, x.Fore, Vector3.Distance(g.Target, g.Shoulder));
            r.ElbowErrorDeg = Mathf.Abs(r.ElbowDeg - r.IntendedElbowDeg);
            r.ArmDirectionErrorDeg = Vector3.Angle(x.W - x.S, g.Target - g.Shoulder);
            if (x.Command == WorkerV4Config.Wait) r.ForearmErrorDeg = Vector3.Angle(x.W - x.E, Vector3.up);
            else if (x.Command == WorkerV4Config.Proceed && g.HasElbow) r.ForearmErrorDeg = Vector3.Angle(x.W - x.E, g.Target - g.Elbow);
            r.Fold = tol.no_fold_commands != null && Array.IndexOf(tol.no_fold_commands, x.Command) >= 0 && r.ElbowDeg < tol.no_fold_min_elbow_deg;
            var why = new List<string>();
            if (!(r.ElbowErrorDeg <= tol.elbow_angle_deg)) why.Add("elbow angle");
            if (!(r.ArmDirectionErrorDeg <= tol.arm_direction_deg)) why.Add("arm direction");
            if (r.ForearmErrorDeg >= 0f && !(r.ForearmErrorDeg <= tol.forearm_direction_deg)) why.Add("forearm direction");
            if (r.Fold) why.Add("fold");
            r.Pass = why.Count == 0;
            r.Why = string.Join(", ", why);
            return r;
        }
    }
}
