"""Data-split lookup and the final-evaluation guard (configs/data_splits.json).

Every script that reads a capture calls guard(). Captures in a final-evaluation split are refused unless
--final-evaluation is passed; that flag is for the one run with a frozen config. Captures in an excluded split are
always refused, and exclusions take precedence over any other matching entry, whatever the entry order.
"""

from __future__ import annotations

import fnmatch
import json
from pathlib import Path, PurePath

DEFAULT = Path(__file__).resolve().parent / "configs" / "data_splits.json"


def load(path: str | Path | None = None) -> dict:
    return json.loads(Path(path or DEFAULT).read_text(encoding="utf-8"))


def capture_key(capture_dir: str | PurePath, dataset_root: str | PurePath) -> str:
    """Capture path relative to the dataset root, POSIX style (e.g. Synthetic_Scenes/Office/dynamic/Capture_2)."""
    try:
        return Path(capture_dir).resolve().relative_to(Path(dataset_root).resolve()).as_posix()
    except ValueError:
        s = Path(capture_dir).as_posix()
        return s[s.index("Synthetic_Scenes/"):] if "Synthetic_Scenes/" in s else s


def _matches(key: str, pattern: str) -> bool:
    return key == pattern or fnmatch.fnmatchcase(key, pattern)


def split_of(key: str, splits: dict) -> str | None:
    caps = splits["captures"]
    excluded = set(splits.get("excluded_splits", []))
    for pattern, split in caps.items():  # exclusions first, independent of entry order
        if split in excluded and _matches(key, pattern):
            return split
    if key in caps:
        return caps[key]
    for pattern, split in caps.items():
        if fnmatch.fnmatchcase(key, pattern):
            return split
    return None


def guard(key: str, final_evaluation: bool, splits: dict | None = None) -> str | None:
    """Return the capture's split; refuse a final-evaluation capture without the explicit flag."""
    splits = splits or load()
    split = split_of(key, splits)
    if split in splits.get("excluded_splits", []):
        raise SystemExit(f"{key} is in the '{split}' split and may not be used for evaluation "
                         "(refused with or without --final-evaluation).")
    if split in splits["final_evaluation_splits"] and not final_evaluation:
        raise SystemExit(f"{key} is in the '{split}' split (final evaluation only). "
                         "Pass --final-evaluation for the one run with a frozen config.")
    if final_evaluation and split not in splits["final_evaluation_splits"]:
        raise SystemExit(f"--final-evaluation given, but {key} is in the '{split}' split.")
    return split
