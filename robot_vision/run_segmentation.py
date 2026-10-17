"""Pretrained SegFormer (ADE20K) inference on a THUD synthetic capture, evaluated against its semantic labels.

Usage:
    python run_segmentation.py --config configs/office.json --frames 3 --device cuda

Each run writes to a new folder under the output root. The run is marked
complete (run_status.json + COMPLETE file) only after every requested frame
and the evaluation have finished.
"""

from __future__ import annotations

import argparse
import json
import platform
import sys
import time
import traceback
from datetime import datetime
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw

import data_splits as ds
import run_paths as rp
import thud_data as td
from audit_dataset import audit_capture
from check_environment import device_name, select_device, verify_device

# Display colours for the grouped project classes (index = project class ID).
PROJECT_COLOURS = np.array([
    [128, 128, 128],  # 0 other
    [70, 130, 230],   # 1 wall
    [60, 200, 90],    # 2 floor
    [250, 220, 60],   # 3 ceiling
    [230, 40, 40],    # 4 person
    [250, 140, 20],   # 5 chair
    [170, 70, 220],   # 6 sofa
], dtype=np.uint8)
IGNORE_COLOUR = np.array([0, 0, 0], dtype=np.uint8)


# ---------------------------------------------------------------- label mapping

def build_prediction_lut(id2label: dict, prediction_mapping: dict[str, list[str]],
                         class_names: list[str]) -> tuple[np.ndarray, dict]:
    """Model class ID -> project class ID, resolved by class *name* from model.config.id2label."""
    labels = {int(k): v.strip() for k, v in id2label.items()}
    name_to_project = {n: i for i, n in enumerate(class_names)}
    lut = np.full(max(labels) + 1, name_to_project["other"], dtype=np.uint8)
    resolved = {}
    for project_name, model_names in prediction_mapping.items():
        for mn in model_names:
            ids = [i for i, lbl in labels.items() if lbl == mn]
            if len(ids) != 1:
                raise ValueError(f"Model label '{mn}' found {len(ids)} times in model.config.id2label; "
                                 "expected exactly one. Check the prediction_mapping in the config.")
            lut[ids[0]] = name_to_project[project_name]
            resolved[str(ids[0])] = {"model_label": mn, "project_class": project_name}
    return lut, resolved


# ---------------------------------------------------------------- evaluation

def evaluate(conf: np.ndarray, class_names: list[str], mean_classes: list[str]) -> dict:
    """Metrics from a confusion matrix with rows = reference, columns = prediction."""
    tp = np.diag(conf).astype(np.int64)
    support = conf.sum(axis=1)          # reference pixels per class
    predicted = conf.sum(axis=0)        # predicted pixels per class
    union = support + predicted - tp
    per_class = {}
    for i, name in enumerate(class_names):
        per_class[name] = {
            "iou": float(tp[i] / union[i]) if union[i] else None,
            "reference_pixels": int(support[i]),
            "predicted_pixels": int(predicted[i]),
            "true_positive_pixels": int(tp[i]),
            "false_positive_pixels": int(predicted[i] - tp[i]),
            "false_negative_pixels": int(support[i] - tp[i]),
            "union_pixels": int(union[i]),
        }
    included = [n for n in mean_classes if per_class[n]["union_pixels"] > 0]
    excluded = [n for n in mean_classes if n not in included]
    total = int(conf.sum())
    return {
        "valid_reference_pixels": total,
        "pixel_accuracy": float(tp.sum() / total) if total else None,
        "mean_iou": float(np.mean([per_class[n]["iou"] for n in included])) if included else None,
        "mean_iou_included_classes": included,
        "mean_iou_excluded_classes_zero_union": excluded,
        "per_class": per_class,
    }


# ---------------------------------------------------------------- images

def colourise(mask: np.ndarray) -> np.ndarray:
    out = np.empty(mask.shape + (3,), dtype=np.uint8)
    out[:] = IGNORE_COLOUR
    valid = mask != td.IGNORE_ID
    out[valid] = PROJECT_COLOURS[mask[valid]]
    return out


