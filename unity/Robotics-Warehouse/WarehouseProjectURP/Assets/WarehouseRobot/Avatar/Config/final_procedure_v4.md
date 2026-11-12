# v4 freeze and finals: the procedure (for Nusrat)

Written 2026-11-13 after Stage F (commit 2b14857). Nothing here has been run: no freeze, no final. The assistant never writes
`robot_vision/configs/v4/frozen.json`, never runs `freeze_v4.py --freeze` and never starts a final.

## 1. Decide B7 with Anisha, then fill `test_assignment`

Read-only check of 2026-11-13 (AUDIT.md section 15): Anisha's unchanged `guard_run` accepts only test data in a final evaluation.

| plan | zoom_on, zoom_off, bystanders | unseen_look |
|---|---|---|
| (a) development looks + development clips; unseen_look sunbox_f2 + test clips | refused | accepted |
| (b) sunbox_f2 + test clips everywhere | accepted | accepted |
| B7 as recorded (development looks + test clips) | refused (mixed) | accepted |

Only plan (b) passes both guards unchanged. Any other plan needs a change in Anisha's `data_splits_v4.guard_run` first.

Once decided:
1. Anisha (or you, under the CLAUDE.local.md exception, named in the task) fills `final_plan.json` `test_assignment` with what each setting
   uses. Python only checks that it is not null; a readable form is one object per setting, e.g. for plan (b):
   `{"zoom_on": {"looks": ["sunbox_f2"], "clips": ["point_mixamo_02", "proceed_ik_03"]}, "zoom_off": {...}, "bystanders": {...},
   "unseen_look": {...}}` (the clips are those of the direction scenario: POINT and PROCEED).
2. Unity follows it in a declared change (dated entry in `upgrade_design.md` section 13, then the code): `final_v4.json` `look_split` per
   setting (plan (b): `"test"` for all four) and the B7 test in `FinalGuardV4Tests`. Both suites, commit.
3. Fill `unity_files_and_guard` (B9: "final_v4.json freeze_files, FinalGuardV4") and `acceptance_criteria` (B11, the draft in AUDIT.md
   section 15 once Anisha agrees). `freeze_v4.py` refuses to freeze while any of the three is null.

## 2. Before the freeze: the B9 files must reach `frozen.json`

