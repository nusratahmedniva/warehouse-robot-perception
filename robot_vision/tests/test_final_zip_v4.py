"""AUDIT.md 16.30.2: final_zip_v4.py packs ONE zip per final sitting and one for the avatar experiment, with the SHA-256 next to it, from synthetic
sessions; it refuses what is missing or unexpected, never writes inside the repository or over a file, and verify reads the zip in place."""

import contextlib
import io
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
import test_final_resume_v4 as tr  # noqa: E402
import test_v4_final as tf  # noqa: E402


class ZipBase(tr.ResumeBase):
    def setUp(self):
        super().setUp()
        self.zips = self.root / "zips"                                   # outside the repository (a temp folder)

    def final(self, setting: str, stamp: str = "20261121_100000", logs: bool = True, protocol: bool = True):
        """One synthetic final setting in the output root, named as the launcher names its files."""
        u, b = tf.session(self.out, f"final_Task2_{setting}_{stamp}", n=2, setting=setting, extra=tr.EXTRA)
        (b / "FINAL_SETTING.json").write_text(json.dumps({"setting": setting, "frozen_sha256": self.sha}), encoding="utf-8")
        (b / "summary.json").write_text("{}", encoding="utf-8")
        (b / "stop_reading.jsonl").write_text('{"applies": false}\n', encoding="utf-8")
        if logs:
            for suffix in ("server.log", "server.err.log", "unity.log"):
                (self.out / f"run_session_final_{setting}_{stamp}_{suffix}").write_text(f"{setting} {suffix}", encoding="utf-8")
        if protocol:
            (self.out / f"run_protocol_final_{setting}_{stamp}.txt").write_text(f"{setting} protocol", encoding="utf-8")
        return u, b

    def power(self) -> Path:
        p = self.root / "power_mode.txt"
        p.write_text("power mode: Best performance, 10:00", encoding="utf-8")
        return p

    def names(self, zp: Path) -> list[str]:
        with zipfile.ZipFile(zp) as z:
            return z.namelist()


