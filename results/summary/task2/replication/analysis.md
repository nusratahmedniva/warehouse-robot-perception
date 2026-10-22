# Trial analysis (vision (YOLO11s-pose arm direction + MediaPipe STOP))

Sessions: trials_replication_Task2_20261022_180918. Task ['Task2'], mode ['replication'], seed [2].

**Success 10/10 = 1.0** (Wilson 95 %: 0.7225-1.0); failures: none.

| goal B | SUCCESS | FAILURE |
|---|---|---|
| E1 | 4 | 0 |
| E2 | 2 | 0 |
| E3 | 1 | 0 |
| E4 | 3 | 0 |

Time per step (s, over runs):

| step | n | mean | median | max |
|---|---|---|---|---|
| navigate | 10 | 39.494 | 32.883 | 54.8 |
| scan | 10 | 0.605 | 0.447 | 0.901 |
| approach | 10 | 9.158 | 6.55 | 13.156 |
| ask | 10 | 0.739 | 0.55 | 1.108 |
| gesture | 10 | 1.546 | 1.177 | 2.241 |
| execute | 10 | 2.146 | 1.151 | 3.863 |
| safety stop (any reason) | 10 | 0.0 | 0.0 | 0.0 |
| stale-perception stops | 10 | 0.0 | 0.0 | 0 |
| total | 10 | 53.722 | 42.48 | 75.9 |
| time excl. stale stops | 10 | 53.722 | 42.48 | 75.9 |
| in motion | 10 | 46.704 | 37.95 | 65.2 |

Time excl. stale stops = total minus stale-perception stops (still includes scanning, asking and reading at junctions). In motion = Unity speed above 0.05 m/s. Across machines both are comparable; total time, stale-perception stops and inference times are not (they depend on inference speed).

Junctions: 14/14 read as shown; asks per junction {'1': 14}.

| shown \ read | NONE | LEFT | FORWARD_LEFT | FORWARD | FORWARD_RIGHT | RIGHT | STOP |
|---|---|---|---|---|---|---|---|
| FORWARD | 0 | 0 | 0 | 5 | 0 | 0 | 0 |
| LEFT | 0 | 4 | 0 | 0 | 0 | 0 | 0 |
| RIGHT | 0 | 0 | 0 | 0 | 0 | 5 | 0 |

Speed m/s: average 0.516, max 0.8; turn rate deg/s: average 3.519, max 51.566; travelled / straight line: 1.3.
Final distance from B (successes): mean 0.028 m, max 0.04 m.

Inference time (ms, mean per run, then over runs):

| model | runs | mean | max |
|---|---|---|---|
| jpeg_decode | 10 | 4.939 | 5.298 |
| mediapipe/stop | 10 | 23.746 | 26.378 |
| total_per_frame | 10 | 69.802 | 77.231 |
| yolo11s-pose/cam360 | 10 | 68.666 | 71.911 |
| yolo11s-pose/gesture | 10 | 37.65 | 44.686 |

Round trip (Unity-measured) ms: mean of runs 1.011, max 238.227. Watchdog stops per run: {'n': 10, 'mean': 0.0, 'median': 0.0, 'min': 0, 'max': 0}.
Collisions: 0 (with a person: 0). Closest distance to a person (robot body to worker axis): min 1.002 m, mean 1.129 m.

