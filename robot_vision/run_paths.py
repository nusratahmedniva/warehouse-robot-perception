"""Portable paths in run outputs.

Run folders never store absolute paths. A path is stored as a root token plus a POSIX relative path:
    {dataset_root}/Synthetic_Scenes/Office/dynamic/Capture_1/RGB/rgb_2.png
    {output_root}/seg_Office_dynamic_Capture_1_300f_20261010_032646
    {project_root}/configs/office.json
and resolved when read against the roots configured on the current machine:
- dataset_root: --dataset-root, THUD_DATASET_ROOT or configs/office.json (thud_data.load_config)
- output_root:  output_root in the config (default robot_vision/outputs)
- project_root: the robot_vision folder (this file's folder)

Legacy run folders written before this convention hold absolute paths; migrate_run_paths.py rewrites them.
"""

from __future__ import annotations

import json
import re
from pathlib import Path, PurePath, PurePosixPath, PureWindowsPath

PROJECT_ROOT = Path(__file__).resolve().parent
ORDER = ("output_root", "dataset_root", "project_root")  # most specific first (outputs live inside the project)
TOKEN_RE = re.compile(r"^\{(\w+)\}(?:/(.*))?$")
WIN_ABS_RE = re.compile(r"(?<![A-Za-z0-9])[A-Za-z]:[\\/](?!/)[^\s\"'<>|*?,;]*")  # not URLs (https://)


def make_roots(dataset_root: str | Path | None = None, output_root: str | Path | None = None,
               project_root: str | Path | None = None) -> dict[str, Path]:
    rts = {"project_root": Path(project_root) if project_root else PROJECT_ROOT}
    if dataset_root:
        rts["dataset_root"] = Path(dataset_root)
    if output_root:
        rts["output_root"] = Path(output_root)
    return rts


def roots_from_config(cfg: dict) -> dict[str, Path]:
    """Roots from a thud_data.load_config() result."""
    return make_roots(cfg.get("dataset_root"), cfg.get("output_root"))


def _pure(p: str | PurePath) -> PurePath:
    s = str(p)
    return PureWindowsPath(s) if re.match(r"^[A-Za-z]:[\\/]", s) or "\\" in s else PurePosixPath(s)


def relative_token(path: str | PurePath, rts: dict) -> str | None:
    """Token form of an absolute path under one of the roots, else None. Works for Windows paths on any OS."""
    p = _pure(path)
    for name in ORDER:
        if name not in rts:
            continue
        root = _pure(rts[name])
        if type(root) is not type(p):
            continue
        try:
            rel = p.relative_to(root)
        except ValueError:
            continue
        rel_s = rel.as_posix()
        return f"{{{name}}}" if rel_s in ("", ".") else f"{{{name}}}/{rel_s}"
    return None


def store(path: str | Path, rts: dict, external_ok: bool = False) -> str:
    """Portable string for a path written into a run folder. Never returns an absolute path."""
    s = str(path)
    if TOKEN_RE.match(s):
        return s
    p = Path(s) if Path(s).is_absolute() else Path(s).absolute()
    tok = relative_token(p, rts)
    if tok is not None:
        return tok
    if external_ok:
        return f"<outside configured roots>/{p.name}"
    raise ValueError(f"{p} is not under any configured root {sorted(rts)}")


def resolve(value: str, rts: dict) -> Path:
    """Path on this machine for a stored value (token form; legacy absolute paths only if they exist)."""
    m = TOKEN_RE.match(value)
    if m:
        name, rest = m.group(1), m.group(2) or ""
        if name not in rts:
            raise KeyError(f"Root {{{name}}} is not configured (needed for {value})")
        return rts[name] / rest if rest else rts[name]
    p = Path(value)
    if not p.is_absolute():
        return rts["project_root"] / p
    if p.exists():
        return p
    raise FileNotFoundError(f"Legacy absolute path not found on this machine: {value}. "
                            f"Run migrate_run_paths.py on the run folder.")


def portable_text(text: str, rts: dict) -> tuple[str, list[str]]:
    """Replace absolute paths under the roots inside free text. Returns (text, unmapped absolute paths)."""
    unmapped = []

    def win(m):
        tok = relative_token(m.group(0), rts)
        if tok is None:
            unmapped.append(m.group(0))
            return m.group(0)
        return tok

    out = WIN_ABS_RE.sub(win, text)
    for name in ORDER:  # POSIX roots (e.g. a macOS dataset root)
        root = rts.get(name)
        if root is not None and isinstance(_pure(root), PurePosixPath) and str(root).startswith("/"):
            out = re.sub(re.escape(str(root).rstrip("/")) + r"(?=/|\b)", "{" + name + "}", out)
    return out, unmapped


def portable(obj, rts: dict):
    """For writers: tokenise every path in a JSON-like object; absolute paths outside the roots are reduced to
    '<outside configured roots>/<file name>', so a run folder never contains an absolute path."""
    unmapped: list[str] = []
    out = portable_posix_outside(portable_obj(obj, rts, unmapped))
    if not unmapped:
        return out

    def redact(o):
        if isinstance(o, dict):
            return {k: redact(v) for k, v in o.items()}
        if isinstance(o, list):
            return [redact(v) for v in o]
        if isinstance(o, str):
            return WIN_ABS_RE.sub(lambda m: f"<outside configured roots>/{_pure(m.group(0)).name}", o)
        return o
    return redact(out)


POSIX_ABS_RE = re.compile(r"(?<![\w.:/}>])/(?:[\w.\-]+/)+[\w.\-]+")


def portable_posix_outside(obj):
    """Reduce POSIX absolute paths left after tokenising (outside every root) to their file name."""
    if isinstance(obj, dict):
        return {k: portable_posix_outside(v) for k, v in obj.items()}
    if isinstance(obj, list):
        return [portable_posix_outside(v) for v in obj]
    if isinstance(obj, str) and obj.count("/") >= 2:
        return POSIX_ABS_RE.sub(lambda m: f"<outside configured roots>/{PurePosixPath(m.group(0)).name}", obj)
    return obj


def portable_obj(obj, rts: dict, unmapped: list[str] | None = None):
    """Recursively apply portable_text to every string in a JSON-like object."""
    unmapped = [] if unmapped is None else unmapped
    if isinstance(obj, PurePath):
        obj = str(obj)
    if isinstance(obj, tuple):
        obj = list(obj)
    if isinstance(obj, dict):
        return {k: portable_obj(v, rts, unmapped) for k, v in obj.items()}
    if isinstance(obj, list):
        return [portable_obj(v, rts, unmapped) for v in obj]
    if isinstance(obj, str):
        s, u = portable_text(obj, rts)
        unmapped.extend(u)
        return s
    return obj


# ---------------------------------------------------------------- roots of the current run (used by writers)

_ACTIVE: dict[str, Path] = {"project_root": PROJECT_ROOT}


def set_active_roots(rts: dict) -> None:
    """Register the roots of the run being written; every dumps() call then stores paths relative to them."""
    _ACTIVE.clear()
    _ACTIVE.update({"project_root": PROJECT_ROOT, **rts})


def active_roots() -> dict[str, Path]:
    return dict(_ACTIVE)


def dumps(obj, **kwargs) -> str:
    """json.dumps with every path made portable (see portable())."""
    return json.dumps(portable(obj, _ACTIVE), **kwargs)
