"""The timeout from the step-5 runs (AUDIT.md 16.20.5.1): final_guard_v4.py --timeout-from pools the step-5 development runs of ALL 13 settings ONCE, lists the runs that are excluded
with their outcome and prints the timeout the declared rule gives (1.5 x the longest SUCCESSFUL run, rounded up to a multiple of 30 s, never below 270 s). Synthetic sessions in the three
source forms (the step-5 zip of finals_v4/step5_zip_v4.py read in place, the step-5 manifest, NAME=<session folder>); nothing is written unless --out is given."""

import contextlib
import hashlib
import io
import json
import sys
import tempfile
import unittest
import warnings
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import final_guard_v4 as fg  # noqa: E402

SETTINGS = list(fg.plan()["settings"])


def run(trial, total=100.0, outcome="SUCCESS", reason="none", mode="development", **kw):
    d = {"trial": trial, "task": "Task2", "mode": mode, "seed": 1, "outcome": outcome, "failure_reason": reason, "total_s": total}
    d.update(kw)
    return {k: v for k, v in d.items() if v is not None}


def base_runs():
    """3 successful runs of 100, 110 and 120 s in every setting."""
    return {st: [run(1, 100.0), run(2, 110.0), run(3, 120.0)] for st in SETTINGS}


def with_changes(changes):
    runs = base_runs()
    runs.update(changes)
    return runs


def sessions_of(runs, prefix="t0_", timeout_s=900):
    return [{"setting": f"{prefix}{st}", "unity": f"trials_development_Task2_{st}_20261121_100000", "timeout_s": timeout_s, "runs": rs} for st, rs in runs.items()]


def write_zip(path: Path, sessions, manifest=True, noise=True):
    with zipfile.ZipFile(path, "w") as z, warnings.catch_warnings():
        warnings.simplefilter("ignore")                                                  # a test may write the same name twice on purpose (a repeated trial, two sessions)
        if manifest:
            z.writestr("MANIFEST.json", json.dumps({"what": "step 5", "sessions": [{k: v for k, v in s.items() if k != "runs"} for s in sessions]}))
        for s in sessions:
            base = f"{s['setting']}/{s['unity']}/"
            for r in s["runs"]:
                z.writestr(f"{base}truth_run{r['trial']:03d}.json" if r.get("trial") is not None else f"{base}truth_run099.json", json.dumps(r))
            if noise:                                                                    # the other files of a session folder are not runs
                z.writestr(f"{base}session.json", json.dumps({"mode": "development"}))
                z.writestr(f"{base}truth_run001.csv", "t,x,z\n")
                z.writestr(f"{base}run_001/truth.jsonl", "{}\n")
                z.writestr(f"{s['setting']}/bridge_guide_x/summary.json", json.dumps({"outcome": "SUCCESS", "total_s": 9999.0}))


def write_folders(root: Path, sessions):
    out = []
    for s in sessions:
        d = root / s["unity"]
        d.mkdir(parents=True)
        for r in s["runs"]:
            (d / f"truth_run{r['trial']:03d}.json").write_text(json.dumps(r), encoding="utf-8")
        (d / "session.json").write_text("{}", encoding="utf-8")
        out.append((s["setting"], d))
    return out


def cli(*args):
    buf = io.StringIO()
    with contextlib.redirect_stdout(buf):
        code = fg.main(list(args))
    return code, buf.getvalue()


class Rule(unittest.TestCase):
    """The declared rule itself is pinned by tests/test_v4_frozen.py; here it is only what the command line must reproduce."""

    def test_the_13_settings_come_from_the_plan(self):
        self.assertEqual(len(SETTINGS), 13)
        self.assertEqual(fg.STEP5_PREFIX, "t0_")
        self.assertEqual(fg.STEP5_RUNS_PER_SETTING, 3)
        self.assertEqual(fg.MIN_DEVELOPMENT_TIMEOUT_S, 420.0)


