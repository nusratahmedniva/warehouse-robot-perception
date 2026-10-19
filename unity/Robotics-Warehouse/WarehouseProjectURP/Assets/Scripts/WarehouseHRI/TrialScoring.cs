using System.Collections.Generic;
using System.Globalization;
using UnityEngine;

namespace WarehouseHRI
{
    public enum TrialOutcome { SUCCESS, FAILURE }

    public enum FailureReason { none, timeout, collision, stuck, wrong_goal, aborted }

    public struct TrialScore
    {
        public TrialOutcome Outcome;
        public FailureReason Reason;
        public string Detail;
    }

    /// <summary>
    /// Scoring of one trial from ground truth (true final position, true goal). Used only by TrialManager after
    /// the run; the robot never sees it. Priority: collision, stuck, timeout, aborted, then the final position.
    /// </summary>
    public static class TrialScoring
    {
        public const float DefaultSuccessRadius = 0.3f;

        public static TrialScore Score(Vector2 finalXZ, Vector2 goalXZ, bool robotFinished, bool collided,
            bool stuck, bool timedOut, bool aborted, string abortReason = null,
            float successRadius = DefaultSuccessRadius)
        {
            float d = Vector2.Distance(finalXZ, goalXZ);
            if (collided) return Fail(FailureReason.collision, "collision");
            if (stuck) return Fail(FailureReason.stuck, "no progress while driving");
            if (timedOut) return Fail(FailureReason.timeout, "trial time limit reached");
            if (aborted) return Fail(FailureReason.aborted, string.IsNullOrEmpty(abortReason) ? "aborted" : abortReason);
            if (!robotFinished) return Fail(FailureReason.timeout, "robot did not finish");
            if (d <= successRadius)
                return new TrialScore { Outcome = TrialOutcome.SUCCESS, Reason = FailureReason.none, Detail = "stopped " + F(d) + " m from B" };
            return Fail(FailureReason.wrong_goal, "stopped " + F(d) + " m from B (> " + F(successRadius) + " m)");
        }

        static string F(float x) => x.ToString("0.000", CultureInfo.InvariantCulture);

        static TrialScore Fail(FailureReason r, string detail) =>
            new TrialScore { Outcome = TrialOutcome.FAILURE, Reason = r, Detail = detail };
    }

    /// <summary>
    /// Reproducible goal choice: a SplitMix64 generator (same numbers on every platform and .NET runtime, unlike
    /// System.Random) picks one endpoint per trial, never the same as the previous trial ("B changes every trial").
    /// </summary>
    public class GoalSequence
    {
        ulong m_State;
        int m_Previous = -1;

        public GoalSequence(int seed)
        {
            m_State = unchecked((ulong)(uint)seed * 0x9E3779B97F4A7C15UL + 0x632BE59BD9B4E019UL);
        }

        public ulong NextUInt64()
        {
            unchecked
            {
                ulong z = m_State += 0x9E3779B97F4A7C15UL;
                z = (z ^ (z >> 30)) * 0xBF58476D1CE4E5B9UL;
                z = (z ^ (z >> 27)) * 0x94D049BB133111EBUL;
                return z ^ (z >> 31);
            }
        }

        /// <summary>Uniform integer in [0, n).</summary>
        public int NextInt(int n) => n <= 1 ? 0 : (int)(NextUInt64() % (ulong)n);

        /// <summary>Index of the next goal among <paramref name="count"/> endpoints, different from the previous one.</summary>
        public int NextGoalIndex(int count)
        {
            if (count <= 0) return -1;
            int i;
            if (count == 1 || m_Previous < 0) i = NextInt(count);
            else
            {
                i = NextInt(count - 1);
                if (i >= m_Previous) i++;
            }

            m_Previous = i;
            return i;
        }

        /// <summary>The first <paramref name="trials"/> goal indices for a seed (for logs and tests).</summary>
        public static List<int> Preview(int seed, int count, int trials)
        {
            var g = new GoalSequence(seed);
            var list = new List<int>();
            for (int t = 0; t < trials; t++) list.Add(g.NextGoalIndex(count));
            return list;
        }
    }
}
