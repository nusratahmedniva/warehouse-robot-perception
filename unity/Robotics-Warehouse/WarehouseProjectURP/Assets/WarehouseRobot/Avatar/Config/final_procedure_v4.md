# v4 freeze and finals: the procedure (for Nusrat)

Updated 2026-11-13 (pre-freeze completion). Nothing here has been run yet: no rehearsal on main, no freeze, no final. The assistant never
writes `robot_vision/configs/v4/frozen.json`, never runs `freeze_v4.py --freeze`, never pushes and never starts a final.

> **2026-11-14: the finals are now the experiments A/B** (`experiments_ab.md` section 7). The settings `zoom_on`, `zoom_off`, `bystanders`,
> `zoom_on_repeat` below are **superseded** (`final_v4.json` `superseded_settings`; the Unity guard and the launcher refuse them). The order of the
> procedure (merge, rehearsal on main, freeze by hand on a fresh branch, finals on main, each setting once) is unchanged; only the setting names and
> the launcher arguments differ. The final matrix: `A1`, `A2_right`, `A2_left`, `A3`, `A4`, `B1`, `B2_right`, `B3`, `B4` (sittings: section 7).
> Before the freeze Anisha adds the nine settings to `final_plan.json` and `FINAL_CONTROL`, and the experiment control and map files to the freeze
> (`robot_vision/outputs/for_anisha_finals_ab_*.md`). From the repository root:
>
> ```powershell
> # a rehearsal (development looks and clips, dev seed; -Trials N), e.g. A2 with the left turn:
> .\finals_v4\run_session_v4.ps1 -Experiment A2 -Side left -Rehearsal -Trials 3 -DryRun   # then without -DryRun
> # a final (once per setting, on main, clean tree, frozen), e.g. B3:
> .\finals_v4\run_session_v4.ps1 -Experiment B3 -DryRun                                   # then without -DryRun
> ```
>
> `-DryRun` lists every reason a real run would be refused now. After a valid final the launcher prints the evaluation and CSV export commands
> (Anisha's tools, run once). The avatar experiment runs once after the last final (`experiments_ab.md` section 8).

## 0. Decided and in place

- **B7 = plan (b), confirmed by Anisha on 2026-11-13:** every final uses sunbox_f2 + the test clips; in bystanders every person wears sunbox_f2.
- **The fourth setting is `zoom_on_repeat`** (renamed from unseen_look on 2026-11-13): a repeat of zoom_on. RQ4 (an unseen look) is answered by
  comparing the finals with the development results; the development numbers are optimistic (AUDIT.md section 15).
- **B9:** `final_plan.json` `unity_files_and_guard` names `final_v4.json` (`freeze_files`, 12 Unity files); `freeze_v4.py` records them under
  `unity_files` in `frozen.json`, which the Unity guard reads.
- **B11 = validity only, confirmed by Anisha and updated on 2026-11-13:** seven criteria in `final_plan.json` `acceptance_criteria` (leak test,
  frozen hashes, split guard, all 20 runs present, every outcome recorded, truth and run files accepted, run protocol recorded). A watchdog stop
  is a RESULT (a stop, or the failure, of its run), never a reason for invalidity. A setting that fails a criterion is reported as invalid and
  is **never rerun**. `finals_v4/check_session_v4.ps1` checks them.
- **The freeze is run by Nusrat, by hand** (agreed with Anisha on 2026-11-13; CLAUDE.md).
- **Finals run in the Unity Editor window** (no `-batchmode`; batch mode hangs before the leak test, `TrialRunnerV4.cs` line 481), as D2 to D4.
- **`finals_v4/run_session_v4.ps1 -Setting NAME [-Rehearsal] [-DryRun]`** runs one session end to end: the run-protocol note, `launch_prep`,
  the server (waited for until "listening"), Unity in the Editor window (waited for until it quits), the server's exit on the disconnect,
  `launch_prep --cleanup` (rehearsal only) and the B11 check. A final is never retried and nothing is rerun. It does NOT run the final
  evaluation: it prints that command after a valid check. Server and Unity output go to `robot_vision\outputs\run_session_<label>_<time>_*.log`.

Order: **1** merge to main, **2** rehearsal on main, **3** freeze on a fresh branch (PR, CI green, merge), **4** the finals on main in the order
zoom_on, zoom_off, bystanders, zoom_on_repeat, each followed by its check and evaluation.

## 1. Merge this branch into main

```powershell
git push -u origin nusrat/v4-phase3b-to-final-setup
```

Open a pull request into `main` on GitHub, wait for CI (`tests.yml`) to pass, merge it. Then locally:

```powershell
git switch main
git pull
git status          # clean, on main
```

## 2. Rehearsal on main (development data; not a result)

Proves the launcher, the Editor-window mode, the protocol note and the checks end to end. `sessions/rehearsal_zoom_on.json` equals the zoom_on
final config except the development looks (sunbox_m1, sunbox_f1 alternating) and development clips; the session is a development session
(seed 1, development timeout 420 s, 3 runs by default). Close the Unity Editor first (the launcher opens the project itself). From the
repository root:

```powershell
.\finals_v4\run_session_v4.ps1 -Setting zoom_on -Rehearsal -DryRun     # prints every command, runs nothing
.\finals_v4\run_session_v4.ps1 -Setting zoom_on -Rehearsal             # about 10 to 15 minutes; leave the machine alone
```

Expected at the end: criteria 1 and 3 to 7 `PASS`, criterion 2 `N/A` (nothing is frozen yet), "SESSION VALID" and "REHEARSAL VALID".
Any FAIL: stop and fix the cause before the freeze (a fix after the freeze breaks it). `robot_vision\configs\trials.local.json` must be gone
afterwards (`Test-Path robot_vision\configs\trials.local.json` gives False); the rehearsal's folders are under `robot_vision\outputs\`
(git-ignored) and stay there.

## 3. The freeze (you, by hand) on a fresh branch from up-to-date main

```powershell
git switch main
git pull
git switch -c nusrat/v4-freeze
cd robot_vision
.\.venv\Scripts\python.exe freeze_v4.py
#   check: "frozen: False", "blanks in final_plan.json: none", the 12 unity/... files listed, both models "present", "problems: none"
.\.venv\Scripts\python.exe freeze_v4.py --freeze
#   prints: frozen at <time> (commit <hash>): 15 v4 configs, 5 v3 files, 12 Unity files, 2 model files
.\.venv\Scripts\python.exe freeze_v4.py
#   now: "frozen: True" and "problems: none"
git status --short
#   exactly one line: " M robot_vision/configs/v4/frozen.json". Anything else: stop, do not commit.
```

Run both suites: Unity Test Runner, EditMode, Run All (all pass; `Guard_TheRealRepositoryRefusesEveryFinalToday` now shows "ignored", it
documents the state before the freeze), then Python and the commit:

```powershell
.\.venv\Scripts\python.exe -m unittest discover -s tests; if ($LASTEXITCODE -eq 0) { git add configs/v4/frozen.json; git commit -m "v4 freeze" }
git push -u origin nusrat/v4-freeze
```

Open a pull request into `main` (only `frozen.json` changes), wait for CI to pass, merge it. Then:

```powershell
git switch main
git pull
cd robot_vision
.\.venv\Scripts\python.exe freeze_v4.py        # "frozen: True", "problems: none" on main (exit code 0)
```

From now on any change to a v4 config, a v3 file v4 reads, a model or one of the 12 Unity files breaks the freeze (Python `freeze_v4.problems`,
the server's final mode, the final evaluation, the B11 check and the Unity guard all refuse).

## 4. The finals on main: zoom_on, zoom_off, bystanders, zoom_on_repeat

Each setting runs once, in this order, one at a time. Before each: **run protocol** (close Chrome, the Claude app, the NVIDIA overlay, WSL
(vmmem) and warp-svc; Windows power mode Best performance on mains), the Unity Editor closed, `git status` clean on main. Python marks a setting
as run as soon as one trial has finished (`FINAL_RUN_DONE.json`), Unity after its last run (`UNITY_FINAL_DONE.json`): an interrupted final
cannot be restarted. From the repository root:

```powershell
.\finals_v4\run_session_v4.ps1 -Setting zoom_on -DryRun     # check the commands (control file, --final-setting, -finalSetting)
.\finals_v4\run_session_v4.ps1 -Setting zoom_on             # 20 runs, about 50 to 60 minutes; leave the machine alone
```

The launcher refuses before anything starts when: not on main, tracked changes, a Unity Editor running, `trials.local.json` present, the
setting already run, or the server's final preflight refuses (not frozen, a hash changed, wrong control file). If Unity refuses, its log
(`robot_vision\outputs\run_session_final_zoom_on_<time>_unity.log`) has `[TrialRunnerV4] final zoom_on refused: ...` with every reason; fix
the reason, never edit the guard.

At the end the launcher prints the seven checks and either:
- **"FINAL zoom_on VALID"** and the evaluation command. Run it once, from `robot_vision\` (it writes `FINAL_DONE.json` and cannot be repeated):

  ```powershell
  .\.venv\Scripts\python.exe hri_eval_final_v4.py --setting zoom_on --session "<Unity session folder>" "<bridge run folder>"
  ```

- **"FINAL zoom_on INVALID"**: report the setting as invalid with the reasons; it is never rerun and not evaluated. Stop and read the reason
  before the next setting (a fix that changes a frozen file breaks the freeze and needs a declared change in AUDIT.md first).

If the launcher stops in the middle ("STOPPED: ..."), nothing is retried: write down the message, then run the check by hand on the folders
that exist (`.\finals_v4\check_session_v4.ps1 -U <session> -B <bridge> -Final -Protocol <note>`) and report the setting as it stands.

Then the same for `zoom_off`, `bystanders`, `zoom_on_repeat` (each with `-DryRun` first). The launcher picks each setting's control file
(`bridge/server.py` `FINAL_CONTROL`: zoom_off `configs/v4/control_zoom_off.json`, the others `configs/v4/control_zoom_on.json`).

## 5. After all four

`hri_analysis_v4.py --final --session NAME UNITY BRIDGE ...` (may be re-run into a new folder), the results archive, and the AUDIT.md entry with
every setting's validity, results (with coverage and intervals) and the run-protocol notes.
