"""Demo video of a finished Step 9 replay run (for presentations). No inference is rerun and no reference data is
read: the script draws what earlier runs already wrote.

Inputs follow the lineage recorded in the run folders:
    replay run (decision_log.json) -> motion run -> fusion run (frames, timestamps) -> tracking run (boxes, RGB paths)
Each frame shows the RGB image, every person observed in the decision snapshot (tracker box, track ID, distance,
motion label), the decision (MOVE / STOP / WAIT) with its reason, and a corner label. Box colour: red = in the
stop zone, amber = in the caution zone or predicted to enter the stop zone, white = elsewhere. The strip under
the frame is the decision timeline with a cursor at the current frame.

Output: a new folder outputs/demo_video_<N>f_<timestamp>/ with demo.mp4, three stills (STOP, MOVE, WAIT),
run_info.json and config_used/. Settings: configs/demo_video.json.

Usage (from robot_vision/):
    python make_demo_video.py --replay-run outputs/decisions_replay_1388f_20261015_220231
"""

from __future__ import annotations

import argparse
import csv
import json
import subprocess
from pathlib import Path

import cv2
import numpy as np

import decision_io as dio
import run_paths as rp
import thud_data as td

DEFAULT_CONFIG = "configs/demo_video.json"
DECISIONS = ("STOP", "MOVE", "WAIT")
FONT = cv2.FONT_HERSHEY_SIMPLEX


# ---------------------------------------------------------------- inputs

def read_jsonl(path: Path) -> list[dict]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def require_complete(run: Path, what: str) -> None:
    if not (run / "COMPLETE").exists():
        raise SystemExit(f"{what} run is not complete: {run}")


def load_inputs(replay: Path, rts: dict) -> dict:
    """Decisions, frames and boxes of one replay run, checked to line up frame by frame."""
    require_complete(replay, "Replay")
    rinfo = dio.read_json(replay / "run_info.json")
    log = dio.read_json(replay / "decision_log.json")
    motion = rp.resolve(rinfo["motion_run"], rts)
    require_complete(motion, "Motion")
    minfo = dio.read_json(motion / "run_info.json")
    fusion = rp.resolve(minfo["fusion_run"], rts)
    require_complete(fusion, "Fusion")
    tracking = rp.resolve(dio.read_json(fusion / "run_info.json")["tracking_run"], rts)
    require_complete(tracking, "Tracking")

    frames = read_jsonl(fusion / "frames.jsonl")
    decisions = log["decisions"]
    if len(frames) != len(decisions):
        raise SystemExit(f"{len(decisions)} decisions but {len(frames)} fusion frames")
    for i, (f, d) in enumerate(zip(frames, decisions)):
        if abs(f["timestamp"] - d["timestamp"]) > 1e-6:
            raise SystemExit(f"Frame {i}: decision at {d['timestamp']} s, fusion frame at {f['timestamp']} s")
    track_frames = {f["step"]: f for f in read_jsonl(tracking / "frames.jsonl")}
    boxes: dict[int, dict[int, tuple[float, float, float, float]]] = {}
    with (tracking / "tracks.csv").open(newline="", encoding="utf-8") as fh:
        for r in csv.DictReader(fh):
            boxes.setdefault(int(r["step"]), {})[int(r["track_id"])] = (
                float(r["x1"]), float(r["y1"]), float(r["x2"]), float(r["y2"]))
    for f in frames:
        if f["step"] not in track_frames:
            raise SystemExit(f"Step {f['step']} is missing from the tracking run")
    return {"replay": replay, "motion": motion, "fusion": fusion, "tracking": tracking, "replay_info": rinfo,
            "labels": log.get("labels", {}), "frames": frames, "decisions": decisions,
            "track_frames": track_frames, "boxes": boxes}


def read_rgb(path: Path) -> np.ndarray:
    img = cv2.imdecode(np.fromfile(str(path), dtype=np.uint8), cv2.IMREAD_COLOR)  # non-ASCII-safe on Windows
    if img is None:
        raise SystemExit(f"Could not read {path}")
    return img


# ---------------------------------------------------------------- drawing

def wrap(text: str, max_w: int, scale: float, thick: int) -> list[str]:
    lines, cur = [], ""
    for word in text.split():
        trial = f"{cur} {word}".strip()
        if cur and cv2.getTextSize(trial, FONT, scale, thick)[0][0] > max_w:
            lines.append(cur)
            cur = word
        else:
            cur = trial
    return lines + [cur] if cur else lines


