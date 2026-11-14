using System;
using System.Collections.Generic;
using UnityEngine;

namespace WarehouseAvatar
{
    /// <summary>A look's source asset (by its project path in worker_v4.json) and the prefab it refers to.</summary>
    [Serializable]
    public class LookSource
    {
        public string asset;
        public GameObject prefab;
        /// <summary>Optional (experiments A/B, 2026-11-14): put on every renderer slot of the spawned look (a look's material_override,
        /// resolved by the Editor launcher, which knows asset paths). Null = keep the look's own materials.</summary>
        public Material materialOverride;
    }

    /// <summary>What a worker is asked to show. Clip "" = drawn from AllowedClips (or every clip of the command).</summary>
    public struct GestureRequest
    {
        public string Command;
        public string Clip;
        public IList<string> AllowedClips;
        /// <summary>POINT: the direction to point in, world space (only its horizontal part is used).</summary>
        public Vector3 PointDirection;
        /// <summary>"left", "right" or "" (the variation rule).</summary>
        public string Arm;
        /// <summary>Start without waiting for the question: a STOP shown while the robot drives, or the direction that follows a
        /// WAIT within the same ask (the question appeared before the WAIT); never the first answer to a question.</summary>
        public bool IgnoreQuestion;
        /// <summary>&gt; 0: hold the gesture this long instead of the drawn hold_s (declared scenarios only, e.g. STOP while driving).</summary>
        public float HoldS;
        /// <summary>Experiments A/B (2026-11-14): the direction shown is a lie (truth.jsonl gesture_truthful false while it is performed).</summary>
        public bool Lie;
    }

    /// <summary>
    /// v4 worker template (Phase 2B). One prefab for every worker; the look comes from worker_v4.json by lookId, so
    /// swapping the look changes nothing else. At Play the look is spawned under the worker and driven by the template's
    /// AnimatorController (Assets/WarehouseRobot/Avatar/Animation/WorkerV4.controller) through an override controller:
    /// - base layer: idle and turn (the clips from the git-ignored Mixamo import folder);
    /// - gesture layer (masked to arms and hands): the Mixamo variants, mirrored for the other arm;
    /// - Humanoid IK (OnAnimatorIK): the head looks at the robot; the gesturing hand goes to the command's target (any
    ///   POINT direction; the procedural WAIT and STOP variants are IK only);
    /// - after the Animator (LateUpdate): the hand orientation and the finger shapes of the command.
    /// Behaviour: idle -> notices the robot (behaviour.notice_distance_m) -> turns to face it -> a requested gesture
    /// starts only after "Which direction?" is visible (SetQuestionVisible) -> start_delay -> gesturing -> holding ->
    /// returning -> idle. The gesture's speed, size, arm and start delay are drawn from a stream seeded per run and worker
    /// (SetRun). Nothing here is ever sent over the bridge; truth is read through Truth() by the TruthLogger only.
    /// </summary>
    [DisallowMultipleComponent]
    public class WorkerV4 : MonoBehaviour
    {
        public TextAsset config;
        public RuntimeAnimatorController controller;
        public LookSource[] lookSources = new LookSource[0];
        [Tooltip("A look id of worker_v4.json")]
        public string lookId = "sunbox_m1";
        [Tooltip("truth.jsonl worker_id: the same worker keeps it for the whole run")]
        public int workerId = 1;
        [Tooltip("The robot's root: its forward axis is the reference of point_angle_deg")]
        public Transform robot;
        [Tooltip("Where the head looks (the robot's pan-tilt camera); the robot's root when empty")]
        public Transform robotEye;
        [Tooltip("Turn to face the robot once it is noticed")]
        public bool facesRobot = true;
        /// <summary>Experiments A/B (2026-11-14, experiments_ab.md section 2): looks of looks_ab.json, used when worker_v4.json does not
        /// define lookId. Set at Play by the scenario before Initialize; never serialized (the template prefab is unchanged).</summary>
        [NonSerialized] public IList<LookEntry> extraLooks;

        public const string ParamTurning = "Turning", ParamMirror = "Mirror", ParamGestureSpeed = "GestureSpeed";
        public const int BaseLayer = 0, GestureLayer = 1;
        public const string GestureStatePrefix = "G_";

