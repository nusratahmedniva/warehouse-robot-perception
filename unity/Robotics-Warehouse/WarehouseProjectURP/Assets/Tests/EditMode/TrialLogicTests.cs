using System.Collections.Generic;
using NUnit.Framework;
using UnityEngine;

namespace WarehouseHRI.Tests
{
    public class GoalSequenceTests
    {
        [Test]
        public void SameSeedGivesTheSameGoals()
        {
            CollectionAssert.AreEqual(GoalSequence.Preview(1, 4, 50), GoalSequence.Preview(1, 4, 50));
            CollectionAssert.AreEqual(GoalSequence.Preview(2, 4, 50), GoalSequence.Preview(2, 4, 50));
        }

        [Test]
        public void DevAndFinalSeedsDiffer()
        {
            CollectionAssert.AreNotEqual(GoalSequence.Preview(1, 4, 20), GoalSequence.Preview(2, 4, 20));
        }

        [Test]
        public void KnownSequenceIsPinned()
        {
            // Values computed independently (Python SplitMix64, same algorithm), so a change of the generator,
            // which would silently change which goals the final trials use, fails this test.
            CollectionAssert.AreEqual(new List<int> { 3, 1, 0, 3, 1, 0, 2, 3, 0, 3 }, GoalSequence.Preview(1, 4, 10));
            CollectionAssert.AreEqual(new List<int> { 0, 1, 3, 1, 0, 2, 3, 0, 3, 0 }, GoalSequence.Preview(2, 4, 10));
        }

        [Test]
        public void GoalChangesEveryTrialAndStaysInRange()
        {
            var seq = GoalSequence.Preview(7, 4, 200);
            for (int i = 0; i < seq.Count; i++)
            {
                Assert.That(seq[i], Is.InRange(0, 3));
                if (i > 0) Assert.AreNotEqual(seq[i - 1], seq[i], $"trial {i + 1} repeats the previous goal");
            }

            var counts = new int[4];
            foreach (var s in seq) counts[s]++;
            foreach (var c in counts) Assert.Greater(c, 20, "every endpoint is used");
        }

        [Test]
        public void SingleEndpointIsAlwaysChosen()
        {
            CollectionAssert.AreEqual(new[] { 0, 0, 0 }, GoalSequence.Preview(3, 1, 3));
        }
    }

    public class ScoringTests
    {
        static TrialScore Finished(float dist) =>
            TrialScoring.Score(new Vector2(dist, 0f), Vector2.zero, true, false, false, false, false);

        [Test]
        public void SuccessWithinPointThreeMetres()
        {
            Assert.AreEqual(TrialOutcome.SUCCESS, Finished(0f).Outcome);
            Assert.AreEqual(TrialOutcome.SUCCESS, Finished(0.29f).Outcome);
            Assert.AreEqual(TrialOutcome.SUCCESS, Finished(0.3f).Outcome);
            Assert.AreEqual(FailureReason.none, Finished(0.3f).Reason);
        }

        [Test]
        public void BeyondPointThreeMetresIsWrongGoal()
        {
            var s = Finished(0.31f);
            Assert.AreEqual(TrialOutcome.FAILURE, s.Outcome);
            Assert.AreEqual(FailureReason.wrong_goal, s.Reason);
            Assert.AreEqual(FailureReason.wrong_goal, Finished(12f).Reason);
            StringAssert.Contains("0.310", s.Detail); // invariant culture: a dot, never a comma
        }

        [Test]
        public void FailureReasonsHavePriority()
        {
            var at = Vector2.zero;
            Assert.AreEqual(FailureReason.collision, TrialScoring.Score(at, at, true, true, true, true, true).Reason);
            Assert.AreEqual(FailureReason.stuck, TrialScoring.Score(at, at, true, false, true, true, true).Reason);
            Assert.AreEqual(FailureReason.timeout, TrialScoring.Score(at, at, true, false, false, true, true).Reason);
            Assert.AreEqual(FailureReason.aborted, TrialScoring.Score(at, at, true, false, false, false, true, "unclear").Reason);
            Assert.AreEqual("unclear", TrialScoring.Score(at, at, true, false, false, false, true, "unclear").Detail);
            Assert.AreEqual(FailureReason.timeout, TrialScoring.Score(at, at, false, false, false, false, false).Reason,
                "at B but never finished (still moving) is not a success");
        }

