"""v4 ground-truth evaluation (gt_path.py) on small synthetic grids and trails, the leak-test checker, the rule that
inference code never imports it, and the analysis hook (v3 output byte-identical, v4 measures only with the files)."""

import ast
import csv
import hashlib
import json
import math
import random
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "tests"))

import gt_path as gt  # noqa: E402
import hri_analysis as ha  # noqa: E402
import hri_trials as ht  # noqa: E402

CFG = gt.load_config()
S2 = math.sqrt(2.0)


def grid(rows, cell=0.5, ox=0.0, oz=0.0, start=None, goal=None) -> gt.Grid:
    """rows[iz][ix]: '1' blocked. start / goal default to the centres of the first and last free corner cells."""
    g = gt.Grid(cell, ox, oz, [[c == "1" for c in r] for r in rows], (0, 0), (0, 0))
    g.start = start or g.centre(0, 0)
    g.goal = goal or g.centre(len(rows[0]) - 1, len(rows) - 1)
    return g


def unity_path(g: gt.Grid, cells, length=None) -> dict:
    pts = [g.centre(*c) for c in cells]
    return {"length_m": gt.path_length_m(cells, g.cell) if length is None else length,
            "cells": [{"ix": c[0], "iz": c[1]} for c in cells], "points": [{"x": x, "z": z} for x, z in pts]}


def dijkstra_length(g: gt.Grid, s, t):
    """Independent reference: plain Dijkstra, same rules, no heuristic."""
    import heapq
    dist, heap = {s: 0.0}, [(0.0, s)]
    while heap:
        d, c = heapq.heappop(heap)
        if c == t:
            return d * g.cell
        if d > dist.get(c, 1e18):
            continue
        for dx, dz in [(1, 0), (-1, 0), (0, 1), (0, -1), (1, 1), (1, -1), (-1, 1), (-1, -1)]:
            n = (c[0] + dx, c[1] + dz)
            if not g.free(*n):
                continue
            if dx and dz and not (g.free(c[0] + dx, c[1]) and g.free(c[0], c[1] + dz)):
                continue
            nd = d + (S2 if dx and dz else 1.0)
            if nd < dist.get(n, 1e18):
                dist[n] = nd
                heapq.heappush(heap, (nd, n))
    return None


