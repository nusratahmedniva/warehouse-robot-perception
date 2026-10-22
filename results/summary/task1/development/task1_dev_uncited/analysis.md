# Trial analysis (vision (YOLO11s-pose arm direction + MediaPipe STOP))

Sessions: trials_development_Task1_20261021_235000. Task ['Task1'], mode ['development'], seed [1].

**Success 1/1 = 1.0** (Wilson 95 %: 0.2065-1.0); failures: none.

| goal B | SUCCESS | FAILURE |
|---|---|---|
| E1 | 1 | 0 |

Time per step (s, over runs):

| step | n | mean | median | max |
|---|---|---|---|---|
| navigate | 1 | 40.165 | 40.165 | 40.165 |
| scan | 1 | 1.255 | 1.255 | 1.255 |
| approach | 1 | 15.109 | 15.109 | 15.109 |
| ask | 1 | 1.65 | 1.65 | 1.65 |
| gesture | 1 | 3.145 | 3.145 | 3.145 |
| execute | 1 | 4.772 | 4.772 | 4.772 |
| safety stop (any reason) | 1 | 0.0 | 0.0 | 0.0 |
| stale-perception stops | 1 | 0.0 | 0 | 0 |
| total | 1 | 66.18 | 66.18 | 66.18 |
| time excl. stale stops | 1 | 66.18 | 66.18 | 66.18 |
| in motion | 1 | 48.4 | 48.4 | 48.4 |

Time excl. stale stops = total minus stale-perception stops (still includes scanning, asking and reading at junctions). In motion = Unity speed above 0.05 m/s. Across machines both are comparable; total time, stale-perception stops and inference times are not (they depend on inference speed).

Junctions: 3/3 read as shown; asks per junction {'1': 3}.

| shown \ read | NONE | LEFT | FORWARD_LEFT | FORWARD | FORWARD_RIGHT | RIGHT | STOP |
|---|---|---|---|---|---|---|---|
| FORWARD | 0 | 0 | 0 | 3 | 0 | 0 | 0 |

Speed m/s: average 0.328, max 0.8; turn rate deg/s: average 8.836, max 51.566; travelled / straight line: 1.087.
Final distance from B (successes): mean 0.036 m, max 0.036 m.

Inference time (ms, mean per run, then over runs):

| model | runs | mean | max |
|---|---|---|---|
| jpeg_decode | 1 | 5.868 | 5.868 |
| mediapipe/stop | 1 | 38.072 | 38.072 |
| total_per_frame | 1 | 89.627 | 89.627 |
| yolo11s-pose/cam360 | 1 | 74.255 | 74.255 |
| yolo11s-pose/gesture | 1 | 48.596 | 48.596 |

Round trip (Unity-measured) ms: mean of runs 1.273, max 43.22. Watchdog stops per run: {'n': 1, 'mean': 1.0, 'median': 1, 'min': 1, 'max': 1}.
Collisions: 0 (with a person: 0). Closest distance to a person (robot body to worker axis): min 1.36 m, mean 1.36 m.