        [Test]
        public void SafetyCorridorRule()
        {
            Vector3 o = Vector3.zero, f = Vector3.forward, r = Vector3.right;
            Assert.IsTrue(RobotBrain.InPath(o, f, r, new Vector3(0.2f, 0f, 1.0f), 1.2f, 0.6f));
            Assert.IsFalse(RobotBrain.InPath(o, f, r, new Vector3(0f, 0f, 2.0f), 1.2f, 0.6f), "the worker at the 2.0 m approach distance");
            Assert.IsFalse(RobotBrain.InPath(o, f, r, new Vector3(0.8f, 0f, 0.5f), 1.2f, 0.6f), "beside the corridor");
            Assert.IsFalse(RobotBrain.InPath(o, f, r, new Vector3(0f, 0f, -0.5f), 1.2f, 0.6f), "behind the robot");
        }

        [Test]
        public void WatchdogSilenceRule()
        {
            Assert.IsFalse(PythonLinkWatchdog.IsSilent(0.29f, 0.3f));
            Assert.IsFalse(PythonLinkWatchdog.IsSilent(0.3f, 0.3f));
            Assert.IsTrue(PythonLinkWatchdog.IsSilent(0.31f, 0.3f));
        }

        [Test]
        public void ConfigDefaultsMatchTheSpec()
        {
            var c = new HriConfig();
            Assert.AreEqual(0.3f, c.trials.success_radius_m);
            Assert.AreEqual(2.0f, c.brain.approach_distance_m);
            Assert.AreEqual(1.0f, c.brain.gesture_hold_s);
            Assert.AreEqual(2, c.brain.max_asks);
            Assert.AreEqual(0.3f, c.link.watchdog_s);
            Assert.AreEqual(0.1f, c.telemetry.interval_s);
            Assert.AreEqual(730, c.cameras.gesture_width_px);
            Assert.AreEqual(530, c.cameras.gesture_height_px);
            Assert.AreEqual(60f, c.cameras.gesture_vfov_deg);
            Assert.Less(c.brain.safety_stop_distance_m, c.brain.approach_distance_m);
            Assert.AreNotEqual(c.trials.dev_seed, c.trials.final_seed);
        }
    }

    public class GestureDialogTests
    {
        [Test]
        public void SameAnswerHeldForOneSecondIsAccepted()
        {
            var d = new GestureDialog(1.0f, 5f, 2);
            d.BeginAsk(0f);
            Assert.AreEqual(DialogEvent.Pending, d.Update(GestureCommand.LEFT, 0.0f));
            Assert.AreEqual(DialogEvent.Pending, d.Update(GestureCommand.LEFT, 0.5f));
            Assert.AreEqual(DialogEvent.Pending, d.Update(GestureCommand.LEFT, 0.98f));
            Assert.AreEqual(DialogEvent.Accepted, d.Update(GestureCommand.LEFT, 1.0f));
            Assert.AreEqual(GestureCommand.LEFT, d.Accepted);
        }

        [Test]
        public void ChangeOrNoneRestartsTheHold()
        {
            var d = new GestureDialog(1.0f, 5f, 2);
            d.BeginAsk(0f);
            d.Update(GestureCommand.LEFT, 0f);
            d.Update(GestureCommand.LEFT, 0.9f);
            Assert.AreEqual(DialogEvent.Pending, d.Update(GestureCommand.FORWARD_LEFT, 1.0f), "between two directions");
            Assert.AreEqual(DialogEvent.Pending, d.Update(GestureCommand.FORWARD_LEFT, 1.9f));
            Assert.AreEqual(DialogEvent.Pending, d.Update(GestureCommand.NONE, 1.95f));
            Assert.AreEqual(DialogEvent.Pending, d.Update(GestureCommand.FORWARD_LEFT, 2.0f));
            Assert.AreEqual(DialogEvent.Pending, d.Update(GestureCommand.FORWARD_LEFT, 2.9f));
            Assert.AreEqual(DialogEvent.Accepted, d.Update(GestureCommand.FORWARD_LEFT, 3.0f));
            Assert.AreEqual(GestureCommand.FORWARD_LEFT, d.Accepted);
        }

        [Test]
        public void StopIsNeverAnAnswer()
        {
            var d = new GestureDialog(1.0f, 5f, 2);
            d.BeginAsk(0f);
            for (int i = 0; i < 20; i++) Assert.AreEqual(DialogEvent.Pending, d.Update(GestureCommand.STOP, i * 0.1f));
        }

