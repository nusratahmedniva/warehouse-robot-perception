"""v4 completion, Stage A (2026-11-12, Nusrat during Anisha's absence; Avatar/Config/upgrade_design.md, AUDIT.md section 15):
PROCEED and every other class on synthetic keypoints, the tilt geometry (P6), the ankle height (P1), the junction metrics
(P3), the start search on the v4 map (P7, P8), --control-config and the two zoom files (P10, P11) and the per-frame
model-output log (P12). Pure Python, no models, no Unity."""

import json
import math
import sys
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "tests"))

import commander_v4 as cm  # noqa: E402
import gesture_data as gd  # noqa: E402
import gesture_motion as gm  # noqa: E402
import hri_control as hc  # noqa: E402
import hri_control_v4 as hv  # noqa: E402
import hri_perception as hpm  # noqa: E402
import hri_sim_v4 as hs  # noqa: E402
import v4_synth as vs  # noqa: E402
from bridge import protocol as P  # noqa: E402
from bridge import server as S  # noqa: E402
from hri_sim import SimConfig  # noqa: E402

CFG = gm.load_config()
V4 = ROOT / "configs" / "v4"


# ---------------------------------------------------------------- synthetic people, also through a tilted camera

def tilted_cam(p, tilt_deg):
    """A level-frame point (x right, y down, z forward) in the frame of a camera tilted UP by tilt_deg."""
    t = math.radians(tilt_deg)
    x, y, z = p
    return np.array([x, y * math.cos(t) + z * math.sin(t), -y * math.sin(t) + z * math.cos(t)])


def body3d(x0=0.0, z0=2.0, y0=-0.2, right=vs.DOWN, right_fore=None, left=vs.DOWN):
    """17 keypoints in 3D (level camera frame) of a person facing the camera; as v4_synth.body."""
    pts = np.tile([x0, y0 + vs.TORSO, z0], (17, 1)).astype(float)
    pts[gm.NOSE] = (x0, y0 - 0.25, z0)
    pts[gm.L_EYE], pts[gm.R_EYE] = (x0 + 0.03, y0 - 0.28, z0), (x0 - 0.03, y0 - 0.28, z0)
    pts[gm.L_SHOULDER], pts[gm.R_SHOULDER] = (x0 + vs.SW / 2, y0, z0), (x0 - vs.SW / 2, y0, z0)
    pts[gm.L_HIP], pts[gm.R_HIP] = (x0 + 0.1, y0 + vs.TORSO, z0), (x0 - 0.1, y0 + vs.TORSO, z0)
    for side, d1, d2 in (("left", left, None), ("right", right, right_fore)):
        sh, el, wr = gm.ARMS[side]
        pts[el] = pts[sh] + vs.UPPER * vs.unit(d1)
        pts[wr] = pts[el] + vs.FORE * vs.unit(d2 if d2 is not None else d1)
    return pts


def project(pts, tilt_deg=0.0):
    return np.array([vs.project(tilted_cam(p, tilt_deg)) for p in pts]), np.ones(len(pts))


def swing_samples(n=25, hz=1.5, plane="vertical", amp_deg=40.0, mid_deg=20.0, dt=0.1, hands=None):
    """The right forearm swinging (elbow fixed, upper arm hanging slightly forward): 'vertical' = forward and up (PROCEED),
    'sideways' = left and right in the image plane (a wave)."""
    out = []
    for i in range(n):
        a = math.radians(mid_deg + amp_deg * math.sin(2 * math.pi * hz * i * dt))
        if plane == "vertical":
            fore = (0.0, -math.sin(a), -math.cos(a))                       # toward the camera and up
        else:
            fore = (math.sin(a - math.radians(mid_deg)), -0.6, -0.3)       # left-right, roughly level
        kp, conf = project(body3d(right=(0.0, 1.0, -0.3), right_fore=fore))
        out.append(vs.sample(i * dt, kp, conf, hands or {}))
    return out


