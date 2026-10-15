"""Gesture adapter smoke test on sample images (optional; not an evaluation).

Runs both adapter modes on every image in the configured folder (configs/gesture.json -> smoke.image_dir,
git-ignored) and writes, in a new run folder:
    annotated/full_frame/<image>.png, annotated/person_crop/<image>.png
        person boxes (grey), crop boxes (blue), hand boxes coloured by gesture, with gesture, raw category,
        raw confidence and mode
    detections.jsonl    every GestureDetection (both modes), frame_id = image file name
    run_info.json, config_used/
Person boxes come from the Stage 2 detector (weights and detector confidence from the tracking config), image by
image without tracking: track_id = det<k>. No depth is available, so hand owners come from the wrist rule.
No confidence threshold is applied to gestures.

Usage (from robot_vision/):
    python gesture_smoke.py [--image-dir DIR] [--device auto]
"""

from __future__ import annotations

import argparse
import json
import platform
import sys
from datetime import datetime
from importlib.metadata import version
from pathlib import Path

import cv2
import numpy as np

import decision_io as dio
import gesture_adapter as ga

COLOURS = {"STOP": (0, 0, 255), "MOVE": (0, 200, 0), "NONE": (0, 200, 255)}  # BGR


def read_rgb(p: Path) -> np.ndarray:
    bgr = cv2.imdecode(np.fromfile(str(p), dtype=np.uint8), cv2.IMREAD_COLOR)  # non-ASCII paths on Windows
    if bgr is None:
        raise ValueError(f"cannot read image {p}")
    return cv2.cvtColor(bgr, cv2.COLOR_BGR2RGB)


def detect_persons(model, rgb: np.ndarray, det: dict, device: str) -> list[ga.PersonBox]:
    res = model.predict(np.ascontiguousarray(rgb[:, :, ::-1]), conf=det["confidence"], iou=det["nms_iou"],
                        imgsz=det["image_size"], device=device, verbose=False)[0]
    out = []
    for k, (box, c) in enumerate(zip(res.boxes.xyxy.cpu().numpy(), res.boxes.cls.cpu().numpy())):
        if res.names[int(c)] == "person":
            out.append(ga.PersonBox(f"det{k}", *map(float, box)))
    return out


def annotate(rgb: np.ndarray, persons, dets, mode: str) -> np.ndarray:
    img = np.ascontiguousarray(rgb[:, :, ::-1])
    for p in persons:
        cv2.rectangle(img, (int(p.x1), int(p.y1)), (int(p.x2), int(p.y2)), (160, 160, 160), 1)
        cv2.putText(img, str(p.track_id), (int(p.x1), int(p.y1) + 12), cv2.FONT_HERSHEY_SIMPLEX, 0.4,
                    (160, 160, 160), 1, cv2.LINE_AA)
    lines = []
    for d in dets:
        col = COLOURS[d.gesture]
        if d.crop_box_xyxy:
            x0, y0, x1, y1 = d.crop_box_xyxy
            cv2.rectangle(img, (x0, y0), (x1, y1), (255, 128, 0), 1)
        if d.hand_box_xyxy:
            x0, y0, x1, y1 = map(int, d.hand_box_xyxy)
            cv2.rectangle(img, (x0, y0), (x1, y1), col, 2)
            cv2.putText(img, f"{d.gesture} {d.confidence:.2f}", (x0, max(12, y0 - 4)), cv2.FONT_HERSHEY_SIMPLEX,
                        0.45, col, 1, cv2.LINE_AA)
        conf = "-" if d.confidence is None else f"{d.confidence:.2f}"
        lines.append((f"{d.track_id}: {d.gesture} ({d.raw_category or 'no hand'}) conf {conf} [{d.assignment}]", col))
    lines.insert(0, (f"mode: {mode}", (255, 255, 255)))
    for i, (t, col) in enumerate(lines):
        cv2.putText(img, t, (8, 18 + 16 * i), cv2.FONT_HERSHEY_SIMPLEX, 0.45, (0, 0, 0), 3, cv2.LINE_AA)
        cv2.putText(img, t, (8, 18 + 16 * i), cv2.FONT_HERSHEY_SIMPLEX, 0.45, col, 1, cv2.LINE_AA)
    return img


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--config", default=ga.DEFAULT_CONFIG)
    p.add_argument("--image-dir", help="overrides smoke.image_dir")
    p.add_argument("--device", default="auto", help="person detector device: auto (CUDA, MPS, CPU), cuda, mps, cpu")
    a = p.parse_args()

    cfg_path = dio.resolve(a.config)
    cfg = ga.load_gesture_config(cfg_path)
    sm = cfg["smoke"]
    image_dir = dio.resolve(a.image_dir or sm["image_dir"])
    images = sorted(f for f in image_dir.glob("*") if f.suffix.lower() in sm["image_suffixes"]) \
        if image_dir.is_dir() else []
    if not images:
        raise SystemExit(f"No sample images in {image_dir} (suffixes {sm['image_suffixes']}).")

    from ultralytics import YOLO
    from check_environment import select_device
    track_path = dio.resolve(sm["person_detector_config"])
    det = dio.read_json(track_path)["detector"]
    device = select_device(a.device)
    model = YOLO(str(dio.resolve(det["weights"])))

    out = dio.new_run_dir(cfg, f"gesture_smoke_{len(images)}img")
    adapters = {m: ga.GestureRecognizerAdapter(cfg, m) for m in ga.MODES}
    counts = {m: {g: 0 for g in ("STOP", "MOVE", "NONE")} for m in ga.MODES}
    n_persons = 0
    with (out / "detections.jsonl").open("w", encoding="utf-8") as f:
        for i, img_path in enumerate(images):
            rgb = read_rgb(img_path)
            persons = detect_persons(model, rgb, det, str(device))
            n_persons += len(persons)
            for m, ad in adapters.items():
                dets = ad.detect(rgb, float(i), persons, frame_id=img_path.name)
                for d in dets:
                    f.write(json.dumps(d.as_dict()) + "\n")
                    counts[m][d.gesture] += 1
                (out / "annotated" / m).mkdir(parents=True, exist_ok=True)
                ok, buf = cv2.imencode(".png", annotate(rgb, persons, dets, m))
                buf.tofile(str(out / "annotated" / m / (img_path.stem + ".png")))
            print(f"{img_path.name}: {len(persons)} person box(es)")
    for ad in adapters.values():
        ad.close()

    hashes = dio.copy_configs(out, [cfg_path, track_path])
    dio.write_json(out / "run_info.json", {
        "label": "gesture adapter smoke test (sample images; not an evaluation)",
        "created": datetime.now().isoformat(timespec="seconds"),
        "command": " ".join([Path(sys.executable).name] + sys.argv), "git": dio.git_info(),
        "python": platform.python_version(), "platform": platform.platform(),
        "mediapipe": version("mediapipe"), "config_sha256": hashes,
        "model": cfg["model"]["path"], "model_sha256": cfg["model"]["sha256"],
        "source_commit": cfg["source"]["commit"], "image_dir": a.image_dir or sm["image_dir"],
        "images": [im.name for im in images], "person_boxes": n_persons, "person_detector_device": str(device),
        "detections_by_mode_and_gesture": counts})
    dio.mark_complete(out)
    print(f"Detections by mode: {counts}")
    print(f"Wrote {out}")


if __name__ == "__main__":
    main()
