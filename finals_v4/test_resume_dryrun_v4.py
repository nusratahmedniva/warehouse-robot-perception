"""Tests of resume_dryrun_v4.py (Avatar/Config/experiments_ab.md section 15 addendum 13): the resume of a final, end to end on synthetic
folders, with Anisha's final_guard_v4.py, the launcher (-DryRun -Resume -OutputRoot) and the B11 check (-ResumeMarker). No Unity Play, no
server, no real final; everything is written into a temporary folder. Windows only (PowerShell)."""
import os
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import resume_dryrun_v4 as rd  # noqa: E402


@unittest.skipUnless(os.name == "nt", "the launcher and the check are Windows PowerShell scripts")
class ResumeDryRunTests(unittest.TestCase):
    def test_every_step_of_the_flow(self):
        with tempfile.TemporaryDirectory() as tmp:
            steps = rd.demo(Path(tmp))
            failed = {k: ok for k, ok in rd.verdicts(steps).items() if not ok}
            self.assertEqual(failed, {}, {k: steps for k in failed} if failed else "")


if __name__ == "__main__":
    unittest.main()
