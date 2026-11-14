using System;
using System.Collections.Generic;
using System.Linq;
using UnityEngine;

namespace WarehouseAvatar
{
    /// <summary>looks_ab.json island_hands (experiments_ab.md section 12 addendum 9): a look whose hands are bound by their mesh islands.</summary>
    [Serializable]
    public class IslandHandsSpec
    {
        public string look, material;
        public string[] hands = new string[0];
        public float weld_m, contact_m, blend_segments;
    }

    /// <summary>
    /// Addendum 9 (declared before it was built): bind a hand's glove by its mesh islands. The palm plate island (largest box) goes 100 % to
    /// the hand bone; the other islands are grouped into fingers by contact and matched one to one with the hand's chains (smallest total
    /// centroid-to-chain distance); each finger is weighted only along its own chain: a segment's bone, a linear blend within blend_segments
    /// of an interior joint, the tip on the distal bone, the part before the first joint on the proximal bone. Mesh space throughout.
    /// </summary>
    public static class IslandHands
    {
        public sealed class HandBinding
        {
            public string Hand = "";
            public int Plate;
            public readonly List<string> Fingers = new List<string>();
            public string Problem = "";
        }

        /// <summary>Weights along a chain of joints p (mesh space) for a point at q: (joint index, weight) pairs, 1 or 2 of them; joints
        /// 0..p.Length-2 drive the segments (the last joint is the end).</summary>
        public static List<(int joint, float weight)> ChainWeights(Vector3 q, IList<Vector3> p, float blend)
        {
            int segs = p.Count - 1;
            int bestK = 0;
            float bestS = 0f, bestD = float.PositiveInfinity, rawS = 0f;
            for (int k = 0; k < segs; k++)
            {
                Vector3 a = p[k], ab = p[k + 1] - p[k];
                float raw = ab.sqrMagnitude > 1e-12f ? Vector3.Dot(q - a, ab) / ab.sqrMagnitude : 0f;
                float s = Mathf.Clamp01(raw);
                float d = Vector3.Distance(q, a + s * ab);
                if (d < bestD) { bestD = d; bestK = k; bestS = s; rawS = raw; }
            }
            var w = new List<(int, float)>();
            int last = segs - 1;
            if (bestK == 0 && rawS < 0f) { w.Add((0, 1f)); return w; }              // before the first joint: the proximal bone
            if (bestK == last && rawS > 1f) { w.Add((last, 1f)); return w; }        // beyond the end joint: the distal bone
            if (bestK >= 1 && bestS < blend)
            {
                float own = 0.5f + bestS / (2f * blend);
                w.Add((bestK, own));
                w.Add((bestK - 1, 1f - own));
            }
            else if (bestK + 1 <= last && bestS > 1f - blend)
            {
                float own = 0.5f + (1f - bestS) / (2f * blend);
                w.Add((bestK, own));
                w.Add((bestK + 1, 1f - own));
            }
            else w.Add((bestK, 1f));
            return w;
        }

        /// <summary>One-to-one assignment of groups to chains (groups.Count &lt;= chains.Count) minimising the summed cost; the chain of each group.</summary>
        public static int[] Match(float[,] cost)
        {
            int g = cost.GetLength(0), c = cost.GetLength(1);
            var best = new int[g];
            float bestSum = float.PositiveInfinity;
            var cur = new int[g];
            var used = new bool[c];
            void Go(int i, float sum)
            {
                if (sum >= bestSum) return;
                if (i == g) { bestSum = sum; Array.Copy(cur, best, g); return; }
                for (int k = 0; k < c; k++)
                {
                    if (used[k]) continue;
                    used[k] = true; cur[i] = k;
                    Go(i + 1, sum + cost[i, k]);
                    used[k] = false;
                }
            }
            Go(0, 0f);
            return best;
        }

        /// <summary>Addendum 10: true when some vertex of a lies within d of some vertex of b.</summary>
        public static bool Touch(List<Vector3> a, List<Vector3> b, float d)
        {
            float d2 = d * d;
            foreach (var p in a) foreach (var q in b) if ((p - q).sqrMagnitude <= d2) return true;
            return false;
        }

        /// <summary>Distance from q to the polyline p.</summary>
        static float ChainDistance(Vector3 q, IList<Vector3> p)
        {
            float best = float.PositiveInfinity;
            for (int k = 0; k + 1 < p.Count; k++)
            {
                Vector3 a = p[k], ab = p[k + 1] - p[k];
                float s = ab.sqrMagnitude > 1e-12f ? Mathf.Clamp01(Vector3.Dot(q - a, ab) / ab.sqrMagnitude) : 0f;
                best = Mathf.Min(best, Vector3.Distance(q, a + s * ab));
            }
            return best;
        }

