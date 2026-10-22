"""Results archive for the supervisor and the paper: copies run folders (never modifies or deletes them), checks
them and regenerates summary tables and plots from the copies.

A new folder <archive_root>/results_archive_<time>/ (outside the repository; configs/results_archive.json):
    README.md            per folder: what it is, seed, machine, date, commit; what is comparable across machines
    CHECKSUMS.sha256     SHA-256 of every other file (sha256sum / shasum -a 256 -c format)
    AUDIT.md             copy of the repository's AUDIT.md
    checks.json          done markers, folders not present, copy verification, frozen config and model hashes
    archive_config/      the archive config, the manifest and build_info.json (git commit of this script)
    environment/         pip freeze, Python, OS, Unity; per run: commit, device and precision; model SHA-256;
                         run_checks/ (worker and device checks)
    configs_frozen/      the frozen configs at their repository paths, and hashes.csv
    task1/{final,development,summary}/  task2/{final,replication,development,summary}/  thud_validation/
Next to it: results_archive_<time>.zip and results_archive_<time>.zip.sha256. Then the summary tables and plots
(.csv, .md, .png) are copied to <repo>/results/summary/ for committing.

The run folders are listed in configs/results_manifest.json (task, role, kind, session). Model weights and Mixamo
files are never copied. Folders on the teammate's machine are reported as not present. This is reporting code: it
reads Unity truth through hri_trials.merge (evaluation code; inference code never imports this module).

Usage (from robot_vision/):
    python make_results_archive.py [--archive-root DIR] [--no-zip] [--no-repo-summary] [--replace-repo-summary]
    python make_results_archive.py --verify <archive folder>
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import platform
import re
import shutil
import statistics as st
import subprocess
import sys
import zipfile
from collections import Counter
from datetime import datetime
from importlib import metadata
from pathlib import Path, PurePosixPath

import hri_analysis as ha
import hri_trials as ht

HERE = Path(__file__).resolve().parent
DEFAULT_CONFIG = "configs/results_archive.json"
LOCAL_CONFIG = "configs/results_archive.local.json"
ROLES = ("final", "replication", "development", "validation", "check")
DONE = {"final": "FINAL_DONE.json", "replication": "REPLICATION_DONE.json"}
CHECKSUMS = "CHECKSUMS.sha256"
STAMP_RE = re.compile(r"(\d{8})_(\d{6})$")
NA = "not recorded"
KINDS = {
    "unity": "Unity trial runner: truth, outcomes, goal order",
    "bridge": "Python bridge: decisions, perception, timing",
    "hri_trials": "merged per-run log (hri_trials.py)",
    "hri_analysis": "analysis (hri_analysis.py)",
    "session_check": "acceptance criteria check (hri_session_check.py)",
    "sweep": "Unity gesture sweep: truth per sample",
    "dev_eval": "development evaluation (hri_eval_dev.py)",
    "replay": "replay client measurement (bridge.replay_client)",
    "images": "rendered pan-tilt images",
    "check": "check output",
    "thud": "THUD++ pipeline output",
}
# Reference palette, light surface: first three categorical slots (validated all-pairs) and neutral ink.
INK, INK2, GRID = "#0b0b0b", "#52514e", "#e4e3df"
SERIES = ("#2a78d6", "#eb6834", "#1baf7a")


# ---------------------------------------------------------------- config and manifest

def _p(p, base: Path = HERE) -> Path:
    p = Path(p)
    return p if p.is_absolute() else base / p


def load_config(path=DEFAULT_CONFIG, local=LOCAL_CONFIG) -> dict:
    cfg = json.loads(_p(path).read_text(encoding="utf-8"))
    if local and _p(local).exists():
        cfg.update(json.loads(_p(local).read_text(encoding="utf-8")))
    return cfg


def dig(d, dotted: str):
    for k in dotted.split("."):
        if not isinstance(d, dict) or k not in d:
            return None
        d = d[k]
    return d


def read_json(p: Path):
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None


def dest_for(e: dict) -> str:
    if e["role"] == "validation":
        return f"thud_validation/{e['folder']}"
    if e["role"] == "check":
        return f"environment/run_checks/{e['folder']}"
    return f"{e['task'].lower()}/{e['role']}/{e['folder']}"


def validate_manifest(m: dict) -> list[str]:
    problems, seen = [], set()
    for s, sd in m["sessions"].items():
        if sd.get("role") not in ROLES:
            problems.append(f"session {s}: role {sd.get('role')} not in {ROLES}")
        if sd.get("machine") not in m["machines"]:
            problems.append(f"session {s}: machine {sd.get('machine')} not in machines")
    for f in m["folders"]:
        name, sd = f["folder"], m["sessions"].get(f["session"])
        if sd is None:
            problems.append(f"{name}: unknown session {f['session']}")
            continue
        if name in seen:
            problems.append(f"{name}: listed twice")
        seen.add(name)
        if f.get("kind") not in KINDS:
            problems.append(f"{name}: unknown kind {f.get('kind')}")
        if not STAMP_RE.search(name):
            problems.append(f"{name}: no _YYYYmmdd_HHMMSS time stamp")
        if f.get("kind") == "unity" and sd["role"] in ("final", "replication", "development") \
                and not name.startswith(f"trials_{sd['role']}_{sd['task']}_"):
            problems.append(f"{name}: a {sd['role']} {sd['task']} Unity folder must start with trials_{sd['role']}_{sd['task']}_")
        if f.get("location") not in (None, "teammate"):
            problems.append(f"{name}: location must be absent or 'teammate'")
    return problems


def entries(m: dict) -> list[dict]:
    out = []
    for f in m["folders"]:
        s = m["sessions"][f["session"]]
        e = {**{k: s.get(k) for k in ("task", "role", "seed", "machine", "audit", "what", "device_note")}, **f}
        e["machine_text"] = m["machines"][e["machine"]]
        e["machine_short"] = e["machine_text"].split(":")[0]
        e["dest"] = dest_for(e)
        out.append(e)
    return out


def folder_date(name: str) -> str:
    m = STAMP_RE.search(name)
    if not m:
        return NA
    d, t = m.groups()
    return f"{d[:4]}-{d[4:6]}-{d[6:]} {t[:2]}:{t[2:4]}:{t[4:]}"


# ---------------------------------------------------------------- copying and hashing

def sha256_file(p: Path) -> str:
    h = hashlib.sha256()
    with p.open("rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def sha256_lf(p: Path) -> str:
    """Hash with CRLF -> LF, as the frozen records were taken (a Windows checkout has CRLF, same content)."""
    return hashlib.sha256(p.read_bytes().replace(b"\r\n", b"\n")).hexdigest()


def exclusion(rel: PurePosixPath, ex: dict) -> str | None:
    parts = [p.lower() for p in rel.parts]
    for d in ex.get("dir_names", []):
        if d.lower() in parts[:-1]:
            return f"directory {d}"
    if rel.suffix.lower() in {s.lower() for s in ex.get("suffixes", [])}:
        return f"file type {rel.suffix.lower()}"
    for s in ex.get("name_contains", []):
        if any(s.lower() in p for p in parts):
            return f"name contains '{s}'"
    return None


def copy_tree(src: Path, dst: Path, ex: dict) -> tuple[dict[str, str], list[dict]]:
    """Copy the files of src into the new folder dst, hashing the bytes read. Reads src only."""
    hashes, excluded = {}, []
    for p in sorted(src.rglob("*")):
        if p.is_symlink() or not p.is_file():
            continue
        rel = PurePosixPath(p.relative_to(src).as_posix())
        why = exclusion(rel, ex)
        if why:
            excluded.append({"file": str(rel), "reason": why, "bytes": p.stat().st_size})
            continue
        out = dst.joinpath(*rel.parts)
        out.parent.mkdir(parents=True, exist_ok=True)
        h = hashlib.sha256()
        with p.open("rb") as fi, out.open("xb") as fo:
            for chunk in iter(lambda: fi.read(1 << 20), b""):
                h.update(chunk)
                fo.write(chunk)
        shutil.copystat(p, out)
        hashes[str(rel)] = h.hexdigest()
    return hashes, excluded


def stat_snapshot(folder: Path) -> dict:
    return {p.relative_to(folder).as_posix(): (p.stat().st_size, p.stat().st_mtime_ns)
            for p in folder.rglob("*") if p.is_file()}


def write_csv(path: Path, rows: list[dict], fields: list[str] | None = None) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fields = fields or (list(rows[0]) if rows else ["empty"])
    with path.open("x", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=fields, extrasaction="ignore")
        w.writeheader()
        for r in rows:
            w.writerow(r)


def write_json(path: Path, data) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2, default=str) + "\n", encoding="utf-8")


# ---------------------------------------------------------------- checks

def check_folder(e: dict, folder: Path | None) -> list[dict]:
    """Presence and done markers: final -> FINAL_DONE.json, replication -> REPLICATION_DONE.json (Unity folders)."""
    name = e["folder"]
    if folder is None:
        if e.get("location") == "teammate":
            return [{"folder": name, "check": "present", "status": "not_on_this_machine",
                     "detail": f"on the teammate's machine (Anisha); figures in {e['audit']}"}]
        return [{"folder": name, "check": "present", "status": "MISSING", "detail": "not found under the output root"}]
    out = [{"folder": name, "check": "present", "status": "ok", "detail": ""}]
    if e["kind"] != "unity":
        return out
    want = DONE.get(e["role"])
    for marker in DONE.values():
        p = folder / marker
        if marker == want:
            if not p.exists():
                out.append({"folder": name, "check": marker, "status": "MISSING", "detail": f"a {e['role']} folder must hold {marker}"})
                continue
            d = read_json(p) or {}
            bad = [k for k, v in (("task", e["task"]), ("mode", e["role"]), ("seed", e["seed"])) if d.get(k) != v]
            out.append({"folder": name, "check": marker, "status": "PROBLEM" if bad else "ok",
                        "detail": f"{marker} disagrees on {bad}: {d}" if bad
                        else f"{d.get('successes')}/{d.get('trials')} successes, task {d.get('task')}, seed {d.get('seed')}"})
        elif p.exists():
            out.append({"folder": name, "check": marker, "status": "PROBLEM", "detail": f"a {e['role']} folder holds {marker}"})
    return out


# ---------------------------------------------------------------- environment

META_FILES = ("session.json", "run_info.json", "run.json", "summary.json", "evaluation_report.json",
              "tracking_summary.json", "motion_evaluation.json", "decision_log.json", "device_check.json")


def run_metadata(folder: Path) -> dict:
    """Commit, platform, versions, device and precision as recorded in a run folder (None if not recorded)."""
    m = dict.fromkeys(("commit", "commit_source", "uncommitted_changes", "platform", "python", "unity_version",
                       "torch", "device", "precision", "device_source", "device_evidence"))
    for n in META_FILES:
        d = read_json(folder / n)
        if not isinstance(d, dict):
            continue
        for key in ("git_commit", "git.commit", "unity_git_commit"):
            v = dig(d, key)
            if v and not m["commit"]:
                m.update(commit=v, commit_source=f"{n} {key}", uncommitted_changes=dig(d, "git.uncommitted_changes"))
        m["platform"] = m["platform"] or dig(d, "platform") or dig(d, "packages.platform")
        m["python"] = m["python"] or dig(d, "python") or dig(d, "packages.python")
        m["unity_version"] = m["unity_version"] or dig(d, "unity_version")
        m["torch"] = m["torch"] or dig(d, "packages.torch") or dig(d, "inference_devices.versions.torch") or dig(d, "versions.torch")
        models = dig(d, "inference_devices.models") or (d.get("models") if n == "device_check.json" else None)
        if isinstance(models, dict) and not m["device"]:
            m["device"] = "; ".join(f"{k}: {v.get('device')}" for k, v in models.items())
            m["precision"] = "; ".join(f"{k}: {v.get('precision')}" for k, v in models.items())
            m["device_source"] = f"{n} (read at runtime)"
        dev = dig(d, "detector.model_parameters_device")
        if dev and not m["device"]:
            m.update(device=f"yolo11n: {dev}", device_source=f"{n} detector.model_parameters_device")
        cuda = dig(d, "threads_at_start.torch_cuda")
        if cuda is not None:
            m["device_evidence"] = f"{n} threads_at_start.torch_cuda = {cuda}"
    if isinstance(m["python"], dict):
        m["python"] = None
    return m


def pip_freeze() -> str:
    r = subprocess.run([sys.executable, "-m", "pip", "freeze"], capture_output=True, text=True, timeout=300)
    if r.returncode != 0:
        return f"# pip freeze failed: {r.stderr.strip()}\n"
    lines = [re.sub(r"(@ file://|-e ).*", r"\1<local path>", ln) for ln in r.stdout.splitlines()]
    return "\n".join(lines) + "\n"


def archive_machine(cfg: dict) -> dict:
    versions = {}
    for pkg in ("torch", "torchvision", "ultralytics", "mediapipe", "opencv-python", "numpy", "matplotlib", "transformers"):
        try:
            versions[pkg] = metadata.version(pkg)
        except metadata.PackageNotFoundError:
            versions[pkg] = None
    uv = _p(cfg["unity_project_version"])
    unity = dict(ln.split(": ", 1) for ln in uv.read_text(encoding="utf-8").splitlines() if ": " in ln) if uv.exists() else None
    return {"note": "Environment at archive time (the same PC as the Task 1 final and the Task 2 replication). Per-run values "
                    "as recorded in each run folder are in runs.csv.",
            "python": platform.python_version(), "platform": platform.platform(), "system": platform.system(),
            "machine": platform.machine(), "processor": platform.processor(), "packages": versions,
            "unity_project_version": unity}


def model_hashes(cfg: dict, repo: Path) -> list[dict]:
    rows = []
    for m in cfg["models"]:
        p = None
        if "path" in m:
            p = _p(m["path"])
            where = _rel(p, repo)
        else:
            where = f"{m['hf_repo']}@{m['hf_revision']}"
            try:
                from huggingface_hub import try_to_load_from_cache
                for f in m["hf_files"]:
                    r = try_to_load_from_cache(m["hf_repo"], f, revision=m["hf_revision"])
                    if isinstance(r, str):
                        p, where = Path(r), f"{where}/{f} (Hugging Face cache)"
                        break
            except ImportError:
                pass
        present = p is not None and p.exists()
        expected = None
        if m.get("expected_from"):
            src = read_json(_p(m["expected_from"]))
            expected = dig(src, m["key"]) if src else None
        sha = sha256_file(p) if present else None
        rows.append({"model": m["name"], "file": where, "present": present, "sha256": sha or NA,
                     "expected_sha256": expected or "",
                     "expected_from": f"{_rel(_p(m['expected_from']), repo)} {m['key']}" if m.get("expected_from") else "",
                     "matches": "" if not (expected and sha) else sha == expected,
                     "archived": "no (weights are never archived)"})
    return rows


def _rel(p: Path, base: Path) -> str:
    try:
        return p.resolve().relative_to(base.resolve()).as_posix()
    except ValueError:
        return p.name


# ---------------------------------------------------------------- frozen configs

def frozen_configs(cfg: dict, repo: Path, out: Path) -> list[dict]:
    items = []      # (repo-relative path, expected sha256 or None, recorded in, note)
    for rec_path in cfg["frozen_records"]:
        rec_file = _p(rec_path)
        rec_rel = _rel(rec_file, repo)
        rec = json.loads(rec_file.read_text(encoding="utf-8"))
        items.append((rec_rel, None, "", "frozen record"))
        for k, v in rec.items():
            if k.startswith("sha256") and isinstance(v, dict):
                items += [(path, h, f"{rec_rel} {k}", "") for path, h in v.items()]
        for t, td in rec.get("tasks", {}).items():
            rc = td.get("route_config")
            if rc:
                items.append((rc["path"], rc["sha256"], f"{rec_rel} tasks.{t}.route_config", "per task"))
    for x in cfg.get("frozen_extra_configs", []):
        exp = dig(read_json(_p(x["expected_from"])), x["key"]) if x.get("expected_from") else None
        items.append((x["path"], exp, f"{_rel(_p(x['expected_from']), repo)} {x['key']}" if exp else "", x.get("note", "")))
    rows = []
    for path, exp, where, note in items:
        src = repo / path
        if not src.exists():
            rows.append({"path": path, "recorded_in": where, "expected_sha256": exp or "", "sha256_lf_normalised": "MISSING",
                         "sha256_file_bytes": "MISSING", "matches": False if exp else "", "note": note})
            continue
        dst = out.joinpath(*PurePosixPath(path).parts)
        dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(src, dst)
        lf, raw = sha256_lf(src), sha256_file(src)
        rows.append({"path": path, "recorded_in": where, "expected_sha256": exp or "", "sha256_lf_normalised": lf,
                     "sha256_file_bytes": raw, "matches": (exp in (lf, raw)) if exp else "", "note": note})
    write_csv(out / "hashes.csv", rows)
    return rows


# ---------------------------------------------------------------- summaries

def session_pairs(ents: list[dict], archive: Path) -> dict[str, tuple[Path, Path]]:
    """Session -> (Unity folder with truth_run*.json, bridge folder with python_trial_*.json), when exactly one each."""
    unity, bridge = {}, {}
    for e in ents:
        d = archive / e["dest"]
        if not d.exists():
            continue
        if e["kind"] in ("unity", "sweep") and (any(d.glob("truth_run*.json")) or (d / "truth_sweep.csv").exists()):
            unity.setdefault(e["session"], []).append(d)
        if e["kind"] == "bridge" and (any(d.glob("python_trial_*.json")) or (d / "perception.csv").exists()):
            bridge.setdefault(e["session"], []).append(d)
    return {s: (u[0], bridge[s][0]) for s, u in unity.items() if len(u) == 1 and len(bridge.get(s, [])) == 1}


def _cell(v) -> str:
    return "" if v is None else str(v)


def _same(a, b: str) -> bool:
    a = _cell(a)
    if a == b:
        return True
    try:
        return abs(float(a) - float(b)) < 1e-9
    except ValueError:
        return False


def compare_with_original(rows: list[dict], original_csv: Path) -> list[dict]:
    orig = ht.read_csv(original_csv)
    out = []
    for c in ht.COLUMNS:
        if not orig or c not in orig[0]:
            out.append({"column": c, "runs_equal": "", "runs_differing": "", "note": "not in the original results.csv"})
            continue
        eq = sum(_same(a.get(c), b.get(c, "")) for a, b in zip(rows, orig))
        out.append({"column": c, "runs_equal": eq, "runs_differing": len(rows) - eq,
                    "note": "" if len(rows) == len(orig) else f"run count {len(rows)} vs {len(orig)}"})
    return out


def write_session_summary(runs: list[dict], out: Path, label: str, plots: bool, original_hri: Path | None) -> dict:
    out.mkdir(parents=True, exist_ok=True)
    rows = [ht.csv_row(r) for r in runs]
    write_csv(out / "runs.csv", rows, ht.COLUMNS)
    write_csv(out / "junctions.csv", [{"trial": r["trial"], "b_name": r["b"]["name"], **j} for r in runs for j in r["junctions"]],
              ["trial", "b_name", "junction", "shown", "read", "asks", "result"])
    for r in runs:
        r["_folder"] = label
    a = ha.analyse(runs)
    write_json(out / "analysis.json", a)
    (out / "analysis.md").write_text(ha.markdown(a), encoding="utf-8")
    if plots:
        ha.plots(runs, out)
    result = {"analysis": a}
    if original_hri is not None and (original_hri / "results.csv").exists():
        cmp = compare_with_original(rows, original_hri / "results.csv")
        write_csv(out / "check_against_original_hri_trials.csv", cmp)
        diff = [c["column"] for c in cmp if c["runs_differing"] not in ("", 0)]
        result["equal_to_original_hri_trials"] = {"folder": original_hri.name, "columns_differing": diff}
    return result


def forward_hand_rows(sweep: Path, bridge: Path, hold_s: float) -> tuple[list[dict], dict]:
    import hri_eval_dev as hed
    res = hed.eval_forward_hands(sweep, bridge, hold_s)
    rows = []
    for hand, e in res["per_hand"].items():
        reads = e["reads"]
        rows.append({"hand": hand, "samples": e["samples"], "frames": e["frames"], "read_FORWARD": reads.get("FORWARD", 0),
                     "read_NONE": reads.get("NONE", 0), "read_STOP": reads.get("STOP", 0),
                     "read_other": e["frames"] - sum(reads.get(k, 0) for k in ("FORWARD", "NONE", "STOP")),
                     "forward_rate": e["forward_rate"], "coverage": e["coverage"], "samples_with_stop": e["samples_with_stop"],
                     "hold_strict_correct": e["hold_strict"].get("correct", 0), "hold_strict_none": e["hold_strict"].get("none", 0),
                     "hold_strict_wrong": e["hold_strict"].get("wrong", 0)})
    return rows, res["rule"]


# ---------------------------------------------------------------- the original Task 2 final from AUDIT.md

def audit_section(text: str, number: int) -> str:
    m = re.search(rf"^## {number}\. .*?(?=^## |\Z)", text, re.M | re.S)
    return m.group(0) if m else ""


def parse_table(section: str) -> list[dict]:
    lines = [ln.strip() for ln in section.splitlines()]
    start = next((i for i, ln in enumerate(lines) if ln.startswith("|")), None)
    if start is None:
        return []
    cells = lambda ln: [c.strip() for c in ln.strip("|").split("|")]
    head, rows = cells(lines[start]), []
    for ln in lines[start + 2:]:
        if not ln.startswith("|"):
            break
        rows.append(dict(zip(head, cells(ln))))
    return rows


def task2_original_from_audit(text: str) -> list[dict]:
    """Per-run table of AUDIT.md section 2 (run, goal B, outcome, distance to B, time, junctions, closest)."""
    runs = []
    for row in parse_table(audit_section(text, 2)):
        v = list(row.values())
        if len(v) < 7 or not v[0].isdigit():
            continue
        junctions = []
        for part in filter(None, (p.strip() for p in v[5].split(";"))):
            j, rest = part.split(":", 1)
            shown, read = (x.strip() for x in rest.split(">"))
            junctions.append({"junction": j.strip(), "shown": shown, "read": read, "asks": None})
        runs.append({"trial": int(v[0]), "b": {"name": v[1]}, "outcome": v[2], "final_distance_to_b_m": float(v[3]),
                     "total_s": float(v[4]), "junctions": junctions, "closest_human_m": float(v[6])})
    return runs


# ---------------------------------------------------------------- three-run comparison

def _vals(runs, key):
    return [r.get(key) for r in runs if r.get(key) is not None]


def _na(x) -> str:
    return "not available" if x is None else str(x)


def _mean_max(v, nd=3, unit=""):
    return f"mean {st.fmean(v):.{nd}f}{unit}, max {max(v):.{nd}f}{unit}" if v else "not available"


def _reads(runs) -> tuple[str, str]:
    js = [j for r in runs for j in r["junctions"]]
    ok = sum(j["shown"] == j["read"] for j in js)
    cov = sum(j["read"] not in ("NONE", None) for j in js)
    by = Counter(j["shown"] for j in js)
    good = Counter(j["shown"] for j in js if j["shown"] == j["read"])
    per = ", ".join(f"{c} {good[c]}/{by[c]}" for c in sorted(by))
    return f"{ok}/{len(js)} (coverage {cov}/{len(js)})", per


def comparison_rows(views: dict, cfg: dict) -> list[dict]:
    """Rows: measure, comparable_across_machines, one column per view, note. views: key -> dict (see build)."""
    keys = list(views)
    rows = []

    def add(measure, comparable, fn, note=""):
        rows.append({"measure": measure, "comparable_across_machines": comparable,
                     **{k: fn(views[k]) for k in keys}, "note": note})

    def rep(v, key, fmt="{}"):
        x = (v.get("reported") or {}).get(key)
        return fmt.format(x) if x is not None else "not available"

    def from_runs_or_rep(v, fn, rep_key=None, fmt="{}"):
        if v.get("analysis") is not None:
            return fn(v)
        return rep(v, rep_key, fmt) if rep_key else "not available"

    add("task", "-", lambda v: v["task_text"])
    add("source of the figures", "-", lambda v: v["source"])
    add("machine; inference device", "-", lambda v: f"{v['machine']}; {v['device']}")
    add("commit", "-", lambda v: v["commit"])
    add("seed; trials", "-", lambda v: f"{v['seed']}; {len(v['runs'])}")
    add("successes (Wilson 95 %)", "yes", lambda v: (lambda k, n: f"{k}/{n} ({ha.wilson(k, n)[0]}-{ha.wilson(k, n)[1]})")(
        sum(r["outcome"] == "SUCCESS" for r in v["runs"]), len(v["runs"])))
    add("junctions / stops read as shown (coverage)", "yes", lambda v: _reads(v["runs"])[0])
    add("read at the first ask", "yes", lambda v: rep(v, "junctions_at_first_ask") if v.get("analysis") is None else
        f"{sum(j.get('asks') == 1 for r in v['runs'] for j in r['junctions'])}/{sum(len(r['junctions']) for r in v['runs'])}")
    add("gesture shown vs read, per command", "yes", lambda v: _reads(v["runs"])[1])
    add("collisions (with a person)", "yes", lambda v: (f"{rep(v, 'collisions')} ({rep(v, 'human_collisions')})" if v.get("analysis") is None
        else f"{sum(r['collisions'] for r in v['runs'])} ({sum(r['human_collisions'] for r in v['runs'])})"))
    add("final distance to B (m)", "yes", lambda v: _mean_max(_vals([r for r in v["runs"] if r["outcome"] == "SUCCESS"], "final_distance_to_b_m")))
    add("closest approach to a worker (m)", "yes", lambda v: (lambda x: f"min {min(x):.3f}, mean {st.fmean(x):.3f}" if x else "not available")(
        _vals(v["runs"], "closest_human_m")))
    add("time excluding stale-perception stops (s)", "yes", lambda v: from_runs_or_rep(
        v, lambda w: _mean_max(_vals(w["runs"], "time_excl_stale_stops_s"), 2), "time_excl_stale_stops_s_mean", "mean {}"),
        "; ".join(f"{views[k]['title']}: {views[k]['reported']['time_excl_stale_stops_note']}" for k in keys
                  if (views[k].get("reported") or {}).get("time_excl_stale_stops_note")))
    add("time in motion, Unity speed > 0.05 m/s (s)", "yes", lambda v: from_runs_or_rep(
        v, lambda w: _mean_max(_vals(w["runs"], "in_motion_s"), 2), "in_motion_s_mean", "mean {}"))
    add("time per step, mean: navigate / scan / approach / ask / gesture / execute (s)", "yes", lambda v: (
        " / ".join(str(v["analysis"]["step_s"][s].get("mean")) for s in ht.STEPS) if v.get("analysis") is not None else
        (" / ".join(str(v["reported"]["step_s_mean"].get(s)) for s in ht.STEPS)
         if (v.get("reported") or {}).get("step_s_mean") else "not available")))
    add("speed average / max (m/s); turn rate max (deg/s); travelled / straight line", "yes", lambda v: (
        f"{v['analysis']['speed_mps']['avg'].get('mean')} / {v['analysis']['speed_mps']['max'].get('max')}; "
        f"{v['analysis']['turn_dps']['max'].get('max')}; {v['analysis']['travel_ratio'].get('mean')}" if v.get("analysis") is not None else
        f"{rep(v, 'avg_speed_mps')} / {rep(v, 'max_speed_mps')}; {rep(v, 'max_turn_dps')}; {rep(v, 'travel_ratio')}"))
    add("stale-perception stops (s)", "no", lambda v: from_runs_or_rep(
        v, lambda w: _mean_max(_vals(w["runs"], "stale_stop_s"), 2), "stale_stop_s_mean", "mean {}"))
    add("total time (s)", "no", lambda v: _mean_max(_vals(v["runs"], "total_s"), 2), "includes stale-perception stops")
    add("inference per frame, mean over runs: panorama YOLO / gesture YOLO / MediaPipe / JPEG decode / total (ms)", "no",
        lambda v: (" / ".join(_na((v["analysis"]["inference_ms_mean_of_runs"].get(m) or {}).get("mean"))
                              for m in ("yolo11s-pose/cam360", "yolo11s-pose/gesture", "mediapipe/stop", "jpeg_decode", "total_per_frame"))
                   if v.get("analysis") is not None else
                   " / ".join(_na(v["reported"]["inference_ms_mean"].get(m)) for m in
                              ("yolo11s-pose/cam360", "yolo11s-pose/gesture", "mediapipe/stop", "jpeg_decode", "total_per_frame"))
                   if (v.get("reported") or {}).get("inference_ms_mean") else "not available"))
    add("watchdog stops (decisions.csv counter)", "no", lambda v: (
        str(sum(r.get("watchdog_stops") or 0 for r in v["runs"])) if v.get("analysis") is not None else rep(v, "watchdog_stops")),
        "watchdog trigger changed before the Task 1 final and the replication (AUDIT.md section 9 item 17)")
    return rows


def comparison_markdown(rows: list[dict], views: dict) -> str:
    keys = list(views)
    L = ["# Three-run comparison", "",
         "Columns: " + "; ".join(f"**{views[k]['title']}**" for k in keys) + ".",
         "Comparable across machines per AUDIT.md section 8: success, reads, collisions, distances, time excluding "
         "stale-perception stops, time in motion; not comparable: inference times, stale-perception stops, total time. "
         "Task 1 is a different task (straight route with three stops), shown beside the two Task 2 runs, not a replication.", "",
         "| measure | comparable across machines | " + " | ".join(views[k]["title"] for k in keys) + " | note |",
         "|---|---|" + "---|" * len(keys) + "---|"]
    for r in rows:
        L.append(f"| {r['measure']} | {r['comparable_across_machines']} | " + " | ".join(str(r[k]) for k in keys) + f" | {r['note']} |")
    return "\n".join(L) + "\n"


# ---------------------------------------------------------------- plots

def _style(ax, title: str, xlabel: str) -> None:
    ax.set_title(title, fontsize=9, color=INK, loc="left")
    ax.set_xlabel(xlabel, fontsize=8, color=INK2)
    ax.grid(axis="y", color=GRID, linewidth=0.8)
    ax.set_axisbelow(True)
    for s in ("top", "right"):
        ax.spines[s].set_visible(False)
    for s in ("left", "bottom"):
        ax.spines[s].set_color(INK2)
    ax.tick_params(colors=INK2, labelsize=8)


def plot_per_run(series: list[tuple[str, list[dict]]], out: Path) -> None:
    """Final distance to B and closest approach per run, one line per session (same goal order)."""
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    fig, axes = plt.subplots(1, 2, figsize=(8, 3))
    for ax, key, title in zip(axes, ("final_distance_to_b_m", "closest_human_m"),
                              ("Final distance to B (m)", "Closest approach to a worker (m)")):
        for (label, runs), color in zip(series, SERIES):
            ax.plot([r["trial"] for r in runs], [r[key] for r in runs], color=color, linewidth=2, marker="o",
                    markersize=5, markeredgecolor="white", label=label)
        _style(ax, title, "run")
        ax.set_xticks(range(1, max(len(r) for _, r in series) + 1))
        ax.set_ylim(bottom=0)
    axes[0].legend(frameon=False, fontsize=8, labelcolor=INK)
    fig.tight_layout()
    fig.savefig(out, dpi=150, facecolor="white")
    plt.close(fig)


def plot_three(views: dict, out: Path) -> None:
    """Per-run points and mean (line) of final distance to B and closest approach for each session."""
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    fig, axes = plt.subplots(1, 2, figsize=(8, 3.2))
    keys = list(views)
    for ax, key, title in zip(axes, ("final_distance_to_b_m", "closest_human_m"),
                              ("Final distance to B (m)", "Closest approach to a worker (m)")):
        for i, (k, color) in enumerate(zip(keys, SERIES)):
            ys = _vals(views[k]["runs"], key)
            xs = [i + ((n % 5) - 2) * 0.07 for n in range(len(ys))]
            ax.scatter(xs, ys, s=30, color=color, edgecolors="white", linewidths=1, zorder=3)
            if ys:
                ax.hlines(st.fmean(ys), i - 0.28, i + 0.28, color=INK, linewidth=1.5, zorder=4)
        _style(ax, title, "points = runs, line = mean")
        ax.set_xticks(range(len(keys)), [views[k]["short"] for k in keys])
        ax.set_ylim(bottom=0)
    fig.tight_layout()
    fig.savefig(out, dpi=150, facecolor="white")
    plt.close(fig)


# ---------------------------------------------------------------- README

def readme(info: dict) -> str:
    L = ["# Results archive: avatar-mediated human-robot interaction in a Unity warehouse", "",
         f"Built {info['built']} by `robot_vision/make_results_archive.py` at commit `{info['git']['commit']}` "
         f"(branch {info['git']['branch']}, uncommitted changes: {info['git']['uncommitted_changes']}). "
         "Every run folder here is a **copy**; the originals were only read (checked: "
         f"{'unchanged' if info['originals_unchanged'] else 'CHANGED - see checks.json'}).", "",
         "## Layout", "",
         "| path | content |", "|---|---|",
         "| `README.md` | this file |",
         "| `CHECKSUMS.sha256` | SHA-256 of every other file (verify: see the end of this file) |",
         "| `AUDIT.md` | copy of the repository's audit; the record of every result, change and disclosure |",
         "| `checks.json` | done markers, folders not present, copy verification, frozen config and model hashes |",
         "| `archive_config/` | archive config, run-folder manifest (`results_manifest.json`), `build_info.json` |",
         "| `environment/` | `pip_freeze.txt`, `archive_machine.json` (Python, OS, Unity), `runs.csv` (per run: commit, "
         "platform, Python, Unity, torch, device, precision), `models.csv` (SHA-256; weights not archived), `run_checks/` |",
         "| `configs_frozen/` | frozen configs at their repository paths, `hashes.csv` (recorded vs computed) |",
         "| `task1/final/`, `task1/development/` | Task 1 run folders |",
         "| `task2/final/`, `task2/replication/`, `task2/development/` | Task 2 run folders |",
         "| `task1/summary/`, `task2/summary/` | tables (CSV, Markdown) and plots regenerated from the copied raw data |",
         "| `thud_validation/` | THUD++ pipeline outputs |", "",
         "## Results at a glance", ""]
    L += [f"- {g}" for g in info["glance"]]
    L += ["", "Every accuracy figure in the summaries comes with its coverage; perception against truth (recall, distance "
          "error) is not_evaluated on the final and replication sessions (`hri_eval_dev.py` refuses them by design).", "",
          "## Checks", ""]
    bad = [c for c in info["checks"] if c["status"] not in ("ok",)]
    L += [f"- Run folders listed: {info['n_listed']}; copied: {info['n_copied']}; on the teammate's machine: "
          f"{info['n_teammate']}; missing: {info['n_missing']}.",
          f"- Done markers: every final Unity folder present holds FINAL_DONE.json and every replication folder "
          f"REPLICATION_DONE.json: {'yes' if not [c for c in bad if c['check'] in DONE.values()] else 'NO (below)'}.",
          f"- Copies verified: {info['copy_verified']} ({info['n_files']} files from run folders, re-hashed in the archive).",
          f"- Frozen configs: {info['frozen_match']}.",
          f"- Models: {info['models_match']}.",
          f"- Regenerated per-run tables equal to the original hri_trials folders: {info['regen_equal']}."]
    if bad:
        L += ["", "| folder | check | status | detail |", "|---|---|---|---|"]
        L += [f"| {c['folder']} | {c['check']} | {c['status']} | {c['detail']} |" for c in bad]
    L += ["", "## Task 2 final: original folders", "", info["task2_final_text"], "",
          "## Folders", "",
          "Machine: as declared in the manifest; `environment/runs.csv` adds the platform recorded in each folder. Commit: as "
          "recorded in the folder (Unity session.json, bridge run_info.json, or the analysis script's run.json); "
          "`*` = recorded with uncommitted changes. Seed: dev seed 1, final seed 2; '-' where no seed applies.", "",
          "| archive path | what | task | role | seed | machine | date | commit |", "|---|---|---|---|---|---|---|---|"]
    for e in info["entries"]:
        what = f"{KINDS[e['kind']]}. {e['what']}" + (f" ({e['note']})" if e.get("note") else "") + f" [{e['audit']}]"
        path = f"`{e['dest']}/`" if e["present"] else f"{e['folder']} (not on this machine)"
        L.append(f"| {path} | {what} | {e['task']} | {e['role']} | {e['seed'] if e['seed'] is not None else '-'} | "
                 f"{e['machine_short']} | {folder_date(e['folder'])} | {e['commit_text']} |")
    L += ["", "## What is and is not comparable across machines", "",
          "From AUDIT.md section 8 (Notes) and section 11 item 5. The Task 2 final ran on Anisha's Mac (YOLO on MPS); the "
          "Task 1 final and the Task 2 replication ran on Nusrat's PC (CUDA, RTX 3060).", "",
          "- **Comparable:** " + "; ".join(info["comparability"]["comparable"]) + ".",
          "- **Not comparable:** " + "; ".join(info["comparability"]["not_comparable"]) + ".",
          "- The replication also differs from the original by declared infrastructure (AUDIT.md section 11 item 4): "
          "decoupled server (warm-up, perception threads, heap freeze), corrected watchdog trigger, Unity Editor instead "
          "of batch mode. No frozen setting differs (`configs_frozen/hashes.csv`).",
          "- Task 1 and Task 2 are different tasks; the three-run table (`task2/summary/three_run_comparison.*`) shows "
          "them side by side, not as replications of each other.",
          "- The standing-worker Task 2 layout (AUDIT.md section 12) is for demonstrations only; no folder here uses it.", "",
          "## Excluded from the copies", "",
          "Model weights and Mixamo files are never archived (weights are identified by SHA-256 in `environment/models.csv`). "
          "`_path_migration_backup/` folders hold pre-migration copies with this machine's absolute paths "
          "(each folder's `path_migration.json` records the migration).", ""]
    if info["excluded"]:
        L += ["| reason | files | bytes |", "|---|---|---|"]
        L += [f"| {r} | {n} | {b} |" for r, (n, b) in sorted(info["excluded"].items())]
    else:
        L.append("Nothing matched the exclusion rules.")
    L += ["", "## Output folders on this PC not archived", "",
          "Superseded reruns, hello-mode bridge tests, demo videos and smoke tests; listed so nothing is hidden:", "",
          ", ".join(f"`{n}`" for n in info["not_archived"]) or "none", "",
          "## Verify", "",
          "macOS Terminal, inside this folder: `shasum -a 256 -c CHECKSUMS.sha256`", "",
          "Windows PowerShell, from `robot_vision/` of the repository: "
          "`.\\.venv\\Scripts\\python.exe make_results_archive.py --verify <this folder>` "
          "(macOS: `.venv/bin/python make_results_archive.py --verify <this folder>`). "
          "The zip's SHA-256 is in the `.zip.sha256` file next to it.", ""]
    return "\n".join(L)


# ---------------------------------------------------------------- build

def build(cfg: dict, *, archive_root: Path, output_root: Path, repo: Path, audit: Path, now: datetime,
          freeze=pip_freeze, make_zip: bool = True, repo_summary: Path | None = None,
          replace_repo_summary: bool = False, git: dict | None = None) -> dict:
    import decision_io as dio
    manifest_path = _p(cfg["manifest"])
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    problems = validate_manifest(manifest)
    if problems:
        raise SystemExit("results_manifest.json:\n  " + "\n  ".join(problems))
    ents = entries(manifest)
    name = f"results_archive_{now:%Y%m%d_%H%M%S}"
    archive, zpath = archive_root / name, archive_root / f"{name}.zip"
    if archive.resolve().is_relative_to(repo.resolve()):
        raise SystemExit(f"The archive root must be outside the repository: {archive_root}")
    if archive.exists() or zpath.exists():
        raise SystemExit(f"Archive already exists, not overwriting: {archive}")
    if repo_summary is not None and repo_summary.exists() and not replace_repo_summary:
        raise SystemExit(f"{repo_summary} exists; pass --replace-repo-summary to replace it")
    git = git or dio.git_info()

    sources = {e["folder"]: output_root / e["folder"] for e in ents if (output_root / e["folder"]).is_dir()}
    before = {n: stat_snapshot(p) for n, p in sources.items()}
    archive.mkdir(parents=True)
    shutil.copy2(audit, archive / "AUDIT.md")
    (archive / "archive_config").mkdir()
    shutil.copy2(manifest_path, archive / "archive_config" / "results_manifest.json")
    write_json(archive / "archive_config" / "results_archive_config_used.json", cfg)
    write_json(archive / "archive_config" / "build_info.json",
               {"built": now.isoformat(timespec="seconds"), "git": git, "script": "robot_vision/make_results_archive.py",
                "archive": name})

    # copy
    hashes, excluded, checks = {}, Counter(), []
    excl_bytes = Counter()
    for e in ents:
        src = sources.get(e["folder"])
        e["present"] = src is not None
        checks += check_folder(e, src)
        if src is None:
            continue
        h, ex = copy_tree(src, archive / e["dest"], cfg["exclude"])
        hashes.update({f"{e['dest']}/{k}": v for k, v in h.items()})
        for x in ex:
            excluded[x["reason"]] += 1
            excl_bytes[x["reason"]] += x["bytes"]
    for d in ("task1/final", "task1/development", "task2/final", "task2/replication", "task2/development", "thud_validation"):
        (archive / d).mkdir(parents=True, exist_ok=True)
    for d in ("task2/final", "task2/development", "task1/final", "task1/development", "task2/replication"):
        absent = [e for e in ents if e["dest"].startswith(d + "/") and not e["present"]]
        if absent:
            (archive / d / "NOT_ON_THIS_MACHINE.md").write_text(
                "# Folders not on this machine\n\n" + "\n".join(
                    f"- `{e['folder']}`: {'on the teammate' + chr(39) + 's machine (Anisha)' if e.get('location') == 'teammate' else 'MISSING'}; "
                    f"figures in {e['audit']}" for e in absent) + "\n", encoding="utf-8")

    # environment
    env = archive / "environment"
    env.mkdir(exist_ok=True)
    (env / "pip_freeze.txt").write_text(freeze(), encoding="utf-8")
    write_json(env / "archive_machine.json", archive_machine(cfg))
    run_rows = []
    for e in ents:
        md = run_metadata(archive / e["dest"]) if e["present"] else {}
        commit = md.get("commit")
        e["commit_text"] = (commit[:7] + ("*" if md.get("uncommitted_changes") else "")) if commit else NA
        infers = e["kind"] in ("bridge", "thud", "check")      # the other kinds run no model
        device = md.get("device") or (f"{NA} at runtime" if e["present"] and infers else "")
        run_rows.append({"folder": e["folder"], "archive_path": e["dest"] if e["present"] else "", "present": e["present"],
                         "task": e["task"], "role": e["role"], "kind": e["kind"], "session": e["session"],
                         "date": folder_date(e["folder"]), "machine": e["machine_short"],
                         "commit": commit or NA, "commit_source": md.get("commit_source") or "",
                         "uncommitted_changes": _cell(md.get("uncommitted_changes")), "platform": md.get("platform") or NA,
                         "python": md.get("python") or NA, "unity_version": md.get("unity_version") or "",
                         "torch": md.get("torch") or "", "device": device, "precision": md.get("precision") or "",
                         "device_source": md.get("device_source") or "", "device_evidence": md.get("device_evidence") or "",
                         "device_note": (e.get("device_note") or "") if infers else ""})
    write_csv(env / "runs.csv", run_rows)
    models = model_hashes(cfg, repo)
    write_csv(env / "models.csv", models)

    # frozen configs
    frozen = frozen_configs(cfg, repo, archive / "configs_frozen")

    # summaries
    frozen_copy = lambda rel: archive / "configs_frozen" / "robot_vision" / PurePosixPath(rel)   # noqa: E731
    metrics = ht.load_metrics_config(frozen_copy(cfg["metrics_config"]) if frozen_copy(cfg["metrics_config"]).exists()
                                     else _p(cfg["metrics_config"]))
    pairs = session_pairs(ents, archive)
    sessions = manifest["sessions"]
    hri_of = {e["session"]: archive / e["dest"] for e in ents if e["kind"] == "hri_trials" and e["present"]}
    regen, regen_equal = {}, []
    dev_rows = []
    for sid, (u, b) in sorted(pairs.items()):
        s = sessions[sid]
        if not any(u.glob("truth_run*.json")):
            continue
        runs, meta = ht.merge(u, b, metrics)
        if not runs:
            continue
        role, task = s["role"], s["task"].lower()
        out = archive / task / "summary" / (role if role in ("final", "replication") else f"development/{sid}")
        res = write_session_summary(runs, out, u.name, role in ("final", "replication"), hri_of.get(sid))
        regen[sid] = {"runs": runs, "analysis": res["analysis"], "unity": u.name, "bridge": b.name,
                      "goal_order_matches": meta["check"]["goal_order_matches"]}
        if "equal_to_original_hri_trials" in res:
            regen_equal.append((sid, res["equal_to_original_hri_trials"]))
        if role == "development":
            js = [j for r in runs for j in r["junctions"]]
            dev_rows.append({"session": sid, "task": s["task"], "unity_folder": u.name, "bridge_folder": b.name,
                             "audit": s["audit"], "date": folder_date(u.name), "trials_recorded": len(runs),
                             "successes": sum(r["outcome"] == "SUCCESS" for r in runs),
                             "reads_as_shown": f"{sum(j['shown'] == j['read'] for j in js)}/{len(js)}",
                             "read_at_first_ask": f"{sum(j.get('asks') == 1 for j in js)}/{len(js)}",
                             "collisions": sum(r["collisions"] for r in runs), "what": s["what"]})
    for task in ("task1", "task2"):
        rows = [r for r in dev_rows if r["task"].lower() == task]
        if rows:
            write_csv(archive / task / "summary" / "development" / "sessions.csv", rows)

    # forward hand sweep (Task 1 development)
    ctl = read_json(frozen_copy(cfg["control_config"])) or read_json(_p(cfg["control_config"]))
    for e in ents:
        if e["kind"] == "sweep" and e["present"] and e["session"] in pairs:
            sw, br = pairs[e["session"]]
            truth = ht.read_csv(sw / "truth_sweep.csv")
            if truth and "hand" in truth[0]:
                rows, rule = forward_hand_rows(sw, br, ctl["dialog"]["gesture_hold_s"])
                out = archive / e["task"].lower() / "summary" / "development"
                write_csv(out / "forward_hand_sweep.csv", rows)
                (out / "forward_hand_sweep.md").write_text(
                    f"# FORWARD hand sweep ({sw.name} + {br.name})\n\nRegenerated from the copied raw data. Rule (AUDIT.md "
                    f"section 9 item 15): finger FORWARD rate >= fist: {rule['finger_forward_rate_at_least_fist']}; finger "
                    f"never read STOP: {rule['finger_never_read_stop']}; decision: **{rule['decision']}**. Coverage = "
                    "frames with a command / all frames of that hand.\n", encoding="utf-8")

    # Task 2 original + three-run comparison
    audit_text = audit.read_text(encoding="utf-8")
    t2_rep = cfg.get("task2_original_reported", {})
    t2_sum = archive / "task2" / "summary"
    t2_sum.mkdir(parents=True, exist_ok=True)
    if "task2_final" in regen:
        orig = {"runs": regen["task2_final"]["runs"], "analysis": regen["task2_final"]["analysis"], "reported": None,
                "source": "regenerated from the copied raw data", "commit": sessions["task2_final"].get("commit", "ce37a56")}
    else:
        o_runs = task2_original_from_audit(audit_text)
        write_csv(t2_sum / "final" / "runs_reported_in_audit.csv",
                  [{"trial": r["trial"], "b_name": r["b"]["name"], "outcome": r["outcome"],
                    "final_distance_to_b_m": r["final_distance_to_b_m"], "total_s": r["total_s"],
                    "junctions_shown_vs_read": "; ".join(f"{j['junction']}:{j['shown']}>{j['read']}" for j in r["junctions"]),
                    "closest_human_m": r["closest_human_m"], "source": "AUDIT.md section 2 (raw folders on the teammate's machine)"}
                   for r in o_runs])
        orig = {"runs": o_runs, "analysis": None, "reported": t2_rep, "source": t2_rep.get("source", "AUDIT.md section 2"),
                "commit": t2_rep.get("commit", NA)}
    views = {}
    orig.update(title="Task 2 final (original)", short="Task 2 final\n(original, Mac)", task_text="Task 2: guided route, goal B seeded",
                machine=manifest["machines"]["anisha_mac"].split(":")[0], device="YOLO on MPS (AUDIT.md section 4 item 3; precision not recorded)",
                seed=2)
    views["task2_original_final"] = orig
    for key, sid, title, short, task_text in (
            ("task2_replication", "task2_replication", "Task 2 replication", "Task 2\nreplication (PC)", "Task 2: guided route, goal B seeded"),
            ("task1_final", "task1_final", "Task 1 final", "Task 1 final\n(PC)", "Task 1: straight A to E1, stops C1, J1, C3")):
        if sid not in regen:
            continue
        rr = regen[sid]
        bmeta = run_metadata(archive / next(e["dest"] for e in ents if e["session"] == sid and e["kind"] == "bridge"))
        views[key] = {"runs": rr["runs"], "analysis": rr["analysis"], "reported": None, "title": title, "short": short,
                      "task_text": task_text, "source": f"regenerated from the copied raw data ({rr['unity']}, {rr['bridge']})",
                      "machine": manifest["machines"][sessions[sid]["machine"]].split(":")[0],
                      "device": (bmeta.get("device") + (f" ({bmeta.get('precision')})" if bmeta.get("precision") else ""))
                      if bmeta.get("device") else (sessions[sid].get("device_note") or NA),
                      "commit": (bmeta.get("commit") or NA)[:7], "seed": sessions[sid]["seed"]}
    cmp_rows = comparison_rows(views, cfg)
    write_csv(t2_sum / "three_run_comparison.csv", cmp_rows)
    (t2_sum / "three_run_comparison.md").write_text(comparison_markdown(cmp_rows, views), encoding="utf-8")
    plot_three(views, t2_sum / "three_run_comparison.png")
    if "task2_replication" in views:
        plot_per_run([("original final (AUDIT.md section 2)" if orig["analysis"] is None else "original final", orig["runs"]),
                      ("replication", views["task2_replication"]["runs"])], t2_sum / "original_vs_replication_per_run.png")

    # originals unchanged?
    after = {n: stat_snapshot(p) for n, p in sources.items()}
    originals_unchanged = before == after

    # README inputs (the README is written before the checksums)
    teammate = [e for e in ents if not e["present"] and e.get("location") == "teammate"]
    t2_final_present = [e for e in ents if e["session"] == "task2_final" and e["present"]]
    glance = []
    for sid, label in (("task1_final", "Task 1 final"), ("task2_replication", "Task 2 replication")):
        if sid in regen:
            a = regen[sid]["analysis"]
            j = a["junctions"]
            glance.append(f"**{label}** ({regen[sid]['unity']}): {a['success']['k']}/{a['success']['n']} SUCCESS "
                          f"(Wilson 95 % {a['success']['wilson95'][0]}-{a['success']['wilson95'][1]}); {j['correct']}/{j['n']} "
                          f"junctions / stops read as shown (coverage {sum(sum(c.values()) - c.get('NONE', 0) for c in j['shown_vs_read'].values())}/{j['n']}); "
                          f"collisions {a['collisions']['total']}; regenerated from the copied raw data.")
    o_ok = sum(r["outcome"] == "SUCCESS" for r in orig["runs"])
    glance.insert(1 if glance else 0,
                  f"**Task 2 final (original)**: {o_ok}/{len(orig['runs'])} SUCCESS, {_reads(orig['runs'])[0]} junctions read as shown; "
                  f"source: {orig['source']}.")
    if t2_final_present:
        t2_text = "Anisha's original Task 2 final folders are present and copied into `task2/final/`."
    else:
        t2_text = ("Anisha's original Task 2 final folders (" + ", ".join(f"`{e['folder']}`" for e in ents if e["session"] == "task2_final")
                   + ") are on the teammate's machine, not on this one. Their numbers are in AUDIT.md section 2 (copied here); "
                     "`task2/summary/final/runs_reported_in_audit.csv` is that section's per-run table, and the three-run "
                     "comparison takes the original's figures from it (marked as such). They can be added by rebuilding the "
                     "archive with the folders under the output root.")
    excl_tbl = {r: (excluded[r], excl_bytes[r]) for r in excluded}
    frozen_bad = [r["path"] for r in frozen if r["matches"] is False]
    model_bad = [r["model"] for r in models if r["matches"] is False]
    listed = {e["folder"] for e in ents}
    not_archived = sorted(p.name for p in output_root.iterdir() if p.is_dir() and p.name not in listed) if output_root.exists() else []
    copied_files = {p.relative_to(archive).as_posix(): p for p in archive.rglob("*") if p.is_file()}
    copy_mismatch = [rel for rel, h in hashes.items() if sha256_file(copied_files[rel]) != h]
    info = {"built": now.strftime("%Y-%m-%d %H:%M:%S"), "git": git, "originals_unchanged": originals_unchanged,
            "glance": glance, "checks": checks, "n_listed": len(ents), "n_copied": sum(e["present"] for e in ents),
            "n_teammate": len(teammate), "n_missing": sum(1 for e in ents if not e["present"] and e.get("location") != "teammate"),
            "copy_verified": "yes, every file equals its source" if not copy_mismatch else f"NO: {len(copy_mismatch)} files differ",
            "n_files": len(hashes),
            "frozen_match": "all recorded hashes match" if not frozen_bad else f"MISMATCH: {frozen_bad}",
            "models_match": ("present weights match their recorded hashes" if not model_bad else f"MISMATCH: {model_bad}")
            + f" ({sum(r['present'] for r in models)}/{len(models)} present)",
            "regen_equal": "; ".join(f"{sid}: {'yes' if not d['columns_differing'] else 'differs in ' + ', '.join(d['columns_differing'])}"
                                     for sid, d in regen_equal) or "no original hri_trials folder to compare",
            "task2_final_text": t2_text, "entries": ents, "comparability": cfg["comparability"],
            "excluded": excl_tbl, "not_archived": not_archived}
    write_json(archive / "checks.json", {"manifest_problems": problems, "folders": checks,
                                         "copy": {"files": len(hashes), "mismatches": copy_mismatch, "excluded": excl_tbl},
                                         "originals_unchanged": originals_unchanged, "frozen_configs": frozen, "models": models,
                                         "regenerated_vs_original_hri_trials": dict(regen_equal),
                                         "goal_order_matches": {s: r["goal_order_matches"] for s, r in regen.items()}})
    (archive / "README.md").write_text(readme(info), encoding="utf-8")
    lines = [f"{sha256_file(p)}  {p.relative_to(archive).as_posix()}"
             for p in sorted(archive.rglob("*")) if p.is_file() and p.relative_to(archive).as_posix() != CHECKSUMS]
    (archive / CHECKSUMS).write_text("\n".join(lines) + "\n", encoding="utf-8")

    result = {"archive": archive, "zip": None, "zip_sha256": None, "checks": checks, "copy_mismatch": copy_mismatch,
              "originals_unchanged": originals_unchanged, "frozen_bad": frozen_bad, "model_bad": model_bad,
              "regen_equal": dict(regen_equal), "files": len(lines) + 1}
    if make_zip:
        nostore = {s.lower() for s in cfg.get("no_compress_suffixes", [])}
        with zipfile.ZipFile(zpath, "x", allowZip64=True) as z:
            for p in sorted(archive.rglob("*")):
                if p.is_file():
                    z.write(p, f"{name}/{p.relative_to(archive).as_posix()}",
                            compress_type=zipfile.ZIP_STORED if p.suffix.lower() in nostore else zipfile.ZIP_DEFLATED)
        zsha = sha256_file(zpath)
        (archive_root / f"{name}.zip.sha256").write_text(f"{zsha}  {name}.zip\n", encoding="utf-8")
        result.update(zip=zpath, zip_sha256=zsha)
    if repo_summary is not None:
        copy_repo_summary(archive, repo_summary, cfg, name, result["zip_sha256"], git)
    return result


def copy_repo_summary(archive: Path, dest: Path, cfg: dict, name: str, zip_sha: str | None, git: dict) -> list[str]:
    """Only summary tables and plots (.csv, .md, .png) of task*/summary/ go into the repository."""
    keep = {s.lower() for s in cfg.get("repo_summary_suffixes", [".csv", ".md", ".png"])}
    if dest.exists():
        shutil.rmtree(dest)
    copied = []
    for task in ("task1", "task2"):
        src = archive / task / "summary"
        for p in sorted(src.rglob("*")) if src.exists() else []:
            if p.is_file() and p.suffix.lower() in keep:
                rel = p.relative_to(src)
                out = dest / task / rel
                out.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(p, out)
                copied.append(f"{task}/{rel.as_posix()}")
    (dest / "README.md").write_text(
        "# Results summary (tables and plots)\n\n"
        f"Copied from the results archive `{name}` (built at commit `{git.get('commit')}` by "
        "`robot_vision/make_results_archive.py`). The tables and plots were regenerated there from copies of the raw "
        "run folders; the full archive (run folders, environment, frozen configs, checksums) is kept outside the "
        f"repository{f' as `{name}.zip`, SHA-256 `{zip_sha}`' if zip_sha else ''}.\n\n"
        "- `task1/final/`, `task2/replication/`: per-run table (`runs.csv`), junctions / stops (`junctions.csv`), "
        "`analysis.md`, `running_success.png`, `step_times.png`, check against the original hri_trials folder.\n"
        "- `task1/development/`: one folder per development session, `sessions.csv`, the FORWARD hand sweep.\n"
        "- `task2/final/runs_reported_in_audit.csv`: the original Task 2 final per-run table from AUDIT.md section 2 "
        "(its raw folders are on the teammate's machine).\n"
        "- `task2/three_run_comparison.*`: original Task 2 final, Task 2 replication and Task 1 final side by side, "
        "with what is comparable across machines; `original_vs_replication_per_run.png`.\n", encoding="utf-8")
    return copied


def verify(archive: Path) -> list[str]:
    problems, listed = [], set()
    for ln in (archive / CHECKSUMS).read_text(encoding="utf-8").splitlines():
        if not ln.strip():
            continue
        h, rel = ln.split("  ", 1)
        listed.add(rel)
        p = archive / rel
        if not p.exists():
            problems.append(f"missing: {rel}")
        elif sha256_file(p) != h:
            problems.append(f"changed: {rel}")
    for p in archive.rglob("*"):
        rel = p.relative_to(archive).as_posix()
        if p.is_file() and rel != CHECKSUMS and rel not in listed:
            problems.append(f"not in {CHECKSUMS}: {rel}")
    zs = archive.parent / f"{archive.name}.zip.sha256"
    if zs.exists():
        h, zname = zs.read_text(encoding="utf-8").split()
        if sha256_file(archive.parent / zname) != h:
            problems.append(f"zip hash differs: {zname}")
    return problems


def main(argv=None) -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--config", default=DEFAULT_CONFIG)
    ap.add_argument("--archive-root", help="overrides archive_root in the config (must be outside the repository)")
    ap.add_argument("--no-zip", action="store_true")
    ap.add_argument("--no-repo-summary", action="store_true", help="do not copy the summary into <repo>/results/summary")
    ap.add_argument("--replace-repo-summary", action="store_true", help="replace an existing <repo>/results/summary")
    ap.add_argument("--verify", metavar="ARCHIVE", help="check an archive folder against its CHECKSUMS.sha256 and zip hash")
    a = ap.parse_args(argv)
    if a.verify:
        problems = verify(Path(a.verify))
        print("\n".join(problems) if problems else "OK: every file matches CHECKSUMS.sha256 (and the zip its .sha256)")
        raise SystemExit(1 if problems else 0)
    cfg = load_config(a.config)
    repo = _p(cfg["repo_root"])
    res = build(cfg, archive_root=Path(a.archive_root) if a.archive_root else _p(cfg["archive_root"]),
                output_root=_p(cfg["output_root"]), repo=repo, audit=_p(cfg["audit"]), now=datetime.now(),
                make_zip=not a.no_zip, repo_summary=None if a.no_repo_summary else _p(cfg["repo_summary_dir"]),
                replace_repo_summary=a.replace_repo_summary)
    issues = [c for c in res["checks"] if c["status"] not in ("ok", "not_on_this_machine")]
    away = [c["folder"] for c in res["checks"] if c["status"] == "not_on_this_machine"]
    print(f"Archive: {res['archive'].resolve()}")
    if res["zip"]:
        print(f"Zip:     {res['zip'].resolve()}\nSHA-256: {res['zip_sha256']}")
    print(f"Files in the archive: {res['files']}; originals unchanged: {res['originals_unchanged']}; "
          f"copy mismatches: {len(res['copy_mismatch'])}; frozen hash mismatches: {res['frozen_bad'] or 0}; "
          f"model hash mismatches: {res['model_bad'] or 0}")
    print(f"Regenerated vs original hri_trials (columns differing): {res['regen_equal']}")
    print(f"Not on this machine (teammate): {len(away)} folders: {', '.join(away)}")
    print("Problems: " + ("none" if not issues else "\n  " + "\n  ".join(f"{c['folder']}: {c['check']} {c['status']} {c['detail']}" for c in issues)))


if __name__ == "__main__":
    main()
