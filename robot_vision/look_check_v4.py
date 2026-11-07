"""v4 avatar-look check: do the REAL YOLO11s-pose and MediaPipe hand models find the body and the hands of each avatar
look, and does the v4 reader (gesture_motion.py) read POINT / WAIT / STOP on it? docs/look_check_v4.md.

An engineering check, not an evaluation: nothing is tuned on it (a look that fails is swapped, no reader, commander or
perception value changes), it never reads truth.jsonl, data_splits or any ground-truth loader, and the commands it
compares against are the recording labels in the file names (<look>__<command>__<distance_m>__<n>).

Input folder (from Nusrat): saved pan-tilt PNGs, either single frames or short sequences (one subfolder per sequence,
frame_###.png), each with a header JSON of the same name next to it (fx, fy, cx, cy, vertical_fov_deg; optional width,
height, pan_deg, time_s and "arm"). The frame header is validated like a live frame (protocol 3 intrinsics check).

The models are reached only through the existing code: hri_perception_v4.HriPerceptionV4 loads YOLO (weights and sha256
from configs/hri_perception.json) and the MediaPipe adapter (gesture_adapter_v4.py); the reader is the live one
(hri_perception_v4.PersonsPipeline -> gesture_motion.read_window, thresholds from configs/v4/gesture_reader.json). The
verdict rules are declared in configs/v4/look_check.json. One person is read per frame (the largest box, as v3 does:
the pan-tilt camera is aimed at the commander); no tracker is used, so no state leaks between recordings.

Outputs (a new folder under outputs/): report.json, report.md, annotated/ (keypoints and hand landmarks drawn),
config_used/ and run.json (git commit, model hashes, input manifest).
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import platform
import re
import sys
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path

import numpy as np

import commander_v4 as cm
import decision_io as dio
import gesture_motion as gm
import hri_perception_v4 as hp4

HERE = Path(__file__).resolve().parent
DEFAULT_CONFIG = "configs/v4/look_check.json"
EPS = 1e-9

KEYPOINTS = {"left_shoulder": gm.L_SHOULDER, "right_shoulder": gm.R_SHOULDER, "left_elbow": gm.L_ELBOW,
             "right_elbow": gm.R_ELBOW, "left_wrist": gm.L_WRIST, "right_wrist": gm.R_WRIST,
             "left_hip": gm.L_HIP, "right_hip": gm.R_HIP}
BODY_LINES = [(5, 6), (5, 7), (7, 9), (6, 8), (8, 10), (5, 11), (6, 12), (11, 12)]
HAND_LINES = [(0, 1), (1, 2), (2, 3), (3, 4), (0, 5), (5, 6), (6, 7), (7, 8), (5, 9), (9, 10), (10, 11), (11, 12),
              (9, 13), (13, 14), (14, 15), (15, 16), (13, 17), (17, 18), (18, 19), (19, 20), (0, 17)]
EXPECTED_CATEGORY = {"WAIT": "Pointing_Up", "STOP": "Open_Palm"}
GRADE_ORDER = ["fails", "not_evaluated", "weak", "usable"]       # worst first; not_evaluated is insufficient_data for a look


def load_config(path: str | Path = DEFAULT_CONFIG) -> dict:
    p = Path(path)
    return json.loads((p if p.is_absolute() else HERE / p).read_text(encoding="utf-8"))


def _r(x, n=3):
    return None if x is None else round(float(x), n)


# ---------------------------------------------------------------- input folder

@dataclass
class Item:
    """One recording: a single frame or a sequence."""
    name: str
    kind: str                                # "frame" | "sequence"
    look: str
    command: str
    distance_m: float
    take: str
    files: list                              # [(png Path, header json Path)]

    @property
    def key(self) -> tuple:
        return (self.look, self.command, self.distance_m)


def parse_name(stem: str, cfg: dict) -> tuple[str, str, float, str]:
    """<look>__<command>__<distance_m>__<n> -> (look, command, distance_m, take); ValueError with the reason otherwise."""
    parts = stem.split("__")
    if len(parts) != 4 or not all(parts):
        raise ValueError(f"{stem!r}: not <look>__<command>__<distance_m>__<n>")
    look, command, dist, take = parts
    if command not in cfg["input"]["commands"]:
        raise ValueError(f"{stem!r}: command {command!r} not in {cfg['input']['commands']} (capital letters)")
    try:
        d = float(dist)
    except ValueError:
        raise ValueError(f"{stem!r}: distance {dist!r} is not a number of metres") from None
    if not math.isfinite(d) or d <= 0:
        raise ValueError(f"{stem!r}: distance must be > 0")
    return look, command, d, take


def _natural(p: Path):
    return [int(t) if t.isdigit() else t for t in re.split(r"(\d+)", p.name)]


def discover(folder: Path, cfg: dict) -> tuple[list[Item], list[str]]:
    """Every recording of the folder and the problems found (names that do not parse, missing headers are reported per
    frame later). Single frames: <name>.png in the folder; sequences: a subfolder <name>/ with frame_###.png."""
    ext, hext = cfg["input"]["image_ext"], cfg["input"]["header_ext"]
    items, problems = [], []
    for entry in sorted(folder.iterdir(), key=_natural):
        if entry.name.startswith("."):
            continue
        if entry.is_file() and entry.suffix.lower() == ext:
            kind, stem, pngs = "frame", entry.stem, [entry]
        elif entry.is_dir():
            kind, stem = "sequence", entry.name
            pngs = sorted((p for p in entry.iterdir() if p.is_file() and p.suffix.lower() == ext), key=_natural)
            if not pngs:
                problems.append(f"{entry.name}/: no {ext} frames")
                continue
        else:
            continue
        try:
            look, command, dist, take = parse_name(stem, cfg)
        except ValueError as e:
            problems.append(str(e))
            continue
        items.append(Item(stem, kind, look, command, dist, take, [(p, p.with_suffix(hext)) for p in pngs]))
    return items, problems


