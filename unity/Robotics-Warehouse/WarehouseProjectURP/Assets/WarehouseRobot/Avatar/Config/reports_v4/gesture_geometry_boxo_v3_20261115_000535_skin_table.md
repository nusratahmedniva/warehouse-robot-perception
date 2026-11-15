# Skinning check: forearm volume and torso rigidity (boxo_v3, 2026-11-15T00:05:35)

experiments_ab.md section 12 addendum 5. Reference: the idle pose just before each take's request. Forearm: vertices bound mainly to the gesturing LowerArm (>= 0.5) in 5 bands along elbow to wrist (bands under 8 vertices skipped); each band's mean distance from the elbow-to-wrist line over its reference; the narrowest must keep >= 0.70. Torso: vertices bound mainly to Hips, Spine, Chest, UpperChest (>= 0.5), each in its own bone's frame; p95 displacement < 1.0 cm. Worst values over every measured frame of every take, both arms.

| look | kind | command | frames | forearm vertices | forearm narrowest band (ratio, min) | torso vertices | torso p95 max (cm) | torso max (cm) | pass |
|---|---|---|---|---|---|---|---|---|---|
| mixamo_worker | realistic_human | POINT | 60 | 187 | 0.82 | 3082 | 1.02 | 1.97 | **no** |
| mixamo_worker | realistic_human | PROCEED | 30 | 187 | 0.84 | 3082 | 0.84 | 1.57 | yes |
| mixamo_worker | realistic_human | WAIT | 30 | 187 | 0.87 | 3082 | 0.71 | 4.68 | yes |
| mixamo_worker | realistic_human | STOP | 30 | 187 | 0.93 | 3082 | 0.80 | 1.53 | yes |
| sunbox_m1 | stylised_human | POINT | 60 | 207 | 0.89 | 1774 | 1.29 | 5.78 | **no** |
| sunbox_m1 | stylised_human | PROCEED | 30 | 207 | 0.84 | 1774 | 1.67 | 3.78 | **no** |
| sunbox_m1 | stylised_human | WAIT | 30 | 207 | 0.84 | 1774 | 1.06 | 5.49 | **no** |
| sunbox_m1 | stylised_human | STOP | 30 | 207 | 0.94 | 1774 | 1.60 | 4.72 | **no** |
| sunbox_f1 | stylised_human | POINT | 60 | 191 | 0.88 | 1901 | 1.68 | 3.14 | **no** |
| sunbox_f1 | stylised_human | PROCEED | 30 | 191 | 0.85 | 1901 | 1.43 | 2.44 | **no** |
| sunbox_f1 | stylised_human | WAIT | 30 | 191 | 0.85 | 1901 | 1.59 | 3.08 | **no** |
| sunbox_f1 | stylised_human | STOP | 30 | 191 | 0.94 | 1901 | 1.15 | 2.23 | **no** |
| sunbox_f2 | stylised_human | POINT | 60 | 96 | 0.90 | 2202 | 1.39 | 3.04 | **no** |
| sunbox_f2 | stylised_human | PROCEED | 30 | 96 | 0.85 | 2202 | 0.65 | 1.41 | yes |
| sunbox_f2 | stylised_human | WAIT | 30 | 96 | 0.86 | 2202 | 1.32 | 6.39 | **no** |
| sunbox_f2 | stylised_human | STOP | 30 | 96 | 0.95 | 2202 | 1.04 | 1.96 | **no** |
| sunbox_m2 | stylised_human | POINT | 60 | 109 | 0.91 | 2101 | 1.48 | 3.25 | **no** |
| sunbox_m2 | stylised_human | PROCEED | 30 | 109 | 0.84 | 2101 | 1.33 | 2.92 | **no** |
| sunbox_m2 | stylised_human | WAIT | 30 | 109 | 0.85 | 2101 | 1.50 | 6.50 | **no** |
| sunbox_m2 | stylised_human | STOP | 30 | 109 | 0.95 | 2101 | 1.44 | 3.35 | **no** |
| sunbox_m_shirt_white | stylised_human | POINT | 60 | 207 | 0.89 | 1774 | 1.41 | 5.68 | **no** |
| sunbox_m_shirt_white | stylised_human | PROCEED | 30 | 207 | 0.84 | 1774 | 0.63 | 1.59 | yes |
| sunbox_m_shirt_white | stylised_human | WAIT | 30 | 207 | 0.83 | 1774 | 1.24 | 6.75 | **no** |
| sunbox_m_shirt_white | stylised_human | STOP | 30 | 207 | 0.95 | 1774 | 0.90 | 4.62 | yes |
| sunbox_m_tshirt_black | stylised_human | POINT | 60 | 109 | 0.90 | 2101 | 1.52 | 3.34 | **no** |
| sunbox_m_tshirt_black | stylised_human | PROCEED | 30 | 109 | 0.84 | 2101 | 1.23 | 2.86 | **no** |
| sunbox_m_tshirt_black | stylised_human | WAIT | 30 | 109 | 0.84 | 2101 | 1.68 | 6.23 | **no** |
| sunbox_m_tshirt_black | stylised_human | STOP | 30 | 109 | 0.95 | 2101 | 1.71 | 3.72 | **no** |
| sunbox_m_shirt_plaid | stylised_human | POINT | 60 | 207 | 0.89 | 1774 | 1.62 | 6.11 | **no** |
| sunbox_m_shirt_plaid | stylised_human | PROCEED | 30 | 207 | 0.84 | 1774 | 0.77 | 1.61 | yes |
| sunbox_m_shirt_plaid | stylised_human | WAIT | 30 | 207 | 0.83 | 1774 | 0.85 | 6.68 | yes |
| sunbox_m_shirt_plaid | stylised_human | STOP | 30 | 207 | 0.96 | 1774 | 1.45 | 4.77 | **no** |
| sunbox_f_shirt_white | stylised_human | POINT | 60 | 191 | 0.89 | 1729 | 1.51 | 2.69 | **no** |
| sunbox_f_shirt_white | stylised_human | PROCEED | 30 | 191 | 0.85 | 1729 | 0.84 | 1.35 | yes |
| sunbox_f_shirt_white | stylised_human | WAIT | 30 | 191 | 0.85 | 1729 | 1.34 | 3.61 | **no** |
| sunbox_f_shirt_white | stylised_human | STOP | 30 | 191 | 0.95 | 1729 | 1.22 | 2.14 | **no** |
| sunbox_f_dress_red | stylised_human | POINT | 60 | 96 | 0.91 | 1704 | 1.27 | 2.41 | **no** |
| sunbox_f_dress_red | stylised_human | PROCEED | 30 | 96 | 0.86 | 1704 | 1.17 | 2.13 | **no** |
| sunbox_f_dress_red | stylised_human | WAIT | 30 | 96 | 0.85 | 1704 | 1.46 | 4.81 | **no** |
| sunbox_f_dress_red | stylised_human | STOP | 30 | 96 | 0.97 | 1704 | 1.33 | 2.53 | **no** |
| sunbox_f_shirt_plaid | stylised_human | POINT | 60 | 191 | 0.89 | 1901 | 1.70 | 3.07 | **no** |
| sunbox_f_shirt_plaid | stylised_human | PROCEED | 30 | 191 | 0.86 | 1901 | 1.55 | 2.75 | **no** |
| sunbox_f_shirt_plaid | stylised_human | WAIT | 30 | 191 | 0.84 | 1901 | 1.28 | 3.02 | **no** |
| sunbox_f_shirt_plaid | stylised_human | STOP | 30 | 191 | 0.94 | 1901 | 1.67 | 3.15 | **no** |
| anime_f_01 | anime | POINT | 60 | 436 | 0.82 | 1388 | 1.80 | 6.79 | **no** |
| anime_f_01 | anime | PROCEED | 30 | 436 | 0.86 | 1388 | 1.36 | 3.35 | **no** |
| anime_f_01 | anime | WAIT | 30 | 436 | 0.89 | 1388 | 0.98 | 6.20 | yes |
| anime_f_01 | anime | STOP | 30 | 436 | 0.92 | 1388 | 1.17 | 4.64 | **no** |
| anime_f_02_outfit_short | anime | POINT | 60 | 344 | 0.87 | 1308 | 0.97 | 4.83 | yes |
| anime_f_02_outfit_short | anime | PROCEED | 30 | 344 | 0.90 | 1308 | 0.93 | 2.01 | yes |
| anime_f_02_outfit_short | anime | WAIT | 30 | 344 | 0.97 | 1308 | 0.71 | 3.97 | yes |
| anime_f_02_outfit_short | anime | STOP | 30 | 344 | 0.94 | 1308 | 0.63 | 3.30 | yes |
| anime_f_03_bangs_parted | anime | POINT | 60 | 436 | 0.82 | 1388 | 1.75 | 6.52 | **no** |
| anime_f_03_bangs_parted | anime | PROCEED | 30 | 436 | 0.86 | 1388 | 1.24 | 2.67 | **no** |
| anime_f_03_bangs_parted | anime | WAIT | 30 | 436 | 0.90 | 1388 | 1.58 | 6.03 | **no** |
| anime_f_03_bangs_parted | anime | STOP | 30 | 436 | 0.92 | 1388 | 1.03 | 4.56 | **no** |
| cartoon_boxo_01 | cartoon_non_human | POINT | 60 | 99 | 0.73 | 3094 | 1.39 | 6.50 | **no** |
| cartoon_boxo_01 | cartoon_non_human | PROCEED | 30 | 99 | 0.78 | 3094 | 0.99 | 3.07 | yes |
| cartoon_boxo_01 | cartoon_non_human | WAIT | 30 | 99 | 0.72 | 3094 | 1.55 | 11.43 | **no** |
| cartoon_boxo_01 | cartoon_non_human | STOP | 30 | 99 | 0.91 | 3094 | 0.80 | 3.09 | yes |

