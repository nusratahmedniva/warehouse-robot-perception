# Skinning check: forearm volume and torso rigidity (decisions7, 2026-11-15T01:08:52)

experiments_ab.md section 12 addendum 5. Reference: the idle pose just before each take's request. Forearm: vertices bound mainly to the gesturing LowerArm (>= 0.5) in 5 bands along elbow to wrist (bands under 8 vertices skipped); each band's mean distance from the elbow-to-wrist line over its reference; the narrowest must keep >= 0.70. Torso: vertices bound mainly to Hips, Spine, Chest, UpperChest (>= 0.5), each in its own bone's frame; the rule (addendum 7) applies to the torso core (outside 0.4 Lu of both UpperArm bones): core p95 displacement < 2.125 cm; the whole torso's p95 is information. Worst values over every measured frame of every take, both arms.

| look | kind | command | frames | forearm vertices | forearm narrowest band (ratio, min) | torso vertices (core) | torso core p95 max (cm) | torso core max (cm) | whole torso p95 (cm, info) | pass |
|---|---|---|---|---|---|---|---|---|---|---|
| mixamo_worker | realistic_human | POINT | 60 | 187 | 0.82 | 3082 (3077) | 0.99 | 1.85 | 1.00 | yes |
| mixamo_worker | realistic_human | PROCEED | 30 | 187 | 0.84 | 3082 (3076) | 0.81 | 1.58 | 0.81 | yes |
| mixamo_worker | realistic_human | WAIT | 30 | 187 | 0.87 | 3082 (3078) | 0.73 | 4.63 | 0.74 | yes |
| mixamo_worker | realistic_human | STOP | 30 | 187 | 0.93 | 3082 (3073) | 0.76 | 1.59 | 0.76 | yes |
| sunbox_m1 | stylised_human | POINT | 60 | 207 | 0.89 | 1774 (1773) | 1.27 | 2.81 | 1.28 | yes |
| sunbox_m1 | stylised_human | PROCEED | 30 | 207 | 0.84 | 1774 (1773) | 1.71 | 3.81 | 1.71 | yes |
| sunbox_m1 | stylised_human | WAIT | 30 | 207 | 0.84 | 1774 (1773) | 1.03 | 5.50 | 1.03 | yes |
| sunbox_m1 | stylised_human | STOP | 30 | 207 | 0.94 | 1774 (1773) | 1.60 | 3.60 | 1.61 | yes |
| sunbox_f1 | stylised_human | POINT | 60 | 191 | 0.88 | 1901 (1887) | 1.67 | 3.14 | 1.67 | yes |
| sunbox_f1 | stylised_human | PROCEED | 30 | 191 | 0.85 | 1901 (1887) | 1.41 | 2.43 | 1.41 | yes |
| sunbox_f1 | stylised_human | WAIT | 30 | 191 | 0.85 | 1901 (1887) | 1.61 | 3.08 | 1.61 | yes |
| sunbox_f1 | stylised_human | STOP | 30 | 191 | 0.94 | 1901 (1886) | 1.21 | 2.29 | 1.18 | yes |
| sunbox_f2 | stylised_human | POINT | 60 | 96 | 0.90 | 2202 (2183) | 1.38 | 2.96 | 1.37 | yes |
| sunbox_f2 | stylised_human | PROCEED | 30 | 96 | 0.85 | 2202 (2182) | 0.67 | 1.15 | 0.66 | yes |
| sunbox_f2 | stylised_human | WAIT | 30 | 96 | 0.86 | 2202 (2188) | 1.26 | 3.57 | 1.28 | yes |
| sunbox_f2 | stylised_human | STOP | 30 | 96 | 0.95 | 2202 (2175) | 0.99 | 1.92 | 1.00 | yes |
| sunbox_m2 | stylised_human | POINT | 60 | 109 | 0.91 | 2101 (2094) | 1.46 | 3.22 | 1.47 | yes |
| sunbox_m2 | stylised_human | PROCEED | 30 | 109 | 0.84 | 2101 (2095) | 1.33 | 2.96 | 1.33 | yes |
| sunbox_m2 | stylised_human | WAIT | 30 | 109 | 0.85 | 2101 (2090) | 1.47 | 6.31 | 1.46 | yes |
| sunbox_m2 | stylised_human | STOP | 30 | 109 | 0.95 | 2101 (2093) | 1.52 | 3.58 | 1.52 | yes |
| sunbox_m_shirt_white | stylised_human | POINT | 60 | 207 | 0.89 | 1774 (1771) | 1.36 | 3.05 | 1.41 | yes |
| sunbox_m_shirt_white | stylised_human | PROCEED | 30 | 207 | 0.84 | 1774 (1770) | 0.62 | 1.23 | 0.62 | yes |
| sunbox_m_shirt_white | stylised_human | WAIT | 30 | 207 | 0.83 | 1774 (1771) | 1.25 | 4.68 | 1.25 | yes |
| sunbox_m_shirt_white | stylised_human | STOP | 30 | 207 | 0.95 | 1774 (1771) | 0.94 | 1.71 | 0.95 | yes |
| sunbox_m_tshirt_black | stylised_human | POINT | 60 | 109 | 0.90 | 2101 (2095) | 1.52 | 3.38 | 1.54 | yes |
| sunbox_m_tshirt_black | stylised_human | PROCEED | 30 | 109 | 0.83 | 2101 (2094) | 1.21 | 2.77 | 1.21 | yes |
| sunbox_m_tshirt_black | stylised_human | WAIT | 30 | 109 | 0.84 | 2101 (2094) | 1.64 | 6.12 | 1.67 | yes |
| sunbox_m_tshirt_black | stylised_human | STOP | 30 | 109 | 0.95 | 2101 (2096) | 1.62 | 3.54 | 1.62 | yes |
| sunbox_m_shirt_plaid | stylised_human | POINT | 60 | 207 | 0.88 | 1774 (1773) | 1.62 | 3.59 | 1.63 | yes |
| sunbox_m_shirt_plaid | stylised_human | PROCEED | 30 | 207 | 0.83 | 1774 (1770) | 0.83 | 1.76 | 0.83 | yes |
| sunbox_m_shirt_plaid | stylised_human | WAIT | 30 | 207 | 0.83 | 1774 (1770) | 0.72 | 4.42 | 0.72 | yes |
| sunbox_m_shirt_plaid | stylised_human | STOP | 30 | 207 | 0.96 | 1774 (1771) | 1.49 | 3.34 | 1.49 | yes |
| sunbox_f_shirt_white | stylised_human | POINT | 60 | 191 | 0.89 | 1729 (1714) | 1.55 | 2.77 | 1.54 | yes |
| sunbox_f_shirt_white | stylised_human | PROCEED | 29 | 191 | 0.85 | 1729 (1710) | 0.87 | 1.41 | 0.87 | yes |
| sunbox_f_shirt_white | stylised_human | WAIT | 30 | 191 | 0.85 | 1729 (1713) | 1.34 | 3.61 | 1.33 | yes |
| sunbox_f_shirt_white | stylised_human | STOP | 30 | 191 | 0.95 | 1729 (1711) | 1.24 | 2.15 | 1.24 | yes |
| sunbox_f_dress_red | stylised_human | POINT | 60 | 96 | 0.91 | 1704 (1693) | 1.28 | 2.45 | 1.28 | yes |
| sunbox_f_dress_red | stylised_human | PROCEED | 30 | 96 | 0.86 | 1704 (1692) | 1.21 | 2.12 | 1.19 | yes |
| sunbox_f_dress_red | stylised_human | WAIT | 30 | 96 | 0.85 | 1704 (1691) | 1.47 | 4.29 | 1.47 | yes |
| sunbox_f_dress_red | stylised_human | STOP | 30 | 96 | 0.97 | 1704 (1672) | 1.31 | 2.43 | 1.30 | yes |
| sunbox_f_shirt_plaid | stylised_human | POINT | 60 | 191 | 0.89 | 1901 (1886) | 1.70 | 3.07 | 1.69 | yes |
| sunbox_f_shirt_plaid | stylised_human | PROCEED | 30 | 191 | 0.86 | 1901 (1887) | 1.55 | 2.72 | 1.54 | yes |
| sunbox_f_shirt_plaid | stylised_human | WAIT | 30 | 191 | 0.84 | 1901 (1885) | 1.24 | 3.29 | 1.24 | yes |
| sunbox_f_shirt_plaid | stylised_human | STOP | 30 | 191 | 0.94 | 1901 (1886) | 1.67 | 3.17 | 1.67 | yes |
| anime_f_01 | anime | POINT | 60 | 436 | 0.82 | 1388 (1292) | 1.44 | 6.59 | 1.81 | yes |
| anime_f_01 | anime | PROCEED | 30 | 436 | 0.86 | 1388 (1289) | 1.35 | 2.98 | 1.32 | yes |
| anime_f_01 | anime | WAIT | 30 | 436 | 0.89 | 1388 (1286) | 0.87 | 4.99 | 1.02 | yes |
| anime_f_01 | anime | STOP | 30 | 436 | 0.92 | 1388 (1295) | 1.15 | 3.76 | 1.18 | yes |
| anime_f_02_outfit_short | anime | POINT | 60 | 344 | 0.87 | 1308 (1236) | 0.94 | 3.56 | 0.98 | yes |
| anime_f_02_outfit_short | anime | PROCEED | 30 | 344 | 0.90 | 1308 (1223) | 0.97 | 1.62 | 0.97 | yes |
| anime_f_02_outfit_short | anime | WAIT | 30 | 344 | 0.97 | 1308 (1233) | 0.65 | 3.33 | 0.68 | yes |
| anime_f_02_outfit_short | anime | STOP | 30 | 344 | 0.94 | 1308 (1233) | 0.68 | 2.49 | 0.71 | yes |
| anime_f_03_bangs_parted | anime | POINT | 60 | 436 | 0.82 | 1388 (1289) | 1.45 | 6.38 | 1.74 | yes |
| anime_f_03_bangs_parted | anime | PROCEED | 30 | 436 | 0.86 | 1388 (1283) | 1.18 | 2.09 | 1.20 | yes |
| anime_f_03_bangs_parted | anime | WAIT | 30 | 436 | 0.90 | 1388 (1291) | 1.37 | 4.97 | 1.60 | yes |
| anime_f_03_bangs_parted | anime | STOP | 30 | 436 | 0.92 | 1388 (1292) | 1.01 | 3.63 | 1.08 | yes |
| cartoon_boxo_01 | cartoon_non_human | POINT | 60 | 99 | 0.73 | 5128 (5128) | 0.00 | 1.05 | 0.00 | yes |
| cartoon_boxo_01 | cartoon_non_human | PROCEED | 30 | 99 | 0.78 | 5128 (5126) | 0.00 | 0.66 | 0.00 | yes |
| cartoon_boxo_01 | cartoon_non_human | WAIT | 30 | 99 | 0.72 | 5128 (5128) | 0.00 | 1.13 | 0.00 | yes |
| cartoon_boxo_01 | cartoon_non_human | STOP | 30 | 99 | 0.91 | 5128 (5128) | 0.00 | 0.53 | 0.00 | yes |