class AStarTests(unittest.TestCase):
    def test_open_grid_straight_and_diagonal(self):
        g = grid(["0000", "0000", "0000", "0000"])
        cells, length = gt.astar(g, (0, 0), (3, 0))
        self.assertEqual((cells[0], cells[-1], len(cells)), ((0, 0), (3, 0), 4))
        self.assertAlmostEqual(length, 3 * 0.5)
        _, length = gt.astar(g, (0, 0), (3, 3))
        self.assertAlmostEqual(length, 3 * S2 * 0.5)
        _, length = gt.astar(g, (0, 0), (3, 1))          # 1 diagonal + 2 straight
        self.assertAlmostEqual(length, (S2 + 2) * 0.5)

    def test_start_equals_goal(self):
        cells, length = gt.astar(grid(["00", "00"]), (1, 1), (1, 1))
        self.assertEqual((cells, length), ([(1, 1)], 0.0))

    def test_no_diagonal_between_two_blocked_cells(self):
        g = grid(["01", "10"])                              # the only diagonal squeezes between two blocked cells
        self.assertIsNone(gt.astar(g, (0, 0), (1, 1)))

    def test_no_corner_cutting_with_one_blocked_side_cell(self):
        g = grid(["000", "010", "000"])                     # centre blocked
        cells, length = gt.astar(g, (0, 0), (2, 2))
        self.assertAlmostEqual(length, gt.path_length_m(cells, 0.5))
        for a, b in zip(cells, cells[1:]):                  # no step may touch the blocked centre cell diagonally
            dx, dz = b[0] - a[0], b[1] - a[1]
            if dx and dz:
                self.assertTrue(g.free(a[0] + dx, a[1]) and g.free(a[0], a[1] + dz), (a, b))
        self.assertNotIn((1, 1), cells)
        self.assertAlmostEqual(length, 4 * 0.5)             # around the block: 4 straight steps, no diagonals

    def test_corner_cut_is_longer_than_a_cutting_path_would_be(self):
        g = grid(["00", "10"])                              # (0,1) blocked: diagonal (0,0)->(1,1) would cut its corner
        cells, length = gt.astar(g, (0, 0), (1, 1))
        self.assertEqual(cells, [(0, 0), (1, 0), (1, 1)])
        self.assertAlmostEqual(length, 2 * 0.5)

    def test_blocked_or_outside_ends_and_unreachable(self):
        g = grid(["010", "010", "010"])
        self.assertIsNone(gt.astar(g, (0, 0), (2, 0)))      # wall between
        self.assertIsNone(gt.astar(g, (1, 0), (2, 0)))      # start blocked
        self.assertIsNone(gt.astar(g, (0, 0), (5, 0)))      # outside

    def test_matches_an_independent_dijkstra_on_random_grids(self):
        rng = random.Random(4)
        checked = 0
        for _ in range(60):
            nx, nz = rng.randint(3, 12), rng.randint(3, 12)
            rows = ["".join("1" if rng.random() < 0.3 else "0" for _ in range(nx)) for _ in range(nz)]
            g = grid(rows, cell=0.5)
            s, t = (rng.randrange(nx), rng.randrange(nz)), (rng.randrange(nx), rng.randrange(nz))
            res, ref = gt.astar(g, s, t), dijkstra_length(g, s, t) if g.free(*s) and g.free(*t) else None
            if ref is None:
                self.assertIsNone(res)
            else:
                self.assertAlmostEqual(res[1], ref, places=9)
                checked += 1
        self.assertGreater(checked, 20)

    def test_cell_geometry(self):
        g = grid(["00", "00"], cell=0.5, ox=-2.0, oz=10.0)
        self.assertEqual(g.cell_of(-1.9, 10.1), (0, 0))
        self.assertEqual(g.cell_of(-1.25, 10.99), (1, 1))
        self.assertEqual(g.centre(1, 0), (-1.25, 10.25))

    def test_grid_from_dict_validates(self):
        d = {"cell_size_m": 0.5, "origin_x": 0.0, "origin_z": 0.0, "cells_x": 3, "cells_z": 2,
             "blocked_rows": ["010", "000"], "start": {"x": 0.25, "z": 0.25}, "goal": {"x": 1.25, "z": 0.75}}
        g = gt.grid_from_dict(d)
        self.assertEqual((g.nx, g.nz, g.blocked[0][1]), (3, 2, True))
        for bad in ({**d, "cells_x": 4}, {**d, "cells_z": 3}, {**d, "blocked_rows": ["0a0", "000"]}):
            with self.assertRaises(ValueError):
                gt.grid_from_dict(bad)


class CompareOptimalTests(unittest.TestCase):
    def setUp(self):
        self.g = grid(["0000", "0100", "0000", "0000"])

    def test_match(self):
        cells, _ = gt.astar(self.g, (0, 0), (3, 3))
        res = gt.compare_optimal(self.g, unity_path(self.g, cells), 0.001)
        self.assertTrue(res["match"])
        self.assertEqual(res["length_diff_m"], 0.0)

    def test_a_legal_but_longer_unity_path_does_not_match(self):
        g = grid(["000", "000", "000"])
        detour = [(0, 0), (0, 1), (0, 2), (1, 2), (2, 2)]     # 4 straight steps; the diagonal route is 2 sqrt(2) cells
        res = gt.compare_optimal(g, unity_path(g, detour), 0.001)
        self.assertTrue(res["unity_path_legal"])
        self.assertFalse(res["match"])
        self.assertAlmostEqual(res["length_diff_m"], (4 - 2 * S2) * 0.5, places=6)

    def test_a_different_path_of_the_same_length_matches(self):
        g = grid(["000", "000", "000"])
        for cells in ([(0, 0), (1, 1), (2, 2)], ):
            self.assertTrue(gt.compare_optimal(g, unity_path(g, cells), 0.001)["match"])
        g = grid(["0000", "0000"])                            # (0,0)->(3,1): 1 diagonal + 2 straight, in any order
        for cells in ([(0, 0), (1, 1), (2, 1), (3, 1)], [(0, 0), (1, 0), (2, 0), (3, 1)], [(0, 0), (1, 0), (2, 1), (3, 1)]):
            self.assertTrue(gt.compare_optimal(g, unity_path(g, cells), 0.001)["match"], cells)

    def test_length_off_by_more_than_the_tolerance(self):
        cells, length = gt.astar(self.g, (0, 0), (3, 3))
        res = gt.compare_optimal(self.g, unity_path(self.g, cells, length + 0.002), 0.001)
        self.assertFalse(res["match"])
        self.assertAlmostEqual(res["length_diff_m"], 0.002, places=6)

    def test_unity_path_cutting_a_corner_is_flagged(self):
        g = grid(["00", "10"])
        res = gt.compare_optimal(g, unity_path(g, [(0, 0), (1, 1)]), 0.001)    # diagonal past the blocked (0,1)
        self.assertFalse(res["unity_path_legal"])
        self.assertFalse(res["match"])

    def test_unity_path_through_a_blocked_cell_or_wrong_ends(self):
        cells = [(0, 0), (1, 1), (2, 2), (3, 3)]
        res = gt.compare_optimal(self.g, unity_path(self.g, cells), 0.001)
        self.assertFalse(res["unity_path_legal"])               # (1,1) is blocked
        res = gt.compare_optimal(self.g, unity_path(self.g, [(0, 0), (0, 1), (0, 2)]), 0.001)
        self.assertFalse(res["unity_path_legal"])               # does not end at B's cell
        res = gt.compare_optimal(self.g, unity_path(self.g, [(0, 0), (2, 0)]), 0.001)
        self.assertFalse(res["unity_path_legal"])               # a jump

    def test_no_path_in_python(self):
        g = grid(["010", "010", "010"])
        res = gt.compare_optimal(g, unity_path(g, [(0, 0)], 0.0), 0.001)
        self.assertFalse(res["python_found_path"] or res["match"])