@dataclass
class Header:
    fx: float
    fy: float
    cx: float
    cy: float
    vertical_fov_deg: float
    width: int
    height: int
    pan_deg: float = 0.0
    time_s: float | None = None
    arm: str | None = None


def read_header(path: Path, img_w: int, img_h: int, cfg: dict, rel_tol: float) -> tuple[Header | None, str | None]:
    """The frame header next to a PNG, validated like a live frame_pan_tilt (bridge.protocol, version 3)."""
    from bridge import protocol as bp
    if not path.exists():
        return None, f"header {path.name} missing"
    try:
        h = json.loads(path.read_text(encoding="utf-8-sig"))
    except (OSError, ValueError) as e:
        return None, f"header {path.name} unreadable: {e}"
    if not isinstance(h, dict):
        return None, f"header {path.name} is not a JSON object"
    missing = [k for k in ("fx", "fy", "cx", "cy", "vertical_fov_deg") if not isinstance(h.get(k), (int, float))
               or isinstance(h.get(k), bool) or not math.isfinite(h[k])]
    if missing:
        return None, f"header {path.name}: missing or non-numeric {missing}"
    for k, v in (("width", img_w), ("height", img_h)):
        if k in h and h[k] != v:
            return None, f"header {path.name}: {k} {h[k]} differs from the image ({v})"
    full = {**h, "width": img_w, "height": img_h}
    try:
        bp._check_v3("frame_pan_tilt", full, rel_tol)
    except bp.MessageError as e:
        return None, f"header {path.name}: {e}"
    arm = h.get("arm")
    if arm is not None and arm not in cfg["input"]["arms"]:
        return None, f"header {path.name}: arm {arm!r} not in {cfg['input']['arms']}"
    t = h.get("time_s")
    if t is not None and (not isinstance(t, (int, float)) or isinstance(t, bool) or not math.isfinite(t)):
        return None, f"header {path.name}: time_s is not a number"
    pan = h.get("pan_deg", 0.0)
    if not isinstance(pan, (int, float)) or isinstance(pan, bool):
        return None, f"header {path.name}: pan_deg is not a number"
    return Header(float(h["fx"]), float(h["fy"]), float(h["cx"]), float(h["cy"]), float(h["vertical_fov_deg"]), img_w,
                  img_h, float(pan), None if t is None else float(t), arm), None


def read_image(path: Path):
    import cv2
    img = cv2.imdecode(np.fromfile(str(path), np.uint8), cv2.IMREAD_COLOR)
    if img is None:
        raise ValueError(f"{path.name}: image could not be decoded")
    return img


# ---------------------------------------------------------------- detectors (real models or fakes)

@dataclass
class Detection:
    """What the models found in one frame. persons: every YOLO person ({'box', 'kp' (17, 2), 'conf' (17,)}); chosen:
    index of the person that is read (the largest box) or None; hands: the MediaPipe hands found in the chosen person's
    crop (objects with category, score, handedness, landmarks_px (21, 2), world_xyz, box)."""
    persons: list = field(default_factory=list)
    chosen: int | None = None
    hands: list = field(default_factory=list)


def largest(persons: list) -> int | None:
    if not persons:
        return None
    return int(np.argmax([(p["box"][2] - p["box"][0]) * (p["box"][3] - p["box"][1]) for p in persons]))


class RealDetector:
    """YOLO11s-pose (the untracked gesture model of HriPerception, imgsz and det_confidence of configs/hri_perception.json
    'gesture') and the MediaPipe hand adapter v4 (person_crop), both loaded by HriPerceptionV4."""

    def __init__(self, device: str | None = None):
        import hri_perception as hpm
        self.perc = hp4.HriPerceptionV4(hpm.load_config(), gm.load_config(), cm.load_config(), device)

    def detect(self, bgr) -> Detection:
        p, g = self.perc, self.perc.cfg["gesture"]
        r = p.gesture_model.predict(bgr, imgsz=g["imgsz"], conf=g["det_confidence"], device=p.device, verbose=False)[0]
        persons = []
        if r.boxes is not None and len(r.boxes) > 0 and r.keypoints is not None:
            for b, kp, kc in zip(r.boxes.xyxy.cpu().numpy(), r.keypoints.xy.cpu().numpy(), r.keypoints.conf.cpu().numpy()):
                persons.append({"box": tuple(map(float, b)), "kp": kp, "conf": kc})
        i = largest(persons)
        hands = []
        if i is not None:
            box = persons[i]["box"]
            hands = p.hands.detect_hands(bgr[:, :, ::-1], [p._ga.PersonBox(0, *box)]).get(0, [])
        return Detection(persons, i, list(hands))

    def runtime(self) -> dict:
        try:
            return self.perc.inference_devices()
        except Exception as e:                                        # logging only
            return {"error": str(e)}

    def close(self):
        self.perc.close()


# ---------------------------------------------------------------- one frame

def infer_arm(sample: gm.Sample, rc: dict) -> str | None:
    best = None
    for side in gm.ARMS:
        af = gm.arm_frame(sample, side, rc)
        if af.valid and af.raised and (best is None or af.wrist_above_hip > best[0]):
            best = (af.wrist_above_hip, side)
    return best[1] if best else None


def class_of(flags: dict) -> str:
    return "STOP" if flags["stop_ok"] else "WAIT" if flags["wait_ok"] else "POINT" if flags["point_ok"] else "NONE"


