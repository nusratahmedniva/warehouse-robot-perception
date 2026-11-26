# Methods values (for the paper's methods section)

Every value below is copied from the file and line named beside it (line numbers as of the commit this file is committed with; the frozen configs cannot change after the freeze). Nothing here is a new decision. Where a value was set after seeing data, the AUDIT section that discloses it is named.

All paths are relative to the repository root. `gesture_reader.json` = `robot_vision/configs/v4/gesture_reader.json`; `control.json` = `robot_vision/configs/v4/control.json`; `gesture_motion.py` = `robot_vision/gesture_motion.py`.

## 1. Lie detection, the T0 rule (the "on" setting of every B final)

Source: `robot_vision/configs/v4/experiments/control_lie_on.json` lines 92-94 and 101-103 (the "on" control file); definition of the name T0 in AUDIT.md line 3293; checkpoint workers dropped, AUDIT.md section 16.26.9 (the `checkpoint` key of that file).

- Switches: `second_opinion` true, `reject_impossible` true, `backtrack` false, `max_opinions` 3, `second_opinion_radius_m` 6.5; checkpoint off. The "off" files have every switch false.
- **Second opinion** (control_lie_on.json:101): at a node with at least two people (360 camera, track ids) ask a second person after the first accepted answer; if they disagree ask a third and follow the majority; two people who disagree with nobody else present: ask the first person again, the majority of the three answers decides (the first counts twice); no strict majority among three = unclear (abort, fail safe). Answers rejected by `reject_impossible` are not votes. A person whose own asks are all rejected counts as no opinion and the next person is asked.
- **Reject impossible** (control_lie_on.json:102): reject a resolved answer that cannot be a way on, with a logged reason: *arrival* (straight back along the road the robot came from), *no_branch* (no branch of the node within `dialog.branch_match_max_deg` 30 deg of the pointed direction, or PROCEED at a node without a FORWARD branch), *dead_end* (the branch leads to a node of kind dead_end). A rejection held for `dialog.gesture_hold_s` (0.5 s) ends the ask at once and asks again (it uses an ask). A pointed direction is also ambiguous when its branch was found but the other of the two mirror-image depth readings is the arrival road; the second view then decides and does not use up an ask (AUDIT.md 16.11).
- **Backtrack** is off in T0 (the T1 variant switches it on; not used in the finals).
- Second-opinion radius (AUDIT.md 16.19 item 2): a second opinion is asked only of a person within 6.5 m of the junction whose nearest node is this junction.
- `branch_match_max_deg` 30, `gesture_hold_s` 0.5, `reask_shift_m` 0.8: `control.json` (dialog block, lines shown by `sed -n 1,60p`; the `why` texts there give the reasons).

## 2. POINT and WAIT: the window and the minimum-frame rule

Source: `gesture_reader.json` lines 9-12 (window block) and `gesture_motion.py` lines 614, 643, 650.

- Window `window_s` **1.0 s** (10 frames at `frame_hz` 10 Hz): gesture_reader.json:9.
- Minimum valid frames: `min_valid_fraction` **0.6** -> `need = ceil(0.6 x round(window_s x frame_hz))` = **6 of 10 frames** (gesture_motion.py:614); fewer valid frames gives `insufficient_history`, never a guess (gesture_motion.py:683; gesture_reader.json:15).
- Hold: the arm must be still for `hold_min_s` **0.4 s** (5 frames, at least 2 samples; gesture_reader.json:11, gesture_motion.py:643); a trailing still stretch is found with `still_speed_max` 0.4 torso lengths/s and the window is "moving" when the wrist path is at least `motion_path_min` 0.4 torso lengths (gesture_reader.json motion block).
- Decision: a class needs its cues to pass in at least `class_share_min` **0.7** of the hold frames and to beat the next class by `class_margin_min` **0.2**, else NONE (gesture_reader.json decision block; gesture_motion.py:650, 685).
- POINT cues: segment disagreement at most 45 deg, elbow extension at least 140 deg, arm length at least 0.8 shoulder widths, elevation at most 60 deg, `arm_length_in_shoulder_widths` 1.683 (set on development data by the B12 rule, AUDIT.md 14.11 item 3 and the `calibrated` line of gesture_reader.json).

## 3. PROCEED: window, swings and the floor rule

Source: `gesture_reader.json` lines 99-110 (proceed block) and `gesture_motion.py` lines 566-570.

- Window `window_s` **2.0 s** (20 frames at 10 Hz); at least `cycles_min` **2** up-and-down cycles; each stroke at least `swing_min` **0.3** torso lengths; at least `vertical_share_min` **0.7** of the wrist path vertical.
- **Floor rule** (AUDIT.md 16.21, from the candidate B1 of 16.19.2): PROCEED needs valid arm frames >= **max(`min_valid_floor` 10, `min_valid_fraction` 0.6 x the frames the reader received for that person in the 2.0 s window)** instead of 0.6 x the nominal 20 (= 12). At 10 Hz this is max(10, 12) = 12, unchanged; at 5 Hz (10 frames in 2 s) it is 10, so the gesture can still be read (gesture_motion.py:566 nominal, :567-570 floor). Replay on step-5 logs: PROCEED holds 35/62 -> 58/62 (AUDIT.md 16.19.6).

## 4. STOP: the rule, the fingertip spread, and its unit

Source: `gesture_reader.json` lines 63-72 and 86-87; `gesture_motion.py` lines 255-285 (`open_palm_geometry`, `fingertip_spread`, `stop_extra_ok`) and 628-640.