Failures (first failing frame of each failing take):

- mixamo_worker POINT: right point_mixamo_01: torso deforms: forearm 0.86, torso p95 1.02 cm, max 1.89 cm
- sunbox_m1 POINT: left point_mixamo_01: torso deforms: forearm 0.95, torso p95 1.29 cm, max 2.83 cm; left point_ik_01: torso deforms: forearm 0.98, torso p95 1.27 cm, max 2.70 cm; right point_ik_01: torso deforms: forearm 0.97, torso p95 1.28 cm, max 5.23 cm
- sunbox_m1 PROCEED: left proceed_ik_01: torso deforms: forearm 0.90, torso p95 1.67 cm, max 3.78 cm
- sunbox_m1 WAIT: left wait_ik_01: torso deforms: forearm 0.89, torso p95 1.06 cm, max 2.40 cm; right wait_ik_02: torso deforms: forearm 0.89, torso p95 1.05 cm, max 5.38 cm
- sunbox_m1 STOP: left stop_ik_01: torso deforms: forearm 0.99, torso p95 1.60 cm, max 3.58 cm; right stop_ik_02: torso deforms: forearm 0.94, torso p95 1.14 cm, max 4.36 cm
- sunbox_f1 POINT: left point_mixamo_01: torso deforms: forearm 0.95, torso p95 1.49 cm, max 2.61 cm; left point_mixamo_02: torso deforms: forearm 0.92, torso p95 1.58 cm, max 2.81 cm; right point_mixamo_01: torso deforms: forearm 0.94, torso p95 1.57 cm, max 2.78 cm; right point_mixamo_02: torso deforms: forearm 0.88, torso p95 1.68 cm, max 3.14 cm; right point_ik_01: torso deforms: forearm 0.99, torso p95 1.42 cm, max 2.48 cm
- sunbox_f1 PROCEED: left proceed_ik_02: torso deforms: forearm 0.87, torso p95 1.04 cm, max 2.17 cm; right proceed_ik_03: torso deforms: forearm 0.87, torso p95 1.43 cm, max 2.44 cm
- sunbox_f1 WAIT: left wait_ik_02: torso deforms: forearm 0.90, torso p95 1.59 cm, max 2.84 cm; right wait_raise_01: torso deforms: forearm 0.85, torso p95 1.07 cm, max 3.08 cm
- sunbox_f1 STOP: left stop_ik_02: torso deforms: forearm 0.94, torso p95 1.15 cm, max 2.23 cm
- sunbox_f2 POINT: left point_mixamo_01: torso deforms: forearm 0.96, torso p95 1.37 cm, max 2.82 cm; right point_mixamo_01: torso deforms: forearm 0.95, torso p95 1.19 cm, max 2.31 cm; right point_mixamo_02: torso deforms: forearm 0.90, torso p95 1.36 cm, max 3.04 cm; right point_ik_01: torso deforms: forearm 0.99, torso p95 1.39 cm, max 2.97 cm
- sunbox_f2 WAIT: left wait_ik_01: torso deforms: forearm 0.88, torso p95 1.16 cm, max 2.38 cm; left wait_raise_01: torso deforms: forearm 0.86, torso p95 1.32 cm, max 3.57 cm
- sunbox_f2 STOP: right stop_ik_03: torso deforms: forearm 1.00, torso p95 1.04 cm, max 1.96 cm
- sunbox_m2 POINT: left point_mixamo_01: torso deforms: forearm 0.95, torso p95 1.48 cm, max 3.25 cm; left point_mixamo_02: torso deforms: forearm 0.93, torso p95 1.14 cm, max 2.54 cm
- sunbox_m2 PROCEED: left proceed_ik_02: torso deforms: forearm 0.88, torso p95 1.33 cm, max 2.92 cm
- sunbox_m2 WAIT: left wait_ik_02: torso deforms: forearm 0.87, torso p95 1.09 cm, max 2.41 cm; right wait_ik_02: torso deforms: forearm 0.88, torso p95 1.50 cm, max 3.38 cm
- sunbox_m2 STOP: left stop_ik_01: torso deforms: forearm 0.95, torso p95 1.44 cm, max 3.35 cm; right stop_ik_02: torso deforms: forearm 0.98, torso p95 1.31 cm, max 2.96 cm
- sunbox_m_shirt_white POINT: left point_mixamo_01: torso deforms: forearm 0.95, torso p95 1.41 cm, max 3.18 cm; right point_mixamo_01: torso deforms: forearm 0.94, torso p95 1.04 cm, max 5.55 cm
- sunbox_m_shirt_white WAIT: right wait_ik_02: torso deforms: forearm 0.88, torso p95 1.24 cm, max 4.37 cm
- sunbox_m_tshirt_black POINT: left point_mixamo_01: torso deforms: forearm 0.95, torso p95 1.52 cm, max 3.34 cm; left point_mixamo_02: torso deforms: forearm 0.93, torso p95 1.10 cm, max 2.44 cm; right point_mixamo_01: torso deforms: forearm 0.95, torso p95 1.52 cm, max 3.33 cm; right point_mixamo_02: torso deforms: forearm 0.90, torso p95 1.27 cm, max 2.77 cm; right point_ik_01: torso deforms: forearm 0.98, torso p95 1.05 cm, max 1.95 cm
- sunbox_m_tshirt_black PROCEED: left proceed_ik_02: torso deforms: forearm 0.85, torso p95 1.22 cm, max 2.65 cm; right proceed_ik_03: torso deforms: forearm 0.88, torso p95 1.23 cm, max 2.86 cm
- sunbox_m_tshirt_black WAIT: left wait_ik_02: torso deforms: forearm 0.88, torso p95 1.24 cm, max 2.87 cm; right wait_raise_01: torso deforms: forearm 0.85, torso p95 1.68 cm, max 6.23 cm
- sunbox_m_tshirt_black STOP: left stop_ik_02: torso deforms: forearm 0.98, torso p95 1.29 cm, max 2.98 cm; right stop_ik_03: torso deforms: forearm 0.98, torso p95 1.71 cm, max 3.72 cm
- sunbox_m_shirt_plaid POINT: left point_mixamo_01: torso deforms: forearm 0.95, torso p95 1.62 cm, max 3.56 cm; right point_mixamo_01: torso deforms: forearm 0.94, torso p95 1.08 cm, max 5.51 cm; right point_mixamo_02: torso deforms: forearm 0.89, torso p95 1.29 cm, max 6.11 cm; right point_ik_01: torso deforms: forearm 0.97, torso p95 1.18 cm, max 5.55 cm
- sunbox_m_shirt_plaid STOP: right stop_ik_02: torso deforms: forearm 0.99, torso p95 1.45 cm, max 4.77 cm
- sunbox_f_shirt_white POINT: left point_mixamo_01: torso deforms: forearm 0.95, torso p95 1.51 cm, max 2.69 cm
- sunbox_f_shirt_white WAIT: left wait_ik_02: torso deforms: forearm 0.90, torso p95 1.34 cm, max 2.15 cm; right wait_ik_02: torso deforms: forearm 0.90, torso p95 1.27 cm, max 2.11 cm
- sunbox_f_shirt_white STOP: right stop_ik_03: torso deforms: forearm 0.99, torso p95 1.22 cm, max 2.14 cm
- sunbox_f_dress_red POINT: left point_ik_01: torso deforms: forearm 0.98, torso p95 1.24 cm, max 2.21 cm; right point_ik_01: torso deforms: forearm 0.97, torso p95 1.27 cm, max 2.41 cm
- sunbox_f_dress_red PROCEED: right proceed_ik_02: torso deforms: forearm 0.88, torso p95 1.17 cm, max 2.09 cm
- sunbox_f_dress_red WAIT: left wait_ik_01: torso deforms: forearm 0.87, torso p95 1.46 cm, max 2.90 cm
- sunbox_f_dress_red STOP: right stop_ik_01: torso deforms: forearm 1.00, torso p95 1.33 cm, max 2.53 cm
- sunbox_f_shirt_plaid POINT: left point_ik_01: torso deforms: forearm 0.98, torso p95 1.17 cm, max 2.54 cm; right point_mixamo_01: torso deforms: forearm 0.95, torso p95 1.07 cm, max 2.20 cm; right point_ik_01: torso deforms: forearm 0.98, torso p95 1.70 cm, max 3.07 cm
- sunbox_f_shirt_plaid PROCEED: left proceed_ik_01: torso deforms: forearm 0.86, torso p95 1.55 cm, max 2.75 cm
- sunbox_f_shirt_plaid WAIT: left wait_ik_01: torso deforms: forearm 0.88, torso p95 1.28 cm, max 2.34 cm; right wait_ik_01: torso deforms: forearm 0.88, torso p95 1.01 cm, max 2.19 cm
- sunbox_f_shirt_plaid STOP: right stop_ik_01: torso deforms: forearm 0.96, torso p95 1.03 cm, max 1.97 cm; right stop_ik_03: torso deforms: forearm 1.00, torso p95 1.67 cm, max 3.15 cm
- anime_f_01 POINT: left point_mixamo_01: torso deforms: forearm 0.86, torso p95 1.03 cm, max 6.46 cm; left point_mixamo_01: torso deforms: forearm 0.85, torso p95 1.69 cm, max 5.73 cm; left point_mixamo_02: torso deforms: forearm 0.83, torso p95 1.38 cm, max 5.03 cm; right point_mixamo_01: torso deforms: forearm 0.85, torso p95 1.80 cm, max 6.25 cm; right point_mixamo_01: torso deforms: forearm 0.85, torso p95 1.01 cm, max 5.37 cm; right point_mixamo_02: torso deforms: forearm 0.83, torso p95 1.52 cm, max 6.79 cm; right point_ik_01: torso deforms: forearm 0.88, torso p95 1.09 cm, max 4.84 cm
- anime_f_01 PROCEED: left proceed_ik_02: torso deforms: forearm 0.87, torso p95 1.35 cm, max 3.29 cm; right proceed_ik_03: torso deforms: forearm 0.87, torso p95 1.31 cm, max 2.67 cm
- anime_f_01 STOP: left stop_ik_03: torso deforms: forearm 0.93, torso p95 1.17 cm, max 3.74 cm
- anime_f_03_bangs_parted POINT: left point_mixamo_01: torso deforms: forearm 0.85, torso p95 1.03 cm, max 6.52 cm; left point_mixamo_01: torso deforms: forearm 0.85, torso p95 1.75 cm, max 5.54 cm; left point_ik_01: torso deforms: forearm 0.88, torso p95 1.05 cm, max 5.11 cm; right point_mixamo_01: torso deforms: forearm 0.85, torso p95 1.39 cm, max 5.61 cm; right point_ik_01: torso deforms: forearm 0.88, torso p95 1.68 cm, max 5.71 cm
- anime_f_03_bangs_parted PROCEED: right proceed_ik_02: torso deforms: forearm 0.87, torso p95 1.24 cm, max 2.67 cm
- anime_f_03_bangs_parted WAIT: left wait_ik_01: torso deforms: forearm 0.91, torso p95 1.09 cm, max 5.04 cm; right wait_ik_02: torso deforms: forearm 0.92, torso p95 1.58 cm, max 4.86 cm
- anime_f_03_bangs_parted STOP: left stop_ik_01: torso deforms: forearm 0.93, torso p95 1.02 cm, max 4.18 cm; right stop_ik_02: torso deforms: forearm 0.94, torso p95 1.03 cm, max 4.56 cm
- cartoon_boxo_01 POINT: left point_mixamo_01: torso deforms: forearm 0.84, torso p95 1.38 cm, max 6.32 cm; right point_mixamo_01: torso deforms: forearm 0.74, torso p95 1.39 cm, max 6.50 cm; right point_mixamo_02: torso deforms: forearm 0.73, torso p95 1.23 cm, max 5.32 cm
- cartoon_boxo_01 WAIT: left wait_ik_02: torso deforms: forearm 0.77, torso p95 1.55 cm, max 6.19 cm; right wait_raise_01: torso deforms: forearm 0.72, torso p95 1.43 cm, max 11.43 cm
