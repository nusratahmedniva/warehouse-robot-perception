using System.Collections.Generic;
using UnityEngine;

namespace WarehouseAvatar
{
    /// <summary>
    /// Finger skin probe (Avatar/Config/experiments_ab.md section 10, declared before it ran): does each finger chain of a hand move its own
    /// finger and only that one? Per chain under the Hand bone, the chain's first bone is bent BendDeg about the axis across the finger
    /// (finger direction x palm normal) and every skinned mesh is baked before and after; a vertex moves when it moves more than MoveM. A
    /// finger's region = the rest-pose vertices within RegionM of its own bone chain and nearer to it than to any other chain of the hand.
    /// Separate: at least OwnMin of its own region moves and at most OtherMax of every other finger's region. Report only.
    /// </summary>
    public static class FingerSkinCheck
    {
        public const float BendDeg = 30f, MoveM = 0.002f, RegionM = 0.04f, OwnMin = 0.8f, OtherMax = 0.2f;
        public const int MinRegion = 30;
        public const string Separate = "separate", Merged = "merged", Inconclusive = "inconclusive";

        public sealed class FingerResult
        {
            public string Name, Verdict, MostMovedOther = "";
            public string[] Bones;
            public int Region, RegionMoved;
            public float OwnFraction, MaxOtherFraction;
        }

        /// <summary>The bone chains under a hand: each child of the hand followed down its first children.</summary>
        public static List<Transform[]> Chains(Transform hand)
        {
            var list = new List<Transform[]>();
            if (hand == null) return list;
            foreach (Transform c in hand)
            {
                var chain = new List<Transform>();
                for (var t = c; t != null; t = t.childCount > 0 ? t.GetChild(0) : null) chain.Add(t);
                list.Add(chain.ToArray());
            }
            return list;
        }

        /// <summary>Distance of p from the chain's polyline (hand to its first bone excluded: the base joint onward).</summary>
        public static float Distance(Vector3 p, Transform[] chain)
        {
            if (chain.Length == 1) return Vector3.Distance(p, chain[0].position);
            float best = float.PositiveInfinity;
            for (int i = 0; i + 1 < chain.Length; i++)
            {
                Vector3 a = chain[i].position, b = chain[i + 1].position, ab = b - a;
                float s = ab.sqrMagnitude > 1e-12f ? Mathf.Clamp01(Vector3.Dot(p - a, ab) / ab.sqrMagnitude) : 0f;
                best = Mathf.Min(best, Vector3.Distance(p, a + s * ab));
            }
            return best;
        }

        public static string Verdict(int region, float own, float maxOther) =>
            region < MinRegion ? Inconclusive : own >= OwnMin && maxOther <= OtherMax ? Separate : Merged;

        /// <summary>Every chain of one hand; each bent bone's rotation is restored afterwards. With <paramref name="islands"/> (a palm_plates
        /// rule, experiments_ab.md section 12 addendum 7 decision 4) a finger's vertices are those of its mesh islands instead of the RegionM
        /// region: every island of the rule's material belonging to this hand except the plate (the largest box), assigned to the chain
        /// nearest to its centroid.</summary>
        public static List<FingerResult> MeasureHand(Transform hand, IList<SkinnedMeshRenderer> meshes, PalmPlateSpec islands = null)
        {
            var chains = Chains(hand);
            var results = new List<FingerResult>();
            if (chains.Count == 0) return results;
            var tmp = new Mesh();
            try
            {
                var rest = BakeAll(meshes, tmp);
                var owner = islands != null ? IslandOwners(hand, meshes, chains, rest, islands) : RegionOwners(chains, rest);
                var count = new int[chains.Count];
                foreach (int o in owner) if (o >= 0) count[o]++;
                Vector3 normal = PalmNormal(hand, chains);
                for (int f = 0; f < chains.Count; f++)
                {
                    var root = chains[f][0];
                    Vector3 tip = chains[f][chains[f].Length - 1].position;
                    Vector3 dir = (chains[f].Length > 1 ? tip - root.position : root.position - hand.position).normalized;
                    Vector3 axis = Vector3.Cross(dir, normal);
                    if (axis.sqrMagnitude < 1e-6f) axis = Vector3.Cross(dir, Vector3.forward);
                    Quaternion old = root.rotation;
                    root.rotation = Quaternion.AngleAxis(BendDeg, axis.normalized) * old;
                    List<Vector3> bent;
                    try { bent = BakeAll(meshes, tmp); }
                    finally { root.rotation = old; }
                    var moved = new int[chains.Count];
                    for (int i = 0; i < rest.Count && i < bent.Count; i++)
                        if (owner[i] >= 0 && Vector3.Distance(rest[i], bent[i]) > MoveM) moved[owner[i]]++;
                    var r = new FingerResult { Name = root.name, Bones = Names(chains[f]), Region = count[f], RegionMoved = moved[f] };
                    r.OwnFraction = count[f] > 0 ? (float)moved[f] / count[f] : 0f;
                    for (int g = 0; g < chains.Count; g++)
                    {
                        if (g == f || count[g] == 0) continue;
                        float frac = (float)moved[g] / count[g];
                        if (frac > r.MaxOtherFraction) { r.MaxOtherFraction = frac; r.MostMovedOther = chains[g][0].name; }
                    }
                    r.Verdict = Verdict(r.Region, r.OwnFraction, r.MaxOtherFraction);
                    results.Add(r);
                }
            }
            finally { Object.DestroyImmediate(tmp); }
            return results;
        }

