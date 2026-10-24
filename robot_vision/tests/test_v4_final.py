"""v4 final modes: a final evaluation or final run is refused unless the v4 configs are frozen with every hash matching, the data
is test-split only and is what its setting says, and a setting is run / evaluated once (final_guard_v4.py)."""

import json
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "tests"))

import final_guard_v4 as fg  # noqa: E402
import freeze_v4 as fz  # noqa: E402
import gesture_data as gd  # noqa: E402
import hri_eval_dev_v4 as ev  # noqa: E402
import hri_eval_final_v4 as ef  # noqa: E402
import hri_sim_v4 as sv  # noqa: E402
import run_paths as rp  # noqa: E402
import test_hri_sim_v4_trials as tt  # noqa: E402
import test_v4_frozen as tfz  # noqa: E402
from bridge import server as S  # noqa: E402

TEST_SPEC = dict(commander_look="placeholder_look_test_1",
                 clips={"POINT": "placeholder_point_test_1", "WAIT": "placeholder_wait_test_1", "STOP": "placeholder_stop_test_1"})


def final_repo(tmp: Path, freeze: bool = True, runs: int = 2) -> Path:
    """A repository copy with the plan filled, the splits no longer placeholders, and (by default) frozen."""
    repo = tfz.make_repo(tmp)
    plan = repo / fz.PLAN_REL
    d = json.loads(plan.read_text())
    d.update(runs_per_setting=runs, final_seed=7, task="Task2")
    plan.write_text(json.dumps(d))
    sp = repo / fz.V4_DIR / "data_splits.json"
    d = json.loads(sp.read_text())
    d["placeholder"] = False
    sp.write_text(json.dumps(d))
    fz.refresh_list(repo)
    if freeze:
        fz.freeze(repo, git_commit="abc123")
    return repo


def session(tmp: Path, name: str, n: int = 2, zoom: bool = True, mode: str = "final", seed: int = 7, spec_kw=None, goal="E2"):
    spec = sv.SceneSpec(**{**TEST_SPEC, **(spec_kw or {})})
    results = [tt.trial(goal, spec, zoom=zoom, seed=k + 1) for k in range(n)]
    return sv.export_session(results, tmp, zoom, seed=seed, name=name, mode=mode)


