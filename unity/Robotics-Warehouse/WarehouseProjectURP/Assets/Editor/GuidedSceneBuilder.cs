using System.Collections.Generic;
using System.IO;
using System.Text;
using Unity.AI.Navigation;
using UnityEditor;
using UnityEditor.SceneManagement;
using UnityEngine;
using UnityEngine.AI;
using UnityEngine.SceneManagement;

namespace WarehouseHRI.EditorTools
{
    /// <summary>
    /// "Tools > Warehouse HRI > Build Guided Scene": adds the guided-robot set-up to the open scene under one root
    /// object "WarehouseHRI": robot (box stand-in for the MiR100), 360 deg camera, pan-tilt gesture camera, the
    /// worker (Mixamo worker.fbx, or a capsule placeholder when it is missing), a 2-junction roadmap with 4
    /// endpoints, a NavMeshSurface (baked; obstacles = colliders of the racks and walls) and the TrialManager.
    /// Safe to run again: objects are found by name and updated, never duplicated. The scene is marked dirty, not
    /// saved; save it yourself.
    /// </summary>
    public static class GuidedSceneBuilder
    {
        public const string RootName = "WarehouseHRI";
        public const string WorkerModelPath = "Assets/WarehouseRobot/Characters/worker.fbx";
        const string NavMeshAssetName = "NavMesh-WarehouseHRI.asset";
        public const string ScenePath = "Assets/Scenes/WarehouseRobot.unity";
        public const string ViewerOnlyLayer = "ViewerOnly";
        const string MarkerMaterialPath = "Assets/WarehouseRobot/HRIMaterials/GoalMarker.mat";

        // Roadmap in floor coordinates (x, z), placed in the open aisles of the generated warehouse: rack centres
        // are at x = -12.5, 0, 12.5 and z = -15, -5, 5, 15, so x = +-6.25 and z = 0 are clear lanes. The builder
        // checks every node against colliders and the baked NavMesh and logs any problem.
        static readonly Vector2 k_A = new Vector2(6.25f, -10f);
        static readonly Vector2 k_J1 = new Vector2(6.25f, 0f);
        static readonly Vector2 k_J2 = new Vector2(-6.25f, 0f);
        static readonly Vector2 k_E1 = new Vector2(6.25f, 10f);    // J1 FORWARD
        static readonly Vector2 k_E2 = new Vector2(18.75f, 0f);    // J1 RIGHT
        static readonly Vector2 k_E3 = new Vector2(-18.75f, 0f);   // J2 FORWARD
        static readonly Vector2 k_E4 = new Vector2(-6.25f, 10f);   // J2 RIGHT
        const float WorkerCornerOffset = 2.5f; // worker stands ahead-right of the junction, off every lane

        [MenuItem("Tools/Warehouse HRI/Build Guided Scene")]
        public static void BuildMenu()
        {
            if (EditorApplication.isPlayingOrWillChangePlaymode)
            {
                EditorUtility.DisplayDialog("Warehouse HRI", "Leave Play mode before building the scene.", "OK");
                return;
            }

            Build();
        }

        /// <summary>
        /// Batch mode entry point: open the scene, build, save. Example:
        /// Unity -batchmode -quit -projectPath &lt;project&gt; -executeMethod WarehouseHRI.EditorTools.GuidedSceneBuilder.BatchBuild
        /// </summary>
        public static void BatchBuild()
        {
            EditorSceneManager.OpenScene(ScenePath);
            Build();
            if (!EditorSceneManager.SaveScene(SceneManager.GetActiveScene()))
                throw new System.Exception("Could not save " + ScenePath);
        }

        [MenuItem("Tools/Warehouse HRI/Gesture Pose Test")]
        public static void GesturePoseTest()
        {
            if (!EditorApplication.isPlaying)
            {
                EditorUtility.DisplayDialog("Warehouse HRI", "Press Play first, then run Gesture Pose Test.", "OK");
                return;
            }

            var worker = Object.FindObjectOfType<GestureWorker>();
            if (worker == null)
            {
                Debug.LogWarning("[WarehouseHRI] No GestureWorker in the scene. Run Build Guided Scene first.");
                return;
            }

            if (TrialManager.Active != null) TrialManager.Active.StopSession();
            var cycler = worker.GetComponent<GesturePoseCycler>();
            if (cycler == null) cycler = worker.gameObject.AddComponent<GesturePoseCycler>();
            cycler.worker = worker;
            cycler.enabled = true;
            var view = Camera.main;
            if (view != null)
            {
                var follow = view.GetComponent<FollowCamera>();
                if (follow != null) follow.enabled = false; // the pose test places the camera itself
                // Put the view camera where the robot would stand (2 m in front, 1.2 m high) and face the worker.
                Vector3 eye = worker.transform.position + worker.transform.forward * 3f + Vector3.up * 1.3f;
                view.transform.position = eye;
                view.transform.LookAt(worker.transform.position + Vector3.up * 1.2f);
                worker.faceTarget = view.transform;
            }

            Selection.activeGameObject = worker.gameObject;
            Debug.Log("[WarehouseHRI] Gesture pose test: LEFT, FORWARD_LEFT, FORWARD, FORWARD_RIGHT, RIGHT, STOP (NONE between). " +
                      "Directions are from the robot's (viewer's) point of view: LEFT should be an arm on YOUR left.");
        }

