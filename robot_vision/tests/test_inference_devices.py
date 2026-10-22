"""run_info.json -> inference_devices: per model the device and precision actually used, read at runtime (logging only)."""

import json
import sys
import tempfile
import types
import unittest
from pathlib import Path

HERE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(HERE))

import torch  # noqa: E402

import gesture_adapter as ga  # noqa: E402
import hri_perception as hpm  # noqa: E402
from bridge import server  # noqa: E402

WEIGHTS = HERE / "models" / "yolo11s-pose.pt"


def fake_yolo(net=None, live=None):
    """Ultralytics 8.4 layout: YOLO.model (loaded) and YOLO.predictor.model.backend.model (live)."""
    pred = None
    if live is not None:
        pred = types.SimpleNamespace(model=types.SimpleNamespace(backend=types.SimpleNamespace(model=live)))
    return types.SimpleNamespace(model=net, predictor=pred)


class YoloRuntimeTests(unittest.TestCase):
    def test_live_predictor_fp32_cpu(self):
        r = hpm.yolo_runtime(fake_yolo(torch.nn.Linear(2, 2).half(), live=torch.nn.Linear(2, 2)))
        self.assertEqual((r["device"], r["precision"], r["dtype"]), ("CPU", "FP32", "float32"))
        self.assertEqual(r["read_from"], "predictor model parameters")     # the live one, not the loaded one

    def test_fp16_reported(self):
        r = hpm.yolo_runtime(fake_yolo(live=torch.nn.Linear(2, 2).half()))
        self.assertEqual((r["precision"], r["dtype"]), ("FP16", "float16"))

    def test_no_predictor_reads_loaded_model(self):
        r = hpm.yolo_runtime(fake_yolo(torch.nn.Linear(2, 2)))
        self.assertEqual(r["read_from"], "loaded model parameters (no predictor yet)")
        self.assertEqual(r["precision"], "FP32")

    def test_mixed_precision_not_hidden(self):
        net = torch.nn.Sequential(torch.nn.Linear(2, 2), torch.nn.Linear(2, 2).half())
        self.assertEqual(hpm.yolo_runtime(fake_yolo(live=net))["precision"], "mixed")

    def test_no_parameters_is_unknown(self):
        r = hpm.yolo_runtime(fake_yolo(torch.nn.Identity()))
        self.assertEqual((r["device"], r["precision"]), ("unknown", "unknown"))

    @unittest.skipUnless(torch.cuda.is_available(), "no CUDA device")
    def test_cuda_gpu_name(self):
        r = hpm.yolo_runtime(fake_yolo(live=torch.nn.Linear(2, 2).cuda()))
        self.assertEqual(r["device"], "CUDA " + torch.cuda.get_device_name(0))

    @unittest.skipUnless(WEIGHTS.exists(), "pose weights not present (git-ignored)")
    def test_real_ultralytics_layout(self):
        import numpy as np
        from ultralytics import YOLO
        m = YOLO(str(WEIGHTS), task="pose")
        self.assertEqual(hpm.yolo_runtime(m)["read_from"], "loaded model parameters (no predictor yet)")
        m.predict(np.zeros((64, 64, 3), np.uint8), imgsz=64, device="cpu", verbose=False)
        r = hpm.yolo_runtime(m)
        self.assertEqual((r["read_from"], r["device"], r["precision"]), ("predictor model parameters", "CPU", "FP32"))


class MediaPipeRuntimeTests(unittest.TestCase):
    def adapter(self, delegate):
        a = object.__new__(ga.GestureRecognizerAdapter)
        a.delegate = delegate
        return a.runtime()

    def test_default_delegate_is_cpu_precision_unknown(self):
        r = self.adapter(None)
        self.assertEqual((r["device"], r["precision"]), ("CPU", "unknown"))
        self.assertIn("default", r["delegate"])

    def test_gpu_delegate_named(self):
        self.assertEqual(self.adapter(types.SimpleNamespace(name="GPU"))["device"], "GPU")


class RunInfoTests(unittest.TestCase):
    def test_versions_listed(self):
        v = hpm.library_versions()
        for k in ("python", "torch", "torch_cuda_build", "ultralytics", "mediapipe"):
            self.assertIn(k, v)
        self.assertEqual(v["torch"], torch.__version__)

    def test_written_to_run_info(self):
        devices = {"models": {"yolo11s-pose/cam360": {"device": "CPU", "precision": "FP32"}}, "versions": {}}
        fake = types.SimpleNamespace(inference_devices=lambda: devices)
        with tempfile.TemporaryDirectory() as d:
            p = Path(d) / "run_info.json"
            info = {"mode": "guide"}
            p.write_text(json.dumps(info), encoding="utf-8")
            self.assertEqual(server.record_inference_devices(p, info, fake), devices)
            saved = json.loads(p.read_text(encoding="utf-8"))
            self.assertEqual(saved, {"mode": "guide", "inference_devices": devices})   # nothing else changed

    def test_reader_error_is_logged_not_raised(self):
        def boom():
            raise RuntimeError("no device")
        with tempfile.TemporaryDirectory() as d:
            p = Path(d) / "run_info.json"
            server.record_inference_devices(p, {}, types.SimpleNamespace(inference_devices=boom))
            self.assertIn("no device", json.loads(p.read_text(encoding="utf-8"))["inference_devices"]["error"])

    def test_perception_without_reader_leaves_run_info(self):
        with tempfile.TemporaryDirectory() as d:
            p = Path(d) / "run_info.json"
            self.assertIsNone(server.record_inference_devices(p, {}, object()))
            self.assertFalse(p.exists())


if __name__ == "__main__":
    unittest.main()