class ProceedReaderTests(unittest.TestCase):
    def test_count_strokes_with_hysteresis(self):
        self.assertEqual(gm.count_strokes([0, 0.5, 0, 0.5, 0], 0.3), 4)
        self.assertEqual(gm.count_strokes([0, 0.1, 0, 0.1, 0], 0.3), 0)           # jitter is not a swing
        self.assertEqual(gm.count_strokes([0.2, 0.0, 0.6, 0.1, 0.6], 0.3), 3)      # the first dip is too small
        self.assertEqual(gm.count_strokes([0.0], 0.3), 0)

    def test_a_forward_up_swing_reads_proceed(self):
        s = swing_samples()
        r = gm.read_window(s, CFG, s[-1].t)
        self.assertEqual(r.command, "PROCEED", r.why)
        self.assertEqual(r.arm, "right")
        f = r.arms["right"]["proceed"]
        self.assertGreaterEqual(f["cycles"], CFG["proceed"]["cycles_min"])
        self.assertGreaterEqual(f["vertical_share"], CFG["proceed"]["vertical_share_min"])
        self.assertEqual(r.frame_class, "NONE")                       # one frame never says PROCEED
        self.assertIsNotNone(r.fit_box)

    def test_one_swing_or_a_sideways_wave_is_not_proceed(self):
        one = swing_samples(n=25, hz=0.3)                              # under one cycle in the window
        self.assertNotEqual(gm.read_window(one, CFG, one[-1].t).command, "PROCEED")
        wave = swing_samples(plane="sideways", amp_deg=50.0)
        r = gm.read_window(wave, CFG, wave[-1].t)
        self.assertNotEqual(r.command, "PROCEED")
        self.assertLess(r.arms["right"]["proceed"]["vertical_share"], CFG["proceed"]["vertical_share_min"])

    def test_the_short_window_alone_is_not_enough(self):
        s = swing_samples()
        short = [x for x in s if x.t >= s[-1].t - CFG["window"]["window_s"]]
        self.assertNotEqual(gm.read_window(short, CFG, s[-1].t).command, "PROCEED")   # fewer valid frames than 2 s needs

    def test_an_open_palm_still_overrides(self):
        def hands_for(i):
            kp, _ = project(body3d(right=(0.0, 1.0, -0.3), right_fore=(0.0, -0.5, -0.8)))
            return {"right": vs.hand(kp[gm.R_WRIST])}
        s = swing_samples()
        for i, x in enumerate(s):
            x.hands = hands_for(i)
        self.assertEqual(gm.read_window(s, CFG, s[-1].t).command, "STOP")

    def test_the_other_classes_still_read_from_the_longer_buffer(self):
        """POINT, WAIT and STOP from a buffer of read_span_s (2 s) read as from the 1 s window alone."""
        n = int(gm.read_span_s(CFG) * 10) + 1
        cases = {
            "POINT": (vs.direction(90.0, 0.0), None, None),
            "WAIT": ((0.6, 0.3, -0.75), (0.0, -1.0, 0.0), "wait"),
            "STOP": ((0.1, -0.1, -1.0), (0.0, -1.0, -0.3), "stop"),
        }
        for want, (upper, fore, hand) in cases.items():
            kp, conf = vs.body(left=upper, left_fore=fore)
            hands = {}
            if hand == "wait":
                hands = {"left": vs.hand(kp[gm.L_WRIST], extended=("index",), category="Pointing_Up", fan_deg=4.0)}
            elif hand == "stop":
                hands = {"left": vs.hand(kp[gm.L_WRIST])}
            s = [vs.sample(i * 0.1, kp, conf, hands) for i in range(n)]
            self.assertEqual(gm.read_window(s, CFG, s[-1].t).command, want, want)

    def test_commander_rule_takes_a_facing_proceed_without_a_raised_arm(self):
        r = gm.Reading("PROCEED", 0.9, "forearm swings", 1.0, arm="right", raised=False)
        r.arms = {"right": {"raised": False, "path": 0.0}}
        ch = cm.pick_commander([cm.PersonReading(3, 0.0, True, "facing", r)], cm.load_config())
        self.assertEqual(ch.commander, 3)
        r2 = gm.Reading("NONE", 0.0, "no raised arm", 1.0, raised=False)
        ch = cm.pick_commander([cm.PersonReading(4, 0.0, True, "facing", r2)], cm.load_config())
        self.assertIsNone(ch.commander)


