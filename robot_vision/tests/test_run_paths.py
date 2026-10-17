"""Tests for run_paths.py and migrate_run_paths.py. Run from robot_vision/:  python -m unittest discover -s tests -v"""

import json
import re
import shutil
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import migrate_run_paths as mig  # noqa: E402
import run_paths as rp  # noqa: E402

ABS_RE = re.compile(r"(?<![A-Za-z0-9])[A-Za-z]:[\\/](?!/)")
OLD = {"dataset_root": r"D:\OldData\RGB-D", "output_root": r"E:\Old\robot_vision\outputs", "project_root": r"E:\Old\robot_vision"}


class StoreResolveTests(unittest.TestCase):
    def test_windows_paths_become_tokens_on_any_os(self):
        rts = {k: v for k, v in OLD.items()}
        self.assertEqual(rp.relative_token(r"D:\OldData\RGB-D\Synthetic_Scenes\RGB\rgb_2.png", rts),
                         "{dataset_root}/Synthetic_Scenes/RGB/rgb_2.png")
        self.assertEqual(rp.relative_token(r"e:\old\robot_vision\outputs\seg_x", rts), "{output_root}/seg_x")
        self.assertEqual(rp.relative_token(r"E:\Old\robot_vision\configs\office.json", rts),
                         "{project_root}/configs/office.json")
        self.assertIsNone(rp.relative_token(r"C:\Users\someone\cache.bin", rts))

    def test_resolve_under_new_roots(self):
        with tempfile.TemporaryDirectory() as d:
            rts = rp.make_roots(Path(d) / "data", Path(d) / "out")
            self.assertEqual(rp.resolve("{dataset_root}/a/b.png", rts), Path(d) / "data" / "a" / "b.png")
            self.assertEqual(rp.resolve("{output_root}", rts), Path(d) / "out")
            with self.assertRaises(FileNotFoundError):
                rp.resolve(r"Q:\missing\file.png", rts)

    def test_writer_never_emits_absolute_paths(self):
        rts = {k: v for k, v in OLD.items()}
        out = rp.portable({"a": r"D:\OldData\RGB-D\x.png", "b": r"C:\Users\n\.cache\m.bin", "c": "https://x.org/y",
                           "d": "/Users/n/data/z.png", "e": [r"cmd E:\Old\robot_vision\configs\c.json --x"]}, rts)
        text = json.dumps(out)
        self.assertIsNone(ABS_RE.search(text), text)
        self.assertEqual(out["a"], "{dataset_root}/x.png")
        self.assertEqual(out["b"], "<outside configured roots>/m.bin")
        self.assertEqual(out["c"], "https://x.org/y")
        self.assertEqual(out["d"], "<outside configured roots>/z.png")
        self.assertEqual(out["e"], ["cmd {project_root}/configs/c.json --x"])


class MigrationTests(unittest.TestCase):
    def make_legacy_run(self, base: Path) -> Path:
        run = base / "track_2f_legacy"
        run.mkdir(parents=True)
        frames = [{"step": s, "rgb_path": OLD["dataset_root"] + rf"\Synthetic_Scenes\Office\dynamic\Capture_1\RGB\rgb_{s + 2}.png",
                   "segmentation_mask": OLD["output_root"] + rf"\seg_run\pred_grouped\step_{s:06d}.png"} for s in (0, 1)]
        (run / "frames.jsonl").write_text("".join(json.dumps(f) + "\n" for f in frames), encoding="utf-8")
        (run / "tracking_summary.json").write_text(json.dumps(
            {"segmentation_run": OLD["output_root"] + r"\seg_run", "note": "see https://ultralytics.com/license"},
            indent=2), encoding="utf-8")
        (run / "preview.png").write_bytes(b"\x89PNG not text")
        return run

    def test_migrate_then_load_under_a_different_dataset_root(self):
        with tempfile.TemporaryDirectory() as d:
            d = Path(d)
            run = self.make_legacy_run(d / "old_outputs")
            original = (run / "frames.jsonl").read_text(encoding="utf-8")
            log = mig.migrate_run(run, dict(OLD), dry_run=False)
            self.assertEqual(sorted(log["files_changed"]), ["frames.jsonl", "tracking_summary.json"])
            self.assertEqual(log["unmapped_absolute_paths"], {})
            # originals kept byte-for-byte; binary file untouched
            self.assertEqual((run / mig.BACKUP_DIR / "frames.jsonl").read_text(encoding="utf-8"), original)
            self.assertFalse((run / mig.BACKUP_DIR / "preview.png").exists())
            for f in ("frames.jsonl", "tracking_summary.json"):
                self.assertIsNone(ABS_RE.search((run / f).read_text(encoding="utf-8")), f)
            # second migration is a no-op
            self.assertEqual(mig.migrate_run(run, dict(OLD), dry_run=False)["files_changed"], [])

            # a different machine: new dataset root and output root containing the run
            new_data, new_out = d / "Volumes" / "Data" / "RGB-D", d / "new_outputs"
            rgb_dir = new_data / "Synthetic_Scenes" / "Office" / "dynamic" / "Capture_1" / "RGB"
            rgb_dir.mkdir(parents=True)
            for s in (0, 1):
                (rgb_dir / f"rgb_{s + 2}.png").write_bytes(b"x")
            shutil.move(str(run), str(new_out / run.name))
            moved = new_out / run.name
            rts = rp.make_roots(new_data, new_out)
            frames = [json.loads(l) for l in (moved / "frames.jsonl").read_text(encoding="utf-8").splitlines()]
            for f in frames:
                p = rp.resolve(f["rgb_path"], rts)
                self.assertTrue(p.is_file(), p)
                self.assertEqual(rp.resolve(f["segmentation_mask"], rts).parent.parent, new_out / "seg_run")
            summ = json.loads((moved / "tracking_summary.json").read_text(encoding="utf-8"))
            self.assertEqual(rp.resolve(summ["segmentation_run"], rts), new_out / "seg_run")


OUTPUTS = ROOT / "outputs"


@unittest.skipUnless(OUTPUTS.is_dir() and any(OUTPUTS.iterdir()), "no local run folders")
class RealRunFolderTests(unittest.TestCase):
    def test_no_absolute_paths_left_in_run_folders(self):
        bad = []
        for f in OUTPUTS.rglob("*"):
            rel = f.relative_to(OUTPUTS).parts
            if f.is_file() and f.suffix in mig.TEXT_SUFFIXES and mig.BACKUP_DIR not in rel:
                if ABS_RE.search(f.read_text(encoding="utf-8", errors="replace")):
                    bad.append(f.relative_to(OUTPUTS).as_posix())
        self.assertEqual(bad, [], "run migrate_run_paths.py --all")


if __name__ == "__main__":
    unittest.main()
