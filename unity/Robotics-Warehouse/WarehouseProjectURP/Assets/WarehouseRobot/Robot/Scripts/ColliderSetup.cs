using System.Collections.Generic;
using System.Linq;
using UnityEngine;
using UnityEngine.SceneManagement;

namespace WarehouseRobot
{
    /// <summary>
    /// Makes the warehouse physically solid for the robot at Play start, without editing the vendored warehouse
    /// files (robot_unity.json -> obstacles, collisions):
    /// - every direct child of an obstacle group object (Shelves, FloorBoxes, Walls, Stations) that has no collider
    ///   anywhere below it gets a BoxCollider on each of its meshes (sized to the mesh bounds);
    /// - Rigidbodies under those groups become kinematic, so the robot is blocked by boxes and rack legs instead of
    ///   pushing them away (they were dynamic in the generated scene);
    /// - the robot's colliders ignore every collider tagged with collisions.ignore_tags (the floor).
    /// Runs in Awake, before the first physics step.
    /// </summary>
    [DisallowMultipleComponent]
    public class ColliderSetup : MonoBehaviour
    {
        public int CollidersAdded { get; private set; }
        public int RigidbodiesMadeKinematic { get; private set; }
        public int IgnoredPairs { get; private set; }

        void Awake()
        {
            var rig = GetComponent<RobotRig>();
            var cfg = rig != null ? rig.Config : null;
            if (cfg == null)
            {
                Debug.LogError("[ColliderSetup] No robot config; obstacles not set up.", this);
                return;
            }
            var all = SceneManager.GetActiveScene().GetRootGameObjects()
                .SelectMany(r => r.GetComponentsInChildren<Transform>(true))
                .Where(t => !t.IsChildOf(transform))
                .ToList();

            var report = new List<string>();
            foreach (string group in cfg.Unity.obstacles.groups)
            {
                var groupObjects = all.Where(t => t.name == group).ToList();
                if (groupObjects.Count == 0)
                {
                    report.Add(group + ": not in scene");
                    continue;
                }
                int units = 0, added = 0, kinematic = 0;
                foreach (var g in groupObjects)
                {
                    foreach (Transform unit in g)
                    {
                        units++;
                        if (unit.GetComponentsInChildren<Collider>(true).Length == 0)
                        {
                            foreach (var mf in unit.GetComponentsInChildren<MeshFilter>(true))
                            {
                                if (mf.sharedMesh == null || mf.GetComponent<Renderer>() == null) continue;
                                var box = mf.gameObject.AddComponent<BoxCollider>();
                                var b = mf.sharedMesh.bounds;
                                box.center = b.center;
                                box.size = b.size;
                                added++;
                            }
                        }
                        if (cfg.Unity.obstacles.make_rigidbodies_kinematic)
                        {
                            foreach (var body in unit.GetComponentsInChildren<Rigidbody>(true))
                            {
                                if (body.isKinematic) continue;
                                body.isKinematic = true;
                                kinematic++;
                            }
                        }
                    }
                }
                CollidersAdded += added;
                RigidbodiesMadeKinematic += kinematic;
                report.Add($"{group}: {units} objects, {added} colliders added, {kinematic} rigidbodies made kinematic");
            }

            var ignoreTags = new HashSet<string>(cfg.Unity.collisions.ignore_tags);
            var robotColliders = GetComponentsInChildren<Collider>(true);
            foreach (var t in all)
            {
                if (!ignoreTags.Contains(t.gameObject.tag)) continue;
                foreach (var other in t.GetComponents<Collider>())
                    foreach (var own in robotColliders)
                    {
                        Physics.IgnoreCollision(own, other, true);
                        IgnoredPairs++;
                    }
            }
            report.Add($"robot ignores {IgnoredPairs} collider pairs tagged {string.Join(", ", ignoreTags)}");
            Debug.Log("[ColliderSetup] " + string.Join("; ", report), this);
        }
    }
}