# ---------------------------------------------------------------- tilt geometry (P6)

class TiltGeometryTests(unittest.TestCase):
    def test_level_vector_rotates_the_optical_axis_up(self):
        v = gm.level_vector((0.0, 0.0, 1.0), 30.0)
        self.assertAlmostEqual(math.degrees(math.atan2(-v[1], v[2])), 30.0, places=9)
        np.testing.assert_allclose(gm.level_vector((1.0, 2.0, 3.0), 0.0), (1.0, 2.0, 3.0))

    def test_pixel_azimuth_is_tilt_corrected(self):
        p = np.array([0.8, -0.9, 2.0])                    # level frame: azimuth atan2(0.8, 2.0)
        for t in (0.0, 15.0, 30.0):
            u, v = vs.project(tilted_cam(p, t))
            az = gm.pixel_azimuth_deg(u, v, vs.FX, vs.FY, vs.CX, vs.CY, t)
            self.assertAlmostEqual(az, math.degrees(math.atan2(0.8, 2.0)), places=6, msg=t)

    def test_point_solutions_match_the_level_camera_at_any_tilt(self):
        for az in (60.0, -70.0, 120.0):
            for elev in (0.0, 20.0):
                pts = body3d(right=vs.direction(az, elev))
                kp0, conf = project(pts, 0.0)
                ref = gm.arm_solutions(vs.sample(0.0, kp0, conf), "right", CFG)
                for t in (15.0, 30.0):
                    kp, conf = project(pts, t)
                    s = vs.sample(0.0, kp, conf)
                    s.tilt_deg = t
                    sol = gm.arm_solutions(s, "right", CFG)
                    self.assertIsNotNone(sol)
                    for fam in ("away", "toward"):
                        if ref[fam] is None:
                            continue
                        self.assertAlmostEqual(sol[fam][0], ref[fam][0], delta=1.0, msg=(az, elev, t, fam))
                        self.assertAlmostEqual(sol[fam][1], ref[fam][1], delta=1.0, msg=(az, elev, t, fam))
                    if t == 30.0 and ref["away"] is not None:   # without the correction the reading moves
                        s.tilt_deg = 0.0
                        wrong = gm.arm_solutions(s, "right", CFG)
                        moved = wrong is None or wrong["away"] is None or max(
                            abs(gm.wrap(wrong["away"][0] - ref["away"][0])), abs(wrong["away"][1] - ref["away"][1])) > 2.0
                        self.assertTrue(moved, (az, elev))

    def test_commander_bearing_is_tilt_corrected(self):
        pts = body3d(x0=0.7, z0=2.0)
        want = math.degrees(math.atan2(0.7, 2.0))
        for t in (0.0, 25.0):
            kp, conf = project(pts, t)
            s = vs.sample(0.0, kp, conf)
            s.tilt_deg = t
            self.assertAlmostEqual(cm.body_bearing_deg(s, 0.5), want, delta=0.2)

    def test_tilt_target_centres_the_box(self):
        w, h, fov = 730, 530, 60.0
        fy = (h / 2) / math.tan(math.radians(fov / 2))
        v = h / 2 - fy * math.tan(math.radians(12.0))        # a box centred 12 deg above the axis
        self.assertAlmostEqual(hv.tilt_target((0, v - 10, 10, v + 10), (w, h), fov, 5.0), 17.0, places=6)

    def test_zoom_controller_tilts_rate_limited_and_clamped_and_off_is_level(self):
        base, v4 = hv.load_control()
        z = dict(v4["zoom"])
        zc = hv.ZoomController(z)
        r = gm.Reading("POINT", 0.9, "ok", 0.0)
        r.frame_wh, r.hand_box, r.arm_box = (730, 530), (360, 60, 380, 80), (300, 40, 420, 200)
        r.fit_box = (300, 20, 420, 140)                         # well above the centre: tilt up
        tilts = []
        for i in range(30):
            zc.update(i * 0.1, r, 60.0, True, tilts[-1] if tilts else 0.0)
            tilts.append(zc.tilt_cmd)
        self.assertGreater(tilts[0], -1.0)
        steps = np.diff([0.0] + tilts[1:])
        self.assertTrue(all(abs(d) <= z["tilt_max_change_deg_per_s"] * 0.1 + 1e-6 for d in steps[1:]))
        self.assertTrue(all(z["tilt_min_deg"] <= t <= z["tilt_max_deg"] for t in tilts))
        zc.update(4.0, r, 60.0, False, 10.0)
        self.assertEqual(zc.tilt_cmd, -1.0)                     # dialog over: level
        off = hv.ZoomController({**z, "enabled": False})
        self.assertEqual(off.update(0.0, r, 60.0, True, 0.0), -1.0)
        self.assertEqual(off.tilt_cmd, -1.0)

    def test_command_tilt_is_validated(self):
        def cmd(tilt):
            hud = {"state": "", "screen_text": "", "commander_id": -1, "gesture": "PROCEED", "gesture_score": 0.0,
                   "gesture_raw": "NONE", "gesture_accepted": "NONE", "point_angle_deg": -1.0, "people": [], "log": []}
            return P.Message({"type": "command", "seq": 1, "version": 3, "reply_to": 1, "v": 0.0, "omega": 0.0, "pan_deg": 0.0,
                              "has_target": False, "target_x": 0.0, "target_z": 0.0, "state": "", "screen_text": "",
                              "vertical_fov_deg": -1.0, "tilt_deg": tilt, "hud": hud})
        for ok in (-1.0, 0.0, 22.5):
            P.validate(cmd(ok), P.TO_UNITY)
        for bad in (-5.0, 95.0):
            with self.assertRaises(P.MessageError):
                P.validate(cmd(bad), P.TO_UNITY)


