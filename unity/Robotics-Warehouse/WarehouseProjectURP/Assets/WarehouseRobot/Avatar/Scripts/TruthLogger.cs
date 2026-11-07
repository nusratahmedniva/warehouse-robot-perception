using System.Collections.Generic;
using UnityEngine;

namespace WarehouseAvatar
{
    /// <summary>
    /// Writes run_###/truth.jsonl for every worker in the scene (bystanders included), after the workers' Update
    /// (LateUpdate, late execution order): a frame (one line per worker, same Unity Time.time) whenever intervalS has
    /// passed since the last frame and on every frame in which any worker changed phase. Begin() creates the file
    /// (CreateNew: never overwritten); End() closes it. A row or frame that breaks a truth.jsonl rule throws, is logged
    /// and stops the logger (Failed), so a bad file is never completed silently. The file never goes over the bridge.
    /// </summary>
    [DefaultExecutionOrder(1000)]
    public class TruthLogger : MonoBehaviour
    {
        public float intervalS = 0.05f;

        public bool Running => m_Writer != null;
        public string Failed { get; private set; } = "";
        public int Lines => m_Writer != null ? m_Writer.Lines : m_LastLines;
        public string Path { get; private set; } = "";

        readonly List<WorkerV4> m_Workers = new List<WorkerV4>();
        readonly Dictionary<WorkerV4, int> m_Serial = new Dictionary<WorkerV4, int>();
        readonly List<TruthRow> m_Frame = new List<TruthRow>();
        TruthFileWriter m_Writer;
        float m_Last = float.NegativeInfinity;
        int m_LastLines;

        /// <summary>Start a truth.jsonl at path for these workers; writes the first frame now.</summary>
        public void Begin(string path, IEnumerable<WorkerV4> workers, float interval)
        {
            End();
            intervalS = interval;
            m_Workers.Clear();
            m_Serial.Clear();
            m_Workers.AddRange(workers);
            Failed = "";
            Path = path;
            m_Writer = new TruthFileWriter(path);
            m_Last = float.NegativeInfinity;
            Sample(true);
        }

        /// <summary>Write a last frame (the final state) and close the file.</summary>
        public void End() => Close(true);

        void Close(bool lastFrame)
        {
            if (m_Writer == null) return;
            if (lastFrame && Time.time >= m_Last) Sample(true);
            if (m_Writer == null) return; // the last frame failed and closed the file
            m_LastLines = m_Writer.Lines;
            m_Writer.Dispose();
            m_Writer = null;
        }

        void LateUpdate() => Sample(false);

        // On teardown (leaving Play) the workers may already be gone and Time.time reset: close without a frame.
        void OnDestroy() => Close(false);

        void Sample(bool force)
        {
            if (m_Writer == null) return;
            float t = Time.time;
            bool changed = false;
            foreach (var w in m_Workers)
            {
                if (!m_Serial.TryGetValue(w, out int s) || s != w.PhaseSerial) changed = true;
                m_Serial[w] = w.PhaseSerial;
            }
            if (!force && !changed && t - m_Last < intervalS - 1e-4f) return;
            m_Frame.Clear();
            foreach (var w in m_Workers) m_Frame.Add(w.Truth(t));
            try
            {
                m_Writer.WriteFrame(m_Frame);
                m_Last = t;
            }
            catch (System.Exception e)
            {
                Failed = e.Message;
                Debug.LogError("[TruthLogger] " + e.Message + " (logging stopped)");
                m_LastLines = m_Writer.Lines;
                m_Writer.Dispose();
                m_Writer = null;
            }
        }
    }
}