class PathMeasureTests(unittest.TestCase):
    OPT = [(0.0, 0.0), (4.0, 0.0), (4.0, 3.0)]            # length 7

    def trail(self, pts):
        return [(0.1 * i, x, z) for i, (x, z) in enumerate(pts)]

    def test_on_the_path(self):
        m = gt.path_measures(self.trail([(0.0, 0.0), (2.0, 0.0), (4.0, 0.0), (4.0, 3.0)]), self.OPT, (4.0, 3.0), 0.5, 1.0)
        self.assertEqual((m["trail_length_m"], m["optimal_length_m"], m["trail_over_optimal"]), (7.0, 7.0, 1.0))
        self.assertEqual((m["max_distance_from_optimal_m"], m["share_within_near_distance"]), (0.0, 1.0))
        self.assertEqual(m["final_distance_from_b_m"], 0.0)

    def test_detour_and_early_stop(self):
        pts = [(0.0, 0.0), (0.0, 1.0), (2.0, 1.0), (4.0, 0.2), (4.0, 1.5)]
        m = gt.path_measures(self.trail(pts), self.OPT, (4.0, 3.0), 0.5, 1.0)
        self.assertEqual(m["max_distance_from_optimal_m"], 1.0)
        self.assertEqual(m["share_within_near_distance"], 0.6)           # (0,0), (4,.2), (4,1.5) within 0.5 m; the 1.0 m ones not
        self.assertEqual(m["final_distance_from_b_m"], 1.5)
        self.assertAlmostEqual(m["trail_length_m"], 1 + 2 + math.hypot(2, 0.8) + 1.3, places=3)
        self.assertEqual(m["near_distance_m"], 0.5)

    def test_near_distance_scales_with_cells(self):
        pts = [(0.0, 0.0), (0.0, 1.0)]
        self.assertEqual(gt.path_measures(self.trail(pts), self.OPT, (4.0, 3.0), 0.5, 1.0)["share_within_near_distance"], 0.5)
        self.assertEqual(gt.path_measures(self.trail(pts), self.OPT, (4.0, 3.0), 0.5, 2.0)["share_within_near_distance"], 1.0)

    def test_distance_to_polyline_uses_segments_not_vertices(self):
        self.assertEqual(gt.distance_to_polyline(2.0, 0.7, self.OPT), 0.7)
        self.assertEqual(gt.distance_to_polyline(-1.0, 0.0, self.OPT), 1.0)
        self.assertAlmostEqual(gt.distance_to_polyline(5.0, 4.0, self.OPT), math.hypot(1, 1))

    def test_too_little_data_gives_none_not_a_guess(self):
        m = gt.path_measures(self.trail([(0.0, 0.0)]), self.OPT, (4.0, 3.0), 0.5, 1.0)
        self.assertIsNone(m["trail_over_optimal"])
        self.assertIsNone(m["final_distance_from_b_m"])
        self.assertIsNone(gt.path_measures([], [], (0.0, 0.0), 0.5, 1.0)["trail_length_m"])

    def test_load_trail(self):
        with tempfile.TemporaryDirectory() as d:
            p = Path(d) / "trail.csv"
            p.write_text("time_s,x,z,yaw_deg\n0.000,1.5,2.5,0.00\n0.100,1.6,2.5,3.00\n")
            self.assertEqual(gt.load_trail(p), [(0.0, 1.5, 2.5), (0.1, 1.6, 2.5)])


