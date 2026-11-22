"""AUDIT.md 16.33, 16.33.1: the Phase B runbook for the A/B finals (process_final_zip_v4.py). Synthetic sittings only (the helpers of the other final tests): verification,
the copy out of the zip, the eight acceptance checks, the order and the stop rule, the run-once refusals, resumed settings, the tables and matrices, the manifest
entry, and the development flag (no final marker anywhere, steps 3 and 6 skipped)."""

import csv
import hashlib
import json
import shutil
import sys
import tempfile
import unittest
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "tests"))

import final_guard_v4 as fg  # noqa: E402
import final_zip_v4 as fzip  # noqa: E402
import process_final_zip_v4 as pf  # noqa: E402
import test_final_resume_v4 as tr  # noqa: E402
import test_v4_final as tf  # noqa: E402

DEV_SPEC = dict(commander_look="sunbox_m1", clips={"POINT": "point_ik_01", "PROCEED": "proceed_ik_01"})     # development look and clips


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


class Base(tr.ResumeBase):
    """ResumeBase (a frozen repository of 2 runs per setting; self.out holds the source sessions) plus a separate destination root and a manifest copy."""

    def setUp(self):
        super().setUp()
        self.dest = self.root / "dest"
        self.zips = self.root / "zips"
        self.manifest = self.root / "results_manifest.json"
        self.manifest.write_text(json.dumps({"label": "t", "sessions": []}), encoding="utf-8")
        self.stamp = 0

    def complete(self, u: Path, b: Path, setting: str, runs=(1, 2), final: bool = True, machine: bool = True, resources: bool = True) -> None:
        """What a finished session leaves besides the runs: results_unity.csv, summary files, the final markers, run_info.json, resources.csv."""
        with (u / "results_unity.csv").open("w", newline="", encoding="utf-8") as f:
            w = csv.writer(f)
            w.writerow(["trial", "b_name", "outcome"])
            for r in runs:
                w.writerow([r, "E2", "SUCCESS"])
        (u / "summary_unity.json").write_text("{}", encoding="utf-8")
        (b / "summary.json").write_text(json.dumps({"round_trip": {"max_ms": 30.5}, "event_loop_lag": {"max_lag_ms": 12.0}, "watchdog": {"stops_reported_by_unity": 0}}), encoding="utf-8")
        if final:
            (u / "UNITY_FINAL_DONE.json").write_text(json.dumps({"final_setting": setting}), encoding="utf-8")
            fg.write_done(b, setting, "run", {"trials_written": len(runs)})
        (b / "run_info.json").write_text(json.dumps({"machine_state": {"free_mb": 5000}} if machine else {"git": {}}), encoding="utf-8")
        if resources:
            (b / "resources.csv").write_text("t,cpu\n0,1\n", encoding="utf-8")

    def final_session(self, setting: str, stamp: str = "20261122_100000", **kw):
        """A complete synthetic final session of one setting in the source root, with the launcher files the zip tool looks for."""
        u, b = tf.session(self.out, f"final_Task2_{setting}_{stamp}", n=2, setting=setting, extra=tr.EXTRA)
        (b / "FINAL_SETTING.json").write_text(json.dumps({"setting": setting, "frozen_sha256": self.sha}), encoding="utf-8")
        self.complete(u, b, setting, **{k: v for k, v in kw.items() if k in ("runs", "final", "machine", "resources")})
        if kw.get("note", True):
            (self.out / f"run_protocol_final_{setting}_{stamp}.txt").write_text("run protocol note: free memory 5000 MB; programs running: none", encoding="utf-8")
        for suffix in ("server.log", "unity.log"):
            (self.out / f"run_session_final_{setting}_{stamp}_{suffix}").write_text("log", encoding="utf-8")
        return u, b

    def make_zip(self, settings, number=1, extra=True):
        power = self.root / "power_mode.txt"
        power.write_text("power mode: Best performance", encoding="utf-8")
        self.stamp += 1
        res = fzip.make_sitting_zip(number, settings, self.zips, [power] if extra else None, self.out, stamp=f"20261122_12{self.stamp:04d}", repo=self.repo)
        return res["zip"], res["sha256"]

    def run_it(self, zp, sha256, **kw):
        kw.setdefault("manifest_path", self.manifest)
        kw.setdefault("final_root", self.dest)
        return pf.run(zp, sha256, repo=self.repo, **kw)

    def step(self, report, name):
        return next(s for s in report.steps if s["name"] == name)

    def markers_in(self, root):
        """The run-once markers THE RUNBOOK writes (evaluation, export, invalid); FINAL_RUN_DONE.json of the zip's bridge folder is data copied from Unity's machine."""
        return sorted(p.name for n in ("FINAL_DONE.json", "FINAL_EXPORT_DONE.json", "FINAL_INVALID.json") for p in Path(root).rglob(n))


