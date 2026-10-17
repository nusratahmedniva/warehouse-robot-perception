"""Audit a THUD synthetic capture: metadata matching, file checks and palette-decoding coverage.

Usage:
    python audit_dataset.py --config configs/office.json --frames 3
"""

from __future__ import annotations

import argparse
import json
from datetime import datetime
from pathlib import Path

import numpy as np

import data_splits as ds
import run_paths as rp
import thud_data as td


def audit_capture(cfg: dict, start: int, count: int, decode: bool = True) -> tuple[dict, list[td.FrameRecord]]:
    """Validate the capture and the requested frame window.

    Returns (report, selected_records). report["ok"] is False if anything
    blocks safe use of the selected frames; report["problems"] says why.
    """
    capture_dir = Path(cfg["capture_dir"])
    palette = td.load_semantic_palette(capture_dir / cfg["annotation_definitions"], cfg["semantic_annotation_id"])
    records, issues = td.load_frame_records(cfg)
    seq = td.sequence_checks(records) if records else {}
    problems = td.blocking_problems(issues, seq)

    usable = td.usable_records(records, issues)
    selected = usable[start:] if count is None else usable[start:start + count]
    if count is not None and len(selected) < count:
        problems.append(f"Requested {count} frames from index {start}, but only {len(selected)} matched "
                        f"frames are available (total usable: {len(usable)}).")

    report = {
        "created": datetime.now().isoformat(timespec="seconds"),
        "capture_dir": str(capture_dir),
        "rgb_sensor_id": cfg["rgb_sensor_id"],
        "semantic_annotation_id": cfg["semantic_annotation_id"],
        "captures_files": issues["captures_files"],
        "sensors_in_metadata": issues["sensors_in_metadata"],
        "matched_frames_total": len(records),
        "usable_frames_total": len(usable),
        "sequences": seq,
        "missing_rgb_files": issues["missing_rgb_files"],
        "missing_semantic_files": issues["missing_semantic_files"],
        "records_without_semantic_annotation": issues["records_without_semantic_annotation"],
        "unreferenced_rgb_files": issues["unreferenced_rgb_files"],
        "unreferenced_semantic_files": issues["unreferenced_semantic_files"],
        "duplicate_records": issues["duplicate_records"],
        "duplicate_rgb_basenames": issues["duplicate_rgb_basenames"],
        "duplicate_semantic_basenames": issues["duplicate_semantic_basenames"],
        "warnings": issues["warnings"],
        "semantic_classes": [{"index": p.index, "name": p.name, "rgba_float": p.rgba_float,
                              "rgba_code": p.rgba_code} for p in palette],
        "palette_tolerance": cfg["palette_tolerance"],
        "selection": {"start_index": start, "requested": count, "selected": len(selected)},
        "selected_frames": [],
    }
    if selected:
        report["selection"].update({
            "first_step": selected[0].step, "last_step": selected[-1].step,
            "first_timestamp": selected[0].timestamp, "last_timestamp": selected[-1].timestamp,
        })

    if decode:
        totals = {"exact": 0, "tolerance": 0, "unmatched": 0, "ambiguous": 0, "total": 0}
        class_pixels = np.zeros(len(palette), dtype=np.int64)
        sizes = set()
        for r in selected:
            entry = {"step": r.step, "timestamp": r.timestamp, "rgb": Path(r.rgb_path).name,
                     "semantic": Path(r.semantic_path).name}
            try:
                rgb, rgb_mode = td.load_rgb(r.rgb_path)
                sem = td.load_semantic_rgba(r.semantic_path)
            except Exception as exc:  # report undecodable files instead of stopping the audit
                entry["error"] = f"decode failed: {exc}"
                problems.append(f"step {r.step}: {entry['error']}")
                report["selected_frames"].append(entry)
                continue
            entry["rgb_size_wh"] = list(rgb.size)
            entry["rgb_mode"] = rgb_mode
            entry["semantic_size_wh"] = [sem.shape[1], sem.shape[0]]
            if tuple(entry["rgb_size_wh"]) != tuple(entry["semantic_size_wh"]):
                problems.append(f"step {r.step}: RGB {rgb.size} and semantic {sem.shape[1::-1]} sizes differ")
            sizes.add(tuple(entry["rgb_size_wh"]))
            idx, stats = td.decode_semantic(sem, palette, cfg["palette_tolerance"])
            for k in totals:
                totals[k] += stats[k]
            valid = idx[idx != td.UNDECODED]
            class_pixels += np.bincount(valid, minlength=len(palette))
            entry["decoding"] = stats
            report["selected_frames"].append(entry)
        report["image_sizes_wh"] = sorted(list(s) for s in sizes)
        totals["decoded_fraction"] = (totals["exact"] + totals["tolerance"]) / totals["total"] if totals["total"] else 0.0
        report["palette_decoding"] = totals
        report["class_pixels_in_selection"] = {p.name: int(class_pixels[p.index]) for p in palette}

    report["problems"] = problems
    report["ok"] = not problems
    return report, selected


