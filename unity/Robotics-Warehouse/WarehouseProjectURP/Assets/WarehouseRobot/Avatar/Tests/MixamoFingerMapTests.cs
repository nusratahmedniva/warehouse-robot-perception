using System.Collections.Generic;
using System.Linq;
using NUnit.Framework;
using UnityEngine;

namespace WarehouseAvatar.Tests
{
    /// <summary>Humanoid fingers of a Mixamo rig mapped by its bone names (Avatar/Config/experiments_ab.md section 12 addendum 6).</summary>
    public class MixamoFingerMapTests
    {
        static HumanBone B(string human, string bone) => new HumanBone { humanName = human, boneName = bone };

        static IEnumerable<string> Skeleton(params string[] fingers)
        {
            yield return "mixamorig:Hips";
            yield return "mixamorig:LeftHand";
            foreach (var f in fingers) for (int j = 1; j <= 4; j++) yield return $"mixamorig:LeftHand{f}{j}";
        }

        [Test]
        public void HumanName_ReadsMixamoFingerNames()
        {
            Assert.AreEqual("Left Thumb Proximal", MixamoFingerMap.HumanName("mixamorig:LeftHandThumb1"));
            Assert.AreEqual("Right Little Distal", MixamoFingerMap.HumanName("mixamorig:RightHandPinky3"));
            Assert.AreEqual("Left Index Intermediate", MixamoFingerMap.HumanName("mixamorig1:LeftHandIndex2"));
            Assert.IsNull(MixamoFingerMap.HumanName("mixamorig:LeftHandThumb4"), "the end bone is not a Humanoid finger joint");
            Assert.IsNull(MixamoFingerMap.HumanName("J_Bip_L_Thumb1"));
        }

        [Test]
        public void ThumbMappedAsLittleFinger_IsCorrectedByTheNames()
        {
            // Boxo v3 as imported: the thumb chain on the little finger, no thumb
            var human = new[]
            {
                B("Hips", "mixamorig:Hips"), B("LeftHand", "mixamorig:LeftHand"),
                B("Left Little Proximal", "mixamorig:LeftHandThumb1"), B("Left Little Intermediate", "mixamorig:LeftHandThumb2"), B("Left Little Distal", "mixamorig:LeftHandThumb3"),
                B("Left Index Proximal", "mixamorig:LeftHandIndex1"), B("Left Index Intermediate", "mixamorig:LeftHandIndex2"), B("Left Index Distal", "mixamorig:LeftHandIndex3"),
            };
            var fixedHuman = MixamoFingerMap.Correct(human, Skeleton("Thumb", "Index"), out var changes);
            Assert.IsNotNull(fixedHuman);
            var map = fixedHuman.ToDictionary(x => x.humanName, x => x.boneName);
            Assert.AreEqual("mixamorig:LeftHandThumb1", map["Left Thumb Proximal"]);
            Assert.AreEqual("mixamorig:LeftHandThumb3", map["Left Thumb Distal"]);
            Assert.IsFalse(map.ContainsKey("Left Little Proximal"), "no little finger in the rig");
            Assert.AreEqual("mixamorig:LeftHandIndex2", map["Left Index Intermediate"]);
            Assert.AreEqual("mixamorig:Hips", map["Hips"], "non-finger entries kept");
            Assert.IsTrue(changes.Any(c => c.StartsWith("Left Little Proximal: mixamorig:LeftHandThumb1 -> (removed)")), string.Join("; ", changes));
            Assert.IsTrue(changes.Any(c => c.StartsWith("Left Thumb Proximal: (none) -> mixamorig:LeftHandThumb1")), string.Join("; ", changes));
        }

        [Test]
        public void AgreeingMapping_OrANonMixamoRig_IsUntouched()
        {
            var ok = new[] { B("Left Thumb Proximal", "mixamorig:LeftHandThumb1"), B("Left Index Proximal", "mixamorig:LeftHandIndex1") };
            Assert.IsNull(MixamoFingerMap.Correct(ok, Skeleton("Thumb", "Index"), out _));
            var vroid = new[] { B("Left Thumb Proximal", "J_Bip_L_Thumb1") };
            Assert.IsNull(MixamoFingerMap.Correct(vroid, new[] { "J_Bip_L_Thumb1", "J_Bip_L_Hand" }, out _));
        }
    }
}
