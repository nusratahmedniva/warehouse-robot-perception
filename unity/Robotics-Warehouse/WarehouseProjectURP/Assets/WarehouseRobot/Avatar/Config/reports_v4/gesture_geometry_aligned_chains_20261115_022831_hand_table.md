# Hand check: palm orientation and the WAIT thumb (aligned_chains, 2026-11-15T02:28:31)

experiments_ab.md section 12. Palm normal within 30.0 deg of the robot camera (the stand-in robot's eye), from the bones (LookPoser.PalmNormal) and from the skinned mesh (plane fit of the vertices bound mainly to the Hand bone, weight >= 0.5, between wrist and finger bases; n/a below 30 vertices or above flatness 0.5). WAIT thumb tucked: tip within 1.0 palm lengths (Lp) of the palm centre and at least 0.0 Lp on the palm side; 'across' is reported only (0 at the index base, 1 at the outermost base). Addendum 7: for a look with a palm_plates rule (Boxo) the mesh columns are the palm plate's (thinnest principal axis; its vertices; thin / middle extent) and the plate's sorted extents must stay within the rule's change of the rest plate's. Worst values over every measured hold frame of every take, both arms.

| look | kind | command | frames | palm vs camera, bones max (deg) | mesh max (deg) | mesh n/a frames | palm vertices min | flatness max | thumb tip max (Lp) | thumb palm side min (Lp) | thumb across | plate shape change max | pass |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| mixamo_worker | realistic_human | WAIT | 30 | 14.9 | 22.1 | 0 | 245 | 0.452 | 0.95 | 0.86 | -0.11 to -0.03 | - | yes |
| mixamo_worker | realistic_human | STOP | 30 | 12.9 | 22.2 | 0 | 267 | 0.433 | - | - | - | - | yes |
| sunbox_m1 | stylised_human | WAIT | 30 | 15.5 | 16.9 | 0 | 199 | 0.266 | 0.94 | 0.77 | 0.18 to 0.18 | - | yes |
| sunbox_m1 | stylised_human | STOP | 30 | 13.0 | 10.3 | 0 | 185 | 0.278 | - | - | - | - | yes |
| sunbox_f1 | stylised_human | WAIT | 30 | 15.1 | 21.7 | 0 | 131 | 0.398 | 0.93 | 0.77 | 0.20 to 0.20 | - | yes |
| sunbox_f1 | stylised_human | STOP | 30 | 11.8 | 14.0 | 0 | 130 | 0.463 | - | - | - | - | yes |
| sunbox_f2 | stylised_human | WAIT | 30 | 15.5 | 22.1 | 0 | 131 | 0.397 | 0.93 | 0.77 | 0.20 to 0.20 | - | yes |
| sunbox_f2 | stylised_human | STOP | 30 | 11.9 | 13.9 | 0 | 130 | 0.463 | - | - | - | - | yes |
| sunbox_m2 | stylised_human | WAIT | 30 | 14.7 | 16.1 | 0 | 197 | 0.276 | 0.94 | 0.77 | 0.18 to 0.18 | - | yes |
| sunbox_m2 | stylised_human | STOP | 30 | 12.9 | 11.0 | 0 | 185 | 0.277 | - | - | - | - | yes |
| sunbox_m_shirt_white | stylised_human | WAIT | 30 | 15.4 | 16.7 | 0 | 199 | 0.266 | 0.94 | 0.77 | 0.18 to 0.18 | - | yes |
| sunbox_m_shirt_white | stylised_human | STOP | 30 | 12.7 | 11.0 | 0 | 185 | 0.274 | - | - | - | - | yes |
| sunbox_m_tshirt_black | stylised_human | WAIT | 30 | 15.0 | 16.2 | 0 | 199 | 0.267 | 0.94 | 0.77 | 0.18 to 0.18 | - | yes |
| sunbox_m_tshirt_black | stylised_human | STOP | 30 | 12.1 | 10.1 | 0 | 185 | 0.275 | - | - | - | - | yes |
| sunbox_m_shirt_plaid | stylised_human | WAIT | 30 | 15.6 | 17.1 | 0 | 197 | 0.276 | 0.94 | 0.77 | 0.18 to 0.18 | - | yes |
| sunbox_m_shirt_plaid | stylised_human | STOP | 30 | 13.1 | 11.2 | 0 | 185 | 0.277 | - | - | - | - | yes |
| sunbox_f_shirt_white | stylised_human | WAIT | 30 | 16.1 | 22.7 | 0 | 131 | 0.398 | 0.93 | 0.77 | 0.20 to 0.20 | - | yes |
| sunbox_f_shirt_white | stylised_human | STOP | 30 | 13.0 | 15.0 | 0 | 130 | 0.462 | - | - | - | - | yes |
| sunbox_f_dress_red | stylised_human | WAIT | 30 | 16.5 | 23.2 | 0 | 131 | 0.398 | 0.93 | 0.77 | 0.20 to 0.20 | - | yes |
| sunbox_f_dress_red | stylised_human | STOP | 30 | 13.4 | 15.4 | 0 | 128 | 0.465 | - | - | - | - | yes |
| sunbox_f_shirt_plaid | stylised_human | WAIT | 30 | 16.4 | 23.1 | 0 | 131 | 0.397 | 0.93 | 0.77 | 0.20 to 0.20 | - | yes |
| sunbox_f_shirt_plaid | stylised_human | STOP | 30 | 12.6 | 14.7 | 0 | 130 | 0.466 | - | - | - | - | yes |
| anime_f_01 | anime | WAIT | 30 | 13.7 | 95.4 | 0 | 149 | 0.257 | 0.95 | 0.71 | 0.15 to 0.15 | - | **no** |
| anime_f_01 | anime | STOP | 30 | 10.6 | 93.1 | 0 | 141 | 0.256 | - | - | - | - | **no** |
| anime_f_02_outfit_short | anime | WAIT | 30 | 13.2 | 23.2 | 0 | 76 | 0.322 | 0.95 | 0.71 | 0.15 to 0.15 | - | yes |
| anime_f_02_outfit_short | anime | STOP | 30 | 11.0 | 19.3 | 0 | 73 | 0.365 | - | - | - | - | yes |
| anime_f_03_bangs_parted | anime | WAIT | 30 | 13.4 | 94.6 | 0 | 150 | 0.259 | 0.95 | 0.71 | 0.15 to 0.15 | - | **no** |
| anime_f_03_bangs_parted | anime | STOP | 30 | 11.0 | 93.6 | 0 | 139 | 0.254 | - | - | - | - | **no** |
| cartoon_boxo_01 | cartoon_non_human | WAIT | 30 | 10.1 | 14.2 | 0 | 216 | 0.375 | 0.95 | 0.52 | -0.16 to -0.16 | 0.0 % | yes |
| cartoon_boxo_01 | cartoon_non_human | STOP | 30 | 6.0 | 9.2 | 0 | 216 | 0.375 | - | - | - | 0.0 % | yes |

Failures (first failing frame of each failing take):

- anime_f_01 WAIT: left wait_ik_01: palm (mesh): palm bones 10.8 deg, mesh 92.7 deg, thumb 0.95 Lp, side 0.71 Lp; left wait_ik_02: palm (mesh): palm bones 13.7 deg, mesh 95.4 deg, thumb 0.95 Lp, side 0.71 Lp; left wait_raise_01: palm (mesh): palm bones 11.5 deg, mesh 93.3 deg, thumb 0.95 Lp, side 0.71 Lp; right wait_ik_01: palm (mesh): palm bones 11.3 deg, mesh 93.7 deg, thumb 0.95 Lp, side 0.71 Lp; right wait_ik_02: palm (mesh): palm bones 12.5 deg, mesh 93.9 deg, thumb 0.95 Lp, side 0.71 Lp; right wait_raise_01: palm (mesh): palm bones 12.1 deg, mesh 94.1 deg, thumb 0.95 Lp, side 0.71 Lp
- anime_f_01 STOP: left stop_ik_01: palm (mesh): palm bones 9.2 deg, mesh 90.5 deg; left stop_ik_02: palm (mesh): palm bones 10.6 deg, mesh 92.9 deg; left stop_ik_03: palm (mesh): palm bones 8.6 deg, mesh 89.8 deg; right stop_ik_01: palm (mesh): palm bones 9.3 deg, mesh 90.8 deg; right stop_ik_02: palm (mesh): palm bones 10.6 deg, mesh 93.1 deg; right stop_ik_03: palm (mesh): palm bones 8.5 deg, mesh 89.7 deg
- anime_f_03_bangs_parted WAIT: left wait_ik_01: palm (mesh): palm bones 11.4 deg, mesh 93.4 deg, thumb 0.95 Lp, side 0.71 Lp; left wait_ik_02: palm (mesh): palm bones 13.4 deg, mesh 94.6 deg, thumb 0.95 Lp, side 0.71 Lp; left wait_raise_01: palm (mesh): palm bones 11.5 deg, mesh 93.4 deg, thumb 0.95 Lp, side 0.71 Lp; right wait_ik_01: palm (mesh): palm bones 10.8 deg, mesh 92.7 deg, thumb 0.95 Lp, side 0.71 Lp; right wait_ik_02: palm (mesh): palm bones 12.7 deg, mesh 94.3 deg, thumb 0.95 Lp, side 0.71 Lp; right wait_raise_01: palm (mesh): palm bones 11.9 deg, mesh 94.0 deg, thumb 0.95 Lp, side 0.71 Lp
- anime_f_03_bangs_parted STOP: left stop_ik_01: palm (mesh): palm bones 10.0 deg, mesh 91.9 deg; left stop_ik_02: palm (mesh): palm bones 11.0 deg, mesh 93.5 deg; left stop_ik_03: palm (mesh): palm bones 9.1 deg, mesh 90.7 deg; right stop_ik_01: palm (mesh): palm bones 9.8 deg, mesh 91.7 deg; right stop_ik_02: palm (mesh): palm bones 10.7 deg, mesh 93.6 deg; right stop_ik_03: palm (mesh): palm bones 8.6 deg, mesh 89.9 deg

Diagnostic (section 12 addendum 1, not a pass rule): the mesh palm normal of each sub-mesh's palm vertices against the camera, first measured frame of the first take per command and arm:

- mixamo_worker WAIT left (wait_ik_01): Ch32/none: 290 v, 19.8 deg, flatness 0.40
- mixamo_worker WAIT right (wait_ik_01): Ch32/none: 245 v, 17.6 deg, flatness 0.45
- mixamo_worker STOP left (stop_ik_01): Ch32/none: 276 v, 19.9 deg, flatness 0.41
- mixamo_worker STOP right (stop_ik_01): Ch32/none: 270 v, 17.6 deg, flatness 0.43
- sunbox_m1 WAIT left (wait_ik_01): Avatar_Male_GEO/none: 199 v, 14.1 deg, flatness 0.27
- sunbox_m1 WAIT right (wait_ik_01): Avatar_Male_GEO/none: 199 v, 13.3 deg, flatness 0.27
- sunbox_m1 STOP left (stop_ik_01): Avatar_Male_GEO/none: 185 v, 9.0 deg, flatness 0.27
- sunbox_m1 STOP right (stop_ik_01): Avatar_Male_GEO/none: 185 v, 8.1 deg, flatness 0.27
- sunbox_f1 WAIT left (wait_ik_01): Avatar_Female_GEO/none: 131 v, 18.0 deg, flatness 0.40
- sunbox_f1 WAIT right (wait_ik_01): Avatar_Female_GEO/none: 131 v, 18.6 deg, flatness 0.40
- sunbox_f1 STOP left (stop_ik_01): Avatar_Female_GEO/none: 130 v, 12.7 deg, flatness 0.45
- sunbox_f1 STOP right (stop_ik_01): Avatar_Female_GEO/none: 130 v, 12.8 deg, flatness 0.46
- sunbox_f2 WAIT left (wait_ik_01): Avatar_Female_GEO/none: 131 v, 18.2 deg, flatness 0.40
- sunbox_f2 WAIT right (wait_ik_01): Avatar_Female_GEO/none: 131 v, 18.9 deg, flatness 0.40
- sunbox_f2 STOP left (stop_ik_01): Avatar_Female_GEO/none: 130 v, 13.0 deg, flatness 0.45
- sunbox_f2 STOP right (stop_ik_01): Avatar_Female_GEO/none: 130 v, 13.1 deg, flatness 0.46
- sunbox_m2 WAIT left (wait_ik_01): Avatar_Male_GEO/none: 197 v, 13.6 deg, flatness 0.28
- sunbox_m2 WAIT right (wait_ik_01): Avatar_Male_GEO/none: 199 v, 12.6 deg, flatness 0.26
- sunbox_m2 STOP left (stop_ik_01): Avatar_Male_GEO/none: 185 v, 7.9 deg, flatness 0.27
- sunbox_m2 STOP right (stop_ik_01): Avatar_Male_GEO/none: 185 v, 7.6 deg, flatness 0.27
- sunbox_m_shirt_white WAIT left (wait_ik_01): Avatar_Male_GEO/none: 199 v, 13.8 deg, flatness 0.27
- sunbox_m_shirt_white WAIT right (wait_ik_01): Avatar_Male_GEO/none: 199 v, 13.0 deg, flatness 0.27
- sunbox_m_shirt_white STOP left (stop_ik_01): Avatar_Male_GEO/none: 185 v, 8.5 deg, flatness 0.27
- sunbox_m_shirt_white STOP right (stop_ik_01): Avatar_Male_GEO/none: 185 v, 8.2 deg, flatness 0.27
- sunbox_m_tshirt_black WAIT left (wait_ik_01): Avatar_Male_GEO/none: 199 v, 13.7 deg, flatness 0.27
- sunbox_m_tshirt_black WAIT right (wait_ik_01): Avatar_Male_GEO/none: 199 v, 13.5 deg, flatness 0.27
- sunbox_m_tshirt_black STOP left (stop_ik_01): Avatar_Male_GEO/none: 185 v, 7.0 deg, flatness 0.27
- sunbox_m_tshirt_black STOP right (stop_ik_01): Avatar_Male_GEO/none: 185 v, 8.0 deg, flatness 0.27
- sunbox_m_shirt_plaid WAIT left (wait_ik_01): Avatar_Male_GEO/none: 197 v, 13.7 deg, flatness 0.28
- sunbox_m_shirt_plaid WAIT right (wait_ik_01): Avatar_Male_GEO/none: 199 v, 13.6 deg, flatness 0.27
- sunbox_m_shirt_plaid STOP left (stop_ik_01): Avatar_Male_GEO/none: 185 v, 8.6 deg, flatness 0.27
- sunbox_m_shirt_plaid STOP right (stop_ik_01): Avatar_Male_GEO/none: 185 v, 7.7 deg, flatness 0.27
- sunbox_f_shirt_white WAIT left (wait_ik_01): Avatar_Female_GEO/none: 131 v, 18.1 deg, flatness 0.40
- sunbox_f_shirt_white WAIT right (wait_ik_01): Avatar_Female_GEO/none: 131 v, 18.4 deg, flatness 0.40
- sunbox_f_shirt_white STOP left (stop_ik_01): Avatar_Female_GEO/none: 130 v, 13.5 deg, flatness 0.45
- sunbox_f_shirt_white STOP right (stop_ik_01): Avatar_Female_GEO/none: 130 v, 12.7 deg, flatness 0.46
- sunbox_f_dress_red WAIT left (wait_ik_01): Avatar_Female_GEO/none: 131 v, 18.6 deg, flatness 0.40
- sunbox_f_dress_red WAIT right (wait_ik_01): Avatar_Female_GEO/none: 131 v, 19.6 deg, flatness 0.40
- sunbox_f_dress_red STOP left (stop_ik_01): Avatar_Female_GEO/none: 130 v, 14.3 deg, flatness 0.46
- sunbox_f_dress_red STOP right (stop_ik_01): Avatar_Female_GEO/none: 130 v, 14.0 deg, flatness 0.46
- sunbox_f_shirt_plaid WAIT left (wait_ik_01): Avatar_Female_GEO/none: 131 v, 19.0 deg, flatness 0.40
- sunbox_f_shirt_plaid WAIT right (wait_ik_01): Avatar_Female_GEO/none: 131 v, 19.3 deg, flatness 0.40
- sunbox_f_shirt_plaid STOP left (stop_ik_01): Avatar_Female_GEO/none: 130 v, 14.0 deg, flatness 0.46
- sunbox_f_shirt_plaid STOP right (stop_ik_01): Avatar_Female_GEO/none: 130 v, 13.2 deg, flatness 0.46
- anime_f_01 WAIT left (wait_ik_01): Body/none: 150 v, 92.7 deg, flatness 0.25
- anime_f_01 WAIT right (wait_ik_01): Body/none: 149 v, 93.7 deg, flatness 0.25
- anime_f_01 STOP left (stop_ik_01): Body/none: 142 v, 90.5 deg, flatness 0.25
- anime_f_01 STOP right (stop_ik_01): Body/none: 142 v, 90.8 deg, flatness 0.25
- anime_f_02_outfit_short WAIT left (wait_ik_01): Body/none: 76 v, 21.0 deg, flatness 0.32
- anime_f_02_outfit_short WAIT right (wait_ik_01): Body/none: 76 v, 20.6 deg, flatness 0.32
- anime_f_02_outfit_short STOP left (stop_ik_01): Body/none: 76 v, 18.4 deg, flatness 0.31
- anime_f_02_outfit_short STOP right (stop_ik_01): Body/none: 76 v, 18.5 deg, flatness 0.31
- anime_f_03_bangs_parted WAIT left (wait_ik_01): Body/none: 150 v, 93.4 deg, flatness 0.25
- anime_f_03_bangs_parted WAIT right (wait_ik_01): Body/none: 150 v, 92.7 deg, flatness 0.25
- anime_f_03_bangs_parted STOP left (stop_ik_01): Body/none: 141 v, 91.9 deg, flatness 0.24
- anime_f_03_bangs_parted STOP right (stop_ik_01): Body/none: 141 v, 91.7 deg, flatness 0.24
- cartoon_boxo_01 WAIT left (wait_ik_01): Boxo/glovemat: 163 v, 10.9 deg, flatness 0.33; Boxo/limbmat: 22 v, 74.1 deg, flatness 0.17
- cartoon_boxo_01 WAIT right (wait_ik_01): Boxo/glovemat: 163 v, 10.7 deg, flatness 0.33; Boxo/limbmat: 20 v, 80.2 deg, flatness 0.27
- cartoon_boxo_01 STOP left (stop_ik_01): Boxo/glovemat: 163 v, 8.0 deg, flatness 0.33; Boxo/limbmat: 24 v, 82.5 deg, flatness 0.03
- cartoon_boxo_01 STOP right (stop_ik_01): Boxo/glovemat: 163 v, 8.4 deg, flatness 0.33; Boxo/limbmat: 21 v, 80.9 deg, flatness 0.02
