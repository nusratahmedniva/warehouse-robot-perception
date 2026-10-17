"""THUD synthetic-scene loader: metadata parsing, RGB/semantic matching and palette decoding.

Only the Unity Perception-style synthetic captures are supported here
(Synthetic_Scenes/<scene>/<static|dynamic>/Capture_N). The real-scene
captures use a different layout and are intentionally not handled yet.
"""

from __future__ import annotations

import json
import math
import os
import re
from dataclasses import asdict, dataclass
from pathlib import Path

import numpy as np
from PIL import Image

IGNORE_ID = 255
UNDECODED = -1  # palette index used for pixels that match no (or several) palette colours


# ---------------------------------------------------------------- configuration

def load_config(config_path: Path, dataset_root: str | None = None, capture: str | None = None) -> dict:
    """Read a JSON config and resolve the capture directory.

    Priority for the dataset root: --dataset-root argument, THUD_DATASET_ROOT
    environment variable, then the value in the config file.
    """
    config_path = Path(config_path).resolve()
    cfg = json.loads(config_path.read_text(encoding="utf-8"))
    root = dataset_root or os.environ.get("THUD_DATASET_ROOT") or cfg["dataset_root"]
    cfg["dataset_root"] = str(Path(root))
    if capture:
        cfg["capture"] = capture
    capture_dir = Path(cfg["capture"])
    if not capture_dir.is_absolute():
        capture_dir = Path(cfg["dataset_root"]) / capture_dir
    cfg["capture_dir"] = str(capture_dir)
    output_root = Path(cfg.get("output_root", "outputs"))
    if not output_root.is_absolute():
        output_root = config_path.parent.parent / output_root  # relative to robot_vision/
    cfg["output_root"] = str(output_root)
    cfg["config_path"] = str(config_path)
    return cfg


# ---------------------------------------------------------------- palette

@dataclass
class PaletteEntry:
    index: int
    name: str
    rgba_float: tuple[float, float, float, float]
    rgba_code: tuple[int, int, int, int]  # round(value * 255)


def load_semantic_palette(definitions_path: Path, annotation_id: str) -> list[PaletteEntry]:
    data = json.loads(Path(definitions_path).read_text(encoding="utf-8"))
    matches = [d for d in data["annotation_definitions"] if d["id"] == annotation_id]
    if len(matches) != 1:
        raise ValueError(f"Expected one '{annotation_id}' definition in {definitions_path}, found {len(matches)}")
    palette = []
    for i, spec in enumerate(matches[0]["spec"]):
        pv = spec["pixel_value"]
        rgba = tuple(float(pv[k]) for k in "rgba")
        palette.append(PaletteEntry(i, spec["label_name"], rgba, tuple(int(round(v * 255)) for v in rgba)))
    names = [p.name for p in palette]
    if len(set(names)) != len(names):
        raise ValueError(f"Duplicate class names in semantic palette: {names}")
    codes = [p.rgba_code for p in palette]
    if len(set(codes)) != len(codes):
        raise ValueError("Two semantic classes share the same colour code")
    return palette


