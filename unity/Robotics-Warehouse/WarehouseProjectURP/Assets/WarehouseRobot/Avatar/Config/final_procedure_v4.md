# v4 freeze and finals: the procedure (for Nusrat)

Updated 2026-11-13 after commit 9e58419 (B7 = plan (b), B9 in the freeze, B11 adopted; decided by Nusrat in Anisha's absence, pending her
confirmation). Nothing here has been run: no freeze, no final. The assistant never writes `robot_vision/configs/v4/frozen.json`, never
runs `freeze_v4.py --freeze` and never starts a final.

## 0. Decided and in place

- **B7 = plan (b):** every final uses sunbox_f2 + the test clips; unseen_look repeats zoom_on; in bystanders every person wears sunbox_f2.
  `final_plan.json` `test_assignment` is filled; `final_v4.json` `look_split` is "test" everywhere.
- **B9:** `final_plan.json` `unity_files_and_guard` names `final_v4.json` (`freeze_files`, 12 Unity files); `freeze_v4.py` records them
  under `unity_files` in `frozen.json`, which the Unity guard reads.
- **B11:** `final_plan.json` `acceptance_criteria` (the five validity criteria); `finals_v4/check_session_v4.ps1` checks them.
- `python freeze_v4.py` (report only) shows no blank and no problem.

## 1. OPEN: batch mode does not work (decide before the freeze)

The batch-mode rehearsal of 2026-11-13 hung before the leak test (`TrialRunnerV4.cs` line 481, `WaitForEndOfFrame` never returns in
`-batchmode`; AUDIT.md section 15). Two ways on:
- **(a) Finals in the Editor window** (no `-batchmode`), as every development session D2 to D4 was recorded: proven, same timing
  conditions as the development data. Needs only a 3-run rehearsal in that mode (section 3).
- **(b) Make batch mode work:** a declared code change (the wait before the leak test), both suites, then the batch rehearsal again;
  further batch-only problems are possible and the timing differs from the development sessions.

The commands below are for (a). For (b) add `-batchmode` to the Unity command once the change and its rehearsal pass.

## 2. The freeze (you, by hand)