def overlay(rgb: np.ndarray, mask: np.ndarray, alpha: float = 0.5) -> np.ndarray:
    return (rgb * (1 - alpha) + colourise(mask) * alpha).round().astype(np.uint8)


def titled(img: np.ndarray, title: str) -> Image.Image:
    pil = Image.fromarray(img)
    canvas = Image.new("RGB", (pil.width, pil.height + 24), "white")
    canvas.paste(pil, (0, 24))
    ImageDraw.Draw(canvas).text((6, 6), title, fill="black")
    return canvas


def comparison_image(rgb: np.ndarray, ref: np.ndarray, pred: np.ndarray, step: int) -> Image.Image:
    panels = [titled(rgb, f"RGB (step {step})"),
              titled(colourise(ref), "Reference (grouped, black = ignored)"),
              titled(colourise(pred), "Prediction (grouped)")]
    out = Image.new("RGB", (sum(p.width for p in panels), panels[0].height), "white")
    x = 0
    for p in panels:
        out.paste(p, (x, 0))
        x += p.width
    return out


def legend_image(class_names: list[str]) -> Image.Image:
    rows = [(n, tuple(int(v) for v in PROJECT_COLOURS[i])) for i, n in enumerate(class_names)]
    rows.append(("ignored (reference only)", tuple(int(v) for v in IGNORE_COLOUR)))
    img = Image.new("RGB", (300, 26 * len(rows) + 10), "white")
    draw = ImageDraw.Draw(img)
    for i, (name, colour) in enumerate(rows):
        y = 8 + 26 * i
        draw.rectangle([8, y, 30, y + 18], fill=colour, outline="black")
        label = f"{i}  {name}" if i < len(class_names) else f"{td.IGNORE_ID}  {name}"
        draw.text((40, y + 4), label, fill="black")
    return img


def save_confusion_plot(conf: np.ndarray, class_names: list[str], path: Path) -> None:
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    row_sum = conf.sum(axis=1, keepdims=True)
    norm = np.divide(conf, row_sum, out=np.zeros(conf.shape, dtype=float), where=row_sum > 0)
    fig, ax = plt.subplots(figsize=(8, 7))
    ax.imshow(norm, cmap="Blues", vmin=0, vmax=1)
    ax.set_xticks(range(len(class_names)), class_names, rotation=45, ha="right")
    ax.set_yticks(range(len(class_names)), class_names)
    ax.set_xlabel("Predicted class")
    ax.set_ylabel("Reference class")
    ax.set_title("Confusion matrix (row-normalised; pixel counts in brackets)")
    for i in range(len(class_names)):
        for j in range(len(class_names)):
            ax.text(j, i, f"{norm[i, j]:.2f}\n({conf[i, j]})", ha="center", va="center", fontsize=7,
                    color="white" if norm[i, j] > 0.5 else "black")
    fig.tight_layout()
    fig.savefig(path, dpi=120)
    plt.close(fig)


# ---------------------------------------------------------------- main run

