# Trial analysis (vision (YOLO11s-pose arm direction + MediaPipe STOP))

Sessions: trials_final_Task1_20261022_161544. Task ['Task1'], mode ['final'], seed [2].

**Success 10/10 = 1.0** (Wilson 95 %: 0.7225-1.0); failures: none.

| goal B | SUCCESS | FAILURE |
|---|---|---|
| E1 | 10 | 0 |

Time per step (s, over runs):

| step | n | mean | median | max |
|---|---|---|---|---|
| navigate | 10 | 40.201 | 40.203 | 40.363 |
| scan | 10 | 1.281 | 1.278 | 1.332 |
| approach | 10 | 14.898 | 14.904 | 15.045 |
| ask | 10 | 1.579 | 1.587 | 1.652 |
| gesture | 10 | 3.11 | 3.093 | 3.4 |
| execute | 10 | 4.745 | 4.768 | 4.811 |
| safety stop (any reason) | 10 | 0.005 | 0.0 | 0.052 |
| stale-perception stops | 10 | 0.0 | 0.0 | 0 |
| total | 10 | 65.862 | 65.89 | 66.14 |
| time excl. stale stops | 10 | 65.862 | 65.89 | 66.14 |
| in motion | 10 | 48.218 | 48.2 | 48.32 |

Time excl. stale stops = total minus stale-perception stops (still includes scanning, asking and reading at junctions). In motion = Unity speed above 0.05 m/s. Across machines both are comparable; total time, stale-perception stops and inference times are not (they depend on inference speed).

Junctions: 30/30 read as shown; asks per junction {'1': 30}.

| shown \ read | NONE | LEFT | FORWARD_LEFT | FORWARD | FORWARD_RIGHT | RIGHT | STOP |
|---|---|---|---|---|---|---|---|
| FORWARD | 0 | 0 | 0 | 30 | 0 | 0 | 0 |

Speed m/s: average 0.33, max 0.8; turn rate deg/s: average 8.939, max 51.566; travelled / straight line: 1.086.
Final distance from B (successes): mean 0.036 m, max 0.082 m.

Inference time (ms, mean per run, then over runs):

| model | runs | mean | max |
|---|---|---|---|
| jpeg_decode | 10 | 5.223 | 6.037 |
| mediapipe/stop | 10 | 28.466 | 36.963 |
| total_per_frame | 10 | 96.678 | 101.845 |
| yolo11s-pose/cam360 | 10 | 95.451 | 102.377 |
| yolo11s-pose/gesture | 10 | 57.324 | 62.287 |

Round trip (Unity-measured) ms: mean of runs 1.004, max 51.908. Watchdog stops per run: {'n': 10, 'mean': 0.0, 'median': 0.0, 'min': 0, 'max': 0}.
Collisions: 0 (with a person: 0). Closest distance to a person (robot body to worker axis): min 1.352 m, mean 1.376 m.