def analyse_frame(det: Detection, hdr: Header, t: float, idx: int, name: str, item: Item, pipeline: hp4.PersonsPipeline,
                  rc: dict) -> tuple[dict, dict | None]:
    """(record, drawing payload). Everything in the record is a number, a bool, a string or None."""
    thr = rc["keypoints"]["body_kp_conf_min"]
    meta = {"t": t, "fx": hdr.fx, "fy": hdr.fy, "cx": hdr.cx, "cy": hdr.cy, "width": hdr.width, "height": hdr.height,
            "pan_deg": hdr.pan_deg, "robot_yaw_deg": 0.0}
    rec: dict = {"frame": name, "index": idx, "t": _r(t), "person": det.chosen is not None, "n_persons": len(det.persons),
                 "arm": hdr.arm, "arm_source": "label" if hdr.arm else "none", "reader": None}
    if det.chosen is None:
        pipeline.update([], {}, meta)
        return rec, None
    p = det.persons[det.chosen]
    kp, conf = np.asarray(p["kp"], float), np.asarray(p["conf"], float)
    pr = pipeline.update([{"track_id": 0, "box": p["box"], "kp": kp, "conf": conf}], {0: list(det.hands)}, meta)[0]
    sample = pipeline.buffers[0].window(t, 0.0)[-1]
    arm = hdr.arm
    if arm is None:
        arm = infer_arm(sample, rc)
        rec["arm"], rec["arm_source"] = arm, "inferred" if arm else "none"
    sides = [arm] if arm else list(gm.ARMS)
    afs = {s: gm.arm_frame(sample, s, rc) for s in sides}
    flags_by = {s: gm.frame_flags(sample, s, afs[s], rc) for s in sides}
    flags = {k: any(f[k] for f in flags_by.values()) for k in ("point_ok", "wait_ok", "stop_ok")}
    af = afs[arm] if arm else None
    hand = sample.hands.get(arm) if arm else None
    shown = hand if hand is not None else (det.hands[0] if det.hands else None)
    rec["kp"] = {n: _r(conf[i]) for n, i in KEYPOINTS.items()}
    rec["kp_ok"] = {n: bool(conf[i] >= thr) for n, i in KEYPOINTS.items()}
    rec["arm_valid"] = bool(af.valid) if af else False
    rec["arm_why"] = (af.reason if af and not af.valid else "")
    rec["raised"] = bool(af.raised) if af and af.valid else False
    rec["ratio"] = _r(af.length_ratio) if af and af.valid else None
    rec["elbow_deg"] = _r(af.elbow_deg, 1) if af and af.valid else None
    rec["hand_any"], rec["hand_linked"] = bool(det.hands), hand is not None
    rec["hand"], rec["cues"] = None, {}
    if shown is not None:
        cues = gm.hand_cues(shown, rc)
        lm = np.asarray(shown.landmarks_px, float)
        inside = bool(len(lm) == 21 and (lm[:, 0] >= 0).all() and (lm[:, 0] <= hdr.width).all() and (lm[:, 1] >= 0).all()
                      and (lm[:, 1] <= hdr.height).all())
        rec["hand"] = {"linked": hand is not None, "category": shown.category, "score": _r(shown.score),
                       "handedness": getattr(shown, "handedness", None), "n_landmarks": int(len(lm)),
                       "landmarks_inside": inside, "world": getattr(shown, "world_xyz", None) is not None,
                       "box_h_px": _r(shown.box[3] - shown.box[1], 1),
                       "ratios": {k: _r(v) for k, v in cues["ratios"].items()}, "spread_deg": _r(cues["spread_deg"], 1),
                       "index_up_deg": _r(cues["index_up_deg"], 1)}
        h = rc["hand"]
        finger_up = bool(cues["extended"]["index"] and all(cues["curled"][n] for n in ("middle", "ring", "pinky"))
                         and abs(cues["index_up_deg"]) <= h["index_up_tol_deg"])
        open_palm = bool(all(cues["extended"].values()) and cues["spread_deg"] >= h["palm_spread_min_deg"])
        rec["cues"] = {"finger_up": finger_up, "open_palm": open_palm,
                       "category_ok": bool(item.command in EXPECTED_CATEGORY and hand is not None
                                           and cues["category"] == EXPECTED_CATEGORY[item.command])}
    rec["cues"]["raised"] = rec["raised"]
    rec["flags"], rec["frame_class"] = flags, class_of(flags)
    rec["facing"] = bool(pr.facing)
    rd = pr.reading
    rec["reader"] = {"command": rd.command, "score": _r(rd.score), "why": rd.why, "arm": rd.arm, "valid_frames": rd.valid_frames,
                     "n_frames": rd.n_frames, "hold_s": _r(rd.hold_s), "moving": rd.moving, "scores": {k: _r(v) for k, v in rd.scores.items()}}
    draw = {"kp": kp, "conf": conf, "box": p["box"], "hands": list(det.hands), "linked": hand, "others": [q["box"] for i, q in enumerate(det.persons) if i != det.chosen]}
    return rec, draw


def _line(img, p, q, colour, thick: int = 1) -> None:
    """A straight segment drawn with numpy (the cv2 names the pipeline may use are pinned in tests/test_opencv.py)."""
    if not (np.isfinite(p).all() and np.isfinite(q).all()):
        return
    x0, y0, x1, y1 = (int(round(float(v))) for v in (*p, *q))
    n = max(abs(x1 - x0), abs(y1 - y0), 1) + 1
    xs, ys = np.rint(np.linspace(x0, x1, n)).astype(int), np.rint(np.linspace(y0, y1, n)).astype(int)
    h, w = img.shape[:2]
    for dy in range(thick):
        for dx in range(thick):
            yy, xx = ys + dy - thick // 2, xs + dx - thick // 2
            ok = (yy >= 0) & (yy < h) & (xx >= 0) & (xx < w)
            img[yy[ok], xx[ok]] = colour