        public WorkerV4Config Config { get; private set; }
        public string Problem { get; private set; } = "";
        public bool Ready { get; private set; }
        public Animator Animator { get; private set; }
        public GameObject LookInstance { get; private set; }
        public string LookDescription { get; private set; } = "";
        public bool IsCommander { get; set; }
        /// <summary>Experiments A/B (2026-11-14): write gesture_truthful in every truth row (protocol_v3.md amendment 4). Off = rows as before.</summary>
        public bool ReportTruthful { get; set; }
        /// <summary>Experiments A/B: write the extra field active (false while switched off by the activation window). Off = rows as before.</summary>
        public bool ReportActive { get; set; }
        /// <summary>The current (or last) gesture shows a wrong direction (GestureRequest.Lie).</summary>
        public bool CurrentIsLie { get; private set; }
        public bool Noticed { get; private set; }
        public bool Turning { get; private set; }
        public WorkerPhase Phase => m_Scheduler.Phase;
        public int PhaseSerial => m_Scheduler.Serial;
        public GestureParams Current { get; private set; }
        public GestureClipSpec CurrentSpec { get; private set; }
        /// <summary>The horizontal direction the POINT actually shows (after the body-azimuth limit), world space.</summary>
        public Vector3 ShownPointDirection { get; private set; }
        public float ArmLength { get; private set; }
        public bool QuestionVisible => m_Scheduler.QuestionVisible;
        /// <summary>A gesture is queued or under way (not idle): the worker can neither be moved nor asked again.</summary>
        public bool Busy => m_Scheduler.Phase != WorkerPhase.Idle || m_Scheduler.Pending;
        /// <summary>Diagnostics: OnAnimatorIK calls that set the gesturing hand, and the hand's distance to its IK target
        /// after the Animator (both read by the Play-mode look check).</summary>
        public int HandIkCalls { get; private set; }
        public float HandToTargetM { get; private set; } = -1f;

        /// <summary>The current POINT split into stance, torso turn and arm (pointing_design.md); zero for WAIT and STOP.</summary>
        public PointingSplit CurrentSplit { get; private set; }
        /// <summary>The worker holds an angled stance for the current POINT (until the gesture has returned).</summary>
        public bool InStance => m_Stance;

        readonly GestureScheduler m_Scheduler = new GestureScheduler();
        readonly Dictionary<string, AnimationClip> m_Clips = new Dictionary<string, AnimationClip>();
        ClipIndex m_Index;
        SeededRandom m_Rng = SeededRandom.For(0, 0, 1);
        LookPoser.Arm m_Left, m_Right;
        Quaternion[][] m_BindLeft, m_BindRight;
        Vector3 m_Target, m_Hint, m_PointDir;
        float m_IkWeight, m_LookWeight, m_LayerWeight;
        bool m_Mixamo;
        // option A (pointing_design.md): the stance's root rotation, the torso turn, the bones it uses, and the
        // gesturing shoulder as the Animator left it (before the turn) for the next frame's IK target
        bool m_Stance, m_Twisted;
        Quaternion m_StanceRotation;
        Transform[] m_Spine = new Transform[0];
        Transform m_Neck, m_Head;
        Transform m_LeftFoot, m_RightFoot;       // ankle joints of the Humanoid (truth ankle_height_m, P1)
        Vector3 m_AnimShoulder;

        bool m_InitDone;

        void Start() => Initialize();

        /// <summary>Spawn the look and set up the Animator (Play mode, once). A scenario that sets lookId or workerId on a new
        /// instance calls this itself after setting them; otherwise Start does.</summary>
        public bool Initialize()
        {
            if (m_InitDone || !Application.isPlaying) return Ready;
            m_InitDone = true;
            try { Ready = Init(); }
            catch (Exception e) { Fail("could not set up the worker: " + e.Message); }
            if (!Ready) Debug.LogError($"[WorkerV4] {name}: {Problem}");
            return Ready;
        }

        bool Fail(string why)
        {
            Problem = why;
            return false;
        }

