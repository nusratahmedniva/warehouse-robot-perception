"""The avatar experiment, one command (AUDIT.md 16.33.1 B; the protocol is docs/avatar_experiment_protocol_v4.md = AUDIT.md 16.31.1, 16.31.5, 16.31.6).
REPORTING / EVALUATION CODE; inference code never imports it.

  python process_avatar_zip_v4.py <zip> --sha256 <hash>        the zip made by final_zip_v4.py avatar

Steps (it stops at the first failure with the reason; a part is reported once):
  1  verify    SHA-256, .sha256 file, testzip, every member against MANIFEST.json (read in place); the run folders are copied out (hash checked, no code)
  2  guard     per part (a folder with run_info.json): data_splits_v4.guard_avatar_experiment: avatar_experiment_part 'edit' / 'play', STARTED and DONE
               markers, one commit, frozen hashes, every look and clip name of recordings.jsonl listed (any role)
  3  look check  look_check_v4.py (unchanged, frozen look_check.json) on the part's recordings folder
  4  invalid   technical failures only: frames or headers missing / truncated / bad intrinsics, a frame time that breaks the timing rule of Unity's addendum 10,
               the wrong look / command / distance / arm recorded, a placeholder colour while shaders_compiling is true (recordings.jsonl, shader_warm_up.jsonl)
  5  tables    per-take shares, the mean over takes with a bootstrap over takes (2000 resamples, seed 1: configs/v4/analysis.json), Wilson only for take-level
               yes/no outcomes, per look, per kind group, per look role and clip role; Play is the headline, Edit the control, never pooled
Output: a NEW folder avatar_root/process_avatar_zip_v4_<time>/ with a folder per part (CSV and Markdown tables) and report.json / report.md.
"""

from __future__ import annotations

import argparse
import csv
import json
import shutil
import sys
import tempfile
from collections import defaultdict
from datetime import datetime
from pathlib import Path

import avatar_clip_roles_v4 as ac
import data_splits_v4 as ds
import export_csv_v4 as ex
import final_guard_v4 as fg
import freeze_v4 as fz
import look_check_v4 as lc
import process_final_zip_v4 as pf

HERE = Path(__file__).resolve().parent
PLAY, EDIT = "play", "edit"
GESTURES = ("POINT", "WAIT", "STOP", "PROCEED")
OWN_CUE = {"POINT": "point_ok", "WAIT": "wait_ok", "STOP": "stop_ok"}
# frame measures (per-take shares) and the outcomes of a take (yes/no)
MEASURES = ("person", "hand_linked", "hand_any", "arm_valid", "kp_shoulders", "kp_hips", "kp_elbow", "kp_wrist", "facing", "own_cue", "wrong_class")
OUTCOMES = ("read_as_recorded", "read_other_command", "not_read")
PRIMARY = ("person", "hand_linked")
EPS = 1e-9


class PartRefused(pf.StepFailed):
    """A part cannot be processed (the reason)."""


# ---------------------------------------------------------------- the part and its recordings

def find_parts(root: Path, folders: list[str]) -> list[dict]:
    """The run folders of the experiment: a folder with a run_info.json and one subfolder looks_check*/ (the recordings). Returns dicts with the paths."""
    parts = []
    for name in folders:
        d = root / name
        rec = sorted(p for p in d.iterdir() if p.is_dir() and p.name.startswith("looks_check")) if d.is_dir() else []
        if (d / "run_info.json").is_file():
            if len(rec) != 1:
                raise PartRefused(f"{name}: needs exactly one looks_check*/ recordings folder, found {len(rec)}")
            parts.append({"folder": d, "recordings": rec[0]})
    if not parts:
        raise PartRefused("no run folder with a run_info.json in the zip: not an avatar-experiment zip")
    return parts


def read_jsonl(path: Path) -> list[dict]:
    return ac.load_recordings(path)


