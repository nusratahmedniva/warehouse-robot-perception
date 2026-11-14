# Skinning check: forearm volume and torso rigidity (island_hands, 2026-11-15T01:53:10)

experiments_ab.md section 12 addendum 5. Reference: the idle pose just before each take's request. Forearm: vertices bound mainly to the gesturing LowerArm (>= 0.5) in 5 bands along elbow to wrist (bands under 8 vertices skipped); each band's mean distance from the elbow-to-wrist line over its reference; the narrowest must keep >= 0.70. Torso: vertices bound mainly to Hips, Spine, Chest, UpperChest (>= 0.5), each in its own bone's frame; the rule (addendum 7) applies to the torso core (outside 0.4 Lu of both UpperArm bones): core p95 displacement < 2.125 cm; the whole torso's p95 is information. Addendum 9: a palm-plate look's plate must keep its sorted extents within its rule's change in every command (the plate column). Worst values over every measured frame of every take, both arms.

| look | kind | command | frames | forearm vertices | forearm narrowest band (ratio, min) | torso vertices (core) | torso core p95 max (cm) | torso core max (cm) | whole torso p95 (cm, info) | plate shape change max | pass |
|---|---|---|---|---|---|---|---|---|---|---|---|
| mixamo_worker | realistic_human | POINT | 60 | 187 | 0.82 | 3082 (3077) | 0.99 | 1.85 | 0.99 | - | yes |
| mixamo_worker | realistic_human | PROCEED | 29 | 187 | 0.84 | 3082 (3076) | 0.82 | 1.60 | 0.82 | - | yes |
| mixamo_worker | realistic_human | WAIT | 30 | 187 | 0.87 | 3082 (3078) | 0.70 | 4.66 | 0.71 | - | yes |
| mixamo_worker | realistic_human | STOP | 30 | 187 | 0.93 | 3082 (3073) | 0.78 | 1.58 | 0.77 | - | yes |
| sunbox_m1 | stylised_human | POINT | 60 | 207 | 0.89 | 1774 (1771) | 1.27 | 2.80 | 1.28 | - | yes |
| sunbox_m1 | stylised_human | PROCEED | 30 | 207 | 0.84 | 1774 (1773) | 1.64 | 3.72 | 1.65 | - | yes |
| sunbox_m1 | stylised_human | WAIT | 30 | 207 | 0.84 | 1774 (1773) | 1.07 | 5.49 | 1.07 | - | yes |
| sunbox_m1 | stylised_human | STOP | 30 | 207 | 0.94 | 1774 (1773) | 1.60 | 3.57 | 1.60 | - | yes |
| sunbox_f1 | stylised_human | POINT | 60 | 191 | 0.88 | 1901 (1887) | 1.67 | 3.13 | 1.67 | - | yes |
| sunbox_f1 | stylised_human | PROCEED | 30 | 191 | 0.85 | 1901 (1887) | 1.40 | 2.42 | 1.38 | - | yes |
| sunbox_f1 | stylised_human | WAIT | 30 | 191 | 0.85 | 1901 (1887) | 1.62 | 3.08 | 1.62 | - | yes |
| sunbox_f1 | stylised_human | STOP | 30 | 191 | 0.94 | 1901 (1886) | 1.21 | 2.30 | 1.18 | - | yes |
| sunbox_f2 | stylised_human | POINT | 60 | 96 | 0.90 | 2202 (2182) | 1.42 | 3.10 | 1.42 | - | yes |
| sunbox_f2 | stylised_human | PROCEED | 30 | 96 | 0.85 | 2202 (2184) | 0.61 | 1.08 | 0.62 | - | yes |
| sunbox_f2 | stylised_human | WAIT | 30 | 96 | 0.86 | 2202 (2186) | 1.32 | 3.62 | 1.33 | - | yes |
| sunbox_f2 | stylised_human | STOP | 30 | 96 | 0.95 | 2202 (2171) | 1.10 | 2.03 | 1.10 | - | yes |
| sunbox_m2 | stylised_human | POINT | 60 | 109 | 0.91 | 2101 (2094) | 1.44 | 3.19 | 1.46 | - | yes |
| sunbox_m2 | stylised_human | PROCEED | 30 | 109 | 0.84 | 2101 (2095) | 1.35 | 3.01 | 1.35 | - | yes |
| sunbox_m2 | stylised_human | WAIT | 30 | 109 | 0.85 | 2101 (2092) | 1.40 | 6.08 | 1.40 | - | yes |
| sunbox_m2 | stylised_human | STOP | 30 | 109 | 0.95 | 2101 (2094) | 1.59 | 3.74 | 1.59 | - | yes |
| sunbox_m_shirt_white | stylised_human | POINT | 60 | 207 | 0.89 | 1774 (1771) | 1.36 | 3.05 | 1.41 | - | yes |
| sunbox_m_shirt_white | stylised_human | PROCEED | 30 | 207 | 0.84 | 1774 (1770) | 0.64 | 1.21 | 0.64 | - | yes |
| sunbox_m_shirt_white | stylised_human | WAIT | 30 | 207 | 0.83 | 1774 (1771) | 1.25 | 4.69 | 1.25 | - | yes |
| sunbox_m_shirt_white | stylised_human | STOP | 30 | 207 | 0.95 | 1774 (1771) | 0.88 | 1.60 | 0.88 | - | yes |
| sunbox_m_tshirt_black | stylised_human | POINT | 60 | 109 | 0.90 | 2101 (2095) | 1.50 | 3.35 | 1.53 | - | yes |
| sunbox_m_tshirt_black | stylised_human | PROCEED | 30 | 109 | 0.84 | 2101 (2094) | 1.23 | 2.86 | 1.22 | - | yes |
| sunbox_m_tshirt_black | stylised_human | WAIT | 30 | 109 | 0.85 | 2101 (2094) | 1.59 | 6.29 | 1.69 | - | yes |
| sunbox_m_tshirt_black | stylised_human | STOP | 30 | 109 | 0.95 | 2101 (2094) | 1.77 | 3.82 | 1.76 | - | yes |
| sunbox_m_shirt_plaid | stylised_human | POINT | 60 | 207 | 0.89 | 1774 (1773) | 1.61 | 3.58 | 1.63 | - | yes |
| sunbox_m_shirt_plaid | stylised_human | PROCEED | 30 | 207 | 0.83 | 1774 (1770) | 0.78 | 1.62 | 0.78 | - | yes |
| sunbox_m_shirt_plaid | stylised_human | WAIT | 30 | 207 | 0.83 | 1774 (1770) | 0.76 | 4.50 | 0.78 | - | yes |
| sunbox_m_shirt_plaid | stylised_human | STOP | 30 | 207 | 0.96 | 1774 (1771) | 1.42 | 3.18 | 1.42 | - | yes |
| sunbox_f_shirt_white | stylised_human | POINT | 60 | 191 | 0.89 | 1729 (1714) | 1.53 | 2.71 | 1.52 | - | yes |
| sunbox_f_shirt_white | stylised_human | PROCEED | 30 | 191 | 0.85 | 1729 (1710) | 0.85 | 1.35 | 0.84 | - | yes |
| sunbox_f_shirt_white | stylised_human | WAIT | 30 | 191 | 0.85 | 1729 (1713) | 1.35 | 3.61 | 1.35 | - | yes |
| sunbox_f_shirt_white | stylised_human | STOP | 30 | 191 | 0.95 | 1729 (1711) | 1.23 | 2.14 | 1.23 | - | yes |
| sunbox_f_dress_red | stylised_human | POINT | 60 | 96 | 0.91 | 1704 (1693) | 1.28 | 2.45 | 1.28 | - | yes |
| sunbox_f_dress_red | stylised_human | PROCEED | 30 | 96 | 0.86 | 1704 (1692) | 1.14 | 2.17 | 1.14 | - | yes |
| sunbox_f_dress_red | stylised_human | WAIT | 30 | 96 | 0.85 | 1704 (1691) | 1.47 | 4.29 | 1.45 | - | yes |
| sunbox_f_dress_red | stylised_human | STOP | 30 | 96 | 0.97 | 1704 (1674) | 1.34 | 2.57 | 1.33 | - | yes |
| sunbox_f_shirt_plaid | stylised_human | POINT | 60 | 191 | 0.89 | 1901 (1886) | 1.70 | 3.07 | 1.68 | - | yes |
| sunbox_f_shirt_plaid | stylised_human | PROCEED | 30 | 191 | 0.86 | 1901 (1887) | 1.56 | 2.74 | 1.55 | - | yes |
| sunbox_f_shirt_plaid | stylised_human | WAIT | 30 | 191 | 0.85 | 1901 (1884) | 1.21 | 3.57 | 1.21 | - | yes |
| sunbox_f_shirt_plaid | stylised_human | STOP | 30 | 191 | 0.94 | 1901 (1887) | 1.66 | 3.05 | 1.66 | - | yes |
| anime_f_01 | anime | POINT | 60 | 436 | 0.82 | 1388 (1292) | 1.43 | 6.59 | 1.79 | - | yes |
| anime_f_01 | anime | PROCEED | 30 | 436 | 0.86 | 1388 (1289) | 1.35 | 2.98 | 1.32 | - | yes |
| anime_f_01 | anime | WAIT | 30 | 436 | 0.89 | 1388 (1286) | 0.87 | 4.99 | 1.02 | - | yes |
| anime_f_01 | anime | STOP | 30 | 436 | 0.92 | 1388 (1295) | 1.12 | 3.70 | 1.16 | - | yes |
| anime_f_02_outfit_short | anime | POINT | 60 | 344 | 0.87 | 1308 (1236) | 0.96 | 3.57 | 1.00 | - | yes |
| anime_f_02_outfit_short | anime | PROCEED | 29 | 344 | 0.90 | 1308 (1224) | 0.96 | 1.62 | 0.96 | - | yes |
| anime_f_02_outfit_short | anime | WAIT | 30 | 344 | 0.97 | 1308 (1233) | 0.64 | 3.33 | 0.68 | - | yes |
| anime_f_02_outfit_short | anime | STOP | 30 | 344 | 0.94 | 1308 (1233) | 0.69 | 2.49 | 0.71 | - | yes |
| anime_f_03_bangs_parted | anime | POINT | 60 | 436 | 0.82 | 1388 (1289) | 1.45 | 6.38 | 1.74 | - | yes |
| anime_f_03_bangs_parted | anime | PROCEED | 30 | 436 | 0.86 | 1388 (1284) | 1.20 | 2.14 | 1.22 | - | yes |
| anime_f_03_bangs_parted | anime | WAIT | 30 | 436 | 0.90 | 1388 (1292) | 1.36 | 4.97 | 1.58 | - | yes |
| anime_f_03_bangs_parted | anime | STOP | 30 | 436 | 0.92 | 1388 (1292) | 0.93 | 3.54 | 1.05 | - | yes |
| cartoon_boxo_01 | cartoon_non_human | POINT | 60 | 99 | 0.73 | 5128 (5128) | 0.00 | 1.07 | 0.00 | 0.0 % | yes |
| cartoon_boxo_01 | cartoon_non_human | PROCEED | 29 | 99 | 0.78 | 5128 (5126) | 0.00 | 0.66 | 0.00 | 0.0 % | yes |
| cartoon_boxo_01 | cartoon_non_human | WAIT | 30 | 99 | 0.72 | 5128 (5127) | 0.00 | 1.16 | 0.00 | 0.0 % | yes |
| cartoon_boxo_01 | cartoon_non_human | STOP | 30 | 99 | 0.91 | 5128 (5128) | 0.00 | 0.59 | 0.00 | 0.0 % | yes |
