using UnityEditor;
using UnityEditor.SceneManagement;
using UnityEngine;

namespace WarehouseRobot.Bridge.EditorTools
{
    /// <summary>Menu "Warehouse Robot > Create Bridge Client In Scene": adds a RobotBridge object wired to the robot.</summary>
    public static class BridgeMenu
    {
        // Unity asset path (project-relative, the same on every OS).
        const string ConfigAssetPath = "Assets/WarehouseRobot/Bridge/Config/bridge_unity.json";
        const string Title = "Create Bridge Client";

        [MenuItem("Warehouse Robot/Create Bridge Client In Scene")]
        public static void CreateBridgeClient()
        {
            var existing = Object.FindFirstObjectByType<RobotBridgeClient>();
            if (existing != null)
            {
                Selection.activeObject = existing.gameObject;
                EditorUtility.DisplayDialog(Title, "The scene already has a bridge client ('" + existing.name + "').", "OK");
                return;
            }
            var robot = Object.FindFirstObjectByType<RobotRig>();
            if (robot == null)
            {
                EditorUtility.DisplayDialog(Title, "No robot in the open scene. Place WarehouseRobot.prefab first.", "OK");
                return;
            }
            var config = AssetDatabase.LoadAssetAtPath<TextAsset>(ConfigAssetPath);
            if (config == null)
            {
                EditorUtility.DisplayDialog(Title, "Config not found: " + ConfigAssetPath, "OK");
                return;
            }
            var go = new GameObject("RobotBridge");
            Undo.RegisterCreatedObjectUndo(go, Title);
            go.AddComponent<RobotBridgeClient>().Bind(config, robot);
            EditorUtility.SetDirty(go);
            EditorSceneManager.MarkSceneDirty(go.scene);
            Selection.activeObject = go;
            Debug.Log("[BridgeMenu] Created 'RobotBridge' for robot '" + robot.name + "'. Save the scene to keep it.");
        }
    }
}
