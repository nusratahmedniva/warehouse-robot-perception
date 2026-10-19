using UnityEngine;
using UnityEngine.Rendering;

namespace WarehouseHRI
{
    /// <summary>
    /// Gesture camera: 730 x 530 px, 60 deg vertical field of view, on a yaw pivot. AimAt() turns the pivot
    /// (yaw only) at a limited speed. Pitch stays 0 and the robot's roll and pitch are frozen, so the camera is
    /// level, as the lower-bound person-distance estimate assumes. ("Pan-tilt" names the mount; tilt is held at 0.)
    /// </summary>
    public class PanTiltCamera : MonoBehaviour
    {
        public bool useConfigFile = true;
        [Tooltip("Yaw pivot; defaults to this transform.")]
        public Transform yawPivot;
        public Camera gestureCamera;
        public int width = 730;
        public int height = 530;
        public float verticalFovDeg = 60f;
        public float panSpeedDps = 120f;
        public float aimToleranceDeg = 2f;

        float m_TargetYaw;

        public RenderTexture Image { get; private set; }
        /// <summary>Pivot yaw relative to the robot body, deg (+ = right).</summary>
        public float CurrentYawDeg => Mathf.DeltaAngle(0f, Pivot.localEulerAngles.y);
        public float TargetYawDeg => m_TargetYaw;
        public bool IsAimed => Mathf.Abs(Mathf.DeltaAngle(CurrentYawDeg, m_TargetYaw)) <= aimToleranceDeg;
        Transform Pivot => yawPivot != null ? yawPivot : transform;

        void Awake()
        {
            if (useConfigFile)
            {
                var c = HriConfig.Current.cameras;
                width = c.gesture_width_px;
                height = c.gesture_height_px;
                verticalFovDeg = c.gesture_vfov_deg;
                panSpeedDps = c.pan_speed_dps;
            }

            if (gestureCamera == null) gestureCamera = GetComponentInChildren<Camera>();
            if (gestureCamera != null)
            {
                gestureCamera.fieldOfView = verticalFovDeg;
                if (SystemInfo.graphicsDeviceType != GraphicsDeviceType.Null)
                {
                    Image = new RenderTexture(width, height, 24, RenderTextureFormat.ARGB32) { name = "GestureCamera" };
                    Image.Create();
                    gestureCamera.targetTexture = Image;
                }
            }
        }

        void OnDestroy()
        {
            if (gestureCamera != null) gestureCamera.targetTexture = null;
            if (Image != null) Image.Release();
        }

        /// <summary>Turn the camera (yaw only) toward a world point.</summary>
        public void AimAt(Vector3 worldPoint)
        {
            var parent = Pivot.parent;
            Vector3 local = parent != null ? parent.InverseTransformPoint(worldPoint) - Pivot.localPosition
                : worldPoint - Pivot.position;
            local.y = 0f;
            if (local.sqrMagnitude < 1e-6f) return;
            m_TargetYaw = Mathf.Atan2(local.x, local.z) * Mathf.Rad2Deg;
        }

        /// <summary>Look straight ahead along the robot's heading.</summary>
        public void ResetForward() => m_TargetYaw = 0f;

        void LateUpdate()
        {
            float yaw = Mathf.MoveTowardsAngle(CurrentYawDeg, m_TargetYaw, panSpeedDps * Time.deltaTime);
            Pivot.localRotation = Quaternion.Euler(0f, yaw, 0f);
            if (gestureCamera != null && gestureCamera.transform != Pivot)
                gestureCamera.transform.localRotation = Quaternion.identity; // pitch and roll held at 0
        }
    }
}
