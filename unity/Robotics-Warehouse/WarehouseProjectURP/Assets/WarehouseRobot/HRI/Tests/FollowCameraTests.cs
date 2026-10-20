using NUnit.Framework;
using UnityEngine;

namespace WarehouseHRI.Tests
{
    public class FollowCameraTests
    {
        [Test]
        public void CKeyCyclesChaseTopDownGestureCamera()
        {
            var go = new GameObject("view", typeof(Camera));
            try
            {
                var f = go.AddComponent<FollowCamera>();
                Assert.AreEqual(FollowCameraMode.Chase, f.mode, "chase is the default view");
                f.Cycle();
                Assert.AreEqual(FollowCameraMode.TopDown, f.mode);
                f.Cycle();
                Assert.AreEqual(FollowCameraMode.GestureCamera, f.mode);
                Assert.AreEqual("gesture camera", f.ModeLabel);
                f.Cycle();
                Assert.AreEqual(FollowCameraMode.Chase, f.mode);
                Assert.AreEqual(KeyCode.C, f.toggleKey);
            }
            finally
            {
                Object.DestroyImmediate(go);
            }
        }
    }
}
