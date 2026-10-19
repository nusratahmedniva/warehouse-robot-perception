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
    /// Records every collision of the robot body (one record per new contact, from OnCollisionEnter on the
    /// Rigidbody). The robot floats at collider_bottom_m with Y frozen, so the floor never registers.
    /// </summary>
    [DisallowMultipleComponent]
    public class CollisionRecorder : MonoBehaviour
    {
        [SerializeField] bool logToConsole = true;

        readonly List<CollisionRecord> records = new List<CollisionRecord>();

        public IReadOnlyList<CollisionRecord> Records => records;
        public event Action<CollisionRecord> Recorded;

        public void Clear() => records.Clear();

        void OnCollisionEnter(Collision collision)
        {
            var record = new CollisionRecord
            {
                time_s = Time.time,
                object_hit = collision.collider.name,
                object_path = HierarchyPath(collision.collider.transform),
                contact_point = collision.contactCount > 0 ? collision.GetContact(0).point : transform.position,
                relative_speed_mps = collision.relativeVelocity.magnitude,
            };
            records.Add(record);
            if (logToConsole)
                Debug.Log($"[CollisionRecorder] t={record.time_s:F2} s hit '{record.object_path}' at {record.relative_speed_mps:F2} m/s", this);
            Recorded?.Invoke(record);
        }

        static string HierarchyPath(Transform t)
        {
            string path = t.name;
            for (var p = t.parent; p != null; p = p.parent) path = p.name + "/" + path;
            return path;
        }
    }
}
