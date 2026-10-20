"""The configuration of the final guided-robot trials is frozen: hashes and fixed trial settings must not change."""

import hashlib
import json
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
FROZEN = json.loads((REPO / "robot_vision" / "configs" / "hri_frozen.json").read_text(encoding="utf-8"))


class FrozenConfigTests(unittest.TestCase):
    def test_hashes_unchanged(self):
        for rel, digest in FROZEN["sha256"].items():
            # Hashes were taken with LF endings; a Windows checkout (core.autocrlf) has CRLF, same content.
            data = (REPO / rel).read_bytes().replace(b"\r\n", b"\n")
            self.assertEqual(hashlib.sha256(data).hexdigest(), digest, f"{rel} changed after freezing (disclose and re-freeze)")

    def test_flags_set(self):
        for rel in ("robot_vision/configs/hri_control.json", "robot_vision/configs/hri_perception.json"):
            self.assertTrue(json.loads((REPO / rel).read_text(encoding="utf-8"))["frozen"], rel)

    def test_trial_settings_fixed(self):
        trials = json.loads((REPO / "robot_vision" / "configs" / "trials.json").read_text(encoding="utf-8"))
        for k, v in FROZEN["trials_fixed"].items():
            self.assertEqual(trials[k], v, k)


if __name__ == "__main__":
    unittest.main()
