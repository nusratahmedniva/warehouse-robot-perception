"""Step 5 zip for Anisha: ONE zip, outside the repository, of every step-5 session with one setting prefix and the analysis outputs.

Avatar/Config/experiments_ab.md section 15 addendum 8, item 2 (c). Read-only on the outputs; never overwrites; never imported by inference code.
Per manifest entry (robot_vision/outputs/step5_sessions.json, written by step5_session_checks.ps1) whose setting is <prefix><final setting>:
the Unity session folder, the bridge run folder and the export folder (whole, recursively), the launcher transcript, and the launcher's
own logs of that session (run_session_rehearsal_<name>_<stamp>_*.log) and its run-protocol note (run_protocol_*.txt), found by the names
the transcript gives. Plus every --extra file or folder (the analysis outputs, the avatar rehearsal folders), the manifest and this script.
Inside the zip: MANIFEST.json (every file: name in the zip, bytes, SHA-256; the sessions; the git commit). After writing: zipfile.testzip.
Prints the zip's path, size and SHA-256 and writes <zip>.sha256 next to it.

Usage (repository root):
  Windows: robot_vision\\.venv\\Scripts\\python.exe finals_v4\\step5_zip_v4.py --prefix t0_ --out-dir <folder outside the repo>
           [--manifest robot_vision\\outputs\\step5_sessions.json] [--extra <file or folder> ...]
  macOS:   robot_vision/.venv/bin/python finals_v4/step5_zip_v4.py (same arguments, forward slashes)
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import subprocess
import sys
import zipfile
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import step5_report as s5  # noqa: E402  (REPO, RV, OUT, p, SETTINGS)

REPO, RV, OUT = s5.REPO, s5.RV, s5.OUT


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def git_commit() -> str:
    try:
        return subprocess.run(["git", "rev-parse", "HEAD"], cwd=REPO, capture_output=True, text=True, check=True).stdout.strip()
    except (OSError, subprocess.CalledProcessError):
        return "unknown"


def inside(path: Path, root: Path) -> bool:
    try:
        path.resolve().relative_to(root.resolve())
        return True
    except ValueError:
        return False


def tree(path: Path, prefix: str) -> list[tuple[Path, str]]:
    """(file on disk, name in the zip) for a file, or for every file under a folder (sorted)."""
    if path.is_file():
        return [(path, f"{prefix}{path.name}")]
    return [(q, f"{prefix}{path.name}/{q.relative_to(path).as_posix()}") for q in sorted(path.rglob("*")) if q.is_file()]


def launcher_files(transcript: Path) -> list[Path]:
    """The launcher's logs and protocol note named in its transcript (console wrapping can split a path: line breaks are removed first)."""
    text = re.sub(r"[\r\n]+\s*", "", transcript.read_text(encoding="utf-8-sig", errors="replace"))
    found: list[Path] = []
    for stem in sorted(set(re.findall(r"run_session_[A-Za-z0-9_]+?_\d{8}_\d{6}", text))):
        found += sorted(OUT.glob(stem + "_*.log"))
    for name in sorted(set(re.findall(r"run_protocol_[A-Za-z0-9_]+?_\d{8}_\d{6}\.txt", text))):
        if (OUT / name).exists():
            found.append(OUT / name)
    return found


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--prefix", required=True, help="the setting prefix of the sessions, e.g. t0_")
    ap.add_argument("--out-dir", required=True, help="a folder OUTSIDE the repository (created if missing)")
    ap.add_argument("--manifest", default=str(OUT / "step5_sessions.json"))
    ap.add_argument("--extra", nargs="*", default=[], help="analysis outputs and other files or folders to add")
    a = ap.parse_args(argv)
    out_dir = Path(a.out_dir)
    if not out_dir.is_absolute():
        raise SystemExit("--out-dir: give an absolute folder outside the repository")
    if inside(out_dir, REPO):
        raise SystemExit(f"--out-dir {out_dir} is inside the repository {REPO}: refused")
    man = Path(a.manifest) if Path(a.manifest).is_absolute() else REPO / a.manifest
    entries = s5.select(json.loads(man.read_text(encoding="utf-8-sig"))["sessions"], a.prefix)
    if not entries:
        raise SystemExit(f"{man}: no session with the prefix '{a.prefix}' and a final setting name")
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    out_dir.mkdir(parents=True, exist_ok=True)
    zpath = out_dir / f"step5_{a.prefix.rstrip('_')}_logs_{stamp}.zip"
    if zpath.exists():
        raise SystemExit(f"{zpath} exists; not overwritten")

    files: list[tuple[Path, str]] = []
    sessions = []
    for e in entries:
        st = e["setting"]
        U, B, X = s5.p(e["unity"]), s5.p(e["bridge"]), s5.p(e["export"])
        for q in (U, B, X):
            if not q.is_dir():
                raise SystemExit(f"{st}: {q} is not a folder")
        files += tree(U, f"{st}/") + tree(B, f"{st}/") + tree(X, f"{st}/")
        logs = []
        if e.get("launcher_log"):
            t = s5.p(e["launcher_log"])
            if t.exists():
                logs = [t] + launcher_files(t)
        files += [(q, f"{st}/launcher/{q.name}") for q in logs]
        sessions.append({"setting": st, "unity": U.name, "bridge": B.name, "export": X.name, "timeout_s": e.get("timeout_s"),
                         "checks_passed": e.get("checks_passed"), "launcher_files": [q.name for q in logs]})
    for x in a.extra:
        q = Path(x) if Path(x).is_absolute() else REPO / x
        if not q.exists():
            raise SystemExit(f"--extra {x}: not found")
        files += tree(q, "analysis/")
    files += [(man, man.name), (Path(__file__).resolve(), Path(__file__).name)]
    names = [n for _, n in files]
    if len(names) != len(set(names)):
        raise SystemExit("two files would get the same name in the zip")

    listing = [{"name": n, "bytes": q.stat().st_size, "sha256": sha256(q)} for q, n in files]
    meta = {"what": "step 5 development sessions (rehearsal mode) and their analysis; development data, not a result",
            "declared": "Avatar/Config/experiments_ab.md section 15 addendum 8", "created": stamp, "git_commit": git_commit(),
            "prefix": a.prefix, "sessions": sessions, "files": listing}
    with zipfile.ZipFile(zpath, "x", compression=zipfile.ZIP_DEFLATED, allowZip64=True) as z:
        for q, n in files:
            z.write(q, n)
        z.writestr("MANIFEST.json", json.dumps(meta, indent=1) + "\n")
    with zipfile.ZipFile(zpath) as z:
        bad = z.testzip()
    if bad is not None:
        raise SystemExit(f"{zpath}: testzip FAILED at {bad}")
    digest = sha256(zpath)
    with (out_dir / (zpath.name + ".sha256")).open("x", encoding="utf-8") as fh:
        fh.write(f"{digest}  {zpath.name}\n")
    print(f"{zpath}")
    print(f"{len(sessions)} sessions, {len(files) + 1} entries, {zpath.stat().st_size} bytes, testzip clean")
    print(f"SHA-256 {digest}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