        public static string Build()
        {
            var log = new StringBuilder();
            var scene = SceneManager.GetActiveScene();
            var cfg = HriConfig.Load(Path.Combine(Application.streamingAssetsPath, HriConfig.RelativePath), out _);
            var root = FindOrCreateRoot(RootName);

            // The generated floor tiles have BoxColliders of zero thickness (size y ~ 1e-13), which the NavMesh
            // voxeliser cannot use, so one invisible 0.1 m slab with its top flush with the floor is always added.
            float floorY = FloorHeight(out var floorBounds, out bool floorHasColliders);
            var floorCollider = Child(root, "FloorCollider");
            var bc = GetOrAdd<BoxCollider>(floorCollider);
            Vector3 size = floorBounds.size.x > 1f && floorBounds.size.z > 1f ? floorBounds.size : new Vector3(60f, 0.1f, 60f);
            floorCollider.transform.SetPositionAndRotation(new Vector3(floorBounds.center.x, floorY - 0.05f, floorBounds.center.z), Quaternion.identity);
            bc.size = new Vector3(size.x, 0.1f, size.z);
            log.AppendLine($"Floor top y = {floorY:0.###}, {size.x:0.#} x {size.z:0.#} m (tile colliders present: {floorHasColliders}); " +
                           "added a 0.1 m floor slab collider for physics and the NavMesh bake.");

            // Roadmap.
            var roadmap = Child(root, "Roadmap");
            var a = Node(roadmap, "A", k_A, floorY, RoadNodeKind.Waypoint);
            var j1 = Node(roadmap, "J1", k_J1, floorY, RoadNodeKind.Junction);
            var j2 = Node(roadmap, "J2", k_J2, floorY, RoadNodeKind.Junction);
            var e1 = Node(roadmap, "E1", k_E1, floorY, RoadNodeKind.Endpoint);
            var e2 = Node(roadmap, "E2", k_E2, floorY, RoadNodeKind.Endpoint);
            var e3 = Node(roadmap, "E3", k_E3, floorY, RoadNodeKind.Endpoint);
            var e4 = Node(roadmap, "E4", k_E4, floorY, RoadNodeKind.Endpoint);
            Link(a, null, j1);
            Link(j1, a, e1, e2, j2);
            Link(j2, j1, e3, e4);
            foreach (var e in new[] { e1, e2, e3, e4 }) Link(e, null);
            Stand(j1, a);
            Stand(j2, j1);
            log.AppendLine("Roadmap: " + Describe(a) + " " + Describe(j1) + " " + Describe(j2));

            // Viewer-only layer: the goal marker lives there and the robot's cameras never render it.
            int viewerLayer = EnsureLayer(ViewerOnlyLayer, log);

            // Robot, cameras, worker.
            var robot = BuildRobot(root, cfg, a, j1, log);
            int robotMask = viewerLayer >= 0 ? ~(1 << viewerLayer) : ~0;
            robot.transform.Find("PanPivot/GestureCamera").GetComponent<Camera>().cullingMask = robotMask;
            robot.transform.Find("Cam360").GetComponent<Camera>().cullingMask = robotMask;
            var worker = BuildWorker(root, j1, log);

            // The upstream rack prefab carries carving NavMeshObstacles whose extents are centimetre values used as
            // metres (about 120 x 370 x 370 m each), so they carve away the whole NavMesh. Disable carving obstacles
            // larger than 10 m in the scene; the racks still block the NavMesh through their colliders.
            int disabled = 0;
            foreach (var o in Object.FindObjectsOfType<NavMeshObstacle>(true))
            {
                Vector3 s = Vector3.Scale(o.size, o.transform.lossyScale);
                if (o.enabled && o.carving && Mathf.Max(Mathf.Abs(s.x), Mathf.Abs(s.y), Mathf.Abs(s.z)) > 10f)
                {
                    o.enabled = false;
                    EditorUtility.SetDirty(o);
                    disabled++;
                }
            }

            if (disabled > 0)
                log.AppendLine($"Disabled {disabled} oversized carving NavMeshObstacle(s) (upstream rack prefab, > 10 m); racks still block the NavMesh via their colliders.");

            // NavMesh (robot and worker are excluded from the bake).
            var nav = Child(root, "NavMesh");
            var surface = GetOrAdd<NavMeshSurface>(nav);
            surface.collectObjects = CollectObjects.All;
            surface.useGeometry = NavMeshCollectGeometry.PhysicsColliders;
            surface.layerMask = ~0;
            Bake(surface, scene, log);
            Validate(new[] { a, j1, j2, e1, e2, e3, e4 }, log);

            // Trial manager.
            var trialsGo = Child(root, "Trials");
            var tm = GetOrAdd<TrialManager>(trialsGo);
            tm.robot = robot.GetComponent<DiffDriveRobot>();
            tm.brain = robot.GetComponent<RobotBrain>();
            tm.telemetry = robot.GetComponent<RobotTelemetry>();
            tm.bridge = robot.GetComponent<HriBridgeClient>();
            tm.worker = worker;
            tm.startNode = a;
            tm.endpoints = new List<RoadNode> { e1, e2, e3, e4 };
            tm.task1Goal = e1;
            tm.goalMarker = BuildGoalMarker(root, e1.Position, viewerLayer).transform;
            EditorUtility.SetDirty(tm);

            BuildViewCamera(root, robot, log);

            EditorSceneManager.MarkSceneDirty(scene);
            Selection.activeGameObject = root;
            string msg = "[WarehouseHRI] Build Guided Scene finished. Save the scene (Ctrl/Cmd+S), then press Play.\n" + log;
            Debug.Log(msg);
            return msg;
        }

