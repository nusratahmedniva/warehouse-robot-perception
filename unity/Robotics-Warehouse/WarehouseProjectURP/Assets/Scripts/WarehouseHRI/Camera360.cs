using UnityEngine;
using UnityEngine.Rendering;

namespace WarehouseHRI
{
    /// <summary>
    /// 360 deg camera on top of the mast. Every captureIntervalS it renders a cubemap and converts it to an
    /// equirectangular RenderTexture (width = 2 x height). The cubemap faces are world-aligned (Unity renders
    /// RenderToCubemap along the world axes, not the camera's rotation), so the panorama is world-aligned and the
    /// robot heading must be applied by whoever reads it (Step 3 sends the heading with every frame). The exact
    /// column of world +z in the panorama is not verified yet; check it in the Editor before Step 4 relies on it.
    /// The camera component itself stays disabled; it only renders on capture.
    /// </summary>
    [RequireComponent(typeof(Camera))]
    public class Camera360 : MonoBehaviour
    {
        public bool useConfigFile = true;
        public float captureIntervalS = 0.1f;
        public int cubeFaceSize = 512;
        public int equirectWidth = 2048;

        Camera m_Camera;
        RenderTexture m_Cube;
        float m_NextCapture;
        bool m_Warned;

        /// <summary>Latest panorama (null before the first capture or when rendering is unavailable).</summary>
        public RenderTexture Equirect { get; private set; }
        public int FrameCount { get; private set; }
        public float LastCaptureTime { get; private set; } = float.NegativeInfinity;
        public bool RenderingAvailable => SystemInfo.graphicsDeviceType != GraphicsDeviceType.Null;

        void Awake()
        {
            m_Camera = GetComponent<Camera>();
            m_Camera.enabled = false;
            if (useConfigFile)
            {
                var c = HriConfig.Current.cameras;
                captureIntervalS = c.cam360_interval_s;
                cubeFaceSize = c.cam360_face_px;
                equirectWidth = c.cam360_equirect_width_px;
            }
        }

        void OnEnable()
        {
            if (!RenderingAvailable) return;
            m_Cube = new RenderTexture(cubeFaceSize, cubeFaceSize, 24, RenderTextureFormat.ARGB32)
            {
                dimension = TextureDimension.Cube, name = "Cam360_Cube",
            };
            m_Cube.Create();
            Equirect = new RenderTexture(equirectWidth, equirectWidth / 2, 0, RenderTextureFormat.ARGB32)
            {
                name = "Cam360_Equirect",
            };
            Equirect.Create();
        }

        void OnDisable()
        {
            if (m_Cube != null) m_Cube.Release();
            if (Equirect != null) Equirect.Release();
            m_Cube = null;
            Equirect = null;
        }

        void LateUpdate()
        {
            if (Time.time < m_NextCapture) return;
            m_NextCapture = Time.time + captureIntervalS;
            Capture();
        }

        /// <summary>Render the cubemap now and update the panorama. Returns false when rendering failed.</summary>
        public bool Capture()
        {
            if (m_Cube == null || Equirect == null) return false;
            if (!m_Camera.RenderToCubemap(m_Cube, 63))
            {
                if (!m_Warned) Debug.LogWarning("[WarehouseHRI] Camera360: RenderToCubemap failed on this platform/pipeline.");
                m_Warned = true;
                return false;
            }

            m_Cube.ConvertToEquirect(Equirect, Camera.MonoOrStereoscopicEye.Mono);
            FrameCount++;
            LastCaptureTime = Time.time;
            return true;
        }
    }
}
