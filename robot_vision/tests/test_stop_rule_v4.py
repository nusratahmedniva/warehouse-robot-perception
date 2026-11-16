"""check_stop_rule_v4.py (AUDIT.md 16.18): the runs and true STOPs read from truth, criteria (a) to (c) and the declared order of the fallbacks on hand-made
numbers, and whole checks on tiny synthetic zips (no real data, no models): the candidate passes; the candidate and fallback (i) fail (a) and fallback (ii)
passes; the candidate meets (a) but fails (b) so no fallback is tried; a test look stops everything; the reader is left as it was."""

import ast
import json
import sys
import tempfile
import unittest
import zipfile
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "tests"))

import analyse_false_stop_v4 as fs  # noqa: E402
import check_stop_rule_v4 as ck  # noqa: E402
import commander_v4 as cm  # noqa: E402
import gesture_motion as gm  # noqa: E402
import v4_synth as vs  # noqa: E402

CFG = ck.load_config()
RC, CC = gm.load_config(), cm.load_config()


def row(t, cmd, phase="holding", worker=1, look="sunbox_m1", clip=None, arm="right"):
    return {"time_s": t, "worker_id": worker, "look": look, "x": 0.0, "z": 5.0, "true_command": cmd, "point_angle_deg": -1, "arm": arm, "phase": phase,
            "is_commander": True, "clip": clip if clip is not None else ("" if cmd == "NONE" else {"STOP": "stop_ik_01", "PROCEED": "proceed_ik_01",
                                                                                                      "POINT": "point_ik_01", "WAIT": "wait_ik_01"}[cmd])}


class RunKindTests(unittest.TestCase):
    def kind(self, rows_by_worker):
        return ck.run_kind(rows_by_worker, CFG)

    def test_the_item_of_a_run_is_read_from_its_truth(self):
        self.assertEqual(self.kind({1: [row(0, "STOP")]}), "held_stop")
        self.assertEqual(self.kind({1: [row(0, "PROCEED"), row(9, "STOP")]}), "driving_stop")          # a PROCEED starts the drive, then STOP
        for c in ("POINT", "WAIT", "PROCEED"):
            self.assertEqual(self.kind({1: [row(0, c)]}), f"negative_{c}")
        self.assertEqual(self.kind({1: [row(0, "PROCEED")], 2: [row(0, "NONE", "idle", worker=2)]}), "idle_pass")
        self.assertEqual(self.kind({1: [row(0, "NONE", "idle")]}), "other")
        self.assertEqual(self.kind({1: [row(0, "STOP", "returning")]}), "other")                      # only shown phases count

    def test_a_true_stop_is_a_contiguous_run_of_shown_rows(self):
        rows = [row(t * 0.05, "STOP") for t in range(20)] + [row(1.0 + t * 0.05, "STOP", "returning") for t in range(10)] + \
               [row(5.0 + t * 0.05, "STOP", "gesturing") for t in range(10)]
        segs = ck.stop_segments({1: rows}, CFG, "S", 3, "held_stop")
        self.assertEqual([(s["onset"], round(s["end"], 2)) for s in segs], [(0.0, 0.95), (5.0, 5.45)])      # a gap starts a second STOP
        self.assertEqual((segs[0]["session"], segs[0]["run"], segs[0]["worker"], segs[0]["look"], segs[0]["arm"], segs[0]["clip"]), ("S", 3, 1, "sunbox_m1", "right", "stop_ik_01"))
        self.assertEqual(ck.stop_segments({1: [row(0, "PROCEED")]}, CFG, "S", 1, "negative_PROCEED"), [])


def fake(stops=2, read=2, b=None, idle=0, held=None, driving=None):
    """A scored rule with only the fields verdict() reads."""
    b = b or {"PROCEED": (0, 0), "POINT": (0, 0), "WAIT": (0, 0)}
    items = {c: {"frames": 50, "stop_frames": f, "episodes": e} for c, (f, e) in b.items()}
    return {"a_summary": {"stops": stops, "read_within": read, "held": {"stops": stops, "read_within": read}, "driving": {"stops": 0, "read_within": 0},
                          "latency_median_s": None, "latency_max_s": None},
            "b_items": items, "b_total": {k: sum(i[k] for i in items.values()) for k in ("frames", "stop_frames", "episodes")},
            "c_idle_frames": {"frames": 100, "stop_frames": idle, "episodes": idle}}


