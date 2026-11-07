using System.Collections.Generic;
using UnityEngine;

namespace WarehouseAvatar
{
    /// <summary>
    /// Makes a look's Humanoid Avatar agree with the look's own hierarchy above the hips. Humanoid IK works in the Avatar's
    /// normalised space, so an Avatar whose skeleton description has a different armature scale from the scene's puts
    /// every IK goal at that ratio of its offset from the root. Found 2026-11-08: in the Sunbox prefab the female
    /// armature is scaled 0.7312 but Female_Avatar.fbx's Avatar describes it at 1 (the male's describes the 0.7312), so
    /// the female hands stopped at 0.73 of every target. The third-party asset is not edited: the worker rebuilds the
    /// Avatar at Init from the look's own human description with the bones above the hips (not human bones) taken as
    /// they are in the scene. A look whose Avatar already agrees is left untouched.
    /// </summary>
    public static class HumanAvatarFix
    {
        public const float Tolerance = 1e-4f;

        /// <summary>The bones above the hips (hips' parent up to the Animator, exclusive) that differ from the Avatar's skeleton description.</summary>
        public static List<string> Mismatches(Animator animator)
        {
            var result = new List<string>();
            var skeleton = Index(animator.avatar.humanDescription.skeleton);
            foreach (var t in AboveHips(animator))
            {
                if (!skeleton.TryGetValue(t.name, out var b)) { result.Add($"{t.name} (not in the Avatar)"); continue; }
                if (Differs(b, t)) result.Add($"{t.name} scale {b.scale.x:0.####} -> {t.localScale.x:0.####}");
            }
            return result;
        }

        /// <summary>Rebuild and assign the Avatar if any bone above the hips differs; returns what was corrected (empty: untouched).</summary>
        public static List<string> Apply(Animator animator)
        {
            var changed = Mismatches(animator);
            if (changed.Count == 0) return changed;
            var hd = animator.avatar.humanDescription;
            var skeleton = hd.skeleton;
            var above = new Dictionary<string, Transform>();
            foreach (var t in AboveHips(animator)) above[t.name] = t;
            for (int i = 0; i < skeleton.Length; i++)
            {
                if (!above.TryGetValue(skeleton[i].name, out var t)) continue;
                skeleton[i].position = t.localPosition;
                skeleton[i].rotation = t.localRotation;
                skeleton[i].scale = t.localScale;
            }
            hd.skeleton = skeleton;
            // The importer records the root as "<model>(Clone)", also as its children's parent name (not settable from
            // script), and the builder checks those parents by name: the root carries that name while the Avatar is built.
            var go = animator.gameObject;
            string liveName = go.name;
            if (skeleton.Length > 0 && FindInHierarchy(animator.transform, skeleton[0].name) == null) go.name = skeleton[0].name;
            Avatar built;
            try { built = AvatarBuilder.BuildHumanAvatar(go, hd); }
            finally { go.name = liveName; }
            if (built == null || !built.isValid || !built.isHuman)
                throw new System.InvalidOperationException($"{animator.name}: the corrected Humanoid Avatar is not valid ({string.Join(", ", changed)})");
            built.name = animator.avatar.name + "_scene";
            animator.avatar = built;
            return changed;
        }

        static IEnumerable<Transform> AboveHips(Animator animator)
        {
            var hips = animator.GetBoneTransform(HumanBodyBones.Hips);
            if (hips == null) yield break;
            for (var t = hips.parent; t != null && t != animator.transform; t = t.parent) yield return t;
        }

        static bool Differs(SkeletonBone b, Transform t) =>
            (b.scale - t.localScale).sqrMagnitude > Tolerance * Tolerance ||
            (b.position - t.localPosition).sqrMagnitude > Tolerance * Tolerance ||
            Quaternion.Angle(b.rotation, t.localRotation) > 0.01f;

        static Dictionary<string, SkeletonBone> Index(SkeletonBone[] skeleton)
        {
            var d = new Dictionary<string, SkeletonBone>();
            foreach (var b in skeleton) if (!d.ContainsKey(b.name)) d[b.name] = b;
            return d;
        }

        static Transform FindInHierarchy(Transform root, string name)
        {
            if (root.name == name) return root;
            foreach (Transform c in root)
            {
                var f = FindInHierarchy(c, name);
                if (f != null) return f;
            }
            return null;
        }
    }
}