def part_name(session: dict) -> str:
    return (session.get("run_info") or {}).get("avatar_experiment_part") or ""


# ---------------------------------------------------------------- per-take values

def frame_values(rec: dict, command: str) -> dict:
    """The frame measures of one look-check frame record (True / False / None = not applicable for this command)."""
    person = bool(rec.get("person"))
    gesture = command in GESTURES
    arm = rec.get("arm")
    kp = rec.get("kp_ok") or {}
    v = {"person": person,
         "hand_linked": (bool(rec.get("hand_linked")) if person else False) if gesture else None,
         "hand_any": (bool(rec.get("hand_any")) if person else False) if gesture else None,
         "arm_valid": (bool(rec.get("arm_valid")) if person else False) if gesture else None,
         "kp_shoulders": bool(kp.get("left_shoulder") and kp.get("right_shoulder")) if person else False,
         "kp_hips": bool(kp.get("left_hip") and kp.get("right_hip")) if person else False,
         "kp_elbow": (bool(kp.get(f"{arm}_elbow")) if person and arm else False) if gesture else None,
         "kp_wrist": (bool(kp.get(f"{arm}_wrist")) if person and arm else False) if gesture else None,
         "facing": bool(rec.get("facing")) if person else False}
    flags = rec.get("flags") or {}
    v["own_cue"] = (bool(flags.get(OWN_CUE[command])) if person else False) if command in OWN_CUE else None
    cls = rec.get("frame_class") if person else "NONE"
    v["wrong_class"] = (cls != "NONE") if command in ("NONE", "PROCEED") else (cls not in ("NONE", command))
    return v


def take_shares(result: dict) -> dict:
    """measure -> the share of this take's frames with the property (a single frame: 0 or 1); None when the measure does not apply."""
    cols: dict[str, list] = defaultdict(list)
    for rec in result["frames"]:
        for m, val in frame_values(rec, result["command"]).items():
            cols[m].append(val)
    out = {}
    for m in MEASURES:
        vals = [x for x in cols.get(m, []) if x is not None]
        out[m] = (sum(vals) / len(vals)) if vals else None
    return out


def take_outcome(result: dict) -> str | None:
    """A sequence's reading at its last frame: as recorded / another command / not read (NONE and 'no person'). None for a single frame."""
    seq = result.get("sequence")
    if result["kind"] != "sequence" or not seq:
        return None
    cmd = (seq.get("final") or {}).get("command", "NONE")
    if cmd == result["command"]:
        return "read_as_recorded"
    return "not_read" if cmd == "NONE" else "read_other_command"


# ---------------------------------------------------------------- INVALID rules (16.31.1 D3, 16.31.5)