        bool Init()
        {
            if (config == null) return Fail("no worker_v4.json assigned");
            Config = WorkerV4Config.Parse(config.text);
            var errors = Config.Validate();
            if (errors.Count > 0) return Fail("worker_v4.json: " + string.Join("; ", errors));
            var look = ExperimentLooks.Find(Config, extraLooks, lookId);
            if (look == null) return Fail($"look '{lookId}' is not in worker_v4.json" + (extraLooks != null ? " or looks_ab.json" : ""));
            GameObject prefab = null;
            Material overrideMat = null;
            foreach (var s in lookSources) if (s != null && s.asset == look.asset) { prefab = s.prefab; overrideMat = s.materialOverride; }
            if (prefab == null) return Fail($"look '{lookId}': {look.asset} is not installed or not assigned (third-party, git-ignored: import it, then rebuild the worker template)");

            if (!LoadClips(out string clipError)) return Fail(clipError);

            LookInstance = Instantiate(prefab, transform);
            LookInstance.name = "Look_" + lookId;
            LookInstance.transform.localPosition = Vector3.zero;
            LookInstance.transform.localRotation = Quaternion.identity;
            if (look.kind == LookEntry.KindSunbox)
            {
                Animator = SunboxLookApplier.Apply(LookInstance, look.sunbox, out string description);
                SunboxLookApplier.DisableLocomotion(LookInstance);
                LookDescription = description;
            }
            else Animator = LookInstance.GetComponentInChildren<Animator>();
            if (overrideMat != null)
            {
                foreach (var r in LookInstance.GetComponentsInChildren<Renderer>(true))
                {
                    var mats = new Material[Mathf.Max(1, r.sharedMaterials.Length)];
                    for (int i = 0; i < mats.Length; i++) mats[i] = overrideMat;
                    r.sharedMaterials = mats;
                }
                LookDescription += (LookDescription.Length > 0 ? " " : "") + $"Material override {overrideMat.name} on every renderer.";
            }
            if (Animator == null || Animator.avatar == null || !Animator.avatar.isHuman) return Fail($"look '{lookId}' has no Humanoid Animator");
            var avatarFix = HumanAvatarFix.Apply(Animator);     // IK goals land where asked only if the Avatar matches the scene
            if (avatarFix.Count > 0) LookDescription += $" Humanoid Avatar rebuilt to match the scene: {string.Join(", ", avatarFix)}.";

            var bones = new AnimatorBones(Animator);
            m_Left = HandShaper.BuildArm(bones, false);
            m_Right = HandShaper.BuildArm(bones, true);
            if (!HandShaper.Complete(m_Left) || !HandShaper.Complete(m_Right)) return Fail($"look '{lookId}' lacks arm or finger bones");
            float mirrored = HandShaper.MirrorRest(m_Right, m_Left);  // both hands start every shape from mirror-image fingers
            if (mirrored < 0f) return Fail($"look '{lookId}': the hand axes cannot be measured");
            if (mirrored > 0.001f) LookDescription += $" Left hand's rest fingers mirrored from the right hand (largest joint correction {(mirrored * 1000f).ToString("0.0", System.Globalization.CultureInfo.InvariantCulture)} mm).";
            m_BindLeft = HandShaper.Capture(m_Left);        // the prefab's bind pose: straight fingers
            m_BindRight = HandShaper.Capture(m_Right);
            ArmLength = 0.5f * (HandShaper.ArmLength(m_Left) + HandShaper.ArmLength(m_Right));
            var spine = new List<Transform>();
            foreach (var b in new[] { HumanBodyBones.Spine, HumanBodyBones.Chest, HumanBodyBones.UpperChest })
                if (bones.Get(b) != null) spine.Add(bones.Get(b));
            m_Spine = spine.ToArray();
            m_Neck = bones.Get(HumanBodyBones.Neck);
            m_Head = bones.Get(HumanBodyBones.Head);
            m_LeftFoot = bones.Get(HumanBodyBones.LeftFoot);
            m_RightFoot = bones.Get(HumanBodyBones.RightFoot);
            if (m_Spine.Length == 0 || m_Head == null) return Fail($"look '{lookId}' lacks spine or head bones");

            if (controller == null) return Fail("no AnimatorController assigned (Tools > Warehouse v4 > Workers > Build Worker Template)");
            var aoc = new AnimatorOverrideController(controller) { name = "WorkerV4_" + lookId };
            var overrides = new List<KeyValuePair<AnimationClip, AnimationClip>>(aoc.overridesCount);
            aoc.GetOverrides(overrides);
            for (int i = 0; i < overrides.Count; i++)
            {
                var placeholder = overrides[i].Key;
                if (!PlaceholderClip(placeholder.name, out var clip)) return Fail($"the controller's clip '{placeholder.name}' has no source (rebuild the worker template after changing worker_v4.json)");
                overrides[i] = new KeyValuePair<AnimationClip, AnimationClip>(placeholder, clip);
            }
            aoc.ApplyOverrides(overrides);
            // The relay must exist when the Animator binds: it looks for OnAnimatorIK receivers then.
            var relay = Animator.gameObject.GetComponent<WorkerIkRelay>() ?? Animator.gameObject.AddComponent<WorkerIkRelay>();
            relay.Worker = this;
            Animator.runtimeAnimatorController = aoc;
            Animator.applyRootMotion = false;
            Animator.cullingMode = AnimatorCullingMode.AlwaysAnimate;   // the robot cameras render on demand: never cull
            Animator.Rebind();
            Animator.SetFloat(ParamGestureSpeed, 1f);
            Animator.SetLayerWeight(GestureLayer, 0f);
            return true;
        }

        /// <summary>Placeholder names in the controller: placeholder_idle, placeholder_turn, placeholder_&lt;variant&gt;.</summary>
        public static string PlaceholderName(string role) => "placeholder_" + role;

        bool PlaceholderClip(string placeholder, out AnimationClip clip)
        {
            clip = null;
            string role = placeholder.StartsWith("placeholder_", StringComparison.Ordinal) ? placeholder.Substring("placeholder_".Length) : "";
            if (role == "idle") return m_Clips.TryGetValue(Config.animation.idle_clip_file, out clip);
            if (role == "turn")
            {
                string file = string.IsNullOrEmpty(Config.animation.turn_clip_file) ? Config.animation.idle_clip_file : Config.animation.turn_clip_file;
                return m_Clips.TryGetValue(file, out clip);
            }
            var spec = Config.Clip(role);
            return spec != null && spec.IsMixamo && m_Clips.TryGetValue(spec.source_file, out clip);
        }

