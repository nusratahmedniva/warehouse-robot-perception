<!-- Copy (2026-11-20, experiments_ab.md section 15 addendum 8 item 2 (b)) of robot_vision/outputs/back_read_diagnosis_20261119_203250/report.md, written by finals_v4/back_read_diagnosis_v4.py at commit 7c5adc6 (run_info.json). Unchanged below this line. The CSVs stay in that output folder. -->

# Why BACK was not read (20261119_203250)

Session `trials_development_Task2_B3_20261118_235842` + `bridge_guide_20261118_235726`; worker 7, compared with worker 3; planner export `checkpoint_check_20261118_235303`. Reader config: the bridge run's config_used/gesture_reader.json (window 1.0 s at 10.0 Hz, min_valid_fraction 0.6, point.arm_length_min 0.8, arm_length_in_shoulder_widths 1.683). Evaluation only.

## Q1: worker 7 (target), 2 asks; replay against the log: 37 readings equal, 0 differ

### ask serial 8 at J3, t 166.48 s, robot (17.48, 0.78) yaw 301.1; dialog result no_answer, read NONE

- (a) pan-tilt frames 79 in 11.4 s (6.91/s); frame interval median 0.111 s; processing (perception.csv total_ms) median 80 ms, max 287 ms; worker 7 in 37 of 79 frames; pan 0.0 deg, vertical field of view [60.0] deg (no zoom), tilt [0.0]; people in the frame: ['', 'track 111 = worker 7 (0.1 deg) track 121 = worker 4 (0.0 deg)', 'track 111 = worker 7 (0.2 deg) track 121 = worker 4 (0.0 deg)', 'track 111 = worker 7 (0.9 deg)']
- (b) frames while the worker gestured or held: 20; frames in the reader's 1.0 s window at those ticks: [4, 5] (needs 6); hands linked to the worker in 19 of 20
- (c) right arm while gesturing/holding: raised in 19, point_ok in 0; image arm length (shoulder widths) min / median / max 0.73 / 0.78 / 0.83 against 0.8; POINT cue failures: {'length': 18, 'elbow': 19, 'disagreement': 18}
- (d) readings at those frames: {'insufficient_history: fewer than 6 valid frames of 10 expected': 6, 'insufficient_history: raised right arm has fewer than 6 valid frames': 14}

### ask serial 9 at J3, t 177.91 s, robot (17.68, 1.43) yaw 289.5; dialog result no_answer, read NONE

- (a) pan-tilt frames 22 in 5.0 s (4.38/s); frame interval median 0.209 s; processing (perception.csv total_ms) median 209 ms, max 312 ms; worker 7 in 22 of 22 frames; pan 3.38 deg, vertical field of view [60.0] deg (no zoom), tilt [0.0]; people in the frame: ['track 126 = worker 7 (0.0 deg) track 133 = worker 4 (0.1 deg)', 'track 126 = worker 7 (0.1 deg) track 133 = worker 4 (0.1 deg)', 'track 126 = worker 7 (0.2 deg) track 133 = worker 4 (0.0 deg)', 'track 126 = worker 7 (0.2 deg) track 133 = worker 4 (0.1 deg)']
- (b) frames while the worker gestured or held: 20; frames in the reader's 1.0 s window at those ticks: [5, 6] (needs 6); hands linked to the worker in 20 of 20
- (c) right arm while gesturing/holding: raised in 18, point_ok in 0; image arm length (shoulder widths) min / median / max 0.34 / 0.36 / 0.36 against 0.8; POINT cue failures: {'length': 18, 'elbow': 18, 'disagreement': 18}
- (d) readings at those frames: {'NONE: no raised arm': 2, 'insufficient_history: fewer than 6 valid frames of 10 expected': 1, 'insufficient_history: raised right arm has fewer than 6 valid frames': 16, 'NONE: cues not met or classes ambiguous': 1}

## Q1: worker 3 (compare), 3 asks; replay against the log: 37 readings equal, 0 differ

### ask serial 3 at J1, t 72.58 s, robot (5.47, -1.27) yaw 210.9; dialog result accepted, read RIGHT