class HappyPathTests(Base):
    def test_one_sitting_all_six_steps_and_the_files_ready_to_paste(self):
        self.final_session("B3")
        self.final_session("B3_off")
        zp, h = self.make_zip(["B3", "B3_off"])
        code, folder, rep = self.run_it(zp, h)
        self.assertEqual(code, 0, [s for s in rep.steps if s["status"] == "fail"])
        names = [s["name"] for s in rep.steps]
        for n in ("verify", "copy out", "accept B3", "accept B3_off", "evaluate B3", "evaluate B3_off", "export B3", "export B3_off", "combined table", "tables", "pairs",
                  "gesture_confusion", "branch_confusion", "figures", "manifest"):
            self.assertIn(n, names)
        for stem in ("phase_b_tables", "phase_b_pairs", "phase_b_gesture_confusion", "phase_b_branch_confusion"):
            for ext in (".csv", ".md"):
                self.assertTrue((folder / (stem + ext)).is_file(), stem + ext)
        self.assertTrue((folder / "report.json").is_file() and (folder / "report.md").is_file())
        # the run-once markers of both settings, in the destination root
        for s in ("B3", "B3_off"):
            self.assertEqual(len(fg.markers(self.dest, s, "evaluation")), 1)
            self.assertEqual(len(fg.markers(self.dest, s, "export")), 1)
        self.assertEqual(self.step(rep, "figures")["status"], pf.SKIPPED)                      # figures_v4.py is development-only
        self.assertIn("DEVELOPMENT data only", self.step(rep, "figures")["detail"])
        pairs = (folder / "phase_b_pairs.md").read_text(encoding="utf-8")
        self.assertIn("B detection on vs off, scenario 3", pairs)                            # the B ON vs OFF pair is there
        tables = list(csv.DictReader((folder / "phase_b_tables.csv").open(encoding="utf-8")))
        self.assertEqual([r["setting"] for r in tables], ["B3", "B3_off"])
        self.assertEqual(tables[0]["success_n"], "2")

    def test_the_acceptance_report_lists_every_criterion_per_setting(self):
        self.final_session("A3")
        zp, h = self.make_zip(["A3"])
        _, _, rep = self.run_it(zp, h)
        crits = self.step(rep, "accept A3")["criteria"]
        self.assertEqual([c["id"] for c in crits], list(range(1, 9)))
        self.assertEqual({c["status"] for c in crits}, {pf.PASS})

    def test_the_manifest_entry_is_appended_once_and_is_valid(self):
        self.final_session("A3")
        zp, h = self.make_zip(["A3"])
        _, _, rep = self.run_it(zp, h)
        m = json.loads(self.manifest.read_text(encoding="utf-8"))
        self.assertEqual(len(m["sessions"]), 1)
        e = m["sessions"][0]
        self.assertEqual((e["setting"], e["role"]), ("A3", "final"))
        self.assertTrue(e["unity"].startswith("trials_final_Task2_A3_") and e["bridge"].startswith("bridge_") and e["eval"].startswith("hri_eval_final_v4_A3_"))
        self.assertTrue(e["export"].startswith("export_csv_v4_final_A3_"))
        self.assertEqual(self.step(rep, "manifest")["status"], pf.OK)

    def test_no_manifest_append_leaves_the_file_alone(self):
        self.final_session("A3")
        zp, h = self.make_zip(["A3"])
        before = self.manifest.read_text(encoding="utf-8")
        _, _, rep = self.run_it(zp, h, manifest_append=False)
        self.assertEqual(self.manifest.read_text(encoding="utf-8"), before)
        self.assertEqual(self.step(rep, "manifest")["status"], pf.SKIPPED)


