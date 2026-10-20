using UnityEngine;

namespace WarehouseHRI
{
    /// <summary>
    /// Direction commands, always from the ROBOT's point of view and relative to the robot's heading when it
    /// arrived at the junction (the road frame), not to where it faces while asking. The worker faces the robot,
    /// so the worker's right arm sends the robot left.
    /// </summary>
    public enum GestureCommand
    {
        NONE = 0,          // anything else, or between two directions: ask again
        LEFT = 1,          // arm level to the robot's left
        FORWARD_LEFT = 2,  // arm about 45 deg up toward the robot's left
        FORWARD = 3,       // arm straight up
        FORWARD_RIGHT = 4, // arm about 45 deg up toward the robot's right
        RIGHT = 5,         // arm level to the robot's right
        STOP = 6,          // open palm facing the robot; overrides everything
    }

    public static class GestureCommands
    {
        /// <summary>The five direction commands (STOP and NONE are not branches).</summary>
        public static readonly GestureCommand[] Directions =
        {
            GestureCommand.LEFT, GestureCommand.FORWARD_LEFT, GestureCommand.FORWARD,
            GestureCommand.FORWARD_RIGHT, GestureCommand.RIGHT,
        };

        /// <summary>The six commands a worker can show (used by the pose test).</summary>
        public static readonly GestureCommand[] Shown =
        {
            GestureCommand.LEFT, GestureCommand.FORWARD_LEFT, GestureCommand.FORWARD,
            GestureCommand.FORWARD_RIGHT, GestureCommand.RIGHT, GestureCommand.STOP,
        };

        public static bool IsDirection(GestureCommand c) => c != GestureCommand.NONE && c != GestureCommand.STOP;

        /// <summary>
        /// Direction command for a branch leaving at signed angle <paramref name="turnDeg"/> from the arrival heading
        /// (Unity yaw: positive = to the right). Used by the scene builder to label branches from geometry.
        /// </summary>
        public static GestureCommand FromTurnAngle(float turnDeg)
        {
            float a = Mathf.DeltaAngle(0f, turnDeg);
            if (a < -67.5f) return GestureCommand.LEFT;
            if (a < -22.5f) return GestureCommand.FORWARD_LEFT;
            if (a <= 22.5f) return GestureCommand.FORWARD;
            if (a <= 67.5f) return GestureCommand.FORWARD_RIGHT;
            return GestureCommand.RIGHT;
        }
    }
}
