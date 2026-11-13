using System;
using System.Collections.Generic;
using System.Globalization;
using UnityEngine;
using WarehouseHRI;
using WarehouseHRI.V4;
using WarehouseRobot.Bridge;

namespace WarehouseRobot.GroundTruth
{
    /// <summary>
    /// v4 path visualisation (2026-11-12, U4; Avatar/Config/upgrade_design.md section 8 and its section 13 entry). Every object
    /// is on the GroundTruth layer, which both robot cameras skip (the leak test checks it), so none of it can reach the robot:
    /// - the trail, coloured by the robot's state (the light-ring colours) with a direction arrow every 2 m;
    /// - a floor marker at each ask: the command read, the branch chosen and the command shown; green if the branch is the true
    ///   branch toward B, red if not, grey while asking or if the dialog aborted;
    /// - the instructed path: after each accepted instruction the road from the node to the branch's next node, drawn apart
    ///   from the optimal path.
    /// Toggle keys (Game view): F5 trail, F6 ask markers, F7 instructed path, F8 optimal path (A, B and the path); F4 is the
    /// HUD and F9 / F10 the minimaps (MinimapV4). The trial runner calls Begin and End per trial; the visuals stay until the
    /// next Begin.
    /// </summary>
    [DisallowMultipleComponent]
    public class RunVisualsV4 : MonoBehaviour
    {
        public bool showTrail = true, showMarkers = true, showInstructed = true, showOptimal = true;
        public float sampleIntervalS = 0.1f, arrowEveryM = 2f;

        static readonly CultureInfo Inv = CultureInfo.InvariantCulture;
        GroundTruthLayer gt;
        RobotRig robot;
        RobotBridgeClient bridge;
        Func<RoadNode> askNode;
        Func<string> shownCommand;
        RoadNode goal;
        string prompt;
        Transform root, trailRoot, markerRoot, instructedRoot;
        LineRenderer chunk;
        RobotStatus.Light chunkLight;
        Vector3 lastSample, lastArrow;
        float nextSample, sinceArrow;
        bool active, asking;
        string lastScreen = "";
        GameObject openMarker;
        RoadNode openNode;
        string lastState = "", lastRead = "-";
        readonly Dictionary<RobotStatus.Light, Material> mats = new Dictionary<RobotStatus.Light, Material>();
        Material green, red, grey, instructed;
        static Mesh arrowMesh;

        public void Begin(GroundTruthLayer layer, RobotRig rig, RobotBridgeClient client, RoadNode goalNode, string questionPrompt,
                          Func<RoadNode> currentAskNode, Func<string> commanderShows)
        {
            gt = layer;
            robot = rig;
            bridge = client;
            goal = goalNode;
            prompt = questionPrompt ?? "";
            askNode = currentAskNode;
            shownCommand = commanderShows;
            if (root != null) Destroy(root.gameObject);
            root = Child(transform, "RunVisualsV4");
            trailRoot = Child(root, "Trail");
            markerRoot = Child(root, "AskMarkers");
            instructedRoot = Child(root, "InstructedPath");
            if (mats.Count == 0)
            {
                foreach (RobotStatus.Light l in Enum.GetValues(typeof(RobotStatus.Light))) mats[l] = GroundTruthLayer.NewMaterial(RobotStatus.ColorFor(l));
                green = GroundTruthLayer.NewMaterial(new Color(0.1f, 0.85f, 0.25f, 0.9f));
                red = GroundTruthLayer.NewMaterial(new Color(0.95f, 0.1f, 0.1f, 0.9f));
                grey = GroundTruthLayer.NewMaterial(new Color(0.6f, 0.6f, 0.6f, 0.9f));
                instructed = GroundTruthLayer.NewMaterial(new Color(0.1f, 0.85f, 1f, 0.95f));
            }
            chunk = null;
            lastSample = lastArrow = Flat(robot.transform.position);
            sinceArrow = 0f;
            nextSample = Time.time;
            asking = false;
            openMarker = null;
            openNode = null;
            lastScreen = "";
            lastState = "";
            active = true;
            ApplyVisibility();
        }

        /// <summary>The trial is over: a dialog still open is closed as aborted; the drawing stays until the next Begin.</summary>
        public void End()
        {
            if (!active) return;
            Sample(true);
            if (openMarker != null) CloseMarker(null);
            active = false;
        }