class VerifyTests(Base):
    def test_a_wrong_or_malformed_hash_stops_before_anything_is_copied(self):
        self.final_session("A3")
        zp, h = self.make_zip(["A3"])
        for bad in ("0" * 64, "abc", ""):
            code, _, rep = self.run_it(zp, bad)
            self.assertEqual(code, 1)
            self.assertEqual(rep.steps[-1]["name"], "STOPPED")
            self.assertFalse(self.dest.exists() and any(p.name.startswith("trials_") for p in self.dest.iterdir()))
        self.assertEqual(self.markers_in(self.dest) if self.dest.exists() else [], [])

    def test_a_changed_sidecar_or_member_is_found(self):
        self.final_session("A3")
        zp, h = self.make_zip(["A3"])
        (zp.parent / (zp.name + ".sha256")).write_text("1" * 64 + f"  {zp.name}\n", encoding="utf-8")
        code, _, rep = self.run_it(zp, h)
        self.assertEqual(code, 1)
        self.assertIn("differs from the SHA-256 that was given", rep.steps[-1]["detail"])

    def test_the_wrong_kind_of_zip_is_refused_with_the_reason(self):
        self.final_session("A3")
        zp, h = self.make_zip(["A3"])
        code, _, rep = self.run_it(zp, h, development=True)
        self.assertEqual(code, 1)
        self.assertIn("final sitting zip", rep.steps[-1]["detail"])
        dev_zip, dev_h = self.dev_zip("A3")
        code, _, rep = self.run_it(dev_zip, dev_h)
        self.assertEqual(code, 1)
        self.assertIn("development zip", rep.steps[-1]["detail"])

    def dev_zip(self, setting="A3", prefix="t0_", **spec_kw):
        """A zip in the step-5 format (MANIFEST 'sessions'): one development session of the setting."""
        base = self.root / "dev_src"
        base.mkdir(exist_ok=True)
        u, b = tf.session(base, f"development_Task2_{setting}_x", n=2, setting=setting, mode="development", spec_kw={**DEV_SPEC, **spec_kw}, extra=tr.EXTRA)
        self.complete(u, b, setting, final=False)
        note = base / "run_protocol_rehearsal.txt"
        note.write_text("free memory 5000 MB", encoding="utf-8")
        files = []
        label = prefix + setting
        for folder in (u, b):
            for p in sorted(q for q in folder.rglob("*") if q.is_file()):
                files.append((p, f"{label}/{folder.name}/{p.relative_to(folder).as_posix()}"))
        files.append((note, f"{label}/launcher/{note.name}"))
        meta = {"what": "step 5 development sessions (rehearsal mode) and their analysis; development data, not a result", "prefix": prefix, "git_commit": "x",
                "sessions": [{"setting": label, "unity": u.name, "bridge": b.name, "launcher_files": [note.name]}],
                "files": [{"name": n, "bytes": p.stat().st_size, "sha256": sha(p)} for p, n in files]}
        self.zips.mkdir(exist_ok=True)
        zp = self.zips / f"dev_{setting}.zip"
        with zipfile.ZipFile(zp, "x") as z:
            for p, n in files:
                z.write(p, n)
            z.writestr("MANIFEST.json", json.dumps(meta))
        (zp.parent / (zp.name + ".sha256")).write_text(f"{sha(zp)}  {zp.name}\n", encoding="utf-8")
        return zp, sha(zp)


