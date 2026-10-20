# Modifications to Robotics-Warehouse

This folder is a vendored copy of Unity Technologies' Robotics-Warehouse,
changed so that it compiles in Unity 2022.3.62f3 without the Unity
Perception package.

| | |
|---|---|
| Upstream | https://github.com/Unity-Technologies/Robotics-Warehouse |
| Commit | `4a2a506dd48c62bbd1ee5de4eb15ddd679a38e6f` (2022-06-16, "Merge pull request #27 from Unity-Technologies/dev") |
| License | Apache License 2.0, see [LICENSE](LICENSE) (unchanged) |
| Vendored | 2026-10-16 |

Why: `com.unity.perception@0.9.0-preview.2` does not compile in Unity
2022.3 (`GroundTruthCrossPipelinePass.cs`: `RendererListDesc` not found).
Our pipeline does not use Perception: segmentation and detection run in
our own Python code.

All files not listed below are unchanged from upstream.

## Removed

| Path | Reason |
|---|---|
| `.git/` | Vendored as plain files in our repository; upstream commit recorded above. |
| `WarehouseProjectHDRP/` | HDRP project, unused (we use URP). |
| `com.unity.robotics.warehouse.hdrp/` | HDRP package, unused. |
| `com.unity.robotics.warehouse.base/Scripts/Runtime/PerceptionRandomizers/` (folder and its `.meta`) | Every script in it derives from or uses Perception types. |

Files deleted with that folder (each with its `.meta`):
`FloorBoxRandomizerShim.cs`, `FloorBoxRandomizerTag.cs`,
`LocalRotationRandomizerShim.cs`, `MaterialRandomizerShim.cs`,
`MaterialRandomizerTag.cs`, `MaterialToFrictionParameter.cs`,
`RobotPlacementRandomizerShim.cs`, `RobotPlacementTag.cs`,
`RobotStandaloneRandomizerShim.cs`, `ShelfBoxRandomizerShim.cs`,
`ShelfBoxRandomizerTag.cs`, `SurfaceObjectPlacer.cs`,
`Shims/RandomizerShim.cs`, `Shims/ScenarioShim.cs`, and `Shims.meta`.

## Changed

| Path | Change | Reason |
|---|---|---|
| `com.unity.robotics.warehouse.base/package.json` | Removed dependency `com.unity.perception`. | Perception removed. |
| `com.unity.robotics.warehouse.urp/package.json` | Removed dependency `com.unity.perception`. | Perception removed. |
| `WarehouseProjectURP/Packages/packages-lock.json` | Removed `com.unity.perception` and the packages only it pulled in (`com.unity.simulation.core`, `.client`, `.capture`, `com.unity.collections`, `com.unity.nuget.newtonsoft-json`); removed Perception from the two warehouse packages' dependency lists. Unity rewrites this file on open. | Perception removed. |
| `WarehouseProjectURP/Packages/manifest.json` | Package versions raised by the Unity 2022.3 editor on first open (URP 11.0.0 to 14.0.12, etc.; `com.unity.ai.navigation` added). Perception was never listed here directly. | Editor upgrade, not edited by hand. |
| `WarehouseProjectURP/ProjectSettings/ProjectVersion.txt` | 2021.1.11f1 to 2022.3.62f3. | Editor upgrade. |
| `WarehouseProjectURP/ProjectSettings/MemorySettings.asset` | Added by the Unity 2022.3 editor. | Editor upgrade. |
| `com.unity.robotics.warehouse.base/Scripts/Runtime/Unity.Robotics.Warehouse.asmdef` | Removed reference `GUID:a3867139fb5f48e43972bdbc58ef9b3c` (Unity.Perception.Runtime). | Perception removed. |
| `com.unity.robotics.warehouse.base/Scripts/Editor/Unity.Robotics.Warehouse.Editor.asmdef` | Removed the same reference. | Perception removed. |
| `com.unity.robotics.warehouse.base/Scripts/Runtime/WarehouseManager.cs` | Removed `[RequireComponent(typeof(ScenarioShim))]`, the `ScenarioShim` property, `IncrementIteration()`, and `AddComponent<MaterialRandomizerTag>()` on each floor tile; reworded one tooltip; added a modification notice. | Those types were deleted. |
| `WarehouseProjectURP/.gitignore` | Added two ignore lines at the end (2026-10-20): the extracted Mixamo textures folder's `.meta` and `*.local.json.meta`. | The upstream rule `!/[Aa]ssets/**/*.meta` re-includes every meta file; these two belong to git-ignored content. |
| `com.unity.robotics.warehouse.base/Scripts/Editor/EditorWarehouseGeneration.cs` | `Generate` no longer runs a randomizer iteration; removed the "Warehouse/Increment Iteration" menu item, its validator and Inspector button; added a modification notice. | Those types were deleted. |

