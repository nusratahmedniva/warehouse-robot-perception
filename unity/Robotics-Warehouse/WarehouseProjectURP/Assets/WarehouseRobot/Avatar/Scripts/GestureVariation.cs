using System;
using System.Collections.Generic;
using UnityEngine;

namespace WarehouseAvatar
{
    /// <summary>The worker's own state, as written in truth.jsonl (docs/protocol_v3.md phase list).</summary>
    public enum WorkerPhase { Idle, StartDelay, Gesturing, Holding, Returning }

    public static class WorkerPhases
    {
        public static string Name(WorkerPhase p)
        {
            switch (p)
            {
                case WorkerPhase.StartDelay: return "start_delay";
                case WorkerPhase.Gesturing: return "gesturing";
                case WorkerPhase.Holding: return "holding";
                case WorkerPhase.Returning: return "returning";
                default: return "idle";
            }
        }

        /// <summary>The worker performs its command (truth true_command is not NONE) in these phases only.</summary>
        public static bool Performing(WorkerPhase p) => p == WorkerPhase.Gesturing || p == WorkerPhase.Holding || p == WorkerPhase.Returning;
    }

    /// <summary>
    /// SplitMix64: a small deterministic generator, the same on every platform and runtime (System.Random and
    /// UnityEngine.Random are not guaranteed to be), so a run's gestures repeat exactly from its seed.
    /// </summary>
    public sealed class SeededRandom
    {
        ulong m_State;

        public SeededRandom(ulong seed) { m_State = seed; }

        /// <summary>One stream per (session seed, run, worker): the "seeded per run and worker" rule of the variation.</summary>
        public static SeededRandom For(int sessionSeed, int run, int workerId) =>
            new SeededRandom(Mix(Mix(Mix(0x5741524548534531UL ^ (ulong)(uint)sessionSeed) ^ (ulong)(uint)run) ^ (ulong)(uint)workerId));

        public static ulong Mix(ulong z)
        {
            z += 0x9E3779B97F4A7C15UL;
            z = (z ^ (z >> 30)) * 0xBF58476D1CE4E5B9UL;
            z = (z ^ (z >> 27)) * 0x94D049BB133111EBUL;
            return z ^ (z >> 31);
        }

        public ulong NextULong()
        {
            m_State += 0x9E3779B97F4A7C15UL;
            ulong z = m_State;
            z = (z ^ (z >> 30)) * 0xBF58476D1CE4E5B9UL;
            z = (z ^ (z >> 27)) * 0x94D049BB133111EBUL;
            return z ^ (z >> 31);
        }

        /// <summary>Uniform in [0, 1).</summary>
        public double NextDouble() => (NextULong() >> 11) * (1.0 / 9007199254740992.0);

        public float Range(float[] r) => r[0] + (float)NextDouble() * (r[1] - r[0]);

        public int Index(int count) => Math.Min(count - 1, (int)(NextDouble() * count));
    }

    /// <summary>The random parameters of one gesture (written to truth.jsonl as extra fields).</summary>
    [Serializable]
    public struct GestureParams
    {
        public string command, clip, arm;
        public float speed, size, start_delay_s, hold_s, point_elevation_deg;
        public Vector3 sway_amplitude_m, sway_frequency_hz, sway_phase_rad;
    }

    public static class GestureVariation
    {
        /// <summary>
        /// Draw a gesture. clip "" = one of allowedClips (or of every clip of the command when allowedClips is empty);
        /// arm "" = the variation rule: POINT uses the arm on the side of the pointed direction (bodyAzimuthDeg, + = the
        /// person's right) unless it is within point_either_arm_within_deg of straight ahead; otherwise left with
        /// left_arm_probability. The draws happen in a fixed order, so a given stream gives the same gesture whatever
        /// was forced.
        /// </summary>
        public static GestureParams Draw(SeededRandom rng, WorkerV4Config cfg, string command, string clip, IList<string> allowedClips,
                                         string arm, float bodyAzimuthDeg)
        {
            var v = cfg.variation;
            var p = new GestureParams { command = command };
            var pool = allowedClips != null && allowedClips.Count > 0 ? new List<string>(allowedClips) : cfg.ClipNames(command);
            if (pool.Count == 0) throw new ArgumentException($"no clip for {command}");
            int pick = rng.Index(pool.Count);
            p.clip = string.IsNullOrEmpty(clip) ? pool[pick] : clip;
            var spec = cfg.Clip(p.clip) ?? throw new ArgumentException($"clip '{p.clip}' is not in worker_v4.json");
            if (spec.command != command) throw new ArgumentException($"clip '{p.clip}' is a {spec.command} clip, not {command}");
            p.speed = rng.Range(v.speed);
            p.size = rng.Range(v.size);
            p.start_delay_s = rng.Range(v.start_delay_s);
            p.hold_s = rng.Range(v.hold_s);
            p.point_elevation_deg = rng.Range(v.point_elevation_deg);
            bool left = rng.NextDouble() < v.left_arm_probability;
            if (command == WorkerV4Config.Point && Mathf.Abs(bodyAzimuthDeg) > v.point_either_arm_within_deg) left = bodyAzimuthDeg < 0f;
            p.arm = string.IsNullOrEmpty(arm) ? (left ? "left" : "right") : arm;
            if (p.arm != "left" && p.arm != "right") throw new ArgumentException($"arm '{arm}' must be left or right");
            p.sway_amplitude_m = new Vector3(rng.Range(v.sway_amplitude_m), rng.Range(v.sway_amplitude_m), rng.Range(v.sway_amplitude_m));
            p.sway_frequency_hz = new Vector3(rng.Range(v.sway_frequency_hz), rng.Range(v.sway_frequency_hz), rng.Range(v.sway_frequency_hz));
            p.sway_phase_rad = new Vector3((float)(rng.NextDouble() * 2 * Math.PI), (float)(rng.NextDouble() * 2 * Math.PI), (float)(rng.NextDouble() * 2 * Math.PI));
            return p;
        }

