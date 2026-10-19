using UnityEngine;

namespace WarehouseHRI
{
    /// <summary>
    /// VISION people source: the people in the latest Python reply (YOLO11s-pose + ByteTrack on the 360 deg panorama).
    /// Positions are rebuilt from bearing and distance with the robot pose the observation was sent with; an
    /// unknown distance is replaced by the conservative unknown_person_distance_m. Never reads true positions.
    /// </summary>
    public class VisionPersonSource : MonoBehaviour, IPersonSource
    {
        public HriBridgeClient bridge;
        public bool useConfigFile = true;
        public float staleAfterS = 0.5f;
        public float unknownDistanceM = 1.0f;
        public float chestHeightM = 1.3f;

        public string Label => "vision (YOLO11s-pose people on the 360 deg camera)";

        void Awake()
        {
            if (bridge == null) bridge = GetComponent<HriBridgeClient>();
            if (!useConfigFile) return;
            var p = HriConfig.Current.perception;
            staleAfterS = p.stale_after_s;
            unknownDistanceM = p.unknown_person_distance_m;
            chestHeightM = p.chest_height_m;
        }

        public void Detect(Vector3 robotPosition, System.Collections.Generic.List<PersonObservation> into)
        {
            into.Clear();
            var r = bridge != null ? bridge.LatestPerception : null;
            var pose = bridge != null ? bridge.LatestPerceptionPose : null;
            if (r?.people == null || pose == null || !VisionGeometry.Fresh(Time.time, bridge.LastReplyTime, staleAfterS)) return;
            foreach (var q in r.people)
            {
                float d = q.distance_m >= 0f ? q.distance_m : unknownDistanceM;
                var feet = VisionGeometry.WorldPoint(pose.x, pose.z, pose.heading_deg, q.bearing_deg, d, robotPosition.y);
                Vector3 flat = feet - robotPosition;
                flat.y = 0f;
                into.Add(new PersonObservation { Position = feet, Chest = feet + Vector3.up * chestHeightM, Distance = flat.magnitude, Worker = null });
            }
        }
    }
}