- Read on the short window `stop_window_s` **0.3 s** (3 frames at 10 Hz; gesture_reader.json:12), not the hold: STOP is the safety command.
- Open-palm geometry: all four fingers extended (`finger_extended_ratio` 1.6: wrist-to-tip over wrist-to-MCP) and the wrist-angle spread (index tip to pinky tip, angle at the wrist) at least `palm_spread_min_deg` **20 deg** (gesture_reader.json:63; gesture_motion.py:255-258). MediaPipe's own label and score are logged but not required (decided 2026-11-08, AUDIT.md 14.16).
- The arm must be raised (`stop_requires_raised` true, line 70; decided 2026-11-16, AUDIT.md 16.18.2 after the STOP-session results, disclosed there).
- **Fingertip spread** (`stop_fingertip_spread_min` **1.3**, line 72): distance from the index fingertip to the pinky fingertip divided by the distance from the index knuckle (MCP) to the pinky knuckle, both from the 21 landmarks in image **pixels** (gesture_motion.py:261-267). **Its unit is a dimensionless ratio** (about 1 for fingers held together, larger for a fan); it is not an angle and not a length. 1.3 was fixed in AUDIT.md 16.18 before the STOP sessions were read and never varied.
- Stillness while the robot is stopped (C2s, below): `stop_still_when_robot_stopped` true (line 71).
- No push (growth of the hand box) is required (`stop_requires_push` false).

## 5. C2s (stillness of a STOP while the robot is stopped)

Source: AUDIT.md section 16.19.5 item 1 (line 2816) for the definition, 16.19.7 (line 2844) for the adoption, 16.19.6 (line 2822) for the replay table; `control.json` lines 35-39 (`stop_rule`); `gesture_reader.json` line 86; `gesture_motion.py` lines 628-633.

- **C2s = C2 with the reader's short 0.3 s window instead of its `moving` flag.** While the robot is stopped (speed below `robot_stopped_speed_mps` **0.05 m/s**, in the states read, approach or wait), a STOP needs the mean wrist speed over the last `stop_window_s` **0.3 s** to be at most `still_speed_max` **0.4** torso lengths/s (no samples = not still). While the robot moves the fast STOP rule is unchanged. No new number.
- Adopted 2026-11-17 AFTER seeing 16.19.6, with criterion (a) of 16.18.2 not met: 32 instead of 34 of 40 true STOPs within 1.0 s, none lost altogether; false STOPs in the step-5 logs 216 frames / 150 episodes -> 73 / 65 (AUDIT.md 16.19.7, disclosed there). The plain C2 (`moving` flag, 1.0 s) was rejected.

## 6. The interruption rule of the finals (AUDIT.md 16.30.1, lines 3916-3945; built in 16.30.1.1, line 3966)

1. **Interruption = infrastructure only**: the bridge server or Unity dies, or the machine fails, before a run finishes. A run that ends (success, wrong goal, abort, timeout, collision, any outcome in `truth_run###.json`) is not an interruption; a failure of the robot's behaviour is a result.
2. **Completed runs stand**: runs 1 to k-1 are never rerun and never rescored.
3. **The interrupted run k has no outcome**: it is recorded as "interrupted (infrastructure)" with the evidence, listed in the results and not scored.
4. **One resume**: the session may be resumed once from run k (same run number, so the goal of run k is the one that was interrupted), with the same seed, goal order, configs and frozen hashes; it is declared before it starts, never silent.
5. **A second interruption in the same setting makes the setting INVALID**, reported with the reason, never rerun.
6. Every interruption and resume is reported in the results.
7. No resume after the setting was evaluated, exported or declared invalid.

Applied to the avatar experiment (AUDIT.md 16.31, line 4027): a part (Edit or Play) may be resumed once from the interrupted group; a second interruption makes the part INVALID. **The Edit part of the avatar experiment stopped after about one minute (STARTED marker, no DONE marker, partial recordings for 10 of the 15 looks); the look checks have no resume mechanism, so the rule cannot apply, the partial data is not evaluated, and the Edit control is reported as NOT COMPLETED (a limitation); Play stays the declared headline** (AUDIT.md 16.38 and its correction 16.38.1).

## 7. How recordings map to takes in the avatar experiment

Source: `docs/avatar_experiment_protocol_v4.md` lines 28-39 (counts and definition of a take) and 69-77 (the take is the unit); `robot_vision/process_avatar_zip_v4.py` lines 102-115 (`take_shares`, `take_outcome`) and 259-267 (one take per recorded sequence or single frame).

- Per look in Play: 18 groups (look x command x distance x arm): 12 POINT/WAIT/STOP, 4 PROCEED, 2 NONE; each group has 2 sequences (11 frames, PROCEED 21) and 16 single frames; 764 frames per look.
- **A take is one performance with its own variation and its own drawn camera pose: a sequence or a single frame.** The 2 m and the 4 m camera see the same take, so a gesturing take is counted once per arm, not once per distance (144 takes per look for the four commands); NONE takes are counted per distance (36 per look).
- A frame-level measure (person found, hand found, hand linked, arm valid, facing, own cue, wrong class) is first computed as a share per take (0 or 1 for a single frame); the reported value is the mean over takes, with a bootstrap over takes (2000 resamples, seed 1, 2.5 and 97.5 percentiles; `robot_vision/configs/v4/analysis.json` avatar_experiment block), resampled within each look x command x distance x arm cell; a pooled cell resamples the takes of each look separately. Only a take-level yes/no gets a Wilson 95 % interval. Never an interval over frames.
- Floor (Play): a look x command cell is evaluated only if its valid takes include at least 2 sequences and at least 10 single-frame takes per arm and distance; otherwise `insufficient_data`.
- Clip per take: read from `recordings.jsonl` (look, command, distance, arm, take, clip); Edit takes and Play NONE takes have no clip.
- Primary measure per take: gesturing hand **found and linked** (hand detected AND linked to the person, AUDIT.md 16.31.1).
