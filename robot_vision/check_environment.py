"""Report the Python/PyTorch environment and verify a compute device with a real tensor operation.

Usage:
    python check_environment.py --device cuda    # fail if CUDA is not usable
    python check_environment.py --device auto    # CUDA, then MPS, then CPU
"""

from __future__ import annotations

import argparse
import platform
import shutil
import subprocess
import sys

import torch


def select_device(mode: str) -> torch.device:
    """Return the requested device. Explicit modes never fall back to another device."""
    mode = mode.lower()
    mps_ok = hasattr(torch.backends, "mps") and torch.backends.mps.is_available()
    if mode == "cuda":
        if not torch.cuda.is_available():
            raise RuntimeError(
                "CUDA was requested but torch.cuda.is_available() is False. "
                f"Installed torch {torch.__version__} (built for CUDA {torch.version.cuda}). "
                "Install a CUDA-enabled PyTorch build or choose --device auto/cpu.")
        return torch.device("cuda")
    if mode == "mps":
        if not mps_ok:
            raise RuntimeError("MPS was requested but torch.backends.mps.is_available() is False.")
        return torch.device("mps")
    if mode == "cpu":
        return torch.device("cpu")
    if mode == "auto":
        if torch.cuda.is_available():
            return torch.device("cuda")
        if mps_ok:
            return torch.device("mps")
        return torch.device("cpu")
    raise ValueError(f"Unknown device mode '{mode}' (use auto, cuda, mps or cpu)")


def device_name(device: torch.device) -> str:
    if device.type == "cuda":
        return torch.cuda.get_device_name(device)
    if device.type == "mps":
        return f"Apple MPS ({platform.machine()})"
    return f"CPU ({platform.processor() or platform.machine()})"


def verify_device(device: torch.device) -> float:
    """Run a small matrix multiply on the device and check it against the CPU result."""
    a = torch.arange(16, dtype=torch.float32).reshape(4, 4)
    expected = a @ a.T
    result = (a.to(device) @ a.to(device).T).cpu()
    if not torch.allclose(result, expected):
        raise RuntimeError(f"Tensor check on {device} returned a wrong result")
    return float(result.sum())


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--device", default="auto", choices=["auto", "cuda", "mps", "cpu"])
    args = parser.parse_args()

    print(f"Python      : {sys.version.split()[0]} ({sys.executable})")
    print(f"Platform    : {platform.platform()} / {platform.machine()}")
    print(f"PyTorch     : {torch.__version__} (CUDA build: {torch.version.cuda})")
    print(f"CUDA usable : {torch.cuda.is_available()}")
    mps = hasattr(torch.backends, "mps") and torch.backends.mps.is_available()
    print(f"MPS usable  : {mps}")
    for pkg in ("torchvision", "transformers", "huggingface_hub", "numpy", "PIL", "matplotlib"):
        try:
            mod = __import__(pkg)
            print(f"{pkg:<12}: {mod.__version__}")
        except ImportError as exc:
            print(f"{pkg:<12}: NOT IMPORTABLE ({exc})")
    if shutil.which("nvidia-smi"):
        out = subprocess.run(["nvidia-smi", "--query-gpu=name,driver_version,memory.total",
                              "--format=csv,noheader"], capture_output=True, text=True)
        print(f"nvidia-smi  : {out.stdout.strip() or out.stderr.strip()}")
    else:
        print("nvidia-smi  : not found")

    device = select_device(args.device)
    print(f"Selected    : {device} - {device_name(device)}")
    checksum = verify_device(device)
    print(f"Tensor test : OK on {device} (checksum {checksum:.1f})")


if __name__ == "__main__":
    main()