def invalid_reasons(result: dict, row: dict | None, part: str, cfg: dict, warm_up_ok: bool, timing_problem) -> tuple[list[str], list[str]]:
    """(INVALID reasons: technical failures only, notes such as a look defect). Never decided from what the models saw."""
    why, notes = [], []
    if row is None:
        return [f"no recordings.jsonl row for {result['name']}: the recording cannot be checked against Unity's record (iv)"], notes
    declared = cfg["avatar"]["proceed_sequence_frames"] if result["command"] == "PROCEED" else cfg["avatar"]["sequence_frames"]
    need = declared if result["kind"] == "sequence" else 1
    if result["errors"]:
        why.append("frames or headers missing, truncated or with bad intrinsics (i, ii): " + "; ".join(result["errors"][:3]))
    if result["n_frames"] < need:
        why.append(f"{result['n_frames']} frames, fewer than the declared {need} (i)")
    for key, got, want in (("look", row.get("look"), result["look"]), ("command", row.get("command"), result["command"]),
                           ("distance_m", row.get("distance_m"), result["distance_m"])):
        if key == "distance_m":
            bad = got is None or abs(float(got) - float(want)) > 1e-6
        else:
            bad = got != want
        if bad:
            why.append(f"recordings.jsonl says {key} {got!r} but the recording is {want!r} (iv)")
    if result["command"] != "NONE" and (row.get("arm") or "") != (result.get("arm") or ""):
        why.append(f"recordings.jsonl says arm {row.get('arm')!r} but the recording's header says {result.get('arm')!r} (iv)")
    if part == PLAY and result["kind"] == "sequence" and result["n_frames"] >= 2:
        times = [f["t"] for f in result["frames"]]
        prob = timing_problem(times, result["command"])
        if prob:
            why.append("timing rule of addendum 10 broken (iii): " + prob[:160])
    pix = int(row.get("cyan_pixels") or 0) + int(row.get("magenta_pixels") or 0)
    if pix > 0:
        flag = row.get("shaders_compiling")
        if flag is True:
            why.append(f"{pix} placeholder-colour pixels while shaders_compiling is true (v)")
        elif flag is False:
            notes.append(f"look defect: {pix} placeholder-colour pixels after the warm-up finished (reported as failing, not repeated)")
        else:
            raise PartRefused(f"{result['name']}: placeholder pixels but no shaders_compiling in recordings.jsonl: the rule cannot be applied")
        if not warm_up_ok:
            raise PartRefused("placeholder-colour pixels exist but shader_warm_up.jsonl is missing or empty: the placeholder rule cannot be applied (16.31.5)")
    return why, notes


# ---------------------------------------------------------------- aggregation

def stats_mean(group: list[dict], measure: str, settings: dict) -> dict:
    by_look: dict[str, list[float]] = defaultdict(list)
    frames = 0
    for t in group:
        v = t["shares"].get(measure)
        if v is not None:
            by_look[t["look"]].append(v)
            frames += t["n_frames"]
    r = ac.mean_with_bootstrap(by_look, settings)
    return {"n": r["takes"], "mean": r["mean"], "lo": r["interval"][0] if r["interval"] else None, "hi": r["interval"][1] if r["interval"] else None,
            "frames": frames}


def stats_yesno(group: list[dict], outcome: str, z: float) -> dict:
    seqs = [t for t in group if t["outcome"] is not None]
    k = sum(t["outcome"] == outcome for t in seqs)
    w = ex._wilson(k, len(seqs), z)
    ci = w["wilson95"] if isinstance(w["wilson95"], list) else [None, None]
    return {"k": k, "n": len(seqs), "lo": ci[0], "hi": ci[1]}


def group_row(keys: dict, group: list[dict], settings: dict, z: float, extra: dict | None = None) -> dict:
    row = {**keys, **(extra or {}), "looks": len({t["look"] for t in group}), "takes_recorded": sum(t["recorded"] for t in group),
           "takes_valid": sum(t["valid"] for t in group), "takes_used": sum(t["used"] for t in group)}
    used = [t for t in group if t["used"]]
    row["sequences_used"] = sum(t["kind"] == "sequence" for t in used)
    row["singles_used"] = sum(t["kind"] == "single" for t in used)
    for m in MEASURES:
        s = stats_mean(used, m, settings)
        row.update({f"{m}_n": s["n"], f"{m}_mean": s["mean"], f"{m}_lo": s["lo"], f"{m}_hi": s["hi"], f"{m}_frames": s["frames"]})
    for o in OUTCOMES:
        s = stats_yesno(used, o, z)
        row.update({f"{o}_k": s["k"], f"{o}_n": s["n"], f"{o}_wilson_lo": s["lo"], f"{o}_wilson_hi": s["hi"]})
    return row


def _cell(row: dict, m: str) -> str:
    if row.get(f"{m}_mean") is None:
        return "not evaluated"
    return f"{row[f'{m}_mean']:.2f} [{row[f'{m}_lo']:.2f}, {row[f'{m}_hi']:.2f}] (n={row[f'{m}_n']})"


