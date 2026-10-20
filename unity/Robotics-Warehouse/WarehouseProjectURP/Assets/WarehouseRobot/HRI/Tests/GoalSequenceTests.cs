using System.Collections.Generic;
using NUnit.Framework;

namespace WarehouseHRI.Tests
{
    public class GoalSequenceTests
    {
        static List<int> Preview(int seed, int count, int n)
        {
            var g = new GoalSequence(seed);
            var l = new List<int>();
            for (int i = 0; i < n; i++) l.Add(g.NextGoalIndex(count));
            return l;
        }

        [Test]
        public void PinnedToTheIndependentPythonComputation()
        {
            // Same values as robot_vision/hri_trials.py (and the v1 branch's pinned test).
            CollectionAssert.AreEqual(new List<int> { 3, 1, 0, 3, 1, 0, 2, 3, 0, 3 }, Preview(1, 4, 10));
            CollectionAssert.AreEqual(new List<int> { 0, 1, 3, 1, 0, 2, 3, 0, 3, 0 }, Preview(2, 4, 10));
        }

        [Test]
        public void GoalChangesEveryTrial()
        {
            var s = Preview(7, 4, 200);
            for (int i = 1; i < s.Count; i++) Assert.AreNotEqual(s[i - 1], s[i]);
        }
    }
}
