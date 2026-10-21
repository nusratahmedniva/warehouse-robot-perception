using System.Collections.Generic;

namespace WarehouseHRI
{
    /// <summary>
    /// The bridge watchdog rule (used by RobotBridgeClient; pure C#, so EditMode tests can drive it with any clock).
    /// Since 2026-10-22 (AUDIT.md section 9, measurement correction): the robot is stopped only when Python is silent
    /// for telemetry Unity actually sent, i.e. a telemetry message whose write to the socket started more than
    /// timeout_s ago and no command has arrived since. Before, it stopped when no command had arrived for timeout_s of
    /// wall-clock time, so a long Unity frame (during which Unity sends no telemetry and Python has nothing to answer)
    /// also stopped the robot although Python was answering every message within milliseconds.
    /// Backstop: a telemetry message queued but not yet written for timeout_s, with no command since it was queued,
    /// also stops the robot (the socket is blocked, so Python cannot be seeing the robot's state).
    /// Silences that only the old wall-clock rule catches are kept as "unity_frame_stall" events with their durations;
    /// stops are "watchdog_stop" events (cause no_reply or not_written). Times are seconds on one monotonic clock.
    /// </summary>
    public sealed class CommandWatchdog
    {
        public struct Event
        {
            public string Kind;        // "watchdog_stop" or "unity_frame_stall"
            public string Cause;       // watchdog_stop: "no_reply" / "not_written"; unity_frame_stall: "no_telemetry_sent"
            public double StartS;      // last command before the silence
            public double GapMs;       // command silence (until the next command, or the disconnect)
            public double FrameMsMax;  // longest Unity frame during the silence
            public bool EndedByDisconnect;
        }

        struct Pending
        {
            public int Seq;
            public double QueuedS, WrittenS;
            public bool Written;
            public double Ref => Written ? WrittenS : QueuedS;
        }

        const int MaxPending = 400;
        readonly double timeoutS;
        readonly List<Pending> pending = new List<Pending>();
        readonly List<Event> events = new List<Event>();
        bool hasCommand;
        double lastCommandS;
        bool episodeOld, episodeNew;
        string episodeCause;
        double episodeFrameMaxMs;

        public CommandWatchdog(double timeoutS) { this.timeoutS = timeoutS; }

        public double TimeoutS => timeoutS;
        public bool Stopped { get; private set; }
        public int StopCount { get; private set; }
        public int FrameStallCount { get; private set; }
        public bool HasCommand => hasCommand;
        public double LastCommandS => lastCommandS;

        /// <summary>Forget everything (new connection or disconnect). Counters stay.</summary>
        public void Reset()
        {
            pending.Clear();
            hasCommand = Stopped = false;
            ClearEpisode();
        }

        /// <summary>Main thread, right after a telemetry message was queued for the network thread.</summary>
        public void TelemetryQueued(int seq, double nowS)
        {
            pending.Add(new Pending { Seq = seq, QueuedS = nowS });
            if (pending.Count > MaxPending) pending.RemoveAt(0);
        }

        /// <summary>Network thread's time stamp when it started writing that telemetry message to the socket.</summary>
        public void TelemetryWritten(int seq, double writtenS)
        {
            for (int i = 0; i < pending.Count; i++)
            {
                if (pending[i].Seq != seq) continue;
                var p = pending[i];
                p.WrittenS = writtenS;
                p.Written = true;
                pending[i] = p;
                return;
            }
        }

        /// <summary>A command arrived (network thread's receive time). Returns true if it released a watchdog stop.</summary>
        public bool CommandReceived(double receivedS)
        {
            if (hasCommand && (episodeOld || episodeNew)) Emit(receivedS, false);
            ClearEpisode();
            hasCommand = true;
            lastCommandS = receivedS;
            pending.RemoveAll(p => p.Written && p.WrittenS <= receivedS);
            bool released = Stopped;
            Stopped = false;
            return released;
        }

        /// <summary>
        /// Once per Unity frame (after the commands of this frame were applied). frameMs = duration of the frame that
        /// just ended. Returns the cause when the robot must stop now ("no_reply" / "not_written"), else null.
        /// </summary>
        public string Check(double nowS, double frameMs)
        {
            if (!hasCommand) return null;
            if (frameMs > episodeFrameMaxMs) episodeFrameMaxMs = frameMs;
            if (nowS - lastCommandS > timeoutS) episodeOld = true;          // the old wall-clock rule would stop here
            if (Stopped) return null;
            foreach (var p in pending)
            {
                if (p.Ref < lastCommandS || nowS - p.Ref <= timeoutS) continue;
                Stopped = true;
                StopCount++;
                episodeNew = true;
                episodeCause = p.Written ? "no_reply" : "not_written";
                return episodeCause;
            }

            return null;
        }

        /// <summary>The connection dropped: close an open silence episode (gap up to now) and forget the state.</summary>
        public void Disconnected(double nowS)
        {
            if (hasCommand && (episodeOld || episodeNew)) Emit(nowS, true);
            Reset();
        }

        /// <summary>Events completed since the previous call (sent with the next telemetry).</summary>
        public List<Event> TakeEvents()
        {
            var e = new List<Event>(events);
            events.Clear();
            return e;
        }

        void Emit(double endS, bool byDisconnect)
        {
            bool stop = episodeNew;
            if (!stop) FrameStallCount++;
            events.Add(new Event
            {
                Kind = stop ? "watchdog_stop" : "unity_frame_stall",
                Cause = stop ? episodeCause : "no_telemetry_sent",
                StartS = lastCommandS,
                GapMs = (endS - lastCommandS) * 1000.0,
                FrameMsMax = episodeFrameMaxMs,
                EndedByDisconnect = byDisconnect,
            });
        }

        void ClearEpisode()
        {
            episodeOld = episodeNew = false;
            episodeCause = null;
            episodeFrameMaxMs = 0.0;
        }
    }
}