        /// <summary>The Mixamo clips and their index, from the git-ignored Resources import folder.</summary>
        bool LoadClips(out string error)
        {
            error = null;
            string res = Config.paths.clip_resources_path;
            var indexAsset = Resources.Load<TextAsset>(res + "/" + Config.paths.clip_index_name);
            if (indexAsset == null)
            {
                error = $"no clip index in {Config.paths.clip_import_folder} (Tools > Warehouse v4 > Workers > Import Mixamo Clips)";
                return false;
            }
            m_Index = JsonUtility.FromJson<ClipIndex>(indexAsset.text);
            var files = new List<string> { Config.animation.idle_clip_file };
            if (!string.IsNullOrEmpty(Config.animation.turn_clip_file)) files.Add(Config.animation.turn_clip_file);
            foreach (var c in Config.clips) if (c.IsMixamo) files.Add(c.source_file);
            foreach (var f in files)
            {
                if (m_Clips.ContainsKey(f)) continue;
                var entry = m_Index.Find(f);
                if (entry == null) { error = $"Mixamo clip {f} is not imported (Tools > Warehouse v4 > Workers > Import Mixamo Clips)"; return false; }
                AnimationClip found = null;
                foreach (var c in Resources.LoadAll<AnimationClip>(res + "/" + entry.resource))
                    if (c != null && c.name == entry.clip_name) found = c;
                if (found == null) { error = $"Mixamo clip {f}: clip '{entry.clip_name}' not found in Resources/{res}/{entry.resource}"; return false; }
                m_Clips[f] = found;
            }
            return true;
        }

        // ---------------------------------------------------------------- what the scenario calls

        /// <summary>Seed the gesture stream of this worker for one run (variation "seeded per run and worker").</summary>
        public void SetRun(int sessionSeed, int run) => m_Rng = SeededRandom.For(sessionSeed, run, workerId);

        /// <summary>Is "Which direction?" on screen now? A requested gesture starts only while it is.</summary>
        public void SetQuestionVisible(bool visible) => m_Scheduler.SetQuestionVisible(visible, Time.time);

        /// <summary>Queue a gesture (it starts once the question is visible). False if the worker is busy or the request is invalid.</summary>
        public bool Request(GestureRequest req, out string error)
        {
            error = null;
            if (!Ready) { error = "worker not ready: " + Problem; return false; }
            if (m_Scheduler.Phase != WorkerPhase.Idle || m_Scheduler.Pending) { error = "worker is busy"; return false; }
            if (Array.IndexOf(WorkerV4Config.AllCommands, req.Command) < 0) { error = $"command '{req.Command}' must be POINT, WAIT, STOP or PROCEED"; return false; }
            BodyFrame(out var right, out var fwd);
            float bodyAz = 0f;
            var split = new PointingSplit();
            if (req.Command == WorkerV4Config.Point)
            {
                var d = Vector3.ProjectOnPlane(req.PointDirection, Vector3.up);
                if (d.sqrMagnitude < 1e-8f) { error = "POINT needs a horizontal direction"; return false; }
                bodyAz = Vector3.SignedAngle(fwd, d, Vector3.up);
                split = PointingSplit.For(bodyAz, Config.pointing, Config.limits.point_max_body_azimuth_deg);
                m_PointDir = Quaternion.AngleAxis(split.Shown, Vector3.up) * fwd;
            }
            GestureParams p;
            try { p = GestureVariation.Draw(m_Rng, Config, req.Command, req.Clip, req.AllowedClips, req.Arm, bodyAz); }
            catch (ArgumentException e) { error = e.Message; return false; }
            if (req.HoldS > 0f) p.hold_s = req.HoldS;
            var spec = Config.Clip(p.clip);
            ClipIndexEntry entry = null;
            if (spec.IsMixamo)
            {
                entry = m_Index.Find(spec.source_file);
                if (entry == null || !(entry.peak_s > 0f) || !(entry.release_s >= entry.peak_s) || entry.arm == "") { error = $"clip {spec.source_file} has no usable raise in the clip index"; return false; }
            }
            if (!m_Scheduler.Request(GestureTiming.For(spec, entry, p), req.IgnoreQuestion)) { error = "worker is busy"; return false; }
            Current = p;
            CurrentSpec = spec;
            CurrentIsLie = req.Lie;
            m_Mixamo = spec.IsMixamo;
            m_MixamoEntry = entry;
            CurrentSplit = split;
            m_Stance = Mathf.Abs(split.Stand) > 0f;
            m_StanceRotation = Quaternion.AngleAxis(split.Stand, Vector3.up) * transform.rotation;
            m_Twisted = false;
            return true;
        }

        ClipIndexEntry m_MixamoEntry;

