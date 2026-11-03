using System.IO;
using System.Text;
using UnityEngine;
using WarehouseHRI.V4;

namespace WarehouseRobot.GroundTruth
{
    /// <summary>
    /// v4 trail (docs/protocol_v3.md, run_###/trail.csv): the robot root's position and yaw every trail_interval_s (0.1 s)
    /// of simulation time from the start of a run to its end, header "time_s,x,z,yaw_deg", time_s = Unity Time.time
    /// (absolute, the clock of telemetry and frame headers), 3 decimals. The first row is written at Begin (run start),
    /// the last at End (final position). Sampled in FixedUpdate on the grid t0 + k * interval, so the interval does not
    /// drift. A line is drawn behind the robot on the ground-truth layer (never seen by the robot cameras).
    /// </summary>
    [DisallowMultipleComponent]
    public class TrailRecorder : MonoBehaviour
    {
        Transform robot;
        StreamWriter writer;
        LineRenderer line;
        float t0, interval, lastRowTime, y;
        int k;

        public bool Recording => writer != null;
        public int Rows { get; private set; }

        /// <summary>Start a run: create runDir/trail.csv (never overwritten) and write the first row now.</summary>
        public void Begin(Transform robotRoot, string runDir, float intervalS, int layer, Material material, float widthM, float lineY)
        {
            if (Recording) End();
            robot = robotRoot;
            interval = intervalS;
            y = lineY;
            writer = new StreamWriter(new FileStream(Path.Combine(runDir, "trail.csv"), FileMode.CreateNew, FileAccess.Write),
                new UTF8Encoding(false)) { NewLine = "\n", AutoFlush = true };
            writer.WriteLine(GroundTruthFiles.TrailHeader);
            Rows = 0;
            k = 0;
            t0 = Time.time;

            if (line == null)
            {
                var go = new GameObject("Trail") { layer = layer };
                go.transform.SetParent(transform, false);
                line = go.AddComponent<LineRenderer>();
                GroundTruthLayer.Unshadowed(line, material);
                line.useWorldSpace = true;
            }
            line.widthMultiplier = widthM;
            line.positionCount = 0;
            Row(t0);
        }

        void FixedUpdate()
        {
            if (!Recording || robot == null) return;
            float now = Time.time;
            const float eps = 1e-4f;                       // float time: 0.1 s steps land within this of the grid
            if (now < t0 + (k + 1) * interval - eps) return;
            while (now >= t0 + (k + 1) * interval - eps) k++;   // a long step skips slots instead of writing them late
            Row(now);
        }

        /// <summary>End the run: write the final position (unless a row was just written this step) and close the file.</summary>
        public void End()
        {
            if (!Recording) return;
            if (robot != null && Time.time > lastRowTime) Row(Time.time);
            writer.Dispose();
            writer = null;
        }

        void Row(float t)
        {
            var p = robot.position;
            writer.WriteLine(GroundTruthFiles.TrailRow(t, p.x, p.z, robot.eulerAngles.y));
            lastRowTime = t;
            Rows++;
            line.positionCount++;
            line.SetPosition(line.positionCount - 1, new Vector3(p.x, y, p.z));
        }

        void OnDestroy()
        {
            if (writer != null) writer.Dispose();
            writer = null;
        }
    }
}
