"""v4 data splits: avatar looks and animation clips (configs/v4/data_splits.json). The v3 capture splits stay in
data_splits.py and are not touched.

Development looks and clips are used to set thresholds; test looks and clips are never used in development. guard_run
refuses a run that mixes the two, a look or clip that is not listed, and a final evaluation while the names in the
config are placeholders. Like data_splits.guard it raises SystemExit.

Third role (AUDIT.md 16.31, 16.31.2, 2026-11-21): a LOOK may have the role "avatar_experiment": it is never used for navigation,
development or the A/B finals, it is for the evaluation of the avatar experiment only, and no value is ever set from it. guard_run
refuses such a look in every mode, alone or mixed. The avatar experiment has its own guard, guard_avatar_experiment: every name listed
(any role), the session an OFFICIAL avatar-experiment run (run_info.json avatar_experiment_part 'edit' or 'play' and the run-once markers,
AUDIT.md 16.31.6), the frozen hashes matching; the development/test mixing rule does not apply to it. A clip is only development or test.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Iterable

DEFAULT = Path(__file__).resolve().parent / "configs" / "v4" / "data_splits.json"
SPLITS = ("development", "test")
AVATAR_ROLE = "avatar_experiment"
LOOK_ROLES = SPLITS + (AVATAR_ROLE,)
KIND_GROUPS = ("stylised_human", "realistic_human", "anime", "cartoon_non_human")


def load(path: str | Path | None = None) -> dict:
    splits = json.loads(Path(path or DEFAULT).read_text(encoding="utf-8"))
    problems = check_config(splits)
    if problems:
        raise ValueError("v4 data splits config: " + "; ".join(problems))
    return splits


def check_config(splits: dict) -> list[str]:
    """Problems in the config itself: unknown split names, no development or test entry, wrong final splits. A look may also have the
    role avatar_experiment (it needs a kind group); a clip may not."""
    problems = []
    for kind in ("looks", "clips"):
        table = splits.get(kind)
        if not isinstance(table, dict) or not table:
            problems.append(f"no {kind}")
            continue
        allowed = LOOK_ROLES if kind == "looks" else SPLITS
        for name, split in table.items():
            if split not in allowed:
                problems.append(f"{kind} {name!r} has split {split!r} (expected one of {allowed})")
        for want in SPLITS:
            if want not in table.values():
                problems.append(f"{kind} has no {want} entry")
    groups = splits.get("kind_groups", {})
    if not isinstance(groups, dict):
        problems.append("kind_groups is not a table")
        groups = {}
    for name, group in groups.items():
        if name not in splits.get("looks", {}):
            problems.append(f"kind_groups names {name!r}, which is not a listed look")
        if group not in KIND_GROUPS:
            problems.append(f"kind_groups {name!r} has group {group!r} (expected one of {KIND_GROUPS})")
    for name, role in splits.get("looks", {}).items():
        if role == AVATAR_ROLE and name not in groups:
            problems.append(f"look {name!r} is an avatar_experiment look and has no kind group")
    if splits.get("final_evaluation_splits") != ["test"]:
        problems.append("final_evaluation_splits must be ['test']")
    return problems


def split_of_look(look: str, splits: dict) -> str | None:
    """The role of a look ('development', 'test' or 'avatar_experiment'), None when not listed. Not a split to evaluate on: use guard_run."""
    return splits["looks"].get(look)


def split_of_clip(clip: str, splits: dict) -> str | None:
    return splits["clips"].get(clip)


def guard_run(looks: Iterable[str], clips: Iterable[str], final_evaluation: bool = False,
              splits: dict | None = None) -> str:
    """The split ('development' or 'test') of a run with these avatar looks and gesture animation clips, or SystemExit.

    looks: the looks of the workers in the run. clips: the animation clip names of its gestures (a gesture with no
    logged name is "" and refused). Refused: nothing listed; an unlisted look or clip; **a look with the role avatar_experiment,
    in every mode** (AUDIT.md 16.31.2: it is for the avatar experiment only; a lone third role would otherwise be returned as
    the run's split); a mix of development and test (looks with clips included); test without final_evaluation;
    final_evaluation on development; final_evaluation while the config's names are placeholders."""
    splits = splits if splits is not None else load()
    looks, clips = sorted(set(looks)), sorted(set(clips))
    if not looks:
        raise SystemExit("no avatar look given: the split of a run cannot be checked without it.")
    avatar = [n for n in looks if splits["looks"].get(n) == AVATAR_ROLE]
    if avatar:
        raise SystemExit(f"look {', '.join(avatar)} has the role avatar_experiment: it is for the avatar experiment only and is refused in "
                         "navigation, development and the A/B finals (data_splits_v4.guard_avatar_experiment is its guard).")
    found: dict[str, list[str]] = {}
    for kind, names, table in (("look", looks, splits["looks"]), ("clip", clips, splits["clips"])):
        for name in names:
            if name == "":
                raise SystemExit("a gesture has no animation clip name logged (clip is empty): its split is unknown, "
                                 "so the run is refused.")
            if name not in table:
                raise SystemExit(f"{kind} {name!r} is not listed in the v4 data splits (unknown is never assumed to be "
                                 f"development). Add it to configs/v4/data_splits.json first.")
            if table[name] == AVATAR_ROLE:       # a clip cannot have it (check_config); a hand-edited table is refused here too
                raise SystemExit(f"{kind} {name!r} has the role avatar_experiment: refused outside the avatar experiment.")
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


AVATAR_PARTS = ("edit", "play")
AVATAR_RUN_INFO = "run_info.json"
AVATAR_STARTED = "AVATAR_EXPERIMENT_STARTED.json"
AVATAR_DONE = "AVATAR_EXPERIMENT_DONE.json"


def load_avatar_session(folder: str | Path) -> dict:
    """The session record of an avatar-experiment run folder (Unity's look_check_play_ab_<time>/ or look_check_ab_<time>/): run_info.json and the
    two run-once markers, each None when absent or unreadable. AUDIT.md 16.31.6 decision 1 (Q6 closed by Nusrat, 2026-11-21)."""
    folder = Path(folder)

    def read(name):
        try:
            return json.loads((folder / name).read_text(encoding="utf-8"))
        except (OSError, ValueError):
            return None

    return {"folder": folder.name, "run_info": read(AVATAR_RUN_INFO), "started": read(AVATAR_STARTED), "done": read(AVATAR_DONE)}


def avatar_session_problems(session: dict | None) -> list[str]:
    """What is wrong with the session record as an OFFICIAL avatar-experiment run (empty = fine): run_info.json with avatar_experiment_part
    'edit' or 'play' ('' = an engineering check, refused as not official), both markers with the same part, the same commit in run_info and
    both markers, and the markers' folder equal to the run folder's name."""
    if not isinstance(session, dict):
        return ["no session record: the avatar guard needs the run folder's run_info.json and markers"]
    info, started, done = session.get("run_info"), session.get("started"), session.get("done")
    if not isinstance(info, dict):
        return [f"no {AVATAR_RUN_INFO} in the run folder: the session is not marked as an avatar-experiment session"]
    part = info.get("avatar_experiment_part")
    if part == "":
        return ["avatar_experiment_part is empty in run_info.json: this is an engineering check, not an official avatar-experiment run"]
    if part not in AVATAR_PARTS:
        return [f"avatar_experiment_part {part!r} in run_info.json is not one of {AVATAR_PARTS}"]
    out = []
    for name, marker, kind in ((AVATAR_STARTED, started, "started"), (AVATAR_DONE, done, "done")):
        if not isinstance(marker, dict):
            out.append(f"no {name}: " + ("the run did not start as an official run" if kind == "started" else
                                         "the part did not finish (an interrupted part follows the interruption rule, which is not built)"))
            continue
        if marker.get("marker") != kind:
            out.append(f"{name} says marker {marker.get('marker')!r}, expected {kind!r}")
        if marker.get("avatar_experiment_part") != part:
            out.append(f"{name} has avatar_experiment_part {marker.get('avatar_experiment_part')!r} but run_info.json has {part!r}")
        if marker.get("git_commit") != info.get("git_commit"):
            out.append(f"{name} has git_commit {marker.get('git_commit')!r} but run_info.json has {info.get('git_commit')!r}")
        if session.get("folder") and marker.get("folder") != session["folder"]:
            out.append(f"{name} names the folder {marker.get('folder')!r}, not {session['folder']!r}")
    return out


def guard_avatar_experiment(looks: Iterable[str], clips: Iterable[str], session: dict, splits: dict | None = None,
                            repo: Path | None = None) -> dict:
    """The guard of the avatar experiment (AUDIT.md 16.31 decision b, 16.31.2, wired to the session marker by 16.31.6). SystemExit unless:
    the session record (load_avatar_session) shows an OFFICIAL run (avatar_experiment_part 'edit' or 'play', both run-once markers, one commit),
    the v4 configs are frozen with every hash matching (the experiment runs after the freeze, so nothing can be tuned on it), and every look and
    clip name is listed in data_splits.json, in ANY role (an empty clip name is refused; unknown is never assumed). The development/test
    mixing rule of guard_run does not apply: a group shows every clip of a command on every look. Returns {"part", "commit", "status",
    "look_roles", "clip_roles", "kind_groups"}; the results are reported split by look role and clip role, not refused for mixing."""
    import freeze_v4 as fz
    problems = avatar_session_problems(session)
    if problems:
        raise SystemExit("the session is not an official avatar-experiment session: " + "; ".join(problems))
    fz.require_frozen(repo if repo is not None else fz.REPO)
    splits = splits if splits is not None else load()
    looks, clips = sorted(set(looks)), sorted(set(clips))
    if not looks:
        raise SystemExit("no avatar look given: the avatar experiment cannot be checked without it.")
    out = {"part": session["run_info"]["avatar_experiment_part"], "commit": session["run_info"].get("git_commit"),
           "status": (session["done"] or {}).get("status", ""), "look_roles": {}, "clip_roles": {}, "kind_groups": {}}
    for kind, names, table, key in (("look", looks, splits["looks"], "look_roles"), ("clip", clips, splits["clips"], "clip_roles")):
        for name in names:
            if name == "":
                raise SystemExit("a gesture has no animation clip name (clip is empty): its role is unknown, so the session is refused.")
            if name not in table:
                raise SystemExit(f"{kind} {name!r} is not listed in the v4 data splits (unknown is never assumed). Add it to "
                                 "configs/v4/data_splits.json first, before the freeze.")
            out[key][name] = table[name]
    out["kind_groups"] = {n: splits.get("kind_groups", {}).get(n) for n in looks}
    return out