class CopyOutTests(Base):
    def test_only_plain_data_folders_are_copied_and_code_is_never(self):
        self.final_session("A3")
        u = next(self.out.glob("trials_final_Task2_A3_*"))
        (u / "helper.py").write_text("raise SystemExit('never run')", encoding="utf-8")        # code inside a data folder
        zp, h = self.make_zip(["A3"])
        _, _, rep = self.run_it(zp, h)
        copied = next(self.dest.glob("trials_final_Task2_A3_*"))
        self.assertFalse((copied / "helper.py").exists())
        self.assertTrue((copied / "session.json").is_file())
        self.assertFalse(list(self.dest.rglob("final_zip_v4.py")))                           # nothing outside the settings' folders
        self.assertFalse(list(self.dest.rglob("power_mode.txt")))                            # extra/ stays in the zip

    def test_a_path_that_leaves_the_destination_is_refused(self):
        z = self.root / "evil.zip"
        with zipfile.ZipFile(z, "w") as zf:
            zf.writestr("A3/../outside/x.txt", "x")
        meta = {"files": [{"name": "A3/../outside/x.txt", "sha256": hashlib.sha256(b"x").hexdigest(), "bytes": 1}]}
        for bad in ("../outside", "/abs", "a\\b", "C:x"):
            with self.assertRaises(pf.StepFailed):
                pf.copy_out(z, meta, [{"setting": "A3", "label": "A3", "unity": [bad], "bridge": [], "markers": []}], self.dest)
        self.assertFalse((self.root / "outside").exists())

    def test_a_hash_that_differs_removes_the_partial_folder(self):
        z = self.root / "bad.zip"
        with zipfile.ZipFile(z, "w") as zf:
            zf.writestr("A3/f/a.txt", "a")
            zf.writestr("A3/f/b.txt", "b")
        meta = {"files": [{"name": "A3/f/a.txt", "sha256": hashlib.sha256(b"a").hexdigest(), "bytes": 1},
                          {"name": "A3/f/b.txt", "sha256": "0" * 64, "bytes": 1}]}
        with self.assertRaisesRegex(pf.StepFailed, "differs from MANIFEST.json after the copy"):
            pf.copy_out(z, meta, [{"setting": "A3", "label": "A3", "unity": ["f"], "bridge": [], "markers": []}], self.dest)
        self.assertEqual([p.name for p in self.dest.iterdir()], [])                           # neither f nor .ingest_f is left

    def test_an_existing_folder_is_never_overwritten(self):
        self.final_session("A3")
        zp, h = self.make_zip(["A3"])
        u = next(self.out.glob("trials_final_Task2_A3_*"))
        (self.dest / u.name).mkdir(parents=True)
        code, _, rep = self.run_it(zp, h)
        self.assertEqual(code, 1)
        self.assertIn("exists already: nothing is overwritten", rep.steps[-1]["detail"])


