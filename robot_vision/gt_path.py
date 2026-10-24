"""v4 ground-truth evaluation: the grid, the optimal path, the robot's trail and the leak test (docs/protocol_v3.md,
"Per-run files Unity writes"). EVALUATION CODE ONLY: it reads Unity's ground-truth files (goal B is in grid.json).
Inference code must never import it (tests/test_gt_path.py checks that).

- load_grid / astar: the grid (0.5 m cells, blocked cells already widened by Unity) and an 8-connected A* (straight
  step 1 cell, diagonal sqrt(2) cells, no corner cutting: a diagonal step needs both side cells free).
- compare_optimal: Python's A* length against Unity's optimal_path.json length, within a tolerance from the config.
- path_measures: from trail.csv: trail length / optimal length, largest distance from the optimal polyline, share of
  trail points within near_optimal_cells of it, final distance from B.
- leak_test: every <name>_on / <name>_off image pair must be pixel-identical (max difference from the config);
  writes leak_test.json.

Usage (from robot_vision/):
    python gt_path.py run   outputs/trials_X/run_001 [--config configs/v4/gt_eval.json]
    python gt_path.py leak  outputs/trials_X/leak_test
"""

from __future__ import annotations

import argparse
import csv
import heapq
import json
import math
from pathlib import Path

HERE = Path(__file__).resolve().parent
DEFAULT_CONFIG = "configs/v4/gt_eval.json"
SQRT2 = math.sqrt(2.0)
STEPS = ((1, 0, 1.0), (-1, 0, 1.0), (0, 1, 1.0), (0, -1, 1.0),
         (1, 1, SQRT2), (1, -1, SQRT2), (-1, 1, SQRT2), (-1, -1, SQRT2))


def load_config(path: str | Path = DEFAULT_CONFIG) -> dict:
    p = Path(path)
    return json.loads((p if p.is_absolute() else HERE / p).read_text(encoding="utf-8"))


# ---------------------------------------------------------------- grid and A*

class Grid:
    """cells[iz][ix] is True when blocked. Cell (ix, iz) covers x in [origin_x + ix*s, origin_x + (ix+1)*s), same for z;
    its centre is half a cell further."""

    def __init__(self, cell_size_m: float, origin_x: float, origin_z: float, blocked: list[list[bool]],
                 start: tuple[float, float], goal: tuple[float, float]):
        self.cell = float(cell_size_m)
        self.ox, self.oz = float(origin_x), float(origin_z)
        self.blocked = blocked
        self.nz = len(blocked)
        self.nx = len(blocked[0]) if blocked else 0
        self.start, self.goal = start, goal

    def cell_of(self, x: float, z: float) -> tuple[int, int]:
        return int(math.floor((x - self.ox) / self.cell)), int(math.floor((z - self.oz) / self.cell))

    def centre(self, ix: int, iz: int) -> tuple[float, float]:
        return self.ox + (ix + 0.5) * self.cell, self.oz + (iz + 0.5) * self.cell

    def inside(self, ix: int, iz: int) -> bool:
        return 0 <= ix < self.nx and 0 <= iz < self.nz

    def free(self, ix: int, iz: int) -> bool:
        return self.inside(ix, iz) and not self.blocked[iz][ix]


def grid_from_dict(d: dict) -> Grid:
    rows = d["blocked_rows"]
    if len(rows) != d["cells_z"] or any(len(r) != d["cells_x"] for r in rows):
        raise ValueError(f"grid.json: blocked_rows must be {d['cells_z']} strings of {d['cells_x']} characters")
    if any(c not in "01" for r in rows for c in r):
        raise ValueError("grid.json: blocked_rows may only contain '0' (free) and '1' (blocked)")
    return Grid(d["cell_size_m"], d["origin_x"], d["origin_z"], [[c == "1" for c in r] for r in rows],
                (d["start"]["x"], d["start"]["z"]), (d["goal"]["x"], d["goal"]["z"]))


def load_grid(path: str | Path) -> Grid:
    return grid_from_dict(json.loads(Path(path).read_text(encoding="utf-8")))


