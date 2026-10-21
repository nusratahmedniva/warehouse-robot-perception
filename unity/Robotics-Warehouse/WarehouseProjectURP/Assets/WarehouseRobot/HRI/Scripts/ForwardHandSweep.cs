using System.Collections.Generic;

namespace WarehouseHRI
{
    /// <summary>
    /// Seeded hand order of the development FORWARD hand sweep (TrialRunner task "ForwardHandSweep", AUDIT.md section 9
    /// item 15): 'repeats' pairs, each showing FORWARD with both hands at one placement; which hand comes first in a
    /// pair is a seeded coin flip (SplitMix64, GoalSequence), so the order is the same on every platform.
    /// </summary>
    public static class ForwardHandSweepOrder
    {
        public static List<GestureWorker.ForwardHand> Order(int seed, int repeats)
        {
            var rng = new GoalSequence(seed ^ 0x0f1d);
            var list = new List<GestureWorker.ForwardHand>();
            for (int p = 0; p < repeats; p++)
            {
                bool fistFirst = rng.NextInt(2) == 0;
                list.Add(fistFirst ? GestureWorker.ForwardHand.Fist : GestureWorker.ForwardHand.IndexFinger);
                list.Add(fistFirst ? GestureWorker.ForwardHand.IndexFinger : GestureWorker.ForwardHand.Fist);
            }

            return list;
        }

        /// <summary>Name written to truth_sweep.csv (column hand).</summary>
        public static string Label(GestureWorker.ForwardHand hand) =>
            hand == GestureWorker.ForwardHand.IndexFinger ? "index_finger" : "fist";
    }
}
