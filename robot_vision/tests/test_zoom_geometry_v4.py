"""v4 zoom with a LEVEL camera and a raised arm (AUDIT.md 14.15, decision of 2026-11-07).

Nusrat found in Unity that at 2.0 m a raised hand is about 22-24 degrees above the level pan-tilt camera, so a 30 degree view (half
angle 15 degrees) loses the hand. Decision (c): the camera stays level (tilt_deg is not used) and the zoom is limited by distance through
the existing arm_fit rule (configs/v4/control.json zoom). This module checks that decision on the real ZoomController in a closed loop:
a pinhole camera 1.2 m above the floor, a person centred in front of it, shoulder 1.5 m high, the arm raised (upper arm 0.30 m, forearm
0.26 m, hand 0.19 m); every frame the keypoints are projected at the field of view the controller last commanded (Unity is taken to apply
it by the next frame), YOLO is taken to miss a keypoint outside the image (no arm box, no hand box), and the controller answers.

The camera height (1.2 m) is inferred, not read from a config: with it a vertical arm puts the wrist 23.3 degrees above the axis at 2.0 m,
which is Nusrat's measurement. Everything is pure arithmetic: no model, no clock, no machine speed.
"""

import json
import math
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import gesture_motion as gm  # noqa: E402
import hri_control_v4 as hv  # noqa: E402

Z = json.loads((ROOT / "configs" / "v4" / "control.json").read_text(encoding="utf-8"))["zoom"]
W, H = 730, 530
CAM_H, SHOULDER_H = 1.2, 1.5
UPPER, FORE, HAND = 0.30, 0.26, 0.19
DISTANCES = (2.0, 3.0, 4.0, 6.0)


def pose(elev_deg: float):
    """(shoulder, elbow, wrist, hand top), each (lateral x, height above the camera y) in metres; the arm rises at elev_deg."""
    e = math.radians(elev_deg)
    s = (0.20, SHOULDER_H - CAM_H)
    el = (s[0], s[1] + UPPER * math.sin(e))
    wr = (s[0], el[1] + FORE * math.sin(e))
    return s, el, wr, (s[0], wr[1] + HAND * math.sin(e))


def project(pt, d: float, fov: float):
    fy = (H / 2) / math.tan(math.radians(fov) / 2)
    return W / 2 + fy * pt[0] / d, H / 2 - fy * pt[1] / d


def inside(p, margin: float = 0.0) -> bool:
    return margin * W <= p[0] <= (1 - margin) * W and margin * H <= p[1] <= (1 - margin) * H


def floor_fov(d: float, elev: float, margin: float) -> float:
    """Narrowest vertical field of view (deg) at which shoulder, elbow and wrist are all inside the image with `margin` on every side."""
    t = max(max(abs(y) / d, abs(x) / d * H / W) for x, y in pose(elev)[:3]) / (1 - 2 * margin)
    return 2 * math.degrees(math.atan(t))


def reading(d: float, fov: float, elev: float):
    s, el, wr, top = pose(elev)
    ps = [project(p, d, fov) for p in (s, el, wr)]
    if not all(inside(p) for p in ps):
        return None
    hx = [project((wr[0] + dx, wr[1] + dy), d, fov) for dx in (-0.05, 0.05) for dy in (0.0, top[1] - wr[1])]
    hb = (max(0.0, min(q[0] for q in hx)), max(0.0, min(q[1] for q in hx)), min(float(W), max(q[0] for q in hx)), min(float(H), max(q[1] for q in hx)))
    ab = (min(p[0] for p in ps), min(p[1] for p in ps), max(p[0] for p in ps), max(p[1] for p in ps))
    return gm.Reading("POINT", 0.9, "ok", 0.0, hand_box=hb, arm_box=ab, frame_wh=(W, H))


def closed_loop(d: float, elev: float, seconds: float = 60.0, z: dict = Z) -> list[tuple[float, float, bool]]:
    """(time, commanded field of view, arm visible in that frame) at 10 Hz."""
    zc, cur, t, log = hv.ZoomController(z), z["fov_default_deg"], 0.0, []
    while t < seconds:
        rd = reading(d, cur, elev)
        out = zc.update(t, rd, cur, True)
        cur = z["fov_default_deg"] if out < 0 else out
        log.append((t, cur, rd is not None))
        t = round(t + 0.1, 3)
    return log


def magnification(fov: float) -> float:
    """How much larger things look than at the default field of view."""
    return math.tan(math.radians(Z["fov_default_deg"]) / 2) / math.tan(math.radians(fov) / 2)


