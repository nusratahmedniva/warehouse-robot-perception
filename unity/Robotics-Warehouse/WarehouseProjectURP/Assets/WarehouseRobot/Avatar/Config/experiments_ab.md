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
- **Boxo's screenshots come from its Edit-mode poses** with the neutral camera of item 8 (POINT and WAIT `seq1`, STOP `seq1`, PROCEED at the top of
  the `seq1` swing; both arms). The anime looks' screenshots come from the Play geometry check (the worker template), as declared.
