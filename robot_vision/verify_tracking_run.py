"""Integrity checks of a completed track_objects.py run, recomputed from its saved files.

These checks confirm frame alignment, identifiers, box coordinates and association arithmetic.
They are NOT a detection or tracking-accuracy evaluation.

Usage:
    python verify_tracking_run.py outputs/track_300f_<date>_<time>
"""
import csv, json, sys
from pathlib import Path
import numpy as np, cv2
from PIL import Image
import run_paths as rp
run = Path(sys.argv[1])
summ = json.loads((run / "tracking_summary.json").read_text(encoding="utf-8"))
n_expected = summ["frames"]["count"]
# stored paths are relative to the output root, which holds this run
roots = rp.make_roots(output_root=run.resolve().parent)
seg = rp.resolve(summ["segmentation_run"], roots)
man = [json.loads(l) for l in (seg / "manifest.jsonl").read_text(encoding="utf-8").splitlines()][:n_expected]
frames = [json.loads(l) for l in (run / "frames.jsonl").read_text(encoding="utf-8").splitlines()]
for f in frames:
    f["segmentation_mask"] = rp.resolve(f["segmentation_mask"], roots)
key = lambda d: (d["sequence_id"], d["sensor_id"], int(d["step"]))
assert json.loads((run / "run_status.json").read_text())["status"] == "complete" and (run / "COMPLETE").exists()
assert len(frames) == n_expected, len(frames)
assert [key(f) for f in frames] == [key(m) for m in man], "frame identifiers/order differ from segmentation manifest"
mk = {key(m): m for m in man}
for f in frames:
    m = mk[key(f)]
    assert f["timestamp"] == m["timestamp"] and [f["image_width"], f["image_height"]] == m["size_wh"]
    assert Path(f["segmentation_mask"]) == seg / m["outputs"]["pred_grouped"]
ts = [f["timestamp"] for f in frames]; assert all(b > a for a, b in zip(ts, ts[1:]))
rows = list(csv.DictReader(open(run / "tracks.csv", encoding="utf-8")))
assert len(rows) == sum(f["num_tracked_observations"] for f in frames) == summ["observations"]["total"]
fk = {key(f): f for f in frames}
obs_keys = set()
for r in rows:
    k = key(r); f = fk[k]
    assert float(r["timestamp"]) == f["timestamp"]
    ok = (r["sequence_id"], r["sensor_id"], int(r["step"]), int(r["track_id"]))
    assert ok not in obs_keys, ok; obs_keys.add(ok)
    x1, y1, x2, y2 = (float(r[c]) for c in ("x1", "y1", "x2", "y2"))
    W, H = int(r["image_width"]), int(r["image_height"])
    assert (W, H) == (f["image_width"], f["image_height"])
    assert 0 <= x1 < x2 <= W and 0 <= y1 < y2 <= H, (r["step"], x1, y1, x2, y2)
    assert int(r["track_id"]) in f["track_ids"]
assoc = list(csv.DictReader(open(run / "object_segmentation_associations.csv", encoding="utf-8")))
assert len(assoc) == sum(r["box_valid"] == "True" for r in rows)
fr_cols = [c for c in assoc[0] if c.startswith("seg_frac_")] if assoc else []
rng = np.random.default_rng(0); sample = rng.choice(len(assoc), size=min(40, len(assoc)), replace=False) if assoc else []
for i in sample:
    a = assoc[i]; mask = np.array(Image.open(fk[key(a)]["segmentation_mask"]))
    patch = mask[int(a["region_y0"]):int(a["region_y1"]), int(a["region_x0"]):int(a["region_x1"])]
    exp = np.bincount(patch.ravel(), minlength=7)[:7] / patch.size
    got = np.array([float(a[c]) for c in fr_cols])
    assert np.allclose(exp, got, atol=1e-6) and patch.size == int(a["region_pixels"])
for a in assoc:
    assert abs(sum(float(a[c]) for c in fr_cols) - 1) < 1e-4
cap = cv2.VideoCapture(str(run / "preview.mp4")); nvid = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
size = (int(cap.get(cv2.CAP_PROP_FRAME_WIDTH)), int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))); cap.release()
assert nvid == n_expected, nvid
ov = sorted(p.name for p in (run / "overlays").glob("*.png"))
print("frames", len(frames), "observations", len(rows), "associations", len(assoc), "unique obs keys", len(obs_keys))
print("video frames", nvid, "size", size, "fps", summ["preview_video"]["playback_fps"], "overlays", ov)
print("empty frames", sum(f["num_tracked_observations"] == 0 for f in frames))
print("ALL INTEGRITY CHECKS PASSED")