        /// <summary>Drop a gesture that has not started yet.</summary>
        public void CancelPending()
        {
            bool wasPending = m_Scheduler.Pending;
            m_Scheduler.Cancel();
            if (wasPending) EndStance();
        }

        void EndStance()
        {
            m_Stance = false;
            m_Twisted = false;
            CurrentSplit = new PointingSplit();
        }

        // ---------------------------------------------------------------- per frame

        void Update()
        {
            if (!Ready) return;
            float t = Time.time;
            UpdateNotice();
            WorkerPhase before = m_Scheduler.Phase;
            if (m_Scheduler.Tick(t)) OnPhase(before, m_Scheduler.Phase);
            UpdateTurn();
            // held still (docs/look_check_v4.md): no idle motion under the held arm; natural motion in the other phases
            Animator.speed = m_Scheduler.Phase == WorkerPhase.Holding ? Config.animation.hold_body_speed : 1f;
            m_IkWeight = WorkerPhases.Performing(m_Scheduler.Phase) ? m_Scheduler.Weight(t, CurrentSpec.ease) : 0f;
            UpdateGestureLayer(t);
            ComputeTargets(t);
            float lookWant = Noticed ? Config.behaviour.look_at.weight : 0f;
            m_LookWeight = Mathf.MoveTowards(m_LookWeight, lookWant, Time.deltaTime / Config.behaviour.look_at.fade_s);
        }

        void UpdateNotice()
        {
            if (robot == null) { Noticed = false; return; }
            float d = Horizontal(robot.position - transform.position).magnitude;
            float range = Config.behaviour.notice_distance_m;
            if (!Noticed && d <= range) Noticed = true;
            else if (Noticed && d > range + 1f) Noticed = false;     // 1 m hysteresis
        }

        void UpdateTurn()
        {
            if (m_Stance)
            {
                // option A: turn in place to the stance (a fixed root rotation, so the torso turn cannot pull it back)
                float left = Quaternion.Angle(transform.rotation, m_StanceRotation);
                Turning = left > 0.5f;
                if (Turning) transform.rotation = Quaternion.RotateTowards(transform.rotation, m_StanceRotation, Config.behaviour.turn_speed_deg_per_s * Time.deltaTime);
                Animator.SetBool(ParamTurning, Turning);
                return;
            }
            bool canTurn = facesRobot && Noticed && robot != null && (m_Scheduler.Phase == WorkerPhase.Idle || m_Scheduler.Phase == WorkerPhase.StartDelay);
            float err = 0f;
            if (canTurn)
            {
                BodyFrame(out _, out var fwd);
                var to = Horizontal(robot.position - transform.position);
                if (to.sqrMagnitude > 1e-6f) err = Vector3.SignedAngle(fwd, to, Vector3.up);
            }
            var b = Config.behaviour;
            if (!canTurn || Mathf.Abs(err) <= b.face_tolerance_deg) Turning = false;
            else if (Mathf.Abs(err) >= b.turn_start_deg) Turning = true;
            if (Turning)
            {
                float step = Mathf.Clamp(err, -b.turn_speed_deg_per_s * Time.deltaTime, b.turn_speed_deg_per_s * Time.deltaTime);
                transform.rotation = Quaternion.AngleAxis(step, Vector3.up) * transform.rotation;
            }
            Animator.SetBool(ParamTurning, Turning);
        }

        void OnPhase(WorkerPhase before, WorkerPhase now)
        {
            if (now == WorkerPhase.Idle) EndStance();         // the gesture has returned: face the robot again
            if (!m_Mixamo) return;
            string state = GestureStatePrefix + CurrentSpec.name;
            var e = m_MixamoEntry;
            if (now == WorkerPhase.Gesturing)
            {
                Animator.SetBool(ParamMirror, Current.arm != e.arm);
                Animator.SetFloat(ParamGestureSpeed, Current.speed);
                Animator.Play(state, GestureLayer, 0f);
            }
            else if (now == WorkerPhase.Holding) Animator.SetFloat(ParamGestureSpeed, 0f);
            else if (now == WorkerPhase.Returning)
            {
                Animator.SetFloat(ParamGestureSpeed, Current.speed);
                Animator.Play(state, GestureLayer, e.length_s > 0f ? Mathf.Clamp01(e.release_s / e.length_s) : 1f);
            }
        }

        void UpdateGestureLayer(float t)
        {
            float want = 0f;
            if (m_Mixamo && WorkerPhases.Performing(m_Scheduler.Phase))
            {
                float fade = Config.animation.gesture_layer_fade_s;
                want = 1f;
                if (m_Scheduler.Phase == WorkerPhase.Gesturing) want = Mathf.Clamp01(m_Scheduler.Elapsed(t) / fade);
                if (m_Scheduler.Phase == WorkerPhase.Returning)
                    want = Mathf.Clamp01((m_Scheduler.Timing.Return - m_Scheduler.Elapsed(t)) / fade);
            }
            m_LayerWeight = want;
            Animator.SetLayerWeight(GestureLayer, m_LayerWeight);
        }