        // ---------- helpers ----------

        static GameObject FindOrCreateRoot(string name)
        {
            foreach (var go in SceneManager.GetActiveScene().GetRootGameObjects())
                if (go.name == name) return go;
            var created = new GameObject(name);
            Undo.RegisterCreatedObjectUndo(created, "Build Guided Scene");
            return created;
        }

        static GameObject Child(GameObject parent, string name)
        {
            var t = parent.transform.Find(name);
            if (t != null) return t.gameObject;
            var go = new GameObject(name);
            go.transform.SetParent(parent.transform, false);
            Undo.RegisterCreatedObjectUndo(go, "Build Guided Scene");
            return go;
        }

        static GameObject Primitive(GameObject parent, string name, PrimitiveType type, bool keepCollider = false)
        {
            var t = parent.transform.Find(name);
            if (t != null) return t.gameObject;
            var go = GameObject.CreatePrimitive(type);
            go.name = name;
            go.transform.SetParent(parent.transform, false);
            if (!keepCollider) Object.DestroyImmediate(go.GetComponent<Collider>());
            Undo.RegisterCreatedObjectUndo(go, "Build Guided Scene");
            return go;
        }

        static T GetOrAdd<T>(GameObject go) where T : Component
        {
            var c = go.GetComponent<T>();
            return c != null ? c : go.AddComponent<T>();
        }

        static float FloorHeight(out Bounds bounds, out bool hasColliders)
        {
            bounds = new Bounds(Vector3.zero, Vector3.zero);
            hasColliders = false;
            bool any = false;
            GameObject[] floors;
            try { floors = GameObject.FindGameObjectsWithTag("Floor"); }
            catch (UnityException) { floors = new GameObject[0]; }
            foreach (var f in floors)
            {
                var r = f.GetComponent<Renderer>();
                if (r == null) continue;
                if (!any) { bounds = r.bounds; any = true; }
                else bounds.Encapsulate(r.bounds);
                if (f.GetComponent<Collider>() != null) hasColliders = true;
            }

            return any ? bounds.max.y : 0f;
        }

        static RoadNode Node(GameObject parent, string name, Vector2 xz, float y, RoadNodeKind kind)
        {
            var go = Child(parent, name);
            go.transform.position = new Vector3(xz.x, y, xz.y);
            var n = GetOrAdd<RoadNode>(go);
            n.kind = kind;
            if (kind != RoadNodeKind.Junction)
            {
                var stand = go.transform.Find("WorkerStand");
                if (stand != null) Object.DestroyImmediate(stand.gameObject);
                n.workerStand = null;
            }

            EditorUtility.SetDirty(n);
            return n;
        }

