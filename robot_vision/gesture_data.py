"""v4 gesture data: Unity's truth.jsonl, joined to pan-tilt frames and cut into labelled clips (docs/protocol_v3.md).
EVALUATION CODE ONLY: it reads the workers' true commands. Inference code must never import it (tests check that).

- parse_truth / load_truth: read truth.jsonl and check every line against the protocol table; a bad line raises
  TruthError naming the file and line. Nothing is repaired or guessed.
- frames_from_messages: the pan-tilt frame headers (frame_index, time_s, pose) of a bridge run's messages.jsonl.
- join: each frame gets, per worker, the nearest truth row in time if it is within truth_join_max_s
  (configs/v4/gesture_data.json), else no label. Both times are Unity Time.time (no offset).
- build_clips / attach_frames: one clip per worker per uninterrupted stretch of rows with the same non-NONE
  true_command, arm and animation clip; with its look, phases, true POINT angle and, from the joined frames, the
  robot-to-worker distance.

Usage (from robot_vision/):  python gesture_data.py outputs/trials_X/run_001/truth.jsonl [--messages outputs/bridge_guide_Y/messages.jsonl]
"""

from __future__ import annotations

import argparse
import bisect
import json
import math
import statistics as st
from collections import defaultdict
from dataclasses import dataclass, field
from pathlib import Path

HERE = Path(__file__).resolve().parent
DEFAULT_CONFIG = "configs/v4/gesture_data.json"


class TruthError(ValueError):
    """A truth.jsonl line (or the file) does not follow docs/protocol_v3.md."""


def load_config(path: str | Path = DEFAULT_CONFIG) -> dict:
    p = Path(path)
    return json.loads((p if p.is_absolute() else HERE / p).read_text(encoding="utf-8"))


def _reject_constant(name: str):
    raise ValueError(f"non-finite number {name}")


def _is_num(x) -> bool:
    return isinstance(x, (int, float)) and not isinstance(x, bool) and math.isfinite(x)


def _is_int(x) -> bool:
    return isinstance(x, int) and not isinstance(x, bool)


@dataclass(frozen=True)
class TruthRow:
    line: int
    time_s: float
    worker_id: int
    look: str
    x: float
    z: float
    true_command: str
    point_angle_deg: float
    arm: str
    phase: str
    is_commander: bool
    clip: str = ""


def _parse_line(obj: dict, n: int, where: str, cfg: dict) -> TruthRow:
    def bad(msg):
        return TruthError(f"{where} line {n}: {msg}")

    if not isinstance(obj, dict):
        raise bad("not a JSON object")
    kinds = {"time_s": _is_num, "worker_id": _is_int, "look": lambda v: isinstance(v, str) and v != "",
             "x": _is_num, "z": _is_num, "true_command": lambda v: isinstance(v, str), "point_angle_deg": _is_num,
             "arm": lambda v: isinstance(v, str), "phase": lambda v: isinstance(v, str),
             "is_commander": lambda v: isinstance(v, bool)}
    for key, ok in kinds.items():
        if key not in obj:
            raise bad(f"missing field {key!r}")
        if not ok(obj[key]):
            raise bad(f"field {key!r} has a wrong type or value ({obj[key]!r})")
    for key, allowed in (("true_command", cfg["commands"]), ("arm", cfg["arms"]), ("phase", cfg["phases"])):
        if obj[key] not in allowed:
            raise bad(f"{key} {obj[key]!r} is not one of {allowed}")
    if obj["true_command"] != "POINT" and obj["point_angle_deg"] != -1:
        raise bad(f"point_angle_deg must be -1 unless true_command is POINT (got {obj['true_command']} "
                  f"with {obj['point_angle_deg']})")
    clip = obj.get("clip", "")
    if not isinstance(clip, str):
        raise bad(f"field 'clip' must be a string ({clip!r})")
    return TruthRow(n, float(obj["time_s"]), obj["worker_id"], obj["look"], float(obj["x"]), float(obj["z"]),
                    obj["true_command"], float(obj["point_angle_deg"]), obj["arm"], obj["phase"], obj["is_commander"], clip)


