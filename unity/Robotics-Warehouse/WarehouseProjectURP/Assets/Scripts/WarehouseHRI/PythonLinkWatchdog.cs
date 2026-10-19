using UnityEngine;

namespace WarehouseHRI
{
    /// <summary>
    /// Unity-side watchdog: when the Python link is required and nothing has arrived for watchdog_s (0.3 s), the
    /// robot stops by itself (DiffDriveRobot checks ShouldStop every physics step). STUB: the TCP client of Step 3
    /// calls NotifyMessageReceived() for every message; until then linkRequired is false and nothing is stopped.
    /// </summary>
    public class PythonLinkWatchdog : MonoBehaviour
    {
        public bool useConfigFile = true;
        public bool linkRequired;
        public float silenceLimitS = 0.3f;

        float m_LastHeard = float.NegativeInfinity;

        public float LastHeardTime => m_LastHeard;
        public float SilenceSeconds => Time.time - m_LastHeard;
        public bool ShouldStop => linkRequired && IsSilent(SilenceSeconds, silenceLimitS);

        void Awake()
        {
            if (!useConfigFile) return;
            var l = HriConfig.Current.link;
            linkRequired = l.link_required;
            silenceLimitS = l.watchdog_s;
        }

        /// <summary>Called by the TCP client (Step 3) for every message received from Python.</summary>
        public void NotifyMessageReceived() => m_LastHeard = Time.time;

        /// <summary>Pure rule: silent when strictly more than the limit has passed since the last message.</summary>
        public static bool IsSilent(float secondsSinceLastMessage, float limitSeconds) =>
            secondsSinceLastMessage > limitSeconds;
    }
}
