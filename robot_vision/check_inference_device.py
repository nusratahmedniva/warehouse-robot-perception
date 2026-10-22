"""Which device and precision each perception model actually runs with (read-only check, 2026-10-22).

    python check_inference_device.py                 print the report (JSON)
    python check_inference_device.py --save          also write outputs/device_check_<time>/device_check.json

Loads the perception exactly as the bridge server does (configs/hri_perception.json: pose weights hash check, device
selection, both YOLO11s-pose models, the MediaPipe STOP adapter, the full warm-up), then reads per model the device
(CUDA GPU name, MPS or CPU) and precision (FP32 / FP16) from the live predictors, the library versions, and the
dtype the weights are stored in. It is the same reader the server writes into run_info.json -> inference_devices.
Changes no setting and runs no live frame. Unity need not run; with the bridge server running, both share the GPU.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))


def stored_dtypes(weights: Path) -> list[str]:
    """dtypes of the parameters as saved in the .pt checkpoint (Ultralytics saves FP16; loading makes it FP32)."""
    import torch
    ckpt = torch.load(weights, map_location="cpu", weights_only=False)
    m = ckpt.get("ema") or ckpt["model"]
    return sorted({str(p.dtype).replace("torch.", "") for p in m.parameters()})


def report(perception_config: str | Path = "configs/hri_perception.json") -> dict:
    import hri_perception as hpm
    cfg = hpm.load_config(hpm.resolve(perception_config))
    p = hpm.HriPerception(cfg)
    try:
        out = p.inference_devices()
    finally:
        p.close()
    w = hpm.resolve(cfg["pose_model"]["weights"])
    out["pose_weights"] = {"path": w.relative_to(HERE).as_posix() if w.is_relative_to(HERE) else w.name,
                           "sha256": cfg["pose_model"]["sha256"], "stored_dtypes": stored_dtypes(w)}
    out["perception_config"] = Path(perception_config).as_posix()
    return out


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--perception-config", default="configs/hri_perception.json")
    ap.add_argument("--save", action="store_true", help="write outputs/device_check_<time>/ (config, git commit)")
    a = ap.parse_args(argv)
    r = report(a.perception_config)
    print(json.dumps(r, indent=2))
    if a.save:
        import decision_io as dio
        bridge_cfg = dio.read_json("configs/bridge.json")
        out = dio.new_run_dir(bridge_cfg, "device_check")
        dio.copy_configs(out, [dio.resolve(a.perception_config)])
        dio.write_json(out / "device_check.json", {"git": dio.git_info(), "command": " ".join(sys.argv), **r})
        print(f"[device_check] saved {out / 'device_check.json'}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