- (a) pan-tilt frames 306 in 46.1 s (6.64/s); frame interval median 0.119 s; processing (perception.csv total_ms) median 146 ms, max 314 ms; worker 3 in 89 of 306 frames; pan 0.0 deg, vertical field of view [53.357391357421875, 53.684234619140625, 54.4427490234375, 55.27519226074219, 56.601104736328125, 57.33970642089844, 57.87139892578125, 57.891998291015625, 57.90687561035156, 59.02862548828125, 59.200286865234375, 60.0] deg (no zoom), tilt [0.0, 0.799713134765625, 0.9033650755882263, 0.9049363136291504, 0.9111762046813965, 0.9423753619194031, 0.9647015333175659, 0.9782625436782837, 0.9842416048049927, 1.0783034563064575, 1.2130662202835083, 1.2356172800064087, 1.2640225887298584, 1.3242851495742798, 1.3715746402740479]; people in the frame: ['', 'track 15 = worker 3 (0.2 deg)', 'track 15 = worker 3 (1.8 deg)', 'track 15 = worker 3 (14.9 deg)']
- (b) frames while the worker gestured or held: 16; frames in the reader's 1.0 s window at those ticks: [6, 7, 8] (needs 6); hands linked to the worker in 5 of 16
- (c) right arm while gesturing/holding: raised in 15, point_ok in 15; image arm length (shoulder widths) min / median / max 1.46 / 1.76 / 1.78 against 0.8; POINT cue failures: none
- (d) readings at those frames: {'NONE: no raised arm': 1, 'NONE: moving, no hold yet': 7, 'POINT: ok': 6, 'NONE: cues not met or classes ambiguous': 2}

### ask serial 6 at J1, t 118.69 s, robot (5.90, -1.75) yaw 229.0; dialog result accepted, read RIGHT

- (a) pan-tilt frames 72 in 9.3 s (7.75/s); frame interval median 0.106 s; processing (perception.csv total_ms) median 73 ms, max 238 ms; worker 3 in 18 of 72 frames; pan -3.69 deg, vertical field of view [53.023223876953125, 53.878326416015625, 53.982696533203125, 55.86433410644531, 56.082916259765625, 57.86064147949219, 57.92243957519531, 58.07373046875, 60.0] deg (no zoom), tilt [0.0, 1.1700013875961304, 1.2279430627822876, 1.3143144845962524, 1.3167160749435425, 1.3362188339233398, 1.3541444540023804, 1.4103379249572754]; people in the frame: ['', 'track 91 = worker 3 (0.3 deg)', 'track 91 = worker 3 (0.4 deg)', 'track 91 = worker 3 (0.7 deg)']
- (b) frames while the worker gestured or held: 8; frames in the reader's 1.0 s window at those ticks: [5, 6, 7] (needs 6); hands linked to the worker in 5 of 8
- (c) right arm while gesturing/holding: raised in 3, point_ok in 3; image arm length (shoulder widths) min / median / max 0.99 / 1.51 / 1.70 against 0.8; POINT cue failures: none
- (d) readings at those frames: {'NONE: no raised arm': 3, 'NONE: moving, no hold yet': 1, 'POINT: ok': 1, 'insufficient_history: fewer than 6 valid frames of 10 expected': 1, 'insufficient_history: raised right arm has fewer than 6 valid frames': 2}

### ask serial 7 at J1, t 127.98 s, robot (5.33, -1.37) yaw 217.6; dialog result accepted, read RIGHT