def astar(grid: Grid, start: tuple[int, int], goal: tuple[int, int]) -> tuple[list[tuple[int, int]], float] | None:
    """Shortest 8-connected path of cells and its length in metres, or None when there is none (or an end is blocked).
    A diagonal step is allowed only when both orthogonal neighbours are free (no cutting through a blocked corner)."""
    if not (grid.free(*start) and grid.free(*goal)):
        return None

    def h(c):                       # octile distance: admissible and consistent for these step costs
        dx, dz = abs(c[0] - goal[0]), abs(c[1] - goal[1])
        return (dx + dz) + (SQRT2 - 2.0) * min(dx, dz)

    best = {start: 0.0}
    came: dict[tuple[int, int], tuple[int, int]] = {}
    heap = [(h(start), 0.0, start)]
    done = set()
    while heap:
        _, g, cur = heapq.heappop(heap)
        if cur in done:
            continue
        if cur == goal:
            path = [cur]
            while path[-1] != start:
                path.append(came[path[-1]])
            return path[::-1], g * grid.cell
        done.add(cur)
        for dx, dz, cost in STEPS:
            nx, nz = cur[0] + dx, cur[1] + dz
            if not grid.free(nx, nz):
                continue
            if dx != 0 and dz != 0 and not (grid.free(cur[0] + dx, cur[1]) and grid.free(cur[0], cur[1] + dz)):
                continue
            ng = g + cost
            if ng < best.get((nx, nz), math.inf) - 1e-12:
                best[(nx, nz)] = ng
                came[(nx, nz)] = cur
                heapq.heappush(heap, (ng + h((nx, nz)), ng, (nx, nz)))
    return None


def path_length_m(cells: list[tuple[int, int]], cell_size_m: float) -> float:
    return sum(math.hypot(b[0] - a[0], b[1] - a[1]) for a, b in zip(cells, cells[1:])) * cell_size_m


def compare_optimal(grid: Grid, unity: dict, tolerance_m: float) -> dict:
    """Python's A* from the cell of A to the cell of B against Unity's optimal_path.json
    ({"length_m", "cells": [{"ix", "iz"}, ...], "points": [{"x", "z"}, ...]}). Also checks that Unity's cells are a
    legal path (steps between neighbours, free cells, no corner cutting) with the length Unity reports."""
    s, g = grid.cell_of(*grid.start), grid.cell_of(*grid.goal)
    found = astar(grid, s, g)
    out = {"start_cell": list(s), "goal_cell": list(g), "unity_length_m": unity["length_m"],
           "tolerance_m": tolerance_m, "python_found_path": found is not None}
    if found is None:
        out.update(python_length_m=None, length_diff_m=None, match=False, unity_path_legal=None,
                   note="no path in Python's A*")
        return out
    cells, length = found
    out.update(python_length_m=round(length, 6), length_diff_m=round(abs(length - unity["length_m"]), 6))
    ucells = [(c["ix"], c["iz"]) for c in unity["cells"]]
    legal = bool(ucells) and ucells[0] == s and ucells[-1] == g and all(grid.free(*c) for c in ucells)
    for a, b in zip(ucells, ucells[1:]):
        dx, dz = b[0] - a[0], b[1] - a[1]
        if max(abs(dx), abs(dz)) != 1:
            legal = False
        elif dx != 0 and dz != 0 and not (grid.free(a[0] + dx, a[1]) and grid.free(a[0], a[1] + dz)):
            legal = False
    out["unity_path_legal"] = legal
    out["unity_length_matches_its_cells"] = abs(path_length_m(ucells, grid.cell) - unity["length_m"]) <= tolerance_m
    out["match"] = bool(out["length_diff_m"] <= tolerance_m and legal and out["unity_length_matches_its_cells"])
    return out


# ---------------------------------------------------------------- trail measures

def load_trail(path: str | Path) -> list[tuple[float, float, float]]:
    """trail.csv (time_s, x, z, yaw_deg) -> [(time_s, x, z)]."""
    with Path(path).open(encoding="utf-8", newline="") as f:
        return [(float(r["time_s"]), float(r["x"]), float(r["z"])) for r in csv.DictReader(f)]


def point_segment_distance(px: float, pz: float, ax: float, az: float, bx: float, bz: float) -> float:
    dx, dz = bx - ax, bz - az
    n2 = dx * dx + dz * dz
    t = 0.0 if n2 == 0.0 else max(0.0, min(1.0, ((px - ax) * dx + (pz - az) * dz) / n2))
    return math.hypot(px - (ax + t * dx), pz - (az + t * dz))


def distance_to_polyline(px: float, pz: float, poly: list[tuple[float, float]]) -> float:
    if len(poly) == 1:
        return math.hypot(px - poly[0][0], pz - poly[0][1])
    return min(point_segment_distance(px, pz, *a, *b) for a, b in zip(poly, poly[1:]))


def polyline_length(poly: list[tuple[float, float]]) -> float:
    return sum(math.hypot(b[0] - a[0], b[1] - a[1]) for a, b in zip(poly, poly[1:]))


