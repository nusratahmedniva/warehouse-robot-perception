using System.Collections.Generic;
using NUnit.Framework;
using UnityEngine;

namespace WarehouseHRI.Tests
{
    /// <summary>Task 1 checkpoints: the same stops as robot_vision/task_route.py (test_task_route.py pins the same list).</summary>
    public class Task1RouteTests
    {
        // Default 3 checkpoints: name, x, z, is an existing junction (C2 falls on J1 and is J1).
        static readonly (string, float, float, bool)[] k_Expected =
        {
            ("C1", 6.25f, -5f, false),
            ("J1", 6.25f, 0f, true),
            ("C3", 6.25f, 5f, false),
        };

        // One standing worker per stop (2026-10-21): stop, x, z, facing yaw; 1.0 m ahead, 2.5 m right, facing back.
        // test_task_route.py pins the same list.
        static readonly (string, float, float, float)[] k_ExpectedWorkers =
        {
            ("C1", 8.75f, -4f, 180f),
            ("J1", 8.75f, 1f, 180f),
            ("C3", 8.75f, 6f, 180f),
        };

        readonly List<GameObject> m_Created = new List<GameObject>();
        RoadNode m_A, m_J1, m_J2, m_E1, m_E2;

        RoadNode Node(string name, float x, float z, RoadNodeKind kind, Transform parent)
        {
            var go = new GameObject(name);
            go.transform.SetParent(parent, false);
            go.transform.position = new Vector3(x, 0f, z);
            var n = go.AddComponent<RoadNode>();
            n.kind = kind;
            return n;
        }

        [SetUp]
        public void BuildRoadmap()
        {
            var root = new GameObject("Roadmap");
            m_Created.Add(root);
            m_A = Node("A", 6.25f, -10f, RoadNodeKind.Waypoint, root.transform);
            m_J1 = Node("J1", 6.25f, 0f, RoadNodeKind.Junction, root.transform);
            m_J2 = Node("J2", -6.25f, 0f, RoadNodeKind.Junction, root.transform);
            m_E1 = Node("E1", 6.25f, 10f, RoadNodeKind.Endpoint, root.transform);
            m_E2 = Node("E2", 18.75f, 0f, RoadNodeKind.Endpoint, root.transform);
            m_A.branches = new List<RoadBranch> { new RoadBranch { command = GestureCommand.FORWARD, next = m_J1 } };
            m_J1.branches = new List<RoadBranch>
            {
                new RoadBranch { command = GestureCommand.FORWARD, next = m_E1 },
                new RoadBranch { command = GestureCommand.RIGHT, next = m_E2 },
                new RoadBranch { command = GestureCommand.LEFT, next = m_J2 },
            };
            var stand = new GameObject("WorkerStand").transform;
            stand.SetParent(m_J1.transform, false);
            m_J1.workerStand = stand;
        }

        [TearDown]
        public void Clean()
        {
            foreach (var go in m_Created) Object.DestroyImmediate(go);
            m_Created.Clear();
        }

        [Test]
        public void StraightLineFollowsForward()
        {
            var line = Task1Route.StraightLine(m_A);
            Assert.AreEqual(new[] { "A", "J1", "E1" }, line.ConvertAll(n => n.name).ToArray());
        }

        [Test]
        public void DefaultStopsArePinned()
        {
            var stops = Task1Route.Stops(Task1Route.StraightLine(m_A), 3, 0.5f);
            Assert.AreEqual(k_Expected.Length, stops.Count);
            for (int i = 0; i < stops.Count; i++)
            {
                Assert.AreEqual(k_Expected[i].Item1, stops[i].Name);
                Assert.AreEqual(k_Expected[i].Item2, stops[i].Position.x, 1e-4f);
                Assert.AreEqual(k_Expected[i].Item3, stops[i].Position.y, 1e-4f);
                Assert.AreEqual(k_Expected[i].Item4, stops[i].IsJunction);
            }

            Assert.AreEqual("Task1:C1,J1,C3", Task1Route.RouteId(stops));
        }

        [Test]
        public void ZeroOrOneCheckpointIsTheFormerTask1()
        {
            foreach (int n in new[] { 0, 1 })
                Assert.AreEqual("Task1:J1", Task1Route.RouteId(Task1Route.Stops(Task1Route.StraightLine(m_A), n, 0.5f)));
            Assert.AreEqual("Task1:C1,C2,J1,C3,C4", Task1Route.RouteId(Task1Route.Stops(Task1Route.StraightLine(m_A), 4, 0.5f)));
        }

        [Test]
        public void ApplyLinksTheStopsAndKeepsJ1sOtherBranches()
        {
            var stops = Task1Route.Apply(m_A, new Task1RouteConfig(), out string id);   // created under Roadmap
            Assert.AreEqual("Task1:C1,J1,C3", id);
            Assert.AreEqual(new[] { "C1", "J1", "C3" }, stops.ConvertAll(n => n.name).ToArray());
            Assert.AreEqual(stops[0], m_A.OnlyNext);
            Assert.AreEqual(m_J1, stops[0].Next(GestureCommand.FORWARD));
            Assert.AreEqual(stops[2], m_J1.Next(GestureCommand.FORWARD));
            Assert.AreEqual(m_E2, m_J1.Next(GestureCommand.RIGHT));
            Assert.AreEqual(m_J2, m_J1.Next(GestureCommand.LEFT));
            Assert.AreEqual(m_E1, stops[2].Next(GestureCommand.FORWARD));
            foreach (var s in stops)
            {
                Assert.IsTrue(s.IsJunction, s.name);
                Assert.AreEqual(GestureCommand.FORWARD, s.CommandToward(m_E1), s.name);
            }
            Assert.IsNull(stops[0].workerStand, "Task 1 workers stand by themselves; no moved-worker stand");
        }

        [Test]
        public void OneStandingWorkerPerStopIsPinned()
        {
            var stands = Task1Route.WorkerStands(m_A, new Task1RouteConfig());
            Assert.AreEqual(k_ExpectedWorkers.Length, stands.Count);
            for (int i = 0; i < stands.Count; i++)
            {
                Assert.AreEqual(k_ExpectedWorkers[i].Item1, stands[i].Stop);
                Assert.AreEqual(k_ExpectedWorkers[i].Item2, stands[i].Position.x, 1e-4f);
                Assert.AreEqual(k_ExpectedWorkers[i].Item3, stands[i].Position.z, 1e-4f);
                Assert.AreEqual(k_ExpectedWorkers[i].Item4, stands[i].Rotation.eulerAngles.y, 1e-3f);
            }

            Assert.AreEqual("Worker_C1", Task1Route.WorkerName("C1"));
            Assert.AreEqual(5, m_A.transform.parent.childCount, "WorkerStands adds nothing to the scene (A, J1, J2, E1, E2)");
        }
    }
}
