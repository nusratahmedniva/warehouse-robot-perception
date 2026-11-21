"""AUDIT.md 16.31.1 (declared 2026-11-21): the avatar experiment's intervals use the TAKE as the unit. The numbers are those of the navigation
bootstrap block (2000 resamples, seed 1), never a Wilson interval over frames. The floor is the declared one."""

import json
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CFG = json.loads((ROOT / "configs/v4/analysis.json").read_text(encoding="utf-8"))


class AvatarProtocolConfigTests(unittest.TestCase):
    def test_the_unit_is_the_take_and_the_bootstrap_numbers_are_the_declared_ones(self):
        a = CFG["avatar_experiment"]
        self.assertEqual(a["unit"], "take")
        b = CFG["bootstrap"]
        self.assertEqual((b["n_resamples"], b["seed"], b["percentiles"]), (2000, 1, [2.5, 97.5]))
        self.assertIn("n_resamples 2000, seed 1", a["bootstrap"])
        self.assertEqual(b["unit"], "run")                                       # the navigation analysis is unchanged

    def test_wilson_is_for_take_level_outcomes_only_and_never_for_frames(self):
        text = CFG["avatar_experiment"]["wilson"]
        self.assertIn("take-level yes/no", text)
        self.assertIn("never over frames", text)
        self.assertIn("share per take", CFG["avatar_experiment"]["frame_measures"])

    def test_the_floor_is_two_sequences_and_ten_single_takes(self):
        f = CFG["avatar_experiment"]["floor"]
        self.assertEqual((f["sequences_min"], f["single_takes_min"]), (2, 10))

    def test_the_protocol_text_and_the_audit_agree_with_the_config(self):
        repo = ROOT.parent
        doc = (repo / "docs/avatar_experiment_protocol_v4.md").read_text(encoding="utf-8")
        audit = (repo / "AUDIT.md").read_text(encoding="utf-8")
        self.assertIn("#### 16.31.1 DECLARED", audit)
        for needle in ("2000", "seed 1", "at least 2 sequences", "at least 10 single", "never a Wilson interval over frames"):
            self.assertIn(needle.lower(), doc.lower(), needle)


if __name__ == "__main__":
    unittest.main()