        [Test]
        public void UnclearAsksOnceMoreThenAborts()
        {
            var d = new GestureDialog(1.0f, 5f, 2);
            d.BeginAsk(0f);
            DialogEvent e = DialogEvent.Pending;
            for (int i = 0; i <= 300 && e == DialogEvent.Pending; i++) e = d.Update(GestureCommand.NONE, i * 0.02f);
            Assert.AreEqual(DialogEvent.AskAgain, e, "first unclear answer: ask once more");
            Assert.AreEqual(1, d.AskCount);

            d.BeginAsk(6f);
            e = DialogEvent.Pending;
            for (int i = 0; i <= 300 && e == DialogEvent.Pending; i++) e = d.Update(GestureCommand.NONE, 6f + i * 0.02f);
            Assert.AreEqual(DialogEvent.Abort, e, "second unclear answer: abort");
            Assert.AreEqual(2, d.AskCount);
            Assert.AreEqual(GestureCommand.NONE, d.Accepted);
        }

        [Test]
        public void AnswerOnTheSecondAskIsAccepted()
        {
            var d = new GestureDialog(1.0f, 5f, 2);
            d.BeginAsk(0f);
            Assert.AreEqual(DialogEvent.AskAgain, d.Update(GestureCommand.NONE, 5f));
            d.BeginAsk(5.5f);
            d.Update(GestureCommand.RIGHT, 6f);
            Assert.AreEqual(DialogEvent.Accepted, d.Update(GestureCommand.RIGHT, 7f));
            Assert.AreEqual(GestureCommand.RIGHT, d.Accepted);
        }

        [Test]
        public void DirectionWithoutBranchCountsAsUnclear()
        {
            var d = new GestureDialog(1.0f, 5f, 2);
            d.BeginAsk(0f);
            Assert.AreEqual(DialogEvent.AskAgain, d.Reject());
            d.BeginAsk(1f);
            Assert.AreEqual(DialogEvent.Abort, d.Reject());
        }

        [Test]
        public void ResetStartsANewJunction()
        {
            var d = new GestureDialog(1.0f, 5f, 2);
            d.BeginAsk(0f);
            d.BeginAsk(1f);
            d.Reset();
            Assert.AreEqual(0, d.AskCount);
            d.BeginAsk(2f);
            Assert.AreEqual(DialogEvent.AskAgain, d.Reject());
        }
    }

    public class PurePursuitTests
    {
        static PurePursuit.Settings S() => new PurePursuit.Settings
        {
            MaxSpeed = 1f, MaxTurnRateDeg = 60f, LookAhead = 0.8f, RotateInPlaceDeg = 60f, TurnGain = 2f, Decel = 0.5f,
            StopDistance = 0.1f,
        };

        [Test]
        public void StraightPathDrivesStraight()
        {
            int seg = 0;
            var r = PurePursuit.Step(Vector2.zero, 0f, new[] { Vector2.zero, new Vector2(0f, 10f) }, ref seg, S());
            Assert.AreEqual(1f, r.V, 1e-3f);
            Assert.AreEqual(0f, r.WDeg, 1e-3f);
        }

        [Test]
        public void TargetToTheRightTurnsRight()
        {
            int seg = 0;
            var r = PurePursuit.Step(Vector2.zero, 0f, new[] { Vector2.zero, new Vector2(0.5f, 10f) }, ref seg, S());
            Assert.Greater(r.WDeg, 0f);
        }

        [Test]
        public void SharpTurnRotatesInPlace()
        {
            int seg = 0;
            var r = PurePursuit.Step(Vector2.zero, 0f, new[] { Vector2.zero, new Vector2(-5f, 0f) }, ref seg, S());
            Assert.AreEqual(0f, r.V);
            Assert.Less(r.WDeg, 0f, "target on the left: turn left");
        }

        [Test]
        public void SlowsDownBeforeTheGoalAndArrives()
        {
            int seg = 0;
            var path = new[] { Vector2.zero, new Vector2(0f, 10f) };
            var near = PurePursuit.Step(new Vector2(0f, 9.8f), 0f, path, ref seg, S());
            Assert.Less(near.V, 0.5f);
            var at = PurePursuit.Step(new Vector2(0f, 9.95f), 0f, path, ref seg, S());
            Assert.IsTrue(at.Arrived);
        }
    }
}
