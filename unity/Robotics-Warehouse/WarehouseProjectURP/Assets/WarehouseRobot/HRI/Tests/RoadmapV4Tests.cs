using System.Collections.Generic;
using System.IO;
using NUnit.Framework;
using UnityEditor.SceneManagement;
using UnityEngine;
using UnityEngine.SceneManagement;
using WarehouseHRI.V4;

namespace WarehouseHRI.Tests
{
    /// <summary>
    /// The v4 map (2026-11-12, P7 and P8; Avatar/Config/upgrade_design.md section 6): robot_vision/configs/v4/roadmap.json is
    /// read correctly, its labels match the geometry, and WarehouseRobot_v4.unity holds exactly that roadmap (nodes, kinds,
    /// positions, branches, worker stands), so Unity and Python use one map.
    /// </summary>
    public class RoadmapV4Tests
    {
        const string Scene = "Assets/Scenes/WarehouseRobot_v4.unity";
        static string RepoFile(string rel) => Path.GetFullPath(Path.Combine(Application.dataPath, "../../../..", rel));
        static RoadmapV4 Map() => RoadmapV4.Parse(File.ReadAllText(RepoFile("robot_vision/configs/v4/roadmap.json")));

        [Test]
        public void MiniJson_ReadsObjectsArraysAndNumbers()
        {
            var o = (Dictionary<string, object>)MiniJson.Parse("{\"a\": [1, -2.5e1, \"x\\\"y\"], \"b\": {\"c\": true, \"d\": null}}");
            var a = (List<object>)o["a"];
            Assert.AreEqual(1.0, a[0]);
            Assert.AreEqual(-25.0, a[1]);
            Assert.AreEqual("x\"y", a[2]);
            Assert.AreEqual(true, ((Dictionary<string, object>)o["b"])["c"]);
            Assert.Throws<System.FormatException>(() => MiniJson.Parse("{\"a\": 1,}"));
        }

        [Test]
        public void File_HasTheDeclaredMapAndConsistentLabels()
        {
            var m = Map();
            Assert.AreEqual("A", m.Start);
            Assert.AreEqual(RoadmapV4.KindStart, m.Node("A").Kind);
            CollectionAssert.IsEmpty(m.LabelProblems());
            var ends = m.Nodes.FindAll(n => n.Kind == RoadmapV4.KindEndpoint).ConvertAll(n => n.Name);
            CollectionAssert.AreEqual(new[] { "E1", "E2", "E3", "E4", "E5", "E6" }, ends);
            Assert.AreEqual(4, m.Nodes.FindAll(n => n.Kind == RoadmapV4.KindJunction).Count);
            m.Stand(m.Node("A"), 0f, out var p, out var r);
            Assert.AreEqual(8.75f, p.x, 1e-4f);
            Assert.AreEqual(-17.5f, p.z, 1e-4f);
            Assert.AreEqual(180f, r.eulerAngles.y, 1e-3f, "the worker at A faces the arriving robot");
        }

        [Test]
        public void V4Scene_RoadmapEqualsTheFile()
        {
            var m = Map();
            var scene = EditorSceneManager.OpenScene(Scene, OpenSceneMode.Additive);
            try
            {
                var found = new Dictionary<string, RoadNode>();
                foreach (var go in scene.GetRootGameObjects())
                    foreach (var n in go.GetComponentsInChildren<RoadNode>(true)) found[n.name] = n;
                CollectionAssert.AreEquivalent(m.Nodes.ConvertAll(n => n.Name), found.Keys, "node names");
                float y = found["A"].Position.y;
                foreach (var d in m.Nodes)
                {
                    var n = found[d.Name];
                    Assert.AreEqual(d.X, n.Position.x, 1e-3f, d.Name);
                    Assert.AreEqual(d.Z, n.Position.z, 1e-3f, d.Name);
                    var kind = d.Kind == RoadmapV4.KindStart ? RoadNodeKind.Start : d.Kind == RoadmapV4.KindJunction ? RoadNodeKind.Junction : RoadNodeKind.Endpoint;
                    Assert.AreEqual(kind, n.kind, d.Name);
                    if (d.HasStartYaw) Assert.AreEqual(Mathf.DeltaAngle(0f, d.StartYawDeg), Mathf.DeltaAngle(0f, n.transform.eulerAngles.y), 1e-3f, d.Name + " start heading");
                    var want = m.Branches.TryGetValue(d.Name, out var b) ? b : new List<KeyValuePair<string, string>>();
                    var have = n.branches.ConvertAll(x => new KeyValuePair<string, string>(x.command.ToString(), x.next != null ? x.next.name : ""));
                    CollectionAssert.AreEquivalent(want, have, d.Name + " branches");
                    if (n.IsAskNode)
                    {
                        Assert.IsNotNull(n.workerStand, d.Name + " worker stand");
                        m.Stand(d, y, out var p, out var r);
                        Assert.Less(Vector3.Distance(p, n.workerStand.position), 1e-3f, d.Name + " stand position");
                        Assert.Less(Quaternion.Angle(r, n.workerStand.rotation), 0.01f, d.Name + " stand facing");
                    }
                }
            }
            finally { EditorSceneManager.CloseScene(scene, true); }
        }
    }
}