def write_run(folder: Path, trail_pts, rows=None, length_delta=0.0):
    """A v4 run folder: a small grid, Unity's optimal path (from Python's A*, optionally with a wrong length), a trail."""
    rows = rows or ["0000", "0100", "0000", "0000"]
    g = grid(rows, cell=0.5, ox=0.0, oz=0.0)
    cells, length = gt.astar(g, g.cell_of(*g.start), g.cell_of(*g.goal))
    folder.mkdir(parents=True)
    (folder / "grid.json").write_text(json.dumps({
        "cell_size_m": 0.5, "origin_x": 0.0, "origin_z": 0.0, "cells_x": len(rows[0]), "cells_z": len(rows),
        "blocked_rows": rows, "start": {"x": g.start[0], "z": g.start[1]}, "goal": {"x": g.goal[0], "z": g.goal[1]}}))
    (folder / "optimal_path.json").write_text(json.dumps(unity_path(g, cells, length + length_delta)))
    with (folder / "trail.csv").open("w", newline="") as f:
        f.write("time_s,x,z,yaw_deg\n" + "".join(f"{0.1 * i:.3f},{x},{z},0.00\n" for i, (x, z) in enumerate(trail_pts)))
    return g, cells


class EvaluateRunTests(unittest.TestCase):
    def test_run_folder(self):
        with tempfile.TemporaryDirectory() as d:
            run = Path(d) / "run_001"
            g, cells = write_run(run, [(0.25, 0.25), (0.75, 0.75), (1.25, 1.25), (1.75, 1.75)])
            self.assertTrue(gt.has_v4_files(run))
            res = gt.evaluate_run(run, CFG)
            self.assertTrue(res["optimal_path_check"]["match"])
            m = res["measures"]
            self.assertEqual(m["final_distance_from_b_m"], 0.0)
            self.assertEqual(m["share_within_near_distance"], 1.0)
            run2 = Path(d) / "run_002"
            write_run(run2, [(0.25, 0.25), (0.25, 0.75)], length_delta=0.5)
            self.assertFalse(gt.evaluate_run(run2, CFG)["optimal_path_check"]["match"])
            (Path(d) / "run_003").mkdir()
            self.assertFalse(gt.has_v4_files(Path(d) / "run_003"))


def write_png(path: Path, arr):
    from PIL import Image
    Image.fromarray(arr).save(path)


