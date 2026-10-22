# Trial analysis (vision (YOLO11s-pose arm direction + MediaPipe STOP))

Sessions: trials_development_Task1_20261021_025326. Task ['Task1'], mode ['development'], seed [1].

**Success 10/10 = 1.0** (Wilson 95 %: 0.7225-1.0); failures: none.

| goal B | SUCCESS | FAILURE |
|---|---|---|
| E1 | 10 | 0 |

Time per step (s, over runs):

| step | n | mean | median | max |
|---|---|---|---|---|
| navigate | 10 | 31.424 | 30.069 | 43.619 |
| scan | 10 | 0.439 | 0.44 | 0.505 |
| approach | 10 | 6.237 | 6.216 | 6.368 |
| ask | 10 | 0.536 | 0.54 | 0.568 |
| gesture | 10 | 1.109 | 1.102 | 1.26 |
| execute | 10 | 1.126 | 1.121 | 1.18 |
| safety stop (any reason) | 10 | 1.34 | 0.0 | 13.403 |
| stale-perception stops | 10 | 1.339 | 0.0 | 13.388 |
| total | 10 | 40.928 | 39.57 | 53.04 |
| time excl. stale stops | 10 | 39.589 | 39.57 | 39.92 |
| in motion | 10 | 35.026 | 34.9 | 36.2 |

Time excl. stale stops = total minus stale-perception stops (still includes scanning, asking and reading at junctions). In motion = Unity speed above 0.05 m/s. Across machines both are comparable; total time, stale-perception stops and inference times are not (they depend on inference speed).

Junctions: 10/10 read as shown; asks per junction {'1': 10}.

| shown \ read | NONE | LEFT | FORWARD_LEFT | FORWARD | FORWARD_RIGHT | RIGHT | STOP |
|---|---|---|---|---|---|---|---|
| FORWARD | 0 | 0 | 0 | 10 | 0 | 0 | 0 |

Speed m/s: average 0.508, max 0.8; turn rate deg/s: average 3.054, max 51.566; travelled / straight line: 1.031.
Final distance from B (successes): mean 0.038 m, max 0.057 m.

Inference time (ms, mean per run, then over runs):

| model | runs | mean | max |
|---|---|---|---|
| jpeg_decode | 10 | 5.82 | 6.717 |
| mediapipe/stop | 10 | 23.085 | 27.082 |
| total_per_frame | 10 | 61.283 | 83.009 |
| yolo11s-pose/cam360 | 10 | 61.205 | 110.636 |
| yolo11s-pose/gesture | 10 | 28.149 | 29.806 |

Round trip (Unity-measured) ms: mean of runs 1.215, max 330.609. Watchdog stops per run: {'n': 10, 'mean': 0.8, 'median': 0.0, 'min': 0, 'max': 5}.
Collisions: 0 (with a person: 0). Closest distance to a person (robot body to worker axis): min 1.157 m, mean 1.174 m.