        /// <summary>The region of each vertex: the nearest chain within RegionM (-1 = none).</summary>
        static int[] RegionOwners(List<Transform[]> chains, List<Vector3> rest)
        {
            var owner = new int[rest.Count];
            for (int i = 0; i < rest.Count; i++)
            {
                owner[i] = -1;
                float best = RegionM;
                for (int f = 0; f < chains.Count; f++)
                {
                    float d = Distance(rest[i], chains[f]);
                    if (d <= best) { best = d; owner[i] = f; }
                }
            }
            return owner;
        }

        /// <summary>Addendum 7 decision 4: each vertex's finger by mesh islands (see MeasureHand); vertex order as BakeAll's.</summary>
        static int[] IslandOwners(Transform hand, IList<SkinnedMeshRenderer> meshes, List<Transform[]> chains, List<Vector3> rest, PalmPlateSpec spec)
        {
            var owner = new int[rest.Count];
            for (int i = 0; i < owner.Length; i++) owner[i] = -1;
            int offset = 0;
            foreach (var smr in meshes)
            {
                var mesh = smr.sharedMesh;
                int n = mesh != null ? mesh.vertexCount : 0;
                var bones = smr.bones;
                var mats = smr.sharedMaterials;
                if (mesh != null && bones != null)
                {
                    var tris = new List<int>();
                    var glove = new HashSet<int>();
                    for (int sub = 0; sub < mesh.subMeshCount && sub < mats.Length; sub++)
                    {
                        if (mats[sub] == null || mats[sub].name.Replace(" (Instance)", "") != spec.material) continue;
                        var idx = mesh.GetIndices(sub);
                        tris.AddRange(idx);
                        foreach (int i in idx) glove.Add(i);
                    }
                    if (tris.Count > 0)
                    {
                        var tree = new bool[bones.Length];
                        for (int b = 0; b < bones.Length; b++) tree[b] = bones[b] != null && (bones[b] == hand || bones[b].IsChildOf(hand));
                        var bw = mesh.boneWeights;
                        var local = rest.GetRange(offset, n);
                        var mine = new List<int>();
                        foreach (int i in glove)
                        {
                            if (i >= bw.Length) continue;
                            var w = bw[i];
                            float t = (tree[w.boneIndex0] ? w.weight0 : 0f) + (tree[w.boneIndex1] ? w.weight1 : 0f) + (tree[w.boneIndex2] ? w.weight2 : 0f) + (tree[w.boneIndex3] ? w.weight3 : 0f);
                            if (t >= 0.5f) mine.Add(i);
                        }
                        var island = PalmPlate.Islands(local, tris, spec.weld_m);
                        int plate = PalmPlate.LargestIsland(local, island, mine);
                        var centroid = new Dictionary<int, Vector3>();
                        var size = new Dictionary<int, int>();
                        foreach (int i in mine)
                        {
                            if (island[i] < 0 || island[i] == plate) continue;
                            centroid[island[i]] = (centroid.TryGetValue(island[i], out var c) ? c : Vector3.zero) + local[i];
                            size[island[i]] = (size.TryGetValue(island[i], out int k) ? k : 0) + 1;
                        }
                        var finger = new Dictionary<int, int>();
                        foreach (var kv in centroid)
                        {
                            Vector3 c = kv.Value / size[kv.Key];
                            int best = -1;
                            float bd = float.PositiveInfinity;
                            for (int f = 0; f < chains.Count; f++) { float d = Distance(c, chains[f]); if (d < bd) { bd = d; best = f; } }
                            finger[kv.Key] = best;
                        }
                        foreach (int i in mine) if (island[i] >= 0 && finger.TryGetValue(island[i], out int f)) owner[offset + i] = f;
                    }
                }
                offset += n;
            }
            return owner;
        }

        /// <summary>The palm's normal: the mean finger direction crossed with the line through the two finger bases farthest apart (up if the
        /// hand has one chain).</summary>
        static Vector3 PalmNormal(Transform hand, List<Transform[]> chains)
        {
            Vector3 mean = Vector3.zero;
            foreach (var c in chains) mean += c[0].position - hand.position;
            float far = 0f;
            Vector3 spread = Vector3.zero;
            for (int a = 0; a < chains.Count; a++)
                for (int b = a + 1; b < chains.Count; b++)
                {
                    var d = chains[b][0].position - chains[a][0].position;
                    if (d.magnitude > far) { far = d.magnitude; spread = d; }
                }
            var n = Vector3.Cross(mean.normalized, spread.normalized);
            return n.sqrMagnitude > 1e-6f ? n.normalized : Vector3.up;
        }

        static string[] Names(Transform[] chain)
        {
            var n = new string[chain.Length];
            for (int i = 0; i < chain.Length; i++) n[i] = chain[i].name;
            return n;
        }

        static List<Vector3> BakeAll(IList<SkinnedMeshRenderer> meshes, Mesh tmp)
        {
            var all = new List<Vector3>();
            foreach (var smr in meshes)
            {
                smr.BakeMesh(tmp, true);
                var m = Matrix4x4.TRS(smr.transform.position, smr.transform.rotation, Vector3.one);
                foreach (var v in tmp.vertices) all.Add(m.MultiplyPoint3x4(v));
            }
            return all;
        }
    }
}