class LeakTestTests(unittest.TestCase):
    def setUp(self):
        import numpy as np
        self.np = np
        self.img = (np.arange(8 * 6 * 3) % 251).astype("uint8").reshape(8, 6, 3)

    def pair(self, folder, name, a=None, b=None):
        write_png(folder / f"{name}_on.png", self.img if a is None else a)
        write_png(folder / f"{name}_off.png", self.img if b is None else b)

    def test_identical_pairs_pass_and_are_written(self):
        with tempfile.TemporaryDirectory() as d:
            d = Path(d)
            self.pair(d, "cam360")
            self.pair(d, "pan_tilt")
            res = gt.leak_test(d, 0)
            self.assertTrue(res["passed"])
            self.assertEqual((res["max_diff"], len(res["pairs"])), (0, 2))
            self.assertTrue(json.loads((d / "leak_test.json").read_text())["passed"])

    def test_one_pixel_difference_fails(self):
        with tempfile.TemporaryDirectory() as d:
            d = Path(d)
            other = self.img.copy()
            other[3, 2, 1] += 7
            self.pair(d, "cam360")
            self.pair(d, "pan_tilt", b=other)
            res = gt.leak_test(d, 0)
            self.assertFalse(res["passed"])
            self.assertEqual(res["max_diff"], 7)
            bad = [p for p in res["pairs"] if not p["passed"]]
            self.assertEqual((bad[0]["name"], bad[0]["differing_pixels"]), ("pan_tilt", 1))
            self.assertFalse(json.loads((d / "leak_test.json").read_text())["passed"])

    def test_difference_allowed_only_up_to_the_config_value(self):
        with tempfile.TemporaryDirectory() as d:
            d = Path(d)
            other = self.img.copy()
            other[0, 0, 0] = (int(other[0, 0, 0]) + 2) % 256 if other[0, 0, 0] < 250 else other[0, 0, 0] - 2
            self.pair(d, "cam360", b=other)
            self.assertTrue(gt.leak_test(d, 2, write=False)["passed"])
            self.assertFalse(gt.leak_test(d, 1, write=False)["passed"])

    def test_missing_partner_size_mismatch_and_no_pairs_fail(self):
        with tempfile.TemporaryDirectory() as d:
            d = Path(d)
            self.assertFalse(gt.leak_test(d, 0, write=False)["passed"])      # nothing to compare is not a pass
            write_png(d / "lonely_on.png", self.img)
            res = gt.leak_test(d, 0, write=False)
            self.assertFalse(res["passed"])
            self.assertIn("only the on image", res["problems"][0])
            self.pair(d, "ok")
            self.pair(d, "sized", b=self.img[:4])
            res = gt.leak_test(d, 0, write=False)
            self.assertFalse(res["passed"])
            self.assertTrue(any("sizes differ" in p for p in res["problems"]))

    def test_never_overwrites(self):
        with tempfile.TemporaryDirectory() as d:
            d = Path(d)
            self.pair(d, "cam360")
            gt.leak_test(d, 0)
            with self.assertRaises(FileExistsError):
                gt.leak_test(d, 0)


# A 7 x 5 grid whose middle is a wall: from A (0, 0) to B (6, 4) the robot can go along the top and down the right side, or down the
# left side and along the bottom. Both routes are 10 straight steps (5.0 m); they are 2.0 m apart.
TWO_ROUTES = ["0000000", "0111110", "0111110", "0111110", "0000000"]
TOP = [(i, 0) for i in range(7)] + [(6, j) for j in range(1, 5)]
BOTTOM = [(0, j) for j in range(5)] + [(i, 4) for i in range(1, 7)]


def centres(g, cells):
    return [g.centre(*c) for c in cells]


def trail_on(g, cells):
    return [(0.1 * i, *g.centre(*c)) for i, c in enumerate(cells)]


