"""Phase B runbook (AUDIT.md 16.33): what happens when a final sitting's zip arrives, in order, in one command. REPORTING / EVALUATION CODE;
inference code never imports it.

  python process_final_zip_v4.py <zip> --sha256 <hash>                 a final sitting (final_zip_v4.py sitting ...)
  python process_final_zip_v4.py <zip> --sha256 <hash> --development   a dry run on development data (the step-5 zip): steps 3 and 6 are SKIPPED

Steps (it stops at the first failure with the reason, writes its report either way, and never re-evaluates a setting):
  1  verify      the zip's SHA-256 against the one given (and its .sha256 file), zipfile.testzip, every member against MANIFEST.json; read in place
  2  accept      for ALL settings first: only the settings' folders are copied out of the zip (member by member, hash checked, no path outside the
                 destination, no code, nothing run), then the seven acceptance_criteria of final_plan.json and the interruption / resume rule of 16.30.1
  3  evaluate    hri_eval_final_v4.evaluate_final per setting, once (FINAL_DONE.json)                                   [final only]
  4  export      export_csv_v4.export_final per setting (FINAL_EXPORT_DONE.json), then the combined table over every final export in the
                 root: Wilson per setting, Newcombe per pair (B detection ON against OFF among them). Development: development export folders
                 and a development combined table, no marker
  5  tables      per-setting summary tables (phase_b_tables.csv / .md) and the paper figures (paper_v4/figures_v4.py, development data only)
  6  manifest    the entries in configs/v4/archive/results_manifest.json                                              [final only]
Configuration: configs/v4/experiments/phase_b.json (paths relative to robot_vision/; not frozen). A final copies the sitting's folders into final_root (outputs, the store
every tool and the run-once markers use); --development copies them to a NEW folder under development_root (outside the repository) and writes no
FINAL marker anywhere (checked at the end).
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import os
import re
import statistics
import subprocess
import sys
import zipfile
from datetime import datetime
from pathlib import Path

import data_splits_v4 as ds
import decision_io as dio
import export_csv_v4 as ex
import final_guard_v4 as fg
import final_zip_v4 as fzip
import freeze_v4 as fz
import gesture_data as gd
import gt_path
import hri_eval_dev_v4 as ev

HERE = Path(__file__).resolve().parent
DEFAULT_CONFIG = HERE / "configs" / "v4" / "experiments" / "phase_b.json"
FINAL_MARKER_FILES = ("FINAL_DONE.json", "FINAL_EXPORT_DONE.json", "FINAL_RUN_DONE.json", "FINAL_INTERRUPTION.json", "FINAL_RESUME.json", "FINAL_INVALID.json")
PASS, FAIL, NOT_EVALUATED, SKIPPED, OK = "pass", "fail", "not_evaluated", "skipped", "ok"


class StepFailed(Exception):
    """A step failed: the runbook stops here and says why."""


def load_config(path: str | Path | None = None) -> dict:
    p = Path(path) if path else DEFAULT_CONFIG
    return json.loads(p.read_text(encoding="utf-8"))


def _root(rel: str) -> Path:
    p = Path(rel)
    return (p if p.is_absolute() else HERE / p).resolve()


class Report:
    """The steps of one run with their status and detail, written to a NEW folder (report.json, report.md) also when a step fails."""

    def __init__(self, zip_path: Path, development: bool, title: str = "process_final_zip_v4", unit: str = "Settings"):
        self.title, self.unit = title, unit
        self.steps: list[dict] = []
        self.zip, self.development = str(zip_path), development
        self.settings: list[str] = []
        self.started = datetime.now().isoformat(timespec="seconds")
        self.extra: dict = {}

    def add(self, step: int, name: str, status: str, detail: str = "", **data) -> dict:
        rec = {"step": step, "name": name, "status": status, "detail": detail, **data}
        self.steps.append(rec)
        print(f"[{step}] {name}: {status}" + (f" - {detail}" if detail else ""), flush=True)
        return rec

    def write(self, folder: Path, failed: str | None) -> None:
        body = {"zip": Path(self.zip).name, "development": self.development, "settings": self.settings, "started": self.started,
                "failed": failed, "steps": self.steps, **self.extra}
        dio.write_json(folder / "report.json", body)
        L = [f"# {self.title}: {Path(self.zip).name}" + (" (DEVELOPMENT dry run: not a result)" if self.development else ""), "",
             f"{self.unit}: {', '.join(self.settings) or '-'}. " + (f"**FAILED: {failed}**" if failed else "All steps that ran are ok."), "",
             "| step | name | status | detail |", "|---|---|---|---|"]
        L += [f"| {s['step']} | {s['name']} | {s['status']} | {str(s['detail']).replace('|', '/')} |" for s in self.steps]
        (folder / "report.md").write_text("\n".join(L) + "\n", encoding="utf-8")


# ---------------------------------------------------------------- step 1: verify and read the manifest

def normalise_manifest(meta: dict, development: bool, prefix: str) -> list[dict]:
    """One entry per setting: {label (the folder prefix inside the zip), setting, unity [..], bridge [..], markers [..], launcher [..]}. A final
    sitting manifest has "settings"; the step-5 manifest of step5_zip_v4.py has "sessions" (development only)."""
    if "settings" in meta and "sitting" in meta:
        if development:
            raise StepFailed("--development was given, but this is a final sitting zip: development runs use the development splits and refuse test data")
        return [{"label": s["setting"], "setting": s["setting"], "unity": list(s["unity"]), "bridge": list(s["bridge"]),
                 "markers": list(s.get("marker_folders", [])), "launcher": list(s.get("launcher_files", [])), "invalid": list(s.get("invalid", []))}
                for s in meta["settings"]]
    if "sessions" in meta:
        if not development:
            raise StepFailed("this zip is a development zip (its manifest says: " + str(meta.get("what", "step 5 sessions")) + "): a final needs a final "
                             "sitting zip made by final_zip_v4.py; use --development for a dry run")
        out = []
        for s in meta["sessions"]:
            label = s["setting"]
            if prefix and not label.startswith(prefix):
                continue
            setting = label[len(prefix):] if prefix else label
            out.append({"label": label, "setting": setting, "unity": [s["unity"]], "bridge": [s["bridge"]], "markers": [], "invalid": [],
                        "launcher": list(s.get("launcher_files", []))})
        return out
    raise StepFailed("MANIFEST.json has neither 'settings' (final sitting) nor 'sessions' (step 5): not a zip this runbook knows")


def verify_zip_hash(zpath: Path, expected_sha: str) -> tuple[str, list[str], dict]:
    """Step 1 for any zip of the tools: the SHA-256 given, the .sha256 file next to it, testzip and every member against MANIFEST.json, all read in
    place. Returns (the SHA-256, warnings, the manifest). StepFailed with the reason otherwise."""
    expected = (expected_sha or "").strip().lower()
    if not re.fullmatch(r"[0-9a-f]{64}", expected):
        raise StepFailed(f"--sha256 {expected_sha!r} is not a SHA-256 (64 hex digits)")
    if not zpath.is_file():
        raise StepFailed(f"{zpath}: not found")
    got = fzip.s5z.sha256(zpath)
    if got != expected:
        raise StepFailed(f"SHA-256 of {zpath.name} is {got}, not the {expected} that was given: not processed")
    side = zpath.parent / (zpath.name + ".sha256")
    warnings = []
    if side.is_file():
        if side.read_text(encoding="utf-8").split()[0].lower() != expected:
            raise StepFailed(f"{side.name} differs from the SHA-256 that was given")
    else:
        warnings.append(f"{side.name} not found next to the zip (only the given hash was checked)")
    problems = [p for p in fzip.verify_zip(zpath) if not p.endswith(".sha256: not found")]
    if problems:
        raise StepFailed("the zip does not agree with its MANIFEST.json: " + "; ".join(problems[:5]))
    with zipfile.ZipFile(zpath) as z:
        meta = json.loads(z.read("MANIFEST.json").decode("utf-8-sig"))
    return got, warnings, meta


def step_verify(zpath: Path, expected_sha: str, development: bool, prefix: str, report: Report) -> tuple[dict, list[dict]]:
    got, warnings, meta = verify_zip_hash(zpath, expected_sha)
    entries = normalise_manifest(meta, development, prefix)
    if not entries:
        raise StepFailed("the manifest names no setting" + (f" with the prefix {prefix!r}" if development else ""))
    names = [e["setting"] for e in entries]
    if len(set(names)) != len(names):
        raise StepFailed(f"a setting appears twice in the zip: {sorted(n for n in set(names) if names.count(n) > 1)}")
    for n in names:
        fg.check_name(n)
    report.settings = names
    report.add(1, "verify", OK, f"SHA-256 {got[:12]}... matches; testzip and MANIFEST.json agree; settings {', '.join(names)}"
               + (f"; warning: {'; '.join(warnings)}" if warnings else ""), sha256=got, warnings=warnings, git_commit=meta.get("git_commit"))
    return meta, entries


# ---------------------------------------------------------------- run-once preflight and the copy out of the zip

def preflight_final(entries: list[dict], roots: list[Path], repo: Path, check_destination: bool = True) -> None:
    """Nothing is written before every setting is known not to have been evaluated, exported or declared invalid (in the final root and in the
    default outputs, where the manual tools write), and no destination folder exists."""
    for e in entries:
        s = e["setting"]
        if e["invalid"]:
            raise StepFailed(f"{s}: the zip carries a FINAL_INVALID marker ({', '.join(e['invalid'])}): the setting is reported as invalid and not evaluated")
        for root in roots:
            for kind, what in (("evaluation", "evaluated"), ("export", "exported"), ("invalid", "declared invalid")):
                found = fg.markers(root, s, kind)
                if found:
                    raise StepFailed(f"{s}: already {what} ({found[0].parent.name} in {root}): finals are run once, nothing is repeated")
    for e in entries if check_destination else []:
        for folder in e["unity"] + e["bridge"] + e["markers"]:
            if (roots[0] / folder).exists():
                raise StepFailed(f"{e['setting']}: {roots[0] / folder} exists already: nothing is overwritten (a second zip of the same sitting is refused)")


def _safe_rel(rel: str) -> bool:
    p = Path(rel)
    return bool(rel) and not p.is_absolute() and ".." not in p.parts and ":" not in rel and "\\" not in rel and not rel.startswith("/")


def copy_out(zpath: Path, meta: dict, entries: list[dict], dest: Path, reuse: bool = False) -> list[str]:
    """Copy the folders of every setting out of the zip into dest, member by member: only members listed in MANIFEST.json, each file's SHA-256
    checked as it is written, never a name that leaves dest, never code (.py, .ps1, .sh, .exe, .dll). A folder is built under a temporary name
    and renamed only when complete (a failure removes the temporary one and leaves dest as it was). Returns the folder names."""
    import shutil
    listed = {f["name"]: f for f in meta["files"]}
    done, dest = [], Path(dest)
    dest.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(zpath) as z:
        for e in entries:
            for folder in e["unity"] + e["bridge"] + e["markers"]:
                if not _safe_rel(folder):
                    raise StepFailed(f"{e['setting']}: the folder name {folder!r} is not a plain name")
                prefix = f"{e['label']}/{folder}/"
                members = [n for n in listed if n.startswith(prefix)]
                if not members:
                    raise StepFailed(f"{e['setting']}: the zip lists no file of {folder}")
                if reuse and (dest / folder).is_dir():       # an earlier copy of THIS zip (a run that stopped part-way): every file must be the zip's, byte for byte
                    for name in members:
                        f = dest / folder / name[len(prefix):]
                        if Path(name[len(prefix):]).suffix.lower() in (".py", ".ps1", ".sh", ".exe", ".dll", ".bat", ".cmd"):
                            continue
                        if not f.is_file() or hashlib.sha256(f.read_bytes()).hexdigest() != listed[name]["sha256"]:
                            raise StepFailed(f"{e['setting']}: {dest / folder} exists but {name[len(prefix):]} differs from the zip: not reused")
                    done.append(folder)
                    continue
                if (dest / folder).exists():
                    raise StepFailed(f"{e['setting']}: {dest / folder} exists already: nothing is overwritten")
                tmp = dest / f".ingest_{folder}"
                if tmp.exists():
                    raise StepFailed(f"{tmp} exists: a previous copy was interrupted; remove it by hand")
                try:
                    for name in members:
                        rel = name[len(prefix):]
                        if not _safe_rel(rel) or Path(rel).suffix.lower() in (".py", ".ps1", ".sh", ".exe", ".dll", ".bat", ".cmd"):
                            if Path(rel).suffix.lower() in (".py", ".ps1", ".sh", ".exe", ".dll", ".bat", ".cmd"):
                                continue                                                      # code inside a data folder is never copied out
                            raise StepFailed(f"{name}: not a plain relative name")
                        target = (tmp / rel)
                        if not str(target.resolve()).startswith(str(tmp.resolve())):
                            raise StepFailed(f"{name}: would leave the destination")
                        target.parent.mkdir(parents=True, exist_ok=True)
                        h = hashlib.sha256()
                        with z.open(name) as src, target.open("xb") as out:
                            for chunk in iter(lambda: src.read(1 << 20), b""):
                                h.update(chunk)
                                out.write(chunk)
                        if h.hexdigest() != listed[name]["sha256"]:
                            raise StepFailed(f"{name}: SHA-256 differs from MANIFEST.json after the copy")
                    os.rename(tmp, dest / folder)
                except BaseException:
                    if tmp.exists():
                        shutil.rmtree(tmp)
                    raise
                done.append(folder)
    return done


# ---------------------------------------------------------------- step 2: the acceptance criteria

def _crit(n: int, name: str, status: str, detail: str) -> dict:
    return {"id": n, "name": name, "status": status, "detail": detail}


def _runs_in(unity: Path) -> list[Path]:
    return sorted(unity.glob("run_[0-9][0-9][0-9]"))


def _numbers(names, pattern) -> list[int]:
    return sorted(int(m.group(1)) for n in names if (m := re.match(pattern, n)))


def pair_parts(setting: str, root: Path, entry: dict) -> list[tuple[Path, Path]]:
    """(unity, bridge) per part. One part: the one pair. Two parts (a declared and resumed interruption): the declaration names part 1."""
    u, b = entry["unity"], entry["bridge"]
    if len(u) == 1 and len(b) == 1:
        return [(root / u[0], root / b[0])]
    decl = fg.markers(root, setting, "interruption")
    if len(u) == 2 and len(b) == 2 and len(decl) == 1:
        d = json.loads(decl[0].read_text(encoding="utf-8"))
        if d["unity_folder"] in u and d["bridge_folder"] in b:
            p1 = (root / d["unity_folder"], root / d["bridge_folder"])
            p2 = (root / next(x for x in u if x != d["unity_folder"]), root / next(x for x in b if x != d["bridge_folder"]))
            return [p1, p2]
    raise StepFailed(f"{setting}: {len(u)} Unity and {len(b)} bridge folders cannot be paired (one part, or two parts with a declared interruption)")


def acceptance(setting: str, parts: list[tuple[Path, Path]], root: Path, repo: Path, development: bool, dev_runs: int, zpath: Path,
               entry: dict, extra_names: list[str]) -> list[dict]:
    """The seven acceptance_criteria of final_plan.json plus the interruption / resume rule (criterion 8), as pass / fail / not_evaluated with the reason.
    Read-only on the copied folders (gt_path.session_leak_check writes leak_test.json when absent, as it always does)."""
    plan = fg.plan(repo)
    n_runs = dev_runs if development else int(plan["runs_per_setting"])
    gcfg = gd.load_config(repo / "robot_vision/configs/v4/gesture_data.json")
    gt_cfg = gt_path.load_config(repo / "robot_vision/configs/v4/gt_eval.json")
    splits = ds.load(repo / "robot_vision/configs/v4/data_splits.json")
    out: list[dict] = []
    pairs = list(parts)
    resumed = len(pairs) == 2
    k = None
    rp = fg.resume_plan(root, setting, pairs, repo) if not development else {"problems": [], "resumed": False, "declaration": None}
    if rp.get("declaration"):
        k = int(rp["declaration"]["resume_from_run"])

    def expected(i: int) -> tuple[list[int], list[int]]:
        """(required, allowed extra) run numbers of part i."""
        if not resumed or k is None:
            return list(range(1, n_runs + 1)), []
        return (list(range(1, k)), [k]) if i == 0 else (list(range(k, n_runs + 1)), [])

    # 1 leak test
    bad = []
    for u, _ in pairs:
        s = json.loads((u / "session.json").read_text(encoding="utf-8")) if (u / "session.json").is_file() else {}
        unity_ok = (s.get("leak_test") or {}).get("passed") is True
        try:
            leak = gt_path.session_leak_check(u, gt_cfg)
        except (SystemExit, ValueError, OSError) as e:
            leak = {"passed": False, "reasons": [str(e)]}
        if not (unity_ok and leak["passed"]):
            bad.append(f"{u.name}: Unity {unity_ok}, Python {leak['passed']}" + (f" ({'; '.join(leak['reasons'])})" if not leak["passed"] else ""))
    out.append(_crit(1, "leak test", FAIL if bad else PASS, "; ".join(bad) or "passed in Unity (session.json) and in Python (gt_path.session_leak_check)"))

    # 2 frozen hashes
    if development:
        out.append(_crit(2, "frozen hashes", NOT_EVALUATED, "development: nothing is frozen"))
    else:
        try:
            fz.require_frozen(repo)
            now = fz.sha256_lf(repo / fz.FROZEN_REL)
            shas = {b.name: (json.loads((b / "FINAL_SETTING.json").read_text(encoding="utf-8")).get("frozen_sha256") if (b / "FINAL_SETTING.json").is_file() else None)
                    for _, b in pairs}
            wrong = {k_: v for k_, v in shas.items() if v != now}
            out.append(_crit(2, "frozen hashes", FAIL if wrong else PASS,
                             f"the bridge folders {sorted(wrong)} do not record the current frozen.json hash" if wrong else "require_frozen passes and every bridge folder recorded the current frozen.json hash"))
        except SystemExit as e:
            out.append(_crit(2, "frozen hashes", FAIL, str(e)))

    # 3 split guard
    bad, n_checked = [], 0
    for u, _ in pairs:
        for r in _runs_in(u):
            if resumed and k is not None and r.name == f"run_{k:03d}" and u == pairs[0][0]:
                continue                                                                  # the interrupted attempt is listed, not scored
            n_checked += 1
            try:
                t = gd.load_truth(r / "truth.jsonl", gcfg)
                ds.guard_run({x.look for x in t}, {c.clip for c in gd.build_clips(t)}, final_evaluation=not development, splits=splits)
            except (SystemExit, ValueError, OSError) as e:
                bad.append(f"{u.name}/{r.name}: {e}")
    out.append(_crit(3, "split guard", FAIL if bad or not n_checked else PASS,
                     "; ".join(bad[:4]) if bad else (f"{n_checked} runs, every run wholly in the {'development' if development else 'test'} split" if n_checked else "no run folder")))

    # 4 all runs present
    bad = []
    for i, (u, b) in enumerate(pairs):
        need, allow = expected(i)
        rows = []
        if (u / "results_unity.csv").is_file():
            with (u / "results_unity.csv").open(encoding="utf-8", newline="") as f:
                rows = sorted(int(r["trial"]) for r in csv.DictReader(f))
        dirs = _numbers([d.name for d in _runs_in(u)], r"^run_(\d{3})$")
        py = _numbers([p.name for p in b.glob("python_trial_*.json")], r"^python_trial_(\d{3})\.json$")
        for what, got in (("results_unity.csv", rows), ("run_###", dirs), ("python_trial_###", py)):
            extra = [x for x in got if x not in need]
            if sorted(set(got) - set(allow)) != need or any(x not in need + allow for x in extra):
                bad.append(f"{u.name}: {what} {got}, expected {need[0]}..{need[-1]}" if need else f"{u.name}: {what} {got}")
    out.append(_crit(4, "all runs present", FAIL if bad else PASS, "; ".join(bad) or "results_unity.csv, run_### and python_trial_### are exactly the expected runs"
                     + (f" (resumed: part 1 runs 1..{k - 1}, part 2 runs {k}..{n_runs})" if resumed and k else f" (1..{n_runs})")))

    # 5 outcomes recorded
    bad = []
    for i, (u, b) in enumerate(pairs):
        last = i == len(pairs) - 1
        need = [("summary_unity.json", u), ("summary.json", b)] if (last or development) else []
        if not development and last:
            need += [("UNITY_FINAL_DONE.json", u), ("FINAL_RUN_DONE.json", b)]
        bad += [f"{d.name}/{name} missing" for name, d in need if not (d / name).is_file()]
    out.append(_crit(5, "every outcome recorded", FAIL if bad else PASS, "; ".join(bad) or "summary files" + ("" if development else " and the Unity and Python final markers") + " present"))

    # 6 truth and run files accepted
    bad, n_checked = [], 0
    for u, _ in pairs:
        for r in _runs_in(u):
            if resumed and k is not None and r.name == f"run_{k:03d}" and u == pairs[0][0]:
                continue
            n_checked += 1
            try:
                gd.load_truth(r / "truth.jsonl", gcfg)
            except (SystemExit, ValueError, OSError) as e:
                bad.append(f"{u.name}/{r.name} truth: {e}")
                continue
            if gt_path.has_v4_files(r):
                try:
                    gt_path.evaluate_run(r)
                except (SystemExit, ValueError, OSError, KeyError) as e:
                    bad.append(f"{u.name}/{r.name} run files: {e}")
    out.append(_crit(6, "truth and run files accepted", FAIL if bad or not n_checked else PASS, "; ".join(bad[:4]) or (f"{n_checked} runs accepted" if n_checked else "no run folder")))

    # 7 run protocol recorded
    bad, notes = [], []
    for _, b in pairs:
        info = json.loads((b / "run_info.json").read_text(encoding="utf-8")) if (b / "run_info.json").is_file() else None
        if not info or not [k_ for k_ in info if "machine" in k_]:
            bad.append(f"{b.name}/run_info.json has no machine state")
        if not (b / "resources.csv").is_file():
            bad.append(f"{b.name}/resources.csv missing")
    with zipfile.ZipFile(zpath) as z:
        for name in entry["launcher"]:
            if name.startswith("run_protocol"):
                text = z.read(f"{entry['label']}/launcher/{name}").decode("utf-8-sig", errors="replace")
                if re.search(r"free memory", text, re.I):
                    notes.append(name)
    if not notes:
        bad.append("no run-protocol note with 'free memory' in the zip's launcher files")
    power = [n for n in extra_names if "power" in n.lower()]
    warn = "" if power else " WARNING: no file named like a power-mode note in extra/ (docs/handoff_freeze_v4.md section 1)"
    out.append(_crit(7, "run protocol recorded", FAIL if bad else PASS, ("; ".join(bad) or f"run_info.json machine state, resources.csv and the note {notes[0]}") + warn))

    # 8 interruption / resume (16.30.1)
    if development:
        out.append(_crit(8, "interruption / resume", NOT_EVALUATED, "development: no declaration or marker exists"))
    else:
        probs = list(rp["problems"])
        decl = fg.markers(root, setting, "interruption")
        if decl and not resumed:
            probs.append("an interruption is declared but the zip holds one part only")
        if resumed and not decl:
            probs.append("two parts without a declared interruption")
        out.append(_crit(8, "interruption / resume", FAIL if probs else PASS,
                         "; ".join(probs) or (f"declared and resumed once from run {k}: same seed, goal order, frozen hashes, start_run == resume_from_run" if resumed else "none declared")))
    return out


def step_accept(zpath: Path, meta: dict, entries: list[dict], root: Path, repo: Path, development: bool, dev_runs: int, report: Report, reuse: bool = False) -> dict:
    with zipfile.ZipFile(zpath) as z:
        extra_names = [n for n in z.namelist() if n.startswith("extra/")]
    copied = copy_out(zpath, meta, entries, root, reuse)
    report.add(2, "copy out", OK, f"{len(copied)} folders copied to {root} (hash checked; no code, nothing run)", folders=copied)
    pairs_by_setting, failed = {}, []
    for e in entries:
        parts = pair_parts(e["setting"], root, e)
        pairs_by_setting[e["setting"]] = parts
        crits = acceptance(e["setting"], parts, root, repo, development, dev_runs, zpath, e, extra_names)
        bad = [c for c in crits if c["status"] == FAIL]
        report.add(2, f"accept {e['setting']}", FAIL if bad else OK, "; ".join(f"criterion {c['id']} {c['name']}: {c['detail']}" for c in bad)
                   or "; ".join(f"{c['id']} {c['status']}" for c in crits), criteria=crits)
        if bad:
            failed.append(e["setting"])
    if failed:
        raise StepFailed(f"acceptance failed for {', '.join(failed)}: those settings are reported as invalid with the reasons above, never rerun and not evaluated; "
                         "nothing was evaluated or exported")
    return pairs_by_setting


# ---------------------------------------------------------------- steps 3 and 4

def step_evaluate(pairs_by_setting: dict, root: Path, repo: Path, report: Report) -> dict:
    import hri_eval_final_v4 as ef
    out = {}
    for s, pairs in pairs_by_setting.items():
        try:
            folder, _ = ef.evaluate_final(s, pairs, repo, root)
        except SystemExit as e:
            raise StepFailed(f"{s}: the final evaluation refused: {e}") from None
        out[s] = folder
        report.add(3, f"evaluate {s}", OK, f"{folder.name} (FINAL_DONE.json written: {s} cannot be evaluated again)", folder=folder.name)
    return out


def step_export_final(pairs_by_setting: dict, root: Path, repo: Path, report: Report) -> dict:
    out = {}
    for s, pairs in pairs_by_setting.items():
        try:
            folder, rows, _ = ex.export_final(s, pairs, repo, root)
        except SystemExit as e:
            raise StepFailed(f"{s}: the final export refused: {e}") from None
        out[s] = folder
        report.add(4, f"export {s}", OK, f"{folder.name}: {len(rows)} runs (FINAL_EXPORT_DONE.json written)", folder=folder.name)
    exports = [m.parent for s in fg.settings(repo) for m in fg.markers(root, s, "export")]
    try:
        comb, res = ex.combine(exports, repo, root)
    except SystemExit as e:
        raise StepFailed(f"the combined table refused: {e}") from None
    report.add(4, "combined table", OK, f"{comb.name}: {len(res['settings'])} settings exported so far, {len(res['comparisons'])} comparisons", folder=comb.name)
    report.extra["comparisons"] = res["comparisons"]
    return out


def step_export_development(pairs_by_setting: dict, root: Path, repo: Path, report: Report) -> dict:
    """Development exports: runs.csv, dialogs.csv, summary.json per setting in a NEW folder, no marker; and a development combined table."""
    cfg = ex.load_config()
    ex.check_columns(cfg)
    gcfg = gd.load_config(repo / "robot_vision/configs/v4/gesture_data.json")
    ecfg = ev.load_config(repo / "robot_vision/configs/v4/eval_dev.json")
    splits = ds.load(repo / "robot_vision/configs/v4/data_splits.json")
    z = ex.wilson_z(repo)
    plan = fg.plan(repo)
    out, per = {}, {}
    for s, pairs in pairs_by_setting.items():
        runs = ev.load_sessions(pairs, gcfg, splits, settings=[s] * len(pairs))
        rows, dialogs = ex.build_tables(runs, ecfg, splits)
        sm = ex.summarize(rows, z)
        folder = dio.new_run_dir({"paths": {"output_root": str(root)}}, f"export_csv_v4_development_{s}")
        ex.write_csv(folder / "runs.csv", rows, cfg["runs"], cfg.get("empty", ""))
        ex.write_csv(folder / "dialogs.csv", dialogs, cfg["dialogs"], cfg.get("empty", ""))
        dio.write_json(folder / "summary.json", {"setting": s, "development": True, "summary": sm, "plan_entry": plan["settings"][s]})
        (folder / "DEVELOPMENT.txt").write_text("Development dry run of process_final_zip_v4.py: not a result, no final marker.\n", encoding="utf-8")
        out[s] = folder
        per[s] = {"folder": folder.name, "setting": s, "summary": sm}
        report.add(4, f"export {s} (development)", OK, f"{folder.name}: {len(rows)} runs, {len(dialogs)} asks", folder=folder.name)
    res, crows, comp = ex.combined_tables(per, plan, z)
    comb = dio.new_run_dir({"paths": {"output_root": str(root)}}, "export_csv_v4_development_combined")
    ex.write_combined(comb, per, plan, res, crows, comp, "# DEVELOPMENT dry run (not a result): combined table of the development sessions", list(out.values()))
    report.add(4, "combined table (development)", OK, f"{comb.name}: {len(res['settings'])} settings, {len(res['comparisons'])} comparisons", folder=comb.name)
    report.extra["comparisons"] = res["comparisons"]
    return out


# ---------------------------------------------------------------- step 5: tables and figures

def _floats(rows: list[dict], key: str) -> list[float]:
    out = []
    for r in rows:
        v = r.get(key, "")
        if v not in ("", None):
            try:
                out.append(float(v))
            except ValueError:
                pass
    return out


def setting_table_row(setting: str, export_folder: Path, bridges: list[Path]) -> dict:
    """One row of the per-setting table from the export folder (runs.csv, summary.json) and the bridge summary.json of each part."""
    sj = json.loads((export_folder / "summary.json").read_text(encoding="utf-8"))
    sm = sj["summary"]
    with (export_folder / "runs.csv").open(encoding="utf-8", newline="") as f:
        rows = list(csv.DictReader(f))
    st, sf = _floats(rows, "stop_gestures_true"), _floats(rows, "stop_gestures_false")
    close = _floats(rows, "closest_person_m")
    ls = sm["lies"]
    rt, lag, wd = [], [], []
    for b in bridges:
        p = b / "summary.json"
        if p.is_file():
            bs = json.loads(p.read_text(encoding="utf-8"))
            rt.append((bs.get("round_trip") or {}).get("max_ms"))
            lag.append((bs.get("event_loop_lag") or {}).get("max_lag_ms"))
            wd.append((bs.get("watchdog") or {}).get("stops_reported_by_unity"))
    num = lambda xs: [x for x in xs if isinstance(x, (int, float))]  # noqa: E731
    return {"setting": setting, "runs": sm["runs"], "success_k": sm["success"]["k"], "success_n": sm["success"]["n"],
            "success_wilson95": sm["success"]["wilson95"] if isinstance(sm["success"]["wilson95"], list) else "not evaluated",
            **{f"failed_{k}": v for k, v in sm["failure_kinds"].items()},
            "lies_given": ls["given"], "lies_detected": ls["detected"]["total"], "lies_corrected": ls["corrected"]["total"], "lies_fooled": ls["fooled"]["total"],
            "stop_gestures_true": int(sum(st)) if st else "not evaluated", "stop_gestures_false": int(sum(sf)) if sf else "not evaluated",
            "stop_runs_counted": len(st), "closest_person_min_m": round(min(close), 3) if close else "not evaluated",
            "closest_person_median_m": round(statistics.median(close), 3) if close else "not evaluated",
            "median_time_s_success": sm["time_s"]["success_runs"]["median"],
            "round_trip_max_ms": max(num(rt)) if num(rt) else "not evaluated", "event_loop_lag_max_ms": max(num(lag)) if num(lag) else "not evaluated",
            "watchdog_stops_reported": sum(num(wd)) if num(wd) else "not evaluated"}


def write_tables(rows: list[dict], folder: Path, development: bool) -> Path:
    cols = list(dict.fromkeys(k for r in rows for k in r))
    with (folder / "phase_b_tables.csv").open("x", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(cols)
        for r in rows:
            w.writerow([r.get(c, "") for c in cols])
    L = ["# " + ("DEVELOPMENT dry run (not a result): " if development else "") + "per-setting summary", "",
         "| setting | runs | SUCCESS k/n (Wilson 95 %) | failures | lies g/d/c/f | STOP episodes true / false | closest person min / median (m) | median time of SUCCESS (s) | round trip max (ms) | loop lag max (ms) | watchdog stops |",
         "|---|---|---|---|---|---|---|---|---|---|---|"]
    for r in rows:
        fails = ", ".join(f"{k[7:]} {v}" for k, v in r.items() if k.startswith("failed_") and v) or "none"
        w95 = r["success_wilson95"]
        w95 = f"{w95[0]:.2f} to {w95[1]:.2f}" if isinstance(w95, list) else w95
        L.append(f"| {r['setting']} | {r['runs']} | {r['success_k']}/{r['success_n']} ({w95}) | {fails} | {r['lies_given']}/{r['lies_detected']}/{r['lies_corrected']}/{r['lies_fooled']} | "
                 f"{r['stop_gestures_true']} / {r['stop_gestures_false']} | {r['closest_person_min_m']} / {r['closest_person_median_m']} | {r['median_time_s_success']} | "
                 f"{r['round_trip_max_ms']} | {r['event_loop_lag_max_ms']} | {r['watchdog_stops_reported']} |")
    L += ["", "Every figure carries its count; a cell that could not be computed is 'not evaluated', never 0. STOP episodes are the accepted STOP gesture episodes "
          "(AUDIT.md 16.31.6) summed over the runs that have the columns.", ""]
    (folder / "phase_b_tables.md").write_text("\n".join(L), encoding="utf-8")
    return folder / "phase_b_tables.md"


def run_figures(pairs_by_setting: dict, report: Report, development: bool, repo: Path, skip: bool = False) -> None:
    if skip:
        report.add(5, "figures", SKIPPED, "--no-figures")
        return
    if not development:
        report.add(5, "figures", SKIPPED, "paper_v4/figures_v4.py reads DEVELOPMENT data only (its split guard refuses test data) and is Nusrat's file: it needs a "
                   "final mode through hri_eval_final_v4.gate, agreed with her (AUDIT.md 16.33 decision 7); the tables above are made")
        return
    script = repo / "paper_v4" / "figures_v4.py"
    args = [sys.executable, str(script)]
    for pairs in pairs_by_setting.values():
        for u, b in pairs:
            args += ["--session", str(u), str(b)]
    before = set((HERE / "outputs").glob("paper_v4_*")) if (HERE / "outputs").is_dir() else set()
    proc = subprocess.run(args, cwd=repo, capture_output=True, text=True)
    new = sorted(set((HERE / "outputs").glob("paper_v4_*")) - before)
    if proc.returncode != 0:
        raise StepFailed("paper_v4/figures_v4.py failed: " + (proc.stderr or proc.stdout).strip().splitlines()[-1][:300])
    report.add(5, "figures (development)", OK, f"{new[-1].name if new else 'no new folder'} (written by figures_v4.py under outputs/, git-ignored)",
               folder=new[-1].name if new else None)


def confusion(rows: list[dict], shown_key: str, read_key: str, labels: list[str]) -> dict:
    """counts[shown][read] over the asks that have a shown label; a blank reading is its own column '(none)'; row totals and the share on the diagonal."""
    cols = labels + ["(none)"]
    counts = {a: {b: 0 for b in cols} for a in labels}
    other = 0
    for r in rows:
        a, b = (r.get(shown_key) or "").strip(), (r.get(read_key) or "").strip() or "(none)"
        if a not in counts:
            other += 1
            continue
        counts[a][b if b in cols else "(none)"] += 1
    total = {a: sum(counts[a].values()) for a in labels}
    diag = {a: (counts[a][a] / total[a] if total[a] else None) for a in labels}
    return {"labels": labels, "columns": cols, "counts": counts, "row_total": total, "share_read_as_shown": diag, "asks": sum(total.values()),
            "asks_without_a_shown_label": other}


def write_matrix(folder: Path, stem: str, title: str, mats: dict[str, dict], shown: str, read: str, share_label: str = "share read as shown") -> None:
    """One CSV (setting, shown, columns..., total, share) and one Markdown with a matrix per key of mats."""
    cols = next(iter(mats.values()))["columns"] if mats else []
    with (folder / f"{stem}.csv").open("x", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["scope", shown] + cols + ["row_total", share_label.replace(" ", "_")])
        for scope, m in mats.items():
            for a in m["labels"]:
                share = m["share_read_as_shown"][a]
                w.writerow([scope, a] + [m["counts"][a][c] for c in cols] + [m["row_total"][a], "" if share is None else round(share, 3)])
    L = [f"# {title}", "", f"Rows: {shown}; columns: {read}. Counts are asks; '(none)' = no reading. A pooled matrix mixes settings.", ""]
    for scope, m in mats.items():
        L += [f"## {scope} ({m['asks']} asks" + (f", {m['asks_without_a_shown_label']} without a shown label left out" if m["asks_without_a_shown_label"] else "") + ")", "",
              "| " + shown + " \\ " + read + " | " + " | ".join(cols) + f" | total | {share_label} |", "|---|" + "---|" * (len(cols) + 2)]
        for a in m["labels"]:
            share = m["share_read_as_shown"][a]
            L.append(f"| {a} | " + " | ".join(str(m["counts"][a][c]) for c in cols) + f" | {m['row_total'][a]} | {'' if share is None else f'{share:.2f}'} |")
        L.append("")
    (folder / f"{stem}.md").write_text("\n".join(L), encoding="utf-8")


def write_pairs(comparisons: list[dict], folder: Path, development: bool) -> None:
    """B detection ON vs OFF and Set A vs Set B (and A2 right vs left) with Newcombe 95 % intervals, from the combined table's comparison rows."""
    cols = ["kind", "name", "metric", "x", "x_cell", "y", "y_cell", "difference_pp", "difference_lo_pp", "difference_hi_pp", "available"]
    order = {"B on vs off": 0, "A vs B": 1, "A2 right vs left": 2}
    rows = sorted(comparisons, key=lambda c: (order.get(c.get("kind"), 9), c["name"], c["metric"]))
    with (folder / "phase_b_pairs.csv").open("x", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(cols)
        for c in rows:
            w.writerow([ex._fmt(c.get(k)) for k in cols])
    L = ["# " + ("DEVELOPMENT dry run (not a result): " if development else "") + "pairs: B detection ON vs OFF, Set A vs Set B", "",
         "y minus x in percentage points with the Newcombe hybrid-score 95 % interval (Wilson based). It describes the two rates only: no test, no claim of significance.", "",
         "| kind | comparison | metric | x | y | y - x (pp) | Newcombe 95 % (pp) |", "|---|---|---|---|---|---|---|"]
    for c in rows:
        ci = f"[{c['difference_lo_pp']}, {c['difference_hi_pp']}]" if c.get("difference_lo_pp") not in ("", None) else ""
        L.append(f"| {c.get('kind')} | {c['name']} | {c['metric']} | {c['x']}: {c['x_cell']} | {c['y']}: {c['y_cell']} | {ex._fmt(c.get('difference_pp'))} | {ci} |")
    (folder / "phase_b_pairs.md").write_text("\n".join(L) + "\n", encoding="utf-8")


def step_tables(pairs_by_setting: dict, export_folders: dict, folder: Path, development: bool, repo: Path, report: Report, cfg: dict | None = None,
                no_figures: bool = False) -> None:
    cfg = cfg or load_config()
    rows = [setting_table_row(s, export_folders[s], [b for _, b in pairs_by_setting[s]]) for s in pairs_by_setting]
    path = write_tables(rows, folder, development)
    report.add(5, "tables", OK, f"{path.name} and phase_b_tables.csv: {len(rows)} settings", rows=rows)
    comps = report.extra.get("comparisons") or []
    write_pairs(comps, folder, development)
    report.add(5, "pairs", OK, f"phase_b_pairs.csv / .md: {len(comps)} comparison rows (B ON vs OFF, Set A vs Set B, A2 right vs left)")
    dialogs = {}
    for s, ef_ in export_folders.items():
        with (Path(ef_) / "dialogs.csv").open(encoding="utf-8", newline="") as f:
            dialogs[s] = list(csv.DictReader(f))
    allrows = [r for rs in dialogs.values() for r in rs]
    for stem, title, shown, read, labels in (("phase_b_gesture_confusion", "gesture confusion: shown vs read", "command_shown", "command_read", cfg["gesture_labels"]),
                                            ("phase_b_branch_confusion", "branch confusion: true vs read branch", "true_branch", "branch_read", cfg["branch_labels"])):
        mats = {s: confusion(rs, shown, read, labels) for s, rs in dialogs.items()}
        mats = {"ALL settings of this run (pooled)": confusion(allrows, shown, read, labels), **mats}
        write_matrix(folder, stem, ("DEVELOPMENT dry run (not a result): " if development else "") + title, mats, shown, read,
                     "share read as shown" if shown == "command_shown" else "share read as true")
        report.add(5, stem.replace("phase_b_", ""), OK, f"{stem}.csv / .md: {mats['ALL settings of this run (pooled)']['asks']} asks pooled, {len(dialogs)} settings")
    run_figures(pairs_by_setting, report, development, repo, no_figures)


# ---------------------------------------------------------------- step 6: the archive manifest

def step_manifest(pairs_by_setting: dict, eval_folders: dict, export_folders: dict, manifest_path: Path, append: bool, report: Report) -> None:
    import make_results_archive_v4 as mav
    entries = []
    for s, pairs in pairs_by_setting.items():
        e = {"setting": s, "role": "final", "unity": pairs[0][0].name, "bridge": pairs[0][1].name, "eval": eval_folders[s].name, "export": export_folders[s].name}
        if len(pairs) == 2:
            e.update({"unity_resumed": pairs[1][0].name, "bridge_resumed": pairs[1][1].name,
                      "note": "resumed once after a declared interruption (AUDIT.md 16.30.1); the archive tool archives the first part only until it is extended"})
        entries.append(e)
    if not append:
        report.add(6, "manifest", SKIPPED, "--no-manifest-append: the entries are in the report only", entries=entries)
        return
    m = json.loads(manifest_path.read_text(encoding="utf-8"))
    have = {(x.get("setting"), x.get("role")) for x in m.get("sessions", [])}
    dup = [e["setting"] for e in entries if (e["setting"], "final") in have]
    if dup:
        raise StepFailed(f"results_manifest.json already has a final entry for {dup}: nothing appended")
    m["sessions"] = list(m.get("sessions", [])) + entries
    problems = mav.validate_manifest(m)
    if problems:
        raise StepFailed("the manifest would be invalid: " + "; ".join(problems))
    tmp = manifest_path.with_suffix(".json.tmp")
    tmp.write_text(json.dumps(m, indent=1) + "\n", encoding="utf-8")
    os.replace(tmp, manifest_path)
    report.add(6, "manifest", OK, f"{len(entries)} entries appended to {manifest_path.name} (a tracked file: commit it)", entries=entries)


# ---------------------------------------------------------------- the runbook

def new_report_dir(root: Path, prefix: str = "process_final_zip_v4") -> Path:
    """A NEW report folder under root (never reused: a second run in the same second gets a numbered name)."""
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    for k in range(1, 100):
        d = Path(root) / (f"{prefix}_{stamp}" + ("" if k == 1 else f"_{k}"))
        try:
            d.mkdir(parents=True)
            return d
        except FileExistsError:
            continue
    raise SystemExit("cannot make a new report folder")


def run(zip_path, sha256: str, development: bool = False, config: str | Path | None = None, repo: Path | None = None, only: list[str] | None = None,
        final_root: str | Path | None = None, work_root: str | Path | None = None, manifest_append: bool = True, manifest_path: str | Path | None = None,
        dev_runs: int | None = None, no_figures: bool = False, reuse_ingested: bool = False) -> tuple[int, Path, Report]:
    """The whole runbook. Returns (exit code, report folder, report). A failed step stops it: the report says which and why."""
    cfg = load_config(config)
    repo = Path(repo) if repo else fz.REPO
    zpath = Path(zip_path)
    report = Report(zpath, development)
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    if development:
        base = _root(str(work_root or cfg["development_root"]))
        root = base / f"phase_b_development_{stamp}"
    else:
        root = _root(str(final_root or cfg["final_root"]))
    if development and not _outside_repo(root, repo):
        print(f"WARNING: the development root {root} is inside the repository", file=sys.stderr)
    report_dir = None
    failed = None
    try:
        meta, entries = step_verify(zpath, sha256, development, cfg["development"]["prefix"] if development else "", report)
        if only:
            entries = [e for e in entries if e["setting"] in only]
            if not entries:
                raise StepFailed(f"--only {only}: none of them is in the zip")
            report.settings = [e["setting"] for e in entries]
        root.mkdir(parents=True, exist_ok=True)
        if not development:
            preflight_final(entries, [root, _root("outputs")] if root != _root("outputs") else [root], repo, check_destination=not reuse_ingested)
            report.add(2, "run-once preflight", OK, "no evaluation, export or invalid marker for any setting in the zip; no destination folder exists")
        pairs = step_accept(zpath, meta, entries, root, repo, development, int(dev_runs or cfg["development"]["runs_per_setting"]), report, reuse_ingested)
        if development:
            report.add(3, "evaluate", SKIPPED, "--development: no final evaluation, no FINAL_DONE.json")
            export_folders = step_export_development(pairs, root, repo, report)
            eval_folders = {}
        else:
            eval_folders = step_evaluate(pairs, root, repo, report)
            export_folders = step_export_final(pairs, root, repo, report)
        report_dir = new_report_dir(root)
        step_tables(pairs, export_folders, report_dir, development, repo, report, cfg, no_figures)
        if development:
            report.add(6, "manifest", SKIPPED, "--development: nothing is written as final, no archive entry")
            leaked = [str(p) for name in FINAL_MARKER_FILES for p in root.rglob(name)]
            if leaked:
                raise StepFailed(f"a FINAL marker exists in the development folder: {leaked}")
            report.add(0, "no final marker", OK, "no FINAL_*.json anywhere in the development folder")
        else:
            step_manifest(pairs, eval_folders, export_folders, _root(str(manifest_path or cfg["manifest"])), manifest_append, report)
    except StepFailed as e:
        failed = str(e)
        report.add(99, "STOPPED", FAIL, failed)
    except SystemExit as e:                                   # a library refusal that no step caught: still a stop with its reason
        failed = str(e)
        report.add(99, "STOPPED", FAIL, failed)
    if report_dir is None:
        report_dir = new_report_dir(root)
    report.write(report_dir, failed)
    print(f"report: {report_dir}")
    return (1 if failed else 0), report_dir, report


def _outside_repo(path: Path, repo: Path) -> bool:
    try:
        path.resolve().relative_to(repo.resolve())
        return False
    except ValueError:
        return True


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("zip", help="the sitting zip made by final_zip_v4.py (or, with --development, the step-5 zip)")
    ap.add_argument("--sha256", required=True, help="the SHA-256 Nusrat sent with the zip")
    ap.add_argument("--development", action="store_true", help="dry run on development data: steps 3 and 6 are skipped, nothing is written as final")
    ap.add_argument("--only", nargs="+", default=None, help="process only these settings of the zip (development dry runs)")
    ap.add_argument("--config", default=None)
    ap.add_argument("--final-root", default=None, help="a final: where the sitting's folders and the results go (default: configs/v4/phase_b.json final_root)")
    ap.add_argument("--work-root", default=None, help="--development: where the dry run's folder is made (default: development_root of the config)")
    ap.add_argument("--reuse-ingested", action="store_true", help="a final: a folder of THIS zip already in the final root (a run that stopped part-way) is reused if every file equals the zip's; never overwritten")
    ap.add_argument("--no-figures", action="store_true", help="skip the paper figures (paper_v4/figures_v4.py)")
    ap.add_argument("--no-manifest-append", action="store_true", help="a final: do not append the entries to results_manifest.json (they stay in the report)")
    a = ap.parse_args(argv)
    code, _, _ = run(a.zip, a.sha256, a.development, a.config, only=a.only, final_root=a.final_root, work_root=a.work_root, manifest_append=not a.no_manifest_append, no_figures=a.no_figures, reuse_ingested=a.reuse_ingested)
    return code


if __name__ == "__main__":
    sys.exit(main())
