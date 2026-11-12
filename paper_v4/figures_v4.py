"""v4 paper features (Stage E1, E2, E3, E5; 2026-11-12, Nusrat; Avatar/Config/upgrade_design.md). RESULT-NEUTRAL: it only reads saved
outputs (Unity session folders, bridge run folders) and draws or tabulates them; it decides nothing and changes no config. It lives outside
robot_vision/ (Anisha's) and uses that folder's modules read-only: gt_path (grid, optimal corridor), hri_eval_dev_v4 (sessions, junction
metrics, the development split guard), hri_control_v4 (the v4 map).

- E1 top-down figure per run: the ground-truth grid (blocked cells), the optimal corridor, A and B, the trail coloured by the robot's state
  (the light-ring colours) and a marker at each ask (green correct, red wrong, grey abort).
- E2 distance accuracy: the 360 distance estimate against the true distance at every ask, before the ankle-height correction (P1) and after
  it (both from the same pixels: d_without = d_with * h_cam / (h_cam - ankle), with the session's own ankle value).
- E3 per-look table: frame accuracy and coverage, dialog correct share and abort rate, per development look.
- E5 junction confusion table: the true branch toward B against the branch chosen (or abort), per node and in total.

Usage (from the repository root, with the project venv):
  robot_vision/.venv/Scripts/python.exe paper_v4/figures_v4.py --session robot_vision/outputs/trials_X robot_vision/outputs/bridge_guide_Y [...]
Writes robot_vision/outputs/paper_v4_<time>/ (git-ignored, a new folder every time): <session>_run_###_topdown.png, distance_accuracy.png,
per_look.md/.csv, junction_confusion.md/.csv, report.json, run.json (git commit, sessions) and config_used/ (the configs read).
The 360 camera height is each session's own (config_used/robot_unity_v4.json camera_360.height_m). Tests: paper_v4/test_figures_v4.py.
"""

from __future__ import annotations

import argparse
import csv
import json
import math
import sys
from collections import Counter, defaultdict
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
RV = ROOT / "robot_vision"
sys.path.insert(0, str(RV))

import gesture_data as gd  # noqa: E402
import gt_path  # noqa: E402
import hri_control_v4 as hv  # noqa: E402
import hri_eval_dev_v4 as ev  # noqa: E402

# palette (dataviz reference instance, light surface); the trail mirrors the robot's light ring
SURFACE, INK, MUTED, GRID = "#fcfcfb", "#0b0b0b", "#52514e", "#d9d8d4"
STATE = {"driving": "#008300", "searching": "#2a78d6", "asking": "#eda100", "stopped": "#e34948", "idle": "#8a8985"}
CORRIDOR, BLOCKED = "#c9c2f2", "#c8c7c3"
OUTCOME = {"correct": "#1baf7a", "wrong": "#e34948", "abort": "#8a8985"}


def light(state: str) -> str:
    s = (state or "").strip()
    if "stopped" in s or s.startswith("aborted"):
        return "stopped"
    if s.startswith(("navigate", "execute")):
        return "driving"
    if s.startswith(("scan", "approach")):
        return "searching"
    if s.startswith(("ask", "read", "wait")):
        return "asking"
    return "idle"


def decisions(bridge: Path) -> dict:
    by = defaultdict(list)
    with (bridge / "decisions.csv").open(encoding="utf-8") as f:
        for r in csv.DictReader(f):
            t = int(r["trial"])
            if t >= 1:
                by[t].append((float(r["time_s"]), float(r["x"]), float(r["z"]), r["state"]))
    return by


