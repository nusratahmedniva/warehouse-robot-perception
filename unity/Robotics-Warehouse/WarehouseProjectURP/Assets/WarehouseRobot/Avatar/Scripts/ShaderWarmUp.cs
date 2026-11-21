using System;

namespace WarehouseAvatar
{
    /// <summary>
    /// experiments_ab.md section 15 addendum 11: the Play look check's shader warm-up and its error-shader pixel count. The Editor draws a
    /// shader variant that is still compiling as flat cyan (0, 255, 255) and a missing shader as magenta (255, 0, 255); the avatar rehearsal of
    /// 2026-11-21 recorded 38 cyan frames at the first render of the anime materials although asynchronous compilation was switched off for the
    /// session. LookCheckPlayDriver renders every camera before a round's first take until <see cref="Next"/> says done. The limits are operating
    /// limits of the capture, not evaluation thresholds.
    /// </summary>
    public static class ShaderWarmUp
    {
        /// <summary>At least this many renders of every camera.</summary>
        public const int MinRenders = 3;
        /// <summary>The last this many renders of every camera without an error-shader pixel.</summary>
        public const int CleanRenders = 2;
        /// <summary>A warm-up that is not done after this many seconds of real time fails the run.</summary>
        public const float MaxSeconds = 120f;

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

        /// <summary>The stop rule after a render of every camera: done when at least <see cref="MinRenders"/> renders were made, the last
        /// <paramref name="cleanStreak"/> renders had no error-shader pixel on any camera (at least <see cref="CleanRenders"/>) and nothing is
        /// compiling; timed out after <see cref="MaxSeconds"/>; otherwise render again.</summary>
        public static State Next(int renders, int cleanStreak, bool compiling, float seconds)
        {
            if (renders >= MinRenders && cleanStreak >= CleanRenders && !compiling) return State.Done;
            return seconds >= MaxSeconds ? State.TimedOut : State.Continue;
        }
    }
}
