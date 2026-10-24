"""Results archive for the v4 study (the v3 one, make_results_archive.py, is unchanged and is reused for its copy, hashing, zip and
verify helpers). Copies v4 session folders, checks them, and records the freeze. Never modifies or deletes a run folder.

A new folder <archive_root>/results_archive_v4_<time>/ (outside the repository; configs/v4/archive/results_archive.json):
    README.md            what each session folder is, its setting, role (final / development), machine and checks
    CHECKSUMS.sha256     SHA-256 of every other file (sha256sum / shasum -a 256 -c format)
    AUDIT.md             copy of the repository's AUDIT.md (section 14 is the v4 plan)
    checks.json          per session: folders present, done markers, leak test, truth files, freeze, copy verification
    archive_config/      the archive config and the manifest, and build_info.json (git commit)
    environment/         machine.json, pip_freeze.txt, models.csv (SHA-256 of the pose weights and the MediaPipe model)
    frozen/              configs/v4/frozen.json, every v4 config and the v3 files v4 reads at their repository paths, hashes.csv
    sessions/<setting>/<role>/{unity,bridge,eval,analysis}/   copies of the run folders: Unity's trial folder with run_###/ (truth.jsonl,
                         grid / optimal path / trail, run.json) and leak_test/, the bridge guide folder (v4_log.jsonl, ...),
                         the evaluation and analysis folders
Next to it: results_archive_v4_<time>.zip and .zip.sha256. With --repo-summary the analysis tables (analysis.md, rq1_comparison.csv)
are also copied to <repo>/results/summary/v4/<setting>/ for committing.

The sessions are listed in configs/v4/archive/results_manifest.json (setting, role, folder names). Model weights are never copied.
Folders on another machine are reported as not_on_this_machine. This is reporting code: inference code never imports it.

Usage (from robot_vision/):
    python make_results_archive_v4.py [--archive-root DIR] [--no-zip] [--repo-summary DIR]
    python make_results_archive_v4.py --verify <archive folder>
"""

from __future__ import annotations

import argparse
import hashlib
import json
import platform
import shutil
import sys
import zipfile
from datetime import datetime
from pathlib import Path

import final_guard_v4 as fg
import freeze_v4 as fz
import make_results_archive as ma

HERE = Path(__file__).resolve().parent
DEFAULT_CONFIG = "configs/v4/archive/results_archive.json"
KINDS = ("unity", "bridge", "eval", "analysis")
ROLES = ("final", "development")


def load_config(path=DEFAULT_CONFIG) -> dict:
    p = Path(path)
    return json.loads((p if p.is_absolute() else HERE / p).read_text(encoding="utf-8"))


def validate_manifest(m: dict) -> list[str]:
    out = []
    for i, s in enumerate(m.get("sessions", [])):
        if s.get("role") not in ROLES:
            out.append(f"session {i}: role {s.get('role')!r} not in {ROLES}")
        if not s.get("setting"):
            out.append(f"session {i}: no setting")
        if s.get("role") == "final" and s.get("setting") not in fg.settings():
            out.append(f"session {i}: a final session needs one of the plan's settings {fg.settings()}")
        if not s.get("unity") or not s.get("bridge"):
            out.append(f"session {i}: needs 'unity' and 'bridge' folders")
    seen = [(s.get("setting"), s.get("role")) for s in m.get("sessions", [])]
    out += [f"setting/role {x} listed more than once" for x in sorted(set(seen), key=str) if seen.count(x) > 1]
    return out


