using NUnit.Framework;

namespace WarehouseHRI.Tests
{
    public class ForwardHandSweepTests
    {
        [Test]
        public void EveryPairShowsBothHandsAndTheOrderIsSeeded()
        {
            var a = ForwardHandSweepOrder.Order(1, 20);
            Assert.AreEqual(40, a.Count);
            int firstFist = 0;
            for (int p = 0; p < 20; p++)
            {
                Assert.AreNotEqual(a[2 * p], a[2 * p + 1]);
                if (a[2 * p] == GestureWorker.ForwardHand.Fist) firstFist++;
            }

            Assert.That(firstFist, Is.InRange(1, 19), "both hands come first in some pairs");
            CollectionAssert.AreEqual(a, ForwardHandSweepOrder.Order(1, 20));
            CollectionAssert.AreNotEqual(a, ForwardHandSweepOrder.Order(2, 20));
        }

        [Test]
        public void LabelsMatchThePythonEvaluation()
        {
            Assert.AreEqual("fist", ForwardHandSweepOrder.Label(GestureWorker.ForwardHand.Fist));
            Assert.AreEqual("index_finger", ForwardHandSweepOrder.Label(GestureWorker.ForwardHand.IndexFinger));
        }

        [Test]
        public void DefaultForwardHandIsTheFist()
        {
            var go = new UnityEngine.GameObject("w");
            try { Assert.AreEqual(GestureWorker.ForwardHand.Fist, go.AddComponent<GestureWorker>().forwardHand); }
            finally { UnityEngine.Object.DestroyImmediate(go); }
        }
    }
}