CURRENT = fake(b={"PROCEED": (30, 5), "POINT": (0, 0), "WAIT": (10, 2)})


class CriteriaTests(unittest.TestCase):
    def test_a_is_n_of_n(self):
        self.assertTrue(ck.verdict(fake(stops=40, read=40), CURRENT)["a"]["met"])
        v = ck.verdict(fake(stops=40, read=39), CURRENT)["a"]
        self.assertEqual((v["met"], v["n"], v["read_within"]), (False, 40, 39))
        self.assertFalse(ck.verdict(fake(stops=0, read=0), CURRENT)["a"]["met"])                      # no STOP in the data: nothing is met

    def test_b_needs_fewer_in_both_counts_and_no_category_with_more(self):
        better = fake(b={"PROCEED": (3, 1), "POINT": (0, 0), "WAIT": (0, 0)})
        v = ck.verdict(better, CURRENT)["b"]
        self.assertEqual((v["met"], v["frames"], v["episodes"], v["no_category_with_more"]), (True, [3, 40], [1, 7], True))
        worse_in_one = fake(b={"PROCEED": (1, 1), "POINT": (1, 1), "WAIT": (0, 0)})                    # POINT 0 -> 1: a category with more
        v = ck.verdict(worse_in_one, CURRENT)["b"]
        self.assertEqual((v["met"], v["no_category_with_more"]), (False, False))
        same_frames = fake(b={"PROCEED": (30, 4), "POINT": (0, 0), "WAIT": (10, 1)})                   # fewer episodes but not fewer frames
        self.assertFalse(ck.verdict(same_frames, CURRENT)["b"]["met"])
        none_at_all = ck.verdict(better, fake())["b"]                                                  # the current rule has no false STOP: nothing to be fewer than
        self.assertEqual((none_at_all["met"], none_at_all["testable"]), (False, False))

    def test_c_is_zero_stops_on_every_idle_frame(self):
        self.assertTrue(ck.verdict(fake(idle=0), CURRENT)["c"]["met"])
        v = ck.verdict(fake(idle=1), CURRENT)["c"]
        self.assertEqual((v["met"], v["stop_frames"]), (False, 1))


class DecisionOrderTests(unittest.TestCase):
    def scored(self, **rules):
        good = fake(b={"PROCEED": (1, 1), "POINT": (0, 0), "WAIT": (0, 0)})
        out = {"current": CURRENT, "candidate": good, "fallback_i": good, "fallback_ii": good}
        out.update(rules)
        return out

    def test_the_candidate_alone_when_it_meets_everything(self):
        d = ck.decide(self.scored(), CFG)
        self.assertEqual((d["tried"], d["not_tried"], d["outcome"]), (["candidate"], ["fallback_i", "fallback_ii"], "candidate meets (a), (b) and (c)"))

    def test_the_fallbacks_follow_in_order_only_after_a_failed_a(self):
        d = ck.decide(self.scored(candidate=fake(stops=40, read=38)), CFG)
        self.assertEqual((d["tried"], d["outcome"]), (["candidate", "fallback_i"], "fallback_i meets (a), (b) and (c)"))
        d = ck.decide(self.scored(candidate=fake(stops=40, read=38), fallback_i=fake(stops=40, read=39)), CFG)
        self.assertEqual((d["tried"], d["outcome"]), (["candidate", "fallback_i", "fallback_ii"], "fallback_ii meets (a), (b) and (c)"))
        d = ck.decide(self.scored(candidate=fake(stops=40, read=38), fallback_i=fake(stops=40, read=39), fallback_ii=fake(stops=40, read=1)), CFG)
        self.assertEqual(d["outcome"], "none of the tried rules meets (a), (b) and (c)")

    def test_no_fallback_when_a_is_met_and_b_or_c_is_not(self):
        for bad in (fake(b={"PROCEED": (30, 5), "POINT": (0, 0), "WAIT": (10, 2)}), fake(idle=3)):         # (b) not fewer; (c) an idle STOP
            d = ck.decide(self.scored(candidate=bad), CFG)
            self.assertEqual((d["tried"], d["not_tried"]), (["candidate"], ["fallback_i", "fallback_ii"]))
            self.assertEqual(d["outcome"], "none of the tried rules meets (a), (b) and (c)")


