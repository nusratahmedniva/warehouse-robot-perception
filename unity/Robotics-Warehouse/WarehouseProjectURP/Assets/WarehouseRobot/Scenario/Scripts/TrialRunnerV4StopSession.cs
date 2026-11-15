using System.Collections.Generic;
using UnityEngine;
using WarehouseAvatar;
using WarehouseHRI;

namespace WarehouseRobot.Scenario
{
    /// <summary>
    /// The STOP session (scenario stop_session; Avatar/Config/experiments_ab.md section 13 part B, declared 2026-11-15 before it was built):
    /// a development session of the Task 2 runner whose runs each record ONE declared item (<see cref="StopSessionPlan"/>), for Anisha's
    /// check of the candidate false-STOP rule (AUDIT.md 16.16 decision 2, 16.17 item 3). Selected by TrialPlayV4 -workersConfig
    /// Assets/WarehouseRobot/Avatar/Config/sessions/dev_stop_session.json; refused with -finalSetting or -experiment.
    /// - held item (STOP, or a negative POINT / PROCEED / WAIT): the worker at A's stand shows it at the first ask (after the question, as
    ///   every answer), with the item's arm and clip; a POINT points point_body_azimuth_deg to the arm's own side. It answers no later ask.
    /// - driving STOP: the worker answers every ask at A with PROCEED (the drive's start, not an item), is moved once idle to J1's stand
    ///   (as in stop_while_driving) and shows STOP when Python's state is navigate, it has noticed the robot and the robot is
    ///   driving_stop_distance_m from it.
    /// - idle pass: the worker answers at A with PROCEED and is not moved; a second worker of the same look (worker_id commander + 1, never
    ///   gestures) stands at idle_stand, checked like a bystander stand.
    /// A run ends (<see cref="StopSessionEnd"/>) settle_s after the item's gesture has returned to idle, idle_passed_m after the robot has
    /// passed the idle worker along the road, or as ITEM_MISSED item_timeout_s after its start (never re-recorded); collision and stuck end
    /// it as always; Python's done / aborted do not. The robot really reacts (the bridge server in guide mode, the current reader).
    /// </summary>
    public partial class TrialRunnerV4
    {
        const string StopItemDone = "item_done", StopItemMissed = "item_missed";
        readonly List<StopSessionItem> stopItems = new List<StopSessionItem>();
        StopSessionItem stopItem;
        WorkerV4 idleWorker;
        Vector3 idleStandPosition, idleRoadDirection;
        Quaternion idleStandRotation;
        bool itemRequested, itemBegan;
        float itemReturnedAt = -1f, idleClosest = float.PositiveInfinity;
        string stopNote = "";

        bool StopSession => wcfg != null && wcfg.scenario == TrialWorkersConfig.ScenarioStopSession;

        /// <summary>The commander is moved to the junctions the robot is sent to in every session except a STOP session's held items and
        /// idle passes (there it stays at A).</summary>
        bool StopSessionMovesCommander => !StopSession || (stopItem != null && stopItem.Kind == StopItemKind.DrivingStop);

        string StopItemText(StopSessionItem item) =>
            item == null ? "-" : item.Describe() + (item.Kind == StopItemKind.IdlePass ? ""
                : ", clip " + StopSessionPlan.Clip(plans[item.Run - 1].AllowedFor(item.Command), item.Repetition));

        bool SetupStopSession(out string error)
        {
            error = null;
            stopItems.Clear();
            if (!StopSession) return true;
            if (Final || Experiment)
                return Fail(out error, "the stop_session scenario is a development session of the Task 2 runner: refused with -finalSetting or -experiment");
            stopItems.AddRange(StopSessionPlan.Items(wcfg.stop_session));
            return true;
        }

        /// <summary>The idle worker's stand (bystander rules of the session config) and the direction of its road.</summary>
        bool CheckIdleStand(out string error)
        {
            error = null;
            var c = wcfg.stop_session;
            if (c.idle_pass_per_look <= 0) return true;
            var s = c.idle_stand;
            string label = $"idle worker ({s.junction}, ahead {s.ahead_m.ToString("0.00", Inv)} m, right {s.right_m.ToString("0.00", Inv)} m)";
            if (!CheckStand(label, s, wcfg.bystanders, out idleStandPosition, out idleStandRotation, out error)) return false;
            var j = nodes[s.junction];
            idleRoadDirection = Vector3.ProjectOnPlane(j.Position - ArrivalNode(j).Position, Vector3.up).normalized;
            Debug.Log($"[TrialRunnerV4] STOP session: {stopItems.Count} items; idle stand ({idleStandPosition.x.ToString("0.00", Inv)}, {idleStandPosition.z.ToString("0.00", Inv)})");
            return true;
        }

        /// <summary>Once per run, after the commander is spawned at A: the run's item, and the idle worker of an idle pass.</summary>
        bool ResetStopSessionRun(int run, out string error)
        {
            error = null;
            stopItem = stopItems[run - 1];
            itemRequested = itemBegan = false;
            itemReturnedAt = -1f;
            idleClosest = float.PositiveInfinity;
            stopNote = "not shown";
            idleWorker = null;
            if (stopItem.Kind != StopItemKind.IdlePass) return true;
            idleWorker = Spawn("WorkerV4_Idle", stopItem.Look, wcfg.commander_worker_id + 1, idleStandPosition, idleStandRotation, run, out error);
            if (idleWorker == null) return false;
            bystanders.Add(idleWorker);
            return true;
        }

