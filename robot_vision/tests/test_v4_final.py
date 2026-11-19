"""v4 final modes: a final evaluation, export or run is refused unless the v4 configs are frozen with every hash matching, the data
is test-split only and is what its setting says, and a setting is run / evaluated / exported once (final_guard_v4.py). Since 2026-11-14
(AUDIT.md 16.15) the settings are the 13 of the experiments A/B (A1 ... B4, B1_off ... B4_off); the four Task 2 settings are superseded."""

import json
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "tests"))

import export_csv_v4 as ex  # noqa: E402
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

# the test look and clips of the experiments A/B finals (plan test_assignment); the synthetic scenes show POINT only
TEST_SPEC = dict(commander_look="sunbox_m_shirt_plaid", clips={"POINT": "point_mixamo_02", "PROCEED": "proceed_ik_03"})
SCENARIOS = json.loads((ROOT / "configs/v4/experiments/scenarios_ab.json").read_text(encoding="utf-8"))


def final_repo(tmp: Path, freeze: bool = True, runs: int = 2) -> Path:
    """A repository copy with the plan filled, the splits no longer placeholders, and (by default) frozen."""
    repo = tfz.make_repo(tmp)
    plan = repo / fz.PLAN_REL
    d = json.loads(plan.read_text())
    real = json.loads((ROOT.parent / fz.PLAN_REL).read_text())
    d.update(runs_per_setting=runs, final_seed=7, task="Task2", test_assignment=real["test_assignment"])   # make_repo fills a stub
    plan.write_text(json.dumps(d))
    sp = repo / fz.V4_DIR / "data_splits.json"
    d = json.loads(sp.read_text())
    d["placeholder"] = False
    sp.write_text(json.dumps(d))
    fz.refresh_list(repo)
    if freeze:
        fz.freeze(repo, git_commit="abc123")
    return repo


def leak_images(folder: Path, differ: bool = False) -> None:
    """Two image pairs (360 and pan-tilt): identical on / off, or with one pixel different."""
    import numpy as np
    from PIL import Image
    folder.mkdir(exist_ok=True)
    for cam in ("cam360", "pan_tilt"):
        a = (np.arange(8 * 6 * 3) % 251).astype("uint8").reshape(8, 6, 3)
        b = a.copy()
        if differ and cam == "pan_tilt":
            b[2, 2, 0] += 5
        Image.fromarray(a).save(folder / f"{cam}_on.png")
        Image.fromarray(b).save(folder / f"{cam}_off.png")


def session(tmp: Path, name: str, n: int = 2, zoom: bool = True, mode: str = "final", seed: int = 7, spec_kw=None, goal="E2",
            leak: str = "ok", unity_leak=True, setting: str = "A3", extra=None, control_edit=None):
    """A synthetic session of an experiment setting (default A3: the v4 map, so goal E2 exists). Its session.json carries the experiment, set
    and lie probability Unity records, and its bridge run folder the control file the server must run that setting with (S.FINAL_CONTROL).
    leak: 'ok' identical image pairs, 'differ' one pixel differs, 'none' no leak_test/ folder. unity_leak: the value Unity records under the
    leak key in session.json (None = key absent). extra: more session.json keys; control_edit: a function changing the control dict."""
    spec = sv.SceneSpec(**{**TEST_SPEC, **(spec_kw or {})})
    results = [tt.trial(goal, spec, zoom=zoom, seed=k + 1) for k in range(n)]
    entry = fg.plan(REPO_REAL)["settings"][setting]
    control = json.loads((ROOT / S.FINAL_CONTROL[setting]).read_text(encoding="utf-8"))
    if control_edit is not None:
        control_edit(control)
    u, b = sv.export_session(results, tmp, zoom, seed=seed, name=name, mode=mode, v4_override=control,
                             session_extra={"experiment": entry["experiment"], "set": entry["set"],
                                            "lie_probability": SCENARIOS["sets"][entry["set"]]["lie_probability"],
                                            "final_setting": setting, **(extra or {})})
    if leak != "none":
        leak_images(u / "leak_test", differ=(leak == "differ"))
    if unity_leak is not None:
        sj = json.loads((u / "session.json").read_text())
        sj["leak_test"] = {"passed": unity_leak}                   # the key confirmed 2026-11-04: leak_test.passed
        (u / "session.json").write_text(json.dumps(sj))
    return u, b


