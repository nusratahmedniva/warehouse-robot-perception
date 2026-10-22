# Trial analysis (vision (YOLO11s-pose arm direction + MediaPipe STOP))

Sessions: trials_development_Task1_20261021_215821. Task ['Task1'], mode ['development'], seed [1].

**Success 10/10 = 1.0** (Wilson 95 %: 0.7225-1.0); failures: none.

| goal B | SUCCESS | FAILURE |
|---|---|---|
| E1 | 10 | 0 |

Time per step (s, over runs):

| step | n | mean | median | max |
|---|---|---|---|---|
| navigate | 10 | 40.596 | 40.618 | 41.232 |
| scan | 10 | 1.283 | 1.273 | 1.337 |
| approach | 10 | 18.031 | 19.345 | 24.517 |
| ask | 10 | 1.957 | 2.05 | 2.629 |
| gesture | 10 | 6.409 | 7.556 | 12.086 |
| execute | 10 | 4.602 | 4.612 | 4.728 |
| safety stop (any reason) | 10 | 0.03 | 0.0 | 0.162 |
| stale-perception stops | 10 | 0.0 | 0.0 | 0 |
| total | 10 | 72.96 | 75.78 | 86.3 |
| time excl. stale stops | 10 | 72.96 | 75.78 | 86.3 |
| in motion | 10 | 49.38 | 49.8 | 51.98 |

Time excl. stale stops = total minus stale-perception stops (still includes scanning, asking and reading at junctions). In motion = Unity speed above 0.05 m/s. Across machines both are comparable; total time, stale-perception stops and inference times are not (they depend on inference speed).

Junctions: 30/30 read as shown; asks per junction {'1': 23, '2': 7}.

| shown \ read | NONE | LEFT | FORWARD_LEFT | FORWARD | FORWARD_RIGHT | RIGHT | STOP |
|---|---|---|---|---|---|---|---|
| FORWARD | 0 | 0 | 0 | 30 | 0 | 0 | 0 |

Speed m/s: average 0.304, max 0.8; turn rate deg/s: average 9.596, max 51.566; travelled / straight line: 1.103.
Final distance from B (successes): mean 0.052 m, max 0.074 m.

Inference time (ms, mean per run, then over runs):

| model | runs | mean | max |
|---|---|---|---|
| jpeg_decode | 10 | 6.331 | 6.997 |
| mediapipe/stop | 10 | 48.868 | 52.065 |
| total_per_frame | 10 | 88.262 | 90.362 |
| yolo11s-pose/cam360 | 10 | 58.66 | 59.958 |
| yolo11s-pose/gesture | 10 | 44.376 | 45.574 |

Round trip (Unity-measured) ms: mean of runs 1.659, max 233.301. Watchdog stops per run: {'n': 10, 'mean': 0.4, 'median': 0.0, 'min': 0, 'max': 1}.
Collisions: 0 (with a person: 0). Closest distance to a person (robot body to worker axis): min 1.303 m, mean 1.369 m.

