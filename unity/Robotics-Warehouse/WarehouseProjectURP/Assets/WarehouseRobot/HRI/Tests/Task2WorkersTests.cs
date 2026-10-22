using System.Collections.Generic;
using NUnit.Framework;
using UnityEngine;

namespace WarehouseHRI.Tests
{
    public class Task2WorkersTests
    {
        readonly List<GameObject> m_Made = new List<GameObject>();

        [TearDown]
        public void TearDown()
        {
            foreach (var go in m_Made) Object.DestroyImmediate(go);
            m_Made.Clear();
        }

        RoadNode Node(string name, RoadNodeKind kind, bool stand = true)
        {
            var go = new GameObject(name);
            m_Made.Add(go);
            var n = go.AddComponent<RoadNode>();
            n.kind = kind;
            if (kind == RoadNodeKind.Junction && stand)
            {
                var s = new GameObject(name + "_stand");
                m_Made.Add(s);
                n.workerStand = s.transform;
            }
            return n;
        }

        static void Link(RoadNode from, GestureCommand c, RoadNode to) =>
            from.branches.Add(new RoadBranch { command = c, next = to });

        [Test]
        public void OneWorkerPerJunctionInNameOrder()
        {
            var nodes = new[] { Node("E1", RoadNodeKind.Endpoint), Node("J2", RoadNodeKind.Junction), Node("A", RoadNodeKind.Waypoint),
                                Node("J1", RoadNodeKind.Junction) };
            var js = Task2Workers.Junctions(nodes, out var problem);
            Assert.IsNull(problem);
            CollectionAssert.AreEqual(new[] { "J1", "J2" }, js.ConvertAll(j => j.name));
        }

        [Test]
        public void JunctionWithoutStandRefused()
        {
            var nodes = new[] { Node("J1", RoadNodeKind.Junction), Node("J2", RoadNodeKind.Junction, stand: false) };
            Assert.IsNull(Task2Workers.Junctions(nodes, out var problem));
            StringAssert.Contains("J2", problem);
            Assert.IsNull(Task2Workers.Junctions(new[] { Node("A", RoadNodeKind.Waypoint) }, out problem));
            Assert.IsNotNull(problem);
        }

        [Test]
        public void CopyNameCountsAsAPerson()
        {
            Assert.AreEqual("Worker_Task2_J2", Task2Workers.CopyName("Worker", "J2"));
            StringAssert.Contains("Worker", Task2Workers.CopyName("Worker", "J2"));
            Assert.AreNotEqual("Worker_J1", Task2Workers.CopyName("Worker", "J1"));   // not a Task 1 worker's name
        }

        [Test]
        public void WorkerOffTheRouteShowsNone()
        {
            // The roadmap's shape: J1 -> FORWARD E1, RIGHT E2, LEFT J2; J2 -> FORWARD E3, RIGHT E4.
            RoadNode j1 = Node("J1", RoadNodeKind.Junction), j2 = Node("J2", RoadNodeKind.Junction);
            RoadNode e1 = Node("E1", RoadNodeKind.Endpoint), e2 = Node("E2", RoadNodeKind.Endpoint);
            RoadNode e3 = Node("E3", RoadNodeKind.Endpoint), e4 = Node("E4", RoadNodeKind.Endpoint);
            Link(j1, GestureCommand.FORWARD, e1); Link(j1, GestureCommand.RIGHT, e2); Link(j1, GestureCommand.LEFT, j2);
            Link(j2, GestureCommand.FORWARD, e3); Link(j2, GestureCommand.RIGHT, e4);
            Assert.AreEqual(GestureCommand.NONE, j2.CommandToward(e1));      // J2's worker stands idle on E1 / E2 trials
            Assert.AreEqual(GestureCommand.NONE, j2.CommandToward(e2));
            Assert.AreEqual(GestureCommand.RIGHT, j2.CommandToward(e4));
            Assert.AreEqual(GestureCommand.LEFT, j1.CommandToward(e4));
        }
    }
}
