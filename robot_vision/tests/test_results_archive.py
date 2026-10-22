"""Results archive (make_results_archive.py) on small fake runs: copies only, checks, exclusions, checksums, zip,
regenerated summaries, the three-run comparison and the repository summary copy."""

import csv
import hashlib
import json
import sys
import tempfile
import unittest
import zipfile
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import hri_trials as ht  # noqa: E402
import make_results_archive as mra  # noqa: E402

HERE = Path(__file__).resolve().parents[1]
REPO = HERE.parent

AUDIT = """# Audit

## 1. Step table

text

## 2. Final result (final seed 2, run once, commit ce37a56)

**10/10 SUCCESS**

| run | goal B | outcome | distance to B (m) | time (s) | junctions shown > read | closest to worker (m) |
|---|---|---|---|---|---|---|
| 1 | E1 | SUCCESS | 0.031 | 40.64 | J1: FORWARD > FORWARD | 1.127 |
| 2 | E4 | SUCCESS | 0.052 | 72.88 | J1: LEFT > LEFT; J2: RIGHT > RIGHT | 1.264 |

- Junctions: 3/3.

## 3. Development
"""


def write(p: Path, text: str | bytes) -> Path:
    p.parent.mkdir(parents=True, exist_ok=True)
    (p.write_bytes if isinstance(text, bytes) else lambda t: p.write_text(t, encoding="utf-8"))(text)
    return p


def wjson(p: Path, d) -> Path:
    return write(p, json.dumps(d, indent=1))


def wcsv(p: Path, rows: list[dict]) -> None:
    p.parent.mkdir(parents=True, exist_ok=True)
    with p.open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0]))
        w.writeheader()
        w.writerows(rows)


def fake_session(out: Path, unity: str, bridge: str, task: str, mode: str, seed: int, goals: list[str],
                 shown: list[list[tuple[str, str]]], marker: str | None, commit: str) -> None:
    u, b = out / unity, out / bridge
    wjson(u / "session.json", {"task": task, "mode": mode, "seed": seed, "trials": len(goals), "endpoints": ["E1", "E2", "E3", "E4"],
                               "goal_order": goals, "git_commit": commit, "unity_version": "2022.3.62f3"})
    wjson(u / "config_used" / "trials.json", {"task": task, "mode": mode})
    if marker:
        wjson(u / marker, {"trials": len(goals), "successes": len(goals), "mode": mode, "task": task, "seed": seed})
    wjson(b / "run_info.json", {"git": {"commit": commit, "uncommitted_changes": False}, "python": "3.12.14",
                                "platform": "Windows-11", "inference_devices": {"models": {"yolo11s-pose/cam360": {
                                    "device": "CUDA test GPU", "precision": "FP32"}}}})
    dec, per = [], []
    for i, (goal, js) in enumerate(zip(goals, shown), 1):
        t0 = 100.0 * i
        wjson(u / f"truth_run{i:03d}.json", {
            "trial": i, "task": task, "mode": mode, "seed": seed, "a_name": "A", "b_name": goal, "a_x": 6.25, "a_z": -10.0,
            "b_x": 6.25, "b_z": 10.0, "outcome": "SUCCESS", "failure_reason": "none", "detail": "ok", "python_final_state": "done",
            "final_distance_to_b_m": 0.02 * i, "straight_line_m": 20.0, "travelled_m": 21.0, "total_s": 40.0 + i, "t_start": t0,
            "t_end": t0 + 40.0 + i, "avg_speed_mps": 0.5, "max_speed_mps": 0.8, "avg_turn_dps": 5.0, "max_turn_dps": 50.0,
            "collisions": 0, "human_collisions": 0, "collided_with": "", "closest_human_m": 1.1 + 0.01 * i, "closest_human_note": "",
            "shown": [{"junction": j, "shown": s} for j, s in js], "truth_file": f"truth_run{i:03d}.csv"})
        wcsv(u / f"truth_run{i:03d}.csv", [{"time_s": t0 + k * 0.1, "v_mps": 0.5 if k < 5 else 0.0} for k in range(10)])
        wjson(b / f"python_trial_{i:03d}.json", {
            "state": "done", "step_s": {s: 1.0 for s in ht.STEPS}, "safety_stop_s": 0.0, "trial": i, "perception": "vision",
            "junctions": [{"junction": j, "result": "accepted", "asks": 1, "read": s} for j, s in js], "trace": []})
        dec += [{"trial": i, "time_s": t0 + k * 0.1, "safety": "perception stale" if k == 2 else "", "rtt_ms": 1.0,
                 "watchdog_count": 0} for k in range(5)]
        per.append({"time_s": t0 + 1, "decode_ms": 5.0, "model_ms": "yolo11s-pose/cam360:60.0", "total_ms": 70.0})
    wcsv(b / "decisions.csv", dec)
    wcsv(b / "perception.csv", per)
    write(b / "frames" / "frame_000001.jpg", b"\xff\xd8fake")


