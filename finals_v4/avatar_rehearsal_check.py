"""Avatar-experiment rehearsal (step 5, 2026-11-16): a BLIND format check of the rehearsal recordings.

It checks only that the pipeline works, never what a model sees: NO YOLO, NO MediaPipe, NO reader runs here, and no detection
or accuracy number is computed. From look_check_v4.py (Anisha's, unchanged) it uses only the input-side functions that the
tool itself applies before any model (discover: names; read_header: the frame_pan_tilt header schema and intrinsics through
bridge.protocol, version 3; read_image: the PNG decodes). Truth files go through gesture_data.py's loader (format only).

Per recording folder (an Edit-mode looks_check/ or a Play-mode looks_check_<time>/ with its run folder):
  - every name parses, every header passes, every PNG decodes at the header's size;
  - coverage: every look of the list x command x distance (x arm for POINT / WAIT / STOP / PROCEED) is present, and the
    takes per group (sequences, singles) are reported and compared with the plan (Play: 2 sequences + 16 singles);
  - sequence frame counts: 11 frames, PROCEED 21 (look_check_play_ab.json proceed.sequence_frames), equal to recordings.jsonl n_frames;
  - timing (headers with time_s; experiments_ab.md section 15 addendum 10): strictly increasing, steps at most 0.2 s, and every frame
    within 0.100 s (exclusive) of its 0.1 s mark m_i = t_0 + 0.1 i (+ 0.001 s for PROCEED frames 1..), frame 0 the anchor: Unity takes
    frame i at the first rendered frame at or after its mark (LookCheckPlayDriver), so a late frame followed by a short step is on the grid
    (the earlier lower bound of 0.09 s per step failed every Play run); the largest offset per part goes into the report;
  - error shader: pixels of exactly magenta (255, 0, 255) or cyan (0, 255, 255) per PNG (the Editor's missing-shader and
    still-compiling colours); recordings.jsonl magenta_pixels and inventory.json material_problems / renders_in_urp;
  - truth (Play run folder truth/*.jsonl): gesture_data.load_truth accepts each file (labels, phases, clips).
Writes robot_vision/outputs/avatar_rehearsal_check_<time>/report.json and report.md (never overwritten).
With --delete-frames, AFTER the report is written, deletes the PNG frames (and their header JSONs) of the checked recording
folders only (the rehearsal recordings; nothing else), and records the deletion in the report folder.
Without --edit (addendum 10) only the Play part is checked (a repeat of the rehearsal's Play part); a part whose recording folder is missing
fails the check.
Usage (repository root): robot_vision\\.venv\\Scripts\\python.exe finals_v4\\avatar_rehearsal_check.py
        [--edit <look_check_ab_<time>>] --play <look_check_play_ab_<time>> [--geometry <gesture_geometry_<time>>] [--delete-frames]
Its tests: robot_vision\\.venv\\Scripts\\python.exe -m unittest discover -s finals_v4 -p "test_*.py" (repository root).
"""
from __future__ import annotations

import argparse
import json
import sys
from collections import Counter, defaultdict
from datetime import datetime
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
RV = REPO / "robot_vision"
UNITY_CFG = REPO / "unity/Robotics-Warehouse/WarehouseProjectURP/Assets/WarehouseRobot/Avatar/Config"
sys.path.insert(0, str(RV))

import numpy as np  # noqa: E402

import look_check_v4 as lc  # noqa: E402  (input-side functions only; no detector is ever built)

ARMED = ("POINT", "WAIT", "STOP", "PROCEED")
MARK_STEP_S = 0.1          # the capture grid, 10 Hz
MARK_TOL_S = 0.1           # |offset from the mark| < one sampling interval (exclusive)
STEP_MAX_S = 0.2           # unchanged: no step longer than two intervals
PROCEED_DELAY_S = 0.001    # PROCEED frames 1.. are timed from frame 0's real time + 1 ms (LookCheckPlayDriver.Perform)


def jl(path: Path) -> list[dict]:
    return [json.loads(l) for l in path.read_text(encoding="utf-8-sig").splitlines() if l.strip()] if path.exists() else []


def bad_pixels(img) -> tuple[int, int]:
    b, g, r = img[:, :, 0].astype(np.int16), img[:, :, 1].astype(np.int16), img[:, :, 2].astype(np.int16)
    magenta = int(np.count_nonzero((r == 255) & (g == 0) & (b == 255)))
    cyan = int(np.count_nonzero((r == 0) & (g == 255) & (b == 255)))
    return magenta, cyan


def timing_offsets(times, command: str) -> np.ndarray:
    """Each frame's offset from its 0.1 s mark, frame 0 the anchor: m_i = t_0 + 0.1 i, + 0.001 s for PROCEED frames i >= 1."""
    t = np.asarray(times, dtype=float)
    i = np.arange(len(t))
    marks = t[0] + MARK_STEP_S * i + np.where((i > 0) & (command == "PROCEED"), PROCEED_DELAY_S, 0.0)
    return t - marks