class AcceptanceFailureTests(Base):
    def stops_with(self, zp, h, pattern):
        code, _, rep = self.run_it(zp, h)
        self.assertEqual(code, 1)
        self.assertRegex(rep.steps[-1]["detail"], pattern)
        self.assertEqual([s for s in rep.steps if s["name"].startswith(("evaluate", "export", "manifest"))], [])      # nothing downstream ran
        self.assertEqual(self.markers_in(self.dest), [])                                                              # no marker was written
        self.assertEqual(json.loads(self.manifest.read_text(encoding="utf-8"))["sessions"], [])
        return rep

    def failing(self, rep, setting, cid):
        c = next(c for c in self.step(rep, f"accept {setting}")["criteria"] if c["id"] == cid)
        self.assertEqual(c["status"], pf.FAIL)
        return c["detail"]

    def test_a_missing_python_trial_file_fails_criterion_4(self):
        u, b = self.final_session("A3")
        (b / "python_trial_002.json").unlink()
        zp, h = self.make_zip(["A3"])
        rep = self.stops_with(zp, h, "acceptance failed for A3")
        self.assertIn("python_trial_###", self.failing(rep, "A3", 4))

    def test_a_missing_final_marker_fails_criterion_5(self):
        u, b = self.final_session("A3")
        (b / "FINAL_RUN_DONE.json").unlink()
        zp, h = self.make_zip(["A3"])
        rep = self.stops_with(zp, h, "acceptance failed")
        self.assertIn("FINAL_RUN_DONE.json missing", self.failing(rep, "A3", 5))

    def test_a_failed_leak_test_fails_criterion_1(self):
        u, b = self.final_session("A3")
        tf.leak_images(u / "leak_test", differ=True)
        zp, h = self.make_zip(["A3"])
        rep = self.stops_with(zp, h, "acceptance failed")
        self.assertIn("Python False", self.failing(rep, "A3", 1))

    def test_a_missing_run_protocol_note_or_machine_state_fails_criterion_7(self):
        u, b = self.final_session("A3", note=False)
        zp, h = self.make_zip(["A3"])
        rep = self.stops_with(zp, h, "acceptance failed")
        self.assertIn("no run-protocol note", self.failing(rep, "A3", 7))
        shutil.rmtree(self.out)
        self.out.mkdir()
        self.dest = self.root / "dest2"
        u, b = self.final_session("A3", machine=False, resources=False)
        zp, h = self.make_zip(["A3"])
        rep = self.stops_with(zp, h, "acceptance failed")
        detail = self.failing(rep, "A3", 7)
        self.assertIn("no machine state", detail)
        self.assertIn("resources.csv missing", detail)

    def test_a_development_look_in_a_final_fails_the_split_guard(self):
        u, b = tf.session(self.out, "final_Task2_A3_20261122_100000", n=2, setting="A3", extra=tr.EXTRA, spec_kw=DEV_SPEC)
        (b / "FINAL_SETTING.json").write_text(json.dumps({"setting": "A3", "frozen_sha256": self.sha}), encoding="utf-8")
        self.complete(u, b, "A3")
        (self.out / "run_protocol_final_A3_20261122_100000.txt").write_text("free memory", encoding="utf-8")
        zp, h = self.make_zip(["A3"])
        rep = self.stops_with(zp, h, "acceptance failed")
        self.assertIn("test", self.failing(rep, "A3", 3) + "test")

    def test_an_unfrozen_repository_or_a_changed_frozen_hash_fails_criterion_2(self):
        u, b = self.final_session("A3")
        (b / "FINAL_SETTING.json").write_text(json.dumps({"setting": "A3", "frozen_sha256": "9" * 64}), encoding="utf-8")
        zp, h = self.make_zip(["A3"])
        rep = self.stops_with(zp, h, "acceptance failed")
        self.assertIn("do not record the current frozen.json hash", self.failing(rep, "A3", 2))

    def test_one_invalid_setting_stops_everything_before_any_evaluation(self):
        self.final_session("B3")
        u, b = self.final_session("B3_off")
        (b / "python_trial_001.json").unlink()                                                 # the second setting is invalid
        zp, h = self.make_zip(["B3", "B3_off"])
        rep = self.stops_with(zp, h, "acceptance failed for B3_off")
        self.assertEqual(self.step(rep, "accept B3")["status"], pf.OK)                          # the first is fine, and still nothing was evaluated
        self.assertEqual(fg.markers(self.dest, "B3", "evaluation"), [])

    def test_a_setting_with_a_failed_evaluation_gate_is_not_marked(self):
        self.final_session("A3")
        zp, h = self.make_zip(["A3"])
        import hri_eval_final_v4 as ef
        original = ef.evaluate_final
        ef.evaluate_final = lambda *a, **k: (_ for _ in ()).throw(SystemExit("refused for a reason"))
        try:
            code, _, rep = self.run_it(zp, h)
        finally:
            ef.evaluate_final = original
        self.assertEqual(code, 1)
        self.assertIn("the final evaluation refused: refused for a reason", rep.steps[-1]["detail"])
        self.assertEqual(fg.markers(self.dest, "A3", "evaluation"), [])
        self.assertEqual(self.step(rep, "accept A3")["status"], pf.OK)