        void Update()
        {
            if (!active || robot == null || bridge == null) return;
            if (Time.time >= nextSample) { nextSample += sampleIntervalS; Sample(false); }
            string screen = bridge.ScreenText ?? "";
            bool question = prompt.Length > 0 && screen.StartsWith(prompt, StringComparison.Ordinal);
            if (question && (!asking || screen != lastScreen)) OpenMarker();
            asking = question || (asking && !string.IsNullOrEmpty(screen));
            lastScreen = screen;
            string state = bridge.State ?? "";
            var hud = bridge.Hud;
            if (openMarker != null && hud != null && hud.gesture != "NONE" && hud.gesture != "STOP") lastRead = hud.gesture;
            if (openMarker != null && state.StartsWith("execute") && !lastState.StartsWith("execute"))
            {
                string accepted = bridge.Hud != null ? bridge.Hud.gesture_accepted : "NONE";
                CloseMarker(accepted);
                DrawInstructed(openNode != null ? openNode : askNode?.Invoke(), accepted);
                openNode = null;
            }
            if (openMarker != null && state.StartsWith("aborted")) CloseMarker(null);
            lastState = state;
        }

        void Sample(bool force)
        {
            Vector3 p = Flat(robot.transform.position);
            var light = RobotStatus.LightFor(bridge.State);
            if (chunk == null || light != chunkLight)
            {
                chunk = NewLine(trailRoot, "Trail_" + light, mats[light], 0.07f);
                chunkLight = light;
                chunk.positionCount = 1;
                chunk.SetPosition(0, lastSample + Vector3.up * 0.03f);        // joins the previous chunk
            }
            if (!force && (p - lastSample).sqrMagnitude < 1e-6f) return;
            chunk.positionCount++;
            chunk.SetPosition(chunk.positionCount - 1, p + Vector3.up * 0.03f);
            sinceArrow += (p - lastSample).magnitude;
            if (sinceArrow >= arrowEveryM && (p - lastArrow).sqrMagnitude > 1e-4f)
            {
                Arrow(p, p - lastArrow, mats[light]);
                lastArrow = p;
                sinceArrow = 0f;
            }
            lastSample = p;
        }

        void OpenMarker()
        {
            if (openMarker != null) CloseMarker(null);       // the previous ask of the same dialog: kept grey
            openNode = askNode?.Invoke();
            lastRead = "-";
            Vector3 p = Flat(robot.transform.position);
            openMarker = new GameObject("Ask " + (openNode != null ? openNode.name : "?")) { layer = gt.Layer };
            openMarker.transform.SetParent(markerRoot, false);
            openMarker.transform.position = p;
            var disc = Prim(PrimitiveType.Cylinder, openMarker.transform, new Vector3(0f, 0.02f, 0f), new Vector3(0.5f, 0.005f, 0.5f), grey);
            disc.name = "Disc";
            var text = new GameObject("Label") { layer = gt.Layer };
            text.transform.SetParent(openMarker.transform, false);
            text.transform.localPosition = new Vector3(0f, 0.05f, 0f);
            text.transform.rotation = Quaternion.Euler(90f, 0f, 0f);
            var tm = text.AddComponent<TextMesh>();
            var font = Resources.GetBuiltinResource<Font>("LegacyRuntime.ttf");
            tm.font = font;
            var mr = text.GetComponent<MeshRenderer>();
            mr.sharedMaterial = font.material;
            tm.anchor = TextAnchor.UpperCenter;
            tm.characterSize = 0.03f;
            tm.fontSize = 40;
            tm.color = Color.white;
            tm.text = "asking at " + (openNode != null ? openNode.name : "?");
        }

        /// <summary>Close the open ask marker: accepted = the branch the robot took, or null when the dialog ended without one.</summary>
        void CloseMarker(string accepted)
        {
            var node = openNode != null ? openNode : askNode?.Invoke();
            string truth = node != null && goal != null ? node.CommandToward(goal).ToString() : "NONE";
            string shown = shownCommand?.Invoke() ?? "?";
            bool taken = !string.IsNullOrEmpty(accepted) && accepted != "NONE" && accepted != "WAIT";
            var mat = !taken ? grey : accepted == truth ? green : red;
            var disc = openMarker.transform.Find("Disc");
            if (disc != null) GroundTruthLayer.Unshadowed(disc.GetComponent<Renderer>(), mat);
            var tm = openMarker.GetComponentInChildren<TextMesh>();
            if (tm != null)
                tm.text = $"{(node != null ? node.name : "?")}: read {lastRead}\nbranch {(taken ? accepted : "none")}\nshown {shown} (true {truth})";
            openMarker = null;
        }

