using UnityEngine;

namespace WarehouseAvatar
{
    /// <summary>Forwards OnAnimatorIK from the look's Animator (a child object) to its WorkerV4. Added at Play by WorkerV4.</summary>
    [DisallowMultipleComponent]
    public class WorkerIkRelay : MonoBehaviour
    {
        public WorkerV4 Worker { get; set; }

        void OnAnimatorIK(int layerIndex)
        {
            if (Worker != null) Worker.OnIK(layerIndex);
        }
    }
}
