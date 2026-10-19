using System;
using System.Collections.Generic;
using UnityEngine;

namespace WarehouseRobot
{
    [Serializable]
    public struct CollisionRecord
    {
        /// <summary>Time.time (s since play started) when the contact began.</summary>
        public float time_s;
        public string object_hit;
        /// <summary>Full hierarchy path of the object hit, to tell apart objects with the same name.</summary>
        public string object_path;
        public Vector3 contact_point;
        public float relative_speed_mps;
    }

    /// <summary>
    /// Records every collision of the robot (body and mast colliders; Unity reports them on the Rigidbody's object).
    /// One record per obstacle contact: while any robot collider still touches an obstacle, further contacts with it
    /// are the same collision, and touching it again within collisions.merge_recontact_s of losing contact is too.
    /// Objects tagged collisions.ignore_tags (the floor) are never recorded (ColliderSetup also makes physics ignore
    /// them).
    /// </summary>
    [DisallowMultipleComponent]
    public class CollisionRecorder : MonoBehaviour
    {
        [SerializeField] bool logToConsole = true;

        readonly List<CollisionRecord> records = new List<CollisionRecord>();
        readonly Dictionary<Collider, int> touching = new Dictionary<Collider, int>();
        readonly Dictionary<Collider, float> lastContactEnd = new Dictionary<Collider, float>();
        HashSet<string> ignoreTags = new HashSet<string>();
        float mergeWindowS;

        public IReadOnlyList<CollisionRecord> Records => records;
        public int IgnoredContacts { get; private set; }
        public event Action<CollisionRecord> Recorded;

        public void Clear() => records.Clear();

        void Awake()
        {
            var rig = GetComponent<RobotRig>();
            var cfg = rig != null ? rig.Config : null;
            if (cfg == null) return;
            ignoreTags = new HashSet<string>(cfg.Unity.collisions.ignore_tags);
            mergeWindowS = cfg.Unity.collisions.merge_recontact_s;
        }

        void OnCollisionEnter(Collision collision)
        {
            var other = collision.collider;
            if (ignoreTags.Contains(other.gameObject.tag))
            {
                IgnoredContacts++;
                return;
            }
            touching.TryGetValue(other, out int n);
            touching[other] = n + 1;
            if (n > 0) return; // another robot collider already touches this obstacle
            if (lastContactEnd.TryGetValue(other, out float end) && Time.time - end < mergeWindowS) return;

            var record = new CollisionRecord
            {
                time_s = Time.time,
                object_hit = other.name,
                object_path = HierarchyPath(other.transform),
                contact_point = collision.contactCount > 0 ? collision.GetContact(0).point : transform.position,
                relative_speed_mps = collision.relativeVelocity.magnitude,
            };
            records.Add(record);
            if (logToConsole)
                Debug.Log($"[CollisionRecorder] t={record.time_s:F2} s hit '{record.object_path}' at {record.relative_speed_mps:F2} m/s (collision #{records.Count})", this);
            Recorded?.Invoke(record);
        }

        void OnCollisionExit(Collision collision)
        {
            var other = collision.collider;
            if (other == null || !touching.TryGetValue(other, out int n)) return;
            if (n > 1) touching[other] = n - 1;
            else
            {
                touching.Remove(other);
                lastContactEnd[other] = Time.time;
            }
        }

        static string HierarchyPath(Transform t)
        {
            string path = t.name;
            for (var p = t.parent; p != null; p = p.parent) path = p.name + "/" + path;
            return path;
        }
    }
}