        void DrawInstructed(RoadNode node, string accepted)
        {
            if (node == null || string.IsNullOrEmpty(accepted)) return;
            if (!Enum.TryParse(accepted, out GestureCommand cmd)) return;
            var next = node.Next(cmd);
            if (next == null) return;
            var lr = NewLine(instructedRoot, $"Instructed {node.name}->{next.name}", instructed, 0.12f);
            lr.positionCount = 2;
            lr.SetPosition(0, Flat(node.Position) + Vector3.up * 0.05f);
            lr.SetPosition(1, Flat(next.Position) + Vector3.up * 0.05f);
        }

        void OnGUI()
        {
            var e = Event.current;
            if (e.type != EventType.KeyDown) return;
            bool changed = true;
            switch (e.keyCode)
            {
                case KeyCode.F5: showTrail = !showTrail; break;
                case KeyCode.F6: showMarkers = !showMarkers; break;
                case KeyCode.F7: showInstructed = !showInstructed; break;
                case KeyCode.F8: showOptimal = !showOptimal; break;
                default: changed = false; break;
            }
            if (changed) ApplyVisibility();
        }

        public void ApplyVisibility()
        {
            if (trailRoot != null) trailRoot.gameObject.SetActive(showTrail);
            if (markerRoot != null) markerRoot.gameObject.SetActive(showMarkers);
            if (instructedRoot != null) instructedRoot.gameObject.SetActive(showInstructed);
            if (gt != null && gt.RunVisuals != null) gt.RunVisuals.SetActive(showOptimal);
        }

        // ---------------------------------------------------------------- drawing helpers (GroundTruth layer only)

        Vector3 Flat(Vector3 p) => new Vector3(p.x, gt != null ? gt.FloorY : 0f, p.z);

        Transform Child(Transform parent, string name)
        {
            var go = new GameObject(name) { layer = gt != null ? gt.Layer : 0 };
            go.transform.SetParent(parent, false);
            return go.transform;
        }

        LineRenderer NewLine(Transform parent, string name, Material mat, float width)
        {
            var go = new GameObject(name) { layer = gt.Layer };
            go.transform.SetParent(parent, false);
            var lr = go.AddComponent<LineRenderer>();
            GroundTruthLayer.Unshadowed(lr, mat);
            lr.useWorldSpace = true;
            lr.widthMultiplier = width;
            lr.positionCount = 0;
            lr.alignment = LineAlignment.TransformZ;
            go.transform.rotation = Quaternion.Euler(90f, 0f, 0f);                     // flat on the floor
            return lr;
        }

        GameObject Prim(PrimitiveType type, Transform parent, Vector3 localPos, Vector3 scale, Material mat)
        {
            var p = GameObject.CreatePrimitive(type);
            Destroy(p.GetComponent<Collider>());
            p.layer = gt.Layer;
            p.transform.SetParent(parent, false);
            p.transform.localPosition = localPos;
            p.transform.localScale = scale;
            GroundTruthLayer.Unshadowed(p.GetComponent<Renderer>(), mat);
            return p;
        }

        void Arrow(Vector3 at, Vector3 dir, Material mat)
        {
            if (arrowMesh == null)
            {
                arrowMesh = new Mesh { name = "TrailArrow" };
                arrowMesh.vertices = new[] { new Vector3(0f, 0f, 0.25f), new Vector3(0.15f, 0f, -0.15f), new Vector3(-0.15f, 0f, -0.15f) };
                arrowMesh.triangles = new[] { 0, 1, 2, 0, 2, 1 };
                arrowMesh.RecalculateNormals();
            }
            var go = new GameObject("Arrow") { layer = gt.Layer };
            go.transform.SetParent(trailRoot, false);
            go.transform.SetPositionAndRotation(at + Vector3.up * 0.04f, Quaternion.LookRotation(new Vector3(dir.x, 0f, dir.z), Vector3.up));
            go.AddComponent<MeshFilter>().sharedMesh = arrowMesh;
            GroundTruthLayer.Unshadowed(go.AddComponent<MeshRenderer>(), mat);
        }
    }
}
