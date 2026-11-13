using UnityEngine;
using WarehouseHRI.V4;
using WarehouseRobot.Bridge;

namespace WarehouseRobot
{
    /// <summary>
    /// v4 robot body (2026-11-12, U1; Avatar/Config/upgrade_design.md section 7): the status light ring and the front
    /// display. Colours and messages from WarehouseHRI.V4.RobotStatus for Python's state, screen text and accepted branch,
    /// as they arrive in each command. Display only: it never changes what the robot does, and it lies outside every view
    /// of the pan-tilt camera (self-visibility check); the 360 camera sees it in the bottom rows of its image, as it sees
    /// the whole body. Emissive materials light nothing in the scene.
    /// </summary>
    [DisallowMultipleComponent]
    public class RobotStatusDisplay : MonoBehaviour
    {
        public RobotBridgeClient bridge;
        public Renderer[] lights = new Renderer[0];
        public TextMesh display;

        static readonly int BaseColor = Shader.PropertyToID("_BaseColor"), EmissionColor = Shader.PropertyToID("_EmissionColor");
        MaterialPropertyBlock block;
        RobotStatus.Light shown = (RobotStatus.Light)(-1);
        string shownText;

        void Awake()
        {
            if (bridge == null) bridge = FindFirstObjectByType<RobotBridgeClient>();
            block = new MaterialPropertyBlock();
            Apply(RobotStatus.Light.Idle, "");
        }

        void Update()
        {
            if (bridge == null) return;
            var light = RobotStatus.LightFor(bridge.State);
            string text = RobotStatus.MessageFor(bridge.State, bridge.ScreenText, bridge.Hud != null ? bridge.Hud.gesture_accepted : "");
            if (light != shown || text != shownText) Apply(light, text);
        }

        void Apply(RobotStatus.Light light, string text)
        {
            shown = light;
            shownText = text;
            var c = RobotStatus.ColorFor(light);
            foreach (var r in lights)
            {
                if (r == null) continue;
                r.GetPropertyBlock(block);
                block.SetColor(BaseColor, c);
                block.SetColor(EmissionColor, c * 2.5f);
                r.SetPropertyBlock(block);
            }
            if (display != null)
            {
                display.text = text;
                display.color = light == RobotStatus.Light.Stopped ? RobotStatus.Red : new Color(0.75f, 0.95f, 1f);
            }
        }
    }
}
