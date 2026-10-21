using System;
using System.Collections;
using System.Globalization;
using System.IO;
using System.Text;
using UnityEngine;
using WarehouseHRI;
using WarehouseRobot.Bridge;

namespace WarehouseRobot.Scenario
{
    /// <summary>
    /// Saves one PNG per command (LEFT, FORWARD, RIGHT, STOP) from the robot's pan-tilt camera, the image Python's
    /// gesture reader gets, with the robot 2.0 m (hri_control.json approach_distance_m) from the worker: the worker at
    /// J1's stand, the robot on the line from J1 to the worker (where a Task 2 / Task 1 ask happens), facing the
    /// worker, pan 0; the worker faces the robot. For comparing the poses and the worker's look between machines.
    /// Output: robot_vision/outputs/gesture_pngs_&lt;time&gt;/ (git-ignored): LEFT.png, FORWARD.png, RIGHT.png, STOP.png,
    /// capture.json. Added by Tools > Warehouse HRI > Save Gesture PNGs (Play mode) or the batch entry
    /// WarehouseRobot.ScenarioEditor.GesturePngBatch.Run. Trials are stopped while it runs; nothing is scored.
    /// </summary>
    public class GesturePngCapture : MonoBehaviour
    {
        public const float DistanceM = 2.0f;
        public static readonly GestureCommand[] Commands = { GestureCommand.LEFT, GestureCommand.FORWARD, GestureCommand.RIGHT, GestureCommand.STOP };
        public float settleS = 1.0f;
        public string repoRootRelativeToProject = "../../..";

        public bool Done { get; private set; }
        public string Folder { get; private set; }
        public string Error { get; private set; }

        static readonly CultureInfo Inv = CultureInfo.InvariantCulture;

        void Start() => StartCoroutine(Capture());

        IEnumerator Capture()
        {
            var runner = FindFirstObjectByType<TrialRunner>();
            if (runner != null) { runner.StopAllCoroutines(); runner.enabled = false; }
            var bridge = FindFirstObjectByType<RobotBridgeClient>();
            if (bridge != null) bridge.enabled = false;            // no Python commands while capturing
            var robot = FindFirstObjectByType<RobotRig>();
            var worker = FindFirstObjectByType<GestureWorker>();
            RoadNode j1 = null;
            foreach (var n in FindObjectsByType<RoadNode>(FindObjectsSortMode.None)) if (n.name == "J1") j1 = n;
            if (robot == null || robot.PanTilt == null || worker == null || j1 == null || j1.workerStand == null)
            {
                Fail("need RobotRig with its pan-tilt camera, GestureWorker and roadmap node J1 with a worker stand");
                yield break;
            }

            while (!robot.PanTilt.Ready) yield return null;
            worker.faceTarget = null;
            worker.PlaceAt(j1.workerStand);
            Vector3 w = worker.transform.position;
            Vector3 toJ1 = j1.Position - w;
            toJ1.y = 0f;
            Vector3 rp = w + toJ1.normalized * DistanceM;
            rp.y = robot.transform.position.y;
            var rot = Quaternion.LookRotation(new Vector3(w.x - rp.x, 0f, w.z - rp.z), Vector3.up);
            var rb = robot.GetComponent<Rigidbody>();
            if (robot.Drive != null) robot.Drive.ResetMotion();
            if (rb != null) { rb.position = rp; rb.rotation = rot; }
            robot.transform.SetPositionAndRotation(rp, rot);
            robot.PanTilt.SetPanDeg(0f);
            worker.FaceTowards(rp);

            string repo = Path.GetFullPath(Path.Combine(Application.dataPath, "..", repoRootRelativeToProject));
            string root = Path.Combine(repo, "robot_vision", "outputs");
            Folder = Path.Combine(root, "gesture_pngs_" + DateTime.Now.ToString("yyyyMMdd_HHmmss", Inv));
            for (int i = 2; Directory.Exists(Folder); i++) Folder = Path.Combine(root, $"gesture_pngs_{DateTime.Now:yyyyMMdd_HHmmss}_{i}");
            Directory.CreateDirectory(Folder);

            var img = robot.PanTilt.Image;
            var tex = new Texture2D(img.width, img.height, TextureFormat.RGB24, false);
            foreach (var cmd in Commands)
            {
                worker.Show(cmd);
                float until = Time.realtimeSinceStartup + settleS;
                while (Time.realtimeSinceStartup < until) yield return null;
                yield return null;   // the camera has rendered a frame posed in the previous LateUpdate
                var prev = RenderTexture.active;
                RenderTexture.active = img;
                tex.ReadPixels(new Rect(0, 0, img.width, img.height), 0, 0);
                tex.Apply();
                RenderTexture.active = prev;
                File.WriteAllBytes(Path.Combine(Folder, cmd + ".png"), tex.EncodeToPNG());
            }

            worker.Show(GestureCommand.NONE);
            Destroy(tex);
            var cam = robot.PanTilt.Camera.transform.position;
            float dRobot = Vector2.Distance(new Vector2(rp.x, rp.z), new Vector2(w.x, w.z));
            float dCam = Vector2.Distance(new Vector2(cam.x, cam.z), new Vector2(w.x, w.z));
            var animator = worker.GetComponentInChildren<Animator>();
            var problems = WorkerAppearance.Problems(worker.gameObject);
            string F(float x) => x.ToString("0.000", Inv);
            string E(string s) => (s ?? "").Replace("\\", "\\\\").Replace("\"", "\\\"").Replace("\n", "\\n");
            var sb = new StringBuilder("{\n");
            sb.Append($"  \"commands\": [\"LEFT\", \"FORWARD\", \"RIGHT\", \"STOP\"],\n");
            sb.Append($"  \"image\": \"pan-tilt camera {img.width} x {img.height}, pan 0, the frame Python's gesture reader gets\",\n");
            sb.Append($"  \"worker_x\": {F(w.x)}, \"worker_z\": {F(w.z)}, \"worker_yaw_deg\": {F(worker.transform.eulerAngles.y)},\n");
            sb.Append($"  \"robot_x\": {F(rp.x)}, \"robot_z\": {F(rp.z)}, \"robot_yaw_deg\": {F(rot.eulerAngles.y)},\n");
            sb.Append($"  \"robot_to_worker_m\": {F(dRobot)}, \"camera_to_worker_m\": {F(dCam)},\n");
            sb.Append($"  \"placement\": \"worker at J1's stand; robot {DistanceM:0.0} m from it on the line toward J1, facing it\",\n");
            sb.Append($"  \"unity_version\": \"{Application.unityVersion}\", \"gpu\": \"{E(SystemInfo.graphicsDeviceName)}\",\n");
            sb.Append($"  \"worker_appearance\": \"{E(WorkerAppearance.Describe(worker.gameObject))}\",\n");
            sb.Append($"  \"worker_problems\": \"{E(string.Join("; ", problems))}\",\n");
            sb.Append($"  \"worker_avatar_bone_map_sha256\": \"{WorkerAppearance.Sha256(WorkerAppearance.BoneMap(animator))}\"\n}}\n");
            File.WriteAllText(Path.Combine(Folder, "capture.json"), sb.ToString());
            Debug.Log($"[GesturePngCapture] saved {Commands.Length} PNGs to {Folder}" + (problems.Count > 0 ? " (WORKER APPEARANCE PROBLEMS: " + string.Join("; ", problems) + ")" : ""));
            Done = true;
        }

        void Fail(string why)
        {
            Error = why;
            Debug.LogError("[GesturePngCapture] " + why);
            Done = true;
        }
    }
}