        /// <summary>Branches labelled from geometry: the turn from the arrival direction (prev -> node) to each next node.</summary>
        static void Link(RoadNode node, RoadNode previous, params RoadNode[] next)
        {
            node.branches = new List<RoadBranch>();
            Vector3 arrive = previous != null ? node.Position - previous.Position : Vector3.forward;
            arrive.y = 0f;
            foreach (var n in next)
            {
                Vector3 d = n.Position - node.Position;
                d.y = 0f;
                var cmd = previous == null ? GestureCommand.FORWARD
                    : GestureCommands.FromTurnAngle(Vector3.SignedAngle(arrive, d, Vector3.up));
                node.branches.Add(new RoadBranch { command = cmd, next = n });
            }

            EditorUtility.SetDirty(node);
        }

        static void Stand(RoadNode junction, RoadNode previous)
        {
            var standGo = Child(junction.gameObject, "WorkerStand");
            Vector3 arrive = junction.Position - previous.Position;
            arrive.y = 0f;
            arrive.Normalize();
            Vector3 right = Vector3.Cross(Vector3.up, arrive);
            standGo.transform.position = junction.Position + (arrive + right) * WorkerCornerOffset;
            standGo.transform.rotation = Quaternion.LookRotation(-arrive, Vector3.up); // faces the arriving robot
            junction.workerStand = standGo.transform;
            EditorUtility.SetDirty(junction);
        }

        static string Describe(RoadNode n)
        {
            var parts = new List<string>();
            foreach (var b in n.branches) parts.Add($"{b.command}->{b.next.name}");
            return $"{n.name}[{string.Join(", ", parts)}]";
        }

