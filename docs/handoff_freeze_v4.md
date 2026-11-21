# Hand-off to Nusrat (Niva): from step 5 to the freeze and the finals (2026-11-21; updated the same day for the interruption rule and the final zips, AUDIT 16.30 to 16.30.3)

Written by Anisha's side (Python), after the review of your step-5 data (AUDIT.md 16.28, 16.28.1) and the pre-freeze changes (16.27, 16.29, 16.29.1). Everything below is about what you do next, in this order. Commands are for Windows PowerShell, run from the repository root unless it says otherwise.

## 0. What changed since `affe652` (the commit your step-5 sessions ran on, apart from A1 on `e2c116f`)

Python side only. Nothing under `unity/` or `external/` changed, and no v3 file.

| change | where | what it means for you |
|---|---|---|
| **Stall dump OFF** (AUDIT 16.27) | `robot_vision/configs/v4/bridge.json` `timing.stall_dump` false; `bridge/timing_v4.py`, `bridge/server.py` | No `stall_tracebacks.txt` in a bridge run folder any more and no `faulthandler` call: the native crash you saw in B1 (python312.dll, 0xc0000005, inside the thread dump) cannot come from it. `loop_lag.csv` and the lag numbers in `summary.json` stay. |
| **Timeout 480 s** (AUDIT 16.29) | `robot_vision/configs/v4/final_plan.json` `timeout_s` 480 (record in `timeout_s_applied`) | From your step-5 runs by the declared rule: 1.5 x 301.4 s (A4 trial 3) = 452.2, up to 480 s. The finals use it; the development timeout stays 900 s. |
| **New log: which STOP reading was used** (AUDIT 16.29) | `stop_reading.jsonl` in every bridge run folder (next to `v4_log.jsonl`) | One row per control step. It makes C2s (the short-window STOP while the robot stands still) provable. **Instrument only: no decision changes.** `decisions.csv` has no new column. If one of your checks complains about the new file, tell me; nothing else reads it. |
| `final_guard_v4.py --timeout-from` | (already on `main` since `affe652`) | `python robot_vision\final_guard_v4.py --timeout-from <step-5 zip>` reproduces the 480 s from your zip. |
| **Interruption rule** (AUDIT 16.30.1) | `robot_vision/final_guard_v4.py`, `bridge/server.py` (`--resume-marker`), `hri_eval_final_v4.py`, `export_csv_v4.py`, `hri_eval_dev_v4.py` (`include`, default None) | A crash of the server, Unity or the machine in a final can be declared and the session **resumed once**; a started final can no longer be restarted silently (section 8). Nothing changes for a session that does not crash. |
| **Final zips** (AUDIT 16.30.2) | `robot_vision/final_zip_v4.py` | One zip per sitting and one for the avatar experiment, SHA-256 next to it (section 6). |
| Review and analysis | `AUDIT.md` 16.28, 16.28.1, 16.29, 16.29.1; `robot_vision/compare_sim_unity_v4.py` | Reading only. 16.28.1 replays your B3, B3_off, B4, B4_off runs in the simulator with your placement and liars: it reproduces the 0/12. |

The reader, the controller's decisions, every control and roadmap file and the T0 on and off settings are as they were in step 5.

## 1. Before anything else: the run protocol must be met (strict)

Your step-5 notes show that it was **not** fully met: Chrome (8 processes, about 330 MB) was running in 12 of the 13 sessions, and the launcher note records the power PLAN `AMD Ryzen Balanced` (the Windows power MODE is not in the note). For the smoke check, the avatar rehearsal and every final sitting:

- **Close Chrome and every other app** (also the browser helpers). The launcher's note lists what is still running ("programs on the watch list still running"): it must show **no `chrome`**. `nvcontainer` and `warp-svc` are services; if you cannot stop them, say so in your notes. VS Code and Claude Code closed too (free memory was 195 MB with them open in the smoke trial).
- **Windows power mode "Best performance"** (Settings > System > Power & battery), **recorded for every session**: the launcher does not record it, so put a screenshot of that page, or one line "power mode: Best performance, <time>", next to each session's run-protocol note (and in the zip you send). Also record the power plan name as before.
- Mains power, enough free memory (your step-5 minimum was 2005 MB), resource log on (it is).
- A session that runs outside this protocol is not discarded, but its run-protocol note must say what deviated, and I report it.

