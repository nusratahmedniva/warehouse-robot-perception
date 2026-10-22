using System;
using System.Collections.Generic;

namespace WarehouseHRI
{
    /// <summary>
    /// Task 2 workers (2026-10-22, declared design change after the Task 2 final and its replication; AUDIT.md section
    /// 12): one standing worker per junction instead of the one worker moved from junction to junction. Only one worker
    /// is coded and kept in the scene (GestureWorker "Worker"); the trial runner copies it at Play, so every copy has
    /// the same avatar, material, poses and code. The scene worker stands at the first junction (name order), a copy
    /// named <see cref="CopyName"/> at every other, each at its junction's workerStand (the roadmap rule, unchanged).
    /// </summary>
    public static class Task2Workers
    {
        /// <summary>Name of the copy at a junction; contains "Worker", which the collision scoring counts as a person.</summary>
        public static string CopyName(string original, string junction) => original + "_Task2_" + junction;

        /// <summary>The junctions in name order, or null with the reason when one has no worker stand.</summary>
        public static List<RoadNode> Junctions(IEnumerable<RoadNode> nodes, out string problem)
        {
            problem = null;
            var list = new List<RoadNode>();
            foreach (var n in nodes)
                if (n != null && n.IsJunction) list.Add(n);
            list.Sort((a, b) => string.CompareOrdinal(a.name, b.name));
            foreach (var j in list)
                if (j.workerStand == null)
                {
                    problem = $"junction {j.name} has no worker stand";
                    return null;
                }
            if (list.Count == 0) problem = "the roadmap has no junction";
            return problem == null ? list : null;
        }
    }
}