def comparison_indices(n: int) -> set[int]:
    if n <= 10:
        return set(range(n))
    return {0, n // 2, n - 1}


def package_versions() -> dict:
    import huggingface_hub, matplotlib, PIL, torch, torchvision, transformers
    return {"python": sys.version.split()[0], "platform": platform.platform(), "torch": torch.__version__,
            "torch_cuda_build": torch.version.cuda, "torchvision": torchvision.__version__,
            "transformers": transformers.__version__, "huggingface_hub": huggingface_hub.__version__,
            "numpy": np.__version__, "pillow": PIL.__version__, "matplotlib": matplotlib.__version__}


def resolve_revision(model_id: str, revision: str) -> str:
    """Commit hash of the locally cached snapshot that from_pretrained() loaded for `revision`."""
    from huggingface_hub import hf_hub_download

    config_file = Path(hf_hub_download(model_id, "config.json", revision=revision, local_files_only=True))
    return config_file.parent.name  # .../snapshots/<commit hash>/config.json


def write_json(path: Path, data) -> None:
    path.write_text(rp.dumps(data, indent=2), encoding="utf-8")


def run(args: argparse.Namespace) -> Path:
    import torch
    import torch.nn.functional as F
    from transformers import AutoImageProcessor, SegformerForSemanticSegmentation

    cfg = td.load_config(args.config, args.dataset_root, args.capture)
    if args.output_root:
        cfg["output_root"] = str(Path(args.output_root).absolute())
    rp.set_active_roots(rp.roots_from_config(cfg))
    ds.guard(ds.capture_key(cfg["capture_dir"], cfg["dataset_root"]), args.final_evaluation)
    class_names = cfg["project_classes"]
    if class_names[0] != "other" or len(class_names) > len(PROJECT_COLOURS):
        raise ValueError("project_classes must start with 'other' and have at most "
                         f"{len(PROJECT_COLOURS)} entries")

    # 1. Device
    device = select_device(args.device)
    print(f"Device: {device} - {device_name(device)}")
    verify_device(device)
    print("Device tensor check: OK")

    # 2. Dataset metadata validation (images are checked again as each frame is loaded)
    audit, frames = audit_capture(cfg, args.start, None if args.all_frames else args.frames, decode=False)
    if not audit["ok"]:
        raise RuntimeError("Dataset validation failed:\n  " + "\n  ".join(audit["problems"]))
    for w in audit["warnings"]:
        print(f"WARNING: {w}")
    palette = td.load_semantic_palette(Path(cfg["capture_dir"]) / cfg["annotation_definitions"],
                                       cfg["semantic_annotation_id"])
    ref_lut, ref_mapping = td.build_reference_lut(palette, cfg["reference_mapping"], class_names)

    # 3. Model
    model_id, revision = cfg["model"]["id"], cfg["model"]["revision"]
    print(f"Loading {model_id} @ {revision}")
    processor = AutoImageProcessor.from_pretrained(model_id, revision=revision)
    model = SegformerForSemanticSegmentation.from_pretrained(model_id, revision=revision)
    model.to(device).eval()
    resolved_revision = resolve_revision(model_id, revision)
    if resolved_revision != revision:
        raise RuntimeError(f"Loaded model revision {resolved_revision} differs from requested {revision}")
    pred_lut, pred_mapping = build_prediction_lut(model.config.id2label, cfg["prediction_mapping"], class_names)

    # 4. Output folder
    tag = Path(cfg["capture_dir"]).relative_to(Path(cfg["capture_dir"]).parents[2]).as_posix().replace("/", "_")
    run_dir = Path(cfg["output_root"]) / f"seg_{tag}_{len(frames)}f_{datetime.now():%Y%m%d_%H%M%S}"
    subdirs = {k: run_dir / k for k in ("pred_ade20k", "pred_grouped", "ref_grouped", "overlays",
                                        "floor_candidate", "comparisons")}
    for d in subdirs.values():
        d.mkdir(parents=True, exist_ok=False)
    status = {"status": "running", "started": datetime.now().isoformat(timespec="seconds"),
              "frames_requested": len(frames), "frames_done": 0}
    write_json(run_dir / "run_status.json", status)
    args.run_status = (run_dir, status)  # lets main() record a failure in this folder
    print(f"Output folder: {run_dir}")

    run_info = {
        "model": {"id": model_id, "requested_revision": revision, "resolved_revision": resolved_revision,
                  "processor_class": type(processor).__name__, "num_model_labels": len(model.config.id2label)},
        "packages": package_versions(),
        "device": {"type": device.type, "name": device_name(device)},
        "batch_size": 1,
        "capture_dir": cfg["capture_dir"],
        "config_path": cfg["config_path"],
        "rgb_sensor_id": cfg["rgb_sensor_id"],
        "frame_selection": audit["selection"],
        "project_classes": {i: n for i, n in enumerate(class_names)},
        "ignore_id": td.IGNORE_ID,
        "prediction_mapping_model_ids": pred_mapping,
        "reference_mapping_dataset_names": ref_mapping,
        "palette_tolerance": cfg["palette_tolerance"],
        "dataset_warnings": audit["warnings"],
    }
    write_json(run_dir / "run_info.json", run_info)
    legend_image(class_names).save(run_dir / "legend.png")

    # 5. Per-frame inference
    n_cls = len(class_names)
    conf = np.zeros((n_cls, n_cls), dtype=np.int64)
    decode_totals = {"exact": 0, "tolerance": 0, "unmatched": 0, "ambiguous": 0, "total": 0}
    sizes, timings = set(), []
    compare_at = comparison_indices(len(frames))

    def sync():
        if device.type == "cuda":
            torch.cuda.synchronize()
        elif device.type == "mps":
            torch.mps.synchronize()

    with open(run_dir / "manifest.jsonl", "w", encoding="utf-8") as manifest:
        for i, rec in enumerate(frames):
            rgb_img, rgb_mode = td.load_rgb(rec.rgb_path)
            sem = td.load_semantic_rgba(rec.semantic_path)
            w, h = rgb_img.size
            if (sem.shape[1], sem.shape[0]) != (w, h):
                raise RuntimeError(f"step {rec.step}: RGB {w}x{h} and semantic {sem.shape[1]}x{sem.shape[0]} differ")
            sizes.add((w, h))
            pal_idx, dstats = td.decode_semantic(sem, palette, cfg["palette_tolerance"])
            ref = td.reference_to_project(pal_idx, ref_lut)
            for k in decode_totals:
                decode_totals[k] += dstats[k]

            t0 = time.perf_counter()
            inputs = processor(images=rgb_img, return_tensors="pt")
            pixel_values = inputs["pixel_values"].to(device)
            sync()
            t1 = time.perf_counter()
            with torch.inference_mode():
                logits = model(pixel_values=pixel_values).logits
                logits = F.interpolate(logits, size=(h, w), mode="bilinear", align_corners=False)
                ade = logits.argmax(dim=1)[0]
            sync()
            t2 = time.perf_counter()
            ade = ade.to("cpu").numpy().astype(np.uint8)
            pred = pred_lut[ade]

            valid = ref != td.IGNORE_ID
            frame_conf = np.bincount(ref[valid].astype(np.int64) * n_cls + pred[valid],
                                     minlength=n_cls * n_cls).reshape(n_cls, n_cls)
            conf += frame_conf

            name = f"step_{rec.step:06d}.png"
            rgb_np = np.asarray(rgb_img)
            Image.fromarray(ade).save(subdirs["pred_ade20k"] / name)
            Image.fromarray(pred).save(subdirs["pred_grouped"] / name)
            Image.fromarray(ref).save(subdirs["ref_grouped"] / name)
            Image.fromarray(overlay(rgb_np, pred)).save(subdirs["overlays"] / name)
            Image.fromarray(((pred == class_names.index("floor")) * 255).astype(np.uint8)).save(
                subdirs["floor_candidate"] / name)
            outputs = {k: f"{k}/{name}" for k in ("pred_ade20k", "pred_grouped", "ref_grouped",
                                                   "overlays", "floor_candidate")}
            if i in compare_at:
                comparison_image(rgb_np, ref, pred, rec.step).save(subdirs["comparisons"] / name)
                outputs["comparison"] = f"comparisons/{name}"

            timing = {"preprocess_ms": (t1 - t0) * 1000, "inference_ms": (t2 - t1) * 1000}
            timings.append(timing)
            manifest.write(rp.dumps({
                "index": i, **{k: v for k, v in rec.to_dict().items()},
                "rgb_mode": rgb_mode, "size_wh": [w, h], "outputs": outputs, "timing": timing,
                "valid_reference_pixels": int(valid.sum()), "ignored_pixels": int((~valid).sum()),
                "frame_pixel_accuracy": float(np.trace(frame_conf) / valid.sum()) if valid.any() else None,
                "palette_decoding": {k: dstats[k] for k in ("exact", "tolerance", "unmatched", "ambiguous")},
            }) + "\n")
            manifest.flush()
            status["frames_done"] = i + 1
            write_json(run_dir / "run_status.json", status)
            if (i + 1) % 25 == 0 or i + 1 == len(frames):
                print(f"  {i + 1}/{len(frames)} frames (step {rec.step}, inference {timing['inference_ms']:.1f} ms)")

    # 6. Evaluation
    metrics = evaluate(conf, class_names, cfg["mean_iou_classes"])
    ignored = decode_totals["total"] - metrics["valid_reference_pixels"]
    if ignored != decode_totals["unmatched"] + decode_totals["ambiguous"]:
        raise RuntimeError("Internal check failed: ignored pixels != undecoded reference pixels")
    np.savetxt(run_dir / "confusion_matrix.csv", conf, fmt="%d", delimiter=",",
               header="rows=reference, columns=prediction: " + ",".join(class_names))
    save_confusion_plot(conf, class_names, run_dir / "confusion_matrix.png")

    inf = np.array([t["inference_ms"] for t in timings])
    pre = np.array([t["preprocess_ms"] for t in timings])
    report = {
        "note": "Development-sequence results on a single capture; not independent held-out performance.",
        **run_info,
        "frames": {"count": len(frames), "first_step": frames[0].step, "last_step": frames[-1].step,
                   "first_timestamp": frames[0].timestamp, "last_timestamp": frames[-1].timestamp,
                   "sequence_ids": sorted({f.sequence_id for f in frames}),
                   "comparison_steps": sorted(frames[i].step for i in compare_at)},
        "input_sizes_wh": sorted(list(s) for s in sizes),
        "evaluation_settings": {
            "confusion_rows": "reference", "confusion_columns": "prediction",
            "pixels_evaluated": "all reference pixels with a decoded palette colour (ignore ID excluded), "
                                "including 'other'",
            "mean_iou_rule": "mean over mean_iou_classes whose union > 0; 'other' pixels stay in the matrix",
            "logit_resize": "bilinear, align_corners=False, to original image size, argmax after resize",
        },
        "reference_decoding": {**decode_totals, "ignored_pixels": ignored},
        "metrics": metrics,
        "confusion_matrix": conf.tolist(),
        "timing_ms": {
            "inference_mean": float(inf.mean()), "inference_median": float(np.median(inf)),
            "inference_first_frame": float(inf[0]),
            "inference_mean_excluding_first": float(inf[1:].mean()) if len(inf) > 1 else None,
            "preprocess_mean": float(pre.mean()),
            "note": "inference = model forward + logit resize + argmax on device; excludes file I/O",
        },
    }
    write_json(run_dir / "evaluation_report.json", report)

    status.update({"status": "complete", "finished": datetime.now().isoformat(timespec="seconds")})
    write_json(run_dir / "run_status.json", status)
    (run_dir / "COMPLETE").write_text("All requested frames and the evaluation finished.\n", encoding="utf-8")

    print(f"Pixel accuracy : {metrics['pixel_accuracy']:.4f}")
    print(f"Mean IoU ({', '.join(metrics['mean_iou_included_classes'])}): {metrics['mean_iou']:.4f}")
    for n, c in metrics["per_class"].items():
        iou = "n/a" if c["iou"] is None else f"{c['iou']:.4f}"
        print(f"  {n:<8} IoU {iou:>7}  reference pixels {c['reference_pixels']}")
    print(f"Ignored reference pixels: {ignored}")
    print(f"Run complete: {run_dir}")
    return run_dir


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--config", type=Path, default=Path(__file__).parent / "configs" / "office.json")
    parser.add_argument("--dataset-root", help="Overrides dataset_root (also THUD_DATASET_ROOT env var)")
    parser.add_argument("--capture", help="Capture folder, relative to dataset root or absolute")
    parser.add_argument("--frames", type=int, default=3, help="Number of matched frames to process")
    parser.add_argument("--start", type=int, default=0, help="Index of the first matched frame")
    parser.add_argument("--all-frames", action="store_true", help="Process every usable frame (ignores --frames)")
    parser.add_argument("--final-evaluation", action="store_true",
                        help="required for a final-evaluation capture (one run, frozen config)")
    parser.add_argument("--device", default="auto", choices=["auto", "cuda", "mps", "cpu"],
                        help="'cuda'/'mps'/'cpu' fail instead of falling back; 'auto' picks CUDA, MPS, then CPU")
    parser.add_argument("--output-root", type=Path, help="Overrides output_root from the config")
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
