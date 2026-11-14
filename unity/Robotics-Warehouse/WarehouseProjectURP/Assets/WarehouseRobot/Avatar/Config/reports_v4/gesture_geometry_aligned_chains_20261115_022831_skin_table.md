# Skinning check: forearm volume and torso rigidity (aligned_chains, 2026-11-15T02:28:31)

experiments_ab.md section 12 addendum 5. Reference: the idle pose just before each take's request. Forearm: vertices bound mainly to the gesturing LowerArm (>= 0.5) in 5 bands along elbow to wrist (bands under 8 vertices skipped); each band's mean distance from the elbow-to-wrist line over its reference; the narrowest must keep >= 0.70. Torso: vertices bound mainly to Hips, Spine, Chest, UpperChest (>= 0.5), each in its own bone's frame; the rule (addendum 7) applies to the torso core (outside 0.4 Lu of both UpperArm bones): core p95 displacement < 2.125 cm; the whole torso's p95 is information. Addendum 9: a palm-plate look's plate must keep its sorted extents within its rule's change in every command (the plate column). Worst values over every measured frame of every take, both arms.

| look | kind | command | frames | forearm vertices | forearm narrowest band (ratio, min) | torso vertices (core) | torso core p95 max (cm) | torso core max (cm) | whole torso p95 (cm, info) | plate shape change max | pass |
|---|---|---|---|---|---|---|---|---|---|---|---|
| mixamo_worker | realistic_human | POINT | 60 | 187 | 0.82 | 3082 (3079) | 0.98 | 1.84 | 0.99 | - | yes |
| mixamo_worker | realistic_human | PROCEED | 29 | 187 | 0.84 | 3082 (3076) | 0.83 | 1.61 | 0.83 | - | yes |
| mixamo_worker | realistic_human | WAIT | 30 | 187 | 0.87 | 3082 (3078) | 0.69 | 4.68 | 0.70 | - | yes |
| mixamo_worker | realistic_human | STOP | 30 | 187 | 0.93 | 3082 (3072) | 0.77 | 1.58 | 0.76 | - | yes |
| sunbox_m1 | stylised_human | POINT | 60 | 207 | 0.89 | 1774 (1771) | 1.25 | 2.79 | 1.28 | - | yes |
| sunbox_m1 | stylised_human | PROCEED | 30 | 207 | 0.84 | 1774 (1773) | 1.67 | 3.78 | 1.67 | - | yes |
| sunbox_m1 | stylised_human | WAIT | 30 | 207 | 0.83 | 1774 (1771) | 1.06 | 5.60 | 1.06 | - | yes |
| sunbox_m1 | stylised_human | STOP | 30 | 207 | 0.94 | 1774 (1773) | 1.66 | 3.71 | 1.66 | - | yes |
| sunbox_f1 | stylised_human | POINT | 60 | 191 | 0.88 | 1901 (1887) | 1.68 | 3.16 | 1.68 | - | yes |
| sunbox_f1 | stylised_human | PROCEED | 30 | 191 | 0.85 | 1901 (1887) | 1.37 | 2.42 | 1.35 | - | yes |
| sunbox_f1 | stylised_human | WAIT | 30 | 191 | 0.85 | 1901 (1886) | 1.65 | 3.11 | 1.65 | - | yes |
| sunbox_f1 | stylised_human | STOP | 30 | 191 | 0.94 | 1901 (1886) | 1.17 | 2.21 | 1.17 | - | yes |
| sunbox_f2 | stylised_human | POINT | 60 | 96 | 0.90 | 2202 (2182) | 1.44 | 3.14 | 1.42 | - | yes |
| sunbox_f2 | stylised_human | PROCEED | 30 | 96 | 0.85 | 2202 (2183) | 0.61 | 1.06 | 0.61 | - | yes |
| sunbox_f2 | stylised_human | WAIT | 30 | 96 | 0.86 | 2202 (2185) | 1.35 | 3.57 | 1.38 | - | yes |
| sunbox_f2 | stylised_human | STOP | 30 | 96 | 0.95 | 2202 (2171) | 1.09 | 2.02 | 1.10 | - | yes |
| sunbox_m2 | stylised_human | POINT | 60 | 109 | 0.91 | 2101 (2094) | 1.44 | 3.19 | 1.46 | - | yes |
| sunbox_m2 | stylised_human | PROCEED | 30 | 109 | 0.84 | 2101 (2095) | 1.33 | 2.93 | 1.32 | - | yes |
| sunbox_m2 | stylised_human | WAIT | 30 | 109 | 0.85 | 2101 (2091) | 1.49 | 6.42 | 1.48 | - | yes |
| sunbox_m2 | stylised_human | STOP | 30 | 109 | 0.95 | 2101 (2093) | 1.47 | 3.46 | 1.47 | - | yes |
| sunbox_m_shirt_white | stylised_human | POINT | 60 | 207 | 0.89 | 1774 (1771) | 1.36 | 3.05 | 1.41 | - | yes |
| sunbox_m_shirt_white | stylised_human | PROCEED | 30 | 207 | 0.84 | 1774 (1770) | 0.68 | 1.23 | 0.70 | - | yes |
| sunbox_m_shirt_white | stylised_human | WAIT | 30 | 207 | 0.83 | 1774 (1771) | 1.27 | 4.72 | 1.29 | - | yes |
| sunbox_m_shirt_white | stylised_human | STOP | 30 | 207 | 0.95 | 1774 (1771) | 0.92 | 1.67 | 0.93 | - | yes |
| sunbox_m_tshirt_black | stylised_human | POINT | 60 | 109 | 0.90 | 2101 (2095) | 1.49 | 3.32 | 1.51 | - | yes |
| sunbox_m_tshirt_black | stylised_human | PROCEED | 30 | 109 | 0.84 | 2101 (2094) | 1.16 | 2.61 | 1.16 | - | yes |
| sunbox_m_tshirt_black | stylised_human | WAIT | 30 | 109 | 0.84 | 2101 (2094) | 1.63 | 6.14 | 1.66 | - | yes |
| sunbox_m_tshirt_black | stylised_human | STOP | 30 | 109 | 0.95 | 2101 (2097) | 1.70 | 3.66 | 1.68 | - | yes |
| sunbox_m_shirt_plaid | stylised_human | POINT | 60 | 207 | 0.89 | 1774 (1773) | 1.61 | 3.58 | 1.62 | - | yes |
| sunbox_m_shirt_plaid | stylised_human | PROCEED | 30 | 207 | 0.83 | 1774 (1770) | 0.79 | 1.66 | 0.79 | - | yes |
| sunbox_m_shirt_plaid | stylised_human | WAIT | 30 | 207 | 0.83 | 1774 (1770) | 0.75 | 4.51 | 0.76 | - | yes |
| sunbox_m_shirt_plaid | stylised_human | STOP | 30 | 207 | 0.96 | 1774 (1771) | 1.47 | 3.32 | 1.48 | - | yes |
| sunbox_f_shirt_white | stylised_human | POINT | 60 | 191 | 0.89 | 1729 (1714) | 1.53 | 2.71 | 1.51 | - | yes |
| sunbox_f_shirt_white | stylised_human | PROCEED | 30 | 191 | 0.85 | 1729 (1710) | 0.80 | 1.24 | 0.80 | - | yes |
| sunbox_f_shirt_white | stylised_human | WAIT | 30 | 191 | 0.85 | 1729 (1713) | 1.35 | 3.61 | 1.33 | - | yes |
| sunbox_f_shirt_white | stylised_human | STOP | 30 | 191 | 0.95 | 1729 (1711) | 1.22 | 2.14 | 1.22 | - | yes |
| sunbox_f_dress_red | stylised_human | POINT | 60 | 96 | 0.91 | 1704 (1694) | 1.27 | 2.34 | 1.25 | - | yes |
| sunbox_f_dress_red | stylised_human | PROCEED | 30 | 96 | 0.85 | 1704 (1693) | 1.06 | 2.25 | 1.06 | - | yes |
| sunbox_f_dress_red | stylised_human | WAIT | 30 | 96 | 0.85 | 1704 (1690) | 1.46 | 4.18 | 1.43 | - | yes |
| sunbox_f_dress_red | stylised_human | STOP | 30 | 96 | 0.97 | 1704 (1673) | 1.32 | 2.45 | 1.31 | - | yes |
| sunbox_f_shirt_plaid | stylised_human | POINT | 60 | 191 | 0.89 | 1901 (1886) | 1.70 | 3.07 | 1.69 | - | yes |
| sunbox_f_shirt_plaid | stylised_human | PROCEED | 30 | 191 | 0.86 | 1901 (1887) | 1.53 | 2.67 | 1.53 | - | yes |
| sunbox_f_shirt_plaid | stylised_human | WAIT | 30 | 191 | 0.85 | 1901 (1884) | 1.17 | 3.43 | 1.17 | - | yes |
| sunbox_f_shirt_plaid | stylised_human | STOP | 30 | 191 | 0.94 | 1901 (1886) | 1.66 | 3.04 | 1.66 | - | yes |
| anime_f_01 | anime | POINT | 60 | 436 | 0.82 | 1388 (1292) | 1.42 | 6.59 | 1.80 | - | yes |
| anime_f_01 | anime | PROCEED | 30 | 436 | 0.86 | 1388 (1289) | 1.34 | 3.00 | 1.36 | - | yes |
| anime_f_01 | anime | WAIT | 30 | 436 | 0.89 | 1388 (1286) | 0.86 | 4.99 | 1.00 | - | yes |
| anime_f_01 | anime | STOP | 30 | 436 | 0.92 | 1388 (1295) | 1.09 | 3.70 | 1.14 | - | yes |
| anime_f_02_outfit_short | anime | POINT | 60 | 344 | 0.87 | 1308 (1236) | 0.91 | 3.57 | 0.97 | - | yes |
| anime_f_02_outfit_short | anime | PROCEED | 30 | 344 | 0.90 | 1308 (1222) | 0.95 | 1.64 | 0.95 | - | yes |
| anime_f_02_outfit_short | anime | WAIT | 30 | 344 | 0.97 | 1308 (1233) | 0.66 | 3.33 | 0.70 | - | yes |
| anime_f_02_outfit_short | anime | STOP | 30 | 344 | 0.94 | 1308 (1233) | 0.63 | 2.49 | 0.66 | - | yes |
| anime_f_03_bangs_parted | anime | POINT | 60 | 436 | 0.82 | 1388 (1289) | 1.44 | 6.38 | 1.72 | - | yes |
| anime_f_03_bangs_parted | anime | PROCEED | 30 | 436 | 0.86 | 1388 (1284) | 1.16 | 2.03 | 1.20 | - | yes |
| anime_f_03_bangs_parted | anime | WAIT | 30 | 436 | 0.90 | 1388 (1291) | 1.42 | 4.97 | 1.66 | - | yes |
| anime_f_03_bangs_parted | anime | STOP | 30 | 436 | 0.92 | 1388 (1292) | 1.03 | 3.65 | 1.09 | - | yes |
| cartoon_boxo_01 | cartoon_non_human | POINT | 60 | 99 | 0.73 | 5128 (5128) | 0.00 | 1.06 | 0.00 | 0.0 % | yes |
| cartoon_boxo_01 | cartoon_non_human | PROCEED | 30 | 99 | 0.78 | 5128 (5126) | 0.00 | 0.66 | 0.00 | 0.0 % | yes |
| cartoon_boxo_01 | cartoon_non_human | WAIT | 30 | 99 | 0.72 | 5128 (5128) | 0.00 | 1.10 | 0.00 | 0.0 % | yes |
| cartoon_boxo_01 | cartoon_non_human | STOP | 30 | 99 | 0.91 | 5128 (5128) | 0.00 | 0.42 | 0.00 | 0.0 % | yes |
