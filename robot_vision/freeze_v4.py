"""Freezing the v4 study (same pattern as configs/hri_frozen.json + tests/test_hri_frozen.py, for configs/v4/).

configs/v4/frozen.json lists every v4 config file ("files") and, once frozen, their LF-normalised SHA-256, the v3 files v4
reads (hri_control, hri_perception, gesture_hri, roadmap, robot), and the SHA-256 of the pose weights and the MediaPipe
model. While "frozen" is false it holds only the file list: the thresholds are still being set on development data.
Nothing here freezes by itself: the freeze is a deliberate command, and it is refused while a blank is left in
configs/v4/final_plan.json, while a model file is missing, or when the file is already frozen (never overwritten).

Usage (from robot_vision/):
    python freeze_v4.py                 report: status, blanks, what would be hashed, current mismatches
    python freeze_v4.py --refresh-list  rewrite "files" of an UNFROZEN frozen.json from configs/v4/*.json
    python freeze_v4.py --freeze        write the hashes and set "frozen": true (Anisha, after the development evaluation)

Library use (final evaluation, server in final mode): problems(), require_frozen().
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from datetime import datetime
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parent
V4_DIR = "robot_vision/configs/v4"
FROZEN_REL = f"{V4_DIR}/frozen.json"
PLAN_REL = f"{V4_DIR}/final_plan.json"
V3_DEPENDENCIES = [f"robot_vision/configs/{n}" for n in
                   ("hri_control.json", "hri_perception.json", "gesture_hri.json", "roadmap.json", "robot.json")]
PLAN_BLANK_KEYS = ("task", "dev_seed", "final_seed", "runs_per_setting", "timeout_s", "success_radius_m",
                   "test_assignment", "unity_files_and_guard", "acceptance_criteria")
SPLITS_REL = f"{V4_DIR}/data_splits.json"


def sha256_lf(p: Path) -> str:
    """SHA-256 with CRLF read as LF (a Windows checkout with core.autocrlf has the same content)."""
    return hashlib.sha256(Path(p).read_bytes().replace(b"\r\n", b"\n")).hexdigest()


def read(repo: Path = REPO) -> dict:
    return json.loads((repo / FROZEN_REL).read_text(encoding="utf-8"))


def config_files(repo: Path = REPO) -> list[str]:
    """Repo-relative paths of every v4 config (configs/v4/*.json except frozen.json), sorted."""
    return sorted(f"{V4_DIR}/{p.name}" for p in (repo / V4_DIR).glob("*.json") if p.name != "frozen.json")


def snapshot(repo: Path = REPO) -> dict:
    return {"sha256": {f: sha256_lf(repo / f) for f in config_files(repo)},
            "v3_dependencies": {f: sha256_lf(repo / f) for f in V3_DEPENDENCIES}}


def _models(repo: Path) -> dict:
    """Where the pose weights and the MediaPipe model are, and the hashes the frozen v3 configs expect."""
    perc = json.loads((repo / "robot_vision/configs/hri_perception.json").read_text(encoding="utf-8"))
    gest = json.loads((repo / "robot_vision/configs/gesture_hri.json").read_text(encoding="utf-8"))
    root = repo / "robot_vision"
    return {"pose_weights": {"path": (root / perc["pose_model"]["weights"]).resolve(), "expected": perc["pose_model"]["sha256"]},
            "mediapipe_model": {"path": (root / gest["model"]["path"]).resolve(), "expected": gest["model"]["sha256"]}}


def model_status(repo: Path = REPO) -> dict:
    out = {}
    for name, m in _models(repo).items():
        p = m["path"]
        out[name] = {"path": p.relative_to(repo.resolve()).as_posix() if repo.resolve() in p.parents else p.name,
                     "present": p.exists(), "expected_sha256": m["expected"],
                     "sha256": hashlib.sha256(p.read_bytes()).hexdigest() if p.exists() else None}
    return out


def blanks(repo: Path = REPO) -> list[str]:
    plan = json.loads((repo / PLAN_REL).read_text(encoding="utf-8"))
    out = [f"final_plan.json: {k}" for k in PLAN_BLANK_KEYS if plan.get(k) is None]
    if json.loads((repo / SPLITS_REL).read_text(encoding="utf-8")).get("placeholder"):
        out.append("data_splits.json: look and clip names are still placeholders")
    return out


def problems(repo: Path = REPO, require_models: bool = False) -> list[str]:
    """What is wrong with the freeze. Unfrozen is not listed here (see is_frozen). Empty = frozen and every hash matches."""
    rec = read(repo)
    out = []
    if rec["files"] != config_files(repo):
        out.append(f"the file list is out of date: {sorted(set(rec['files']) ^ set(config_files(repo)))}")
    if not rec["frozen"]:
        return out
    now = snapshot(repo)
    for group in ("sha256", "v3_dependencies"):
        for f in sorted(set(rec[group]) | set(now[group])):
            if rec[group].get(f) != now[group].get(f):
                out.append(f"{f} changed after freezing" if f in rec[group] and f in now[group] else f"{f} added or removed since freezing")
    for name, st in model_status(repo).items():
        want = rec["models"].get(name, {}).get("sha256")
        if not st["present"]:
            if require_models:
                out.append(f"{name} not found at {st['path']}")
        elif st["sha256"] != want:
            out.append(f"{name} does not match the frozen hash")
    out += blanks(repo)
    return out


def is_frozen(repo: Path = REPO) -> bool:
    return bool(read(repo)["frozen"])


def require_frozen(repo: Path = REPO, require_models: bool = True) -> dict:
    """The frozen record, or SystemExit: a final run or final evaluation needs frozen = true and every hash matching."""
    if not is_frozen(repo):
        raise SystemExit("configs/v4/frozen.json is not frozen (\"frozen\": false): final runs and final evaluations are refused "
                         "until Anisha freezes the v4 configs after the development evaluation (python freeze_v4.py --freeze).")
    p = problems(repo, require_models)
    if p:
        raise SystemExit("the v4 freeze is broken: " + "; ".join(p))
    return read(repo)


def refresh_list(repo: Path = REPO) -> dict:
    rec = read(repo)
    if rec["frozen"]:
        raise SystemExit("frozen.json is frozen: its file list is not rewritten (disclose the change in AUDIT.md and use a new record)")
    rec["files"] = config_files(repo)
    (repo / FROZEN_REL).write_text(json.dumps(rec, indent=2) + "\n", encoding="utf-8")
    return rec


def freeze(repo: Path = REPO, now: datetime | None = None, git_commit: str | None = None) -> dict:
    """Write the hashes and set frozen = true. Refused: already frozen; a blank in final_plan.json; a model file missing."""
    rec = read(repo)
    if rec["frozen"]:
        raise SystemExit("frozen.json is already frozen; it is never overwritten")
    if blanks(repo):
        raise SystemExit("not frozen: blanks left in the plan: " + "; ".join(blanks(repo)))
    models = model_status(repo)
    missing = [n for n, m in models.items() if not m["present"]]
    if missing:
        raise SystemExit(f"not frozen: model file(s) not found: {missing} (the freeze records their SHA-256)")
    bad = [n for n, m in models.items() if m["sha256"] != m["expected_sha256"]]
    if bad:
        raise SystemExit(f"not frozen: {bad} do not match the SHA-256 in the frozen v3 configs")
    rec.update(frozen=True, frozen_at=(now or datetime.now()).isoformat(timespec="seconds"), git_commit=git_commit,
               files=config_files(repo), **snapshot(repo),
               models={n: {"path": m["path"], "sha256": m["sha256"]} for n, m in models.items()})
    (repo / FROZEN_REL).write_text(json.dumps(rec, indent=2) + "\n", encoding="utf-8")
    return rec


def main(argv=None) -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    g = ap.add_mutually_exclusive_group()
    g.add_argument("--refresh-list", action="store_true")
    g.add_argument("--freeze", action="store_true")
    a = ap.parse_args(argv)
    if a.refresh_list:
        print(json.dumps(refresh_list()["files"], indent=2))
        return
    if a.freeze:
        import decision_io as dio
        rec = freeze(git_commit=dio.git_info()["commit"])
        print(f"frozen at {rec['frozen_at']} (commit {rec['git_commit']}): {len(rec['sha256'])} v4 configs, "
              f"{len(rec['v3_dependencies'])} v3 files, {len(rec['models'])} model files")
        return
    rec = read()
    print(f"frozen: {rec['frozen']}")
    print("blanks in final_plan.json: " + (", ".join(blanks()) or "none"))
    print("would be hashed:\n  " + "\n  ".join(config_files() + V3_DEPENDENCIES))
    for n, m in model_status().items():
        print(f"model {n}: {'present' if m['present'] else 'MISSING'} {m['path']}")
    p = problems()
    print("problems: " + ("; ".join(p) if p else "none"))
    sys.exit(0 if not p or not rec["frozen"] else 1)


if __name__ == "__main__":
    main()