def session_checks(s: dict, output_root: Path, repo: Path) -> list[dict]:
    """Presence, done markers, leak test, truth files and the freeze, for one manifest entry."""
    def row(kind, check, status, detail=""):
        return {"setting": s["setting"], "role": s["role"], "folder": s.get(kind, ""), "check": check, "status": status, "detail": detail}

    out, final = [], s["role"] == "final"
    for kind in KINDS:
        if s.get(kind) and not (output_root / s[kind]).is_dir():
            out.append(row(kind, "present", "not_on_this_machine"))
        elif s.get(kind):
            out.append(row(kind, "present", "ok"))
    u, b, e = (output_root / s[k] if s.get(k) else None for k in ("unity", "bridge", "eval"))
    if u is not None and u.is_dir():
        runs = sorted(u.glob("run_[0-9][0-9][0-9]"))
        out.append(row("unity", "run folders", "ok" if runs else "problem", f"{len(runs)} run_### folders"))
        missing = [r.name for r in runs if not ((r / "truth.jsonl").is_file() and (r / "run.json").is_file())]
        out.append(row("unity", "truth.jsonl and run.json in every run folder", "ok" if not missing else "problem", ", ".join(missing)))
        lt = u / "leak_test" / "leak_test.json"
        if lt.is_file():
            ok = json.loads(lt.read_text(encoding="utf-8")).get("passed") is True
            out.append(row("unity", "leak test passed", "ok" if ok else "problem", str(lt.relative_to(u))))
        else:
            out.append(row("unity", "leak test passed", "problem" if final else "missing", "no leak_test/leak_test.json"))
        if final:
            sess = json.loads((u / "session.json").read_text(encoding="utf-8")) if (u / "session.json").is_file() else {}
            out.append(row("unity", "Unity session mode is final", "ok" if sess.get("mode") == "final" else "problem", f"mode {sess.get('mode')!r}"))
    if final:
        if b is not None and b.is_dir():
            f = b / fg.MARKERS["run"]
            out.append(row("bridge", fg.MARKERS["run"], "ok" if f.is_file() else "problem", "the final run finished" if f.is_file() else "no marker: the run did not finish"))
            fs = b / "FINAL_SETTING.json"
            if fs.is_file():
                rec = json.loads(fs.read_text(encoding="utf-8"))
                same = rec.get("frozen_sha256") == fz.sha256_lf(repo / fz.FROZEN_REL)
                out.append(row("bridge", "run started with this freeze", "ok" if same else "problem", f"setting {rec.get('setting')}"))
            else:
                out.append(row("bridge", "FINAL_SETTING.json", "problem", "not recorded"))
        if e is not None and e.is_dir():
            f = e / fg.MARKERS["evaluation"]
            out.append(row("eval", fg.MARKERS["evaluation"], "ok" if f.is_file() else "problem"))
        elif s.get("eval"):
            pass
        else:
            out.append(row("eval", "final evaluation listed", "problem", "a final session needs its evaluation folder"))
    return out


def freeze_rows(repo: Path, out: Path) -> tuple[list[dict], list[str]]:
    """Copy the freeze record, the v4 configs and the v3 files v4 reads to out/ at their repository paths; hashes.csv."""
    rec = fz.read(repo)
    rows = []
    for f in [fz.FROZEN_REL, *fz.config_files(repo), *fz.V3_DEPENDENCIES]:
        src = repo / f
        dst = out.joinpath(*Path(f).parts)
        dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(src, dst)
        lf = fz.sha256_lf(src)
        want = rec["sha256"].get(f) or rec["v3_dependencies"].get(f)
        rows.append({"path": f, "sha256_lf_normalised": lf, "recorded_in_frozen_json": want or "",
                     "matches": (lf == want) if (rec["frozen"] and want) else ""})
    ma.write_csv(out / "hashes.csv", rows)
    return rows, fz.problems(repo)


def readme(info: dict) -> str:
    L = [f"# v4 results archive {info['name']}", "", f"Built {info['built']} at commit `{info['git'].get('commit')}` by `robot_vision/make_results_archive_v4.py`.",
         f"Freeze: frozen = **{info['frozen']}**" + (f", frozen at {info['frozen_at']} (commit {info['frozen_commit']})." if info["frozen"] else
                                                      " (the v4 configs were NOT frozen when this archive was built: development sessions only)."), "",
         "Verify: `python make_results_archive_v4.py --verify <this folder>` (or `shasum -a 256 -c CHECKSUMS.sha256`).", "",
         "| setting | role | folders copied | checks |", "|---|---|---|---|"]
    for s in info["sessions"]:
        L.append(f"| {s['setting']} | {s['role']} | {', '.join(s['copied']) or 'none'} | {s['checks']} |")
    L += ["", "Folders: `sessions/<setting>/<role>/{unity,bridge,eval,analysis}` are copies of the run folders; `frozen/` the freeze record, the v4 configs and the v3 "
          "files v4 reads with `hashes.csv`; `environment/` machine, packages and model hashes (the model files are not copied); `checks.json` every check.",
          "", "Not comparable across machines: inference times, stale-perception stops, total trial time, round trip (see AUDIT.md section 14)."]
    return "\n".join(L) + "\n"