        static GameObject BuildRobot(GameObject root, HriConfig cfg, RoadNode a, RoadNode first, StringBuilder log)
        {
            var r = cfg.robot;
            var c = cfg.cameras;
            var robot = Child(root, "Robot");
            float yaw = Mathf.Atan2(first.Position.x - a.Position.x, first.Position.z - a.Position.z) * Mathf.Rad2Deg;
            robot.transform.SetPositionAndRotation(a.Position, Quaternion.Euler(0f, yaw, 0f));

            var body = GetOrAdd<Rigidbody>(robot);
            body.mass = r.mass_kg;
            body.useGravity = false; // planar robot: height frozen, the collider never touches the floor
            body.isKinematic = false;
            body.interpolation = RigidbodyInterpolation.Interpolate;
            body.collisionDetectionMode = CollisionDetectionMode.Continuous;
            body.constraints = DiffDriveRobot.PlanarConstraints;
            var box = GetOrAdd<BoxCollider>(robot);
            box.size = new Vector3(r.width_m, r.height_m - r.ground_clearance_m, r.length_m);
            box.center = new Vector3(0f, r.ground_clearance_m + (r.height_m - r.ground_clearance_m) * 0.5f, 0f);

            // Visual stand-in; skipped when an imported MiR100 model is a child named "MiR100".
            bool hasModel = robot.transform.Find("MiR100") != null;
            Transform wheelL = null, wheelR = null;
            if (!hasModel)
            {
                var vis = Primitive(robot, "Body", PrimitiveType.Cube);
                vis.transform.localPosition = new Vector3(0f, 0.08f + (r.height_m - 0.08f) * 0.5f, 0f);
                vis.transform.localScale = new Vector3(r.width_m, r.height_m - 0.08f, r.length_m);
                var front = Primitive(robot, "FrontMarker", PrimitiveType.Cube);
                front.transform.localPosition = new Vector3(0f, r.height_m, r.length_m * 0.5f - 0.06f);
                front.transform.localScale = new Vector3(r.width_m * 0.6f, 0.02f, 0.08f);
                wheelL = Primitive(robot, "WheelLeft", PrimitiveType.Cylinder).transform;
                wheelR = Primitive(robot, "WheelRight", PrimitiveType.Cylinder).transform;
                foreach (var w in new[] { wheelL, wheelR })
                {
                    w.localRotation = Quaternion.Euler(0f, 0f, 90f); // cylinder axis (local y) across the robot
                    w.localScale = new Vector3(0.2f, 0.02f, 0.2f);
                }

                wheelL.localPosition = new Vector3(-r.width_m * 0.5f - 0.02f, 0.1f, 0f);
                wheelR.localPosition = new Vector3(r.width_m * 0.5f + 0.02f, 0.1f, 0f);
            }
            else log.AppendLine("Robot: MiR100 child found; box stand-in body not created.");

            var mast = Primitive(robot, "Mast", PrimitiveType.Cylinder);
            float mastTop = c.cam360_height_m - 0.05f;
            mast.transform.localPosition = new Vector3(0f, (r.height_m + mastTop) * 0.5f, 0f);
            mast.transform.localScale = new Vector3(0.05f, (mastTop - r.height_m) * 0.5f, 0.05f);

            var cam360Go = Child(robot, "Cam360");
            cam360Go.transform.localPosition = new Vector3(0f, c.cam360_height_m, 0f);
            cam360Go.transform.localRotation = Quaternion.identity;
            var cam360Cam = GetOrAdd<Camera>(cam360Go);
            cam360Cam.enabled = false;
            cam360Cam.nearClipPlane = 0.05f;
            var cam360 = GetOrAdd<Camera360>(cam360Go);

            var pivot = Child(robot, "PanPivot");
            pivot.transform.localPosition = new Vector3(0f, c.gesture_height_m, 0f);
            pivot.transform.localRotation = Quaternion.identity;
            var camGo = Child(pivot, "GestureCamera");
            camGo.transform.localPosition = new Vector3(0f, 0f, 0.06f); // just outside the mast
            camGo.transform.localRotation = Quaternion.identity;
            var gcam = GetOrAdd<Camera>(camGo);
            gcam.fieldOfView = c.gesture_vfov_deg;
            gcam.nearClipPlane = 0.05f;
            var pan = GetOrAdd<PanTiltCamera>(pivot);
            pan.yawPivot = pivot.transform;
            pan.gestureCamera = gcam;

            var displayGo = Child(robot, "Display");
            displayGo.transform.localPosition = new Vector3(0f, c.cam360_height_m + 0.25f, 0f);
            displayGo.transform.localRotation = Quaternion.Euler(0f, 180f, 0f); // readable from in front of the robot
            var text = GetOrAdd<TextMesh>(displayGo);
            text.text = "";
            text.anchor = TextAnchor.MiddleCenter;
            text.alignment = TextAlignment.Center;
            text.characterSize = 0.04f;
            text.fontSize = 64;
            text.color = Color.yellow;
            var font = Resources.GetBuiltinResource<Font>("LegacyRuntime.ttf");
            if (font != null)
            {
                text.font = font;
                displayGo.GetComponent<MeshRenderer>().sharedMaterial = font.material;
            }

            var watchdog = GetOrAdd<PythonLinkWatchdog>(robot);
            var drive = GetOrAdd<DiffDriveRobot>(robot);
            drive.watchdog = watchdog;
            drive.leftWheels = wheelL != null ? new[] { wheelL } : new Transform[0];
            drive.rightWheels = wheelR != null ? new[] { wheelR } : new Transform[0];
            drive.wheelSpinAxis = Vector3.up;
            drive.wheelRadiusM = 0.1f;
            drive.trackWidthM = r.width_m;
            var gestures = GetOrAdd<ScriptedGestureSource>(robot);
            var people = GetOrAdd<ScriptedPersonSource>(robot);
            var brain = GetOrAdd<RobotBrain>(robot);
            brain.robot = drive;
            brain.panTilt = pan;
            brain.gestureSourceBehaviour = gestures;
            brain.personSourceBehaviour = people;
            brain.watchdog = watchdog;
            var telemetry = GetOrAdd<RobotTelemetry>(robot);
            telemetry.robot = drive;
            telemetry.brain = brain;
            var hud = GetOrAdd<HriHud>(robot);
            hud.brain = brain;
            hud.panTilt = pan;
            hud.cam360 = cam360;
            hud.robotDisplay = text;
            var bridge = GetOrAdd<HriBridgeClient>(robot);
            bridge.watchdog = watchdog;
            bridge.robot = drive;
            bridge.brain = brain;
            bridge.panTilt = pan;
            bridge.cam360 = cam360;
            telemetry.bridge = bridge;
            hud.bridge = bridge;
            GetOrAdd<NavMeshModifier>(robot).ignoreFromBuild = true;

            foreach (var comp in robot.GetComponents<Component>()) EditorUtility.SetDirty(comp);
            log.AppendLine($"Robot: {r.length_m} x {r.width_m} x {r.height_m} m box collider, Rigidbody {r.mass_kg} kg, " +
                           $"Cam360 at {c.cam360_height_m} m, gesture camera {c.gesture_width_px}x{c.gesture_height_px} at {c.gesture_height_m} m.");
            return robot;
        }