# ---------------------------------------------------------------- ankle height (P1)

class AnkleHeightTests(unittest.TestCase):
    P = {"ankle_confidence": 0.5, "occlusion_margin_px": 4, "camera_height_m": 1.6}

    def row_for(self, d, h_point, H=1024, cam=1.6):
        e = -math.degrees(math.atan2(cam - h_point, d))         # elevation of a point h_point high at distance d
        return (90.0 - e) / 180.0 * H - 0.5

    def test_ankles_above_the_floor_are_corrected(self):
        H, ankle = 1024, 0.08
        v = self.row_for(2.0, ankle)
        kp = np.zeros((17, 2))
        kp[hpm.L_ANKLE] = kp[hpm.R_ANKLE] = (100.0, v)
        conf = np.ones(17)
        d0, src = hpm.person_distance((0, 0, 1, v), kp, conf, H, self.P, camera_height_m=1.6)
        d1, _ = hpm.person_distance((0, 0, 1, v), kp, conf, H, self.P, camera_height_m=1.6, ankle_height_m=ankle)
        self.assertEqual(src, "ankles")
        self.assertAlmostEqual(d1, 2.0, places=6)
        self.assertAlmostEqual(d0, 2.0 * 1.6 / (1.6 - ankle), places=6)       # the old bias (+0.105 m)

    def test_box_bottom_is_unchanged(self):
        H = 1024
        v = self.row_for(3.0, 0.0)
        d0 = hpm.person_distance((0, 0, 1, v), None, None, H, self.P, camera_height_m=1.6)
        d1 = hpm.person_distance((0, 0, 1, v), None, None, H, self.P, camera_height_m=1.6, ankle_height_m=0.08)
        self.assertEqual(d0, d1)

    def test_v4_config_and_truth_field(self):
        cfg = json.loads((V4 / "perception.json").read_text(encoding="utf-8"))
        self.assertGreaterEqual(cfg["ankle_height_m"], 0.0)
        base = {"time_s": 1.0, "worker_id": 1, "look": "sunbox_m1", "x": 0.0, "z": 0.0, "true_command": "PROCEED",
                "point_angle_deg": -1, "arm": "right", "phase": "holding", "is_commander": True, "clip": "proceed_ik_01"}
        rows = gd.parse_truth([json.dumps({**base, "ankle_height_m": 0.083}), json.dumps({**base, "time_s": 1.1})])
        self.assertEqual((rows[0].ankle_height_m, rows[1].ankle_height_m), (0.083, None))
        with self.assertRaises(gd.TruthError):
            gd.parse_truth([json.dumps({**base, "ankle_height_m": 0.9})])
        self.assertIn("ankle_height_m", P.TRUTH_KEYS)


