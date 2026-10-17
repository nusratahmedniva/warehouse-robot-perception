"""YOLO11n + ByteTrack 2D tracking on the frames of a completed segmentation run, with
bounding-box summaries of the predicted segmentation masks.

Usage:
    python track_objects.py --segmentation-run outputs/seg_..._300f_... --device cuda

Frames, order and identifiers come from the segmentation run's manifest.jsonl. Tracker state is kept
between consecutive frames of one sequence and reset at every new sequence and every new run.
The integrity checks in tracking_summary.json are NOT a tracking-accuracy evaluation.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
import time
import traceback
from collections import Counter, defaultdict
from datetime import datetime
from pathlib import Path

import numpy as np
from PIL import Image

import data_splits as ds
import run_paths as rp
import thud_data as td
from check_environment import device_name, select_device, verify_device
from run_segmentation import PROJECT_COLOURS, overlay

TRACK_FIELDS = ["sequence_id", "sensor_id", "step", "timestamp", "track_id", "class_id", "class_name",
                "confidence", "x1", "y1", "x2", "y2", "box_valid", "box_clipped", "image_width", "image_height"]


# ---------------------------------------------------------------- inputs

def frame_key(rec: dict) -> tuple[str, str, int]:
    return rec["sequence_id"], rec["sensor_id"], int(rec["step"])


def load_segmentation_run(run_dir: Path) -> tuple[list[dict], dict]:
    status = json.loads((run_dir / "run_status.json").read_text(encoding="utf-8"))
    if status.get("status") != "complete" or not (run_dir / "COMPLETE").exists():
        raise RuntimeError(f"Segmentation run is not complete: {run_dir} ({status.get('status')})")
    run_info = json.loads((run_dir / "run_info.json").read_text(encoding="utf-8"))
    lines = (run_dir / "manifest.jsonl").read_text(encoding="utf-8").splitlines()
    frames = [json.loads(line) for line in lines if line.strip()]
    if len(frames) != status["frames_done"]:
        raise RuntimeError(f"Manifest has {len(frames)} frames, run status says {status['frames_done']}")
    return frames, run_info


def check_frame_order(frames: list[dict]) -> None:
    """Manifest order must already be chronological: contiguous sequences, increasing step and timestamp."""
    keys = [frame_key(f) for f in frames]
    if len(set(keys)) != len(keys):
        raise RuntimeError("Duplicate (sequence, sensor, step) entries in the segmentation manifest")
    seen_sequences = set()
    for prev, cur in zip(frames, frames[1:]):
        if cur["sequence_id"] != prev["sequence_id"]:
            if cur["sequence_id"] in seen_sequences:
                raise RuntimeError(f"Sequence {cur['sequence_id']} is not contiguous in the manifest")
            seen_sequences.add(prev["sequence_id"])
            continue
        if not cur["step"] > prev["step"]:
            raise RuntimeError(f"Steps not increasing in manifest: {prev['step']} -> {cur['step']}")
        if not (math.isfinite(cur["timestamp"]) and cur["timestamp"] > prev["timestamp"]):
            raise RuntimeError(f"Timestamps not strictly increasing at step {cur['step']}")


def check_against_metadata(frames: list[dict], seg_config_path: str, capture_dir: str | None = None) -> int:
    """Re-read the dataset metadata and confirm each manifest frame's identifiers and files."""
    cfg = td.load_config(rp.resolve(seg_config_path, rp.active_roots()), capture=capture_dir)
    records, _ = td.load_frame_records(cfg)
    by_key = {(r.sequence_id, r.sensor_id, r.step): r for r in records}
    for f in frames:
        r = by_key.get(frame_key(f))
        if r is None:
            raise RuntimeError(f"Manifest frame {frame_key(f)} not found in dataset metadata")
        if r.timestamp != f["timestamp"] or Path(r.rgb_path) != Path(f["rgb_path"]) or r.capture_id != f["capture_id"]:
            raise RuntimeError(f"Manifest frame {frame_key(f)} differs from dataset metadata")
    return len(frames)


