"""AUDIT.md 16.30.1: the interruption rule for the finals. A started final is never started again silently; an infrastructure interruption is
declared with evidence (final_guard_v4.declare_interruption), the session may be resumed ONCE from the interrupted run, a second interruption
makes the setting invalid, and the evaluation and the export score a resumed setting as one session (interrupted run listed, not scored)."""

import contextlib
import io
import json
import shutil
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
import hri_eval_final_v4 as ef  # noqa: E402
import run_paths as rp  # noqa: E402
import test_v4_final as tf  # noqa: E402
from bridge import server as S  # noqa: E402

SETTING = "A3"
GOALS = ["E2", "E2"]
EXTRA = {"goal_order": GOALS}


class ResumeBase(unittest.TestCase):
    """A frozen copy of the repository (2 runs per setting) and an outputs folder that holds the sessions, as the real outputs/ does."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        self.repo = tf.final_repo(self.root / "r")
        self.out = self.root / "outputs"
        self.out.mkdir()
        self.sha = fg.frozen_sha256(self.repo)
        self.evidence = self.root / "event_viewer.txt"
        self.evidence.write_text("Application Error python.exe 0xc0000005", encoding="utf-8")

    def tearDown(self):
        rp.set_active_roots({})
        self.tmp.cleanup()

    def start_marker(self, bridge: Path, sha: str | None = None, **extra) -> None:
        """What the server writes before the first trial."""
        (bridge / "FINAL_SETTING.json").write_text(json.dumps({"setting": SETTING, "frozen_sha256": sha or self.sha, **extra}), encoding="utf-8")

    def part1(self, name="p1"):
        """Part 1: run 1 finished, run 2 interrupted (no truth_run002.json, no python_trial_002.json, a half-written run_002 folder)."""
        u, b = tf.session(self.out, name, n=2, extra=EXTRA)
        (u / "truth_run002.json").unlink()
        (b / "python_trial_002.json").unlink()
        (u / "run_002" / "truth.jsonl").write_text('{"half written', encoding="utf-8")      # an incomplete file: never read
        self.start_marker(b)
        return u, b

    def part2(self, u1: Path, name="p2", seed=7, goals=None, resume_from=2, sha=None, resume_of=True, early_run=False):
        """Part 2: the resumed session, from run 2. Like Unity's, its session.json carries start_run (the run it started at) next to the
        keys of our rule, resume_from_run and resume_of (AUDIT.md 16.31.4)."""
        extra = {"goal_order": goals or GOALS, "resume_from_run": resume_from, "start_run": resume_from,
                 **({"resume_of": u1.name} if resume_of else {})}
        u, b = tf.session(self.out, name, n=2, seed=seed, extra=extra)
        (u / "truth_run001.json").unlink()
        (b / "python_trial_001.json").unlink()
        if not early_run:
            shutil.rmtree(u / "run_001")
        self.start_marker(b, sha=sha, resume_from_run=resume_from)
        return u, b

    def declare(self, u, b, run=2, **kw):
        return fg.declare_interruption(kw.pop("setting", SETTING), run, kw.pop("reason", "python.exe crashed (0xc0000005)"),
                                       kw.pop("evidence", [self.evidence]), u, b, self.out, self.repo)

    def resume(self, marker: Path, b2: Path) -> None:
        """What the server does for the declared resume: check_start, then write FINAL_RESUME.json into the new bridge folder."""
        rec = fg.check_start(self.out, SETTING, marker.parent, self.sha, self.repo)
        fg.write_resume(b2, SETTING, rec, marker.parent.name, self.sha)


class StartTests(ResumeBase):
    def test_a_fresh_setting_starts_and_nothing_can_be_resumed(self):
        self.assertIsNone(fg.check_start(self.out, SETTING, None, self.sha, self.repo))
        with self.assertRaisesRegex(SystemExit, "nothing to resume"):
            fg.check_start(self.out, SETTING, self.out, self.sha, self.repo)

    def test_a_hard_crash_leaves_no_done_marker_but_the_start_is_not_silent(self):
        _, b = tf.session(self.out, "crash", n=1)
        self.start_marker(b)                                     # FINAL_SETTING.json only: no FINAL_RUN_DONE.json
        self.assertEqual(fg.markers(self.out, SETTING, "run"), [])
        with self.assertRaisesRegex(SystemExit, "already run as a final.*declare it first.*--declare-interruption"):
            fg.check_start(self.out, SETTING, None, self.sha, self.repo)

    def test_a_clean_exit_after_unity_died_does_not_allow_a_silent_restart_either(self):
        _, b = tf.session(self.out, "clean", n=1)
        self.start_marker(b)
        fg.write_done(b, SETTING, "run", {"trials_written": 1})
        with self.assertRaisesRegex(SystemExit, "declare it first"):
            fg.check_start(self.out, SETTING, None, self.sha, self.repo)
        fg.check_start(self.out, "B3", None, self.sha, self.repo)             # another setting is free

    def test_a_declared_interruption_allows_one_resume_with_its_marker_only(self):
        u1, b1 = self.part1()
        marker = self.declare(u1, b1)
        with self.assertRaisesRegex(SystemExit, "start the resume with --resume-marker"):
            fg.check_start(self.out, SETTING, None, self.sha, self.repo)             # not silently
        for given in (marker, marker.parent):                                         # the file or its folder
            rec = fg.check_start(self.out, SETTING, given, self.sha, self.repo)
            self.assertEqual((rec["setting"], rec["resume_from_run"]), (SETTING, 2))
        with self.assertRaisesRegex(SystemExit, "is not the declaration"):
            other = self.root / "elsewhere"                                               # outside the output root: not scanned
            other.mkdir()
            fg.write_done(other, SETTING, "interruption", {"resume_from_run": 2})
            fg.check_start(self.out, SETTING, other, self.sha, self.repo)

    def test_a_resume_with_changed_frozen_hash_is_refused(self):
        u1, b1 = self.part1()
        marker = self.declare(u1, b1)
        with self.assertRaisesRegex(SystemExit, "frozen.json changed"):
            fg.check_start(self.out, SETTING, marker, "0" * 64, self.repo)

    def test_the_second_resume_is_refused(self):
        u1, b1 = self.part1()
        marker = self.declare(u1, b1)
        u2, b2 = self.part2(u1)
        self.resume(marker, b2)
        with self.assertRaisesRegex(SystemExit, "already resumed once.*second resume is never made"):
            fg.check_start(self.out, SETTING, marker, self.sha, self.repo)
        with self.assertRaisesRegex(SystemExit, "already resumed once"):
            fg.check_start(self.out, SETTING, None, self.sha, self.repo)

    def test_no_start_after_evaluation_or_export_or_invalid(self):
        u1, b1 = self.part1()
        marker = self.declare(u1, b1)
        for kind, what in (("evaluation", "evaluated"), ("export", "exported")):
            d = self.out / f"done_{kind}"
            d.mkdir()
            fg.write_done(d, SETTING, kind)
            with self.assertRaisesRegex(SystemExit, f"already {what}"):
                fg.check_start(self.out, SETTING, marker, self.sha, self.repo)
            with self.assertRaisesRegex(SystemExit, f"already {what}"):
                self.declare(u1, b1)
            shutil.rmtree(d)
        d = self.out / "inv"
        d.mkdir()
        fg.write_done(d, SETTING, "invalid", {"reason": "x"})
        with self.assertRaisesRegex(SystemExit, "declared invalid"):
            fg.check_start(self.out, SETTING, marker, self.sha, self.repo)

    def test_the_server_preflight_uses_the_guard(self):
        fz.require_frozen, real = (lambda *a, **k: {}), fz.require_frozen
        try:
            cfg, _ = S.load_config("configs/v4/bridge.json")
            cfg = {**cfg, "paths": {"output_root": str(self.out)}}
            control = "configs/v4/experiments/control_lie_on.json"
            self.assertIsNone(S.preflight_final(cfg, "guide", SETTING, control))
            u1, b1 = self.part1()
            # the repository's own frozen.json is what the server hashes; declare with it
            real_frozen = fg.frozen_sha256(fz.REPO)
            self.start_marker(b1, sha=real_frozen)
            marker = fg.declare_interruption(SETTING, 2, "python.exe crashed", [self.evidence], u1, b1, self.out, fz.REPO)
            with self.assertRaisesRegex(SystemExit, "start the resume with --resume-marker"):
                S.preflight_final(cfg, "guide", SETTING, control)
            rec = S.preflight_final(cfg, "guide", SETTING, control, marker.parent)
            self.assertEqual(rec["resume_from_run"], 2)
            with self.assertRaisesRegex(SystemExit, "must run with --control-config"):       # the other checks still apply to a resume
                S.preflight_final(cfg, "guide", SETTING, "configs/v4/control.json", marker.parent)
        finally:
            fz.require_frozen = real


class ServerOptionTests(unittest.IsolatedAsyncioTestCase):
    async def test_resume_marker_without_final_setting_is_refused(self):
        cfg, path = S.load_config("configs/v4/bridge.json")
        with self.assertRaisesRegex(SystemExit, "--resume-marker belongs to --final-setting"):
            await S.run(cfg, path, "guide", None, resume_marker="x")


class DeclareTests(ResumeBase):
    def test_the_declaration_records_what_the_rule_asks(self):
        u1, b1 = self.part1()
        marker = self.declare(u1, b1)
        self.assertTrue(marker.parent.name.startswith("final_interruption_A3_"))
        rec = json.loads(marker.read_text(encoding="utf-8"))
        self.assertEqual((rec["setting"], rec["kind"], rec["resume_from_run"], rec["interrupted_run"]), (SETTING, "interruption", 2, 2))
        self.assertEqual(rec["outcome_of_interrupted_run"], "interrupted (infrastructure)")
        self.assertEqual((rec["seed"], rec["goal_order"], rec["completed_runs"]), (7, GOALS, [1]))
        self.assertEqual((rec["unity_folder"], rec["bridge_folder"], rec["frozen_sha256"]), (u1.name, b1.name, self.sha))
        self.assertIn("0xc0000005", rec["reason"])
        ev = rec["evidence"][0]                                                        # the evidence file with its SHA-256
        self.assertEqual(len(ev["sha256"]), 64)
        self.assertIn("event_viewer.txt", ev["path"])
        with self.assertRaisesRegex(SystemExit, "already declared"):                   # one declaration per setting
            self.declare(u1, b1)

    def test_refusals(self):
        u1, b1 = self.part1()
        with self.assertRaisesRegex(SystemExit, "--reason is required"):
            self.declare(u1, b1, reason=" ")
        with self.assertRaisesRegex(SystemExit, "evidence is empty|evidence .* not found"):
            self.declare(u1, b1, evidence=[self.root / "no_such_file"])
        empty = self.root / "empty_folder"
        empty.mkdir()
        with self.assertRaisesRegex(SystemExit, "the evidence is empty"):
            self.declare(u1, b1, evidence=[empty])
        with self.assertRaisesRegex(SystemExit, "runs 1 to 2"):
            self.declare(u1, b1, run=3)
        with self.assertRaisesRegex(SystemExit, "needs exactly runs 1 to 0"):          # run 1 HAS an outcome: a result, not an interruption
            self.declare(u1, b1, run=1)
        self.assertEqual(fg.markers(self.out, SETTING, "interruption"), [])

    def test_a_run_with_an_outcome_is_not_an_interruption(self):
        u, b = tf.session(self.out, "done", n=2, extra=EXTRA)                          # both runs finished
        self.start_marker(b)
        with self.assertRaisesRegex(SystemExit, "a result, not an interruption"):
            self.declare(u, b, run=2)

    def test_nothing_started_nothing_to_declare(self):
        with self.assertRaisesRegex(SystemExit, "no final of 'A3' was started"):
            fg.declare_interruption(SETTING, 2, "x", [self.evidence], self.out, self.out, self.out, self.repo)

    def test_the_folders_must_be_the_started_final(self):
        u1, b1 = self.part1()
        u9, b9 = tf.session(self.out, "other", n=2, extra=EXTRA)                        # a bridge folder with no start marker
        with self.assertRaisesRegex(SystemExit, "must be the one bridge run folder"):
            self.declare(u1, b9)
        self.start_marker(b9)
        with self.assertRaisesRegex(SystemExit, "must be the one bridge run folder"):   # two started finals, no declaration yet
            self.declare(u1, b1)
        with self.assertRaisesRegex(SystemExit, "not a bridge run folder of the final"):  # the part check itself, for a folder with the wrong setting
            fg._check_part("B3", u1, b1, 1, 2)

    def test_a_completed_run_without_python_output_is_not_declared(self):
        u1, b1 = self.part1()
        (b1 / "python_trial_001.json").unlink()
        with self.assertRaisesRegex(SystemExit, "no python_trial file"):
            self.declare(u1, b1)

    def test_a_session_without_seed_or_goal_order_cannot_be_checked_later(self):
        u, b = tf.session(self.out, "noseed", n=2)                                      # no goal_order in session.json
        (u / "truth_run002.json").unlink()
        (b / "python_trial_002.json").unlink()
        self.start_marker(b)
        with self.assertRaisesRegex(SystemExit, "has no goal_order"):
            self.declare(u, b)

    def test_changed_frozen_hash_since_the_start_is_refused(self):
        u1, b1 = self.part1()
        self.start_marker(b1, sha="1" * 64)
        with self.assertRaisesRegex(SystemExit, "frozen.json changed since this run started"):
            self.declare(u1, b1)

    def test_a_second_interruption_makes_the_setting_invalid(self):
        u1, b1 = self.part1()
        marker = self.declare(u1, b1)
        u2, b2 = self.part2(u1)
        (u2 / "truth_run002.json").unlink()                                              # the resumed part died in run 2 as well
        (b2 / "python_trial_002.json").unlink()
        self.resume(marker, b2)
        inv = self.declare(u2, b2, run=2, reason="Unity crashed again")
        self.assertEqual(inv.name, fg.MARKERS["invalid"])
        self.assertTrue(inv.parent.name.startswith("final_invalid_A3_"))
        rec = json.loads(inv.read_text(encoding="utf-8"))
        self.assertIn("second interruption", rec["rule"])
        self.assertEqual((rec["first_interruption"], rec["resume_folder"]), (marker.parent.name, b2.name))
        for call in (lambda: fg.check_start(self.out, SETTING, marker, self.sha, self.repo), lambda: self.declare(u2, b2, run=2)):
            with self.assertRaisesRegex(SystemExit, "declared invalid"):
                call()
        with self.assertRaisesRegex(SystemExit, "declared invalid"):                    # nor evaluated, nor exported
            ef.evaluate_final(SETTING, [(u1, b1), (u2, b2)], self.repo, self.out)
        with self.assertRaisesRegex(SystemExit, "declared invalid"):
            ex.export_final(SETTING, [(u1, b1), (u2, b2)], self.repo, self.out)
        row = next(r for r in fg.status(self.out, self.repo) if r["setting"] == SETTING)
        self.assertEqual(row["state"], "invalid")

    def test_a_second_interruption_must_name_the_resumed_folder(self):
        u1, b1 = self.part1()
        marker = self.declare(u1, b1)
        u2, b2 = self.part2(u1)
        self.resume(marker, b2)
        with self.assertRaisesRegex(SystemExit, "must be the resumed run's folder"):
            self.declare(u1, b1, run=2)


class EvaluationTests(ResumeBase):
    def resumed(self):
        u1, b1 = self.part1()
        marker = self.declare(u1, b1)
        u2, b2 = self.part2(u1)
        self.resume(marker, b2)
        return (u1, b1), (u2, b2), marker

    def test_a_resumed_setting_is_evaluated_as_one_session(self):
        p1, p2, marker = self.resumed()
        out, res = ef.evaluate_final(SETTING, [p1, p2], self.repo, self.out)
        self.assertEqual(res["experiment"]["summary"]["runs"], 2)
        self.assertEqual(sorted(r["trial"] for r in res["experiment"]["runs_table"]) if "trial" in res["experiment"]["runs_table"][0]
                         else [1, 2], [1, 2])
        rep = res["interruption"]
        self.assertEqual((rep["interrupted_run"], rep["outcome_of_interrupted_run"], rep["scored_as_one_session"]), (2, "interrupted (infrastructure)", True))
        self.assertEqual(rep["interrupted_runs_listed_not_scored"], [{"unity": p1[0].name, "run": 2}])
        md = (out / "eval.md").read_text(encoding="utf-8")
        self.assertIn("Interruption and resume", md)
        self.assertIn("interrupted (infrastructure)", md)
        self.assertIn("event_viewer.txt", md)
        self.assertTrue((out / "FINAL_DONE.json").exists())
        with self.assertRaisesRegex(SystemExit, "already evaluated"):
            ef.evaluate_final(SETTING, [p1, p2], self.repo, self.out)

    def test_the_order_of_the_two_parts_does_not_matter_and_the_export_scores_one_session(self):
        p1, p2, _ = self.resumed()
        out, rows, sm = ex.export_final(SETTING, [p2, p1], self.repo, self.out)
        self.assertEqual((len(rows), sm["runs"]), (2, 2))
        s = json.loads((out / "summary.json").read_text(encoding="utf-8"))
        self.assertEqual(s["interruption"]["interrupted_run"], 2)
        self.assertTrue((out / "FINAL_EXPORT_DONE.json").exists())
        ef.evaluate_final(SETTING, [p1, p2], self.repo, self.out)                          # the export does not block the evaluation

    def test_an_uninterrupted_setting_reports_no_interruption(self):
        u, b = tf.session(self.out, "plain", n=2, extra=EXTRA)
        self.start_marker(b)
        out, res = ef.evaluate_final(SETTING, [(u, b)], self.repo, self.out)
        self.assertIsNone(res["interruption"])
        self.assertNotIn("Interruption and resume", (out / "eval.md").read_text(encoding="utf-8"))

    def test_the_interrupted_run_is_never_scored_or_read(self):
        p1, p2, _ = self.resumed()
        plan = fg.resume_plan(self.out, SETTING, [p1, p2], self.repo)
        self.assertEqual(plan["problems"], [])
        self.assertTrue(plan["include"](p1[0], 1) and not plan["include"](p1[0], 2))
        self.assertTrue(plan["include"](p2[0], 2) and not plan["include"](p2[0], 1))
        # the half-written truth.jsonl of the interrupted run (part 1, run 2) would have raised if it had been read: the evaluation works
        ef.evaluate_final(SETTING, [p1, p2], self.repo, self.out)

    def refused(self, pairs, pattern):
        with self.assertRaisesRegex(SystemExit, pattern):
            ef.evaluate_final(SETTING, pairs, self.repo, self.out)
        self.assertEqual(fg.markers(self.out, SETTING, "evaluation"), [])

    def test_one_part_only_is_refused(self):
        p1, p2, _ = self.resumed()
        self.refused([p1], "TWO session parts")
        self.refused([p2], "TWO session parts")

    def test_a_declared_interruption_that_was_never_resumed_is_refused(self):
        u1, b1 = self.part1()
        self.declare(u1, b1)
        self.refused([(u1, b1)], "never resumed: a partial session is not scored")

    def test_a_resumed_run_without_a_declaration_is_refused(self):
        u1, b1 = self.part1()
        u2, b2 = self.part2(u1)
        fg.write_done(b2, SETTING, "resume", {"resume_from_run": 2})
        self.refused([(u1, b1), (u2, b2)], "without a declared interruption")

    def test_a_different_seed_is_refused(self):
        p1, _, _ = self.resumed()
        s = json.loads((self.out / "trials_p2" / "session.json").read_text())
        s["seed"] = 8
        (self.out / "trials_p2" / "session.json").write_text(json.dumps(s))
        self.refused([p1, (self.out / "trials_p2", self.out / "bridge_p2")], "the seed differs")

    def test_a_different_goal_order_is_refused(self):
        p1, _, _ = self.resumed()
        s = json.loads((self.out / "trials_p2" / "session.json").read_text())
        s["goal_order"] = ["E1", "E2"]
        (self.out / "trials_p2" / "session.json").write_text(json.dumps(s))
        self.refused([p1, (self.out / "trials_p2", self.out / "bridge_p2")], "goal order differs")

    def test_a_part_two_that_does_not_say_it_resumed_is_refused(self):
        p1, _, _ = self.resumed()
        for key, pattern in (("resume_from_run", "records resume_from_run None"), ("resume_of", "records resume_of None")):
            f = self.out / "trials_p2" / "session.json"
            s = json.loads(f.read_text())
            keep = s.pop(key)
            f.write_text(json.dumps(s))
            self.refused([p1, (self.out / "trials_p2", self.out / "bridge_p2")], pattern)
            s[key] = keep
            f.write_text(json.dumps(s))

    def edit_part2(self, **changes):
        """Rewrite keys of part 2's session.json (a value of None removes the key); returns the two parts."""
        p1, _, _ = self.resumed()
        f = self.out / "trials_p2" / "session.json"
        sj = json.loads(f.read_text())
        for k, v in changes.items():
            if v is None:
                sj.pop(k, None)
            else:
                sj[k] = v
        f.write_text(json.dumps(sj))
        return [p1, (self.out / "trials_p2", self.out / "bridge_p2")]

    def test_a_resumed_final_needs_start_run_equal_to_resume_from_run(self):
        """AUDIT.md 16.31.4: both keys are required and must agree (and equal the declaration's k); neither is an alias of the other."""
        for change, pattern in (({"start_run": None}, "records start_run None: a resumed final needs the whole number"),
                                ({"start_run": 1}, r"start_run 1 but resume_from_run 2: a resumed final must have start_run == resume_from_run"),
                                ({"start_run": 3}, r"start_run 3 but resume_from_run 2"),
                                ({"start_run": "2"}, "records start_run '2'"),
                                ({"start_run": True}, "records start_run True"),
                                ({"start_run": 2.0}, "records start_run 2.0"),
                                ({"resume_from_run": None}, "records resume_from_run None"),                 # start_run alone is refused
                                ({"resume_from_run": 3}, r"start_run 2 but resume_from_run 3")):             # and so is a mismatch the other way
            with self.subTest(change=change):
                tmp = self.__class__()                                                                    # a fresh fixture per case
                tmp.setUp()
                try:
                    pairs = tmp.edit_part2(**change)
                    tmp.refused(pairs, pattern)
                finally:
                    tmp.tearDown()

    def test_start_run_equal_to_k_is_accepted_and_part_one_is_not_checked_for_it(self):
        p1, p2, _ = self.resumed()
        s1 = json.loads((p1[0] / "session.json").read_text())
        self.assertNotIn("start_run", s1)                                                                  # part 1 has none here: it is not checked
        ef.evaluate_final(SETTING, [p1, p2], self.repo, self.out)

    def test_changed_frozen_hash_between_the_parts_is_refused(self):
        p1, p2, _ = self.resumed()
        self.start_marker(p2[1], sha="2" * 64, resume_from_run=2)
        self.refused([p1, p2], "frozen hashes differ")

    def test_a_resumed_session_that_starts_before_the_resume_point_is_refused(self):
        u1, b1 = self.part1()
        marker = self.declare(u1, b1)
        u2, b2 = self.part2(u1, early_run=True)                                            # run_001 is also in part 2
        self.resume(marker, b2)
        self.refused([(u1, b1), (u2, b2)], "before the resume point 2")

    def test_the_wrong_part_one_is_refused(self):
        p1, p2, _ = self.resumed()
        u3, b3 = tf.session(self.out, "p3", n=2, extra=EXTRA)
        self.refused([(u3, b3), p2], "the parts must be")