def parse_truth(lines, cfg: dict | None = None, where: str = "truth.jsonl") -> list[TruthRow]:
    """Parse and check truth lines (blank lines are skipped, line numbers count them). Raises TruthError."""
    cfg = cfg if cfg is not None else load_config()
    rows: list[TruthRow] = []
    for n, text in enumerate(lines, 1):
        if not text.strip():
            continue
        try:
            obj = json.loads(text, parse_constant=_reject_constant)
        except ValueError as e:
            raise TruthError(f"{where} line {n}: not valid JSON ({e})") from None
        rows.append(_parse_line(obj, n, where, cfg))
    looks: dict[int, str] = {}
    last_t: dict[int, float] = {}
    commanders: dict[float, int] = {}
    for r in rows:
        if looks.setdefault(r.worker_id, r.look) != r.look:
            raise TruthError(f"{where} line {r.line}: worker {r.worker_id} has look {r.look!r} but {looks[r.worker_id]!r} earlier")
        if r.time_s < last_t.get(r.worker_id, -math.inf):
            raise TruthError(f"{where} line {r.line}: time_s {r.time_s} goes backwards for worker {r.worker_id}")
        last_t[r.worker_id] = r.time_s
        if r.is_commander:
            if commanders.setdefault(r.time_s, r.worker_id) != r.worker_id:
                raise TruthError(f"{where} line {r.line}: two commanders at time_s {r.time_s} "
                                 f"(workers {commanders[r.time_s]} and {r.worker_id})")
    return rows


def load_truth(path: str | Path, cfg: dict | None = None) -> list[TruthRow]:
    p = Path(path)
    return parse_truth(p.read_text(encoding="utf-8").splitlines(), cfg, where=p.name)


# ---------------------------------------------------------------- frames and the join

def frames_from_messages(messages_jsonl: str | Path) -> list[dict]:
    """Pan-tilt frames Python received (bridge run messages.jsonl): [{"frame_index", "time_s", "pose"}] in file order."""
    out = []
    for text in Path(messages_jsonl).read_text(encoding="utf-8").splitlines():
        m = json.loads(text)
        if m.get("dir") == "in" and m.get("type") == "frame_pan_tilt":
            h = m["header"]
            out.append({"frame_index": h["frame_index"], "time_s": h["time_s"], "pose": h.get("pose")})
    return out


@dataclass
class Join:
    labels: list[dict] = field(default_factory=list)       # one per (frame, worker) with a row within tolerance
    unlabelled_frames: list[int] = field(default_factory=list)   # frames with no worker row within tolerance
    n_frames: int = 0
    tolerance_s: float = 0.0

    def coverage(self) -> str:
        done = self.n_frames - len(self.unlabelled_frames)
        return f"{done} of {self.n_frames} frames have a truth label within {self.tolerance_s} s"


def join(frames: list[dict], rows: list[TruthRow], cfg: dict | None = None) -> Join:
    """Label each frame with, for every worker, the truth row nearest in time (|dt| <= truth_join_max_s). A worker with
    no row that close gets no label for that frame; a frame with no label at all is listed as unlabelled."""
    cfg = cfg if cfg is not None else load_config()
    tol = float(cfg["truth_join_max_s"])
    by_worker: dict[int, list[TruthRow]] = defaultdict(list)
    for r in rows:
        by_worker[r.worker_id].append(r)
    times = {w: [r.time_s for r in rs] for w, rs in by_worker.items()}
    res = Join(n_frames=len(frames), tolerance_s=tol)
    for f in frames:
        got = False
        for w, rs in sorted(by_worker.items()):
            ts = times[w]
            i = bisect.bisect_left(ts, f["time_s"])
            near = [j for j in (i - 1, i) if 0 <= j < len(rs)]
            j = min(near, key=lambda k: abs(ts[k] - f["time_s"]))
            dt = rs[j].time_s - f["time_s"]
            if abs(dt) <= tol + 1e-9:
                pose = f.get("pose") or {}
                dist = math.hypot(rs[j].x - pose["x"], rs[j].z - pose["z"]) if "x" in pose and "z" in pose else None
                res.labels.append({"frame_index": f["frame_index"], "frame_time_s": f["time_s"], "worker_id": w,
                                   "row": rs[j], "dt_s": round(dt, 6), "distance_m": None if dist is None else round(dist, 4)})
                got = True
        if not got:
            res.unlabelled_frames.append(f["frame_index"])
    return res


# ---------------------------------------------------------------- labelled clips

