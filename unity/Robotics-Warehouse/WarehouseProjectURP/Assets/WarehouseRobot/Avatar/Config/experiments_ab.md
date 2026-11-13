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
