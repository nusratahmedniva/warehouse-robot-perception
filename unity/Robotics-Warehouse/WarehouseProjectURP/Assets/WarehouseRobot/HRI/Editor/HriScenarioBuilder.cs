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
    /// Since 2026-10-21 it also builds the Task 1 workers (WarehouseHRI/Task1Workers, one instance of the same worker
    /// per Task 1 stop, positions from robot_vision/configs/task1_route.json); the group is saved INACTIVE, so Task 2
    /// and the gesture tools never see it, and the trial runner activates it only in Task 1 sessions.
    /// </summary>
    public static class HriScenarioBuilder
    {
        public const string RootName = "WarehouseHRI";
        public const string ScenePath = "Assets/Scenes/WarehouseRobot.unity";
        public const string WorkerModelPath = "Assets/WarehouseRobot/Characters/worker.fbx";
        /// <summary>Extracted Mixamo textures and the worker material; git-ignored like the FBX.</summary>
        public const string WorkerTextureDir = "Assets/WarehouseRobot/Characters/worker_textures";

        // Roadmap in floor coordinates (x, z), in the open aisles of the generated warehouse (rack centres at
        // x = -12.5, 0, 12.5 and z = -15, -5, 5, 15). Checked against the AMR NavMesh on every build. Must equal
        // robot_vision/configs/roadmap.json (Python's map): robot_vision/tests/test_trials.py compares them.
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
            BuildTask1Workers(root, a, log);

            var robot = FindByTypeName("RobotRig");
            if (robot != null) BuildViewCamera(root, robot, log);
            else log.AppendLine("WARNING: no RobotRig in the scene; the chase camera was not added.");

            // Step 7 trial runner (Assembly-CSharp; added by type name, this editor assembly does not reference it).
            var trialsGo = Child(root, "Trials");
            var runnerType = System.Type.GetType("WarehouseRobot.Scenario.TrialRunner, Assembly-CSharp");
            if (runnerType == null) log.AppendLine("WARNING: TrialRunner type not found; trials cannot run.");
            else if (trialsGo.GetComponent(runnerType) == null) trialsGo.AddComponent(runnerType);

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

        static void BuildWorker(GameObject root, RoadNode firstJunction, StringBuilder log) =>
            BuildWorkerAt(root, "Worker", firstJunction.workerStand.position, firstJunction.workerStand.rotation, log);

        // ---------------- Task 1 workers (declared design change, 2026-10-21) ----------------

        /// <summary>robot_vision/configs/task1_route.json, from the repository that contains this Unity project.</summary>
        public static string Task1RouteConfigPath =>
            Path.GetFullPath(Path.Combine(Path.GetDirectoryName(Application.dataPath) ?? ".", "..", "..", "..", "robot_vision", "configs", "task1_route.json"));

        /// <summary>
        /// One worker per Task 1 stop under WarehouseHRI/Task1Workers (Task1Route.WorkerStands: worker_ahead_m ahead
        /// and worker_right_m right of the stop, facing the arriving robot), built exactly like the scene's worker (same
        /// FBX, material, collider). The group is left inactive; workers of stops no longer in the config are removed.
        /// </summary>
        static void BuildTask1Workers(GameObject root, RoadNode start, StringBuilder log)
        {
            Task1RouteConfig cfg;
            try { cfg = JsonUtility.FromJson<Task1RouteConfig>(File.ReadAllText(Task1RouteConfigPath)); }
            catch (System.Exception e)
            {
                log.AppendLine("WARNING: Task 1 workers not built: cannot read " + Task1RouteConfigPath + ": " + e.Message);
                return;
            }

            var group = Child(root, Task1Route.WorkersGroup);
            group.SetActive(true);                 // build while active, save inactive
            var stands = Task1Route.WorkerStands(start, cfg);
            var keep = new HashSet<string>();
            var placed = new List<string>();
            foreach (var s in stands)
            {
                string name = Task1Route.WorkerName(s.Stop);
                keep.Add(name);
                BuildWorkerAt(group, name, s.Position, s.Rotation, log);
                placed.Add($"{s.Stop} ({s.Position.x:0.##}, {s.Position.z:0.##})");
                Physics.SyncTransforms();
                foreach (var c in Physics.OverlapCapsule(s.Position + Vector3.up * 0.4f, s.Position + Vector3.up * 1.6f, 0.25f, ~0, QueryTriggerInteraction.Ignore))
                    if (!c.transform.IsChildOf(group.transform) && FindRobotRoot(c.transform) == null)
                        log.AppendLine($"  WARNING Task 1 worker {name} overlaps {c.name}: move it (task1_route.json worker_ahead_m / worker_right_m).");
            }

            for (int i = group.transform.childCount - 1; i >= 0; i--)
            {
                var c = group.transform.GetChild(i);
                if (!keep.Contains(c.name)) Object.DestroyImmediate(c.gameObject);
            }

            group.SetActive(false);
            EditorUtility.SetDirty(group);
            log.AppendLine($"Task 1 workers (inactive group {Task1Route.WorkersGroup}, active only in Task 1 sessions): {string.Join(", ", placed)}.");
        }

        static Transform FindRobotRoot(Transform t)
        {
            for (; t != null; t = t.parent)
                foreach (var mb in t.GetComponents<MonoBehaviour>())
                    if (mb != null && mb.GetType().Name == "RobotRig") return t;
            return null;
        }

        static GestureWorker BuildWorkerAt(GameObject parent, string name, Vector3 position, Quaternion rotation, StringBuilder log)
        {
            var go = Child(parent, name);
            go.transform.SetPositionAndRotation(position, rotation);
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
                log.AppendLine(human ? name + ": Mixamo model (Humanoid avatar)." : name + ": model is not Humanoid; set Rig > Animation Type = Humanoid on worker.fbx.");
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
            return worker;
        }

        /// <summary>
        /// Mixamo FBX files embed their textures, which Unity does not extract by itself (the worker rendered pale
        /// and was hard to detect). Extract them once into a git-ignored folder and use an opaque URP Lit material.
        /// </summary>
        static void ApplyWorkerMaterial(GameObject model, StringBuilder log)
        {
            var mat = EnsureWorkerMaterial(log);
            if (mat == null) return;
            foreach (var r in model.GetComponentsInChildren<Renderer>(true))
            {
                var mats = new Material[Mathf.Max(1, r.sharedMaterials.Length)];
                for (int i = 0; i < mats.Length; i++) mats[i] = mat;
                r.sharedMaterials = mats;
            }
        }

        // ---------------- worker appearance (environment fix, 2026-10-21) ----------------

        public const string WorkerMaterialPath = WorkerTextureDir + "/Worker_URP.mat";
        /// <summary>
        /// The committed scene references the worker material by this GUID (created by Add Worker and Roadmap on the
        /// machine that built the scene). The material lives in the git-ignored texture folder, so on any other machine
        /// the reference was missing and the worker rendered magenta. It is now created with this fixed GUID everywhere,
        /// so the committed scene resolves on every machine without being changed.
        /// </summary>
        public const string WorkerMaterialGuid = "fececb7a5daa044cfabce1101932b943";

        [MenuItem("Tools/Warehouse HRI/Restore Worker Appearance")]
        public static void RestoreAppearanceMenu()
        {
            if (EditorApplication.isPlayingOrWillChangePlaymode)
            {
                EditorUtility.DisplayDialog("Warehouse HRI", "Leave Play mode first.", "OK");
                return;
            }

            string msg = RestoreAppearance();
            Debug.Log(msg);
            EditorUtility.DisplayDialog("Warehouse HRI", msg.Length > 900 ? msg.Substring(0, 900) + " ..." : msg, "OK");
        }

        /// <summary>Batch mode: Unity -batchmode -quit -projectPath P -executeMethod WarehouseHRI.EditorTools.HriScenarioBuilder.BatchRestoreAppearance</summary>
        public static void BatchRestoreAppearance()
        {
            EditorSceneManager.OpenScene(ScenePath);
            Debug.Log(RestoreAppearance());
        }

        /// <summary>
        /// Extracts the FBX textures (git-ignored), creates the URP Lit worker material with the fixed GUID and reports
        /// whether the open scene's worker now renders correctly. Changes the scene only if one of its worker renderers
        /// points at another material (then: save the scene); the committed scene needs no change.
        /// </summary>
        public static string RestoreAppearance()
        {
            var log = new StringBuilder("[WarehouseHRI] Restore Worker Appearance\n");
            var mat = EnsureWorkerMaterial(log);
            var workers = Object.FindObjectsOfType<GestureWorker>(true);   // the scene's worker and the inactive Task 1 workers
            if (workers.Length == 0)
            {
                log.AppendLine("No GestureWorker in the open scene (open Assets/Scenes/WarehouseRobot.unity).");
                return log.ToString();
            }

            int changed = 0;
            if (mat != null)
                foreach (var w in workers)
                foreach (var r in w.GetComponentsInChildren<Renderer>(true))
                {
                    var mats = r.sharedMaterials;
                    bool same = mats.Length > 0;
                    foreach (var m in mats) same &= m == mat;
                    if (same) continue;
                    var fixedMats = new Material[Mathf.Max(1, mats.Length)];
                    for (int i = 0; i < fixedMats.Length; i++) fixedMats[i] = mat;
                    r.sharedMaterials = fixedMats;
                    EditorUtility.SetDirty(r);
                    changed++;
                }

            if (changed > 0)
            {
                EditorSceneManager.MarkSceneDirty(SceneManager.GetActiveScene());
                log.AppendLine($"Re-assigned the worker material on {changed} renderer(s): save the scene.");
            }
            else log.AppendLine("The scene's worker already uses " + WorkerMaterialPath + " (no scene change).");

            foreach (var w in workers)
            {
                var problems = WorkerAppearance.Problems(w.gameObject);
                log.AppendLine(problems.Count == 0 ? $"Check passed ({w.name}): " + WorkerAppearance.Describe(w.gameObject)
                    : $"Still wrong ({w.name}): " + string.Join("; ", problems));
            }

            return log.ToString();
        }

        /// <summary>Textures extracted from worker.fbx (git-ignored folder) and the worker material with the fixed GUID.</summary>
        public static Material EnsureWorkerMaterial(StringBuilder log)
        {
            if (AssetDatabase.LoadAssetAtPath<GameObject>(WorkerModelPath) == null)
            {
                log.AppendLine("worker.fbx not found at " + WorkerModelPath + " (git-ignored: copy it from the team drive / Mixamo first).");
                return null;
            }

            if (!AssetDatabase.IsValidFolder(WorkerTextureDir))
                AssetDatabase.CreateFolder(Path.GetDirectoryName(WorkerTextureDir)?.Replace('\\', '/'), Path.GetFileName(WorkerTextureDir));
            var diffuse = FindDiffuse(log);
            if (diffuse == null)
            {
                var importer = AssetImporter.GetAtPath(WorkerModelPath) as ModelImporter;
                bool ok = importer != null && importer.ExtractTextures(WorkerTextureDir);
                AssetDatabase.Refresh();
                log.AppendLine(ok ? "Extracted the FBX textures to " + WorkerTextureDir + " (git-ignored)." : "worker.fbx has no extractable textures.");
                diffuse = FindDiffuse(log);
            }

            string guidNow = AssetDatabase.AssetPathToGUID(WorkerMaterialPath);
            if (!string.IsNullOrEmpty(guidNow) && guidNow != WorkerMaterialGuid && AssetDatabase.LoadAssetAtPath<Material>(WorkerMaterialPath) != null)
            {
                AssetDatabase.DeleteAsset(WorkerMaterialPath);
                log.AppendLine($"Replaced {WorkerMaterialPath} (GUID {guidNow}) by one with the scene's GUID {WorkerMaterialGuid}.");
            }

            var mat = AssetDatabase.LoadAssetAtPath<Material>(WorkerMaterialPath);
            if (mat == null)
            {
                string other = AssetDatabase.GUIDToAssetPath(WorkerMaterialGuid);
                if (!string.IsNullOrEmpty(other) && AssetDatabase.LoadMainAssetAtPath(other) != null)
                {
                    log.AppendLine($"GUID {WorkerMaterialGuid} already belongs to {other}; move or delete it, then run again.");
                    return null;
                }

                // Create at a temporary path, then copy the file next to a .meta with the fixed GUID: Unity imports a new
                // file with the GUID of its existing .meta.
                string tmp = WorkerTextureDir + "/Worker_URP_tmp.mat";
                AssetDatabase.CreateAsset(new Material(Shader.Find("Universal Render Pipeline/Lit")), tmp);
                AssetDatabase.SaveAssets();
                string projectDir = Path.GetDirectoryName(Application.dataPath);
                File.Copy(Path.Combine(projectDir, tmp), Path.Combine(projectDir, WorkerMaterialPath), true);
                File.WriteAllText(Path.Combine(projectDir, WorkerMaterialPath + ".meta"),
                    "fileFormatVersion: 2\nguid: " + WorkerMaterialGuid + "\nNativeFormatImporter:\n  externalObjects: {}\n" +
                    "  mainObjectFileID: 2100000\n  userData: \n  assetBundleName: \n  assetBundleVariant: \n");
                AssetDatabase.DeleteAsset(tmp);
                AssetDatabase.ImportAsset(WorkerMaterialPath, ImportAssetOptions.ForceUpdate);
                mat = AssetDatabase.LoadAssetAtPath<Material>(WorkerMaterialPath);
                if (mat == null || AssetDatabase.AssetPathToGUID(WorkerMaterialPath) != WorkerMaterialGuid)
                {
                    log.AppendLine("Could not create " + WorkerMaterialPath + " with GUID " + WorkerMaterialGuid + ".");
                    return null;
                }

                log.AppendLine($"Created {WorkerMaterialPath} with GUID {WorkerMaterialGuid} (git-ignored).");
            }

            if (mat.shader == null || mat.shader.name != "Universal Render Pipeline/Lit") mat.shader = Shader.Find("Universal Render Pipeline/Lit");
            mat.name = "Worker_URP";   // the copy keeps the temporary asset's internal name otherwise
            mat.SetTexture("_BaseMap", diffuse);
            mat.SetColor("_BaseColor", diffuse != null ? Color.white : new Color(0.25f, 0.35f, 0.55f));
            mat.SetFloat("_Surface", 0f);
            mat.SetFloat("_Smoothness", 0.25f);
            EditorUtility.SetDirty(mat);
            AssetDatabase.SaveAssets();
            log.AppendLine("Worker material: URP Lit, opaque, smoothness 0.25, base map " + (diffuse != null ? AssetDatabase.GetAssetPath(diffuse) : "NONE (no diffuse texture found)") + ".");
            return mat;
        }

        /// <summary>The extracted diffuse (albedo) texture: name contains "diffuse" or "albedo" (as before 2026-10-21).</summary>
        static Texture2D FindDiffuse(StringBuilder log)
        {
            var names = new List<string>();
            foreach (var guid in AssetDatabase.FindAssets("t:Texture2D", new[] { WorkerTextureDir }))
            {
                var path = AssetDatabase.GUIDToAssetPath(guid);
                names.Add(Path.GetFileName(path));
                if (path.IndexOf("diffuse", System.StringComparison.OrdinalIgnoreCase) >= 0 ||
                    path.IndexOf("albedo", System.StringComparison.OrdinalIgnoreCase) >= 0)
                    return AssetDatabase.LoadAssetAtPath<Texture2D>(path);
            }

            if (names.Count > 0) log.AppendLine("Textures in " + WorkerTextureDir + " but none named diffuse/albedo: " + string.Join(", ", names));
            return null;
        }

        // ---------------- worker check (import settings, avatar mapping) ----------------

        [MenuItem("Tools/Warehouse HRI/Check Worker (import settings, avatar, appearance)")]
        public static void CheckWorkerMenu()
        {
            string msg = CheckWorker(out string folder);
            Debug.Log(msg);
            EditorUtility.DisplayDialog("Warehouse HRI", (msg.Length > 900 ? msg.Substring(0, 900) + " ..." : msg) + "\n\nReport: " + folder, "OK");
        }

        /// <summary>Batch mode: -executeMethod WarehouseHRI.EditorTools.HriScenarioBuilder.BatchCheckWorker</summary>
        public static void BatchCheckWorker()
        {
            EditorSceneManager.OpenScene(ScenePath);
            Debug.Log(CheckWorker(out _));
        }

        /// <summary>
        /// The worker.fbx import settings against the values committed in worker.fbx.meta (Humanoid, avatar created from
        /// this model, mapping generated automatically), the Humanoid bone mapping Unity generated on this machine (the
        /// .meta stores none, so it depends on the FBX file and the Unity version: compare its sha256 between machines),
        /// the FBX sha256 and the scene worker's appearance. Writes robot_vision/outputs/worker_check_&lt;time&gt;/ (git-ignored).
        /// </summary>
        public static string CheckWorker(out string folder)
        {
            var log = new StringBuilder("[WarehouseHRI] Check Worker\n");
            var json = new StringBuilder("{\n");
            void Field(string k, string v, bool last = false) =>
                json.Append($"  \"{k}\": \"{(v ?? "").Replace("\\", "\\\\").Replace("\"", "\\\"").Replace("\n", "\\n")}\"{(last ? "" : ",")}\n");
            string projectDir = Path.GetDirectoryName(Application.dataPath);
            string repo = Path.GetFullPath(Path.Combine(projectDir, "..", "..", ".."));
            folder = Path.Combine(repo, "robot_vision", "outputs", "worker_check_" + System.DateTime.Now.ToString("yyyyMMdd_HHmmss"));
            Directory.CreateDirectory(folder);
            Field("unity_version", Application.unityVersion);
            Field("platform", SystemInfo.operatingSystem + " / " + SystemInfo.graphicsDeviceName);

            string fbx = Path.Combine(projectDir, WorkerModelPath);
            var importer = AssetImporter.GetAtPath(WorkerModelPath) as ModelImporter;
            if (importer == null || !File.Exists(fbx))
            {
                log.AppendLine("worker.fbx missing: " + WorkerModelPath);
                Field("error", "worker.fbx missing", true);
                File.WriteAllText(Path.Combine(folder, "worker_check.json"), json.Append("}\n").ToString());
                return log.ToString();
            }

            Field("worker_fbx_sha256", FinalRunGuard.Sha256File(fbx));
            Field("worker_fbx_meta_sha256_lf", FinalRunGuard.Sha256TextLf(fbx + ".meta"));
            var expected = new (string name, object got, object want)[]
            {
                ("animationType", importer.animationType, ModelImporterAnimationType.Human),
                ("avatarSetup", importer.avatarSetup, ModelImporterAvatarSetup.CreateFromThisModel),
                ("autoGenerateAvatarMappingIfUnspecified", importer.autoGenerateAvatarMappingIfUnspecified, true),
                // The committed .meta stores no mapping ("human: []"): Unity generates it at import (the importer API
                // then returns the generated bones, so the file is checked, not the API).
                ("worker.fbx.meta stores a bone mapping", !File.ReadAllText(fbx + ".meta").Contains("    human: []"), false),
                ("materialImportMode", importer.materialImportMode, ModelImporterMaterialImportMode.ImportViaMaterialDescription),
                ("materialLocation", importer.materialLocation, ModelImporterMaterialLocation.InPrefab),
                ("globalScale", importer.globalScale, 1f),
                ("useFileUnits", importer.useFileUnits, true),
                ("optimizeGameObjects", importer.optimizeGameObjects, false),
                ("importAnimation", importer.importAnimation, true),
            };
            int bad = 0;
            var lines = new List<string>();
            foreach (var e in expected)
            {
                bool ok = Equals(e.got, e.want);
                if (!ok) bad++;
                lines.Add($"{e.name}: {e.got}{(ok ? "" : $" (committed .meta: {e.want})")}");
            }

            Field("import_settings", string.Join("\n", lines));
            Field("import_settings_match_committed_meta", bad == 0 ? "yes" : $"no ({bad} differ)");
            log.AppendLine(bad == 0 ? "Import settings: equal to the committed worker.fbx.meta (Humanoid, avatar from this model, mapping generated)."
                : $"Import settings: {bad} differ from the committed .meta:\n  " + string.Join("\n  ", lines));

            Avatar avatar = null;
            foreach (var o in AssetDatabase.LoadAllAssetsAtPath(WorkerModelPath))
                if (o is Avatar a) avatar = a;
            var map = new List<string>();
            if (avatar != null)
                foreach (var hb in avatar.humanDescription.human) map.Add(hb.humanName + "=" + hb.boneName);
            map.Sort(System.StringComparer.Ordinal);
            string mapText = string.Join("\n", map);
            Field("avatar_valid_human", avatar != null && avatar.isValid && avatar.isHuman ? "yes" : "no");
            Field("avatar_mapping_count", map.Count.ToString());
            Field("avatar_mapping_sha256", WorkerAppearance.Sha256(mapText));
            File.WriteAllText(Path.Combine(folder, "avatar_mapping.txt"), mapText + "\n");
            log.AppendLine($"Avatar: {(avatar != null && avatar.isHuman ? "Humanoid" : "NOT Humanoid")}, {map.Count} bones mapped, mapping sha256 {WorkerAppearance.Sha256(mapText)} (compare with the other machine).");

            var worker = Object.FindObjectOfType<GestureWorker>(true);
            if (worker != null)
            {
                var problems = WorkerAppearance.Problems(worker.gameObject);
                var animator = worker.GetComponentInChildren<Animator>(true);
                string sceneMap = WorkerAppearance.BoneMap(animator);
                Field("scene_worker_appearance", WorkerAppearance.Describe(worker.gameObject));
                Field("scene_worker_problems", string.Join("; ", problems));
                Field("scene_worker_bone_map_sha256", WorkerAppearance.Sha256(sceneMap));   // = session.json worker_avatar_bone_map_sha256
                log.AppendLine(problems.Count == 0 ? "Scene worker: renders correctly (" + WorkerAppearance.Describe(worker.gameObject) + ")."
                    : "Scene worker: " + string.Join("; ", problems));
            }
            else Field("scene_worker_problems", "no GestureWorker in the open scene");

            Field("note", "Report only; nothing in the project was changed.", true);
            File.WriteAllText(Path.Combine(folder, "worker_check.json"), json.Append("}\n").ToString());
            log.AppendLine("Report: " + folder);
            return log.ToString();
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