def decode_semantic(rgba: np.ndarray, palette: list[PaletteEntry], tolerance: int) -> tuple[np.ndarray, dict]:
    """Map an RGBA semantic image to palette indices.

    Exact colour-code matches are tried first. Colours with no exact match may
    match a palette entry within +/- `tolerance` per channel (RGBA), but only if
    exactly one entry qualifies. Everything else becomes UNDECODED.
    """
    if rgba.ndim != 3 or rgba.shape[2] != 4:
        raise ValueError(f"Semantic image must be RGBA, got shape {rgba.shape}")
    codes = np.array([p.rgba_code for p in palette], dtype=np.int32)
    flat = rgba.reshape(-1, 4).astype(np.uint32)
    packed = (flat[:, 0] << 24) | (flat[:, 1] << 16) | (flat[:, 2] << 8) | flat[:, 3]
    colours, inverse, counts = np.unique(packed, return_inverse=True, return_counts=True)

    lut = np.full(len(colours), UNDECODED, dtype=np.int16)
    stats = {"exact": 0, "tolerance": 0, "unmatched": 0, "ambiguous": 0}
    unmatched_colours, ambiguous_colours, tolerance_colours = {}, {}, {}
    for i, (c, n) in enumerate(zip(colours.tolist(), counts.tolist())):
        rgba_c = np.array([(c >> 24) & 255, (c >> 16) & 255, (c >> 8) & 255, c & 255], dtype=np.int32)
        diff = np.abs(codes - rgba_c).max(axis=1)
        exact = np.flatnonzero(diff == 0)
        if len(exact) == 1:
            lut[i] = exact[0]
            stats["exact"] += n
            continue
        near = np.flatnonzero(diff <= tolerance)
        key = str(tuple(rgba_c.tolist()))
        if len(near) == 1:
            lut[i] = near[0]
            stats["tolerance"] += n
            tolerance_colours[key] = {"class": palette[near[0]].name, "pixels": n}
        elif len(near) > 1:
            stats["ambiguous"] += n
            ambiguous_colours[key] = {"candidates": [palette[j].name for j in near], "pixels": n}
        else:
            stats["unmatched"] += n
            unmatched_colours[key] = n
    stats["total"] = int(packed.size)
    stats["tolerance_colours"] = tolerance_colours
    stats["unmatched_colours"] = unmatched_colours
    stats["ambiguous_colours"] = ambiguous_colours
    return lut[inverse].reshape(rgba.shape[:2]), stats


# ---------------------------------------------------------------- frame records

@dataclass
class FrameRecord:
    sequence_id: str
    sensor_id: str
    capture_id: str
    step: int
    timestamp: float
    captures_file: str
    rgb_metadata_path: str
    semantic_metadata_path: str
    rgb_path: str
    semantic_path: str

    def to_dict(self) -> dict:
        return asdict(self)


def _number_in_name(name: str) -> int:
    m = re.search(r"(\d+)(?=\.[^.]+$)", name)
    return int(m.group(1)) if m else -1


def _captures_files(label_dir: Path) -> list[Path]:
    # Numeric ordering of captures_NNN.json; the final record order comes from metadata anyway.
    return sorted(label_dir.glob("captures_*.json"), key=lambda p: _number_in_name(p.name))