        /// <summary>IK target and elbow hint of the gesturing hand (world), from the current shoulder and body frame.</summary>
        void ComputeTargets(float t)
        {
            if (!WorkerPhases.Performing(m_Scheduler.Phase)) return;
            var arm = Current.arm == "right" ? m_Right : m_Left;
            BodyFrame(out var right, out var fwd);
            // after a torso turn the bones hold the turned pose; the IK runs on the Animator's (unturned) one
            Vector3 side = arm.IsRight ? right : -right, up = Vector3.up, s = m_Twisted ? m_AnimShoulder : arm.Upper.position;
            float L = ArmLength, k = Current.size;
            var spec = CurrentSpec;
            var lim = Config.limits;
            switch (spec.command)
            {
                case WorkerV4Config.Point:
                {
                    float el = Current.point_elevation_deg * k;
                    Vector3 d = (Mathf.Cos(el * Mathf.Deg2Rad) * m_PointDir.normalized + Mathf.Sin(el * Mathf.Deg2Rad) * up).normalized;
                    float reach = Mathf.Clamp(spec.reach, lim.point_reach[0], lim.point_reach[1]);
                    m_Target = s + d * (L * reach);
                    m_Hint = s + d * (0.5f * L) - up * (spec.elbow_down_l * L);
                    ShownPointDirection = m_PointDir;
                    break;
                }
                case WorkerV4Config.Proceed:
                {
                    // PROCEED (upgrade_design.md section 2): the elbow bent below the shoulder, the forearm swinging forward and
                    // up between swing_low_deg and swing_high_deg (the size draw scales the top) at swing_hz while held;
                    // raising and returning bring the forearm to the bottom of the swing (the IK weight blends it in and out).
                    float Lu = 0.53f * L, Lf = 0.47f * L;            // upper arm and forearm shares of the shoulder-to-wrist length
                    float au = spec.upper_forward_deg * Mathf.Deg2Rad;
                    Vector3 elbow = s + Lu * (Mathf.Cos(au) * -up + Mathf.Sin(au) * fwd) + side * (0.08f * L);
                    float lo = spec.swing_low_deg, hi = lo + (spec.swing_high_deg - spec.swing_low_deg) * k;
                    float phi = lo;
                    if (m_Scheduler.Phase == WorkerPhase.Holding)
                        phi = lo + (hi - lo) * 0.5f * (1f - Mathf.Cos(2f * Mathf.PI * Current.swing_hz * m_Scheduler.Elapsed(t)));
                    float pr = phi * Mathf.Deg2Rad;
                    m_Target = elbow + (Mathf.Cos(pr) * fwd + Mathf.Sin(pr) * up) * Lf;
                    m_Hint = elbow + side * (0.1f * L) - up * (0.02f * L);
                    break;
                }
                case WorkerV4Config.Wait:
                {
                    float upL = Mathf.Max(spec.hand_up_l * k, lim.wait_min_up_l);
                    m_Target = s + L * (side * (spec.hand_side_l * k) + fwd * (spec.hand_forward_l * k) + up * upL);
                    m_Hint = m_Target - up * (0.5f * L) + side * (spec.elbow_down_l * L);   // forearm vertical, elbow out
                    break;
                }
                default:
                {
                    float az = spec.azimuth_out_deg * Mathf.Deg2Rad, el = spec.elevation_deg * Mathf.Deg2Rad;
                    Vector3 h = Mathf.Cos(az) * fwd + Mathf.Sin(az) * side;
                    Vector3 d = (Mathf.Cos(el) * h + Mathf.Sin(el) * up).normalized;
                    float reach = Mathf.Clamp(spec.reach * k, lim.stop_reach[0], lim.stop_reach[1]);
                    float push = 0f;
                    if (spec.push_l > 0f)
                    {
                        // the last 35 per cent of the raise pushes the palm toward the robot; it stays there
                        float u = m_Scheduler.Phase == WorkerPhase.Gesturing ? Mathf.Clamp01((m_Scheduler.Progress(t) - 0.65f) / 0.35f) : 1f;
                        push = spec.push_l * k * GestureVariation.Ease(WorkerV4Config.EaseSmooth, u) * L;
                    }
                    m_Target = s + d * (L * reach) + fwd * push;
                    m_Hint = s + d * (0.5f * L) - up * (spec.elbow_down_l * L) + side * (0.05f * L);
                    break;
                }
            }
            var sway = GestureVariation.Sway(Current, t, m_IkWeight);      // the hold's own amplitude while held
            m_Target += side * sway.x + up * sway.y + fwd * sway.z;
        }