class Pooling(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.dir = Path(self.tmp.name)

    def tearDown(self):
        self.tmp.cleanup()

    def mixed(self):
        return with_changes({
            "B3": [run(1, 150.0), run(2, 312.4), run(3, 140.0)],                                                     # the longest successful run of the pool
            "A4": [run(1, 200.0), run(2, 210.0), run(3, 900.0, "FAILURE", "timeout")],                                # a timeout: 900 s is not a duration
            "B4": [run(1, 600.0, "FAILURE", "aborted"), run(2, 180.0), run(3, 170.0)],                                # an abort: no duration
            "B3_off": [run(1, 40.0, "FAILURE", "collision"), run(2, 130.0), run(3, 135.0)],
        })

    def test_one_value_from_the_pooled_successful_runs_of_all_13_settings(self):
        z = self.dir / "step5.zip"
        write_zip(z, sessions_of(self.mixed()))
        code, out = cli("--timeout-from", str(z))
        self.assertEqual(code, 0, out)
        self.assertIn("Pooled: 39 runs of 13 settings; 36 successful, 3 excluded (1 timed out, 2 other failures)", out)
        self.assertIn("Longest SUCCESSFUL run: 312.4 s (B3 trial 2)", out)
        self.assertIn("1.5 x 312.4 = 468.6, rounded up to a multiple of 30 s, never below 270 s = 480 s", out)         # 468.6 -> 480
        flat = [r for st in SETTINGS for r in self.mixed()[st]]
        self.assertEqual(fg.development_timeout(flat)["timeout_s"], 480.0)                                             # the same number as the function on the pooled list
        # not per setting: the largest of the per-setting values would be the same here, the mean or any subset would not
        per_setting = [fg.development_timeout(self.mixed()[st])["timeout_s"] if any(r["outcome"] == "SUCCESS" for r in self.mixed()[st]) else None for st in SETTINGS]
        self.assertGreater(len({v for v in per_setting if v is not None}), 1)
        self.assertEqual(code, 0)

    def test_excluded_runs_are_listed_with_their_outcome_and_do_not_count(self):
        z = self.dir / "step5.zip"
        write_zip(z, sessions_of(self.mixed()))
        _, out = cli("--timeout-from", str(z))
        self.assertIn("Excluded from the rule (3):", out)
        self.assertIn("A4 trial 3: FAILURE / timeout, 900.0 s", out)
        self.assertIn("B4 trial 1: FAILURE / aborted, 600.0 s", out)
        self.assertIn("B3_off trial 1: FAILURE / collision, 40.0 s", out)
        self.assertIn("| A4 | 3 | FAILURE | timeout | 900.0 | NO: gives no duration (timed out: its cause must be found before the freeze, 16.16 decision 4) |", out)
        self.assertIn("| B4 | 1 | FAILURE | aborted | 600.0 | NO: gives no duration |", out)
        self.assertIn("CAUSE NEEDED BEFORE THE FREEZE: 1 development run(s) timed out", out)
        self.assertNotIn("900 s =", out)

    def test_the_rounding_up_and_the_floor(self):
        for longest, want in ((300.0, 450), (300.1, 480), (180.0, 270), (181.0, 300), (120.0, 270)):
            z = self.dir / f"step5_{longest}.zip"
            write_zip(z, sessions_of(with_changes({"A1": [run(1, longest), run(2, 50.0), run(3, 60.0)], **{st: [run(1, 100.0), run(2, 100.0), run(3, 100.0)] for st in SETTINGS if st != "A1"}})))
            code, out = cli("--timeout-from", str(z))
            self.assertEqual(code, 0)
            self.assertIn(f"= {want} s\n", out + "\n", longest)

    def test_no_clean_run_means_no_cause_line_and_no_excluded_runs(self):
        z = self.dir / "clean.zip"
        write_zip(z, sessions_of(base_runs()))
        code, out = cli("--timeout-from", str(z))
        self.assertEqual(code, 0)
        self.assertIn("Excluded from the rule (0):\n  none", out)
        self.assertNotIn("CAUSE NEEDED", out)
        self.assertIn("= 270 s", out)                                                                                  # 1.5 x 120 = 180 -> the floor

    def test_the_plan_is_not_edited(self):
        plan = ROOT / "configs/v4/final_plan.json"
        before = hashlib.sha256(plan.read_bytes()).hexdigest()
        z = self.dir / "step5.zip"
        write_zip(z, sessions_of(self.mixed()))
        cli("--timeout-from", str(z))
        self.assertEqual(hashlib.sha256(plan.read_bytes()).hexdigest(), before)


class Sources(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.dir = Path(self.tmp.name)
        self.runs = with_changes({"B3": [run(1, 150.0), run(2, 312.4), run(3, 140.0)], "A4": [run(1, 200.0), run(2, 210.0), run(3, 900.0, "FAILURE", "timeout")]})

    def tearDown(self):
        self.tmp.cleanup()

    def body(self, out):
        return out.split("\n\n", 1)[1]                                                                                  # after the "read in place" header (it names the source)

    def test_the_zip_is_read_in_place_and_not_changed(self):
        z = self.dir / "step5_t0_logs.zip"
        write_zip(z, sessions_of(self.runs))
        before, listing = hashlib.sha256(z.read_bytes()).hexdigest(), sorted(p.name for p in self.dir.iterdir())
        code, out = cli("--timeout-from", str(z))
        self.assertEqual(code, 0)
        self.assertEqual(hashlib.sha256(z.read_bytes()).hexdigest(), before)
        self.assertEqual(sorted(p.name for p in self.dir.iterdir()), listing)                                          # nothing extracted, nothing written
        self.assertIn(f"step5_t0_logs.zip sha256 {before}", out)
        self.assertNotIn("9999", out)                                                                                  # the bridge folder's summary is not a run

    def test_manifest_and_folders_and_pairs_give_the_same_report_as_the_zip(self):
        sess = sessions_of(self.runs)
        z = self.dir / "step5.zip"
        write_zip(z, sess)
        folders = write_folders(self.dir / "outputs", sess)
        manifest = self.dir / "step5_sessions.json"
        manifest.write_text(json.dumps({"sessions": [{"setting": s["setting"], "unity": str(d), "timeout_s": s["timeout_s"]} for s, (_, d) in zip(sess, folders)]}), encoding="utf-8")
        a = cli("--timeout-from", str(z))
        b = cli("--timeout-from", str(manifest))
        c = cli("--timeout-from", *[f"{n}={d}" for n, d in folders])
        self.assertEqual((a[0], b[0], c[0]), (0, 0, 0))
        self.assertEqual(self.body(a[1]), self.body(b[1]))
        self.assertEqual(self.body(a[1]), self.body(c[1]))
        self.assertIn("= 480 s", a[1])

    def test_sources_can_be_combined(self):
        sess = sessions_of(self.runs)
        z1, z2 = self.dir / "a.zip", self.dir / "b.zip"
        write_zip(z1, sess[:7])
        write_zip(z2, sess[7:])
        code, out = cli("--timeout-from", str(z1), str(z2))
        self.assertEqual(code, 0, out)
        self.assertIn("Pooled: 39 runs of 13 settings", out)

    def test_smoke_and_dry_sessions_are_not_step_5(self):
        sess = sessions_of(self.runs) + sessions_of({"B3": [run(1, 800.0)]}, prefix="smoke_t0_") + sessions_of({"A3": [run(1, 700.0)]}, prefix="dry_")
        z = self.dir / "step5.zip"
        write_zip(z, sess)
        code, out = cli("--timeout-from", str(z))
        self.assertEqual(code, 0, out)
        self.assertIn("Longest SUCCESSFUL run: 312.4 s (B3 trial 2)", out)                                              # the 800 s smoke run and the 700 s dry run do not count
        self.assertIn("Not step 5 (ignored): dry_A3, smoke_t0_B3", out)

    def test_another_prefix(self):
        z = self.dir / "x.zip"
        write_zip(z, sessions_of(self.runs, prefix="x_"))
        self.assertEqual(cli("--timeout-from", str(z))[0], 2)                                                           # no t0_ sessions
        code, out = cli("--timeout-from", str(z), "--prefix", "x_")
        self.assertEqual(code, 0, out)

    def test_out_writes_a_new_file_and_never_overwrites(self):
        z = self.dir / "step5.zip"
        write_zip(z, sessions_of(self.runs))
        o = self.dir / "report.txt"
        code, out = cli("--timeout-from", str(z), "--out", str(o))
        self.assertEqual(code, 0)
        self.assertEqual(o.read_text(encoding="utf-8"), out)
        with self.assertRaises(FileExistsError):
            cli("--timeout-from", str(z), "--out", str(o))


class Refusals(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.dir = Path(self.tmp.name)

    def tearDown(self):
        self.tmp.cleanup()

    def refused(self, sessions, *extra, message):
        z = self.dir / f"r{len(list(self.dir.iterdir()))}.zip"
        write_zip(z, sessions)
        code, out = cli("--timeout-from", str(z), *extra)
        self.assertEqual(code, 2, out)
        self.assertIn("REFUSED: no timeout is derived.", out) if "REFUSED: " not in message else self.assertIn(message, out)
        self.assertIn(message, out)
        self.assertNotIn("timeout_s = ", out)                                                                           # nothing is derived

    def test_a_missing_setting(self):
        self.refused([s for s in sessions_of(base_runs()) if s["setting"] != "t0_B4_off"], message="t0_B4_off: no session (step 5 has all 13 settings)")

    def test_two_sessions_for_one_setting(self):
        sess = sessions_of(base_runs()) + sessions_of({"A3": [run(1), run(2), run(3)]})
        sess[-1]["unity"] = "trials_development_Task2_A3_interrupted"
        self.refused(sess, message="t0_A3: 2 sessions")

    def test_the_wrong_number_of_runs(self):
        self.refused(sessions_of(with_changes({"A2_left": [run(1), run(2)]})), message="t0_A2_left: 2 runs, step 5 has 3 per setting")
        z = self.dir / "five.zip"
        write_zip(z, sessions_of(with_changes({"A1": [run(i) for i in range(1, 6)]})))
        self.assertEqual(cli("--timeout-from", str(z), "--runs-per-setting", "3")[0], 2)

    def test_runs_that_are_not_development_runs(self):
        self.refused(sessions_of(with_changes({"A1": [run(1, mode="final"), run(2), run(3)]})), message="t0_A1 trial 1: mode 'final': only development runs feed the rule")
        r = run(1)
        del r["mode"]
        self.refused(sessions_of(with_changes({"A1": [r, run(2), run(3)]})), message="mode None")

    def test_a_development_timeout_below_420_s(self):
        self.refused(sessions_of(base_runs(), timeout_s=270), message="development timeout 270 s is below 420 s: its runs cannot feed the rule (16.20.5)")

    def test_a_missing_value_or_a_repeated_trial(self):
        r = run(1)
        del r["total_s"]
        self.refused(sessions_of(with_changes({"A1": [r, run(2), run(3)]})), message="t0_A1 trial 1: outcome or total_s missing")
        self.refused(sessions_of(with_changes({"A1": [run(1), run(1), run(3)]})), message="t0_A1: a trial number appears twice")

    def test_no_successful_run_in_the_whole_pool(self):
        fail = {st: [run(i, 900.0, "FAILURE", "timeout") for i in (1, 2, 3)] for st in SETTINGS}
        self.refused(sessions_of(fail), message="REFUSED: no successful development run: the timeout cannot be derived")

    def test_sources_that_are_not_sources(self):
        with self.assertRaises(SystemExit):
            cli("--timeout-from", str(self.dir / "missing.zip"))
        z = self.dir / "nomanifest.zip"
        write_zip(z, sessions_of(base_runs()), manifest=False)
        with self.assertRaisesRegex(SystemExit, "no MANIFEST.json"):
            cli("--timeout-from", str(z))
        t = self.dir / "notes.txt"
        t.write_text("x", encoding="utf-8")
        with self.assertRaisesRegex(SystemExit, "not a .zip"):
            cli("--timeout-from", str(t))
        with self.assertRaisesRegex(SystemExit, "is not a folder"):
            cli("--timeout-from", f"t0_A3={self.dir / 'nofolder'}")

    def test_a_refusal_lists_every_problem_not_only_the_first(self):
        sess = [s for s in sessions_of(with_changes({"A1": [run(1), run(2)]})) if s["setting"] != "t0_B1"]
        z = self.dir / "two.zip"
        write_zip(z, sess)
        code, out = cli("--timeout-from", str(z))
        self.assertEqual(code, 2)
        self.assertIn("t0_B1: no session", out)
        self.assertIn("t0_A1: 2 runs", out)


class Isolation(unittest.TestCase):
    def test_nothing_in_inference_imports_the_command_line_helpers(self):
        """The helpers are guard code in final_guard_v4.py, which only the server's preflight and the reports import (unchanged)."""
        src = (ROOT / "final_guard_v4.py").read_text(encoding="utf-8")
        self.assertIn('if __name__ == "__main__":', src)
        self.assertIn("--timeout-from", src)
        self.assertNotIn("gt_path", src)


if __name__ == "__main__":
    unittest.main()