def timing_problem(times, command: str) -> str | None:
    """None when a sequence's frame times follow Unity's capture rule (strictly increasing, steps at most 0.2 s, every frame
    within 0.100 s of its mark), else the reason."""
    if len(times) < 2:
        return None
    steps = np.diff(np.asarray(times, dtype=float))
    off = timing_offsets(times, command)
    why = []
    if not np.all(steps > 0):
        why.append("times not strictly increasing")
    if not np.all(steps <= STEP_MAX_S):
        why.append(f"a step over {STEP_MAX_S:g} s")
    if not np.all(np.abs(off) < MARK_TOL_S):
        why.append(f"a frame {float(np.max(np.abs(off))):.3f} s from its mark (limit < {MARK_TOL_S:.3f} s)")
    if not why:
        return None
    return f"{'; '.join(why)}: steps {np.round(steps, 3).tolist()}, offsets {np.round(off, 3).tolist()}"


def check_folder(part: str, run_dir: Path, looks: list[str], cfg: dict, play_cfg: dict) -> dict:
    rec_dirs = [d for d in run_dir.iterdir() if d.is_dir() and d.name.startswith("looks_check")] if run_dir.is_dir() else []
    if len(rec_dirs) != 1:
        problems = [f"expected one looks_check* folder, found {len(rec_dirs)}"]
        rel = str(run_dir.relative_to(RV)) if run_dir.is_relative_to(RV) else run_dir.name      # no absolute path under outputs/
        return {"part": part, "run_dir": rel, "problems": problems, "problem_count": len(problems)}
    rec = rec_dirs[0]
    items, problems = lc.discover(rec, cfg)
    meta = {r["name"]: r for r in jl(run_dir / "recordings.jsonl")}
    seq_frames = {"PROCEED": int(play_cfg["proceed"]["sequence_frames"])}
    groups: dict[tuple, Counter] = defaultdict(Counter)
    frames = magenta = cyan = timed = 0
    off_max = 0.0
    bad_px_items, timing_bad, count_bad = [], [], []
    for it in items:
        arm = None
        times = []
        for png, js in it.files:
            try:
                img = lc.read_image(png)
            except (OSError, ValueError) as e:
                problems.append(str(e))
                continue
            hdr, err = lc.read_header(js, img.shape[1], img.shape[0], cfg, 1e-3)
            if err:
                problems.append(f"{it.name}: {err}")
                continue
            frames += 1
            arm = arm or hdr.arm
            if hdr.time_s is not None:
                times.append(hdr.time_s)
            m, c = bad_pixels(img)
            magenta += m
            cyan += c
            if m or c:
                bad_px_items.append(f"{it.name}/{png.name}: magenta {m}, cyan {c}")
        groups[(it.look, it.command, it.distance_m, arm or "-")][it.kind] += 1
        if it.kind == "sequence":
            want = seq_frames.get(it.command, 11)
            have = len(it.files)
            n_meta = meta.get(it.name, {}).get("n_frames")
            if have != want or (n_meta is not None and n_meta != have):
                count_bad.append(f"{it.name}: {have} frames on disk, recordings.jsonl {n_meta}, expected {want}")
            if len(times) == have and have > 1:
                timed += 1
                off_max = max(off_max, float(np.max(np.abs(timing_offsets(times, it.command)))))
                why = timing_problem(times, it.command)
                if why:
                    timing_bad.append(f"{it.name}: {why}")
        if it.name not in meta and meta:
            problems.append(f"{it.name}: not in recordings.jsonl")
    missing = []
    commands = cfg["input"]["commands"]
    for look in looks:
        for cmd in commands:
            for d in (2.0, 4.0):
                arms = ("left", "right") if cmd in ARMED else ("-",)
                for a in arms:
                    g = groups.get((look, cmd, d, a))
                    if not g:
                        missing.append(f"{look} {cmd} {d} {a}")
    takes = Counter((g["sequence"], g["frame"]) for g in groups.values())
    extra_looks = sorted({k[0] for k in groups} - set(looks))
    return {"part": part, "run_dir": str(run_dir.relative_to(RV)), "recordings": str(rec.relative_to(RV)), "items": len(items),
            "frames_ok": frames, "groups": len(groups), "takes_per_group (sequences, singles): groups": {str(k): v for k, v in takes.items()},
            "missing_groups": missing, "extra_looks": extra_looks, "sequence_count_problems": count_bad,
            "sequences_timed": timed, "timing_offset_max_s": round(off_max, 4), "timing_problems": timing_bad, "magenta_pixels": magenta, "cyan_pixels": cyan, "error_shader_frames": bad_px_items[:50],
            "error_shader_frame_count": len(bad_px_items), "recordings_jsonl_magenta": sum(int(r.get("magenta_pixels", 0) or 0) for r in meta.values()),
            "problems": problems[:100], "problem_count": len(problems)}


def truth_check(play_dir: Path) -> dict:
    import gesture_data as gd
    files = sorted((play_dir / "truth").glob("*.jsonl"))
    bad, rows, labels = [], 0, Counter()
    for f in files:
        try:
            t = gd.load_truth(f)
            rows += len(t)
            labels.update((r.true_command, r.phase) for r in t)
        except (SystemExit, ValueError, OSError) as e:
            bad.append(f"{f.name}: {e}")
    return {"files": len(files), "accepted": len(files) - len(bad), "rows": rows, "refused": bad,
            "labels (command, phase)": {f"{c}/{p}": n for (c, p), n in sorted(labels.items())}}