def build(cfg: dict, *, archive_root: Path, output_root: Path, repo: Path, audit: Path, now: datetime, make_zip: bool = True,
          repo_summary: Path | None = None, include_pip: bool = True) -> dict:
    from decision_io import git_info
    manifest = ma.read_json(ma._p(cfg["manifest"])) or {"sessions": []}
    bad = validate_manifest(manifest)
    if bad:
        raise SystemExit("manifest problems: " + "; ".join(bad))
    name = f"results_archive_v4_{now:%Y%m%d_%H%M%S}"
    archive = Path(archive_root) / name
    if repo.resolve() in archive.resolve().parents or archive.resolve() == repo.resolve():
        raise SystemExit(f"the archive must be outside the repository: {archive}")
    if archive.exists():
        raise SystemExit(f"archive folder already exists, not overwriting: {archive}")
    archive.mkdir(parents=True)
    ex = cfg["exclude"]
    checks, summaries, mismatch, changed, excluded_all = [], [], [], [], []
    for s in manifest["sessions"]:
        checks += session_checks(s, output_root, repo)
        copied = []
        for kind in KINDS:
            if not s.get(kind) or not (output_root / s[kind]).is_dir():
                continue
            src, dst = output_root / s[kind], archive / "sessions" / s["setting"] / s["role"] / kind
            before = ma.stat_snapshot(src)
            hashes, excluded = ma.copy_tree(src, dst, ex)
            excluded_all += [{**x, "folder": s[kind]} for x in excluded]
            for rel, h in hashes.items():
                if ma.sha256_file(dst.joinpath(*Path(rel).parts)) != h or ma.sha256_file(src.joinpath(*Path(rel).parts)) != h:
                    mismatch.append(f"{s[kind]}/{rel}")
            if ma.stat_snapshot(src) != before:
                changed.append(s[kind])
            copied.append(kind)
        problems = [c for c in checks if c["setting"] == s["setting"] and c["role"] == s["role"] and c["status"] == "problem"]
        summaries.append({"setting": s["setting"], "role": s["role"], "copied": copied,
                          "checks": "all ok" if not problems else f"{len(problems)} problem(s): " + "; ".join(f"{p['check']}" for p in problems)})
    rows, freeze_problems = freeze_rows(repo, archive / "frozen")
    rec = fz.read(repo)
    if any(s["role"] == "final" for s in manifest["sessions"]) and not rec["frozen"]:
        checks.append({"setting": "", "role": "final", "folder": "", "check": "v4 configs frozen", "status": "problem", "detail": "frozen is false"})
    checks.append({"setting": "", "role": "", "folder": "", "check": "freeze matches the files", "status": "ok" if not freeze_problems else "problem",
                   "detail": "; ".join(freeze_problems)})
    models = ma.model_hashes(cfg, repo)
    ma.write_csv(archive / "environment" / "models.csv", models)
    machine = ma.archive_machine(cfg)
    ma.write_json(archive / "environment" / "machine.json", machine)
    (archive / "environment" / "pip_freeze.txt").write_text(ma.pip_freeze() if include_pip else "# not recorded (include_pip false)\n", encoding="utf-8")
    git = git_info()
    ma.write_json(archive / "archive_config" / "build_info.json", {"built": now.isoformat(timespec="seconds"), "git": git,
                                                                   "command": " ".join([Path(sys.executable).name] + sys.argv)})
    ma.write_json(archive / "archive_config" / "results_archive.json", cfg)
    ma.write_json(archive / "archive_config" / "results_manifest.json", manifest)
    if audit.exists():
        shutil.copy2(audit, archive / "AUDIT.md")
    ma.write_json(archive / "checks.json", {"checks": checks, "copy_mismatch": mismatch, "originals_changed": changed,
                                           "excluded": excluded_all, "model_hash_mismatch": [m["model"] for m in models if m["matches"] is False]})
    info = {"name": name, "built": now.isoformat(timespec="seconds"), "git": git, "frozen": rec["frozen"], "frozen_at": rec["frozen_at"],
            "frozen_commit": rec["git_commit"], "sessions": summaries}
    (archive / "README.md").write_text(readme(info), encoding="utf-8")
    files = sorted(p for p in archive.rglob("*") if p.is_file())
    (archive / ma.CHECKSUMS).write_text("".join(f"{ma.sha256_file(p)}  {p.relative_to(archive).as_posix()}\n" for p in files), encoding="utf-8")
    zip_path = zip_sha = None
    if make_zip:
        zip_path = archive.parent / f"{name}.zip"
        no = {x.lower() for x in cfg.get("no_compress_suffixes", [])}
        with zipfile.ZipFile(zip_path, "x") as z:
            for p in sorted(archive.rglob("*")):
                if p.is_file():
                    z.write(p, f"{name}/{p.relative_to(archive).as_posix()}",
                            compress_type=zipfile.ZIP_STORED if p.suffix.lower() in no else zipfile.ZIP_DEFLATED)
        zip_sha = ma.sha256_file(zip_path)
        (archive.parent / f"{name}.zip.sha256").write_text(f"{zip_sha}  {zip_path.name}\n", encoding="utf-8")
    if repo_summary is not None:
        copy_repo_summary(archive, Path(repo_summary), manifest)
    return {"archive": archive, "zip": zip_path, "zip_sha256": zip_sha, "files": len(files) + 1, "checks": checks, "copy_mismatch": mismatch,
            "originals_changed": changed, "frozen": rec["frozen"], "freeze_problems": freeze_problems}