class GuardTests(unittest.TestCase):
    def test_markers_are_per_setting_and_per_kind(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            (root / "bridge_a").mkdir()
            (root / "eval_b").mkdir()
            fg.write_done(root / "bridge_a", "zoom_on", "run")
            fg.write_done(root / "eval_b", "zoom_off", "evaluation")
            self.assertEqual(len(fg.markers(root, "zoom_on", "run")), 1)
            self.assertEqual(fg.markers(root, "zoom_on", "evaluation"), [])        # a finished run does not block its evaluation
            self.assertEqual(fg.markers(root, "zoom_off", "run"), [])
            with self.assertRaisesRegex(SystemExit, "already run as a final"):
                fg.ensure_not_done(root, "zoom_on", "run")
            with self.assertRaisesRegex(SystemExit, "already evaluated as a final"):
                fg.ensure_not_done(root, "zoom_off", "evaluation")
            fg.ensure_not_done(root, "bystanders", "run")                          # another setting is free

    def test_never_overwritten_and_unreadable_markers_are_ignored(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            (root / "x").mkdir()
            fg.write_done(root / "x", "zoom_on", "run")
            with self.assertRaises(FileExistsError):
                fg.write_done(root / "x", "zoom_on", "run")
            (root / "y").mkdir()
            (root / "y" / fg.MARKERS["run"]).write_text("{not json")
            self.assertEqual(len(fg.markers(root, "zoom_on", "run")), 1)
            self.assertEqual(fg.markers(root / "missing", "zoom_on", "run"), [])

    def test_unknown_setting_is_refused(self):
        with self.assertRaisesRegex(SystemExit, "unknown final setting"):
            fg.ensure_not_done(".", "zoom_sideways", "run")

    def test_the_marker_records_what_was_done(self):
        with tempfile.TemporaryDirectory() as d:
            p = fg.write_done(d, "bystanders", "evaluation", {"git_commit": "abc", "runs": 10})
            rec = json.loads(p.read_text())
            self.assertEqual((rec["setting"], rec["kind"], rec["runs"]), ("bystanders", "evaluation", 10))
            self.assertIn("written", rec)


class SettingChecks(unittest.TestCase):
    def runs(self, tmp, **kw):
        u, b = session(tmp, "s", **kw)
        return ev.load_sessions([(u, b)], gd.load_config(), final_evaluation=True,
                                splits={**json.loads((ROOT / "configs/v4/data_splits.json").read_text()), "placeholder": False})

    def test_a_matching_session_is_fine(self):
        with tempfile.TemporaryDirectory() as d:
            repo = final_repo(Path(d) / "r")
            self.assertEqual(fg.check_setting("zoom_on", self.runs(Path(d)), repo), [])

    def test_each_mismatch_is_reported(self):
        with tempfile.TemporaryDirectory() as d:
            repo = final_repo(Path(d) / "r")
            r = self.runs(Path(d), n=3, zoom=False, mode="development", seed=1)
            p = " | ".join(fg.check_setting("zoom_on", r, repo))
            for want in ("needs zoom on", "3 runs, the plan has 2", "seed 1 but the plan's final seed is 7", "not 'final'"):
                self.assertIn(want, p)
        with tempfile.TemporaryDirectory() as d:
            repo = final_repo(Path(d) / "r")
            r = self.runs(Path(d))
            self.assertTrue(any("needs bystanders" in x for x in fg.check_setting("bystanders", r, repo)))
            self.assertTrue(any("needs zoom off" in x for x in fg.check_setting("zoom_off", r, repo)))
            self.assertEqual(fg.check_setting("unseen_look", r, repo), [])

    def test_blanks_in_the_plan_are_reported(self):
        with tempfile.TemporaryDirectory() as d:
            repo = tfz.make_repo(Path(d), fill_plan=False)
            plan = repo / fz.PLAN_REL
            p = json.loads(plan.read_text())
            p["final_seed"] = None
            plan.write_text(json.dumps(p))
            self.assertIn("final_plan.json: final_seed is blank", fg.check_setting("zoom_on", [object()], repo))
        self.assertEqual(fg.check_setting("nonsense", [], REPO_REAL), ["unknown setting 'nonsense'"])


REPO_REAL = fz.REPO


class FinalEvaluationTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        self.repo = final_repo(self.root / "r")
        self.out = self.root / "outputs"
        self.out.mkdir()

    def tearDown(self):
        rp.set_active_roots({})
        self.tmp.cleanup()

    def pairs(self, **kw):
        return [session(self.root, kw.pop("name", "s"), **kw)]

    def test_the_real_repository_is_not_frozen_so_a_final_is_refused(self):
        with self.assertRaisesRegex(SystemExit, "not frozen"):
            ef.evaluate_final("zoom_on", [], REPO_REAL, self.out)

    def test_a_frozen_test_session_is_evaluated_once(self):
        out, res = ef.evaluate_final("zoom_on", self.pairs(), self.repo, self.out)
        self.assertTrue(out.name.startswith("hri_eval_final_v4_zoom_on_"))
        for name in ("eval.json", "eval.md", "run.json", "FINAL_DONE.json", "config_used/frozen.json", "config_used/control.json",
                     "config_used/final_plan.json"):
            self.assertTrue((out / name).exists(), name)
        self.assertEqual(res["final_setting"], "zoom_on")
        self.assertIn("TEST looks", res["splits"])
        done = json.loads((out / "FINAL_DONE.json").read_text())
        self.assertEqual((done["setting"], done["runs"], done["git_commit"] is not None), ("zoom_on", 2, True))
        self.assertEqual(done["frozen_sha256"], fz.sha256_lf(self.repo / fz.FROZEN_REL))
        with self.assertRaisesRegex(SystemExit, "already evaluated as a final"):
            ef.evaluate_final("zoom_on", self.pairs(name="again"), self.repo, self.out)
        other, _ = ef.evaluate_final("zoom_off", self.pairs(name="off", zoom=False), self.repo, self.out)   # another setting is free
        self.assertTrue(other.name.startswith("hri_eval_final_v4_zoom_off_"))

    def test_a_crash_leaves_no_marker_and_does_not_block(self):
        real = ev.evaluate
        ev.evaluate = lambda *a, **k: (_ for _ in ()).throw(RuntimeError("boom"))
        try:
            with self.assertRaises(RuntimeError):
                ef.evaluate_final("zoom_on", self.pairs(), self.repo, self.out)
        finally:
            ev.evaluate = real
        self.assertEqual(fg.markers(self.out, "zoom_on", "evaluation"), [])
        ef.evaluate_final("zoom_on", self.pairs(name="retry"), self.repo, self.out)

    def test_a_changed_config_after_the_freeze_refuses_before_any_data_is_read(self):
        f = self.repo / fz.V4_DIR / "gesture_reader.json"
        f.write_text(f.read_text() + " ")
        called = []
        real = ev.load_sessions
        ev.load_sessions = lambda *a, **k: called.append(1)
        try:
            with self.assertRaisesRegex(SystemExit, "freeze is broken"):
                ef.evaluate_final("zoom_on", self.pairs(), self.repo, self.out)
        finally:
            ev.load_sessions = real
        self.assertEqual(called, [])

    def test_development_data_is_refused_in_the_final(self):
        pairs = [session(self.root, "dev", spec_kw={"commander_look": "placeholder_look_dev_1",
                                                    "clips": {"POINT": "placeholder_point_dev_1", "WAIT": "placeholder_wait_dev_1",
                                                              "STOP": "placeholder_stop_dev_1"}})]
        with self.assertRaisesRegex(SystemExit, "--final-evaluation given"):
            ef.evaluate_final("zoom_on", pairs, self.repo, self.out)

    def test_a_mix_of_development_and_test_is_refused(self):
        pairs = [session(self.root, "mix", spec_kw={"bystander_offsets_m": [(1.2, 0.3)], "bystander_looks": ["placeholder_look_dev_1"]})]
        with self.assertRaisesRegex(SystemExit, "mixes development and test"):
            ef.evaluate_final("bystanders", pairs, self.repo, self.out)

    def test_placeholder_names_cannot_be_frozen_so_no_final_can_start(self):
        repo = tfz.make_repo(self.root / "p")
        sp = repo / fz.SPLITS_REL
        d = json.loads(sp.read_text())
        d["placeholder"] = True
        sp.write_text(json.dumps(d))
        fz.refresh_list(repo)
        with self.assertRaisesRegex(SystemExit, "placeholders"):
            fz.freeze(repo)
        with self.assertRaisesRegex(SystemExit, "not frozen"):
            ef.evaluate_final("zoom_on", self.pairs(name="ph"), repo, self.out)

    def test_wrong_zoom_runs_seed_or_unity_mode_are_refused(self):
        with self.assertRaisesRegex(SystemExit, "needs zoom on"):
            ef.evaluate_final("zoom_on", self.pairs(name="a", zoom=False), self.repo, self.out)
        with self.assertRaisesRegex(SystemExit, "the plan has 2 per setting"):
            ef.evaluate_final("zoom_on", self.pairs(name="b", n=3), self.repo, self.out)
        with self.assertRaisesRegex(SystemExit, "final seed is 7"):
            ef.evaluate_final("zoom_on", self.pairs(name="c", seed=1), self.repo, self.out)
        with self.assertRaisesRegex(SystemExit, "not 'final'"):
            ef.evaluate_final("zoom_on", self.pairs(name="d", mode="development"), self.repo, self.out)
        self.assertEqual(fg.markers(self.out, "zoom_on", "evaluation"), [])          # refusals leave no marker

    def test_a_run_marker_does_not_stop_the_evaluation(self):
        (self.out / "bridge_x").mkdir()
        fg.write_done(self.out / "bridge_x", "zoom_on", "run")
        out, _ = ef.evaluate_final("zoom_on", self.pairs(), self.repo, self.out)
        self.assertTrue((out / "FINAL_DONE.json").exists())


class ServerFinalTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.cfg, _ = S.load_config("configs/v4/bridge.json")
        self.real_req = fz.require_frozen

    def tearDown(self):
        fz.require_frozen = self.real_req
        rp.set_active_roots({})

    def test_refused_while_the_configs_are_not_frozen(self):
        with self.assertRaisesRegex(SystemExit, "not frozen"):
            S.preflight_final(self.cfg, "guide", "zoom_on")

    def test_protocol_2_and_hello_mode_are_refused(self):
        fz.require_frozen = lambda *a, **k: {}
        v2, _ = S.load_config()
        with self.assertRaisesRegex(SystemExit, "protocol 3"):
            S.preflight_final(v2, "guide", "zoom_on")
        with self.assertRaisesRegex(SystemExit, "protocol 3"):
            S.preflight_final(self.cfg, "hello", "zoom_on")

    def test_unknown_setting_zoom_mismatch_and_earlier_run(self):
        fz.require_frozen = lambda *a, **k: {}
        with tempfile.TemporaryDirectory() as d:
            cfg = {**self.cfg, "paths": {"output_root": d}}
            with self.assertRaisesRegex(SystemExit, "unknown final setting"):
                S.preflight_final(cfg, "guide", "nonsense")
            with self.assertRaisesRegex(SystemExit, "needs zoom off"):
                S.preflight_final(cfg, "guide", "zoom_off")                          # control.json has zoom on
            S.preflight_final(cfg, "guide", "zoom_on")
            (Path(d) / "bridge_guide_1").mkdir()
            fg.write_done(Path(d) / "bridge_guide_1", "zoom_on", "run")
            with self.assertRaisesRegex(SystemExit, "already run as a final"):
                S.preflight_final(cfg, "guide", "zoom_on")

    async def test_a_final_run_writes_its_setting_and_the_done_marker_only_after_a_trial(self):
        from test_v4_integration import FakeWorkerV4
        fz.require_frozen = lambda *a, **k: {}
        real = S.make_perception_worker_v4
        made = []

        def factory(out, *a, **k):
            made.append(out)
            return FakeWorkerV4()
        S.make_perception_worker_v4 = factory
        try:
            with tempfile.TemporaryDirectory() as d:
                cfg = {**self.cfg, "port": 0, "paths": {"output_root": d}}
                cfg_path = ROOT / "configs" / "v4" / "bridge.json"
                out = await S.run(cfg, cfg_path, "guide", duration_s=0.3, perception="vision", task="Task2", final_setting="zoom_on")
                self.assertTrue((out / "FINAL_SETTING.json").exists())
                self.assertEqual(json.loads((out / "FINAL_SETTING.json").read_text())["setting"], "zoom_on")
                self.assertFalse((out / "FINAL_RUN_DONE.json").exists())             # no trial finished: no marker, no block
                self.assertEqual(fg.markers(d, "zoom_on", "run"), [])
        finally:
            S.make_perception_worker_v4 = real

    async def test_after_a_finished_trial_the_marker_is_written_and_a_restart_is_refused(self):
        import time
        from test_v4_integration import FakeWorkerV4
        fz.require_frozen = lambda *a, **k: {}
        real = S.make_perception_worker_v4

        def factory(out, *a, **k):
            (out / "python_trial_001.json").write_text("{}")                          # a trial finished in this run
            return FakeWorkerV4()
        S.make_perception_worker_v4 = factory
        try:
            with tempfile.TemporaryDirectory() as d:
                cfg = {**self.cfg, "port": 0, "paths": {"output_root": d}}
                cfg_path = ROOT / "configs" / "v4" / "bridge.json"
                out = await S.run(cfg, cfg_path, "guide", duration_s=0.3, perception="vision", task="Task2", final_setting="zoom_on")
                marker = json.loads((out / "FINAL_RUN_DONE.json").read_text())
                self.assertEqual((marker["setting"], marker["kind"], marker["trials_written"]), ("zoom_on", "run", 1))
                time.sleep(1.1)                                                       # run folders are named by the second
                with self.assertRaisesRegex(SystemExit, "already run as a final"):
                    await S.run(cfg, cfg_path, "guide", duration_s=0.3, perception="vision", task="Task2", final_setting="zoom_on")
                other = await S.run(cfg, cfg_path, "guide", duration_s=0.3, perception="vision", task="Task2", final_setting="bystanders")
                self.assertTrue((other / "FINAL_SETTING.json").exists())
        finally:
            S.make_perception_worker_v4 = real


if __name__ == "__main__":
    unittest.main()
