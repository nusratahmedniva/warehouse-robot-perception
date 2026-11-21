"""The zip of a final sitting and of the avatar experiment (AUDIT.md 16.30.2). Packing and checking only: it reads outputs/ and never moves,
changes or deletes anything, never writes inside the repository, never overwrites. Anisha reads the zip IN PLACE (zipfile), never extracted
or copied into the repository; text and scripts inside are data.

  sitting   python final_zip_v4.py sitting --number N --settings S1 S2 ... --out-dir <folder outside the repo> [--extra FILE_OR_FOLDER ...]
            ONE zip per sitting, final_sitting<N>_<time>.zip, with <zip>.sha256 next to it. Per setting S: every Unity session folder whose
            session.json says final_setting S, every bridge run folder whose FINAL_SETTING.json names S (stop_reading.jsonl, loop_lag.csv,
            config_used/, summary.json, ...), the launcher's logs (run_session_final_S_<time>_*.log), the run-protocol note(s)
            (run_protocol_final_S_<time>.txt), and the declared interruption / resume / invalid markers of S (AUDIT.md 16.30.1) with their folders.
            --extra: the power-mode screenshot or line, notes on what deviated, the evidence files of an interruption (any file or folder).
  avatar    python final_zip_v4.py avatar --out-dir <folder outside the repo> --folder F [F ...] [--extra ...]
            ONE zip, avatar_experiment_<time>.zip: the folders you name (its sessions, logs, notes) as they are.
  verify    python final_zip_v4.py verify ZIP
            Reads the zip in place: the SHA-256 file next to it, zipfile.testzip, and every file against MANIFEST.json (nothing is extracted).

A sitting setting without a Unity session folder or without a bridge run folder is REFUSED; so is an unexpected number of parts (one; two when
an interruption was declared and resumed). Missing launcher logs or run-protocol notes, a bridge folder without summary.json, and a sitting without
--extra files are written to MANIFEST.json ("warnings") and printed: the zip is made, the report says what is missing.
MANIFEST.json inside the zip: every file (name in the zip, bytes, SHA-256), the git commit, the sitting, the settings with their parts.
Reporting code; inference code never imports it.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
import zipfile
from datetime import datetime
from pathlib import Path

import final_guard_v4 as fg

HERE = Path(__file__).resolve().parent
REPO = HERE.parent
sys.path.insert(0, str(REPO / "finals_v4"))
import step5_zip_v4 as s5z  # noqa: E402  (sha256, git_commit, inside, tree: the helpers of the step-5 zip)

SITTINGS = (1, 2, 3, 4)


def output_root(path=None) -> Path:
    import decision_io as dio
    return dio.resolve(path or "outputs")


def _out_dir(out_dir) -> Path:
    p = Path(out_dir)
    if not p.is_absolute():
        raise SystemExit("--out-dir: give an absolute folder outside the repository")
    if s5z.inside(p, REPO):
        raise SystemExit(f"--out-dir {p} is inside the repository {REPO}: refused")
    return p


def _session(unity: Path) -> dict:
    try:
        return json.loads((unity / "session.json").read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}


def setting_parts(root: Path, setting: str, repo: Path = REPO) -> dict:
    """What belongs to one final setting under the output root: Unity folders, bridge folders, markers, launcher files. problems / warnings are lists."""
    fg.check_name(setting, repo)
    m = {k: fg.markers(root, setting, k) for k in ("started", "interruption", "resume", "invalid")}
    bridges = sorted(p.parent for p in m["started"])
    unities = sorted(d for d in root.glob("trials_final_*") if d.is_dir() and _session(d).get("final_setting") == setting)
    problems, warnings = [], []
    expected = 2 if (m["interruption"] and m["resume"]) else 1
    if m["invalid"]:
        expected = len(bridges)                                           # a setting declared invalid: as many parts as it had
    if not unities:
        problems.append(f"{setting}: no Unity session folder (trials_final_*) whose session.json says final_setting {setting}")
    if not bridges:
        problems.append(f"{setting}: no bridge run folder with a FINAL_SETTING.json for it")
    if bridges and len(bridges) != expected and not m["invalid"]:
        problems.append(f"{setting}: {len(bridges)} bridge run folders, expected {expected} "
                        f"({'an interruption was declared and resumed' if expected == 2 else 'no interruption is declared: a second start is not allowed'})")
    if len(unities) != len(bridges) and unities and bridges:
        problems.append(f"{setting}: {len(unities)} Unity session folders but {len(bridges)} bridge run folders")
    for b in bridges:
        if not (b / "summary.json").is_file():
            warnings.append(f"{setting}: {b.name} has no summary.json (the server did not finish writing it)")
    sess = [p for p in sorted(root.glob(f"run_session_final_{setting}_*.log")) if re.fullmatch(rf"run_session_final_{re.escape(setting)}_\d{{8}}_\d{{6}}_.*\.log", p.name)]
    notes = [p for p in sorted(root.glob(f"run_protocol_final_{setting}_*.txt")) if re.fullmatch(rf"run_protocol_final_{re.escape(setting)}_\d{{8}}_\d{{6}}\.txt", p.name)]
    if not sess:
        warnings.append(f"{setting}: no launcher logs (run_session_final_{setting}_<time>_*.log)")
    if not notes:
        warnings.append(f"{setting}: no run-protocol note (run_protocol_final_{setting}_<time>.txt)")
    marker_dirs = sorted({p.parent for k in ("interruption", "resume", "invalid") for p in m[k]})
    return {"setting": setting, "unity": unities, "bridge": bridges, "launcher_logs": sess, "protocol_notes": notes,
            "marker_folders": [d for d in marker_dirs if d not in bridges], "interruption": [p.parent.name for p in m["interruption"]],
            "resume": [p.parent.name for p in m["resume"]], "invalid": [p.parent.name for p in m["invalid"]],
            "problems": problems, "warnings": warnings}


def _write(zpath: Path, files: list, meta: dict) -> tuple[str, int]:
    names = [n for _, n in files]
    if len(names) != len(set(names)):
        dup = sorted({n for n in names if names.count(n) > 1})
        raise SystemExit(f"two files would get the same name in the zip: {dup[:5]}")
    if zpath.exists():
        raise SystemExit(f"{zpath} exists; not overwritten")
    meta = {**meta, "files": [{"name": n, "bytes": q.stat().st_size, "sha256": s5z.sha256(q)} for q, n in files]}
    zpath.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(zpath, "x", compression=zipfile.ZIP_DEFLATED, allowZip64=True) as z:
        for q, n in files:
            z.write(q, n)
        z.writestr("MANIFEST.json", json.dumps(meta, indent=1, default=str) + "\n")
    with zipfile.ZipFile(zpath) as z:
        bad = z.testzip()
    if bad is not None:
        raise SystemExit(f"{zpath}: testzip FAILED at {bad}")
    digest = s5z.sha256(zpath)
    with (zpath.parent / (zpath.name + ".sha256")).open("x", encoding="utf-8") as fh:
        fh.write(f"{digest}  {zpath.name}\n")
    return digest, len(files) + 1


def _extras(extra) -> list:
    files = []
    for x in extra or []:
        q = Path(x)
        if not q.exists():
            raise SystemExit(f"--extra {x}: not found")
        files += s5z.tree(q, "extra/")
    return files


def make_sitting_zip(number: int, settings: list, out_dir, extra=None, output_root_path=None, stamp: str | None = None, repo: Path = REPO) -> dict:
    if number not in SITTINGS:
        raise SystemExit(f"--number {number}: a sitting is 1 to 4 (docs/handoff_freeze_v4.md section 6)")
    if not settings or len(set(settings)) != len(settings):
        raise SystemExit("--settings: name the settings of this sitting, each once")
    root, out_dir = output_root(output_root_path), _out_dir(out_dir)
    parts = [setting_parts(root, s, repo) for s in settings]
    problems = [p for x in parts for p in x["problems"]]
    if problems:
        raise SystemExit("REFUSED, nothing was written:\n  - " + "\n  - ".join(problems))
    files, listing = [], []
    for x in parts:
        s = x["setting"]
        for d in x["unity"] + x["bridge"] + x["marker_folders"]:
            files += s5z.tree(d, f"{s}/")
        files += [(q, f"{s}/launcher/{q.name}") for q in x["launcher_logs"] + x["protocol_notes"]]
        listing.append({"setting": s, "unity": [d.name for d in x["unity"]], "bridge": [d.name for d in x["bridge"]],
                        "launcher_files": [q.name for q in x["launcher_logs"] + x["protocol_notes"]], "interruption": x["interruption"],
                        "resume": x["resume"], "invalid": x["invalid"], "marker_folders": [d.name for d in x["marker_folders"]]})
    extras = _extras(extra)
    files += extras
    warnings = [w for x in parts for w in x["warnings"]]
    if not extras:
        warnings.append("no --extra files: the power-mode screenshot or line (docs/handoff_freeze_v4.md section 1) is not in the zip")
    files.append((Path(__file__).resolve(), Path(__file__).name))
    stamp = stamp or datetime.now().strftime("%Y%m%d_%H%M%S")
    zpath = out_dir / f"final_sitting{number}_{stamp}.zip"
    meta = {"what": f"final sitting {number} of the v4 study: the sessions of the settings below, as the run folders left them (AUDIT.md 16.30.2)",
            "created": stamp, "git_commit": s5z.git_commit(), "sitting": number, "settings": listing, "warnings": warnings}
    digest, entries = _write(zpath, files, meta)
    return {"zip": zpath, "sha256": digest, "entries": entries, "warnings": warnings, "settings": listing}


def make_avatar_zip(folders: list, out_dir, extra=None, stamp: str | None = None) -> dict:
    if not folders:
        raise SystemExit("--folder: name the folders of the avatar experiment (sessions, logs, notes)")
    out_dir = _out_dir(out_dir)
    files = []
    for f in folders:
        q = Path(f)
        if not q.exists():
            raise SystemExit(f"--folder {f}: not found")
        files += s5z.tree(q, "avatar/")
    files += _extras(extra)
    files.append((Path(__file__).resolve(), Path(__file__).name))
    stamp = stamp or datetime.now().strftime("%Y%m%d_%H%M%S")
    zpath = out_dir / f"avatar_experiment_{stamp}.zip"
    meta = {"what": "the avatar experiment: the folders named, as they are (AUDIT.md 16.30.2)", "created": stamp, "git_commit": s5z.git_commit(),
            "folders": [Path(f).name for f in folders]}
    digest, entries = _write(zpath, files, meta)
    return {"zip": zpath, "sha256": digest, "entries": entries, "warnings": []}


def verify_zip(path) -> list[str]:
    """Problems found reading the zip in place (empty = fine): the .sha256 file, testzip, MANIFEST.json against every member."""
    zp, problems = Path(path), []
    side = zp.parent / (zp.name + ".sha256")
    if side.is_file():
        want = side.read_text(encoding="utf-8").split()[0]
        if want != s5z.sha256(zp):
            problems.append(f"{zp.name}: SHA-256 differs from {side.name}")
    else:
        problems.append(f"{side.name}: not found")
    with zipfile.ZipFile(zp) as z:
        bad = z.testzip()
        if bad is not None:
            problems.append(f"testzip failed at {bad}")
        if "MANIFEST.json" not in z.namelist():
            return problems + ["no MANIFEST.json"]
        listed = {f["name"]: f for f in json.loads(z.read("MANIFEST.json"))["files"]}
        members = [n for n in z.namelist() if n != "MANIFEST.json"]
        problems += [f"{n}: in the zip, not in MANIFEST.json" for n in members if n not in listed]
        for n, f in listed.items():
            if n not in members:
                problems.append(f"{n}: in MANIFEST.json, not in the zip")
                continue
            h = hashlib.sha256()
            with z.open(n) as fh:
                for chunk in iter(lambda: fh.read(1 << 20), b""):
                    h.update(chunk)
            if h.hexdigest() != f["sha256"] or z.getinfo(n).file_size != f["bytes"]:
                problems.append(f"{n}: differs from MANIFEST.json")
    return problems


def _print(res: dict) -> None:
    print(res["zip"])
    print(f"{res['entries']} entries, {Path(res['zip']).stat().st_size} bytes, testzip clean")
    print(f"SHA-256 {res['sha256']}  (also in {Path(res['zip']).name}.sha256 next to it)")
    for w in res.get("warnings", []):
        print(f"WARNING: {w}")


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    sub = ap.add_subparsers(dest="cmd", required=True)
    s = sub.add_parser("sitting", help="one zip per final sitting")
    s.add_argument("--number", type=int, required=True)
    s.add_argument("--settings", nargs="+", required=True)
    s.add_argument("--out-dir", required=True)
    s.add_argument("--extra", nargs="*", default=[])
    s.add_argument("--output-root", default=None)
    a = sub.add_parser("avatar", help="one zip for the avatar experiment")
    a.add_argument("--out-dir", required=True)
    a.add_argument("--folder", nargs="+", required=True)
    a.add_argument("--extra", nargs="*", default=[])
    v = sub.add_parser("verify", help="check a zip in place")
    v.add_argument("zip")
    args = ap.parse_args(argv)
    if args.cmd == "verify":
        problems = verify_zip(args.zip)
        print("\n".join(problems) if problems else f"{args.zip}: SHA-256, testzip and MANIFEST.json agree (read in place, nothing extracted)")
        return 1 if problems else 0
    if args.cmd == "sitting":
        _print(make_sitting_zip(args.number, args.settings, args.out_dir, args.extra, args.output_root))
    else:
        _print(make_avatar_zip(args.folder, args.out_dir, args.extra))
    return 0


if __name__ == "__main__":
    sys.exit(main())