def copy_repo_summary(archive: Path, dest: Path, manifest: dict) -> list[str]:
    """Only the analysis tables (analysis.md, rq1_comparison.csv) of the archived analysis folders go into the repository."""
    copied = []
    for s in manifest["sessions"]:
        src = archive / "sessions" / s["setting"] / s["role"] / "analysis"
        for name in ("analysis.md", "rq1_comparison.csv"):
            if (src / name).is_file():
                out = dest / s["setting"] / s["role"] / name
                out.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(src / name, out)
                copied.append(out.relative_to(dest).as_posix())
    return copied


def main(argv=None) -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--config", default=DEFAULT_CONFIG)
    ap.add_argument("--archive-root", help="overrides archive_root in the config (must be outside the repository)")
    ap.add_argument("--no-zip", action="store_true")
    ap.add_argument("--repo-summary", metavar="DIR", help="also copy the analysis tables to this folder (e.g. ../results/summary/v4)")
    ap.add_argument("--verify", metavar="ARCHIVE", help="check an archive folder against its CHECKSUMS.sha256 and zip hash")
    a = ap.parse_args(argv)
    if a.verify:
        problems = ma.verify(Path(a.verify))
        print("\n".join(problems) if problems else "OK: every file matches CHECKSUMS.sha256 (and the zip its .sha256)")
        raise SystemExit(1 if problems else 0)
    cfg = load_config(a.config)
    res = build(cfg, archive_root=Path(a.archive_root) if a.archive_root else ma._p(cfg["archive_root"]), output_root=ma._p(cfg["output_root"]),
                repo=ma._p(cfg["repo_root"]), audit=ma._p(cfg["audit"]), now=datetime.now(), make_zip=not a.no_zip,
                repo_summary=Path(a.repo_summary) if a.repo_summary else None)
    issues = [c for c in res["checks"] if c["status"] == "problem"]
    away = sorted({c["folder"] for c in res["checks"] if c["status"] == "not_on_this_machine"})
    print(f"Archive: {res['archive'].resolve()}")
    if res["zip"]:
        print(f"Zip:     {res['zip'].resolve()}\nSHA-256: {res['zip_sha256']}")
    print(f"Files: {res['files']}; originals unchanged: {not res['originals_changed']}; copy mismatches: {len(res['copy_mismatch'])}; "
          f"v4 configs frozen: {res['frozen']}; freeze problems: {len(res['freeze_problems'])}")
    print(f"Not on this machine: {', '.join(away) or 'none'}")
    print("Problems: " + ("none" if not issues else "\n  " + "\n  ".join(f"{c['setting']}/{c['role']} {c['check']}: {c['detail']}" for c in issues)))
    raise SystemExit(1 if issues or res["copy_mismatch"] or res["originals_changed"] else 0)


if __name__ == "__main__":
    main()
