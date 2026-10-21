using NUnit.Framework;

namespace WarehouseHRI.Tests
{
    public class CommandWatchdogTests
    {
        const double T = 0.3;

        /// <summary>20 Hz telemetry, each written 1 ms after queueing and answered 2 ms later, from t0 to t1.</summary>
        static double Talk(CommandWatchdog w, ref int seq, double t0, double t1)
        {
            double t = t0;
            for (; t < t1; t += 0.05)
            {
                w.TelemetryQueued(seq, t);
                w.TelemetryWritten(seq, t + 0.001);
                w.CommandReceived(t + 0.003);
                Assert.IsNull(w.Check(t + 0.016, 16.0));
                seq++;
            }

            return t;
        }

        [Test]
        public void UnityFrameStallIsLoggedNotStopped()
        {
            var w = new CommandWatchdog(T);
            int seq = 0;
            double t = Talk(w, ref seq, 0.0, 1.0);
            // Unity's main thread stalls 0.32 s: no telemetry is sent, so Python has nothing to answer.
            double after = t + 0.32;
            Assert.IsNull(w.Check(after, 320.0), "a Unity hitch must not stop the robot");
            Assert.IsFalse(w.Stopped);
            w.TelemetryQueued(seq, after);
            w.TelemetryWritten(seq, after + 0.001);
            w.CommandReceived(after + 0.003);
            var ev = w.TakeEvents();
            Assert.AreEqual(1, ev.Count);
            Assert.AreEqual("unity_frame_stall", ev[0].Kind);
            Assert.That(ev[0].GapMs, Is.GreaterThan(300.0));
            Assert.AreEqual(320.0, ev[0].FrameMsMax, 1e-9);
            Assert.AreEqual((0, 1), (w.StopCount, w.FrameStallCount));
        }

        [Test]
        public void PythonSilentForSentTelemetryStops()
        {
            var w = new CommandWatchdog(T);
            int seq = 0;
            double t = Talk(w, ref seq, 0.0, 1.0);
            // Unity keeps sending at 20 Hz; Python stops answering.
            string cause = null;
            double next = t, firedAt = -1.0;
            for (double u = t; u < t + 0.5 && cause == null; u += 0.01)
            {
                if (u >= next)
                {
                    w.TelemetryQueued(seq, u);
                    w.TelemetryWritten(seq, u + 0.001);
                    seq++;
                    next += 0.05;
                }

                cause = w.Check(u, 10.0);
                if (cause != null) firedAt = u;
            }

            Assert.AreEqual("no_reply", cause);
            Assert.That(firedAt - (t + 0.001), Is.GreaterThan(T));
            Assert.That(firedAt - (t + 0.001), Is.LessThan(T + 0.02));
            Assert.IsTrue(w.Stopped);
            Assert.IsTrue(w.CommandReceived(t + 0.6), "the next command releases the stop");
            var ev = w.TakeEvents();
            Assert.AreEqual(1, ev.Count);
            Assert.AreEqual("watchdog_stop", ev[0].Kind);
            Assert.AreEqual("no_reply", ev[0].Cause);
            Assert.AreEqual(1, w.StopCount);
        }

        [Test]
        public void TelemetryStuckInTheSendQueueStops()
        {
            var w = new CommandWatchdog(T);
            int seq = 0;
            double t = Talk(w, ref seq, 0.0, 1.0);
            w.TelemetryQueued(seq, t);                       // never written: the socket is blocked
            Assert.IsNull(w.Check(t + 0.2, 16.0));
            Assert.AreEqual("not_written", w.Check(t + 0.31, 16.0));
        }

        [Test]
        public void AnsweredTelemetryAndOldWritesDoNotStop()
        {
            var w = new CommandWatchdog(T);
            int seq = 0;
            double t = Talk(w, ref seq, 0.0, 1.0);
            // The write stamp of an answered message arrives late (after its reply): ignored.
            w.TelemetryQueued(seq, t);
            w.CommandReceived(t + 0.003);
            w.TelemetryWritten(seq, t + 0.001);
            Assert.IsNull(w.Check(t + 0.25, 16.0));
            // No telemetry at all before the first command: never a stop.
            var fresh = new CommandWatchdog(T);
            fresh.TelemetryQueued(0, 0.0);
            fresh.TelemetryWritten(0, 0.0);
            Assert.IsNull(fresh.Check(5.0, 16.0));
        }

        [Test]
        public void DisconnectClosesTheEpisode()
        {
            var w = new CommandWatchdog(T);
            int seq = 0;
            double t = Talk(w, ref seq, 0.0, 0.5);
            Assert.IsNull(w.Check(t + 0.4, 400.0));
            w.Disconnected(t + 0.5);
            var ev = w.TakeEvents();
            Assert.AreEqual(1, ev.Count);
            Assert.IsTrue(ev[0].EndedByDisconnect);
            Assert.IsFalse(w.HasCommand);
        }
    }
}