The other asmdef references (`1da8e233...`, `809aba06...`, `465c1207...`
in the Editor asmdef; `b1ef917f...` in the Runtime asmdef) do not belong
to any installed package. They were already unresolved upstream and are
left unchanged.

## Features lost

Warehouse generation itself is unchanged and deterministic: the shell
(floor, walls, ceiling, skylights, lights, glulam beams), the shelf grid
and the stations are placed purely from `AppParam` (width, length,
shelfRows, shelfCols). No random numbers are involved.

Lost, because they ran only as Perception randomizers on the
`WarehouseManager` prefab's `ScenarioShim` (random seed 539662031):

- **Boxes on shelves** (`ShelfBoxRandomizerShim`): each shelf slot got
  `box001` or `box002` with probability 0.5. Newly generated racks are
  now empty.
- **Rotation of tagged objects** (`LocalRotationRandomizerShim`): random
  0-360 degree local rotation of objects with a `RotationRandomizerTag`.
- **Sun angle** (`SunAngleRandomizer`, Perception built-in): random
  hour, day of year and latitude for the directional light.
- **Floor boxes** (`FloorBoxRandomizerShim`): configured with
  `numBoxToSpawn: 0`, so it spawned nothing; no visible change.
- **Material and friction randomization** (`MaterialRandomizerShim`):
  not in the prefab's randomizer list, so it had no effect; only the
  tag on floor tiles is gone.
- **Robot placement** (`RobotPlacementRandomizerShim`,
  `RobotStandaloneRandomizerShim`): not in the prefab's randomizer list;
  no effect in this project.
- **Perception labelling** (`Labeling` components) and any Perception
  ground-truth capture.

## Remaining references (not edited)

Scenes and prefabs still contain components whose scripts no longer
exist. Unity shows each one as a "Missing (Mono Script)" component and
may log "The referenced script on this Behaviour is missing!" warnings.
They have no other effect. They were not edited by hand because Unity
YAML is easier to break than to fix outside the editor.

| Component (script GUID) | Where (count) |
|---|---|
| `Labeling` (Perception, `8b33f0bc...`) | `Scenes/Warehouse.unity` (421), `SavedWarehouses/GeneratedWarehouse.prefab` (80), `box001`, `box002`, `ShelvingRackRandom`, and the 9 prefabs in `WarehouseParts/` (1 each) |
| `MaterialRandomizerTag` (`0f3c0b98...`) | `Scenes/Warehouse.unity` (81), `GeneratedWarehouse.prefab` (81) |
| `ShelfBoxRandomizerTag` (`3e3632af...`) | `Scenes/Warehouse.unity` (12), `ShelvingRackRandom.prefab` (1) |
| `RotationRandomizerTag` (Perception, `b85e54e3...`) | `Scenes/Warehouse.unity` (12), `ShelvingRackRandom.prefab` (1) |
| `SunAngleRandomizerTag` (Perception, `db00808a...`) | `Scenes/Warehouse.unity` (1) |
| `ScenarioShim` (`50ef6faf...`) with serialized randomizers | `Resources/Prefabs/WarehouseManager.prefab` (1) |

All paths above are under `com.unity.robotics.warehouse.urp/`.

Text mentions left unchanged: `README.md` and `Documentation/Usage.md`
(upstream documentation, including the Increment Iteration workflow),
and `com.unity.robotics.warehouse.urp/Resources/Configs/warehouse.json`
(names `PerceptionRandomizationInstantiator` from
`Unity.Robotics.SimulationControl`, a package not in this project; the
file is not read by any code here).