        /// <summary>The weights of a hand's glove after binding: per hand, the glove vertices on this hand, those entirely on the hand bone,
        /// those on one finger chain only, and those whose weights touch more than one part (hand or chains): must be 0.</summary>
        public static List<(string hand, int vertices, int onHand, int oneChain, int crossed, int chainsUsed, int chains)> Audit(Mesh mesh, Transform[] bones, string[] materialNames, IslandHandsSpec spec)
        {
            var list = new List<(string, int, int, int, int, int, int)>();
            if (mesh == null || bones == null || spec == null) return list;
            var glove = new HashSet<int>();
            for (int sub = 0; sub < mesh.subMeshCount && sub < materialNames.Length; sub++)
                if ((materialNames[sub] ?? "").Replace(" (Instance)", "") == spec.material) foreach (int i in mesh.GetIndices(sub)) glove.Add(i);
            var bw = mesh.boneWeights;
            foreach (var handName in spec.hands)
            {
                int hi = Array.FindIndex(bones, b => b != null && b.name == handName);
                if (hi < 0) continue;
                var hand = bones[hi];
                // the part of each bone: -1 = the hand bone, k = the k-th chain under the hand, -2 = elsewhere
                var part = new int[bones.Length];
                for (int b = 0; b < bones.Length; b++) part[b] = -2;
                part[hi] = -1;
                int k = 0;
                foreach (Transform child in hand)
                {
                    for (var t = child; t != null; t = t.childCount > 0 ? t.GetChild(0) : null) { int j = Array.IndexOf(bones, t); if (j >= 0) part[j] = k; }
                    k++;
                }
                int n = 0, onHand = 0, one = 0, crossed = 0;
                var used = new HashSet<int>();
                foreach (int i in glove)
                {
                    if (i >= bw.Length) continue;
                    var w = bw[i];
                    var parts = new HashSet<int>();
                    foreach (var (bi, wt) in new[] { (w.boneIndex0, w.weight0), (w.boneIndex1, w.weight1), (w.boneIndex2, w.weight2), (w.boneIndex3, w.weight3) })
                        if (wt > 1e-6f) parts.Add(part[bi]);
                    if (!parts.Any(p => p != -2)) continue;          // the other hand's glove
                    n++;
                    if (parts.Count == 1 && parts.First() == -1) onHand++;
                    else if (parts.Count == 1 && parts.First() >= 0) { one++; used.Add(parts.First()); }
                    else crossed++;
                }
                list.Add((handName, n, onHand, one, crossed, used.Count, k));
            }
            return list;
        }