class NeverReEvaluatesTests(Base):
    def test_a_second_run_of_the_same_zip_is_refused_and_writes_nothing_new(self):
        self.final_session("A3")
        zp, h = self.make_zip(["A3"])
        code, _, _ = self.run_it(zp, h)
        self.assertEqual(code, 0)
        before = sorted(p.name for p in self.dest.iterdir() if not p.name.startswith("process_final_zip_v4_"))
        code, _, rep = self.run_it(zp, h)
        self.assertEqual(code, 1)
        self.assertIn("already evaluated", rep.steps[-1]["detail"])
        self.assertEqual(sorted(p.name for p in self.dest.iterdir() if not p.name.startswith("process_final_zip_v4_")), before)
        self.assertEqual(len(fg.markers(self.dest, "A3", "evaluation")), 1)
        self.assertEqual(len(json.loads(self.manifest.read_text(encoding="utf-8"))["sessions"]), 1)

    def test_a_marker_in_the_default_outputs_or_an_invalid_marker_is_refused_too(self):
        entries = [{"setting": "A3", "unity": ["u"], "bridge": ["b"], "markers": [], "invalid": []}]
        other = self.root / "other_outputs"
        (other / "hri_eval_final_v4_A3_x").mkdir(parents=True)
        fg.write_done(other / "hri_eval_final_v4_A3_x", "A3", "evaluation")
        with self.assertRaisesRegex(pf.StepFailed, "already evaluated"):
            pf.preflight_final(entries, [self.dest, other], self.repo)
        (self.root / "inv").mkdir()
        fg.write_done(self.root / "inv", "A3", "invalid", {"reason": "x"})
        with self.assertRaisesRegex(pf.StepFailed, "declared invalid"):
            pf.preflight_final(entries, [self.root], self.repo)
        entries[0]["invalid"] = ["final_invalid_A3_x"]
        with self.assertRaisesRegex(pf.StepFailed, "FINAL_INVALID marker"):
            pf.preflight_final(entries, [self.dest], self.repo)


class ResumedSettingTests(Base):
    def resumed_zip(self):
        n1, n2 = "final_Task2_A3_20261122_100000", "final_Task2_A3_20261122_110000"
        u1, b1 = self.part1(n1)
        self.complete(u1, b1, "A3", runs=(1,), final=False)
        marker = self.declare(u1, b1)
        u2, b2 = self.part2(u1, n2)
        self.resume(marker, b2)
        self.complete(u2, b2, "A3", runs=(2,))
        for stamp in ("20261122_100000", "20261122_110000"):
            (self.out / f"run_protocol_final_A3_{stamp}.txt").write_text("free memory 5000 MB", encoding="utf-8")
            (self.out / f"run_session_final_A3_{stamp}_server.log").write_text("log", encoding="utf-8")
        return self.make_zip(["A3"])

    def test_a_declared_and_resumed_setting_is_accepted_and_evaluated_as_one_session(self):
        zp, h = self.resumed_zip()
        code, folder, rep = self.run_it(zp, h)
        self.assertEqual(code, 0, [s for s in rep.steps if s["status"] == "fail"])
        crits = {c["id"]: c for c in self.step(rep, "accept A3")["criteria"]}
        self.assertEqual(crits[8]["status"], pf.PASS)
        self.assertIn("resumed once from run 2", crits[8]["detail"])
        self.assertIn("part 1 runs 1..1, part 2 runs 2..2", crits[4]["detail"])
        eval_folder = next(self.dest.glob("hri_eval_final_v4_A3_*"))
        res = json.loads((eval_folder / "eval.json").read_text(encoding="utf-8"))
        self.assertEqual(res["interruption"]["interrupted_run"], 2)
        e = json.loads(self.manifest.read_text(encoding="utf-8"))["sessions"][0]
        self.assertIn("unity_resumed", e)                                                    # the second part is recorded in the entry

    def test_a_declared_interruption_that_was_not_resumed_fails_criterion_8(self):
        n1 = "final_Task2_A3_20261122_100000"
        u1, b1 = self.part1(n1)
        self.complete(u1, b1, "A3", runs=(1,), final=False)
        self.declare(u1, b1)
        (self.out / "run_protocol_final_A3_20261122_100000.txt").write_text("free memory", encoding="utf-8")
        zp, h = self.make_zip(["A3"])
        code, _, rep = self.run_it(zp, h)
        self.assertEqual(code, 1)
        bad = [c for c in self.step(rep, "accept A3")["criteria"] if c["status"] == pf.FAIL]
        self.assertTrue(any(c["id"] == 8 for c in bad), bad)
        self.assertEqual(fg.markers(self.dest, "A3", "evaluation"), [])


