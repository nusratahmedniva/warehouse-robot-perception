"""Step 9 inputs and outputs around decision.py: configs, placeholder providers, scenario files, run folders.

Providers. A decision frame is assembled from three sources, each behind a small interface:
- persons:  persons_at(t) -> list[PersonState]   (THUD: Step 8 motion_states.csv; Unity: the scene adapter)
- passage:  passage_at(t) -> PassageState        (placeholder until Step 6 exists)
- gestures: gestures_at(t) -> list[GestureEvent] (placeholder until the gesture adapter exists)
The placeholders here read scenario / script files. The real gesture module connects later through an adapter
that outputs GestureEvent; its code is not touched.

Scenario files (tests/scenarios/*.json) are plain JSON so the same cases can be replayed in Unity:
    {"name", "description", "config_assumptions": {decision.json key: value},
     "corridor": {"label", "centreline_xz_m": [[x, z], ...], "width_m": number | "required"},
     "time": {"start_s", "end_s", "dt_s"},          frames at start_s + k*dt_s up to end_s
     "robot_xz": [x, z] | null,
     "persons":  [{"track_id", "from_t", "to_t", "position_xz" | null, "velocity_xz" | null, "advance": bool,
                   "distance_m" (optional; default = distance to robot_xz), "distance_lower_bound_m" (optional),
                   "motion_label", "motion_trusted"}],
     "passage":  [{"from_t", "to_t", "status", "available_width_m"}],   not covered -> not_evaluated
     "gestures": [{"from_t", "to_t", "track_id", "gesture", "confidence"}],  one event per frame
     "expect":   [{"from_t", "to_t", "decision", "rule", "track_ids" (optional), "reason_contains" (optional)}]}
Every interval is half-open [from_t, to_t).
"""

from __future__ import annotations

import csv
import hashlib
import json
import math
import platform
import subprocess
import sys
from datetime import datetime
from pathlib import Path

import footprint as fp
import run_paths as rp
from decision import (RULE_NAMES, Decision, DecisionEngine, DecisionFrame, GestureEvent, PassageState, PersonState,
                      RouteCorridor)

HERE = Path(__file__).resolve().parent
DEFAULT_CONFIG = "configs/decision.json"
EPS = 1e-9


def resolve(p: str | Path) -> Path:
    p = Path(p)
    return p if p.is_absolute() else HERE / p


def read_json(p: str | Path) -> dict:
    return json.loads(resolve(p).read_text(encoding="utf-8"))


def load_decision_config(path: str | Path = DEFAULT_CONFIG) -> tuple[dict, dict, dict, dict]:
    """(decision config, robot config, load config, footprint record). The required width comes only from
    footprint.load_footprint (robot.json + the load file it names); look_ahead_m is recomputed and checked."""
    cfg = read_json(path)
    foot = fp.load_footprint(resolve(cfg["paths"]["robot_config"]))
    la = fp.look_ahead(foot["robot"], cfg["look_ahead"])
    ca = fp.caution_ahead(foot["robot"], cfg["look_ahead"], cfg["caution_ahead"])
    if ca["caution_ahead_m"] < la["look_ahead_m"] - EPS:
        raise ValueError(f"caution_ahead_m {ca['caution_ahead_m']} < look_ahead_m {la['look_ahead_m']}")
    cfg = {**cfg, "look_ahead": {**cfg["look_ahead"], **la}, "caution_ahead": {**cfg["caution_ahead"], **ca},
           "caution_ahead_m": ca["caution_ahead_m"]}
    return cfg, foot["robot"], foot["load"], foot


def footprint_files(foot: dict) -> list[Path]:
    return [foot["robot_path"]] + ([foot["load_path"]] if foot["load_path"] else [])


def footprint_record(foot: dict) -> dict:
    return {k: v for k, v in foot.items() if k not in ("robot", "load")}


def _within(seg: dict, t: float) -> bool:
    return seg["from_t"] - EPS <= t < seg["to_t"] - EPS


# ---------------------------------------------------------------- placeholder providers

class ScriptedPassage:
    """Placeholder for Step 6: passage status from time segments. Not covered -> not_evaluated."""

    def __init__(self, segments: list[dict], required_width_m: float):
        self.segments, self.required = segments, required_width_m

    def passage_at(self, t: float) -> PassageState:
        for s in self.segments:
            if _within(s, t):
                return PassageState(s["status"], s.get("available_width_m"), self.required)
        return PassageState("not_evaluated", None, self.required)


