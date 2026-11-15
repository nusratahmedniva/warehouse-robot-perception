# Skinning check: forearm volume and torso rigidity (torso_calibration, 2026-11-15T00:44:24)

experiments_ab.md section 12 addendum 5. Reference: the idle pose just before each take's request. Forearm: vertices bound mainly to the gesturing LowerArm (>= 0.5) in 5 bands along elbow to wrist (bands under 8 vertices skipped); each band's mean distance from the elbow-to-wrist line over its reference; the narrowest must keep >= 0.70. Torso: vertices bound mainly to Hips, Spine, Chest, UpperChest (>= 0.5), each in its own bone's frame; the rule (addendum 7) applies to the torso core (outside 0.4 Lu of both UpperArm bones): core p95 displacement < 1.00 cm; the whole torso's p95 is information. Worst values over every measured frame of every take, both arms.

| look | kind | command | frames | forearm vertices | forearm narrowest band (ratio, min) | torso vertices (core) | torso core p95 max (cm) | torso core max (cm) | whole torso p95 (cm, info) | pass |
|---|---|---|---|---|---|---|---|---|---|---|
| mixamo_worker | realistic_human | POINT | 60 | 187 | 0.82 | 3082 (3079) | 0.98 | 1.84 | 0.99 | yes |
| mixamo_worker | realistic_human | PROCEED | 30 | 187 | 0.84 | 3082 (3076) | 0.83 | 1.61 | 0.83 | yes |
| mixamo_worker | realistic_human | WAIT | 30 | 187 | 0.87 | 3082 (3078) | 0.69 | 4.67 | 0.70 | yes |
| mixamo_worker | realistic_human | STOP | 30 | 187 | 0.93 | 3082 (3073) | 0.78 | 1.57 | 0.78 | yes |
| sunbox_m1 | stylised_human | POINT | 60 | 207 | 0.89 | 1774 (1773) | 1.28 | 2.83 | 1.29 | **no** |
| sunbox_m1 | stylised_human | PROCEED | 30 | 207 | 0.84 | 1774 (1773) | 1.65 | 3.75 | 1.66 | **no** |
| sunbox_m1 | stylised_human | WAIT | 30 | 207 | 0.84 | 1774 (1773) | 1.11 | 5.50 | 1.11 | **no** |
| sunbox_m1 | stylised_human | STOP | 30 | 207 | 0.94 | 1774 (1773) | 1.61 | 3.62 | 1.61 | **no** |
| sunbox_f1 | stylised_human | POINT | 60 | 191 | 0.88 | 1901 (1887) | 1.67 | 3.15 | 1.67 | **no** |
| sunbox_f1 | stylised_human | PROCEED | 30 | 191 | 0.85 | 1901 (1887) | 1.39 | 2.41 | 1.37 | **no** |
| sunbox_f1 | stylised_human | WAIT | 30 | 191 | 0.85 | 1901 (1886) | 1.62 | 3.08 | 1.62 | **no** |
| sunbox_f1 | stylised_human | STOP | 30 | 191 | 0.94 | 1901 (1886) | 1.15 | 2.23 | 1.15 | **no** |
| sunbox_f2 | stylised_human | POINT | 60 | 96 | 0.90 | 2202 (2182) | 1.42 | 3.10 | 1.42 | **no** |
| sunbox_f2 | stylised_human | PROCEED | 30 | 96 | 0.85 | 2202 (2183) | 0.61 | 1.10 | 0.62 | yes |
| sunbox_f2 | stylised_human | WAIT | 30 | 96 | 0.86 | 2202 (2185) | 1.31 | 3.57 | 1.33 | **no** |
| sunbox_f2 | stylised_human | STOP | 30 | 96 | 0.95 | 2202 (2171) | 1.12 | 2.10 | 1.12 | **no** |
| sunbox_m2 | stylised_human | POINT | 60 | 109 | 0.91 | 2101 (2094) | 1.45 | 3.21 | 1.47 | **no** |
| sunbox_m2 | stylised_human | PROCEED | 30 | 109 | 0.85 | 2101 (2095) | 1.34 | 2.97 | 1.33 | **no** |
| sunbox_m2 | stylised_human | WAIT | 30 | 109 | 0.85 | 2101 (2091) | 1.53 | 6.65 | 1.53 | **no** |
| sunbox_m2 | stylised_human | STOP | 30 | 109 | 0.95 | 2101 (2093) | 1.38 | 3.20 | 1.38 | **no** |
| sunbox_m_shirt_white | stylised_human | POINT | 60 | 207 | 0.89 | 1774 (1771) | 1.37 | 3.06 | 1.41 | **no** |
| sunbox_m_shirt_white | stylised_human | PROCEED | 30 | 207 | 0.84 | 1774 (1770) | 0.62 | 1.20 | 0.62 | yes |
| sunbox_m_shirt_white | stylised_human | WAIT | 30 | 207 | 0.83 | 1774 (1771) | 1.17 | 4.60 | 1.19 | **no** |
| sunbox_m_shirt_white | stylised_human | STOP | 30 | 207 | 0.95 | 1774 (1771) | 0.97 | 1.74 | 0.97 | yes |
| sunbox_m_tshirt_black | stylised_human | POINT | 60 | 109 | 0.90 | 2101 (2095) | 1.50 | 3.34 | 1.52 | **no** |
| sunbox_m_tshirt_black | stylised_human | PROCEED | 30 | 109 | 0.84 | 2101 (2094) | 1.20 | 2.70 | 1.20 | **no** |
| sunbox_m_tshirt_black | stylised_human | WAIT | 30 | 109 | 0.84 | 2101 (2094) | 1.58 | 6.01 | 1.66 | **no** |
| sunbox_m_tshirt_black | stylised_human | STOP | 30 | 109 | 0.95 | 2101 (2097) | 1.57 | 3.44 | 1.56 | **no** |
| sunbox_m_shirt_plaid | stylised_human | POINT | 60 | 207 | 0.88 | 1774 (1773) | 1.61 | 3.58 | 1.63 | **no** |
| sunbox_m_shirt_plaid | stylised_human | PROCEED | 30 | 207 | 0.83 | 1774 (1770) | 0.86 | 1.87 | 0.86 | yes |
| sunbox_m_shirt_plaid | stylised_human | WAIT | 30 | 207 | 0.83 | 1774 (1771) | 0.75 | 4.32 | 0.75 | yes |
| sunbox_m_shirt_plaid | stylised_human | STOP | 30 | 207 | 0.96 | 1774 (1771) | 1.52 | 3.41 | 1.52 | **no** |
| sunbox_f_shirt_white | stylised_human | POINT | 60 | 191 | 0.89 | 1729 (1714) | 1.53 | 2.69 | 1.52 | **no** |
| sunbox_f_shirt_white | stylised_human | PROCEED | 30 | 191 | 0.85 | 1729 (1710) | 0.87 | 1.43 | 0.87 | yes |
| sunbox_f_shirt_white | stylised_human | WAIT | 30 | 191 | 0.85 | 1729 (1713) | 1.32 | 3.61 | 1.31 | **no** |
| sunbox_f_shirt_white | stylised_human | STOP | 30 | 191 | 0.95 | 1729 (1711) | 1.22 | 2.12 | 1.22 | **no** |
| sunbox_f_dress_red | stylised_human | POINT | 60 | 96 | 0.91 | 1704 (1693) | 1.29 | 2.50 | 1.29 | **no** |
| sunbox_f_dress_red | stylised_human | PROCEED | 30 | 96 | 0.86 | 1704 (1691) | 1.28 | 2.31 | 1.28 | **no** |
| sunbox_f_dress_red | stylised_human | WAIT | 30 | 96 | 0.85 | 1704 (1692) | 1.47 | 4.13 | 1.47 | **no** |
| sunbox_f_dress_red | stylised_human | STOP | 30 | 96 | 0.97 | 1704 (1672) | 1.25 | 2.22 | 1.22 | **no** |
| sunbox_f_shirt_plaid | stylised_human | POINT | 60 | 191 | 0.89 | 1901 (1886) | 1.70 | 3.07 | 1.69 | **no** |
| sunbox_f_shirt_plaid | stylised_human | PROCEED | 30 | 191 | 0.86 | 1901 (1886) | 1.46 | 2.46 | 1.45 | **no** |
| sunbox_f_shirt_plaid | stylised_human | WAIT | 30 | 191 | 0.85 | 1901 (1884) | 1.17 | 3.57 | 1.16 | **no** |
| sunbox_f_shirt_plaid | stylised_human | STOP | 30 | 191 | 0.94 | 1901 (1886) | 1.65 | 3.02 | 1.65 | **no** |