class Fixture:
    def __init__(self, root: Path):
        self.root = root
        self.repo = root / "repo"
        self.out = root / "outputs"
        self.archive_root = root / "archives"
        rv = self.repo / "robot_vision"
        cfgs = rv / "configs"
        write(self.repo / "AUDIT.md", AUDIT)
        crlf = b'{\r\n  "a": 1\r\n}\r\n'
        write(cfgs / "a.json", crlf)
        write(cfgs / "route.json", b'{"r": 1}\n')
        write(cfgs / "motion_office.json", b'{"m": 1}\n')
        lf_sha = hashlib.sha256(crlf.replace(b"\r\n", b"\n")).hexdigest()
        wjson(cfgs / "hri_frozen.json", {
            "sha256": {"robot_vision/configs/a.json": lf_sha},
            "pose_weights": {"sha256": hashlib.sha256(b"weights").hexdigest()},
            "tasks": {"Task1": {"route_config": {"path": "robot_vision/configs/route.json",
                                                 "sha256": hashlib.sha256(b'{"r": 1}\n').hexdigest()}}}})
        wjson(cfgs / "motion_frozen.json", {"config": "configs/motion_office.json",
                                            "sha256": hashlib.sha256(b'{"m": 1}\n').hexdigest()})
        wjson(cfgs / "hri_trials_metrics.json", {"in_motion_speed_threshold_mps": 0.05})
        wjson(cfgs / "hri_control.json", {"dialog": {"gesture_hold_s": 1.0}})
        write(rv / "models" / "pose.pt", b"weights")
        self.manifest = {
            "machines": {"nusrat_pc": "Nusrat's PC: test", "anisha_mac": "Anisha's Mac: test"},
            "sessions": {
                "task1_final": {"task": "Task1", "role": "final", "seed": 2, "machine": "nusrat_pc", "audit": "AUDIT.md section 10", "what": "T1 final"},
                "task2_final": {"task": "Task2", "role": "final", "seed": 2, "machine": "anisha_mac", "audit": "AUDIT.md section 2", "what": "T2 final"},
                "task2_replication": {"task": "Task2", "role": "replication", "seed": 2, "machine": "nusrat_pc", "audit": "AUDIT.md section 13", "what": "T2 rep"},
                "thud_validation": {"task": "THUD++", "role": "validation", "seed": None, "machine": "nusrat_pc", "audit": "README", "what": "thud"}},
            "folders": [
                {"folder": "trials_final_Task1_20990101_000000", "session": "task1_final", "kind": "unity"},
                {"folder": "bridge_guide_20990101_000001", "session": "task1_final", "kind": "bridge"},
                {"folder": "hri_trials_20990101_000002", "session": "task1_final", "kind": "hri_trials"},
                {"folder": "trials_final_Task2_20980101_000000", "session": "task2_final", "kind": "unity", "location": "teammate"},
                {"folder": "trials_replication_Task2_20990101_000100", "session": "task2_replication", "kind": "unity"},
                {"folder": "bridge_guide_20990101_000101", "session": "task2_replication", "kind": "bridge"},
                {"folder": "seg_X_20990101_000200", "session": "thud_validation", "kind": "thud"}]}
        wjson(cfgs / "results_manifest.json", self.manifest)
        fake_session(self.out, "trials_final_Task1_20990101_000000", "bridge_guide_20990101_000001", "Task1", "final", 2,
                     ["E1", "E1"], [[("C1", "FORWARD"), ("J1", "FORWARD")]] * 2, "FINAL_DONE.json", "1111111aaaa")
        # Task 2 replication without REPLICATION_DONE.json (the check must report it)
        fake_session(self.out, "trials_replication_Task2_20990101_000100", "bridge_guide_20990101_000101", "Task2", "replication", 2,
                     ["E1", "E4"], [[("J1", "FORWARD")], [("J1", "LEFT"), ("J2", "RIGHT")]], None, "2222222bbbb")
        # original hri_trials folder for the Task 1 final (written by the same code)
        runs, _ = ht.merge(self.out / "trials_final_Task1_20990101_000000", self.out / "bridge_guide_20990101_000001",
                           {"in_motion_speed_threshold_mps": 0.05})
        h = self.out / "hri_trials_20990101_000002"
        h.mkdir()
        with (h / "results.csv").open("w", newline="", encoding="utf-8") as f:
            w = csv.DictWriter(f, fieldnames=ht.COLUMNS)
            w.writeheader()
            for r in runs:
                w.writerow(ht.csv_row(r))
        wjson(h / "run.json", {"git": {"commit": "3333333cccc", "uncommitted_changes": False}})
        s = self.out / "seg_X_20990101_000200"
        wjson(s / "evaluation_report.json", {"packages": {"python": "3.12.14", "platform": "Windows-11", "torch": "2.x"}})
        write(s / "model.pt", b"weights")
        write(s / "_path_migration_backup" / "old.json", "{}")
        write(s / "worker_textures" / "Ch32.png", b"png")
        write(s / "overlays" / "o.png", b"png")
        (self.out / "unlisted_20990101_000300").mkdir()
        self.cfg = {
            "manifest": str(cfgs / "results_manifest.json"), "repo_root": str(self.repo),
            "frozen_records": [str(cfgs / "hri_frozen.json"), str(cfgs / "motion_frozen.json")],
            "frozen_extra_configs": [{"path": "robot_vision/configs/motion_office.json", "expected_from": str(cfgs / "motion_frozen.json"),
                                      "key": "sha256", "note": "motion"}],
            "metrics_config": str(cfgs / "hri_trials_metrics.json"), "control_config": str(cfgs / "hri_control.json"),
            "unity_project_version": str(self.repo / "nothing.txt"),
            "models": [{"name": "pose", "path": str(rv / "models" / "pose.pt"), "expected_from": str(cfgs / "hri_frozen.json"),
                        "key": "pose_weights.sha256"}],
            "exclude": {"suffixes": [".pt", ".task"], "dir_names": ["_path_migration_backup", "worker_textures"], "name_contains": ["mixamo"]},
            "no_compress_suffixes": [".png", ".jpg"], "repo_summary_suffixes": [".csv", ".md", ".png"],
            "comparability": {"comparable": ["success"], "not_comparable": ["inference time"]},
            "task2_original_reported": {"source": "AUDIT.md section 2", "commit": "ce37a56", "junctions_at_first_ask": "3/3",
                                        "collisions": 0, "human_collisions": 0, "step_s_mean": {s: 1.0 for s in ht.STEPS},
                                        "stale_stop_s_mean": 1.35, "time_excl_stale_stops_s_mean": 53.35, "in_motion_s_mean": None,
                                        "inference_ms_mean": {"total_per_frame": 177}}}

    def build(self, now=datetime(2099, 1, 2, 3, 4, 5), **kw):
        kw.setdefault("repo_summary", self.repo / "results" / "summary")
        return mra.build(self.cfg, archive_root=self.archive_root, output_root=self.out, repo=self.repo,
                         audit=self.repo / "AUDIT.md", now=now, freeze=lambda: "pkg==1.0\n",
                         git={"commit": "abc", "branch": "test", "uncommitted_changes": False}, **kw)


