using System.IO;
using System.Text.RegularExpressions;
using NUnit.Framework;
using UnityEngine;
using WarehouseHRI.V4;

namespace WarehouseHRI.Tests
{
    /// <summary>
    /// v4 hand zoom with tilt (2026-11-12, P6; Avatar/Config/upgrade_design.md section 5): the tilt a command resolves to,
    /// Unity's tilt range against Python's, and the self-visibility check over every pan and tilt.
    /// </summary>
    public class PanTiltTiltTests
    {
        static string Repo(string rel) => Path.GetFullPath(Path.Combine(Application.dataPath, "../../../..", rel));

        [Test]
        public void TryResolveTilt_DefaultClampAndInvalid()
        {
            Assert.IsTrue(ProtocolV3.TryResolveTilt(-1f, 0f, 0f, 35f, out float a, out _));
            Assert.AreEqual(0f, a);
            Assert.IsTrue(ProtocolV3.TryResolveTilt(22.5f, 0f, 0f, 35f, out a, out _));
            Assert.AreEqual(22.5f, a);
            Assert.IsTrue(ProtocolV3.TryResolveTilt(60f, 0f, 0f, 35f, out a, out _));
            Assert.AreEqual(35f, a, "clamped to Unity's range");
            foreach (var bad in new[] { -5f, 90f, 120f, float.NaN, float.PositiveInfinity })
                Assert.IsFalse(ProtocolV3.TryResolveTilt(bad, 0f, 0f, 35f, out _, out string err), bad.ToString());
        }

        [Test]
        public void TiltRange_UnityEqualsPythonsZoomRule()
        {
            string unity = File.ReadAllText(Path.Combine(Application.dataPath, "WarehouseRobot/Robot/Config/robot_unity_v4.json"));
            string py = File.ReadAllText(Repo("robot_vision/configs/v4/control.json"));
            float Num(string json, string key)
            {
                var m = Regex.Match(json, "\"" + key + "\"\\s*:\\s*(-?[0-9.]+)");
                Assert.IsTrue(m.Success, key);
                return float.Parse(m.Groups[1].Value, System.Globalization.CultureInfo.InvariantCulture);
            }
            Assert.AreEqual(Num(py, "tilt_min_deg"), Num(unity, "tilt_min_deg"));
            Assert.AreEqual(Num(py, "tilt_max_deg"), Num(unity, "tilt_max_deg"));
            Assert.AreEqual(0f, Num(unity, "tilt_deg"), "the default tilt is level");
        }

        static GameObject Box(Transform root, string name, Vector3 centre, Vector3 size, PrimitiveType type = PrimitiveType.Cube)
        {
            var go = GameObject.CreatePrimitive(type);
            go.name = name;
            Object.DestroyImmediate(go.GetComponent<Collider>());
            go.transform.SetParent(root, false);
            go.transform.localPosition = centre;
            go.transform.localScale = size;
            return go;
        }

        [Test]
        public void SelfVisibility_MastThroughTheCameraAndBodyBelowAreNeverSeen()
        {
            var root = new GameObject("robot");
            try
            {
                Box(root.transform, "Body", new Vector3(0f, 0.3f, 0f), new Vector3(0.6f, 0.5f, 0.8f));
                Box(root.transform, "Mast", new Vector3(0f, 1.05f, 0f), new Vector3(0.05f, 0.55f, 0.05f), PrimitiveType.Cylinder);
                var cam = new Vector3(0f, 1.2f, 0f);
                var v = PanTiltGeometry.SelfVisibilityViolations(root.transform, cam, 60f, 730f / 530f, 0.1f, -180f, 180f, 0f, 35f);
                CollectionAssert.IsEmpty(v, string.Join(", ", v));

                Box(root.transform, "Front", new Vector3(0f, 1.2f, 1.0f), new Vector3(0.1f, 0.1f, 0.1f));
                v = PanTiltGeometry.SelfVisibilityViolations(root.transform, cam, 60f, 730f / 530f, 0.1f, -180f, 180f, 0f, 35f);
                CollectionAssert.AreEqual(new[] { "Front" }, v);
            }
            finally { Object.DestroyImmediate(root); }
        }

        [Test]
        public void SelfVisibility_APartAboveIsSeenOnlyWhenTilted()
        {
            var root = new GameObject("robot");
            try
            {
                Box(root.transform, "Above", new Vector3(0f, 1.7f, 0.4f), new Vector3(0.05f, 0.05f, 0.05f));    // 51 deg above the camera
                var cam = new Vector3(0f, 1.2f, 0f);
                CollectionAssert.IsEmpty(PanTiltGeometry.SelfVisibilityViolations(root.transform, cam, 60f, 730f / 530f, 0.1f, -180f, 180f, 0f, 0f));
                CollectionAssert.AreEqual(new[] { "Above" },
                    PanTiltGeometry.SelfVisibilityViolations(root.transform, cam, 60f, 730f / 530f, 0.1f, -180f, 180f, 0f, 35f));
            }
            finally { Object.DestroyImmediate(root); }
        }
    }
}