# ---------------------------------------------------------------- the v4 map, start search, PROCEED in the dialog (P2, P7, P8)

class MapAndStartTests(unittest.TestCase):
    def setUp(self):
        self.road = hv.load_roadmap()

    def test_map_labels_lengths_and_stands(self):
        self.assertEqual(hv.check_labels_v4(self.road), [])
        self.assertEqual(self.road.kind("A"), hv.START)
        self.assertEqual(sorted(self.road.endpoints()), ["E1", "E2", "E3", "E4", "E5", "E6"])
        lengths = self.road.cfg["route_lengths_m"]
        for e in self.road.endpoints():
            n, total = e, 0.0
            while n != "A":
                prev = next(j for j, br in self.road.branches.items() if n in br.values())
                total += math.dist(self.road.pos(prev), self.road.pos(n))
                n = prev
            self.assertAlmostEqual(total, lengths[e], places=6, msg=e)
            self.assertTrue(40.0 <= total <= 70.0)
        self.assertEqual(hv.stand(self.road, "A")[:2], (8.75, -17.5))
        self.assertEqual(hv.roadmap_path(hv.load_control()[1]), "configs/v4/roadmap.json")

    def test_proceed_is_the_forward_branch_only_where_there_is_one(self):
        self.assertEqual(hv.proceed_branch(self.road, "A"), "FORWARD")
        self.assertEqual(hv.proceed_branch(self.road, "J1"), "FORWARD")
        self.assertIsNone(hv.proceed_branch(self.road, "J3"))
        dirs, arrival = hv.branch_directions(self.road, "A")
        self.assertAlmostEqual(arrival, -180.0)                 # behind the start heading
        self.assertAlmostEqual(dirs["FORWARD"], 0.0)

    def test_the_robot_starts_by_searching_and_never_drives_without_an_instruction(self):
        c = hv.make_controller_v4()
        c.begin(0.0)
        self.assertEqual((c.state, c.node), ("scan", "A"))
        # the commander's PROCEED is never read: the robot asks twice at A and aborts, never navigating
        r = hs.SimulatorV4(hv.make_controller_v4(), SimConfig(), hs.GestureSimConfig(coverage={"PROCEED": 0.0}),
                           hs.SceneSpec(proceed_forward=True), 1).run("E1")
        self.assertEqual(r["failure_reason"], "aborted")
        self.assertFalse(any(x.endswith(":navigate") or x.endswith(":execute") for x in r["trace"]), r["trace"])
        self.assertLess(r["travelled_m"], 3.0)

    def test_every_goal_in_the_simulator_with_proceed_and_ask_distances(self):
        for goal in ("E1", "E2", "E5"):
            r = hs.SimulatorV4(hv.make_controller_v4(), SimConfig(), hs.GestureSimConfig(), hs.SceneSpec(proceed_forward=True),
                               1).run(goal)
            self.assertEqual(r["outcome"], "SUCCESS", (goal, r["failure_reason"]))
            self.assertEqual(r["junctions"][0]["junction"], "A")
            for j in r["junctions"]:
                self.assertTrue(j["asks_log"])
                self.assertTrue(all(a["distance_est_m"] > 0 for a in j["asks_log"]))
            shown = {row["true_command"] for row in r["truth_rows"] if row["is_commander"]}
            self.assertIn("PROCEED", shown)

    def test_a_proceed_where_there_is_no_forward_branch_is_unclear(self):
        c = hv.make_controller_v4()
        c.begin(0.0)
        c.node = "J3"
        r = gm.Reading("PROCEED", 0.9, "forearm swings", 1.0, arm="right")
        r.arms = {"right": {"raised": False, "path": 0.0}}
        p = cm.PersonReading(5, 0.0, True, "facing", r)
        c.record = {"t_ask_first": 0.5}
        lab = c._interpret(hv.TickInputV4(1.0, 21.25, -0.5, 0.0, people=[], people_time_s=1.0, persons=[p], persons_time_s=1.0))
        self.assertEqual(lab, "NONE")
        self.assertIn("no FORWARD branch", c.proceed_note)