def _marker(img, p, radius: int, colour, filled: bool) -> None:
    import cv2
    if not np.isfinite(p).all():
        return
    x, y = int(round(float(p[0]))), int(round(float(p[1])))
    cv2.rectangle(img, (x - radius, y - radius), (x + radius, y + radius), colour, -1 if filled else 1)


def annotate(img, rec: dict, draw: dict | None, item: Item, rc: dict, acfg: dict):
    import cv2
    out = img.copy()
    col, k, line = acfg["colours_bgr"], acfg["keypoint_radius_px"], acfg["line_px"]
    thr = rc["keypoints"]["body_kp_conf_min"]
    if draw is not None:
        kp, conf = draw["kp"], draw["conf"]
        for a, b in BODY_LINES:
            ok = conf[a] >= thr and conf[b] >= thr
            _line(out, kp[a], kp[b], col["ok"] if ok else col["low"], line)
        for i in range(len(kp)):
            _marker(out, kp[i], k, col["ok"] if conf[i] >= thr else col["low"], bool(conf[i] >= thr))
        x1, y1, x2, y2 = (int(v) for v in draw["box"])
        cv2.rectangle(out, (x1, y1), (x2, y2), (200, 200, 200), 1)
        for b in draw["others"]:
            cv2.rectangle(out, tuple(int(v) for v in b[:2]), tuple(int(v) for v in b[2:]), (120, 120, 120), 1)
        for hand in draw["hands"]:
            lm = np.asarray(hand.landmarks_px, float)
            for a, b in HAND_LINES:
                _line(out, lm[a], lm[b], col["hand"], 1)
            for pt in lm:
                _marker(out, pt, 1, col["hand"], True)
            hb = hand.box
            cv2.rectangle(out, (int(hb[0]), int(hb[1])), (int(hb[2]), int(hb[3])), col["hand_box"], 1)
    lines = [f"{item.look} {item.command} {item.distance_m:g} m take {item.take} frame {rec['index']}"]
    if draw is None:
        lines.append("NO PERSON FOUND")
    else:
        h = rec["hand"]
        lines.append(f"arm {rec['arm']} ({rec['arm_source']}) valid {int(rec['arm_valid'])}  hand {'linked' if rec['hand_linked'] else ('seen' if rec['hand_any'] else 'none')}"
                     + (f" {h['category']} {h['score']}" if h else ""))
        lines.append(f"frame class {rec['frame_class']}  ratio {rec['ratio']}" + (f"  reader {rec['reader']['command']} {rec['reader']['score']}" if rec["reader"] else ""))
    cv2.rectangle(out, (0, 0), (out.shape[1], 8 + 16 * len(lines)), (0, 0, 0), -1)     # solid strip: the text stays readable on any look
    for i, text in enumerate(lines):
        cv2.putText(out, text, (6, 16 + 16 * i), cv2.FONT_HERSHEY_SIMPLEX, 0.45, tuple(col["text"]), 1, cv2.LINE_AA)
    return out


def analyse_item(item: Item, det_fn, cfg: dict, rc: dict, cc: dict, rel_tol: float, out_dir: Path | None) -> dict:
    """All frames of one recording through the models and the reader. det_fn(bgr) -> Detection."""
    import cv2
    hz = cfg["input"]["fallback_frame_hz"]
    pipeline = hp4.PersonsPipeline(rc, cc)
    loaded, errors = [], []
    for png, js in item.files:
        try:
            img = read_image(png)
        except (OSError, ValueError) as e:
            errors.append(f"{png.name}: {e}")
            continue
        hdr, err = read_header(js, img.shape[1], img.shape[0], cfg, rel_tol)
        if err:
            errors.append(err)
            continue
        loaded.append((png, img, hdr))
    arms = sorted({h.arm for _, _, h in loaded if h.arm})
    if len(arms) > 1:
        errors.append(f"{item.name}: frames carry different arm labels {arms}; the first is used")
    arm = arms[0] if arms else None
    use_time = bool(loaded) and all(h.time_s is not None for _, _, h in loaded)
    records, final = [], None
    for i, (png, img, hdr) in enumerate(loaded):
        hdr.arm = arm
        t = hdr.time_s if use_time else (i / hz if item.kind == "sequence" else 0.0)
        rec, draw = analyse_frame(det_fn(img), hdr, t, i, png.name, item, pipeline, rc)
        records.append(rec)
        if out_dir is not None and cfg["annotation"]["enabled"]:
            dest = out_dir / "annotated" / (item.name + ".png" if item.kind == "frame" else f"{item.name}/{png.name}")
            dest.parent.mkdir(parents=True, exist_ok=True)
            dest.write_bytes(cv2.imencode(".png", annotate(img, rec, draw, item, rc, cfg["annotation"]))[1].tobytes())
    if item.kind == "sequence" and records:
        last = records[-1]
        final = last["reader"] or {"command": "NONE", "score": 0.0, "why": "no person in the last frame"}
    seq = None
    if final is not None:
        cmds = [r["reader"]["command"] if r["reader"] else "NONE" for r in records]
        seq = {"final": final, "commands": cmds,
               "first_expected_frame": next((i for i, c in enumerate(cmds) if c == item.command), None)}
    return {"name": item.name, "kind": item.kind, "look": item.look, "command": item.command, "distance_m": item.distance_m,
            "take": item.take, "arm": arm, "n_files": len(item.files), "n_frames": len(records), "errors": errors,
            "sequence": seq, "frames": records}


# ---------------------------------------------------------------- aggregation

def _rate(flags: list[bool]) -> float | None:
    return sum(flags) / len(flags) if flags else None


