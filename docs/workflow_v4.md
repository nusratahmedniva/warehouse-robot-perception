# Warehouse Robot Perception: Project Workflow (v4)

*Status as of 19 November 2026. This file is the starting point for a new reader. The full, dated record of every decision is in `AUDIT.md`; when this file and `AUDIT.md` disagree, `AUDIT.md` wins.*

---

## 1. What the project is

A robot in a virtual warehouse (Unity) has to reach a goal **B that it does not know**. Human-like avatar workers stand along the roads. At each junction the robot finds a worker, drives up to them, asks "Which direction?", reads their arm gesture with its cameras, and follows it. Python does all the perception and decision-making. Unity runs the world, the avatars and the robot's body.

The current study (v4) asks two big questions set by our faculty (13 November 2026):

1. **Avatar experiment (the main experiment).** Does the robot still detect the person and their hands reliably across different kinds of avatars (same body, male/female, different clothes and colours)?
2. **Experiments A and B (lying workers).** Can the robot reach the goal when every worker is truthful (Set A), and can it **detect lies from evidence and correct itself** when each worker lies with 20 % probability (Set B)? The robot never knows the goal, so it can only use what it sees.

---

## 2. v3 and v4

| | v3 (baseline) | v4 (current study) |
|---|---|---|
| Status | **Frozen** as release `v1.0`; results final | In development; freeze not yet run |
| Gestures | Fixed arm poses | Natural, moving gestures (POINT, WAIT, STOP, PROCEED) |
| People | One worker per stop | Several people, one commander; two workers per node |
| Configs | `robot_vision/configs/` | `robot_vision/configs/v4/` |
| Protocol | v2 | v3 (`docs/protocol_v3.md`), port 5005 |
| Results | Task 1: 10/10; Task 2: 10/10 (and 10/10 on a second machine) | Not yet run |