# ---------------------------------------------------------------- junction metrics (P3)

class JunctionMetricTests(unittest.TestCase):
    def test_junction_level_block_on_a_simulated_session(self):
        import hri_eval_dev_v4 as ev
        results = [hs.SimulatorV4(hv.make_controller_v4(), SimConfig(), hs.GestureSimConfig(), hs.SceneSpec(proceed_forward=True),
                                  s).run(g) for s, g in ((1, "E1"), (2, "E3"))]
        with tempfile.TemporaryDirectory() as d:
            u, b = hs.export_session(results, d, zoom_enabled=True)
            for i, r in enumerate(results, 1):            # export_session writes b_name; check it is the goal
                self.assertEqual(json.loads((u / f"truth_run{i:03d}.json").read_text())["b_name"], r["goal"])
            runs = ev.load_sessions([(u, b)], gd.load_config())
            res = ev.evaluate(runs)
        jl = res["junction_level"]
        self.assertEqual((jl["dialogs"], jl["correct"], jl["wrong"], jl["abort"]), (5, 5, 0, 0))
        pairs = {(p["node"], p["shown"]): p for p in jl["pairs"]}
        self.assertEqual(pairs[("A", "PROCEED")]["dialogs"], 2)
        self.assertEqual(pairs[("J1", "PROCEED")]["correct"], 1)
        self.assertEqual(pairs[("J3", "POINT")]["correct_share"], 1.0)
        so = jl["standoff"]
        self.assertEqual(so["coverage"], 1.0)
        self.assertLess(so["abs_error_m"]["median"], 0.5)
        self.assertTrue(all(a["dialog_outcome"] == "correct" for a in jl["asks"]))


# ---------------------------------------------------------------- control files and the server option (P10, P11)

class ControlFileTests(unittest.TestCase):
    def test_zoom_files_differ_only_in_the_switch(self):
        base = json.loads((V4 / "control.json").read_text(encoding="utf-8"))
        on = json.loads((V4 / "control_zoom_on.json").read_text(encoding="utf-8"))
        off = json.loads((V4 / "control_zoom_off.json").read_text(encoding="utf-8"))
        self.assertEqual(on, base)
        self.assertTrue(on["zoom"]["enabled"])
        self.assertFalse(off["zoom"]["enabled"])
        self.assertEqual({**off, "zoom": {**off["zoom"], "enabled": True}}, on)

    def test_each_final_setting_has_its_file(self):
        import final_guard_v4 as fg
        self.assertEqual(set(S.FINAL_CONTROL), set(fg.plan()["settings"]))
        for setting, f in S.FINAL_CONTROL.items():
            S.check_final_control(setting, f)
            want = fg.plan()["settings"][setting].get("zoom")
            if want is not None:
                self.assertEqual(json.loads((ROOT / f).read_text(encoding="utf-8"))["zoom"]["enabled"], want)
        with self.assertRaises(SystemExit):
            S.check_final_control("zoom_off", "configs/v4/control_zoom_on.json")
        with self.assertRaises(SystemExit):
            S.check_final_control("zoom_on", "configs/v4/control.json")

    def test_server_option_default_is_unchanged(self):
        import argparse
        seen = {}
        real = S.asyncio.run

        def fake_run(coro):
            seen["control_config"] = coro.cr_frame.f_locals["control_config"]
            coro.close()
        try:
            S.asyncio.run = fake_run
            S.main(["--config", "configs/v4/bridge.json", "--mode", "guide", "--task", "Task2"])
            self.assertEqual(seen["control_config"], "configs/v4/control.json")
            S.main(["--config", "configs/v4/bridge.json", "--mode", "guide", "--task", "Task2",
                    "--control-config", "configs/v4/control_zoom_off.json"])
            self.assertEqual(seen["control_config"], "configs/v4/control_zoom_off.json")
        finally:
            S.asyncio.run = real
        self.assertTrue(argparse)


