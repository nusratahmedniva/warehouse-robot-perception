using System;
using System.Collections.Generic;
using System.Linq;
using System.Reflection;
using UnityEngine;

namespace WarehouseAvatar
{
    /// <summary>
    /// Customises an instance of the Sunbox avatar prefab (Stylized Customizable Avatars, Asset Store, git-ignored) as a
    /// look of worker_v4.json / look_check.json says: gender, skin, hair, facial hair and the free pack's clothing items.
    /// The pack is reached by reflection only (its public fields and methods), so the project compiles without it.
    /// Used by the Edit-mode look check (LookCheckMenu) and by WorkerV4 at Play.
    /// </summary>
    public static class SunboxLookApplier
    {
        public const string Component = "Sunbox.Avatars.AvatarCustomization";

        /// <summary>Apply the look; returns the active base's Animator and a one-line description of what was chosen.</summary>
        public static Animator Apply(GameObject inst, SunboxLook s, out string description)
        {
            try { return ApplyInternal(inst, s, out description); }
            catch (TargetInvocationException e) when (e.InnerException != null)
            {
                var broken = inst.GetComponentsInChildren<MonoBehaviour>(true)
                    .Where(m => m != null && m.GetType().FullName == "Sunbox.Avatars.UClothingItem" && m.GetType().GetField("ClothingItem").GetValue(m) as UnityEngine.Object == null)
                    .Select(m => m.gameObject.name).ToList();
                throw new InvalidOperationException($"Sunbox: {e.InnerException.GetType().Name}: {e.InnerException.Message}" +
                                                    (broken.Count > 0 ? $" (clothing objects without their item: {string.Join(", ", broken)})" : "") +
                                                    "\n" + e.InnerException.StackTrace, e.InnerException);
            }
        }

        /// <summary>
        /// The free pack's prefab carries clothing objects whose item asset belongs to the paid pack (missing here). At Play
        /// those references are null and the pack's own hair update throws on them; the pack destroys every clothing object
        /// it does not equip anyway, so they are removed first. Returns how many.
        /// </summary>
        public static int RemoveOrphanClothing(GameObject inst)
        {
            int n = 0;
            foreach (var m in inst.GetComponentsInChildren<MonoBehaviour>(true))
            {
                if (m == null || m.GetType().FullName != "Sunbox.Avatars.UClothingItem") continue;
                if (m.GetType().GetField("ClothingItem")?.GetValue(m) as UnityEngine.Object != null) continue;
                UnityEngine.Object.DestroyImmediate(m.gameObject);
                n++;
            }
            return n;
        }

        static Animator ApplyInternal(GameObject inst, SunboxLook s, out string description)
        {
            int orphans = RemoveOrphanClothing(inst);
            var comp = inst.GetComponentsInChildren<MonoBehaviour>(true).FirstOrDefault(m => m != null && m.GetType().FullName == Component)
                       ?? throw new InvalidOperationException($"no {Component} on {inst.name}");
            var t = comp.GetType();
            FieldInfo Field(string n) => t.GetField(n) ?? throw new MissingFieldException(Component, n);
            MethodInfo Method(string n) => t.GetMethod(n) ?? throw new MissingMethodException(Component, n);

            var gender = Enum.Parse(Field("CurrentGender").FieldType, s.gender);
            Field("SkinMaterialIndex").SetValue(comp, s.skin);
            Field("HairStyleIndex").SetValue(comp, s.hair_style);
            Field("HairMaterialIndex").SetValue(comp, s.hair_material);
            Field("FacialHairStyleIndex").SetValue(comp, s.facial_hair_style);
            Method("SetGender").Invoke(comp, new[] { gender, (object)true });

            var refs = Field("AvatarReferences").GetValue(comp) ?? throw new InvalidOperationException("AvatarReferences not set on the Sunbox prefab");
            var items = (Array)refs.GetType().GetField("AvailableClothingItems").GetValue(refs);
            var chosen = new List<string>();
            foreach (var c in s.clothing ?? new SunboxClothing[0])
            {
                object item = items.Cast<object>().FirstOrDefault(i => i != null && (string)i.GetType().GetField("Name").GetValue(i) == c.name)
                              ?? throw new ArgumentException($"Sunbox clothing item '{c.name}' is not in this pack");
                var variations = (Material[])item.GetType().GetField("Variations").GetValue(item);
                if (c.variation < 0 || c.variation >= variations.Length)
                    throw new ArgumentException($"Sunbox clothing item '{c.name}' has {variations.Length} variations; {c.variation} requested");
                Method("AttachClothingItem").Invoke(comp, new[] { item, (object)c.variation });
                chosen.Add($"{c.name} [{(variations[c.variation] != null ? variations[c.variation].name : "none")}]");
            }
            Method("UpdateCustomization").Invoke(comp, null);

            var skins = (Material[])refs.GetType().GetField(s.gender == "Male" ? "MaleSkinMaterials" : "FemaleSkinMaterials").GetValue(refs);
            var hairs = (Array)refs.GetType().GetField("HairItems").GetValue(refs);
            string skin = s.skin >= 0 && s.skin < skins.Length && skins[s.skin] != null ? skins[s.skin].name : "out of range";
            string hair = s.hair_style >= 0 && s.hair_style < hairs.Length ? (string)hairs.GetValue(s.hair_style).GetType().GetField("Name").GetValue(hairs.GetValue(s.hair_style)) : "out of range";
            description = $"{s.gender}, skin {skin}, hair {hair}; " + string.Join(", ", chosen) + "." +
                          (orphans > 0 ? $" {orphans} clothing objects of the paid pack removed." : "");
            return (Animator)t.GetProperty("Animator").GetValue(comp);
        }

        /// <summary>
        /// Switch off the pack's own locomotion script (it drives the pack's Animator parameters); the worker template
        /// drives its own Animator.
        /// </summary>
        public static int DisableLocomotion(GameObject inst)
        {
            int n = 0;
            foreach (var mb in inst.GetComponentsInChildren<MonoBehaviour>(true))
                if (mb != null && mb.GetType().FullName == "Sunbox.Avatars.AvatarLocomotion") { mb.enabled = false; n++; }
            return n;
        }
    }
}