class CorridorTests(unittest.TestCase):
    def setUp(self):
        self.g = grid(TWO_ROUTES)
        self.s, self.t = (0, 0), (6, 4)

    def test_both_equally_short_routes_are_in_the_corridor(self):
        cor = gt.optimal_corridor(self.g, self.s, self.t, 0.001)
        self.assertAlmostEqual(cor["length_m"], 5.0)
        self.assertEqual(set(cor["cells"]), set(TOP) | set(BOTTOM))
        self.assertEqual(cor["size"], 20)                                    # 11 + 11 - the shared A and B
        for route in (TOP, BOTTOM):
            self.assertAlmostEqual(gt.path_length_m(route, 0.5), 5.0)         # and both really are shortest paths
        self.assertEqual(gt.astar(self.g, self.s, self.t)[1], 5.0)

    def test_a_single_shortest_path_gives_a_corridor_of_that_path(self):
        g = grid(["0000", "0000", "0000", "0000"])
        self.assertEqual(gt.optimal_corridor(g, (0, 0), (3, 0), 0.001)["cells"], [(0, 0), (1, 0), (2, 0), (3, 0)])
        self.assertEqual(gt.optimal_corridor(g, (0, 0), (3, 3), 0.001)["cells"], [(0, 0), (1, 1), (2, 2), (3, 3)])
        self.assertIsNone(gt.optimal_corridor(grid(["010", "010", "010"]), (0, 0), (2, 0), 0.001))      # unreachable
        self.assertIsNone(gt.optimal_corridor(grid(["010", "000"]), (1, 0), (2, 1), 0.001))             # A blocked

    def test_corner_cutting_is_not_allowed_in_the_corridor_either(self):
        g = grid(["00", "10"])                                                # (0,1) blocked: the diagonal would cut its corner
        self.assertEqual(gt.optimal_corridor(g, (0, 0), (1, 1), 0.001)["cells"], [(0, 0), (1, 0), (1, 1)])

    def test_matches_an_independent_brute_force_on_random_grids(self):
        rng = random.Random(11)
        checked = 0
        for _ in range(60):
            nx, nz = rng.randint(3, 10), rng.randint(3, 10)
            g = grid(["".join("1" if rng.random() < 0.25 else "0" for _ in range(nx)) for _ in range(nz)])
            s, t = (rng.randrange(nx), rng.randrange(nz)), (rng.randrange(nx), rng.randrange(nz))
            cor = gt.optimal_corridor(g, s, t, 0.001)
            ref = dijkstra_length(g, s, t) if g.free(*s) and g.free(*t) else None
            if ref is None:
                self.assertIsNone(cor)
                continue
            def d(a, b):
                if a == b:
                    return 0.0
                v = dijkstra_length(g, a, b)
                return math.inf if v is None else v
            want = {(x, z) for x in range(nx) for z in range(nz) if g.free(x, z) and d(s, (x, z)) + d((x, z), t) <= ref + 0.001}
            self.assertEqual(set(cor["cells"]), want)
            self.assertIn(s, want)
            self.assertIn(t, want)
            checked += 1
        self.assertGreater(checked, 20)

    def test_the_tolerance_only_absorbs_rounding(self):
        a = gt.optimal_corridor(self.g, self.s, self.t, 0.0)
        b = gt.optimal_corridor(self.g, self.s, self.t, 0.001)
        self.assertEqual(a["cells"], b["cells"])
        wide = gt.optimal_corridor(self.g, self.s, self.t, 0.3)                   # 0.3 m is more than the 0.29 m of one diagonal detour
        self.assertGreaterEqual(wide["size"], b["size"])

    def measures(self, cells, rows=None):
        g = self.g
        cor = gt.optimal_corridor(g, self.s, self.t, 0.001)
        return gt.corridor_measures(trail_on(g, cells), centres(g, cor["cells"]), g.goal, g.cell, 1.0, cor["length_m"])

    def test_a_trail_on_either_route_scores_zero_deviation_and_full_share(self):
        for route in (TOP, BOTTOM):
            m = self.measures(route)
            self.assertEqual((m["max_distance_from_optimal_m"], m["share_within_near_distance"]), (0.0, 1.0))
            self.assertAlmostEqual(m["trail_over_optimal"], 1.0)
            self.assertEqual(m["final_distance_from_b_m"], 0.0)
            self.assertEqual(m["reference"], "optimal corridor")

    def test_a_trail_off_both_routes_does_not(self):
        inside = [(2, 2), (3, 2), (4, 2)]                                         # the middle of the wall: 1.0 m from both routes
        m = self.measures(inside)
        self.assertAlmostEqual(m["max_distance_from_optimal_m"], 1.0)
        self.assertEqual(m["share_within_near_distance"], 0.0)
        mixed = self.measures([(0, 0), (1, 0), (2, 0), (3, 0), (3, 1), (3, 2), (3, 3), (3, 4)])
        self.assertAlmostEqual(mixed["max_distance_from_optimal_m"], 1.0)
        self.assertTrue(0 < mixed["share_within_near_distance"] < 1)

    def test_the_old_one_path_measure_depended_on_which_path_was_drawn_the_corridor_does_not(self):
        g = self.g
        bottom_trail = trail_on(g, BOTTOM)
        pts_top = centres(g, TOP)
        old = gt.path_measures(bottom_trail, pts_top, g.goal, g.cell, 1.0)
        self.assertGreater(old["max_distance_from_optimal_m"], 1.5)                # judged against the top route only
        self.assertLess(old["share_within_near_distance"], 1.0)
        new = self.measures(BOTTOM)
        self.assertEqual(new["max_distance_from_optimal_m"], 0.0)

    def run_folder(self, d, trail_cells, drawn):
        folder = Path(d) / "run"
        write_run(folder, [], rows=TWO_ROUTES)
        (folder / "trail.csv").write_text("time_s,x,z,yaw_deg\n" + "".join(
            f"{0.1 * i:.3f},{x},{z},0.000\n" for i, (_, x, z) in enumerate(trail_on(self.g, trail_cells))))
        (folder / "optimal_path.json").write_text(json.dumps(unity_path(self.g, drawn)))
        return folder

    def test_evaluate_run_gives_the_same_measures_whichever_shortest_path_unity_drew(self):
        with tempfile.TemporaryDirectory() as d:
            a = gt.evaluate_run(self.run_folder(Path(d) / "a", BOTTOM, TOP), CFG)
            b = gt.evaluate_run(self.run_folder(Path(d) / "b", BOTTOM, BOTTOM), CFG)
        self.assertEqual(a["measures"], b["measures"])
        self.assertEqual((a["measures"]["max_distance_from_optimal_m"], a["measures"]["share_within_near_distance"]), (0.0, 1.0))
        self.assertTrue(a["optimal_path_check"]["match"] and b["optimal_path_check"]["match"])        # the length check is kept

    def test_the_corridor_size_and_what_unitys_path_covers_are_reported(self):
        with tempfile.TemporaryDirectory() as d:
            r = gt.evaluate_run(self.run_folder(d, TOP, TOP), CFG)
        c = r["corridor"]
        self.assertEqual((c["cells"], c["length_m"], c["astar_length_m"]), (20, 5.0, 5.0))
        self.assertEqual((c["unity_path_cells"], c["unity_path_cells_in_corridor"], c["corridor_cells_on_unity_path"]), (11, 11, 11))
        self.assertEqual(c["corridor_share_on_unity_path"], 0.55)
        self.assertTrue(c["several_shortest_paths"])
        self.assertEqual(c["astar_path_cells"], 11)

    def test_a_grid_with_one_shortest_path_has_a_corridor_equal_to_it(self):
        with tempfile.TemporaryDirectory() as d:
            g, cells = write_run(Path(d) / "r", [(0.25, 0.25), (0.75, 0.25)], rows=["0000"])             # one row: one shortest path
            r = gt.evaluate_run(Path(d) / "r", CFG)
        self.assertFalse(r["corridor"]["several_shortest_paths"])
        self.assertEqual(r["corridor"]["corridor_share_on_unity_path"], 1.0)
        self.assertEqual(r["corridor"]["cells"], r["corridor"]["unity_path_cells"])

    def test_too_little_data_and_an_unreachable_goal_are_none_not_a_guess(self):
        m = gt.corridor_measures([(0.0, 0.25, 0.25)], [(0.25, 0.25)], (1.0, 1.0), 0.5, 1.0, 2.0)
        self.assertIsNone(m["trail_over_optimal"])
        self.assertIsNone(gt.corridor_measures([], [], (0.0, 0.0), 0.5, 1.0, 0.0)["max_distance_from_optimal_m"])

    def test_the_trail_is_scored_against_cell_centres_so_half_a_step_is_the_resolution(self):
        g = self.g
        cor = gt.optimal_corridor(g, self.s, self.t, 0.001)
        c = centres(g, cor["cells"])

        def worst(trail):
            return gt.corridor_measures(trail, c, g.goal, g.cell, 1.0, cor["length_m"])["max_distance_from_optimal_m"]
        self.assertAlmostEqual(worst([(0.0, 0.5, 0.25), (0.1, 0.5, 0.25)]), 0.25)                    # midway between two centres, straight step
        self.assertAlmostEqual(worst([(0.0, 0.0, 0.0), (0.1, 0.0, 0.0)]), math.hypot(0.25, 0.25), places=3)    # the corner of the first cell
        self.assertEqual(worst([(0.0, 0.25, 0.25), (0.1, 0.75, 0.25)]), 0.0)                         # on centres: exactly 0