def _pct(values: list[float], q: float) -> float | None:
    return float(np.percentile(values, q)) if values else None


def metrics(items: list[dict], command: str) -> dict:
    """Rates over every valid frame of the recordings (a lost person is a lost frame: the denominator is all frames)."""
    fr = [f for it in items for f in it["frames"]]
    n = len(fr)
    pf = [f for f in fr if f["person"]]
    seqs = [it for it in items if it["sequence"] is not None]
    kp = {name: _rate([bool(f["person"] and f["kp_ok"][name]) for f in fr]) for name in KEYPOINTS}
    hands = [f for f in fr if f.get("hand")]
    linked = [f for f in fr if f["person"] and f["hand_linked"]]
    ratios = [f["ratio"] for f in fr if f["person"] and f["ratio"] is not None]
    cls = {}
    for f in pf:
        cls[f["frame_class"]] = cls.get(f["frame_class"], 0) + 1
    own_key = {"POINT": "point_ok", "WAIT": "wait_ok", "STOP": "stop_ok"}.get(command)
    finals = [it["sequence"]["final"]["command"] for it in seqs]
    wrong = [c for c in finals if c in gm.COMMANDS and c != command]
    reads = {}
    for c in finals:
        reads[c] = reads.get(c, 0) + 1
    ok_scores = [it["sequence"]["final"]["score"] for it in seqs if it["sequence"]["final"]["command"] == command]
    return {
        "n_items": len(items), "n_frames": n, "n_sequences": len(seqs), "n_singles": len(items) - len(seqs),
        "n_header_or_image_errors": sum(len(it["errors"]) for it in items),
        "person_rate": _rate([f["person"] for f in fr]),
        "multiple_persons_frames": sum(1 for f in fr if f["n_persons"] > 1),
        "keypoint_rates": {k: _r(v) for k, v in kp.items()},
        "arm_valid_rate": _rate([bool(f["person"] and f["arm_valid"]) for f in fr]),
        "hand_any_rate": _rate([bool(f["person"] and f["hand_any"]) for f in fr]),
        "hand_linked_rate": _rate([bool(f["person"] and f["hand_linked"]) for f in fr]),
        "hand_landmarks_inside_rate": _rate([f["hand"]["landmarks_inside"] for f in hands]),
        "hand_world_rate": _rate([f["hand"]["world"] for f in hands]),
        "hand_box_h_px_median": _r(float(np.median([f["hand"]["box_h_px"] for f in linked])), 1) if linked else None,
        "raised_rate": _rate([bool(f["person"] and f["cues"].get("raised")) for f in fr]),
        "finger_up_rate": _rate([bool(f["person"] and f["cues"].get("finger_up")) for f in fr]),
        "open_palm_rate": _rate([bool(f["person"] and f["cues"].get("open_palm")) for f in fr]),
        "category_rate": _rate([bool(f["person"] and f["cues"].get("category_ok")) for f in fr]) if command in EXPECTED_CATEGORY else None,
        "own_cue_rate": _rate([bool(f["person"] and f["flags"][own_key]) for f in fr]) if own_key else None,
        "wrong_class_rate": _rate([bool(f["person"] and f["frame_class"] not in (command, "NONE")) for f in fr]),
        "frame_classes": cls,
        "facing_rate": _rate([bool(f["person"] and f["facing"]) for f in fr]),
        "arm_ratio": {"n": len(ratios), "median": _r(_pct(ratios, 50)), "p95": _r(_pct(ratios, 95)),
                      "min": _r(min(ratios)) if ratios else None, "max": _r(max(ratios)) if ratios else None},
        "sequence_read_rate": _rate([c == command for c in finals]),
        "wrong_read_rate": _rate([c in gm.COMMANDS and c != command for c in finals]),
        "sequence_reads": reads,
        "sequence_read_score_median": _r(float(np.median(ok_scores))) if ok_scores else None,
        "n_wrong_reads": len(wrong),
    }


def _grade_high(v, usable, weak):
    return "usable" if v >= usable - EPS else "weak" if v >= weak - EPS else "fails"


def _grade_low(v, usable, weak):
    return "usable" if v <= usable + EPS else "weak" if v <= weak + EPS else "fails"


def distance_role(d: float, cfg: dict) -> tuple[str, float]:
    """('decisive' | 'secondary' | 'other', the canonical distance)."""
    tol = cfg["distances"]["match_tol_m"]
    for role in ("decisive", "secondary"):
        for ref in cfg["distances"][f"{role}_m"]:
            if abs(d - ref) <= tol + EPS:
                return role, float(ref)
    return "other", round(d, 3)


