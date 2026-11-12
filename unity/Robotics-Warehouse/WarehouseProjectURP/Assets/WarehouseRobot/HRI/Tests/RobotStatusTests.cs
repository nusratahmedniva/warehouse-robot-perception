using NUnit.Framework;
using WarehouseHRI.V4;

namespace WarehouseHRI.Tests
{
    /// <summary>The v4 robot's light ring and front display (2026-11-12, U1; upgrade_design.md section 7).</summary>
    public class RobotStatusTests
    {
        [Test]
        public void Light_FollowsTheDeclaredColours()
        {
            Assert.AreEqual(RobotStatus.Light.Driving, RobotStatus.LightFor("navigate"));
            Assert.AreEqual(RobotStatus.Light.Driving, RobotStatus.LightFor("execute"));
            Assert.AreEqual(RobotStatus.Light.Searching, RobotStatus.LightFor("scan"));
            Assert.AreEqual(RobotStatus.Light.Searching, RobotStatus.LightFor("approach"));
            Assert.AreEqual(RobotStatus.Light.Asking, RobotStatus.LightFor("ask"));
            Assert.AreEqual(RobotStatus.Light.Asking, RobotStatus.LightFor("read"));
            Assert.AreEqual(RobotStatus.Light.Asking, RobotStatus.LightFor("wait"));
            Assert.AreEqual(RobotStatus.Light.Stopped, RobotStatus.LightFor("navigate (stopped: STOP gesture)"));
            Assert.AreEqual(RobotStatus.Light.Stopped, RobotStatus.LightFor("aborted"));
            Assert.AreEqual(RobotStatus.Light.Idle, RobotStatus.LightFor("done"));
            Assert.AreEqual(RobotStatus.Light.Idle, RobotStatus.LightFor(null));
            Assert.AreEqual(RobotStatus.Green, RobotStatus.ColorFor(RobotStatus.Light.Driving));
            Assert.AreEqual(RobotStatus.Red, RobotStatus.ColorFor(RobotStatus.Light.Stopped));
        }

        [Test]
        public void Display_ShowsTheScreenTextElseTheState()
        {
            Assert.AreEqual("Which direction?", RobotStatus.MessageFor("read", "Which direction?", "NONE"));
            Assert.AreEqual("Going LEFT", RobotStatus.MessageFor("execute", "", "LEFT"));
            Assert.AreEqual("Driving", RobotStatus.MessageFor("navigate", "", "NONE"));
            Assert.AreEqual("STOP", RobotStatus.MessageFor("navigate (stopped: STOP gesture)", "", "FORWARD"));
            Assert.AreEqual("Looking for help", RobotStatus.MessageFor("scan", "", ""));
            Assert.AreEqual("Arrived", RobotStatus.MessageFor("done", "", "RIGHT"));
        }
    }
}