def tree_hashes(root: Path) -> dict:
    return {p.relative_to(root).as_posix(): hashlib.sha256(p.read_bytes()).hexdigest() for p in root.rglob("*") if p.is_file()}


class TestFakeArchive(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory()
        cls.fx = Fixture(Path(cls.tmp.name))
        cls.before = tree_hashes(cls.fx.out)
        cls.res = cls.fx.build()
        cls.a = cls.res["archive"]

    @classmethod
    def tearDownClass(cls):
        cls.tmp.cleanup()

    def test_originals_unchanged(self):
        self.assertEqual(tree_hashes(self.fx.out), self.before)
        self.assertTrue(self.res["originals_unchanged"])

    def test_layout(self):
        for d in ("README.md", "CHECKSUMS.sha256", "AUDIT.md", "checks.json", "environment/pip_freeze.txt",
                  "environment/runs.csv", "environment/models.csv", "environment/archive_machine.json",
                  "configs_frozen/hashes.csv", "task1/final/trials_final_Task1_20990101_000000/FINAL_DONE.json",
                  "task1/final/bridge_guide_20990101_000001/frames/frame_000001.jpg",
                  "task2/replication/trials_replication_Task2_20990101_000100/session.json",
                  "thud_validation/seg_X_20990101_000200/overlays/o.png", "task1/development", "task2/development",
                  "task2/final/NOT_ON_THIS_MACHINE.md", "archive_config/results_manifest.json", "archive_config/build_info.json"):
            self.assertTrue((self.a / d).exists(), d)

    def test_exclusions(self):
        names = [p.relative_to(self.a).as_posix() for p in self.a.rglob("*") if p.is_file()]
        self.assertFalse([n for n in names if n.endswith(".pt") or "_path_migration_backup" in n or "worker_textures" in n], names)
        self.assertIn("file type .pt", json.loads((self.a / "checks.json").read_text(encoding="utf-8"))["copy"]["excluded"])

    def test_done_marker_checks(self):
        st = {(c["folder"], c["check"]): c["status"] for c in self.res["checks"]}
        self.assertEqual(st[("trials_final_Task1_20990101_000000", "FINAL_DONE.json")], "ok")
        self.assertEqual(st[("trials_replication_Task2_20990101_000100", "REPLICATION_DONE.json")], "MISSING")
        self.assertEqual(st[("trials_final_Task2_20980101_000000", "present")], "not_on_this_machine")
        readme = (self.a / "README.md").read_text(encoding="utf-8")
        self.assertIn("on the teammate's machine", readme)
        self.assertIn("AUDIT.md section 2", readme)
        self.assertIn("REPLICATION_DONE.json | MISSING", readme)
        self.assertIn("unlisted_20990101_000300", readme)

    def test_checksums_and_zip(self):
        lines = (self.a / "CHECKSUMS.sha256").read_text(encoding="utf-8").splitlines()
        listed = {ln.split("  ", 1)[1] for ln in lines}
        files = {p.relative_to(self.a).as_posix() for p in self.a.rglob("*") if p.is_file()}
        self.assertEqual(listed, files - {"CHECKSUMS.sha256"})
        self.assertEqual(mra.verify(self.a), [])
        z = self.res["zip"]
        self.assertEqual(hashlib.sha256(z.read_bytes()).hexdigest(), self.res["zip_sha256"])
        self.assertIn(self.res["zip_sha256"], (z.parent / f"{z.name}.sha256").read_text(encoding="utf-8"))
        with zipfile.ZipFile(z) as zf:
            self.assertEqual({n.split("/", 1)[1] for n in zf.namelist()}, files)
        self.assertEqual(self.res["copy_mismatch"], [])

    def test_regenerated_summary(self):
        rows = ht.read_csv(self.a / "task1" / "summary" / "final" / "runs.csv")
        self.assertEqual([r["outcome"] for r in rows], ["SUCCESS", "SUCCESS"])
        self.assertEqual(float(rows[1]["final_distance_to_b_m"]), 0.04)
        self.assertEqual(self.res["regen_equal"]["task1_final"]["columns_differing"], [])
        for f in ("running_success.png", "step_times.png", "analysis.md", "junctions.csv"):
            self.assertTrue((self.a / "task1" / "summary" / "final" / f).exists(), f)
        self.assertTrue((self.a / "task2" / "summary" / "replication" / "runs.csv").exists())

    def test_three_run_comparison(self):
        t2 = self.a / "task2" / "summary"
        rows = ht.read_csv(t2 / "three_run_comparison.csv")
        by = {r["measure"]: r for r in rows}
        self.assertEqual(set(rows[0]) - {"measure", "comparable_across_machines", "note"},
                         {"task2_original_final", "task2_replication", "task1_final"})
        self.assertTrue(by["successes (Wilson 95 %)"]["task2_original_final"].startswith("2/2"))
        self.assertEqual(by["junctions / stops read as shown (coverage)"]["task2_replication"], "3/3 (coverage 3/3)")
        self.assertEqual(by["total time (s)"]["comparable_across_machines"], "no")
        self.assertIn("not available", by["time in motion, Unity speed > 0.05 m/s (s)"]["task2_original_final"])
        for f in ("three_run_comparison.png", "original_vs_replication_per_run.png", "final/runs_reported_in_audit.csv"):
            self.assertTrue((t2 / f).exists(), f)

    def test_environment_and_frozen(self):
        runs = {r["folder"]: r for r in ht.read_csv(self.a / "environment" / "runs.csv")}
        self.assertEqual(runs["trials_final_Task1_20990101_000000"]["commit"], "1111111aaaa")
        self.assertIn("CUDA test GPU", runs["bridge_guide_20990101_000001"]["device"])
        self.assertEqual(runs["trials_final_Task2_20980101_000000"]["present"], "False")
        models = ht.read_csv(self.a / "environment" / "models.csv")
        self.assertEqual(models[0]["matches"], "True")
        frozen = {r["path"]: r for r in ht.read_csv(self.a / "configs_frozen" / "hashes.csv")}
        self.assertEqual(frozen["robot_vision/configs/a.json"]["matches"], "True")    # CRLF file, LF-normalised hash
        self.assertEqual(frozen["robot_vision/configs/route.json"]["matches"], "True")
        self.assertEqual(frozen["robot_vision/configs/motion_office.json"]["matches"], "True")
        self.assertTrue((self.a / "configs_frozen" / "robot_vision" / "configs" / "a.json").exists())

    def test_repo_summary_only_tables_and_plots(self):
        dest = self.fx.repo / "results" / "summary"
        files = [p.relative_to(dest).as_posix() for p in dest.rglob("*") if p.is_file()]
        self.assertIn("task2/three_run_comparison.csv", files)
        self.assertIn("task1/final/running_success.png", files)
        self.assertFalse([f for f in files if not f.endswith((".csv", ".md", ".png"))], files)
        self.assertIn(self.res["zip_sha256"], (dest / "README.md").read_text(encoding="utf-8"))

    def test_refusals(self):
        with self.assertRaises(SystemExit):     # same time stamp: never overwrite
            self.fx.build(repo_summary=None)
        with self.assertRaises(SystemExit):     # repo summary exists
            self.fx.build(now=datetime(2099, 1, 2, 3, 4, 6))
        with self.assertRaises(SystemExit):     # archive inside the repository
            mra.build(self.fx.cfg, archive_root=self.fx.repo / "arch", output_root=self.fx.out, repo=self.fx.repo,
                      audit=self.fx.repo / "AUDIT.md", now=datetime(2099, 1, 2, 3, 4, 7), freeze=lambda: "",
                      git={"commit": "abc"}, make_zip=False)

    def test_no_absolute_paths_written(self):
        """Files the archive writes itself (copied run folders are verbatim; archive_config holds the test's config)."""
        roots = (str(Path(self.tmp.name)), str(Path(self.tmp.name).as_posix()))
        written = [self.a / n for n in ("README.md", "checks.json", "CHECKSUMS.sha256")]
        written += list((self.a / "environment").glob("*.*")) + [self.a / "configs_frozen" / "hashes.csv"]
        written += [p for t in ("task1", "task2") for p in (self.a / t / "summary").rglob("*") if p.suffix in (".md", ".csv", ".json")]
        self.assertGreater(len(written), 10)
        for p in written:
            text = p.read_text(encoding="utf-8")
            for r in roots:
                self.assertNotIn(r, text, p)


class TestVerifyDetectsChange(unittest.TestCase):
    def test_changed_file(self):
        with tempfile.TemporaryDirectory() as t:
            fx = Fixture(Path(t))
            res = fx.build(make_zip=False, repo_summary=None)
            write(res["archive"] / "AUDIT.md", "edited")
            self.assertEqual(mra.verify(res["archive"]), ["changed: AUDIT.md"])


class TestUnits(unittest.TestCase):
    def test_exclusion(self):
        ex = {"suffixes": [".pt", ".fbx"], "dir_names": ["_path_migration_backup"], "name_contains": ["mixamo"]}
        P = mra.PurePosixPath
        self.assertIsNotNone(mra.exclusion(P("models/yolo.PT"), ex))
        self.assertIsNotNone(mra.exclusion(P("a/_path_migration_backup/x.json"), ex))
        self.assertIsNotNone(mra.exclusion(P("Mixamo_walk/x.json"), ex))
        self.assertIsNone(mra.exclusion(P("frames/frame_pan_tilt_000020.jpg"), ex))

    def test_done_marker_content(self):
        with tempfile.TemporaryDirectory() as t:
            f = Path(t) / "trials_final_Task1_20990101_000000"
            wjson(f / "FINAL_DONE.json", {"task": "Task1", "mode": "final", "seed": 1})
            wjson(f / "REPLICATION_DONE.json", {})
            e = {"folder": f.name, "kind": "unity", "role": "final", "task": "Task1", "seed": 2, "audit": ""}
            st = {c["check"]: c["status"] for c in mra.check_folder(e, f)}
            self.assertEqual(st["FINAL_DONE.json"], "PROBLEM")          # seed disagrees
            self.assertEqual(st["REPLICATION_DONE.json"], "PROBLEM")    # wrong marker in a final folder
            e2 = dict(e, location=None)
            self.assertEqual(mra.check_folder(e2, None)[0]["status"], "MISSING")

    def test_audit_section2_of_the_real_audit(self):
        runs = mra.task2_original_from_audit((REPO / "AUDIT.md").read_text(encoding="utf-8"))
        self.assertEqual(len(runs), 10)
        self.assertTrue(all(r["outcome"] == "SUCCESS" for r in runs))
        self.assertEqual(sum(len(r["junctions"]) for r in runs), 14)
        self.assertEqual([r["b"]["name"] for r in runs], "E1 E2 E4 E2 E1 E3 E4 E1 E4 E1".split())
        self.assertAlmostEqual(sum(r["total_s"] for r in runs) / 10, 54.666, places=3)

    def test_real_manifest_and_config(self):
        m = json.loads((HERE / "configs" / "results_manifest.json").read_text(encoding="utf-8"))
        self.assertEqual(mra.validate_manifest(m), [])
        ents = mra.entries(m)
        roles = {(e["task"], e["role"]) for e in ents}
        for need in (("Task1", "final"), ("Task2", "final"), ("Task2", "replication"), ("Task1", "development"),
                     ("THUD++", "validation")):
            self.assertIn(need, roles)
        finals = [e for e in ents if e["role"] in ("final", "replication") and e["kind"] == "unity"]
        self.assertEqual(sorted(e["folder"].split("_2026")[0] for e in finals),
                         ["trials_final_Task1", "trials_final_Task2", "trials_replication_Task2"])
        cfg = mra.load_config(local=None)
        root = (HERE / cfg["archive_root"]).resolve()
        self.assertFalse(root.is_relative_to(REPO.resolve()), "the archive root must be outside the repository")
        self.assertNotRegex(json.dumps(cfg), r"[A-Za-z]:\\\\")

    def test_manifest_problems_found(self):
        m = {"machines": {"pc": "PC"}, "sessions": {"s": {"task": "Task1", "role": "final", "machine": "pc"}},
             "folders": [{"folder": "trials_development_Task1_20990101_000000", "session": "s", "kind": "unity"},
                         {"folder": "trials_development_Task1_20990101_000000", "session": "s", "kind": "unity"},
                         {"folder": "x", "session": "nope", "kind": "unity"}]}
        p = mra.validate_manifest(m)
        self.assertTrue(any("must start with trials_final_Task1_" in x for x in p))
        self.assertTrue(any("listed twice" in x for x in p))
        self.assertTrue(any("unknown session" in x for x in p))


if __name__ == "__main__":
    unittest.main()
