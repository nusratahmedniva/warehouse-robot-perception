# Trial analysis (vision (YOLO11s-pose arm direction + MediaPipe STOP))

Sessions: trials_development_Task1_20261022_022631. Task ['Task1'], mode ['development'], seed [1].

**Success 5/5 = 1.0** (Wilson 95 %: 0.5655-1.0); failures: none.

| goal B | SUCCESS | FAILURE |
|---|---|---|
| E1 | 5 | 0 |

Time per step (s, over runs):

| step | n | mean | median | max |
|---|---|---|---|---|
| navigate | 5 | 40.258 | 40.243 | 40.309 |
| scan | 5 | 1.276 | 1.268 | 1.312 |
| approach | 5 | 14.551 | 14.488 | 14.759 |
| ask | 5 | 1.587 | 1.594 | 1.635 |
| gesture | 5 | 3.248 | 3.301 | 3.39 |
| execute | 5 | 4.779 | 4.8 | 4.807 |
| safety stop (any reason) | 5 | 0.0 | 0.0 | 0.0 |
| stale-perception stops | 5 | 0.0 | 0 | 0 |
| total | 5 | 65.744 | 65.66 | 66.14 |
| time excl. stale stops | 5 | 65.744 | 65.66 | 66.14 |
| in motion | 5 | 48.08 | 48.1 | 48.2 |

Time excl. stale stops = total minus stale-perception stops (still includes scanning, asking and reading at junctions). In motion = Unity speed above 0.05 m/s. Across machines both are comparable; total time, stale-perception stops and inference times are not (they depend on inference speed).

Junctions: 15/15 read as shown; asks per junction {'1': 15}.

| shown \ read | NONE | LEFT | FORWARD_LEFT | FORWARD | FORWARD_RIGHT | RIGHT | STOP |
|---|---|---|---|---|---|---|---|
| FORWARD | 0 | 0 | 0 | 15 | 0 | 0 | 0 |

Speed m/s: average 0.329, max 0.8; turn rate deg/s: average 8.891, max 51.566; travelled / straight line: 1.082.
Final distance from B (successes): mean 0.05 m, max 0.087 m.

Inference time (ms, mean per run, then over runs):

| model | runs | mean | max |
|---|---|---|---|
| jpeg_decode | 5 | 4.008 | 4.298 |
| mediapipe/stop | 5 | 23.53 | 24.825 |
| total_per_frame | 5 | 65.03 | 69.889 |
| yolo11s-pose/cam360 | 5 | 58.272 | 59.52 |
| yolo11s-pose/gesture | 5 | 37.501 | 43.589 |

Round trip (Unity-measured) ms: mean of runs 0.846, max 18.867. Watchdog stops per run: {'n': 5, 'mean': 0.0, 'median': 0, 'min': 0, 'max': 0}.
Collisions: 0 (with a person: 0). Closest distance to a person (robot body to worker axis): min 1.391 m, mean 1.413 m.

