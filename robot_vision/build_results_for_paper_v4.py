"""results_for_paper.md (AUDIT.md 16.40): ONE file with the result tables of the finals, the avatar experiment (Play headline) and Set C (S1), and the figure list. REPORTING CODE.

  python build_results_for_paper_v4.py --finals <final_results_...> [--avatar <Play tables folder>] [--s1 <process_supplementary_zip_v4_... folder>] [--figures <folder>] [--out <file>]

It only copies the Markdown tables the other tools wrote (nothing is recomputed). A section whose folder is not given says NOT AVAILABLE and why: nothing is filled in.
"""
import argparse
import sys
from datetime import datetime
from pathlib import Path

FINALS = [("a_per_setting", "Finals A: success per setting (Wilson 95 %)"), ("b_on_vs_off", "Finals B: lie detection ON vs OFF (Newcombe 95 %)"), ("c_set_a_vs_b", "Finals C: Set A vs Set B"),
          ("d_lies", "Finals D: lies given / detected / corrected / fooled"), ("e_stop_and_c2s", "Finals E: STOP episodes and C2s"),
          ("f_gesture_confusion", "Finals F: gesture confusion"), ("f_branch_confusion", "Finals F: branch confusion"),
          ("g_interruptions_and_supersessions", "Finals G: interruptions and supersessions")]
S1 = [("s1_a_per_character_and_scene", "Set C (S1): per character x scene"), ("s1_b_lies_B3", "Set C: lies (B3)"), ("s1_c_vs_sunbox_finals", "Set C against the Sunbox finals (paired)"),
      ("s1_c2_paired_outcomes", "Set C paired outcomes"), ("s1_e_gesture_confusion", "Set C gesture confusion"), ("s1_f_branch_confusion", "Set C branch confusion"),
      ("s1_d_provenance", "Set C provenance"), ("s1_g_abort_reasons_per_ask", "Set C: abort reasons per ask")]


def body(folder: Path, stem: str) -> str:
    p = folder / f"{stem}.md"
    if not p.is_file():
        return f"_{stem}.md not found in {folder.name}: NOT AVAILABLE._\n"
    return "\n".join(l.replace("# ", "#### ", 1) if l.startswith("# ") else l for l in p.read_text(encoding="utf-8").splitlines()) + "\n"


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--finals", required=True)
    ap.add_argument("--avatar", default=None)
    ap.add_argument("--s1", default=None)
    ap.add_argument("--figures", default=None)
    ap.add_argument("--out", required=True)
    a = ap.parse_args(argv)
    out = Path(a.out)
    if out.exists():
        raise SystemExit(f"{out} exists: never overwritten")
    L = [f"# Results for the paper (built {datetime.now():%Y-%m-%d %H:%M})", "",
         "Every table is copied from the tool that computed it (nothing recomputed here). Accuracy figures carry their counts. The A/B finals, the avatar experiment and Set C are three separate "
         "bodies of data and are never pooled: Set C (S1) is post-freeze, exploratory and descriptive.", "", "## 1. The A/B finals (13 settings x 20 runs)", "", f"Source: `{Path(a.finals).name}`.", ""]
    for stem, title in FINALS:
        L += [f"### {title}", "", body(Path(a.finals), stem)]
    L += ["## 2. Avatar experiment (Play is the headline)", "",
          "**Edit part (control): NOT COMPLETED, a limitation (AUDIT.md 16.38 and 16.38.1).** The Edit part started 2026-11-24 17:55:15 (STARTED marker) and stopped after about one minute with no DONE marker; "
          "the zip holds partial recordings for 10 of the 15 looks. The look checks have no resume mechanism, so the interruption rule of 16.30.1 cannot apply; the part is not evaluated (a subset chosen "
          "after the fact would be post hoc) and nothing is claimed from it. Play is the declared headline and is complete (4860 takes, 0 invalid). The unchanged look-check tool's own verdict is "
          "'fails' for all 15 looks, Sunbox looks included; it is reported as the tool gives it. Take is the unit; intervals are bootstrap over takes (Wilson only for take-level yes/no).", ""]
    if a.avatar:
        order = ["per_kind_group", "per_look", "per_look_role", "per_clip_role"]
        for name in sorted((q.stem for q in Path(a.avatar).glob("*.md")), key=lambda n: order.index(n) if n in order else 99):
            p = Path(a.avatar) / (name + ".md")
            L += [f"### {p.stem}", "", body(Path(a.avatar), p.stem)]
    else:
        L += ["**NOT AVAILABLE in this build:** the avatar zip was not on the machine (AUDIT.md 16.38). No number is given.", ""]
    L += ["## 3. Set C (supplementary S1; exploratory, descriptive only, 5 runs per cell)", "",
          "Post-freeze, never pooled with the finals (AUDIT.md 16.36 to 16.39.2). 12 cells x 5 runs, seed 2; B3 runs are plan runs 5, 7, 8, 10, 11. **Disclosed:** (1) the mixamo_worker / A1 cell was marked INVALID by the "
          "packer's checker (criterion 5, a wildcard bug counting config copies as final markers, fixed in commit 17be117; read-only re-check: every criterion passed); it ran at commit f90a72e, the others at 17be117 "
          "(only checker, zip script, doc and tests differ); it is evaluated like the others (16.39.1). (2) One earlier mixamo_worker / A1 start was refused (look source not installed) and has no runs. "
          "(3) The abort-reason table was re-run after a join bug in my code was fixed (16.39.2); the first output is superseded. (4) Other programs were running in the mixamo_worker / A1 run protocol note.", ""]
    if a.s1:
        for stem, title in S1:
            L += [f"### {title}", "", body(Path(a.s1), stem)]
    else:
        L += ["**NOT AVAILABLE in this build:** the S1 zip was not on the machine (AUDIT.md 16.39). No number is given.", ""]
    L += ["## 4. Figures (Times New Roman, PDF and PNG 300 dpi, from the result CSVs only)", ""]
    if a.figures:
        for p in sorted(Path(a.figures).glob("*.pdf")):
            L.append(f"- `{p.name}` (and `.png`) in `{Path(a.figures).name}`")
    L += ["", "| figure | content | source table |", "|---|---|---|", "| fig_a | success per setting, Wilson whiskers, A and B grouped by scenario | finals a_per_setting.csv |",
          "| fig_b | ON minus OFF, Newcombe whiskers | finals b_on_vs_off.csv |", "| fig_c | gesture confusion heatmap (pooled) | finals f_gesture_confusion.csv |",
          "| fig_d | avatar detection per look grouped by kind | avatar Play per-look table |", "| fig_e | Set C success per character x scene | s1_a_per_character_and_scene.csv |", ""]
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text("\n".join(L), encoding="utf-8")
    print(out)
    return 0


if __name__ == "__main__":
    sys.exit(main())
