"""The clip-role split of the avatar experiment (AUDIT.md 16.31.1 D6, 16.31.5 item 4). EVALUATION CODE; inference code never imports it.

Each recording of the experiment is one row of Unity's recordings.jsonl (look, command, distance_m, arm, take, clip, name; `name` is the
recording name the look-check report uses). A take's clip, and so its clip role (development or test, from configs/v4/data_splits.json), comes
from that row and from nowhere else:
  clip      a Play gesture take with a clip listed in data_splits.json: its clip role is the clip's role
  posed     an Edit take (clip "" and pose "posed"): excluded from the clip-role split, counted
  no_gesture_clip   a NONE take (nobody gestures): excluded, counted
  missing_clip      a gesture take with no clip and not posed: NOT evaluated (counted and listed), never guessed
Refused (SystemExit): a clip that is not listed (unknown is never assumed), a recording without a name, two rows with the same name, a posed
row that names a clip, a value for a take at another distance than the one asked.

split_by_clip_role takes one per-take share per recording name (the look-check report's per-take shares: the join is the reporting step's) for ONE
distance, never pooled over distances (the 2 m and the 4 m camera see the same take, so a pooled cell would count it twice), and gives, per clip
role, the number of takes, the mean over takes and the bootstrap interval of AUDIT.md 16.31.1 D5: configs/v4/analysis.json `bootstrap`
(2000 resamples, seed 1, percentiles 2.5 and 97.5; numpy's default_rng), takes resampled with replacement within each look so the look composition stays fixed.
"""

from __future__ import annotations

import json
from collections import defaultdict
from pathlib import Path

import data_splits_v4 as ds

HERE = Path(__file__).resolve().parent
ANALYSIS = HERE / "configs" / "v4" / "analysis.json"
ROLES = ("development", "test")
POSED = "posed"


def load_recordings(path: str | Path) -> list[dict]:
    """The rows of a recordings.jsonl (blank lines skipped)."""
    rows = []
    for n, line in enumerate(Path(path).read_text(encoding="utf-8").splitlines(), 1):
        if line.strip():
            try:
                rows.append(json.loads(line))
            except ValueError as e:
                raise SystemExit(f"{path}: line {n} is not JSON: {e}") from None
    return rows


def bootstrap_settings(path: str | Path = ANALYSIS) -> dict:
    """n_resamples, seed and percentiles of configs/v4/analysis.json `bootstrap` (the avatar experiment's own block repeats them)."""
    b = json.loads(Path(path).read_text(encoding="utf-8"))["bootstrap"]
    return {"n_resamples": int(b["n_resamples"]), "seed": int(b["seed"]), "percentiles": [float(x) for x in b["percentiles"]]}


def classify(rows: list[dict], splits: dict | None = None) -> dict[str, dict]:
    """name -> {"status", "clip", "clip_role", "look", "command", "distance_m", "arm"} for every recording (see the module text)."""
    splits = splits if splits is not None else ds.load()
    out: dict[str, dict] = {}
    for r in rows:
        name = r.get("name")
        if not name:
            raise SystemExit("a recording has no name: it cannot be joined to the look-check report")
        if name in out:
            raise SystemExit(f"two recordings are named {name!r}: the clip of a take must be unique")
        clip = r.get("clip") or ""
        info = {"clip": clip, "clip_role": None, "look": r.get("look"), "command": r.get("command"), "distance_m": r.get("distance_m"),
                "arm": r.get("arm")}
        if r.get("pose") == POSED:
            if clip:
                raise SystemExit(f"recording {name!r} is posed but names the clip {clip!r}: a posed take shows no animation clip")
            info["status"] = "posed"
        elif r.get("command") == "NONE":
            info["status"] = "no_gesture_clip"
        elif clip:
            if clip not in splits["clips"]:
                raise SystemExit(f"clip {clip!r} of recording {name!r} is not listed in the v4 data splits (unknown is never assumed)")
            info["status"], info["clip_role"] = "clip", splits["clips"][clip]
        else:
            info["status"] = "missing_clip"
        out[name] = info
    return out


def mean_with_bootstrap(values_by_look: dict[str, list[float]], settings: dict | None = None) -> dict:
    """The mean over takes (each take once) and its bootstrap interval; takes are resampled with replacement within each look (a look is a
    fixed avatar, so the look composition of the cell does not change). numpy's default_rng(seed), n_resamples and percentiles of
    configs/v4/analysis.json. No takes: mean None, interval None (not evaluated)."""
    import numpy as np
    settings = settings or bootstrap_settings()
    looks = {k: np.asarray(v, dtype=float) for k, v in sorted(values_by_look.items()) if len(v)}
    n = sum(len(v) for v in looks.values())
    if n == 0:
        return {"takes": 0, "mean": None, "interval": None}
    mean = float(sum(v.sum() for v in looks.values()) / n)
    rng = np.random.default_rng(settings["seed"])
    total = np.zeros(settings["n_resamples"])
    for v in looks.values():
        total += v[rng.integers(0, len(v), size=(settings["n_resamples"], len(v)))].sum(axis=1)
    means = total / n
    lo, hi = (float(np.percentile(means, q)) for q in settings["percentiles"])
    return {"takes": n, "mean": mean, "interval": [lo, hi]}


def split_by_clip_role(take_values: dict[str, float], rows: list[dict], distance_m: float, splits: dict | None = None,
                       settings: dict | None = None) -> dict:
    """The clip-role split of one per-take measure at ONE distance. take_values: recording name -> share in 0..1."""
    splits = splits if splits is not None else ds.load()
    cls = classify(rows, splits)
    per_role: dict[str, dict[str, list[float]]] = {r: defaultdict(list) for r in ROLES}
    excluded = {"posed": [], "no_gesture_clip": []}
    not_evaluated = {"missing_clip": [], "no_recording": []}
    for name, value in sorted(take_values.items()):
        if isinstance(value, bool) or not isinstance(value, (int, float)) or not 0.0 <= float(value) <= 1.0:
            raise SystemExit(f"take {name!r}: the value {value!r} is not a share between 0 and 1")
        info = cls.get(name)
        if info is None:
            not_evaluated["no_recording"].append(name)
            continue
        if info["distance_m"] is None or abs(float(info["distance_m"]) - float(distance_m)) > 1e-6:
            raise SystemExit(f"take {name!r} was recorded at {info['distance_m']} m, not {distance_m} m: the clip-role split is made per "
                             "distance (the 2 m and the 4 m camera see the same take)")
        if info["status"] == "clip":
            per_role[info["clip_role"]][info["look"]].append(float(value))
        elif info["status"] == "missing_clip":
            not_evaluated["missing_clip"].append(name)
        else:
            excluded[info["status"]].append(name)
    out = {"distance_m": float(distance_m), "roles": {r: mean_with_bootstrap(per_role[r], settings) for r in ROLES},
           "excluded": {k: {"takes": len(v), "names": v} for k, v in excluded.items()},
           "not_evaluated": {k: {"takes": len(v), "names": v} for k, v in not_evaluated.items()}}
    out["takes_by_look"] = {r: {look: len(v) for look, v in sorted(per_role[r].items())} for r in ROLES}
    return out