def topdown(run, dec: list, dialogs: list, out: Path, plt) -> Path:
    grid = gt_path.load_grid(run.unity_dir / f"run_{run.trial:03d}" / "grid.json")
    a, b = grid.cell_of(*grid.start), grid.cell_of(*grid.goal)
    corr = gt_path.optimal_corridor(grid, a, b, gt_path.load_config()["optimal_length_tolerance_m"])
    fig, ax = plt.subplots(figsize=(9.0, 7.2), dpi=150)
    fig.patch.set_facecolor(SURFACE)
    ax.set_facecolor(SURFACE)
    s = grid.cell
    xs = [x for x, _, _ in [(t[1], t[2], t[3]) for t in dec]] + [grid.start[0], grid.goal[0]]
    zs = [z for _, z, _ in [(t[1], t[2], t[3]) for t in dec]] + [grid.start[1], grid.goal[1]]
    pad = 6.0
    x0, x1, z0, z1 = min(xs) - pad, max(xs) + pad, min(zs) - pad, max(zs) + pad
    for iz in range(grid.nz):
        for ix in range(grid.nx):
            cx, cz = grid.centre(ix, iz)
            if x0 <= cx <= x1 and z0 <= cz <= z1 and grid.blocked[iz][ix]:
                ax.add_patch(plt.Rectangle((cx - s / 2, cz - s / 2), s, s, color=BLOCKED, lw=0))
    if corr:
        for ix, iz in corr["cells"]:
            cx, cz = grid.centre(ix, iz)
            ax.add_patch(plt.Rectangle((cx - s / 2, cz - s / 2), s, s, color=CORRIDOR, lw=0, alpha=0.8))
    # trail by state: one polyline per stretch of the same light
    seg, cur = [], None
    for t, x, z, st in dec:
        l = light(st)
        if l != cur and seg:
            ax.plot([p[0] for p in seg], [p[1] for p in seg], color=STATE[cur], lw=2, solid_capstyle="round")
            seg = seg[-1:]
        cur = l
        seg.append((x, z))
    if seg and cur:
        ax.plot([p[0] for p in seg], [p[1] for p in seg], color=STATE[cur], lw=2, solid_capstyle="round")
    for d in dialogs:
        for k, ask in enumerate(d.get("asks_log", [])):
            last = k + 1 == len(d["asks_log"])
            if last:
                ax.scatter([ask["robot"]["x"]], [ask["robot"]["z"]], s=90, zorder=5, edgecolors=SURFACE, linewidths=2,
                           color=OUTCOME[d["outcome"]])
            else:                                                       # an earlier ask of the same dialog (asked again)
                ax.scatter([ask["robot"]["x"]], [ask["robot"]["z"]], s=70, zorder=5, facecolors=SURFACE, edgecolors=MUTED, linewidths=1.5)
            if last:
                ax.annotate(f"{d['node']}: {d['chosen'] or 'abort'}", (ask["robot"]["x"], ask["robot"]["z"]), xytext=(8, 6),
                            textcoords="offset points", fontsize=8, color=INK)
    ax.scatter([grid.start[0]], [grid.start[1]], marker="o", s=140, color="#2a78d6", edgecolors=SURFACE, linewidths=2, zorder=6)
    ax.scatter([grid.goal[0]], [grid.goal[1]], marker="*", s=260, color="#e34948", edgecolors=SURFACE, linewidths=1.5, zorder=6)
    ax.annotate("A", grid.start, xytext=(-14, -4), textcoords="offset points", fontsize=10, color=INK, weight="bold")
    ax.annotate("B", grid.goal, xytext=(8, -4), textcoords="offset points", fontsize=10, color=INK, weight="bold")
    ax.set_xlim(x0, x1)
    ax.set_ylim(z0, z1)
    ax.set_aspect("equal")
    ax.set_xlabel("x (m)", color=MUTED)
    ax.set_ylabel("z (m)", color=MUTED)
    ax.tick_params(colors=MUTED, labelsize=8)
    for sp in ax.spines.values():
        sp.set_color(GRID)
    handles = [plt.Line2D([], [], color=c, lw=2, label=k) for k, c in STATE.items() if k != "idle"]
    handles += [plt.Rectangle((0, 0), 1, 1, color=CORRIDOR, label="optimal corridor"),
                plt.Rectangle((0, 0), 1, 1, color=BLOCKED, label="blocked (widened)")]
    handles += [plt.Line2D([], [], marker="o", lw=0, color=c, label=f"last ask: {k}") for k, c in OUTCOME.items()]
    handles += [plt.Line2D([], [], marker="o", lw=0, markerfacecolor=SURFACE, markeredgecolor=MUTED, label="earlier ask (asked again)")]
    ax.legend(handles=handles, fontsize=7, loc="upper left", bbox_to_anchor=(1.02, 1.0), frameon=False, labelcolor=INK)
    ax.set_title(f"{run.name}: goal {ev.run_goal(run)}", fontsize=10, color=INK, loc="left")
    p = out / f"{run.session}_run_{run.trial:03d}_topdown.png"        # one file per session and run (runs repeat across sessions)
    if p.exists():
        raise SystemExit(f"{p.name} already written: the same session given twice?")
    fig.tight_layout()
    fig.savefig(p, facecolor=SURFACE)
    plt.close(fig)
    return p


