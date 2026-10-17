"""Robot-and-load footprint: the one required passage width, and the stopping look-ahead. Standard library only.

Every user of the required width (Step 9 decisions, make_proxy_route.py, the estimate_motion.py corridor check)
calls load_footprint(), which reads configs/robot.json and the load file it names (configs/load.json).
"""

from __future__ import annotations

import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
LOOK_AHEAD_FORMULA = "look_ahead_m = v * reaction_s + v^2 / (2 * decel) + buffer_m"
CAUTION_AHEAD_FORMULA = ("caution_ahead_m = stopping_distance + person_speed_mps * stopping_time, "
                         "stopping_distance = v * reaction_s + v^2 / (2 * decel), "
                         "stopping_time = reaction_s + v / decel")


def _resolve(p: str | Path) -> Path:
    p = Path(p)
    return p if p.is_absolute() else HERE / p


def required_width(robot: dict, load: dict | None) -> dict:
    """required_width_m = (furthest right - furthest left extent of robot and load, from the robot centre line)
    + 2 * safety_margin_per_side_m. The robot is centred on its centre line; lateral_offset_m > 0 is to the right."""
    half = robot["robot_width_m"] / 2
    left, right = -half, half
    if load:
        if not load["width_m"] > 0:
            raise ValueError("load width must be positive")
        off = load.get("lateral_offset_m", 0.0)
        left, right = min(left, off - load["width_m"] / 2), max(right, off + load["width_m"] / 2)
    margin = robot["safety_margin_per_side_m"]
    return {"required_width_m": round(right - left + 2 * margin, 6), "left_extent_m": round(left, 6),
            "right_extent_m": round(right, 6), "margin_per_side_m": margin,
            "load_label": (load or {}).get("label", "no load configured")}


def load_footprint(robot_path: str | Path = "configs/robot.json") -> dict:
    """robot.json + the load file it names -> {"robot", "load", "robot_path", "load_path", **required_width}."""
    rp = _resolve(robot_path)
    robot = json.loads(rp.read_text(encoding="utf-8"))
    lp = _resolve(robot["load_config"]) if robot.get("load_config") else None
    load = json.loads(lp.read_text(encoding="utf-8")) if lp else None
    return {"robot": robot, "load": load, "robot_path": rp, "load_path": lp, **required_width(robot, load)}


def look_ahead(robot: dict, la: dict) -> dict:
    """Stopping look-ahead from robot.json (max_speed_mps, decel_mps2) and decision.json (reaction_s, buffer_m).
    Refuses a declared look_ahead_m that no longer matches its inputs."""
    v, decel = robot["max_speed_mps"], robot["decel_mps2"]
    if not (v > 0 and decel > 0):
        raise ValueError("max_speed_mps and decel_mps2 must be positive")
    value = round(v * la["reaction_s"] + v * v / (2 * decel) + la["buffer_m"], 6)
    declared = la.get("look_ahead_m")
    if declared is not None and abs(declared - value) > 1e-6:
        raise ValueError(f"declared look_ahead_m {declared} != {value} from {LOOK_AHEAD_FORMULA} "
                         f"(v={v}, decel={decel}, reaction_s={la['reaction_s']}, buffer_m={la['buffer_m']})")
    return {"formula": LOOK_AHEAD_FORMULA, "max_speed_mps": v, "decel_mps2": decel,
            "reaction_s": la["reaction_s"], "buffer_m": la["buffer_m"],
            "reaction_distance_m": round(v * la["reaction_s"], 6), "braking_distance_m": round(v * v / (2 * decel), 6),
            "look_ahead_m": value}


def caution_ahead(robot: dict, la: dict, ca: dict) -> dict:
    """Caution distance: how far a walking person can come while the robot stops. Uses reaction_s from the
    look-ahead block and v, decel from robot.json. Refuses a declared caution_ahead_m that no longer matches."""
    v, decel, reaction = robot["max_speed_mps"], robot["decel_mps2"], la["reaction_s"]
    stop_dist = v * reaction + v * v / (2 * decel)
    stop_time = reaction + v / decel
    value = round(stop_dist + ca["person_speed_mps"] * stop_time, 6)
    declared = ca.get("caution_ahead_m")
    if declared is not None and abs(declared - value) > 1e-6:
        raise ValueError(f"declared caution_ahead_m {declared} != {value} from {CAUTION_AHEAD_FORMULA} "
                         f"(v={v}, decel={decel}, reaction_s={reaction}, person_speed_mps={ca['person_speed_mps']})")
    return {"formula": CAUTION_AHEAD_FORMULA, "stopping_distance_m": round(stop_dist, 6),
            "stopping_time_s": round(stop_time, 6), "person_speed_mps": ca["person_speed_mps"],
            "caution_ahead_m": value}
