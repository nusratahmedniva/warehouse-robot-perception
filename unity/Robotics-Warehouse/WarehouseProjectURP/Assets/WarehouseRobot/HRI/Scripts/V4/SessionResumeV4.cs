using System.Globalization;

namespace WarehouseHRI.V4
{
    /// <summary>
    /// A session that starts at run k (Avatar/Config/experiments_ab.md section 15 addendum 10; TrialPlayV4 -startRun k). TrialRunnerV4 plans
    /// and checks all N runs as a full session does and drives runs k..N: every element of a run (goal, map side, placement, looks, liars,
    /// the workers' variation streams) is a function of (session seed, run, goal of the run) and the goals of all N runs come from one seeded
    /// sequence, so runs k..N are those of the full session (SessionResumeTests). Refused in a final: the run-once guards (FinalGuardV4,
    /// Python's FINAL_RUN_DONE.json) refuse a second session of a setting; a resumed final needs Anisha's interruption rule in them first.
    /// </summary>
    public static class SessionResumeV4
    {
        /// <summary>The first run from the -startRun text: "" = 1 (a full session); otherwise a whole number within 1..<paramref name="runs"/>,
        /// and refused in a final. False with the reason otherwise.</summary>
        public static bool Parse(string text, int runs, bool final, out int startRun, out string error)
        {
            startRun = 1;
            error = null;
            text = (text ?? "").Trim();
            if (text.Length == 0) return true;
            if (final)
            {
                error = $"-startRun {text} is refused in a final: the run-once guards refuse a second session of a setting (a resumed final " +
                        "needs Anisha's interruption rule in both guards first; experiments_ab.md section 15 addendum 10)";
                return false;
            }
            if (!int.TryParse(text, NumberStyles.None, CultureInfo.InvariantCulture, out int k))
            {
                error = $"-startRun '{text}' is not a whole number";
                return false;
            }
            if (k < 1 || k > runs)
            {
                error = $"-startRun {k} is outside 1..{runs} (the session's runs)";
                return false;
            }
            startRun = k;
            return true;
        }
    }
}