def ankle_of(bridge: Path) -> float:
    p = bridge / "config_used" / "perception.json"
    return float(json.loads(p.read_text(encoding="utf-8"))["ankle_height_m"]) if p.exists() else 0.0


def camera_height_of(unity: Path) -> float:
    """The 360 camera height the Unity session ran with (its copy of robot_unity_v4.json, camera_360.height_m)."""
    p = unity / "config_used" / "robot_unity_v4.json"
    return float(json.loads(p.read_text(encoding="utf-8"))["camera_360"]["height_m"])


def distance_without_and_with(est_m: float, h_cam: float, ankle_run: float, ankle_measured: float) -> tuple:
    """From the same pixels: the estimate with the ankles taken as floor points (before P1), and with the measured ankle height
    subtracted (P1). est_m was computed with ankle_run (0 before P1)."""
    without = est_m * h_cam / (h_cam - ankle_run)
    return without, without * (h_cam - ankle_measured) / h_cam


def main(argv=None) -> None:
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--session", nargs=2, action="append", required=True, metavar=("UNITY", "BRIDGE"))
    a = ap.parse_args(argv)
    import decision_io as dio
    pairs = [(Path(u).resolve(), Path(b).resolve()) for u, b in a.session]
    runs = ev.load_sessions(pairs, gd.load_config())                   # development split only
    road = hv.load_roadmap(hv.roadmap_path(hv.load_control()[1]))
    res = ev.evaluate(runs, road=road)
    jl = res["junction_level"]
    trials_cfg = json.loads((RV / "configs/trials.json").read_text(encoding="utf-8"))
    out = dio.new_run_dir({"paths": {"output_root": trials_cfg["output_root"]}}, "paper_v4")   # new timestamped folder, never reused
    report = {"sessions": [f"{u.name} + {b.name}" for u, b in pairs], "runs": len(runs), "figures": []}
    used = out / "config_used"
    used.mkdir()
    for rel in ("configs/v4/perception.json", "configs/v4/eval_dev.json", "configs/v4/gt_eval.json", "configs/v4/roadmap.json",
                "configs/v4/gesture_data.json"):
        (used / Path(rel).name).write_bytes((RV / rel).read_bytes())
    dio.write_json(out / "run.json", {"git": dio.git_info(), "script": "paper_v4/figures_v4.py", "sessions": report["sessions"],
                                      "note": "result-neutral: reads saved development outputs only; decides nothing, changes no config"})

    # E1
    dec = {u: decisions(b) for u, b in pairs}
    for run in runs:
        dialogs = [d for d in jl["dialog_detail"] if d["run"] == run.name]
        for d, rec in zip(dialogs, run.junctions):
            d["asks_log"] = rec.get("asks_log", [])
        report["figures"].append(topdown(run, dec[run.unity_dir].get(run.trial, []), dialogs, out, plt).name)

    # E2: before / after the ankle correction, from the same pixels
    ankles = {b.name: ankle_of(b) for _, b in pairs}               # what each session ran with
    heights = {u.name: camera_height_of(u) for u, _ in pairs}
    measured = float(json.loads((RV / "configs/v4/perception.json").read_text(encoding="utf-8"))["ankle_height_m"])
    pts = []
    for s in jl["standoff"]["detail"]:
        if s["est_m"] is None:
            continue
        unity, bridge = next((u, b) for u, b in pairs if s["run"].startswith(u.name + "/"))
        ank = ankles[bridge.name]
        without, with_c = distance_without_and_with(s["est_m"], heights[unity.name], ank, measured)
        pts.append((s["true_m"], without, with_c, ank, s["look"]))
    fig, ax = plt.subplots(figsize=(5.4, 5.0), dpi=150)
    fig.patch.set_facecolor(SURFACE)
    ax.set_facecolor(SURFACE)
    if pts:
        lo, hi = min(min(p[:3]) for p in pts) - 0.1, max(max(p[:3]) for p in pts) + 0.1
        ax.plot([lo, hi], [lo, hi], color=GRID, lw=1, zorder=1)
        ax.scatter([p[0] for p in pts], [p[1] for p in pts], s=64, color="#eb6834", edgecolors=SURFACE, linewidths=2,
                   label="ankles as floor points (before P1)", zorder=3)
        ax.scatter([p[0] for p in pts], [p[2] for p in pts], s=64, color="#2a78d6", edgecolors=SURFACE, linewidths=2,
                   label="ankle height subtracted (P1)", zorder=4)
        ax.set_xlim(lo, hi)
        ax.set_ylim(lo, hi)
    ax.set_xlabel("true distance at the ask (m)", color=MUTED)
    ax.set_ylabel("360 estimate (m)", color=MUTED)
    ax.tick_params(colors=MUTED, labelsize=8)
    for sp in ax.spines.values():
        sp.set_color(GRID)
    ax.legend(fontsize=8, frameon=False, labelcolor=INK, loc="upper left")
    ax.set_title("Distance at every ask", fontsize=10, color=INK, loc="left")
    fig.tight_layout()
    fig.savefig(out / "distance_accuracy.png", facecolor=SURFACE)
    plt.close(fig)

    def med_abs(i):
        v = sorted(abs(p[i] - p[0]) for p in pts)
        return round(v[len(v) // 2] if len(v) % 2 else 0.5 * (v[len(v) // 2 - 1] + v[len(v) // 2]), 3) if v else None
    report["distance"] = {"asks": len(pts), "median_abs_error_before_m": med_abs(1), "median_abs_error_after_m": med_abs(2),
                          "ankle_height_m_by_session": ankles, "camera_height_m_by_session": heights}

    # E3 per look
    looks = sorted({p["look"] for p in jl["pairs"]})
    rows = []
    for lk in looks:
        fr = res["per_look"].get(lk, {})
        ds = [d for d in jl["dialog_detail"] if d["look"] == lk]
        n = len(ds)
        rows.append({"look": lk, "frames": fr.get("frames"), "coverage": fr.get("coverage"), "accuracy_of_answered": fr.get("accuracy_of_answered"),
                     "dialogs": n, "correct_share": round(sum(d["outcome"] == "correct" for d in ds) / n, 3) if n else None,
                     "wrong": sum(d["outcome"] == "wrong" for d in ds), "abort_rate": round(sum(d["outcome"] == "abort" for d in ds) / n, 3) if n else None})
    with (out / "per_look.csv").open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0]) if rows else ["look"])
        w.writeheader()
        w.writerows(rows)
    md = ["| look | frames | coverage | accuracy of answered | dialogs | correct share | wrong | abort rate |", "|---|---|---|---|---|---|---|---|"]
    md += [f"| {r['look']} | {r['frames']} | {r['coverage']} | {r['accuracy_of_answered']} | {r['dialogs']} | {r['correct_share']} | {r['wrong']} | {r['abort_rate']} |" for r in rows]
    (out / "per_look.md").write_text("\n".join(md) + "\n", encoding="utf-8")
    report["per_look"] = rows

    # E5 junction confusion
    conf = defaultdict(Counter)
    for d in jl["dialog_detail"]:
        conf[(d["node"], d["true_branch"])][d["chosen"] or "abort"] += 1
    cols = sorted({c for v in conf.values() for c in v})
    with (out / "junction_confusion.csv").open("w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["node", "true_branch"] + cols)
        for (node, tb), c in sorted(conf.items()):
            w.writerow([node, tb] + [c[k] for k in cols])
    md = ["| node | true branch | " + " | ".join(cols) + " |", "|---|---|" + "---|" * len(cols)]
    md += [f"| {node} | {tb} | " + " | ".join(str(c[k]) for k in cols) + " |" for (node, tb), c in sorted(conf.items())]
    total = Counter()
    for (node, tb), c in conf.items():
        for k, v in c.items():
            total[(tb, k)] += v
    (out / "junction_confusion.md").write_text("\n".join(md) + "\n", encoding="utf-8")
    report["junction_confusion"] = {f"{n} {tb}": dict(c) for (n, tb), c in sorted(conf.items())}
    (out / "report.json").write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({k: report[k] for k in ("runs", "distance")}, indent=2))
    print(f"Folder: {out}")


if __name__ == "__main__":
    main()
