"""Does a STOP reading restart the 0.5 s PROCEED hold? (Avatar/Config/experiments_ab.md section 15 addendum 3, item 4; report only.)

Replays the live dialog class hri_control.GestureDialog (unchanged from v3; the v4 controller's dialog) on every ask of the step-5 sessions.
The frames the dialog saw are the v4_log.jsonl rows: ControllerV4._log_frame runs only inside _read_tick, which the base Controller.step skips
while a safety stop holds. Each session's own config_used values are used. Three models:
  S  = the code as written: a frame read STOP never reaches the dialog (Controller.step returns at the safety stop before _tick);
  R1 = the claim: every STOP frame restarts the hold (candidate NONE, since = that frame's time);
  R2 = a STOP frame given to the dialog as a no-direction reading (the max_none_gap_s rule decides; the change tried in AUDIT.md 16.19.3).
STOP frames = distinct gesture_time_s of the decisions.csv rows with safety 'STOP gesture' in the read state, inside the ask. Each model's
acceptance (controller time) is compared with the logged t_accept of python_trial_###.json.

Usage, from the repository root with the project venv:
  Windows: robot_vision\\.venv\\Scripts\\python.exe finals_v4\\replay_dialog_hold.py
  macOS:   robot_vision/.venv/bin/python finals_v4/replay_dialog_hold.py
Writes a new folder <outputs>/replay_dialog_hold_<time>/ (report.md, asks.csv, examples.json, run_info.json).
"""
from __future__ import annotations

import csv
import json
import subprocess
import sys
from datetime import datetime
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
CONFIG = json.loads(Path(__file__).with_suffix(".json").read_text(encoding="utf-8"))
PY = REPO / CONFIG["python_root"]
sys.path.insert(0, str(PY))
import hri_control as hc  # noqa: E402  (the dialog class only; read, never changed)

MODELS = ("S", "R1", "R2")


def dialog_cfg(bridge: Path) -> tuple[dict, str]:
    run = json.loads((bridge / "run_info.json").read_text(encoding="utf-8"))
    base = json.loads((bridge / "config_used/hri_control.json").read_text(encoding="utf-8"))["dialog"]
    v4 = json.loads((bridge / "config_used" / Path(run["control_config"]).name).read_text(encoding="utf-8"))["dialog"]
    return {**base, **{k: v for k, v in v4.items() if k in base}}, run["git"]["commit"]   # hri_control_v4.load_control's merge


def replay(events, d: dict, t_ask: float, mode: str):
    """events: (frame_t, ctrl_t, kind, label) in frame order. (frame_t, ctrl_t, since) of the acceptance, or None."""
    g = hc.GestureDialog(d["gesture_hold_s"], d["gesture_window_s"], d["max_asks"], d.get("max_none_gap_s", 0.0))
    g.begin_ask(t_ask)
    for ft, ct, kind, label in events:
        if kind == "stop":
            if mode == "S":
                continue
            if mode == "R1":
                g.candidate, g.since = "NONE", ft
                continue
            label = "NONE"
        ev = g.update(label if label in hc.DIRECTIONS else "NONE", ft, ct)
        if ev == "accepted":
            return ft, ct, g.since
        if ev in ("ask_again", "abort"):
            return None
    return None


def git_head() -> str:
    try:
        return subprocess.run(["git", "rev-parse", "HEAD"], cwd=REPO, capture_output=True, text=True, check=True).stdout.strip()
    except (OSError, subprocess.CalledProcessError):
        return "unknown"


