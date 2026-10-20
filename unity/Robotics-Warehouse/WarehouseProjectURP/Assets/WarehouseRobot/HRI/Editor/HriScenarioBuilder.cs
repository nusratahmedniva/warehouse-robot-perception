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
    /// "Tools > Warehouse HRI > Add Worker and Roadmap": adds to the open scene, under one root "WarehouseHRI", the
    /// guided-task pieces the team's Step 1-2 scene does not have yet: the Mixamo worker (GestureWorker; capsule
    /// placeholder when worker.fbx is missing), a 2-junction roadmap with 4 endpoints (RoadNode, worker stands) and a
    /// chase camera (FollowCamera, C cycles chase / top-down / gesture camera). It never edits the robot prefab, the
    /// bridge or the NavMesh; the robot and its pan-tilt camera are found by component type name (RobotRig,
    /// PanTiltCamera), so this editor assembly does not depend on theirs. Safe to run again (found by name).
    /// </summary>
    public static class HriScenarioBuilder
    {
        public const string RootName = "WarehouseHRI";
        public const string ScenePath = "Assets/Scenes/WarehouseRobot.unity";
        public const string WorkerModelPath = "Assets/WarehouseRobot/Characters/worker.fbx";
        /// <summary>Extracted Mixamo textures and the worker material; git-ignored like the FBX.</summary>
        public const string WorkerTextureDir = "Assets/WarehouseRobot/Characters/worker_textures";

        // Roadmap in floor coordinates (x, z), in the open aisles of the generated warehouse (rack centres at
        // x = -12.5, 0, 12.5 and z = -15, -5, 5, 15). Checked against the AMR NavMesh on every build.
        static readonly Vector2 k_A = new Vector2(6.25f, -10f);
        static readonly Vector2 k_J1 = new Vector2(6.25f, 0f);
        static readonly Vector2 k_J2 = new Vector2(-6.25f, 0f);
        static readonly Vector2 k_E1 = new Vector2(6.25f, 10f);    // J1 FORWARD
        static readonly Vector2 k_E2 = new Vector2(18.75f, 0f);    // J1 RIGHT
        static readonly Vector2 k_E3 = new Vector2(-18.75f, 0f);   // J2 FORWARD
        static readonly Vector2 k_E4 = new Vector2(-6.25f, 10f);   // J2 RIGHT
        const float WorkerCornerOffset = 2.5f;

        [MenuItem("Tools/Warehouse HRI/Add Worker and Roadmap")]
        public static void BuildMenu()
        {
            if (EditorApplication.isPlayingOrWillChangePlaymode)
            {
                EditorUtility.DisplayDialog("Warehouse HRI", "Leave Play mode first.", "OK");
                return;
            }

            Build();
        }

        /// <summary>Batch mode: Unity -batchmode -quit -projectPath P -executeMethod WarehouseHRI.EditorTools.HriScenarioBuilder.BatchBuild</summary>
        public static void BatchBuild()
        {
            EditorSceneManager.OpenScene(ScenePath);
            Build();
            if (!EditorSceneManager.SaveScene(SceneManager.GetActiveScene())) throw new System.Exception("Could not save " + ScenePath);
        }

        public static string Build()
        {
            var log = new StringBuilder();
            var root = FindOrCreateRoot();
            float floorY = 0f;

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

            BuildWorker(root, j1, log);

            var robot = FindByTypeName("RobotRig");
            if (robot != null) BuildViewCamera(root, robot, log);
            else log.AppendLine("WARNING: no RobotRig in the scene; the chase camera was not added.");

            DisableOversizedCarvingObstacles(log);
            Validate(new[] { a, j1, j2, e1, e2, e3, e4 }, log);
            EditorSceneManager.MarkSceneDirty(SceneManager.GetActiveScene());
            string msg = "[WarehouseHRI] Add Worker and Roadmap finished. Save the scene.\n" + log;
            Debug.Log(msg);
            return msg;
        }

        // ---------------- pose test ----------------

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
                Debug.LogWarning("[WarehouseHRI] No GestureWorker in the scene. Run Add Worker and Roadmap first.");
                return;
            }

            var cycler = worker.GetComponent<GesturePoseCycler>();
            if (cycler == null) cycler = worker.gameObject.AddComponent<GesturePoseCycler>();
            cycler.worker = worker;
            cycler.enabled = true;
            var view = Camera.main;
            if (view != null)
            {
                var follow = view.GetComponent<FollowCamera>();
                if (follow != null) follow.enabled = false; // the pose test places the camera itself
                view.transform.position = worker.transform.position + worker.transform.forward * 3f + Vector3.up * 1.3f;
                view.transform.LookAt(worker.transform.position + Vector3.up * 1.2f);
                worker.faceTarget = view.transform;
            }

            Selection.activeGameObject = worker.gameObject;
            Debug.Log("[WarehouseHRI] Gesture pose test: LEFT, FORWARD_LEFT, FORWARD, FORWARD_RIGHT, RIGHT, STOP (NONE between), " +
                      "from the robot's (viewer's) point of view.");
        }

        // ---------------- pieces ----------------

        static GameObject FindOrCreateRoot()
        {
            foreach (var go in SceneManager.GetActiveScene().GetRootGameObjects())
                if (go.name == RootName) return go;
            var created = new GameObject(RootName);
            Undo.RegisterCreatedObjectUndo(created, "Add Worker and Roadmap");
            return created;
        }

        static GameObject Child(GameObject parent, string name)
        {
            var t = parent.transform.Find(name);
            if (t != null) return t.gameObject;
            var go = new GameObject(name);
            go.transform.SetParent(parent.transform, false);
            Undo.RegisterCreatedObjectUndo(go, "Add Worker and Roadmap");
            return go;
        }

        static GameObject Primitive(GameObject parent, string name, PrimitiveType type)
        {
            var t = parent.transform.Find(name);
            if (t != null) return t.gameObject;
            var go = GameObject.CreatePrimitive(type);
            go.name = name;
            go.transform.SetParent(parent.transform, false);
            Object.DestroyImmediate(go.GetComponent<Collider>());
            Undo.RegisterCreatedObjectUndo(go, "Add Worker and Roadmap");
            return go;
        }

        static T GetOrAdd<T>(GameObject go) where T : Component
        {
            var c = go.GetComponent<T>();
            return c != null ? c : go.AddComponent<T>();
        }

        /// <summary>A scene object carrying a component with this class name (any assembly).</summary>
        static GameObject FindByTypeName(string typeName)
        {
            foreach (var mb in Object.FindObjectsOfType<MonoBehaviour>(true))
                if (mb != null && mb.GetType().Name == typeName) return mb.gameObject;
            return null;
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

        /// <summary>Branch commands from geometry: the turn from the arrival direction (prev -> node) to each next node.</summary>
        static void Link(RoadNode node, RoadNode previous, params RoadNode[] next)
        {
            node.branches = new List<RoadBranch>();
            Vector3 arrive = previous != null ? node.Position - previous.Position : Vector3.forward;
            arrive.y = 0f;
            foreach (var n in next)
            {
                Vector3 d = n.Position - node.Position;
                d.y = 0f;
                var cmd = previous == null ? GestureCommand.FORWARD : GestureCommands.FromTurnAngle(Vector3.SignedAngle(arrive, d, Vector3.up));
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
            standGo.transform.rotation = Quaternion.LookRotation(-arrive, Vector3.up);
            junction.workerStand = standGo.transform;
            EditorUtility.SetDirty(junction);
        }

        static string Describe(RoadNode n)
        {
            var parts = new List<string>();
            foreach (var b in n.branches) parts.Add($"{b.command}->{b.next.name}");
            return $"{n.name}[{string.Join(", ", parts)}]";
        }

        static void BuildWorker(GameObject root, RoadNode firstJunction, StringBuilder log)
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

                ApplyWorkerMaterial(modelChild.gameObject, log);
                var animator = modelChild.GetComponentInChildren<Animator>();
                if (animator == null) animator = modelChild.gameObject.AddComponent<Animator>();
                worker.animator = animator;
                worker.leftArmPivot = null;
                worker.rightArmPivot = null;
                bool human = animator.avatar != null && animator.avatar.isHuman;
                log.AppendLine(human ? "Worker: Mixamo model (Humanoid avatar)." : "Worker: model is not Humanoid; set Rig > Animation Type = Humanoid on worker.fbx.");
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
                worker.leftArmPivot = PlaceholderArm(ph, "LeftArmPivot", -0.26f);
                worker.rightArmPivot = PlaceholderArm(ph, "RightArmPivot", 0.26f);
                worker.animator = null;
                string msg = "worker.fbx not found at " + WorkerModelPath + "; using a capsule placeholder (no keypoints for vision).";
                log.AppendLine("Worker: " + msg);
                Debug.LogWarning("[WarehouseHRI] " + msg);
            }

            EditorUtility.SetDirty(worker);
        }

        /// <summary>
        /// Mixamo FBX files embed their textures, which Unity does not extract by itself (the worker rendered pale
        /// and was hard to detect). Extract them once into a git-ignored folder and use an opaque URP Lit material.
        /// </summary>
        static void ApplyWorkerMaterial(GameObject model, StringBuilder log)
        {
            if (!AssetDatabase.IsValidFolder(WorkerTextureDir))
            {
                var importer = AssetImporter.GetAtPath(WorkerModelPath) as ModelImporter;
                AssetDatabase.CreateFolder(Path.GetDirectoryName(WorkerTextureDir)?.Replace('\\', '/'), Path.GetFileName(WorkerTextureDir));
                bool ok = importer != null && importer.ExtractTextures(WorkerTextureDir);
                AssetDatabase.Refresh();
                log.AppendLine(ok ? "Worker: extracted the FBX textures to " + WorkerTextureDir + " (git-ignored)." : "Worker: no extractable textures.");
            }

            Texture2D diffuse = null;
            foreach (var guid in AssetDatabase.FindAssets("t:Texture2D", new[] { WorkerTextureDir }))
            {
                var path = AssetDatabase.GUIDToAssetPath(guid);
                if (path.IndexOf("diffuse", System.StringComparison.OrdinalIgnoreCase) >= 0 ||
                    path.IndexOf("albedo", System.StringComparison.OrdinalIgnoreCase) >= 0)
                {
                    diffuse = AssetDatabase.LoadAssetAtPath<Texture2D>(path);
                    break;
                }
            }

            string matPath = WorkerTextureDir + "/Worker_URP.mat";
            var mat = AssetDatabase.LoadAssetAtPath<Material>(matPath);
            if (mat == null)
            {
                mat = new Material(Shader.Find("Universal Render Pipeline/Lit"));
                AssetDatabase.CreateAsset(mat, matPath);
            }

            mat.SetTexture("_BaseMap", diffuse);
            mat.SetColor("_BaseColor", diffuse != null ? Color.white : new Color(0.25f, 0.35f, 0.55f));
            mat.SetFloat("_Surface", 0f);
            mat.SetFloat("_Smoothness", 0.25f);
            EditorUtility.SetDirty(mat);
            foreach (var r in model.GetComponentsInChildren<Renderer>(true))
            {
                var mats = new Material[Mathf.Max(1, r.sharedMaterials.Length)];
                for (int i = 0; i < mats.Length; i++) mats[i] = mat;
                r.sharedMaterials = mats;
            }
        }

        static Transform PlaceholderArm(GameObject parent, string name, float x)
        {
            var pivot = Child(parent, name);
            pivot.transform.localPosition = new Vector3(x, 1.38f, 0f);
            var arm = Primitive(pivot, "Arm", PrimitiveType.Cylinder);
            arm.transform.localRotation = Quaternion.Euler(90f, 0f, 0f);
            arm.transform.localPosition = new Vector3(0f, 0f, 0.3f);
            arm.transform.localScale = new Vector3(0.08f, 0.3f, 0.08f);
            var palm = Primitive(pivot, "Hand", PrimitiveType.Cube);
            palm.transform.localPosition = new Vector3(0f, 0f, 0.64f);
            palm.transform.localScale = new Vector3(0.1f, 0.12f, 0.03f);
            return pivot.transform;
        }

        /// <summary>Game-view chase camera; the scene's old camera objects are disabled.</summary>
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
            follow.gestureCamera = PanTiltCameraOf(robot);
            follow.mode = FollowCameraMode.Chase;
            Vector3 fwd = robot.transform.forward;
            go.transform.SetPositionAndRotation(robot.transform.position - fwd * follow.chaseDistanceM + Vector3.up * follow.chaseHeightM,
                Quaternion.LookRotation(fwd * (follow.chaseDistanceM + follow.lookAheadM) + Vector3.up * (follow.lookHeightM - follow.chaseHeightM)));
            EditorUtility.SetDirty(follow);
            foreach (var other in SceneManager.GetActiveScene().GetRootGameObjects())
            {
                if (other == root || other.GetComponent<Camera>() == null || !other.activeSelf) continue;
                other.SetActive(false);
                log.AppendLine($"Disabled the camera object '{other.name}' (replaced by the chase camera).");
            }

            log.AppendLine($"Chase camera on '{robot.name}' (C: chase / top-down / gesture camera{(follow.gestureCamera == null ? ", gesture camera not found" : "")}).");
        }

        /// <summary>The Camera of the robot's PanTiltCamera component (found by type name and its 'Camera' property).</summary>
        static Camera PanTiltCameraOf(GameObject robot)
        {
            foreach (var mb in robot.GetComponentsInChildren<MonoBehaviour>(true))
            {
                if (mb == null || mb.GetType().Name != "PanTiltCamera") continue;
                var prop = mb.GetType().GetProperty("Camera");
                if (prop?.GetValue(mb) is Camera c) return c;
                return mb.GetComponentInChildren<Camera>(true);
            }

            return null;
        }

        /// <summary>
        /// The upstream rack prefab carries carving NavMeshObstacles whose extents are centimetre values used as
        /// metres (about 120 x 370 x 370 m each); enabled, they carve away the whole NavMesh, so every path query
        /// fails. Disable carving obstacles larger than 10 m in the scene; the racks still block the NavMesh through
        /// their colliders in the bake. Vendored prefabs are not edited.
        /// </summary>
        static void DisableOversizedCarvingObstacles(StringBuilder log)
        {
            int n = 0;
            foreach (var o in Object.FindObjectsOfType<NavMeshObstacle>(true))
            {
                Vector3 s = Vector3.Scale(o.size, o.transform.lossyScale);
                if (!o.enabled || !o.carving || Mathf.Max(Mathf.Abs(s.x), Mathf.Abs(s.y), Mathf.Abs(s.z)) <= 10f) continue;
                o.enabled = false;
                EditorUtility.SetDirty(o);
                n++;
            }

            if (n > 0) log.AppendLine($"Disabled {n} oversized carving NavMeshObstacle(s) on the racks (they erased the whole NavMesh).");
        }

        /// <summary>Nodes and branch paths on the team's AMR NavMesh (log only; the NavMesh itself is not touched).</summary>
        static void Validate(RoadNode[] nodes, StringBuilder log)
        {
            // The agent type of the scene's NavMesh Surface, as the team's bridge does (the AMR agent).
            int agent = int.MinValue;
            foreach (var surface in Object.FindObjectsOfType<NavMeshSurface>())
                if (surface.navMeshData != null) { agent = surface.agentTypeID; break; }
            if (agent == int.MinValue)
            {
                log.AppendLine("Validation skipped: no NavMesh Surface with baked data in the scene.");
                return;
            }

            var filter = new NavMeshQueryFilter { agentTypeID = agent, areaMask = NavMesh.AllAreas };
            int problems = 0;
            foreach (var n in nodes)
            {
                if (!NavMesh.SamplePosition(n.Position, out _, 0.5f, filter))
                {
                    log.AppendLine($"  WARNING {n.name}: not on the AMR NavMesh (within 0.5 m).");
                    problems++;
                }

                foreach (var b in n.branches)
                {
                    var path = new NavMeshPath();
                    bool ok = NavMesh.SamplePosition(n.Position, out var p0, 1f, filter) &&
                              NavMesh.SamplePosition(b.next.Position, out var p1, 1f, filter) &&
                              NavMesh.CalculatePath(p0.position, p1.position, filter, path) &&
                              path.status == NavMeshPathStatus.PathComplete;
                    if (!ok)
                    {
                        log.AppendLine($"  WARNING {n.name} -> {b.next.name}: no complete AMR path.");
                        problems++;
                    }
                }
            }

            log.AppendLine(problems == 0 ? $"Validation: all roadmap nodes and branch paths are on the NavMesh (agent {NavMesh.GetSettingsNameFromID(agent)})."
                : $"Validation: {problems} problem(s) on the AMR NavMesh; move the nodes in Roadmap.");
        }
    }
}
