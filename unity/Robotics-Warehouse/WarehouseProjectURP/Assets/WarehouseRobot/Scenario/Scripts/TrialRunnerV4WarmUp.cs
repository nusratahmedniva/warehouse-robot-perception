using System;
using System.Collections;
using System.Collections.Generic;
using System.Globalization;
using UnityEngine;
using WarehouseAvatar;

namespace WarehouseRobot.Scenario
{
    /// <summary>
    /// experiments_ab.md section 15 addendum 12: the shader warm-up of a trial session. After the plans are made and before the leak test, every
    /// look of the session (every planned run's commander and bystanders; an experiment's planned workers) is drawn once: a temporary worker of the
    /// template with that look stands 2.0 m ahead of the start node A on A's heading, and a temporary camera with the pan-tilt camera's settings at
    /// A renders only a private layer (the worker is moved to it, so nothing hides it) until ShaderWarmUp's rule holds. A look whose render equals
    /// the empty render was not drawn (not_in_view) and the session does not start. The temporary worker is not in the session's worker list, has
    /// no run stream (no SetRun) and draws nothing: no seeded stream of the session is used, so every planned run is unchanged. The records go into
    /// session.json shader_warm_up.
    /// </summary>
    public partial class TrialRunnerV4
    {
        /// <summary>The temporary worker's distance ahead of A (the asking distance).</summary>
        const float WarmUpDistanceM = 2.0f;
        readonly List<ShaderWarmUpRecord> sessionWarmUps = new List<ShaderWarmUpRecord>();
        string warmUpError;

        /// <summary>Every look the session's runs use (all planned runs, also those before -startRun k).</summary>
        List<string> WarmUpLooks()
        {
            var all = new List<string>();
            if (Experiment) { foreach (var r in eRuns) foreach (var w in r.Workers) all.Add(w.Look); }
            else foreach (var p in plans) all.AddRange(p.AllLooks());
            return ShaderWarmUp.SessionLooks(all);
        }

        static bool WarmUpCompiling
        {
            get
            {
#if UNITY_EDITOR
                return UnityEditor.ShaderUtil.anythingCompiling;
#else
                return false;
#endif
            }
        }

        static string WarmUpNow() => DateTime.Now.ToString("yyyy-MM-dd'T'HH:mm:ss.fff", CultureInfo.InvariantCulture);

        /// <summary>Render the warm-up camera and read it back (RGBA32); in the Editor its shader variants compile synchronously.
        /// <paramref name="compiling"/>: a shader was compiling just before or just after the render.</summary>
        static byte[] WarmUpRender(Camera cam, RenderTexture rt, Texture2D tex, out bool compiling)
        {
            compiling = WarmUpCompiling;
#if UNITY_EDITOR
            bool async = UnityEditor.ShaderUtil.allowAsyncCompilation;
            UnityEditor.ShaderUtil.allowAsyncCompilation = false;
#endif
            var previous = RenderTexture.active;
            try
            {
                cam.targetTexture = rt;
                cam.Render();
                RenderTexture.active = rt;
                tex.ReadPixels(new Rect(0, 0, rt.width, rt.height), 0, 0, false);
                tex.Apply(false);
            }
            finally
            {
                cam.targetTexture = null;
                RenderTexture.active = previous;
#if UNITY_EDITOR
                UnityEditor.ShaderUtil.allowAsyncCompilation = async;
#endif
            }
            compiling |= WarmUpCompiling;
            return tex.GetRawTextureData();
        }

        static void SetLayerRecursive(GameObject go, int layer)
        {
            go.layer = layer;
            foreach (Transform t in go.transform) SetLayerRecursive(t.gameObject, layer);
        }