def sha256_of(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


# ---------------------------------------------------------------- boxes and association

def box_region(x1: float, y1: float, x2: float, y2: float, w: int, h: int) -> tuple[int, int, int, int] | None:
    """Integer pixel region covered by a box (rounded outward), clipped to the image. None if empty."""
    c0, r0 = max(0, math.floor(x1)), max(0, math.floor(y1))
    c1, r1 = min(w, math.ceil(x2)), min(h, math.ceil(y2))
    if c1 <= c0 or r1 <= r0:
        return None
    return c0, r0, c1, r1


def class_fractions(mask: np.ndarray, region: tuple[int, int, int, int], n_classes: int) -> tuple[np.ndarray, int]:
    c0, r0, c1, r1 = region
    patch = mask[r0:r1, c0:c1]
    counts = np.bincount(patch.ravel(), minlength=n_classes)[:n_classes]
    return counts / patch.size, int(patch.size)


# ---------------------------------------------------------------- drawing

def track_colour(track_id: int) -> tuple[int, int, int]:
    rng = np.random.default_rng(track_id * 7919)
    return tuple(int(v) for v in rng.integers(60, 256, size=3))


def annotate(rgb: np.ndarray, pred: np.ndarray, frame: dict, observations: list[dict],
             class_names: list[str]) -> np.ndarray:
    """RGB blended with predicted segmentation, plus boxes/IDs/labels and a header with frame identifiers."""
    import cv2

    img = overlay(rgb, pred, alpha=0.4)[:, :, ::-1].copy()  # to BGR for OpenCV drawing
    for o in observations:
        if not o["box_valid"]:
            continue
        c = track_colour(o["track_id"])[::-1]
        p1 = (int(round(o["x1"])), int(round(o["y1"])))
        p2 = (int(round(o["x2"])), int(round(o["y2"])))
        cv2.rectangle(img, p1, p2, c, 2)
        text = f"ID {o['track_id']} {o['class_name']} {o['confidence']:.2f}"
        (tw, th), _ = cv2.getTextSize(text, cv2.FONT_HERSHEY_SIMPLEX, 0.45, 1)
        ty = max(th + 4, p1[1])
        cv2.rectangle(img, (p1[0], ty - th - 4), (p1[0] + tw + 4, ty), c, -1)
        cv2.putText(img, text, (p1[0] + 2, ty - 3), cv2.FONT_HERSHEY_SIMPLEX, 0.45, (0, 0, 0), 1, cv2.LINE_AA)
    header = (f"step {frame['step']}  t={frame['timestamp']:.4f} s  {frame['sensor_id']}  "
              f"seq {frame['sequence_id'][:8]}  tracks {len(observations)}")
    cv2.rectangle(img, (0, 0), (img.shape[1], 20), (0, 0, 0), -1)
    cv2.putText(img, header, (5, 14), cv2.FONT_HERSHEY_SIMPLEX, 0.45, (255, 255, 255), 1, cv2.LINE_AA)
    # Segmentation legend along the bottom edge
    x = 5
    y = img.shape[0] - 8
    for i, name in enumerate(class_names):
        colour = tuple(int(v) for v in PROJECT_COLOURS[i][::-1])
        cv2.rectangle(img, (x, y - 10), (x + 10, y), colour, -1)
        cv2.putText(img, name, (x + 13, y), cv2.FONT_HERSHEY_SIMPLEX, 0.4, (255, 255, 255), 1, cv2.LINE_AA)
        x += 20 + 8 * len(name)
    return img


def open_video(path: Path, fps: float, size_wh: tuple[int, int]):
    import cv2

    # MPEG-4 Part 2 works with the pip OpenCV build; H.264 would need the separate OpenH264 DLL.
    codec = "mp4v"
    writer = cv2.VideoWriter(str(path), cv2.VideoWriter_fourcc(*codec), fps, size_wh)
    if not writer.isOpened():
        raise RuntimeError(f"Could not open an MP4 video writer with codec {codec}")
    return writer, codec


# ---------------------------------------------------------------- main run

def write_json(path: Path, data) -> None:
    path.write_text(rp.dumps(data, indent=2), encoding="utf-8")


def run(args: argparse.Namespace) -> Path:
    import torch
    import ultralytics
    from ultralytics import YOLO
    from ultralytics.trackers.basetrack import BaseTrack
    from ultralytics.utils.checks import check_yaml

    here = Path(__file__).parent
    cfg = json.loads(args.config.read_text(encoding="utf-8"))
    det = cfg["detector"]
    for key in ("confidence", "nms_iou", "image_size"):
        if getattr(args, key) is not None:
            det[key] = getattr(args, key)
    if det.get("batch_size", 1) != 1:
        raise ValueError("Only batch_size 1 is supported for tracking")

    seg_dir = args.segmentation_run.resolve()
    frames, seg_info = load_segmentation_run(seg_dir)
    seg_cfg = td.load_config(rp.resolve(seg_info["config_path"], rp.make_roots(output_root=seg_dir.parent)))
    # the capture the segmentation run used (it may have been given with --capture), not the config default
    seg_cfg = td.load_config(Path(seg_cfg["config_path"]), capture=str(rp.resolve(
        seg_info["capture_dir"], rp.make_roots(seg_cfg["dataset_root"], seg_dir.parent))))
    rp.set_active_roots(rp.make_roots(seg_cfg["dataset_root"], seg_dir.parent))
    ds.guard(ds.capture_key(seg_cfg["capture_dir"], seg_cfg["dataset_root"]), args.final_evaluation)
    for f in frames:  # stored paths -> paths on this machine
        f["rgb_path"] = str(rp.resolve(f["rgb_path"], rp.active_roots()))
    check_frame_order(frames)
    checked = check_against_metadata(frames, seg_info["config_path"], seg_cfg["capture_dir"])
    print(f"Segmentation run: {seg_dir.name} ({len(frames)} frames, identifiers checked against metadata)")
    pred_by_key = {frame_key(f): f for f in frames}  # segmentation outputs looked up by frame identifiers
    if args.frames:
        if args.frames > len(frames):
            raise RuntimeError(f"Requested {args.frames} frames but the segmentation run has {len(frames)}")
        frames = frames[:args.frames]
    class_names = [seg_info["project_classes"][str(i)] for i in range(len(seg_info["project_classes"]))]

    # Device
    device = select_device(args.device)
    print(f"Device: {device} - {device_name(device)}")
    verify_device(device)
    print("Device tensor check: OK")
    yolo_device = 0 if device.type == "cuda" else device.type

    # Detector and tracker
    weights = Path(det["weights"])
    if not weights.is_absolute():
        weights = here / weights
    weights.parent.mkdir(parents=True, exist_ok=True)
    model = YOLO(str(weights))  # downloads the official yolo11n.pt to this path if missing
    if not weights.is_file():
        raise RuntimeError(f"Detector weights not found after loading: {weights}")
    weights_sha = sha256_of(weights)
    tracker_path = Path(check_yaml(cfg["tracker"]))
    tracker_text = tracker_path.read_text(encoding="utf-8")
    BaseTrack.reset_id()

    output_root = Path(args.output_root or cfg.get("output_root", "outputs"))
    if not output_root.is_absolute():
        output_root = here / output_root
    run_dir = output_root / f"track_{len(frames)}f_{datetime.now():%Y%m%d_%H%M%S}"
    (run_dir / "overlays").mkdir(parents=True, exist_ok=False)
    (run_dir / "tracker_config.yaml").write_text(tracker_text, encoding="utf-8")
    status = {"status": "running", "started": datetime.now().isoformat(timespec="seconds"),
              "frames_requested": len(frames), "frames_done": 0}
    write_json(run_dir / "run_status.json", status)
    args.run_status = (run_dir, status)
    print(f"Output folder: {run_dir}")

    overlay_steps = set(cfg.get("overlay_steps", []))
    if len(frames) <= 10:
        overlay_steps |= {f["step"] for f in frames}
    ts = [f["timestamp"] for f in frames]
    dts = np.diff(ts) if len(ts) > 1 else np.array([1.0])
    video_fps = float(1.0 / np.median(dts))
    first_size = tuple(frames[0]["size_wh"])
    writer, codec = open_video(run_dir / "preview.mp4", video_fps, first_size)

    n_cls = len(class_names)
    track_classes: dict[int, list[str]] = defaultdict(list)
    track_steps: dict[int, list[int]] = defaultdict(list)
    counts = Counter()
    det_per_class = Counter()
    invalid_boxes, clipped_boxes, duplicate_ids, timings = [], [], [], []
    seen_obs_keys = set()
    current_sequence = None
    tracker_resets = []

    tracks_f = open(run_dir / "tracks.csv", "w", newline="", encoding="utf-8")
    assoc_f = open(run_dir / "object_segmentation_associations.csv", "w", newline="", encoding="utf-8")
    frames_f = open(run_dir / "frames.jsonl", "w", encoding="utf-8")
    try:
        tracks_w = csv.DictWriter(tracks_f, fieldnames=TRACK_FIELDS)
        tracks_w.writeheader()
        assoc_fields = (["sequence_id", "sensor_id", "step", "timestamp", "track_id", "detector_class_id",
                         "detector_class_name", "confidence", "region_x0", "region_y0", "region_x1", "region_y1",
                         "region_pixels"] + [f"seg_frac_{n}" for n in class_names]
                        + ["dominant_seg_class", "dominant_seg_fraction"])
        assoc_w = csv.DictWriter(assoc_f, fieldnames=assoc_fields)
        assoc_w.writeheader()

        for i, frame in enumerate(frames):
            key = frame_key(frame)
            if frame["sequence_id"] != current_sequence:
                predictor = getattr(model, "predictor", None)
                for tr in getattr(predictor, "trackers", []) or []:
                    tr.reset()  # also restarts track IDs
                BaseTrack.reset_id()
                current_sequence = frame["sequence_id"]
                tracker_resets.append({"before_step": frame["step"], "sequence_id": current_sequence})

            rgb = np.asarray(td.load_rgb(frame["rgb_path"])[0])
            h, w = rgb.shape[:2]
            if [w, h] != frame["size_wh"]:
                raise RuntimeError(f"step {frame['step']}: image is {w}x{h}, manifest says {frame['size_wh']}")

            t0 = time.perf_counter()
            result = model.track(rgb[:, :, ::-1].copy(), persist=True, tracker=cfg["tracker"],
                                 conf=det["confidence"], iou=det["nms_iou"], imgsz=det["image_size"],
                                 classes=det.get("classes"), device=yolo_device, verbose=False)[0]
            if device.type == "cuda":
                torch.cuda.synchronize()
            elapsed_ms = (time.perf_counter() - t0) * 1000
            if tuple(result.orig_shape) != (h, w):
                raise RuntimeError(f"step {frame['step']}: detector saw {result.orig_shape}, expected {(h, w)}")
            timings.append({"track_call_ms": elapsed_ms, **{f"{k}_ms": v for k, v in result.speed.items()}})

            # Join to the predicted segmentation mask by frame identifiers.
            seg_frame = pred_by_key.get(key)
            if seg_frame is None:
                raise RuntimeError(f"No segmentation prediction for frame {key}")
            pred = np.array(Image.open(seg_dir / seg_frame["outputs"]["pred_grouped"]))
            if pred.shape != (h, w):
                raise RuntimeError(f"step {frame['step']}: mask {pred.shape} vs image {(h, w)}")

            observations = []
            boxes = result.boxes
            if boxes is not None and len(boxes) and boxes.id is not None:
                xyxy = boxes.xyxy.cpu().numpy().astype(float)
                ids = boxes.id.cpu().numpy().astype(int)
                cls = boxes.cls.cpu().numpy().astype(int)
                conf = boxes.conf.cpu().numpy().astype(float)
                for (x1, y1, x2, y2), tid, c, p in zip(xyxy, ids, cls, conf):
                    finite = all(math.isfinite(v) for v in (x1, y1, x2, y2))
                    region = box_region(x1, y1, x2, y2, w, h) if finite else None
                    valid = finite and x2 > x1 and y2 > y1 and region is not None
                    clipped = finite and (x1 < 0 or y1 < 0 or x2 > w or y2 > h)
                    obs = {"sequence_id": frame["sequence_id"], "sensor_id": frame["sensor_id"],
                           "step": frame["step"], "timestamp": frame["timestamp"], "track_id": int(tid),
                           "class_id": int(c), "class_name": result.names[int(c)], "confidence": float(p),
                           "x1": float(x1), "y1": float(y1), "x2": float(x2), "y2": float(y2),
                           "box_valid": valid, "box_clipped": bool(clipped), "image_width": w, "image_height": h}
                    observations.append(obs)
                    tracks_w.writerow(obs)
                    obs_key = key + (int(tid),)
                    if obs_key in seen_obs_keys:
                        duplicate_ids.append({"step": frame["step"], "track_id": int(tid)})
                    seen_obs_keys.add(obs_key)
                    if not valid:
                        invalid_boxes.append({"step": frame["step"], "track_id": int(tid),
                                              "box": [float(x1), float(y1), float(x2), float(y2)]})
                    if clipped:
                        clipped_boxes.append({"step": frame["step"], "track_id": int(tid)})
                    track_classes[int(tid)].append(obs["class_name"])
                    track_steps[int(tid)].append(frame["step"])
                    det_per_class[obs["class_name"]] += 1
                    if valid:
                        fr, npx = class_fractions(pred, region, n_cls)
                        dom = int(np.argmax(fr))
                        assoc_w.writerow({
                            "sequence_id": obs["sequence_id"], "sensor_id": obs["sensor_id"], "step": obs["step"],
                            "timestamp": obs["timestamp"], "track_id": obs["track_id"],
                            "detector_class_id": obs["class_id"], "detector_class_name": obs["class_name"],
                            "confidence": obs["confidence"], "region_x0": region[0], "region_y0": region[1],
                            "region_x1": region[2], "region_y1": region[3], "region_pixels": npx,
                            **{f"seg_frac_{n}": round(float(fr[j]), 6) for j, n in enumerate(class_names)},
                            "dominant_seg_class": class_names[dom], "dominant_seg_fraction": round(float(fr[dom]), 6)})

            counts["frames"] += 1
            counts["observations"] += len(observations)
            counts["empty_frames"] += not observations
            frames_f.write(rp.dumps({
                "index": i, "sequence_id": frame["sequence_id"], "sensor_id": frame["sensor_id"],
                "capture_id": frame["capture_id"], "step": frame["step"], "timestamp": frame["timestamp"],
                "image_width": w, "image_height": h, "rgb_path": frame["rgb_path"],
                "segmentation_mask": str(seg_dir / seg_frame["outputs"]["pred_grouped"]),
                "num_tracked_observations": len(observations),
                "track_ids": [o["track_id"] for o in observations],
                "timing_ms": timings[-1],
            }) + "\n")
            for fh in (tracks_f, assoc_f, frames_f):
                fh.flush()

            annotated = annotate(rgb, pred, frame, observations, class_names)
            writer.write(annotated)
            if frame["step"] in overlay_steps:
                Image.fromarray(annotated[:, :, ::-1]).save(run_dir / "overlays" / f"step_{frame['step']:06d}.png")
            status["frames_done"] = i + 1
            write_json(run_dir / "run_status.json", status)
            if (i + 1) % 50 == 0 or i + 1 == len(frames):
                print(f"  {i + 1}/{len(frames)} frames, {counts['observations']} tracked observations so far")
    finally:
        writer.release()
        for fh in (tracks_f, assoc_f, frames_f):
            fh.close()

    # Summary
    class_changes = {}
    for tid, names in track_classes.items():
        switches = sum(a != b for a, b in zip(names, names[1:]))
        if switches:
            class_changes[str(tid)] = {"switches": switches, "classes": dict(Counter(names))}
    tracks = {str(tid): {"observations": len(track_steps[tid]), "first_step": min(track_steps[tid]),
                         "last_step": max(track_steps[tid]), "classes": dict(Counter(track_classes[tid]))}
              for tid in sorted(track_classes)}
    # Ultralytics runs inference through predictor.model (AutoBackend), not model.model.
    model_device = str(next(model.predictor.model.model.parameters()).device)
    if torch.device(model_device).type != device.type:
        raise RuntimeError(f"Detector ran on {model_device}, but {device} was requested")
    call_ms = np.array([t["track_call_ms"] for t in timings])
    summary = {
        "note": ("Integrity checks only; this is not a detection or tracking-accuracy evaluation. Track-ID count "
                 "is not a count of real objects (IDs can split, switch or be re-created after occlusion)."),
        "segmentation_run": str(seg_dir),
        "frames_checked_against_dataset_metadata": checked,
        "frames": {"count": counts["frames"], "first_step": frames[0]["step"], "last_step": frames[-1]["step"],
                   "first_timestamp": frames[0]["timestamp"], "last_timestamp": frames[-1]["timestamp"],
                   "sequence_ids": sorted({f["sequence_id"] for f in frames}),
                   "sensor_ids": sorted({f["sensor_id"] for f in frames}),
                   "image_sizes_wh": sorted({tuple(f["size_wh"]) for f in frames}),
                   "frames_without_tracked_observations": counts["empty_frames"]},
        "observations": {"total": counts["observations"], "per_detector_class": dict(det_per_class),
                         "invalid_boxes": invalid_boxes, "clipped_boxes": len(clipped_boxes),
                         "duplicate_track_ids_within_frame": duplicate_ids},
        "track_ids": {"count": len(tracks), "class_change_warnings": class_changes, "tracks": tracks},
        "tracker_resets": tracker_resets,
        "detector": {"weights": str(weights), "weights_sha256": weights_sha, **det,
                     "class_names": result.names, "model_parameters_device": model_device},
        "tracker": {"requested": cfg["tracker"], "resolved_path": str(tracker_path), "config_text": tracker_text,
                    "state": "persist=True within a sequence; reset at each new sequence and each new run"},
        "device": {"type": device.type, "name": device_name(device), "ultralytics_device_arg": yolo_device},
        "packages": {"ultralytics": ultralytics.__version__, "torch": torch.__version__,
                     "torch_cuda_build": torch.version.cuda, "opencv": __import__("cv2").__version__,
                     "numpy": np.__version__},
        "timing_ms": {"track_call_mean": float(call_ms.mean()), "track_call_median": float(np.median(call_ms)),
                      "first_frame": float(call_ms[0]),
                      "note": "track_call = Ultralytics preprocessing + detector inference + NMS + ByteTrack update"},
        "association": {
            "method": ("For each valid tracked box: the box is rounded outward to whole pixels and clipped to the "
                       "image; seg_frac_<class> = share of those pixels in the predicted grouped segmentation mask."),
            "caveat": ("Bounding-box summaries only. Background and overlapping objects inside the box contaminate "
                       "the proportions; they are not instance masks and do not measure object extent. Reference "
                       "masks and reference object IDs are not used."),
            "join": "frames and masks joined on (sequence_id, sensor_id, step) from the segmentation manifest",
        },
        "preview_video": {
            "file": "preview.mp4", "codec": codec, "playback_fps": video_fps,
            "playback_fps_source": "1 / median difference of the recorded timestamps of the processed frames",
            "warning": ("Playback timing is for viewing only. Use the per-frame timestamps in frames.jsonl, never "
                        "the video frame rate, for any motion measurement."),
        },
    }
    write_json(run_dir / "tracking_summary.json", summary)
    status.update({"status": "complete", "finished": datetime.now().isoformat(timespec="seconds")})
    write_json(run_dir / "run_status.json", status)
    (run_dir / "COMPLETE").write_text("All requested frames finished.\n", encoding="utf-8")

    print(f"Frames: {counts['frames']} ({counts['empty_frames']} without tracked observations)")
    print(f"Tracked observations: {counts['observations']}  per class: {dict(det_per_class)}")
    print(f"Track IDs: {len(tracks)} (not a count of real objects); tracks with class changes: {len(class_changes)}")
    print(f"Invalid boxes: {len(invalid_boxes)}, clipped boxes: {len(clipped_boxes)}, "
          f"duplicate IDs within a frame: {len(duplicate_ids)}")
    print(f"Detector parameters on: {model_device}; weights sha256 {weights_sha}")
    print(f"Run complete: {run_dir}")
    return run_dir


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--config", type=Path, default=Path(__file__).parent / "configs" / "tracking_office.json")
    parser.add_argument("--segmentation-run", type=Path, required=True,
                        help="Completed run folder from run_segmentation.py")
    parser.add_argument("--frames", type=int, help="Process only the first N manifest frames (default: all)")
    parser.add_argument("--device", default="auto", choices=["auto", "cuda", "mps", "cpu"])
    parser.add_argument("--confidence", type=float, help="Override detector confidence threshold")
    parser.add_argument("--nms-iou", dest="nms_iou", type=float, help="Override NMS IoU threshold")
    parser.add_argument("--image-size", dest="image_size", type=int, help="Override inference image size")
    parser.add_argument("--output-root", type=Path)
    parser.add_argument("--final-evaluation", action="store_true",
                        help="required for a final-evaluation capture (one run, frozen config)")
    args = parser.parse_args()
    args.run_status = None
    try:
        run(args)
    except Exception as exc:
        traceback.print_exc()
        if args.run_status:
            run_dir, status = args.run_status
            status.update({"status": "failed", "error": f"{type(exc).__name__}: {exc}",
                           "finished": datetime.now().isoformat(timespec="seconds")})
            write_json(run_dir / "run_status.json", status)
            print(f"Run FAILED; partial outputs kept in {run_dir}")
        raise SystemExit(1)


if __name__ == "__main__":
    main()
