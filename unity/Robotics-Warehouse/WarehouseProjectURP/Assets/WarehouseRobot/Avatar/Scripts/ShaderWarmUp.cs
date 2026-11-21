using System;
using System.Collections.Generic;
using UnityEngine;

namespace WarehouseAvatar
{
    /// <summary>
    /// experiments_ab.md section 15 addendum 11: the Play look check's shader warm-up and its error-shader pixel count. The Editor draws a
    /// shader variant that is still compiling as flat cyan (0, 255, 255) and a missing shader as magenta (255, 0, 255); the avatar rehearsal of
    /// 2026-11-21 recorded 38 cyan frames at the first render of the anime materials although asynchronous compilation was switched off for the
    /// session. LookCheckPlayDriver renders every camera before a round's first take until <see cref="Next"/> says done. The limits are operating
    /// limits of the capture, not evaluation thresholds. Addendum 12: the same rule warms up the Edit look check and every trial session, and
    /// every warm-up keeps its record (<see cref="ShaderWarmUpRecord"/>, <see cref="ShaderWarmUpTracker"/>).
    /// </summary>
    public static class ShaderWarmUp
    {
        /// <summary>At least this many renders of every camera.</summary>
        public const int MinRenders = 3;
        /// <summary>The last this many renders of every camera without an error-shader pixel.</summary>
        public const int CleanRenders = 2;
        /// <summary>A warm-up that is not done after this many seconds of real time fails the run.</summary>
        public const float MaxSeconds = 120f;
        /// <summary>Addendum 12: the file of the warm-up records in a look check's run folder (next to recordings.jsonl).</summary>
        public const string RecordFile = "shader_warm_up.jsonl";

        public enum State { Continue, Done, TimedOut }

        /// <summary>Exact magenta and cyan pixels of an RGBA32 buffer (4 bytes per pixel, as Texture2D.GetRawTextureData of TextureFormat.RGBA32),
        /// counted as finals_v4/avatar_rehearsal_check.py counts them in the PNG (alpha ignored).</summary>
        public static void ErrorShaderPixels(byte[] rgba, out int magenta, out int cyan)
        {
            if (rgba == null || rgba.Length % 4 != 0) throw new ArgumentException("an RGBA32 buffer has 4 bytes per pixel");
            magenta = cyan = 0;
            for (int i = 0; i < rgba.Length; i += 4)
            {
                if (rgba[i + 2] != 255) continue;
                byte r = rgba[i], g = rgba[i + 1];
                if (r == 255 && g == 0) magenta++;
                else if (r == 0 && g == 255) cyan++;
            }
        }

        /// <summary>The same count on Color32 pixels (the Edit look check's render).</summary>
        public static void ErrorShaderPixels(Color32[] px, out int magenta, out int cyan)
        {
            if (px == null) throw new ArgumentException("no pixels");
            magenta = cyan = 0;
            foreach (var p in px)
            {
                if (p.b != 255) continue;
                if (p.r == 255 && p.g == 0) magenta++;
                else if (p.r == 0 && p.g == 255) cyan++;
            }
        }

        /// <summary>The stop rule after a render of every camera: done when at least <see cref="MinRenders"/> renders were made, the last
        /// <paramref name="cleanStreak"/> renders had no error-shader pixel on any camera (at least <see cref="CleanRenders"/>) and nothing is
        /// compiling; timed out after <see cref="MaxSeconds"/>; otherwise render again.</summary>
        public static State Next(int renders, int cleanStreak, bool compiling, float seconds)
        {
            if (renders >= MinRenders && cleanStreak >= CleanRenders && !compiling) return State.Done;
            return seconds >= MaxSeconds ? State.TimedOut : State.Continue;
        }

        /// <summary>Addendum 12: pixels whose colour (RGB) differs between two RGBA32 buffers of the same size (the session warm-up's
        /// "the look was drawn" check: the render with the look against the empty render).</summary>
        public static int DifferingPixels(byte[] a, byte[] b)
        {
            if (a == null || b == null || a.Length != b.Length || a.Length % 4 != 0) throw new ArgumentException("two RGBA32 buffers of the same size");
            int n = 0;
            for (int i = 0; i < a.Length; i += 4)
                if (a[i] != b[i] || a[i + 1] != b[i + 1] || a[i + 2] != b[i + 2]) n++;
            return n;
        }

