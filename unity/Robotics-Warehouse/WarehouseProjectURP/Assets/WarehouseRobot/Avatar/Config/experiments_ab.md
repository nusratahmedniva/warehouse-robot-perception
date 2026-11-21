# Experiments A and B and the avatar experiment: Unity side (design notes, declared before testing)

Branch `nusrat/v4-experiments-ab` (from main a6839ae, which holds Anisha's side: AUDIT.md section 16, `configs/v4/experiments/scenarios_ab.json`,
`docs/protocol_v3.md` amendment 4). Faculty plan of 2026-11-13. Every entry is dated and written BEFORE the thing it declares was tested.
Nothing here changes a v3 file, a Python file, a file of the B9 freeze list (`final_v4.json` `freeze_files`) or a frozen value; the v4 finals
(`zoom_on`, `zoom_off`, `bystanders`, `zoom_on_repeat`) are not affected. **[A]** marks a default that needs Anisha's confirmation, **[N]** one
that needs Nusrat's.

## 2026-11-14, section 1: what is built where

- The experiments run in the v4 scene with `TrialRunnerV4` in a new **experiment mode** (`TrialPlayV4 -experiment <A1..A4|B1..B4>`): the v4
  Task 2 path (one commander moved between stands, bystanders) is untouched when the argument is absent.
- Experiment looks are in a NEW file `Avatar/Config/looks_ab.json`, merged at Play with `worker_v4.json` (which stays as it is: it is on the
  B9 list). Experiment scene settings are in a NEW file `Scenario/Config/experiments_ab_unity.json`.
- Every look and clip a session uses must be listed in `robot_vision/configs/v4/data_splits.json` (Anisha's): until she adds the new look
  names, a development session with them is refused before anything is recorded (Unity's `DataSplitsV4.GuardRun`, unchanged).

## 2026-11-14, section 2: avatars (step 2), declared before the look check ran

**Kinds and looks.**

| kind | looks | source |
|---|---|---|
| realistic human | `mixamo_worker` (the v3 Mixamo worker, `Characters/worker.fbx`, git-ignored) | Mixamo (Adobe) |
| stylised human | Sunbox base, male and female, several costumes (below), plus the existing `sunbox_m1`, `sunbox_f1`, `sunbox_f2`, `sunbox_m2` | Stylized Customizable Avatars (Free), Sunbox Games, Unity Asset Store |
| anime | `anime_f_01` (Nusrat's own VRoid character, exported as FBX) | `unity/downloads/characters_v4/anime_f_01.fbx` |
| cartoon non-human | `cartoon_boxo_01` (Nusrat's own procedurally generated character, thumb + 3 fingers) | `unity/downloads/characters_v4/cartoon_boxo_01.fbx` |
| faceless mannequin | none: no `mannequin_*.fbx` is present (checked 2026-11-14) | |

**Names** encode person, gender and costume: `<person>_<m|f>_<costume>_<colour>` (a-z, 0-9, single `_`; the look check needs no `__`). The
Sunbox "person" is one base identity per gender: skin index 1 (Skin_Male_02 / Skin_Female_02), hair 1 (male) and 5 (female), no facial hair;
only the clothing changes ("the same person as male and female, several dress colours and costumes"). Navigation looks (Sets A and B):

| look | gender | costume (Sunbox free-pack item [variation]) | proposed split **[A]** |
|---|---|---|---|
| `sunbox_m_shirt_white` | male | Shirt [1] white, Pants [0] black jeans, Suit Shoes [0] black | development |
| `sunbox_m_tshirt_black` | male | TShirt [0] black, Tracksuit Pants [1] grey, Basketball Shoes [1] white | development |
| `sunbox_m_shirt_plaid` | male | Shirt [0] plaid red, Cargo Shorts [1] blue, Basketball Shoes [0] black | **test (unseen)** |
| `sunbox_f_shirt_white` | female | Shirt [1] white, Long Skirt [0] black, Flats [0] black | development |
| `sunbox_f_dress_red` | female | Dress Sleeveless [2] red, Flats [1] white | development |
| `sunbox_f_shirt_plaid` | female | Shirt [0] plaid red, Pants [1] blue jeans, Flats [0] black | **test (unseen)** |

The two test looks share the plaid shirt (the same costume on the male and the female person), so the finals show an unseen costume on both genders.
The existing looks keep their names and roles (v4 finals: sunbox_f2 test); they are in the avatar experiment only.

**Look check, every look of every kind, before any clip is made** (an engineering check, nothing tuned on it; docs/look_check_v4.md rules unchanged):
1. *Edit-mode inventory* (`Tools > Warehouse v4 > Look Check > Run Look Check`, now with `-looksFile Assets/WarehouseRobot/Avatar/Config/looks_ab.json`):
   Humanoid, bones and finger bones mapped, material problems (error shader, no URP pass), magenta pixels in every render; held poses on the neutral stage.
2. *Play-mode look check at the real ask positions* (`LookCheckPlayDriver`, venue `WarehouseRobot_v4.unity`, the J1 and J2 worker stands, asking
   bearings 15 to 50 deg, 2.0 and 4.0 m, real motion with the worker template), with a new config `Avatar/Config/look_check_play_ab.json` that lists
   every look; it differs from `look_check_play.json` only in `looks` and the output prefix. A look the worker template cannot spawn (for
   example a hand without the index-to-little finger bones that `HandShaper` needs) is taken out of that list with the reason, and is reported with
   its Edit-mode results only; the worker template is not changed to make a look pass.
3. Anisha's `look_check_v4.py --input <recordings>` on both outputs (person, arm valid, hand linked, own cue, wrong class, sequence read, arm ratio p95,
   facing). PROCEED is not in her tool's commands (`configs/v4/look_check.json` `input.commands`), so PROCEED readability is **not evaluated** by it
   (a Python change, written down for Anisha, not made).

**Pitfall checks, reported per look:**
- *Arm-to-shoulder ratio:* the YOLO p95 of Anisha's report and the bone ratio of the Play check (`workers.json` `arm_to_shoulder_ratio`), each as a
  difference from 1.683. The reader is not changed.
- *Left/right rest pose:* the existing mirror fix (`HandShaper.MirrorRest`, run by `WorkerV4.Initialize` for every look) with the size of the
  correction it made (from the look description), and the Edit Mode test of the fix run on every installed rig.
- *Armature scale vs Humanoid avatar:* hand reach = `hand_to_target_max_m` of the Play check (distance of the gesturing hand from its IK target,
  held frames) and `HumanAvatarFix` rebuilds; a look whose hand misses its target by more than 0.05 m is reported **[A]**.
- *URP materials:* the inventory's material problems and magenta pixels. `cartoon_boxo_01`: if it imports without colours, its materials are
  recoloured from their names (teal body, orange vest, white hat, dark gloves, navy trousers, brown boots) into new URP Lit materials in the
  git-ignored import folder.
- *Clothing over the palm, dark faces, glasses:* from the annotated frames and the hand-linked and facing rates.
- *More avatars:* the active-avatar limit stays enforced (section 3); frame times are in every telemetry message (`frame_ms_max`); free memory is
  sampled during the look check by the launcher script.

**Import** (`Tools > Warehouse v4 > Experiments > Import Characters`, also `-executeMethod`): copies each `unity/downloads/characters_v4/*.fbx` into
`Assets/ThirdParty/CharactersV4/<id>/` (git-ignored; `.gitignore` already ignores `Assets/ThirdParty/`), sets Rig > Humanoid (avatar from the
model), extracts embedded textures and materials there, and writes a report. **No character FBX, texture or material is committed.**
*Unit scale (added 2026-11-14 after the first import, before any look-check result of these two looks was read):* the first import of anime_f_01 and
cartoon_boxo_01 gave Humanoid `humanScale` 0.010 and 0.008 (renderer heights 0.018 and 0.016 m; `outputs/probe_rigs_20261114_022855`): their FBX
units are centimetres read as metres. Rule: when a model's head-to-foot bone height lies outside [0.5, 2.5] m, the import sets the model importer's
scale factor (`globalScale`) to the power of ten that brings it inside, and reports it per look. Nothing else (no bone, proportion or pose) is changed.
(First applied with `humanScale` outside [0.5, 2.0] as the test; after the import Unity reported `humanScale` 103.8 for a model of the right size
(head to foot 1.40 m, renderer height 1.79 m), so a re-import would have undone the factor: the test was changed to the bone height in metres, which
the factor already applied passes. Changed before any look-check result of these looks was read.) After a scale change the Humanoid avatar is
rebuilt from the scaled model (the old avatar kept the 1/100 skeleton description: `humanScale` ~100, and at Play Mecanim posed anime_f_01 about 11.6 m
above the floor; found by the truth logger's ankle-height rule in the first Play look check, `look_check_play_ab_20261114_031052`, whose anime_f_01
recordings are therefore not used).
*Embedded textures without a file extension (added 2026-11-14, after the first Edit-mode renders showed anime_f_01 as a flat white silhouette,
before any verdict of it was used):* anime_f_01's FBX embeds its 25 textures under names without an extension (`_01` ... `_21`, PNG by their
magic bytes), so Unity imports none of them and every material has no base map. The import gives each extracted image file without an extension
the extension of its format (PNG, JPEG) and re-creates the model's materials, linking a material's base texture that the FBX names but Unity could
not resolve to `Textures/<name>.<ext>` (`ExperimentCharacterPostprocessor`, active only under the import folder). No colour or texture is invented.
*Emission (added 2026-11-14, same reason, before any verdict of anime_f_01 was used):* every anime_f_01 material is imported with emission ON at pure
white and no emission map (`outputs/probe_rigs_*`), which renders the whole model as a flat white glow. An extracted material with that combination
gets emission off; nothing else is changed. *Finding, not fixed:* anime_f_01's arm mesh does not follow its Humanoid arm bones (the hands and
fingers do), although every skinned mesh uses those bones (no duplicate armature): an export problem of the FBX's skin weights, reported as such.
Licences: `unity/downloads/characters_v4/SOURCES.txt` is named as the source of the licences but **does not exist** (checked 2026-11-14); the
licence check is reported as not done for anime_f_01 and cartoon_boxo_01 **[N]**.

## 2026-11-14, section 3: scenes A1 to A4 (step 3), declared before any test

**Maps.** A1 and A2 use Anisha's maps of `scenarios_ab.json` (decision 1 of 16.2) in the warehouse coordinates: both fit the Unity floor (checked on
a Unity `grid.json`: (26.25, 0) is a free cell 2.0 m from the nearest blocked cell; every node is free). A1 = `corridor` A (6.25, -20) to B (6.25, 20);
A2 = `turn`: A to B (6.25, 0), one right turn, C (26.25, 0). Nusrat's plan allows a LEFT turn too ("left or right at the corridor end"); the mirror map
`turn_left` (C at (-13.75, 0), equal legs) is a **proposal for Anisha** (`outputs/experiments_ab_roadmaps_<time>/`, roadmap.json format) and is used
only when `experiments_ab_unity.json` `a2_sides` lists it (default `["right"]` = Anisha's decision) **[A][N]**. A3 and A4 use the v4 map
`configs/v4/roadmap.json` (A, J1 to J4, E1 to E6). The robot's map is Python's; Unity reads the same file and refuses a scene that does not match.

**Goal.** A1: B; A2: C; A3, A4: an endpoint of the v4 map per run from the session's existing goal generator (`GoalSequence(seed)`, the Task 2
order), not the simulator's `random.Random(f"{seed}|goal")` (Python's string seeding is not reproduced in C#) **[A]**.

**Who stands where (placement).** Workers stand at every asking node (the start node and every junction of the map, also those off the
optimal path, as 16.2 decision 3). Rules for every scenario (`scenarios_ab.json` `placement_rule`, read from Anisha's file, plus Unity's
existing bystander rule):
1. any two workers at least `min_worker_separation_m` 3.0 m apart (also across nodes);
2. every worker at least `min_turning_point_m` 3.0 m from every junction and from the start node;
3. **bystander rule:** at each node the worker the robot should reach first ("first worker") is the nearest one along the approach; every
   other worker of that node is at least `nearer_margin_m` 1.0 m farther from the robot than the first at every point of the last 3.0 m of
   the arrival road (`TrialWorkerGeometry.NearerMargin`, the rule of `trial_workers_v4.json`); at the start node, from the start position;
4. on a free cell of the ground-truth grid and not inside a collider; in the `random` layout also at least `min_road_m` 1.0 m from every road
   centre line of the run's map and of the physical v4 map (16.2 decision 3; the v4 map's roads count for the corridor and turn maps too, so a
   worker never stands on a crossing road the robot's map does not know). Rule 2 counts the start node and junctions of both maps.

*Layout `beside`* (A1, A2, A3): fixed slots per node in the node's arrival frame (`before_m` back along the arrival road, `right_m` to its right;
at the start node, behind A along the start heading). Junctions: slot 1 (3.0, -2.0), slot 2 (5.5, +2.0), slot 3 (6.0, -2.0). Start node: slot 1
(3.0, -2.0), slot 2 (3.0, +4.0) (5.5 m behind A would put slot 2 0.25 m from the inflated south wall on the Unity grid; the start node's approach is the
start position alone, where 5.0 m against 3.6 m keeps the 1.0 m margin). Anisha's simulator puts both people at 3.0 m before the node, 2.0 m each
side; that symmetric pair breaks the bystander rule (the two are equally near on every approach), so slot 2 stands farther away ("male first, female
next" of the plan: the first worker is reached first) **[A]**. The slots satisfy rules 1 to 3 on every node of the three maps (checked by an Edit Mode
test with the real map files). A fixed slot that breaks a rule refuses the session.

*Layout `random`* (A4): per node, each worker uniform in the 6 m x 6 m square centred on the node (16.2 decision 3, `half_size_m` 3.0), drawn
from a stream seeded by session seed, run and node; a draw that breaks any rule above is redrawn from the same stream (at most 10 000 draws, then
the session is refused) and the **number of redraws is logged** (`session.json` `experiment.placement`, per run and node).

*Conflict found by the first test (2026-11-14, before any run; numbers from a seeded Monte Carlo of the rules at a four-way junction such as J1,
arrival from the south):* Anisha's 6 m x 6 m square together with rules 1, 2, 4 and the bystander margin of 1.0 m accepts 2 workers in 1 draw of
11 800 and 3 workers practically never (0 of 200 000), so A4 and B4 could not be built. Default chosen, **[A][N]**: the `random` layout keeps her
square and every other rule, and its bystander margin is `random_nearer_margin_m` **0.25 m** (every other worker still strictly farther than the
first at every point of the approach; acceptance 1 in 114 draws for 2 workers, 1 in 2 900 for 3), with up to `random_max_draws` 100 000 draws.
Alternatives for the decision: margin 1.0 m with a 10 m x 10 m square (1 in 16 and 1 in 106), or no third worker at J1 in A4 and B4.
The `beside` layout keeps 1.0 m.

**How many workers.** 2 at every asking node; **3 at J1** in A3, A4, B3, B4 (Set B needs "some junctions with 2-3 workers"; the same layout in A
and B keeps the only difference the lies) **[A]**. A1, A2: 2 at each asking node (A1: A; A2: A and B).

**Looks by position (clothing differs by position).** Slot 1 male, slot 2 female, slot 3 male ("male first, female next"); within a gender the
development looks are taken in name order, rotated by node index and run: look = list[(node index + run - 1 + slot // 2) mod n]. Two workers
of one node never wear the same look; neighbouring nodes differ. Development sessions use development looks only; test looks never.

**Who answers.** Anyone asked answers (16.3, "every person at a node is a worker who can be asked"). When the question appears (a new ask,
QuestionWatch as before), the worker who answers is the active worker within `ask_max_distance_m` 3.5 m of the robot with the smallest angle
between the pan-tilt camera's forward axis and the direction to the worker's head (Python pans the camera to the person it asks); nobody within
3.5 m = nobody answers (logged). That worker is `is_commander` true in truth.jsonl from the request until its gesture has returned.

**What a truthful worker shows.** The branch toward B (PROCEED for the FORWARD branch, POINT otherwise, as Task 2). At a node from which no branch
leads to B (reached after a lie or a misread) the truthful worker points BACK along the arrival road (AUDIT 16.11 item 4, accepted modelling assumption).

**Active-avatar limit.** All workers of a run are spawned at the start of the run and keep their identity, look and lie; a worker is ACTIVE
(rendered and animated) only while the robot is within `activation_radius_m` 8.0 m of it (beyond the 6 m motion range, so no person appears
inside it) and stays active while it gestures. `max_active_avatars` stays enforced: 6 in the experiments **[N]**; every run's plan is refused
when, sampled every 0.5 m along every road of its map, more than 6 workers could be active at once (`ExperimentPlanAB.MaxActive`). truth.jsonl keeps one row per worker per frame (the writer requires the
same workers in every frame); an inactive worker is logged idle at its stand with the extra field `active` false (extra fields are ignored by Python)
**[A]**. Frame times are in every telemetry message.

**Ground-truth markers.** Each worker's stand gets a ring on the GroundTruth layer (never seen by the robot cameras; the leak test still runs before
trial 1): green for a truthful worker, **magenta-red for a liar**; the ask markers of `RunVisualsV4` are coloured the same way by the answering
worker's lie. The HUD minimap (`MinimapV4`) is checked in the first Play run; a fix, if needed, is display only.

**Smoke check of the runner (declared 2026-11-14 before it ran).** Until Anisha lists the new look names in data_splits.json, an experiment session
is refused. To check the experiment mode end to end before that (placement in the scene, activation, who answers, lies, truth files, markers,
minimap), `TrialPlayV4 -experimentLooks sunbox_m1|sunbox_f1` (male|female) replaces the navigation looks by these two existing DEVELOPMENT looks
(recorded in session.json `navigation_looks_override`). Only experiments on the v4 map (A3/B3) can run against today's server. One trial each, a
smoke check of the code, **not an experiment run** (step 5): its sessions are reported as smoke checks and are not used for any result.

**Scene check.** An Edit Mode test loads the map files (`scenarios_ab.json` maps, `configs/v4/roadmap.json`, the proposal files) and checks that the
experiment configuration's nodes, branches and slots match them and obey every placement rule.

## 2026-11-14, section 4: lying workers (step 4), declared before any test

- **Who lies.** Per worker per run, with probability `lie_probability` of the session's set in `scenarios_ab.json` (A 0.0, B 0.2), drawn ONCE from a
  stream seeded by (session seed, run, worker id) when the run's workers are spawned. The draw does not depend on anything that happens in the run.
- **Consistent.** A liar shows the SAME wrong direction every time it is asked in that run (re-ask, second view, a later visit). **Differs from the
  simulator**: Anisha's 16.2 decision 2 draws every gesture independently (a re-ask is a new draw) **[A][N]**: Nusrat's plan says consistent.
- **What a liar shows.** A wrong but VALID branch: uniformly one of the node's branches in the robot's map other than the true one (the true one
  = toward B, or BACK at a node that cannot lead there). Where the node has no other branch (A1's A; A2's A and B; the start node A of the v4 map):
  the rule of AUDIT 16.2 decision 2 (Anisha's simulator), one of the other directions of LEFT / FORWARD / RIGHT / BACK relative to the arrival
  direction, uniformly, which is then an impossible direction (what rule (b) catches). protocol_v3.md has no such rule; this default is **[N]** ("or ask me").
  The direction is drawn once per liar, from the same seeded stream, right after the lie draw. Unlike the simulator, a liar at a junction never
  shows an impossible direction **[A]**.
- **Truth.** `gesture_truthful` (protocol_v3.md amendment 4) in every truth.jsonl row: false on every row of a liar's gesture (phases
  gesturing, holding, returning), true otherwise (also while idle, in start_delay and for every truthful worker). The direction shown is the
  existing `point_angle_deg` (POINT) or PROCEED (FORWARD). The lie is in no other file except the run's ground-truth markers and session.json's
  `experiment` block (the lie draw per worker), and **never in a message**: `gesture_truthful` joins Unity's forbidden keys (`ProtocolV3.TruthKeys`,
  equal to Python's `TRUTH_KEYS`).
- **Tests (Edit Mode).** The seeding (the same seed gives the same liars and directions; another run or worker another stream); the rate over many runs
  (0.2 within a binomial bound); consistency (a liar's answer is the same on every ask); valid-branch and fallback directions; the truth field (false
  exactly on a liar's gesture rows, the line format) and the forbidden key.

## 2026-11-14, section 5: anime_f_01 re-export, arm-skin probe, look check of two looks (declared before any of it ran)

- **Inputs (Nusrat, 2026-11-14 afternoon).** `unity/downloads/characters_v4/anime_f_01.fbx` re-exported (sha256 `fe304543...311d`, 9 932 076 bytes;
  the imported file of section 2 is `79f49bc1...7b377`). `cartoon_boxo_01.fbx` unchanged (`431e6cb2...7632`, same as imported).
  `unity/downloads/characters_v4/SOURCES.txt` now exists but is **empty (0 bytes)**: the licences of both characters cannot be checked from it and
  stay **not verified** **[N]**. Nothing of these files is committed either way.
- **Re-import.** The importer never overwrites an imported FBX that differs (section 2). The superseded import folder
  `Assets/ThirdParty/CharactersV4/anime_f_01/` (with `anime_f_01.meta`) is **moved, not deleted**, to the git-ignored
  `unity/downloads/superseded/anime_f_01_79f49bc1/` (outside `Assets/`, so Unity no longer imports it); then `Import Characters` runs unchanged.
  The declared fixes of section 2 (unit scale, textures without an extension, white emission) apply only where the new file needs them, and the
  import report says which did. cartoon_boxo_01 is imported again as it is (same file, idempotent). A new problem of the re-export that no declared
  fix covers is reported, not fixed.
- **Arm-skin probe (new, report only; `-executeMethod WarehouseAvatar.EditorTools.ExperimentLooksMenu.BatchProbeArmSkin`, every prefab look of
  looks_ab.json, into `robot_vision/outputs/probe_arm_skin_<time>/`).** Does the mesh follow the Humanoid arm bones? Per side, with the look in its
  import pose: rotate the upper arm 45 deg about the axis perpendicular to the arm and the vertical (the arm swings up), and bake every skinned mesh
  before and after. *Arm region* = import-pose vertices within 0.25 x upper-arm length of the forearm segment (elbow to wrist) or of the distal half
  of the upper arm (midpoint to elbow); *hand region* = the remaining vertices within 0.5 x forearm length of the wrist. A vertex *follows* when its
  baked position lies within 25 % of its expected displacement of the expected position (the rigid rotation with the upper arm, which carries the
  forearm and hand). A side **follows** when at least 95 % of its arm-region vertices follow; fewer than 50 arm-region vertices = inconclusive. The
  hand region is reported the same way, for comparison only. **Controls:** mixamo_worker (expected: follows) and the superseded anime_f_01 import,
  probed before it is moved (expected: does not follow, the visual finding of section 2). If a control does not come out as expected, the probe's
  verdict is not used and "the arm follows" is decided from the frames alone, reported as such. An Edit Mode test checks the probe on a synthetic
  skinned arm (weighted to the arm: follows; weighted to the chest: does not).
- **Visual check.** The Play-mode frames of anime_f_01 (POINT, WAIT, STOP, both arms) are looked at for the arm mesh following the arm.
- **Look check of anime_f_01 and cartoon_boxo_01 only.** New command-line option `-lookCheckLooks <id>[,<id>...]` for the Edit-mode
  (`LookCheckMenu.BatchRunExperiment`) and the Play-mode (`LookCheckPlayMenu.CommandLineRunAB`) look checks: keeps those looks of the run's list, in
  its order; a name not in the list refuses the run; recorded in `run_info.json` `looks_subset`. No config file changes (copied to `config_used/` as
  before). With one look, the Play check still records it at both junctions in a round, the coverage each look had in step 2. cartoon_boxo_01 stays
  out of the Play check (section 2 rule, its file unchanged): its rerun is the Edit-mode check. anime_f_01: Edit and Play. Then Anisha's
  `look_check_v4.py --input` on both outputs, reported per look in the format of the step 2 report. Nothing is tuned on it.
- *Addendum (2026-11-14, after the re-import and the arm-skin probe, before any look check of the new file ran).* Results so far:
  `probe_arm_skin_20261114_133039` (controls before the move: mixamo_worker follows 371/371 and 400/400; superseded anime_f_01 does not follow,
  115/183 per side; cartoon_boxo_01 follows) and, after the re-import `import_characters_20261114_133118`, `probe_arm_skin_20261114_133152`:
  **the re-exported anime_f_01 follows (183/183 per side)**. The re-export is in metres (no unit-scale change, humanScale 1.04) and only the
  white-emission fix applied. **But none of its 18 materials has a base texture** (the superseded import: 18 of 18 linked): the re-export names its
  25 textures *with* an extension (`_01.png` ...), so the extension step renamed nothing, and the material re-creation that lets
  `ExperimentCharacterPostprocessor` link the textures ran only after a rename, while the materials were extracted before the textures existed.
  That is an ordering gap of the declared texture-link fix of section 2, not a new kind of fix. Change: the materials are re-created when textures
  were renamed **or newly extracted by this import** (a re-import of an imported model extracts none, so it stays idempotent); nothing else.
  The unlinked import is moved, not deleted, to `unity/downloads/superseded/anime_f_01_fe304543_unlinked/`, and Import Characters runs again.
  The arm-skin probe is repeated on that import (materials do not change skinning; reported).
- *Addendum 2 (2026-11-14, after the first Play run of the re-imported anime_f_01, before a second one).* After the texture-link fix
  (`import_characters_20261114_134655`: 18 of 18 base textures linked; emission rule not applied, every material now has an emission map, 17 of 18
  the all-black `Shader_NoneBlack.png`, the hair `_21.png`, the export's own highlight; arm-skin probe `probe_arm_skin_20261114_134730`: follows,
  183/183 per side) the Edit check `look_check_ab_20261114_134755` and the Play check `look_check_play_ab_20261114_134932` ran on 66f41f6. In the
  Play run **56 of the 76 NONE frames show the Editor's flat-cyan placeholder** of a shader variant still compiling (a frame counts with at least
  500 pixels of (<= 8, >= 247, >= 247)); NONE is recorded first, so these were the first renders of the new materials. All 456 POINT, WAIT and STOP
  frames, every frame of the step 2 Play run and every Edit-mode render: 0. Rule: the Play check of anime_f_01 is run **once more**, unchanged, on
  the same commit (the variants are now compiled); both runs are kept and reported; the second is used if it has no cyan frame, otherwise the first
  is reported with its cyan frames named and nothing is run again.
- *Results (2026-11-14; report `robot_vision/outputs/experiments_ab_step2b_anime_cartoon_20261114.md`).* Play run 2 `look_check_play_ab_20261114_140152`
  (tool `look_check_v4_20261114_140845`) has 0 cyan frames and is used; run 1 is kept. **anime_f_01 re-export: the arm mesh follows its bones**
  (probe and frames); person at 2 m 0.99 (old export 0.79); **verdict still fails**: no POINT, WAIT or STOP sequence read at 2 m, MediaPipe finds a
  hand in 0 to 5 % of frames, the POINT clips fold the forearm on this rig (bone arm-to-shoulder ratio 2.28), facing 0.07 (bangs over one eye).
  **cartoon_boxo_01: unchanged** (same file; Edit mode only; person 0.08). Licences of both: **not verified** (SOURCES.txt empty) **[N]**. Nothing
  tuned. The two code commits were first made on local `main` by mistake and moved unchanged to `nusrat/v4-experiments-ab-anime`; the three
  look-check run_info files say `git_branch: main` with commit 66f41f6.

## 2026-11-14, section 6: licences, the two failed looks, reports in the repo (after the step 2b results)

- **Licences re-checked.** `unity/downloads/characters_v4/SOURCES.txt` (git-ignored) is now filled in: anime_f_01 is Nusrat's own character made in
  VRoid Studio and converted to FBX in Blender (VRM Add-on); cartoon_boxo_01 is Nusrat's own character generated procedurally (`make_cartoon_boxo.py`,
  not in this repository) and rigged with Mixamo's auto-rigger; neither is redistributed. Terms of the tools (read through search results; vroid.com
  and helpx.adobe.com refused a direct fetch): the VRoid Studio Guidelines allow any use, commercial included, of models made with VRoid Studio and
  its preset items unless an item carries special clauses; Adobe's Mixamo FAQ says the user keeps the rights to their own creations, allows
  royalty-free use in personal, commercial and non-profit projects and excludes training machine-learning models on Mixamo content (nothing is
  trained here). `looks_ab.json` `licence` of both looks updated; the "not verified" of sections 2 and 5 and of the step 2 and 2b reports is
  superseded by this entry (those texts are kept as written). Both characters stay git-ignored and are never committed.
- **anime_f_01 and cartoon_boxo_01 stay in the avatar experiment as reported failures; neither is used for navigation** (`navigation` false,
  no `proposed_split`). Causes (step 2b report): *anime_f_01* (re-export, arm mesh follows its bones): no POINT, WAIT or STOP sequence read at
  2 m; MediaPipe finds a hand in 0 to 5 % of frames; the POINT clips fold the forearm on this rig (bone arm-to-shoulder ratio 2.28 vs 1.683);
  facing 0.07 (the bangs cover one eye). *cartoon_boxo_01*: one finger chain per hand, so no hand shape at all (WAIT and STOP impossible by
  construction, the worker template cannot shape its hand, so it is checked in Edit mode only); YOLO finds a person in 8 % of frames.
- **Reports in the repo.** Verbatim copies (byte-identical) of the step reports from the git-ignored `robot_vision/outputs/` are tracked in
  `Avatar/Config/reports_v4/`: `experiments_ab_step1_20261114.md`, `experiments_ab_step2_avatars_20261114.md`,
  `experiments_ab_step2b_anime_cartoon_20261114.md`, and the roadmap proposal's README as
  `experiments_ab_roadmaps_20261114_025749_README.md` (its map files stay in the output folder). Paths inside them are relative to
  `robot_vision/outputs/` as written.

## 2026-11-14, section 7: the final matrix of the new study (declared before any final config, guard or launcher change; nothing run)