class ResumeInfoTests(ResumeBase):
    """AUDIT.md 16.31.2 item 3: what the launcher asks before it passes -StartRun k and --resume-marker."""

    def test_the_declaration_gives_the_run_the_marker_and_the_seed_and_goal_order(self):
        u1, b1 = self.part1()
        marker = self.declare(u1, b1)
        info = fg.resume_info(self.out, SETTING, self.repo)
        self.assertEqual((info["resume_from_run"], info["resume_marker"], info["seed"], info["goal_order"]), (2, marker.parent.name, 7, GOALS))
        self.assertEqual((info["part_1"], info["frozen_sha256"]), ({"unity": u1.name, "bridge": b1.name}, self.sha))
        rec = fg.check_start(self.out, SETTING, info["resume_marker"] and self.out / info["resume_marker"], self.sha, self.repo)
        self.assertEqual(rec["resume_from_run"], info["resume_from_run"])                 # the server accepts exactly what the info names

    def test_refusals_with_the_reason(self):
        with self.assertRaisesRegex(SystemExit, "no final was started"):
            fg.resume_info(self.out, SETTING, self.repo)
        u1, b1 = self.part1()
        with self.assertRaisesRegex(SystemExit, "no interruption is declared"):
            fg.resume_info(self.out, SETTING, self.repo)
        marker = self.declare(u1, b1)
        u2, b2 = self.part2(u1)
        self.resume(marker, b2)
        with self.assertRaisesRegex(SystemExit, "already resumed once"):
            fg.resume_info(self.out, SETTING, self.repo)
        d = self.out / "ev"
        d.mkdir()
        fg.write_done(d, SETTING, "evaluation")
        with self.assertRaisesRegex(SystemExit, "already evaluated"):
            fg.resume_info(self.out, SETTING, self.repo)
        with self.assertRaisesRegex(SystemExit, "unknown final setting"):
            fg.resume_info(self.out, "nonsense", self.repo)

    def test_an_invalid_setting_has_no_resume(self):
        d = self.out / "inv"
        d.mkdir()
        fg.write_done(d, SETTING, "invalid", {"reason": "x"})
        with self.assertRaisesRegex(SystemExit, "declared invalid"):
            fg.resume_info(self.out, SETTING, self.repo)

    def test_the_command_line_prints_json(self):
        u1, b1 = self.part1()
        self.declare(u1, b1)
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            self.assertEqual(fg.main(["--resume-info", SETTING, "--output-root", str(self.out)]), 0)
        self.assertEqual(json.loads(buf.getvalue())["resume_from_run"], 2)
        with contextlib.redirect_stderr(io.StringIO()), self.assertRaises(SystemExit) as c:
            fg.main(["--resume-info", SETTING, "--status"])
        self.assertEqual(c.exception.code, 2)