def delete_frames(rec: Path) -> dict:
    n = 0
    size = 0
    for f in list(rec.rglob("*")):
        if f.is_file() and f.suffix.lower() in (".png", ".json"):
            size += f.stat().st_size
            f.unlink()
            n += 1
    for d in sorted((d for d in rec.rglob("*") if d.is_dir()), key=lambda p: len(p.parts), reverse=True):
        if not any(d.iterdir()):
            d.rmdir()
    if not any(rec.iterdir()):
        rec.rmdir()
    return {"folder": str(rec.relative_to(RV)), "files_deleted": n, "bytes": size}


def parser() -> argparse.ArgumentParser:
    ap = argparse.ArgumentParser()
    ap.add_argument("--edit", default="", help="the Edit-mode run folder; omitted = a play-only check (addendum 10)")
    ap.add_argument("--play", required=True)
    ap.add_argument("--geometry", default="")
    ap.add_argument("--delete-frames", action="store_true")
    return ap


def verdict(report: dict) -> bool:
    """True when every checked part (a part with not_checked is left out) has no problem of any kind and the truth files are accepted.
    A part whose recording folder is missing has a problem, so it fails (addendum 10; it used to be left out of the verdict)."""
    parts = [p for p in ("edit", "play") if not report[p].get("not_checked")]
    return all(not report[p].get("missing_groups") and not report[p].get("problem_count") and not report[p].get("sequence_count_problems")
               and not report[p].get("timing_problems") and not report[p].get("error_shader_frame_count") for p in parts) \
        and not report["truth_play"]["refused"]


def main(argv=None) -> int:
    a = parser().parse_args(argv)
    cfg = lc.load_config()
    looks = json.loads((UNITY_CFG / "looks_ab.json").read_text(encoding="utf-8"))["avatar_experiment"]
    play_cfg = json.loads((UNITY_CFG / "look_check_play_ab.json").read_text(encoding="utf-8"))
    edit_dir = (RV / "outputs" / a.edit).resolve() if a.edit else None
    play_dir = (RV / "outputs" / a.play).resolve()
    for d in (edit_dir, play_dir):
        if d is not None and (not d.name.startswith(("look_check_ab_", "look_check_play_ab_")) or d.parent != (RV / "outputs").resolve()):
            raise SystemExit(f"refused: {d} is not a look-check run folder directly under robot_vision/outputs")
    report = {"what": "avatar-experiment rehearsal, blind format check (no model, no detection or accuracy number)",
              "created": datetime.now().isoformat(timespec="seconds"), "looks": looks,
              "edit": check_folder("edit", edit_dir, looks, cfg, play_cfg) if edit_dir else
                      {"part": "edit", "not_checked": "no --edit given: a play-only check (experiments_ab.md section 15 addendum 10)"},
              "play": check_folder("play", play_dir, looks, cfg, play_cfg),
              "truth_play": truth_check(play_dir)}
    inv = json.loads((edit_dir / "inventory.json").read_text(encoding="utf-8")) if edit_dir and (edit_dir / "inventory.json").exists() else {"looks": []}
    report["inventory_edit"] = [{k: l.get(k) for k in ("id", "status", "installed", "humanoid", "renders_in_urp", "material_problems",
                                                       "magenta_pixels", "hand_shapes_possible", "shaders")} for l in inv["looks"]]
    for name, d in (("edit", edit_dir), ("play", play_dir)):
        if d is None:
            report[f"run_info_{name}"], report[f"guard_markers_{name}"] = None, []
            continue
        report[f"run_info_{name}"] = {k: v for k, v in json.loads((d / "run_info.json").read_text(encoding="utf-8")).items()
                                      if k in ("git_commit", "git_branch", "git_dirty", "avatar_experiment_part", "looks_subset", "created_local")} \
            if (d / "run_info.json").exists() else None
        report[f"guard_markers_{name}"] = sorted(p.name for p in d.rglob("AVATAR_EXPERIMENT_*.json"))
    if a.geometry:
        g = (RV / "outputs" / a.geometry).resolve()
        report["geometry"] = {"folder": str(g.relative_to(RV)), "files": sorted(p.name for p in g.iterdir())}
    out = RV / "outputs" / f"avatar_rehearsal_check_{datetime.now():%Y%m%d_%H%M%S}"
    out.mkdir(exist_ok=False)
    (out / "report.json").write_text(json.dumps(report, indent=1), encoding="utf-8")
    if a.delete_frames:
        dels = [delete_frames(RV / report[p]["recordings"]) for p in ("edit", "play") if "recordings" in report[p]]
        (out / "frames_deleted.json").write_text(json.dumps(dels, indent=1), encoding="utf-8")
    print(out)
    ok = verdict(report)
    print(("FORMAT CHECK PASSED" if ok else "FORMAT CHECK: problems found (report.json)") + ("" if edit_dir else " (play part only)"))
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
