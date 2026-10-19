using System;
using System.Collections.Generic;
using UnityEngine;

namespace WarehouseHRI
{
    public enum RoadNodeKind
    {
        Waypoint, // pass-through (e.g. start point A): exactly one branch, no worker, no question
        Junction, // a worker stands at workerStand; the robot asks which branch to take
        Endpoint, // end of a road: a possible goal B
    }

    [Serializable]
    public class RoadBranch
    {
        public GestureCommand command = GestureCommand.FORWARD;
        public RoadNode next;
    }

    /// <summary>
    /// One node of the warehouse roadmap. The robot knows the roadmap (it is the map), never the goal B.
    /// </summary>
    public class RoadNode : MonoBehaviour
    {
        public RoadNodeKind kind = RoadNodeKind.Junction;
        [Tooltip("Junctions only: where the worker stands (position and facing).")]
        public Transform workerStand;
        public List<RoadBranch> branches = new List<RoadBranch>();

        public bool IsEndpoint => kind == RoadNodeKind.Endpoint;
        public bool IsJunction => kind == RoadNodeKind.Junction;
        public Vector3 Position => transform.position;

        /// <summary>The node reached by <paramref name="command"/>, or null when this node has no such branch.</summary>
        public RoadNode Next(GestureCommand command)
        {
            foreach (var b in branches)
                if (b != null && b.next != null && b.command == command) return b.next;
            return null;
        }

        /// <summary>Waypoints: their single successor (null otherwise).</summary>
        public RoadNode OnlyNext => branches.Count == 1 && branches[0] != null ? branches[0].next : null;

        /// <summary>True when <paramref name="goal"/> is this node or can be reached from it.</summary>
        public bool Reaches(RoadNode goal)
        {
            if (goal == null) return false;
            var seen = new HashSet<RoadNode>();
            var stack = new Stack<RoadNode>();
            stack.Push(this);
            while (stack.Count > 0)
            {
                var n = stack.Pop();
                if (n == null || !seen.Add(n)) continue;
                if (n == goal) return true;
                foreach (var b in n.branches)
                    if (b != null && b.next != null) stack.Push(b.next);
            }

            return false;
        }

        /// <summary>
        /// SCRIPTING / SCORING ONLY: the command that leads toward <paramref name="goal"/> (NONE if no branch does).
        /// Used to script what the worker shows and to score the run, never by the robot's decisions.
        /// </summary>
        public GestureCommand CommandToward(RoadNode goal)
        {
            foreach (var b in branches)
                if (b != null && b.next != null && b.next.Reaches(goal)) return b.command;
            return GestureCommand.NONE;
        }

        /// <summary>All endpoints reachable from this node (possible goals), in stable depth-first order.</summary>
        public List<RoadNode> ReachableEndpoints()
        {
            var result = new List<RoadNode>();
            var seen = new HashSet<RoadNode>();
            Collect(this, seen, result);
            return result;
        }

        static void Collect(RoadNode n, HashSet<RoadNode> seen, List<RoadNode> result)
        {
            if (n == null || !seen.Add(n)) return;
            if (n.IsEndpoint) result.Add(n);
            foreach (var b in n.branches)
                if (b != null) Collect(b.next, seen, result);
        }

        void OnDrawGizmos()
        {
            Vector3 p = transform.position + Vector3.up * 0.05f;
            switch (kind)
            {
                case RoadNodeKind.Endpoint:
                    Gizmos.color = new Color(1f, 0.55f, 0f);
                    Gizmos.DrawWireSphere(p, 0.3f); // the 0.3 m success radius
                    Gizmos.DrawSphere(p, 0.1f);
                    break;
                case RoadNodeKind.Junction:
                    Gizmos.color = Color.yellow;
                    Gizmos.DrawWireCube(p, new Vector3(0.6f, 0.1f, 0.6f));
                    break;
                default:
                    Gizmos.color = Color.green;
                    Gizmos.DrawSphere(p, 0.2f);
                    break;
            }

            foreach (var b in branches)
            {
                if (b == null || b.next == null) continue;
                Gizmos.color = Color.white;
                Vector3 q = b.next.transform.position + Vector3.up * 0.05f;
                Gizmos.DrawLine(p, q);
                // Arrow head near the far end shows the direction of travel.
                Vector3 dir = (q - p).normalized;
                Vector3 side = Vector3.Cross(Vector3.up, dir) * 0.25f;
                Vector3 tip = q - dir * 0.6f;
                Gizmos.DrawLine(tip, tip - dir * 0.4f + side);
                Gizmos.DrawLine(tip, tip - dir * 0.4f - side);
            }

            if (workerStand != null)
            {
                Gizmos.color = Color.magenta;
                Gizmos.DrawLine(p, workerStand.position + Vector3.up * 0.05f);
                Gizmos.DrawWireSphere(workerStand.position + Vector3.up * 0.9f, 0.3f);
                Gizmos.DrawRay(workerStand.position + Vector3.up * 0.9f, workerStand.forward * 0.6f);
            }
        }
    }
}