class DeclaredRulesTests(unittest.TestCase):
    def test_the_rules_are_exactly_those_declared_in_audit_16_18(self):
        self.assertEqual(CFG["rules"], {"current": {}, "candidate": {"spread": 1.3, "static": "arm_moving", "raised": True},
                                        "fallback_i": {"spread": 1.3, "static": "speed_stop_window", "raised": True}, "fallback_ii": {"spread": 1.3, "raised": True}})
        self.assertEqual(CFG["order"], ["candidate", "fallback_i", "fallback_ii"])
        self.assertTrue(all("palm" not in c for c in CFG["rules"].values()))                              # palm direction is not used (16.17 item 3)
        self.assertEqual((CFG["within_s"], CFG["episode_gap_s"]), (1.0, 0.5))
        base = fs.load_config()
        self.assertEqual((CFG["match_bearing_deg"], CFG["truth_join_max_s"], CFG["shown_phases"]), (base["match_bearing_deg"], base["truth_join_max_s"], base["shown_phases"]))
        self.assertEqual((RC["motion"]["still_speed_max"], RC["motion"]["motion_path_min"], RC["window"]["stop_window_s"]), (0.4, 0.4, 0.3))   # the reader's own values
        self.assertEqual(CFG["plan"]["S1"], {"held_stop": 20, "driving_stop": 6, "negative_POINT": 12, "negative_PROCEED": 12, "negative_WAIT": 12, "idle_pass": 2})
        self.assertEqual(CFG["plan"]["S2"], {"held_stop": 8, "driving_stop": 6})

    def test_the_check_config_is_outside_the_freeze_list(self):
        import freeze_v4 as fz
        self.assertNotIn("robot_vision/configs/v4/experiments/stop_rule_check.json", fz.config_files())


# ---------------------------------------------------------------- a whole check on a tiny synthetic zip

def frame(t, i, raised, swing):
    arm = (-0.3 + (0.6 * np.sin(i * 1.2) if swing else 0.0), -1.0, 0.0) if raised else vs.DOWN
    kp, conf = vs.body(z0=5.0, right=arm)
    h = vs.hand(kp[gm.ARMS["right"][2]], axis=(0.0, -1.0), z=5.0, category="Open_Palm", fan_deg=18.0)
    return {"cam": "pan_tilt", "time_s": round(t, 4), "frame_index": i, "pose": {"x": 0.0, "z": 0.0, "yaw_deg": 0.0}, "pan_deg": 0.0, "tilt_deg": 0.0,
            "vertical_fov_deg": 60.0, "fx": vs.FX, "fy": vs.FY, "cx": vs.CX, "cy": vs.CY, "width": vs.WIDTH, "height": vs.HEIGHT,
            "people": [{"track_id": 1, "box": [float(kp[:, 0].min()) - 20, float(kp[:, 1].min()) - 20, float(kp[:, 0].max()) + 20, float(kp[:, 1].max()) + 20],
                        "kp": [[float(x), float(y), 1.0] for x, y in kp]}],
            "hands": [{"track_id": 1, "category": "Open_Palm", "score": 0.9, "handedness": "Right", "lm": h.landmarks_px.tolist(), "world": None, "box": list(h.box),
                       "wrist": list(h.wrist)}]}


