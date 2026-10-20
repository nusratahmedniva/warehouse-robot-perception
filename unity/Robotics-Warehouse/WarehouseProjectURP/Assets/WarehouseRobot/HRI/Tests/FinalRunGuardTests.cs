using System.IO;
using NUnit.Framework;

namespace WarehouseHRI.Tests
{
    public class FinalRunGuardTests
    {
        string m_Root;

        [SetUp]
        public void SetUp()
        {
            m_Root = Path.Combine(Path.GetTempPath(), "FinalRunGuardTests_" + System.Guid.NewGuid().ToString("N"));
            Directory.CreateDirectory(m_Root);
        }

        [TearDown]
        public void TearDown()
        {
            if (Directory.Exists(m_Root)) Directory.Delete(m_Root, true);
        }

        void Final(string folder, bool done)
        {
            string d = Path.Combine(m_Root, folder);
            Directory.CreateDirectory(d);
            if (done) File.WriteAllText(Path.Combine(d, FinalRunGuard.DoneFile), "{}");
        }

        [Test]
        public void Task2FinalPresent_Task1FinalAllowed()
        {
            Final("trials_final_Task2_20261020_172445", true);
            Assert.IsNull(FinalRunGuard.EarlierFinal(m_Root, "Task1"));
            Assert.AreEqual("trials_final_Task2_20261020_172445", FinalRunGuard.EarlierFinal(m_Root, "Task2"));
        }

        [Test]
        public void Task1FinalPresent_Task1FinalRefused()
        {
            Final("trials_final_Task2_20261020_172445", true);
            Final("trials_final_Task1_20261021_120000", true);
            Assert.AreEqual("trials_final_Task1_20261021_120000", FinalRunGuard.EarlierFinal(m_Root, "Task1"));
        }

        [Test]
        public void UnfinishedFinalFolderDoesNotBlock()
        {
            Final("trials_final_Task1_20261021_120000", false);
            Assert.IsNull(FinalRunGuard.EarlierFinal(m_Root, "Task1"));
        }

        [Test]
        public void MissingOutputRootAllows()
        {
            Assert.IsNull(FinalRunGuard.EarlierFinal(Path.Combine(m_Root, "absent"), "Task1"));
        }

        [Test]
        public void WeightsHashChecked()
        {
            string w = Path.Combine(m_Root, "w.pt");
            File.WriteAllText(w, "abc");
            // sha256("abc")
            const string abc = "ba7816bf8f01cfea414140de5dae2223b00361a396177a9cb410ff61f20015ad";
            Assert.IsNull(FinalRunGuard.WeightsProblem(w, abc));
            Assert.IsNotNull(FinalRunGuard.WeightsProblem(w, new string('0', 64)));
            Assert.IsNotNull(FinalRunGuard.WeightsProblem(Path.Combine(m_Root, "missing.pt"), abc));
            Assert.IsNotNull(FinalRunGuard.WeightsProblem(w, ""));
        }
    }
}
