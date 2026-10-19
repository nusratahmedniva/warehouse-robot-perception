using UnityEngine;

namespace WarehouseHRI
{
    public enum FollowCameraMode { Chase = 0, TopDown = 1, GestureCamera = 2 }

    /// <summary>
    /// Viewer camera for the Game view (not a robot sensor). Press C to cycle: Chase (smoothly behind and above
    /// the robot), TopDown (orthographic, north = +z up, following the robot) and GestureCamera (exactly what the
    /// pan-tilt gesture camera sees, with its field of view and culling mask, so viewer-only objects such as the
    /// goal marker disappear as they do for the robot).
    /// </summary>
    [RequireComponent(typeof(Camera))]
    public class FollowCamera : MonoBehaviour
    {
        public Transform target;
        [Tooltip("Camera mirrored in GestureCamera mode (the robot's pan-tilt camera).")]
        public Camera gestureCamera;
        public FollowCameraMode mode = FollowCameraMode.Chase;
        public KeyCode toggleKey = KeyCode.C;

        [Header("Chase")]
        public float chaseDistanceM = 3.5f;
        public float chaseHeightM = 2.2f;
        public float lookAheadM = 2f;
        public float lookHeightM = 0.6f;
        [Tooltip("Position smoothing time, s.")]
        public float positionSmoothS = 0.35f;
        [Tooltip("Rotation smoothing rate, 1/s.")]
        public float rotationSharpness = 6f;
        public float chaseFovDeg = 60f;

        [Header("Top-down")]
        public float topDownHeightM = 30f;
        public float topDownOrthoSize = 10f;
        [Tooltip("Only geometry below this height is drawn (near clip plane), so the roof does not hide the floor.")]
        public float topDownClipHeightM = 5f;

        Camera m_Camera;
        Vector3 m_Velocity;
        int m_DefaultMask;
        float m_DefaultNear, m_DefaultFar;
        bool m_Snap = true;

        public Camera ViewCamera => m_Camera != null ? m_Camera : (m_Camera = GetComponent<Camera>());

        void Awake()
        {
            m_DefaultMask = ViewCamera.cullingMask;
            m_DefaultNear = ViewCamera.nearClipPlane;
            m_DefaultFar = ViewCamera.farClipPlane;
        }

        void OnEnable() => m_Snap = true;

        void Update()
        {
            if (Input.GetKeyDown(toggleKey)) Cycle();
        }

        /// <summary>Next view: Chase -> TopDown -> GestureCamera -> Chase.</summary>
        public void Cycle() => SetMode((FollowCameraMode)(((int)mode + 1) % 3));

        public void SetMode(FollowCameraMode m)
        {
            mode = m;
            m_Snap = true;
        }

        public string ModeLabel => mode == FollowCameraMode.GestureCamera ? "gesture camera" :
            mode == FollowCameraMode.TopDown ? "top-down" : "chase";

        void LateUpdate()
        {
            if (target == null) return;
            var cam = ViewCamera;
            cam.nearClipPlane = m_DefaultNear;
            cam.farClipPlane = m_DefaultFar;
            switch (mode)
            {
                case FollowCameraMode.Chase:
                {
                    cam.orthographic = false;
                    cam.fieldOfView = chaseFovDeg;
                    cam.cullingMask = m_DefaultMask;
                    Vector3 fwd = Vector3.ProjectOnPlane(target.forward, Vector3.up).normalized;
                    if (fwd.sqrMagnitude < 1e-6f) fwd = Vector3.forward;
                    Vector3 want = target.position - fwd * chaseDistanceM + Vector3.up * chaseHeightM;
                    Vector3 look = target.position + fwd * lookAheadM + Vector3.up * lookHeightM;
                    var rot = Quaternion.LookRotation(look - want, Vector3.up);
                    if (m_Snap)
                    {
                        transform.SetPositionAndRotation(want, rot);
                        m_Velocity = Vector3.zero;
                    }
                    else
                    {
                        transform.position = Vector3.SmoothDamp(transform.position, want, ref m_Velocity, positionSmoothS);
                        transform.rotation = Quaternion.Slerp(transform.rotation, rot, 1f - Mathf.Exp(-rotationSharpness * Time.deltaTime));
                    }

                    break;
                }

                case FollowCameraMode.TopDown:
                    cam.orthographic = true;
                    cam.orthographicSize = topDownOrthoSize;
                    cam.cullingMask = m_DefaultMask;
                    cam.nearClipPlane = Mathf.Max(0.05f, topDownHeightM - topDownClipHeightM);
                    cam.farClipPlane = topDownHeightM + 2f;
                    transform.SetPositionAndRotation(new Vector3(target.position.x, target.position.y + topDownHeightM, target.position.z),
                        Quaternion.Euler(90f, 0f, 0f)); // looking down, +z at the top of the screen
                    break;

                case FollowCameraMode.GestureCamera:
                    if (gestureCamera == null)
                    {
                        SetMode(FollowCameraMode.Chase);
                        break;
                    }

                    cam.orthographic = false;
                    cam.fieldOfView = gestureCamera.fieldOfView;
                    cam.nearClipPlane = gestureCamera.nearClipPlane;
                    cam.cullingMask = gestureCamera.cullingMask;
                    transform.SetPositionAndRotation(gestureCamera.transform.position, gestureCamera.transform.rotation);
                    break;
            }

            m_Snap = false;
        }
    }
}