def zip_of(tmp: Path, stop_swings: bool = False, negative_raised: bool = False, look: str = "sunbox_m1") -> Path:
    """Run 1: a held STOP, the arm raised and (stop_swings) swinging. Run 2: 1 s idle with an open hand hanging, then a PROCEED (the arm hangs, or is
    raised when negative_raised). Run 2 is on the session clock from t = 10 s."""
    frames, truth1, truth2 = [], [], []
    for i in range(25):
        frames.append(frame(i * 0.1, i, True, stop_swings))
    for k in range(50):
        truth1.append(row(k * 0.05, "STOP", look=look))
    for i in range(25):
        frames.append(frame(10 + i * 0.1, i, negative_raised, False))
    for k in range(50):
        t = 10 + k * 0.05
        truth2.append(row(t, "NONE", "idle", look=look) if k < 20 else row(t, "PROCEED", look=look))
    p = tmp / "logs.zip"
    with zipfile.ZipFile(p, "w") as z:
        z.writestr("logs/bridge_x/model_outputs.jsonl", "".join(json.dumps(f) + "\n" for f in frames))
        z.writestr("logs/bridge_x/decisions.csv", "trial,time_s,state,x,z,yaw_deg,v,omega,v_cmd,gesture,safety\n"
                   "1,0.3,read (stopped: STOP gesture),0,0,0,0.0,0,0,STOP,STOP gesture\n2,10.3,read (stopped: STOP gesture),0,0,0,0.0,0,0,STOP,STOP gesture\n")
        z.writestr("logs/trials_x/run_001/truth.jsonl", "".join(json.dumps(r) + "\n" for r in truth1))
        z.writestr("logs/trials_x/run_002/truth.jsonl", "".join(json.dumps(r) + "\n" for r in truth2))
    return p


CFG_S = {**CFG, "sessions": {"S": {"bridge": "bridge_x", "unity": "trials_x", "what": "synthetic"}},
         "plan": {"S": {"held_stop": 1, "negative_PROCEED": 1}}}


