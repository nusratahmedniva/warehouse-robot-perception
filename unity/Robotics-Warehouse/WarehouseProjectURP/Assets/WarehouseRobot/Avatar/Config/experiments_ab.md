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

Question: how does the kind of avatar change what the robot's perception finds and reads (person, arm, hand, the gesture), with the frozen
reader? An engineering measurement with Anisha's `look_check_v4.py` **unchanged** (its rules: `docs/look_check_v4.md`, `configs/v4/look_check.json`);
no value of any tool, reader or config is tuned on it, and its results never feed back into the navigation finals.

**Looks per kind** (the `avatar_experiment` list of `looks_ab.json`, unchanged; 13 looks):

| kind | looks | recorded in |
|---|---|---|
| realistic human | `mixamo_worker` | Edit mode and Play mode |
| stylised human (Sunbox body family) | development: `sunbox_m1`, `sunbox_f1`, `sunbox_m2`, `sunbox_m_shirt_white`, `sunbox_m_tshirt_black`, `sunbox_f_shirt_white`, `sunbox_f_dress_red`; test: `sunbox_f2`, `sunbox_m_shirt_plaid`, `sunbox_f_shirt_plaid` | Edit mode and Play mode |
| anime | `anime_f_01` (the re-export of section 5) | Edit mode and Play mode |
| cartoon non-human | `cartoon_boxo_01` | Edit mode only: the worker template cannot spawn it (one finger chain per hand; `look_check_play_ab.json` `looks_excluded`, section 2 rule) |

No look is added, dropped or replaced because of a result; a look that fails is reported as failed (as anime_f_01 and cartoon_boxo_01 in section 6).

**Commands, distances, repeats** (the existing configs, unchanged):
- *Commands:* POINT, WAIT, STOP and the negative control NONE (the worker idle, facing the robot). PROCEED is **not evaluated**: the Unity look checks
  record `WorkerV4Config.Commands` (POINT, WAIT, STOP) only, and Anisha's tool grades PROCEED only when PROCEED recordings exist (AUDIT.md 16.12
  item 5). Recording PROCEED would be a Unity change, to be declared before the freeze if wanted **[N]**.
- *Edit mode* (`Avatar/Config/look_check.json` with the looks of `looks_ab.json`, `LookCheckMenu.BatchRunExperiment`, every look of the list): the declared held
  poses on the neutral stage at 2.0 m (verdict distance) and 4.0 m, both arms, 11-frame sequences and singles as `look_check.json` `recording`.
- *Play mode* (`Avatar/Config/look_check_play_ab.json`, unchanged: venue `WarehouseRobot_v4.unity`, the J1 and J2 worker stands, asking bearings
  15 to 50 deg, real motion with the worker template, seed 1): per look, command, distance (2.0 and 4.0 m +- 0.15 m) and arm (left, right; NONE
  has none): **2 sequences of 11 frames + 16 single frames = 38 frames** per group, so 12 POINT/WAIT/STOP groups (456 frames) and 2 NONE groups
  (76 frames) = **532 frames per look**, 12 looks = 6 384 frames. The seed is the one of the step 2 check (the same poses are drawn again, so the
  numbers are comparable with that engineering check, which is not part of the experiment).
- *Measures, per look and summed per kind:* the fields of Anisha's report (person found, arm valid, hand linked, own cue, wrong class, sequence
  read, arm-to-shoulder ratio p95, facing, verdict) at 2.0 m and at 4.0 m, each with its count (coverage); plus the Unity-side checks of section 2
  (bone arm-to-shoulder ratio against 1.683, hand reach to the IK target, the mirror-rest correction, material problems, magenta pixels).

**How it runs, once, after the freeze.**
1. Precondition: `configs/v4/frozen.json` frozen with every hash matching, *and the last navigation final of section 7 is done* (so no avatar
   result can influence a final). The configs it reads (`looks_ab.json`, `look_check.json`, `look_check_play_ab.json`, `worker_v4.json`,
   `WorkerV4.prefab`, the v4 scene) are on the B9 list (section 7 step 4) and therefore frozen.
2. On main at the frozen commit, clean tree, Nusrat's PC, the run protocol (other apps closed, Best performance; `run_protocol_v4.ps1 -Label avatar_experiment`).
3. Edit mode (batch mode works for it), from the repository root:
   `& "C:\Program Files\Unity\Hub\Editor\2022.3.62f3\Editor\Unity.exe" -batchmode -quit -projectPath unity\Robotics-Warehouse\WarehouseProjectURP -executeMethod WarehouseAvatar.EditorTools.LookCheckMenu.BatchRunExperiment -logFile robot_vision\outputs\avatar_experiment_edit_<time>.log`
   -> `robot_vision/outputs/look_check_ab_<time>/`.
4. Play mode in the Editor WINDOW (no `-batchmode`, as the finals):
   `& "C:\Program Files\Unity\Hub\Editor\2022.3.62f3\Editor\Unity.exe" -projectPath unity\Robotics-Warehouse\WarehouseProjectURP -executeMethod WarehouseAvatar.EditorTools.LookCheckPlayMenu.CommandLineRunAB -lookCheckTimeout 10800 -logFile robot_vision\outputs\avatar_experiment_play_<time>.log`
   -> `robot_vision/outputs/look_check_play_ab_<time>/` (recordings in its `looks_check_<time>/`).
5. From `robot_vision\`: `.\.venv\Scripts\python.exe look_check_v4.py --input <the recordings folder of the Edit-mode run>` and the same for the
   Play folder; nothing else is run on them. A cyan-placeholder frame (section 5, addendum 2) or a crash is reported as it is; the run is **not
   repeated** (as for a final). The step 2 and 2b look checks stay engineering checks and are not results of the experiment.
6. Run once: the two output folders (identified by their `run_info.json` commit = the frozen commit) are the avatar experiment. No code guard is
   built for it (declared; a guard like `FinalGuardV4` would be a later, declared change **[N]**).
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