class SittingTests(ZipBase):
    def test_one_zip_per_sitting_with_its_checksum_and_everything_of_the_settings(self):
        self.final("B3")
        self.final("B3_off")                                             # B3 and its OFF partner: one sitting, the logs of B3 are not B3_off's
        self.final("B4")
        res = fzip.make_sitting_zip(2, ["B3", "B3_off"], self.zips, [self.power()], self.out, stamp="20261121_120000")
        zp = res["zip"]
        self.assertEqual(zp.name, "final_sitting2_20261121_120000.zip")
        side = zp.parent / (zp.name + ".sha256")
        self.assertEqual(side.read_text(encoding="utf-8"), f"{res['sha256']}  {zp.name}\n")
        names = self.names(zp)
        for n in ("B3/trials_final_Task2_B3_20261121_100000/session.json", "B3/bridge_final_Task2_B3_20261121_100000/stop_reading.jsonl",
                  "B3/bridge_final_Task2_B3_20261121_100000/FINAL_SETTING.json", "B3/launcher/run_session_final_B3_20261121_100000_server.log",
                  "B3/launcher/run_protocol_final_B3_20261121_100000.txt", "B3_off/trials_final_Task2_B3_off_20261121_100000/session.json",
                  "B3_off/launcher/run_session_final_B3_off_20261121_100000_unity.log", "extra/power_mode.txt", "MANIFEST.json", "final_zip_v4.py"):
            self.assertIn(n, names)
        self.assertFalse([n for n in names if n.startswith("B3/") and "B3_off" in n])      # B3 holds nothing of B3_off
        self.assertFalse([n for n in names if n.startswith("B4")])                    # nor of a setting of another sitting
        meta = json.loads(zipfile.ZipFile(zp).read("MANIFEST.json"))
        self.assertEqual((meta["sitting"], [s["setting"] for s in meta["settings"]], meta["warnings"]), (2, ["B3", "B3_off"], []))
        self.assertEqual(fzip.verify_zip(zp), [])
        self.assertTrue(all(len(f["sha256"]) == 64 for f in meta["files"]))

    def test_the_cli_prints_the_path_and_the_sha256(self):
        self.final("A3")
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            code = fzip.main(["sitting", "--number", "4", "--settings", "A3", "--out-dir", str(self.zips), "--extra", str(self.power()),
                              "--output-root", str(self.out)])
        self.assertEqual(code, 0)
        self.assertIn("final_sitting4_", buf.getvalue())
        self.assertIn("SHA-256", buf.getvalue())

    def test_a_setting_without_its_session_is_refused_and_nothing_is_written(self):
        self.final("A3")
        with self.assertRaisesRegex(SystemExit, "(?s)B3: no Unity session folder.*B3: no bridge run folder"):
            fzip.make_sitting_zip(1, ["A3", "B3"], self.zips, [self.power()], self.out)
        self.assertFalse(self.zips.exists() and list(self.zips.iterdir()))

    def test_a_second_start_without_a_declaration_is_refused(self):
        self.final("A3")
        self.final("A3", stamp="20261121_110000")
        with self.assertRaisesRegex(SystemExit, "2 bridge run folders, expected 1"):
            fzip.make_sitting_zip(1, ["A3"], self.zips, [self.power()], self.out)

    def test_missing_logs_notes_and_extras_are_reported_not_hidden(self):
        self.final("A3", logs=False, protocol=False)
        (self.out / "bridge_final_Task2_A3_20261121_100000" / "summary.json").unlink()
        res = fzip.make_sitting_zip(1, ["A3"], self.zips, None, self.out)
        text = " | ".join(res["warnings"])
        for part in ("no launcher logs", "no run-protocol note", "no summary.json", "power-mode"):
            self.assertIn(part, text)
        meta = json.loads(zipfile.ZipFile(res["zip"]).read("MANIFEST.json"))
        self.assertEqual(meta["warnings"], res["warnings"])

    def test_an_interrupted_and_resumed_setting_packs_both_parts_and_the_declaration(self):
        u1, b1 = self.part1("final_Task2_A3_20261121_100000")
        marker = self.declare(u1, b1)                                    # declared before the resumed session exists, as in real life
        u2, b2 = self.part2(u1, "final_Task2_A3_20261121_110000")
        self.resume(marker, b2)
        res = fzip.make_sitting_zip(1, ["A3"], self.zips, [self.power(), self.evidence], self.out)
        names = self.names(res["zip"])
        for n in ("A3/trials_final_Task2_A3_20261121_100000/session.json", "A3/trials_final_Task2_A3_20261121_110000/session.json",
                  "A3/bridge_final_Task2_A3_20261121_110000/FINAL_RESUME.json", f"A3/{marker.parent.name}/FINAL_INTERRUPTION.json",
                  "extra/event_viewer.txt"):
            self.assertIn(n, names)
        meta = json.loads(zipfile.ZipFile(res["zip"]).read("MANIFEST.json"))["settings"][0]
        self.assertEqual((len(meta["unity"]), len(meta["bridge"]), meta["interruption"] != [], meta["resume"] != []), (2, 2, True, True))

    def test_a_declared_interruption_not_yet_resumed_packs_part_one_only(self):
        u1, b1 = self.part1("final_Task2_A3_20261121_100000")
        self.declare(u1, b1)
        res = fzip.make_sitting_zip(1, ["A3"], self.zips, [self.power()], self.out)
        self.assertEqual(fzip.verify_zip(res["zip"]), [])

    def test_the_inputs_are_not_changed(self):
        self.final("A3")
        before = sorted((str(p.relative_to(self.out)), p.stat().st_size) for p in self.out.rglob("*") if p.is_file())
        fzip.make_sitting_zip(1, ["A3"], self.zips, [self.power()], self.out)
        after = sorted((str(p.relative_to(self.out)), p.stat().st_size) for p in self.out.rglob("*") if p.is_file())
        self.assertEqual(before, after)

    def test_the_out_dir_must_be_absolute_outside_the_repository_and_never_overwritten(self):
        self.final("A3")
        with self.assertRaisesRegex(SystemExit, "absolute"):
            fzip.make_sitting_zip(1, ["A3"], "zips_here", [self.power()], self.out)
        with self.assertRaisesRegex(SystemExit, "inside the repository"):
            fzip.make_sitting_zip(1, ["A3"], fzip.REPO / "results" / "zips", [self.power()], self.out)
        fzip.make_sitting_zip(1, ["A3"], self.zips, [self.power()], self.out, stamp="20261121_130000")
        with self.assertRaisesRegex(SystemExit, "exists; not overwritten"):
            fzip.make_sitting_zip(1, ["A3"], self.zips, [self.power()], self.out, stamp="20261121_130000")

    def test_bad_arguments(self):
        self.final("A3")
        with self.assertRaisesRegex(SystemExit, "a sitting is 1 to 4"):
            fzip.make_sitting_zip(5, ["A3"], self.zips, None, self.out)
        with self.assertRaisesRegex(SystemExit, "each once"):
            fzip.make_sitting_zip(1, ["A3", "A3"], self.zips, None, self.out)
        with self.assertRaisesRegex(SystemExit, "unknown final setting"):
            fzip.make_sitting_zip(1, ["nonsense"], self.zips, None, self.out)
        with self.assertRaisesRegex(SystemExit, "--extra .*: not found"):
            fzip.make_sitting_zip(1, ["A3"], self.zips, [self.root / "nothing.png"], self.out)