From `robot_vision\`, on the commit to be frozen, with a clean tree (`git status` shows nothing to commit):

```powershell
.\.venv\Scripts\python.exe freeze_v4.py
#   check: "frozen: False", "blanks in final_plan.json: none", the 12 unity/... files listed, both models "present", "problems: none"
.\.venv\Scripts\python.exe freeze_v4.py --freeze
#   prints: frozen at <time> (commit <hash>): 15 v4 configs, 5 v3 files, 12 Unity files, 2 model files
```

Verify the freeze:

```powershell
.\.venv\Scripts\python.exe freeze_v4.py
#   now: "frozen: True" and "problems: none" (exit code 0)
.\.venv\Scripts\python.exe -c "import json; d=json.load(open('configs/v4/frozen.json')); print(d['frozen'], d['git_commit'], len(d['sha256']), len(d['v3_dependencies']), len(d['unity_files']), len(d['models']))"
#   True <hash> 15 5 12 2
.\.venv\Scripts\python.exe -m unittest discover -s tests; if ($LASTEXITCODE -eq 0) { git add configs/v4/frozen.json; git commit -m "v4 freeze" }
```

Then the Unity Edit Mode tests (Test Runner, EditMode, all must pass; `Guard_TheRealRepositoryRefusesEveryFinalToday` now reports
"ignored": it documents the state before the freeze). From now on any change to a v4 config, a v3 file v4 reads, a model or one of the
12 Unity files breaks the freeze (Python `freeze_v4.problems`, the server's final mode, the final evaluation and the Unity guard refuse).

## 3. Rehearsal in the mode of the finals (development, 3 runs), after the freeze

Proves the mode, the protocol note and the checks end to end on the frozen commit. Not a result. Terminal 1 (`robot_vision\`):

```powershell
..\finals_v4\run_protocol_v4.ps1 -Label rehearsal_zoom_on        # prints the note's path: keep it
.\.venv\Scripts\python.exe launch_prep.py --task Task2 --trials 3
.\.venv\Scripts\python.exe -m bridge.server --mode guide --task Task2 --perception vision --config configs/v4/bridge.json --control-config configs/v4/control_zoom_on.json --resource-log --exit-on-disconnect
```

Terminal 2 (repository root), once the server says "listening":

```powershell
& "$env:ProgramFiles\Unity\Hub\Editor\2022.3.62f3\Editor\Unity.exe" -projectPath "unity\Robotics-Warehouse\WarehouseProjectURP" -executeMethod WarehouseRobot.ScenarioEditor.TrialPlayV4.Run -workersConfig Assets/WarehouseRobot/Avatar/Config/sessions/final_zoom_on.json -trialTimeout 3000 -logFile "$env:TEMP\unity_v4_rehearsal.log"
```

Afterwards (terminal 1): `.\.venv\Scripts\python.exe launch_prep.py --cleanup`, then the checks of section 5 with `-Runs 3` and without
`-Final`. All five must PASS.

## 4. The first final: zoom_on

Run protocol first: close Chrome, the Claude app, the NVIDIA overlay, WSL (vmmem) and warp-svc; Windows power mode Best performance on
mains; no `robot_vision\configs\trials.local.json`. Python marks a setting as run as soon as one trial has finished
(`FINAL_RUN_DONE.json`): an interrupted final cannot be restarted without a repetition declared in AUDIT.md first.

Terminal 1 (`robot_vision\`):

```powershell
..\finals_v4\run_protocol_v4.ps1 -Label final_zoom_on               # keep the printed path for check 5
.\.venv\Scripts\python.exe -m bridge.server --mode guide --task Task2 --perception vision --config configs/v4/bridge.json --control-config configs/v4/control_zoom_on.json --final-setting zoom_on --resource-log --exit-on-disconnect
```

Terminal 2 (repository root), once the server says "listening":

```powershell
& "$env:ProgramFiles\Unity\Hub\Editor\2022.3.62f3\Editor\Unity.exe" -projectPath "unity\Robotics-Warehouse\WarehouseProjectURP" -executeMethod WarehouseRobot.ScenarioEditor.TrialPlayV4.Run -finalSetting zoom_on -trialTimeout 7200 -logFile "$env:TEMP\unity_v4_final_zoom_on.log"
```

Leave the machine alone until Unity quits (20 runs, about 50 to 60 minutes). If Unity refuses, the log line
`[TrialRunnerV4] final zoom_on refused: ...` lists every reason and nothing was written; fix the reason, do not edit the guard.

Control files of the other settings (section 6): zoom_off `configs/v4/control_zoom_off.json`; bystanders and unseen_look
`configs/v4/control_zoom_on.json`.

## 5. The checks after the final (B11), before anything else

Terminal 1 (`robot_vision\`), with `U` the new `outputs\trials_final_Task2_zoom_on_<time>`, `B` the new `outputs\bridge_guide_<time>`
and `N` the protocol note:

```powershell
..\finals_v4\check_session_v4.ps1 -U $U -B $B -Runs 20 -Final -Protocol $N
#   PASS 1..5 and "SESSION VALID" (exit code 0). Any FAIL: stop, report it as invalid with the reason, do not evaluate, do not re-run.
```

Only then the evaluation, once (it writes `FINAL_DONE.json`; it cannot be repeated):

```powershell
.\.venv\Scripts\python.exe hri_eval_final_v4.py --setting zoom_on --session $U $B
```

## 6. The other settings

The same steps 4 and 5 for `zoom_off`, `bystanders`, `unseen_look` (unseen_look is the repeat of zoom_on), one at a time, each once.
After all four: `hri_analysis_v4.py --final --session NAME UNITY BRIDGE ...` (may be re-run into a new folder) and the results archive.