def load_frame_records(cfg: dict) -> tuple[list[FrameRecord], dict]:
    """Parse all captures_*.json files and match RGB + semantic files via metadata.

    Returns the ordered frame records for the configured RGB sensor and a
    dictionary of problems/warnings found while matching.
    """
    capture_dir = Path(cfg["capture_dir"])
    label_dir = capture_dir / cfg["label_dir"]
    rgb_dir = capture_dir / cfg["rgb_dir"]
    sem_dir = capture_dir / cfg["semantic_dir"]
    sensor_id = cfg["rgb_sensor_id"]
    sem_ann_id = cfg["semantic_annotation_id"]

    for d in (capture_dir, label_dir, rgb_dir, sem_dir):
        if not d.is_dir():
            raise FileNotFoundError(f"Required folder not found: {d}")
    files = _captures_files(label_dir)
    if not files:
        raise FileNotFoundError(f"No captures_*.json files in {label_dir}")

    issues = {
        "records_without_semantic_annotation": [],
        "missing_rgb_files": [],
        "missing_semantic_files": [],
        "duplicate_records": [],
        "duplicate_rgb_basenames": [],
        "duplicate_semantic_basenames": [],
        "other_sensors_sharing_rgb_basenames": {},
        "warnings": [],
    }
    sensors_seen: dict[str, int] = {}
    selected: list[FrameRecord] = []
    other_sensor_basenames: dict[str, set[str]] = {}

    for f in files:
        for cap in json.loads(f.read_text(encoding="utf-8"))["captures"]:
            sid = cap["sensor"]["sensor_id"]
            sensors_seen[sid] = sensors_seen.get(sid, 0) + 1
            rgb_meta = cap["filename"]
            if sid != sensor_id:
                other_sensor_basenames.setdefault(sid, set()).add(Path(rgb_meta).name)
                continue
            sem = [a for a in cap.get("annotations", []) if a.get("id") == sem_ann_id]
            if len(sem) != 1 or not sem[0].get("filename"):
                issues["records_without_semantic_annotation"].append(
                    {"step": cap["step"], "file": f.name, "count": len(sem)})
                continue
            rec = FrameRecord(
                sequence_id=cap["sequence_id"], sensor_id=sid, capture_id=cap["id"],
                step=int(cap["step"]), timestamp=float(cap["timestamp"]), captures_file=f.name,
                rgb_metadata_path=rgb_meta, semantic_metadata_path=sem[0]["filename"],
                # The dataset copy on disk flattens Unity's per-run "RGB<uuid>/" and
                # "SemanticSegmentation<uuid>/" folders, so match by basename.
                rgb_path=str(rgb_dir / Path(rgb_meta).name),
                semantic_path=str(sem_dir / Path(sem[0]["filename"]).name),
            )
            selected.append(rec)

    if sensor_id not in sensors_seen:
        raise ValueError(f"Sensor '{sensor_id}' not found. Sensors in metadata: {sorted(sensors_seen)}")

    # Uniqueness checks: reject duplicates rather than picking one silently.
    def dupes(key):
        seen, out = {}, []
        for r in selected:
            k = key(r)
            if k in seen:
                out.append(str(k))
            seen[k] = r
        return out

    issues["duplicate_records"] = dupes(lambda r: (r.sequence_id, r.step))
    issues["duplicate_rgb_basenames"] = dupes(lambda r: Path(r.rgb_path).name)
    issues["duplicate_semantic_basenames"] = dupes(lambda r: Path(r.semantic_path).name)

    selected_rgb = {Path(r.rgb_path).name for r in selected}
    for sid, names in other_sensor_basenames.items():
        shared = len(names & selected_rgb)
        if shared:
            issues["other_sensors_sharing_rgb_basenames"][sid] = shared
            issues["warnings"].append(
                f"Sensor '{sid}' records also use {shared} of the same RGB basenames. The flattened "
                f"'{cfg['rgb_dir']}' folder cannot show which sensor rendered each file; "
                f"'{sensor_id}' is used because it carries the semantic annotations.")

    # Order: sequences by their first timestamp, frames by metadata step.
    first_ts: dict[str, float] = {}
    for r in selected:
        first_ts[r.sequence_id] = min(first_ts.get(r.sequence_id, math.inf), r.timestamp)
    selected.sort(key=lambda r: (first_ts[r.sequence_id], r.sequence_id, r.step))

    for r in selected:
        if not Path(r.rgb_path).is_file():
            issues["missing_rgb_files"].append(r.rgb_path)
        if not Path(r.semantic_path).is_file():
            issues["missing_semantic_files"].append(r.semantic_path)

    # Files present on disk that no selected record references.
    referenced_sem = {Path(r.semantic_path).name for r in selected}
    issues["unreferenced_rgb_files"] = sorted(
        (p.name for p in rgb_dir.iterdir() if p.is_file() and p.name not in selected_rgb), key=_number_in_name)
    issues["unreferenced_semantic_files"] = sorted(
        (p.name for p in sem_dir.iterdir() if p.is_file() and p.name not in referenced_sem), key=_number_in_name)

    issues["sensors_in_metadata"] = sensors_seen
    issues["captures_files"] = [f.name for f in files]
    return selected, issues