        /// <summary>Called by WorkerIkRelay from OnAnimatorIK of the look's Animator.</summary>
        internal void OnIK(int layer)
        {
            if (!Ready) return;
            if (layer == BaseLayer)
            {
                var la = Config.behaviour.look_at;
                Animator.SetLookAtWeight(m_LookWeight, la.body, la.head, la.eyes, la.clamp);
                var eye = robotEye != null ? robotEye : robot;
                if (eye != null) Animator.SetLookAtPosition(eye.position);
            }
            bool mine = (layer == BaseLayer && !m_Mixamo) || (layer == GestureLayer && m_Mixamo);
            if (!mine || !WorkerPhases.Performing(m_Scheduler.Phase)) return;
            bool r = Current.arm == "right";
            var goal = r ? AvatarIKGoal.RightHand : AvatarIKGoal.LeftHand;
            var hint = r ? AvatarIKHint.RightElbow : AvatarIKHint.LeftElbow;
            Animator.SetIKPositionWeight(goal, m_IkWeight);
            Animator.SetIKPosition(goal, m_Target);
            Animator.SetIKRotationWeight(goal, 0f);
            Animator.SetIKHintPositionWeight(hint, m_IkWeight);
            Animator.SetIKHintPosition(hint, m_Hint);
            HandIkCalls++;
        }

        /// <summary>After the Animator: the gesturing hand's orientation and finger shape, blended in by the IK weight.</summary>
        void LateUpdate()
        {
            m_Twisted = false;
            if (!Ready || !WorkerPhases.Performing(m_Scheduler.Phase) || m_IkWeight <= 0f) return;
            bool r = Current.arm == "right";
            var arm = r ? m_Right : m_Left;
            var bind = r ? m_BindRight : m_BindLeft;
            if (CurrentSpec.command == WorkerV4Config.Point && Mathf.Abs(CurrentSplit.Torso) > 0f) TurnTorso(arm, CurrentSplit.Torso * m_IkWeight);
            HandToTargetM = Vector3.Distance(arm.Hand.position, m_Target);
            var shape = Config.hand_shapes.For(CurrentSpec.command);
            Vector3 fingerDir, palm;
            if (CurrentSpec.command == WorkerV4Config.Proceed)
            {
                // fingers along the forearm, together; the palm toward the body (up when the forearm is level, toward the
                // chest when it is raised): never an open palm to the robot
                fingerDir = (arm.Hand.position - arm.Lower.position).normalized;
                BodyFrame(out var rr, out _);
                palm = Vector3.Cross(fingerDir, rr);
                if (palm.sqrMagnitude < 1e-6f) palm = Vector3.up;
            }
            else if (CurrentSpec.command == WorkerV4Config.Point)
            {
                fingerDir = (arm.Hand.position - arm.Lower.position).normalized;      // a straight wrist
                palm = Vector3.ProjectOnPlane(Vector3.down, fingerDir);
                if (palm.sqrMagnitude < 1e-4f) { BodyFrame(out var rr, out _); palm = r ? -rr : rr; }
            }
            else
            {
                fingerDir = Vector3.up;                                                // fingers up, palm toward the robot
                var eye = robotEye != null ? robotEye : robot;
                palm = eye != null ? Horizontal(eye.position - arm.Hand.position) : transform.forward;
                if (palm.sqrMagnitude < 1e-6f) palm = transform.forward;
            }
            HandShaper.Apply(arm, bind, shape, fingerDir, palm.normalized, m_IkWeight);
        }

        /// <summary>Option A torso turn (after the Animator): the spine bones share the yaw; the gesturing arm keeps its
        /// world orientation (so it still points exactly where the IK aimed it) and the neck and head keep theirs (the
        /// head stays on the robot, as the look-at left it).</summary>
        void TurnTorso(LookPoser.Arm arm, float yawDeg)
        {
            m_AnimShoulder = arm.Upper.position;
            Quaternion upper = arm.Upper.rotation, head = m_Head.rotation;
            Quaternion neck = m_Neck != null ? m_Neck.rotation : Quaternion.identity;
            var step = Quaternion.AngleAxis(yawDeg / m_Spine.Length, Vector3.up);
            foreach (var b in m_Spine) b.rotation = step * b.rotation;     // each child already carries its parents' share
            if (m_Neck != null) m_Neck.rotation = neck;
            m_Head.rotation = head;
            arm.Upper.rotation = upper;
            m_Twisted = true;
        }

        // ---------------------------------------------------------------- truth (files only, never the bridge)