class WholeCheckTests(unittest.TestCase):
    def run_check(self, **kw):
        with tempfile.TemporaryDirectory() as t:
            p = zip_of(Path(t), **kw)
            before = sorted(Path(t).iterdir())
            rep = ck.check(fs.Logs(p), CFG_S, RC, CC)
            self.assertEqual(sorted(Path(t).iterdir()), before)                                       # read in place: nothing extracted or written
            return rep

    def test_the_candidate_passes_when_the_stop_is_held_still_and_raised(self):
        rep = self.run_check()
        self.assertTrue(rep["guard_all_development"])
        self.assertEqual(rep["stops_found"], {"total": 1, "held": 1, "driving": 0})
        self.assertTrue(rep["plan_check"]["S"]["as_planned"])
        cur, cand = rep["rules"]["current"], rep["rules"]["candidate"]
        self.assertEqual(cur["a_summary"]["read_within"], 1)
        self.assertLessEqual(cur["a"][0]["latency_s"], 0.5)
        self.assertGreater(cur["b_total"]["stop_frames"], 10)                                         # the hanging open hand during the PROCEED reads STOP
        self.assertGreater(cur["c_idle_frames"]["stop_frames"], 5)                                    # ... and during the idle second
        self.assertEqual((cand["b_total"]["stop_frames"], cand["c_idle_frames"]["stop_frames"]), (0, 0))
        d = rep["decision"]
        self.assertEqual((d["tried"], d["outcome"]), (["candidate"], "candidate meets (a), (b) and (c)"))
        self.assertFalse(rep["reader_changed"])
        self.assertEqual(rep["live_robot_stop_runs"]["held_stop"], {"runs": 1, "with_a_stop": 1})
        self.assertEqual(rep["replay_check"]["S"]["decision_STOP_rows_without_a_replayed_STOP_in_the_0.6_s_before"], 0)    # the replay reproduces the live STOP rows
        self.assertGreater(cur["a"][0]["frames_with_a_hand_in_the_window"], 5)                        # the hand was there: a late reading is not a missing hand
        listed = cur["c_idle_stop_frames_listed"]
        self.assertEqual(len(listed), cur["c_idle_frames"]["stop_frames"])                              # every idle STOP of a rule is listed with run, time and worker
        self.assertTrue(all(x["run"] == 2 and 10.0 <= x["t"] < 11.0 for x in listed))
        self.assertEqual(cand["c_idle_stop_frames_listed"], [])
        md = ck.markdown(rep, CFG_S)
        for word in ("not tried", "Outcome (declared order", "candidate meets (a), (b) and (c)", "No reader value was changed", "Accepted STOPs on idle frames (c)",
                     "Frames with a hand detected"):
            self.assertIn(word, md)

    def test_a_swinging_stop_fails_the_candidate_and_fallback_i_and_fallback_ii_passes(self):
        rep = self.run_check(stop_swings=True)
        v = rep["decision"]["verdicts"]
        self.assertEqual(rep["rules"]["current"]["a_summary"]["read_within"], 1)                      # the live rule reads it (it needs no stillness)
        self.assertEqual((v["candidate"]["a"]["met"], v["fallback_i"]["a"]["met"], v["fallback_ii"]["a"]["met"]), (False, False, True))
        self.assertEqual(rep["decision"]["tried"], ["candidate", "fallback_i", "fallback_ii"])
        self.assertEqual(rep["decision"]["outcome"], "fallback_ii meets (a), (b) and (c)")
        self.assertIsNone(rep["rules"]["candidate"]["a"][0]["latency_s"])                             # not read within 1.0 s: no latency
        self.assertIsNone(rep["rules"]["candidate"]["a"][0]["first_reading_s_any_time_in_the_segment"])        # and never read in the segment: "never" in the table
        self.assertIn("never", ck.markdown(rep, CFG_S))

    def test_no_fallback_when_the_candidate_meets_a_but_fails_b(self):
        rep = self.run_check(negative_raised=True)                                                    # the PROCEED is shown with a raised, still, open hand
        d = rep["decision"]
        self.assertTrue(d["verdicts"]["candidate"]["a"]["met"])
        self.assertFalse(d["verdicts"]["candidate"]["b"]["met"])                                      # a raised still open hand is a STOP for every rule
        self.assertEqual((d["tried"], d["not_tried"]), (["candidate"], ["fallback_i", "fallback_ii"]))
        self.assertEqual(d["outcome"], "none of the tried rules meets (a), (b) and (c)")
        self.assertEqual(rep["rules"]["fallback_i"]["b_total"]["stop_frames"], rep["rules"]["current"]["b_total"]["stop_frames"])   # computed, decides nothing

    def test_a_test_look_in_the_zip_stops_everything(self):
        with tempfile.TemporaryDirectory() as t:
            p = zip_of(Path(t), look="sunbox_f2")
            with self.assertRaises(SystemExit):
                ck.check(fs.Logs(p), CFG_S, RC, CC)

    def test_the_reader_is_left_as_it_was(self):
        before = (gm.frame_flags, gm._arm_window)
        self.run_check()
        self.assertEqual((gm.frame_flags, gm._arm_window), before)
        self.assertEqual(json.loads((ROOT / "configs/v4/gesture_reader.json").read_text(encoding="utf-8"))["window"]["stop_window_s"], 0.3)


class IsolationTests(unittest.TestCase):
    def test_inference_never_imports_the_check(self):
        offenders = []
        for p in ROOT.rglob("*.py"):
            rel = p.relative_to(ROOT)
            if ".venv" in rel.parts or rel.parts[0] == "tests" or rel.name == "check_stop_rule_v4.py":
                continue
            tree = ast.parse(p.read_text(encoding="utf-8"))
            mods = {a.name.split(".")[0] for n in ast.walk(tree) if isinstance(n, ast.Import) for a in n.names}
            mods |= {n.module.split(".")[0] for n in ast.walk(tree) if isinstance(n, ast.ImportFrom) and n.module}
            if "check_stop_rule_v4" in mods:
                offenders.append(str(rel))
        self.assertEqual(offenders, [])


if __name__ == "__main__":
    unittest.main()