def grade_group(command: str, m: dict, cfg: dict) -> dict:
    """The declared checks of one group -> {check: {...}} and the group grade (worst of its evaluated checks)."""
    c, mn = cfg["checks"], cfg["minimum_data"]
    enough_frames = m["n_frames"] >= mn["frames_per_group"]
    enough_seq = m["n_sequences"] >= mn["sequences_per_group"]
    out: dict = {}

    def add(name, value, usable, weak, high, applicable=True, cap_weak=False, extra=None):
        if not applicable:
            return
        need_seq = name in ("sequence_read_rate", "wrong_read_rate")
        have = enough_seq if need_seq else enough_frames
        entry = {"value": _r(value), "usable": usable, "weak": weak, "direction": ">=" if high else "<="}
        if not have or value is None:
            entry.update(grade="not_evaluated", note=(f"fewer than {mn['sequences_per_group']} sequences" if need_seq
                                                      else f"fewer than {mn['frames_per_group']} frames"))
        else:
            g = (_grade_high if high else _grade_low)(value, usable, weak)
            if cap_weak and g == "fails":
                g, entry["note"] = "weak", "not required for this command: capped at weak"
            entry["grade"] = g
        if extra:
            entry.update(extra)
        out[name] = entry

    real = command in cfg["input"]["required_commands"]
    add("person_rate", m["person_rate"], c["person_rate"]["usable_min"], c["person_rate"]["weak_min"], True)
    add("arm_valid_rate", m["arm_valid_rate"], c["arm_valid_rate"]["usable_min"], c["arm_valid_rate"]["weak_min"], True,
        applicable=real and c["arm_valid_rate"]["required"][command])
    h = c["hand_linked_rate"]
    add("hand_linked_rate", m["hand_linked_rate"], h["usable_min"], h["weak_min"], True, applicable=real,
        cap_weak=not h["hand_required"][command] if real else False)
    add("own_cue_rate", m["own_cue_rate"], c["own_cue_rate"]["usable_min"], c["own_cue_rate"]["weak_min"], True, applicable=real)
    add("wrong_class_rate", m["wrong_class_rate"], c["wrong_class_rate"]["usable_max"], c["wrong_class_rate"]["weak_max"], False)
    add("sequence_read_rate", m["sequence_read_rate"], c["sequence_read_rate"]["usable_min"], c["sequence_read_rate"]["weak_min"],
        True, applicable=real)
    add("wrong_read_rate", m["wrong_read_rate"], c["wrong_read_rate"]["usable_max"], c["wrong_read_rate"]["weak_max"], False)
    if command == "POINT":
        a = c["arm_ratio_p95"]
        lo, hi = a["assumed"] * (1 - a["low_rel"]), a["assumed"] * (1 + a["high_rel"])
        p95, n = m["arm_ratio"]["p95"], m["arm_ratio"]["n"]
        if p95 is None or n < mn["frames_per_group"]:
            out["arm_ratio_p95"] = {"value": p95, "grade": "n/a", "note": f"fewer than {mn['frames_per_group']} frames with a valid arm: not evaluated, does not block a verdict",
                                    "low": _r(lo), "high": _r(hi), "assumed": a["assumed"]}
        else:
            out["arm_ratio_p95"] = {"value": p95, "grade": "usable" if lo - EPS <= p95 <= hi + EPS else "weak", "low": _r(lo),
                                    "high": _r(hi), "assumed": a["assumed"],
                                    "note": "" if lo - EPS <= p95 <= hi + EPS else "outside the accepted range around the assumed arm length: POINT directions are biased (can only make the look weak)"}
    grades = [e["grade"] for e in out.values() if e["grade"] in GRADE_ORDER]
    return {"checks": out, "grade": next((g for g in GRADE_ORDER if g in grades), "usable")}


def _fmt_check(name: str, e: dict) -> str:
    if name == "arm_ratio_p95":
        return f"arm_ratio_p95 {e['value']} (accepted {e['low']} to {e['high']}; assumed {e['assumed']})"
    return f"{name} {e['value']} (usable {e['direction']} {e['usable']}, weak {e['direction']} {e['weak']})"


def build_report(results: list[dict], problems: list[str], cfg: dict) -> dict:
    """Groups (look, command, distance, arm), pooled (look, command) rows and the verdict per look."""
    groups: dict = {}
    for it in results:
        role, dist = distance_role(it["distance_m"], cfg)
        key = (it["look"], it["command"], dist, it["arm"] or "?")
        groups.setdefault(key, {"role": role, "items": []})["items"].append(it)
    rows = []
    for (look, command, dist, arm), g in sorted(groups.items()):
        m = metrics(g["items"], command)
        gr = grade_group(command, m, cfg)
        rows.append({"look": look, "command": command, "distance_m": dist, "arm": arm, "role": g["role"], "metrics": m,
                     "checks": gr["checks"], "grade": gr["grade"], "recordings": [it["name"] for it in g["items"]]})
    pooled = []
    by_lc: dict = {}
    for it in results:
        by_lc.setdefault((it["look"], it["command"]), []).append(it)
    for (look, command), its in sorted(by_lc.items()):
        pooled.append({"look": look, "command": command, "note": "all distances and arms pooled; not graded",
                       "metrics": metrics(its, command)})
    looks = sorted({r["look"] for r in rows})
    verdicts = {look: verdict_for(look, rows, cfg) for look in looks}
    return {"groups": rows, "pooled": pooled, "verdicts": verdicts, "problems": problems}


def verdict_for(look: str, rows: list[dict], cfg: dict) -> dict:
    mine = [r for r in rows if r["look"] == look]
    labelled = any(r["arm"] in cfg["input"]["arms"] for r in mine)
    arms = list(cfg["input"]["arms"]) if labelled else ["?"]
    reasons: list[str] = []
    worst = {"fails": 0, "insufficient_data": 0, "weak": 0}

    def note(level, text):
        worst[level] += 1
        reasons.append(f"{level}: {text}")

    for d in cfg["distances"]["decisive_m"]:
        for command in cfg["input"]["required_commands"]:
            for arm in arms:
                label = f"{command} at {d:g} m" + (f", {arm} arm" if labelled else "")
                rs = [r for r in mine if r["command"] == command and r["role"] == "decisive" and r["distance_m"] == float(d) and r["arm"] == arm]
                if not rs:
                    note("insufficient_data", f"{label}: no recording")
                    continue
                r = rs[0]
                for name, e in r["checks"].items():
                    if e["grade"] == "fails":
                        note("fails", f"{label}: {_fmt_check(name, e)}")
                    elif e["grade"] == "not_evaluated":
                        note("insufficient_data", f"{label}: {name} not evaluated ({e['note']})")
                    elif e["grade"] == "weak":
                        note("weak", f"{label}: {_fmt_check(name, e)}" + (f" - {e['note']}" if e.get("note") else ""))
    for r in mine:
        label = f"{r['command']} at {r['distance_m']:g} m" + (f", {r['arm']} arm" if r["arm"] in cfg["input"]["arms"] else "")
        if r["role"] == "decisive" and r["command"] not in cfg["input"]["required_commands"]:     # optional NONE control
            for name, e in r["checks"].items():
                if e["grade"] == "fails":
                    note("fails", f"{label} (negative control): {_fmt_check(name, e)}")
                elif e["grade"] == "weak":
                    note("weak", f"{label} (negative control): {_fmt_check(name, e)}")
        elif r["role"] == "secondary":
            for name, e in r["checks"].items():
                if e["grade"] in ("fails", "weak"):
                    note("weak", f"{label} (not the asking distance, lowers at most to weak): {_fmt_check(name, e)}")
    verdict = "fails" if worst["fails"] else "insufficient_data" if worst["insufficient_data"] else "weak" if worst["weak"] else "usable"
    return {"verdict": verdict, "arms_labelled": labelled, "reasons": reasons or ["every decisive check passed its usable bound"]}