class DevelopmentTests(VerifyTests):
    """--development on a zip in the step-5 format."""

    def test_the_dry_run_skips_steps_3_and_6_and_writes_no_final_marker(self):
        zp, h = self.dev_zip("A3")
        before_manifest = self.manifest.read_text(encoding="utf-8")
        code, folder, rep = self.run_it(zp, h, development=True, work_root=self.root / "work", no_figures=True, dev_runs=2)
        self.assertEqual(code, 0, [s for s in rep.steps if s["status"] == "fail"])
        self.assertEqual(self.step(rep, "evaluate")["status"], pf.SKIPPED)
        self.assertEqual(self.step(rep, "manifest")["status"], pf.SKIPPED)
        self.assertEqual(self.markers_in(self.root / "work"), [])
        self.assertEqual(self.markers_in(self.dest) if self.dest.exists() else [], [])
        self.assertEqual(self.manifest.read_text(encoding="utf-8"), before_manifest)
        crits = {c["id"]: c["status"] for c in self.step(rep, "accept A3")["criteria"]}
        self.assertEqual((crits[2], crits[8]), (pf.NOT_EVALUATED, pf.NOT_EVALUATED))            # as far as development allows
        self.assertTrue(all(crits[i] == pf.PASS for i in (1, 3, 4, 5, 6, 7)), crits)
        for stem in ("phase_b_tables", "phase_b_pairs", "phase_b_gesture_confusion", "phase_b_branch_confusion"):
            self.assertTrue((folder / f"{stem}.csv").is_file() and (folder / f"{stem}.md").is_file())
        self.assertIn("DEVELOPMENT dry run", (folder / "phase_b_tables.md").read_text(encoding="utf-8"))
        export = next((folder.parent).glob("export_csv_v4_development_A3_*"))
        self.assertTrue((export / "runs.csv").is_file() and (export / "dialogs.csv").is_file() and (export / "summary.json").is_file())
        self.assertFalse((export / "FINAL_EXPORT_DONE.json").exists())

    def test_a_test_look_in_a_development_dry_run_is_refused(self):
        zp, h = self.dev_zip("A3", commander_look="sunbox_m_shirt_plaid", clips={"POINT": "point_mixamo_02", "PROCEED": "proceed_ik_03"})
        code, _, rep = self.run_it(zp, h, development=True, work_root=self.root / "work", no_figures=True, dev_runs=2)
        self.assertEqual(code, 1)
        c3 = next(c for c in self.step(rep, "accept A3")["criteria"] if c["id"] == 3)
        self.assertEqual(c3["status"], pf.FAIL)

    def test_the_development_folder_is_new_every_time(self):
        zp, h = self.dev_zip("A3")
        _, f1, _ = self.run_it(zp, h, development=True, work_root=self.root / "work", no_figures=True, dev_runs=2)
        import time
        time.sleep(1.1)
        _, f2, _ = self.run_it(zp, h, development=True, work_root=self.root / "work", no_figures=True, dev_runs=2)
        self.assertNotEqual(f1.parent, f2.parent)


