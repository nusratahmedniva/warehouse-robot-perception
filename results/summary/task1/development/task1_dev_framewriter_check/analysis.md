# Trial analysis (vision (YOLO11s-pose arm direction + MediaPipe STOP))

Sessions: trials_development_Task1_20261021_205126. Task ['Task1'], mode ['development'], seed [1].

**Success 1/1 = 1.0** (Wilson 95 %: 0.2065-1.0); failures: none.

| goal B | SUCCESS | FAILURE |
|---|---|---|
| E1 | 1 | 0 |

Time per step (s, over runs):

| step | n | mean | median | max |
|---|---|---|---|---|
| navigate | 1 | 37.406 | 37.406 | 37.406 |
| scan | 1 | 1.251 | 1.251 | 1.251 |
| approach | 1 | 20.683 | 20.683 | 20.683 |
| ask | 1 | 1.598 | 1.598 | 1.598 |
| gesture | 1 | 3.094 | 3.094 | 3.094 |
| execute | 1 | 3.955 | 3.955 | 3.955 |
| safety stop (any reason) | 1 | 0.398 | 0.398 | 0.398 |
| stale-perception stops | 1 | 0.402 | 0.402 | 0.402 |
| total | 1 | 68.12 | 68.12 | 68.12 |
| time excl. stale stops | 1 | 67.718 | 67.718 | 67.718 |
| in motion | 1 | 52.88 | 52.88 | 52.88 |

Time excl. stale stops = total minus stale-perception stops (still includes scanning, asking and reading at junctions). In motion = Unity speed above 0.05 m/s. Across machines both are comparable; total time, stale-perception stops and inference times are not (they depend on inference speed).

Junctions: 3/3 read as shown; asks per junction {'1': 3}.

| shown \ read | NONE | LEFT | FORWARD_LEFT | FORWARD | FORWARD_RIGHT | RIGHT | STOP |
|---|---|---|---|---|---|---|---|
| FORWARD | 0 | 0 | 0 | 3 | 0 | 0 | 0 |

Speed m/s: average 0.324, max 0.8; turn rate deg/s: average 6.327, max 51.566; travelled / straight line: 1.105.
Final distance from B (successes): mean 0.035 m, max 0.035 m.

Inference time (ms, mean per run, then over runs):

| model | runs | mean | max |
|---|---|---|---|
| jpeg_decode | 1 | 6.061 | 6.061 |
| mediapipe/stop | 1 | 31.527 | 31.527 |
| total_per_frame | 1 | 64.436 | 64.436 |
| yolo11s-pose/cam360 | 1 | 52.312 | 52.312 |
| yolo11s-pose/gesture | 1 | 29.464 | 29.464 |

Round trip (Unity-measured) ms: mean of runs 1.149, max 11.96. Watchdog stops per run: {'n': 1, 'mean': 2.0, 'median': 2, 'min': 2, 'max': 2}.
Collisions: 0 (with a person: 0). Closest distance to a person (robot body to worker axis): min 1.291 m, mean 1.291 m.

