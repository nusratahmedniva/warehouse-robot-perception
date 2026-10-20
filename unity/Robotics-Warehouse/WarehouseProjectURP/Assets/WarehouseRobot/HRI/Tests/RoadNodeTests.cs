using System.Collections.Generic;
using NUnit.Framework;
using UnityEngine;

namespace WarehouseHRI.Tests
{
    /// <summary>Roadmap lookup on the same shape the scene builder creates: A -> J1 {F: E1, R: E2, L: J2}, J2 {F: E3, R: E4}.</summary>
    public class RoadNodeTests
    {
        readonly List<GameObject> m_Objects = new List<GameObject>();
        RoadNode m_A, m_J1, m_J2, m_E1, m_E2, m_E3, m_E4;

        RoadNode Make(string name, RoadNodeKind kind)
        {
            var go = new GameObject(name);
            m_Objects.Add(go);
            var n = go.AddComponent<RoadNode>();
            n.kind = kind;
            return n;
        }

        static void Link(RoadNode n, params (GestureCommand c, RoadNode next)[] branches)
        {
            n.branches = new List<RoadBranch>();
            foreach (var (c, next) in branches) n.branches.Add(new RoadBranch { command = c, next = next });
        }

        [SetUp]
        public void SetUp()
        {
            m_A = Make("A", RoadNodeKind.Waypoint);
            m_J1 = Make("J1", RoadNodeKind.Junction);
            m_J2 = Make("J2", RoadNodeKind.Junction);
            m_E1 = Make("E1", RoadNodeKind.Endpoint);
            m_E2 = Make("E2", RoadNodeKind.Endpoint);
            m_E3 = Make("E3", RoadNodeKind.Endpoint);
            m_E4 = Make("E4", RoadNodeKind.Endpoint);
            Link(m_A, (GestureCommand.FORWARD, m_J1));
            Link(m_J1, (GestureCommand.FORWARD, m_E1), (GestureCommand.RIGHT, m_E2), (GestureCommand.LEFT, m_J2));
            Link(m_J2, (GestureCommand.FORWARD, m_E3), (GestureCommand.RIGHT, m_E4));
        }

        [TearDown]
        public void TearDown()
        {
            foreach (var go in m_Objects) Object.DestroyImmediate(go);
            m_Objects.Clear();
        }

        [Test]
        public void NextReturnsTheBranchForACommand()
        {
            Assert.AreSame(m_E1, m_J1.Next(GestureCommand.FORWARD));
            Assert.AreSame(m_E2, m_J1.Next(GestureCommand.RIGHT));
            Assert.AreSame(m_J2, m_J1.Next(GestureCommand.LEFT));
            Assert.AreSame(m_E4, m_J2.Next(GestureCommand.RIGHT));
        }

        [Test]
        public void NextIsNullForCommandsWithoutABranch()
        {
            Assert.IsNull(m_J1.Next(GestureCommand.FORWARD_LEFT));
            Assert.IsNull(m_J1.Next(GestureCommand.NONE));
            Assert.IsNull(m_J1.Next(GestureCommand.STOP));
            Assert.IsNull(m_J2.Next(GestureCommand.LEFT));
            Assert.IsNull(m_E1.Next(GestureCommand.FORWARD));
        }

        [Test]
        public void ReachesFollowsBranchesTransitively()
        {
            Assert.IsTrue(m_A.Reaches(m_E4));
            Assert.IsTrue(m_J1.Reaches(m_E3));
            Assert.IsTrue(m_E2.Reaches(m_E2));
            Assert.IsFalse(m_J2.Reaches(m_E1));
            Assert.IsFalse(m_E1.Reaches(m_E2));
            Assert.IsFalse(m_J1.Reaches(null));
        }

        [Test]
        public void ReachesTerminatesOnCycles()
        {
            Link(m_E1, (GestureCommand.FORWARD, m_J1)); // loop E1 -> J1 -> E1
            Assert.IsTrue(m_E1.Reaches(m_E4));
            Assert.IsFalse(m_E3.Reaches(m_A));
        }

        [Test]
        public void CommandTowardScriptsTheWorkerPerGoal()
        {
            Assert.AreEqual(GestureCommand.FORWARD, m_J1.CommandToward(m_E1));
            Assert.AreEqual(GestureCommand.RIGHT, m_J1.CommandToward(m_E2));
            Assert.AreEqual(GestureCommand.LEFT, m_J1.CommandToward(m_E3));
            Assert.AreEqual(GestureCommand.LEFT, m_J1.CommandToward(m_E4));
            Assert.AreEqual(GestureCommand.RIGHT, m_J2.CommandToward(m_E4));
            Assert.AreEqual(GestureCommand.NONE, m_J2.CommandToward(m_E1)); // after a wrong turn: nothing to show
        }

        [Test]
        public void ReachableEndpointsListsAllFourGoals()
        {
            CollectionAssert.AreEquivalent(new[] { m_E1, m_E2, m_E3, m_E4 }, m_A.ReachableEndpoints());
            Assert.AreSame(m_J1, m_A.OnlyNext);
        }

        [Test]
        public void TurnAnglesMapToCommands()
        {
            Assert.AreEqual(GestureCommand.FORWARD, GestureCommands.FromTurnAngle(0f));
            Assert.AreEqual(GestureCommand.RIGHT, GestureCommands.FromTurnAngle(90f));
            Assert.AreEqual(GestureCommand.LEFT, GestureCommands.FromTurnAngle(-90f));
            Assert.AreEqual(GestureCommand.FORWARD_RIGHT, GestureCommands.FromTurnAngle(45f));
            Assert.AreEqual(GestureCommand.FORWARD_LEFT, GestureCommands.FromTurnAngle(-45f));
            Assert.AreEqual(GestureCommand.LEFT, GestureCommands.FromTurnAngle(270f));
        }
    }
}