## 2. The smoke check with the stall dump OFF (3 development runs of ONE setting)

Setting: **B1**, because the crash happened there (about 6 minutes).

```powershell
.\finals_v4\run_session_v4.ps1 -Experiment B1 -Rehearsal -Trials 3
```

Then the session checks exactly as for your smoke trial of addendum 8 item 7 (setting name `smoke_t0_B1`). It passes when **all** of this holds:

1. the launcher says `REHEARSAL VALID` (exit 0) and `watchdog stops reported by Unity: 0`;
2. the Python server did not crash: the server `.err.log` has no traceback and **Event Viewer > Windows Logs > Application has no "Application Error" for `python.exe`** during the session;
3. in the bridge run folder there is `loop_lag.csv`, there is **no** `stall_tracebacks.txt`, `config_used\bridge.json` has `"stall_dump": false` in `timing`, and `summary.json` `event_loop_lag` has `"stall_dump": false`;
4. `stop_reading.jsonl` exists and has rows (`(Get-Content <bridge folder>\stop_reading.jsonl | Measure-Object).Count`), and at least one row says `"applies":true` with `"used":"reading_stopped"` (`Select-String -Path <bridge folder>\stop_reading.jsonl -Pattern '"used":"reading_stopped"' | Measure-Object`). A row with `"applies":false` while the robot moves is expected.

Send me: the zip of that session and its SHA-256, made as for step 5:

```powershell
robot_vision\.venv\Scripts\python.exe finals_v4\step5_zip_v4.py --prefix smoke_t0_ --out-dir <a folder OUTSIDE the repository>
```

(it writes `<zip>.sha256` next to the zip). Do not go on to the freeze if any of the four points fails: send me the zip anyway.

## 3. The avatar rehearsal Play part: fix it, repeat it, it must pass BEFORE the freeze

Your step-5 rehearsal check (`avatar_rehearsal_check_20261121_001920`): the **Edit part is clean**; the **Play part failed its format check**: Unity ended with `[LookCheckPlay] finished (1): timeout` after about an hour, 146 of 270 groups recorded, 124 groups missing (all of 7 looks: `sunbox_f_dress_red`, `sunbox_f_shirt_plaid`, `anime_f_01`, `anime_f_02_outfit_short`, `anime_f_03_bangs_parted`, `cartoon_boxo_01`, `sunbox_f_shirt_white`), and 122 groups with a timing problem (frame steps 0.085 to 0.118 s against 0.1 s). Please find why it timed out (more time for `-lookCheckTimeout`, fewer looks per run, or a slow step), repeat the Play part, run `avatar_rehearsal_check.py` again, and delete the frames after the check as before. **The check must pass (no missing group, no timing problem) before `freeze_v4.py --freeze`.** Send me `report.json` of the new check (the frames are deleted, as the blind rule says).

## 4. The freeze (you, by hand)

