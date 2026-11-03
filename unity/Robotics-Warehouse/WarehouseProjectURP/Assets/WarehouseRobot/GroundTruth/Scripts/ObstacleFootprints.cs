using System.Collections.Generic;
using System.Linq;
using UnityEngine;
using UnityEngine.SceneManagement;
using WarehouseHRI.V4;

namespace WarehouseRobot.GroundTruth
{
    /// <summary>
    /// Ground-plane footprints (convex hulls in x, z) of what the robot collides with, for the v4 ground-truth grid.
    /// Obstacles follow ColliderSetup exactly, without touching physics: every direct child ("unit") of an object named
    /// after an obstacle group (robot_unity*.json obstacles.groups: racks, boxes, walls, stations) contributes its
    /// colliders, or, when it has none, one box per mesh (the box ColliderSetup adds at Play). Only active, enabled,
    /// non-trigger parts count, and only those reaching into the robot's height band (above the floor, below the top of
    /// the mast). The floor is every collider tagged placement.floor_tag. The same footprints result in Edit and Play mode.
    /// </summary>
    public static class ObstacleFootprints
    {
        public static List<List<Vector2>> Obstacles(RobotConfig cfg, Transform robotRoot, float floorY, out string report)
        {
            float top = floorY + cfg.Unity.camera_360.height_m;     // top of the mast: the robot's full height
            var all = SceneManager.GetActiveScene().GetRootGameObjects()
                .SelectMany(r => r.GetComponentsInChildren<Transform>(true))
                .Where(t => robotRoot == null || !t.IsChildOf(robotRoot))
                .ToList();
            var result = new List<List<Vector2>>();
            var parts = new List<string>();
            foreach (string group in cfg.Unity.obstacles.groups)
            {
                int units = 0, colliders = 0, meshBoxes = 0;
                foreach (var g in all.Where(t => t.name == group))
                    foreach (Transform unit in g)
                    {
                        units++;
                        var own = unit.GetComponentsInChildren<Collider>(true);
                        if (own.Length > 0)
                        {
                            foreach (var c in own)
                            {
                                if (!c.enabled || !c.gameObject.activeInHierarchy || c.isTrigger) continue;
                                var fp = Footprint(c, floorY, top);
                                if (fp != null) { result.Add(fp); colliders++; }
                            }
                        }
                        else
                        {
                            foreach (var mf in unit.GetComponentsInChildren<MeshFilter>(true))
                            {
                                if (mf.sharedMesh == null || mf.GetComponent<Renderer>() == null || !mf.gameObject.activeInHierarchy) continue;
                                var b = mf.sharedMesh.bounds;
                                var fp = BoxFootprint(mf.transform, b.center, b.size, floorY, top);
                                if (fp != null) { result.Add(fp); meshBoxes++; }
                            }
                        }
                    }
                parts.Add($"{group}: {units} objects, {colliders} colliders, {meshBoxes} mesh boxes");
            }
            report = string.Join("; ", parts) + $" (height band {floorY:0.00} to {top:0.00} m)";
            return result;
        }

        /// <summary>Footprints of the floor: every active collider tagged floorTag.</summary>
        public static List<List<Vector2>> Floors(string floorTag, Transform robotRoot)
        {
            var result = new List<List<Vector2>>();
            foreach (var c in Object.FindObjectsByType<Collider>(FindObjectsInactive.Exclude, FindObjectsSortMode.InstanceID))
            {
                if (!c.enabled || c.isTrigger || !c.CompareTag(floorTag)) continue;
                if (robotRoot != null && c.transform.IsChildOf(robotRoot)) continue;
                var fp = Footprint(c, float.NegativeInfinity, float.PositiveInfinity);
                if (fp != null && fp.Count >= 3) result.Add(fp);
            }
            return result;
        }

        /// <summary>Convex footprint of a collider inside the height band, or null if it lies wholly outside it.</summary>
        static List<Vector2> Footprint(Collider c, float yMin, float yMax)
        {
            switch (c)
            {
                case BoxCollider box:
                    return BoxFootprint(box.transform, box.center, box.size, yMin, yMax);
                case MeshCollider mesh when mesh.sharedMesh != null:
                {
                    var b = c.bounds;
                    if (!(b.max.y > yMin && b.min.y < yMax)) return null;
                    var pts = new List<Vector2>();
                    foreach (var v in mesh.sharedMesh.vertices)
                    {
                        var w = mesh.transform.TransformPoint(v);
                        pts.Add(new Vector2(w.x, w.z));
                    }
                    return Geometry2D.ConvexHull(pts);
                }
                default:
                {
                    var b = c.bounds;
                    if (!(b.max.y > yMin && b.min.y < yMax)) return null;
                    return Geometry2D.ConvexHull(new[]
                    {
                        new Vector2(b.min.x, b.min.z), new Vector2(b.max.x, b.min.z),
                        new Vector2(b.max.x, b.max.z), new Vector2(b.min.x, b.max.z),
                    });
                }
            }
        }

        /// <summary>Footprint of a local box (centre, size) under transform t: the hull of its 8 corners on the ground plane.</summary>
        static List<Vector2> BoxFootprint(Transform t, Vector3 center, Vector3 size, float yMin, float yMax)
        {
            var pts = new List<Vector2>(8);
            float lo = float.PositiveInfinity, hi = float.NegativeInfinity;
            for (int i = 0; i < 8; i++)
            {
                var corner = center + Vector3.Scale(0.5f * size, new Vector3((i & 1) == 0 ? -1 : 1, (i & 2) == 0 ? -1 : 1, (i & 4) == 0 ? -1 : 1));
                var w = t.TransformPoint(corner);
                lo = Mathf.Min(lo, w.y);
                hi = Mathf.Max(hi, w.y);
                pts.Add(new Vector2(w.x, w.z));
            }
            if (!(hi > yMin && lo < yMax)) return null;
            return Geometry2D.ConvexHull(pts);
        }
    }
}