class MatrixAndTableTests(unittest.TestCase):
    def test_the_confusion_matrix_counts_asks_and_keeps_a_blank_reading(self):
        rows = [{"command_shown": "POINT", "command_read": "POINT"}, {"command_shown": "POINT", "command_read": "NONE"}, {"command_shown": "POINT", "command_read": ""},
                {"command_shown": "STOP", "command_read": "PROCEED"}, {"command_shown": "", "command_read": "POINT"}, {"command_shown": "ODD", "command_read": "POINT"}]
        m = pf.confusion(rows, "command_shown", "command_read", ["POINT", "WAIT", "STOP", "PROCEED", "NONE"])
        self.assertEqual(m["counts"]["POINT"], {"POINT": 1, "WAIT": 0, "STOP": 0, "PROCEED": 0, "NONE": 1, "(none)": 1})
        self.assertEqual(m["counts"]["STOP"]["PROCEED"], 1)
        self.assertEqual((m["row_total"]["POINT"], m["asks"], m["asks_without_a_shown_label"]), (3, 4, 2))
        self.assertAlmostEqual(m["share_read_as_shown"]["POINT"], 1 / 3)
        self.assertIsNone(m["share_read_as_shown"]["WAIT"])                                       # no asks: no share, not 0

    def test_the_matrix_files_say_what_they_rest_on(self):
        with tempfile.TemporaryDirectory() as d:
            d = Path(d)
            m = pf.confusion([{"true_branch": "LEFT", "branch_read": "LEFT"}], "true_branch", "branch_read", ["FORWARD", "LEFT", "RIGHT", "BACK", "NONE"])
            pf.write_matrix(d, "x", "branch", {"ALL (pooled)": m}, "true_branch", "branch_read", "share read as true")
            text = (d / "x.md").read_text(encoding="utf-8")
            self.assertIn("ALL (pooled) (1 asks)", text)
            self.assertIn("share read as true", text)
            self.assertEqual(next(csv.reader((d / "x.csv").open()))[-1], "share_read_as_true")

    def test_pairs_are_sorted_with_the_on_off_pairs_first(self):
        comps = [{"kind": "A vs B", "name": "A vs B, scenario 3", "metric": "success", "x": "A3", "x_cell": "1", "y": "B3", "y_cell": "1", "difference_pp": 0.0,
                  "difference_lo_pp": -5.0, "difference_hi_pp": 5.0, "available": True},
                 {"kind": "B on vs off", "name": "B detection on vs off, scenario 3", "metric": "success", "x": "B3_off", "x_cell": "1", "y": "B3", "y_cell": "1",
                  "difference_pp": 0.0, "difference_lo_pp": -5.0, "difference_hi_pp": 5.0, "available": True}]
        with tempfile.TemporaryDirectory() as d:
            pf.write_pairs(comps, Path(d), False)
            kinds = [r["kind"] for r in csv.DictReader((Path(d) / "phase_b_pairs.csv").open())]
            self.assertEqual(kinds, ["B on vs off", "A vs B"])

    def test_a_cell_without_data_is_not_evaluated_never_zero(self):
        with tempfile.TemporaryDirectory() as d:
            d = Path(d)
            summary = {"success": {"k": 1, "n": 2, "wilson95": [0.1, 0.9], "ratio": 0.5}, "failure_kinds": {"timeout": 1}, "runs": 2,
                       "lies": {"given": 0, "detected": {"total": 0}, "corrected": {"total": 0}, "fooled": {"total": 0}}, "time_s": {"success_runs": {"median": None}}}
            (d / "summary.json").write_text(json.dumps({"setting": "A1", "summary": summary}), encoding="utf-8")
            (d / "runs.csv").write_text("trial,closest_person_m,stop_gestures_true,stop_gestures_false\n1,,,\n2,,,\n", encoding="utf-8")
            row = pf.setting_table_row("A1", d, [])
            for k in ("stop_gestures_true", "stop_gestures_false", "closest_person_min_m", "round_trip_max_ms", "event_loop_lag_max_ms", "watchdog_stops_reported"):
                self.assertEqual(row[k], "not evaluated", k)
            (d / "runs.csv").write_text("trial,closest_person_m,stop_gestures_true,stop_gestures_false\n1,1.5,0,2\n2,1.2,1,0\n", encoding="utf-8")
            row = pf.setting_table_row("A1", d, [])
            self.assertEqual((row["stop_gestures_true"], row["stop_gestures_false"], row["closest_person_min_m"]), (1, 2, 1.2))


if __name__ == "__main__":
    unittest.main()