        static int EnsureLayer(string name, StringBuilder log)
        {
            int existing = LayerMask.NameToLayer(name);
            if (existing >= 0) return existing;
            var assets = AssetDatabase.LoadAllAssetsAtPath("ProjectSettings/TagManager.asset");
            if (assets == null || assets.Length == 0) return -1;
            var tags = new SerializedObject(assets[0]);
            var layers = tags.FindProperty("layers");
            for (int i = 8; i < layers.arraySize; i++)
            {
                var p = layers.GetArrayElementAtIndex(i);
                if (!string.IsNullOrEmpty(p.stringValue)) continue;
                p.stringValue = name;
                tags.ApplyModifiedProperties();
                AssetDatabase.SaveAssets();
                log.AppendLine($"Added layer '{name}' (index {i}) to ProjectSettings/TagManager.asset.");
                return i;
            }

            log.AppendLine($"WARNING: no free user layer for '{name}'; the goal marker will be visible to the robot cameras.");
            return -1;
        }

        static Material MarkerMaterial()
        {
            var m = AssetDatabase.LoadAssetAtPath<Material>(MarkerMaterialPath);
            if (m != null) return m;
            string dir = Path.GetDirectoryName(MarkerMaterialPath)?.Replace('\\', '/');
            if (!AssetDatabase.IsValidFolder(dir)) AssetDatabase.CreateFolder(Path.GetDirectoryName(dir)?.Replace('\\', '/'), Path.GetFileName(dir));
            var shader = Shader.Find("Universal Render Pipeline/Unlit") ?? Shader.Find("Unlit/Color");
            m = new Material(shader) { color = new Color(1f, 0.65f, 0f) };
            AssetDatabase.CreateAsset(m, MarkerMaterialPath);
            return m;
        }

        /// <summary>Goal B marker: a ring of the 0.3 m success radius and a pole with a ball. No colliders.</summary>
        static GameObject BuildGoalMarker(GameObject root, Vector3 at, int layer)
        {
            var marker = Child(root, "GoalMarker");
            marker.transform.SetPositionAndRotation(at, Quaternion.identity);
            var ring = Primitive(marker, "Ring", PrimitiveType.Cylinder);
            ring.transform.localPosition = new Vector3(0f, 0.01f, 0f);
            ring.transform.localScale = new Vector3(0.6f, 0.005f, 0.6f); // diameter 0.6 m = success radius 0.3 m
            var pole = Primitive(marker, "Pole", PrimitiveType.Cylinder);
            pole.transform.localPosition = new Vector3(0f, 1f, 0f);
            pole.transform.localScale = new Vector3(0.04f, 1f, 0.04f);
            var ball = Primitive(marker, "Ball", PrimitiveType.Sphere);
            ball.transform.localPosition = new Vector3(0f, 2.05f, 0f);
            ball.transform.localScale = Vector3.one * 0.25f;
            var mat = MarkerMaterial();
            foreach (var r in marker.GetComponentsInChildren<Renderer>())
            {
                r.sharedMaterial = mat;
                r.shadowCastingMode = UnityEngine.Rendering.ShadowCastingMode.Off;
            }

            if (layer >= 0)
                foreach (var t in marker.GetComponentsInChildren<Transform>(true)) t.gameObject.layer = layer;
            GetOrAdd<NavMeshModifier>(marker).ignoreFromBuild = true;
            return marker;
        }

        /// <summary>Game-view camera with FollowCamera (chase by default); the old fly camera is disabled.</summary>
        static void BuildViewCamera(GameObject root, GameObject robot, StringBuilder log)
        {
            var go = Child(root, "ViewCamera");
            var cam = GetOrAdd<Camera>(go);
            cam.depth = 10f;
            cam.nearClipPlane = 0.05f;
            cam.farClipPlane = 300f;
            go.tag = "MainCamera";
            if (go.GetComponent<AudioListener>() == null) go.AddComponent<AudioListener>();
            var follow = GetOrAdd<FollowCamera>(go);
            follow.target = robot.transform;
            follow.gestureCamera = robot.transform.Find("PanPivot/GestureCamera").GetComponent<Camera>();
            follow.mode = FollowCameraMode.Chase;
            Vector3 fwd = robot.transform.forward;
            go.transform.SetPositionAndRotation(robot.transform.position - fwd * follow.chaseDistanceM + Vector3.up * follow.chaseHeightM,
                Quaternion.LookRotation(fwd * (follow.chaseDistanceM + follow.lookAheadM) + Vector3.up * (follow.lookHeightM - follow.chaseHeightM)));
            var hud = robot.GetComponent<HriHud>();
            if (hud != null) hud.followCamera = follow;
            EditorUtility.SetDirty(follow);

            foreach (var other in SceneManager.GetActiveScene().GetRootGameObjects())
            {
                if (other == root || other.GetComponent<Camera>() == null || !other.activeSelf) continue;
                other.SetActive(false);
                log.AppendLine($"Disabled the camera object '{other.name}' (the view camera with FollowCamera replaces it).");
            }

            log.AppendLine("View camera: chase by default; C cycles chase / top-down / gesture camera.");
        }