class GeometryTests(unittest.TestCase):
    def test_a_vertical_arm_puts_the_wrist_22_to_24_degrees_up_at_2_m_like_unity(self):
        wrist_y = pose(90.0)[2][1]
        self.assertTrue(22.0 <= math.degrees(math.atan(wrist_y / 2.0)) <= 24.0)

    def test_a_30_degree_view_loses_the_hand_at_2_m_and_the_default_view_keeps_it(self):
        wrist = pose(90.0)[2]
        self.assertFalse(inside(project(wrist, 2.0, 30.0)))
        self.assertTrue(inside(project(wrist, 2.0, Z["fov_default_deg"]), Z["arm_fit_margin"]))

    def test_the_floor_is_the_view_that_just_keeps_the_arm_inside_the_margin(self):
        for d in DISTANCES:
            for elev in (90.0, 60.0):
                f = floor_fov(d, elev, Z["arm_fit_margin"])
                pts = pose(elev)[:3]
                self.assertTrue(all(inside(project(p, d, f + 0.01), Z["arm_fit_margin"]) for p in pts), (d, elev))
                self.assertFalse(all(inside(project(p, d, f - 0.5), Z["arm_fit_margin"]) for p in pts), (d, elev))


class ClosedLoopTests(unittest.TestCase):
    def test_at_2_m_the_controller_never_narrows_below_the_view_that_keeps_the_arm_in_the_margin(self):
        for elev in (90.0, 75.0, 60.0, 45.0):
            floor = floor_fov(2.0, elev, Z["arm_fit_margin"])
            fovs = [f for _, f, _ in closed_loop(2.0, elev)]
            self.assertGreaterEqual(min(fovs), floor - 1e-9, f"arm at {elev} deg: commanded {min(fovs)} < floor {floor:.2f}")

    def test_at_2_m_the_zoom_hardly_does_anything(self):
        for elev in (90.0, 60.0):
            fovs = [f for _, f, _ in closed_loop(2.0, elev)]
            self.assertLessEqual(magnification(min(fovs)), 1.2)       # at most 20 per cent larger than the default view

    def test_the_arm_is_in_the_image_in_every_frame_at_every_distance(self):
        for d in DISTANCES:
            for elev in (90.0, 60.0):
                self.assertTrue(all(vis for *_, vis in closed_loop(d, elev)), (d, elev))

    def test_3_and_4_m_stay_above_the_floor_and_6_m_overshoots_it_by_less_than_one_degree(self):
        for d, tol in ((3.0, 1e-9), (4.0, 1e-9), (6.0, 1.0)):
            for elev in (90.0, 60.0):
                floor = floor_fov(d, elev, Z["arm_fit_margin"])
                low = min(f for _, f, _ in closed_loop(d, elev))
                self.assertGreaterEqual(low, floor - tol, (d, elev, low, floor))

    def test_the_narrowest_view_gets_narrower_with_distance(self):
        for elev in (90.0, 60.0):
            lows = [min(f for _, f, _ in closed_loop(d, elev)) for d in DISTANCES]
            self.assertEqual(lows, sorted(lows, reverse=True), (elev, lows))

    def test_zoom_matters_from_about_3_m(self):
        """Magnification of the narrowest view the controller commands, vertical arm: about 1.1x at 2 m, 1.5x at 3 m, 2x at 4 m, 3x at 6 m."""
        mag = {d: magnification(min(f for _, f, _ in closed_loop(d, 90.0))) for d in DISTANCES}
        self.assertLessEqual(mag[2.0], 1.2)
        self.assertGreaterEqual(mag[3.0], 1.4)
        self.assertGreaterEqual(mag[4.0], 1.9)
        self.assertGreaterEqual(mag[6.0], 3.0)

    def test_the_hand_cannot_leave_the_frame_for_good_even_when_the_rule_overshoots(self):
        """A view that is too narrow loses the hand; the rule then widens (hand_lost_s, widen_step_deg), it does not stay narrow."""
        for d in (3.0, 4.0, 6.0):
            fovs = [f for _, f, _ in closed_loop(d, 90.0)]
            half = fovs[len(fovs) // 2:]
            self.assertGreater(max(half) - min(half), 1.0)                  # it keeps adjusting: the view moves in and out
            self.assertGreater(min(half), Z["fov_min_deg"])                # and never sits at the narrowest allowed view


if __name__ == "__main__":
    unittest.main()
