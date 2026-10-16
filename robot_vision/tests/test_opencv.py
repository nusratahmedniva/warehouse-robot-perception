"""cv2 comes from two packages: opencv-python (required by ultralytics) and opencv-contrib-python (required by
mediapipe). Both install the same cv2 module, so they must stay at the same version. These checks run in CI on
Windows and macOS. Run from robot_vision/:  python -m unittest discover -s tests -v"""

import re
import sys
import unittest
from importlib.metadata import PackageNotFoundError, version
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import cv2  # noqa: E402

# every cv2 name the pipeline uses (grep "cv2\." over robot_vision/*.py)
USED = ["imdecode", "imencode", "cvtColor", "resize", "rectangle", "putText", "getTextSize", "VideoWriter",
        "VideoWriter_fourcc", "VideoCapture", "FONT_HERSHEY_SIMPLEX", "LINE_AA", "INTER_LINEAR", "INTER_AREA",
        "IMREAD_COLOR", "COLOR_BGR2RGB", "CAP_PROP_FRAME_WIDTH", "CAP_PROP_FRAME_HEIGHT", "CAP_PROP_FRAME_COUNT",
        "CAP_PROP_FOURCC", "CAP_PROP_FPS"]


def pins() -> dict[str, str]:
    out = {}
    for line in (ROOT / "requirements.txt").read_text(encoding="utf-8").splitlines():
        m = re.match(r"^(opencv-python|opencv-contrib-python)==([\w.]+)", line.strip())
        if m:
            out[m.group(1)] = m.group(2)
    return out


class OpenCVTests(unittest.TestCase):
    def test_both_packages_pinned_to_the_same_version(self):
        p = pins()
        self.assertEqual(set(p), {"opencv-python", "opencv-contrib-python"})
        self.assertEqual(p["opencv-python"], p["opencv-contrib-python"])

    def test_installed_versions_match_the_pin(self):
        pin = pins()["opencv-python"]
        self.assertEqual(version("opencv-python"), pin)
        try:
            self.assertEqual(version("opencv-contrib-python"), pin)
        except PackageNotFoundError:
            pass  # absent only where mediapipe is not installed (no Intel macOS wheel)
        self.assertEqual(cv2.__version__, ".".join(pin.split(".")[:3]))

    def test_used_names_exist(self):
        missing = [n for n in USED if not hasattr(cv2, n)]
        self.assertEqual(missing, [])

    def test_used_names_cover_the_pipeline(self):
        names = set()
        for f in ROOT.glob("*.py"):
            names |= set(re.findall(r"\bcv2\.(\w+)", f.read_text(encoding="utf-8")))
        self.assertEqual(sorted(names - set(USED)), [])

    def test_used_functions_work(self):
        rgb = np.zeros((40, 60, 3), np.uint8)
        rgb[10:20, 10:30] = (255, 0, 0)
        ok, buf = cv2.imencode(".png", rgb)
        self.assertTrue(ok)
        back = cv2.imdecode(buf, cv2.IMREAD_COLOR)
        self.assertTrue(np.array_equal(back, rgb))
        self.assertEqual(tuple(cv2.cvtColor(back, cv2.COLOR_BGR2RGB)[15, 15]), (0, 0, 255))
        self.assertEqual(cv2.resize(rgb, (120, 80), interpolation=cv2.INTER_LINEAR).shape, (80, 120, 3))
        self.assertEqual(cv2.resize(rgb, (30, 20), interpolation=cv2.INTER_AREA).shape, (20, 30, 3))
        img = rgb.copy()
        cv2.rectangle(img, (1, 1), (5, 5), (0, 255, 0), 1)
        cv2.putText(img, "STOP", (2, 30), cv2.FONT_HERSHEY_SIMPLEX, 0.4, (255, 255, 255), 1, cv2.LINE_AA)
        self.assertGreater(int(img.sum()), int(rgb.sum()))
        (w, h), _ = cv2.getTextSize("STOP", cv2.FONT_HERSHEY_SIMPLEX, 0.4, 1)
        self.assertGreater(w, 0)
        self.assertIsInstance(cv2.VideoWriter_fourcc(*"mp4v"), int)


if __name__ == "__main__":
    unittest.main()
