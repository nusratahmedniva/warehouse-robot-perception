"""v4 data splits: avatar looks and animation clips (configs/v4/data_splits.json). The v3 capture splits stay in
data_splits.py and are not touched.

Development looks and clips are used to set thresholds; test looks and clips are never used in development. guard_run
refuses a run that mixes the two, a look or clip that is not listed, and a final evaluation while the names in the
config are placeholders. Like data_splits.guard it raises SystemExit.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Iterable

DEFAULT = Path(__file__).resolve().parent / "configs" / "v4" / "data_splits.json"
SPLITS = ("development", "test")


def load(path: str | Path | None = None) -> dict:
    splits = json.loads(Path(path or DEFAULT).read_text(encoding="utf-8"))
    problems = check_config(splits)
    if problems:
        raise ValueError("v4 data splits config: " + "; ".join(problems))
    return splits


def check_config(splits: dict) -> list[str]:
    """Problems in the config itself: unknown split names, no development or test entry, wrong final splits."""
    problems = []
    for kind in ("looks", "clips"):
        table = splits.get(kind)
        if not isinstance(table, dict) or not table:
            problems.append(f"no {kind}")
            continue
        for name, split in table.items():
            if split not in SPLITS:
                problems.append(f"{kind} {name!r} has split {split!r} (expected one of {SPLITS})")
        for want in SPLITS:
            if want not in table.values():
                problems.append(f"{kind} has no {want} entry")
    if splits.get("final_evaluation_splits") != ["test"]:
        problems.append("final_evaluation_splits must be ['test']")
    return problems


def split_of_look(look: str, splits: dict) -> str | None:
    return splits["looks"].get(look)


def split_of_clip(clip: str, splits: dict) -> str | None:
    return splits["clips"].get(clip)


def guard_run(looks: Iterable[str], clips: Iterable[str], final_evaluation: bool = False,
              splits: dict | None = None) -> str:
    """The split ('development' or 'test') of a run with these avatar looks and gesture animation clips, or SystemExit.

    looks: the looks of the workers in the run. clips: the animation clip names of its gestures (a gesture with no
    logged name is "" and refused). Refused: nothing listed; an unlisted look or clip; a mix of development and test
    (looks with clips included); test without final_evaluation; final_evaluation on development; final_evaluation
    while the config's names are placeholders."""
    splits = splits if splits is not None else load()
    looks, clips = sorted(set(looks)), sorted(set(clips))
    if not looks:
        raise SystemExit("no avatar look given: the split of a run cannot be checked without it.")
    found: dict[str, list[str]] = {}
    for kind, names, table in (("look", looks, splits["looks"]), ("clip", clips, splits["clips"])):
        for name in names:
            if name == "":
                raise SystemExit("a gesture has no animation clip name logged (clip is empty): its split is unknown, "
                                 "so the run is refused.")
            if name not in table:
                raise SystemExit(f"{kind} {name!r} is not listed in the v4 data splits (unknown is never assumed to be "
                                 f"development). Add it to configs/v4/data_splits.json first.")
            found.setdefault(table[name], []).append(f"{kind} {name}")
    if len(found) > 1:
        raise SystemExit("run mixes development and test data: " + "; ".join(
            f"{split}: {', '.join(items)}" for split, items in sorted(found.items())))
    split = next(iter(found))
    if split in splits["final_evaluation_splits"] and not final_evaluation:
        raise SystemExit(f"the run uses test data ({', '.join(found[split])}), final evaluation only. "
                         "Pass --final-evaluation for the one run with a frozen config.")
    if final_evaluation and split not in splits["final_evaluation_splits"]:
        raise SystemExit(f"--final-evaluation given, but the run uses {split} data ({', '.join(found[split])}).")
    if final_evaluation and splits.get("placeholder"):
        raise SystemExit("--final-evaluation refused: the look and clip names in configs/v4/data_splits.json are still "
                         "placeholders.")
    return split