# ---------------------------------------------------------------- per-frame model-output log (P12)

class ModelOutputLogTests(unittest.TestCase):
    def test_one_line_per_camera_frame(self):
        from bridge.perception_v4 import MODEL_OUTPUTS, PerceptionWorkerV4

        class FakeP:
            label = "fake"

            def decode_jpeg(self, data):
                return np.zeros((530, 730, 3), np.uint8)

            def people(self, *a, **k):
                self.last_people_raw = [{"track_id": 3, "box": [1.0, 2.0, 3.0, 4.0], "conf": 0.9, "kp": [[1.0, 2.0, 0.9]] * 17,
                                         "bearing_deg": 10.0, "distance_m": 2.1, "distance_source": "ankles"}]
                return [{"track_id": 3, "bearing_deg": 10.0, "distance_m": 2.1, "distance_source": "ankles",
                         "confidence": 0.9, "box_h": 2.0}], 1.0

            def persons(self, bgr, meta):
                self.meta = meta
                self.last_persons_raw = {"people": [{"track_id": 1, "box": [0, 0, 1, 1], "kp": []}],
                                         "hands": [{"track_id": 1, "category": "None", "score": 0.5, "handedness": None,
                                                    "lm": [[0.0, 0.0]] * 21, "world": None, "box": [0, 0, 1, 1], "wrist": [0, 0]}]}
                return [], {"yolo": 1.0}

        def msg(kind, **h):
            pose = {"x": 1.0, "z": 2.0, "yaw_deg": 3.0}
            return SimpleNamespace(type=kind, header={"time_s": 5.0, "frame_index": 7, "pose": pose, **h},
                                   attachments={"image": b"\xff\xd8"})

        with tempfile.TemporaryDirectory() as d:
            fp = FakeP()
            w = PerceptionWorkerV4(fp, Path(d), verbose=False)
            try:
                w._process("frame_360", msg("frame_360", camera_height_m=1.6, centre_world_yaw_deg=0.0), 0)
                w._process("frame_pan_tilt", msg("frame_pan_tilt", fx=458.99, fy=458.99, cx=365.0, cy=265.0, width=730,
                                                 height=530, vertical_fov_deg=60.0, pan_deg=4.0, tilt_deg=12.0), 0)
                self.assertEqual(fp.meta["tilt_deg"], 12.0)
                self.assertEqual(w.snapshot_v4()["tilt_deg"], 12.0)
            finally:
                w.close()
            lines = [json.loads(x) for x in (Path(d) / MODEL_OUTPUTS).read_text(encoding="utf-8").splitlines()]
        self.assertEqual([x["cam"] for x in lines], ["360", "pan_tilt"])
        self.assertEqual(lines[0]["people"][0]["distance_source"], "ankles")
        self.assertEqual((lines[1]["tilt_deg"], lines[1]["vertical_fov_deg"], lines[1]["fx"]), (12.0, 60.0, 458.99))
        self.assertEqual(len(lines[1]["hands"][0]["lm"]), 21)


if __name__ == "__main__":
    unittest.main()