def path_measures(trail: list[tuple[float, float, float]], optimal_points: list[tuple[float, float]],
                  goal: tuple[float, float], cell_size_m: float, near_cells: float) -> dict:
    """Trail against the optimal polyline. Fewer than 2 trail points or an empty optimal path give None values."""
    pts = [(x, z) for _, x, z in trail]
    opt_len = polyline_length(optimal_points)
    if len(pts) < 2 or not optimal_points:
        return {"trail_points": len(pts), "trail_length_m": None, "optimal_length_m": round(opt_len, 4) or None,
                "trail_over_optimal": None, "max_distance_from_optimal_m": None, "share_within_near_distance": None,
                "near_distance_m": near_cells * cell_size_m, "final_distance_from_b_m": None}
    d = [distance_to_polyline(x, z, optimal_points) for x, z in pts]
    near = near_cells * cell_size_m
    length = polyline_length(pts)
    return {"trail_points": len(pts), "trail_length_m": round(length, 4), "optimal_length_m": round(opt_len, 4),
            "trail_over_optimal": round(length / opt_len, 4) if opt_len > 0 else None,
            "max_distance_from_optimal_m": round(max(d), 4),
            "share_within_near_distance": round(sum(x <= near + 1e-9 for x in d) / len(d), 4),
            "near_distance_m": near,
            "final_distance_from_b_m": round(math.hypot(pts[-1][0] - goal[0], pts[-1][1] - goal[1]), 4)}


RUN_FILES = ("grid.json", "optimal_path.json", "trail.csv")


def has_v4_files(run_dir: Path) -> bool:
    return all((Path(run_dir) / f).is_file() for f in RUN_FILES)


def evaluate_run(run_dir: str | Path, cfg: dict | None = None) -> dict:
    """Both checks for one run folder (grid.json, optimal_path.json, trail.csv)."""
    cfg = cfg if cfg is not None else load_config()
    run_dir = Path(run_dir)
    grid = load_grid(run_dir / "grid.json")
    unity = json.loads((run_dir / "optimal_path.json").read_text(encoding="utf-8"))
    pts = [(p["x"], p["z"]) for p in unity["points"]]
    return {"optimal_path_check": compare_optimal(grid, unity, cfg["optimal_length_tolerance_m"]),
            "measures": path_measures(load_trail(run_dir / "trail.csv"), pts, grid.goal, grid.cell,
                                      cfg["near_optimal_cells"])}


# ---------------------------------------------------------------- leak test

def leak_test(folder: str | Path, max_pixel_diff: int = 0, write: bool = True) -> dict:
    """Compare every <name>_on.<ext> with <name>_off.<ext> (lossless images, e.g. PNG) pixel by pixel. Passes only
    when at least one pair exists, every pair has an on and an off image of the same size, and the largest absolute
    per-channel difference of every pair is at most max_pixel_diff. Writes leak_test.json (never overwrites)."""
    import numpy as np
    from PIL import Image

    folder = Path(folder)
    on, off = {}, {}
    for f in sorted(folder.iterdir()):
        if f.suffix.lower() not in (".png", ".bmp", ".tif", ".tiff", ".jpg", ".jpeg"):
            continue
        if f.stem.endswith("_on"):
            on[f.stem[:-3]] = f
        elif f.stem.endswith("_off"):
            off[f.stem[:-4]] = f
    pairs, problems = [], []
    for name in sorted(set(on) | set(off)):
        if name not in on or name not in off:
            problems.append(f"{name}: only the {'on' if name in on else 'off'} image exists")
            continue
        try:
            with Image.open(on[name]) as ia, Image.open(off[name]) as ib:
                a, b = np.asarray(ia).copy(), np.asarray(ib).copy()
        except OSError as e:
            problems.append(f"{name}: an image could not be read ({e})")
            continue
        if a.shape != b.shape:
            problems.append(f"{name}: sizes differ {a.shape} vs {b.shape}")
            continue
        diff = np.abs(a.astype(np.int32) - b.astype(np.int32))
        pairs.append({"name": name, "max_diff": int(diff.max()), "differing_pixels": int((diff.max(axis=-1) if diff.ndim == 3 else diff).astype(bool).sum()),
                      "passed": bool(diff.max() <= max_pixel_diff)})
    result = {"passed": bool(pairs) and not problems and all(p["passed"] for p in pairs),
              "max_diff": max((p["max_diff"] for p in pairs), default=None), "max_pixel_diff_allowed": max_pixel_diff,
              "pairs": pairs, "problems": problems or ([] if pairs else ["no image pairs found"])}
    if write:
        with (folder / "leak_test.json").open("x", encoding="utf-8") as f:
            f.write(json.dumps(result, indent=2) + "\n")
    return result


def main(argv=None) -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("what", choices=["run", "leak"])
    ap.add_argument("folder")
    ap.add_argument("--config", default=DEFAULT_CONFIG)
    a = ap.parse_args(argv)
    import decision_io as dio
    cfg = load_config(dio.resolve(a.config))
    folder = dio.resolve(a.folder)
    res = evaluate_run(folder, cfg) if a.what == "run" else leak_test(folder, cfg["leak_max_pixel_diff"])
    print(json.dumps(res, indent=2))
    if a.what == "leak" and not res["passed"]:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
