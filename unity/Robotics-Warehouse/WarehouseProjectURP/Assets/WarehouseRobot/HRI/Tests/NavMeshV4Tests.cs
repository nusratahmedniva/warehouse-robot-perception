using System.Collections.Generic;
using System.IO;
using System.Linq;
using System.Security.Cryptography;
using System.Text.RegularExpressions;
using NUnit.Framework;
using UnityEditor.SceneManagement;
using UnityEngine;
using UnityEngine.AI;
using UnityEngine.SceneManagement;

namespace WarehouseHRI.Tests
{
    /// <summary>
    /// The racks in the robot's NavMesh (Avatar/Config/experiments_ab.md section 15 addendum 2). The v4 scene's NavMesh Surface (AMR) bakes the
    /// racks and pallets ("Ignore NavMesh Obstacles" off: the generated warehouse puts a NavMeshObstacle on each of them) into its own asset;
    /// the v3 scene keeps its asset, unchanged; on the v4 NavMesh no rack centre is reachable and a path across a rack goes around it.
    /// </summary>
    public class NavMeshV4Tests
    {
        const string V4Scene = "Assets/Scenes/WarehouseRobot_v4.unity";
        const string V3Scene = "Assets/Scenes/WarehouseRobot.unity";
        const string V4Asset = "Assets/Scenes/WarehouseRobot_v4/NavMesh-AMR.asset";
        const string V3Asset = "Assets/Scenes/WarehouseRobot/NavMesh-NavMesh Surface.asset";
        const string V3AssetGuid = "245bc8b1ab28a914a8f44731e6d8341d";
        /// <summary>SHA-256 (CRLF read as LF, as freeze_v4.py hashes) of the v3 asset at v1.0 and on 3f0422c; it must never change.</summary>
        const string V3AssetSha256 = "09aee22a747c25eace3f57d21978d3c86d2f5a1e07a3f13b03e7e0be20579294";
        const string SurfaceScriptGuid = "7a5ac11cc976e418e8d13136b07e1f52";   // Unity.AI.Navigation NavMeshSurface
        const string ModifierScriptGuid = "1e3fdca004f2d45fe8abbed571a8abd5";  // Unity.AI.Navigation NavMeshModifier
        const int AmrAgentTypeId = -1372625422;                                // ProjectSettings/NavMeshAreas.asset, "AMR"
        const int NotWalkableArea = 1;                                         // built-in area "Not Walkable"

        static string Project(string rel) => Path.Combine(Application.dataPath, "..", rel);

        /// <summary>The serialized NavMeshSurface blocks of a scene file.</summary>
        static List<string> SurfaceBlocks(string scenePath)
        {
            var blocks = Regex.Split(File.ReadAllText(Project(scenePath)).Replace("\r\n", "\n"), @"\n--- !u!");
            return blocks.Where(b => b.Contains("m_Script: {fileID: 11500000, guid: " + SurfaceScriptGuid)).ToList();
        }

        static string Field(string block, string name) => Regex.Match(block, @"\n  " + name + @": ([^\n]*)").Groups[1].Value.Trim();

        static string MetaGuid(string assetPath) => Regex.Match(File.ReadAllText(Project(assetPath + ".meta")), @"guid: ([0-9a-f]{32})").Groups[1].Value;

        static string Sha256Lf(string path)
        {
            var b = File.ReadAllBytes(path);
            var lf = new List<byte>(b.Length);
            for (int i = 0; i < b.Length; i++)
                if (!(b[i] == (byte)'\r' && i + 1 < b.Length && b[i + 1] == (byte)'\n')) lf.Add(b[i]);
            using (var sha = SHA256.Create()) return string.Concat(sha.ComputeHash(lf.ToArray()).Select(x => x.ToString("x2")));
        }

        [Test]
        public void V4Surface_BakesTheObstacles_IntoItsOwnAsset()
        {
            var s = SurfaceBlocks(V4Scene);
            Assert.AreEqual(1, s.Count, "one NavMesh Surface in the v4 scene");
            Assert.AreEqual(AmrAgentTypeId.ToString(), Field(s[0], "m_AgentTypeID"), "agent type AMR");
            Assert.AreEqual("0", Field(s[0], "m_IgnoreNavMeshObstacle"), "racks and pallets carry NavMeshObstacles; they must be baked");
            Assert.AreEqual("0", Field(s[0], "m_CollectObjects"), "collect All");
            Assert.AreEqual("0", Field(s[0], "m_UseGeometry"), "render meshes");
            Assert.IsTrue(File.Exists(Project(V4Asset)), V4Asset);
            string guid = MetaGuid(V4Asset);
            Assert.AreNotEqual(V3AssetGuid, guid);
            StringAssert.Contains("guid: " + guid + ",", Field(s[0], "m_NavMeshData"), "the v4 Surface uses the v4 asset");
        }

