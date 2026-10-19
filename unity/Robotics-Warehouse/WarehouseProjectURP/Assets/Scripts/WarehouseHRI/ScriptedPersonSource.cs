using System.Collections.Generic;
using UnityEngine;

namespace WarehouseHRI
{
    /// <summary>
    /// SCRIPTED-PERCEPTION BASELINE: reports the true positions of the GestureWorkers in the scene within a range.
    /// Not vision. Step 3/4 replace it with people found by YOLO on the 360 deg camera (another IPersonSource).
    /// </summary>
    public class ScriptedPersonSource : MonoBehaviour, IPersonSource
    {
        public const string BaselineLabel = "scripted-perception baseline (true positions)";

        public float detectionRangeM = 12f;

        readonly List<GestureWorker> m_Workers = new List<GestureWorker>();
        float m_NextRefresh;

        public bool useConfigFile = true;

        public string Label => BaselineLabel;

        void Awake()
        {
            if (useConfigFile) detectionRangeM = HriConfig.Current.brain.person_detection_range_m;
        }

        public void Detect(Vector3 robotPosition, List<PersonObservation> into)
        {
            into.Clear();
            if (Time.time >= m_NextRefresh || m_Workers.Count == 0)
            {
                m_Workers.Clear();
                m_Workers.AddRange(FindObjectsOfType<GestureWorker>());
                m_NextRefresh = Time.time + 1f;
            }

            foreach (var w in m_Workers)
            {
                if (w == null || !w.isActiveAndEnabled) continue;
                Vector3 d = w.transform.position - robotPosition;
                d.y = 0f;
                float dist = d.magnitude;
                if (dist > detectionRangeM) continue;
                into.Add(new PersonObservation
                {
                    Position = w.transform.position, Chest = w.ChestPosition, Distance = dist, Worker = w,
                });
            }
        }
    }
}
