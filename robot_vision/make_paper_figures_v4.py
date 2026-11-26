"""Figures for the paper (AUDIT.md 16.40). REPORTING CODE: reads the RESULT CSVs only (never a session, a log or a reference file) and writes PDF and PNG (300 dpi) in Times New Roman.

  python make_paper_figures_v4.py --finals <final_results_... folder> [--avatar <avatar Play tables folder>] [--s1 <process_supplementary_zip_v4_... folder>] [--out <folder>]

  a  success per setting with Wilson 95 % whiskers, A and B grouped by scenario          (finals a_per_setting.csv)
  b  detection ON minus OFF, percentage points, Newcombe 95 % whiskers                    (finals b_on_vs_off.csv)
  c  gesture confusion heatmap, all 13 settings pooled (row share, counts in the cells)   (finals f_gesture_confusion.csv)
  d  avatar experiment: person detected and gesturing hand found AND linked, per look grouped by kind group, per command and distance with their bootstrap-over-takes 95 % interval
                                                                                          (the Play per-look table of process_avatar_zip_v4.py)
  e  Set C (S1): success per character x scene with Wilson 95 % whiskers                  (s1_a_per_character_and_scene.csv)

d and e are written only when their folders are given. Plain 2-D charts, the Okabe-Ito colour-blind-safe palette, no title text beyond axis labels. If the font "Times New Roman" is not
installed the script stops (it never falls back). Never writes into a results folder it reads: --out is a NEW folder.
"""

from __future__ import annotations

import argparse
import csv
import sys
from datetime import datetime
from pathlib import Path

HERE = Path(__file__).resolve().parent
FONT = "Times New Roman"
OKABE = {"blue": "#0072B2", "orange": "#E69F00", "green": "#009E73", "vermillion": "#D55E00", "sky": "#56B4E9", "purple": "#CC79A7", "yellow": "#F0E442", "black": "#000000"}


def setup():
    import matplotlib
    matplotlib.use("Agg")
    from matplotlib import font_manager as fm
    if FONT not in {f.name for f in fm.fontManager.ttflist}:
        raise SystemExit(f'the font "{FONT}" is not installed: stopped (no fallback font is used)')
    matplotlib.rcParams.update({"font.family": FONT, "font.size": 10, "axes.spines.top": False, "axes.spines.right": False, "pdf.fonttype": 42, "ps.fonttype": 42,
                                "axes.grid": True, "grid.alpha": 0.25, "grid.linewidth": 0.5, "axes.axisbelow": True})
    import matplotlib.pyplot as plt
    return plt


def read(path: Path) -> list[dict]:
    with Path(path).open(encoding="utf-8", newline="") as f:
        return list(csv.DictReader(f))


def num(v):
    try:
        return float(v)
    except (TypeError, ValueError):
        return None


def save(fig, out: Path, stem: str) -> list[str]:
    names = []
    for ext in ("pdf", "png"):
        p = out / f"{stem}.{ext}"
        fig.savefig(p, dpi=300, bbox_inches="tight")
        names.append(p.name)
    return names


def scenario_of(setting: str) -> str:
    return setting.split("_")[0][1:]            # A2_right -> "2", B1_off -> "1"


def fig_a(plt, rows: list[dict], out: Path) -> list[str]:
    order = [("A", "A1"), ("A", "A2_right"), ("A", "A2_left"), ("A", "A3"), ("A", "A4"), ("B", "B1"), ("B", "B1_off"), ("B", "B2_right"), ("B", "B2_right_off"),
             ("B", "B3"), ("B", "B3_off"), ("B", "B4"), ("B", "B4_off")]
    by = {r["setting"]: r for r in rows}
    items = [s for _, s in order if s in by]
    fig, ax = plt.subplots(figsize=(7.2, 3.4))
    x, ticks, labels, gap, prev = [], [], [], 0.0, None
    pos = 0.0
    for s in items:
        key = (s[0], scenario_of(s))
        if prev is not None and key != prev:
            pos += 0.6
        prev = key
        r = by[s]
        rate, lo, hi = num(r["rate"]), num(r["wilson_lo"]), num(r["wilson_hi"])
        col = OKABE["blue"] if s[0] == "A" else (OKABE["orange"] if not s.endswith("_off") else OKABE["vermillion"])
        ax.bar(pos, rate, width=0.8, color=col, edgecolor="black", linewidth=0.5)
        ax.errorbar(pos, rate, yerr=[[rate - lo], [hi - rate]], fmt="none", ecolor="black", capsize=3, linewidth=1)
        ax.text(pos, 0.02, f"{r['successes']}/{r['n']}", ha="center", va="bottom", fontsize=7, color="white" if rate > 0.12 else "black")
        ticks.append(pos)
        labels.append(s.replace("_right", " R").replace("_left", " L").replace("_off", " off"))
        pos += 1.0
    ax.set_xticks(ticks)
    ax.set_xticklabels(labels, rotation=45, ha="right")
    ax.set_ylim(0, 1.05)
    ax.set_ylabel("Success rate (Wilson 95 % interval)")
    ax.legend(handles=[plt.Rectangle((0, 0), 1, 1, color=OKABE["blue"], ec="black"), plt.Rectangle((0, 0), 1, 1, color=OKABE["orange"], ec="black"),
                       plt.Rectangle((0, 0), 1, 1, color=OKABE["vermillion"], ec="black")], labels=["Set A (truthful)", "Set B, lie detection on", "Set B, lie detection off"],
              loc="lower center", bbox_to_anchor=(0.5, 1.0), ncol=3, frameon=False, fontsize=8)
    return save(fig, out, "fig_a_success_per_setting")


