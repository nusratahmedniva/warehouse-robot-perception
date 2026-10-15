"""Gesture evaluation hook: accuracy by distance bin and mode, plus confusion matrices, from Unity ground truth.

Status: not_evaluated until Unity recordings with ground-truth gesture labels exist (configs/gesture.json ->
evaluation.unity_labels and evaluation.predictions are null until then; the script then reports not_evaluated and
writes nothing).

EVALUATION CODE: this is the only gesture file that reads reference labels. The adapter and the smoke script never
import it.

Labels (CSV, one row per labelled person and frame): frame_id, track_id, gesture_true (STOP / MOVE / NONE),
distance_m. Predictions: detections.jsonl of an adapter run (both modes). Per mode, the detections of one frame
and track are combined with gesture_adapter.to_gesture_events (STOP over MOVE over NONE). A labelled person
without a hand detection in that mode counts as predicted NONE and as not covered.

Each accuracy is given with its coverage, raw (no threshold) and at decision.json gesture_min_confidence (a score
below it -> NONE, as the decision's gesture filter does). Distance bins are centred on evaluation.distance_bins_m
with +/- bin_half_width_m; other distances go to "outside_bins".

Usage (from robot_vision/):
    python gesture_eval.py
"""

from __future__ import annotations

import argparse
import csv
import json
from collections import defaultdict
from pathlib import Path

import decision_io as dio
import gesture_adapter as ga
from decision import GESTURES

DEFAULT_CONFIG = "configs/gesture.json"


def read_labels(path) -> list[dict]:
    with open(path, newline="", encoding="utf-8") as f:
        rows = list(csv.DictReader(f))
    for r in rows:
        if r["gesture_true"] not in GESTURES:
            raise ValueError(f"gesture_true {r['gesture_true']!r} not in {GESTURES}")
        r["distance_m"] = float(r["distance_m"])
    return rows


def read_detections(path) -> list[ga.GestureDetection]:
    out = []
    for line in Path(path).read_text(encoding="utf-8").splitlines():
        if line.strip():
            d = json.loads(line)
            for k in ("hand_box_xyxy", "wrist_xy", "crop_box_xyxy"):
                d[k] = tuple(d[k]) if d.get(k) is not None else None
            d["candidates"] = tuple(d.get("candidates", ()))
            d["duplicates"] = tuple(tuple(x) for x in d.get("duplicates", ()))
            out.append(ga.GestureDetection(**d))
    return out


def bin_name(distance_m: float, centres, half_width: float) -> str:
    for c in centres:
        if c - half_width <= distance_m < c + half_width:
            return f"{c:g}m"
    return "outside_bins"


def _empty_matrix() -> dict:
    return {t: {p: 0 for p in GESTURES} for t in GESTURES}


def _summary(rows: list[dict]) -> dict:
    n = len(rows)
    cov = sum(r["covered"] for r in rows)
    raw = _empty_matrix()
    thr = _empty_matrix()
    for r in rows:
        raw[r["true"]][r["pred_raw"]] += 1
        thr[r["true"]][r["pred_thr"]] += 1
    return {"n_labels": n, "covered": cov, "coverage": cov / n if n else None,
            "accuracy_raw": sum(r["true"] == r["pred_raw"] for r in rows) / n if n else None,
            "accuracy_at_min_confidence": sum(r["true"] == r["pred_thr"] for r in rows) / n if n else None,
            "confusion_raw": raw, "confusion_at_min_confidence": thr}


def evaluate(labels: list[dict], detections, eval_cfg: dict, min_confidence: float) -> dict:
    """Per mode: overall and per distance bin, accuracy (raw and at min_confidence) with coverage and confusion
    matrices (rows = true gesture, columns = predicted)."""
    centres, half = eval_cfg["distance_bins_m"], eval_cfg["bin_half_width_m"]
    groups: dict = defaultdict(list)
    for d in detections:
        if d.track_id is not None and d.raw_category is not None:  # a hand assigned to a track
            groups[(d.mode, d.frame_id, str(d.track_id))].append(d)
    preds = {}
    for key, ds in groups.items():
        (ev,) = ga.to_gesture_events(ds)
        preds[key] = ev
    out = {}
    for mode in ga.MODES:
        rows = []
        for lab in labels:
            ev = preds.get((mode, lab["frame_id"], str(lab["track_id"])))
            raw = ev.gesture if ev else "NONE"
            thr = raw if ev and ev.confidence >= min_confidence else "NONE"
            rows.append({"true": lab["gesture_true"], "pred_raw": raw, "pred_thr": thr, "covered": ev is not None,
                         "bin": bin_name(lab["distance_m"], centres, half)})
        bins = [f"{c:g}m" for c in centres] + ["outside_bins"]
        out[mode] = {"overall": _summary(rows),
                     "by_distance_bin": {b: _summary([r for r in rows if r["bin"] == b]) for b in bins}}
    return out


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--config", default=DEFAULT_CONFIG)
    a = p.parse_args()
    cfg_path = dio.resolve(a.config)
    cfg = ga.load_gesture_config(cfg_path)
    ev = cfg["evaluation"]
    if not ev.get("unity_labels") or not ev.get("predictions"):
        print(f"status: {ev['status_note']} Nothing written.")
        return
    labels_path, pred_path = dio.resolve(ev["unity_labels"]), dio.resolve(ev["predictions"])
    for f in (labels_path, pred_path):
        if not f.exists():
            print(f"status: not_evaluated ({f} not found). Nothing written.")
            return
    dec_path = dio.resolve(ev["decision_config"])
    min_conf = dio.read_json(dec_path)["gesture_min_confidence"]
    result = evaluate(read_labels(labels_path), read_detections(pred_path), ev, min_conf)

    out = dio.new_run_dir(cfg, "gesture_eval")
    hashes = dio.copy_configs(out, [cfg_path, dec_path])
    dio.write_json(out / "gesture_eval.json", {"status": "evaluated", "gesture_min_confidence": min_conf,
                                               "results": result})
    dio.write_json(out / "run_info.json", {
        "label": "gesture evaluation on Unity ground truth", "config_sha256": hashes, "git": dio.git_info(),
        "unity_labels": str(labels_path), "predictions": str(pred_path),
        "labels_sha256": dio.sha256(labels_path), "predictions_sha256": dio.sha256(pred_path)})
    dio.mark_complete(out)
    print(f"Wrote {out}")


if __name__ == "__main__":
    main()
