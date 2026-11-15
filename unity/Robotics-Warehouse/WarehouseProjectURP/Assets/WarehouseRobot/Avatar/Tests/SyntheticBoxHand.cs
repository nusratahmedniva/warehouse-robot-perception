using System.Collections.Generic;
using UnityEngine;

namespace WarehouseAvatar.Tests
{
    /// <summary>
    /// A synthetic Boxo-like right hand (Avatar/Config/experiments_ab.md section 12 addenda 9 to 11): a palm plate box, three fingers along +x
    /// (index z +0.05, middle 0, ring -0.05), each a box with a touching tip box, and a thumb at 45 deg on the index side; one sub-mesh of
    /// material "glovemat", every vertex on the index chain's first bone (the auto-rigger's spread). The Mixamo-named chains are placed as the
    /// auto-rigger placed Boxo's: bunched near the middle, the thumb chain on the wrong side. Hand at the origin; mesh space = world.
    /// </summary>
    public sealed class SyntheticBoxHand
    {
        public Transform Hand;
        public Transform[] Bones;
        public Mesh Mesh;
        public readonly Dictionary<string, List<int>> Finger = new Dictionary<string, List<int>>();
        public int PlateVertices;
        public readonly List<Object> Made = new List<Object>();

        public static readonly string[] Names = { "Thumb", "Index", "Middle", "Ring" };

        static void Box(List<Vector3> v, List<int> t, Vector3 c, Vector3 size, Quaternion q, int n)
        {
            for (int axis = 0; axis < 3; axis++)
                foreach (float side in new[] { -0.5f, 0.5f })
                {
                    int a1 = (axis + 1) % 3, a2 = (axis + 2) % 3, start = v.Count;
                    for (int i = 0; i <= n; i++)
                        for (int j = 0; j <= n; j++)
                        {
                            var p = Vector3.zero;
                            p[axis] = side * size[axis];
                            p[a1] = (i / (float)n - 0.5f) * size[a1];
                            p[a2] = (j / (float)n - 0.5f) * size[a2];
                            v.Add(c + q * p);
                        }
                    for (int i = 0; i < n; i++)
                        for (int j = 0; j < n; j++) { int k = start + i * (n + 1) + j; t.AddRange(new[] { k, k + 1, k + n + 1, k + 1, k + n + 2, k + n + 1 }); }
                }
        }

        public SyntheticBoxHand()
        {
            Hand = new GameObject("mixamorig:RightHand").transform;
            Made.Add(Hand.gameObject);
            var bones = new List<Transform> { Hand };
            // the auto-rigger's chains: bunched within 1 cm of the middle; the thumb chain on the ring side (-z)
            var chainZ = new Dictionary<string, float> { { "Thumb", -0.02f }, { "Index", 0.01f }, { "Middle", 0f }, { "Ring", -0.01f } };
            foreach (var name in Names)
            {
                Transform parent = Hand;
                for (int j = 1; j <= 4; j++)
                {
                    var b = new GameObject($"mixamorig:RightHand{name}{j}").transform;
                    b.SetParent(parent, false);
                    b.position = new Vector3(0.08f + 0.025f * (j - 1), 0f, chainZ[name]);
                    bones.Add(b);
                    parent = b;
                }
            }
            Bones = bones.ToArray();
            var v = new List<Vector3>();
            var t = new List<int>();
            Box(v, t, new Vector3(0.03f, 0f, 0f), new Vector3(0.08f, 0.03f, 0.16f), Quaternion.identity, 3);
            PlateVertices = v.Count;
            foreach (var (name, z) in new[] { ("Index", 0.05f), ("Middle", 0f), ("Ring", -0.05f) })
            {
                int s = v.Count;
                Box(v, t, new Vector3(0.12f, 0f, z), new Vector3(0.09f, 0.02f, 0.02f), Quaternion.identity, 3);
                Box(v, t, new Vector3(0.17f, 0f, z), new Vector3(0.015f, 0.015f, 0.015f), Quaternion.identity, 2);
                Finger[name] = Range(s, v.Count);
            }
            {
                int s = v.Count;
                var q = Quaternion.AngleAxis(-45f, Vector3.up);                    // +x turned toward +z
                Vector3 dir = q * Vector3.right, start = new Vector3(0.04f, 0f, 0.09f);
                Box(v, t, start + dir * 0.035f, new Vector3(0.07f, 0.02f, 0.02f), q, 3);
                Box(v, t, start + dir * 0.075f, new Vector3(0.015f, 0.015f, 0.015f), q, 2);
                Finger["Thumb"] = Range(s, v.Count);
            }
            Mesh = new Mesh();
            Made.Add(Mesh);
            Mesh.SetVertices(v);
            Mesh.SetTriangles(t, 0);
            var w = new BoneWeight[v.Count];
            for (int i = 0; i < w.Length; i++) w[i] = new BoneWeight { boneIndex0 = 5, weight0 = 1f };   // Index1
            Mesh.boneWeights = w;
        }

        static List<int> Range(int a, int b) { var l = new List<int>(); for (int i = a; i < b; i++) l.Add(i); return l; }

        public Transform[] Chain(string name)
        {
            var c = new List<Transform>();
            foreach (var b in Bones) if (b.name.StartsWith("mixamorig:RightHand" + name)) c.Add(b);
            return c.ToArray();
        }

        public void Destroy() { foreach (var o in Made) if (o != null) Object.DestroyImmediate(o); }
    }
}