Branch `nusrat/v4-finals-ab` (from main 15f70cf). Unity side only: no file under `robot_vision/`, `docs/` or `external/` is changed, nothing is
frozen, no final and no development run is made (step 5, the development runs, waits for Anisha's false-STOP fix, AUDIT.md 16.12 item 1).
**The new study replaces the four v4 finals** `zoom_on`, `zoom_off`, `bystanders`, `zoom_on_repeat`: their Unity files are kept and marked
superseded, and the Unity guard refuses them from now on (section 7 step 2). Whatever Python needs is listed for Anisha in a file under
`robot_vision/outputs/` (step 7), never in her files.

**The matrix (9 final settings, each run once).**

| setting | experiment | set (lie p) | map (scenarios_ab.json) | A2 side | goal | layout | workers per asking node |
|---|---|---|---|---|---|---|---|
| `A1` | A1 | A (0.0) | `corridor` | - | B | beside | 2 at A |
| `A2_right` | A2 | A (0.0) | `turn` | right | C (26.25, 0) | beside | 2 at A and at B |
| `A2_left` | A2 | A (0.0) | `turn_left` | left | C (-13.75, 0) | beside | 2 at A and at B |
| `A3` | A3 | A (0.0) | v4 `roadmap.json` | - | GoalSequence(2) over E1..E6 | beside | 2, 3 at J1 |
| `A4` | A4 | A (0.0) | v4 `roadmap.json` | - | GoalSequence(2) over E1..E6 | random | 2, 3 at J1 |
| `B1` | B1 | B (0.2) | `corridor` | - | B | beside | 2 at A |
| `B2_right` | B2 | B (0.2) | `turn` | right | C (26.25, 0) | beside | 2 at A and at B |
| `B3` | B3 | B (0.2) | v4 `roadmap.json` | - | GoalSequence(2) over E1..E6 | beside | 2, 3 at J1 |
| `B4` | B4 | B (0.2) | v4 `roadmap.json` | - | GoalSequence(2) over E1..E6 | random | 2, 3 at J1 |

- **Names.** The setting name is the experiment, plus `_right` / `_left` for the turn map; the Unity session folder is
  `trials_final_Task2_<setting>_<time>`; the same name is proposed as Python's `--final-setting` (step 7) **[A]**.
- **B2 is run with the right turn only** (`B2_right`, paired with `A2_right`, the default side of AUDIT 16.2 decision 1); `A2_left` has no Set B
  counterpart: it shows whether the turn side matters with truthful workers. Adding `B2_left` (+20 runs, about 50 min) is a decision for
  **[N]**, to be declared before the freeze.
- **Fixed numbers, read from Anisha's `configs/v4/final_plan.json` at run time and never copied into a Unity file:** task Task2, final seed **2**,
  **20** runs per setting, timeout **270 s** (`timeout_s`, the declared v4 value; `scenarios_ab.json` `trial_timeout_s` is the same 270 s), success
  radius **0.3 m**. Goals with seed 2: A1 B and A2 C in every run; A3, A4, B3, B4: `GoalSequence(2)` over the sorted endpoints = E5 E1 E5 E2 E5 E3
  E5 E3 E4 E3 E5 E3 E5 E6 E2 E5 E3 E1 E4 E2 (checked equal to Python's `hri_trials.goal_order(2, [E1..E6], 20)` on 2026-11-14). Placements of
  A4 and B4 and the liars of B1 to B4 come from the session seed 2 (`Rng(seed, run, ...)`), so no final run repeats a development scene.
- **Looks: test looks only.** Male slots (1 and 3) wear `sunbox_m_shirt_plaid`, female slots (2) `sunbox_f_shirt_plaid` (data_splits.json `test`,
  Anisha 16.12 item 5). **Clips: test clips only:** POINT `point_mixamo_02`, PROCEED `proceed_ik_03` (an experiment worker shows only these two
  commands). Each run must pass `DataSplitsV4.GuardRun` with final evaluation (wholly test, no mix, no placeholder). *Declared difference from
  development:* with one test look per gender, the third worker at J1 (slot 3, male) wears the same look as the first (slot 1) in A3, A4, B3, B4;
  development rotates two looks per gender, so there two workers of one node never share a look. They are told apart by position only **[A][N]**.
- **Robot side (Python, Anisha's decision) [A][N]: lie detection ON (second opinion + reject impossible, backtrack off; `scenarios_ab.json`
  `detection.on`) in all nine settings,** so that A and B differ only in the lies: the control file per map is
  `configs/v4/experiments/control_lie_on_a1.json` (A1, B1), `control_lie_on_a2_right.json` (A2_right, B2_right), `control_lie_on_a2_left.json`
  (A2_left), `control_lie_on.json` (A3, A4, B3, B4). The detection-off comparison stays in the simulator (16.13.1). Alternative: B1 to B4 also
  with detection off as four more settings (`B1_off` ...; +80 runs, about 2.5 h), declared before the freeze.
- **Unchanged from sections 3 and 4:** maps, slots, the random layout and its 0.25 m margin, the placement rules, activation (8.0 m, at most 6),
  who answers, the lie draw (per worker per run, consistent, valid branch else compass), truth fields, rings. `experiments_ab_unity.json` stays
  as it is; its `a2_sides` (`["right"]`) is overridden per setting by the final config (and in development by a new `-experimentSide`).
- **Unity in final mode (built in steps 2 and 3):** one final config per setting `Avatar/Config/sessions/final_ab_<setting>.json` (experiment,
  side, looks, clips, the Python control file it must run with); `TrialPlayV4 -finalSetting <setting>` only, `-experiment`, `-experimentSide`,
  `-experimentLooks` and `-workersConfig` refused with it; the seed, runs, timeout and radius from final_plan.json; `UNITY_FINAL_DONE.json` at the
  end; a second final of the same setting refused (Unity or Python marker); frozen hashes of the B9 list required (step 4).

**Run count and estimated running time.** 9 settings x 20 runs = **180 runs**. Estimate (scratch script, read-only, from the four Task 2
development sessions on the v4 map: `trials_development_Task2_20261112_163710`, `_173220`, `_214837`, `_20261114_015118` with their bridge folders):
39 successful runs, median travelled / total time **0.434 m/s** (asks included); per-run gap between runs 1.3 s; session start (bridge folder to
Unity `session.json`, Unity opening and model warm-up included) at most 422 s, used for every session. Route length per goal = the median
travelled in those runs (E1 41.1, E2 57.6, E3 57.6, E4 53.9, E5 70.5, E6 74.0 m), A1 and A2 40 m. Lie detection makes every ask node a second
dialog; its cost is taken from the simulator (16.13.1, median on / off: A1 1.21, A2 1.37, A3 1.52, A4 1.43, B1 1.21, B2 1.37, B3 1.63, B4 1.54).

| setting | mean run (s) | longest run (s) | runs over 0.9 x 270 s | session (min) |
|---|---|---|---|---|
| A1, B1 | 112 | 112 | 0 | 45 each |
| A2_right, A2_left, B2_right | 126 | 126 | 0 | 50 each |
| A3 | 214 | 260 | 8 | 79 |
| A4 | 200 | 243 | 1 | 74 |
| B3 | 230 | 279 | 8 | 84 |
| B4 | 216 | 263 | 8 | 80 |
| **total** | | | | **about 9.2 h** (detection off: 6.8 h) |

Caveats: no experiment run has been completed in Unity yet (the two smoke runs of section 4 aborted early), the Task 2 speed comes from runs with
one person per node, and the detection factor is the simulator's; failures that abort early shorten a session.

**Finding (not changed; for [A][N] before the freeze): the 270 s timeout is tight with lie detection on.** The timeout rule (final_plan.json
`timeout_s_source`) was set from Task 2 runs without second opinions. With detection on, the estimate puts the E5 and E6 routes of A3, B3 and B4 at
243 to 279 s, and 8 of 20 runs of each of these settings at more than 0.9 x 270 s, so timeouts are likely in A3, A4, B3, B4. The timeout is a
frozen-plan value of Anisha's and is NOT changed here; a timeout is a result (a failure) as declared. If it is to change, it must be declared and
changed before the freeze.

**Proposed split (the total exceeds 4 h): two sittings on two days, each with the run protocol, every setting its own Unity start.**
- *Sitting 1 (about 4.2 h):* `A1`, `B1`, `B3`, `A3`.
- *Sitting 2 (about 5.1 h):* `A2_right`, `B2_right`, `B4`, `A4`, `A2_left`.
A and B of the same scenario run in the same sitting (same machine state), in alternating order (A first in scenario 1 and 2, B first in 3 and 4).
Both sittings stay above 4 h; the alternative is three sittings, keeping the pairs: {A1, B1, A2_right, B2_right} 3.2 h, {A3, B3} 2.7 h,
{A4, B4, A2_left} 3.4 h **[N]**. Splitting changes nothing in a setting: each setting is one session of 20 runs either way.

**Baseline repair (found 2026-11-14 when both suites were run on 15f70cf before step 1; no behaviour of a reported session changes).** Unity Edit
Mode was 216/221: since Anisha listed the six experiment looks in `data_splits.json` (16.12 item 5), the Task 2 worker plan
(`TrialRunWorkers.Plan` / `PlanFinal`, `looks` empty = every look of the split) picked `sunbox_f_dress_red` and the plaid looks, which only
`looks_ab.json` has, and refused every Task 2 session ("not in worker_v4.json"). Fix: an empty `looks` list means every look of the split *that
the Task 2 template (worker_v4.json) has*: development `sunbox_f1`, `sunbox_m1`, test `sunbox_f2`, exactly as before her change. The test that
pinned the split's names (`Splits_RealFile_HasTheAgreedNames`) now lists her file as it is.

*Step 2, built as declared (final configs).* `final_v4.json` `settings` = the nine experiment settings (`experiment_config` =
`sessions/final_ab_<setting>.json`, `workers_config` = the base `trial_workers_v4.json`, test / test); the four Task 2 settings moved unchanged to
`superseded_settings`, and their session configs (and `rehearsal_zoom_on.json`) say SUPERSEDED at the start of `session_note` (no parsed value
changed). `FinalGuardV4.ExperimentProblems` refuses a final config whose looks or clips are not test (or not navigation looks of the listed gender,
or not clips of their command), whose side, setting name, lie switch or control file do not fit the experiment's map, or whose set fails `GuardRun`
as a final; `FinalGuardV4.ExperimentData` gives a final exactly its config's looks and clips and a development session only development looks and
clips. `TrialRunnerV4` in a final of an experiment setting: experiment and side from the final config (any `-experiment`, `-experimentSide`,
`-experimentLooks` refused), seed `final_seed`, `GuardRun` as a final on every run, the final config copied to `config_used/`. New in development:
`TrialPlayV4 -experimentSide right|left` (the A2 / B2 side for that session; refused on any other map). The freeze list is unchanged until step 4.
Edit Mode test (`FinalExperimentsABTests`) plans the 20 seed-2 runs of every setting with its final looks (placement rules met everywhere; the
in-scene free-cell and collider check runs only at Play).

*Step 3, the final-run guard for the experiment names.* `FinalGuardV4.Problems` (unchanged rules, now with the experiment settings): a setting
must be in `final_v4.json` `settings` and in Python's `final_plan.json` `settings`; a superseded name is refused as superseded; `frozen.json` must
be frozen with every B9 file present, recorded and unchanged; no development override; **each setting once**: a Unity `UNITY_FINAL_DONE.json`
(`final_setting`) or a Python `FINAL_RUN_DONE.json` (`setting`) of the same name anywhere under the output root refuses it, and a marker of another
setting (also `A2_right` vs `A2_left`, or a superseded Task 2 setting) refuses nothing else. A config listing a name both as a setting and as
superseded is invalid. Tests: `FinalExperimentsABTests` (guard section). Today every experiment final is refused (not frozen; not in
`final_plan.json`).

*Step 4, B9 of the new study (`final_v4.json` `freeze_files`, 22 files; `freeze_v4.unity_files` reads this list unchanged).* Kept: the v4 scene,
`bridge_unity_v4.json`, `robot_unity_v4.json`, `worker_v4.json` (looks, clips, gesture variation, question), `WorkerV4.prefab`,
`trial_workers_v4.json` (the experiment settings' `workers_config`), `final_v4.json`, `trial_plan_v4.json`. Added: `looks_ab.json` (the
experiment looks), `experiments_ab_unity.json` (slots, placement margins, who answers, activation, the lie and marker settings),
`roadmap_proposals/turn_left.json` (Unity's left-turn map), the avatar experiment's `Avatar/Config/look_check.json` and `look_check_play_ab.json`
(section 8), and the nine `sessions/final_ab_<setting>.json`. Removed: the four superseded Task 2 session configs (never run). Not hashed, as
before: the code (pinned by the commit in `session.json`) and the third-party and git-ignored avatar assets (each session records their appearance
text). Python's experiment files (`scenarios_ab.json` is frozen already; the `control_lie_*` and `roadmap_a*` files are not yet) are Anisha's.

*Step 5, the launcher (`finals_v4/run_session_v4.ps1`).* `-Experiment A1..B4` with `-Side right|left` for A2 and B2 (required there, refused
elsewhere); the setting must be one of `final_v4.json` `settings`, and its final config names the server's `--control-config`. Rehearsal
(`-Rehearsal [-Trials N]`): Unity `-experiment X [-experimentSide S]`, development looks and clips, dev seed, no `--final-setting`. Final: Unity
`-finalSetting <setting>`, server `--final-setting <setting>`. Refusals as before plus the experiment ones: a Unity Editor running, not on main, a
dirty tree, `trials.local.json`, the setting already run (Unity's or Python's marker), Python's `final_plan.json` or `FINAL_CONTROL` not knowing the
setting or naming another control file, `frozen.json` not frozen, then the server's own `preflight_final`. `-Setting zoom_on` etc. is refused as
superseded. `-DryRun` prints every command and every reason a real run would be refused now. After a valid B11 check it prints the evaluation and
CSV export commands (Anisha's tools; their final mode for the experiments is pending). `final_procedure_v4.md` has a 2026-11-14 block on top.

## 2026-11-14, section 8: the avatar experiment, protocol (declared only; nothing run)

*Corrected 2026-11-21 (section 15 addendum 11):* the look list (15 looks), the role of the looks in no split, PROCEED (recorded),
`cartoon_boxo_01` (Play too), the counts and step 6 (the run-once guard exists) are brought up to what sections 10 and 11 and the section 15
addenda built. The question, the unchanged tool, the order (after the last navigation final) and run-once are unchanged. The text as declared
on 2026-11-14 is in this file's git history.

Question: how does the kind of avatar change what the robot's perception finds and reads (person, arm, hand, the gesture), with the frozen
reader? An engineering measurement with Anisha's `look_check_v4.py` **unchanged** (its rules: `docs/look_check_v4.md`, `configs/v4/look_check.json`);
no value of any tool, reader or config is tuned on it, and its results never feed back into the navigation finals.

**Looks per kind** (the `avatar_experiment` list of `looks_ab.json`; 15 looks). The six looks in no split of `data_splits.json` have role
`avatar_experiment` in `looks_ab.json` (addendum 11): only these look checks record them, and every trial session refuses them
(`DataSplitsV4.GuardRun`). The other nine are the study's Sunbox looks with their splits (role `candidate`).

| kind | looks | recorded in |
|---|---|---|
| realistic human | `mixamo_worker` (role `avatar_experiment`) | Edit mode and Play mode |
| stylised human (Sunbox body family) | split development: `sunbox_m1`, `sunbox_f1`, `sunbox_m_shirt_white`, `sunbox_m_tshirt_black`, `sunbox_f_shirt_white`, `sunbox_f_dress_red`; split test: `sunbox_f2`, `sunbox_m_shirt_plaid`, `sunbox_f_shirt_plaid`; no split: `sunbox_m2` (role `avatar_experiment`) | Edit mode and Play mode |
| anime | `anime_f_01` (the re-export of section 5) and its controlled variants `anime_f_02_outfit_short` (outfit with short sleeves) and `anime_f_03_bangs_parted` (bangs only), added in section 10; all role `avatar_experiment` | Edit mode and Play mode |
| cartoon non-human | `cartoon_boxo_01` (version 3; role `avatar_experiment`) | Edit mode and Play mode: separate finger chains and island-bound hands (section 10, addenda 6 to 13) let the worker template spawn it; it is in `look_check_play_ab.json` `looks` |

No look is added, dropped or replaced because of a result; a look that fails is reported as failed (as anime_f_01 and cartoon_boxo_01 in section 6).
The two anime variants were added in section 10 as controlled variants, before any run of the experiment.

**Commands, distances, repeats** (the existing configs, unchanged):
- *Commands:* POINT, WAIT, STOP, PROCEED and the negative control NONE (the worker idle, facing the robot). PROCEED is recorded since section 10
  item 5 (Play: `look_check_play_ab.json` `proceed.record` true, sequences of 21 frames taken while the forearm swings; Edit: a posed swing,
  section 10 addendum 1); Anisha's tool grades PROCEED when PROCEED recordings exist (`graded_when_present`, AUDIT.md 16.12 item 5).
- *Edit mode* (`Avatar/Config/look_check.json` with the looks of `looks_ab.json`, `LookCheckMenu.BatchRunExperiment`, every look of the list): the declared held
  poses on the neutral stage at 2.0 m (verdict distance) and 4.0 m, both arms, 11-frame sequences (PROCEED 21) and singles as `look_check.json`
  `recording`: 2 sequences + 5 singles per group, 18 groups, 126 recordings and 566 frames per look; 15 looks = 270 groups, 1 890 recordings,
  8 490 frames (the rehearsal of 2026-11-20, `look_check_ab_20261120_231306`). Edit takes are held poses, not clips: their rows carry `clip` ""
  and `pose` "posed" (addendum 11).
- *Play mode* (`Avatar/Config/look_check_play_ab.json`, unchanged: venue `WarehouseRobot_v4.unity`, the J1 and J2 worker stands, asking bearings
  15 to 50 deg, real motion with the worker template, seed 1): per look, command, distance (2.0 and 4.0 m +- 0.15 m) and arm (left, right; NONE
  has none): **2 sequences + 16 single frames** per group, sequences of 11 frames (PROCEED 21), so 38 frames per group (PROCEED 58): 12
  POINT/WAIT/STOP groups (456 frames), 4 PROCEED groups (232) and 2 NONE groups (76) = 18 groups, 324 recordings and **764 frames per look**;
  15 looks = 270 groups, 4 860 recordings, **11 460 frames** (the rehearsal of 2026-11-21, `look_check_play_ab_20261121_151205`, 131 min). Each
  row names its clip (`recordings.jsonl` `clip`, and `clip` in every truth row). Since addendum 11 each round of looks starts with a shader
  warm-up (no recording). The seed is the one of the step 2 check (the same poses are drawn again, so the numbers are comparable with that
  engineering check, which is not part of the experiment).
- *Measures, per look and summed per kind:* the fields of Anisha's report (person found, arm valid, hand linked, own cue, wrong class, sequence
  read, arm-to-shoulder ratio p95, facing, verdict) at 2.0 m and at 4.0 m, each with its count (coverage); plus the Unity-side checks of section 2
  (bone arm-to-shoulder ratio against 1.683, hand reach to the IK target, the mirror-rest correction, material problems, magenta pixels).

**How it runs, once, after the freeze.**
1. Precondition: `configs/v4/frozen.json` frozen with every hash matching, *and the last navigation final of section 7 is done* (so no avatar
   result can influence a final). The configs it reads (`looks_ab.json`, `look_check.json`, `look_check_play_ab.json`, `worker_v4.json`,
   `WorkerV4.prefab`, the v4 scene) are on the B9 list (section 7 step 4) and therefore frozen.
2. On main at the frozen commit, clean tree, Nusrat's PC, the run protocol (other apps closed, Best performance; `run_protocol_v4.ps1 -Label avatar_experiment`).
3. Edit mode (batch mode works for it), from the repository root:
   `& "C:\Program Files\Unity\Hub\Editor\2022.3.62f3\Editor\Unity.exe" -batchmode -quit -projectPath unity\Robotics-Warehouse\WarehouseProjectURP -executeMethod WarehouseAvatar.EditorTools.LookCheckMenu.BatchRunExperiment -avatarExperiment -logFile robot_vision\outputs\avatar_experiment_edit_<time>.log`
   -> `robot_vision/outputs/look_check_ab_<time>/`.
4. Play mode in the Editor WINDOW (no `-batchmode`, as the finals):
   `& "C:\Program Files\Unity\Hub\Editor\2022.3.62f3\Editor\Unity.exe" -projectPath unity\Robotics-Warehouse\WarehouseProjectURP -executeMethod WarehouseAvatar.EditorTools.LookCheckPlayMenu.CommandLineRunAB -avatarExperiment -lookCheckTimeout 10800 -logFile robot_vision\outputs\avatar_experiment_play_<time>.log`
   -> `robot_vision/outputs/look_check_play_ab_<time>/` (recordings in its `looks_check_<time>/`).
5. From `robot_vision\`: `.\.venv\Scripts\python.exe look_check_v4.py --input <the recordings folder of the Edit-mode run>` and the same for the
   Play folder; nothing else is run on them. A cyan-placeholder frame (section 5, addendum 2) or a crash is reported as it is; the run is **not
   repeated** (as for a final). The step 2 and 2b look checks stay engineering checks and are not results of the experiment.
6. Run once: the two output folders (identified by their `run_info.json` commit = the frozen commit and `avatar_experiment_part` "edit" /
   "play") are the avatar experiment. Enforced since section 10 item 6 by the run-once guard (`avatar_experiment.json`, `AvatarExperimentGuard`):
   only with the `-avatarExperiment` flag, frozen B9 files unchanged, every navigation final done, no look subset, and no earlier
   `AVATAR_EXPERIMENT_STARTED.json` / `AVATAR_EXPERIMENT_DONE.json` of the same part.
7. Reported per kind and per look with every rate's count; the test looks are reported like the others (the finals are over by then).

## 2026-11-14, section 9: what the Python side needs for these finals (step 7)

Written for Anisha to `robot_vision/outputs/for_anisha_finals_ab_20261114_164233.md` (git-ignored; a byte-identical copy is tracked in
`Avatar/Config/reports_v4/`): the decisions before the freeze (lie detection in the finals, the 270 s timeout, B2 sides, the shared J1 look, the
sittings), the nine `final_plan.json` settings and their test assignment, the `FINAL_CONTROL` entries, the experiment control and map files for the
freeze, and a final mode of the evaluation and CSV export per experiment. None of her files was changed.

## 2026-11-14, section 10: avatar pipeline fixes before the freeze (declared before any change; nothing run)

Branch `nusrat/v4-finals-ab` (HEAD 085e4ff). Unity side only: nothing under `robot_vision/`, `docs/` or `external/` is changed, nothing is frozen, no
final and no navigation run is made. The avatar-experiment configs are on the B9 list (section 7 step 4), so these fixes come before the freeze.
**Integrity rule:** every fix is verified GEOMETRICALLY (bone and joint positions of the rendered pose against the intended pose; the arm-skin probe
of section 5 shows the meshes follow these bones). **No perception** (YOLO, MediaPipe, `look_check_v4.py`) is run on any avatar-experiment look in
this work: the avatar experiment measures perception once, after the finals (section 8). Nothing is tuned on a perception result.

**Inputs** (`unity/downloads/characters_v4/`, git-ignored, never committed):
- `cartoon_boxo_01.fbx` **version 2** (sha256 `00fbf466...`, 366 096 bytes): fingers fanned with gaps of at least 3 cm so Mixamo's auto-rigger
  separates them, rigged with Mixamo's Standard Skeleton (65). Version 1 (`431e6cb2...`, the imported file of sections 2 and 5) is kept in
  `unity/downloads/superseded/`. Its generator `unity/tools/avatars/make_cartoon_boxo.py` (v2) is committed with step 3.
- `anime_f_02_outfit_short.fbx` (`d94b472a...`, 11 192 092 bytes) and `anime_f_03_bangs_parted.fbx` (`a3cf3439...`, 10 025 164 bytes): Nusrat's
  **controlled variants of anime_f_01**. 02 changes the outfit, sleeves included (short sleeves); hair, face and body as 01. 03 changes only the
  bangs (parted, both eyes visible); outfit, face and body as 01.
- *Found, not changed:* `SOURCES.txt` names the third file `anime_f_03_hairback.fbx` ("hair tied back, same outfit"), but the file present is
  `anime_f_03_bangs_parted.fbx` and the task describes parted bangs. The licence statement is the same (Nusrat's own VRoid character, converted in
  Blender, not redistributed); `looks_ab.json` uses the file name and the task's description. SOURCES.txt is Nusrat's record and is not edited **[N]**.

**1. Arm scaling.** What is Sunbox's in `WorkerV4.ComputeTargets` today (every target is already an offset from the rig's own shoulder bone, in units
of its own shoulder-to-wrist length L): PROCEED splits L into upper arm 0.53 L and forearm 0.47 L; the elbow hints of POINT and STOP lie 0.5 L along
the arm and the WAIT hint ("forearm vertical") 0.5 L below the hand, i.e. an arm with equal segments. *Change:* each rig is measured once at
`Initialize`, in its rest pose before any animation: upper arm `Lu` (UpperArm to LowerArm bone), forearm `Lf` (LowerArm to Hand), `L = Lu + Lf` (as
now), shoulder width `W` (between the two upper-arm bones) and shoulder height `H` (upper-arm bones above the worker's root). PROCEED: the elbow at
`Lu` from the shoulder and the hand at `Lf` from the elbow; POINT and STOP hints at `Lu` along the arm; WAIT hint `Lf` below the hand. The other
offsets stay fractions of the rig's own L from its own shoulder bone, which already carries W and H; W and H are recorded per look and enter the
check's body frame. `worker_v4.json` values are not changed.
*Baseline first:* the geometry check below runs once on the UNCHANGED code (baseline, kept and reported), then on the changed code. If the baseline
shows a cause this change does not cover (for example the anime forearm fold of section 5, which was read from YOLO's wrist, not from bones), it is
written here as an addendum before any further change.

**2. Geometric verification (`GestureGeometryCheck`, Play mode).** Stage: a new unsaved scene (grey floor, one directional light, no warehouse), one
worker template per look, each on its own spot 4 m apart, a stand-in robot 2.0 m in front of it. Looks: every look of `looks_ab.json`
`avatar_experiment` the worker template can spawn, plus the two anime variants (and Boxo v2 if its hands can be shaped). Per look: every clip of
POINT, PROCEED, WAIT and STOP in `worker_v4.json`, both arms; POINT at side azimuth 0 and 45 deg (the look check's convention); variation stream
`SetRun(1, take)`. Measured after the worker's LateUpdate (hand shape, torso turn) on 5 frames spread over the hold, PROCEED on every frame of 2.0 s
of the swing, from the bones: shoulder S (UpperArm), elbow E (LowerArm), wrist Wr (Hand). *Intended pose* = the worker's own goal of that frame:
hand target T from shoulder s; intended elbow interior angle = the two-bone angle of `|T - s|` with the rig's `Lu`, `Lf` (180 deg if out of reach);
intended arm direction = `(T - s)`; PROCEED also the intended elbow E* and forearm direction `(T - E*)`; WAIT forearm direction = up.
*Measures:* elbow interior angle `angle(S - E, Wr - E)` minus intended; arm direction `angle(Wr - S, T - s)`; forearm direction `angle(Wr - E, intended)`
(WAIT, PROCEED). **Tolerance (declared now, in a new config `Avatar/Config/gesture_geometry.json`):** elbow angle within **10 deg**, arm direction
within **5 deg**, forearm direction within **10 deg**, and **no fold**: the elbow interior angle of POINT and STOP at least **120 deg** (POINT's design
is 144 to 163 deg, `worker_v4.json` limits). A look x command passes when every measured frame of every take passes. **No regression:** every
Sunbox look and mixamo_worker must pass after the change; the largest shift of a hand target between the old and the new formula is reported per look.
Output `robot_vision/outputs/gesture_geometry_<time>/` (geometry.json, a per-look table, run_info.json with the commit); the table is copied
byte-identical to `reports_v4/`. Edit Mode tests: the two-bone angle, the measures and the pass rule on synthetic arms, and the new targets on a
synthetic rig (the old targets equal for an arm with Lu = 0.53 L).

**3. Boxo v2.** The v1 import folder `Assets/ThirdParty/CharactersV4/cartoon_boxo_01/` (and its `.meta`) is moved, not deleted, to the git-ignored
`unity/downloads/superseded/cartoon_boxo_01_431e6cb2_import/`, then `Import Characters` runs unchanged (scale, texture, emission and recolour rules
of sections 2 and 5). Report: each hand's bones (every chain under the Hand bone, by name) and the Humanoid finger mapping; **finger skin probe**
(new, report only, like the arm-skin probe): per hand, each finger chain's proximal bone is bent 30 deg about the axis across the finger (finger
direction x palm normal) and every skinned mesh is baked before and after; a vertex *moves* when it moves more than 2 mm; a finger's *region* = the
rest-pose vertices within 4 cm of its own bone chain (base to the end of its last bone) and nearer to it than to any other chain of that hand. A
finger is **separate** when at least 80 % of its own region moves and at most 20 % of every other finger's region moves; fewer than 30 vertices in
its region = inconclusive. Colours: every material with its shader, base colour and base texture (recolour rule unchanged); **error-shader check**:
a material on `Hidden/InternalErrorShader` or without a URP pass, and the magenta pixels of a neutral render (`LookInventory.MagentaPixels`).
**If the fingers are still one chain, the work STOPS there and is reported.** If both hands have the index to little bones the worker template needs,
Boxo joins the Play look check (`look_check_play_ab.json`; its exclusion was "cannot be spawned", section 2 rule) and the geometry check.

**4. Anime variants.** Imported by the same importer, unchanged; arm-skin probe (section 5 rule). **Controlled-variant check** (geometric, report
only): every mapped Humanoid bone's rest position of each variant against anime_f_01 (same body = all within 1 mm), and the skinned meshes compared by
name and vertex count (which meshes differ; expected: 02 the clothing, 03 the hair). Added to `looks_ab.json` under kind `anime`
(`navigation` false, no proposed split, licence from SOURCES.txt) with `variant_of` `anime_f_01` and `variant_changes`, and to `avatar_experiment`
after anime_f_01 (15 looks). A result is reported as it comes; nothing is adjusted on it.

**5. PROCEED in the Unity look-check recordings (changes section 8 before anything ran).** The Play-mode look check of the avatar experiment
(`look_check_play_ab.json`) records PROCEED for every look it spawns, in Anisha's format (`configs/v4/look_check.json` `graded_when_present`): the
same takes as the other commands (2 sequences + 16 singles per distance and arm, the PROCEED variants cycling), sequences of **21 frames** at 10 Hz
(2.0 s, the reader's `proceed.window_s`) taken during the swing, singles at a random moment of it; names `<look>__PROCEED__<d>__<arm>_<take>`, the arm
label and the real `time_s` in every header. `look_check_play.json` (the v4 Phase 2 check) is unchanged. The Edit-mode stage shows held poses only;
a look the worker template cannot spawn gets PROCEED there as a posed swing of 21 frames (`LookPoser`, the proceed_ik_01 swing at 1.5 Hz), built
only if such a look remains after step 3.

**6. Run-once guard of the avatar experiment (replaces section 8 step 6, "no code guard").** New config `Avatar/Config/avatar_experiment.json`. An
official run is started with `-avatarExperiment` on `LookCheckMenu.BatchRunExperiment` (part `edit`) or `LookCheckPlayMenu.CommandLineRunAB` (part
`play`) and is refused unless: `frozen.json` is frozen with every B9 file recorded and unchanged (the rule of `FinalGuardV4`); every final setting of
`final_v4.json` has its `UNITY_FINAL_DONE.json` (section 8 precondition); no `-lookCheckLooks` subset; and no marker of the same part exists under
`robot_vision/outputs/`. It writes `AVATAR_EXPERIMENT_STARTED.json` before the first render (so a crashed run also counts as run) and
`AVATAR_EXPERIMENT_DONE.json` at the end; either marker of a part refuses a second run of that part. Without `-avatarExperiment` the tools stay
engineering checks and are never the experiment. Edit Mode tests of every refusal.

**7. B9.** `avatar_experiment.json` and `gesture_geometry.json` join `final_v4.json` `freeze_files`; the changed `looks_ab.json`,
`look_check_play_ab.json` and `worker_v4.json` (if changed) are already on it.

**8. Screenshots for Nusrat's visual check** (not perception input): from the geometry check's neutral camera, NOT the robot cameras' settings:
3.0 m in front of the worker, 20 deg to its right, 1.3 m high, vertical field of view 35 deg, 1280 x 960 PNG, in the middle of the hold (PROCEED: at
the top of the swing), every anime look and Boxo, each of POINT, PROCEED, WAIT and STOP, both arms, into `gesture_geometry_<time>/screens/`.

*Addendum 1 (2026-11-14, after the Boxo v2 import and its finger probe; before the arm-scaling change, the Edit-mode PROCEED or any screenshot).*
Results: `import_characters_20261114_180918` (Boxo v2: unit scale x100 and avatar rebuilt as section 2, humanScale 0.774, bone height 1.138 m; 46
Humanoid bones; finger bones **24 of 30**: thumb, index, middle and ring mapped, **no little finger** on either hand; `glovemat` and `helmetmat`
recoloured, `eye_whitemat` and `stripemat` colourless and matched by no rule; the variants: 55 bones, 30 of 30 finger bones, 25 textures linked).
`probe_fingers_20261114_181109`: **Boxo v2 has 4 chains per hand (Thumb, Index, Middle, Ring) and every finger is separate** (own region 93 to 100 %
moves, no other finger's region more than 4 %); no material problem, 0 magenta pixels. Controls: mixamo_worker 5 separate chains per hand (own 87 to
96 %, others at most 7 %); anime_f_01 reads "merged" by the rule (own 61 to 89 %, others at most 15 %: no finger moves its neighbour, but the 4 cm
region of this small hand reaches palm vertices weighted to the hand bone), reported as it is, the rule is not changed. So the fingers are no longer
one chain and the work continues. **Consequences (declared now):**
- Boxo v2 still cannot be spawned by the worker template: `HandShaper` needs index to little (section 2 rule; the template is not changed to make a
  look pass; a three-finger hand shape would be a template change for **[N]**). It stays out of the Play look check and the Play geometry check;
  `look_check_play_ab.json` `looks_excluded` gets the new reason. It stays in the Edit-mode look check (which records it as before).
- Item 5 applies: **PROCEED is added to the Edit-mode look check** (`look_check.json`) for every look of it, as a posed swing: upper arm down and
  `upper_forward_deg` forward with the elbow 0.08 L out, forearm at `phi(t) = low + (high - low) * (1 - cos(2 pi f t)) / 2`, f 1.5 Hz,
  t = frame / 10 s; flat hand, fingers along the forearm, palm toward the body (the worker's PROCEED shape). Takes: two 21-frame sequences
  (`seq1` = proceed_ik_01: 15, -20, 60 deg; `seq2` = proceed_ik_02: 35, 0, 75 deg) and singles at fixed phases of proceed_ik_01 (forearm at -20, 0,
  20, 40, 60 deg), with no `time_s` (Anisha's tool then uses 10 Hz). A sequence's frames are rendered one by one (the held-pose sequences keep one
  render per sequence). Recordings named as the others.
- **Boxo's geometric check comes from its Edit-mode poses** (`LookPoser`, every POINT, WAIT, STOP and PROCEED take of `look_check.json`, both arms):
  rendered elbow angle, upper-arm and forearm directions against the pose's intended ones, with the declared tolerance (elbow 10 deg, upper-arm
  direction 5 deg in place of the shoulder-to-wrist direction, forearm 10 deg; no fold for the POINT and STOP poses designed straight: the STOP takes
  with `forearm_up` are bent by design since Phase 2A). The same Edit-mode geometry is reported for every look of the Edit-mode check
  (`pose_geometry_<time>/`).

*Addendum 2 (2026-11-14, after the baseline geometry run, before the arm-scaling change).* Baseline `gesture_geometry_baseline_20261114_182535`
(commit 3e6054b, targets unchanged; 12 looks spawned, Boxo not: "lacks arm or finger bones"). **POINT and WAIT pass on every look, anime_f_01
included**: its POINT elbow is never below 151.0 deg (intended 151.9 to 157.0), so the "forearm folds back" of section 5 is NOT in the bones; it was
read from YOLO's wrist on the rendered frames (the wide sleeve), which this work does not measure. **PROCEED fails on every look** (forearm 10.7 to
12.9 deg off its goal): the Sunbox split and the sideways offset put the intended elbow where the arm cannot reach, exactly what item 1 changes. No
other cause is found, so no further change is added. Measured proportions: upper-arm share of L 0.512 (every Sunbox look), 0.536 (mixamo_worker),
0.514 (anime_f_01); arm-to-shoulder ratio 1.590, 1.098, 2.241. **Found, not changed (decision for [N]):** STOP is flagged "fold" on 10 looks at
elbows of 116.2 to 119.8 deg with an elbow error of at most 0.7 deg there: the rendered pose equals the intended one, and the intended one is
`worker_v4.json` `limits.stop_reach` [0.85, 0.97] at its lower bound (0.85 L gives 116 deg). The declared no-fold threshold (120 deg) is stricter
than the frozen STOP design; neither is changed after seeing this. STOP is reported with this split: elbow, direction and forearm checks
(rendering) and the no-fold check (design) separately.

*Addendum 3 (2026-11-14, after the first run with item 1, before any further change).* `gesture_geometry_after_20261114_183103` (item 1 applied,
uncommitted, on 3e6054b): POINT, WAIT and the rendering of STOP pass on every look as before; PROCEED's forearm error falls from 12.3 to 12.9 deg
(Sunbox) to 10.1 to 10.6 deg (mixamo_worker 10.9 to 11.2) but still exceeds 10 deg, **with an elbow-angle error of 0.0 and an arm-direction error of
0.0 deg on every frame**: the hand is on its target and the elbow has the intended angle, so the only freedom left is the elbow's swivel about the
shoulder-to-hand axis, which Mecanim takes from the hint. PROCEED's hint lies 0.1 L sideways and 0.02 L below the intended elbow, so the bend plane
misses it. *Change (a cause item 1 does not cover):* with the rig split, PROCEED's hint is the intended elbow pushed away from the shoulder-to-hand
axis (hint = E* + 0.5 L x the unit vector from the axis to E*), so the bend plane contains E*; with the legacy split the old hint is kept (it stays
the reference of the target-shift column). Nothing else changes; the tolerance stays.

*Results (2026-11-14, steps 1 to 7 committed 67efb67 to aa3db71; report `reports_v4/avatar_pipeline_fixes_20261114.md`, a byte-identical copy of
`robot_vision/outputs/avatar_pipeline_fixes_20261114.md`, with the geometry tables next to it).* Geometry on aa3db71
(`gesture_geometry_final_20261114_193832`, 14 spawnable looks): POINT, PROCEED and WAIT within tolerance on every look; PROCEED's forearm error
11.1 to 12.9 deg (baseline) -> 0.0 deg; anime_f_01's POINT elbow at least 150.9 deg before and after (no fold in the bones). STOP: the design's
116 deg elbows (addendum 2, [N]) and one out-of-reach take of anime_f_02 (168.8 vs 180 deg, direction exact). Boxo v2: four separate finger chains
per hand, no little finger, so still Edit mode only ([N]); Edit-mode pose geometry of every look within tolerance (`pose_geometry_20261114_194216`).
Variants: 02 differs in the clothing mesh and its materials (the skeleton shifted by 1.55 mm as a whole), 03 only in the hair mesh. PROCEED is in
both look checks (format checked: 21 frames, Play spans 2.006 to 2.015 s after a timing fix of the first try's 1.990 s). The run-once guard refuses
both parts today (not frozen, finals not done). SOURCES.txt's name for anime_f_03 differs from the file **[N]**. No perception was run.
- **Boxo's screenshots come from its Edit-mode poses** with the neutral camera of item 8 (POINT and WAIT `seq1`, STOP `seq1`, PROCEED at the top of
  the `seq1` swing; both arms). The anime looks' screenshots come from the Play geometry check (the worker template), as declared.

## 2026-11-14, section 11: Nusrat's decisions on the section 10 results (declared before any change; nothing run)

Branch `nusrat/v4-avatar-fixes` (renamed from `nusrat/v4-finals-ab`; HEAD e6c6bfd, `main` merged in, Anisha's PR #35 false-STOP analysis
included). The rules of section 10 stay: Unity side only (nothing under `robot_vision/`, `docs/` or `external/` changes), every fix verified
GEOMETRICALLY, **no perception** (YOLO, MediaPipe, `look_check_v4.py`) on any avatar-experiment look, nothing frozen, nothing pushed, one commit
per decision. Nusrat has corrected `SOURCES.txt` (the third anime file is `anime_f_03_bangs_parted.fbx`), which closes the section 10 [N] on its name.

**1. Check correction (the no-fold rule).** The 120 deg no-fold rule was meant for extended gestures only. Nusrat named POINT and PROCEED.
PROCEED's elbow is bent by design, though: 38 to 125 deg over the swing (`gesture_geometry_final_20261114_193832`, rendered with 0.0 deg error),
so the rule would flag almost every PROCEED frame. Asked about this, Nusrat chose (2026-11-14) **POINT only**: `gesture_geometry.json`
`no_fold_commands` becomes `["POINT"]`. STOP, PROCEED and WAIT are checked against their own design elbow angle within the 10 deg elbow
tolerance, which is the existing elbow measure (the two-bone angle of the take's target with the rig's own upper arm and forearm). Both geometry
tools read the rule from the config (the Play check and the Edit-mode pose geometry). This corrects a mis-specified check, not the avatars; the
STOP design (`worker_v4.json` `limits.stop_reach` [0.85, 0.97]) is not changed. *Disclosed:* a check rule changed after its results were seen
(section 10 addendum 2), by Nusrat's decision.

**2. Reach cap.** `GestureTargets.Compute` caps the hand target's distance from the shoulder, `|T - s|`, after the size and the STOP push are
applied, at the command's own maximum reach in the rig's own `L` (upper arm + forearm, measured per rig in section 10). The caps are
POINT `limits.point_reach[1]` (0.99 L) and STOP `limits.stop_reach[1]` (0.97 L). WAIT and PROCEED are capped at `L`; their designs never
reach it, so this cap is a guard only. The target moves toward the shoulder along `T - s`, so its direction is kept, and the elbow hint is
unchanged. The cap level is Nusrat's answer (2026-11-14) to whether "the rig's own reach" means `L` or the command's maximum: Mecanim does not
straighten an arm fully, so out-of-reach takes rendered at 168.8 to 174 deg against an intended 180 deg. `worker_v4.json` is not changed.
The legacy goal (the "target shift vs old" column) stays uncapped, so that column shows what the cap moved. Expected effect: only STOP takes
whose push carried the target beyond 0.97 L. anime_f_02's STOP is re-verified. Edit Mode tests: a pushed STOP target is capped at exactly
0.97 L in its own direction, and a take within reach is unchanged bit for bit.

**3. Boxo in Play mode (the worker template accepts hands without a little finger).** `HandShaper.Complete` now requires the upper arm,
forearm, hand and the index, middle and ring proximal bones; the little finger is optional. Two hand measures used the little finger's base:
the palm normal (`LookPoser.PalmNormal`, from the index and little bases) and the thumb's swing across the palm. Both now use the outermost
finger present (little, otherwise ring). Every shape bends only the bones that exist, as before. On a five-finger rig every code path is the
one used before.
**Proof that five-finger looks are unchanged:**
- (a) An Edit Mode test with golden values computed by the UNCHANGED code before the change: a synthetic five-finger hand, every hand shape of
  `worker_v4.json`, both hands, every finger joint and tip within 1e-6 m. It is committed with the change and must pass before and after.
- (b) A new Edit-mode tool, `ExperimentLooksMenu.BatchHandShapes`, runs on every installed avatar-experiment look. It writes every finger
  bone's world position and rotation after `HandShaper.Apply` for every hand shape and both hands, on the rest pose with fixed directions and
  `MirrorRest` as the template applies it. It runs before and after the change, and the two outputs are compared value for value: every
  five-finger look must be **exactly** equal.
- A Play run is not bit-reproducible (it depends on frame timing), so the identity is proven in Edit mode on the functions the template
  calls. The Play geometry rerun (item 7) then shows every look within tolerance.

Boxo then joins `look_check_play_ab.json` `looks` (its exclusion is removed), the Play geometry check and its screenshots, PROCEED included. A
**format check** of the Play recordings runs on Boxo alone (`-lookCheckLooks cartoon_boxo_01`; an engineering check, not the experiment; no
perception). *Disclosed:* Boxo's Edit-mode poses change too, because before this its palm was never turned (`PalmNormal` found no little finger).

**4. anime_f_02's black patches (alpha clipping in the importer).** The cause was found by reading the files only. Every imported anime
material is URP Lit, Opaque. The FBX (Blender's export) links an alpha texture (`TransparencyFactor`) only on the EyeIris, EyeHighlight,
FaceBrow, FaceEyelash and FaceEyeline materials. Each base texture carries VRoid's cut-out mask in its alpha channel; for example, anime_f_02's
dress textures `_15` and `_19` have 96 and 99 % of their texels below alpha 0.5, black underneath. The FBX conversion lost the clothing
material's cut-out link, so opaque rendering shows those texels black.
*Rule (`ExperimentLooksMenu.ImportOne`, every look it imports):* a material whose base texture has an alpha channel with at least 0.1 % of
its texels below 0.5 gets URP alpha clipping: `_AlphaClip` 1, `_Cutoff` 0.5 (URP's and glTF's default), keyword `_ALPHATEST_ON`, render
queue AlphaTest, RenderType TransparentCutout. The surface stays opaque, with no blending. It applies to anime_f_01 and 03 as well (same
importer, same kind of textures), so the controlled variants stay controlled; Boxo's materials carry no texture and are unaffected.
Import Characters is re-run (the imports are kept, only material settings change, all git-ignored), with each clipped material in the import
report. New screenshots come from item 7.

**5. anime_f_02's skeleton shift (1.55 mm as a whole) is an export difference and is accepted.** It is recorded in `looks_ab.json`
`variant_changes` of anime_f_02. The variant probe's 1 mm "same body" rule and its result stay as reported. In the same commit, the anime_f_03
licence text drops the SOURCES.txt name mismatch (corrected by Nusrat).

**6. Note for Anisha** (`reports_v4/for_anisha_avatar_fixes_20261114.md`):
- PROCEED changed on every look (forearm error about 12 deg -> 0.0 deg; hand target moved by up to 22 mm), so her false-STOP fix (PR #35)
  must be confirmed on the new PROCEED pose in step 5.
- The anime "fold" was YOLO placing the wrist on the sleeve, not the bones (POINT elbow at least 150.9 deg before and after).
- Items 2 and 4 change some STOP takes and the anime looks' materials.

A Unity-side note only; nothing of hers is edited.

**7. Rerun.** `gesture_geometry.json` `screens.kind_groups` becomes every group (realistic_human, stylised_human, anime, cartoon_non_human),
so there is a screenshot of every look, each command and both arms. Then:
- the Play geometry check of every look of `avatar_experiment`, Boxo included (label `decisions`);
- the Edit-mode pose geometry, since item 1 applies to it.

Tables are copied byte-identical to `reports_v4/`. No perception is run, and nothing is tuned on these results.

*Results (2026-11-14; items 1 to 7 committed 29507fd to a5c032b, one commit each, every tree tested by Unity; Python 1108 OK on e6c6bfd
and on the item 6 tree).*
- **Geometry, Play** (`gesture_geometry_decisions_20261114_210047`, commit a5c032b, clean tree; table in `reports_v4/`): **all 15 looks
  pass** every command, Boxo included (spawned by the template; upper arm / forearm 0.247 / 0.240 m). POINT elbow at least 150.8 deg; PROCEED
  forearm error 0.0 deg on every look; STOP elbow error at most 0.9 deg.
- **anime_f_02's STOP**: 11.2 deg -> 0.9 deg (the out-of-reach take is capped). The cap moved STOP targets by up to 41 mm (sunbox_f_dress_red;
  the "target shift vs old" column, legacy uncapped). The design's 116 deg STOP elbows remain, and pass against their own design (item 1).
- **Five-finger looks unchanged** (item 3): the golden test passes, and `hand_shapes_20261114_203658` against `_202913` is identical on all
  14 five-finger looks (3584 lines). Only Boxo differs: its hands are now shaped.
- **Pose geometry, Edit mode** (`pose_geometry_20261114_210511`): all 15 looks render within tolerance, with no fold flag.
- **Alpha clipping** (`import_characters_20261114_204415`): 14 materials per anime look (face, eyes, hair back, body mask, clothing, shoes)
  and none on Boxo. The 120 screenshots (`gesture_geometry_decisions_20261114_210047/screens/`) show anime_f_02's dress without the black
  patches.
- **Boxo's Play recordings, format check** (`look_check_play_ab_debug_20261114_210603`, `-lookCheckQuick cartoon_boxo_01`, not the
  experiment): 36 recordings, 476 frames, none outside the hold. PROCEED sequences have 21 frames spanning 2.005 to 2.018 s.
- **Seen in the screenshots, not changed (for Nusrat's visual check):** Boxo's WAIT raises the index finger, but its flat black palm plate is
  seen edge-on and the thumb stands out to the side.

No perception was run.

## 2026-11-14, section 12: palm orientation and the WAIT thumb in the geometry check (declared before building or measuring; nothing run)

Nusrat's check before the merge (branch `nusrat/v4-avatar-fixes`, HEAD 045dce5). The rules of sections 10 and 11 stay: Unity side
only, geometric, **no perception**, nothing frozen, nothing pushed.

**Added to the Play geometry check** (`GestureGeometryDriver`), for every look of `avatar_experiment`, both arms, on the same measured hold
frames of every STOP and WAIT take:
- **Robot camera point C:** the stand-in robot's eye on the stage (the worker's `robotEye`, 2.0 m in front of it at 1.2 m height). It is
  the point the worker turns its palm toward.
- **Hand frame from the rendered bones:**
  - palm centre P is the mean of the hand bone and the index, middle and outermost (little, else ring) proximal bones;
  - palm length Lp = |middle proximal - hand|;
  - finger direction = middle proximal - hand.
- **Palm normal, bones:** `LookPoser.PalmNormal`, the convention the hand shaper aligns.
- **Palm normal, mesh** (independent of that convention: what the camera sees):
  - The vertices are the rendered skinned-mesh vertices whose largest bone weight is on the Hand bone and is at least 0.5, lying between
    the wrist and the finger bases along the finger direction (0 to Lp from the hand bone). This keeps out sleeves and forearm.
  - The normal is their plane fit (the least-variance axis of the covariance), with its sign chosen to agree with the bone normal.
  - It is *undetermined* with fewer than 30 vertices or a flatness (smallest / middle variance) above 0.5. An undetermined mesh normal
    is reported as "mesh n/a" and the palm check then rests on the bone normal; it is never counted as a pass of the mesh part.
- **Palm facing (STOP and WAIT): the angle between each palm normal (bones, and mesh when determined) and C - P is at most 30 deg.**
- **WAIT thumb, curled toward the palm:** the thumb tip Tt (`HandShaper.Tip`, one distal-bone length beyond the distal joint) is
  *tucked* when **|Tt - P| <= 1.0 Lp** (over the palm, not sticking out) **and (Tt - P) . n_bones >= 0** (on the palm side). Also
  reported, not judged: the tip's position across the palm (0 at the index base, 1 at the outermost base).
- **Pass rule:** a look x command passes the hand check when every measured frame passes. It is reported per look in a separate hand
  table (`hand_table.md`) and in `geometry.json`; the arm columns and their pass are unchanged. Values go to `gesture_geometry.json`
  `tolerance` (`palm_facing_deg` 30, `palm_commands` STOP and WAIT, `thumb_tip_max_palm_lengths` 1.0, `thumb_palm_side_min` 0.0,
  `palm_mesh_min_vertices` 30, `palm_mesh_flatness_max` 0.5, `palm_hand_weight_min` 0.5). Edit Mode tests of the measures on synthetic
  hands.

**If any look fails** (Boxo or another): the fix goes into the pipeline, never the reader. It changes the worker template's hand
orientation or thumb curl (`HandShaper`, `WorkerV4`) or the import. It is written here as an addendum before the change. Tests must prove
five-finger looks unchanged (the golden test and the `BatchHandShapes` comparison, value for value). Then the geometry check and its
screenshots are rerun. Nothing is tuned on a perception result.

*Addendum 1 (2026-11-14, after the first run `gesture_geometry_hand_20261114_214854` on b4cf95c, before any fix).*
- **The palm faces the camera by the bones on every look:** at most 16.5 deg.
- **The mesh normal agrees** (10 to 25 deg) on the Sunbox looks, mixamo_worker and anime_f_02.
- **anime_f_01 and anime_f_03 fail the mesh part at 90 to 101 deg.** These are the long-sleeve variants; the short-sleeve anime_f_02 passes,
  and the long-sleeve ones have 65 more hand-bound vertices (141 against 76). The suspicion is that sleeve-cuff vertices are weighted to
  the hand and enter the plane fit.
- **Boxo's mesh normal is n/a:** its low-poly glove gives 18 to 20 palm vertices, fewer than 30, so its palm rests on the bones (5 to 9 deg).
- **The WAIT thumb fails on mixamo_worker (1.27 Lp), the three anime looks (1.57 Lp) and Boxo (2.50 Lp)**; the Sunbox looks pass
  (0.93 to 0.94 Lp).

Four of the five failing looks have five fingers, so item 2's condition "five-finger looks stay unchanged" cannot hold for a fix of
their thumbs. That is Nusrat's decision. *Diagnostic before asking (report only; the pass rule is not changed):* the geometry check also
reports the mesh palm normal of each group of palm vertices by sub-mesh (material), so the sleeve suspicion is checked, not assumed. It
runs on the three anime looks only.
*Diagnostic result* (`gesture_geometry_hand_diag_20261114_215527`): **inconclusive**. In Play mode the Body mesh gave no sub-mesh
assignment for any palm vertex (all labelled `Body/none`), so the sleeve could not be separated from the skin. The run reproduces the
first: anime_f_01 and 03 at 90 to 98 deg (141 to 142 vertices), anime_f_02 at 18 to 22 deg (75 to 76 vertices). The sleeve explanation
remains a suspicion. Nothing was fixed; Nusrat decides (the thumb of five-finger looks, and the anime mesh result).

*Addendum 2 (2026-11-14): Nusrat's decisions, declared before any change.*

**1. The WAIT thumb is tucked per rig, in the hand shaper.** The aim is the same WAIT hand on every look: the avatar experiment compares
appearance, not posing.
- `HandShaper.ThumbTuck` runs at `WorkerV4.Initialize`, per arm. It applies the WAIT shape (weight 1) to the bind pose and measures the
  thumb tip exactly as the check does (`HandGeometry.Frame`, `HandShaper.Tip`). If the tip lies within the goal, **nothing is stored and
  nothing changes**.
- Otherwise the thumb is curled across the palm until the tip is within the goal.
  - First the thumb root swings toward a target point 0.25 Lp in front of the palm centre (on the palm side). The swing is a fraction
    a of the rotation that aims the root-to-tip direction at the target, and a is the smallest fraction that meets the goal (bisection).
  - Only if a = 1 does not meet the goal, the two outer thumb joints are also curled toward the palm, by the smallest equal angle up to
    90 deg that meets the goal.
- The resulting thumb local rotations are stored and used for every WAIT frame instead of the shape's thumb; the other fingers are as
  before. They are blended by the IK weight as the rest of the hand.
- **Goal: 0.95 Lp**, a 5 % margin under the check's declared 1.0 Lp, so blending and pose noise cannot cross the limit. The values go to
  `worker_v4.json` `hand_shapes.wait` (`thumb_tuck_max_palm_lengths` 0.95, `thumb_tuck_side_l` 0.25); the other shapes keep 0 (off).
- A rig whose shaped thumb already meets the goal is untouched. The Sunbox looks are at 0.93 to 0.94 Lp, so this is a 1.5 % margin;
  their identity is proven, not assumed:
  - a new Edit Mode test pins every installed Sunbox look of `worker_v4.json` (both bases) to golden values computed by the code before
    the change;
  - `BatchHandShapes`, which now applies the tuck as the template does, is compared value for value on every look: the 10 Sunbox looks
    must be identical.
- The section 11 golden test of the synthetic hand stays as it is.

**2. Anime palm diagnostic (Edit mode).** The rule is unchanged. A new Edit-mode probe, `LookCheckMenu.BatchPalmProbe`, works on every
avatar-experiment look on the LookCheck stage:
- **Pose:** each hand is shaped as the template shapes it (STOP and WAIT, tuck included), with the fingers up and the palm toward a
  camera point 2.0 m in front of the look at 1.2 m height.
- **Two mesh palm normals**, compared with the camera direction under the same 30 deg rule:
  - (a) every hand-bound palm vertex, as the Play check;
  - (b) only the vertices of the skin material: a sub-mesh whose material name contains `SKIN` (VRoid's `Body_00_SKIN`), so sleeve and
    cuff are excluded.
- The sub-mesh of each vertex comes from the mesh's index data. The probe reports how it was read and refuses to guess.
- **Outcomes:**
  - If (b) passes on anime_f_01 and anime_f_03, the earlier mesh result is recorded as a sleeve artefact of the check.
  - If (b) fails, the palm orientation is fixed in the pipeline, after a further addendum, and reported.

**3. Boxo, judged by the bones: the proof.** The same probe reports, for Boxo's hands:
- the share of the glove vertices (material `glovemat`) bound to the Hand bone with weight >= 0.95;
- the same share within the palm region (wrist to finger bases).

If (nearly) all palm-region glove vertices move rigidly with the hand bone, the mesh plate turns exactly with the bone frame, so the bone
and mesh orientation are the same.

**Then** the full geometry and hand check runs on all 15 looks, with screenshots. No perception; one commit per decision.

*Addendum 3 (2026-11-14, after the first tuck run `hand_shapes_20261114_223353`, uncommitted, before any further change).*
- **Results:** the tuck reaches 0.95 Lp by the root swing alone on mixamo_worker (1.24 to 1.27 -> 0.95; swing 0.43 to 0.46) and on the
  three anime looks (1.57 -> 0.95; swing 0.68). The 10 Sunbox looks are identical value for value (3584 lines), and on the tucked looks
  only the WAIT thumb lines changed (12 per look).
- **Boxo misses** (2.50 / 2.46 -> 1.18 / 1.13 Lp). After the full swing its long thumb lies across the palm, so the declared stage-2 curl
  axis (the shape's axis, across the fingers) runs almost along the thumb and cannot fold it.
- *Correction of stage 2 only:* the outer joints curl about the axis perpendicular to the swung thumb (root to tip) and to the palm
  normal, with the sign that moves the tip toward the palm side. The rule (smallest equal angle up to 90 deg that meets 0.95 Lp) and
  stage 1 are unchanged.
- Stage 2 runs only on rigs the full swing does not tuck, so the four looks above and the Sunbox looks keep their values; the comparison
  with `hand_shapes_20261114_223353` must show only Boxo changed. If Boxo still misses, it is reported, not tuned further.
- *Result* (`hand_shapes_20261114_223517`): only Boxo changed (14 looks identical). **Boxo still misses the goal at the full 90 deg curl:
  2.50 / 2.46 -> 1.08 / 1.03 Lp** (left / right). Its glove thumb is longer than its palm can hold, so it will still fail the check's
  1.0 Lp. This is reported, not tuned further.

*Addendum 4 (2026-11-14, after the palm probe `palm_probe_20261114_225116` on 97c84da plus the uncommitted probe; before any further
change).*

**Decision 2: the anime mesh palm result is a sleeve artefact of the check.** The Edit-mode probe reproduces the Play failure and
locates it. The pass rule is unchanged; the earlier mesh result of anime_f_01 and 03 is recorded as the sleeve, not the palm. No
palm fix is needed.

| look | mesh (a), every hand-bound palm vertex | mesh (b), skin material `N00_000_00_Body_00_SKIN` only |
|---|---|---|
| anime_f_01, anime_f_03 | 87 to 89 deg (144 to 145 vertices) | **10.2 to 12.6 deg (74 to 75 vertices)** |
| anime_f_02 | 10.2 to 12.6 deg (identical to (b), no sleeve) | 10.2 to 12.6 deg |

The bones are at 6.9 deg on all three. The sub-meshes were read from the index data (`Mesh.GetIndices`, Body 9 sub-meshes); in Play
mode they had not been available.

**Decision 3: Boxo's rigidity is NOT proven.**
- Only **6 of 576 glove vertices (1.0 %)** are bound to the Hand bone with weight >= 0.95. In the palm region it is **0 of 44 to
  378**, and only 2 to 4 palm-region vertices are bound mainly to the Hand bone at all (hence "mesh n/a" in Play).
- Mixamo's auto-rigger spread the glove plate's weights over the finger bones, so the plate does not turn rigidly with the hand bone, and
  the bones alone do not prove its orientation.

*Diagnostic, declared now:* mesh (c) is the plane fit of Boxo's glove-material vertices in the palm region, whatever their bone
weights, under the same 30 deg rule, minimum vertices and flatness. It shows whether the rendered plate faces the camera. It is reported
for Nusrat; the pass rule is not changed.
*Correction of my probe (before using its numbers):* the first run with mesh (c) (`palm_probe_20261114_225325`) gave Boxo's STOP left
plate at 91 deg, contradicting the Play screenshots (both STOP palms face-on). The glove vertices had not been limited to the measured
hand. In the Edit-mode T-pose both hands are at the same height, so the other hand's glove fell into the palm slab, and the 576 "glove
vertices" were both hands'. The glove counts and mesh (c) now use only the glove vertices of the measured hand: at least half of their
weight is on that hand bone or a bone below it. The rigid share stays "weight >= 0.95 on the Hand bone itself". The probe is run
again; the first run is kept.

*Result of decision 3* (`palm_probe_20261114_225451`, the corrected probe; it replaces the counts above):
- **Rigidity: NOT proven.** Per hand, **6 of 288 glove vertices (2.1 %)** have Hand-bone weight >= 0.95, and **0 of the 22 (STOP) to 193
  (WAIT)** palm-region glove vertices do. The auto-rigger spread the plate's weights over the finger bones.
- **Mesh (c), the glove plate itself:** WAIT faces the camera at **13.8 deg (left) and 21.4 deg (right)**, within 30 deg; the flatness of
  0.33 includes the curled fingers. STOP is *undetermined*: only 22 palm-region vertices, below the declared 30 (a low-poly box plate).
- The Play screenshots show both STOP plates face-on, a visual check only.
- So Boxo's palm is judged by the bones (2.0 deg) and, for WAIT, also by the plate mesh; for STOP the mesh cannot be measured under the
  declared minimum. Nothing is changed for this; it is Nusrat's call.

*Results (2026-11-14, decisions 1 to 3 committed 97c84da, b0eacb3, a1981fc; rerun `gesture_geometry_hand_final_20261114_225633` on
a1981fc, clean tree, all 15 looks, 120 screenshots; tables in `reports_v4/`).*
- **Arm geometry:** all 15 looks pass, as before.
- **Hand check:** 12 of 15 pass.
  - **WAIT thumb:** mixamo_worker 1.27 -> 0.95 Lp, anime_f_01/02/03 1.57 -> 0.95 Lp, all on the palm side (0.71 to 0.86 Lp). The Sunbox
    looks are unchanged at 0.93 to 0.94 Lp.
  - **Palm by the bones:** at most 16.5 deg on every look.
- **anime_f_01 and anime_f_03 still fail the mesh part** (89 to 95 deg). By decision 2 this is recorded as the sleeve artefact of the
  check (skin-only palm at 10.2 to 12.6 deg in the probe); the rule is unchanged, so the table still says "no".
- **cartoon_boxo_01 fails the WAIT thumb:** 1.08 Lp, and -0.07 Lp, i.e. just behind the palm plane. The tuck's best at the full 90 deg
  curl (addendum 3) is reported, not tuned further. Its STOP passes by the bones; the mesh is n/a.
- **Screenshots (visual only):** mixamo_worker's WAIT thumb no longer sticks out; Boxo's thumb lies bunched with its curled fingers.

No perception was run.

*Addendum 5 (2026-11-14): Boxo v3 replaces v2, and skinning checks are added. Declared before any change; nothing run.*

Nusrat's finding in the v2 screenshots:
- WAIT's forearm collapses into a cone and the hand looks detached;
- the vest stripes bend into a V when an arm is raised.

The cause is that the generator built limbs and body with almost no edge loops, so skinning could not bend or twist smoothly.

**v3** (`unity/downloads/characters_v4/cartoon_boxo_01.fbx`, sha256 `4a69abed...`, 504 944 bytes; SOURCES.txt "version 3"):
- every part is subdivided with edge loops about every 2.5 cm (`STEP = 0.025` in `unity/tools/avatars/make_cartoon_boxo.py`, committed
  with step 1);
- a shorter thumb, set near the wrist;
- the same look.

v2 (`00fbf466...`) is kept as `unity/downloads/superseded/cartoon_boxo_01_v2.fbx`.

**Step 1: re-import and probes.**
- The v2 import folder `Assets/ThirdParty/CharactersV4/cartoon_boxo_01/` (and its `.meta`) is moved, not deleted, to the git-ignored
  `unity/downloads/superseded/cartoon_boxo_01_00fbf466_import/`. Then Import Characters runs unchanged: scale and avatar rebuild,
  recolour rules, alpha clipping (Boxo has no textures).
- Probes as before:
  - the finger probe (chains, Humanoid mapping, skin per finger, materials and colours, error shader, magenta pixels);
  - the arm-skin probe;
  - the palm / glove probe of addendum 2.
- `looks_ab.json` Boxo's source text names v3.

**Step 2: new skinning checks for every look, in the Play geometry check.** These are separate from the arm and hand checks, which do not
change. The limits are declared now in `gesture_geometry.json` `skinning`.
- **Reference:** the idle pose just before each take's request (arms down), baked once per take.
- **Forearm volume** of the gesturing arm:
  - The forearm vertices are those of every skinned mesh whose largest bone weight is on the LowerArm bone and at least 0.5 (sleeves
    included: what the camera sees).
  - At the reference they are assigned to 5 bands by their position along elbow to wrist (0 to 0.2, ..., 0.8 to 1.0); a band with fewer
    than 8 vertices is skipped.
  - On each measured frame, each band's mean distance from the current elbow-to-wrist line is divided by its reference value.
  - **The narrowest band's ratio must be at least 0.70**, on every measured frame of every command.
- **Torso stays rigid:**
  - The torso vertices are those whose largest bone weight is on Hips, Spine, Chest or UpperChest and at least 0.5 (vest, shirt and
    body included).
  - Each vertex's position is taken in its own dominant bone's frame, so bending or turning of the spine is not counted, only
    deformation from other bones.
  - Its displacement from the reference is measured on every measured frame. **The 95th percentile of the displacement must be below
    1.0 cm.** The maximum is reported too.
- **Frames:** the arm check's hold frames for POINT, WAIT and STOP; for PROCEED, 5 frames evenly spaced over its 2.0 s window.
- **Output:** a look x command passes when every frame passes. Reported per look in `skin_table.md`.
- Edit Mode tests on synthetic meshes cover the bands, the ratio and the percentile.
- The five-finger looks are expected to pass with their meshes unchanged. If one does not, it is reported, not tuned.

**Step 3: rerun of the geometry, hand and skinning checks on all 15 looks** (WAIT thumb 1.0 Lp; the mesh palm, where Boxo should now have
at least 30 palm vertices). If Boxo's tucked WAIT thumb still exceeds 1.0 Lp, a thumb opposition at the base joint for him alone is
declared here as a further addendum before it is built.

**Step 4: screenshots** of every look, command and arm, from the rerun's neutral camera.

No perception. One commit per step; nothing pushed or frozen.

*Addendum 6 (2026-11-14, after the v3 import `import_characters_20261114_234411` and its finger probe `probe_fingers_20261114_234431`,
before any change).* v3 imports as Humanoid with 46 bones and 24 of 30 finger bones, but **Unity's automatic Humanoid mapping assigns
the thumb chain `mixamorig:{Left,Right}HandThumb1-3` to the LITTLE finger**, and no thumb is mapped. v2 was mapped correctly. The shorter
thumb set near the wrist evidently looks like a little finger to the auto-mapper.

With this mapping the worker template would treat Boxo's thumb as his outermost finger: the palm frame, the thumb tuck and every hand
measure of the probes would be wrong. The probes of this import are therefore kept, but not used.

*Rule (importer, `ExperimentLooksMenu.ImportOne`, after the scale and avatar rebuild):*
- It applies to a model whose skeleton uses Mixamo's names (`mixamorig:`).
- Every finger bone the Humanoid avatar maps is checked against Mixamo's own finger names: Thumb, Index, Middle, Ring and Pinky = Little,
  joints 1 to 3 = proximal, intermediate, distal.
- **If any finger mapping contradicts the names, all the finger entries are replaced by the name-based ones** and the avatar is rebuilt
  from that description. The change is listed in the import report.
- Nothing else is changed. A model without `mixamorig:` names, or one whose mapping already agrees, is untouched; only Boxo is
  affected.

Then step 1's probes run again on the corrected import. *Also found, rule unchanged:* the finger probe now reads middle and ring as
"merged". The denser mesh puts palm-plate vertices into their 4 cm regions: middle moves 41 to 42 % of ring's region, and ring moves only
58 to 59 % of its own. This is reported again after the remap.

*Step 1 results (2026-11-14; import `import_characters_20261114_234707`, probes `probe_fingers_20261114_234734`,
`probe_arm_skin_20261114_234751`, `palm_probe_20261114_234807`).*
- **Remap:** 12 entries changed, Boxo only (both thumbs 1 to 3 from Little to Thumb). The anime imports are untouched (0 changes).
- **Fingers:** 4 chains per hand, the thumb now mapped as the thumb; 24 of 30 finger bones (no little finger).
  - Index and thumb read separate (own 84 to 98 %, others at most 11 %).
  - Middle and ring read "merged" by the unchanged rule: bending middle moves 41 to 42 % of ring's 4 cm region, and ring moves 58 to 59 %
    of its own. This is reported, not changed.
- **Colours:** 11 materials, all URP Lit, recoloured as before (glove 0.12/0.12/0.14, helmet 0.95); no error shader, 0 magenta pixels.
- **Arm skin:** both arms and hands follow their bones (219 to 220 arm and 86 to 92 hand vertices).
- **Glove / palm (Edit mode):**
  - Bones: 2.5 to 2.6 deg.
  - Mesh (a), hand-bound palm vertices: now 60 to 127 vertices (above 30), but **undetermined, flatness 0.53 to 0.68 > 0.5**. The v3 glove
    plate is 4.5 cm thick, and the region between wrist and finger bases is about as short as that, so the region is not flat.
  - Mesh (c), the glove plate: STOP 14.5 / 17.3 deg (within 30). WAIT is not reliable (n/a and 88 deg), because the curled fingers fall
    into the region.
  - Hand-bone weight >= 0.95: 0 to 3.8 % of palm-region vertices.
- `looks_ab.json` names v3. The edit-mode `LookPoser` still reports "shapes False" (it requires a little finger); the worker template
  does not.

*Steps 3 and 4 results (2026-11-15; `gesture_geometry_boxo_v3_20261115_000535` on 25fb6fe, clean tree, all 15 looks, 120 screenshots;
tables in `reports_v4/`).*
- **Arm geometry:** 15 of 15 pass.
- **Hand check: 13 of 15**, now including Boxo.
  - Boxo's tucked WAIT thumb is at **0.95 Lp** (palm side 0.55 Lp), so the thumb opposition of step 3 is not needed and is not built.
  - Boxo's palm by the bones is at 5.6 to 9.8 deg. His mesh palm is still n/a: 59 to 64 vertices, but flatness 0.66 > 0.5.
  - anime_f_01 and 03 fail only the mesh part (the sleeve artefact of decision 2).
- **Forearm volume: passes on every look.** The narrowest band keeps 0.82 to 0.97 on the five-finger looks and **0.72 to 0.91 on Boxo v3**
  (WAIT 0.72, POINT 0.73, close to the 0.70 limit). In the screenshot Boxo's WAIT forearm keeps its shape and the hand stays attached.
- **Torso rigidity: the declared limit (p95 < 1.0 cm) fails on 14 of 15 looks, five-finger looks included.** Only anime_f_02 passes.

  | looks | torso p95 (cm) | torso max (cm) |
  |---|---|---|
  | mixamo_worker | 0.71 to 1.02 (fails on POINT) | |
  | Sunbox | 0.63 to 1.71 | 1.35 to 6.75 |
  | anime_f_01, 03 | 0.98 to 1.80 | |
  | cartoon_boxo_01 v3 | 0.80 to 1.55 | 3.07 to **11.43** (WAIT) |

  The unchanged five-finger rigs deform their upper chest and shoulder vertices by 1 to 2 cm (p95) when an arm moves, so the limit is
  stricter than every rig. **This is reported, not tuned (Nusrat decides).**
  - Boxo's p95 is within the five-finger range, but his WAIT maximum of 11.4 cm is the largest of all. In the WAIT screenshot the upper
    vest stripe is wavy and a flap of the body pulls out at the raised arm's shoulder.
  - His POINT stripes are straight.

No perception was run.

*Addendum 7 (2026-11-15): Nusrat's four decisions, declared before any change.* No perception; one commit per decision. The
five-finger looks must stay unchanged: decisions 2 to 4 apply only to looks named in a new `looks_ab.json` rule, i.e. only Boxo. The
Sunbox pin test, the golden test and a `BatchHandShapes` comparison prove it.

**1. Torso core check (replaces the torso rule of addendum 5).**
- **Core:** the torso vertices as before (largest weight on Hips, Spine, Chest or UpperChest, at least 0.5), **minus a shoulder zone**:
  every vertex within **0.4 x the rig's own upper-arm length (Lu)** of either UpperArm bone, at the take's reference pose. The zone is
  about 11 cm on Sunbox, 9 cm on the anime looks and 10 cm on Boxo.
- **Metric:** as before, each vertex in its own dominant bone's frame, the 95th percentile of its displacement from the pre-take idle.
- **Limit, calibrated before it is applied:**
  - First the check runs on the professionally rigged looks only: the 10 Sunbox looks and mixamo_worker. Their worst core p95 over every
    command, frame and arm, **x 1.25**, is the limit.
  - It is written into `gesture_geometry.json` (`torso_max_displacement_m`) and recorded here as a further addendum, committed, and only
    then applied to all 15 looks.
- The whole-torso p95 of addendum 5 stays in `skin_table.md` as information, not as a rule.

**2. Boxo's rigid torso (importer, Boxo only).** Boxo's body is a rigid box by design. A new `looks_ab.json` rule `rigid_parts`
(look `cartoon_boxo_01`, bone `mixamorig:Spine2`, Mixamo's upper spine, mapped as Chest or UpperChest) binds every vertex of the
materials `bodymat`, `vestmat`, `stripemat`, `eye_whitemat`, `pupilmat`, `mouthmat` and `helmetmat` 100 % to that bone.
- This is done in `ExperimentCharacterPostprocessor.OnPostprocessModel`, so it is applied by every import of that model and never by
  hand.
- Arms (`limbmat`), hands (`glovemat`) and legs (`trousersmat`, `bootmat`) keep their weights.
- The import report lists the vertices rebound per material.
- The re-check of the rerun (screenshots and torso core) must show no shoulder flap, straight vest stripes, and the torso check passing.

**3. Boxo's palm plate (geometry check, Boxo only).** A new `looks_ab.json` rule `palm_plates` (look `cartoon_boxo_01`, material
`glovemat`, `max_dimension_change` 0.05).
- **The plate:** the hand's glove mesh island with the largest bounding-box volume. Islands are formed from the triangles, with the
  vertices welded by position to 0.1 mm. "The hand's" means more than half the weight on that hand bone or below it.
- **Measure:** a PCA of the plate's vertices. Its **thinnest principal axis is the palm normal**, signed by the bone normal, and the 30 deg
  palm-to-camera rule applies to it.
- **Shape:** the plate's extents along its three principal axes, sorted, must each stay **within 5 %** of the rest plate's (the plate
  as spawned, before the first animated frame).
- For that look this replaces the hand-bound-vertex mesh normal (whose flatness rule could not be met by a 4.5 cm thick plate). The bone
  normal rule stays.
- The plate's triangles must be readable at Play, so the rule also imports Boxo's model with Read/Write enabled. Nothing else changes.

**4. Boxo's fingers by mesh islands (finger probe).** For a look with a `palm_plates` rule, the finger probe also measures each finger by
its mesh islands instead of the 4 cm region:
- Every glove island of the hand except the plate is assigned to the finger chain nearest to its centroid. A finger's vertices are those
  of its islands.
- The bend (30 deg), the movement threshold (2 mm) and the verdict (own >= 80 %, every other <= 20 %, at least 30 vertices) are as before.
- If middle and ring still move together, it is reported as real.

**Then** all checks rerun on all 15 looks, with screenshots: geometry, hand, skinning with the calibrated torso core, and Boxo's probes.

*Addendum 8 (2026-11-15): the torso core limit, calibrated on the professionally rigged looks; declared before it is applied to the
other looks.*
- **Run:** `gesture_geometry_torso_calibration_20261115_004424` on 0ec0318 (clean tree), with only mixamo_worker and the 10 Sunbox looks.
- **Worst torso core p95:** **1.70 cm** (sunbox_f_shirt_plaid, POINT, right arm, point_ik_01). The others range from 0.61 to 1.67 cm;
  mixamo_worker's worst is 0.98 cm.
- **Limit: 1.70 x 1.25 = 2.125 cm.** `gesture_geometry.json` `skinning.torso_max_displacement_m` becomes **0.02125**, applied from now on
  to all 15 looks.
- *Observation:* the shoulder zone (0.4 Lu) removes only 1 to 32 vertices per rig (for example 3082 -> 3079 on mixamo_worker), so the
  core p95 is nearly the whole-torso p95. On these rigs the 1 to 2 cm is spread over the torso, not concentrated at the shoulder. The zone
  is not changed after seeing this.

*Results of addendum 7 (2026-11-15; decisions committed 0ec0318, 59a66e5, f796d09, fcdbcc9, b5b6c90; full rerun
`gesture_geometry_decisions7_20261115_010852` on b5b6c90, clean tree, all 15 looks, 120 screenshots; tables in `reports_v4/`).*
- **Arm geometry:** 15 of 15 pass.
- **Skinning: 15 of 15 pass.**
  - Torso core p95 at most 1.71 cm on any look (sunbox_m1 PROCEED; the calibration run's 1.70 differs by run-to-run noise), under the
    2.125 cm limit.
  - Forearm: narrowest band at least 0.72 (Boxo WAIT, 0.716).
- **Decision 2, Boxo's rigid torso: confirmed.** All 5112 body vertices are bound to `mixamorig:Spine2`. His torso core p95 is 0.00 cm on
  every command (max 0.53 to 1.13 cm: vertices of other materials dominated by the spine). In the WAIT screenshot the vest stripes are
  straight and there is no shoulder flap.
- **Decision 3, Boxo's palm plate:**
  - STOP passes: plate normal 6.6 deg, plate shape change 1.2 %.
  - **WAIT fails the plate shape: 35.9 %.** The plate's weights lie on the finger bones (rigid share 0 to 4 %, step 1), so curling the
    fingers bends the plate. The WAIT screenshot shows the glove crumpled around the curled fingers. Its normal (23.2 deg) is within
    30 deg. **Hand check 12 of 15**: Boxo fails (WAIT plate), and anime_f_01 and 03 fail (the sleeve artefact of decision 2 of
    addendum 2).
- **Decision 4, Boxo's fingers by islands:** index and thumb are separate (114 vertices each, own 100 %, others 0 %). **Middle and ring
  still move together, reported as real:**
  - the two finger islands split 34 / 170 (left) and 114 / 90 (right) between the middle and ring chains;
  - bending middle moves 43 to 62 % of ring's vertices;
  - so the auto-rigger's middle and ring chains share both finger meshes.
- **Five-finger looks unchanged:** `hand_shapes_20261115_011330` against `_20261114_223517` is identical on all 14 other looks (Boxo
  differs; the baseline held v2). The Sunbox pin test and the golden test pass. The rules of decisions 2 to 4 name only Boxo.
- *Not decided, open for Nusrat:* Boxo's WAIT palm plate. Binding the plate 100 % to the hand bone, as his torso is bound, would keep it
  rigid. That would be a new decision.

No perception was run.

*Addendum 9 (2026-11-15): Nusrat's decision, declared before any change. Boxo only; no perception.* Boxo's hands are bound by their
mesh islands, as his torso is. A new `looks_ab.json` rule, `island_hands` (look `cartoon_boxo_01`, material `glovemat`, weld 0.1 mm), is
applied by `ExperimentCharacterPostprocessor.OnPostprocessModel` on every import of the model, after the rigid torso.

**Method** (in mesh space; joint positions from the bind poses):
- **This hand's glove:** the glovemat vertices with at least half of their auto-rigger weight on that hand bone or below it (decided
  before any weight is changed).
- **Islands:** from the triangles, with the vertices welded within 0.1 mm.
- **Palm plate:** the island with the largest box volume, bound **100 % to the hand bone**.
- **Fingers:** the other islands are grouped into fingers by contact: islands whose bounding boxes touch within 5 mm are one finger,
  e.g. a finger's cylinder and its tip sphere. The finger groups are matched **one to one** with the hand's four chains (thumb, index,
  middle, ring) by the smallest total centroid-to-chain distance over all assignments. Nearest-centroid assignment had split middle and
  ring 34 / 170 in addendum 7's probe.
- **Finger weights, only along the finger's own chain**, with joints j0 to j3 (proximal, intermediate, distal, end):
  - each vertex gets a position u along the chain's polyline, in segment units: u = k + s on the segment from joint k to joint k + 1,
    clamped to [0, 3];
  - a segment's vertex belongs 100 % to that segment's bone (j0, j1 or j2);
  - within 0.25 segment of an interior joint (j1, j2), it blends linearly between the two bones meeting there (50 / 50 at the joint);
  - the part beyond the end joint (the tip sphere) belongs to the distal bone, and the part before j0 to the proximal bone;
  - **no weight on any other finger, the hand or the arm.**
- The import report lists the vertices bound per part.

**Verification** (rerun of all checks on all 15 looks, with screenshots):
- **Palm plate shape: change under 5 % in every command.** The geometry check measures Boxo's plate on every measured frame of POINT,
  PROCEED, WAIT and STOP. It is reported in `skin_table.md` and is part of the skinning pass for a palm-plate look; STOP and WAIT also keep
  it in the hand check as before.
- **Fingers:** bending each finger moves **0 %** of the other fingers' vertices (the island finger probe, every finger of both hands).
- **Five-finger looks unchanged:** the rule names only Boxo. The `BatchHandShapes` comparison, the Sunbox pin test and the golden test
  confirm it.
- **Edit Mode tests:**
  - the binding on a synthetic hand (plate on the hand bone, fingers only on their own chain, the blend at the joints, no cross-finger
    weight, one-to-one matching);
  - the installed Boxo import, when present: every plate vertex on the hand bone, and no finger vertex on another chain.

*Addendum 10 (2026-11-15, after the first island-bound import `import_characters_20261115_014947`, uncommitted, before any further
change): a correction of the finger grouping.*
- **What happened:** the import bound every vertex to exactly one part (0 crossing), but formed only **three** finger groups per hand:
  ring 114, middle 114, thumb **204** vertices. The thumb and the index finger became one group, so the index finger was bound to the
  thumb chain and the index chain got nothing.
- **Cause:** grouping by *bounding-box* contact. v3's shortened thumb lies diagonally near the index base, so its box touched the index
  finger's box although the meshes do not touch.
- **Correction:** two islands are one finger when their **closest vertices** lie within `contact_m` (5 mm). A cylinder and its tip
  sphere overlap, so they still join. Everything else in addendum 9 is unchanged.
- The audit and the installed-Boxo test now also require **every chain of each hand to receive vertices**. The earlier test only checked
  that each vertex lies on one chain, which this fault passed.

*Results of addendums 9 and 10 (2026-11-15; binding committed 148cdbc; import `import_characters_20261115_015143`; rerun
`gesture_geometry_island_hands_20261115_015310` on 148cdbc, all 15 looks, 120 screenshots; finger probe `probe_fingers_20261115_015834`).*

**Measured (the declared checks):**
- **Binding:** per hand, the plate's 216 vertices are on the hand bone; index, middle and ring get 114 vertices each and the thumb 90, each
  on its own chain; 0 vertices cross parts; 4 of 4 chains are used.
- **Palm plate shape: 0.0 % change in every command** (POINT, PROCEED, WAIT, STOP), under 5 %. The plate's normal is 6.3 deg (STOP) and
  11.1 deg (WAIT).
- **Hand check 13 of 15** (Boxo passes; anime_f_01 and 03 are the sleeve artefact). Skinning 15 of 15. Arm geometry 15 of 15.
- **Five-finger looks unchanged:** `hand_shapes_20261115_015702` against `_011330` is identical on all 15 looks (the bones do not change).
  The Sunbox pin and golden tests pass.

**But the binding does not give Boxo usable hands. Seen in the screenshots, not measurable by the bone-based checks.**
- His fingers stick out at odd angles and stand apart from the plate: in WAIT, in STOP, and on the idle hand.
- The **finger island probe** cannot show "0 % of the other fingers": its nearest-centroid assignment disagrees with the binder's
  one-to-one matching, so every finger reads "merged" or "inconclusive" (own 0 %, others 44 to 56 %).
- *Diagnostic (report only):* in each hand's frame,
  - the **auto-rigger's chains lie bunched within +-3.5 cm** of the middle (index x +0.035, middle 0, ring -0.035 m; the thumb diagonal on
    the +x side, out of the palm plane);
  - the **generator's finger meshes fan out to +-15 cm**, with the short 56-vertex thumb mesh on the -x side, opposite the chain named
    Thumb.
  - So each finger mesh is bound to a chain whose joints lie several centimetres outside it. It swings about those joints instead of
    bending at its own knuckles, and no distance rule can identify which mesh finger belongs to which chain.
- **Cause:** the rig, not the weights. Mixamo placed the finger chains for a human hand, not for Boxo's fanned glove. Island binding
  removes the plate's bending and the cross-finger weights, but cannot move the joints.
- **Not fixed, Nusrat's decision:**
  - (a) Revert the island binding: the auto-rigger's weights, with the bent WAIT plate.
  - (b) In the importer, move each finger chain's joints into its finger mesh (joint positions along the mesh finger's axis, the bind
    poses recomputed), then bind by islands. A rig change that needs its own declaration.
  - (c) Re-rig Boxo outside Unity (a rig built by the generator, with joints at the finger cylinders' ends).

No perception was run.

*Addendum 11 (2026-11-15): Nusrat chose option (b). Declared before any change; Boxo only; no perception.* The importer moves Boxo's
finger chains into his finger meshes and then binds by islands. `looks_ab.json` `island_hands` gets `move_joints: true`. Everything runs
in `ExperimentCharacterPostprocessor` on every import of the model, in this order: rigid torso, then chain alignment, then binding.

**1. Finger axis per island group** (rest pose, mesh space):
- the finger groups are as in addenda 9 and 10 (islands joined by closest vertices within 5 mm; the plate is the largest box);
- each group's axis is the first principal axis (PCA) of its vertices;
- its **knuckle end** is the end of the axis nearest the palm plate's centroid, and its **tip end** is the other end (the projections'
  extreme values along the axis).

**2. Chain assignment by a fixed anatomical rule** (no distance matching):
- the hand's **forward axis** is from the hand bone to the plate's centroid;
- the **thumb** is the group whose axis (knuckle to tip) deviates most from the forward axis;
- the other groups are ordered across the palm by their knuckle's distance from the thumb's knuckle along the plate's across axis (its
  longest principal axis, made perpendicular to the forward axis): nearest = **index**, then **middle**, then **ring**;
- chains are identified by their Mixamo names (Thumb, Index, Middle, Ring);
- a hand that does not give exactly one group per chain is refused: reported, nothing moved or bound.

**3. Chain alignment:**
- Each chain's joints j0 to j3 are placed on its group's axis: **j0 at the knuckle end, j3 at the tip end, j1 and j2 evenly between**.
  They are set base to tip by position only; joint rotations are kept.
- The mesh's bind poses are recomputed for every moved bone (bone world-to-local times the renderer's local-to-world, at the import pose).
- Then the island binding of addenda 9 and 10 runs, with this assignment in place of the distance matching.
- **The Humanoid avatar is rebuilt from the corrected skeleton:** `ExperimentLooksMenu.ImportOne` writes the imported hierarchy's
  transforms into the importer's `humanDescription.skeleton` and re-imports. The import report lists the moved joints (old to new
  position, in cm) and whether the avatar is valid.

**4. The finger probe uses the same assignment** (the shared `IslandHands.Analyse`) instead of its nearest-centroid rule.

**Tests and checks:**
- Each finger bends at its own knuckles: on the installed Boxo, every joint j0 to j2 of each chain lies inside its group's box (in the
  group's principal frame, within 1 mm).
- Bending one finger moves **0 %** of the other fingers' vertices (island probe, both hands).
- Palm plate shape change under 5 % in every command.
- Five-finger looks unchanged (`BatchHandShapes` comparison, Sunbox pin test, golden test).
- Edit Mode tests of the analysis on a synthetic four-finger hand: thumb by axis deviation, order across the palm, joints on the axes.
- Then all checks rerun on all 15 looks, with screenshots.

**Stop rule (Nusrat's):** if the screenshots still show fingers swinging outside their knuckles, the work STOPS, Boxo reverts to option
(a) (the auto-rigger's weights and joints), and his hand is documented as it is.

*Addendum 12 (2026-11-15, after the aligned import `import_characters_20261115_022715` (be2346f), the rerun
`gesture_geometry_aligned_chains_20261115_022831` and the probe `probe_fingers_20261115_022815`; before any further change).*

**Stop rule: not triggered.** The screenshots show each finger attached at the plate's edge and bending at its own knuckles:
- STOP: the plate face-on, three fingers straight up, the thumb at the side;
- POINT: the index straight, the others curled into the plate;
- WAIT: the index up, the others curled;
- the idle hand's fingers hang from the plate.

Option (b) stays.

**A correction of my item 4.** The probe re-ran the anatomical rule on the bound model instead of reusing the importer's assignment, and
the two disagree on the same geometry. The probe's dump shows every chain's joints exactly on a group's axis, but labels the groups
differently: its "thumb" is a long finger, and the real 90-vertex thumb becomes "ring". So bending each chain moves "another" finger.
- *Cause:* the rule's forward axis runs from the hand bone to the plate's centre, and the plate counts only "this hand's" vertices.
  - In the importer these are chosen by the auto-rigger's weights, which put part of the plate elsewhere.
  - In the probe, after binding, the whole plate counts.
  - The plate centre shifts, the forward axis tilts, and a long finger out-deviates the thumb.
- **So the rule as declared is fragile on Boxo. It gave the anatomically right thumb in the importer only with the auto-rigger's
  partial plate.** The screenshots confirm that the importer's assignment is right: the finger next to the short diagonal thumb is the
  one that points.
- *Correction (item 4 as decided: "the SAME assignment"):* the probe reads the importer's assignment from the binding itself. Each glove
  island of the hand, other than the plate, is owned by the chain that holds most of its vertices' weight. The rule is not re-run.
- The fragility is reported for Nusrat; the importer's rule is not changed after seeing this.

*Results of addenda 11 and 12 (2026-11-15).*
- **Import** (`import_characters_20261115_022715`, be2346f):
  - 32 finger joints moved onto their fingers' axes, by up to 8.4 cm;
  - the Humanoid avatar was rebuilt from the corrected skeleton (32 entries, human, valid);
  - per hand, the plate's 216 vertices are on the hand bone; index, middle and ring get 114 each and the thumb 90, on their own chains;
    0 cross parts.
- **Joints inside their own finger:** the installed-Boxo test passes (every j0 to j2 inside its own finger group's box, 1 mm).
- **Fingers** (`probe_fingers_20261115_023523`, the importer's assignment): **every finger of both hands is separate.** Bending it moves
  95.6 to 96.5 % of its own vertices and **0.000 % of every other finger's.**
- **Palm plate shape: 0.0 % change in every command** (POINT, PROCEED, WAIT, STOP). The plate's normal is 9.2 deg (STOP) and 14.2 deg
  (WAIT), and the WAIT thumb is at 0.95 Lp.
- **Full rerun** (`gesture_geometry_aligned_chains_20261115_022831`, be2346f, all 15 looks, 120 screenshots):
  - arm geometry 15 of 15;
  - **hand check 13 of 15** (only anime_f_01 and 03, the sleeve artefact);
  - skinning 15 of 15 (torso core p95 at most 1.70 cm under 2.125 cm; forearm at least 0.72, Boxo WAIT).
- **Five-finger looks unchanged:** `hand_shapes_20261115_023246` against `_015702` is identical on the 14 other looks; only Boxo changed
  (his joints moved). The Sunbox pin test and the golden test pass.
- **Screenshots:** no finger swings outside its knuckles (stop rule not triggered).

No perception was run.

*Addendum 13 (2026-11-15): Nusrat's decision, declared before any change. Boxo only; no perception.* **The importer's
island-to-chain assignment is pinned.** Addendum 12 showed that the anatomical rule is fragile on Boxo, so the assignment the screenshots
confirmed (be2346f, `import_characters_20261115_022715`) is recorded and guarded.
- **What is recorded** (`looks_ab.json` `island_hands[cartoon_boxo_01].pinned_assignment`): per hand and chain (Thumb, Index, Middle,
  Ring), the finger the binding gives that chain. It is read back from the imported mesh's weights (`IslandHands.ReadAssignment`):
  each glove island of the hand except the plate belongs to the chain holding most of its weight. Each entry records the number of
  vertices and the first and last mesh vertex index. Vertex order is fixed by the FBX, so these identify the finger's islands across
  re-imports of the same file.
- **Guard:**
  - an Edit Mode test on the installed Boxo **fails if a re-import gives a different assignment** (any entry differs, is missing or is
    extra);
  - a synthetic test shows that the comparison catches two swapped fingers;
  - the import report states whether the pin matches.
- The values are filled from the current import, not chosen.
- Nothing else changes: the importer still applies the rule of addendum 11; the pin only detects a change.
- *Result (2026-11-15):*
  - the pin (8 entries: per hand, index, middle and ring 114 vertices each and the thumb 90) was read from the confirmed binding;
  - a fresh re-import (`import_characters_20261115_025911`) reports "pinned assignment: matches", and
    `IslandHandsTests.BoxoAssignment_MatchesThePin` passes on it;
  - the synthetic swap test catches index and middle swapped, and only those.

## 2026-11-15, section 13: detection-off finals, the STOP session, the zip for Anisha (declared before any change or recording; nothing run)

Branch `nusrat/v4-stop-session` (from main c59b168, which holds Anisha's AUDIT.md 16.15 to 16.17 and the avatar fixes of sections 10 to
12). Unity side only: no file under `robot_vision/`, `docs/` or `external/` is changed, nothing is frozen, no final is run. The two
sessions of part B run in the Unity Editor WINDOW (never `-batchmode`). One commit per part.

### Part A: the four detection-off final settings (agreed with Anisha)

**Her names, used exactly** (checked on main: `configs/v4/final_plan.json` `settings`, `bridge/server.py` `FINAL_CONTROL`, AUDIT.md 16.15
decision 1): `B1_off`, `B2_right_off`, `B3_off`, `B4_off`. Each is its on twin (`B1`, `B2_right`, `B3`, `B4`) with the server's
lie-detection-OFF control file:

| setting | experiment | side | control file (`--control-config`) | on twin |
|---|---|---|---|---|
| `B1_off` | B1 | - | `configs/v4/experiments/control_lie_off_a1.json` | `B1` |
| `B2_right_off` | B2 | right | `configs/v4/experiments/control_lie_off_a2_right.json` | `B2_right` |
| `B3_off` | B3 | - | `configs/v4/experiments/control_lie_off.json` | `B3` |
| `B4_off` | B4 | - | `configs/v4/experiments/control_lie_off.json` | `B4` |

What changes in Unity:
1. **Final configs** `Avatar/Config/sessions/final_ab_<setting>.json` for the four: the on twin's file with `lie_detection` "off" and
   `python_control` the off file; looks, clips and side unchanged. Unity runs the same as for the twin: same experiment, seed 2, so the
   same goals, placements and liars run by run (the paired comparison of AUDIT.md 16.15: `B*` against `B*_off`).
2. **The config names its setting with its lie switch:** `FinalExperimentV4.SettingName` becomes experiment + `_<side>` +
   (`_off` when `lie_detection` is "off"). Without it the guard would call a `B1_off` config "the config of setting B1" and refuse it.
   A `B1` config with "off" is then "the config of setting B1_off" and is refused under `B1`. The control-file check is unchanged.
3. **`final_v4.json`:** `settings` 9 -> 13 (the four after the nine); `freeze_files` 24 -> 28 (the four configs).
   `freeze_v4.unity_files` reads this list unchanged, so no Python change is needed.
4. **The guard is unchanged.** It already looks a setting up by its exact name in the markers: a `B1` marker never blocks `B1_off`.
5. **Launcher** `finals_v4/run_session_v4.ps1`: new `-LieDetection on|off` (default on). The setting name gets `_off` with "off". A
   setting missing from `final_v4.json` (e.g. `A1_off`) is refused as now. `-DryRun` prints the commands and every refusal.
   - final: Unity `-finalSetting B1_off`, server `--final-setting B1_off --control-config <off file>`;
   - rehearsal: Unity `-experiment B1` (development looks and clips), server with the off control file.
6. **Tests:** the 13 settings and their configs; on/off switches of each control file; on and off twins identical except the switch and
   the control file; the name rule; markers of a twin independent; launcher dry runs (by hand).

**The matrix: 13 settings x 20 runs = 260 runs.**
- Estimate: the method and numbers of section 7. A detection-off run = the on run divided by the simulator's on/off factor
  (16.13.1: B1 1.21, B2 1.37, B3 1.63, B4 1.54).
- The caveats of section 7 hold: no experiment run has completed in Unity yet.

| setting | mean run (s) | longest run (s) | session (min) |
|---|---|---|---|
| `B1_off` | 93 | 93 | 38 |
| `B2_right_off` | 92 | 92 | 38 |
| `B3_off` | 141 | 171 | 55 |
| `B4_off` | 140 | 171 | 54 |
| the nine of section 7 | | | 557 |
| **total** | | | **742 min, about 12.4 h** |

**Proposed four sittings** (Anisha 16.17 item 1: four sittings of about 3 h; each B with its off partner; the A settings spread) **[N]**:
- *Sitting 1 (3.1 h):* `B3`, `B3_off`, `A2_right`.
- *Sitting 2 (3.1 h):* `B4_off`, `B4`, `A2_left`.
- *Sitting 3 (3.4 h):* `B1`, `B1_off`, `A1`, `A4`.
- *Sitting 4 (2.8 h):* `B2_right_off`, `B2_right`, `A3`.

Rules for the sittings:
- On and off alternate which runs first (on first in sittings 1 and 3).
- Every setting has its own Unity start, the run protocol and one session of 20 runs.
- Splitting changes nothing in a setting.

Alternative: group by scenario (A, B, B_off together). Not proposed, because the third sitting would take 3.6 h. Anything the Python
side still needs goes to a file under `robot_vision/outputs/` (`for_anisha_off_settings_<time>.md`), never into her files.

*Part A, built as declared (2026-11-15).*
- **Files:** the four `sessions/final_ab_<setting>_off.json` (+ `.meta`), generated from the twins (only `lie_detection`,
  `python_control` and the two notes differ); `final_v4.json` (13 settings, 28 freeze files); `FinalExperimentV4.SettingName`; the
  launcher's `-LieDetection`; `TrialPlayV4` doc comment.
- **Tests:** `FinalExperimentsABTests` covers the 13 names, on/off per setting, the control file's switches, the twins identical but
  for the switch and the file, the name rule, and independent markers of a twin pair. `FinalGuardV4Tests` covers the 13 names.
  Unity Edit Mode 308/308.
- **Launcher dry runs:** all four off settings show the right Unity and server commands. Each is refused today only for "not on main",
  "tree not clean" and "frozen.json is not frozen"; Python's `final_plan.json` and `FINAL_CONTROL` accept each with the same control
  file. `-Experiment A1 -LieDetection off` is refused ("'A1_off' is not a setting of the final matrix"). A rehearsal of `B3_off` runs
  Unity `-experiment B3` with the server on `control_lie_off.json`.
- **For Anisha:** the note `for_anisha_off_settings_20261115.md` (a byte-identical copy in `Avatar/Config/reports_v4/`). Her side
  needs no change for the off settings. Open for her: whether the timeout rule needs detection-off development runs, the STOP counts
  (13 vs 20 per look), and the sittings.

### Part B: the STOP session (development, seed 1, today's poses)

Purpose: the recordings AUDIT.md 16.16 decision 3 asks for, with the poses on main (PROCEED changed on every look, sections 10 and 11).
Anisha checks the candidate false-STOP rule (16.17 item 3) on them against criteria (a) to (c) of 16.16 decision 2. **The server runs
the CURRENT reader** (`configs/v4/gesture_reader.json` as on main; the rule is not switched on). It logs every processed frame's
model outputs (`model_outputs.jsonl`), and Unity writes the truth per frame (`truth.jsonl` every 0.05 s and on every phase change:
`true_command`, `arm`, `phase`, `clip`, `look`).

**Not the look-check Play mode:** that mode never connects to Python, so it gives no `model_outputs.jsonl` and no `decisions.csv`. The
session is a new **development scenario** `stop_session` of `TrialRunnerV4`: `TrialPlayV4 -workersConfig
Assets/WarehouseRobot/Avatar/Config/sessions/dev_stop_session.json`, with the bridge server in guide mode. The robot really reacts.

**One item per run, 64 runs, exact counts:**

| kind | command | looks | arms | per look per arm | runs |
|---|---|---|---|---|---|
| held at the ask (A) | STOP | `sunbox_m1`, `sunbox_f1` | right, left | 5 | 20 |
| negative at the ask (A) | POINT | both | right, left | 3 | 12 |
| negative at the ask (A) | PROCEED | both | right, left | 3 | 12 |
| negative at the ask (A) | WAIT | both | right, left | 3 | 12 |
| STOP while the robot drives (toward J1) | STOP | both | m1: right, left, right; f1: left, right, left | 3 per look | 6 |
| drive past an idle worker | (none) | both | - | 1 per look | 2 |
| **total** | | | | | **64** |

- **Counts differ from Anisha's 16.16 decision 3.** She asked for 20 STOPs per look (10 per arm), part while driving. This task gives
  13 per look (5 held per arm + 3 while driving). Disclosed for her; criterion (a) is n of n with the n reported.
- **Looks and clips:** development only.
  - Looks: `sunbox_m1`, `sunbox_f1` (`data_splits.json`).
  - Clips: the development clips of each command in `worker_v4.json` order, by repetition within a look and arm: repetition r uses
    clip (r - 1) mod 2. So STOP `stop_ik_01`, `stop_ik_03`; POINT `point_mixamo_01`, `point_ik_01`; PROCEED `proceed_ik_01`,
    `proceed_ik_02`; WAIT `wait_ik_01`, `wait_raise_01`.
  - Every run passes `DataSplitsV4.GuardRun` as development (test data refused before anything is recorded).
  - Speed, size, start delay, hold (3.0 to 4.5 s) and sway: the worker's seeded draw (seed 1, run, worker id) from `worker_v4.json`, as
    in every session.
- **Order:** the 32 items of a look in this order, with the two looks alternating run by run (run 1 `sunbox_m1` item 1, run 2
  `sunbox_f1` item 1, ...):
  1. repetitions 1 to 3 of [STOP R, STOP L, POINT R, POINT L, PROCEED R, PROCEED L, WAIT R, WAIT L];
  2. repetitions 4 and 5 of [STOP R, STOP L];
  3. the three driving STOPs;
  4. the idle pass.
- **Held items and negatives (at A, at 2 m):**
  - The robot starts at A, scans, approaches the worker at A's stand to Python's 2.0 m standoff and asks "Which direction?".
  - At the first ask the worker shows the item. It starts only after the question appears, as every answer does; STOP too.
  - POINT points at 90 deg to the worker's own side of the arm (the worker faces the robot). PROCEED, WAIT and STOP are shown as
    in every session.
  - The worker answers no later ask.
  - What the robot does is the real controller: STOP stops it; WAIT holds it; PROCEED sends it toward J1; POINT to the side is unclear
    and asked again. So some PROCEED and POINT frames come from a robot that is moving or repositioning; the README says which.
- **STOP while driving:**
  - At A the worker answers every ask with PROCEED (the direction; not a counted item) until the robot drives toward J1. It is then
    moved, once idle, to J1's stand, as in `stop_while_driving`.
  - It shows STOP (the item's arm and clip, drawn hold) when Python's state is `navigate`, it has noticed the robot (8 m) and the
    robot is **4.0 to 6.0 m** from it.
  - 2 m is not possible while driving: on the road the robot comes no nearer than about 3.7 m to J1's stand before it stops to scan.
    That was measured in `bridge_guide_20261112_181504` run 1 (scan at 6.26, -0.24). 4.0 to 6.0 m is the nearest band in which it
    still drives (`stop_while_driving` used 6 to 9 m).
- **Idle pass:**
  - At A the worker answers with PROCEED as above and is NOT moved.
  - A second worker of the same look (`worker_id` 2, never gestures, relaxed hanging hands) stands 10.0 m before J1, 1.6 m to the
    right of the road A-J1, at (7.85, -10.0). It turns to face the robot as every worker does.
  - Its stand passes the bystander checks: `min_road_clearance_m` 1.5 (1.6 rather than exactly 1.5, so float noise in the scene's node
    positions cannot put it on the limit), 4.0 m from every commander stand, farther than the commander on every approach (nearest
    margin 1.14 m on the last 3 m before J1), a free grid cell, no collider.
- **End of a run (Unity):**
  - **`ITEM_DONE`:** the item's gesture has returned to idle and 1.5 s more have passed; for the idle pass, the robot is 3.0 m past
    the idle worker along the road.
  - **`ITEM_MISSED`:** the item has not ended 90 s after the run start, e.g. PROCEED never read at A or the driving band never
    reached.
  - **Collision and stuck:** end the run as always (FAILURE). Python's `aborted` and `done` do not end a run of this scenario: the
    item does.
  - The robot never reaches B; the goal (GoalSequence(1)) only names the grid and optimal-path files.
  - **A missed item is reported, never re-recorded** to fill the counts.
- **Fixed for the session:**
  - `trials.json` `trial_count` is not used: the plan's 64 items set it.
  - No bystanders; at most 2 avatars.
  - `session.json` `scenario` "stop_session"; `run_workers` lists every run's item.
  - `truth_run###.json` `detail` names the item.
- **Python:** `bridge.server --mode guide --task Task2 --perception vision --config configs/v4/bridge.json` with the default
  `configs/v4/control.json`: v4 map, lie detection off, the current reader. Started with `--resource-log --exit-on-disconnect`.
- **Run protocol:** `finals_v4/run_protocol_v4.ps1 -Label stop_session` before the session (free memory, programs still running). The
  free memory and the heavy programs still running are reported with the bridge's `resources.csv` minimum.
- **Checks:**
  - leak test in Unity (`session.json` `leak_test.passed`) and in Python (`gt_path.py session <folder>`);
  - every `run_###/truth.jsonl` accepted by `gesture_data.py` (with `--messages` of the bridge run);
  - the counts actually recorded per kind, look and arm, against the table above.
- **Not an evaluation:** no criterion of 16.16 is applied here (Anisha's tool and decision), and no reader value is changed.

*Part B, built as declared (commit 560ef27) and recorded once (2026-11-15). Development; not a result.*
- **Code:**
  - `TrialWorkersConfig` scenario `stop_session` (`StopSessionConfig`, `StopSessionPlan`), `TrialRunnerV4StopSession.cs`, and
    `TrialRunnerV4` hooks: per-run look, the idle stand through the bystander check `CheckStand`, the item ends the run;
  - `sessions/dev_stop_session.json`;
  - `StopSessionTests` (6): the 64 items, counts, order, clip rule, development-only looks and clips, refusals.
  - Unity Edit Mode 314/314, Python 1138 OK (2 skipped).
- **Session:** Unity `trials_development_Task2_20261115_152104` + bridge `bridge_guide_20261115_151856`.
  - Recorded on 560ef27, clean tree, Unity Editor window, server with the default `configs/v4/control.json` (current reader).
  - Logs `robot_vision/outputs/stop_session_20261115_151855_{unity,server}.log`.
- **Run protocol** (`run_protocol_stop_session_20261115_151855.txt`):
  - before the session: free memory 3,791 MB of 14,226 MB, power Best performance on mains;
  - still running (not closed): Chrome x10 (285 MB), Claude x9 (489 MB), NVIDIA container x5 and overlay x5, warp-svc;
  - during the session (`resources.csv`): available memory minimum 725 MB, hard paging median 16 pages/s, peak 58,058 pages/s.
  - The run protocol (other apps closed) was therefore NOT fully met; disclosed.
- **Every item recorded as planned, none missed:** 64/64 runs `ITEM_DONE`.
  - 20 held STOPs (5 per look per arm) and 36 negatives (3 POINT, 3 PROCEED, 3 WAIT per look per arm), all at the first ask at A,
    robot 2.08 to 2.15 m from the worker.
  - 6 driving STOPs:
    - each requested at the band's first moment, 5.98 to 5.99 m, robot 0.80 m/s, Python `navigate`;
    - shown (first gesturing frame) 5.48 to 5.71 m from the robot while it was still driving (0.35 to 0.65 m/s);
    - arms: m1 right, left, right; f1 left, right, left.
  - 2 idle passes.
  - **Deviation found (not changed):** the robot passed the idle worker at 1.06 m and 1.08 m (centre to centre), not 1.6 m. The robot
    drives from its ask position at A straight to J1, not along the road centre line, so the declared 1.6 m from the centre line was
    not the passing distance. Robot at 0.80 m/s at the closest point.
- **Bridge:**
  - watchdog stops 0;
  - 2 Unity frame stalls (11.1 s and 2.1 s), both at start-up before trial 1;
  - pan-tilt frames 11,236 sent / 11,237 received, drop rate 1.2 % on both cameras;
  - `model_outputs.jsonl` has 16,819 lines for 16,857 received frames (the worker takes the latest frame only).
- **Checks:**
  - leak test passed in Unity (`session.json` `leak_test.passed` true) and in Python (`gt_path.py session`: max diff 0, 2 pairs);
  - `gesture_data.py <run>/truth.jsonl --messages <bridge>/messages.jsonl` exit 0 for all 64 runs (19,071 truth rows);
  - counts recorded = the declared table.
- **Descriptive only (the live robot, `decisions.csv`; Anisha's tool decides the criteria):** runs with at least one stop by STOP:
  - held STOP 20/20, driving STOP 6/6;
  - negatives: PROCEED 12/12, WAIT 4/12, POINT 0/12;
  - idle pass 2/2. These runs also contain the PROCEED at A, so this count does not isolate the hanging hands.

### Part C: the zip for Anisha (read only on outputs)

- **File:** a new `robot_vision/outputs/stop_session_logs_<time>.zip`, laid out as `analyse_false_stop_v4.Logs` reads it.
- **Contents:**
  - root `stop_session_logs_<time>/`;
  - `<bridge run>/decisions.csv`, `model_outputs.jsonl`, `v4_log.jsonl`;
  - `<Unity session>/run_###/truth.jsonl` for every run;
  - `README.md` at the root.
- **The README lists:**
  - every gesture segment from `truth.jsonl`: run, kind, look, arm, command, clip, start and end `time_s`, first shown time, whether
    the robot was driving (speed from `trail.csv` above 0.05 m/s at the first shown frame, plus the share of shown time driving) and
    the robot-to-worker distance there;
  - the idle passes (window and closest distance);
  - the session ids, every file's size and SHA-256.
- **Integrity:** the zip's path, size and SHA-256 are reported. Nothing in either session folder is changed. The generating script is
  stored in the zip (`make_stop_zip.py`).

*Part C, made (2026-11-15).*
- **Zip:** `robot_vision/outputs/stop_session_logs_20261115_154026.zip` (git-ignored).
  - 4,439,567 bytes; SHA-256 `34feb2c98831986dc737b0afb03d4314edf201b9b7ce715ac27dd2461113ccbd`;
  - 69 entries (25.1 MB uncompressed): `README.md`, `make_stop_zip.py`, the bridge's `decisions.csv`, `model_outputs.jsonl` and
    `v4_log.jsonl`, and the 64 `run_###/truth.jsonl`.
- **README:**
  - the run table;
  - the counts against the plan (all as declared);
  - 70 gesture segments: 56 at the ask, 6 driving STOPs and 8 PROCEEDs that start a drive (marked "not an item");
  - the 2 idle passes;
  - every file's size and SHA-256.
- **Checks:**
  - `zipfile.testzip` clean;
  - Anisha's `analyse_false_stop_v4.Logs` opens it as is (64 runs, 11,236 decision rows, 16,819 model-output lines);
  - the session folders are unchanged except `leak_test/leak_test.json`, which `gt_path.py session` writes by design (part B check).

## 2026-11-15, section 14: the second STOP session (declared before any change or recording; nothing run)

Same branch `nusrat/v4-stop-session` (after b5afb7f). Unity side only: no file under `robot_vision/`, `docs/` or `external/` is changed,
nothing is frozen, no final is run, the session runs in the Unity Editor WINDOW. Purpose: reach Anisha's declared count, AUDIT.md 16.16
decision 3: **20 STOPs per look (10 per arm), part of them while driving**. Session 1 (section 13 part B) gave 13 per look.

**Seed 3, not 2 (Nusrat, 2026-11-15, before anything was built).**
- The task said seed 2 "so items differ from session 1". Seed 2 is the final seed (`final_plan.json` `final_seed`).
- The runner refuses `dev_seed == final_seed`.
- Each worker's draws (speed, size, start delay, hold, sway) come from the stream (session seed, run, worker id). So seed 2 would give
  this session's worker 1 in runs 1 to 14 the same draws as worker 1 in runs 1 to 14 of every final setting, and Anisha sets her
  false-STOP rule from this data.
- Seed 3 differs from session 1 just as much (the item list does not depend on the seed; only the draws do) and touches no final.

**One item per run, 14 runs, exact counts:**

| kind | command | look | arms (in order) | runs |
|---|---|---|---|---|
| held at the ask (A), 2 m | STOP | `sunbox_f1` | right, left, right, left (repetitions 1, 1, 2, 2) | 4 |
| held at the ask (A), 2 m | STOP | `sunbox_m1` | right, left, right, left (repetitions 1, 1, 2, 2) | 4 |
| STOP while the robot drives (toward J1) | STOP | `sunbox_f1` | right, left, right | 3 |
| STOP while the robot drives (toward J1) | STOP | `sunbox_m1` | left, right, left | 3 |
| **total** | | | | **14** |

- **No negatives and no idle pass:** session 1 already gave the 3 negatives of each command per look per arm (16.16 decision 3).
- **Order:** the plan of section 13 part B, unchanged code, with the looks listed as [`sunbox_f1`, `sunbox_m1`]:
  - the looks alternate run by run, `sunbox_f1` first (run 1 f1, run 2 m1, ...);
  - per look: held STOP right 1, left 1, right 2, left 2, then the three driving STOPs;
  - the plan's driving arms alternate from right for the first listed look and from left for the second. Listing f1 first gives m1
    left, right, left and f1 right, left, right: the arms session 1 did not give.
- **Totals over both sessions, per look and arm (STOP):**

| look | arm | held (S1 + S2) | driving (S1 + S2) | total |
|---|---|---|---|---|
| `sunbox_m1` | right | 5 + 2 | 2 + 1 | 10 |
| `sunbox_m1` | left | 5 + 2 | 1 + 2 | 10 |
| `sunbox_f1` | right | 5 + 2 | 1 + 2 | 10 |
| `sunbox_f1` | left | 5 + 2 | 2 + 1 | 10 |

  So 20 per look, 6 of them while driving.
- **Clips:** as in section 13 part B (repetition r uses the (r - 1) mod 2-th development clip): held reps 1, 2 `stop_ik_01`,
  `stop_ik_03`; driving 1, 2, 3 `stop_ik_01`, `stop_ik_03`, `stop_ik_01`.
  - Held clips over both sessions per look and arm: `stop_ik_01` 4, `stop_ik_03` 3.
  - Driving clips per look over both sessions: `stop_ik_01` 4, `stop_ik_03` 2.
- **Everything else as session 1 (section 13 part B):** worker at A's stand, item at the first ask after the question; the driving
  STOP shown when Python's state is `navigate`, the worker has noticed the robot and the robot is 4.0 to 6.0 m from it; settle 1.5 s;
  `ITEM_MISSED` after 90 s, reported and never re-recorded; at most 1 avatar (no idle worker); development mode; development looks
  and clips only (`DataSplitsV4.GuardRun`).

**What changes in Unity (built only after this note):**
1. `StopSessionConfig.seed` (int): the session seed of a STOP session; 0 = the runner's `dev_seed` (session 1's config has none, so
   it is unchanged). The runner refuses a STOP-session seed equal to `final_seed` or below 0. `session.json` `seed` records it.
2. `Avatar/Config/sessions/dev_stop_session_2.json` (+ `.meta`): looks [`sunbox_f1`, `sunbox_m1`], `held_stop_per_arm` 2,
   `negative_commands` [], `negatives_per_arm` 0, `driving_stop_per_look` 3, band [4.0, 6.0], `idle_pass_per_look` 0,
   `max_active_avatars` 1, `seed` 3; the other values as `dev_stop_session.json`.
3. `StopSessionTests`: the 14 items, counts, order and arms; the totals of both sessions per look and arm (10 each); development
   looks and clips only; the seed rule (0 -> dev seed, 3 accepted, the final seed and negatives refused).

**Recording and checks (as session 1):**
- `finals_v4/run_protocol_v4.ps1 -Label stop_session_2` before the session (free memory, programs still running); the bridge's
  `resources.csv` minimum reported.
- Server: `bridge.server --mode guide --task Task2 --perception vision --config configs/v4/bridge.json --resource-log
  --exit-on-disconnect` with the default `configs/v4/control.json` (the CURRENT reader; the candidate rule not switched on).
- Unity: `TrialPlayV4 -workersConfig Assets/WarehouseRobot/Avatar/Config/sessions/dev_stop_session_2.json`, Editor window.
- Checks: leak test in Unity (`session.json` `leak_test.passed`) and in Python (`gt_path.py session`); every `run_###/truth.jsonl`
  accepted by `gesture_data.py --messages`; the counts recorded against the table above.
- Not an evaluation: no criterion of 16.16 is applied and no reader value is changed.

**The zip, rebuilt with both sessions:** a NEW `robot_vision/outputs/stop_session_logs_<time>.zip` (the first zip is kept, unchanged).
- Root `stop_session_logs_<time>/` holding both pairs side by side: each session's bridge files (`decisions.csv`,
  `model_outputs.jsonl`, `v4_log.jsonl`) and every `run_###/truth.jsonl`, under their own folder names, as `analyse_false_stop_v4`
  reads a session (`sessions.<name>.bridge` / `.unity` in her config; Anisha adds the two entries, the README gives them).
- `README.md`: both session ids (S1, S2) with seed and commit; every run's item and outcome; every gesture segment with its session,
  run, look, arm, command, clip, start and end `time_s`, first shown time and whether the robot was driving; the idle passes of S1; the
  counts per look and arm against the plan of each session and against 16.16 decision 3 (20 per look, 10 per arm); every file's size
  and SHA-256.
- The script `make_stop_zip.py` (now taking several sessions) is stored in the zip. Path, size and SHA-256 reported.

*Section 14, built as declared (commit c2e75f4) and recorded once (2026-11-15). Development; not a result.*
- **Code:** `StopSessionConfig.seed` and `StopSessionPlan.SessionSeed` (config seed, 0 = dev seed; the final seed and negatives refused),
  the runner's session seed, `sessions/dev_stop_session_2.json`, 5 new `StopSessionTests`. Unity Edit Mode 319/319, Python 1138 OK
  (2 skipped).
- **Session S2:** Unity `trials_development_Task2_20261115_191700` + bridge `bridge_guide_20261115_191520`.
  - Recorded on c2e75f4, clean tree, Unity Editor window; `session.json` mode development, seed 3, scenario `stop_session`, 14 runs.
  - Server with the default `configs/v4/control.json` (current reader).
  - Logs `robot_vision/outputs/stop_session_2_20261115_191518_{unity,server}.log`.
- **Run protocol** (`run_protocol_stop_session_2_20261115_191518.txt`):
  - before the session: free memory 3,865 MB of 14,226 MB; `launch_prep`: power mode Best performance on mains;
  - still running (not closed): Chrome x6 (529 MB), Claude x1 (247 MB), NVIDIA container x4 (121 MB), warp-svc (52 MB);
  - during the session (`resources.csv`, 471 samples): available memory minimum 882 MB (median 1,299 MB), hard paging median
    11.9 pages/s, peak 32,292 pages/s.
  - The run protocol (other apps closed) was therefore NOT fully met; disclosed.
- **Every item recorded as planned, none missed:** 14/14 runs `ITEM_DONE`.
  - 8 held STOPs (2 per look per arm) at the first ask at A, robot 2.06 to 2.11 m from the worker; clips `stop_ik_01` (rep 1),
    `stop_ik_03` (rep 2).
  - 6 driving STOPs:
    - requested at 5.96 to 6.00 m, robot 0.80 m/s, Python `navigate`;
    - shown (first gesturing frame) 5.52 to 5.74 m from the robot while it was still driving (0.43 to 0.67 m/s);
    - arms: f1 right, left, right; m1 left, right, left; clips `stop_ik_01`, `stop_ik_03`, `stop_ik_01`.
  - **Both sessions together: 10 STOPs per look and arm** (7 held + 3 driving), 20 per look, as AUDIT.md 16.16 decision 3.
- **Bridge:**
  - watchdog stops 0;
  - 1 Unity frame stall (2.46 s) at start-up, before trial 1;
  - round trip max 45.1 ms, event-loop lag max 84 ms;
  - pan-tilt frames 3,588 sent / 3,588 received, Unity drop rate 3.65 % (session 1: 1.2 %); 360 frames 0.11 %;
  - `model_outputs.jsonl` 4,774 lines.
- **Checks:**
  - leak test passed in Unity (`session.json` `leak_test.passed` true) and in Python (`gt_path.py session`: max diff 0, 2 pairs; it
    writes `leak_test/leak_test.json` by design);
  - `gesture_data.py <run>/truth.jsonl --messages <bridge>/messages.jsonl` exit 0 for all 14 runs (4,244 truth rows);
  - counts recorded = the declared table.
- **Descriptive only (the live robot, `decisions.csv`):** a STOP reading in 14/14 runs. Anisha's tool decides the criteria.

*Section 14, the zip with both sessions (2026-11-15).*
- **Zip:** `robot_vision/outputs/stop_session_logs_20261115_192423.zip` (git-ignored; the first zip is kept unchanged).
  - 5,410,206 bytes; SHA-256 `ca1173ac497eed26ea6e075547a5fae018fc98be7d13c056bae72164162755a5`;
  - 86 entries (30.6 MB uncompressed): `README.md`, `make_stop_zip.py` (version 2), and for S1 and S2 the bridge's `decisions.csv`,
    `model_outputs.jsonl`, `v4_log.jsonl` and every `run_###/truth.jsonl` (64 + 14).
- **README:**
  - both sessions (S1, S2) with seed and commit;
  - the `sessions` entries for Anisha's `false_stop_analysis.json` (she adds them);
  - the STOP totals per look and arm against 16.16 decision 3 (10 each) and the counts against each session's plan (all as declared);
  - 78 runs, 90 gesture segments (each with its session), the 2 idle passes of S1, every file's size and SHA-256.
- **Checks:** `zipfile.testzip` clean; Anisha's `analyse_false_stop_v4.Logs` reads both sessions as they are (S1: 64 runs, 11,236 decision
  rows, 16,819 model-output lines; S2: 14 runs, 3,650 decision rows, 4,774 model-output lines); every run passes her split guard as
  development.

## 2026-11-16, section 15: step 5, development runs of the final matrix (STOPPED by the Set A wrong-branch rule after A3)

Branch `nusrat/v4-step5-dev` = main 8848a7a (PR #39: Anisha's STOP rule, `gesture_reader.json` `stop_requires_raised` true,
`stop_fingertip_spread_min` 1.3). Unity side only: nothing under `robot_vision/`, `docs/` or `external/` changed, nothing frozen, no final
run, nothing tuned. **Development data, not a result.**

**Plan (Nusrat's task):** the 13 final settings, 3 runs each, with `finals_v4/run_session_v4.ps1 -Rehearsal -Trials 3`. That means the final
settings' maps, routes, lie switches and control files, with the dev seed (1), development looks and clips, and the development timeout
(420 s, `trial_plan_v4.json`). Each B setting runs next to its `_off` partner; the session runs in the Unity Editor window. Stop rule: a
wrong-branch decision in Set A ends the step after that setting's 3 runs.

**Preconditions:**
- branch = origin/main 8848a7a, clean;
- Python 1163 OK (2 skipped), Unity Edit Mode 319/319;
- free memory 3,317 MB of 14,226 MB, power mode Best performance on mains;
- still running and not closed: Chrome x9 (about 620 MB) and the Claude / VS Code session. "Other apps closed" was therefore NOT fully met;
  disclosed.

**Run (one Unity start and one server per session):**
- Sitting 1 (21:28 to 22:22): A1, B1, B1_off, A2_right, B2_right, B2_right_off, A2_left.
- Sitting 2 (22:23): A3.
- Then STOPPED. Not run: B3, B3_off, A4, B4, B4_off, and the avatar-experiment rehearsal.
- Free memory before each session: 3.3 to 4.6 GB, never under 2 GB. Minimum during the sessions (bridge `resources.csv`): 293 to 637 MB.

**Checks, every session:**
- launcher B11 check REHEARSAL VALID;
- leak test passed in Unity (`session.json` `leak_test.passed`) and in Python (`gt_path.py session`);
- every `run_###/truth.jsonl` accepted by `gesture_data.py --messages`;
- `export_csv_v4.py --session` (development) written.

**Outcomes:**

| setting | SUCCESS | failures | longest run (s) | dialogs: correct / wrong branch / asked again / abort | accepted STOPs (true / false) | watchdog | round trip max (ms) | loop lag max (ms) |
|---|---|---|---|---|---|---|---|---|
| A1 | 3/3 | - | 84.7 | 6 / 0 / 0 / 0 | 0 / 19 | 0 | 70.7 | 68 |
| B1 | 3/3 | - | 93.0 | 5 / 0 / 1 / 0 (1 rejected) | 0 / 15 | 0 | 61.3 | 68 |
| B1_off | 3/3 | - | 68.9 | 3 / 0 / 0 / 0 | 0 / 10 | 0 | 97.1 | 115 |
| A2_right | 2/3 | run 3 aborted at A | 139.4 | 7 / 0 / 5 / 3 | 0 / 21 | 0 | 58.9 | 68 |
| B2_right | 3/3 | - | 138.7 | 8 / 0 / 6 / 2 (2 rejected) | 0 / 32 | 0 | 215.5 | 225 |
| B2_right_off | 1/3 | run 1 aborted at B, run 2 at A | 99.9 | 3 / 0 / 3 / 2 | 0 / 19 | 0 | 42.8 | 83 |
| A2_left | 1/3 | runs 1 and 3 aborted at A | 164.7 | 2 / 0 / 7 / 6 (1 rejected) | 0 / 27 | 0 | 65.0 | 84 |
| A3 | 1/3 | runs 1 and 2 timed out (420 s) | 420.0 | 9 / 2 / 6 / 5 | 0 / 23 | 0 | 46.0 | 52 |

- **Every abort:** "gesture unclear after 2 asks" (PROCEED unread at A or B).
- **False STOPs:**
  - all 166 accepted STOPs were false; no worker shows STOP in the experiments;
  - 154 came while the commander swung PROCEED (phase holding), 12 right after it (phase returning);
  - all came in the states read, approach or execute, none while navigating;
  - each episode lasted at most about 0.4 s;
  - these are STOP-gesture episodes in `decisions.csv`. Python's own `safety_stops` counts every safety stop (STOP gesture and person in
    path), so it is a different count. It equals the STOP episodes only in A1 (19) and B1 (15). A3: 58 against 23 STOP and 34
    person-in-path episodes. B1_off, A2_right, B2_right, B2_right_off, A2_left: 1 to 3 more than the STOP episodes (`decisions.csv`
    has one row per 0.1 s, so a shorter stop may not show). *Corrected 2026-11-17 (addendum 1, item 3e); the sentence first said the
    counts equal Python's `safety_stops` per run.*
- **Set B lies (given / detected / corrected / fooled):** B1 2/2/2/0, B1_off 0/0/0/0, B2_right 4/3/3/0, B2_right_off 2/0/0/0.
  - Without a second opinion the liar at A is seldom asked, so `_off` gives fewer lies.
  - Mean time minus the matching A setting: B1 +3.2 s, B1_off -15.5 s, B2_right +31.7 s, B2_right_off -40.0 s. These means mix in
    failures; the per-run pairs are in the report.
- **Closest person:** at least 1.10 m in every setting except A3 (0.38 and 0.41 m, both while stopped; no collision).

**The stop (A3 run 1, goal E2, J1 true branch LEFT):**
- J1's three workers pointed LEFT. Their answers were ambiguous (second view) or unread.
- Looking for a second opinion, the robot approached the next person: J2's workers (w7 at (-0.75, 2.0), w6 at (-3.25, -2.0)). It drove
  about 3.7 m from J1 toward J2 to ask them.
- Unity's answer rule ("the active worker within 3.5 m nearest the pan-tilt axis answers") let them answer for THEIR node. Unity's
  `truth_run001.json` `shown` says junction J2, RIGHT (north, toward E2).
- Python, still at J1 heading north, resolved that pointing as FORWARD. The reader read what was shown; the export marks it truthful.
- Two answers agreed, so the controller decided "go FORWARD" at J1 (t 160.99 s): a wrong-branch decision.
- The robot never drove that branch: it stood "stopped: person in path" next to w7 until the timeout.
- Run 2 timed out the same way after a correct "go RIGHT": stopped next to a worker beside J3.
- **Cause, as found:** a scenario fault in the multi-node "beside" layout (like the R3 bystander finding of Stage D2, `upgrade_design.md`). It is not a reader
  error. Fix options are for Nusrat and Anisha, not chosen here:
  - Unity: a worker answers only an ask at its own node;
  - Python: the second-opinion search stays near the junction;
  - placement: wider slots.

**Tools (new, `finals_v4/`):**
- `step5_session_checks.ps1`: the extra checks, the export and the session list `robot_vision/outputs/step5_sessions.json`. It also rewrites
  the launcher's console transcript (`outputs/step5_launcher_<setting>.txt`) with repository-relative paths. The first transcripts held
  absolute paths, and the Python test `test_run_paths` (no absolute path under `outputs/`) failed on them. They were rewritten the same
  way; nothing else changed.
- `step5_report.py`: the per-setting report, `step5_durations_<time>.csv` and `step5_stops_<time>.csv`. Evaluation only.
- `avatar_rehearsal_check.py`: the blind format check of the avatar rehearsal. No model; tested read-only on an old Edit-mode folder; not
  yet used.
- **Fix in `check_session_v4.ps1`:** it inherited `$ErrorActionPreference = "Stop"` from the launcher, so the stderr of criterion 2 ("not
  frozen") ended the check after criterion 1. It now sets Continue in its own scope. A1's check was run by hand: VALID.

**Outputs (`robot_vision/outputs/`, git-ignored):**
- `step5_report_20261116_224356.md`, `step5_durations_20261116_224356.csv`, `step5_stops_20261116_224356.csv`;
- `step5_launcher_<setting>.txt`;
- `run_protocol_rehearsal_<setting>_*.txt`.

### 2026-11-17, section 15 addendum 1: after the diagnosis (declared before any change below)

Nusrat's task of 2026-11-17, after the report-only diagnosis (PROCEED: the pose did not cause the PROCEED misses or the false STOPs; no pose
change). Branch `nusrat/v4-step5-dev`. Nothing under `robot_vision/`, `docs/` or `external/` changes; nothing is frozen, no final is run,
nothing is pushed. Development work, not a result.

**Already done before this declaration (read only, no change to the repository):**
- Item 1, the zip for Anisha. It reads `outputs/` only and adds one new zip file (record below).
- A geometry-only model of the placement, used to find out whether item 3b can be met. It uses the config and map files and one run's saved
  `grid.json` for the free cells; it reads no trial results. Findings that shaped this declaration:
  - with the beside slots of section 3 and a 1.0 m clearance, workers on `turn_left` and `roadmap` stand 0.03 to 0.89 m from a segment the
    robot can drive. One case is J1's slot-2 ask position to J3, which passes J3's slot-2 worker at 0.34 m: A3 run 2 stopped there;
  - over every pair and triple of junction slots on a 0.5 m grid (before_m -8 to 10, right_m -4.5 to 4.5), every rule together is met only
    by workers at the junction corners, two of them ahead of the node;
  - in the random layout (Anisha's 6 m square), 3 workers at J1 are practically never placeable under the clearance (0 of 1,000,000
    draws); 2 are (about 1 in 400).
- Nusrat chose (2026-11-17): adopt the corner slots, and 2 workers at J1 in A4 and B4.

**Item 2, answers for Anisha's recovery (report only, no behaviour change):**
- **(a) Reversing.** A Play-mode check. A new unsaved copy of the v4 scene has `TrialRunnerV4` and the bridge client disabled, so no
  Python and no trial run.
  - The robot stands at (6.25, -10.0), facing +z. One worker in a development look (`sunbox_m_shirt_white`) stands 1.2 m ahead, centre to
    centre.
  - `DiffDriveController.SetCommand(-0.2, 0)` until the robot has moved 1.0 m backward, then (0, 0).
  - Reported: the ramp, the speed reached, the distance, lateral drift, heading change, overshoot after the stop command, the signed `V`
    that telemetry sends, and collisions.
  - The code already clamps v to +-`max_speed_mps` (no rejection of a negative v); the check confirms the motion.
- **(b) Side waypoints.** An Edit-mode batch tool on the v4 scene's AMR NavMesh (the bridge's agent type and snap rule). For every road of
  every map (`corridor`, `turn`, `turn_left`, `roadmap`):
  - a point every 0.5 m along the road;
  - a waypoint 1.0 m to its left and to its right;
  - "reachable" when the waypoint is on the NavMesh within 0.05 m, the path from the road point is complete, and the path is at most 1.5 m
    long.
  - Reported per road and side (counts, and where it fails), plus which side the beside workers stand on near each node.

**Item 3a, who answers: a zone per node (live).**
- A worker answers a new ask only while the robot's centre is within `answer_zone_radius_m` = **6.0 m** of the worker's own node. Outside
  its zone it answers NONE:
  - the worker chosen by the existing rule (nearest the pan-tilt axis within 3.5 m) becomes the commander but shows nothing, so
    `truth.jsonl` has `true_command` NONE;
  - the ask record says `NONE (outside the <node> zone)`.
- **Why 6.0 m:**
  - zones never overlap: 2 x 6.0 < 12.5 m, the shortest distance between two asking nodes of any map;
  - with `answer_zone_margin_m` 0.5 m, every modelled ask position of a node's own workers must lie within 5.5 m of the node. The live slots
    reach 5.40 m at J1 (second opinions) and the corner slots 4.95 m.
- **What it does not cover:** a robot that Python drives into another node's zone and then asks that node's worker still gets an answer
  for that node. Example: A3 run 1 at 159 s was 4.7 m from J2. Unity cannot tell that apart from a legitimate ask there; the fix is
  Python's second-opinion search staying near its node (for Anisha). A3 run 1 at 136 s (7.3 m from J2) would now get NONE.
- Edit Mode tests.

**Item 3b, placement clearance (built, with the new layout PENDING):**
- **The rule.** No worker within `path_clearance_m` = **1.0 m** of any segment the robot can drive. 1.0 m = Python's person-in-path
  corridor half-width 0.6 m (`hri_control.json` `safety.corridor_half_width_m`) + 0.4 m (the re-ask shift, also the allowance for where
  the robot really stands).
- **The segments**, straight, as Python's `_target` sends the robot (NavMesh paths are straight in the open aisles):
  - every road of the run's map and of the physical v4 map;
  - per asking node, from the node to the ask position of each of its workers, in every order (second opinions), including the return to
    the first worker (tie);
  - from every ask position, and its re-ask point, to the next node of every branch of the node (any branch can be taken after a wrong
    answer or a lie).
- **The ask-position model.** The ask position is `ask_standoff_m` 2.0 m from the worker toward where the robot comes from (the node, or
  the previous ask position); the re-ask point is that position moved `reask_shift_m` 0.4 m to the robot's right and put back on the
  2.0 m circle. Both values are Python's (`hri_control.json` `dialog`); Unity holds copies in its config.
  - Not modelled: Python turning its approach point by 30-degree steps when another person is within 1.2 m of it.
- **Zone check.** The same model's ask positions must lie within `answer_zone_radius_m - answer_zone_margin_m` of their node (item 3a).
- **Checked** against the workers already placed at other nodes and against the new node's own workers. Applies to beside (fixed slots)
  and random (redraws).
- **Layout (Nusrat's choice):**
  - junction slots: 1 = 2.5 m before, 2.5 m left; 2 = 4.5 m ahead, 3.5 m right; 3 (J1 in A3 and B3) = 5.0 m ahead, 3.5 m left;
  - start slots unchanged;
  - A4 and B4: 2 workers at J1.
  - Among the slot sets that meet every rule this one has the smallest largest own-ask distance (4.95 m), then the least movement from
    the section 3 slots.
- **Why it stays PENDING.** Anisha's `tests/test_lie_detection_v4.py` `MatchesUnity` requires Unity's `junction_slots`, `start_slots` and
  `three_worker_nodes` to equal her `scenarios_ab.json`. Changing them alone would fail her suite, and her files are hers. So:
  - the new values go into a `clearance_layout` block of `experiments_ab_unity.json` with `"active": false`;
  - the code applies the block, the clearance and the zone check only when it is active;
  - the live layout stays as in section 3 until Anisha changes `scenarios_ab.json` (slots, `people_by_node` of scenario 4), her tests and
    her simulator's placement rules; then the block is switched on in one change.
- **Edit Mode tests:**
  - with the block applied: every run of seed 1 and seed 2 (20 runs each) of every setting (A1, A2 right and left, A3, A4, B1, B2 right and
    left, B3, B4; the `_off` settings use the same Unity plans) is planned, and every worker keeps the clearance and the zone;
  - the live slots with the clearance on reproduce the A3 run 2 geometry (0.34 m);
  - the live config plans as before.

**Item 3c, development-only goal override:**
- `TrialPlayV4 -experimentGoals E5,E6,...` replaces the seeded goals of an experiment session.
- **Refused:**
  - in a final (`-finalSetting`);
  - on a fixed-goal map (A1, B1, A2, B2);
  - a name that is not an endpoint of the map;
  - a list whose length is not the number of runs.
- **Recorded:** `session.json` `goal_order` holds the list, and a new Unity key `goals_override` holds the given text ("" without one),
  like `navigation_looks_override`. Python does not check `session.json` keys (v3's `hri_trials` recomputes `goal_order`; v4 tools read
  each run's goal from `truth_run###.json`).
- **Launcher:** `run_session_v4.ps1 -ExperimentGoals "E5,E6,E5"`, rehearsal only, refused in a final, passed through to Unity.
- Edit Mode tests on the parsing and every refusal.

**Item 3d, the PROCEED palm in the geometry check (reported, no pass/fail change):**
- On every measured PROCEED frame (the swing window `proceed_window_s`), from the bones (`HandGeometry.Frame`, the palm normal the poser
  sets), measure:
  - the angle between the palm normal and the direction to the stand-in robot camera;
  - the angle between the palm normal and the direction to the worker's torso centre (halfway between the midpoint of the two UpperArm
    bones and the Hips bone).
- Per look, arm and take: min, mean and max of both angles, the frames where the palm faces the camera more than the body (camera angle
  < body angle), and the frames with the camera angle under 60 degrees.
- A new table `proceed_palm_table.md`. The arm, hand and skinning checks and their pass are unchanged. All looks; no perception.

**Item 3e:** correct the sentence about `safety_stops` in section 15 (below, in its own commit).

**Commits:** one per item (declaration; 3e; 2a and 2b; 3a; 3b; 3c; 3d), each after both suites pass.

*Item 1, made (2026-11-17).*
- **Zip:** `robot_vision/outputs/step5_logs_20261117_011303.zip` (git-ignored).
  - 9,431,342 bytes; SHA-256 `75bbc8851a758a76c7140a20b8c24e10035d6c0095091d1b2429099c42d17d3f`;
  - 71 entries (94.8 MB uncompressed); `zipfile.testzip` clean.
- **Contents:**
  - the 8 step-5 sessions in the layout of the section 13 zip: `<bridge run>/decisions.csv`, `model_outputs.jsonl`, `v4_log.jsonl`;
    `<Unity session>/run_###/truth.jsonl` (24 runs);
  - `step5_durations_20261116_224356.csv`, `step5_stops_20261116_224356.csv`, the step 5 report and `step5_sessions.json`;
  - `diagnosis/`: the diagnosis tables (`proceed_out/proceed_per_ask.md` and its per-frame JSON), the captured console outputs (PROCEED
    summary, valid frames, replay vs live, A3 timeline, safety stops by cause) and their scripts;
  - `make_step5_zip.py`;
  - `README.md`: a table naming each setting (experiment, map, A2 side, lie detection on/off, goals, folders) and every file's size and
    SHA-256.

*Item 2, answers for Anisha's recovery (2026-11-17).* Tools: `Robot/PlayCheck/ReverseDriveCheck.cs`, `Robot/Editor/RecoveryChecksMenu.cs`
(Tools > Warehouse v4 > Recovery). Report only; no behaviour changed.
- **(a) Reversing: yes.** `robot_vision/outputs/reverse_drive_check_20261117_022117/` (`report.md`, `samples.csv`; batch-mode Play, 0 errors).
  - `DiffDriveController` takes a negative v: v = -0.20 m/s was reached in 0.40 s (the 0.5 m/s^2 ramp).
  - v = 0 was commanded at 1.002 m; the robot stood at 1.040 m. The overshoot of 0.038 m is the braking distance at 0.5 m/s^2.
  - Lateral drift 0.0000 m, heading change 0.000 deg, no collision.
  - The worker (`sunbox_m_shirt_white`, a development look) stood 1.20 m ahead; 2.24 m after the move.
  - Telemetry's `v` is the signed `drive.V`, so Python sees -0.20.
  - The check's PASS rule (within 0.1 m, drift under 0.02 m, heading under 0.5 deg, no collision) was set in the check's code before it
    ran, not in this addendum.
- **(b) Side waypoints: yes on every road, but the NavMesh cannot tell.** Final run: `robot_vision/outputs/navmesh_side_waypoints_20261117_021955/`.
  - Earlier runs `_021708` and `_021805` were the same tool without, then with a first negative control; kept, superseded.
  - All 1220 points (every road of `corridor`, `turn`, `turn_left`, `roadmap`, every 0.5 m, both sides) passed: a waypoint 1.0 m to the side
    on the AMR NavMesh, with a complete straight path of 1.00 m.
  - **Negative control failed: the baked AMR NavMesh does not contain the racks.** From the aisle at (6.25, -5) the NavMesh gives a complete,
    straight 6.25 m path to the rack centre (0, -5), and the same at two other rack centres. The ground-truth grid marks those cells
    blocked. Only the point beyond the south wall is off the NavMesh.
    - So a NavMesh path or snap test cannot vouch for a recovery waypoint.
    - The bridge's NavMesh targets are not checked against racks either: worth knowing for Anisha's recovery and for any target off the
      roads.
    - Not investigated further: why the racks are missing from the bake.
  - **Independent check against the ground-truth grid** (`grid_check.md` in the same folder; the v4 grid of
    `trials_development_Task2_A3_20261116_222448/run_001/grid.json`, colliders widened by 0.40 m). The road point, the waypoint and the
    straight 1.0 m move to it are free for **1220 of 1220** samples, on both sides of every road.
  - The aisles are about 10 m wide, so 1.0 m to either side is clear of static obstacles everywhere. **"The clear side" is decided by the
    workers only.** `report.md` lists, per road, which side and how far along each beside worker stands (live slots). In the live layout
    the junction workers stand 2.0 m beside the arrival road, slot 1 on the left 3.0 m before the node, slot 2 on the right 5.5 m before it.

*Item 3a, made (2026-11-17, commit 8375ba8).*
- `answer_zone_radius_m` 6.0 is in `experiments_ab_unity.json`. `TrialRunnerV4Experiment` gates each new ask with
  `ExperimentPlanAB.InAnswerZone`:
  - outside the zone the chosen worker is the commander but gets no request (truth NONE);
  - the ask record reads `NONE (outside the <node> zone)`; `session.json` `answer_rule` says so.
- 5 Edit Mode tests (`HRI/Tests/ExperimentAnswerZoneTests.cs`):
  - the radius and its refusal at 0;
  - the A3 run 1 positions: 7.6 m from J2 gets NONE, 4.7 m still answers (the uncovered case);
  - the ask-position helper;
  - every own ask position of the live layout (A1 to A4, seeds 1 and 2, 20 runs) within 5.5 m;
  - no two zones overlap on any map.
- Not run in Play (no Python session); the gate is covered by the logic tests only.

*Item 3c, made (2026-11-17, commit 89d7cd1).*
- `ExperimentPlanAB.GoalsOverride`, `TrialPlayV4 -experimentGoals`, `session.json` `goals_override`, and
  `run_session_v4.ps1 -ExperimentGoals`.
- 6 Edit Mode tests (`HRI/Tests/ExperimentGoalsOverrideTests.cs`): no override, order and spaces, planning with the given goals, and the
  refusals (final, fixed-goal maps, unknown names, empty name, wrong count).
- Launcher dry runs:
  - A3 with `"E5, E6,E5"` passes `-experimentGoals E5,E6,E5` to Unity;
  - refused: A1 (fixed goal B), a count that differs from `-Trials`, a final.
- Not run in Play.

*Item 3b, made (2026-11-17).*
- `ExperimentPlanAB.DrivableSegments` / `ReaskPosition` / `ClearanceProblem`, `PlacementRule.PathClearanceM` / `AskZoneM`, and
  `ExperimentsUnityConfig.WithClearanceLayout`.
- In `experiments_ab_unity.json`: `answer_zone_margin_m` 0.5, `path_clearance_m` 1.0, `ask_standoff_m` 2.0, `reask_shift_m` 0.4, and the
  `clearance_layout` block with `"active": false`.
- `session.json` `clearance_rule` says whether the checks were applied (now: pending).
- **Disclosure: the slots differ from the ones declared above.**
  - The slot search before the declaration left out one declared segment, the return to the first worker (tie).
  - Under the full declared model, checked by Unity's Edit Mode test, the declared choice (slot 1 2.5 m before, slot 3 3.5 m left) failed
    at A3 J1 seed 1 run 1: worker 3 stood 0.97 m from the segment from its own tie ask position (3.41, 3.11) to E1.
  - The search was rerun with the tie, with the same rules and the same declared choice rule (meets every rule; smallest largest own-ask
    distance; then least movement). Nothing else changed: no value and no rule.
  - Its first choice, now pending:
    - slot 1: **3.5 m before**, 2.5 m left;
    - slot 2: 4.5 m ahead, 3.5 m right;
    - slot 3 (J1 in A3, B3): 5.0 m ahead, **4.0 m left**;
    - largest own-ask distance 5.19 m (within 5.5).
  - Still a corner layout, as Nusrat chose. With the tie included, 58 slot sets keep the clearance and 8 of them also keep the 5.5 m ask
    zone.
- 5 Edit Mode tests (`HRI/Tests/ExperimentClearanceTests.cs`):
  - the config values and that the block is inactive;
  - **all 400 plans with the pending layout pass**: A1, A2 right and left, A3, A4, B1, B2 right and left, B3, B4; seeds 1 and 2; 20 runs
    each. Each plan gets an independent re-check of separation, turning points, bystander margin, clearance to every road and every
    drivable segment, ask positions within 5.5 m, and at most 6 active avatars;
  - the segment model (every order, the tie, every branch, the re-ask point on the 2.0 m circle);
  - the live slots with the clearance on are refused. From A3 run 2's logged ask position (6.3, -5.3) the line to J3 passes J3's slot-2
    worker at 0.31 m; the diagnosis's 0.33 m was measured from the driven trail;
  - the live config plans as before.
- **Not checked:** free cells and colliders for the pending slots at Play. The Edit Mode tests have no scene; the search checked the slot
  positions against the saved ground-truth grid. Unity checks both at Play once the block is active.
- **For Anisha (her files; nothing changed there):**
  - `scenarios_ab.json` `junction_slots` of scenarios 1 to 3 = the pending slots;
  - scenario 4 without `people_by_node` J1 3 (A4 and B4: 2 at J1);
  - her `MatchesUnity` tests (`test_the_slots_and_margins_are_unitys`, `test_slot_positions`);
  - her simulator's placement: the clearance and the ask zone, so that the simulator still does what Unity does (AUDIT.md 16.13);
  - then Nusrat sets `clearance_layout.active` true (and the live `junction_slots` / `three_worker_nodes` to the pending values) in one
    change;
  - also for Anisha (items 2b and 3a): keep the second-opinion search near its node.

*Item 3d, made (2026-11-17).*
- `GestureGeometryDriver` measures the PROCEED palm and writes `proceed_palm_table.md`. The other checks and the pass are unchanged.
- **Run:** `robot_vision/outputs/gesture_geometry_proceed_palm_20261117_034140/` (batch mode, all 15 looks, no perception).
  - `run_info.json` names HEAD 89d7cd1: the run used the uncommitted 3b and 3d edits; 3b does not touch the geometry check.
  - Arms 15/15, skinning 15/15, hand 13/15 (anime_f_01 and anime_f_03: the known sleeve artefact of section 12), as before.
- **PROCEED palm (bones):**
  - It faces the camera within 60 deg only on Boxo with `proceed_ik_01` (20 of 695 frames, minimum 56.7 deg). On every other look it
    stays at least 61.8 deg from the camera.
  - Mean angle to the camera: 110 to 133 deg by clip. The camera mostly sees the back or the edge of the hand, as MediaPipe did in the
    diagnosis.
  - Mean angle to the torso centre: 77 to 88 deg, i.e. palm up or toward the chest, as designed.
  - Frames with the palm nearer the camera direction than the body direction: 9 to 12 % per look (Boxo 28 %). By clip: `proceed_ik_01`
    30 %, `proceed_ik_02` 4 %, `proceed_ik_03` 2 %. The low part of `proceed_ik_01` again (as the diagnosis said).
- Read with the diagnosis: the pose does not show the palm to the camera. The false STOPs come from the reader's open-hand cues on the
  back of a hand with closed fingers, not from a palm turned toward the robot.

### 2026-11-17, section 15 addendum 2: racks in the robot's NavMesh (declared before any change below)

Nusrat's task of 2026-11-17, before the step-5 rerun: the racks are missing from the AMR NavMesh (item 2b's failed negative control).
Branch `nusrat/v4-step5-dev`. Nothing under `robot_vision/`, `docs/` or `external/` changes; nothing is frozen, no final is run, nothing is
pushed. Development work, not a result.

**Already done before this declaration (read only; a temporary Editor script, deleted again, nothing tracked changed):** a batch-mode
diagnosis of the v4 scene. It called the NavMesh Surface's own source collection and matched every collected mesh to the obstacle groups
of `robot_unity_v4.json` (`Shelves`, `FloorBoxes`, `Walls`, `Stations`).
- The v4 scene has one NavMesh Surface: agent type AMR (radius 0.5 m, height 1.8 m, slope 5 deg, step 0.02 m), collect "All", render
  meshes, all layers. Its baked data is `Assets/Scenes/WarehouseRobot/NavMesh-NavMesh Surface.asset`: the **v3 scene's asset**. The v4
  scene was copied from v3 and both scenes still share it.
- **Cause:** the Surface has "Ignore NavMesh Obstacles" on. It drops every collected mesh whose GameObject has a `NavMeshObstacle`.
  The generated warehouse put one on every rack and on every pallet: 93 `NavMeshObstacle`s, all under `GeneratedWarehouse/Shelves`.
  12 are the racks (disabled, carving); 81 are the pallets (enabled, not carving). So none of the 93 rack and pallet meshes (12 racks)
  reached the bake: 652 meshes were collected, 0 of them from `Shelves`.
- Neither obstacle type puts the racks back at Play: the rack obstacles are disabled, and the pallet obstacles do not carve. The bridge's
  NavMesh paths therefore ignore the racks in Play as well.
- **Not the cause:**
  - layers: all `Default`, the mask takes all;
  - static flags: none set, and "All" does not need them;
  - colliders: the Surface bakes render meshes, not colliders. The racks have their own colliders (165), so `ColliderSetup` adds none
    to them; it adds boxes only to the stations, at Play;
  - `NavMeshModifier`s: 5, each ignoring the robot or a worker, as intended.
- **Walls and stations are collected** (36 of 36 walls and 25 of 25 stations). `FloorBoxes` is empty in the v4 scene (0 units): the
  only boxes are the pallets on the racks, under `Shelves`.

**The fix (v4 scene only):**
- On the v4 scene's NavMesh Surface, "Ignore NavMesh Obstacles" off. Everything else stays as it is: the agent type and its settings,
  render meshes, collect All, the modifiers that keep out the robot and the workers.
  - Not baking from physics colliders: the stations get colliders only at Play (`ColliderSetup`), so an Edit-mode bake from colliders
    would lose them. Render meshes already include the walls and the stations.
  - The vendored warehouse objects and their `NavMeshObstacle`s stay unchanged.
- Rebake into a **new asset**, `Assets/Scenes/WarehouseRobot_v4/NavMesh-AMR.asset`, referenced only by the v4 scene:
  - the Editor's Bake button deletes the Surface's current asset before it saves the new one. Here that is the v3 asset, still used by the
    v3 scene (v1.0 must stay reproducible). So the bake is a script: `NavMeshSurface.BuildNavMesh`, then save the data as the new asset.
  - The v3 scene and its asset stay byte-for-byte unchanged.
  - Tool: Tools > Warehouse v4 > NavMesh > Bake v4 NavMesh (and a batch method). It refuses any scene but the v4 one, and any target
    path that already exists.
- **Every experiment map:** `corridor`, `turn`, `turn_left` and `roadmap` are road graphs on the one floor of the v4 scene; there is no
  other scene or NavMesh. One bake covers all four maps. The verification checks each map separately.

**Verification (Tools > Warehouse v4 > NavMesh > Verify; Edit mode, batch; report only, into a new
`robot_vision/outputs/navmesh_v4_check_<time>/`). Rules fixed here, before anything is baked:**
- **V1, NavMesh paths and racks.**
  - **Point set per map:** every node of the map and of the physical v4 map (start, junctions, endpoints). Also every ask position and
    re-ask point of the item 3b model (`ExperimentPlanAB.DrivableSegments`, standoff 2.0 m, shift 0.4 m), taken from every planned run:
    seeds 1 and 2, 20 runs, all 10 Unity settings (A1, A2 right and left, A3, A4, B1, B2 right and left, B3, B4), in both the live layout
    and the pending clearance layout. Duplicates within 0.01 m are merged.
  - **Paths:** a NavMesh path between every pair of points of the same map, by the bridge's rule (AMR filter; both ends snapped with
    `NavMesh.SamplePosition` within `snap_max_distance_m` 1.0 m). Each path is sampled every 0.05 m along its corners.
  - **Footprints:** the obstacle footprints of the ground-truth grid (`ObstacleFootprints`: every unit of the four groups, its colliders
    or mesh boxes in the robot's height band), not widened.
  - **Pass needs all three:**
    - (a) no path sample lies inside a footprint;
    - (b) every path is complete;
    - (c) every point snaps within 1.0 m.
  - **Reported:** per map, the least clearance of any path to a footprint, the paths closer than 0.40 m (the grid's widening), and the
    snap distances.
- **V1 negative control (must pass):**
  - the three rack centres of item 2b's control are not reachable under item 2b's test;
  - the straight line from (6.25, -5) to (-6.25, -5) crosses the rack at (0, -5), and the NavMesh path between those points does not.
- **V2, NavMesh against the ground-truth grid (report).**
  - The grid is the official v4 grid (0.5 m cells, widened by 0.40 m), built in Edit mode by `GroundTruthLayer.BuildGrid`, as at Play.
    It is also compared cell by cell with run_001's saved `grid.json` of `trials_development_Task2_A3_20261116_222448`.
  - Every cell centre is "on the NavMesh" when `NavMesh.SamplePosition` finds the AMR NavMesh within 0.05 m horizontally.
  - Four counts: both free; both blocked; grid free but off the NavMesh (the NavMesh is stricter); grid blocked but on the NavMesh (the
    NavMesh is looser).
  - For each disagreeing cell: its position, the distance from its centre to the nearest footprint, and whether that centre is on the
    floor. Expected, and not a failure: a band where the NavMesh's 0.5 m radius (rounded to its 0.167 m voxels) exceeds the grid's 0.40 m.
  - **Hard rule, the same as V1 (a):** no cell centre inside a footprint is on the NavMesh. Every other disagreement is reported, not
    judged.
- **V3, the 1.0 m side waypoints again.** Item 2b's tool, rerun unchanged on the new NavMesh, with NavMesh paths.
  - Its negative control must now pass.
  - Its counts are reported, and compared with the grid check of item 2b (1220/1220 free).
  - One text fix in that tool's report: it still describes the pending slots as declared ("2.5 m before", "3.5 m left"), not as built
    ("3.5 m before", "4.0 m left", item 3b's disclosure).
- **V4, the roadmap builder's own NavMesh check, on all four maps:**
  - every node within 0.5 m of the AMR NavMesh;
  - a complete NavMesh path for every branch.
- **Edit Mode tests (new):**
  - the v4 Surface does not ignore NavMesh obstacles and refers to the new asset;
  - the v3 scene still refers to the v3 asset, and the v3 asset's SHA-256 is unchanged (pinned);
  - on the v4 scene, the rack centres are off the NavMesh and the path across the rack at (0, -5) goes around it.
- **Then:**
  - the Edit-mode leak test;
  - both suites;
  - the B9 list: the new asset is added to `final_v4.json` `freeze_files` (29 files) and to `FinalGuardV4Tests`. The v4 scene is
    already listed. `freeze_v4.py` reads that list and needs no change.

**What changes for the robot:** the bridge's NavMesh paths and target snaps now see the racks and pallets. A target inside or within
0.5 m of a rack snaps to the NavMesh's edge, or fails beyond 1.0 m. Every development session before this change used the old NavMesh;
from here on they differ in that respect.

**Commits:**
1. this declaration;
2. the bake tool, the new asset, the scene change, the verification tool, the tests and the B9 list;
3. the results recorded below.

Each commit is made after both suites pass.

*Amendment, 2026-11-17, after the first verification and before any further change: the stations.*
- **What happened.** The bake as declared (commit 275a9eb's plan; bake report `robot_vision/outputs/navmesh_v4_bake_20261117_051457/`)
  was verified in `robot_vision/outputs/navmesh_v4_check_20261117_052310/`.
  - V1 passed: 13,245,624 paths, none entering a footprint, all complete, every point within 0 m of the NavMesh. The negative control
    passed.
  - V4 passed.
  - **V2's hard rule failed:** 100 grid cells whose centre lies inside a footprint are on the NavMesh. **All 100 are stations.** So are
    all 276 "NavMesh looser" cells (the other 176 lie 0.2 to 0.4 m from a station).
- **Why.** The declaration assumed that baking the stations' render meshes makes them obstacles. It does not.
  - A station is a 0.70 x 0.70 m pad, 0.05 m high (y 0.08 to 0.13).
  - That is less than one voxel of the bake's height resolution, so the NavMesh runs over the pads.
  - The racks and walls are tall; they are obstacles now.
  - V1 did not see this because no modelled point or path comes near a station: all 25 stand along the south wall (z -25).
- **The added fix** (v4 scene only; the task requires the stations to be obstacles):
  - a `NavMeshModifier` on the v4 scene's `GeneratedWarehouse/Stations` group object;
  - override area "Not Walkable", applied to its children;
  - Unity bakes a Not Walkable mesh as a hole, widened by the agent radius (0.5 m), like any other obstacle.
  - Only the stations get it. The racks, pallets and walls are already obstacles through their height. The vendored station objects
    themselves stay unchanged.
- **How.**
  - The bake tool adds the modifier when it is missing.
  - The first bake was never committed. Its asset and scene change are discarded and the bake reruns from the committed scene.
  - The first verification folder is kept as the record of this failure.
- **Rules unchanged.** V1 to V4, their pass rules and the tests stay as declared. Two Edit Mode tests are added: the `Stations` modifier,
  and every station centre off the NavMesh.

*Made (2026-11-17, commits 275a9eb declaration, f2c34d9 amendment, 864106b fix).*
- **Bake** (`robot_vision/outputs/navmesh_v4_bake_20261117_052540/`, from the committed scene; Tools > Warehouse v4 > NavMesh > Bake v4
  NavMesh):
  - meshes collected: 652 before, 745 after;
  - `Shelves` 0 -> 93; `Stations` 25 walkable -> 25 Not Walkable; `Walls` 36 and the rest of `GeneratedWarehouse` 591, both unchanged.
  - New asset `Assets/Scenes/WarehouseRobot_v4/NavMesh-AMR.asset` (binary, 80,224 bytes).
  - The scene diff holds exactly three things: the modifier on `Stations`, `m_IgnoreNavMeshObstacle` 1 -> 0, and the data reference.
  - The v3 scene and the v3 asset are byte-for-byte unchanged. The tool checked this, and `NavMeshV4Tests` pins the v3 asset's
    SHA-256.
  - The first bake (`navmesh_v4_bake_20261117_051457/`, without the modifier) was discarded before any commit; its folder is kept.
- **Verification passed** (`robot_vision/outputs/navmesh_v4_check_20261117_053355/`; the failed first one, `_052310`, is kept):
  - **V1:**
    - 800 planned runs: live and pending layout, 10 settings, seeds 1 and 2, 20 runs each;
    - 5,263 points: corridor 22, turn 47, turn_left 47, roadmap 5,147;
    - all 5,263 points lie on the NavMesh (snap 0.000 m);
    - **13,245,624 paths: all complete, none entering a footprint.**
    - Least clearance to a footprint: 0.369 m at (-10.38, -4.29), a rack, in `roadmap`; 0.390 m in the other maps. 199,528 paths
      (199,503 of them in `roadmap`) come closer than the grid's 0.40 m, all at racks.
    - Reported, not judged: the NavMesh keeps 0.5 m from the racks' render meshes rounded to its 0.167 m voxels, while the footprints
      come from the racks' colliders. 0.369 m still clears the robot's half-width of 0.30 m by 0.069 m.
  - **Negative control:**
    - the three rack centres lie 1.24, 1.26 and 1.29 m from the nearest NavMesh: not reachable;
    - (6.25, -5) to (-6.25, -5) goes around the rack in 12.82 m (straight 12.50 m), with a least clearance of 0.502 m.
  - **V2:** 10,740 cells free on both, 1,310 blocked on both. 252 are free on the grid but off the NavMesh: 0.4 to 0.7 m from a rack
    (125), a wall (108) or a station (19), the expected band. 19 are blocked on the grid but on the NavMesh. **None of them lies inside
    a footprint** (the hard rule). All 19 are cells exactly 0.400 m from a station, between two neighbouring stations along the south
    wall: they sit on the grid's own 0.40 m boundary.
  - **V2, saved grid:** the Edit-mode grid equals run_001's saved Play-mode `grid.json`, cell for cell.
  - **V4:** every node of `corridor` (2), `turn` (3), `turn_left` (3) and `roadmap` (11) is on the NavMesh, and every branch path is
    complete.
- **V3, side waypoints again** (`robot_vision/outputs/navmesh_side_waypoints_20261117_053431/`):
  - 1220 of 1220 reachable, every one by a complete 1.00 m NavMesh path;
  - **negative control passed:** rack centres 1.24 to 1.29 m off the NavMesh, beyond the south wall 1.74 m;
  - the same count as item 2b's ground-truth grid check (1220/1220).
- **Leak test** (Edit mode, `robot_vision/outputs/gt_leak_check_20261117_053534/`): passed. cam360 and pan-tilt each have a max diff of
  0, with 0 pixels differing.
- **Tests:** `HRI/Tests/NavMeshV4Tests.cs`, 4 tests: the v4 Surface and its asset; the Stations modifier; the v3 asset pinned; and on the
  v4 NavMesh every rack and station centre off it and the path around the rack at (0, -5). `FinalGuardV4Tests` expects the new asset.
- **B9:** `final_v4.json` `freeze_files` has the new asset, 29 files. `freeze_v4.py` reads that list unchanged.
- **Suites:** Python 1163 OK (2 skipped), Unity Edit Mode 339/339.
- **Not done:** no Play-mode session on the new NavMesh yet. The bridge paths at Play have not been observed; the step-5 rerun will be
  the first.

### 2026-11-17, section 15 addendum 3: the layout with the controller's re-ask shift, three workers at J1, the slot table, Anisha's question (declared before any change below)

Nusrat's task of 2026-11-17. Branch `nusrat/v4-layout-2` = `main` 29510ff (PR #41, Anisha's step-5 fixes) with `nusrat/v4-step5-dev`
(0ee553a: addenda 1 and 2, the NavMesh fix) merged in, because that branch is not on `main` yet. Nothing under `robot_vision/`, `docs/` or
`external/` changes; nothing is frozen, no final is run, nothing is pushed; `clearance_layout` stays `"active": false`. Development work,
not a result.

**Already done before this declaration (read only; no tracked file changed):** item 4's replay of the step-5 logs. It touches no layout
value and shaped nothing in items 1 to 3; it is recorded with its result under item 4.

**Item 1, the clearance search with the controller's real re-ask shift.**
- **The correction.** Item 3b's ask-position model took `reask_shift_m` 0.4 m from v3's `hri_control.json` `dialog`. The v4 controller
  uses **0.8 m**: `configs/v4/control.json` `dialog.reask_shift_m`, merged over the v3 dialog by `hri_control_v4.load_control` (the
  step-5 sessions ran with 0.8 m, `config_used/control_lie_*.json`). Unity's copy in `experiments_ab_unity.json` becomes 0.8, its note
  names `configs/v4/control.json`, and an Edit Mode test pins the copy to that file. The copy is used only by the clearance model and by
  the NavMesh verification's point set; nothing at Play changes while the block is inactive.
- **Rules unchanged** (item 3b as built, `ExperimentPlanAB.NodeProblem` / `ClearanceProblem`):
  - no worker within **1.0 m** of a drivable segment: every road of the run's map and of the physical v4 map; per asking node, from the
    node to the ask position of each of its workers in every order, with the return to the first (tie); from every ask position and
    re-ask point to the next node of every branch of the node;
  - ask position = 2.0 m from the worker toward where the robot comes from; re-ask point = 0.8 m to the robot's right, back on the
    2.0 m circle; every ask position and re-ask point within 5.5 m of its node (zone 6.0 m minus margin 0.5 m);
  - workers at least 3.0 m apart and 3.0 m from every asking node of the run's map and of the physical map; bystander margin 1.0 m over
    the last 3.0 m of the arrival road (beside) or 0.25 m (random); `min_road_m` 1.0 (random); at most 6 active avatars (8.0 m); the
    worker's cell free on the ground-truth grid.
- **The clearance value is not changed.** Item 3b's reason read "0.6 m corridor + 0.4 m (the re-ask shift, ...)", written with the v3
  shift. With 0.8 m the same sum is **1.4 m**; that would be a rule change and is not made here. The search also runs at 1.4 m and is
  **reported only** (does a layout exist, and its first choice), for Nusrat and Anisha to decide.
- **The new NavMesh.** Addendum 2 did not change the ground-truth grid (V2: the Edit-mode grid equals the saved Play grid cell for cell),
  so the worker cells are checked on it as before. **Added requirement, new here:** every modelled ask position and re-ask point lies in
  a cell that is on the new AMR NavMesh, by V2's cell classification in `navmesh_v4_check_20261117_053355/` (grid-free cells minus
  `grid_free_navmesh_off`, plus `grid_blocked_navmesh_on`). The report says whether it changes the choice. The chosen layout is then
  verified on the real NavMesh with addendum 2's tool (V1 to V4, rules unchanged; its point set takes the shift from the config).
- **The search** (as item 3b's, now a committed tool `finals_v4/layout_search_v4.py`, a Python port of the Unity model; it reads the
  config and map files, the saved grid and the V2 classification, and no trial result):
  - slot candidates: `before_m` -8.0 to 10.0 and `right_m` -4.5 to 4.5 in 0.5 m steps, at least 3.0 m from the node;
  - pairs (slots 1 and 2) with 2 workers at every asking node of `corridor`, `turn`, `turn_left` and `roadmap`; then slot 3 with 3 at J1
    of `roadmap`; each set checked on all maps together;
  - start slots unchanged; if they break a rule, the start slots are searched over the same candidates by the same choice rule, reported;
  - **choice rule unchanged:** meets every rule; then the smallest largest own-ask distance; then the least movement from the section 3
    slots (sum of the slot shifts).
- **Checks of the choice:** `ExperimentClearanceTests` with the new block (every plan of seeds 1 and 2, 20 runs, of the 10 Unity
  settings; the independent re-check reads the standoff and the shift from the config instead of fixed numbers); then the NavMesh
  verification. The block stays inactive.

**Item 2, three workers at J1 in A4 and B4** (random layout, scenario 4: a 6 m square around the node, `half_size_m` 3.0). With 2 at J1 a
single lie in B4 is a tie; 3 give a majority. Every rule of item 1 for the random layout applies.
- **Existence:** every triple of points of a 0.25 m lattice over J1's square, ordered by distance to J1 as Unity sorts a draw, checked
  against J1's rules (roads, its own segments, separation, turning points, bystander margin, ask zone, free cell, the NavMesh requirement).
  Reported: the number of valid triples, and the acceptance rate of Unity's draw estimated from them (valid ordered triples / all
  ordered lattice triples), with the chance that 100,000 draws (`random_max_draws`) all fail.
- **Practical:** with the block applied and A4 and B4 given 3 at J1, Unity's own planner for every run of seeds 1 and 2.
- **If no triple exists, or Unity cannot plan every run,** it is reported as impossible under the rules, with:
  - **the binding constraint(s):** which single rule, when dropped alone, lets lattice triples pass (and how many); and the closest
    triple (the largest smallest margin to any rule) with the rule it breaks and by how much;
  - **the closest alternatives, each under every other rule, none switched on:**
    - (a) the third worker at item 1's slot 3, a fixed spot on the other side of the road, and two random in the square;
    - (b) a smaller clearance for one worker only: the largest value (0.05 m steps) at which a valid triple exists, the other two keeping
      1.0 m from everything;
    - (c) a larger square: the smallest `half_size_m` (0.5 m steps, up to 5.0) at which the estimated acceptance rate leaves less than a
      1 in 1,000 chance that 100,000 draws all fail;
  - A4 and B4 then stay with 2 at J1 in the pending block. A3 and B3 (beside) keep 3 at J1 through item 1's slot 3.

**Item 3, the slot table for Anisha** (her `scenarios_ab.json`; nothing of hers changes here). For the chosen layout, and for the 1.4 m
report: per scenario (1 `corridor`; 2 `turn` and `turn_left`; 3 `roadmap`), per asking node and worker: slot, `before_m` / `right_m`,
world position, distance to its node, and the largest own-ask distance. Scenario 4: the random rule (square, margins, `people_by_node`).
Also for her `second_opinion_radius_m` (6.5 m, waiting for the largest placement distance, AUDIT.md 16.19.3 D): the largest
worker-to-node distance and whether every worker's nearest node of the v4 map is its own node. Written to a new output folder and here.

**Item 4, Anisha's question (report only).** The diagnosis said: "whenever STOP fires, the reader returns before evaluating PROCEED,
restarting the 0.5 s PROCEED hold". Asked: the exact file, function and line in her reader and in the dialog code path, and a replayed
example showing the restart; if it cannot be shown, it is withdrawn.
- **Method (already run, read only):** the live dialog class `hri_control.GestureDialog` replayed on the frames the dialog saw in every
  ask of the 8 step-5 sessions (the `v4_log.jsonl` rows, which `_log_frame` writes only inside `_read_tick`), with each session's
  `config_used` values, under three models: S, the code as written (a frame read STOP is never given to the dialog); R1, the claim (a
  STOP frame restarts the hold); R2, a STOP frame given to the dialog as a no-direction reading (the change Anisha tried, AUDIT.md
  16.19.3). STOP frames are the `decisions.csv` rows "STOP gesture" in the read state. Each model's acceptance is compared with the
  logged one. The tool becomes `finals_v4/replay_dialog_hold.py`.

**Commits:** (1) this declaration; (2) the search tool, the config copy, the block and the tests; (3) the results and the slot table;
(4) item 4's tool and record. Each after both suites pass.

*Amendment, 2026-11-17, after the first search run and before anything further is computed: no beside layout with three workers at J1.*
- **What happened** (`finals_v4/layout_search_v4.py`, run `robot_vision/outputs/layout_search_v4_20261117_202249/`, uncommitted tool on 1e56271):
  - addendum 1's pending slots fail with the 0.8 m shift: at J1 of `roadmap` an ask point lies beyond 5.5 m (the ask zone);
  - **no slot set with 3 workers at J1 meets every rule**: 0 at 1.0 m with the NavMesh requirement, 0 at 1.0 m without it, 0 at the
    report-only 1.4 m. The start slots pass unchanged; 2989 slot pairs pass on `corridor`, `turn` and `turn_left` (1.0 m, NavMesh);
  - item 2's lattice: 0 valid triples at J1 (its declared analysis continues in the same run);
  - the port was checked first against addendum 1: with the 0.4 m shift and no NavMesh requirement it returns addendum 1's choice
    (3.5 / -2.5, -4.5 / 3.5, -5.0 / -4.0; largest own-ask distance 5.193 m) as the first of 10 valid sets.
  - A diagnostic script was started and stopped before it printed anything; no result of it was seen.
- **So item 1 has no choice under the declared rules.** Added now, the same treatment as declared for item 2 (nothing is chosen, nothing
  is switched on; the pending block keeps addendum 1's slots, marked as failing at 0.8 m):
  - **binding rule(s) at J1** (3 beside workers, A's workers placed, the 1.0 m clearance and the NavMesh requirement): over every slot
    triple whose slots 1 and 2 are one of the 2989 valid pairs and whose three J1 positions are 3.0 m apart, the set of rules each
    triple breaks, and the number of triples valid when one rule alone is dropped;
  - **the closest alternatives, each checked on every map under every other rule:**
    - (i) 2 workers at J1 in A3 and B3 too: the first pair by the declared choice rule (all four maps, 2 per asking node);
    - (ii) a larger ask zone: the smallest largest own-ask distance of a 3-at-J1 set valid with the zone rule dropped, and the zone
      radius it needs (that distance + the 0.5 m margin), against 6.25 m (beyond it two zones overlap: 12.5 m / 2);
    - (iii) a smaller clearance for slot 3 only: the largest value (0.05 m steps) at which a set exists whose other workers keep 1.0 m
      from every drive and road.
  - Committed as `finals_v4/layout_search_v4_j1.py` (it imports the search tool's model).

*Items 1 to 3, made (2026-11-17). Nothing is chosen or switched on: under the declared rules there is no layout to choose.*
- **Tools** (`finals_v4/`, inputs in `layout_search_v4.json`; geometry only):
  - `layout_search_v4.py`, the search (a Python port of Unity's placement model);
  - `layout_search_v4_j1.py`, the amendment's analysis;
  - `layout_alternatives_v4.py`, the slot tables and item 2's alternative (a).
  - The search run used the tool before one refactor (the pair stage moved into `beside_pairs` for the J1 script, same code); it was not
    rerun (45 min).
- **Port check:** with the 0.4 m shift and no NavMesh requirement the port returns addendum 1's choice first (largest own-ask distance
  5.193 m).
- **The correction:** `experiments_ab_unity.json` `reask_shift_m` 0.4 -> 0.8. Its note names `configs/v4/control.json`, and
  `ExperimentClearanceTests.ReaskShift_IsTheV4ControllersValue` pins it to that file.

**Item 1** (`robot_vision/outputs/layout_search_v4_20261117_202249/`, `layout_search_v4_j1_20261117_204024/`):
- **Search space:** 594 slot candidates; 404 pass roads, turning points and free cells at every junction; 2989 pairs pass `corridor`,
  `turn` and `turn_left` (1.0 m, NavMesh requirement). The start slots pass unchanged.
- **No slot set with 3 workers at J1 meets every rule:** 0 at 1.0 m with the NavMesh requirement, 0 without it, 0 at the report-only
  1.4 m. The NavMesh requirement changes nothing: there is no choice either way.
- **Addendum 1's pending slots fail with 0.8 m:**
  - 3 at J1: an ask position 5.51 m from J1 (Unity: A3 seed 1 run 1);
  - 2 at J1 on `roadmap`: slot 2 (4.5 m ahead, 3.5 m right) stands 0.84 m from J1's drive at the closest (Unity's first find:
    0.85 m, from the line "ask position (9.22, 2.57) to E1").
  - With 2 at J1 they still plan every A1, A2, A4, B1, B2, B4 run (Unity test). A4 and B4 are random, so their junction slots are not
    used there.
- **The binding rule, at J1** (864,782 triples: slots 1 and 2 a valid pair, the J1 positions 3.0 m apart, A's workers placed):
  - **every triple breaks "worker clearance from J1's own drive"**. Dropping that rule alone leaves 103,212 valid at J1. Dropping any
    other single rule leaves 0: ask zone, bystander margin, NavMesh requirement, clearance from A's drive.
  - Most frequent sets of broken rules: own drive + ask zone 283,305; own drive + bystander margin 270,923; own drive alone 103,212.
  - The four clearance rules dropped together leave 111,725.
- **Closest alternatives** (none chosen):

| alternative | result | what it costs |
|---|---|---|
| (i) 2 workers at J1 in A3 and B3 too | 215 pairs valid on every map. First by the declared choice rule: slot 1 = 3.0 m before, 2.0 m left (the live slot 1); slot 2 = 2.5 m ahead, 4.0 m right; largest own-ask distance 4.06 m. **Unity's planner: all 400 plans of seeds 1 and 2 pass every rule** (`Addendum3_TwoAtJ1_AlternativeIPlans_...`) | B3, like B4, has no majority at J1: one lie is a tie |
| (ii) a larger ask zone | 0 sets even with the zone rule dropped | does not help |
| (iii) a smaller clearance for slot 3 only | largest **0.631 m (0.60 m in 0.05 m steps)**: slot 1 = 3.5 m before, 2.5 m left; slot 2 = 4.0 m ahead, 4.0 m right; slot 3 = 4.5 m ahead, 3.0 m left (3.25, 4.50); largest own-ask distance 4.73 m; every other worker at least 1.0 m | 0.63 m is barely above Python's person-in-path corridor half-width (0.6 m): the robot on that line passes the worker at the edge of its stop corridor. Not checked at Play |

**Item 2, three random workers at J1** (A4 and B4, the 6 m square):
- **Lattice:** 625 points, 160 pass the point rules, 247,360 triples keep the separation, **0 valid**.
  - Binding rule: the clearance from J1's own drive. Dropping it alone leaves 29,388 valid; dropping the separation alone 1,226; any
    other single rule 0.
  - Broken sets: bystander margin + own drive 217,972; own drive alone 29,388.
  - The closest triple, (7.25, -3.00), (9.25, 1.75), (4.25, -3.00), misses the clearance by 0.124 m (0.876 m).
- **Unity's planner:** every run of seeds 1 and 2 of A4 and B4 with 3 at J1 is refused at J1 ("no placement within 100000 draws").
  Pinned by `ThreeRandomWorkersAtJ1_InA4AndB4_CannotBePlaced`.
- **Alternatives** (none switched on):
  - **(a) a third worker fixed on the other side of the road, two random:** 0 of 2,000,000 draws accepted, both for the pending slot 3
    (2.25, 5.00) and for (iii)'s slot 3 (3.25, 4.50). Item 1 has no slot 3 of its own, so these two stand in for it.
    (`robot_vision/outputs/layout_alternatives_v4_20261117_211023/`)
  - **(b) one worker closer to J1's drive:** at most 0.215 m (0.20 m in steps). That worker would stand inside the 0.6 m stop corridor of
    a drive line, so this is not usable.
  - **(c) a larger square:** half size 3.0 to 4.5 m, 0 of 2,000,000 draws each; 5.0 m, 1 of 2,000,000 (rate 5e-7, so 100,000 draws all
    fail with a chance of 0.95). No size up to 5.0 m works.
  - So with the 1.0 m clearance and the 0.8 m shift, three random workers at J1 cannot be placed. A4 and B4 stay with 2 at J1 in the
    pending block.
  - The only 3-at-J1 placement found anywhere is (iii), a fixed beside layout with slot 3 at 0.60 m. Using it for A4 and B4 too would
    change Anisha's random layout of scenario 4.

**Item 3, the slot tables** (`layout_alternatives_v4_20261117_211023/slot_table.csv`: candidates P = the pending block with 2 at J1, (i)
and (iii); per scenario, node and worker). The two usable candidates on the v4 map; the start slots are unchanged in both:

(i), 2 at J1 in every setting:

| node | slot | before_m | right_m | x, z | to node (m) | own-ask max (m) | clearance (m) |
|---|---|---|---|---|---|---|---|
| A | 1 | 3.0 | -2.0 | 4.25, -23.00 | 3.61 | 4.06 | 2.00 |
| A | 2 | 3.0 | 4.0 | 10.25, -23.00 | 5.00 | 4.06 | 1.97 |
| J1 | 1 | 3.0 | -2.0 | 4.25, -3.00 | 3.61 | 3.18 | 1.57 |
| J1 | 2 | -2.5 | 4.0 | 10.25, 2.50 | 4.72 | 3.18 | 1.17 |
| J2 | 1 | 3.0 | -2.0 | -3.25, -2.00 | 3.61 | 3.18 | 1.58 |
| J2 | 2 | -2.5 | 4.0 | -8.75, 4.00 | 4.72 | 3.18 | 1.19 |
| J3 | 1 | 3.0 | -2.0 | 15.75, 2.00 | 3.61 | 3.18 | 1.50 |
| J3 | 2 | -2.5 | 4.0 | 21.25, -4.00 | 4.72 | 3.18 | 1.19 |
| J4 | 1 | 3.0 | -2.0 | -15.75, -2.00 | 3.61 | 3.18 | 1.50 |
| J4 | 2 | -2.5 | 4.0 | -21.25, 4.00 | 4.72 | 3.18 | 1.19 |

(iii), 3 at J1 in A3 and B3, slot 3 relaxed:

| node | slot | before_m | right_m | x, z | to node (m) | own-ask max (m) | clearance (m) |
|---|---|---|---|---|---|---|---|
| J1 | 1 | 3.5 | -2.5 | 3.75, -3.50 | 4.30 | 4.73 | 1.73 |
| J1 | 2 | -4.0 | 4.0 | 10.25, 4.00 | 5.66 | 4.73 | 1.01 |
| J1 | 3 | -4.5 | -3.0 | 3.25, 4.50 | 5.41 | 4.73 | 0.63 (relaxed) |
| J2 | 1 / 2 | 3.5 / -4.0 | -2.5 / 4.0 | -2.75, -2.50 / -10.25, 4.00 | 4.30 / 5.66 | 3.95 | 1.86 / 1.21 |
| J3 | 1 / 2 | 3.5 / -4.0 | -2.5 / 4.0 | 15.25, 2.50 / 22.75, -4.00 | 4.30 / 5.66 | 3.95 | 1.22 / 1.61 |
| J4 | 1 / 2 | 3.5 / -4.0 | -2.5 / 4.0 | -15.25, -2.50 / -22.75, 4.00 | 4.30 / 5.66 | 3.95 | 1.65 / 1.61 |

- `turn` and `turn_left` (B) use the same junction slots, and `corridor` only the start slots. Every one of those rows passes; the
  values are in the CSV.
- **For Anisha's `second_opinion_radius_m` (6.5 m):** the largest worker-to-node distance is 5.00 m in (i), 5.66 m in (iii) and 5.70 m
  in P. Every worker's nearest node of its map is its own node in all three, so 6.5 m keeps every worker of every candidate.
- **Scenario 4:** the random rule stays as it is (6 m square, bystander margin 0.25 m, `min_road_m` 1.0), with **2** at J1
  (`people_by_node` J1 3 cannot be met; item 2).
- **Not run:** the NavMesh verification (addendum 2's tool). There is no chosen layout, and the tool stops at the first plan the
  pending layout refuses (A3). It will run once a layout is decided.

*Item 4, Anisha's question, answered (2026-11-17): the claim is WITHDRAWN.* "Whenever STOP fires, the reader returns before
evaluating PROCEED, restarting the 0.5 s PROCEED hold": the first half is true; the second half is not, in the code or in the logs.
- **The code path** (8848a7a, the code of the step-5 runs; line numbers on `main` 29510ff in brackets):
  - the reader, `robot_vision/gesture_motion.py`, `read_window`. STOP is decided first (line 636 [660]) and returns at line 649 [673],
    before the PROCEED block at line 650 [674]. **True:** a frame that passes the STOP rule is read STOP, never PROCEED.
  - the controller, `robot_vision/hri_control_v4.py`, `ControllerV4.step` (line 867 [939]): a STOP reading of anybody sets
    `inp.gesture` STOP (lines 871-872 [948-949]), then calls `super().step` (line 873 [950]);
  - `robot_vision/hri_control.py`, `Controller.step` (unchanged since v3): `_safety` returns "STOP gesture" (line 356), and `step` returns
    at line 391 **before `self._tick` (line 393)**. So `ControllerV4._read_tick` and its `self.dialog.update(...)` (line 812 [884]) never
    see that frame;
  - `hri_control.GestureDialog.update` (lines 172-184) restarts the hold only for (a) a different direction, or (b) a no-direction
    reading more than `max_none_gap_s` 0.3 s after the candidate was last seen. A frame it never receives restarts nothing: `since`
    stays where it was.
  - One more path, found in the replay: the safety stop leaves `last_persons_frame` unchanged. When the STOP frame has gone stale
    (`gesture_stale_s` 0.5 s), the next tick gives that same frame to the dialog as a NONE reading, and rule (b) decides. Example below:
    frame 11.676 s, a STOP stop at 12.113 s, then NONE at 12.204 s, 0.11 s after the last FORWARD, so no restart.
- **The replay** (`finals_v4/replay_dialog_hold.py`, `robot_vision/outputs/replay_dialog_hold_20261117_202338/`): 97 asks of the 8
  step-5 sessions; 45 accepted in the log; 49 with STOP frames.

| model | asks matching the logged outcome | accepted asks at the logged time |
|---|---|---|
| S, the code as written (STOP frames never reach the dialog) | **97/97** | **45/45** |
| R1, the claim (a STOP frame restarts the hold) | 77/97 | 25/45 |
| R2, STOP frames given to the dialog as no-direction readings | 95/97 | 43/45 |

- **20 accepted asks had a STOP frame inside the accepted 0.5 s hold** (hold start < STOP frame < accepting frame). In every one the
  dialog accepted at the logged time, as if the STOP frame were not there. Under the claim none of the 20 would have been accepted in
  that ask. First example, A1 trial 1 at A (ask 9.386 s):

| frame t (s) | controller t (s) | reaches the dialog | label |
|---|---|---|---|
| 11.078 | 11.385 | yes | NONE |
| 11.178 | 11.593 | no (safety stop: STOP gesture) | STOP |
| 11.385 | 11.676 | yes | FORWARD: the hold starts |
| 11.565 | 11.926 | yes | FORWARD |
| 11.676 | 12.113 | no (safety stop: STOP gesture) | STOP |
| 11.676 | 12.204 | yes (the same frame, now stale) | NONE |
| 11.839 | 12.271 | yes | FORWARD |
| 12.088 | 12.380 | yes | FORWARD: accepted, 0.703 s after the hold started (logged 12.38 s) |

- **What a STOP does cost** (not a restart):
  - a frame read STOP is a frame not read PROCEED (the reader's early return);
  - the robot is stopped while STOP holds;
  - the 5 s ask window keeps running.
  - This agrees with AUDIT.md 16.19.3 (Anisha could not reproduce it) and 16.19.4 item 5 (feeding the STOP frames removes no abort).

### 2026-11-18, section 15 addendum 4: layout (i) switched on after Anisha's PR #42 (declared before any change below)

Nusrat's task of 2026-11-18. Branch `nusrat/v4-layout-2` (cd2fbc9). Its PR checks failed only in combination with `main`; the push
checks passed. Nothing under `robot_vision/`, `docs/` or `external/` is edited here (the merge brings `main`'s versions unchanged);
nothing is frozen, no final or Play session is run, nothing is pushed. Development work, not a result.

**What the merge showed** (`origin/main` 1e89dcd, PR #42 `anisha/v4-clearance-layout`, AUDIT.md 16.21.2-16.21.3, merged without a
commit and aborted after both suites ran; no tracked file was changed):
- Anisha's `scenarios_ab.json` now carries alternative (i) of addendum 3: junction slots (3.0, -2.0) and (-2.5, 4.0), two workers at
  every node (`people_by_node` removed from scenarios 3 and 4), `placement_rule` with `path_clearance_m` 1.0, `ask_zone_m` 5.5,
  `ask_standoff_m` 2.0, `reask_shift_m` 0.8.
- Python suite on the merged tree: 1284 tests, **2 failures**, 9 skipped. Both are her pins on Unity's block, which still holds addendum
  1's slots (3.5, -2.5), (-4.5, 3.5):
  - `test_clearance_layout_v4.TheLayout.test_unitys_values_agree_whenever_the_file_carries_them`;
  - `test_lie_detection_v4.MatchesUnity.test_the_slots_and_margins_are_unitys` (and, once the block is active, it also requires
    Unity's live `junction_slots` to equal the two slots exactly).
- Unity Edit Mode suite on the merged tree: 342/342.

**Decision (Nusrat, 2026-11-18):** alternative (i) of addendum 3, as in Anisha's file: two workers at every asking node in every setting
(A3, B3, A4, B4 included); slot 1 3.0 m before and 2.0 m left, slot 2 2.5 m ahead and 4.0 m right; start slots unchanged; the
clearance (1.0 m) and ask-zone (5.5 m) checks on at Play. Values from addendum 3's slot table
(`layout_alternatives_v4_20261117_211023/slot_table.csv`), equal to her `scenarios_ab.json` (16.21.2).

**The change, in one step** (as the block's note says: active becomes true and the live values are replaced):
- `experiments_ab_unity.json`: `clearance_layout.active` true; `clearance_layout.junction_slots` = the two (i) slots;
  `clearance_layout.two_worker_experiments` = A3, B3, A4, B4; live `junction_slots` = the same two slots; `three_worker_nodes` of A3,
  A4, B3, B4 = []; the notes say so. Every other value (start slots, margins, zone, clearance, shift, activation) is unchanged.
- `ExperimentsUnityConfig.Validate` requires 3 junction slots in both places; (i) has 2. The check becomes: at least 2 junction slots,
  3 where an experiment keeps a third worker (live: any `three_worker_nodes`; block: any outside `two_worker_experiments`). Start slots
  keep 3. No planner, rule or Play behaviour changes beyond the switch.
- Edit Mode tests that pinned the block as inactive, or the section 3 / addendum 1 slots as live, are rewritten to pin (i) active and
  every plan of seeds 1 and 2 of the 10 Unity settings under every rule. The earlier findings stay pinned with their slots written in
  the tests: the section 3 slots refused under the clearance (A3 run 2 geometry); addendum 1's slots failing at 0.8 m (three at J1:
  ask zone; two at J1 on `roadmap`: 0.84 m); three random workers at J1 cannot be placed.

**Disclosed consequences:**
- B3 and B4 have no majority at J1: one lie by two workers is a tie (as Anisha records in 16.21.2; she re-asks the first worker).
- The layout tools `finals_v4/layout_search_v4.py` and `layout_search_v4_j1.py` read Unity's live and block slots as their baseline
  ("least movement from the section 3 slots"). A rerun after this change takes (i) as that baseline; their committed outputs of
  2026-11-17 stay the record. They are not changed here.
- Not run here: addendum 2's NavMesh verification of the chosen layout (an Editor menu run), any Play session.

**Commits:** (1) this declaration, before the merge; (2) the merge of `origin/main` with the switch, the `Validate` change and the tests
(the merge alone fails her two pins, so the switch goes into the merge commit). Each after both suites pass.

### 2026-11-20, section 15 addendum 8: checkpoint workers dropped, the T0-ready branch, the development timeout 900 s (declared before any change below)

Nusrat's task of 2026-11-20 after Anisha's decision (AUDIT.md 16.26.9, on main 33cab20). Branch `nusrat/v4-t0-ready`, new from `origin/main`
33cab20. Unity side and `finals_v4/` only: nothing under `robot_vision/`, `docs/` or `external/` changes; nothing is frozen, no final is run,
nothing is pushed. **Development data, not a result.** Numbering: addenda 5 to 7 of this section exist only on the unmerged branch
`nusrat/v4-timing-backtrack` (pushed up to 7c5adc6; 683b5bc local); they are summarised below and not merged.

**1. The record: checkpoint workers were built, diagnosed and dropped.**
- **Built and diagnosed on `nusrat/v4-timing-backtrack`** (not merged): addendum 5 (3ead71b, 8acd539: NavMesh check of layout (i), the
  strict-protocol timing rerun declared (not run), facts for a backtracking design); addendum 6 (be1a08f, 7d8ab30, 7c5adc6: variant T4, seven
  fixed checkpoint workers beside the decision branches, an answer rule, `-experimentForceLie`, Verify points, 12 Edit Mode tests); addendum 7
  (683b5bc: the abeam checkpoint ask, the side-view re-ask, a readability threshold, the BACK diagnosis tool). Uncommitted work after 683b5bc
  (the abeam and side-view planner, a recorder and scorer of BACK readability, a truth `role` field) was never committed; it is kept in a
  local `git stash` of that branch, not here.
- **Unity's diagnosis numbers (development, not results):**
  - addendum 6 checks on 7d8ab30: every run of seeds 1 and 2 of the 10 Unity settings planned; NavMesh Verify PASSED
    (`navmesh_v4_check_20261118_235705`); worker and checkpoint path check PASSED (`checkpoint_check_20261118_235303`: 400 plans, 48,270 paths,
    none within 1.0 m of a worker); pan-tilt never 3 or more people at an ask.
  - B3 smoke trial (`trials_development_Task2_B3_20261118_235842` / `bridge_guide_20261118_235726`, forced liar at J1): REHEARSAL VALID; the
    robot followed the lie at J1; at J3 the honest worker 7 pointed BACK twice and was read NONE both times; aborted at J3 at 213.8 s.
  - BACK diagnosis (`back_read_diagnosis_20261119_203250`, `finals_v4/back_read_diagnosis_v4.py`; replay equals the log in 37 of 37
    readings): the arm pointed 144.8 and 163.5 deg from the worker-to-camera line; POINT cue in 0 of 19 and 0 of 18 raised frames (image arm
    length median 0.78 and 0.36 shoulder widths, needs 0.8); the logged stage was `insufficient_history` (the pan-tilt at 4.35 to 4.40 frames/s
    with two people in its frame, 4 to 5 frames in the 1.0 s window, 6 needed). Development POINT asks by angle to the camera line: 45-135 deg
    33 asks, 27 read as POINT, 20 with the correct direction; 135-180 deg 6 asks, 0 read; below 30 deg 1 ask, 0 read.
  - After 683b5bc (uncommitted code, recorded for completeness): the side view as first declared failed Unity's planning rules (Edit Mode
    341/364; diagnostic `side_view_diag_20261119_214424`: 0 of 400 runs planned with the Edit Mode check, 240 of 400 with Play's); only "J2 and
    J4, back to the first ask point" planned 400 of 400 (`side_view_diag_20261119_215510`). A BACK readability recording
    (`back_readability_20261119_215631`, 156 asks, development looks and clips) scored 7 of 26 spots passing at 10 Hz
    (`back_readability_report_20261119_221613`: the 7 checkpoint FORWARD spots; all 19 BACK spots failed; at 4.4 frames/s every spot
    failed). At J3 and J4 the mirror image of a BACK reading lands 13.8 or 22.6 deg from LEFT or RIGHT, inside `branch_match_max_deg` 30, so
    `resolve_point` returns ambiguous (`mirror_ambiguity_20261120_124936`, ideal reading).
- **Dropped on 2026-11-20 by Anisha's declared stopping rule (AUDIT.md 16.24; 16.26.8.1, 16.26.9).** Simulator: T4 without the side view on
  fresh seeds 101 to 140, 900 s: B3 on 24/40 -> 24/40 (+0.0 pp), B4 on 23/40 -> 23/40 (+0.0 pp), bar +15 pp: FAIL. With the side view
  (16.26.7) the runs stalled: A2 on (no checkpoints) fell from 40/40 to 0/40 and 1/40 by timeouts at 900 s; B3 on -30.0 and -37.5 pp. T0 is
  kept for the finals; her guard refuses any checkpoint key on and `side_view.enabled` true.
- **The final scenes contain no checkpoint workers.** This branch starts from main, where Unity never had them (none of the commits above is
  merged); item 3 proves it.

**2. What comes over from `nusrat/v4-timing-backtrack`, and nothing else.**
- (b) `finals_v4/back_read_diagnosis_v4.py` (from 683b5bc, unchanged: a diagnosis tool of the B3 smoke trial; it reads that trial and the
  checkpoint-era planner export, and changes nothing) and a copy of its report `Avatar/Config/reports_v4/back_read_diagnosis_20261119_203250.md`.
- (c) Tooling useful without checkpoints:
  - `finals_v4/timing_rerun_report.py` (from 8acd539: frames per 2 s window by 1, 2, 3+ people in the frame, overall and in gesture windows;
    perception and round-trip timing), generalised: `--prefix P` takes the manifest entries whose setting starts with P (default `timing_`,
    the old behaviour); its own zip is left as it was (inside `robot_vision/outputs/`).
  - `finals_v4/step5_report.py`: `--prefix P` takes only the manifest entries whose setting is P + one of the 13 final setting names (no
    prefix: the old behaviour, every entry); the prefix is dropped to pair a B setting with its A partner (`t0_B3` with `t0_A3`). Output
    files carry the prefix in their name. Its per-run CSV (`step5_durations_<time>.csv`) already lists outcome, failure reason and duration;
    that is the input of the timeout rule (item 5); the tool computes no timeout.
  - New `finals_v4/step5_zip_v4.py`: ONE zip, OUTSIDE the repository (a folder given on the command line; refused inside the repository),
    of every session of the manifest with the prefix (Unity session folder, bridge run folder, export folder, launcher transcript, the
    launcher's `run_session_*` logs and run-protocol notes of each setting) plus the analysis outputs named on the command line; a
    `MANIFEST.json` inside (every file, size, SHA-256); `zipfile.testzip` after writing; prints the zip's SHA-256 and writes it next to the
    zip (`<zip>.sha256`). Never overwrites. Read-only on the outputs.
  - Not taken (checkpoint-only): `checkpoint_feasibility_v4.py`, `checkpoint_layout_report_v4.py`, the T4 planner, its tests, the launcher's
    `-ExperimentForceLie`, the `t4_` handling of `step5_report.py`, the side-view and readability tools.

**3. Checks that no checkpoint trace remains** (on this branch, before and after the changes):
- search, case-insensitive, all Unity files (scripts, tests, configs, scenes, prefabs, assets), `final_v4.json` (freeze list and settings),
  `experiments_ab_unity.json`, the 13 session configs, the launcher and `finals_v4/`, for `checkpoint`, `side_view` / `side view`, `abeam`,
  `force_lie` / `ForceLie`, `t4_` and the seven checkpoint worker positions of addendum 6 (e.g. `2.25, 15.5`, `12.25, -4.0`); and in the
  plans of the placement check below, no worker off an asking node and no worker id above 2 x the asking nodes (the checkpoint era had ids
  11 to 17 in A3 / B3). **Allowed and listed, not removed:** v3 Task 1 route checkpoints (`Task1Route`, `TrialRunner`,
  `GroundTruthLayer`: C1 to C3 of v3, a different thing, frozen v3), the historical text of this file, and `back_read_diagnosis_v4.py` with
  its report (item 2 (b)). Anything else found is removed after a dated note here, before the removal.
- **Placement identical to main's layout (i):** the temporary worker path check of addendum 5 (`TempWorkerPathCheck`, source in
  `worker_path_check_20261118_214612/`, run on a3fc543 whose `unity/` equals main's) is run again on this branch (copied in, run in batch
  mode, deleted with its `.meta`, source copied to its output). Pass: its 400 plans (10 settings x seeds 1 and 2 x runs 1 to 20, which
  contain seed 1 runs 1 to 3 and seed 2 runs 1 to 20) equal the reference `plans.json` in setting, seed, run, map, goal, max_active and every
  worker's id, node, slot, x and z (within 0.0001 m); every path complete, outside every footprint, none within 0.30 m of a worker (as
  addendum 5); max active avatars <= 6.
- **NavMesh Verify** (`NavMeshV4Menu.BatchVerify`, addendum 2's rules V1 to V4): PASSED.
- **Freeze list:** every `final_v4.json` `freeze_files` entry exists; every setting's experiment config exists, names an existing control
  file and passes Anisha's `final_guard_v4.control_problems` (no problem).

**4. The development timeout for step 5: 900 s** (Anisha's request; at least 420 s so long routes count). `Scenario/Config/trial_plan_v4.json`
`development_timeout_s` 420 -> 900 (the only place: TrialRunnerV4 reads it in development mode, the launcher sets the per-run timeout and its
Unity wait (runs x 900 + 1800 s) from it, `step5_session_checks.ps1` records it as `timeout_s`); its note says why. Development mode only:
`final_plan.json` `timeout_s` (Anisha's) is not touched and **the final timeout is not set here.**

**5. Open item (pending Anisha's confirmation in AUDIT.md): how the final timeout rule treats development runs that time out or abort.**
Her declared rule (AUDIT.md 16.15 decision 2, 16.16 decision 4; `final_guard_v4.development_timeout`): 1.5 x the longest SUCCESSFUL
development run, rounded up to 30 s, never below 270 s; every run that failed by timeout is listed and its cause must be found before the
freeze; other failures (aborts, collisions) give no duration. **Nusrat's proposal:** the longest SUCCESSFUL development run of the step-5 runs
at 900 s; a run that timed out or aborted gives no duration. Not applied until Anisha confirms in AUDIT.md.

**6. Checks before the commit and before the smoke trial:** both full suites (Unity Edit Mode; Python, including her `MatchesUnity` and guard
tests); item 3; `run_session_v4.ps1 -Rehearsal -Trials 3 -DryRun` for all 13 settings (the step-5 arguments; the printed timeout must be 900 s);
dry checks of the blind avatar rehearsal (the entry points `LookCheckMenu.BatchRunExperiment` and `LookCheckPlayMenu.CommandLineRunAB` exist;
`avatar_rehearsal_check.py --help` runs) and of the avatar-experiment commands (each part with `-avatarExperiment`, in batch mode, is
refused because nothing is frozen, and writes no marker).

**7. One development smoke trial:** B3, `-Rehearsal -Trials 1` (seed 1, development looks and clips, 900 s), Python from main (T0,
`control_lie_on.json`). Pass: the launcher's B11 check REHEARSAL VALID; leak test passed in Unity and in Python; `step5_session_checks.ps1`
ALL CHECKS PASSED (setting name `smoke_t0_B3`); Anisha's guard accepts the control file; no `checkpoint` or `side_view` key in any
`messages.jsonl` line or any `truth.jsonl` row. The outcome of the trial is reported, not judged (development).

**Commits:** this declaration alone; then the timeout, the tools and the report copy; then the results. Each after both suites pass. No push.

*Results of addendum 8 (2026-11-20; declaration 2ee6e63, implementation b66e39a; every check below ran on b66e39a).*

- **Kept / dropped.** Kept from `nusrat/v4-timing-backtrack`: `finals_v4/back_read_diagnosis_v4.py` (unchanged, from 683b5bc) with its report
  copy `reports_v4/back_read_diagnosis_20261119_203250.md`; `finals_v4/timing_rerun_report.py` (from 8acd539) with `--prefix`. New:
  `step5_report.py --prefix`, `finals_v4/step5_zip_v4.py`. Dropped: everything checkpoint- or side-view-specific (item 2). The uncommitted work
  of that branch is in a local `git stash` there ("abandoned 2026-11-20: checkpoints dropped"); nothing of it is on this branch.
- **Merge:** none needed (origin/main still 33cab20 after `git fetch`).
- **Suites:** Unity Edit Mode 345/345 (on 2ee6e63 and on b66e39a); Python 1423 OK, 9 skipped (both commits), her `MatchesUnity` (11),
  clearance (`test_clearance_layout_v4`, `test_clearance_rejection_v4`) and guard tests (`test_v4_final`, `test_t0_final_v4`) all run and pass.
- **Item 3, traces: PASSED** (`robot_vision/outputs/trace_check_20261120_135650/`): 56 matches in 7 files, 0 not allowed: the v3 Task 1
  route checkpoints (`Task1Route.cs` 9, `Task1RouteTests.cs` 3, `TrialRunner.cs` 4, `GroundTruthLayer.cs` 1), this addendum's text (25) and
  the diagnosis tool (5) with its report (9). No checkpoint position in any file (scenes and prefabs included). Nothing removed.
- **Item 3, placement: IDENTICAL to main's layout (i)** (`worker_path_check_20261120_142310/`, the temporary `TempWorkerPathCheck` of
  addendum 5 run in batch mode, deleted with its `.meta`, source copied there): all 400 plans equal the reference
  `worker_path_check_20261118_214612/plans.json` in setting, seed, run, map, goal, max_active and every worker's id, node, slot, x and z
  (largest position difference 0.000 m); this includes seed 1 runs 1 to 3 and seed 2 runs 1 to 20 of all 10 Unity settings (230 plans). Max
  worker id 10, no worker off an asking node, **max active avatars 3** (limit 6). Paths: 37,130 (6,163 distinct), every end snapped, none
  incomplete, none entering a footprint, none within 0.30, 0.60 or 1.0 m of a worker (least 1.001 m, A4 seed 2 run 7, as on main).
- **NavMesh Verify: PASSED** (`navmesh_v4_check_20261120_142610/`): V1, V2 (hard rule), V4.
- **Freeze list:** the 29 `final_v4.json` `freeze_files` exist; the 13 settings' experiment configs exist, name existing control files, and
  `final_guard_v4.control_problems` reports no problem for any of them (on files: `control_lie_on*.json`, T0; off files: `control_lie_off*.json`).
- **Launcher dry runs** (`step5_dryrun_t0_20261120_142721/`, `-Rehearsal -Trials 3 -DryRun`, the 13 settings): every one exit 0, not
  refused, "timeout 900 s per run", Unity wait `-trialTimeout 4500`, the setting's control file and `-experiment` / `-experimentSide`.
- **Avatar commands:** blind rehearsal: `avatar_rehearsal_check.py --help` exit 0, both entry points present (they ran below). Avatar
  experiment: `LookCheckMenu.BatchRunExperiment -avatarExperiment` and `LookCheckPlayMenu.CommandLineRunAB -avatarExperiment` in batch mode were
  both **refused** (exit 1: `frozen.json` not frozen, the B9 files not recorded); 0 `AVATAR_EXPERIMENT_*` markers before and after; no
  output folder written. Note for the rehearsal: `looks_ab.json` `avatar_experiment` includes the test looks (e.g. `sunbox_f2`), so the
  rehearsal's frames are deleted after the blind check (`--delete-frames`) and only its report goes to Anisha.
- **Item 7, smoke trial: PASSED** (development, not a result). B3, seed 1, 1 run, goal E2, 900 s (`-trialTimeout 2700`), Python from
  main with `control_lie_on.json` (T0). Unity `trials_development_Task2_B3_20261120_142959`, bridge `bridge_guide_20261120_142801`,
  transcript `smoke_t0_launcher_B3_20261120_142759.txt`, export `export_csv_v4_20261120_143346`.
  - Launcher B11 check: criteria 1, 3 to 7 PASS, 2 N/A (not frozen), REHEARSAL VALID; leak test passed in Unity and Python.
  - `step5_session_checks.ps1 -Setting smoke_t0_B3`: ALL CHECKS PASSED (`gesture_data.py --messages` 1 of 1).
  - Anisha's guard: `control_problems("B3", ...)` = none for both control files in `config_used/` (`checkpoint` false, no `side_view`).
  - No `checkpoint` or side-view key or text in any of 10,717 `messages.jsonl` lines, 245 `v4_log.jsonl` lines, 22,520 `truth.jsonl` rows
    or `session.json`.
  - Outcome: FAILURE, aborted at 190.4 s; 0 collisions, closest person 1.26 m. J1: the seeded liar showed RIGHT (read RIGHT), the second
    opinion LEFT (true, read LEFT), the tie re-asked the liar (RIGHT): the robot took RIGHT (fooled, the T0 limitation of AUDIT.md 16.26.9).
    J3: the honest worker's BACK was read NONE in both dialogs (as in addendum 6's smoke trial); abort. Timing: 0 watchdog stops, round trip
    max 37.7 ms, loop lag max 53 ms, 0 bridge errors; **free memory minimum 195 MB** (VS Code / Claude Code open; step 5 runs with it closed).
- **Not done here:** no step-5 session, no avatar rehearsal, no freeze, no final, no timeout set, no push.

#### 2026-11-20, addendum 8 amendment 1: step 5 draws E5 and E6 in the random-endpoint settings (declared before step 5 runs)

**Omission corrected.** Addendum 8 (items 6 and 7, and the step-5 commands handed to Nusrat with it) ran and recorded the step-5 settings
with `-Rehearsal -Trials 3` only. That drops the development-only goal override that AUDIT.md 16.20.5 decision 2 (Anisha, 2026-11-17) makes
part of the runs that feed the timeout rule: "applied to **Unity's step-5 rerun, which uses the 420 s development timeout and the
development-only goal override, so that E5 and E6 are drawn.**" (see also 16.19 item 4: "the longest routes of the finals' goal order are E5
and E6, which set the timeout"). It was not dropped on purpose and is not a default (the launcher's `-ExperimentGoals` is empty by default;
section 15 addendum 1 item 3c). The 900 s development timeout of addendum 8 item 4 replaces the 420 s of 16.20.5 and is unchanged here.

**The rule.** Step 5 passes `-ExperimentGoals "E5,E6,E5"` (trial 1 E5, trial 2 E6, trial 3 E5; `TrialRunnerV4Experiment` gives run r the
r-th goal, `ExperimentGoalsOverrideTests.Override_OneGoalPerRun_InTheGivenOrder_SpacesIgnored`) to the six random-endpoint settings **A3, B3,
B3_off, A4, B4, B4_off**; the other seven (A1, B1, B1_off, A2_right, B2_right, B2_right_off, A2_left) have fixed goals and get none (the
launcher refuses goals on a fixed-goal map). Development only: the launcher and Unity refuse `-ExperimentGoals` in a final. With
`-Trials N` other than 3 the list alternates E5, E6 for N runs. Placements and lies are seeded per run and do not depend on the goal.

**Where it applies.** Nusrat's step-5 run script (`E:\run_tonight.ps1`, outside the repository: each launcher call and session check in its
own child process, UTF-8 transcripts without absolute paths (the rule of step5_session_checks.ps1), the avatar rehearsal on the
folders of its own run) passes the goals to those six settings; its
dry run (`-DryRun`, prefix `dry_`) prints the six launcher command lines with `-experimentGoals E5,E6,E5`. Nothing in the repository's
code or configs changes. Addendum 8's smoke trial (B3, seeded goal E2) and dry runs stand as recorded (development checks, not step 5).

### 2026-11-21, section 15 addendum 9: the launcher ignores Unity Hub's helper (declared before any change below)

Nusrat's task of 2026-11-21, after step 5 (13 of 13 settings REHEARSAL VALID, `robot_vision/outputs/t0_step5_night_summary_20261120_211406.txt`).
Branch `nusrat/v4-launcher-hub-helper`, new from main affe652. Only `finals_v4/run_session_v4.ps1` changes (plus this entry): nothing under
`robot_vision/`, `docs/` or `external/`, no Unity code, scene or config; nothing is frozen, no session or final is run, nothing is pushed.

**Why.** The launcher refuses a session while any process named `Unity` runs (`Get-Process -Name "Unity"`: "a Unity Editor is running: close
it first"). Unity Hub starts its own helper `<Hub folder>\resources\unity.exe` (command line `unity.exe serve`): not an Editor, it never opens
the project, but it has the same process name. On 2026-11-20 it made the launcher refuse every remaining setting of one step-5 attempt (12
transcripts `robot_vision/outputs/aborted_20261120_night/step5_launcher_t0_*.txt`, "STOPPED: a Unity Editor is running"), and in the attempt
that completed, the night script (outside the repository) had to stop the helper before t0_B1_off (summary: "LEFTOVER before t0_B1_off:
unity PID 4060, hub_helper, ...: stopped"). Stopping a process of the Hub is a workaround; the launcher itself should not count the helper.

**The rule.** A process named `Unity` is Unity Hub's helper, and the check ignores it, only when both hold: (a) its executable is
`resources\unity.exe` (any case) in a folder that also holds `Unity Hub.exe` (the Hub's install folder, wherever the Hub is installed; on
Nusrat's PC `E:\Unity\Unity Hub`); (b) its command line can be read and has the argument `serve`. Every other process named `Unity` still
blocks, also one whose path or command line cannot be read (the check never guesses). An ignored helper is listed as a note ("ignored: Unity
Hub's helper unity.exe serve, PID n"), in `-DryRun` too. The launcher still never stops a process. Everything else is unchanged: the other
blockers, every refusal of a final, the session steps, the run protocol. `run_session_v4.ps1` is not on the B9 freeze list
(`freeze_v4.py` `unity_files`) and no test reads it; the step-5 sessions are not affected (the launcher is the same in every other respect).

**Checks before the commit.** A fake helper (a copy of a harmless program named `unity.exe` in a scratch `<folder>\resources\` beside an empty
`Unity Hub.exe`, started with the argument `serve`) is ignored by `-DryRun`; the same copy without `serve`, and without the `Unity Hub.exe`
beside it, blocks; with no process named Unity the dry run lists no Unity blocker. Both suites (Unity Edit Mode, Python) pass.

### 2026-11-21, section 15 addendum 10: the avatar checker's timing rule and play-only check; a session that starts at run k (declared before any change below)

Nusrat's task of 2026-11-21, items 3 and 5. Branch `nusrat/v4-launcher-hub-helper`, after addendum 9. Nothing under `robot_vision/`, `docs/` or
`external/` changes; nothing is frozen; no session, final, look check or avatar run is made; nothing is pushed. No file of the B9 freeze list
changes (`final_v4.json` `freeze_files`: configs, the scene, the prefab; no `.cs` file and no `finals_v4/` script is on it), so no frozen hash moves.

**Part 1. `finals_v4/avatar_rehearsal_check.py`.**

*What the checker judges.* Only the blind rehearsal of the avatar experiment. The real avatar experiment (section 8 step 5) is judged by Anisha's
`look_check_v4.py`, unchanged, and nothing else is run on it. That tool has no frame-step rule: it gives each header's `time_s` to the reader and
refuses a PROCEED sequence shorter than the reader's window (`proceed.window_s`, 2.0 s). Neither the old nor the new timing rule below touches a
result of the experiment.

*Why the timing rule changes (a rule changed after seeing a result: disclosed).* The rehearsal of 2026-11-20 (`avatar_rehearsal_check_20261121_001920`)
flagged 122 Play sequences, every one only because a step was shorter than 0.09 s (152 of their 1 640 steps; shortest 0.036 s; none longer than
0.2 s). Unity's capture rule (`LookCheckPlayDriver.CaptureIdle` and `Perform`) takes frame i at the first rendered frame at or after its mark
t0 + 0.1 i s (PROCEED: frames 1.. from frame 0's real time + 0.001 s), so a late frame followed by a short step back onto the 10 Hz grid is the rule
working; a minimum step is stricter than the rule it was meant to describe and fails every Play run. Before choosing the tolerance I had seen, from
the steps of the 122 flagged sequences in that report, offsets from -0.018 to +0.091 s; the tolerance is set from the capture rule (one sampling
interval), not from those numbers.

*The rule (replaces "every step at least 0.09 s").* For every sequence whose headers all carry `time_s`, with frame 0 as the anchor (Unity's own t0
of a non-PROCEED sequence is not in the header): (a) the times strictly increase; (b) every step is at most 0.2 s (unchanged); (c) every frame lies
within **0.100 s (exclusive)** of its mark: |t_i - m_i| < 0.100 s, m_i = t_0 + 0.1 i, plus 0.001 s for PROCEED frames i >= 1 (as Unity times them).
0.100 s is one 10 Hz interval: a frame that far from its mark sits in its neighbour's slot. Everything else of the check is unchanged (coverage and
missing groups, sequence frame counts, error-shader pixels, truth files, the frame deletion). The report adds, per part, the largest |offset|
(`timing_offset_max_s`) and the number of sequences timed (`sequences_timed`), so a later reading needs no frame.

*Play-only check.* `--edit` becomes optional. Without it the Edit part is not checked in that run (the report says so and names no Edit folder), the
verdict covers the parts checked, and `--delete-frames` deletes the frames of the checked parts only. Why: the rehearsal repeats only its Play part
(Anisha's `docs/handoff_freeze_v4.md` section 3); the Edit part of 2026-11-20 passed with 0 problems and its frames are deleted, so it cannot be
checked again.

*A part without its recording folder fails (a fault found while reading the checker for this entry).* `check_folder` returns early, with only a
problem, when a run folder has no `looks_check*` folder, and the verdict counted only parts that carry `missing_groups`, so such a part was left out
and the check could print PASSED for a Play folder whose frames are gone. From now on that part counts with its problem and fails. No earlier
verdict changes (2026-11-20's check had both recording folders).

*Test.* `finals_v4/test_avatar_rehearsal_check.py` (unittest; no frame, no model): an exact 10 Hz grid passes; a late frame followed by a short step
passes; the worst flagged sequence of 2026-11-20 (steps from its report.json) passes; a frame 0.100 s from its mark fails; slow drift past 0.1 s fails;
equal or decreasing times fail; a step over 0.2 s fails; PROCEED marks carry the 1 ms; a play-only call parses and an Edit folder is no longer
required; a play-only verdict leaves the Edit part out; missing groups still fail; a part without its recording folder fails. Run from the
repository root: `robot_vision\.venv\Scripts\python.exe -m unittest discover -s finals_v4 -p "test_*.py"` (macOS:
`robot_vision/.venv/bin/python -m unittest discover -s finals_v4 -p "test_*.py"`). CI runs `robot_vision/tests` only, so this third suite is run by
hand before every commit that touches `finals_v4/`.

*Checks on 2026-11-20's Play folder.* Its frames and headers were deleted by the night run's `--delete-frames` at 00:19 (`frames_deleted.json`,
10 800 files), so the checker cannot read it again. Instead: (1) the new rule on the frame times of the 122 flagged sequences rebuilt from report.json's
steps (3 decimals; the rounding adds at most 0.0005 s per step); (2) the same rule on the time_s of every header of the last complete Play run that
still has them, `look_check_play_ab_20261114_043454` (6 384 headers; no PROCEED then; headers read as JSON only, no image opened). The 124
missing groups of the timeout stay reported: the coverage rule does not change.

**Part 2. A session that starts at run k.**

*Can it be done today?* No. `TrialPlayV4` has no such option, `TrialRunnerV4.Trials` always runs 1..N, the launcher only sets the number of runs
(`-Trials`) and `check_session_v4.ps1` criterion 4 expects runs 1..N.

*What is already per run.* Every element of run k is a function of (session seed, k, goal of run k), and no state passes from one run to the next:
the goals of all N runs come from one `GoalSequence(seed)` (`ExperimentPlanAB.Goals`; Task 2: `TrialRunnerV4.Run`), or the N goals of
`-experimentGoals`; the placement from `PlanRun(seed, run, goal)` (`Rng(seed, run, node, salt)`); the A2 side from `RunMap(seed, run)`; the looks from
(node, run, slot); the liars from `DrawLie(seed, run, worker id)`; each worker's variation stream from `WorkerV4.SetRun(session seed, run)`; the STOP
stream from `SeededRandom.For(seed, run, 9973)`; the Task 2 commander and clips from `TrialRunWorkers.Plan(run, ...)`. Python names its
`python_trial_###.json` from the `trial_index` that Unity sends, so run k is trial k on both sides.

*The change.*
- `TrialPlayV4 -startRun k` passes k to the runner (an Editor session key, cleared at the end like the others).
- `TrialRunnerV4`: the rule of a new pure class `SessionResumeV4` (`HRI/Scripts/V4`, new file with its `.meta`): k must be a whole number within
  1..N (N = the session's number of runs), else the session does not start ("refused: -startRun ..."); empty = 1. **Refused with `-finalSetting`**
  (any k; see below). The session plans and checks all N runs exactly as now (the same plans, splits, goals and placement record in session.json),
  takes the leak test from the start of run k (the first run it drives) and drives runs k..N. `session.json` gets `start_run` (1 in every full
  session; a new last field of `SessionV4`, so every earlier field keeps its order) and `summary_unity.json` gets `start_run`; the status line reads
  `done: S/(N-k+1) SUCCESS (runs k..N)` when k > 1.
- Launcher `run_session_v4.ps1 -StartRun k` (rehearsal only; refused in a final; refused unless 1 <= k <= `-Trials`): passes `-startRun k` to Unity;
  `launch_prep --trials N` and `-ExperimentGoals` (still one goal per run of all N) are unchanged; the B11 check gets `-StartRun k`.
- `check_session_v4.ps1 -StartRun k` (default 1): criterion 4 expects runs k..N in `results_unity.csv`, `run_###` and `python_trial_###`; a final
  refuses k other than 1. Its `Report` lines and labels do not change (Anisha's `test_v4_frozen.py` pins them).

*Test (Edit Mode, `HRI/Tests/SessionResumeTests.cs`, new file with its `.meta`).* For each of the 8 experiments, seeds 1 and 2, N = 3 (k = 2, 3) and
N = 20 (k = 2, 11, 20): a fresh `ExperimentPlanAB` (as a new Unity session builds it) plans runs k..N from the goals over all N runs; every run is equal
field by field (goal, map, redraws, max active, and each worker's id, node, slot, position, gender, look, liar, true and shown command) to the same run
of a full session planned in order 1..N on another fresh object (the resumed object never plans runs 1..k-1, so no state of earlier runs can enter).
That the comparison covers lies is checked too (Set B draws liars over 20 runs). Plus the range rule: 0, N + 1 and a non-number refused, empty = 1,
any k refused in a final. The test covers the experiments A/B (the finals and step 5); the Task 2 and STOP-session paths use the same loop and the
same per-run plans (`TrialRunWorkers.Plan(run, ...)`, `stopItems[run - 1]`) and are not tested separately.

*Not changed: the run-once guards.* A resumed FINAL stays refused: when an interrupted final's server exits with a trial file it writes
`FINAL_RUN_DONE.json`, which both Python's guard and Unity's `FinalGuardV4.EarlierFinal` read. How a resumed final counts, and which guard accepts it,
is Anisha's interruption rule (not in the repository on 2026-11-21) and needs her guard first; Unity's guard then follows in a declared change.
**For Anisha [A]:** a resumed session is a second Unity session folder and bridge run folder holding runs k..N; her evaluation and export tools must
accept a session that starts at run k and pair it with the interrupted one (not checked here).

**Addendum 10, as built (2026-11-21).** Implemented as declared. Files: `finals_v4/avatar_rehearsal_check.py`, `finals_v4/test_avatar_rehearsal_check.py`
(new), `Scenario/Editor/TrialPlayV4.cs`, `Scenario/Scripts/TrialRunnerV4.cs`, `HRI/Scripts/V4/SessionResumeV4.cs` (new), `HRI/Tests/SessionResumeTests.cs`
(new), `finals_v4/run_session_v4.ps1`, `finals_v4/check_session_v4.ps1`. One detail added while building, same rule: a part without its recording
folder reports its folder relative to `robot_vision/` (an absolute path in a report under `outputs/` fails Anisha's `test_run_paths`).
- *Checker tests:* 14 of 14 pass (`finals_v4`, the command above).
- *2026-11-20's Play folder (rebuilt times):* the 122 flagged sequences pass the new rule, 0 fail; largest |offset| 0.091 s. Its 124 missing groups stay
  in that report; the folder itself can no longer be checked (frames and headers deleted), so the verdict of a rerun is the repeated Play part.
- *`look_check_play_ab_20261114_043454` (headers only):* 336 sequences (NONE 48, POINT 96, STOP 96, WAIT 96), 0 fail the new rule; 216 of them had
  failed the old 0.09 s minimum step. Largest |offset| **0.096 s**: 4 ms inside the tolerance. A single hitch of 0.1 s or more in the repeated Play part
  will fail it, as declared; that would be reported, not tuned.
- *Launcher and check (dry runs, nothing run):* `-Experiment B3 -Rehearsal -Trials 3 -StartRun 2 -ExperimentGoals "E5,E6,E5"` passes
  `-experimentGoals E5,E6,E5 -startRun 2` to Unity and `-Runs 3 -StartRun 2` to the check; `-StartRun 4` and `0` (of 3) refused; any `-StartRun` in a final
  refused; without `-StartRun` the dry run is as before. `check_session_v4.ps1`: `-StartRun 4 -Runs 3` and `-Final -StartRun 2` refused (exit 2).
- *Not run:* no Play session with `-startRun` (development check for Nusrat when wanted: e.g. B3 with `-Trials 3 -StartRun 2`, then compare
  `session.json` `workers_plan`, `goal_order` and run 2's `truth.jsonl` liars with the full session `trials_development_Task2_B3_*` of step 5).

### 2026-11-21, section 15 addendum 11: the avatar rehearsal's cyan frames, the avatar-experiment look role, the clip of Edit takes, section 8 corrected (declared before any change below)

Nusrat's task of 2026-11-21, after the avatar rehearsal's Play part failed its format check. Branch `nusrat/v4-rehearsal-fixes` from origin/main
`21a4eaf`. Nothing under `robot_vision/`, `docs/` or `external/` changes; nothing is frozen; no session, final, look check or avatar run is made;
nothing is pushed. One file of the B9 freeze list changes: `looks_ab.json` (item 2), so its hash moves before the freeze (nothing is frozen yet).
`look_check_play_ab.json`, `look_check.json`, `worker_v4.json`, the scene and the prefab do not change. The checker
(`finals_v4/avatar_rehearsal_check.py`) does not change: its rules, the 0 error-shader-pixel rule included, stay as in addendum 10.

**Diagnosis (read only, before this entry).** The Play part (launcher 15:10 to 17:20, commit `21a4eaf`, run folder
`look_check_play_ab_20261121_151205`) finished: 15 looks, 270 of 270 groups (2 sequences + 16 singles each), 4 860 recordings, 11 460 frames, Unity
exit 0 after 131 min, no timeout. The play-only check `avatar_rehearsal_check_20261121_172439` failed on one rule only: **38 frames with exact cyan
(0, 255, 255) pixels** (527 520 pixels in all; 0 magenta). All 38 are `anime_f_01`, command NONE, at J2: 8 singles and 1 sequence of 11 frames at
2.0 m (20 089 to 25 042 cyan pixels per frame) and the same takes at 4.0 m (5 284 to 6 080), recorded between Time.time 5124.86 and 5128.80 s.
That window is the first render of any anime material in the session (the looks run in rounds of one look per junction, and each look is at J2 one
round before J1; `anime_f_01` at J2 is worker 22 of round 11 of 15). Its next take (POINT at 5130.98 s), its J1 round, `anime_f_02_outfit_short`, `anime_f_03_bangs_parted` and `cartoon_boxo_01` have
none. The anime materials are URP Lit with `_ALPHATEST_ON` and `_EMISSION`, keywords no earlier look uses (Sunbox: specular set-up, no alpha test,
no emission), so their variants were compiled at that moment: the Unity log shows two shader compilers launched during Play. Everything else passed:
no missing group, every sequence frame count, 540 sequences timed with the largest |offset| 0.0887 s (< 0.100 s), every header, 30 of 30 truth files.
The frames were deleted by `--delete-frames` after the report (22 920 files, 4.85 GB), as the blind rule says (`docs/handoff_freeze_v4.md` section 3).
Classification: **a real recording problem** (the Editor's still-compiling placeholder in recorded frames), not a checker problem and not a
run-condition hitch. It is the failure of section 5 addendum 2 (2026-11-14: 56 of 76 `anime_f_01` NONE frames, first renders of new materials):
the menu's session switch `ShaderUtil.allowAsyncCompilation = false`, set when the scene loads (`LookCheckPlayMenu.OnSceneLoaded`), does not stop
it, and the earlier remedy was a second run once the variants were cached. No tolerance changes.

**Item 1. Shader warm-up and a synchronous capture render (`LookCheckPlayDriver`).**
- After a round's workers are spawned and before their first take, a warm-up: every camera of every site is put on the site's facing line at its
  nominal distance (2.0 and 4.0 m, pan-tilt height, looking at the stand) and rendered once per frame until (a) at least 3 renders, (b) the last 2
  renders of every camera have no exact cyan or magenta pixel, and (c) the Editor reports no shader compiling (`ShaderUtil.anythingCompiling`); at
  most 120 s, else the run fails (`failed: shader warm-up ...`). The warm-up draws from no seeded stream (pose, variation, clip and STOP streams are
  untouched), so every take's camera pose, variation and clip is the same as without it; it writes no recording. The next take's `PlaceCameras`
  sets the camera poses as before.
- Every capture render (warm-up and recording) turns `ShaderUtil.allowAsyncCompilation` off around `Camera.Render()` and restores it (Unity's
  per-call use; Editor only). The menu's session switch stays.
- `recordings.jsonl` Play rows get `magenta_pixels` and `cyan_pixels`: exact colours as the checker counts them, summed over the recording's frames,
  counted in the write task (off the main thread, so capture timing is unchanged). `run_info.json` gets `shader_warm_up` (rounds, renders, the
  longest warm-up, error-shader pixels seen during warm-ups). A recording with such pixels is logged as a warning; the checker judges it.
- The pure parts go into WarehouseAvatar (new `Avatar/Scripts/ShaderWarmUp.cs` with its `.meta`): the pixel count on an RGBA32 buffer and the stop
  rule, with the constants 3 renders, 2 clean renders, 120 s. They are operating limits of the capture, not evaluation thresholds; set before any run.
- Not changed: `TrialRunnerV4` (sessions and finals keep the same session switch; see the limitation below), the Edit look check (0 cyan pixels in
  every Edit run so far; it renders in the Editor, not in Play).
- Tests (Edit Mode, WarehouseAvatar): exact cyan and magenta counted, near colours not counted, an odd buffer length refused; the stop rule (too few
  renders, a dirty render, still compiling, the 120 s limit).
- Limitation, not changed here: `TrialRunnerV4` relies on the same session switch, so the first frames of a look whose shader variants are not yet
  compiled could reach Python cyan. The finals use the Sunbox looks (variants compiled in every earlier session); a check of the finals' first
  frames is for Nusrat's decision.

**Item 2 (task item 0). The avatar-experiment look role and `GuardRun`.**
- Anisha's finding: `DataSplitsV4.GuardRun` would accept a lone avatar-experiment look. Today it refuses those looks only because
  `data_splits.json` does not list them; once it lists them (her hand-off note, section 5 (b)) a trial session could use one.
- `looks_ab.json`: role `avatar_experiment` (today `candidate`) for the six looks of its `avatar_experiment` list that are in no split of
  `data_splits.json`: `mixamo_worker`, `sunbox_m2`, `anime_f_01`, `anime_f_02_outfit_short`, `anime_f_03_bangs_parted`, `cartoon_boxo_01`. The
  navigation looks keep `candidate`; `worker_v4.json` and `look_check.json` do not change.
- `LookEntry.RoleAvatarExperiment`. `ExperimentLooks.Validate`: a role is `candidate` or `avatar_experiment`; a navigation look never has
  `avatar_experiment`; a look with that role is in the `avatar_experiment` list.
- `DataSplitsV4.Parse(splits, looksAb)` keeps the ids of the looks with that role; `GuardRun` refuses any of them first, in development and final
  mode, alone or with other looks, whatever split `data_splits.json` gives it ("... is an avatar-experiment look (looks_ab.json role
  avatar_experiment): refused in every trial session; only the avatar experiment's look checks record it"). `TrialRunnerV4`, the one runtime reader
  of `data_splits.json` (Task 2, STOP, experiments A/B and the finals all go through it), passes `looks_ab.json`.
- The avatar experiment (Edit `LookCheckMenu.RunExperiment` / `BatchRunExperiment`, Play `LookCheckPlayMenu` / `LookCheckPlayDriver`) never calls
  `GuardRun` and records these looks as before; the Edit rows' `role` column now says `avatar_experiment` for them.
- Tests: (a) refused: each of the six alone, in development and final mode, beside a development look, and after adding it as development to a copy
  of `data_splits.json`; (b) the avatar experiment keeps them: `looks_ab.json` validates, every look with the role is in its `avatar_experiment` list,
  every look of that list missing from `data_splits.json` has the role and no listed look has it, and the navigation looks pass `GuardRun` as before.

**Item 3 (task item 1). The clip of each take.**
- Play: `recordings.jsonl` `clip` (the `worker_v4.json` clip name; "" for NONE) beside `look`, `command`, `distance_m`, `arm`, `junction`, `take`,
  e.g. `{"name":"anime_f_01__POINT__2.0__left_s2_j2_point_mixamo_02", ..., "command":"POINT","arm":"left","clip":"point_mixamo_02","junction":"J2",
  ..., "take":2, ..., "distance_m":2.0, ...}`; and every truth row (`truth/*.jsonl` `clip`). No change.
- Edit: none. Edit takes are held poses from `look_check.json` variants (`PoseSpec`), not animation clips. The Edit row gets `clip` "" and `pose`
  "posed" (appended after the earlier fields, which keep their order). The record class moves from `LookCheckMenu` (Editor) to WarehouseAvatar
  (`LookCheckEditRecord`, same fields) so that a test can pin it. Test: a record's JSON has `look`, `command`, `distance_m`, `arm`, `take`, `clip` ""
  and `pose` "posed".

**Item 4 (task item 2). The avatar-session marker.** It exists; no new key: `avatar_experiment_part` ("edit" or "play" in the official run, "" in an
engineering check) in `run_info.json` of each part, and the run-once markers `AVATAR_EXPERIMENT_STARTED.json` / `AVATAR_EXPERIMENT_DONE.json` with
the same key (`AvatarExperimentGuard.MarkerJson`).

**Item 5 (task item 3). Resume names: not changed.** `resume_from_run`, `resume_of` and `--resume-marker` appear on no branch of origin (all refs,
2026-11-21, `anisha/v4-prefreeze` included, which main already contains) and nowhere in the working tree. Unity's names stay `start_run`
(`session.json`, `summary_unity.json`), `-startRun` and `-StartRun` until Anisha names hers **[A]**.

**Item 6 (task item 4). Section 8 corrected in place**, with a dated note at its top: 15 looks (`anime_f_02_outfit_short`,
`anime_f_03_bangs_parted` added in section 10); PROCEED recorded (section 10 item 5); `cartoon_boxo_01` in Play too (addenda 9 to 13); `sunbox_m2`
in no split, role `avatar_experiment` (item 2); counts of the Play and Edit parts as run on 2026-11-20/21; the run-once guard exists (section 10 item 6).

**Item 7 (task item 5). `SOURCES.txt`: nothing to fix.** Its line 12 reads `anime_f_03_bangs_parted.fbx`, the file name and the `looks_ab.json` id;
the earlier `anime_f_03_hairback.fbx` was corrected by Nusrat (section 11).

**Order.** This declaration is committed alone; then items 1, 2, 3 and 6 with their tests in one commit after Unity Edit Mode and the Python suite
pass. Then Nusrat repeats the Play part and the play-only check (about 2 h 15 min); a repeat is a new run folder, the failed one is kept.

**Addendum 11, as built (2026-11-21).** Implemented as declared. Files: `Avatar/PlayCheck/LookCheckPlayDriver.cs` (warm-up `WarmUp`, `RenderInto`,
`Compiling`; `magenta_pixels` / `cyan_pixels` per recording; `run_info.json` `shader_warm_up`), `Avatar/Scripts/ShaderWarmUp.cs` (new, with its `.meta`),
`Avatar/Scripts/TrialWorkersV4.cs` (`DataSplitsV4.AvatarExperimentLooks`, `Parse(splits, looksAb)`, `GuardRun`), `Avatar/Scripts/ExperimentLooks.cs` (role
rules), `Avatar/Scripts/LookCheckConfig.cs` (`LookEntry.RoleAvatarExperiment`, `LookCheckEditRecord`), `Avatar/Editor/LookCheckMenu.cs` (uses it),
`Scenario/Scripts/TrialRunnerV4.cs` (reads `looks_ab.json` with `data_splits.json`), `Avatar/Config/looks_ab.json` (six roles), section 8 above,
`Avatar/Tests/RehearsalFixesTests.cs` (new, with its `.meta`; 6 tests).
- *Tests:* Unity Edit Mode 354 of 354 (348 + 6 new); `finals_v4` 14 of 14 (unchanged); Python suite as in the commit message.
- *Not run:* no Play run. The warm-up, the synchronous render and the pixel fields are exercised only by the repeated Play part (Nusrat), whose
  `run_info.json` `shader_warm_up` and `recordings.jsonl` `cyan_pixels` show what the warm-up did; the checker judges the frames as before.

### 2026-11-21, section 15 addendum 12: the shader warm-up record and compile flag (both look-check parts), the warm-up of a trial session, the data_splits role (declared before any change below)

Nusrat's task of 2026-11-21 (evening), items 1 and 2, with Anisha's corrections: the rehearsal check keeps `--delete-frames` (her blind rule:
frames are deleted even when the check fails; `cyan_pixels` in `recordings.jsonl` is the diagnosis), and her AUDIT.md 16.31.5 item 1 (the cyan /
magenta rule decided from Unity's warm-up record and the frame's time, never from images). Branch `nusrat/v4-rehearsal-fixes` after addendum 11.
Nothing under `robot_vision/`, `docs/` or `external/` is edited; nothing is frozen; no Play run; nothing is pushed. B9: `final_v4.json`,
`looks_ab.json` and the configs do not change in this addendum.

**Item 1. The warm-up record and the compile flag, in both parts of the avatar experiment.**
- *Record.* Every warm-up writes one JSON line into `shader_warm_up.jsonl` in the run folder of the look check (`look_check_play_ab_<time>/`,
  `look_check_ab_<time>/`, next to `recordings.jsonl`; not in the `looks_check*` recordings folder, which `--delete-frames` empties). Fields (class
  `ShaderWarmUpRecord`, WarehouseAvatar): `part` (play, edit or session), `round` (Play round, 1-based; -1 otherwise), `looks` (look per stand, e.g.
  "J1: anime_f_01 (worker 23); J2: ..."), `stands` (where the cameras stood), `cameras` (nominal distances), `clock` (`Time.time` in Play and in a
  session, the clock of the frames' `time_s`; `EditorApplication.timeSinceStartup` in Edit, whose headers carry no `time_s`), `time_start_s`,
  `time_end_s`, `started_local`, `ended_local`, `compiling_at_start`, `compile_seen_first_s` and `compile_seen_last_s` (the clock at the first and
  the last render after which `ShaderUtil.anythingCompiling` was true; -1 if never), `compiling_at_end` (`ShaderUtil.anythingCompiling` when the
  warm-up ended), `renders`, `last_clean_streak`, `error_pixels_seen`, `look_pixels` (session warm-up: pixels the look changes in the render; -1
  otherwise), `status` (done, timed_out, not_in_view). The per-round summary in `run_info.json` `shader_warm_up` stays.
- *Flag per recording.* `recordings.jsonl` rows of both parts get `shaders_compiling` (true when `ShaderUtil.anythingCompiling` was true just before
  or just after the render of any frame of the recording) and `shaders_compiling_frames` (the frame indices for which it was true; `[]` if none).
  Edit rows also get `cyan_pixels` (exact (0, 255, 255), as the checker counts it); their `magenta_pixels` (tolerance rule) is unchanged.
- *Edit part.* `LookCheckMenu.Run` (the Edit check and the avatar experiment's edit part, `RunExperiment` / `BatchRunExperiment`) gets the same
  warm-up before the first recorded render of each look at each distance: the check camera renders the posed look (rest pose) until the rule of
  addendum 11 holds (at least 3 renders, the last 2 clean, nothing compiling; 120 s of real time, else the run fails); each Edit render compiles
  synchronously (`ShaderUtil.allowAsyncCompilation` off around it). No draw from any stream (Edit has none); the recordings are unchanged.
- *The real avatar experiment.* Edit: `RunExperiment` -> `Run` (warm-up, flags). Play: `LookCheckPlayMenu.CommandLineRunAB -avatarExperiment` ->
  `LookCheckPlayDriver` (warm-up per round, flags). Both official parts use exactly these paths; nothing is switched off by the flag.
- *For Anisha's rule (16.31.5 item 1).* A frame with placeholder pixels counts as INVALID when its recording has `shaders_compiling` true (Play: also
  its `time_s` inside a warm-up's `compile_seen_first_s`..`time_end_s` on the same `Time.time` clock); otherwise it is a look defect. Unity provides
  the data; the rule is Anisha's.

**Item 2. The warm-up of a trial session (`TrialRunnerV4`, every session: development, STOP, experiments A/B, finals).**
- After the plans are made and before the leak test (and before any run's workers are spawned), every look of the session (the commander and
  bystander looks of every planned run; an experiment's: every planned worker's look; distinct, ordinal order) is warmed up once: a temporary
  worker of the template with that look (not in the session's worker list, no `SetRun`, no truth logging, no id of the plan) stands 2.0 m ahead of
  the start node A on A's heading; a temporary camera with the pan-tilt camera's settings (`PanTiltCamera.ApplyCameraSettings`, the robot's config)
  at A, at the pan-tilt height, looking along the heading, renders only a free layer (the highest unnamed layer; the temporary worker is moved to it,
  so no rack or robot part can hide it; every light of the v4 scene lights every layer) until the warm-up rule holds; then the worker and the
  camera are destroyed and one frame passes before the next look. A look whose render does not differ from the empty render (`look_pixels` 0) is
  `not_in_view` and the session does not start (nothing is recorded as warmed up that was not drawn).
- No seeded stream is drawn (the plans, goals, placements, looks, liars and clips are made before it and are not read again), so every run is what
  it was. The leak test and run 1 (or run k) follow as before.
- `session.json` gets `shader_warm_up`: the list of the records of item 1 (part "session"), one per look, as a new last field (every earlier
  field keeps its order; an experiment session's own fields follow). A timeout or `not_in_view` refuses the session ("not started: shader warm-up
  ...", `NOT_STARTED.txt`), before the leak test.
- The 360 camera is not warmed up separately (it renders the same materials with the same passes); disclosed.

**Item 3. The `data_splits.json` role (Anisha's 16.31.2).** Her branch `anisha/v4-prefreeze-2` gives the six looks the role `avatar_experiment` in
`data_splits.json` itself and her `guard_run` refuses it in every mode; she asked Unity to close the same hole. `DataSplitsV4.Parse` therefore also
takes every look whose `data_splits.json` role is `avatar_experiment` into `AvatarExperimentLooks` (refused first by `GuardRun`), besides the
`looks_ab.json` roles of addendum 11. A test requires the two sources to agree (a look has role `avatar_experiment` in `looks_ab.json` exactly when
`data_splits.json` does not list it as development or test).

**Item 4. Merge.** After this addendum is built, `origin/anisha/v4-prefreeze-2` (Anisha's branch, e49259b) is merged into this branch so that the
resume work (addendum 13) can use her `final_guard_v4.py --resume-info`; only her files change by the merge.

**Tests (Edit Mode).** The warm-up tracker (renders, clean streak, first and last compile, compiling at end, status, the record's JSON field names);
the per-recording flag (frame indices, Play and Edit records' JSON); the differing-pixel count and the free-layer choice; the session's look list
(distinct, ordinal, no empty name); a source check that `TrialRunnerV4`'s warm-up draws no seeded stream and runs after the plans and before the
leak test; the data_splits role (refused with `Parse(json)` alone; the two sources agree).

**Not run.** No Play run (Nusrat's rehearsal repeat and the next session exercise the Play warm-ups). The Edit warm-up is exercised once by an Edit
engineering check of one look in batch mode (`-lookCheckLooks sunbox_m1`, no `-avatarExperiment`; its folder is kept and named in the as-built note).
