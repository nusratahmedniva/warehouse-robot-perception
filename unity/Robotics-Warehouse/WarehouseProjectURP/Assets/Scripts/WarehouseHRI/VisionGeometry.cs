using UnityEngine;

namespace WarehouseHRI
{
    /// <summary>
    /// Geometry shared by the vision sources (pure, unit-tested): a bearing (deg, + = right of the robot heading)
    /// and a distance, measured from the robot pose of the observation, to a world floor point.
    /// </summary>
    public static class VisionGeometry
    {
        public static Vector3 WorldPoint(float robotX, float robotZ, float headingDeg, float bearingDeg, float distanceM, float y = 0f)
        {
            float yaw = (headingDeg + bearingDeg) * Mathf.Deg2Rad; // Unity yaw: 0 = +z, 90 = +x
            return new Vector3(robotX + Mathf.Sin(yaw) * distanceM, y, robotZ + Mathf.Cos(yaw) * distanceM);
        }

        /// <summary>A reply is usable when it arrived within staleAfter seconds.</summary>
        public static bool Fresh(float now, float replyTime, float staleAfter) => now - replyTime <= staleAfter;
    }
}