- (a) pan-tilt frames 18 in 2.9 s (6.15/s); frame interval median 0.157 s; processing (perception.csv total_ms) median 152 ms, max 235 ms; worker 3 in 18 of 18 frames; pan 3.87 deg, vertical field of view [55.2685546875, 56.187744140625, 57.352294921875, 58.13140869140625, 60.0] deg (no zoom), tilt [0.0, 0.6552423238754272, 0.7204578518867493, 0.7500215768814087, 0.792560875415802, 0.8487339615821838, 0.9049363136291504, 1.0110114812850952, 1.048448085784912]; people in the frame: ['track 94 = worker 3 (0.7 deg)', 'track 94 = worker 3 (3.1 deg)', 'track 94 = worker 3 (3.2 deg)', 'track 94 = worker 3 (3.8 deg)']
- (b) frames while the worker gestured or held: 15; frames in the reader's 1.0 s window at those ticks: [6, 7, 8] (needs 6); hands linked to the worker in 12 of 15
- (c) right arm while gesturing/holding: raised in 15, point_ok in 15; image arm length (shoulder widths) min / median / max 1.73 / 1.78 / 1.92 against 0.8; POINT cue failures: none
- (d) readings at those frames: {'NONE: moving, no hold yet': 7, 'NONE: cues not met or classes ambiguous': 3, 'POINT: ok': 5}

## Q2: the angle between the pointed direction and the line from the worker to the camera, at every modelled ask (Unity's plans)