        /// <summary>Addendum 12: the highest user layer (8 to 31) without a name, the session warm-up's private layer; -1 if every one is named.</summary>
        public static int FreeLayer(Func<int, string> layerName)
        {
            for (int i = 31; i >= 8; i--)
                if (string.IsNullOrEmpty(layerName(i))) return i;
            return -1;
        }

        /// <summary>Addendum 12: the looks a session warms up: every planned look once, no empty name, ordinal order.</summary>
        public static List<string> SessionLooks(IEnumerable<string> looks)
        {
            var set = new SortedSet<string>(StringComparer.Ordinal);
            if (looks != null) foreach (var l in looks) if (!string.IsNullOrEmpty(l)) set.Add(l);
            return new List<string>(set);
        }
    }

    /// <summary>
    /// Addendum 12: one warm-up, as written to shader_warm_up.jsonl (the look checks' run folders) and to session.json shader_warm_up (a trial
    /// session). The times are on <see cref="clock"/>: Time.time in Play and in a session (the clock of the frames' time_s), the Editor's
    /// timeSinceStartup in the Edit look check (its headers carry no time_s). compile_seen_first_s / compile_seen_last_s: the clock at the first and
    /// the last render after which ShaderUtil.anythingCompiling was true (-1 if never).
    /// </summary>
    [Serializable]
    public class ShaderWarmUpRecord
    {
        public const string Play = "play", Edit = "edit", Session = "session";
        public const string ClockTime = "Time.time", ClockEditor = "EditorApplication.timeSinceStartup";
        public const string StatusDone = "done", StatusTimedOut = "timed_out", StatusNotInView = "not_in_view";

        public string part = "";
        public int round = -1;
        public string looks = "", stands = "", cameras = "", clock = "";
        public double time_start_s = -1, time_end_s = -1;
        public string started_local = "", ended_local = "";
        public bool compiling_at_start;
        public double compile_seen_first_s = -1, compile_seen_last_s = -1;
        public bool compiling_at_end;
        public int renders, last_clean_streak, error_pixels_seen;
        public int look_pixels = -1;
        public string status = "";
    }

    /// <summary>Addendum 12: follows one warm-up render by render (the rule of <see cref="ShaderWarmUp.Next"/>) and fills its record.</summary>
    public sealed class ShaderWarmUpTracker
    {
        public readonly ShaderWarmUpRecord Record;
        readonly double m_RealStart;

        public ShaderWarmUpTracker(ShaderWarmUpRecord record, double clockNow, double realNow, bool compiling, string localNow)
        {
            Record = record;
            record.time_start_s = clockNow;
            record.started_local = localNow ?? "";
            record.compiling_at_start = compiling;
            m_RealStart = realNow;
        }

        /// <summary>After a render of every camera: <paramref name="errorPixels"/> on all of them, whether a shader is compiling now.</summary>
        public ShaderWarmUp.State AfterRender(int errorPixels, bool compiling, double clockNow, double realNow, string localNow)
        {
            var r = Record;
            r.renders++;
            r.error_pixels_seen += errorPixels;
            r.last_clean_streak = errorPixels > 0 ? 0 : r.last_clean_streak + 1;
            if (compiling)
            {
                if (r.compile_seen_first_s < 0) r.compile_seen_first_s = clockNow;
                r.compile_seen_last_s = clockNow;
            }
            var state = ShaderWarmUp.Next(r.renders, r.last_clean_streak, compiling, (float)(realNow - m_RealStart));
            if (state != ShaderWarmUp.State.Continue)
            {
                r.time_end_s = clockNow;
                r.ended_local = localNow ?? "";
                r.compiling_at_end = compiling;
                r.status = state == ShaderWarmUp.State.Done ? ShaderWarmUpRecord.StatusDone : ShaderWarmUpRecord.StatusTimedOut;
            }
            return state;
        }
    }
}