def _yn(row: dict, o: str) -> str:
    if not row.get(f"{o}_n"):
        return "not evaluated"
    return f"{row[f'{o}_k']}/{row[f'{o}_n']} [{row[f'{o}_wilson_lo']:.2f}, {row[f'{o}_wilson_hi']:.2f}]"


def write_table(folder: Path, stem: str, title: str, rows: list[dict], key_cols: list[str], note: str = "") -> None:
    cols = list(dict.fromkeys(k for r in rows for k in r))
    with (folder / f"{stem}.csv").open("x", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(cols)
        for r in rows:
            w.writerow([ex._fmt(r.get(c)) for c in cols])
    shown = ["person", "hand_linked", "hand_any", "arm_valid", "facing", "own_cue", "wrong_class"]
    L = [f"# {title}", ""] + ([note, ""] if note else []) + [
        "Take is the unit. Frame measures: mean over takes of the per-take share with a bootstrap 95 % interval over takes (2000 resamples, seed 1, takes resampled within each look); "
        "n = takes with the measure. Take-level outcomes (sequences): count/n with a Wilson 95 % interval. Never an interval over frames.", ""]
    head = key_cols + ["looks", "takes rec/valid/used", "seq/single used"] + shown + [o.replace("_", " ") for o in OUTCOMES]
    L += ["| " + " | ".join(head) + " |", "|" + "---|" * len(head)]
    for r in rows:
        L.append("| " + " | ".join([str(r.get(k, "")) for k in key_cols] + [str(r["looks"]), f"{r['takes_recorded']}/{r['takes_valid']}/{r['takes_used']}",
                                                                              f"{r['sequences_used']}/{r['singles_used']}"] + [_cell(r, m) for m in shown] + [_yn(r, o) for o in OUTCOMES]) + " |")
    (folder / f"{stem}.md").write_text("\n".join(L) + "\n", encoding="utf-8")


# ---------------------------------------------------------------- one part

def process_part(part: dict, session: dict, guard: dict, out: Path, repo: Path, cfg: dict, detector, splits: dict, timing_problem, report: pf.Report) -> dict:
    name = guard["part"]
    rec_dir, folder = part["recordings"], part["folder"]
    rows = read_jsonl(folder / "recordings.jsonl")
    by_name: dict[str, dict] = {}
    for r in rows:
        if r.get("name") in by_name:
            raise PartRefused(f"{name}: two rows of recordings.jsonl are named {r.get('name')!r}: repeat declarations are not defined yet (AUDIT.md 16.33.1 B 3)")
        by_name[r.get("name")] = r
    warm = folder / "shader_warm_up.jsonl"
    warm_ok = warm.is_file() and bool(read_jsonl(warm))
    if not warm_ok:
        report.add(3, f"warm-up record ({name})", pf.OK, "shader_warm_up.jsonl missing or empty: allowed only while no recording has placeholder-colour pixels (checked per take)")
    lc_out = out / "look_check"
    lc_out.mkdir()
    lcfg, lcfg_path = lc.load_config(), HERE / lc.DEFAULT_CONFIG
    result = lc.run_check(rec_dir, detector, lcfg, lcfg_path, lc_out, annotate_png=False)
    report.add(3, f"look check ({name})", pf.OK, f"{len(result['recordings'])} recordings, {sum(r['n_frames'] for r in result['recordings'])} frames; verdicts "
               + ", ".join(f"{k}: {v['verdict']}" for k, v in sorted(result["verdicts"].items())), verdicts=result["verdicts"])
    roles = classify_roles(rows, splits)
    takes = []
    for r in result["recordings"]:
        row = by_name.get(r["name"])
        why, notes = invalid_reasons(r, row, name, cfg, warm_ok, timing_problem)
        cls = roles.get(r["name"], {})
        takes.append({"name": r["name"], "part": name, "kind": "sequence" if r["kind"] == "sequence" else "single", "look": r["look"], "command": r["command"], "distance_m": r["distance_m"], "arm": r.get("arm") or "",
                      "n_frames": r["n_frames"], "clip": cls.get("clip", ""), "clip_status": cls.get("status", "missing_row"), "clip_role": cls.get("clip_role"),
                      "look_role": splits["looks"].get(r["look"]), "kind_group": splits.get("kind_groups", {}).get(r["look"]),
                      "invalid": why, "notes": notes, "shares": take_shares(r), "outcome": take_outcome(r)})
    # the floor (Play only): per look x command x distance x arm, valid sequences >= 2 and valid singles >= 10
    settings, z = ac.bootstrap_settings(), ex.wilson_z(repo)
    floor = json.loads((HERE / "configs/v4/analysis.json").read_text(encoding="utf-8"))["avatar_experiment"]["floor"]
    cells = defaultdict(lambda: {"sequence": 0, "single": 0})
    for t in takes:
        if not t["invalid"]:
            cells[(t["look"], t["command"], t["distance_m"], t["arm"])][t["kind"]] += 1
    for t in takes:
        c = cells[(t["look"], t["command"], t["distance_m"], t["arm"])]
        t["cell_ok"] = True if name == EDIT else (c["sequence"] >= floor["sequences_min"] and c["single"] >= floor["single_takes_min"])
        t["recorded"], t["valid"] = 1, int(not t["invalid"])
        evaluable = not (name == EDIT and t["command"] == "PROCEED")                          # PROCEED is evaluated in Play only (Q8)
        t["used"] = int(t["valid"] and t["cell_ok"] and evaluable)
        t["status"] = ("invalid" if t["invalid"] else "not_evaluated (PROCEED in Edit)" if not evaluable else "insufficient_data (below the floor)" if not t["cell_ok"] else "used")
    # tables
    def tab(keys: tuple, rows_: list[dict], extra_fn=None) -> list[dict]:
        groups: dict = defaultdict(list)
        for t in rows_:
            groups[tuple(t[k] for k in keys)].append(t)
        return [group_row(dict(zip(keys, g)), ts, settings, z, extra_fn(g, ts) if extra_fn else None) for g, ts in sorted(groups.items(), key=lambda kv: tuple(map(str, kv[0])))]

    verdict_of = {k: v["verdict"] for k, v in result["verdicts"].items()}
    per_look = tab(("look", "command", "distance_m"), takes, lambda g, ts: {"kind_group": ts[0]["kind_group"], "look_role": ts[0]["look_role"],
                                                                         "look_check_verdict_of_the_look": verdict_of.get(g[0], "")})
    per_kind = tab(("kind_group", "command", "distance_m"), takes, lambda g, ts: {"looks_in_group": len({t["look"] for t in ts})})
    per_role = tab(("look_role", "command", "distance_m"), takes)
    tables = {"per_look": per_look, "per_kind_group": per_kind, "per_look_role": per_role}
    clip_rows = []
    if name == PLAY:
        gest = [t for t in takes if t["clip_status"] == "clip"]
        clip_rows = tab(("clip_role", "command", "distance_m"), gest)
        tables["per_clip_role"] = clip_rows
    part_dir = out
    kind_verdicts = defaultdict(lambda: defaultdict(int))
    for lk, v in verdict_of.items():
        kind_verdicts[splits.get("kind_groups", {}).get(lk, "?")][v] += 1
    ctx = f"{name.upper()} part" + (" (headline)" if name == PLAY else " (control: posed variants, no floor; never pooled with Play)")
    write_table(part_dir, "per_look", f"{ctx}: per look x command x distance (the headline table: every look)", per_look, ["look", "kind_group", "look_role", "command", "distance_m", "look_check_verdict_of_the_look"],
                "facing is in the per-look table (reported only, not in the verdict). The look-check verdict is the unchanged tool's; the take-based means are shown next to it.")
    write_table(part_dir, "per_kind_group", f"{ctx}: per kind group x command x distance", per_kind, ["kind_group", "command", "distance_m"])
    write_table(part_dir, "per_look_role", f"{ctx}: per look role x command x distance", per_role, ["look_role", "command", "distance_m"])
    if name == PLAY:
        write_table(part_dir, "per_clip_role", f"{ctx}: per clip role x command x distance (from recordings.jsonl; NONE and posed takes excluded)", clip_rows, ["clip_role", "command", "distance_m"])
    inv = [{"name": t["name"], "part": name, "look": t["look"], "command": t["command"], "distance_m": t["distance_m"], "arm": t["arm"], "status": t["status"],
            "reasons": " | ".join(t["invalid"] + t["notes"])} for t in takes if t["invalid"] or t["notes"] or t["status"] != "used"]
    with (part_dir / "takes_not_used.csv").open("x", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=["name", "part", "look", "command", "distance_m", "arm", "status", "reasons"])
        w.writeheader()
        w.writerows(inv)
    (part_dir / "verdict_counts_per_kind_group.json").write_text(json.dumps({k: dict(v) for k, v in kind_verdicts.items()}, indent=1), encoding="utf-8")
    dio_write(part_dir / "guard.json", guard)
    summary = {"part": name, "takes_recorded": len(takes), "takes_invalid": sum(bool(t["invalid"]) for t in takes), "takes_used": sum(t["used"] for t in takes),
               "look_defects": sum(any("look defect" in n for n in t["notes"]) for t in takes), "tables": sorted(tables)}
    report.add(5, f"tables ({name})", pf.OK, f"{summary['takes_recorded']} takes, {summary['takes_invalid']} invalid, {summary['takes_used']} used; "
               f"per_look, per_kind_group, per_look_role" + (", per_clip_role" if name == PLAY else "") + " as CSV and Markdown", **summary)
    return summary


def load_session_for(part: dict) -> dict:
    return ds.load_avatar_session(part["folder"])


def classify_roles(rows: list[dict], splits: dict) -> dict:
    return ac.classify(rows, splits)


def dio_write(path: Path, obj) -> None:
    path.write_text(json.dumps(obj, indent=2, default=str) + "\n", encoding="utf-8")


# ---------------------------------------------------------------- the runbook

def preflight(avatar_root: Path, parts_found: list[str]) -> None:
    for part in parts_found:
        for d in sorted(avatar_root.glob("process_avatar_zip_v4_*")) if avatar_root.is_dir() else []:
            for m in d.glob(f"{part}/AVATAR_REPORT_DONE.json"):
                raise pf.StepFailed(f"the {part} part was already reported ({d.name}): an avatar-experiment part is reported once")


def run(zip_path, sha256: str, repo: Path | None = None, config: str | Path | None = None, avatar_root: str | Path | None = None, detector=None,
        device: str | None = None, work_root: str | Path | None = None, keep_data: bool = False) -> tuple[int, Path, pf.Report]:
    cfg = pf.load_config(config)
    repo = Path(repo) if repo else fz.REPO
    zpath = Path(zip_path)
    report = pf.Report(zpath, False, "process_avatar_zip_v4", "Parts")
    root = pf._root(str(avatar_root or cfg["avatar_root"]))
    root.mkdir(parents=True, exist_ok=True)
    out = pf.new_report_dir(root, "process_avatar_zip_v4")
    failed, work = None, None
    try:
        got, warnings, meta = pf.verify_zip_hash(zpath, sha256)
        folders = list(meta.get("folders") or [])
        report.settings = folders
        if not folders:
            raise pf.StepFailed("MANIFEST.json has no 'folders': not a zip made by final_zip_v4.py avatar")
        report.add(1, "verify", pf.OK, f"SHA-256 {got[:12]}... matches; testzip and MANIFEST.json agree; folders {', '.join(folders)}" + (f"; warning: {'; '.join(warnings)}" if warnings else ""), sha256=got)
        work = Path(tempfile.mkdtemp(prefix="avatar_zip_", dir=str(work_root) if work_root else None))      # the frames are copied here, used and removed: the zip is the evidence
        pf.copy_out(zpath, {"files": [{**f, "name": f["name"]} for f in meta["files"]]},
                    [{"setting": "avatar", "label": "avatar", "unity": folders, "bridge": [], "markers": []}], work)
        parts = find_parts(work, folders)
        splits = ds.load(repo / "robot_vision/configs/v4/data_splits.json")
        sessions, guards = {}, {}
        for p in parts:
            session = ds.load_avatar_session(p["folder"])
            rows = read_jsonl(p["folder"] / "recordings.jsonl") if (p["folder"] / "recordings.jsonl").is_file() else None
            if rows is None:
                raise PartRefused(f"{p['folder'].name}: no recordings.jsonl")
            looks = {r["look"] for r in rows}
            clips = {r["clip"] for r in rows if r.get("clip")}
            try:
                guard = ds.guard_avatar_experiment(looks, clips, session, splits, repo)
            except SystemExit as e:
                raise pf.StepFailed(f"{p['folder'].name}: the avatar guard refused: {e}") from None
            if guard["part"] in sessions:
                raise pf.StepFailed(f"two run folders of the part {guard['part']!r} in the zip: a part is reported once")
            sessions[guard["part"]], guards[guard["part"]] = p, guard
            report.add(2, f"guard ({guard['part']})", pf.OK, f"{p['folder'].name}: official {guard['part']} run, commit {str(guard['commit'])[:10]}, markers STARTED and DONE"
                       + (f", DONE status {guard['status']!r}" if guard["status"] else "") + f"; {len(looks)} looks, {len(clips)} clips, all listed", guard=guard)
        preflight(root, list(sessions))
        sys.path.insert(0, str(repo / "finals_v4"))
        import avatar_rehearsal_check as arc                                                  # Nusrat's timing rule, imported read-only
        own_detector = detector is None
        det = detector if detector is not None else lc.RealDetector(device)
        try:
            for part_key in (PLAY, EDIT):                                                    # Play first: the headline; the parts are never pooled
                if part_key not in sessions:
                    report.add(3, f"part {part_key}", pf.SKIPPED, "not in the zip")
                    continue
                pdir = out / part_key
                pdir.mkdir()
                process_part(sessions[part_key], load_session_for(sessions[part_key]), guards[part_key], pdir, repo, cfg, det, splits, arc.timing_problem, report)
                fg_marker = pdir / "AVATAR_REPORT_DONE.json"
                with fg_marker.open("x", encoding="utf-8") as fh:
                    fh.write(json.dumps({"part": part_key, "zip_sha256": got, "written": datetime.now().isoformat(timespec="seconds"),
                                         "note": "this part of the avatar experiment was reported; it is never reported again"}, indent=2) + "\n")
        finally:
            if own_detector and hasattr(det, "close"):
                det.close()
    except pf.StepFailed as e:
        failed = str(e)
        report.add(99, "STOPPED", pf.FAIL, failed)
    except SystemExit as e:
        failed = str(e)
        report.add(99, "STOPPED", pf.FAIL, failed)
    if work is not None and not keep_data:
        shutil.rmtree(work, ignore_errors=True)
    report.write(out, failed)
    return (1 if failed else 0), out, report


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("zip")
    ap.add_argument("--sha256", required=True)
    ap.add_argument("--config", default=None)
    ap.add_argument("--avatar-root", default=None, help="where the results folder is made (default: avatar_root of configs/v4/experiments/phase_b.json)")
    ap.add_argument("--device", default=None, choices=["cpu", "cuda", "mps"])
    a = ap.parse_args(argv)
    code, out, _ = run(a.zip, a.sha256, config=a.config, avatar_root=a.avatar_root, device=a.device)
    print(f"results: {out}")
    return code


if __name__ == "__main__":
    sys.exit(main())
