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
        /// <summary>Addendum 11: move each finger chain's joints onto its finger group's axis before binding.</summary>
        public bool move_joints;
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

        /// <summary>Addendum 11: one hand's island analysis (in the space of the vertices given): the plate, the finger groups (island ids),
        /// each group's axis (knuckle and tip end) and its chain by the anatomical rule.</summary>
        public sealed class HandAnalysis
        {
            public int Plate = -1;
            public Vector3 PlateCentre;
            public readonly List<HashSet<int>> Groups = new List<HashSet<int>>();
            public readonly List<Vector3> Knuckle = new List<Vector3>(), Tip = new List<Vector3>();
            /// <summary>Per group: the index of its chain in Chains.</summary>
            public int[] ChainOf = new int[0];
            public List<Transform[]> Chains = new List<Transform[]>();
            public string Problem = "";
            public bool Ok => Problem.Length == 0;
        }

        /// <summary>The chains under a hand bone (each child followed down its first children; at least two joints).</summary>
        public static List<Transform[]> Chains(Transform hand)
        {
            var chains = new List<Transform[]>();
            foreach (Transform child in hand)
            {
                var chain = new List<Transform>();
                for (var t = child; t != null; t = t.childCount > 0 ? t.GetChild(0) : null) chain.Add(t);
                if (chain.Count >= 2) chains.Add(chain.ToArray());
            }
            return chains;
        }

        static readonly string[] k_Anatomy = { "Thumb", "Index", "Middle", "Ring" };

        /// <summary>
        /// Addendum 11 (declared before it was built): the plate (largest box island among mine), the finger groups (islands joined when
        /// their closest vertices lie within contact), each group's PCA axis with its knuckle end nearest the plate's centre, and the chain
        /// of each group by the anatomical rule: the thumb deviates most from the hand's forward axis (hand bone to plate centre); index,
        /// middle and ring follow by their knuckle's distance from the thumb's knuckle across the palm (the plate's longest axis made
        /// perpendicular to forward). Chains by their Mixamo names. Refused unless there is exactly one group per named chain.
        /// </summary>
        public static HandAnalysis Analyse(IList<Vector3> verts, int[] island, IList<int> mine, Vector3 handPos, List<Transform[]> chains, float contact)
        {
            var a = new HandAnalysis { Chains = chains };
            a.Plate = PalmPlate.LargestIsland(verts, island, mine);
            if (a.Plate < 0) { a.Problem = "no plate island"; return a; }
            var platePts = mine.Where(i => island[i] == a.Plate).Select(i => verts[i]).ToList();
            var plateShape = PalmPlate.Shape(platePts);
            a.PlateCentre = plateShape.Centre;
            var members = new Dictionary<int, List<Vector3>>();
            foreach (int i in mine)
            {
                if (island[i] < 0 || island[i] == a.Plate) continue;
                if (!members.TryGetValue(island[i], out var m)) members[island[i]] = m = new List<Vector3>();
                m.Add(verts[i]);
            }
            var ids = members.Keys.OrderBy(x => x).ToList();
            var parent = ids.ToDictionary(x => x, x => x);
            int Find(int x) { while (parent[x] != x) x = parent[x] = parent[parent[x]]; return x; }
            for (int p = 0; p < ids.Count; p++)
                for (int q = p + 1; q < ids.Count; q++)
                    if (Touch(members[ids[p]], members[ids[q]], contact)) parent[Find(ids[p])] = Find(ids[q]);
            foreach (var g in ids.GroupBy(Find)) a.Groups.Add(new HashSet<int>(g));
            foreach (var g in a.Groups)
            {
                var pts = g.SelectMany(id => members[id]).ToList();
                var sh = PalmPlate.Shape(pts);
                float lo = float.MaxValue, hi = float.MinValue;
                foreach (var p in pts) { float d = Vector3.Dot(p - sh.Centre, sh.Long); lo = Mathf.Min(lo, d); hi = Mathf.Max(hi, d); }
                Vector3 e1 = sh.Centre + sh.Long * lo, e2 = sh.Centre + sh.Long * hi;
                bool firstNear = Vector3.Distance(e1, a.PlateCentre) <= Vector3.Distance(e2, a.PlateCentre);
                a.Knuckle.Add(firstNear ? e1 : e2);
                a.Tip.Add(firstNear ? e2 : e1);
            }
            var named = k_Anatomy.Select(n => chains.FindIndex(c => c[0].name.Contains(n))).ToArray();
            if (named.Any(x => x < 0)) { a.Problem = "the hand lacks a Thumb, Index, Middle or Ring chain"; return a; }
            if (a.Groups.Count != k_Anatomy.Length) { a.Problem = $"{a.Groups.Count} finger groups for {k_Anatomy.Length} named chains: refused"; return a; }
            Vector3 forward = (a.PlateCentre - handPos).normalized;
            int thumb = Enumerable.Range(0, a.Groups.Count).OrderByDescending(g => Vector3.Angle(a.Tip[g] - a.Knuckle[g], forward)).First();
            Vector3 across = Vector3.ProjectOnPlane(plateShape.Long, forward).normalized;
            var rest = Enumerable.Range(0, a.Groups.Count).Where(g => g != thumb)
                                 .OrderBy(g => Mathf.Abs(Vector3.Dot(a.Knuckle[g] - a.Knuckle[thumb], across))).ToList();
            a.ChainOf = new int[a.Groups.Count];
            a.ChainOf[thumb] = named[0];
            for (int k = 0; k < rest.Count; k++) a.ChainOf[rest[k]] = named[k + 1];
            return a;
        }

        /// <summary>The glove of one hand of a mesh: its triangles' islands (welded within weld) and the vertices mostly (>= 0.5) on that hand
        /// bone or below it.</summary>
        static bool Glove(Mesh mesh, Transform[] bones, string[] materialNames, IslandHandsSpec spec, string handName, float unit,
                          out Vector3[] verts, out int[] island, out List<int> mine, out int handIndex)
        {
            verts = null; island = null; mine = null;
            handIndex = Array.FindIndex(bones, b => b != null && b.name == handName);
            if (mesh == null || handIndex < 0) return false;
            var tris = new List<int>();
            var glove = new HashSet<int>();
            for (int sub = 0; sub < mesh.subMeshCount && sub < materialNames.Length; sub++)
            {
                if ((materialNames[sub] ?? "").Replace(" (Instance)", "") != spec.material) continue;
                var idx = mesh.GetIndices(sub);
                tris.AddRange(idx);
                foreach (int i in idx) glove.Add(i);
            }
            if (tris.Count == 0) return false;
            verts = mesh.vertices;
            island = PalmPlate.Islands(verts, tris, spec.weld_m * unit);
            var hand = bones[handIndex];
            var tree = bones.Select(b => b != null && (b == hand || b.IsChildOf(hand))).ToArray();
            var bw = mesh.boneWeights;
            mine = glove.Where(i => i < bw.Length && (tree[bw[i].boneIndex0] ? bw[i].weight0 : 0f) + (tree[bw[i].boneIndex1] ? bw[i].weight1 : 0f)
                                                  + (tree[bw[i].boneIndex2] ? bw[i].weight2 : 0f) + (tree[bw[i].boneIndex3] ? bw[i].weight3 : 0f) >= 0.5f).OrderBy(i => i).ToList();
            return true;
        }

        /// <summary>
        /// Addendum 11: place each finger chain's joints on its group's axis (j0 at the knuckle end, the last joint at the tip end, the others
        /// evenly between), base to tip, by position only. Returns one line per moved joint ("name: old -> new cm"); refused hands are listed
        /// as problems and left alone. The caller recomputes the bind poses of the moved bones.
        /// </summary>
        public static List<string> AlignChains(Mesh mesh, Transform[] bones, string[] materialNames, IslandHandsSpec spec, Matrix4x4 meshFromWorld, Matrix4x4 worldFromMesh,
                                               float scale, List<Transform> moved)
        {
            var log = new List<string>();
            float unit = scale > 1e-9f ? 1f / scale : 1f;
            foreach (var handName in spec.hands)
            {
                if (!Glove(mesh, bones, materialNames, spec, handName, unit, out var verts, out var island, out var mine, out int hi)) { log.Add($"{handName}: no glove"); continue; }
                var hand = bones[hi];
                var a = Analyse(verts, island, mine, meshFromWorld.MultiplyPoint3x4(hand.position), Chains(hand), spec.contact_m * unit);
                if (!a.Ok) { log.Add($"{handName}: PROBLEM {a.Problem}"); continue; }
                for (int g = 0; g < a.Groups.Count; g++)
                {
                    var ch = a.Chains[a.ChainOf[g]];
                    var original = ch.Select(t => t.position).ToArray();
                    for (int k = 0; k < ch.Length; k++)
                    {
                        Vector3 target = worldFromMesh.MultiplyPoint3x4(Vector3.Lerp(a.Knuckle[g], a.Tip[g], k / (float)(ch.Length - 1)));
                        Vector3 old = original[k];
                        ch[k].position = target;
                        moved.Add(ch[k]);
                        log.Add($"{ch[k].name}: moved {(Vector3.Distance(old, target) * 100f).ToString("0.0", System.Globalization.CultureInfo.InvariantCulture)} cm");
                    }
                }
            }
            return log;
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
        /// Bind the hands of one skinned mesh by islands (addenda 9 to 11): the plate 100 % to the hand bone; each finger group only along
        /// the chain the anatomical rule gives it (Analyse). The mesh's bone weights are replaced for the glove vertices of each analysed hand
        /// only; a refused hand is reported and left alone. meshFromWorld maps world positions (bones at the import pose) into mesh space;
        /// scale = world metres per mesh unit.
        /// </summary>
        public static List<HandBinding> Bind(Mesh mesh, Transform[] bones, string[] materialNames, IslandHandsSpec spec, Matrix4x4 meshFromWorld, float scale)
        {
            var result = new List<HandBinding>();
            if (mesh == null || bones == null || spec == null) return result;
            float unit = scale > 1e-9f ? 1f / scale : 1f;
            var bw = mesh.boneWeights;
            Vector3 M(Transform t) => meshFromWorld.MultiplyPoint3x4(t.position);
            foreach (var handName in spec.hands)
            {
                var hb = new HandBinding { Hand = handName };
                result.Add(hb);
                if (!Glove(mesh, bones, materialNames, spec, handName, unit, out var verts, out var island, out var mine, out int hi)) { hb.Problem = "no glove or hand bone"; continue; }
                var a = Analyse(verts, island, mine, M(bones[hi]), Chains(bones[hi]), spec.contact_m * unit);
                if (!a.Ok) { hb.Problem = a.Problem; continue; }
                foreach (int i in mine)
                    if (island[i] == a.Plate) { bw[i] = new BoneWeight { boneIndex0 = hi, weight0 = 1f }; hb.Plate++; }
                for (int g = 0; g < a.Groups.Count; g++)
                {
                    var ch = a.Chains[a.ChainOf[g]];
                    var joints = ch.Select(M).ToList();
                    var jointBone = ch.Take(ch.Length - 1).Select(t => Array.IndexOf(bones, t)).ToArray();
                    if (jointBone.Any(x => x < 0)) { hb.Problem += $" {ch[0].name}: a joint is not among the mesh's bones;"; continue; }
                    int n = 0;
                    foreach (int i in mine)
                    {
                        if (island[i] < 0 || !a.Groups[g].Contains(island[i])) continue;
                        var w = ChainWeights(verts[i], joints, spec.blend_segments);
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