        /// <summary>
        /// Bind the hands of one skinned mesh by islands (returns one entry per hand; the mesh's bone weights are replaced for the glove
        /// vertices of each hand only). meshFromWorld maps world positions (bones at the bind pose) into mesh space; scale = world metres per
        /// mesh unit (the distances of the spec are in metres).
        /// </summary>
        public static List<HandBinding> Bind(Mesh mesh, Transform[] bones, string[] materialNames, IslandHandsSpec spec, Matrix4x4 meshFromWorld, float scale)
        {
            var result = new List<HandBinding>();
            if (mesh == null || bones == null || spec == null) return result;
            var tris = new List<int>();
            var glove = new HashSet<int>();
            for (int sub = 0; sub < mesh.subMeshCount && sub < materialNames.Length; sub++)
            {
                if ((materialNames[sub] ?? "").Replace(" (Instance)", "") != spec.material) continue;
                var idx = mesh.GetIndices(sub);
                tris.AddRange(idx);
                foreach (int i in idx) glove.Add(i);
            }
            if (tris.Count == 0) return result;
            var verts = mesh.vertices;
            var bw = mesh.boneWeights;
            float unit = scale > 1e-9f ? 1f / scale : 1f;
            var island = PalmPlate.Islands(verts, tris, spec.weld_m * unit);
            Vector3 M(Transform t) => meshFromWorld.MultiplyPoint3x4(t.position);
            foreach (var handName in spec.hands)
            {
                var hb = new HandBinding { Hand = handName };
                result.Add(hb);
                int hi = Array.FindIndex(bones, b => b != null && b.name == handName);
                if (hi < 0) { hb.Problem = "hand bone not among the mesh's bones"; continue; }
                var hand = bones[hi];
                var tree = bones.Select(b => b != null && (b == hand || b.IsChildOf(hand))).ToArray();
                var mine = glove.Where(i => i < bw.Length && (tree[bw[i].boneIndex0] ? bw[i].weight0 : 0f) + (tree[bw[i].boneIndex1] ? bw[i].weight1 : 0f)
                                                         + (tree[bw[i].boneIndex2] ? bw[i].weight2 : 0f) + (tree[bw[i].boneIndex3] ? bw[i].weight3 : 0f) >= 0.5f).ToList();
                int plate = PalmPlate.LargestIsland(verts, island, mine);
                if (plate < 0) { hb.Problem = "no plate island"; continue; }
                // finger groups: the other islands, joined when their closest vertices lie within contact_m (addendum 10: not their
                // bounding boxes, which joined a diagonal thumb with the index finger)
                var members = new Dictionary<int, List<Vector3>>();
                foreach (int i in mine)
                {
                    if (island[i] < 0 || island[i] == plate) continue;
                    if (!members.TryGetValue(island[i], out var m)) members[island[i]] = m = new List<Vector3>();
                    m.Add(verts[i]);
                }
                var ids = members.Keys.OrderBy(x => x).ToList();
                var parent = ids.ToDictionary(x => x, x => x);
                int Find(int x) { while (parent[x] != x) x = parent[x] = parent[parent[x]]; return x; }
                float contact = spec.contact_m * unit;
                for (int a = 0; a < ids.Count; a++)
                    for (int c = a + 1; c < ids.Count; c++)
                        if (Touch(members[ids[a]], members[ids[c]], contact)) parent[Find(ids[a])] = Find(ids[c]);
                var groups = ids.GroupBy(Find).Select(g => new HashSet<int>(g)).ToList();
                var chains = new List<Transform[]>();
                foreach (Transform child in hand)
                {
                    var chain = new List<Transform>();
                    for (var t = child; t != null; t = t.childCount > 0 ? t.GetChild(0) : null) chain.Add(t);
                    if (chain.Count >= 2) chains.Add(chain.ToArray());
                }
                if (groups.Count == 0 || chains.Count == 0) { hb.Problem = $"{groups.Count} finger groups, {chains.Count} chains"; continue; }
                var joints = chains.Select(ch => ch.Select(M).ToList()).ToList();
                var centroid = groups.Select(g =>
                {
                    Vector3 s = Vector3.zero; int n = 0;
                    foreach (int i in mine) if (island[i] >= 0 && g.Contains(island[i])) { s += verts[i]; n++; }
                    return n > 0 ? s / n : Vector3.zero;
                }).ToList();
                int[] chainOf;
                if (groups.Count <= chains.Count)
                {
                    var cost = new float[groups.Count, chains.Count];
                    for (int g = 0; g < groups.Count; g++) for (int c = 0; c < chains.Count; c++) cost[g, c] = ChainDistance(centroid[g], joints[c]);
                    chainOf = Match(cost);
                }
                else
                {
                    chainOf = centroid.Select(cg => Enumerable.Range(0, chains.Count).OrderBy(c => ChainDistance(cg, joints[c])).First()).ToArray();
                    hb.Problem = $"{groups.Count} finger groups for {chains.Count} chains: nearest chain used";
                }
                // the weights
                foreach (int i in mine)
                {
                    if (island[i] < 0) continue;
                    if (island[i] == plate) { bw[i] = new BoneWeight { boneIndex0 = hi, weight0 = 1f }; hb.Plate++; continue; }
                }
                for (int g = 0; g < groups.Count; g++)
                {
                    var ch = chains[chainOf[g]];
                    var jointBone = ch.Take(ch.Length - 1).Select(t => Array.IndexOf(bones, t)).ToArray();
                    if (jointBone.Any(x => x < 0)) { hb.Problem += $" {ch[0].name}: a joint is not among the mesh's bones;"; continue; }
                    int n = 0;
                    foreach (int i in mine)
                    {
                        if (island[i] < 0 || !groups[g].Contains(island[i])) continue;
                        var w = ChainWeights(verts[i], joints[chainOf[g]], spec.blend_segments);
                        var nb = new BoneWeight { boneIndex0 = jointBone[w[0].joint], weight0 = w[0].weight };
                        if (w.Count > 1) { nb.boneIndex1 = jointBone[w[1].joint]; nb.weight1 = w[1].weight; }
                        bw[i] = nb;
                        n++;
                    }
                    hb.Fingers.Add($"{ch[0].name} {n}");
                }
            }
            mesh.boneWeights = bw;
            return result;
        }
    }
}
