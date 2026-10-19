using System.Collections.Generic;
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

    /// <summary>Reads the command a worker shows. Step 4 replaces the scripted source with Python vision.</summary>
    public interface IGestureSource
    {
        /// <summary>Short label written to every run log, e.g. "scripted-gesture baseline" or "vision".</summary>
        string Label { get; }

        /// <summary>The command read right now. <paramref name="worker"/> may be null for a vision source.</summary>
        GestureCommand Read(GestureWorker worker);
    }

    /// <summary>One person as seen by the robot's perception (world coordinates, y up).</summary>
    public struct PersonObservation
    {
        public Vector3 Position;      // feet position on the floor (estimated by vision in Step 4)
        public Vector3 Chest;         // aim point for the pan-tilt camera
        public float Distance;        // horizontal distance from the robot centre, m
        public GestureWorker Worker;  // scripted source only; null for vision
    }

    /// <summary>Finds people around the robot. Step 3/4 replace the scripted source with the 360 deg camera + YOLO.</summary>
    public interface IPersonSource
    {
        string Label { get; }

        /// <summary>Clears <paramref name="into"/> and fills it with the people currently detected.</summary>
        void Detect(Vector3 robotPosition, List<PersonObservation> into);
    }
}