class ScriptedGestures:
    """Placeholder for the gesture adapter: one GestureEvent per frame while a segment is active."""

    def __init__(self, segments: list[dict]):
        self.segments = segments

    def gestures_at(self, t: float) -> list[GestureEvent]:
        return [GestureEvent(t, s.get("track_id"), s["gesture"], s.get("confidence", 1.0))
                for s in self.segments if _within(s, t)]


class ScriptedPersons:
    def __init__(self, segments: list[dict], robot_xz):
        self.segments, self.robot = segments, robot_xz

    def persons_at(self, t: float) -> list[PersonState]:
        out = []
        for s in self.segments:
            if not _within(s, t):
                continue
            pos, vel = s.get("position_xz"), s.get("velocity_xz")
            if pos is not None and vel is not None and s.get("advance"):
                pos = [pos[0] + vel[0] * (t - s["from_t"]), pos[1] + vel[1] * (t - s["from_t"])]
            dist = s.get("distance_m")
            if dist is None and pos is not None and self.robot is not None:
                dist = math.hypot(pos[0] - self.robot[0], pos[1] - self.robot[1])
            out.append(PersonState(s["track_id"], t, tuple(pos) if pos is not None else None, dist,
                                   s.get("motion_label", "unknown"), tuple(vel) if vel is not None else None,
                                   bool(s.get("motion_trusted", False)), s.get("distance_lower_bound_m")))
        return out


# ---------------------------------------------------------------- scenarios

def scenario_corridor(sc: dict, required_width_m: float) -> RouteCorridor:
    c = sc["corridor"]
    w = required_width_m if c["width_m"] == "required" else float(c["width_m"])
    return RouteCorridor(tuple(tuple(p) for p in c["centreline_xz_m"]), w, c.get("label", "scenario_corridor"))


def scenario_times(sc: dict) -> list[float]:
    tm = sc["time"]
    n = int(math.floor((tm["end_s"] - tm["start_s"]) / tm["dt_s"] + 1e-6))
    return [round(tm["start_s"] + k * tm["dt_s"], 6) for k in range(n + 1)]


def scenario_frames(sc: dict, required_width_m: float):
    robot = sc.get("robot_xz")
    persons = ScriptedPersons(sc.get("persons", []), robot)
    passage = ScriptedPassage(sc.get("passage", []), required_width_m)
    gestures = ScriptedGestures(sc.get("gestures", []))
    for t in scenario_times(sc):
        yield DecisionFrame(t, tuple(persons.persons_at(t)), passage.passage_at(t), tuple(gestures.gestures_at(t)),
                            tuple(robot) if robot is not None else None)


def check_assumptions(sc: dict, cfg: dict, required: dict) -> list[str]:
    """Config values a scenario's timings were written for; a mismatch means the scenario needs revisiting."""
    have = {**cfg, "required_width_m": required["required_width_m"], "look_ahead_m": cfg["look_ahead"]["look_ahead_m"]}
    return [f"{k}: scenario assumes {v}, config has {have.get(k)}"
            for k, v in sc.get("config_assumptions", {}).items() if have.get(k) != v]


def run_scenario(sc: dict, cfg: dict, required: dict) -> list[Decision]:
    engine = DecisionEngine(cfg, required, scenario_corridor(sc, required["required_width_m"]))
    return [engine.step(f) for f in scenario_frames(sc, required["required_width_m"])]


def check_expectations(sc: dict, decisions: list[Decision]) -> list[str]:
    errors = []
    for e in sc.get("expect", []):
        sel = [d for d in decisions if _within(e, d.timestamp)]
        if not sel:
            errors.append(f"no frames in [{e['from_t']}, {e['to_t']})")
        for d in sel:
            got = (d.decision, d.rule)
            if got != (e["decision"], e["rule"]):
                errors.append(f"t={d.timestamp}: expected {e['decision']} rule {e['rule']}, got {got[0]} rule "
                              f"{got[1]} ({d.reason})")
            elif "track_ids" in e and sorted(map(str, d.track_ids)) != sorted(map(str, e["track_ids"])):
                errors.append(f"t={d.timestamp}: expected tracks {e['track_ids']}, got {d.track_ids}")
            elif "reason_contains" in e and e["reason_contains"] not in d.reason:
                errors.append(f"t={d.timestamp}: reason {d.reason!r} lacks {e['reason_contains']!r}")
    return errors