        static GestureWorker BuildWorker(GameObject root, RoadNode firstJunction, StringBuilder log)
        {
            var go = Child(root, "Worker");
            go.transform.SetPositionAndRotation(firstJunction.workerStand.position, firstJunction.workerStand.rotation);
            var capsule = GetOrAdd<CapsuleCollider>(go);
            capsule.radius = 0.3f;
            capsule.height = 1.8f;
            capsule.center = new Vector3(0f, 0.9f, 0f);
            GetOrAdd<NavMeshModifier>(go).ignoreFromBuild = true;
            var worker = GetOrAdd<GestureWorker>(go);

            var model = AssetDatabase.LoadAssetAtPath<GameObject>(WorkerModelPath);
            var modelChild = go.transform.Find("Model");
            var placeholder = go.transform.Find("Placeholder");
            if (model != null)
            {
                if (placeholder != null) Object.DestroyImmediate(placeholder.gameObject);
                if (modelChild == null)
                {
                    var inst = (GameObject)PrefabUtility.InstantiatePrefab(model, go.transform);
                    inst.name = "Model";
                    inst.transform.localPosition = Vector3.zero;
                    inst.transform.localRotation = Quaternion.identity;
                    modelChild = inst.transform;
                }

                var animator = modelChild.GetComponentInChildren<Animator>();
                if (animator == null) animator = modelChild.gameObject.AddComponent<Animator>();
                worker.animator = animator;
                worker.leftArmPivot = null;
                worker.rightArmPivot = null;
                bool human = animator.avatar != null && animator.avatar.isHuman;
                log.AppendLine(human
                    ? "Worker: Mixamo model from " + WorkerModelPath + " (Humanoid avatar)."
                    : "Worker: model found but its Animator has no Humanoid avatar; set Rig > Animation Type = Humanoid on worker.fbx.");
                if (!human) Debug.LogWarning("[WarehouseHRI] worker.fbx is not imported as Humanoid; arm posing needs a Humanoid avatar.");
            }
            else
            {
                if (modelChild != null) Object.DestroyImmediate(modelChild.gameObject);
                var ph = Child(go, "Placeholder");
                var body = Primitive(ph, "Body", PrimitiveType.Capsule);
                body.transform.localPosition = new Vector3(0f, 0.75f, 0f);
                body.transform.localScale = new Vector3(0.4f, 0.75f, 0.3f);
                var head = Primitive(ph, "Head", PrimitiveType.Sphere);
                head.transform.localPosition = new Vector3(0f, 1.62f, 0f);
                head.transform.localScale = Vector3.one * 0.25f;
                var nose = Primitive(ph, "Nose", PrimitiveType.Cube);
                nose.transform.localPosition = new Vector3(0f, 1.62f, 0.13f);
                nose.transform.localScale = new Vector3(0.05f, 0.05f, 0.05f);
                worker.leftArmPivot = PlaceholderArm(ph, "LeftArmPivot", -0.26f);
                worker.rightArmPivot = PlaceholderArm(ph, "RightArmPivot", 0.26f);
                worker.animator = null;
                string msg = "worker.fbx not found at " + WorkerModelPath + "; using a capsule placeholder (arms are two pivots). " +
                             "Put the Mixamo worker.fbx there (it stays git-ignored), set Rig = Humanoid, and run Build Guided Scene again.";
                log.AppendLine("Worker: " + msg);
                Debug.LogWarning("[WarehouseHRI] " + msg);
            }

            EditorUtility.SetDirty(worker);
            return worker;
        }

        static Transform PlaceholderArm(GameObject parent, string name, float x)
        {
            var pivot = Child(parent, name);
            pivot.transform.localPosition = new Vector3(x, 1.38f, 0f);
            var arm = Primitive(pivot, "Arm", PrimitiveType.Cylinder);
            arm.transform.localRotation = Quaternion.Euler(90f, 0f, 0f); // cylinder axis along the pivot's +z
            arm.transform.localPosition = new Vector3(0f, 0f, 0.3f);
            arm.transform.localScale = new Vector3(0.08f, 0.3f, 0.08f);
            var palm = Primitive(pivot, "Hand", PrimitiveType.Cube);
            palm.transform.localPosition = new Vector3(0f, 0f, 0.64f);
            palm.transform.localScale = new Vector3(0.1f, 0.12f, 0.03f);
            return pivot.transform;
        }