class StatusTests(ResumeBase):
    def test_status_lists_every_setting_and_its_state(self):
        rows = {r["setting"]: r for r in fg.status(self.out, self.repo)}
        self.assertEqual(set(rows), set(fg.settings(self.repo)))
        self.assertTrue(all(r["state"] == "fresh" for r in rows.values()))
        u1, b1 = self.part1()
        self.assertEqual(fg.status(self.out, self.repo)[fg.settings(self.repo).index(SETTING)]["state"], "started (no declaration)")
        marker = self.declare(u1, b1)
        row = next(r for r in fg.status(self.out, self.repo) if r["setting"] == SETTING)
        self.assertEqual((row["state"], row["interruption"]["run"]), ("interrupted (declared, not resumed)", 2))
        u2, b2 = self.part2(u1)
        self.resume(marker, b2)
        row = next(r for r in fg.status(self.out, self.repo) if r["setting"] == SETTING)
        self.assertEqual(row["state"], "resumed")
        text = fg.status_text(fg.status(self.out, self.repo))
        self.assertIn("interrupted run 2", text)
        self.assertIn("resumed in", text)

    def test_the_command_line(self):
        u1, b1 = self.part1()
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            self.assertEqual(fg.main(["--status", "--output-root", str(self.out)]), 0)
        self.assertIn("started (no declaration)", buf.getvalue())
        with contextlib.redirect_stderr(io.StringIO()), self.assertRaises(SystemExit) as c:       # a declaration needs all of its arguments
            fg.main(["--declare-interruption", SETTING, "--output-root", str(self.out)])
        self.assertEqual(c.exception.code, 2)
        with contextlib.redirect_stderr(io.StringIO()), self.assertRaises(SystemExit) as c:       # one mode at a time
            fg.main(["--status", "--timeout-from", "x"])
        self.assertEqual(c.exception.code, 2)


if __name__ == "__main__":
    unittest.main()