# ---------------------------------------------------------------- report files

def _f(x, n=2):
    return "-" if x is None else (f"{x:.{n}f}" if isinstance(x, float) else str(x))


def markdown(report: dict, meta: dict) -> str:
    L = ["# v4 look check", "",
         f"Input folder: `{meta['input_folder']}` ({meta['n_recordings']} recordings, {meta['n_frames']} frames). Config: `look_check.json` "
         f"(declared {meta['declared'][:10]}). Git commit `{(meta['git'].get('commit') or '?')[:10]}`.", "",
         "An engineering check, not an evaluation. Nothing is tuned on it: a look that fails is swapped.", "", "## Verdict per look", ""]
    for look, v in report["verdicts"].items():
        L += [f"### {look}: **{v['verdict']}**", ""]
        L += [f"- {x}" for x in v["reasons"]]
        if not v["arms_labelled"]:
            L.append("- note: no recording carries an arm label, left and right are pooled")
        L.append("")
    L += ["## Groups (look, command, distance, arm)", "",
          "Rates are over all frames of the group (a frame without a person counts as lost). seq = sequences read as recorded / read as another command.", "",
          "| look | command | m | arm | role | frames | seq | person | arm valid | hand linked | own cue | wrong class | seq read / wrong | arm ratio p95 | grade |",
          "|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|"]
    for r in report["groups"]:
        m = r["metrics"]
        L.append(f"| {r['look']} | {r['command']} | {r['distance_m']:g} | {r['arm']} | {r['role']} | {m['n_frames']} | {m['n_sequences']} | "
                 f"{_f(m['person_rate'])} | {_f(m['arm_valid_rate'])} | {_f(m['hand_linked_rate'])} | {_f(m['own_cue_rate'])} | "
                 f"{_f(m['wrong_class_rate'])} | {_f(m['sequence_read_rate'])} / {_f(m['wrong_read_rate'])} | {_f(m['arm_ratio']['p95'])} | {r['grade']} |")
    L += ["", "## Body keypoints and hands (per group)", "",
          "Keypoint rates: share of frames in which the keypoint is above body_kp_conf_min. Hand rows: any hand found in the person crop, "
          "linked to the recorded arm, all 21 landmarks inside the image, world landmarks present, median hand box height in pixels.", "",
          "| look | command | m | arm | L/R shoulder | L/R elbow | L/R wrist | L/R hip | hand any | linked | 21 inside | world | box h px |",
          "|---|---|---|---|---|---|---|---|---|---|---|---|---|"]
    for r in report["groups"]:
        m, k = r["metrics"], r["metrics"]["keypoint_rates"]
        L.append(f"| {r['look']} | {r['command']} | {r['distance_m']:g} | {r['arm']} | {_f(k['left_shoulder'])}/{_f(k['right_shoulder'])} | "
                 f"{_f(k['left_elbow'])}/{_f(k['right_elbow'])} | {_f(k['left_wrist'])}/{_f(k['right_wrist'])} | {_f(k['left_hip'])}/{_f(k['right_hip'])} | "
                 f"{_f(m['hand_any_rate'])} | {_f(m['hand_linked_rate'])} | {_f(m['hand_landmarks_inside_rate'])} | {_f(m['hand_world_rate'])} | {_f(m['hand_box_h_px_median'], 0)} |")
    L += ["", "## Per-frame cues (per group)", "",
          "raised = recorded arm raised; finger up = index extended, other fingers curled, pointing up; open palm = four fingers extended and spread; "
          "category = MediaPipe category is the one the command needs (WAIT: Pointing_Up, STOP: Open_Palm). Frame classes: the command each frame alone would read.", "",
          "| look | command | m | arm | raised | finger up | open palm | category | facing | frame classes | arm ratio median (min-max) | sequence reads |",
          "|---|---|---|---|---|---|---|---|---|---|---|---|"]
    for r in report["groups"]:
        m = r["metrics"]
        ar = m["arm_ratio"]
        ratio = f"{_f(ar['median'])} ({_f(ar['min'])} to {_f(ar['max'])})" if ar["median"] is not None else "-"
        L.append(f"| {r['look']} | {r['command']} | {r['distance_m']:g} | {r['arm']} | {_f(m['raised_rate'])} | {_f(m['finger_up_rate'])} | {_f(m['open_palm_rate'])} | "
                 f"{_f(m['category_rate'])} | {_f(m['facing_rate'])} | {json.dumps(m['frame_classes'])} | {ratio} | {json.dumps(m['sequence_reads'])} |")
    L += ["", "## Per look and command (all distances and arms pooled, not graded)", "",
          "| look | command | frames | sequences | person | arm valid | hand linked | own cue | wrong class | seq read / wrong |", "|---|---|---|---|---|---|---|---|---|---|"]
    for r in report["pooled"]:
        m = r["metrics"]
        L.append(f"| {r['look']} | {r['command']} | {m['n_frames']} | {m['n_sequences']} | {_f(m['person_rate'])} | {_f(m['arm_valid_rate'])} | "
                 f"{_f(m['hand_linked_rate'])} | {_f(m['own_cue_rate'])} | {_f(m['wrong_class_rate'])} | {_f(m['sequence_read_rate'])} / {_f(m['wrong_read_rate'])} |")
    L += ["", "## Checks that decided a group", ""]
    for r in report["groups"]:
        L.append(f"- {r['look']} {r['command']} {r['distance_m']:g} m {r['arm']} ({r['role']}): **{r['grade']}**")
        for name, e in r["checks"].items():
            L.append(f"  - {_fmt_check(name, e)} -> {e['grade']}" + (f" ({e['note']})" if e.get("note") else ""))
    if report["problems"] or meta["item_errors"]:
        L += ["", "## Problems with the input", ""] + [f"- {p}" for p in report["problems"] + meta["item_errors"]]
    L.append("")
    return "\n".join(L)


