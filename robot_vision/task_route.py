"""The robot's map per task: Task 2 uses configs/roadmap.json as it is; Task 1 adds the checkpoints of
configs/task1_route.json on the roadmap's straight line (A -> J1 -> E1), each a stop where the worker is asked.

The same rule is implemented for the Unity scenario side in Assets/WarehouseRobot/HRI/Scripts/Task1Route.cs; both
are pinned to the same positions by tests (tests/test_task_route.py, Task1RouteTests.cs). The straight line is found
from the map alone (start node, then FORWARD at every junction), never from goal B; roadmap.json stays unchanged.

route_id() names the map a run uses ("Task2", or "Task1:C1,J1,C3"); the bridge sends it with every command and the
Unity trial runner refuses to start trials when it is not the map of its own task.

task1_worker_stands() is scenario data (where the Task 1 workers stand); the bridge never uses it.
"""

from __future__ import annotations

import copy
import math

TASKS = ("Task1", "Task2")
TASK1_ROUTE_CONFIG = "configs/task1_route.json"
ROADMAP_CONFIG = "configs/roadmap.json"


def straight_line(road: dict) -> list[str]:
    """Node names from the start along its only branch, then FORWARD at every junction, to an endpoint."""
    line = [road["start"]]
    while True:
        node = line[-1]
        kind = road["nodes"][node]["kind"]
        if kind == "endpoint":
            return line
        branches = road.get("branches", {}).get(node, {})
        nxt = branches.get("FORWARD") if kind == "junction" else (next(iter(branches.values())) if len(branches) == 1 else None)
        if nxt is None or nxt in line:
            raise ValueError(f"the straight line from {road['start']} ends at {node} without an endpoint")
        line.append(nxt)


def _pos(road: dict, name: str) -> tuple[float, float]:
    n = road["nodes"][name]
    return float(n["x"]), float(n["z"])


def checkpoints(road: dict, count: int, merge_m: float) -> list[tuple[str, float, float, bool]]:
    """Every stop on the straight line, in driving order: (name, x, z, is_existing_junction). Checkpoint k of count
    sits k / (count + 1) of the way along the line (by length); one within merge_m of a junction is that junction.
    Junctions on the line are stops too."""
    if count < 0:
        raise ValueError("checkpoints must be >= 0")
    line = straight_line(road)
    pts = [_pos(road, n) for n in line]
    seg = [math.hypot(b[0] - a[0], b[1] - a[1]) for a, b in zip(pts, pts[1:])]
    total = sum(seg)
    along = [0.0]
    for s in seg:
        along.append(along[-1] + s)
    stops: dict[float, tuple[str, float, float, bool]] = {}
    for i, name in enumerate(line):
        if road["nodes"][name]["kind"] == "junction":
            stops[along[i]] = (name, pts[i][0], pts[i][1], True)
    for k in range(1, count + 1):
        d = total * k / (count + 1)
        i = max(j for j in range(len(seg)) if along[j] <= d + 1e-9)
        i = min(i, len(seg) - 1)
        f = (d - along[i]) / seg[i] if seg[i] > 0 else 0.0
        x = pts[i][0] + (pts[i + 1][0] - pts[i][0]) * f
        z = pts[i][1] + (pts[i + 1][1] - pts[i][1]) * f
        near = [a for a, s in stops.items() if s[3] and math.hypot(s[1] - x, s[2] - z) <= merge_m]
        if near:
            continue                                   # this checkpoint is the junction already listed
        for j, name in enumerate(line):
            if math.hypot(pts[j][0] - x, pts[j][1] - z) <= merge_m:
                raise ValueError(f"checkpoint C{k} falls on {name}, which is not a junction")
        stops[d] = (f"C{k}", round(x, 6), round(z, 6), False)
    return [stops[a] for a in sorted(stops)]


def task1_roadmap(road: dict, route: dict) -> dict:
    """Copy of the roadmap with Task 1's checkpoints inserted as junctions on the straight line: each has one
    FORWARD branch to the next stop; a junction on the line keeps its other branches."""
    out = copy.deepcopy(road)
    line = straight_line(road)
    stops = checkpoints(road, int(route["checkpoints"]), float(route["merge_with_junction_m"]))
    chain = [line[0]] + [s[0] for s in stops] + [line[-1]]
    for name, x, z, existing in stops:
        if not existing:
            out["nodes"][name] = {"x": x, "z": z, "kind": "junction"}
    for prev, node, nxt in zip(chain, chain[1:], chain[2:] + [None]):
        if nxt is None:
            break
        if node != line[0]:
            out["nodes"][node]["arrive_from"] = prev
        b = out.setdefault("branches", {}).setdefault(node, {})
        b["FORWARD"] = nxt
    first = out["branches"][line[0]]
    out["branches"][line[0]] = {next(iter(first)): chain[1]}   # the start's only branch now leads to the first stop
    out["task1_stops"] = [s[0] for s in stops]
    return out


def task1_worker_stands(road: dict, route: dict) -> list[tuple[str, float, float, float]]:
    """SCENARIO SIDE ONLY (Unity scene builder / trial runner, simulator, tests): the Task 1 workers, one per stop,
    as (stop, x, z, facing yaw deg): worker_ahead_m ahead of the stop and worker_right_m to the right of the arrival
    direction (previous stop -> stop), facing back toward the arriving robot. Never part of the controller's map:
    the robot finds the workers by vision. Same rule as Task1Route.WorkerStand in Unity (pinned by both test suites)."""
    stops = checkpoints(road, int(route["checkpoints"]), float(route["merge_with_junction_m"]))
    ahead, right = float(route["worker_ahead_m"]), float(route["worker_right_m"])
    prev = _pos(road, straight_line(road)[0])
    out = []
    for name, x, z, _ in stops:
        dx, dz = x - prev[0], z - prev[1]
        n = math.hypot(dx, dz)
        fx, fz = dx / n, dz / n
        rx, rz = fz, -fx                          # right of the arrival direction (Unity: yaw grows clockwise)
        yaw = (math.degrees(math.atan2(-fx, -fz)) + 360.0) % 360.0
        out.append((name, round(x + fx * ahead + rx * right, 6), round(z + fz * ahead + rz * right, 6), round(yaw, 6)))
        prev = (x, z)
    return out


def route_id(task: str, road: dict | None = None) -> str:
    """'Task2' (the roadmap as it is) or 'Task1:<stops>' (e.g. 'Task1:C1,J1,C3')."""
    if task == "Task2":
        return "Task2"
    if task == "Task1":
        return "Task1:" + ",".join(road["task1_stops"])
    raise ValueError(f"task must be one of {TASKS}, not {task!r}")


def map_for_task(task: str, load_json) -> tuple[dict, str, list[str]]:
    """(roadmap config the controller uses, route id, config files it came from) for a task."""
    road = load_json(ROADMAP_CONFIG)
    if task == "Task2":
        return road, route_id(task), [ROADMAP_CONFIG]
    if task == "Task1":
        m = task1_roadmap(road, load_json(TASK1_ROUTE_CONFIG))
        return m, route_id(task, m), [ROADMAP_CONFIG, TASK1_ROUTE_CONFIG]
    raise ValueError(f"task must be one of {TASKS}, not {task!r}")