Failures (first failing frame of each failing take):

- sunbox_m1 POINT: left point_mixamo_01: torso deforms: forearm 0.95, torso p95 1.28 cm, max 2.83 cm; left point_ik_01: torso deforms: forearm 0.98, torso p95 1.24 cm, max 2.62 cm; right point_ik_01: torso deforms: forearm 0.97, torso p95 1.25 cm, max 2.78 cm
- sunbox_m1 PROCEED: left proceed_ik_01: torso deforms: forearm 0.89, torso p95 1.65 cm, max 3.75 cm
- sunbox_m1 WAIT: left wait_ik_01: torso deforms: forearm 0.89, torso p95 1.11 cm, max 2.50 cm; right wait_ik_02: torso deforms: forearm 0.89, torso p95 1.04 cm, max 1.83 cm
- sunbox_m1 STOP: left stop_ik_01: torso deforms: forearm 0.99, torso p95 1.61 cm, max 3.62 cm; right stop_ik_02: torso deforms: forearm 0.94, torso p95 1.12 cm, max 2.42 cm
- sunbox_f1 POINT: left point_mixamo_01: torso deforms: forearm 0.95, torso p95 1.49 cm, max 2.57 cm; left point_mixamo_02: torso deforms: forearm 0.92, torso p95 1.59 cm, max 2.81 cm; right point_mixamo_01: torso deforms: forearm 0.94, torso p95 1.59 cm, max 2.76 cm; right point_mixamo_02: torso deforms: forearm 0.88, torso p95 1.67 cm, max 3.15 cm; right point_ik_01: torso deforms: forearm 0.99, torso p95 1.44 cm, max 2.51 cm
- sunbox_f1 PROCEED: left proceed_ik_02: torso deforms: forearm 0.87, torso p95 1.02 cm, max 2.15 cm; right proceed_ik_03: torso deforms: forearm 0.87, torso p95 1.39 cm, max 2.41 cm
- sunbox_f1 WAIT: left wait_ik_02: torso deforms: forearm 0.90, torso p95 1.62 cm, max 2.91 cm; right wait_raise_01: torso deforms: forearm 0.85, torso p95 1.04 cm, max 3.08 cm
- sunbox_f1 STOP: left stop_ik_02: torso deforms: forearm 0.94, torso p95 1.15 cm, max 2.23 cm
- sunbox_f2 POINT: left point_mixamo_01: torso deforms: forearm 0.96, torso p95 1.33 cm, max 2.75 cm; right point_mixamo_01: torso deforms: forearm 0.95, torso p95 1.18 cm, max 2.22 cm; right point_mixamo_02: torso deforms: forearm 0.90, torso p95 1.39 cm, max 3.10 cm; right point_ik_01: torso deforms: forearm 0.99, torso p95 1.42 cm, max 3.09 cm
- sunbox_f2 WAIT: left wait_ik_01: torso deforms: forearm 0.88, torso p95 1.14 cm, max 2.35 cm; left wait_raise_01: torso deforms: forearm 0.86, torso p95 1.31 cm, max 3.57 cm
- sunbox_f2 STOP: right stop_ik_03: torso deforms: forearm 1.00, torso p95 1.12 cm, max 2.10 cm
- sunbox_m2 POINT: left point_mixamo_01: torso deforms: forearm 0.95, torso p95 1.45 cm, max 3.21 cm; left point_mixamo_02: torso deforms: forearm 0.93, torso p95 1.13 cm, max 2.49 cm; left point_ik_01: torso deforms: forearm 0.98, torso p95 1.01 cm, max 1.97 cm
- sunbox_m2 PROCEED: left proceed_ik_02: torso deforms: forearm 0.88, torso p95 1.34 cm, max 2.97 cm
- sunbox_m2 WAIT: left wait_ik_02: torso deforms: forearm 0.87, torso p95 1.10 cm, max 2.43 cm; right wait_ik_02: torso deforms: forearm 0.88, torso p95 1.53 cm, max 3.45 cm
- sunbox_m2 STOP: left stop_ik_01: torso deforms: forearm 0.95, torso p95 1.38 cm, max 3.20 cm; right stop_ik_02: torso deforms: forearm 0.98, torso p95 1.33 cm, max 3.03 cm
- sunbox_m_shirt_white POINT: left point_mixamo_01: torso deforms: forearm 0.95, torso p95 1.37 cm, max 3.06 cm; right point_mixamo_01: torso deforms: forearm 0.94, torso p95 1.03 cm, max 1.78 cm
- sunbox_m_shirt_white WAIT: right wait_ik_02: torso deforms: forearm 0.88, torso p95 1.17 cm, max 2.48 cm
- sunbox_m_tshirt_black POINT: left point_mixamo_01: torso deforms: forearm 0.95, torso p95 1.50 cm, max 3.34 cm; left point_mixamo_02: torso deforms: forearm 0.93, torso p95 1.07 cm, max 2.35 cm; right point_mixamo_01: torso deforms: forearm 0.94, torso p95 1.43 cm, max 3.15 cm; right point_mixamo_02: torso deforms: forearm 0.91, torso p95 1.08 cm, max 2.36 cm; right point_ik_01: torso deforms: forearm 0.98, torso p95 1.02 cm, max 1.90 cm
- sunbox_m_tshirt_black PROCEED: left proceed_ik_02: torso deforms: forearm 0.85, torso p95 1.04 cm, max 2.25 cm; right proceed_ik_03: torso deforms: forearm 0.87, torso p95 1.20 cm, max 2.70 cm
- sunbox_m_tshirt_black WAIT: left wait_ik_02: torso deforms: forearm 0.88, torso p95 1.41 cm, max 3.27 cm; right wait_raise_01: torso deforms: forearm 0.85, torso p95 1.58 cm, max 6.01 cm
- sunbox_m_tshirt_black STOP: left stop_ik_02: torso deforms: forearm 0.98, torso p95 1.38 cm, max 3.16 cm; right stop_ik_03: torso deforms: forearm 0.98, torso p95 1.57 cm, max 3.44 cm
- sunbox_m_shirt_plaid POINT: left point_mixamo_01: torso deforms: forearm 0.95, torso p95 1.61 cm, max 3.58 cm; right point_mixamo_01: torso deforms: forearm 0.94, torso p95 1.13 cm, max 2.45 cm; right point_mixamo_02: torso deforms: forearm 0.88, torso p95 1.36 cm, max 3.12 cm; right point_ik_01: torso deforms: forearm 0.97, torso p95 1.06 cm, max 2.35 cm
- sunbox_m_shirt_plaid STOP: right stop_ik_02: torso deforms: forearm 0.99, torso p95 1.52 cm, max 3.41 cm
- sunbox_f_shirt_white POINT: left point_mixamo_01: torso deforms: forearm 0.95, torso p95 1.53 cm, max 2.69 cm
- sunbox_f_shirt_white WAIT: left wait_ik_02: torso deforms: forearm 0.90, torso p95 1.32 cm, max 2.12 cm; right wait_ik_02: torso deforms: forearm 0.90, torso p95 1.28 cm, max 2.12 cm
- sunbox_f_shirt_white STOP: right stop_ik_03: torso deforms: forearm 0.99, torso p95 1.22 cm, max 2.12 cm
- sunbox_f_dress_red POINT: left point_ik_01: torso deforms: forearm 0.98, torso p95 1.25 cm, max 2.19 cm; right point_ik_01: torso deforms: forearm 0.97, torso p95 1.29 cm, max 2.50 cm
- sunbox_f_dress_red PROCEED: right proceed_ik_02: torso deforms: forearm 0.89, torso p95 1.28 cm, max 2.31 cm
- sunbox_f_dress_red WAIT: left wait_ik_01: torso deforms: forearm 0.87, torso p95 1.47 cm, max 2.98 cm
- sunbox_f_dress_red STOP: right stop_ik_01: torso deforms: forearm 1.00, torso p95 1.25 cm, max 2.22 cm
- sunbox_f_shirt_plaid POINT: left point_ik_01: torso deforms: forearm 0.98, torso p95 1.17 cm, max 2.54 cm; right point_mixamo_01: torso deforms: forearm 0.95, torso p95 1.11 cm, max 2.23 cm; right point_ik_01: torso deforms: forearm 0.98, torso p95 1.70 cm, max 3.07 cm
- sunbox_f_shirt_plaid PROCEED: left proceed_ik_01: torso deforms: forearm 0.86, torso p95 1.46 cm, max 2.46 cm
- sunbox_f_shirt_plaid WAIT: left wait_ik_01: torso deforms: forearm 0.88, torso p95 1.13 cm, max 2.20 cm; right wait_ik_01: torso deforms: forearm 0.88, torso p95 1.17 cm, max 2.51 cm
- sunbox_f_shirt_plaid STOP: right stop_ik_03: torso deforms: forearm 1.00, torso p95 1.65 cm, max 3.02 cm
