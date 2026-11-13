using System.Collections.Generic;
using UnityEngine;

namespace WarehouseHRI.V4
{
    /// <summary>
    /// Pan-tilt camera geometry of the v4 robot (2026-11-12, P6: Avatar/Config/upgrade_design.md section 5). Pure functions
    /// on transforms, so they are tested in Edit Mode; PanTiltCamera calls them at Start and the v4 robot builder before it
    /// saves the prefab.
    /// </summary>
    public static class PanTiltGeometry
    {
        /// <summary>
        /// v4 (P6): names of robot renderers that the camera could see at some pan in [panMin, panMax] (every 2 degrees) and
        /// tilt in [tiltMin, tiltMax] (every degree), the view widened by 1 degree on every side to cover the steps. Exact for
        /// each pose: a renderer's oriented local bounds (a convex box) and the view frustum (near plane to far, a convex
        /// solid) are tested with the separating-axis theorem (the 5 frustum face normals, the 3 box face normals and the 18
        /// cross products of their edge directions); no separating axis = the box reaches into the view. Unlike the conservative
        /// level check of PanTiltCamera, the mast passing through the camera is handled exactly (its parts lie inside the near plane).
        /// </summary>
        public static List<string> SelfVisibilityViolations(Transform robotRoot, Vector3 cameraPosition, float verticalFovDeg, float aspect,
                                                                  float near, float panMinDeg, float panMaxDeg, float tiltMinDeg, float tiltMaxDeg,
                                                                  float far = 100f)
        {
            float tv = Mathf.Tan(0.5f * verticalFovDeg * Mathf.Deg2Rad + Mathf.Deg2Rad);
            float th = Mathf.Tan(Mathf.Atan(Mathf.Tan(0.5f * verticalFovDeg * Mathf.Deg2Rad) * aspect) + Mathf.Deg2Rad);
            Quaternion toRobot = Quaternion.Inverse(robotRoot.rotation);
            var boxes = new List<(string name, Vector3[] pts, Vector3[] axes)>();
            foreach (var r in robotRoot.GetComponentsInChildren<Renderer>(true))
            {
                Bounds lb = r.localBounds;
                var pts = new Vector3[8];
                for (int i = 0; i < 8; i++)
                {
                    var c = lb.center + Vector3.Scale(lb.extents, new Vector3((i & 1) == 0 ? -1 : 1, (i & 2) == 0 ? -1 : 1, (i & 4) == 0 ? -1 : 1));
                    pts[i] = toRobot * (r.transform.TransformPoint(c) - cameraPosition);     // robot frame, camera at the origin
                }
                var axes = new[] { toRobot * r.transform.TransformVector(Vector3.right), toRobot * r.transform.TransformVector(Vector3.up),
                                   toRobot * r.transform.TransformVector(Vector3.forward) };      // the box's edge directions
                boxes.Add((r.name, pts, axes));
            }
            // the frustum in the camera frame (x right, y up, z forward)
            var fr = new Vector3[8];
            for (int i = 0; i < 4; i++)
            {
                float sx = (i & 1) == 0 ? -1 : 1, sy = (i & 2) == 0 ? -1 : 1;
                fr[i] = new Vector3(sx * th * near, sy * tv * near, near);
                fr[i + 4] = new Vector3(sx * th * far, sy * tv * far, far);
            }
            var frNormals = new[] { Vector3.forward, new Vector3(1f, 0f, th), new Vector3(-1f, 0f, th), new Vector3(0f, 1f, tv), new Vector3(0f, -1f, tv) };
            var frEdges = new[] { Vector3.right, Vector3.up, new Vector3(th, tv, 1f), new Vector3(-th, tv, 1f), new Vector3(th, -tv, 1f), new Vector3(-th, -tv, 1f) };
            var violations = new List<string>();
            int panSteps = Mathf.Max(1, Mathf.CeilToInt((panMaxDeg - panMinDeg) / 2f)), tiltSteps = Mathf.Max(0, Mathf.CeilToInt(tiltMaxDeg - tiltMinDeg));
            var q = new Vector3[8];
            var qa = new Vector3[3];
            var axesAll = new List<Vector3>(26);
            foreach (var (name, pts, axes) in boxes)
            {
                bool seen = false;
                for (int ip = 0; ip <= panSteps && !seen; ip++)
                {
                    float pan = Mathf.Lerp(panMinDeg, panMaxDeg, (float)ip / panSteps);
                    for (int it = 0; it <= tiltSteps && !seen; it++)
                    {
                        float tilt = tiltSteps == 0 ? tiltMinDeg : Mathf.Lerp(tiltMinDeg, tiltMaxDeg, (float)it / tiltSteps);
                        // camera orientation in the robot frame: pan about up (+ = left), then tilt up about the camera's x axis
                        var toCam = Quaternion.Inverse(Quaternion.Euler(0f, -pan, 0f) * Quaternion.Euler(-tilt, 0f, 0f));
                        for (int k = 0; k < 8; k++) q[k] = toCam * pts[k];
                        for (int k = 0; k < 3; k++) qa[k] = toCam * axes[k];
                        axesAll.Clear();
                        axesAll.AddRange(frNormals);
                        axesAll.Add(Vector3.Cross(qa[1], qa[2]));
                        axesAll.Add(Vector3.Cross(qa[2], qa[0]));
                        axesAll.Add(Vector3.Cross(qa[0], qa[1]));
                        foreach (var a in qa) foreach (var e in frEdges) axesAll.Add(Vector3.Cross(a, e));
                        bool separated = false;
                        foreach (var ax in axesAll)
                        {
                            if (ax.sqrMagnitude < 1e-12f) continue;
                            float aMin = float.PositiveInfinity, aMax = float.NegativeInfinity, bMin = float.PositiveInfinity, bMax = float.NegativeInfinity;
                            foreach (var v in q) { float d = Vector3.Dot(v, ax); aMin = Mathf.Min(aMin, d); aMax = Mathf.Max(aMax, d); }
                            foreach (var v in fr) { float d = Vector3.Dot(v, ax); bMin = Mathf.Min(bMin, d); bMax = Mathf.Max(bMax, d); }
                            if (aMax < bMin || bMax < aMin) { separated = true; break; }
                        }
                        seen = !separated;
                    }
                }
                if (seen) violations.Add(name);
            }
            return violations;
        }
    }
}