def sequence_checks(records: list[FrameRecord]) -> dict:
    """Step continuity and timestamp monotonicity per sequence (metadata only)."""
    out = {}
    by_seq: dict[str, list[FrameRecord]] = {}
    for r in records:
        by_seq.setdefault(r.sequence_id, []).append(r)
    for seq, recs in by_seq.items():
        steps = [r.step for r in recs]
        ts = [r.timestamp for r in recs]
        missing = sorted(set(range(min(steps), max(steps) + 1)) - set(steps))
        non_finite = [r.step for r in recs if not math.isfinite(r.timestamp)]
        not_increasing = [recs[i].step for i in range(1, len(recs)) if not ts[i] > ts[i - 1]]
        out[seq] = {
            "frames": len(recs),
            "first_step": steps[0], "last_step": steps[-1],
            "first_timestamp": ts[0], "last_timestamp": ts[-1],
            "missing_steps": missing,
            "non_finite_timestamps": non_finite,
            "non_increasing_timestamps_at_steps": not_increasing,
        }
    return out


def blocking_problems(issues: dict, seq_checks: dict) -> list[str]:
    """Problems that make the matched frame list unsafe to use."""
    problems = []
    for key in ("duplicate_records", "duplicate_rgb_basenames", "duplicate_semantic_basenames"):
        if issues[key]:
            problems.append(f"{key}: {issues[key][:5]}")
    for seq, c in seq_checks.items():
        if c["non_finite_timestamps"]:
            problems.append(f"sequence {seq}: non-finite timestamps at steps {c['non_finite_timestamps'][:5]}")
        if c["non_increasing_timestamps_at_steps"]:
            problems.append(f"sequence {seq}: timestamps not strictly increasing at steps "
                            f"{c['non_increasing_timestamps_at_steps'][:5]}")
    return problems


def usable_records(records: list[FrameRecord], issues: dict) -> list[FrameRecord]:
    """Records whose RGB and semantic files both exist on disk."""
    missing = set(issues["missing_rgb_files"]) | set(issues["missing_semantic_files"])
    return [r for r in records if r.rgb_path not in missing and r.semantic_path not in missing]


# ---------------------------------------------------------------- image loading

def load_rgb(path: str | Path) -> tuple[Image.Image, str]:
    """Load an RGB frame as a PIL RGB image (alpha dropped). Returns (image, original mode)."""
    with Image.open(path) as im:
        mode = im.mode
        im.load()
        return im.convert("RGB"), mode


def load_semantic_rgba(path: str | Path) -> np.ndarray:
    with Image.open(path) as im:
        if im.mode != "RGBA":
            im = im.convert("RGBA")
        return np.array(im)


def build_reference_lut(palette: list[PaletteEntry], reference_mapping: dict[str, list[str]],
                        class_names: list[str]) -> tuple[np.ndarray, dict]:
    """Palette index -> project class ID. Known palette classes not listed map to 'other'."""
    name_to_id = {n: i for i, n in enumerate(class_names)}
    lut = np.full(len(palette), name_to_id["other"], dtype=np.uint8)
    resolved = {}
    used = set()
    for project_name, dataset_names in reference_mapping.items():
        for dn in dataset_names:
            hits = [p for p in palette if p.name == dn]
            if len(hits) != 1:
                raise ValueError(f"Reference mapping name '{dn}' not found exactly once in the dataset palette "
                                 f"{[p.name for p in palette]}")
            lut[hits[0].index] = name_to_id[project_name]
            used.add(hits[0].name)
            resolved[hits[0].name] = project_name
    for p in palette:
        if p.name not in used:
            resolved[p.name] = "other"
    return lut, resolved


def reference_to_project(palette_idx: np.ndarray, lut: np.ndarray) -> np.ndarray:
    out = np.full(palette_idx.shape, IGNORE_ID, dtype=np.uint8)
    valid = palette_idx != UNDECODED
    out[valid] = lut[palette_idx[valid]]
    return out
