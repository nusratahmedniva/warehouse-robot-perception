namespace WarehouseHRI
{
    /// <summary>
    /// Reproducible random numbers for the trials: SplitMix64 (same numbers on every platform and runtime, unlike
    /// System.Random; robot_vision/hri_trials.py implements the same generator to check the goal order). Picks one
    /// goal per trial, never the same as the previous trial ("B changes every trial").
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

        /// <summary>Uniform float in [a, b).</summary>
        public float Uniform(float a, float b) => a + (b - a) * (float)((NextUInt64() >> 11) * (1.0 / (1UL << 53)));

        /// <summary>Index of the next goal among count endpoints, different from the previous one.</summary>
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
    }
}