**Rule:** no v3 file is ever edited. v4 code extends v3 code (for example `ControllerV4` builds on v3's `Controller`), and the paper describes v4 as "v3 plus a list of declared differences" (`configs/v4/analysis.json`). Editing v3 would silently change v4 and break that comparison. We spend no effort on v3, and we do not touch it.

---

## 3. People and ownership

| Person | Owns | Never edits |
|---|---|---|
| **Anisha** (GitHub `anisha274`, Mac) | Python: `robot_vision/`, `docs/`, `AUDIT.md` sections 14 and 16, simulator, reader, controller, evaluation, CSV export, statistics, paper text | `unity/`, `external/` |
| **Nusrat (Niva)** (Windows PC, RTX 3060) | Unity: `unity/.../WarehouseRobot/`, avatars, clips, scenes, NavMesh, truth logger, final-run guard, `AUDIT.md` section 15, `finals_v4/` scripts, **running the finals and the freeze** | `robot_vision/` (except agreed items) |
| **Faculty** | The experiment plan and research questions | — |

Shared files change only by agreement. Repository: `github.com/nusratahmedniva/warehouse-robot-perception`.

---

## 4. The robot's loop (one run)

1. **Start** at A. Goal B is known only to the evaluation, never to the robot.
2. **Drive** toward the next junction on Unity's NavMesh (v4 has its own NavMesh asset; racks, pallets and stations are obstacles).
3. **Scan** with the 360° camera near the junction; find every person.
4. **Pick the commander:** the person facing the robot with a gesturing hand. Bystanders are ignored.
5. **Approach** to 2.0 m and face them.
6. **Ask:** show "Which direction?" and aim the pan-tilt camera (with zoom) at the commander's hand.
7. **Read** the gesture (section 5).
8. **Check for lies** (section 7): ask a second worker at the same junction, reject impossible directions. (Checkpoint workers on the branches were tried and are not used: section 7.)
9. **Return to the junction point**, then **take the branch** (return speed 0.8 m/s).
10. **Repeat** at every junction until B.
11. **End:** SUCCESS within 0.3 m of B. FAILURE on timeout, collision, abort or wrong goal.

**Always active (safety):**
- A STOP gesture from anyone stops the robot.
- A person in the path stops the robot. **New in v4:** after 15 s stopped behind a person who hasn't moved more than 0.3 m, the robot backs up 1.0 m at 0.2 m/s (only if nobody is behind it), steps 1.0 m to the clear side and goes around. It tries at most twice, then waits as v3 does.
- If Python stops answering for 0.3 s, Unity stops the robot by itself.

---

## 5. Commands and the gesture reader

| Command | What the avatar does | What the robot does |
|---|---|---|
| **POINT** | Points with a moving arm in any direction | Takes the branch closest to the pointed angle |
| **PROCEED** | Swinging "go on" motion | Goes forward (the FORWARD branch) |
| **WAIT** | One hand up, index finger raised | Holds and keeps watching the same person (20 s limit) |
| **STOP** | Open palm toward the robot | Stops at once, at any time |

**Reader decisions made in v4** (all disclosed in `AUDIT.md`):

| Decision | Rule | Why | Where |
|---|---|---|---|
| STOP rule (16 Nov) | Open hand **and** fingertip spread ≥ 1.3 **and** raised arm; no static or palm cue | Cut false STOPs; true STOPs not lost; 21 of 39 read later (median +0.21 s) | 16.18 |
| C2s (17 Nov) | While the robot is **standing still** (speed below 0.05 m/s, in read/approach), STOP uses a 0.3 s still-hand window; while driving, the STOP rule is unchanged | False STOPs in step-5 data 216/150 → 73/65 (frames/episodes). Cost: 32/40 true STOPs within 1.0 s instead of 34/40 (one +0.90 s, one +0.20 s) | 16.19.7 |
| B1 floor 10 (17 Nov) | PROCEED needs valid arm frames ≥ max(10, 0.6 × frames received in the 2 s window) | Too few frames (slow PC) made PROCEED unreadable. PROCEED holds in the step-5 data 35/62 → 58/62 with the earlier reader, 59/62 with C2s; no STOP reading changed | 16.19.6, 16.21 |
| Palm-facing STOP | **Rejected** | True STOP palm angles overlap PROCEED's (110–133°) | 16.19.5 |

Config: `robot_vision/configs/v4/gesture_reader.json`. Docs: `docs/gesture_reader_v4.md`.

---

## 6. The world (Unity)

- **Avatars:** one body family (Sunbox), male and female, several outfits.
  - Development looks: `sunbox_m_shirt_white`, `sunbox_m_tshirt_black`, `sunbox_f_shirt_white`, `sunbox_f_dress_red` (and the early `sunbox_m1`, `sunbox_f1`).
  - Test looks (never used in development): `sunbox_m_shirt_plaid`, `sunbox_f_shirt_plaid` (and `sunbox_f2`).
  - Test clips (`data_splits.json`): `point_mixamo_02`, `wait_ik_02`, `stop_ik_02`, `proceed_ik_03`. The experiments A and B use the plaid looks and the two clips a worker shows, `point_mixamo_02` (POINT) and `proceed_ik_03` (PROCEED) (`final_plan.json` `test_assignment`).
  - Free, licensed assets only. No third-party avatar or animation file is ever committed.
- **Ground-truth layer:** on a layer both robot cameras skip. It holds goal markers, the grid, the optimal path, the trail and the truth labels, which are written to files that only evaluation code reads.
- **Leak test:** before every session, both cameras are rendered with the layer on and off. The images must be identical (Unity `session.json` `leak_test.passed`, and Python `gt_path.py`).
- **HUD:** shows the robot's state for us; never in the robot's images.
- **Worker layout (i)** (17–18 Nov): two workers at every node, every worker at least 1.0 m from every road the robot can drive, with the real 0.8 m re-ask shift. Three workers at J1 are impossible under these rules: 0 of 864,782 layouts fit. Switching on Unity's `clearance_layout` is Nusrat's (AUDIT.md 16.20); this draft said it was switched on with layout (i) in her PR #43, which `AUDIT.md` does not record.
- **Answer zone:** a worker answers only while the robot is within 6.0 m of that worker's own junction.

---

## 7. Experiments A and B (faculty plan)

| Set | Experiment | Setup |
|---|---|---|
| A (all truthful) | A1 | Straight corridor A → B, workers on both sides |
| | A2 | A → B → C with a right-angle turn (right; left also exists) |
| | A3 | A → random goal, workers beside the optimal path |
| | A4 | A → random goal, workers at random places |
| B (each worker lies with p = 0.2) | B1–B4 | Same as A1–A4 |

**Lie model:** each worker is drawn as a liar **once per run** (`lie_mode per_worker`). A liar shows the same wrong direction every time they are asked.

**Lie detection** (`lie_detection` block in the v4 control files):

| Rule | Status | What it does |
|---|---|---|
| Second opinion | **On** | After an answer, ask another person **within 6.5 m of this junction whose nearest node is this junction**. Disagree → majority of three; with only two people, re-ask the first (counts twice) |
| Reject impossible | **On** | Rejects answers that point back along the arrival road, toward no branch, or into a dead end. A mirror-image reading near the arrival road triggers a second view |
| Backtrack | **Off** | Return and try another branch when every answer at a junction is rejected |
| Checkpoint workers (T3, T4) | **Not used** (16.26.9) | Tried in the simulator and dropped (below). The robot ignores any checkpoint worker, the control files have `checkpoint` false, and Unity needs none |
| "Back" at the next junction | **Off** | It belonged to T4 and is dropped with it |

**Known weakness (16.21.3, 16.22).** With two workers and consistent liars, the tie rule always follows the **first** worker asked. In the simulator, B3 with detection on reached 11/20 and with detection off 10/20. A first-asked liar fooled the robot 19 times; a second opinion caught a lie only twice. Turning backtrack on adds just 1/20, because a lie toward a valid branch is never contradicted.

**Limitation (reported, `analysis.json`):** with two workers per node and consistent liars, a lie toward a valid branch is not detectable from the available evidence.

**Checkpoint workers: tested in the simulator, NOT adopted (16.23 to 16.26.9).** Niva's proposal addressed that weakness: one worker partway along a branch, honest = PROCEED on the right branch and POINT back on a wrong one, lying at 20 % like everyone else (in detection-off runs the workers were present and ignored).
- **T3 (a "back" always sends the robot back) was not adopted** (16.23.1): 6 lies caught and 6 false backtracks per row, net about zero (B3 on 11/20 to 11/20, B4 on 11/20 to 12/20).
- **T4 (the checkpoint is a vote, not a veto) was adopted on 18 Nov** by the stopping rule declared before the check (16.24.3), then amended: +20.0 pp out of sample, corrected to +17.5 pp (16.25.0), +17.5 pp again with seven fixed positions and a BACK vote at the next junction (16.25.1.1). **All of that was in a simulator that read every pointing.** Disclosed at the time: T4 was designed after seeing T3; the Newcombe interval touched zero.
- **Niva's report (16.26):** an honest BACK pointed 145 to 163 degrees from the camera is unreadable, 42 % of BACKs fall within 30 degrees of the camera line, and the 1.0 s POINT window held too few frames with two people in view. The simulator now models the readability of a pointing by its angle to the line of sight (fitted on the development data, 16.26.6; pessimistic by design, the same in T0 and T4).
- **Final check (16.26.8.1):** T4 without the side view against T0 on fresh simulator seeds 101 to 140 (40 runs per row, 900 s, all 16 rows): **+0.0 pp in B3 on (24/40 against 24/40) and in B4 on (23/40 against 23/40)**, no A row changed. The bar was +15 pp. (Information only, seeds 21 to 60: +5.0 and +7.5 pp. The first rerun, with the side view on, was contaminated by a stall of the side view and is not evidence, 16.26.7.)
- **Dropped on 20 Nov (16.26.9)** by the stopping rule declared before the final check: the four `control_lie_on*.json` files are T0 exactly (`checkpoint` false, `next_junction_back` false), `final_plan.json` and the guard expect checkpoint OFF for every setting and refuse a control file with any checkpoint key on, and **T0 is kept for the finals**. The checkpoint and side-view code stays in the controller and the simulator, off, with its tests; nothing is deleted.
- **Side view (4a, 16.26 item 2):** built, off. Run in the simulator for the first time it showed a trigger defect (fixed) and a stall (A2 on, one run diagnosed, not fixed). It is not part of any final.
- **POINT frames (4b):** the window stretch (variant (ii)) is **not built**; its dialog replay did not reproduce the live logs (the replay most likely used a reader different from the one the logs were read with), so the reference reader stays. Frame rate is measured in step 5 under final conditions (frames per window by 1, 2 and 3 or more people); any later decision on POINT frames is declared before it is computed (16.26.5).
- **Unity:** needs no checkpoint workers. The checkpoint positions Niva sent (16.26 item 1) are kept in `checkpoints_unity.json` for the simulator analyses only; whether the point 2.0 m across a worker lies in the drivable area was never checked and no longer matters for the finals.
- **Time:** the simulator's estimate for the 260 final runs under T0 is about 10.1 h of simulated time (16.26.8.1). The timeout comes from Unity's step-5 runs by the declared rule (section 8).

---

## 8. The final runs

- **13 final settings:** A1, A2_right, A2_left, A3, A4 (detection on); B1, B2_right, B3, B4 (detection on); B1_off, B2_right_off, B3_off, B4_off. B2_left is not run.
- **20 runs each = 260 runs**, in **four sittings of about 3 h each** (about 12 h; AUDIT.md 16.17); each B setting runs together with its OFF partner. The simulator's estimate of the 260 runs under T0 is about 10.1 h of simulated time without overheads (16.26.8.1).
- **Final seed 2**; development seed 1.
- **Machine:** Nusrat's Windows PC (RTX 3060), strict run protocol: other apps closed (Chrome too), best-performance mode, enough free memory, resource log on.
- **Active avatars:** at most 6. This drops to 5 if the strict-protocol timing rerun still breaks the limits (loop lag 100 ms, round trip 150 ms).
- **Timeout rule:** 1.5 × the longest **successful** development run (on the new NavMesh, with the 420 s development timeout and the development-only goal override so E5/E6 are drawn), rounded up to 30 s, never below 270 s, one value for all settings. There are no checkpoint workers (16.26.9). The real value comes from Unity's step-5 runs by this rule; for information only, the simulator's T0 durations give at most 510 s (B3 on, 16.26.8.1).
- **Run-once guards:** `FINAL_RUN_DONE.json`, `FINAL_DONE.json`, `FINAL_EXPORT_DONE.json`. A finished setting can never be run or evaluated again.
- **Acceptance = validity only:** leak test passed, frozen hashes match, split guard passed, all runs present, every outcome recorded. A watchdog stop is a result, not a reason to invalidate. There are no performance thresholds: results are reported whatever they are.

Config: `robot_vision/configs/v4/final_plan.json`.

---

## 9. Statistics and outputs

- Success rates with **Wilson 95 % intervals**; ON vs OFF differences with the **Newcombe interval**; bootstrap over runs (2000 resamples, seed 1).
- CSV exports during and after experiments: `runs.csv` (one row per run), `dialogs.csv` (one row per ask); columns in `configs/v4/experiments/export_csv.json`.
- Lie metrics: lies given, detected (rejected / outvoted / backtracked), corrected, fooled, split by first-asked vs later-asked liar.
- Tools: `hri_eval_final_v4.py`, `export_csv_v4.py` (`--final-combine`), `hri_analysis_v4.py`, `paper_v4/figures_v4.py` (repo root), `make_results_archive_v4.py`.

---

## 10. The workflow from here to the paper

| # | Step | Owner | Status |
|---|---|---|---|
| 1 | Layout (i), floor 10 merged (PR #42); Unity's `clearance_layout` (section 6) | Both | **Done** (the Unity switch is Nusrat's) |
| 2 | Checkpoint workers in the simulator: T3 not adopted; T4 adopted (16.24.3), then dropped after the readability model and the final check (+0.0 pp on fresh seeds, 16.26.8.1, 16.26.9); T0 kept; the guard refuses any checkpoint key on | Anisha (+ Niva's positions) | **Done: dropped** |
| 3 | Strict-protocol timing rerun: frames per window by 1/2/3+ people; active-avatar limit | Niva | In progress |
| 4 | ~~Checkpoint workers in Unity~~ | Niva + Anisha | **Dropped** (16.26.9): Unity needs no checkpoint workers |
| 5 | **Step 5:** all 13 settings on development data with the final rules (T0, no checkpoint workers), plus the blind avatar rehearsal; frames per window by 1/2/3+ people under final conditions | Niva runs, Anisha checks | Waiting on 3 |
| 6 | Apply the timeout rule to Unity's step-5 runs; fix anything step 5 finds | Anisha | Pending |
| 7 | **Freeze:** `python freeze_v4.py --freeze`, by Niva by hand only | Niva | Pending |
| 8 | **Avatar experiment** (main): detection of person and hands across avatar kinds | Niva runs, Anisha analyses | Pending; protocol to confirm |
| 9 | Four final sittings, Set A/B (260 runs) | Niva | Pending |
| 10 | Final evaluation, CSV export, statistics, figures, archive with hashes | Anisha | Pending |
| 11 | Paper (related work doc started) | Both | Pending |

Rough estimate: about 1.5–2 weeks to final data if step 5 comes back clean, and 3–4 weeks to a paper draft.

---

## 11. How we work (rules that keep the results honest)

1. **Declare before computing.** Every rule, candidate and pass criterion is written into `AUDIT.md` **before** the data is replayed or the run is made.
2. **Development data only** for tuning. Test looks and clips are never used before the finals.
3. **Disclose every change made after seeing results**, with its exact cost (section 13 below).
4. **Run once.** No final is repeated silently.
5. **The AI (Claude Code) never runs `git push`** and never runs `freeze_v4.py --freeze`. Anisha pushes; Niva freezes.
6. **Never use GitHub's "Fix with Copilot"** (it once changed frozen v3 code).
7. **Zips are read in place** with `zipfile`, verified by SHA-256, never extracted or copied into the repo.
8. **Windows line endings:** hash and byte comparisons normalise `\r\n` to `\n`.

**Git cycle (Anisha's side):**
```
git checkout main && git pull --ff-only
# Claude Code creates branch anisha/<topic>, works, runs the full suite, prints commit commands
git add <files> && git commit -m "AUDIT <section>: <what>"
git push -u origin anisha/<topic>
gh pr create --base main --head anisha/<topic> --title "..." --body "..."
gh pr checks --watch          # macOS + Windows CI must be green
gh pr merge --merge --delete-branch
git checkout main && git pull --ff-only
```
If CI shows "job was not acquired by Runner", that's GitHub capacity, not a test failure: `gh run rerun <id> --failed`.

---

## 12. Key files

| Area | Files |
|---|---|
| Decisions record | `AUDIT.md` (14 = v4 plan, 15 = Nusrat's changes, 16 = experiments A/B and every fix since) |
| v4 configs | `robot_vision/configs/v4/` (`control.json`, `gesture_reader.json`, `final_plan.json`, `analysis.json`, `data_splits.json`, `frozen.json`) |
| Experiments | `configs/v4/experiments/` (`scenarios_ab.json`, `control_lie_{on,off}*.json`, `roadmap_a1/a2_*.json`, `export_csv.json`, `checkpoints.json` and `checkpoints_unity.json` (checkpoint positions: simulator analyses only, no checkpoint workers in the finals), `point_readability.json` (the simulator's readability model)) |
| Perception | `gesture_motion.py`, `gesture_adapter_v4.py`, `hri_perception_v4.py`, `commander_v4.py` |
| Control | `hri_control_v4.py` |
| Simulator | `hri_sim_v4.py`, `run_experiments_ab_v4.py`, `layout_check_v4.py`, `report_rows_ab_v4.py`, `report_tie_variants_v4.py`, `run_t3_v4.py`, `report_t3_v4.py`, `report_t4_oos_v4.py`, `analyse_cp_rule_v4.py` |
| Bridge | `bridge/server.py`, `bridge/protocol.py` (rejects truth fields from Unity) |
| Finals | `final_guard_v4.py`, `freeze_v4.py`, `hri_eval_final_v4.py`, `export_csv_v4.py`, `finals_v4/` at the repository root (Nusrat's session scripts) |
| Analysis | `analyse_*_v4.py`, `check_stop_rule_v4.py`, `hri_analysis_v4.py`, `paper_v4/` (repo root) |
| Docs | `docs/protocol_v3.md`, `docs/gesture_reader_v4.md`, `docs/look_check_v4.md`, `docs/project_flow_v4.md` (the spec), `docs/workflow_v4.md` (this overview) |

Outputs go to `robot_vision/outputs/` (git-ignored, about 5.5 GB on 18 November and growing).

---

## 13. Changes made after seeing results (disclosed)

| Date | Change | Cost / note | AUDIT |
|---|---|---|---|
| 16 Nov | New STOP rule (spread ≥ 1.3, raised arm) | 21/39 STOPs later, median +0.21 s, max +0.60 s; never checked false STOPs during PROCEED (gap stated) | 16.18, 16.19.2 |
| 17 Nov | Second opinions only within 6.5 m and from the junction's own people | Fixes the robot driving 3.7 m toward J2 to ask | 16.19 |
| 17 Nov | Return to the junction point before branching; return speed 0.8 m/s | Return at 0.31 m/s caused A3 timeouts in the simulator | 16.19.3, 16.20.5 |
| 17 Nov | Person-in-path recovery | Two 420 s deadlocks in step 5 | 16.19.3 |
| 17 Nov | C2s short-window STOP while standing | Criterion (a) not met: 32/40 vs 34/40 | 16.19.7 |
| 17 Nov | B1 floor 10 | No STOP reading changed | 16.21 |
| 17 Nov | Layout (i): two workers everywhere | Weaker lie detection in B3/B4 | 16.21, 16.21.2, 16.21.3 |
| 17 Nov | "STOP before PROCEED" | Mechanism confirmed, no measurable effect, not changed (v3 code) | 16.19.3 |
| 18 Nov | Tie-rule variants T1/T2 (backtrack) | +1/20 only, not adopted | 16.22 |
| 18 Nov | Checkpoint workers, variant T3 (Niva's proposal) | **Not adopted**: 6 lies caught, 6 false backtracks per row, net about zero | 16.23, 16.23.1 |
| 18 Nov | T4: the checkpoint is a vote, not a veto (designed after seeing T3) | **Adopted 19 Nov** by the stopping rule declared before the check; out of sample +20.0 pp (later corrected to +17.5 pp, next row); Newcombe interval touches zero; sign test supplementary; B3 and B4 one result counted twice; simulator only. **Dropped 20 Nov (last rows)** | 16.24 to 16.24.3 |
| 19 Nov | Who is asked at a checkpoint (R = 5.0 m); staging fix | The simulator had asked a worker of the next junction on 3 of 9 branches: T4's gain corrected from +20.0 to +17.5 pp (still above the 15 pp bar) | 16.25, 16.25.0, 16.25.0.1 |
| 19 Nov | 7 checkpoints at fixed positions; "back" at the next junction is a vote (Niva's report) | +17.5 pp again (23/40 to 30/40); 13 backtracks per row, 4 at the next junction | 16.25.1, 16.25.1.1 |
| 19 Nov | Final guard checks the checkpoint switches | A detection-on setting must have T4 exactly, a detection-off setting checkpoint false. **Since 20 Nov: checkpoint OFF for every setting, side view off** | 16.25.2, 16.26.9 |
| 19 Nov | `final_plan.json` `test_assignment_note`: no third worker at J1 | Documentation only | 16.24.3 |
| 20 Nov | The simulator models the readability of a pointing by its angle to the line of sight (fitted on development data; pessimistic by design) | T4's gain did not hold under it; the same model in T0 and T4, not tuned | 16.26, 16.26.5, 16.26.6 |
| 20 Nov | 4b: POINT window stretch (variant (ii)) | **Not built**: the dialog replay did not reproduce the live logs (the replay most likely used a different reader); reference reader kept; frame rate measured in step 5 | 16.26.3 to 16.26.5 |
| 20 Nov | 4a: side view | Built, **off**; a trigger defect found and fixed in the simulator; a stall (A2 on) left unfixed; not part of any final | 16.26 (item 2), 16.26.6, 16.26.7 |
| 20 Nov | Final check of T4 on fresh seeds 101 to 140, side view off; **T4 dropped, T0 kept** | **+0.0 pp** in B3 on and B4 on (bar +15 pp); the four on files are T0 exactly; the guard refuses a checkpoint key or the side view on; limitation: a lie toward a valid branch is not detectable from the available evidence | 16.26.8, 16.26.8.1, 16.26.9 |

Also on the Unity side: the NavMesh fix (v4 now has its own asset). All development runs before it used the old NavMesh, so only runs on the new NavMesh feed the timeout rule.

---

## 14. Open questions

- What timeout do Unity's step-5 runs give by the declared rule (no checkpoint workers; the simulator's T0 durations suggest at most 510 s, information only)?
- Frames per window by 1, 2 and 3 or more people under final conditions (Niva's strict-protocol rerun): the basis for any later decision on POINT frames, declared before it is computed.
- How often are honest BACK pointings (145 to 163 degrees from the camera) unreadable in Unity, and what does a lost robot do then? (The simulator's readability model is a development-data fit, pessimistic by design.)
- **Reported limitation:** with two workers per node and consistent liars, a lie toward a valid branch is not detectable from the available evidence.
- What exactly is the avatar experiment's protocol (avatars, runs per avatar, what counts as "person detected" and "hand detected")?
- Confirmation that v3's NavMesh asset and bake settings are byte-identical to before the fix.
- Small cleanup left: one test scans all of `outputs/` and is slow (the `final_plan.json` `test_assignment_note` was fixed in 16.24.3).

---

## 15. Glossary

| Term | Meaning |
|---|---|
| Junction / node | A road crossing (J1, J2, …); endpoints E1–E6 |
| Commander | The person the robot reads a command from |
| Second opinion | Asking another worker at the same junction |
| Re-ask shift | Moving 0.8 m sideways for a second view of an ambiguous point |
| Mirror ambiguity | A pointing arm can be read toward or away from the camera; both readings are kept |
| Checkpoint worker | A worker beside a branch who says whether the branch is right (PROCEED) or points back; variants T3 and T4, tested in the simulator and **not used** (16.26.9) |
| Disputed junction | A junction whose accepted answers named different branches; in T4 (not used) only there does a checkpoint's "back" send the robot back |
| Step 5 | Development runs of the full final matrix before the freeze |
| Freeze | Recording SHA-256 hashes of every v4 config and Unity file in `frozen.json`; after it, nothing may change |
| False STOP | A STOP read when no STOP was shown |
| Criterion (a) | No true STOP lost, and every STOP the current reader reads within 1.0 s still within 1.0 s |
| Wilson / Newcombe | Confidence intervals for a rate / for a difference of two rates |