def manifest(folder: Path) -> list[dict]:
    out = []
    for p in sorted(folder.rglob("*")):
        if p.is_file() and not p.name.startswith("."):
            out.append({"path": p.relative_to(folder).as_posix(), "bytes": p.stat().st_size,
                        "sha256": hashlib.sha256(p.read_bytes()).hexdigest()})
    return out


def run_check(input_dir: Path, detector, cfg: dict, cfg_path: Path, out: Path, annotate_png: bool = True,
              command: str = "look_check_v4.py") -> dict:
    """Run the check on a folder with a detector (RealDetector or a fake). Writes the files into out and returns the report."""
    cfg = json.loads(json.dumps(cfg))
    cfg["annotation"]["enabled"] = bool(cfg["annotation"]["enabled"] and annotate_png)
    rc, cc = gm.load_config(), cm.load_config()
    bridge_cfg_path = dio.resolve("configs/v4/bridge.json")
    rel_tol = float(json.loads(bridge_cfg_path.read_text(encoding="utf-8"))["intrinsics_rel_tol"])
    items, problems = discover(input_dir, cfg)
    results = [analyse_item(it, detector.detect, cfg, rc, cc, rel_tol, out) for it in items]
    report = build_report(results, problems, cfg)
    item_errors = [e for r in results for e in r["errors"]]
    n_frames = sum(r["n_frames"] for r in results)
    import hri_perception as hpm
    perc_cfg_path = dio.resolve(hpm.DEFAULT_CONFIG)
    perc_cfg = json.loads(perc_cfg_path.read_text(encoding="utf-8"))
    paths = [cfg_path, dio.resolve(gm.DEFAULT_CONFIG), dio.resolve(cm.DEFAULT_CONFIG), bridge_cfg_path, perc_cfg_path,
             dio.resolve(perc_cfg["stop"]["adapter_config"])]
    cfg_hashes = dio.copy_configs(out, paths)
    meta = {"input_folder": input_dir.name, "n_recordings": len(results), "n_frames": n_frames, "declared": cfg["declared"],
            "git": dio.git_info(), "item_errors": item_errors}
    full = {"tool": "look_check_v4.py", "kind": "engineering check, not an evaluation", "verdicts": report["verdicts"],
            "groups": report["groups"], "pooled": report["pooled"], "problems": problems + item_errors,
            "recordings": results}
    dio.write_json(out / "report.json", full)
    (out / "report.md").write_text(markdown(report, meta), encoding="utf-8")
    dio.write_json(out / "run.json", {
        "created": datetime.now().isoformat(timespec="seconds"), "command": command, "git": meta["git"],
        "python": platform.python_version(), "platform": platform.platform(),
        "config": "{project_root}/" + Path(cfg_path).resolve().relative_to(HERE).as_posix() if HERE in Path(cfg_path).resolve().parents else Path(cfg_path).name,
        "config_sha256": cfg_hashes, "input_folder": input_dir.name, "input_manifest": manifest(input_dir),
        "pose_weights_sha256": perc_cfg["pose_model"]["sha256"],
        "models": detector.runtime() if hasattr(detector, "runtime") else {}})
    return full


def main(argv=None, detector=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--input", required=True, help="folder of recordings from Nusrat (docs/look_check_v4.md)")
    ap.add_argument("--config", default=DEFAULT_CONFIG)
    ap.add_argument("--no-annotate", action="store_true", help="do not write the annotated PNGs")
    ap.add_argument("--device", default=None, help="cpu, cuda or mps (default: CUDA, then MPS, then CPU)")
    a = ap.parse_args(argv)
    folder = Path(a.input)
    if not folder.is_dir():
        raise SystemExit(f"--input {folder} is not a folder")
    cfg_path = dio.resolve(a.config)
    cfg = load_config(cfg_path)
    out = dio.new_run_dir(cfg, "look_check_v4")
    own = detector is None
    det = detector if detector is not None else RealDetector(a.device)
    try:
        full = run_check(folder, det, cfg, cfg_path, out, not a.no_annotate,
                         command=" ".join(["look_check_v4.py", "--input", folder.name] + (["--no-annotate"] if a.no_annotate else [])
                                          + (["--config", a.config] if a.config != DEFAULT_CONFIG else [])
                                          + (["--device", a.device] if a.device else [])))
    finally:
        if own:
            det.close()
    print((out / "report.md").read_text(encoding="utf-8"))
    print(f"Folder: {out}")
    for look, v in full["verdicts"].items():
        print(f"{look}: {v['verdict']}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