class IsolationTests(unittest.TestCase):
    def test_only_evaluation_code_imports_gt_path(self):
        allowed = {"hri_analysis.py", "hri_analysis_v4.py"}
        offenders = []
        for p in ROOT.rglob("*.py"):
            rel = p.relative_to(ROOT)
            if ".venv" in rel.parts or rel.parts[0] == "tests" or rel.name == "gt_path.py":
                continue
            tree = ast.parse(p.read_text(encoding="utf-8"))
            mods = set()
            for n in ast.walk(tree):
                if isinstance(n, ast.Import):
                    mods |= {a.name.split(".")[0] for a in n.names}
                elif isinstance(n, ast.ImportFrom) and n.module:
                    mods.add(n.module.split(".")[0])
                    mods |= {a.name for a in n.names}      # from . import gt_path
            if "gt_path" in mods and rel.name not in allowed:
                offenders.append(str(rel))
        self.assertEqual(offenders, [], "inference code must never import gt_path.py (evaluation only)")

    def test_inference_modules_do_not_mention_the_v4_truth_files(self):
        for name in ("hri_control.py", "hri_perception.py", "bridge/perception.py", "bridge/guide.py",
                     "bridge/server.py", "bridge/protocol.py", "gesture_adapter.py"):
            src = (ROOT / name).read_text(encoding="utf-8")
            for word in ("gt_path", "optimal_path", "truth.jsonl", "trail.csv", "grid.json"):
                self.assertNotIn(word, src.replace("docs/protocol_v3.md", ""), (name, word))