class GuardTests(unittest.TestCase):
    def test_markers_are_per_setting_and_per_kind(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            for n in ("bridge_a", "eval_b", "export_c"):
                (root / n).mkdir()
            fg.write_done(root / "bridge_a", "A1", "run")
            fg.write_done(root / "eval_b", "B1_off", "evaluation")
            fg.write_done(root / "export_c", "A3", "export")
            self.assertEqual(len(fg.markers(root, "A1", "run")), 1)
            self.assertEqual(fg.markers(root, "A1", "evaluation"), [])             # a finished run does not block its evaluation
            self.assertEqual(fg.markers(root, "A1", "export"), [])                 # nor its export: three kinds, three markers
            self.assertEqual(fg.markers(root, "B1_off", "run"), [])
            self.assertEqual(fg.markers(root, "B1", "evaluation"), [])             # B1 is not B1_off: a name is a setting
            with self.assertRaisesRegex(SystemExit, "already run as a final"):
                fg.ensure_not_done(root, "A1", "run")
            with self.assertRaisesRegex(SystemExit, "already evaluated as a final"):
                fg.ensure_not_done(root, "B1_off", "evaluation")
            with self.assertRaisesRegex(SystemExit, "already exported as a final"):
                fg.ensure_not_done(root, "A3", "export")
            fg.ensure_not_done(root, "A4", "run")                                  # another setting is free
            fg.ensure_not_done(root, "A2_left", "export")                          # and A2_left is not A2_right

    def test_never_overwritten_and_unreadable_markers_are_ignored(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            (root / "x").mkdir()
            fg.write_done(root / "x", "A1", "run")
            with self.assertRaises(FileExistsError):
                fg.write_done(root / "x", "A1", "run")
            (root / "y").mkdir()
            (root / "y" / fg.MARKERS["run"]).write_text("{not json")
            self.assertEqual(len(fg.markers(root, "A1", "run")), 1)
            self.assertEqual(fg.markers(root / "missing", "A1", "run"), [])

    def test_unknown_and_superseded_settings_are_refused(self):
        with self.assertRaisesRegex(SystemExit, "unknown final setting"):
            fg.ensure_not_done(".", "zoom_sideways", "run")
        for old in ("zoom_on", "zoom_off", "bystanders", "zoom_on_repeat"):            # the four Task 2 settings are superseded
            with self.assertRaisesRegex(SystemExit, "unknown final setting"):
                fg.ensure_not_done(".", old, "run")

    def test_the_marker_records_what_was_done(self):
        with tempfile.TemporaryDirectory() as d:
            p = fg.write_done(d, "B4_off", "evaluation", {"git_commit": "abc", "runs": 10})
            rec = json.loads(p.read_text())
            self.assertEqual((rec["setting"], rec["kind"], rec["runs"]), ("B4_off", "evaluation", 10))
            self.assertIn("written", rec)


class SettingChecks(unittest.TestCase):
    def runs(self, tmp, **kw):
        u, b = session(tmp, "s", **kw)
        return ev.load_sessions([(u, b)], gd.load_config(), final_evaluation=True,
                                splits={**json.loads((ROOT / "configs/v4/data_splits.json").read_text()), "placeholder": False})

    def test_a_matching_session_is_fine(self):
        with tempfile.TemporaryDirectory() as d:
            repo = final_repo(Path(d) / "r")
            self.assertEqual(fg.check_setting("A3", self.runs(Path(d)), repo), [])

    def test_the_off_twin_is_a_session_with_detection_off(self):
        with tempfile.TemporaryDirectory() as d:
            repo = final_repo(Path(d) / "r")
            r = self.runs(Path(d), setting="B3_off")
            self.assertEqual(fg.check_setting("B3_off", r, repo), [])
            p = " | ".join(fg.check_setting("B3", r, repo))                       # detection off run, checked as B3 (detection on)
            self.assertIn("lie_detection.second_opinion is False but setting B3 needs True", p)
            self.assertIn("lie_detection.reject_impossible is False but setting B3 needs True", p)
            self.assertNotIn("backtrack", p)                                       # backtrack is off in both

    def test_each_mismatch_is_reported(self):
        with tempfile.TemporaryDirectory() as d:
            repo = final_repo(Path(d) / "r")
            r = self.runs(Path(d), n=3, mode="development", seed=1)
            p = " | ".join(fg.check_setting("A3", r, repo))
            for want in ("3 runs, the plan has 2", "seed 1 but the plan's final seed is 7", "not 'final'"):
                self.assertIn(want, p)
        with tempfile.TemporaryDirectory() as d:
            repo = final_repo(Path(d) / "r")
            r = self.runs(Path(d))                                                  # an A3 session
            p = " | ".join(fg.check_setting("B3", r, repo))                          # checked as B3
            self.assertIn("experiment 'A3' but setting B3 is experiment B3", p)
            self.assertIn("set 'A' but setting B3 is set B", p)
            self.assertIn("lie probability 0.0 but set B has 0.2", p)
            p = " | ".join(fg.check_setting("A1", r, repo))                          # the corridor setting: another map
            self.assertIn("roadmap is 'configs/v4/roadmap.json' but setting A1 needs 'configs/v4/experiments/roadmap_a1.json'", p)

    def test_unity_records_a_float32_lie_probability_and_the_setting_it_ran(self):
        """Read in Unity's TrialRunnerV4Experiment (16.16 decision 7): lie_probability is a float (0.2f), final_setting the setting name."""
        with tempfile.TemporaryDirectory() as d:
            repo = final_repo(Path(d) / "r")
            r = self.runs(Path(d), setting="B3", extra={"lie_probability": 0.20000000298023224})
            self.assertEqual(fg.check_setting("B3", r, repo), [])                       # float32 0.2f is 0.2
        with tempfile.TemporaryDirectory() as d:
            repo = final_repo(Path(d) / "r")
            r = self.runs(Path(d), setting="B3", extra={"final_setting": "B4"})
            self.assertIn("Unity ran final setting 'B4', not 'B3'", " | ".join(fg.check_setting("B3", r, repo)))
        with tempfile.TemporaryDirectory() as d:
            repo = final_repo(Path(d) / "r")
            r = self.runs(Path(d), setting="B3", extra={"lie_probability": 0.25})
            self.assertIn("lie probability 0.25 but set B has 0.2", " | ".join(fg.check_setting("B3", r, repo)))
        with tempfile.TemporaryDirectory() as d:                                       # no final_setting recorded (older sessions): not a problem
            repo = final_repo(Path(d) / "r")
            r = self.runs(Path(d), setting="B3", extra={"final_setting": ""})
            self.assertEqual(fg.check_setting("B3", r, repo), [])

    def test_looks_and_clips_must_be_the_settings_test_assignment(self):
        with tempfile.TemporaryDirectory() as d:
            repo = final_repo(Path(d) / "r")
            r = self.runs(Path(d), spec_kw={"commander_look": "sunbox_f2", "clips": {"POINT": "point_mixamo_02", "PROCEED": "proceed_ik_03"}})
            p = " | ".join(fg.check_setting("A3", r, repo))                          # sunbox_f2 is a test look, but not this setting's
            self.assertIn("looks ['sunbox_f2'] / clips [] are not in the setting's test assignment", p)
        with tempfile.TemporaryDirectory() as d:
            repo = final_repo(Path(d) / "r")
            r = self.runs(Path(d), spec_kw={"clips": {"POINT": "wait_ik_02", "PROCEED": "proceed_ik_03"}})
            self.assertIn("clips ['wait_ik_02']", " | ".join(fg.check_setting("A3", r, repo)))

    def test_blanks_in_the_plan_are_reported(self):
        with tempfile.TemporaryDirectory() as d:
            repo = tfz.make_repo(Path(d), fill_plan=False)
            plan = repo / fz.PLAN_REL
            p = json.loads(plan.read_text())
            p["final_seed"] = None
            plan.write_text(json.dumps(p))
            self.assertIn("final_plan.json: final_seed is blank", fg.check_setting("A3", [object()], repo))
        self.assertEqual(fg.check_setting("nonsense", [], REPO_REAL), ["unknown setting 'nonsense'"])


class PlanAndControlFiles(unittest.TestCase):
    """AUDIT.md 16.15: the 13 settings, their control files and maps agree with each other and with scenarios_ab.json."""

    PLAN = fg.plan(fz.REPO)

    def test_every_setting_has_its_control_file_and_it_fits(self):
        self.assertEqual(set(S.FINAL_CONTROL), set(self.PLAN["settings"]))
        for setting, f in S.FINAL_CONTROL.items():
            control = json.loads((ROOT / f).read_text(encoding="utf-8"))
            self.assertEqual(fg.control_problems(setting, control, fz.REPO), [], setting)
            S.check_final_control(setting, f)
        self.assertEqual({S.FINAL_CONTROL[s] for s in S.FINAL_CONTROL}, {f"configs/v4/experiments/{n}.json" for n in (
            "control_lie_on", "control_lie_on_a1", "control_lie_on_a2_right", "control_lie_on_a2_left",
            "control_lie_off", "control_lie_off_a1", "control_lie_off_a2_right")})        # no off file for A2_left: it has no Set B twin
        self.assertEqual(S.FINAL_CONTROL["B1_off"], "configs/v4/experiments/control_lie_off_a1.json")

    def test_a_control_file_of_another_setting_is_found(self):
        on = json.loads((ROOT / "configs/v4/experiments/control_lie_on.json").read_text())
        off = json.loads((ROOT / "configs/v4/experiments/control_lie_off.json").read_text())
        self.assertIn("lie_detection.second_opinion is False but setting B3 needs True", fg.control_problems("B3", off, fz.REPO)[0])
        self.assertEqual(len(fg.control_problems("B3_off", on, fz.REPO)), 3)            # second opinion, reject impossible and (AUDIT.md 16.25.2) the checkpoint switch
        a1 = json.loads((ROOT / "configs/v4/experiments/control_lie_on_a1.json").read_text())
        self.assertTrue(any("roadmap is" in x for x in fg.control_problems("A3", a1, fz.REPO)))
        backtrack = json.loads(json.dumps(on))
        backtrack["lie_detection"]["backtrack"] = True                                  # backtrack stays off in every experiment (16.10.2)
        self.assertTrue(any("backtrack" in x for x in fg.control_problems("A3", backtrack, fz.REPO)))

    def test_entries_agree_with_scenarios_ab(self):
        for setting, e in self.PLAN["settings"].items():
            n = e["experiment"][1:]
            sc = SCENARIOS["scenarios"][n]
            side = "_left" if "_left" in setting else "_right" if "_right" in setting else ""
            want_map = {"": sc["map"], "_right": "turn", "_left": "turn_left"}[side]
            self.assertEqual(e["map"], want_map, setting)
            self.assertEqual(e["lie_detection"], "off" if setting.endswith("_off") else "on", setting)
            self.assertEqual(e["set"], e["experiment"][0], setting)
            self.assertEqual(SCENARIOS["detection"][e["lie_detection"]], fg.detection_switches(e["lie_detection"], fz.REPO))
            if e["map"] in SCENARIOS["maps"]:
                road = json.loads((ROOT / e["roadmap"]).read_text(encoding="utf-8"))
                self.assertEqual(road["start"], SCENARIOS["maps"][e["map"]]["start"], setting)
            else:
                self.assertEqual(e["roadmap"], "configs/v4/roadmap.json")
        self.assertEqual(SCENARIOS["sets"]["A"]["lie_probability"], 0.0)
        self.assertEqual(SCENARIOS["sets"]["B"]["lie_probability"], 0.2)

    def test_the_comparisons_of_the_combined_table_follow_from_the_plan(self):
        names = list(self.PLAN["settings"])
        pairs = ex.comparisons(names, self.PLAN)
        kinds = [(c["kind"], c["x"], c["y"]) for c in pairs]
        for pair in (("A vs B", "A1", "B1"), ("A vs B", "A2_right", "B2_right"), ("A vs B", "A3", "B3"), ("A vs B", "A4", "B4"),
                     ("B on vs off", "B1_off", "B1"), ("B on vs off", "B2_right_off", "B2_right"), ("B on vs off", "B3_off", "B3"),
                     ("B on vs off", "B4_off", "B4"), ("A2 right vs left", "A2_left", "A2_right")):
            self.assertIn(pair, kinds)
        self.assertEqual(len(pairs), 9)                                                 # A2_left has no B twin; nothing else is compared
        self.assertTrue(all(c["available"] for c in pairs))
        self.assertFalse(any(c["available"] for c in ex.comparisons(["A1"], self.PLAN)))

    # ---- AUDIT.md 16.25.2: the checkpoint switches of T4 ----
    EXP = ROOT / "configs/v4/experiments"
    CP_KEYS = ("checkpoint", "checkpoint_fraction", "checkpoint_scope", "checkpoint_person_radius_m", "checkpoint_branches", "next_junction_back")

    def on_control(self):
        return json.loads((self.EXP / "control_lie_on.json").read_text(encoding="utf-8"))

    def test_the_switches_are_the_three_rules_and_the_six_checkpoint_keys(self):
        self.assertEqual(fg.LIE_RULES, ("second_opinion", "reject_impossible", "backtrack"))
        self.assertEqual(fg.CHECKPOINT_SWITCHES, self.CP_KEYS)
        self.assertEqual(fg.SWITCHES, fg.LIE_RULES + fg.CHECKPOINT_SWITCHES)

    def test_the_plan_block_is_t4_exactly_the_on_files_and_the_runners_t4(self):
        import run_t3_v4 as rn
        block = self.PLAN["lie_detection_checkpoint"]
        self.assertEqual(set(block), {"declared", "on", "off"})
        self.assertEqual(fg.checkpoint_switches("off", fz.REPO), {"checkpoint": False})
        on = fg.checkpoint_switches("on", fz.REPO)
        self.assertEqual(tuple(on), self.CP_KEYS)
        for name in ("control_lie_on", "control_lie_on_a1", "control_lie_on_a2_right", "control_lie_on_a2_left"):
            ld = json.loads((self.EXP / f"{name}.json").read_text(encoding="utf-8"))["lie_detection"]
            self.assertEqual({k: ld[k] for k in self.CP_KEYS}, on, name)
        cp = json.loads((self.EXP / "checkpoints.json").read_text(encoding="utf-8"))
        t4 = rn.detection_for("T4", "on", cp)
        self.assertEqual({k: t4[k] for k in self.CP_KEYS}, on)
        self.assertEqual(on["checkpoint_branches"], cp["branches"])
        for off in ("control_lie_off", "control_lie_off_a1", "control_lie_off_a2_right"):
            self.assertFalse(json.loads((self.EXP / f"{off}.json").read_text(encoding="utf-8"))["lie_detection"].get("checkpoint", False), off)

    def test_each_checkpoint_key_wrong_in_a_detection_on_file_is_refused_with_one_problem(self):
        wrong = {"checkpoint": False, "checkpoint_fraction": 0.4, "checkpoint_scope": "any", "checkpoint_person_radius_m": 4.0,
                 "checkpoint_branches": ["J1>FORWARD", "J1>RIGHT"], "next_junction_back": False}
        for k, v in wrong.items():
            c = self.on_control()
            c["lie_detection"][k] = v
            problems = fg.control_problems("A3", c, fz.REPO)
            self.assertEqual(len(problems), 1, (k, problems))
            self.assertIn(f"lie_detection.{k} is {v!r} but setting A3 needs {fg.checkpoint_switches('on', fz.REPO)[k]!r}", problems[0])
            c2 = self.on_control()
            del c2["lie_detection"][k]                                                    # a missing key is its default: for a declared value that is a mismatch
            self.assertEqual(len(fg.control_problems("A3", c2, fz.REPO)), 1, k)

    def test_a_detection_on_setting_with_a_file_without_t4_is_refused_for_every_key(self):
        off = json.loads((self.EXP / "control_lie_off.json").read_text(encoding="utf-8"))
        off["lie_detection"].update({k: v for k, v in self.on_control()["lie_detection"].items() if k in fg.LIE_RULES})      # the three rules of "on", no checkpoint keys: the earlier T0 file
        problems = fg.control_problems("B3", off, fz.REPO)
        self.assertEqual(len(problems), 6)
        for k in self.CP_KEYS:
            self.assertTrue(any(f"lie_detection.{k} is" in p for p in problems), k)

    def test_a_detection_off_setting_must_have_checkpoint_false_and_ignores_the_other_keys(self):
        c = json.loads((self.EXP / "control_lie_off.json").read_text(encoding="utf-8"))
        self.assertEqual(fg.control_problems("B3_off", c, fz.REPO), [])                   # no checkpoint keys = false
        c["lie_detection"]["checkpoint"] = True
        problems = fg.control_problems("B3_off", c, fz.REPO)
        self.assertEqual(len(problems), 1)
        self.assertIn("lie_detection.checkpoint is True but setting B3_off needs False", problems[0])
        c["lie_detection"].update({"checkpoint": False, "checkpoint_scope": "anything", "checkpoint_branches": ["x"]})
        self.assertEqual(fg.control_problems("B3_off", c, fz.REPO), [])                   # the other keys do not matter when the checkpoint is off
        self.assertEqual(len(fg.control_problems("B3_off", self.on_control(), fz.REPO)), 3)     # the detection-on file for an off setting: two rules and the checkpoint

    def test_every_one_of_the_13_settings_passes_with_its_own_file(self):
        for setting, f in S.FINAL_CONTROL.items():
            self.assertEqual(fg.control_problems(setting, json.loads((ROOT / f).read_text(encoding="utf-8")), fz.REPO), [], setting)

    def test_the_run_check_of_check_setting_refuses_a_bridge_config_with_a_wrong_checkpoint_switch(self):
        from types import SimpleNamespace
        pl = fg.plan(fz.REPO)
        spec = pl["settings"]["A3"]
        with tempfile.TemporaryDirectory() as d:
            bridge = Path(d) / "bridge_guide_20261119_000000"
            (bridge / "config_used").mkdir(parents=True)
            runs = [SimpleNamespace(name="run_001", looks=[], clips=[], bridge_dir=bridge)]
            good = self.on_control()
            (bridge / "config_used" / "control.json").write_text(json.dumps(good), encoding="utf-8")
            self.assertEqual(fg._experiment_run_problems("A3", spec, pl, runs, fz.REPO), [])
            good["lie_detection"]["checkpoint_scope"] = "any"
            (bridge / "config_used" / "control.json").write_text(json.dumps(good), encoding="utf-8")
            problems = fg._experiment_run_problems("A3", spec, pl, runs, fz.REPO)
            self.assertEqual(len(problems), 1)
            self.assertIn("bridge_guide_20261119_000000: lie_detection.checkpoint_scope is 'any' but setting A3 needs 'disputed'", problems[0])

    def test_the_export_label_does_not_change(self):
        on, off = self.on_control()["lie_detection"], json.loads((self.EXP / "control_lie_off.json").read_text(encoding="utf-8"))["lie_detection"]
        self.assertEqual((ex.lie_detection_label(on), ex.lie_detection_label(off)), ("on", "off"))
        self.assertEqual(ex.lie_detection_label({"second_opinion": True, "reject_impossible": False, "backtrack": False, "checkpoint": True}), "a")       # the checkpoint is not a letter
        self.assertEqual(ex.lie_detection_label({"second_opinion": False, "reject_impossible": True, "backtrack": True, "checkpoint": True, "checkpoint_scope": "disputed"}), "bc")
        self.assertEqual(ex.lie_detection_label({"second_opinion": True, "reject_impossible": True, "backtrack": True}), "abc")


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
            ef.evaluate_final("A3", [], REPO_REAL, self.out)

    def test_a_frozen_test_session_is_evaluated_once(self):
        out, res = ef.evaluate_final("A3", self.pairs(), self.repo, self.out)
        self.assertTrue(out.name.startswith("hri_eval_final_v4_A3_"))
        for name in ("eval.json", "eval.md", "run.json", "FINAL_DONE.json", "config_used/frozen.json", "config_used/control.json",
                     "config_used/final_plan.json"):
            self.assertTrue((out / name).exists(), name)
        self.assertEqual(res["final_setting"], "A3")
        exp = res["experiment"]                                                     # AUDIT.md 16.15 item 6: the experiment's own numbers
        self.assertEqual((exp["setting"], exp["plan_entry"]["experiment"], exp["summary"]["runs"], len(exp["runs_table"])), ("A3", "A3", 2, 2))
        self.assertEqual(exp["summary"]["success"]["n"], 2)
        self.assertIn("### Experiment numbers, setting A3", (out / "eval.md").read_text(encoding="utf-8"))
        self.assertIn("TEST looks", res["splits"])
        done = json.loads((out / "FINAL_DONE.json").read_text())
        self.assertEqual((done["setting"], done["runs"], done["git_commit"] is not None), ("A3", 2, True))
        self.assertEqual(done["frozen_sha256"], fz.sha256_lf(self.repo / fz.FROZEN_REL))
        with self.assertRaisesRegex(SystemExit, "already evaluated as a final"):
            ef.evaluate_final("A3", self.pairs(name="again"), self.repo, self.out)
        other, _ = ef.evaluate_final("B3_off", self.pairs(name="off", setting="B3_off"), self.repo, self.out)   # another setting is free
        self.assertTrue(other.name.startswith("hri_eval_final_v4_B3_off_"))

    def test_a_crash_leaves_no_marker_and_does_not_block(self):
        real = ev.evaluate
        ev.evaluate = lambda *a, **k: (_ for _ in ()).throw(RuntimeError("boom"))
        try:
            with self.assertRaises(RuntimeError):
                ef.evaluate_final("A3", self.pairs(), self.repo, self.out)
        finally:
            ev.evaluate = real
        self.assertEqual(fg.markers(self.out, "A3", "evaluation"), [])
        ef.evaluate_final("A3", self.pairs(name="retry"), self.repo, self.out)

    def test_a_changed_config_after_the_freeze_refuses_before_any_data_is_read(self):
        f = self.repo / fz.V4_DIR / "gesture_reader.json"
        f.write_text(f.read_text() + " ")
        called = []
        real = ev.load_sessions
        ev.load_sessions = lambda *a, **k: called.append(1)
        try:
            with self.assertRaisesRegex(SystemExit, "freeze is broken"):
                ef.evaluate_final("A3", self.pairs(), self.repo, self.out)
        finally:
            ev.load_sessions = real
        self.assertEqual(called, [])

    def test_development_data_is_refused_in_the_final(self):
        pairs = [session(self.root, "dev", spec_kw={"commander_look": "sunbox_m1",
                                                    "clips": {"POINT": "point_mixamo_01", "WAIT": "wait_ik_01",
                                                              "STOP": "stop_ik_01"}})]
        with self.assertRaisesRegex(SystemExit, "--final-evaluation given"):
            ef.evaluate_final("A3", pairs, self.repo, self.out)

    def test_a_mix_of_development_and_test_is_refused(self):
        pairs = [session(self.root, "mix", spec_kw={"bystander_offsets_m": [(1.2, 0.3)], "bystander_looks": ["sunbox_m1"]})]
        with self.assertRaisesRegex(SystemExit, "mixes development and test"):
            ef.evaluate_final("A3", pairs, self.repo, self.out)

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
            ef.evaluate_final("A3", self.pairs(name="ph"), repo, self.out)

    def test_wrong_runs_seed_mode_experiment_control_or_looks_are_refused(self):
        with self.assertRaisesRegex(SystemExit, "the plan has 2 per setting"):
            ef.evaluate_final("A3", self.pairs(name="b", n=3), self.repo, self.out)
        with self.assertRaisesRegex(SystemExit, "final seed is 7"):
            ef.evaluate_final("A3", self.pairs(name="c", seed=1), self.repo, self.out)
        with self.assertRaisesRegex(SystemExit, "not 'final'"):
            ef.evaluate_final("A3", self.pairs(name="d", mode="development"), self.repo, self.out)
        with self.assertRaisesRegex(SystemExit, "experiment 'A3' but setting B3 is experiment B3"):          # the other experiment's name
            ef.evaluate_final("B3", self.pairs(name="e"), self.repo, self.out)
        with self.assertRaisesRegex(SystemExit, "lie_detection.second_opinion is False but setting A3 needs True"):   # detection off run as A3
            ef.evaluate_final("A3", self.pairs(name="f", setting="B3_off", extra={"experiment": "A3", "set": "A", "lie_probability": 0.0}),
                              self.repo, self.out)
        with self.assertRaisesRegex(SystemExit, "not in the setting's test assignment"):
            ef.evaluate_final("A3", self.pairs(name="g", spec_kw={"commander_look": "sunbox_f2"}), self.repo, self.out)
        self.assertEqual(fg.markers(self.out, "A3", "evaluation"), [])          # refusals leave no marker

    def refused_for_leak(self, why: str, **kw):
        called = []
        real = ev.load_sessions
        ev.load_sessions = lambda *a, **k: called.append(1)
        try:
            with self.assertRaisesRegex(SystemExit, "leak test has not passed") as cm:
                ef.evaluate_final("A3", [session(self.root, kw.pop("name", "lk"), **kw)], self.repo, self.out)
        finally:
            ev.load_sessions = real
        self.assertIn(why, str(cm.exception))
        self.assertEqual(called, [])                                           # refused before any test data was read
        self.assertEqual(fg.markers(self.out, "A3", "evaluation"), [])    # and no FINAL_DONE.json

    def test_the_leak_test_is_enforced_before_the_final_evaluation(self):
        self.refused_for_leak("Unity's own leak test failed", name="u", unity_leak=False)
        self.refused_for_leak("Python's leak test failed", name="p", leak="differ")
        self.refused_for_leak("no leak_test/ folder", name="m", leak="none")
        self.refused_for_leak("has no 'leak_test.passed'", name="k", unity_leak=None)

    def test_a_passing_leak_test_is_recorded_by_the_evaluation(self):
        pairs = self.pairs()
        out, _ = ef.evaluate_final("A3", pairs, self.repo, self.out)
        rec = json.loads((pairs[0][0] / "leak_test" / "leak_test.json").read_text())
        self.assertTrue(rec["passed"])                                         # written by the independent check, not by Unity
        self.assertTrue((out / "FINAL_DONE.json").exists())

    def test_a_run_marker_does_not_stop_the_evaluation(self):
        (self.out / "bridge_x").mkdir()
        fg.write_done(self.out / "bridge_x", "A3", "run")
        out, _ = ef.evaluate_final("A3", self.pairs(), self.repo, self.out)
        self.assertTrue((out / "FINAL_DONE.json").exists())


class UnconfirmedKeyTests(unittest.TestCase):
    def test_a_repo_frozen_with_the_placeholder_key_refuses_every_final_evaluation(self):
        with tempfile.TemporaryDirectory() as d:
            repo = tfz.make_repo(Path(d) / "r")
            f = repo / fz.V4_DIR / "gt_eval.json"
            cfg = json.loads(f.read_text())
            cfg["unity_leak_result_key_confirmed"] = False
            f.write_text(json.dumps(cfg))
            fz.refresh_list(repo)
            fz.freeze(repo)                                                     # the freeze itself does not read the key
            u, b = session(Path(d), "s")
            try:
                with self.assertRaisesRegex(SystemExit, "placeholder, not confirmed by Nusrat"):
                    ef.evaluate_final("A3", [(u, b)], repo, Path(d) / "out")
            finally:
                rp.set_active_roots({})


class ServerFinalTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.cfg, _ = S.load_config("configs/v4/bridge.json")
        self.real_req = fz.require_frozen

    def tearDown(self):
        fz.require_frozen = self.real_req
        rp.set_active_roots({})

    def test_refused_while_the_configs_are_not_frozen(self):
        with self.assertRaisesRegex(SystemExit, "not frozen"):
            S.preflight_final(self.cfg, "guide", "A3")

    def test_protocol_2_and_hello_mode_are_refused(self):
        fz.require_frozen = lambda *a, **k: {}
        v2, _ = S.load_config()
        with self.assertRaisesRegex(SystemExit, "protocol 3"):
            S.preflight_final(v2, "guide", "A3")
        with self.assertRaisesRegex(SystemExit, "protocol 3"):
            S.preflight_final(self.cfg, "hello", "A3")

    def test_unknown_setting_zoom_mismatch_and_earlier_run(self):
        fz.require_frozen = lambda *a, **k: {}
        with tempfile.TemporaryDirectory() as d:
            cfg = {**self.cfg, "paths": {"output_root": d}}
            with self.assertRaisesRegex(SystemExit, "unknown final setting"):
                S.preflight_final(cfg, "guide", "nonsense")
            with self.assertRaisesRegex(SystemExit, "must run with --control-config"):
                S.preflight_final(cfg, "guide", "B3_off")                            # P11: control.json is not B3_off's file
            with self.assertRaisesRegex(SystemExit, "must run with --control-config"):
                S.preflight_final(cfg, "guide", "B3_off", "configs/v4/experiments/control_lie_on.json")   # detection ON file for an OFF setting
            S.preflight_final(cfg, "guide", "B3_off", "configs/v4/experiments/control_lie_off.json")
            S.preflight_final(cfg, "guide", "A3", "configs/v4/experiments/control_lie_on.json")
            S.preflight_final(cfg, "guide", "B2_right_off", "configs/v4/experiments/control_lie_off_a2_right.json")
            (Path(d) / "bridge_guide_1").mkdir()
            fg.write_done(Path(d) / "bridge_guide_1", "A3", "run")
            with self.assertRaisesRegex(SystemExit, "already run as a final"):
                S.preflight_final(cfg, "guide", "A3", "configs/v4/experiments/control_lie_on.json")
            S.preflight_final(cfg, "guide", "B3", "configs/v4/experiments/control_lie_on.json")   # the B3 twin is another setting

    def test_a_control_file_that_does_not_fit_its_setting_is_refused_even_under_the_right_name(self):
        """The file name is right but the content is another setting's (detection or map): the preflight reads the content (16.15)."""
        fz.require_frozen = lambda *a, **k: {}
        wrong = json.loads((ROOT / "configs/v4/experiments/control_lie_on.json").read_text())
        wrong["lie_detection"]["second_opinion"] = False
        with tempfile.TemporaryDirectory() as d:
            cfg = {**self.cfg, "paths": {"output_root": d}}
            f = ROOT / "configs/v4/experiments/control_lie_on.json"
            real = f.read_text(encoding="utf-8")
            real_read = S.dio.read_json
            S.dio.read_json = lambda p: wrong if Path(p).name == "control_lie_on.json" else real_read(p)
            try:
                with self.assertRaisesRegex(SystemExit, r"setting 'A3' refused: lie_detection.second_opinion is False but setting A3 needs True"):
                    S.preflight_final(cfg, "guide", "A3", "configs/v4/experiments/control_lie_on.json")
            finally:
                S.dio.read_json = real_read
            self.assertEqual(f.read_text(encoding="utf-8"), real)

    def test_the_preflight_refuses_a_file_whose_checkpoint_switches_are_not_the_settings(self):
        """AUDIT.md 16.25.2: the file name is right but the content has the checkpoint switches of another setting (T0 file for a detection-on setting, T4 file for an off one)."""
        fz.require_frozen = lambda *a, **k: {}
        for setting, name, key, value, message in (
                ("A3", "control_lie_on.json", "checkpoint_scope", "any", r"setting 'A3' refused: lie_detection.checkpoint_scope is 'any' but setting A3 needs 'disputed'"),
                ("A3", "control_lie_on.json", "checkpoint", False, r"setting 'A3' refused: lie_detection.checkpoint is False but setting A3 needs True"),
                ("B3_off", "control_lie_off.json", "checkpoint", True, r"setting 'B3_off' refused: lie_detection.checkpoint is True but setting B3_off needs False")):
            wrong = json.loads((ROOT / "configs/v4/experiments" / name).read_text(encoding="utf-8"))
            wrong["lie_detection"][key] = value
            with tempfile.TemporaryDirectory() as d:
                cfg = {**self.cfg, "paths": {"output_root": d}}
                real_read = S.dio.read_json
                S.dio.read_json = lambda p, wrong=wrong, name=name: wrong if Path(p).name == name else real_read(p)
                try:
                    with self.assertRaisesRegex(SystemExit, message):
                        S.preflight_final(cfg, "guide", setting, f"configs/v4/experiments/{name}")
                finally:
                    S.dio.read_json = real_read

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
                cfg = {**self.cfg, "port": 0, "paths": {"output_root": d}, "perception_workers": {"mode": "threads"}}   # these tests patch the thread factory
                cfg_path = ROOT / "configs" / "v4" / "bridge.json"
                out = await S.run(cfg, cfg_path, "guide", duration_s=0.3, perception="vision", task="Task2", final_setting="A3",
                                  control_config="configs/v4/experiments/control_lie_on.json")
                self.assertTrue((out / "FINAL_SETTING.json").exists())
                self.assertEqual(json.loads((out / "FINAL_SETTING.json").read_text())["setting"], "A3")
                self.assertFalse((out / "FINAL_RUN_DONE.json").exists())             # no trial finished: no marker, no block
                self.assertEqual(fg.markers(d, "A3", "run"), [])
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
                cfg = {**self.cfg, "port": 0, "paths": {"output_root": d}, "perception_workers": {"mode": "threads"}}   # these tests patch the thread factory
                cfg_path = ROOT / "configs" / "v4" / "bridge.json"
                out = await S.run(cfg, cfg_path, "guide", duration_s=0.3, perception="vision", task="Task2", final_setting="A3",
                                  control_config="configs/v4/experiments/control_lie_on.json")
                marker = json.loads((out / "FINAL_RUN_DONE.json").read_text())
                self.assertEqual((marker["setting"], marker["kind"], marker["trials_written"]), ("A3", "run", 1))
                time.sleep(1.1)                                                       # run folders are named by the second
                with self.assertRaisesRegex(SystemExit, "already run as a final"):
                    await S.run(cfg, cfg_path, "guide", duration_s=0.3, perception="vision", task="Task2", final_setting="A3",
                                  control_config="configs/v4/experiments/control_lie_on.json")
                other = await S.run(cfg, cfg_path, "guide", duration_s=0.3, perception="vision", task="Task2", final_setting="B3",
                                      control_config="configs/v4/experiments/control_lie_on.json")
                self.assertTrue((other / "FINAL_SETTING.json").exists())
        finally:
            S.make_perception_worker_v4 = real


class SummaryTests(unittest.TestCase):
    """export_csv_v4.summarize: the numbers of one setting, each with its count (the same code the final evaluation and the combined table use)."""

    def rows(self):
        base = dict(outcome="SUCCESS", failure_reason="none", time_s=100.0, trail_over_optimal=1.1, max_distance_from_optimal_m=0.4,
                    share_within_corridor=0.9, stops=0, stop_s=0.0, collisions=0, lies_given=2, lies_detected=1, lies_corrected=1,
                    lies_fooled=0, watchdog_stops=0)
        return [dict(base), dict(base, time_s=120.0, stops=2, stop_s=3.5, lies_detected=2, lies_corrected=2),
                dict(base, outcome="FAILURE", failure_reason="timeout", time_s=270.0, lies_fooled=1, lies_corrected=0, watchdog_stops=1),
                dict(base, outcome="FAILURE", failure_reason="wrong_goal", time_s=90.0, collisions=1),
                dict(base, outcome="FAILURE", failure_reason="weird"),
                dict(base, outcome=None, failure_reason=None, time_s=None, trail_over_optimal=None, lies_given=None, lies_detected=None,
                     lies_corrected=None, lies_fooled=None, stops=None, collisions=None, watchdog_stops=None)]

    def test_counts_rates_and_intervals(self):
        import hri_analysis as ha
        sm = ex.summarize(self.rows(), 1.96)
        self.assertEqual((sm["runs"], sm["runs_with_an_outcome"]), (6, 5))
        self.assertEqual((sm["success"]["k"], sm["success"]["n"], sm["success"]["ratio"]), (2, 5, 0.4))
        self.assertEqual(sm["success"]["wilson95"], list(ha.wilson(2, 5, 1.96)))
        self.assertEqual(sm["failure_kinds"], {"collision": 0, "timeout": 1, "aborted": 0, "wrong_goal": 1, "other": 1})
        self.assertEqual(sm["time_s"]["all_runs"], {"n": 5, "median": 100.0})
        self.assertEqual(sm["time_s"]["success_runs"], {"n": 2, "median": 110.0})
        self.assertEqual(sm["trail_over_optimal"], {"n": 5, "median": 1.1})
        ls = sm["lies"]
        self.assertEqual((ls["runs_evaluated"], ls["given"], ls["detected"]["total"], ls["corrected"]["total"], ls["fooled"]["total"]), (5, 10, 6, 5, 1))
        self.assertEqual((ls["fooled"]["k"], ls["fooled"]["n"], ls["fooled"]["wilson95"]), (1, 10, list(ha.wilson(1, 10, 1.96))))
        self.assertEqual((sm["safety_stops"]["runs_counted"], sm["safety_stops"]["runs_with_a_stop"]["k"], sm["safety_stops"]["stops_total"],
                          sm["safety_stops"]["seconds_in_stops"]), (5, 1, 2, 3.5))
        self.assertEqual((sm["watchdog_stops"]["runs_counted"], sm["watchdog_stops"]["stops_total"], sm["watchdog_stops"]["runs_with_a_stop"]["k"]), (5, 1, 1))
        self.assertEqual((sm["collisions"]["runs_with_a_collision"], sm["collisions"]["collisions_total"]), (1, 1))
        self.assertIn("**SUCCESS 2/5 = 0.4**", ex.summary_markdown("B3", sm))

    def test_nothing_is_guessed_without_data_or_without_lies(self):
        sm = ex.summarize([], 1.96)
        self.assertEqual((sm["success"]["ratio"], sm["success"]["wilson95"]), (ev.NOT_EVALUATED, ev.NOT_EVALUATED))
        self.assertEqual(sm["time_s"]["all_runs"]["median"], ev.NOT_EVALUATED)
        rows = [dict(outcome="SUCCESS", failure_reason="none", time_s=50.0, lies_given=0, lies_detected=0, lies_corrected=0, lies_fooled=0)] * 3
        sm = ex.summarize(rows, 1.96)                                                  # Set A: no lies, so no detection rates
        self.assertEqual((sm["lies"]["given"], sm["lies"]["detected"]["rate"]), (0, "no lies given"))
        self.assertIn("no lies, so no detection rates", ex.summary_markdown("A3", sm))


class NewcombeTests(unittest.TestCase):
    """The Newcombe hybrid-score interval of a difference of two rates (AUDIT.md 16.16 decision 6), in percentage points."""

    def test_the_published_example(self):
        # Newcombe (1998), Statistics in Medicine 17, example 1 (56/70 against 48/80): difference 0.2000, 95 % interval 0.0524 to 0.3339 (method 10)
        r = ex.newcombe(48, 80, 56, 70)
        self.assertEqual((r["difference_pp"], r["lo_pp"], r["hi_pp"]), (20.0, 5.2, 33.4))
        self.assertEqual(r["method"], "Newcombe hybrid score")

    def test_the_sign_follows_y_minus_x_and_the_interval_is_symmetric_for_equal_rates(self):
        up, down = ex.newcombe(10, 20, 15, 20), ex.newcombe(15, 20, 10, 20)
        self.assertEqual((up["difference_pp"], down["difference_pp"]), (25.0, -25.0))
        self.assertEqual((up["lo_pp"], up["hi_pp"]), (-down["hi_pp"], -down["lo_pp"]))
        eq = ex.newcombe(0, 20, 0, 20)
        self.assertEqual((eq["difference_pp"], eq["lo_pp"], eq["hi_pp"]), (0.0, -16.1, 16.1))       # 0/20 against 0/20: still wide

    def test_the_interval_stays_within_minus_and_plus_100_and_contains_the_difference(self):
        for k1, k2 in ((0, 20), (20, 0), (20, 20), (1, 19), (7, 13)):
            r = ex.newcombe(k1, 20, k2, 20)
            self.assertLessEqual(-100.0, r["lo_pp"])
            self.assertLessEqual(r["hi_pp"], 100.0)
            self.assertLessEqual(r["lo_pp"], r["difference_pp"])
            self.assertLessEqual(r["difference_pp"], r["hi_pp"])

    def test_a_rate_without_a_denominator_is_not_evaluated(self):
        r = ex.newcombe(0, 0, 1, 2)
        self.assertEqual((r["difference_pp"], r["lo_pp"], r["hi_pp"]), (ev.NOT_EVALUATED,) * 3)


class LieDetectionColumnTests(unittest.TestCase):
    """AUDIT.md 16.16.2 item 4: Unity's session.json has no lie_detection, so the export's setting / lie_detection columns come from the bridge's
    control file (what the robot ran)."""

    SW = ("second_opinion", "reject_impossible", "backtrack")

    def test_the_label_of_the_switches(self):
        label = lambda *v: ex.lie_detection_label(dict(zip(self.SW, v)))
        self.assertEqual(label(False, False, False), "off")
        self.assertEqual(label(True, True, False), "on")                              # the experiments' "on": backtrack stays off
        self.assertEqual((label(True, False, False), label(False, True, False), label(False, True, True), label(True, True, True)), ("a", "b", "bc", "abc"))
        self.assertIsNone(ex.lie_detection_label({}))
        self.assertIsNone(ex.lie_detection_label(None))

    def test_a_final_export_says_what_the_robot_ran_although_session_json_has_no_label(self):
        import csv
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            repo, out = final_repo(root / "r"), root / "outputs"
            out.mkdir()
            seen = {}
            for setting, want in (("A3", "on"), ("B3_off", "off")):
                u, b = session(root, "s_" + setting, setting=setting)
                self.assertNotIn("lie_detection", json.loads((u / "session.json").read_text()))     # as Unity writes it
                folder, rows, _ = ex.export_final(setting, [(u, b)], repo, out)
                with (folder / "runs.csv").open(encoding="utf-8") as f:
                    table = list(csv.DictReader(f))
                seen[setting] = {(r["setting"], r["lie_detection"]) for r in table}
                self.assertEqual({(r["setting"], r["lie_detection"]) for r in rows_as_strings(rows)}, seen[setting])
            self.assertEqual(seen, {"A3": {("on", "on")}, "B3_off": {("off", "off")}})
        rp.set_active_roots({})

    def test_a_label_unity_does_record_stays_in_setting_and_lie_detection_is_still_the_control_file(self):
        with tempfile.TemporaryDirectory() as d:
            u, b = session(Path(d), "m", setting="B3", extra={"lie_detection": "mirror"})
            runs = ev.load_sessions([(u, b)], gd.load_config(), final_evaluation=True,
                                    splits={**json.loads((ROOT / "configs/v4/data_splits.json").read_text()), "placeholder": False})
            rows, _ = ex.build_tables(runs)
            self.assertEqual({(r["setting"], r["lie_detection"]) for r in rows}, {("mirror", "on")})
        rp.set_active_roots({})

    def test_the_columns_are_configured_next_to_each_other(self):
        cols = [c["field"] for c in json.loads((ROOT / "configs/v4/experiments/export_csv.json").read_text())["runs"]]
        self.assertEqual(cols[cols.index("setting") + 1], "lie_detection")
        self.assertIn("lie_detection", ex.RUN_FIELDS)


def rows_as_strings(rows):
    return [{k: ex._fmt(v) for k, v in r.items()} for r in rows]


class FinalExportTests(unittest.TestCase):
    """export_csv_v4 final mode (AUDIT.md 16.15 item 5): the same gates as the final evaluation, its own run-once marker, and one combined table."""

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

    def test_the_real_repository_is_not_frozen_so_an_export_is_refused(self):
        with self.assertRaisesRegex(SystemExit, "not frozen"):
            ex.export_final("A3", [], REPO_REAL, self.out)

    def test_a_frozen_test_session_is_exported_once_with_its_own_marker(self):
        out, rows, sm = ex.export_final("A3", self.pairs(), self.repo, self.out)
        self.assertTrue(out.name.startswith("export_csv_v4_final_A3_"))
        for name in ("runs.csv", "dialogs.csv", "summary.json", "export.json", "run.json", "FINAL_EXPORT_DONE.json", "config_used/frozen.json",
                     "config_used/final_plan.json", "config_used/export_csv.json"):
            self.assertTrue((out / name).exists(), name)
        self.assertEqual(len(rows), 2)
        import csv
        with (out / "runs.csv").open(encoding="utf-8") as f:
            table = list(csv.DictReader(f))
        self.assertEqual([(r["final_setting"], r["experiment"], r["set"]) for r in table], [("A3", "A3", "A")] * 2)
        for col in ("share_within_corridor", "max_distance_from_optimal_m", "watchdog_stops", "lies_given"):
            self.assertIn(col, table[0])
        done = json.loads((out / "FINAL_EXPORT_DONE.json").read_text())
        self.assertEqual((done["setting"], done["kind"], done["runs"]), ("A3", "export", 2))
        self.assertEqual(done["frozen_sha256"], fz.sha256_lf(self.repo / fz.FROZEN_REL))
        self.assertEqual(json.loads((out / "summary.json").read_text())["summary"]["runs"], sm["runs"])
        with self.assertRaisesRegex(SystemExit, "already exported as a final"):
            ex.export_final("A3", self.pairs(name="again"), self.repo, self.out)
        other, *_ = ex.export_final("B3_off", self.pairs(name="off", setting="B3_off"), self.repo, self.out)      # another setting is free
        self.assertTrue(other.name.startswith("export_csv_v4_final_B3_off_"))
        ef.evaluate_final("A3", self.pairs(name="ev"), self.repo, self.out)               # an export does not block the evaluation ...
        with self.assertRaisesRegex(SystemExit, "already evaluated as a final"):
            ef.evaluate_final("A3", self.pairs(name="ev2"), self.repo, self.out)
        with self.assertRaisesRegex(SystemExit, "already exported as a final"):           # ... and the evaluation never lifts the export marker
            ex.export_final("A3", self.pairs(name="ex2"), self.repo, self.out)

    def test_an_evaluation_does_not_block_the_export(self):
        ef.evaluate_final("A4", self.pairs(name="ev", setting="A4"), self.repo, self.out)
        out, *_ = ex.export_final("A4", self.pairs(name="ex", setting="A4"), self.repo, self.out)
        self.assertTrue((out / "FINAL_EXPORT_DONE.json").exists())

    def test_refusals_leave_no_marker_and_read_no_test_data(self):
        f = self.repo / fz.V4_DIR / "gesture_reader.json"
        f.write_text(f.read_text() + " ")
        called = []
        real = ev.load_sessions
        ev.load_sessions = lambda *a, **k: called.append(1)
        try:
            with self.assertRaisesRegex(SystemExit, "freeze is broken"):
                ex.export_final("A3", self.pairs(), self.repo, self.out)
        finally:
            ev.load_sessions = real
        self.assertEqual(called, [])
        f.write_text(f.read_text().rstrip(" "))                                            # restored: now the data checks
        dev = [session(self.root, "dev", spec_kw={"commander_look": "sunbox_m1", "clips": {"POINT": "point_mixamo_01", "PROCEED": "proceed_ik_01"}})]
        with self.assertRaisesRegex(SystemExit, "--final-evaluation given"):
            ex.export_final("A3", dev, self.repo, self.out)
        with self.assertRaisesRegex(SystemExit, "experiment 'A3' but setting B3 is experiment B3"):
            ex.export_final("B3", self.pairs(name="wrong"), self.repo, self.out)
        with self.assertRaisesRegex(SystemExit, "the plan has 2 per setting"):
            ex.export_final("A3", self.pairs(name="three", n=3), self.repo, self.out)
        with self.assertRaisesRegex(SystemExit, "leak test has not passed"):
            ex.export_final("A3", self.pairs(name="leak", unity_leak=False), self.repo, self.out)
        for st in ("A3", "B3"):
            self.assertEqual(fg.markers(self.out, st, "export"), [])

    def test_a_crash_leaves_no_marker_and_does_not_block(self):
        real = ex.build_tables
        ex.build_tables = lambda *a, **k: (_ for _ in ()).throw(RuntimeError("boom"))
        try:
            with self.assertRaises(RuntimeError):
                ex.export_final("A3", self.pairs(), self.repo, self.out)
        finally:
            ex.build_tables = real
        self.assertEqual(fg.markers(self.out, "A3", "export"), [])
        ex.export_final("A3", self.pairs(name="retry"), self.repo, self.out)

    def test_an_unknown_or_superseded_setting_is_refused_on_the_command_line(self):
        with self.assertRaisesRegex(SystemExit, "unknown final setting 'zoom_on'"):
            ex.main(["--final", "--setting", "zoom_on", "--session", "u", "b"])
        with self.assertRaisesRegex(SystemExit, "--final needs --setting and --session"):
            ex.main(["--final", "--session", "u", "b"])
        with self.assertRaisesRegex(SystemExit, "development export"):
            ex.main(["--setting", "A3"])
        with self.assertRaisesRegex(SystemExit, "--final-combine takes only export folders"):
            ex.main(["--final-combine", "x", "--final"])

    def exported(self, *settings):
        folders = []
        for st in settings:
            out, *_ = ex.export_final(st, self.pairs(name="x_" + st, setting=st), self.repo, self.out)
            folders.append(out)
        return folders

    def test_the_combined_table_compares_the_settings_with_counts_and_intervals(self):
        folders = self.exported("A3", "B3", "B3_off", "A4")
        out, res = ex.combine(folders, self.repo, self.out)
        self.assertEqual(res["settings"], ["A3", "A4", "B3", "B3_off"])                                  # in the plan's order
        names = {(c["name"], c["metric"]) for c in res["comparisons"]}
        self.assertIn(("A vs B, scenario 3", "success"), names)
        self.assertIn(("B detection on vs off, scenario 3", "success"), names)
        unavailable = [c for c in res["comparisons"] if not c["available"]]
        self.assertTrue(unavailable and all("not available" in c["x_cell"] for c in unavailable))     # the settings not exported are said so
        row = next(c for c in res["comparisons"] if c["name"] == "A vs B, scenario 3" and c["metric"] == "success")
        sa, sb = res["per_setting"]["A3"]["summary"]["success"], res["per_setting"]["B3"]["summary"]["success"]
        self.assertEqual(row["x_cell"], ex._cell(sa))
        self.assertEqual(row["difference_pp"], round(100 * (sb["ratio"] - sa["ratio"]), 1))
        nc = ex.newcombe(sa["k"], sa["n"], sb["k"], sb["n"], res["wilson_z"])
        self.assertEqual((row["difference_lo_pp"], row["difference_hi_pp"]), (nc["lo_pp"], nc["hi_pp"]))      # the interval of the difference
        self.assertLessEqual(row["difference_lo_pp"], row["difference_pp"])
        self.assertLessEqual(row["difference_pp"], row["difference_hi_pp"])
        for name in ("combined.md", "combined.json", "combined_settings.csv", "combined_comparisons.csv", "run.json", "config_used/frozen.json"):
            self.assertTrue((out / name).exists(), name)
        md = (out / "combined.md").read_text(encoding="utf-8")
        self.assertIn("Wilson 95 %", md)
        self.assertIn("Newcombe 95 %", md)
        self.assertIn("no claim of significance", md)
        import csv
        with (out / "combined_comparisons.csv").open(encoding="utf-8") as f:
            cmp_rows = list(csv.DictReader(f))
        self.assertIn("difference_lo_pp", cmp_rows[0])
        self.assertIn("difference_hi_pp", cmp_rows[0])
        self.assertFalse(list(out.glob("FINAL_*")))                                     # derived data: no run-once marker of its own
        import time
        time.sleep(1.1)                                                                 # run folders are named by the second, never overwritten
        out2, _ = ex.combine(folders, self.repo, self.out)                              # and it can be rerun into a new folder
        self.assertNotEqual(out, out2)

    def test_the_combined_table_refuses_what_is_not_a_final_export(self):
        folders = self.exported("A3", "B3")
        with self.assertRaisesRegex(SystemExit, "not a final export folder"):
            ex.combine([self.out], self.repo, self.out)
        with self.assertRaisesRegex(SystemExit, "given twice"):
            ex.combine([folders[0], folders[0]], self.repo, self.out)
        f = self.repo / fz.V4_DIR / "gesture_reader.json"
        f.write_text(f.read_text() + " ")
        with self.assertRaisesRegex(SystemExit, "freeze is broken"):
            ex.combine(folders, self.repo, self.out)

    def test_the_combined_table_refuses_an_export_made_under_another_freeze(self):
        folders = self.exported("A3")
        rec = json.loads((folders[0] / "FINAL_EXPORT_DONE.json").read_text())
        (folders[0] / "FINAL_EXPORT_DONE.json").write_text(json.dumps({**rec, "frozen_sha256": "0" * 64}))
        with self.assertRaisesRegex(SystemExit, "another frozen.json"):
            ex.combine(folders, self.repo, self.out)


def write_messages(bridge: Path, telemetry: list, extra_lines: tuple = ()) -> None:
    """A bridge messages.jsonl: one incoming telemetry line per (watchdog_count, trial_index, trial_running), in the server's
    compact format, plus other lines that must be ignored."""
    lines = [json.dumps({"t_wall_s": 0.1 * k, "dir": "in", "type": "telemetry", "seq": k,
                         "header": {"type": "telemetry", "seq": k, "watchdog_count": c, "trial_index": t, "trial_running": run}},
                        separators=(",", ":")) for k, (c, t, run) in enumerate(telemetry)]
    (bridge / "messages.jsonl").write_text("\n".join(list(extra_lines) + lines) + "\n", encoding="utf-8")


class WatchdogStopTests(unittest.TestCase):
    """B11(a), 2026-11-13: watchdog stops are counted per run from the bridge log and reported as a result, never a refusal."""

    TELEMETRY = [(1, -1, False),                        # a stop at start-up, before trial 1: outside the runs
                 (1, 1, True), (2, 1, True), (2, 1, True),   # one stop during trial 1
                 (3, 1, False),                         # one between the runs: outside
                 (3, 2, True), (5, 2, True)]            # two during trial 2

    def test_stops_are_given_to_the_run_that_was_running(self):
        with tempfile.TemporaryDirectory() as d:
            b = Path(d)
            write_messages(b, self.TELEMETRY, extra_lines=(
                json.dumps({"dir": "out", "type": "command", "header": {"watchdog_count": 99, "trial_index": 1, "trial_running": True}}),
                json.dumps({"dir": "in", "type": "frame_360", "header": {"trial_index": 1}})))
            c = ef.bridge_watchdog_counts(b)
            self.assertEqual((c["per_trial"], c["trials_seen"], c["outside"], c["last_count"]), ({1: 1, 2: 2}, {1, 2}, 2, 5))
            self.assertIsNone(ef.bridge_watchdog_counts(b / "missing"))

    def test_per_run_block_reports_counts_and_not_evaluated_and_refuses_nothing(self):
        with tempfile.TemporaryDirectory() as d:
            b = Path(d)
            write_messages(b, self.TELEMETRY)
            runs = [ev.Run("s", t, [], [], [], True, bridge_dir=b) for t in (1, 2, 3)]
            w = ef.watchdog_block(runs)
            self.assertEqual([p["watchdog_stops"] for p in w["per_run"]], [1, 2, ev.NOT_EVALUATED])   # run 3: no telemetry
            s = w["summary"]
            self.assertEqual((s["runs"], s["runs_counted"], s["stops_in_runs"], s["runs_with_a_stop"], s["stops_outside_runs"],
                              s["reported_by_unity_total"]), (3, 2, 3, 2, 2, 5))
            self.assertIn("never a reason for invalidity", w["note"])
            md = ef.watchdog_markdown(w)
            self.assertIn("| s/run_001 | None | 1 |", md)
            self.assertIn("| s/run_003 | None | not_evaluated |", md)
            none = ef.watchdog_block([ev.Run("s", 1, [], [], [], True, bridge_dir=b / "missing")])
            self.assertEqual((none["per_run"][0]["watchdog_stops"], none["summary"]["runs_counted"]), (ev.NOT_EVALUATED, 0))

    def test_a_final_with_watchdog_stops_is_evaluated_and_reports_them_per_run(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            repo, out = final_repo(root / "r"), root / "outputs"
            out.mkdir()
            u, b = session(root, "wd")
            write_messages(b, [(0, 1, True), (1, 1, True), (1, 2, True), (1, 2, False)])
            folder, res = ef.evaluate_final("A3", [(u, b)], repo, out)
            rp.set_active_roots({})
            w = res["watchdog_stops"]
            self.assertEqual([(p["trial"], p["watchdog_stops"]) for p in w["per_run"]], [(1, 1), (2, 0)])
            self.assertTrue(all(p["outcome"] for p in w["per_run"]), "each run's outcome is reported next to its stops")
            self.assertEqual(json.loads((folder / "eval.json").read_text())["watchdog_stops"]["summary"]["stops_in_runs"], 1)
            self.assertIn("## Watchdog stops (a result, B11(a)", (folder / "eval.md").read_text(encoding="utf-8"))
            self.assertTrue((folder / "FINAL_DONE.json").exists())                      # evaluated, not refused

    def test_without_a_bridge_log_the_stops_are_not_evaluated(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            repo, out = final_repo(root / "r"), root / "outputs"
            out.mkdir()
            _, res = ef.evaluate_final("A3", [session(root, "nolog")], repo, out)
            rp.set_active_roots({})
            self.assertEqual({p["watchdog_stops"] for p in res["watchdog_stops"]["per_run"]}, {ev.NOT_EVALUATED})


if __name__ == "__main__":
    unittest.main()
