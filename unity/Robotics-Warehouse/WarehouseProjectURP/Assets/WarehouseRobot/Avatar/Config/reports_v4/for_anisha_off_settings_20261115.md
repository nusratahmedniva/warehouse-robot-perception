# For Anisha: the detection-off final settings, Unity side (2026-11-15)

From Nusrat's Unity side, branch `nusrat/v4-stop-session`, the commit that adds this note's copy in `Avatar/Config/reports_v4/` (declared in `Avatar/Config/experiments_ab.md` section 13
part A). None of your files was changed. Nothing was frozen and no final was run.

## What Unity now has (your names, used exactly)

| setting | Unity final config | `lie_detection` | `python_control` (= your `FINAL_CONTROL`) |
|---|---|---|---|
| `B1_off` | `sessions/final_ab_B1_off.json` | off | `configs/v4/experiments/control_lie_off_a1.json` |
| `B2_right_off` | `sessions/final_ab_B2_right_off.json` | off | `configs/v4/experiments/control_lie_off_a2_right.json` |
| `B3_off` | `sessions/final_ab_B3_off.json` | off | `configs/v4/experiments/control_lie_off.json` |
| `B4_off` | `sessions/final_ab_B4_off.json` | off | `configs/v4/experiments/control_lie_off.json` |

- **Same as the on twin:**
  - Each config is its on twin's with only `lie_detection` and `python_control` changed (an Edit Mode test pins this).
  - Unity runs it exactly as the twin: same experiment, side, test looks and clips, seed 2. So the goals, placements and liars are the
    same run by run.
- **`final_v4.json`:**
  - `settings` has 13 entries (the four after the nine).
  - `freeze_files` has 28 (+ the four configs).
  - Your `freeze_v4.unity_files` reads it unchanged.
- **Unity's `session.json` of an off final:**
  - `experiment` "B1" / "B2" / "B3" / "B4";
  - `set` "B";
  - `lie_probability` 0.2;
  - `final_setting` "B1_off" etc.
  - This is what your `check_setting` compares (16.16 decision 7). `lie_detection` is still not written (as you noted); the bridge's
    control file is the record.
- **Guard:**
  - `FinalExperimentV4.SettingName` adds `_off` when `lie_detection` is "off", so a `B1` config switched off is refused under `B1`.
  - Markers are matched by exact name: a `B1` marker never blocks `B1_off`, and the reverse (tested).
- **Launcher:**
  - `finals_v4/run_session_v4.ps1 -Experiment B1 -LieDetection off` runs `B1_off`: Unity `-finalSetting B1_off`, server
    `--final-setting B1_off --control-config configs/v4/experiments/control_lie_off_a1.json`.
  - `-Rehearsal` runs Unity `-experiment B1` with the off control file.
  - `-DryRun` for all four today: the only refusals are "not on main", "tree not clean" and "frozen.json is not frozen".
    `final_plan.json` and `FINAL_CONTROL` know each setting with the same control file.

## Matrix and time (13 settings x 20 runs = 260 runs)

Method and numbers of `experiments_ab.md` section 7. A detection-off run = the on run divided by your simulator's on/off factor (16.13.1).
No experiment run has completed in Unity yet, so these are estimates.

| setting | mean run (s) | longest run (s) | session (min) |
|---|---|---|---|
| `B1_off` | 93 | 93 | 38 |
| `B2_right_off` | 92 | 92 | 38 |
| `B3_off` | 141 | 171 | 55 |
| `B4_off` | 140 | 171 | 54 |
| the nine on settings (section 7) | | | 557 |
| **total** | | | **742 min, about 12.4 h** |

**Proposed four sittings** (your 16.17 item 1: about 3 h each, each B with its off partner, A spread). The order is Nusrat's, to be
recorded before the first final:

| sitting | settings, in order | hours |
|---|---|---|
| 1 | `B3`, `B3_off`, `A2_right` | 3.1 |
| 2 | `B4_off`, `B4`, `A2_left` | 3.1 |
| 3 | `B1`, `B1_off`, `A1`, `A4` | 3.4 |
| 4 | `B2_right_off`, `B2_right`, `A3` | 2.8 |

## What your side still needs (nothing here is done by Nusrat)

1. **Timeout rule (16.16 decision 4):** it takes the longest SUCCESSFUL development run "made with the same configs as the finals".
   - The off settings use the off control files, so development (rehearsal) runs with detection off are needed too, or the rule should
     say whether the on runs cover the off settings.
   - Off runs are shorter (estimate above), so they cannot raise the value if the on runs are included.
   - Please decide which sessions count.
2. **The false-STOP rule** (16.17 item 3): the STOP session of section 13 part B is recorded for it; its zip comes separately. The
   recorded counts differ from your 16.16 decision 3: 13 STOPs per look (5 held per arm + 3 while driving), not 20. Criterion (a) is n
   of n, so the n changes. Please say whether that suffices or a second STOP session should add 7 per look.
3. **Sittings:** confirm the four sittings above (or change them) before the first final.
4. **Nothing else found missing for the off settings:**
   - `final_plan.json` (13 settings, `test_assignment`), `FINAL_CONTROL`, `preflight_final` / `control_problems`, `FROZEN_EXTRA` (the
     off control files) and the exporter's B on/off comparison already cover them.
   - Unity's side needs no Python change.