# SHA-256 of analysis.json text and analysis.md of the v3-style fixture (tests/test_trials.py fake_session, folder
# name "trials_x"), taken before hri_analysis.py was changed for v4 (2026-10-23).
V3_ANALYSIS_JSON_SHA256 = "6ba6d5bd0448d4897ca31fe907d255da84e766f7b16f1003f3e049b01b55d383"
V3_ANALYSIS_MD_SHA256 = "4f7a6089c40444b339203b32fb020f28214b7f648b8c5a2392327befc1fcc666"


def sha(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


class AnalysisHookTests(unittest.TestCase):
    def runs_for(self, base: Path):
        import test_trials as tt
        u, b = tt.fake_session(base)
        runs, _ = ht.merge(u, b)
        for r in runs:
            r["_folder"] = u.name
        return runs, u

    def render(self, runs, folders):
        res = ha.analyse(runs)
        sec = ha.path_section(runs, folders)
        if sec is not None:
            res["path_measures"] = sec
        return res, json.dumps(res, indent=2) + "\n", ha.markdown(res) + (ha.path_markdown(sec) if sec else "")

    def test_v3_output_is_byte_identical(self):
        with tempfile.TemporaryDirectory() as d:
            runs, u = self.runs_for(Path(d))
            res, js, md = self.render(runs, [u])
            self.assertNotIn("path_measures", res)
            self.assertEqual(sha(js), V3_ANALYSIS_JSON_SHA256)
            self.assertEqual(sha(md), V3_ANALYSIS_MD_SHA256)

    def test_v3_main_writes_the_v3_files_only(self):
        import io
        from contextlib import redirect_stdout
        import decision_io as dio
        with tempfile.TemporaryDirectory() as d:
            runs, u = self.runs_for(Path(d))
            ht_dir = Path(d) / "hri_trials_x"
            ht_dir.mkdir()
            for r in runs:
                (ht_dir / f"run_{r['trial']:03d}.json").write_text(json.dumps({k: v for k, v in r.items() if k != "_folder"}))
            out = Path(d) / "hri_analysis_out"
            out.mkdir()
            real = dio.new_run_dir
            dio.new_run_dir = lambda cfg, prefix: out       # keep the test out of outputs/
            try:
                with redirect_stdout(io.StringIO()):
                    ha.main([str(ht_dir)])
            finally:
                dio.new_run_dir = real
            expected = ha.analyse(ha.load_runs([ht_dir]))
            self.assertEqual(json.loads((out / "analysis.json").read_text()), json.loads(json.dumps(expected)))
            self.assertEqual((out / "analysis.md").read_text(encoding="utf-8"), ha.markdown(expected))
            self.assertNotIn("path_measures", (out / "analysis.json").read_text())

    def test_v4_files_add_path_measures(self):
        with tempfile.TemporaryDirectory() as d:
            runs, u = self.runs_for(Path(d))
            write_run(u / "run_001", [(0.25, 0.25), (0.75, 0.75), (1.25, 1.25), (1.75, 1.75)])   # run 2 has no v4 files
            res, js, md = self.render(runs, [u])
            sec = res["path_measures"]
            self.assertEqual(sec["coverage"], "1 of 2 runs have the v4 files")
            self.assertEqual(sec["optimal_path_matches"], "1 of 1")
            self.assertEqual(sec["trail_over_optimal"]["n"], 1)
            self.assertEqual(sec["final_distance_from_b_m"]["max"], 0.0)
            self.assertEqual([r["trial"] for r in sec["runs"]], [1])
            self.assertIn("## Path measures (v4 ground truth)", md)
            self.assertIn("1 of 2 runs have the v4 files", md)
            # everything before the new section is the v3 output
            base = ha.analyse(runs)
            self.assertEqual({k: v for k, v in res.items() if k != "path_measures"}, base)
            self.assertTrue(md.startswith(ha.markdown(base)))


if __name__ == "__main__":
    unittest.main()