Only after sections 2 and 3 have passed **and the avatar-experiment looks are listed in `data_splits.json` (section 5: the freeze hashes that file, so it cannot be edited afterwards)**. From `robot_vision\`:

```powershell
.\.venv\Scripts\python.exe freeze_v4.py            # the read-only report first: blanks none, every file listed, models present
.\.venv\Scripts\python.exe freeze_v4.py --freeze   # YOU run this, by hand; nobody else
.\.venv\Scripts\python.exe freeze_v4.py            # afterwards: frozen, no problem
.\.venv\Scripts\python.exe -m unittest discover -s tests
```

The first report prints "the file list is out of date" (`frozen.json` lists 15 files, the freeze hashes 27): that is a diagnostic while unfrozen and **does not block** the freeze: `--freeze` writes the full list itself (AUDIT 16.29.1). Commit `frozen.json` on your own branch only if the whole suite passes. Send me: the commit hash, `frozen.json`, and the suite's last lines.

## 5. The avatar experiment

**Before the freeze (a reminder, a correction of the first version of this note: AUDIT 16.30.3):** `robot_vision/configs/v4/data_splits.json` lists only the 9 Sunbox looks and says the Anime, cartoon and Mixamo looks "are not listed here yet"; the guard refuses an unlisted name. The freeze hashes every `configs/v4/*.json`, so **those looks (and any clip of the experiment) must be in `data_splits.json`, each with its split, BEFORE `freeze_v4.py --freeze`**; after the freeze the file cannot change. **Still open: send me your list of look and clip names with the split you propose for each** (development or test); I decide the split, record it in AUDIT.md and enter it in its own commit, before any recording of those looks. The A/B finals do not depend on it.

The experiment itself runs after the freeze. Its protocol is still open (`docs/workflow_v4.md` section 14: which avatars, how many runs, what counts as "person detected" and "hand detected"): Anisha confirms it. When it is done, send the zip and its SHA-256 (section 6, `avatar`).

## 6. The four final sittings (260 runs)

Order and run order are yours (AUDIT 16.17): four sittings of about 3 h, **each B setting in the same sitting as its detection-off partner**, the A settings spread. A balanced plan from your step-5 durations (12.2 to 14.0 h in total; AUDIT 16.29.1):

| sitting | settings | estimate |
|---|---|---|
| 1 | B1, B1_off, B2_right, B2_right_off, A1 | 2.8 to 3.6 h |
| 2 | B3, B3_off, A2_right | 3.1 to 3.4 h |
| 3 | B4, B4_off, A2_left | 3.2 to 3.5 h |
| 4 | A3, A4 | 3.2 to 3.4 h |

A final is never retried and nothing is rerun (the run-once guards); the timeout is 480 s; the strict run protocol of section 1 applies to every session. Final sessions run without `-Rehearsal`:

```powershell
.\finals_v4\run_session_v4.ps1 -Experiment A3                        # a setting
.\finals_v4\run_session_v4.ps1 -Experiment B2 -Side right            # turn map: -Side right or left
.\finals_v4\run_session_v4.ps1 -Experiment B3 -LieDetection off      # the detection-off partner (B3_off)
```

### The zip of a sitting (AUDIT 16.30.2)

After EACH sitting send me ONE zip with its SHA-256, made by `final_zip_v4.py` (from `robot_vision\`, run it with the project venv; it reads `outputs\` and changes nothing):

```powershell
.\.venv\Scripts\python.exe final_zip_v4.py sitting --number 1 --settings B1 B1_off B2_right B2_right_off A1 --out-dir <a folder OUTSIDE the repository> --extra <power-mode screenshot or line> <notes on what deviated> <evidence files of an interruption>
.\.venv\Scripts\python.exe final_zip_v4.py verify <the zip>      # check it before you send it
```

- **Naming:** `final_sitting<N>_<YYYYMMDD_HHMMSS>.zip` (N = 1 to 4) and `<zip name>.sha256` next to it (`<hex>  <zip name>`); the avatar experiment: `avatar_experiment_<YYYYMMDD_HHMMSS>.zip` made with `final_zip_v4.py avatar --out-dir <folder> --folder <session folder> ... --extra ...`. Send the zip and the SHA-256 (print it in the message too).
- **Inside, per setting:** every Unity session folder of the setting (found by the `final_setting` in its `session.json`), every bridge run folder of the setting (`FINAL_SETTING.json`; with `stop_reading.jsonl`, `loop_lag.csv`, `config_used\`), the launcher's logs (`run_session_final_<setting>_<time>_*.log`) and run-protocol note (`run_protocol_final_<setting>_<time>.txt`), and the interruption, resume or invalid markers of the setting; under `extra\` what you pass with `--extra` (**the power-mode screenshot or line is required by section 1; the tool warns when there is no `--extra`**). `MANIFEST.json` lists every file with its SHA-256 and the warnings.
- **It refuses** (and writes nothing) a setting with no Unity session or no bridge folder, and an unexpected number of parts (one; two only after a declared and resumed interruption). **Missing launcher logs or notes are warnings**, written into `MANIFEST.json` and printed: read them before you send.
- I read the zip in place (`zipfile`); nothing is extracted or copied into the repository. `step5_zip_v4.py` is for the step-5 development sessions only and is not used for the finals.
- The final evaluation, the CSV export and the statistics are mine (step 10); the launcher prints their commands after a valid check; do not run them.

## 7. Open items, so that nothing is a surprise

- Loop-lag maxima over 100 ms (A1 146 ms, B1_off 178 ms) coincided with the two stall dumps of step 5; the dump is now off. If a final session shows one without a dump, it is a result and I will report it, not a reason to rerun.
- The 5-avatar rule is not triggered (at most 3 avatars were active in any step-5 run; the limit stays 6).
- B3 and B4 (on and off) failed all 12 step-5 runs. That is the declared limitation (a lie toward a valid branch is not detectable with two workers per node and consistent liars) plus the development seed's lie draw; the simulator reproduces it with your placement and liars (AUDIT 16.28.1). Nothing is to be changed for it before the finals.

## 8. If a final is interrupted: the procedure (AUDIT 16.30.1)

**Interruption = infrastructure only:** the Python server or Unity dies, or the machine fails, BEFORE a run finishes. A run that ended with any outcome (success, wrong goal, abort, timeout, collision) is a result, never an interruption. Completed runs stand. The interrupted run has no outcome and is not scored. The session may be **resumed ONCE** from that run. A **second** interruption in the same setting makes the setting INVALID: it is reported with its reason and never rerun.

Do exactly this, in this order. Do not rerun the launcher, restart the server, delete or rename any folder before step 5.

1. **Stop.** Close Unity and the server windows. Write down the time and what you saw.
2. **Is it infrastructure?** The python process died (Event Viewer "Application Error"), Unity crashed or hung until you killed it, the PC rebooted or lost power. If a run had ended with an outcome (look for `truth_run<k>.json`), it is not an interruption: the session simply stands as it is; tell me.
3. **Collect the evidence** into one folder (any place): the Event Viewer entry exported (Windows Logs > Application > right-click the entry > Save Selected Events), the server `.err.log` and `.log`, the Unity log of the session (`run_session_final_<setting>_<time>_*.log`) and the Unity `Editor.log`, a screenshot if there is one.
4. **Find the interrupted run k:** the first run of the Unity session folder (`trials_final_Task2_<setting>_<time>`) that has no `truth_run<k>.json` (runs 1 to k-1 have one).
5. **Declare it** (from `robot_vision\`; the tool checks that runs 1 to k-1 have an outcome and Python output and that run k has none, and that the evidence exists):
   ```powershell
   .\.venv\Scripts\python.exe final_guard_v4.py --declare-interruption B3 --run 11 --reason "python.exe crashed 0xc0000005" --evidence <evidence folder or files> --unity-folder outputs\trials_final_Task2_B3_<time> --bridge-folder outputs\bridge_guide_<time>
   .\.venv\Scripts\python.exe final_guard_v4.py --status
   ```
   It writes `outputs\final_interruption_<setting>_<time>\FINAL_INTERRUPTION.json`. **If it refuses, read the message, do not work around it, and send it to me.** The server (and the launcher it starts) now refuses to start this setting again *without* that marker: a started final is never restarted silently.
6. **Resume once:** the launcher and Unity start the resumed session at run k with `--resume-marker outputs\final_interruption_<setting>_<time>` passed to the server. What Unity must do is the list in AUDIT 16.30.1 (your part; I do not edit `unity/` or the launcher): same seed, same goal order, same configs and frozen hashes, run numbers continue at k, `session.json` records `resume_from_run` and `resume_of`, and Unity refuses to start for a different seed or goal order, a second resume, or a finished or invalid setting. **Until that is built, a crash cannot be resumed: stop after step 5 and report.** (The Python side is tested with synthetic sessions only; a rehearsal cannot use `--resume-marker` because it belongs to `--final-setting`, so the first real use is in a final. Test your Unity side on a development setting as far as it goes.)
7. **Run protocol for the resumed part** as for any session (other apps closed, Best performance, note and power-mode line).
8. **A second crash in the resumed part:** stop. Run the same `--declare-interruption` command with the **resumed** session's two folders and the new evidence: it writes `FINAL_INVALID.json` instead. No third part, nothing repaired. Send me the evidence.
9. **Send the sitting zip** (section 6) as usual: it contains both parts, the declaration and the resume marker; add the evidence files with `--extra`. The evaluation and the export (mine) take the two parts with `--session` twice and score them as ONE session: runs 1 to k-1 from part 1, runs k on from part 2; the interrupted run is listed, not scored; every interruption and resume is in the report.

If the server crashed hard and left no `FINAL_RUN_DONE.json`, step 5 is still required: the start marker `FINAL_SETTING.json` of the first part is what blocks the silent restart.
