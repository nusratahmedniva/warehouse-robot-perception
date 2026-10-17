"""Rewrite absolute paths in existing run folders as portable root tokens (see run_paths.py). No inference is
rerun and no image is touched.

For every .json / .jsonl / .md / .csv / .yaml / .txt file of a run folder, string values that are absolute paths
under the OLD dataset, output or project roots become {dataset_root}/..., {output_root}/... or
{project_root}/.... The original file is copied first to <run>/_path_migration_backup/<same relative path>
(an existing backup is never overwritten). A log is written to <run>/path_migration.json.

The old roots default to the roots configured on this machine; pass --old-* when migrating folders that were
written on another machine.

Usage (from robot_vision/):
    python migrate_run_paths.py --all                    # every run folder in the output root
    python migrate_run_paths.py outputs/fuse_300f_20261011_042733 --dry-run
"""

from __future__ import annotations

import argparse
import json
import shutil
from datetime import datetime
from pathlib import Path

import run_paths as rp
import thud_data as td

BACKUP_DIR = "_path_migration_backup"
LOG = "path_migration.json"
TEXT_SUFFIXES = {".json", ".jsonl", ".md", ".csv", ".yaml", ".yml", ".txt"}


def migrate_text(path: Path, rts: dict) -> tuple[str, str, list[str]]:
    """(original text, migrated text, unmapped absolute paths) for one file."""
    text = path.read_text(encoding="utf-8")
    unmapped: list[str] = []
    if path.suffix == ".json":
        new = json.dumps(rp.portable_obj(json.loads(text), rts, unmapped), indent=2)
        if text.endswith("\n"):
            new += "\n"
        if json.loads(new) == json.loads(text):
            new = text  # keep the original formatting when nothing changed
    elif path.suffix == ".jsonl":
        lines = []
        for line in text.splitlines():
            lines.append(json.dumps(rp.portable_obj(json.loads(line), rts, unmapped)) if line.strip() else line)
        new = "\n".join(lines) + ("\n" if text.endswith("\n") else "")
        if [json.loads(l) for l in new.splitlines() if l.strip()] == [json.loads(l) for l in text.splitlines() if l.strip()]:
            new = text
    else:
        new, unmapped = rp.portable_text(text, rts)
    return text, new, unmapped


def migrate_run(run: Path, rts: dict, dry_run: bool) -> dict:
    changed, unmapped = [], {}
    for f in sorted(run.rglob("*")):
        if not f.is_file() or f.suffix.lower() not in TEXT_SUFFIXES or BACKUP_DIR in f.relative_to(run).parts \
                or f.name == LOG:
            continue
        old, new, um = migrate_text(f, rts)
        if um:
            unmapped[f.relative_to(run).as_posix()] = sorted(set(um))[:20]
        if new == old:
            continue
        changed.append(f.relative_to(run).as_posix())
        if dry_run:
            continue
        backup = run / BACKUP_DIR / f.relative_to(run)
        if not backup.exists():
            backup.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(f, backup)
        f.write_text(new, encoding="utf-8")
    log = {"run": run.name, "dry_run": dry_run, "files_changed": changed, "unmapped_absolute_paths": unmapped}
    if not dry_run and changed:
        prev = json.loads((run / LOG).read_text(encoding="utf-8")) if (run / LOG).exists() else {"migrations": []}
        prev["migrations"].append({"at": datetime.now().isoformat(timespec="seconds"), "files_changed": changed,
                                   "backup_dir": BACKUP_DIR, "unmapped_absolute_paths": unmapped,
                                   "convention": "see run_paths.py"})
        (run / LOG).write_text(json.dumps(prev, indent=2) + "\n", encoding="utf-8")
    return log


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("runs", nargs="*", type=Path)
    p.add_argument("--all", action="store_true", help="every folder in the configured output root")
    p.add_argument("--config", default=str(rp.PROJECT_ROOT / "configs" / "office.json"))
    p.add_argument("--old-dataset-root")
    p.add_argument("--old-output-root")
    p.add_argument("--old-project-root")
    p.add_argument("--dry-run", action="store_true")
    a = p.parse_args()
    cfg = td.load_config(Path(a.config))
    rts = rp.make_roots(a.old_dataset_root or cfg["dataset_root"], a.old_output_root or cfg["output_root"],
                        a.old_project_root)
    runs = [r if r.is_absolute() else rp.PROJECT_ROOT / r for r in a.runs]
    if a.all:
        runs += sorted(d for d in Path(cfg["output_root"]).iterdir() if d.is_dir())
    if not runs:
        raise SystemExit("Give run folders or --all")
    total_unmapped = 0
    for run in runs:
        log = migrate_run(run, rts, a.dry_run)
        total_unmapped += sum(len(v) for v in log["unmapped_absolute_paths"].values())
        print(f"{run.name}: {len(log['files_changed'])} file(s) {'would change' if a.dry_run else 'rewritten'}"
              + (f"; UNMAPPED absolute paths: {log['unmapped_absolute_paths']}" if log["unmapped_absolute_paths"] else ""))
    if total_unmapped:
        raise SystemExit(f"{total_unmapped} absolute path(s) were not under the given roots; see above.")


if __name__ == "__main__":
    main()