`freeze_v4.py` hashes `configs/v4/*.json`, the v3 files v4 reads and the models, **not the Unity files**. The Unity final guard refuses
a final unless every file of `final_v4.json` `freeze_files` is recorded in `frozen.json` (by its repository path, LF-normalised SHA-256,
in any hash table). So `freeze_v4.py` needs a small change first (Anisha's file): read `freeze_files` from
`unity/.../Avatar/Config/final_v4.json` and record them, e.g. under `"unity_files": {path: sha256}`, plus a test in
`tests/test_v4_frozen.py`. Without it no final can start.

## 3. The freeze (you, by hand)

From `robot_vision\`, on the commit to be frozen, with a clean tree:

```powershell
.\.venv\Scripts\python.exe freeze_v4.py              # report: blanks, files, mismatches; must show no blank and no mismatch
.\.venv\Scripts\python.exe freeze_v4.py --freeze     # writes frozen.json once ("frozen": true); never overwritten
.\.venv\Scripts\python.exe -m unittest discover -s tests; if ($LASTEXITCODE -eq 0) { git add configs/v4/frozen.json; git commit -m "v4 freeze" }
```

Then the Unity Edit Mode tests. `FinalGuardV4Tests.Guard_TheRealRepositoryRefusesEveryFinalToday` is ignored from then on (it says so).

## 4. A batch-mode check first (development, 3 runs)

No v4 session has run in batch mode yet (D2 to D4 ran in the Editor window). Before the first final, one 3-run development session in
batch mode on the frozen commit confirms both cameras, the bridge and the timing. In batch mode the HUD (IMGUI) and the `-checkDir`
screenshots are not drawn: display only, nothing a result reads.

```powershell
# robot_vision\ : terminal 1
.\.venv\Scripts\python.exe launch_prep.py --task Task2 --trials 3
.\.venv\Scripts\python.exe -m bridge.server --mode guide --task Task2 --perception vision --config configs/v4/bridge.json --resource-log --exit-on-disconnect
# repository root: terminal 2, once the server says "listening"
& "$env:ProgramFiles\Unity\Hub\Editor\2022.3.62f3\Editor\Unity.exe" -batchmode -projectPath "unity\Robotics-Warehouse\WarehouseProjectURP" -executeMethod WarehouseRobot.ScenarioEditor.TrialPlayV4.Run -trialTimeout 3000 -logFile "$env:TEMP\unity_v4_batch_check.log"
# robot_vision\ : afterwards
.\.venv\Scripts\python.exe launch_prep.py --cleanup
```

## 5. The finals: one setting at a time, each once

Order: `zoom_on`, `zoom_off`, `bystanders`, `unseen_look`. Each setting runs once (20 runs, seed 2, timeout 270 s, success 0.3 m, all
from `final_plan.json`). **Python marks a setting as run as soon as one trial has finished** (`FINAL_RUN_DONE.json`), so an interrupted
final cannot be restarted without a repetition declared in AUDIT.md first; Unity marks it after the last run (`UNITY_FINAL_DONE.json`).

Before each setting, the run protocol: other programs closed (Chrome, the Claude app, the NVIDIA overlay, WSL / vmmem, warp-svc), power
mode Best performance on mains, no `robot_vision\configs\trials.local.json`. Write down the free memory and what still runs.

| setting | `--control-config` |
|---|---|
| zoom_on | `configs/v4/control_zoom_on.json` |
| zoom_off | `configs/v4/control_zoom_off.json` |
| bystanders | `configs/v4/control_zoom_on.json` |
| unseen_look | `configs/v4/control_zoom_on.json` |

```powershell
# robot_vision\ : terminal 1 (example zoom_on)
.\.venv\Scripts\python.exe -m bridge.server --mode guide --task Task2 --perception vision --config configs/v4/bridge.json --control-config configs/v4/control_zoom_on.json --final-setting zoom_on --resource-log --exit-on-disconnect
# repository root: terminal 2, once the server says "listening"
& "$env:ProgramFiles\Unity\Hub\Editor\2022.3.62f3\Editor\Unity.exe" -batchmode -projectPath "unity\Robotics-Warehouse\WarehouseProjectURP" -executeMethod WarehouseRobot.ScenarioEditor.TrialPlayV4.Run -finalSetting zoom_on -trialTimeout 7200 -logFile "$env:TEMP\unity_v4_final_zoom_on.log"
```

Unity refuses (and writes nothing) unless the guard passes; the reasons are in the log line `[TrialRunnerV4] final <setting> refused: ...`.

## 6. Checks after each setting (the B11 draft), before the next one

From `robot_vision\`, with `U` = `outputs\trials_final_Task2_<setting>_<time>` and `B` = the matching `outputs\bridge_guide_<time>`:

```powershell
.\.venv\Scripts\python.exe gt_path.py session $U                                   # 1. leak test, Unity and Python
Get-ChildItem $U -Directory -Filter run_* | ForEach-Object { .\.venv\Scripts\python.exe gt_path.py run $_.FullName; .\.venv\Scripts\python.exe gesture_data.py "$($_.FullName)\truth.jsonl" }   # 3.
```

2. `results_unity.csv` has 20 rows; 20 `run_###` and 20 `python_trial_###.json`; `UNITY_FINAL_DONE.json` in `U`; `FINAL_RUN_DONE.json`
   and `summary.json` in `B`. 4. `B\summary.json` `watchdog.stops_reported_by_unity` is 0. 5. `B\run_info.json` (machine state) and
   `B\resources.csv` exist; add the free memory and programs you wrote down.

Only then the evaluation of that setting, once (it writes `FINAL_DONE.json` and cannot be repeated):

```powershell
.\.venv\Scripts\python.exe hri_eval_final_v4.py --setting zoom_on --session $U $B
```

After all four: `hri_analysis_v4.py --final --session NAME UNITY BRIDGE ...` (may be re-run into a new folder), and the results
archive. Stop and report any failed check instead of running the next setting.
