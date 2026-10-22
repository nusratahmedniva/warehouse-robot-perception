# Trial analysis (vision (YOLO11s-pose arm direction + MediaPipe STOP))

Sessions: trials_development_Task1_20261022_021648. Task ['Task1'], mode ['development'], seed [1].

**Success 1/1 = 1.0** (Wilson 95 %: 0.2065-1.0); failures: none.

| goal B | SUCCESS | FAILURE |
|---|---|---|
| E1 | 1 | 0 |

Time per step (s, over runs):

| step | n | mean | median | max |
|---|---|---|---|---|
| navigate | 1 | 40.328 | 40.328 | 40.328 |
| scan | 1 | 1.244 | 1.244 | 1.244 |
| approach | 1 | 14.676 | 14.676 | 14.676 |
| ask | 1 | 1.622 | 1.622 | 1.622 |
| gesture | 1 | 3.107 | 3.107 | 3.107 |
| execute | 1 | 4.727 | 4.727 | 4.727 |
| safety stop (any reason) | 1 | 0.0 | 0.0 | 0.0 |
| stale-perception stops | 1 | 0.0 | 0 | 0 |
| total | 1 | 65.74 | 65.74 | 65.74 |
| time excl. stale stops | 1 | 65.74 | 65.74 | 65.74 |
| in motion | 1 | 47.9 | 47.9 | 47.9 |

Time excl. stale stops = total minus stale-perception stops (still includes scanning, asking and reading at junctions). In motion = Unity speed above 0.05 m/s. Across machines both are comparable; total time, stale-perception stops and inference times are not (they depend on inference speed).

Junctions: 3/3 read as shown; asks per junction {'1': 3}.

| shown \ read | NONE | LEFT | FORWARD_LEFT | FORWARD | FORWARD_RIGHT | RIGHT | STOP |
|---|---|---|---|---|---|---|---|
| FORWARD | 0 | 0 | 0 | 3 | 0 | 0 | 0 |

Speed m/s: average 0.329, max 0.8; turn rate deg/s: average 8.944, max 51.566; travelled / straight line: 1.082.
Final distance from B (successes): mean 0.039 m, max 0.039 m.

Inference time (ms, mean per run, then over runs):

| model | runs | mean | max |
|---|---|---|---|
| jpeg_decode | 1 | 5.521 | 5.521 |
| mediapipe/stop | 1 | 32.56 | 32.56 |
| total_per_frame | 1 | 75.207 | 75.207 |
| yolo11s-pose/cam360 | 1 | 60.767 | 60.767 |
| yolo11s-pose/gesture | 1 | 40.184 | 40.184 |

Round trip (Unity-measured) ms: mean of runs 1.188, max 41.23. Watchdog stops per run: {'n': 1, 'mean': 0.0, 'median': 0, 'min': 0, 'max': 0}.
Collisions: 0 (with a person: 0). Closest distance to a person (robot body to worker axis): min 1.42 m, mean 1.42 m.