        public static float Ease(string ease, float u)
        {
            u = Mathf.Clamp01(u);
            if (ease == WorkerV4Config.EaseQuick) { float r = 1f - u; return 1f - r * r * r; }
            return u * u * (3f - 2f * u);
        }

        /// <summary>Small hand sway around the target (side, up, forward in metres), scaled by the gesture's size.</summary>
        public static Vector3 Sway(GestureParams p, float t)
        {
            float S(int i) => p.sway_amplitude_m[i] * p.size * Mathf.Sin(2f * Mathf.PI * p.sway_frequency_hz[i] * t + p.sway_phase_rad[i]);
            return new Vector3(S(0), S(1), S(2));
        }
    }

    /// <summary>Durations of one gesture's phases in seconds (speed already applied).</summary>
    public struct GestureTiming
    {
        public float StartDelay, Raise, Hold, Return;

        /// <summary>procedural: raise_s / return_s of the variant; mixamo: from the clip (start to peak, release to end).</summary>
        public static GestureTiming For(GestureClipSpec spec, ClipIndexEntry clip, GestureParams p)
        {
            float raise = spec.IsMixamo ? clip.peak_s : spec.raise_s;
            float ret = spec.IsMixamo ? clip.length_s - clip.release_s : spec.return_s;
            return new GestureTiming { StartDelay = p.start_delay_s, Raise = raise / p.speed, Hold = p.hold_s, Return = ret / p.speed };
        }
    }

    /// <summary>
    /// When a requested gesture runs: never before the question ("Which direction?") is visible, unless the request
    /// says so (a STOP demonstration). Then start_delay -> gesturing -> holding -> returning -> idle. Pure (time is passed
    /// in), so it is tested in Edit Mode; WorkerV4 drives it with Time.time.
    /// </summary>
    public sealed class GestureScheduler
    {
        public WorkerPhase Phase { get; private set; } = WorkerPhase.Idle;
        public float PhaseStart { get; private set; }
        public bool Pending { get; private set; }
        public bool IgnoreQuestion { get; private set; }
        public GestureTiming Timing { get; private set; }
        /// <summary>Incremented on every phase change (the truth logger writes a line on each).</summary>
        public int Serial { get; private set; }
        public float QuestionSince { get; private set; } = -1f;

        public bool QuestionVisible => QuestionSince >= 0f;

        /// <summary>Queue a gesture; it starts at the first Tick at which the question is visible (or at once if ignoreQuestion).</summary>
        public bool Request(GestureTiming timing, bool ignoreQuestion)
        {
            if (Phase != WorkerPhase.Idle || Pending) return false;
            Timing = timing;
            Pending = true;
            IgnoreQuestion = ignoreQuestion;
            return true;
        }

        public void SetQuestionVisible(bool visible, float t)
        {
            if (visible && QuestionSince < 0f) QuestionSince = t;
            else if (!visible) QuestionSince = -1f;
        }

        /// <summary>Drop a pending request that has not started (a gesture already started runs to its end).</summary>
        public void Cancel() => Pending = false;

        /// <summary>Advance to time t; returns true if the phase changed.</summary>
        public bool Tick(float t)
        {
            int before = Serial;
            if (Pending && Phase == WorkerPhase.Idle && (IgnoreQuestion || QuestionVisible))
            {
                Pending = false;
                Enter(WorkerPhase.StartDelay, t);
            }
            for (int guard = 0; guard < 5; guard++)
            {
                float end = PhaseStart + Duration(Phase);
                if (Phase == WorkerPhase.Idle || t < end) break;
                Enter(Next(Phase), end);
            }
            return Serial != before;
        }

        float Duration(WorkerPhase p)
        {
            switch (p)
            {
                case WorkerPhase.StartDelay: return Timing.StartDelay;
                case WorkerPhase.Gesturing: return Timing.Raise;
                case WorkerPhase.Holding: return Timing.Hold;
                case WorkerPhase.Returning: return Timing.Return;
                default: return float.PositiveInfinity;
            }
        }

        static WorkerPhase Next(WorkerPhase p)
        {
            switch (p)
            {
                case WorkerPhase.StartDelay: return WorkerPhase.Gesturing;
                case WorkerPhase.Gesturing: return WorkerPhase.Holding;
                case WorkerPhase.Holding: return WorkerPhase.Returning;
                default: return WorkerPhase.Idle;
            }
        }

        void Enter(WorkerPhase p, float t)
        {
            Phase = p;
            PhaseStart = t;
            Serial++;
        }

        /// <summary>Seconds into the current phase and its 0..1 progress.</summary>
        public float Elapsed(float t) => Mathf.Max(0f, t - PhaseStart);

        public float Progress(float t)
        {
            float d = Duration(Phase);
            return float.IsInfinity(d) || d <= 0f ? 1f : Mathf.Clamp01(Elapsed(t) / d);
        }

        /// <summary>IK and hand-shape weight: eased up while gesturing, 1 while holding, eased down while returning.</summary>
        public float Weight(float t, string ease)
        {
            switch (Phase)
            {
                case WorkerPhase.Gesturing: return GestureVariation.Ease(ease, Progress(t));
                case WorkerPhase.Holding: return 1f;
                case WorkerPhase.Returning: return 1f - GestureVariation.Ease(ease, Progress(t));
                default: return 0f;
            }
        }
    }
}