0 deg = the arm points straight at the camera, 180 = straight away. A level arm of 1.683 shoulder widths projects to at least arm_length_min 0.8 only when the angle is between 28.4 and 151.6 deg (shoulders square to the camera; the worker's stance and torso turn for a large angle narrow the shoulders and change this a little).

| spot | command | how it can be shown | asks | min / median / max (deg) | within 30 deg of the line (toward / away / either) | within 45 deg (toward / away / either) | below arm_length_min |
|---|---|---|---|---|---|---|---|
| checkpoint J1 FORWARD -> E1 | BACK | honest on a wrong branch; liar on the right branch | 640 | 14.5 / 87.3 / 160.2 | 160 / 160 / 320 | 320 / 320 / 640 | 320 |
| checkpoint J1 RIGHT -> J3 | BACK | honest on a wrong branch; liar on the right branch | 640 | 11.9 / 80.2 / 148.4 | 160 / 0 / 160 | 320 / 160 / 480 | 160 |
| checkpoint J2 RIGHT -> E2 | BACK | honest on a wrong branch; liar on the right branch | 640 | 14.5 / 87.3 / 160.2 | 160 / 160 / 320 | 320 / 320 / 640 | 320 |
| checkpoint J3 LEFT -> E3 | BACK | honest on a wrong branch; liar on the right branch | 640 | 14.5 / 87.3 / 160.2 | 160 / 160 / 320 | 320 / 320 / 640 | 320 |
| checkpoint J3 RIGHT -> E4 | BACK | honest on a wrong branch; liar on the right branch | 640 | 17.2 / 89.8 / 162.5 | 160 / 160 / 320 | 320 / 320 / 640 | 320 |
| checkpoint J4 LEFT -> E6 | BACK | honest on a wrong branch; liar on the right branch | 640 | 14.5 / 87.3 / 160.2 | 160 / 160 / 320 | 320 / 320 / 640 | 320 |
| checkpoint J4 RIGHT -> E5 | BACK | honest on a wrong branch; liar on the right branch | 640 | 17.2 / 89.8 / 162.5 | 160 / 160 / 320 | 320 / 320 / 640 | 320 |
| corridor A slot 1 | BACK | liar only (a node with one branch) | 480 | 98.9 / 123.9 / 168.1 | 0 / 80 / 80 | 0 / 160 / 160 | 80 |
| corridor A slot 2 | BACK | liar only (a node with one branch) | 480 | 75.6 / 101.2 / 126.9 | 0 / 0 / 0 | 0 / 0 / 0 | 0 |
| roadmap A slot 1 | BACK | liar only (a node with one branch) | 952 | 27.5 / 105.3 / 178.4 | 2 / 118 / 120 | 46 / 232 / 278 | 116 |
| roadmap A slot 2 | BACK | liar only (a node with one branch) | 946 | 24.3 / 105.1 / 167.2 | 26 / 22 / 48 | 58 / 88 / 146 | 36 |
| roadmap J1 slot 1 | BACK | never (a liar shows a wrong valid branch) | 948 | 117.8 / 146.3 / 175.9 | 0 / 404 / 404 | 0 / 700 / 700 | 374 |
| roadmap J1 slot 1 | POINT LEFT | branch | 948 | 94.1 / 123.7 / 152.2 | 0 / 4 / 4 | 0 / 254 / 254 | 2 |
| roadmap J1 slot 1 | POINT RIGHT | branch | 948 | 27.8 / 56.3 / 85.9 | 4 / 0 / 4 | 254 / 0 / 254 | 2 |
| roadmap J1 slot 2 | BACK | never (a liar shows a wrong valid branch) | 944 | 23.3 / 43.0 / 62.6 | 126 / 0 / 126 | 472 / 0 / 472 | 114 |
| roadmap J1 slot 2 | POINT LEFT | branch | 944 | 27.4 / 47.0 / 66.7 | 22 / 0 / 22 | 472 / 0 / 472 | 2 |
| roadmap J1 slot 2 | POINT RIGHT | branch | 944 | 113.3 / 132.9 / 152.6 | 0 / 22 / 22 | 0 / 472 / 472 | 2 |
| roadmap J2 slot 1 | BACK | honest when the robot arrives on a wrong path | 956 | 107.8 / 145.4 / 176.4 | 0 / 372 / 372 | 0 / 712 / 712 | 362 |
| roadmap J2 slot 1 | POINT RIGHT | branch | 956 | 17.8 / 63.8 / 154.4 | 24 / 32 / 56 | 178 / 68 / 246 | 44 |
| roadmap J2 slot 2 | BACK | honest when the robot arrives on a wrong path | 952 | 20.3 / 44.5 / 78.9 | 214 / 0 / 214 | 502 / 0 / 502 | 194 |
| roadmap J2 slot 2 | POINT RIGHT | branch | 952 | 11.1 / 126.2 / 150.3 | 68 / 2 / 70 | 88 / 366 / 454 | 62 |
| roadmap J3 slot 1 | BACK | honest when the robot arrives on a wrong path | 960 | 123.1 / 154.1 / 179.8 | 0 / 520 / 520 | 0 / 806 / 806 | 514 |
| roadmap J3 slot 1 | POINT LEFT | branch | 960 | 62.5 / 115.8 / 146.9 | 0 / 0 / 0 | 0 / 156 / 156 | 0 |
| roadmap J3 slot 1 | POINT RIGHT | branch | 960 | 33.1 / 64.2 / 117.5 | 0 / 0 / 0 | 156 / 0 / 156 | 0 |
| roadmap J3 slot 2 | BACK | honest when the robot arrives on a wrong path | 960 | 7.9 / 37.2 / 65.5 | 282 / 0 / 282 | 586 / 0 / 586 | 268 |
| roadmap J3 slot 2 | POINT LEFT | branch | 960 | 32.0 / 56.6 / 155.5 | 0 / 24 / 24 | 332 / 42 / 374 | 22 |
| roadmap J3 slot 2 | POINT RIGHT | branch | 960 | 24.5 / 123.3 / 148.0 | 24 / 0 / 24 | 42 / 332 / 374 | 22 |
| roadmap J4 slot 1 | BACK | honest when the robot arrives on a wrong path | 960 | 116.1 / 152.1 / 179.9 | 0 / 500 / 500 | 0 / 802 / 802 | 482 |
| roadmap J4 slot 1 | POINT LEFT | branch | 960 | 26.1 / 114.2 / 147.0 | 12 / 0 / 12 | 40 / 120 / 160 | 12 |
| roadmap J4 slot 1 | POINT RIGHT | branch | 960 | 33.0 / 65.8 / 153.9 | 0 / 12 / 12 | 120 / 40 / 160 | 12 |
| roadmap J4 slot 2 | BACK | honest when the robot arrives on a wrong path | 960 | 0.1 / 36.2 / 65.9 | 296 / 0 / 296 | 602 / 0 / 602 | 280 |
| roadmap J4 slot 2 | POINT LEFT | branch | 960 | 32.0 / 59.9 / 155.9 | 0 / 30 / 30 | 300 / 58 / 358 | 22 |
| roadmap J4 slot 2 | POINT RIGHT | branch | 960 | 24.1 / 120.1 / 148.0 | 30 / 0 / 30 | 58 / 300 / 358 | 22 |
| turn A slot 1 | BACK | liar only (a node with one branch) | 480 | 98.9 / 123.9 / 168.1 | 0 / 80 / 80 | 0 / 160 / 160 | 80 |
| turn A slot 2 | BACK | liar only (a node with one branch) | 480 | 75.6 / 101.2 / 126.9 | 0 / 0 / 0 | 0 / 0 / 0 | 0 |
| turn B slot 1 | BACK | liar only (a node with one branch) | 480 | 133.9 / 151.0 / 168.1 | 0 / 240 / 240 | 0 / 400 / 400 | 240 |
| turn B slot 1 | POINT RIGHT | branch | 480 | 43.9 / 61.0 / 78.1 | 0 / 0 / 0 | 80 / 0 / 80 | 0 |
| turn B slot 2 | BACK | liar only (a node with one branch) | 480 | 26.8 / 42.4 / 58.0 | 80 / 0 / 80 | 240 / 0 / 240 | 80 |
| turn B slot 2 | POINT RIGHT | branch | 480 | 116.8 / 132.4 / 148.0 | 0 / 0 / 0 | 0 / 240 / 240 | 0 |
| turn_left A slot 1 | BACK | liar only (a node with one branch) | 480 | 98.9 / 123.9 / 168.1 | 0 / 80 / 80 | 0 / 160 / 160 | 80 |
| turn_left A slot 2 | BACK | liar only (a node with one branch) | 480 | 75.6 / 101.2 / 126.9 | 0 / 0 / 0 | 0 / 0 / 0 | 0 |
| turn_left B slot 1 | BACK | liar only (a node with one branch) | 480 | 133.9 / 151.0 / 168.1 | 0 / 240 / 240 | 0 / 400 / 400 | 240 |
| turn_left B slot 1 | POINT LEFT | branch | 480 | 101.9 / 119.0 / 136.1 | 0 / 0 / 0 | 0 / 80 / 80 | 0 |
| turn_left B slot 2 | BACK | liar only (a node with one branch) | 480 | 26.8 / 42.4 / 58.0 | 80 / 0 / 80 | 240 / 0 / 240 | 80 |
| turn_left B slot 2 | POINT LEFT | branch | 480 | 32.0 / 47.6 / 63.2 | 0 / 0 / 0 | 240 / 0 / 240 | 0 |

Totals over every plan: BACK (honest J2-J4 / checkpoints): 10228 asks, 4264 within 30 deg of the line, 4180 below arm_length_min; BACK (liar only): 8590 asks, 1578 within 30 deg of the line, 1520 below arm_length_min; FORWARD (PROCEED): 13058 asks, 3604 within 30 deg of the line, 3516 below arm_length_min; POINT LEFT: 6692 asks, 92 within 30 deg of the line, 60 below arm_length_min; POINT RIGHT: 8600 asks, 218 within 30 deg of the line, 166 below arm_length_min

## Q2b: the same angle at the real POINT asks of the development sessions (truth + trail; read = export dialogs.csv)

Sessions of `step5_sessions.json`: ['A2_left', 'A2_right', 'A3', 'B1', 'B2_right', 'B2_right_off', 'smoke_t4_B3']. 42 POINT asks with a holding phase.

| angle to the camera line (deg) | asks | read as POINT | correct direction |
|---|---|---|---|
| 0-30 | 1 | 0 | 0 |
| 30-45 | 2 | 2 | 0 |
| 45-90 | 18 | 15 | 13 |
| 90-135 | 15 | 12 | 7 |
| 135-150 | 3 | 0 | 0 |
| 150-180 | 3 | 0 | 0 |

By the direction shown: BACK: 6 asks, angle min / median / max 89 / 107 / 164; FORWARD: 3 asks, angle min / median / max 51 / 106 / 123; LEFT: 11 asks, angle min / median / max 12 / 86 / 126; RIGHT: 22 asks, angle min / median / max 38 / 73 / 175