        /// <summary>This worker's truth.jsonl row at time t (docs/protocol_v3.md), relative to the robot's forward axis.</summary>
        public TruthRow Truth(double t)
        {
            var phase = m_Scheduler.Phase;
            bool performing = WorkerPhases.Performing(phase);
            string cmd = performing ? Current.command : WorkerV4Config.None;
            var row = new TruthRow
            {
                TimeS = t, WorkerId = workerId, Look = lookId, X = transform.position.x, Z = transform.position.z,
                TrueCommand = cmd, PointAngleDeg = -1.0, Arm = performing ? Current.arm : "none",
                Phase = WorkerPhases.Name(phase), IsCommander = IsCommander, Clip = performing ? Current.clip : "",
            };
            double ankle = AnkleHeight();
            if (!double.IsNaN(ankle)) { row.HasAnkle = true; row.AnkleHeightM = ankle; }
            if (performing && cmd == WorkerV4Config.Point && robot != null) row.PointAngleDeg = Math.Round(TruthFormat.PointAngle(robot.forward, ShownPointDirection), 2);
            if (ReportTruthful) { row.HasTruthful = true; row.GestureTruthful = !(performing && CurrentIsLie); }
            if (ReportActive) { row.HasActive = true; row.Active = gameObject.activeInHierarchy; }
            if (performing)
            {
                row.HasParams = true;
                row.Speed = Current.speed; row.Size = Current.size; row.StartDelayS = Current.start_delay_s; row.HoldS = Current.hold_s;
            }
            return row;
        }

        /// <summary>Truth ankle_height_m (P1): the mean height of the two ankle (Humanoid foot) bones above the worker's root,
        /// which stands on the floor; NaN when a bone is missing (the field is then left out).</summary>
        public double AnkleHeight()
        {
            if (m_LeftFoot == null || m_RightFoot == null) return double.NaN;
            double h = 0.5 * (m_LeftFoot.position.y + m_RightFoot.position.y) - transform.position.y;
            return Math.Round(Math.Max(0.0, h), 4);
        }

        // ---------------------------------------------------------------- geometry

        /// <summary>Worker's right (level, unit) and forward (right x up), from the two upper-arm bones (rig-independent).</summary>
        public void BodyFrame(out Vector3 right, out Vector3 forward)
        {
            right = m_Right != null && m_Left != null ? Horizontal(m_Right.Upper.position - m_Left.Upper.position) : transform.right;
            if (right.sqrMagnitude < 1e-8f) right = transform.right;
            right.Normalize();
            forward = Vector3.Cross(right, Vector3.up).normalized;
        }

        /// <summary>Diagnostics: the shoulder and hand of the gesturing arm (world). False when no gesture was requested yet.</summary>
        public bool GestureArmPositions(out Vector3 shoulder, out Vector3 hand)
        {
            var arm = Current.arm == "right" ? m_Right : Current.arm == "left" ? m_Left : null;
            shoulder = arm != null ? arm.Upper.position : Vector3.zero;
            hand = arm != null ? arm.Hand.position : Vector3.zero;
            return arm != null;
        }

        static Vector3 Horizontal(Vector3 v) => Vector3.ProjectOnPlane(v, Vector3.up);

        string Ancestor(Transform t)
        {
            while (t.parent != null && t.parent != LookInstance.transform) t = t.parent;
            return t.name;
        }

        /// <summary>One line of diagnostics: phase, weights, the gesture layer's state and the hand against its IK target.</summary>
        public string DebugState()
        {
            if (!Ready) return "not ready: " + Problem;
            var arm = Current.arm == "right" ? m_Right : m_Left;
            var st = Animator.GetCurrentAnimatorStateInfo(GestureLayer);
            string state = CurrentSpec != null && st.IsName(GestureStatePrefix + CurrentSpec.name) ? GestureStatePrefix + CurrentSpec.name : st.shortNameHash.ToString();
            return $"phase {Phase} ik {m_IkWeight:0.00} layer1 {Animator.GetLayerWeight(GestureLayer):0.00} state {state} t {st.normalizedTime:0.00} " +
                   $"arm {Current.arm} hand {(arm != null ? arm.Hand.position.ToString("F3") : "-")} target {m_Target.ToString("F3")} " +
                   $"err {HandToTargetM:0.000} ikcalls {HandIkCalls} animator {Animator.name} enabled {Animator.enabled} active {Animator.gameObject.activeInHierarchy} " +
                   $"controller {Animator.runtimeAnimatorController?.name} handBoneUnder {HandOwner(arm)} " +
                   $"animatorHand {AnimatorHandId()} heldHand {(arm != null ? arm.Hand.GetInstanceID() : 0)} armLength {ArmLength:0.000}";
        }

        string HandOwner(LookPoser.Arm arm) => arm != null ? Ancestor(arm.Hand) : "-";

        int AnimatorHandId()
        {
            var h = Animator.GetBoneTransform(Current.arm == "right" ? HumanBodyBones.RightHand : HumanBodyBones.LeftHand);
            return h != null ? h.GetInstanceID() : 0;
        }

        void OnDrawGizmos()
        {
            Gizmos.color = IsCommander ? new Color(1f, 0.6f, 0f) : new Color(0.2f, 0.7f, 1f);
            Gizmos.DrawWireCube(transform.position + Vector3.up * 0.9f, new Vector3(0.5f, 1.8f, 0.3f));
            Gizmos.DrawLine(transform.position + Vector3.up * 1.5f, transform.position + Vector3.up * 1.5f + transform.forward * 0.5f);
        }
    }
}