class AvatarTests(ZipBase):
    def test_one_avatar_zip_of_the_named_folders(self):
        a = self.root / "avatar_session_1"
        (a / "sub").mkdir(parents=True)
        (a / "sub" / "report.json").write_text("{}", encoding="utf-8")
        (a / "note.txt").write_text("looks", encoding="utf-8")
        res = fzip.make_avatar_zip([a], self.zips, [self.power()], stamp="20261121_140000")
        self.assertEqual(res["zip"].name, "avatar_experiment_20261121_140000.zip")
        names = self.names(res["zip"])
        for n in ("avatar/avatar_session_1/sub/report.json", "avatar/avatar_session_1/note.txt", "extra/power_mode.txt", "MANIFEST.json"):
            self.assertIn(n, names)
        self.assertTrue((self.zips / (res["zip"].name + ".sha256")).is_file())
        self.assertEqual(fzip.verify_zip(res["zip"]), [])
        with self.assertRaisesRegex(SystemExit, "not found"):
            fzip.make_avatar_zip([self.root / "missing"], self.zips)
        with self.assertRaisesRegex(SystemExit, "name the folders"):
            fzip.make_avatar_zip([], self.zips)


class VerifyTests(ZipBase):
    def make(self):
        self.final("A3")
        return fzip.make_sitting_zip(1, ["A3"], self.zips, [self.power()], self.out)["zip"]

    def test_a_changed_checksum_file_is_found(self):
        zp = self.make()
        (zp.parent / (zp.name + ".sha256")).write_text("0" * 64 + f"  {zp.name}\n", encoding="utf-8")
        self.assertTrue(any("SHA-256 differs" in p for p in fzip.verify_zip(zp)))

    def test_a_changed_member_is_found_by_the_manifest(self):
        zp = self.make()
        tampered = zp.parent / "tampered.zip"
        with zipfile.ZipFile(zp) as src, zipfile.ZipFile(tampered, "w") as dst:
            for info in src.infolist():
                data = src.read(info.filename)
                dst.writestr(info.filename, data + b"x" if info.filename.endswith("stop_reading.jsonl") else data)
        shutil.copy(zp.parent / (zp.name + ".sha256"), zp.parent / "tampered.zip.sha256")
        problems = fzip.verify_zip(tampered)
        self.assertTrue(any("stop_reading.jsonl: differs from MANIFEST.json" in p for p in problems), problems)

    def test_the_command_line_verifies_in_place(self):
        zp = self.make()
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            self.assertEqual(fzip.main(["verify", str(zp)]), 0)
        self.assertIn("nothing extracted", buf.getvalue())


if __name__ == "__main__":
    unittest.main()