def fig_b(plt, rows: list[dict], out: Path) -> list[str]:
    rows = [r for r in rows if r["metric"] == "success"]
    fig, ax = plt.subplots(figsize=(5.2, 3.0))
    for i, r in enumerate(rows):
        d, lo, hi = num(r["difference_pp (ON - OFF)"]), num(r["newcombe_lo_pp"]), num(r["newcombe_hi_pp"])
        ax.errorbar(d, i, xerr=[[d - lo], [hi - d]], fmt="o", color=OKABE["blue"], ecolor="black", capsize=3, markersize=5)
    ax.axvline(0, color="black", linewidth=0.8)
    ax.set_yticks(range(len(rows)))
    ax.set_yticklabels([r["comparison"].replace("B detection on vs off, ", "").capitalize() for r in rows])
    ax.invert_yaxis()
    ax.set_xlabel("Success, detection ON minus OFF (percentage points, Newcombe 95 % interval)")
    ax.grid(axis="y", visible=False)
    return save(fig, out, "fig_b_on_vs_off")


def fig_c(plt, rows: list[dict], out: Path) -> list[str]:
    import numpy as np
    pooled = [r for r in rows if r["scope"].startswith("ALL")]
    pooled = [r for r in pooled if num(r["row_total"]) and num(r["row_total"]) > 0]
    cols = [c for c in rows[0] if c not in ("scope", "command_shown", "row_total", "share_read_as_shown")]
    m = np.array([[float(r[c]) / float(r["row_total"]) for c in cols] for r in pooled])
    fig, ax = plt.subplots(figsize=(5.4, 0.55 * len(pooled) + 1.6))
    im = ax.imshow(m, cmap="Blues", vmin=0, vmax=1, aspect="auto")
    for i, r in enumerate(pooled):
        for j, c in enumerate(cols):
            v = float(r[c])
            if v:
                ax.text(j, i, f"{int(v)}", ha="center", va="center", fontsize=8, color="white" if m[i, j] > 0.55 else "black")
    ax.set_xticks(range(len(cols)))
    ax.set_xticklabels(cols)
    ax.set_yticks(range(len(pooled)))
    ax.set_yticklabels([f"{r['command_shown']} (n={int(float(r['row_total']))})" for r in pooled])
    ax.set_xlabel("Command read")
    ax.set_ylabel("Command shown")
    ax.grid(False)
    fig.colorbar(im, ax=ax, label="Share of the row")
    return save(fig, out, "fig_c_gesture_confusion")


def fig_d(plt, rows: list[dict], out: Path) -> list[str]:
    looks = sorted({r["look"] for r in rows}, key=lambda l: (next(r["kind_group"] for r in rows if r["look"] == l), l))
    kinds = [next(r["kind_group"] for r in rows if r["look"] == l) for l in looks]
    cmds = ["POINT", "WAIT", "STOP", "PROCEED", "NONE"]
    mk = dict(zip(cmds, ["o", "s", "^", "D", "v"]))
    dists = sorted({r["distance_m"] for r in rows}, key=float)
    # horizontal layout: a row per look (grouped by kind), one column per measure x distance, y labels on the left panel only
    panels = [(m, n, d) for d in dists for m, n in (("person", "Person detected"), ("hand_linked", "Gesturing hand found and linked"))]
    fig, axes = plt.subplots(1, len(panels), figsize=(11.0, 6.2), sharey=True, squeeze=False)
    axes = axes[0]
    ypos = {l: len(looks) - 1 - i for i, l in enumerate(looks)}
    for ax, (meas, name, dist) in zip(axes, panels):
        for c_i, cmd in enumerate(cmds):
            for look in looks:
                cell = [r for r in rows if r["look"] == look and r["command"] == cmd and r["distance_m"] == dist]
                if not cell:
                    continue
                r = cell[0]
                mean, lo, hi = num(r.get(f"{meas}_mean")), num(r.get(f"{meas}_lo")), num(r.get(f"{meas}_hi"))
                if mean is None:
                    continue
                y = ypos[look] + (2 - c_i) * 0.13
                xerr = [[mean - lo], [hi - mean]] if lo is not None and hi is not None else None
                ax.errorbar(mean, y, xerr=xerr, fmt=mk[cmd], color=list(OKABE.values())[c_i], ecolor="black", capsize=1.5, markersize=4, linewidth=0.6)
        for i in range(1, len(looks)):
            if kinds[i] != kinds[i - 1]:
                ax.axhline(len(looks) - i - 0.5, color="0.6", linewidth=0.6)
        ax.set_xlim(-0.03, 1.05)
        ax.set_xlabel(f"{name}\n(share of takes, {dist} m)", fontsize=9)
        ax.grid(axis="x", color="0.9", linewidth=0.5)
    axes[0].set_yticks([ypos[l] for l in looks])
    axes[0].set_yticklabels([f"{l} [{k}]" for l, k in zip(looks, kinds)], fontsize=8)
    axes[0].set_ylim(-0.6, len(looks) - 0.4)
    handles = [plt.Line2D([], [], marker=mk[c], linestyle="", color=list(OKABE.values())[i], label=c) for i, c in enumerate(cmds)]
    fig.legend(handles=handles, loc="lower center", ncol=5, frameon=False)
    fig.tight_layout(rect=(0, 0.06, 1, 1))
    return save(fig, out, "fig_d_avatar_detection_per_look")