        static void Bake(NavMeshSurface surface, Scene scene, StringBuilder log)
        {
            var old = surface.navMeshData;
            surface.RemoveData();
            surface.BuildNavMesh();
            if (surface.navMeshData == null)
            {
                log.AppendLine("NavMesh: bake produced no data.");
                return;
            }

            if (string.IsNullOrEmpty(scene.path))
            {
                log.AppendLine("NavMesh: baked, but the scene is unsaved, so the NavMesh asset was not written. Save the scene and run again.");
                return;
            }

            string dir = Path.Combine(Path.GetDirectoryName(scene.path) ?? "Assets", Path.GetFileNameWithoutExtension(scene.path)).Replace('\\', '/');
            if (!AssetDatabase.IsValidFolder(dir))
                AssetDatabase.CreateFolder(Path.GetDirectoryName(dir)?.Replace('\\', '/'), Path.GetFileName(dir));
            string assetPath = dir + "/" + NavMeshAssetName;
            if (old != null && AssetDatabase.Contains(old) && AssetDatabase.GetAssetPath(old) == assetPath)
                AssetDatabase.DeleteAsset(assetPath);
            else if (AssetDatabase.LoadAssetAtPath<NavMeshData>(assetPath) != null)
                AssetDatabase.DeleteAsset(assetPath);
            AssetDatabase.CreateAsset(surface.navMeshData, assetPath);
            AssetDatabase.SaveAssets();
            EditorUtility.SetDirty(surface);
            var tri = NavMesh.CalculateTriangulation();
            log.AppendLine($"NavMesh: baked ({tri.vertices.Length} vertices) and saved to {assetPath}.");
        }

        static void Validate(RoadNode[] nodes, StringBuilder log)
        {
            Physics.SyncTransforms();
            int problems = 0;
            foreach (var n in nodes)
            {
                if (!NavMesh.SamplePosition(n.Position, out var hit, 0.5f, NavMesh.AllAreas))
                {
                    log.AppendLine($"  WARNING {n.name}: not on the NavMesh (within 0.5 m).");
                    problems++;
                }

                foreach (var c in Physics.OverlapBox(n.Position + Vector3.up * 0.6f, new Vector3(0.5f, 0.5f, 0.5f)))
                {
                    if (c.GetComponentInParent<RoadNode>() != null || c.GetComponentInParent<DiffDriveRobot>() != null ||
                        c.GetComponentInParent<GestureWorker>() != null) continue;
                    log.AppendLine($"  WARNING {n.name}: collider '{c.name}' within 0.5 m.");
                    problems++;
                    break;
                }

                if (n.workerStand != null && !NavMesh.SamplePosition(n.workerStand.position, out _, 0.8f, NavMesh.AllAreas))
                {
                    log.AppendLine($"  WARNING {n.name}: worker stand not on the NavMesh.");
                    problems++;
                }

                foreach (var b in n.branches)
                {
                    var path = new NavMeshPath();
                    bool ok = NavMesh.SamplePosition(n.Position, out var p0, 1f, NavMesh.AllAreas) &&
                              NavMesh.SamplePosition(b.next.Position, out var p1, 1f, NavMesh.AllAreas) &&
                              NavMesh.CalculatePath(p0.position, p1.position, NavMesh.AllAreas, path) &&
                              path.status == NavMeshPathStatus.PathComplete;
                    float len = 0f;
                    for (int i = 0; ok && i < path.corners.Length - 1; i++) len += Vector3.Distance(path.corners[i], path.corners[i + 1]);
                    float straight = Vector3.Distance(n.Position, b.next.Position);
                    if (!ok)
                    {
                        log.AppendLine($"  WARNING {n.name} -> {b.next.name}: no complete NavMesh path.");
                        problems++;
                    }
                    else log.AppendLine($"  path {n.name} -> {b.next.name} ({b.command}): {len:0.00} m (straight {straight:0.00} m)");
                }
            }

            log.AppendLine(problems == 0 ? "Validation: all nodes on the NavMesh, no colliders at nodes, all branch paths complete."
                : $"Validation: {problems} problem(s); see warnings above and move the nodes in Roadmap.");
        }
    }
}