def label_box(img: np.ndarray, text: str, org: tuple[int, int], scale: float, thick: int, fg, bg) -> None:
    """Text on a filled box; org is the bottom-left of the text."""
    (w, h), base = cv2.getTextSize(text, FONT, scale, thick)
    x, y = org
    pad = max(2, thick * 2)
    cv2.rectangle(img, (x - pad, y - h - pad), (x + w + pad, y + base + pad // 2), bg, -1)
    cv2.putText(img, text, (x, y), FONT, scale, fg, thick, cv2.LINE_AA)


def person_text(p: dict) -> str:
    if p.get("distance_m") is not None:
        dist = f"{p['distance_m']:.2f} m"
    elif p.get("distance_lower_bound_m") is not None:
        dist = f">= {p['distance_lower_bound_m']:.2f} m"
    else:
        dist = "distance unknown"
    motion = (p.get("motion_label") or "unknown").replace("_", " ")
    return f"ID {p['track_id']} | {dist} | {motion}"


def box_colour(p: dict, colors: dict):
    if p.get("in_stop_zone"):
        return tuple(colors["box_stop_zone"])
    if p.get("in_caution_zone") or p.get("entry_in_s") is not None:
        return tuple(colors["box_caution"])
    return tuple(colors["box_other"])


def timeline_strip(decisions: list[dict], width: int, height: int, colors: dict) -> np.ndarray:
    strip = np.zeros((height, width, 3), np.uint8)
    n = len(decisions)
    for x in range(width):
        strip[:, x] = colors[decisions[min(n - 1, x * n // width)]["decision"]]
    return strip


def banner_lines(d: dict, width: int, s: float) -> list[str]:
    """Wrapped reason and the active scripted gestures, as drawn under the decision word."""
    margin, small, t1 = round(10 * s), 0.38 * s, max(1, round(s))
    gest = [f"{g['track_id']}: {g['gesture']}" for g in d["snapshot"].get("gestures", []) if g["gesture"] != "NONE"]
    return (wrap(f"Reason: {d['reason']}", width - 2 * margin - round(18 * s), small, t1)
            + ([f"Gestures (scripted): {', '.join(gest)}"] if gest else []))


def render(rgb: np.ndarray, d: dict, boxes: dict, index: int, n_frames: int, strip: np.ndarray, cfg: dict,
           rows: int) -> np.ndarray:
    """One output frame: decision banner (rows text lines, fixed for the whole video), the scaled RGB frame with
    person boxes, the timeline strip."""
    s = float(cfg["scale"])
    colors = cfg["colors_bgr"]
    colour = tuple(colors[d["decision"]])
    frame = cv2.resize(rgb, (round(rgb.shape[1] * s), round(rgb.shape[0] * s)), interpolation=cv2.INTER_LINEAR)
    W = frame.shape[1]
    t1, t2 = max(1, round(s)), max(2, round(1.5 * s))

    # people observed in this frame: tracker box + decision snapshot values
    for p in d["snapshot"]["persons"]:
        if not p["observed"] or p["track_id"] not in boxes:
            continue
        x1, y1, x2, y2 = (round(v * s) for v in boxes[p["track_id"]])
        c = box_colour(p, colors)
        cv2.rectangle(frame, (x1, y1), (x2, y2), c, t2 + (t1 if p["track_id"] in d["track_ids"] else 0))
        scale = 0.42 * s
        (_, th), _ = cv2.getTextSize("ID", FONT, scale, t1)
        y = y1 - 3 * t1 if y1 - th - 4 * t1 > 0 else y1 + th + 3 * t1
        label_box(frame, person_text(p), (max(2 * t1, x1), y), scale, t1, (0, 0, 0), c)

    label_box(frame, cfg["corner_label"], (round(6 * s), frame.shape[0] - round(6 * s)), 0.36 * s, t1,
              (255, 255, 255), (40, 40, 40))

    # banner: decision word, rule and time, wrapped reason, active scripted gestures
    big, small = 1.25 * s, 0.38 * s
    (bw, bh), _ = cv2.getTextSize(d["decision"], FONT, big, 3 * t1)
    margin = round(10 * s)
    info_lines = banner_lines(d, W, s)
    (_, lh), _ = cv2.getTextSize("Ag", FONT, small, t1)
    line_h = round(lh * 1.7)
    banner_h = margin + bh + margin + rows * line_h + margin // 2
    banner = np.full((banner_h, W, 3), 25, np.uint8)
    cv2.rectangle(banner, (0, 0), (round(8 * s), banner_h), colour, -1)
    x0 = round(18 * s)
    cv2.putText(banner, d["decision"], (x0, margin + bh), FONT, big, colour, 3 * t1, cv2.LINE_AA)
    meta = f"rule {d['rule']}   t = {d['timestamp']:.2f} s   frame {index + 1}/{n_frames}"
    cv2.putText(banner, meta, (x0 + bw + round(14 * s), margin + bh), FONT, small, (200, 200, 200), t1, cv2.LINE_AA)
    y = margin + bh + margin + lh
    for line in info_lines[:rows]:
        cv2.putText(banner, line, (x0, y), FONT, small, (255, 255, 255), t1, cv2.LINE_AA)
        y += line_h

    bar = strip.copy()
    cx = min(W - 1, index * W // n_frames)
    cv2.rectangle(bar, (cx - t1, 0), (cx + t1, bar.shape[0] - 1), (255, 255, 255), -1)
    out = np.vstack([banner, frame, bar])
    return out[: out.shape[0] // 2 * 2, : out.shape[1] // 2 * 2]  # H.264 needs even sizes


# ---------------------------------------------------------------- stills and video

def longest_runs(decisions: list[dict], keep=lambda d: True) -> dict[str, tuple[int, int]]:
    """Per decision, the (start, end) indices (end exclusive) of its longest contiguous run of frames for which
    keep(frame) holds; first one on ties."""
    best: dict[str, tuple[int, int]] = {}
    start = None
    for i in range(len(decisions) + 1):
        if start is not None and (i == len(decisions) or not keep(decisions[i])
                                  or decisions[i]["decision"] != decisions[start]["decision"]):
            name = decisions[start]["decision"]
            if name not in best or i - start > best[name][1] - best[name][0]:
                best[name] = (start, i)
            start = None
        if start is None and i < len(decisions) and keep(decisions[i]):
            start = i
    return best


def person_visible(d: dict) -> bool:
    return any(p["observed"] for p in d["snapshot"]["persons"])


def pick_stills(decisions: list[dict], overrides: dict[str, int]) -> dict[str, dict]:
    """One still per decision: the middle frame of its longest run with a person visible, else of its longest run."""
    with_person, any_frame = longest_runs(decisions, person_visible), longest_runs(decisions)
    out = {}
    for name in DECISIONS:
        if name in overrides:
            i = overrides[name]
            if decisions[i]["decision"] != name:
                raise SystemExit(f"--still {name}={i}: that frame's decision is {decisions[i]['decision']}")
            out[name] = {"index": i, "chosen_by": "--still"}
        elif name in with_person or name in any_frame:
            a, b = with_person.get(name) or any_frame[name]
            what = "with a person visible" if name in with_person else "(no frame of it shows a person)"
            out[name] = {"index": (a + b - 1) // 2, "chosen_by": f"middle of longest run {what}, frames {a}-{b - 1}"}
    return out


def open_writer(path: Path, fps: float, size_wh: tuple[int, int], codecs: list[str]):
    for codec in codecs:
        w = cv2.VideoWriter(str(path), cv2.VideoWriter_fourcc(*codec), fps, size_wh)
        if w.isOpened():
            return w, codec
        w.release()
    raise RuntimeError(f"No MP4 writer could be opened with codecs {codecs}")


def probe_video(path: Path) -> dict:
    cap = cv2.VideoCapture(str(path))
    try:
        fourcc = int(cap.get(cv2.CAP_PROP_FOURCC))
        return {"readable": cap.isOpened(), "frames": int(cap.get(cv2.CAP_PROP_FRAME_COUNT)),
                "fps": round(cap.get(cv2.CAP_PROP_FPS), 3),
                "width": int(cap.get(cv2.CAP_PROP_FRAME_WIDTH)), "height": int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT)),
                "codec": fourcc.to_bytes(4, "little").decode("ascii", "replace").strip("\x00")}
    finally:
        cap.release()


def write_png(path: Path, img: np.ndarray) -> None:
    ok, buf = cv2.imencode(".png", img)
    if not ok:
        raise RuntimeError(f"Could not encode {path.name}")
    path.write_bytes(buf.tobytes())


def code_changes_here() -> bool | None:
    """Uncommitted changes to tracked files under robot_vision/ (the repo-wide flag also counts the Unity project)."""
    try:
        r = subprocess.run(["git", "status", "--porcelain", "--untracked-files=no", "--", "."], cwd=dio.HERE,
                           capture_output=True, text=True, timeout=20)
        return bool(r.stdout.strip())
    except (OSError, subprocess.SubprocessError):
        return None


def parse_stills(items: list[str]) -> dict[str, int]:
    out = {}
    for it in items:
        name, _, idx = it.partition("=")
        if name not in DECISIONS or not idx.isdigit():
            raise SystemExit(f"--still expects DECISION=FRAME_INDEX with DECISION in {DECISIONS}, got {it!r}")
        out[name] = int(idx)
    return out


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--replay-run", required=True, help="finished replay_decisions.py run folder")
    p.add_argument("--config", default=DEFAULT_CONFIG)
    p.add_argument("--dataset-root", help="THUD root (default: THUD_DATASET_ROOT, then the dataset config)")
    p.add_argument("--still", action="append", default=[], metavar="DECISION=FRAME_INDEX",
                   help="choose a still frame (0-based index) instead of the default")
    a = p.parse_args()

    cfg_path = dio.resolve(a.config)
    cfg = dio.read_json(cfg_path)
    data_cfg_path = dio.resolve(cfg["paths"]["dataset_config"])
    data_cfg = td.load_config(data_cfg_path, a.dataset_root)
    rts = rp.make_roots(dataset_root=data_cfg["dataset_root"], output_root=dio.resolve(cfg["paths"]["output_root"]))
    inp = load_inputs(dio.resolve(a.replay_run), rts)
    decisions, frames = inp["decisions"], inp["frames"]
    n = len(frames)
    stills = pick_stills(decisions, parse_stills(a.still))
    fps = (n - 1) / (frames[-1]["timestamp"] - frames[0]["timestamp"])

    out = dio.new_run_dir(cfg, f"demo_video_{n}f")
    rp.set_active_roots(rts)
    hashes = dio.copy_configs(out, [cfg_path])
    # the dataset config holds this machine's dataset root: stored with paths as root tokens (hash of the original)
    dio.write_json(out / "config_used" / data_cfg_path.name, dio.read_json(data_cfg_path))
    hashes[data_cfg_path.name] = dio.sha256(data_cfg_path)
    by_index = {v["index"]: k for k, v in stills.items()}
    width = round(read_rgb(rp.resolve(inp["track_frames"][frames[0]["step"]]["rgb_path"], rts)).shape[1]
                  * float(cfg["scale"]))
    rows = max(len(banner_lines(d, width, float(cfg["scale"]))) for d in decisions)
    strip = timeline_strip(decisions, width, round(9 * float(cfg["scale"])), cfg["colors_bgr"])
    writer = codec = None
    for i, (f, d) in enumerate(zip(frames, decisions)):
        rgb = read_rgb(rp.resolve(inp["track_frames"][f["step"]]["rgb_path"], rts))
        img = render(rgb, d, inp["boxes"].get(f["step"], {}), i, n, strip, cfg, rows)
        if writer is None:
            writer, codec = open_writer(out / "demo.mp4", fps, (img.shape[1], img.shape[0]), cfg["codec_preference"])
        writer.write(img)
        if i in by_index:
            name = by_index[i]
            stills[name]["file"] = f"still_{name}_frame{i:04d}.png"
            stills[name].update(timestamp=d["timestamp"], rule=d["rule"], reason=d["reason"])
            write_png(out / stills[name]["file"], img)
        if (i + 1) % 200 == 0:
            print(f"  {i + 1}/{n} frames")
    writer.release()
    probe = probe_video(out / "demo.mp4")
    if probe["frames"] != n:
        raise SystemExit(f"Video check failed: {probe['frames']} frames read back, {n} written")

    info = dio.run_info(cfg_path, {
        "purpose": "presentation video of an existing replay run; no inference rerun, no reference data read",
        "labels": {**inp["labels"], "video": cfg["corner_label"]},
        "replay_run": str(inp["replay"]), "motion_run": str(inp["motion"]), "fusion_run": str(inp["fusion"]),
        "tracking_run": str(inp["tracking"]), "replay_git": inp["replay_info"].get("git"),
        "robot_vision_uncommitted_changes": code_changes_here(),
        "dataset_config": str(data_cfg_path), "config_sha256": hashes,
        "frames": n, "video": {"file": "demo.mp4", "codec_requested": codec, "fps_written": round(fps, 4),
                               "read_back": probe,
                               "fallback_used": codec != cfg["codec_preference"][0]},
        "stills": stills, "decision_counts": {k: sum(x["decision"] == k for x in decisions) for k in DECISIONS},
        "render_config": cfg})
    info.pop("decision_config", None)  # run_info's generic field; the config here is the render config
    info.pop("decision_config_sha256", None)
    dio.write_json(out / "run_info.json", info)
    dio.mark_complete(out)
    print(f"Video: {probe['codec']} {probe['width']}x{probe['height']}, {probe['frames']} frames at {fps:.2f} fps"
          + (" (FALLBACK codec)" if codec != cfg["codec_preference"][0] else ""))
    for name, s in stills.items():
        print(f"  still {name}: frame {s['index']} ({s['chosen_by']})")
    print(f"Wrote {out}")


if __name__ == "__main__":
    main()