def fig_e(plt, rows: list[dict], out: Path) -> list[str]:
    scenes = ["A1", "A3", "B3"]
    chars = sorted({r["character"] for r in rows})
    cols = [OKABE["blue"], OKABE["orange"], OKABE["green"], OKABE["purple"]]
    fig, ax = plt.subplots(figsize=(6.4, 3.2))
    w = 0.8 / max(1, len(chars))
    for c_i, ch in enumerate(chars):
        for s_i, sc in enumerate(scenes):
            r = [x for x in rows if x["character"] == ch and x["scene"] == sc]
            if not r:
                continue
            r = r[0]
            rate, lo, hi = num(r["rate"]), num(r["wilson_lo"]), num(r["wilson_hi"])
            x = s_i + (c_i - (len(chars) - 1) / 2) * w
            ax.bar(x, rate, width=w * 0.95, color=cols[c_i % 4], edgecolor="black", linewidth=0.5, label=ch if s_i == 0 else None)
            ax.errorbar(x, rate, yerr=[[rate - lo], [hi - rate]], fmt="none", ecolor="black", capsize=2.5, linewidth=1)
            ax.text(x, hi + 0.02, f"{r['successes']}/{r['n']}", ha="center", va="bottom", fontsize=7)
    ax.set_xticks(range(len(scenes)))
    ax.set_xticklabels(scenes)
    ax.set_ylim(0, 1.12)
    ax.set_ylabel("Success rate (Wilson 95 % interval, 5 runs per bar)")
    ax.set_xlabel("Scene")
    ax.legend(frameon=False, fontsize=8, loc="lower center", bbox_to_anchor=(0.5, 1.0), ncol=4)
    return save(fig, out, "fig_e_set_c_success")


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--finals", required=True, help="final_results_<time> folder (a_per_setting.csv, b_on_vs_off.csv, f_gesture_confusion.csv)")
    ap.add_argument("--avatar", default=None, help="folder with the avatar Play per-look table (per_look.csv)")
    ap.add_argument("--s1", default=None, help="process_supplementary_zip_v4_<time> folder (s1_a_per_character_and_scene.csv)")
    ap.add_argument("--out", default=None, help="a NEW folder (default ~/RobotVisionResults/paper_results/figures_<time>)")
    a = ap.parse_args(argv)
    plt = setup()
    out = Path(a.out) if a.out else Path.home() / "RobotVisionResults" / "paper_results" / f"figures_{datetime.now():%Y%m%d_%H%M%S}"
    out.mkdir(parents=True, exist_ok=False)
    fin = Path(a.finals)
    made = {}
    made["a"] = fig_a(plt, read(fin / "a_per_setting.csv"), out)
    made["b"] = fig_b(plt, read(fin / "b_on_vs_off.csv"), out)
    made["c"] = fig_c(plt, read(fin / "f_gesture_confusion.csv"), out)
    if a.avatar:
        made["d"] = fig_d(plt, read(Path(a.avatar) / "per_look.csv"), out)
    if a.s1:
        made["e"] = fig_e(plt, read(Path(a.s1) / "s1_a_per_character_and_scene.csv"), out)
    (out / "sources.txt").write_text("".join(f"{k}: {v}\n" for k, v in made.items()) + f"finals: {fin}\navatar: {a.avatar}\ns1: {a.s1}\n", encoding="utf-8")
    print(f"figures: {out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
