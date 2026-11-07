using System;
using System.Collections.Generic;
using UnityEngine;
using UnityEngine.Rendering;

namespace WarehouseAvatar
{
    /// <summary>One look's row in the inventory (inventory.json of a look check).</summary>
    [Serializable]
    public class LookInventoryRow
    {
        public string id, family, role, source, asset;
        /// <summary>ok, not_installed, not_humanoid, no_arm_bones, load_failed.</summary>
        public string status;
        public bool installed, humanoid;
        public int human_bones_mapped;
        /// <summary>Finger bones mapped of the 30 Humanoid finger bones (3 per finger, 5 fingers, 2 hands).</summary>
        public int finger_bones_mapped;
        public string[] finger_bones_missing = new string[0];
        /// <summary>Each hand has a proximal bone for index, middle, ring and little, so the hand shapes can be posed.</summary>
        public bool hand_shapes_possible;
        /// <summary>Top of the model above the floor in the neutral pose: skinned and readable meshes (LookInventory.MeshExtentY), so
        /// non-readable accessories such as Sunbox hair and hats are not included.</summary>
        public float height_m;
        public string[] shaders = new string[0];
        public string[] material_problems = new string[0];
        /// <summary>Most error-shader magenta pixels in any render of this look (-1 = not rendered).</summary>
        public int magenta_pixels = -1;
        /// <summary>No material problem and no magenta pixel: the look renders in URP.</summary>
        public bool renders_in_urp;
        public string note = "";
    }

    public static class LookInventory
    {
        public const string ErrorShaderName = "Hidden/InternalErrorShader";
        static readonly HashSet<string> k_SrpLightModes = new HashSet<string> { "", "SRPDefaultUnlit", "UniversalForward", "UniversalForwardOnly", "UniversalGBuffer" };

        public static readonly HumanBodyBones[] FingerBones = BuildFingerBones();

        static HumanBodyBones[] BuildFingerBones()
        {
            var list = new List<HumanBodyBones>();
            for (var b = HumanBodyBones.LeftThumbProximal; b <= HumanBodyBones.RightLittleDistal; b++) list.Add(b);
            return list.ToArray();
        }

        public static void FillBones(LookInventoryRow row, IBoneSource bones, LookPoser poser)
        {
            int mapped = 0;
            for (var b = HumanBodyBones.Hips; b < HumanBodyBones.LastBone; b++)
                if (bones.Get(b) != null) mapped++;
            row.human_bones_mapped = mapped;
            var missing = new List<string>();
            foreach (var b in FingerBones)
                if (bones.Get(b) == null) missing.Add(b.ToString());
            row.finger_bones_mapped = FingerBones.Length - missing.Count;
            row.finger_bones_missing = missing.ToArray();
            row.hand_shapes_possible = poser != null && poser.HasArms && poser.HasFingers;
        }

        /// <summary>
        /// Lowest and highest world y of the active, enabled meshes as posed now: skinned meshes are baked (their bounds
        /// are loose), mesh renderers use their vertices. Mesh renderers whose mesh is not CPU-readable (e.g. the Sunbox
        /// hair and hat accessories) are left out rather than measured by their loose bounds. False when there is no mesh.
        /// </summary>
        public static bool MeshExtentY(GameObject root, out float minY, out float maxY)
        {
            minY = float.PositiveInfinity;
            maxY = float.NegativeInfinity;
            var baked = new Mesh();
            try
            {
                foreach (var r in root.GetComponentsInChildren<Renderer>(false))
                {
                    if (!r.enabled) continue;
                    Mesh mesh;
                    Matrix4x4 m;
                    if (r is SkinnedMeshRenderer smr)
                    {
                        if (smr.sharedMesh == null) continue;
                        smr.BakeMesh(baked, true);     // scale baked in: apply position and rotation only
                        mesh = baked;
                        m = Matrix4x4.TRS(r.transform.position, r.transform.rotation, Vector3.one);
                    }
                    else
                    {
                        var mf = r.GetComponent<MeshFilter>();
                        if (mf == null || mf.sharedMesh == null || !mf.sharedMesh.isReadable) continue;
                        mesh = mf.sharedMesh;
                        m = r.transform.localToWorldMatrix;
                    }
                    foreach (var v in mesh.vertices)
                    {
                        float y = m.MultiplyPoint3x4(v).y;
                        if (y < minY) minY = y;
                        if (y > maxY) maxY = y;
                    }
                }
            }
            finally
            {
                UnityEngine.Object.DestroyImmediate(baked);
            }
            return !float.IsInfinity(minY);
        }

        /// <summary>Top of the posed meshes above the floor (the root stands on it at y = root y), in metres.</summary>
        public static float Height(GameObject root) =>
            MeshExtentY(root, out _, out float top) ? (float)Math.Round(top - root.transform.position.y, 2) : 0f;

        /// <summary>
        /// Material problems that make an active renderer draw magenta or not at all under the active pipeline: a missing
        /// material, Unity's error shader, a shader unsupported on this GPU, or (with a render pipeline) a shader with no
        /// pass for it (e.g. Built-in Standard under URP). Inactive objects and disabled renderers are skipped. Shader
        /// names of active renderers go to shaders (sorted, distinct).
        /// </summary>
        public static List<string> MaterialProblems(GameObject root, out string[] shaders)
        {
            var problems = new List<string>();
            var names = new SortedSet<string>(StringComparer.Ordinal);
            bool srp = GraphicsSettings.currentRenderPipeline != null;
            foreach (var r in root.GetComponentsInChildren<Renderer>(false))
            {
                if (!r.enabled) continue;
                var mats = r.sharedMaterials;
                if (mats.Length == 0) problems.Add($"{r.name}: no material");
                for (int i = 0; i < mats.Length; i++)
                {
                    var m = mats[i];
                    if (m == null) { problems.Add($"{r.name} material {i}: missing"); continue; }
                    var s = m.shader;
                    if (s == null || s.name == ErrorShaderName) { problems.Add($"{r.name} '{m.name}': error shader"); continue; }
                    names.Add(s.name);
                    if (!s.isSupported) problems.Add($"{r.name} '{m.name}': shader '{s.name}' not supported on this GPU");
                    else if (srp && !HasSrpPass(m)) problems.Add($"{r.name} '{m.name}': shader '{s.name}' has no pass for the active render pipeline");
                }
            }
            shaders = new string[names.Count];
            names.CopyTo(shaders);
            return problems;
        }

        static bool HasSrpPass(Material m)
        {
            var tag = new ShaderTagId("LightMode");
            for (int i = 0; i < m.passCount; i++)
                if (k_SrpLightModes.Contains(m.shader.FindPassTagValue(i, tag).name)) return true;
            return false;
        }

        /// <summary>Pixels of Unity's error-shader magenta (R and B >= 255 - tolerance, G <= tolerance).</summary>
        public static int MagentaPixels(Color32[] pixels, int tolerance)
        {
            int n = 0, hi = 255 - tolerance;
            foreach (var p in pixels)
                if (p.r >= hi && p.b >= hi && p.g <= tolerance) n++;
            return n;
        }
    }
}
