using System.Collections.Generic;
using System.Globalization;
using System.IO;
using System.Linq;
using System.Security.Cryptography;
using System.Text;
using NUnit.Framework;
using UnityEditor;
using UnityEngine;

namespace WarehouseAvatar.Tests
{
    /// <summary>
    /// The Sunbox looks' hand shapes stay identical (Avatar/Config/experiments_ab.md section 12 addendum 2): every installed Sunbox look of
    /// worker_v4.json, prepared as WorkerV4.Initialize prepares it, every hand shape on both hands, every finger bone position to 1e-6 m,
    /// hashed per look and compared with golden hashes computed by the code before the WAIT thumb tuck (5317465).
    /// </summary>
    public class SunboxHandPinTests
    {
        const string PrefabAsset = "Assets/WarehouseRobot/Avatar/Prefabs/WorkerV4.prefab";
        static readonly CultureInfo Inv = CultureInfo.InvariantCulture;

        static readonly Dictionary<string, string> Golden = new Dictionary<string, string>
        {
            { "sunbox_m1", "a5fb1cd7e42a2bbbd655643be7c349a46e1838d566fc3b7a97580a6e4dcfcc39" },
            { "sunbox_f1", "6b15ff26e819bf7b2df03bef431a277d909f176853fe825fc267d054427ce8a8" },
            { "sunbox_f2", "6b15ff26e819bf7b2df03bef431a277d909f176853fe825fc267d054427ce8a8" },
        };

        [Test]
        public void SunboxHands_AreIdenticalToBeforeTheThumbTuck()
        {
            var cfg = WorkerV4Config.Parse(File.ReadAllText(Path.Combine(Application.dataPath, "..", "Assets/WarehouseRobot/Avatar/Config/worker_v4.json")));
            var w = AssetDatabase.LoadAssetAtPath<GameObject>(PrefabAsset).GetComponent<WorkerV4>();
            var now = new Dictionary<string, string>();
            foreach (var look in cfg.looks.Where(l => l.kind == LookEntry.KindSunbox))
            {
                var prefab = w.lookSources.FirstOrDefault(s => s.asset == look.asset)?.prefab;
                if (prefab == null) continue;
                var inst = Object.Instantiate(prefab);
                try
                {
                    inst.transform.SetPositionAndRotation(Vector3.zero, Quaternion.identity);
                    var animator = SunboxLookApplier.Apply(inst, look.sunbox, out _);
                    HumanAvatarFix.Apply(animator);
                    var bones = new AnimatorBones(animator);
                    var left = HandShaper.BuildArm(bones, false);
                    var right = HandShaper.BuildArm(bones, true);
                    HandShaper.MirrorRest(right, left);                     // as WorkerV4.Initialize
                    var sb = new StringBuilder();
                    foreach (var a in new[] { left, right })
                    {
                        var bind = HandShaper.Capture(a);
                        var restHand = a.Hand.localRotation;
                        var tuck = HandShaper.ThumbTuck(a, bind, cfg.hand_shapes.wait);      // as WorkerV4.Initialize (section 12 addendum 2)
                        Assert.IsFalse(tuck.Active, $"{look.id}: the Sunbox thumb already meets the goal ({tuck.BeforeLp:0.000} Lp)");
                        foreach (var name in new[] { "point", "wait", "stop", "proceed" })
                        {
                            var shape = name == "point" ? cfg.hand_shapes.point : name == "wait" ? cfg.hand_shapes.wait : name == "stop" ? cfg.hand_shapes.stop : cfg.hand_shapes.proceed;
                            a.Hand.localRotation = restHand;
                            for (int f = 0; f < 5; f++) for (int j = 0; j < 3; j++) if (a.Fingers[f][j] != null) a.Fingers[f][j].localRotation = bind[f][j];
                            HandShaper.Apply(a, bind, shape, Vector3.up, Vector3.forward, 1f, name == "wait" ? tuck : null);
                            for (int f = 0; f < 5; f++)
                                for (int j = 0; j < 3; j++)
                                {
                                    var p = a.Fingers[f][j].position;
                                    sb.Append(p.x.ToString("0.000000", Inv)).Append(' ').Append(p.y.ToString("0.000000", Inv)).Append(' ').Append(p.z.ToString("0.000000", Inv)).Append('\n');
                                }
                        }
                    }
                    using (var sha = SHA256.Create())
                        now[look.id] = string.Concat(sha.ComputeHash(Encoding.ASCII.GetBytes(sb.ToString())).Select(b => b.ToString("x2")));
                }
                finally { Object.DestroyImmediate(inst); }
            }
            if (now.Count == 0) Assert.Ignore("no Sunbox look installed (third-party, git-ignored)");
            string computed = string.Join(", ", now.Select(kv => $"{{ \"{kv.Key}\", \"{kv.Value}\" }}"));
            Assert.IsNotEmpty(Golden, "golden hashes missing; computed now: " + computed);
            foreach (var kv in now)
            {
                Assert.IsTrue(Golden.ContainsKey(kv.Key), $"{kv.Key} has no golden hash; computed now: {computed}");
                Assert.AreEqual(Golden[kv.Key], kv.Value, $"{kv.Key}: the hand shapes changed");
            }
        }
    }
}
