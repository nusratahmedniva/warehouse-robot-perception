# Trial analysis (vision (YOLO11s-pose arm direction + MediaPipe STOP))

Sessions: trials_development_Task1_20261022_025616. Task ['Task1'], mode ['development'], seed [1].

**Success 10/10 = 1.0** (Wilson 95 %: 0.7225-1.0); failures: none.

| goal B | SUCCESS | FAILURE |
|---|---|---|
| E1 | 10 | 0 |

Time per step (s, over runs):

| step | n | mean | median | max |
|---|---|---|---|---|
| navigate | 10 | 40.224 | 40.203 | 40.326 |
| scan | 10 | 1.294 | 1.301 | 1.339 |
| approach | 10 | 14.804 | 14.805 | 15.022 |
| ask | 10 | 1.564 | 1.555 | 1.639 |
| gesture | 10 | 3.241 | 3.265 | 3.461 |
| execute | 10 | 4.728 | 4.746 | 4.796 |
| safety stop (any reason) | 10 | 0.0 | 0.0 | 0.0 |
| stale-perception stops | 10 | 0.0 | 0.0 | 0 |
| total | 10 | 65.882 | 65.88 | 66.18 |
| time excl. stale stops | 10 | 65.882 | 65.88 | 66.18 |
| in motion | 10 | 48.242 | 48.21 | 48.4 |

Time excl. stale stops = total minus stale-perception stops (still includes scanning, asking and reading at junctions). In motion = Unity speed above 0.05 m/s. Across machines both are comparable; total time, stale-perception stops and inference times are not (they depend on inference speed).

Junctions: 30/30 read as shown; asks per junction {'1': 30}.

| shown \ read | NONE | LEFT | FORWARD_LEFT | FORWARD | FORWARD_RIGHT | RIGHT | STOP |
|---|---|---|---|---|---|---|---|
| FORWARD | 0 | 0 | 0 | 30 | 0 | 0 | 0 |

Speed m/s: average 0.329, max 0.8; turn rate deg/s: average 8.904, max 51.566; travelled / straight line: 1.084.
Final distance from B (successes): mean 0.029 m, max 0.037 m.

Inference time (ms, mean per run, then over runs):

| model | runs | mean | max |
|---|---|---|---|
| jpeg_decode | 10 | 4.559 | 5.19 |
| mediapipe/stop | 10 | 26.912 | 30.133 |
| total_per_frame | 10 | 89.899 | 100.141 |
| yolo11s-pose/cam360 | 10 | 90.316 | 102.834 |
| yolo11s-pose/gesture | 10 | 52.784 | 62.192 |

Round trip (Unity-measured) ms: mean of runs 0.941, max 33.777. Watchdog stops per run: {'n': 10, 'mean': 0.0, 'median': 0.0, 'min': 0, 'max': 0}.
Collisions: 0 (with a person: 0). Closest distance to a person (robot body to worker axis): min 1.358 m, mean 1.377 m.