        /// <summary>The warm-up of every look of the session; sets warmUpError when a look is refused (its record is kept).</summary>
        IEnumerator WarmUpSessionLooks()
        {
            warmUpError = null;
            sessionWarmUps.Clear();
            int layer = ShaderWarmUp.FreeLayer(LayerMask.LayerToName);
            if (layer < 0) { warmUpError = "no unnamed layer (8 to 31) for the warm-up camera"; yield break; }
            var start = nodes[meta.start];
            var heading = Quaternion.Euler(0f, start.transform.eulerAngles.y, 0f) * Vector3.forward;
            float floorY = start.workerStand != null ? start.workerStand.position.y : start.Position.y;
            var a = new Vector3(start.Position.x, floorY, start.Position.z);
            var stand = a + heading * WarmUpDistanceM;
            var pt = robot.Config.Unity.pan_tilt_camera;
            var camGo = new GameObject("ShaderWarmUpCamera");
            var cam = camGo.AddComponent<Camera>();
            PanTiltCamera.ApplyCameraSettings(cam, pt);
            cam.enabled = false;
            cam.cullingMask = 1 << layer;
            camGo.transform.SetPositionAndRotation(a + Vector3.up * pt.height_m, Quaternion.LookRotation(heading, Vector3.up));
            var rt = new RenderTexture(pt.width_px, pt.height_px, 24, RenderTextureFormat.ARGB32) { name = "ShaderWarmUp" };
            rt.Create();
            var tex = new Texture2D(pt.width_px, pt.height_px, TextureFormat.RGBA32, false);
            try
            {
                yield return new WaitForEndOfFrame();
                byte[] empty = WarmUpRender(cam, rt, tex, out _);
                foreach (var look in WarmUpLooks())
                {
                    var w = Instantiate(workerPrefab, stand, Quaternion.LookRotation(-heading, Vector3.up), workersRoot);
                    w.name = "ShaderWarmUp_" + look;
                    w.lookId = look;
                    w.robot = robot.transform;
                    w.robotEye = robot.PanTilt != null ? robot.PanTilt.transform : null;
                    if (Experiment && elooks != null) w.extraLooks = new List<LookEntry>(elooks.looks);
                    AddS1Sources(w);
                    if (!w.Initialize())
                    {
                        warmUpError = $"look {look}: {w.Problem}";
                        Destroy(w.gameObject);
                        yield break;
                    }
                    SetLayerRecursive(w.gameObject, layer);
                    var rec = new ShaderWarmUpRecord
                    {
                        part = ShaderWarmUpRecord.Session, looks = look, clock = ShaderWarmUpRecord.ClockTime,
                        stands = $"{WarmUpDistanceM.ToString("0.0", Inv)} m ahead of {meta.start} on its heading ({stand.x.ToString("0.00", Inv)}, {stand.z.ToString("0.00", Inv)})",
                        cameras = $"pan-tilt settings at {meta.start}, height {pt.height_m.ToString("0.00", Inv)} m, rendering only layer {layer.ToString(Inv)}",
                    };
                    var tracker = new ShaderWarmUpTracker(rec, Time.time, Time.realtimeSinceStartup, WarmUpCompiling, WarmUpNow());
                    ShaderWarmUp.State state;
                    byte[] last;
                    do
                    {
                        yield return new WaitForEndOfFrame();
                        last = WarmUpRender(cam, rt, tex, out bool compiling);
                        ShaderWarmUp.ErrorShaderPixels(last, out int magenta, out int cyan);
                        state = tracker.AfterRender(magenta + cyan, compiling, Time.time, Time.realtimeSinceStartup, WarmUpNow());
                    } while (state == ShaderWarmUp.State.Continue);
                    rec.look_pixels = ShaderWarmUp.DifferingPixels(empty, last);
                    if (state == ShaderWarmUp.State.Done && rec.look_pixels == 0) rec.status = ShaderWarmUpRecord.StatusNotInView;
                    sessionWarmUps.Add(rec);
                    Destroy(w.gameObject);
                    yield return null;
                    if (rec.status != ShaderWarmUpRecord.StatusDone)
                    {
                        warmUpError = $"look {look}: {rec.status} ({rec.renders} renders, last clean streak {rec.last_clean_streak}, compiling {rec.compiling_at_end}, " +
                                      $"look pixels {rec.look_pixels})";
                        yield break;
                    }
                }
            }
            finally
            {
                Destroy(camGo);
                rt.Release();
                Destroy(rt);
                Destroy(tex);
            }
        }
    }
}