def print_summary(report: dict) -> None:
    sel = report["selection"]
    print(f"Capture        : {report['capture_dir']}")
    print(f"RGB sensor     : {report['rgb_sensor_id']}  (sensors in metadata: {report['sensors_in_metadata']})")
    print(f"Matched frames : {report['matched_frames_total']} (usable {report['usable_frames_total']})")
    for seq, c in report["sequences"].items():
        print(f"Sequence {seq}: steps {c['first_step']}..{c['last_step']}, "
              f"timestamps {c['first_timestamp']}..{c['last_timestamp']}, missing steps {len(c['missing_steps'])}")
    print(f"Missing files  : RGB {len(report['missing_rgb_files'])}, semantic {len(report['missing_semantic_files'])}")
    print(f"Unreferenced   : RGB {len(report['unreferenced_rgb_files'])}, "
          f"semantic {len(report['unreferenced_semantic_files'])}")
    print(f"Selected       : {sel['selected']}/{sel['requested']} frames from index {sel['start_index']}"
          + (f", steps {sel['first_step']}..{sel['last_step']}" if sel.get("selected") else ""))
    if "image_sizes_wh" in report:
        print(f"Image sizes    : {report['image_sizes_wh']} (width x height)")
        d = report["palette_decoding"]
        print(f"Palette decode : {d['decoded_fraction']:.4%} decoded "
              f"(exact {d['exact']}, within tolerance {d['tolerance']}, "
              f"unmatched {d['unmatched']}, ambiguous {d['ambiguous']} of {d['total']} pixels)")
    print(f"Semantic classes ({len(report['semantic_classes'])}): "
          + ", ".join(c["name"] for c in report["semantic_classes"]))
    for w in report["warnings"]:
        print(f"WARNING: {w}")
    for p in report["problems"]:
        print(f"PROBLEM: {p}")
    print("Audit result   : " + ("OK" if report["ok"] else "FAILED"))


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--config", type=Path, default=Path(__file__).parent / "configs" / "office.json")
    parser.add_argument("--dataset-root", help="Overrides dataset_root (also THUD_DATASET_ROOT env var)")
    parser.add_argument("--capture", help="Capture folder, relative to dataset root or absolute")
    parser.add_argument("--frames", type=int, default=3, help="Number of matched frames to audit")
    parser.add_argument("--start", type=int, default=0, help="Index of the first matched frame")
    parser.add_argument("--output-dir", type=Path, help="Where to write the report (default: a new folder)")
    parser.add_argument("--final-evaluation", action="store_true",
                        help="required for a final-evaluation capture (one run, frozen config)")
    args = parser.parse_args()

    cfg = td.load_config(args.config, args.dataset_root, args.capture)
    rp.set_active_roots(rp.roots_from_config(cfg))
    ds.guard(ds.capture_key(cfg["capture_dir"], cfg["dataset_root"]), args.final_evaluation)
    report, _ = audit_capture(cfg, args.start, args.frames, decode=True)
    out_dir = args.output_dir or Path(cfg["output_root"]) / f"audit_{datetime.now():%Y%m%d_%H%M%S}"
    out_dir.mkdir(parents=True, exist_ok=False)
    path = out_dir / "audit_report.json"
    path.write_text(rp.dumps(report, indent=2), encoding="utf-8")
    print_summary(report)
    print(f"Report written : {path}")
    raise SystemExit(0 if report["ok"] else 1)


if __name__ == "__main__":
    main()