def main() -> int:
    sessions = json.loads((REPO / CONFIG["sessions"]).read_text(encoding="utf-8"))["sessions"]
    out = REPO / CONFIG["outputs"] / f"replay_dialog_hold_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
    out.mkdir(parents=True, exist_ok=False)
    rows, examples, used = [], [], {}
    for s in sessions:
        bridge = REPO / "robot_vision" / s["bridge"]
        d, commit = dialog_cfg(bridge)
        used[s["setting"]] = {"bridge": s["bridge"], "commit": commit, "dialog": {k: d[k] for k in ("gesture_hold_s", "gesture_window_s", "max_asks", "max_none_gap_s")}}
        frames: dict[int, list] = {}
        for line in (bridge / "v4_log.jsonl").read_text(encoding="utf-8").splitlines():
            o = json.loads(line)
            frames.setdefault(o["trial"], []).append(o)
        stops: dict[int, dict] = {}
        with open(bridge / "decisions.csv", encoding="utf-8", newline="") as f:
            for r in csv.DictReader(f):
                if r["safety"] == "STOP gesture" and r["state"].startswith("read") and r["gesture_time_s"]:
                    stops.setdefault(int(r["trial"]), {}).setdefault(round(float(r["gesture_time_s"]), 4), float(r["time_s"]))
        for pt in sorted(bridge.glob("python_trial_*.json")):
            tr = json.loads(pt.read_text(encoding="utf-8"))
            asks = sorted(((a["t"], rec) for rec in tr["junctions"] for a in rec.get("asks_log", [])), key=lambda x: x[0])
            for i, (t_ask, rec) in enumerate(asks):
                t_next = asks[i + 1][0] if i + 1 < len(asks) else float("inf")
                fr = [o for o in frames.get(tr["trial"], []) if t_ask <= o["ctrl_t"] < t_next and o["t"] >= t_ask - 1e-6]
                st = sorted((ft, ct) for ft, ct in stops.get(tr["trial"], {}).items() if t_ask <= ct < t_next and ft >= t_ask - 1e-6)
                ev = sorted([(o["t"], o["ctrl_t"], "frame", o["label"]) for o in fr] + [(ft, ct, "stop", "STOP") for ft, ct in st],
                            key=lambda e: (e[0], 0 if e[2] == "stop" else 1))
                t_acc = rec.get("t_accept")
                logged = t_acc if rec.get("result") == "accepted" and t_acc is not None and t_ask <= t_acc < t_next else None
                res = {m: replay(ev, d, t_ask, m) for m in MODELS}
                row = {"setting": s["setting"], "trial": tr["trial"], "junction": rec["junction"], "t_ask": t_ask, "dialog_frames": len(fr),
                       "stop_frames": len(st), "logged_accept": logged}
                for m in MODELS:
                    r = res[m]
                    row[f"{m}_accept"] = round(r[1], 4) if r else ""
                    row[f"{m}_matches_log"] = (r is None and logged is None) or (r is not None and logged is not None and abs(r[1] - logged) < 0.002)
                inside = [x for x in st if res["S"] and logged is not None and res["S"][2] < x[0] < res["S"][0]]
                row["stop_frames_inside_accepted_hold"] = len(inside)
                rows.append(row)
                if inside:
                    since, acc_ft = res["S"][2], res["S"][0]
                    examples.append({"setting": s["setting"], "trial": tr["trial"], "junction": rec["junction"], "t_ask": t_ask,
                                     "hold_since_frame_t": since, "accepted_frame_t": acc_ft, "logged_accept_ctrl_t": logged,
                                     "stop_frames_inside": [x[0] for x in inside], "R1_accept": row["R1_accept"], "R2_accept": row["R2_accept"],
                                     "timeline": [{"frame_t": round(a, 4), "ctrl_t": round(b, 4), "seen_by_dialog": k == "frame",
                                                   "label": l} for a, b, k, l in ev if since - 0.5 <= a <= acc_ft + 1e-6]})
    with open(out / "asks.csv", "w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        w.writeheader()
        w.writerows(rows)
    (out / "examples.json").write_text(json.dumps(examples, indent=1), encoding="utf-8")
    acc = [r for r in rows if r["logged_accept"] is not None]
    lines = [f"# Replay of the dialog hold on the step-5 logs ({out.name})", "",
             "experiments_ab.md section 15 addendum 3, item 4. Development data; report only.", "",
             f"Asks {len(rows)} (accepted in the log {len(acc)}; asks with a STOP frame {sum(1 for r in rows if r['stop_frames'])}).", "",
             "| model | asks matching the logged outcome | accepted asks matching the logged time |", "|---|---|---|"]
    for m, name in zip(MODELS, ("S: the code as written (STOP frames never reach the dialog)", "R1: the claim (a STOP frame restarts the hold)",
                                "R2: STOP frames given to the dialog as no-direction readings")):
        lines.append(f"| {name} | {sum(1 for r in rows if r[m + '_matches_log'])}/{len(rows)} | {sum(1 for r in acc if r[m + '_matches_log'])}/{len(acc)} |")
    lines += ["", f"Accepted asks with a STOP frame inside the accepted hold (model S: hold start < STOP frame < accepting frame): {len(examples)}", ""]
    for e in examples:
        lines.append(f"- {e['setting']} trial {e['trial']} {e['junction']} (ask {e['t_ask']} s): hold since frame {e['hold_since_frame_t']:.3f} s, STOP "
                     f"frame(s) {', '.join(f'{x:.3f}' for x in e['stop_frames_inside'])}, accepted at frame {e['accepted_frame_t']:.3f} s = controller "
                     f"{e['logged_accept_ctrl_t']} s as logged; R1 would accept: {e['R1_accept'] or 'never in this ask'}")
    if examples:
        e = examples[0]
        lines += ["", f"Timeline of the first example ({e['setting']} trial {e['trial']}, {e['junction']}):", "",
                  "| frame t (s) | controller t (s) | reaches the dialog | label |", "|---|---|---|---|"]
        lines += [f"| {x['frame_t']:.3f} | {x['ctrl_t']:.3f} | {'yes' if x['seen_by_dialog'] else 'no (safety stop: STOP gesture)'} | {x['label']} |"
                  for x in e["timeline"]]
    (out / "report.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    (out / "run_info.json").write_text(json.dumps({"git_commit": git_head(), "python": sys.version.split()[0], "config": CONFIG,
                                                   "sessions": used, "tool": "finals_v4/replay_dialog_hold.py"}, indent=1), encoding="utf-8")
    print("\n".join(lines))
    print(f"\nwritten: {out.relative_to(REPO).as_posix()}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