        [Test]
        public void V4Stations_AreNotWalkable()
        {
            // the 0.05 m station pads are below the bake's height resolution: a NavMeshModifier on the Stations group marks them Not Walkable
            string text = File.ReadAllText(Project(V4Scene)).Replace("\r\n", "\n");
            var blocks = Regex.Split(text, @"\n--- !u!");
            var go = blocks.Where(b => b.StartsWith("1 &") && b.Contains("\n  m_Name: Stations\n")).ToList();
            Assert.AreEqual(1, go.Count, "one Stations object");
            string id = Regex.Match(go[0], @"^1 &(\d+)").Groups[1].Value;
            var mods = blocks.Where(b => b.Contains("m_Script: {fileID: 11500000, guid: " + ModifierScriptGuid) && b.Contains("m_GameObject: {fileID: " + id + "}")).ToList();
            Assert.AreEqual(1, mods.Count, "a NavMeshModifier on Stations");
            Assert.AreEqual("1", Field(mods[0], "m_Enabled"));
            Assert.AreEqual("1", Field(mods[0], "m_OverrideArea"));
            Assert.AreEqual(NotWalkableArea.ToString(), Field(mods[0], "m_Area"), "Not Walkable");
            Assert.AreEqual("1", Field(mods[0], "m_ApplyToChildren"));
            Assert.AreEqual("0", Field(mods[0], "m_IgnoreFromBuild"));
        }

        [Test]
        public void V3Scene_KeepsItsNavMeshAsset_Unchanged()
        {
            var s = SurfaceBlocks(V3Scene);
            Assert.AreEqual(1, s.Count, "one NavMesh Surface in the v3 scene");
            StringAssert.Contains("guid: " + V3AssetGuid + ",", Field(s[0], "m_NavMeshData"), "the v3 Surface still uses the v3 asset");
            Assert.AreEqual("1", Field(s[0], "m_IgnoreNavMeshObstacle"), "v3 unchanged");
            Assert.AreEqual(V3AssetGuid, MetaGuid(V3Asset));
            Assert.AreEqual(V3AssetSha256, Sha256Lf(Project(V3Asset)), "the v3 NavMesh asset must stay byte for byte as at v1.0");
        }

        [Test]
        public void V4NavMesh_HasTheRacks()
        {
            var scene = EditorSceneManager.OpenScene(V4Scene, OpenSceneMode.Additive);
            try
            {
                var filter = new NavMeshQueryFilter { agentTypeID = AmrAgentTypeId, areaMask = NavMesh.AllAreas };
                var shelves = scene.GetRootGameObjects().SelectMany(r => r.GetComponentsInChildren<Transform>(true)).Single(t => t.name == "Shelves");
                Assert.AreEqual(12, shelves.childCount, "the 12 racks of the generated warehouse");
                float floorY = 0f;
                Assert.IsTrue(NavMesh.SamplePosition(new Vector3(6.25f, 0f, -5f), out var aisle, 0.5f, filter), "the aisle at (6.25, -5) is on the AMR NavMesh");
                floorY = aisle.position.y;
                var boxes = new List<Bounds>();
                foreach (Transform rack in shelves)
                {
                    var cs = rack.GetComponentsInChildren<Collider>(true);
                    Assert.Greater(cs.Length, 0, rack.name + " colliders");
                    var b = cs[0].bounds;
                    foreach (var c in cs) b.Encapsulate(c.bounds);
                    boxes.Add(b);
                    var centre = new Vector3(b.center.x, floorY, b.center.z);
                    bool near = NavMesh.SamplePosition(centre, out var hit, 0.6f, filter);
                    Assert.IsFalse(near && new Vector2(hit.position.x - centre.x, hit.position.z - centre.z).magnitude <= 0.5f,
                                   $"rack centre ({b.center.x:0.00}, {b.center.z:0.00}) lies on the NavMesh");
                }
                var stations = scene.GetRootGameObjects().SelectMany(r => r.GetComponentsInChildren<Transform>(true)).Single(t => t.name == "Stations");
                Assert.AreEqual(25, stations.childCount, "the 25 stations of the generated warehouse");
                foreach (Transform st in stations)
                {
                    var centre = new Vector3(st.position.x, floorY, st.position.z);
                    bool near = NavMesh.SamplePosition(centre, out var hit, 0.6f, filter);
                    Assert.IsFalse(near && new Vector2(hit.position.x - centre.x, hit.position.z - centre.z).magnitude <= 0.5f,
                                   $"station centre ({st.position.x:0.00}, {st.position.z:0.00}) lies on the NavMesh");
                }
                // across the rack at (0, -5): the straight line crosses it, the NavMesh path goes around it
                var a = aisle.position;
                Assert.IsTrue(NavMesh.SamplePosition(new Vector3(-6.25f, floorY, -5f), out var other, 0.5f, filter));
                var rackAt = boxes.Single(b => b.min.x < 0f && b.max.x > 0f && b.min.z < -5f && b.max.z > -5f);
                var path = new NavMeshPath();
                Assert.IsTrue(NavMesh.CalculatePath(a, other.position, filter, path));
                Assert.AreEqual(NavMeshPathStatus.PathComplete, path.status);
                float len = 0f;
                for (int k = 1; k < path.corners.Length; k++)
                {
                    var p = path.corners[k - 1]; var q = path.corners[k];
                    len += Vector3.Distance(p, q);
                    for (int i = 0; i <= 200; i++)
                    {
                        var x = Vector3.Lerp(p, q, i / 200f);
                        Assert.IsFalse(x.x > rackAt.min.x && x.x < rackAt.max.x && x.z > rackAt.min.z && x.z < rackAt.max.z,
                                       $"the path enters the rack at ({x.x:0.00}, {x.z:0.00})");
                    }
                }
                Assert.Greater(len, 12.5f + 0.05f, "the path goes around the rack");
            }
            finally { EditorSceneManager.CloseScene(scene, true); }
        }
    }
}