# ---------------------------------------------------------------- run folders

CSV_FIELDS = ["timestamp", "decision", "rule", "rule_name", "reason", "track_ids", "passage_status",
              "passage_effective_status", "available_width_m", "required_width_m", "n_persons", "n_in_stop_zone",
              "n_entering", "n_in_caution_zone", "gestures"]


def git_info() -> dict:
    def git(*a):
        try:
            return subprocess.run(["git", *a], cwd=HERE, capture_output=True, text=True, timeout=20).stdout.strip()
        except (OSError, subprocess.SubprocessError):
            return None
    return {"commit": git("rev-parse", "HEAD"), "branch": git("rev-parse", "--abbrev-ref", "HEAD"),
            "uncommitted_changes": bool(git("status", "--porcelain", "--untracked-files=no"))}


def sha256(p: Path) -> str:
    return hashlib.sha256(p.read_bytes()).hexdigest()


def new_run_dir(cfg: dict, prefix: str) -> Path:
    """A new timestamped folder under the configured output root; never reuses an existing one."""
    root = resolve(cfg["paths"]["output_root"])
    rp.set_active_roots(rp.make_roots(output_root=root))
    out = root / f"{prefix}_{datetime.now():%Y%m%d_%H%M%S}"
    if out.exists():
        raise SystemExit(f"Output folder already exists, not overwriting: {out}")
    out.mkdir(parents=True)
    return out


def write_json(path: Path, data) -> None:
    path.write_text(rp.dumps(data, indent=2, default=str) + "\n", encoding="utf-8")


def copy_configs(out: Path, paths: list[Path]) -> dict:
    (out / "config_used").mkdir(exist_ok=False)
    hashes = {}
    for p in paths:
        (out / "config_used" / p.name).write_bytes(p.read_bytes())
        hashes[p.name] = sha256(p)
    return hashes


def run_info(cfg_path: Path, extra: dict) -> dict:
    return {"created": datetime.now().isoformat(timespec="seconds"),
            "command": " ".join([Path(sys.executable).name] + sys.argv), "git": git_info(),
            "python": platform.python_version(), "platform": platform.platform(),
            "decision_config": str(cfg_path), "decision_config_sha256": sha256(cfg_path), **extra}


def csv_row(d: Decision) -> dict:
    s, ps = d.snapshot, d.snapshot["persons"]
    gest = ";".join(f"{g['track_id']}:{g['gesture']}" for g in s["gestures"] if g["gesture"] != "NONE")
    return {"timestamp": f"{d.timestamp:.4f}", "decision": d.decision, "rule": d.rule,
            "rule_name": RULE_NAMES[d.rule],
            "reason": d.reason, "track_ids": ";".join(map(str, d.track_ids)),
            "passage_status": s["passage"]["status"], "passage_effective_status": s["passage_effective_status"],
            "available_width_m": "" if s["passage"]["available_width_m"] is None else s["passage"]["available_width_m"],
            "required_width_m": s["required_width_m"], "n_persons": len(ps),
            "n_in_stop_zone": sum(a["in_stop_zone"] for a in ps),
            "n_entering": sum(a["entry_in_s"] is not None for a in ps),
            "n_in_caution_zone": sum(a["in_caution_zone"] for a in ps), "gestures": gest}


def write_decisions(out: Path, decisions: list[Decision], log_header: dict) -> None:
    with (out / "decisions.csv").open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=CSV_FIELDS)
        w.writeheader()
        for d in decisions:
            w.writerow(csv_row(d))
    counts: dict = {}
    for d in decisions:
        counts[f"{d.decision} rule {d.rule}"] = counts.get(f"{d.decision} rule {d.rule}", 0) + 1
    write_json(out / "decision_log.json", {**log_header, "n_decisions": len(decisions),
                                           "decision_counts": dict(sorted(counts.items())),
                                           "decisions": [d.as_dict() for d in decisions]})


def mark_complete(out: Path) -> None:
    (out / "COMPLETE").write_text(datetime.now().isoformat(), encoding="utf-8")
