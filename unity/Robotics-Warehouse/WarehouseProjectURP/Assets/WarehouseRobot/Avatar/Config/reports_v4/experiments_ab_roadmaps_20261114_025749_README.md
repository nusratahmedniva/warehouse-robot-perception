# Experiments A and B: map files and what Python needs before Unity runs (for Anisha)

Written 2026-11-14 by Claude for Nusrat, to pass to Anisha. Unity branch `nusrat/v4-experiments-ab`; design notes in
`unity/.../Assets/WarehouseRobot/Avatar/Config/experiments_ab.md`. **Nothing under `robot_vision/` or `docs/` was changed** (this folder is
git-ignored output). Each item below is a change for you to decide; none is made.

## Files here

| file | what |
|---|---|
| `corridor.json` | YOUR map `scenarios_ab.json` `maps.corridor` (A1/B1), copied verbatim into the roadmap.json format. Not a new route. |
| `turn.json` | YOUR map `maps.turn` (A2/B2), the same. Unity checked it fits the warehouse: C (26.25, 0) is a free cell of the Unity ground-truth grid, 2.0 m from the nearest blocked cell. |
| `turn_left.json` | **PROPOSAL (new route)**: A2 with a LEFT turn, the mirror of `turn` about x = 6.25 (C at (-13.75, 0), equal legs 20 + 20 m). Nusrat's plan says "left or right at the corridor end"; your 16.2 decision 1 has the right turn only. Unity uses it only if `experiments_ab_unity.json` `a2_sides` lists `left` (default `["right"]`). Unity test: `ExperimentPlanABTests.TurnLeftProposal_IsTheMirrorOfAnishasTurnMap`. |

## What Python needs (write-down only; for your decision)

1. **Maps for the server (A1, A2).** `bridge.server` takes the robot's map from `control.json` -> `roadmap`. For Unity runs of A1/B1 and A2/B2 the server
   needs a roadmap file of the corridor and turn maps (the two files here are your maps in that format) and control configs that name them. A3/A4 use
   `configs/v4/roadmap.json` and run with the existing server. Unity checks only Python's route name (`Task2`), so a server with the wrong map would not be noticed.
2. **Detection settings for Unity runs.** Control configs with `lie_detection` off and on (a + b), like `scenarios_ab.json` `detection`; and
   `export_csv_v4.py` reads the setting from `session.json` `lie_detection`, which Unity does not know: for Unity sessions it could come from the bridge's
   `config_used/control.json` instead.
3. **data_splits.json.** The new look names (proposed split in Nusrat's report; `looks_ab.json` `proposed_split`). Unity refuses an experiment session
   until data_splits.json lists at least one male and one female development navigation look.
4. **Lie model (difference to the simulator).** Unity: a worker's lie is drawn ONCE per worker per run and is **consistent** (the same wrong direction every
   time that worker is asked, as Nusrat's plan says). Your 16.2 decision 2: every gesture is an independent draw. Unity also shows a wrong but VALID branch
   where the node has one (your simulator draws among all three other directions, so it can show an impossible one at a junction); where no other branch
   exists Unity uses your rule (one of the other directions of LEFT/FORWARD/RIGHT/BACK). Please confirm, or say which one the paper uses.
5. **People per node.** Unity: 2 everywhere and **3 at J1** in A3, A4, B3, B4 (Nusrat: Set B needs junctions with 2-3 workers; same layout in A and B).
   Your simulator: 2 everywhere.
6. **Beside layout.** Unity: slot 1 = your (3.0 m before, 2.0 m left); slot 2 stands farther back (5.5 m before, 2.0 m right) at junctions and 4.0 m right at
   the start node, because your symmetric pair breaks the bystander rule (the robot would see both equally near). Slot 3 (J1) 3.0 m behind slot 1.
7. **Random layout.** Your 6 m square + the placement rule + Unity's 1.0 m bystander margin cannot place 3 workers (0 of 200 000 draws) and needs ~11 800
   draws for 2. Unity default: margin 0.25 m in the random layout (~114 and ~2 900 draws). Alternatives: 1.0 m with a 10 m square, or no third worker at J1.
8. **Goals of A3/A4.** Unity draws them with the session's existing `GoalSequence(seed)` (the Task 2 order), not `random.Random(f"{seed}|goal")`.
9. **Truth: extra field `active`.** Workers far from the robot are switched off (activation window, at most 6 active); truth.jsonl still lists them every frame
   (the writer requires the same workers in every frame) with `"active": false`, idle at their stand. Extra fields are ignored by `gesture_data.py`.
   A hidden worker cannot be seen by the robot; please confirm the evaluation is fine with that (or add `active` to the bystander logic).
10. **look_check_v4.py has no PROCEED** (`configs/v4/look_check.json` `input.commands`): PROCEED readability per look cannot be judged by the tool.
11. **FALSE STOP during PROCEED (step 1 of Nusrat's task)**: see `outputs/experiments_ab_step1_20261114.md`: the live reader reads STOP on 37-62 % of PROCEED frames;
    `v4_log.jsonl` cannot show it (no READ tick during a safety stop). For your decision before the freeze.
