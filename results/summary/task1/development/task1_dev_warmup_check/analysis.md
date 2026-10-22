# Trial analysis (vision (YOLO11s-pose arm direction + MediaPipe STOP))

Sessions: trials_development_Task1_20261021_203226. Task ['Task1'], mode ['development'], seed [1].

**Success 1/1 = 1.0** (Wilson 95 %: 0.2065-1.0); failures: none.

| goal B | SUCCESS | FAILURE |
|---|---|---|
| E1 | 1 | 0 |

Time per step (s, over runs):

| step | n | mean | median | max |
|---|---|---|---|---|
| navigate | 1 | 37.398 | 37.398 | 37.398 |
| scan | 1 | 1.251 | 1.251 | 1.251 |
| approach | 1 | 24.72 | 24.72 | 24.72 |
| ask | 1 | 2.087 | 2.087 | 2.087 |
| gesture | 1 | 7.572 | 7.572 | 7.572 |
| execute | 1 | 3.961 | 3.961 | 3.961 |
| safety stop (any reason) | 1 | 0.0 | 0.0 | 0.0 |
| stale-perception stops | 1 | 0.0 | 0 | 0 |
| total | 1 | 77.14 | 77.14 | 77.14 |
| time excl. stale stops | 1 | 77.14 | 77.14 | 77.14 |
| in motion | 1 | 53.8 | 53.8 | 53.8 |

Time excl. stale stops = total minus stale-perception stops (still includes scanning, asking and reading at junctions). In motion = Unity speed above 0.05 m/s. Across machines both are comparable; total time, stale-perception stops and inference times are not (they depend on inference speed).

Junctions: 3/3 read as shown; asks per junction {'1': 2, '2': 1}.

| shown \ read | NONE | LEFT | FORWARD_LEFT | FORWARD | FORWARD_RIGHT | RIGHT | STOP |
|---|---|---|---|---|---|---|---|
| FORWARD | 0 | 0 | 0 | 3 | 0 | 0 | 0 |

Speed m/s: average 0.294, max 0.8; turn rate deg/s: average 7.848, max 51.566; travelled / straight line: 1.133.
Final distance from B (successes): mean 0.054 m, max 0.054 m.

Inference time (ms, mean per run, then over runs):

| model | runs | mean | max |
|---|---|---|---|
| jpeg_decode | 1 | 5.25 | 5.25 |
| mediapipe/stop | 1 | 27.248 | 27.248 |
| total_per_frame | 1 | 57.964 | 57.964 |
| yolo11s-pose/cam360 | 1 | 51.191 | 51.191 |
| yolo11s-pose/gesture | 1 | 25.326 | 25.326 |

Round trip (Unity-measured) ms: mean of runs 1.106, max 31.393. Watchdog stops per run: {'n': 1, 'mean': 1.0, 'median': 1, 'min': 1, 'max': 1}.
Collisions: 0 (with a person: 0). Closest distance to a person (robot body to worker axis): min 1.255 m, mean 1.255 m.