        /// <summary>Every frame of a STOP-session run (after the question watch and the commander's move).</summary>
        void UpdateStopSession()
        {
            var item = stopItem;
            if (item == null) return;
            bool atStart = commanderAt != null && commanderAt.name == meta.start;
            commander.SetQuestionVisible(question.Visible);
            // a pending answer (not started) belongs to the question that is gone; a started gesture continues
            if (!question.Visible && commander.Busy && commander.Phase == WorkerPhase.Idle)
            {
                commander.CancelPending();
                if (item.Kind == StopItemKind.Held && !itemBegan) itemRequested = false;
            }
            bool newAsk = question.Visible && question.Ask > servedAsk;
            if (item.Kind == StopItemKind.Held)
            {
                if (!itemRequested && newAsk && atStart && !commander.Busy)
                {
                    servedAsk = question.Ask;
                    itemRequested = ShowItem(item, false, $"item {item.Describe()}");
                }
            }
            else
            {
                // the drive: every ask at A is answered with PROCEED toward the FORWARD branch (not an item)
                if (newAsk && atStart && !commander.Busy && moveTo == null)
                {
                    servedAsk = question.Ask;
                    var next = commanderAt.Next(GestureCommand.FORWARD);
                    if (next != null) Show(wcfg.forward_command, TrialWorkerGeometry.BranchDirection(commanderAt.Position, next.Position), false, "the drive's start, not an item");
                }
                if (item.Kind == StopItemKind.DrivingStop && !itemRequested && !atStart && commanderAt != null && moveTo == null && !commander.Busy)
                {
                    string st = bridge.State ?? "";
                    Vector3 d = commander.transform.position - robot.transform.position;
                    d.y = 0f;
                    float dist = d.magnitude;
                    var band = wcfg.stop_session.driving_stop_distance_m;
                    if (st.StartsWith("navigate") && commander.Noticed && dist >= band[0] && dist <= band[1])
                    {
                        itemRequested = ShowItem(item, true, $"item {item.Describe()}, STOP while driving, {dist.ToString("0.0", Inv)} m");
                        if (itemRequested)
                            stopNote = $"STOP requested at {F(dist, "0.00")} m from the robot, robot v {F(robot.Drive.V, "0.00")} m/s, Python {st}";
                    }
                }
            }
            if (itemRequested && commander.Phase != WorkerPhase.Idle) itemBegan = true;
            if (itemBegan && !commander.Busy && itemReturnedAt < 0f) itemReturnedAt = Time.time;
        }

        /// <summary>The item's gesture, with its arm and the clip of its repetition (StopSessionPlan.Clip).</summary>
        bool ShowItem(StopSessionItem item, bool ignoreQuestion, string what)
        {
            string clip = StopSessionPlan.Clip(runPlan.AllowedFor(item.Command), item.Repetition);
            Vector3 dir = Vector3.zero;
            if (item.Command == WorkerV4Config.Point)
            {
                commander.BodyFrame(out _, out var fwd);
                float az = wcfg.stop_session.point_body_azimuth_deg * (item.Arm == "left" ? -1f : 1f);
                dir = Quaternion.AngleAxis(az, Vector3.up) * fwd;
            }
            if (!Show(item.Command, dir, ignoreQuestion, what, 0f, clip, item.Arm)) return false;
            if (item.Kind == StopItemKind.Held)
            {
                Vector3 d = commander.transform.position - robot.transform.position;
                d.y = 0f;
                stopNote = $"requested at the ask {question.Ask} at {commanderAt.name}, robot {F(d.magnitude, "0.00")} m from the worker";
            }
            return true;
        }

        /// <summary>The end of a STOP-session run: <see cref="StopItemDone"/> or <see cref="StopItemMissed"/>, or false to go on.</summary>
        bool StopSessionEnd(float now, float t0, out string end)
        {
            end = null;
            var c = wcfg.stop_session;
            if (stopItem.Kind == StopItemKind.IdlePass && idleWorker != null)
            {
                Vector3 d = robot.transform.position - idleWorker.transform.position;
                d.y = 0f;
                idleClosest = Mathf.Min(idleClosest, d.magnitude);
                if (Vector3.Dot(d, idleRoadDirection) >= c.idle_passed_m)
                {
                    stopNote = $"passed the idle worker, closest {F(idleClosest, "0.00")} m";
                    end = StopItemDone;
                    return true;
                }
            }
            else if (itemReturnedAt >= 0f && now - itemReturnedAt >= c.settle_s)
            {
                stopNote += $"; returned to idle at {F(itemReturnedAt, "0.000")}";
                end = StopItemDone;
                return true;
            }
            if (now - t0 > c.item_timeout_s)
            {
                string why = stopItem.Kind == StopItemKind.IdlePass ? $"the robot did not pass the idle worker (closest {F(idleClosest, "0.00")} m)"
                           : itemBegan ? "the gesture did not return" : itemRequested ? "requested but never started" : "never requested";
                stopNote = $"{why} within {F(c.item_timeout_s, "0")} s (Python {bridge.State})";
                end = StopItemMissed;
                return true;
            }
            return false;
        }
    }
}
