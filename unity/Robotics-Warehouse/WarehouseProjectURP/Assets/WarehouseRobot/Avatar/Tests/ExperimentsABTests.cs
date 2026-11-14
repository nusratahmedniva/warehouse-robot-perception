using System.IO;
using System.Linq;
using System.Text.RegularExpressions;
using NUnit.Framework;
using UnityEngine;
using WarehouseHRI.V4;

namespace WarehouseAvatar.Tests
{
    /// <summary>
    /// Experiments A and B, avatars (Avatar/Config/experiments_ab.md section 2): looks_ab.json (names, kinds, split proposal, git-ignored
    /// imports) and the avatar-experiment Play config. The lie and truth-field tests are in ExperimentLiesTests.
    /// </summary>
    public class ExperimentsABTests
    {
        static string Project(string rel) => File.ReadAllText(Path.Combine(Application.dataPath, "..", rel));
        static string Repo(string rel) => File.ReadAllText(Path.Combine(Application.dataPath, "../../../..", rel));

        [Test]
        public void LooksAB_IsValid_NamesEncodePersonGenderCostume_AndTheFbxLooksStayGitIgnored()
        {
            var f = ExperimentLooks.Parse(Project(ExperimentLooks.AssetPath));
            var worker = WorkerV4Config.Parse(Project("Assets/WarehouseRobot/Avatar/Config/worker_v4.json"));
            CollectionAssert.IsEmpty(ExperimentLooks.Validate(f, worker.looks));
            var nav = f.looks.Where(l => l.navigation).ToList();
            Assert.GreaterOrEqual(nav.Count(l => l.gender == "male"), 3, "3 costume variants per gender");
            Assert.GreaterOrEqual(nav.Count(l => l.gender == "female"), 3);
            foreach (var l in nav) StringAssert.IsMatch($"^{l.person}_{(l.gender == "male" ? "m" : "f")}_[a-z0-9]+(_[a-z0-9]+)*$", l.id);
            Assert.IsTrue(nav.All(l => l.kind == LookEntry.KindSunbox), "navigation looks are human-like (Sunbox)");
            foreach (var kind in new[] { ExperimentLook.Realistic, ExperimentLook.Stylised, ExperimentLook.Anime, ExperimentLook.Cartoon })
                Assert.IsTrue(f.avatar_experiment.Any(id => (f.looks.FirstOrDefault(l => l.id == id)?.kind_group ?? ExperimentLook.Stylised) == kind), kind);
            string ignore = File.ReadAllText(Path.Combine(Application.dataPath, "../../../../.gitignore"));
            StringAssert.Contains("unity/**/Assets/ThirdParty/", ignore, "imported characters are never committed");
            foreach (var l in f.looks.Where(l => l.kind == LookEntry.KindPrefab && l.kind_group != ExperimentLook.Realistic))
                StringAssert.StartsWith(f.paths.import_folder + "/", l.asset, l.id);
            StringAssert.StartsWith("Assets/ThirdParty/", f.paths.import_folder);
        }

        [Test]
        public void LookCheckPlayAB_DiffersFromTheDeclaredPlayConfigOnlyInLooksAndPrefix()
        {
            string a = Project("Assets/WarehouseRobot/Avatar/Config/look_check_play.json"), b = Project("Assets/WarehouseRobot/Avatar/Config/look_check_play_ab.json");
            string Strip(string s)
            {
                s = s.Replace("\r\n", "\n");
                foreach (var key in new[] { "\"note\": \"[^\"]*\",", "\"looks\": \\[[^\\]]*\\],", "\"looks_excluded\": \\{[^}]*\\},", "\"run_prefix\": \"[^\"]*\"," })
                    s = Regex.Replace(s, "\n[ ]*" + key, "");
                return s;
            }
            Assert.AreEqual(Strip(a), Strip(b));
            var f = ExperimentLooks.Parse(Project(ExperimentLooks.AssetPath));
            var looks = Regex.Matches(Regex.Match(b, "\"looks\": \\[([^\\]]*)\\]").Groups[1].Value, "\"([^\"]+)\"").Cast<Match>().Select(m => m.Groups[1].Value).ToList();
            var excluded = Regex.Matches(Regex.Match(b, "\"looks_excluded\": \\{([^}]*)\\}").Groups[1].Value, "\"([a-z0-9_]+)\":").Cast<Match>().Select(m => m.Groups[1].Value).ToList();
            CollectionAssert.AreEquivalent(f.avatar_experiment, looks.Concat(excluded), "every avatar-experiment look is checked in Play or excluded with its reason");
        }
    }
}
