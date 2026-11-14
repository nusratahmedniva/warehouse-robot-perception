# Hand check: palm orientation and the WAIT thumb (hand, 2026-11-14T21:48:54)

experiments_ab.md section 12. Palm normal within 30.0 deg of the robot camera (the stand-in robot's eye), from the bones (LookPoser.PalmNormal) and from the skinned mesh (plane fit of the vertices bound mainly to the Hand bone, weight >= 0.5, between wrist and finger bases; n/a below 30 vertices or above flatness 0.5). WAIT thumb tucked: tip within 1.0 palm lengths (Lp) of the palm centre and at least 0.0 Lp on the palm side; 'across' is reported only (0 at the index base, 1 at the outermost base). Worst values over every measured hold frame of every take, both arms.

| look | kind | command | frames | palm vs camera, bones max (deg) | mesh max (deg) | mesh n/a frames | palm vertices min | flatness max | thumb tip max (Lp) | thumb palm side min (Lp) | thumb across | pass |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| mixamo_worker | realistic_human | WAIT | 30 | 14.9 | 21.6 | 0 | 245 | 0.451 | 1.27 | 0.83 | -0.67 to -0.57 | **no** |
| mixamo_worker | realistic_human | STOP | 30 | 12.9 | 22.2 | 0 | 267 | 0.433 | - | - | - | yes |
| sunbox_m1 | stylised_human | WAIT | 30 | 15.5 | 17.0 | 0 | 199 | 0.266 | 0.94 | 0.77 | 0.18 to 0.18 | yes |
| sunbox_m1 | stylised_human | STOP | 30 | 13.0 | 11.1 | 0 | 185 | 0.277 | - | - | - | yes |
| sunbox_f1 | stylised_human | WAIT | 30 | 15.2 | 21.8 | 0 | 131 | 0.398 | 0.93 | 0.77 | 0.20 to 0.20 | yes |
| sunbox_f1 | stylised_human | STOP | 30 | 11.9 | 14.0 | 0 | 130 | 0.463 | - | - | - | yes |
| sunbox_f2 | stylised_human | WAIT | 30 | 15.5 | 22.1 | 0 | 131 | 0.397 | 0.93 | 0.77 | 0.20 to 0.20 | yes |
| sunbox_f2 | stylised_human | STOP | 30 | 11.8 | 13.9 | 0 | 130 | 0.463 | - | - | - | yes |
| sunbox_m2 | stylised_human | WAIT | 30 | 14.8 | 16.1 | 0 | 197 | 0.276 | 0.94 | 0.77 | 0.18 to 0.18 | yes |
| sunbox_m2 | stylised_human | STOP | 30 | 12.9 | 11.0 | 0 | 185 | 0.277 | - | - | - | yes |
| sunbox_m_shirt_white | stylised_human | WAIT | 30 | 15.4 | 16.7 | 0 | 199 | 0.266 | 0.94 | 0.77 | 0.18 to 0.18 | yes |
| sunbox_m_shirt_white | stylised_human | STOP | 30 | 12.7 | 11.0 | 0 | 185 | 0.274 | - | - | - | yes |
| sunbox_m_tshirt_black | stylised_human | WAIT | 30 | 14.9 | 16.2 | 0 | 199 | 0.267 | 0.94 | 0.77 | 0.18 to 0.18 | yes |
| sunbox_m_tshirt_black | stylised_human | STOP | 30 | 12.1 | 10.1 | 0 | 185 | 0.275 | - | - | - | yes |
| sunbox_m_shirt_plaid | stylised_human | WAIT | 30 | 15.6 | 17.1 | 0 | 197 | 0.276 | 0.94 | 0.77 | 0.18 to 0.18 | yes |
| sunbox_m_shirt_plaid | stylised_human | STOP | 30 | 13.2 | 11.3 | 0 | 185 | 0.278 | - | - | - | yes |
| sunbox_f_shirt_white | stylised_human | WAIT | 30 | 16.1 | 22.7 | 0 | 131 | 0.398 | 0.93 | 0.77 | 0.20 to 0.20 | yes |
| sunbox_f_shirt_white | stylised_human | STOP | 30 | 12.9 | 14.9 | 0 | 130 | 0.462 | - | - | - | yes |
| sunbox_f_dress_red | stylised_human | WAIT | 30 | 16.5 | 23.2 | 0 | 131 | 0.398 | 0.93 | 0.77 | 0.20 to 0.20 | yes |
| sunbox_f_dress_red | stylised_human | STOP | 30 | 13.4 | 15.3 | 0 | 128 | 0.465 | - | - | - | yes |
| sunbox_f_shirt_plaid | stylised_human | WAIT | 30 | 16.4 | 23.1 | 0 | 131 | 0.397 | 0.93 | 0.77 | 0.20 to 0.20 | yes |
| sunbox_f_shirt_plaid | stylised_human | STOP | 30 | 12.6 | 14.6 | 0 | 130 | 0.466 | - | - | - | yes |
| anime_f_01 | anime | WAIT | 30 | 13.7 | 100.6 | 0 | 141 | 0.323 | 1.57 | 1.16 | -0.91 to -0.91 | **no** |
| anime_f_01 | anime | STOP | 30 | 10.6 | 93.1 | 0 | 141 | 0.256 | - | - | - | **no** |
| anime_f_02_outfit_short | anime | WAIT | 30 | 13.2 | 24.7 | 0 | 76 | 0.345 | 1.57 | 1.16 | -0.91 to -0.91 | **no** |
| anime_f_02_outfit_short | anime | STOP | 30 | 11.0 | 19.3 | 0 | 73 | 0.365 | - | - | - | yes |
| anime_f_03_bangs_parted | anime | WAIT | 30 | 13.3 | 99.2 | 0 | 142 | 0.323 | 1.57 | 1.16 | -0.91 to -0.91 | **no** |
| anime_f_03_bangs_parted | anime | STOP | 30 | 11.0 | 93.6 | 0 | 139 | 0.254 | - | - | - | **no** |
| cartoon_boxo_01 | cartoon_non_human | WAIT | 30 | 9.4 | n/a | **30** | 0 | - | 2.50 | 1.48 | -0.66 to -0.65 | **no** |
| cartoon_boxo_01 | cartoon_non_human | STOP | 30 | 5.2 | n/a | **30** | 2 | - | - | - | - | yes |

Failures (first failing frame of each failing take):

- mixamo_worker WAIT: left wait_ik_01: thumb sticks out: palm bones 11.7 deg, mesh 19.3 deg, thumb 1.24 Lp, side 0.83 Lp; left wait_ik_02: thumb sticks out: palm bones 14.4 deg, mesh 21.1 deg, thumb 1.24 Lp, side 0.83 Lp; left wait_raise_01: thumb sticks out: palm bones 14.4 deg, mesh 21.6 deg, thumb 1.24 Lp, side 0.83 Lp; right wait_ik_01: thumb sticks out: palm bones 12.1 deg, mesh 16.9 deg, thumb 1.27 Lp, side 0.86 Lp; right wait_ik_02: thumb sticks out: palm bones 14.7 deg, mesh 19.0 deg, thumb 1.27 Lp, side 0.86 Lp; right wait_raise_01: thumb sticks out: palm bones 14.9 deg, mesh 19.4 deg, thumb 1.27 Lp, side 0.86 Lp
- anime_f_01 WAIT: left wait_ik_01: palm (mesh), thumb sticks out: palm bones 10.8 deg, mesh 97.7 deg, thumb 1.57 Lp, side 1.16 Lp; left wait_ik_02: palm (mesh), thumb sticks out: palm bones 13.7 deg, mesh 100.6 deg, thumb 1.57 Lp, side 1.16 Lp; left wait_raise_01: palm (mesh), thumb sticks out: palm bones 11.5 deg, mesh 98.3 deg, thumb 1.57 Lp, side 1.16 Lp; right wait_ik_01: palm (mesh), thumb sticks out: palm bones 11.3 deg, mesh 99.3 deg, thumb 1.57 Lp, side 1.16 Lp; right wait_ik_02: palm (mesh), thumb sticks out: palm bones 12.4 deg, mesh 98.5 deg, thumb 1.57 Lp, side 1.16 Lp; right wait_raise_01: palm (mesh), thumb sticks out: palm bones 12.2 deg, mesh 99.2 deg, thumb 1.57 Lp, side 1.16 Lp
- anime_f_01 STOP: left stop_ik_01: palm (mesh): palm bones 9.2 deg, mesh 90.5 deg; left stop_ik_02: palm (mesh): palm bones 10.6 deg, mesh 92.9 deg; left stop_ik_03: palm (mesh): palm bones 8.7 deg, mesh 89.8 deg; right stop_ik_01: palm (mesh): palm bones 9.3 deg, mesh 90.8 deg; right stop_ik_02: palm (mesh): palm bones 10.6 deg, mesh 93.1 deg; right stop_ik_03: palm (mesh): palm bones 8.6 deg, mesh 89.8 deg
- anime_f_02_outfit_short WAIT: left wait_ik_01: thumb sticks out: palm bones 11.4 deg, mesh 22.4 deg, thumb 1.57 Lp, side 1.16 Lp; left wait_ik_02: thumb sticks out: palm bones 13.2 deg, mesh 24.7 deg, thumb 1.57 Lp, side 1.16 Lp; left wait_raise_01: thumb sticks out: palm bones 11.8 deg, mesh 22.9 deg, thumb 1.57 Lp, side 1.16 Lp; right wait_ik_01: thumb sticks out: palm bones 11.1 deg, mesh 22.1 deg, thumb 1.57 Lp, side 1.16 Lp; right wait_ik_02: thumb sticks out: palm bones 12.6 deg, mesh 24.0 deg, thumb 1.57 Lp, side 1.16 Lp; right wait_raise_01: thumb sticks out: palm bones 11.7 deg, mesh 22.7 deg, thumb 1.57 Lp, side 1.16 Lp
- anime_f_03_bangs_parted WAIT: left wait_ik_01: palm (mesh), thumb sticks out: palm bones 11.4 deg, mesh 98.6 deg, thumb 1.57 Lp, side 1.16 Lp; left wait_ik_02: palm (mesh), thumb sticks out: palm bones 13.3 deg, mesh 99.2 deg, thumb 1.57 Lp, side 1.16 Lp; left wait_raise_01: palm (mesh), thumb sticks out: palm bones 11.6 deg, mesh 98.4 deg, thumb 1.57 Lp, side 1.16 Lp; right wait_ik_01: palm (mesh), thumb sticks out: palm bones 10.8 deg, mesh 97.8 deg, thumb 1.57 Lp, side 1.16 Lp; right wait_ik_02: palm (mesh), thumb sticks out: palm bones 12.7 deg, mesh 99.0 deg, thumb 1.57 Lp, side 1.16 Lp; right wait_raise_01: palm (mesh), thumb sticks out: palm bones 11.9 deg, mesh 99.1 deg, thumb 1.57 Lp, side 1.16 Lp
- anime_f_03_bangs_parted STOP: left stop_ik_01: palm (mesh): palm bones 10.0 deg, mesh 91.9 deg; left stop_ik_02: palm (mesh): palm bones 11.0 deg, mesh 93.5 deg; left stop_ik_03: palm (mesh): palm bones 9.1 deg, mesh 90.7 deg; right stop_ik_01: palm (mesh): palm bones 9.8 deg, mesh 91.7 deg; right stop_ik_02: palm (mesh): palm bones 10.7 deg, mesh 93.6 deg; right stop_ik_03: palm (mesh): palm bones 8.6 deg, mesh 89.9 deg
- cartoon_boxo_01 WAIT: left wait_ik_01: thumb sticks out: palm bones 5.1 deg, mesh n/a, thumb 2.50 Lp, side 1.52 Lp; left wait_ik_02: thumb sticks out: palm bones 7.4 deg, mesh n/a, thumb 2.50 Lp, side 1.52 Lp; left wait_raise_01: thumb sticks out: palm bones 8.7 deg, mesh n/a, thumb 2.50 Lp, side 1.52 Lp; right wait_ik_01: thumb sticks out: palm bones 5.5 deg, mesh n/a, thumb 2.46 Lp, side 1.48 Lp; right wait_ik_02: thumb sticks out: palm bones 8.7 deg, mesh n/a, thumb 2.46 Lp, side 1.48 Lp; right wait_raise_01: thumb sticks out: palm bones 9.4 deg, mesh n/a, thumb 2.46 Lp, side 1.48 Lp
