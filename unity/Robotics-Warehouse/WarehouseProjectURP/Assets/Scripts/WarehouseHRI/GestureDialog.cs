namespace WarehouseHRI
{
    public enum DialogEvent
    {
        Pending,  // keep reading
        Accepted, // the same direction was held for hold_s
        AskAgain, // unclear: ask once more
        Abort,    // unclear after the last allowed ask
    }

    /// <summary>
    /// The "Which direction?" dialog as a pure state machine (no Unity calls, so it is unit-tested):
    /// a direction is accepted only when the same answer is read continuously for holdSeconds; any change or a
    /// NONE restarts the hold. If nothing is accepted within windowSeconds the answer is unclear: the robot asks
    /// once more (maxAsks = 2 in total), then aborts. STOP is not an answer: the caller handles it as a safety
    /// stop and does not pass it here.
    /// </summary>
    public class GestureDialog
    {
        public readonly float HoldSeconds;
        public readonly float WindowSeconds;
        public readonly int MaxAsks;

        GestureCommand m_Candidate = GestureCommand.NONE;
        float m_CandidateSince;
        float m_AskStart;

        public int AskCount { get; private set; }
        public GestureCommand Accepted { get; private set; } = GestureCommand.NONE;
        public GestureCommand Candidate => m_Candidate;

        public GestureDialog(float holdSeconds = 1.0f, float windowSeconds = 5f, int maxAsks = 2)
        {
            HoldSeconds = holdSeconds;
            WindowSeconds = windowSeconds;
            MaxAsks = maxAsks;
        }

        /// <summary>Start (or restart) the dialog at a new junction.</summary>
        public void Reset()
        {
            AskCount = 0;
            Accepted = GestureCommand.NONE;
            m_Candidate = GestureCommand.NONE;
        }

        /// <summary>The robot asks "Which direction?" at time <paramref name="t"/>.</summary>
        public void BeginAsk(float t)
        {
            AskCount++;
            m_AskStart = t;
            m_Candidate = GestureCommand.NONE;
            m_CandidateSince = t;
        }

        /// <summary>Feed the command read at time <paramref name="t"/>.</summary>
        public DialogEvent Update(GestureCommand read, float t)
        {
            if (!GestureCommands.IsDirection(read))
            {
                m_Candidate = GestureCommand.NONE;
                m_CandidateSince = t;
            }
            else if (read != m_Candidate)
            {
                m_Candidate = read;
                m_CandidateSince = t;
            }
            else if (t - m_CandidateSince >= HoldSeconds - 1e-4f)
            {
                Accepted = read;
                return DialogEvent.Accepted;
            }

            return t - m_AskStart >= WindowSeconds ? Unclear() : DialogEvent.Pending;
        }

        /// <summary>
        /// The accepted direction has no branch at this junction (or the answer was otherwise unusable):
        /// same consequence as an unclear answer.
        /// </summary>
        public DialogEvent Reject() => Unclear();

        DialogEvent Unclear()
        {
            Accepted = GestureCommand.NONE;
            return AskCount < MaxAsks ? DialogEvent.AskAgain : DialogEvent.Abort;
        }
    }
}