@dataclass
class Clip:
    worker_id: int
    look: str
    clip: str                      # animation clip name ("" when Unity did not log one)
    command: str
    arm: str
    t_start: float
    t_end: float
    phases: list[str]
    commander_share: float         # fraction of the clip's rows in which this worker was the commander
    point_angle_hold_deg: float | None    # circular mean of the true POINT angle over the "holding" rows; None otherwise
    n_rows: int
    row_lines: list[int] = field(default_factory=list)
    frame_indices: list[int] = field(default_factory=list)
    distance_m: float | None = None       # median robot-worker distance over the clip's joined frames; None if no frame had a pose

    def label(self) -> dict:
        return {k: getattr(self, k) for k in ("worker_id", "look", "clip", "command", "arm", "t_start", "t_end",
                                              "phases", "commander_share", "point_angle_hold_deg", "n_rows",
                                              "frame_indices", "distance_m")}


def _circular_mean_deg(angles: list[float]) -> float:
    s = sum(math.sin(math.radians(a)) for a in angles)
    c = sum(math.cos(math.radians(a)) for a in angles)
    return math.degrees(math.atan2(s, c))


def build_clips(rows: list[TruthRow]) -> list[Clip]:
    """One clip per worker per uninterrupted stretch of rows with the same non-NONE true_command, arm and animation
    clip. A NONE row, or a change of command, arm or clip, ends it. The phases of its rows are kept (in order, once)."""
    clips: list[Clip] = []
    by_worker: dict[int, list[TruthRow]] = defaultdict(list)
    for r in rows:
        by_worker[r.worker_id].append(r)
    for w, rs in sorted(by_worker.items()):
        run: list[TruthRow] = []

        def flush():
            if not run:
                return
            hold = [r.point_angle_deg for r in run if r.phase == "holding" and r.true_command == "POINT"]
            phases = list(dict.fromkeys(r.phase for r in run))
            clips.append(Clip(w, run[0].look, run[0].clip, run[0].true_command, run[0].arm, run[0].time_s,
                              run[-1].time_s, phases, sum(r.is_commander for r in run) / len(run),
                              round(_circular_mean_deg(hold), 3) if hold else None, len(run),
                              [r.line for r in run]))
            run.clear()

        for r in rs:
            key = (r.true_command, r.arm, r.clip)
            if r.true_command == "NONE" or (run and key != (run[0].true_command, run[0].arm, run[0].clip)):
                flush()
            if r.true_command != "NONE":
                run.append(r)
        flush()
    return sorted(clips, key=lambda c: (c.t_start, c.worker_id))


def attach_frames(clips: list[Clip], joined: Join) -> list[Clip]:
    """Add to each clip the frames whose label for its worker is one of the clip's rows, and the median distance."""
    for c in clips:
        lines = set(c.row_lines)
        got = [lab for lab in joined.labels if lab["worker_id"] == c.worker_id and lab["row"].line in lines]
        c.frame_indices = [lab["frame_index"] for lab in got]
        d = [lab["distance_m"] for lab in got if lab["distance_m"] is not None]
        c.distance_m = round(st.median(d), 4) if d else None
    return clips


def clip_summary(clips: list[Clip]) -> dict:
    """Counts only (no accuracy): clips per command, per look, per animation clip."""
    out: dict = {"clips": len(clips), "per_command": defaultdict(int), "per_look": defaultdict(int),
                 "per_clip_name": defaultdict(int), "without_frames": sum(1 for c in clips if not c.frame_indices)}
    for c in clips:
        out["per_command"][c.command] += 1
        out["per_look"][c.look] += 1
        out["per_clip_name"][c.clip or "(none logged)"] += 1
    return {k: dict(v) if isinstance(v, defaultdict) else v for k, v in out.items()}


def main(argv=None) -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("truth", help="run_###/truth.jsonl")
    ap.add_argument("--messages", help="bridge run messages.jsonl, to join the pan-tilt frames")
    ap.add_argument("--config", default=DEFAULT_CONFIG)
    a = ap.parse_args(argv)
    import decision_io as dio
    cfg = load_config(dio.resolve(a.config))
    rows = load_truth(dio.resolve(a.truth), cfg)
    clips = build_clips(rows)
    out = {"rows": len(rows)}
    if a.messages:
        j = join(frames_from_messages(dio.resolve(a.messages)), rows, cfg)
        attach_frames(clips, j)
        out["join"] = j.coverage()
    out["summary"] = clip_summary(clips)
    print(json.dumps(out, indent=2))


if __name__ == "__main__":
    main()
