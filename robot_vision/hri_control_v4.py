"""v4 state machine (docs/project_flow_v4.md): the v3 controller (hri_control.py, unchanged) with the v4 dialog.

States are those of v3: IDLE -> NAVIGATE -> (junction) SCAN -> APPROACH -> ASK -> READ -> EXECUTE ... DONE / ABORTED. What
changes is how READ works and what the command carries (vertical_fov_deg, HUD fields):

- Input per tick (TickInputV4): the people of the 360 camera as in v3, plus PersonReading objects for the people the
  pan-tilt camera sees (commander_v4.py: window reading of gesture_motion.py, facing, bearing) and the rendered field of
  view of the last pan-tilt frame.
- The commander is chosen among them every new frame (commander_v4.pick_commander; the previous one is kept while
  still gesturing; none or a tie = NONE). The pan-tilt camera is aimed at the commander.
- POINT -> the pointed world direction (two candidates: the arm pointing away from / toward the camera, from
  gesture_motion) is resolved with the roadmap (resolve_point): each candidate goes to the nearest of the junction's
  branches and the ARRIVAL direction; a candidate nearest to the arrival direction is dropped (the branch the robot came
  from is never an answer), one farther than branch_match_max_deg from its branch is dropped; exactly one distinct branch
  left = the answer, none or two = unclear (ask again, then abort, as in v3). The answer goes through the v3
  GestureDialog (hold, a different branch restarts it).
- WAIT (read for wait_hold_s) -> the robot holds position and keeps watching the same commander ('wait' mode of the READ
  state, shown as state 'wait'); a POINT that resolves and holds ends it, wait_timeout_s (20 s) without one counts as an
  unclear ask (ask again from a new viewpoint, then abort).
- STOP of anybody the pan-tilt camera sees stops the robot at once (the v3 safety rule, via TickInput.gesture), also
  while navigating; it resumes when the open palm is gone.
- Zoom (ZoomController): after the commander is picked the field of view narrows until the hand fills hand_share of the
  image height (never narrower than the arm fits with arm_fit_margin), widens in steps when the hand is lost, clamped to
  [fov_min_deg, fov_max_deg]; a config switch turns it off (vertical_fov_deg = -1).

Added 2026-11-12 (Nusrat during Anisha's absence; Avatar/Config/upgrade_design.md; AUDIT.md section 15):
- P7 map: the v4 roadmap is configs/v4/roadmap.json (named by control.json -> roadmap); the v3 configs/roadmap.json is unchanged.
- P8 start search: the start node has kind 'start' and asks like a junction: the robot starts in SCAN at A, approaches the
  person, asks, and drives only after an accepted instruction. Its arrival direction is its start heading
  (roadmap start_yaw_deg), so PROCEED there means the FORWARD branch.
- P2 PROCEED (reader command): the branch straight ahead of the arrival direction, i.e. the node's FORWARD branch (dialog
  label FORWARD, through the same hold); no FORWARD branch here = unclear. A PROCEED reading also marks a gesture onset.
- P6 tilt: the zoom rule also tilts the pan-tilt camera up so the fit box (nose, shoulders, hips, the active arm) is centred
  vertically, and narrows the view so the hand fills hand_share without losing the fit box; command tilt_deg (-1 = level).
- P3/P8 record: every ask logs the 360 distance estimate of the approached person (record['asks_log']).

Added 2026-11-13 (AUDIT.md section 16, experiments A and B; every switch in control.json -> lie_detection, default false = all of
the above unchanged): three ways to find out that a worker pointed a wrong direction, from evidence only, never from goal B:
- second_opinion: at a node with 2+ people ask a second person after the first answer; on disagreement a third and follow the
  majority (two people who disagree and nobody else: ask the first again, the first counts twice; no majority = abort);
- reject_impossible: an answer that is the arrival road, no branch of the node, or a dead end is rejected with a reason and the
  question is asked again at once;
- backtrack: when every answer at a junction was rejected, drive back to the last decision junction and take its other branch
  (the one untried branch directly; with two untried ask again with the failed one excluded); once per junction, one level.
Every decision is logged with its reason (summary()["v4"]["decisions"]), also with the switches off.

Everything v3 does (drive, safety, scan, approach, execute, reposition) is inherited unchanged. Pure Python, no I/O.
"""

from __future__ import annotations

import math
from collections import Counter
from dataclasses import dataclass, field, replace

import commander_v4 as cm
import gesture_motion as gm
import hri_control as hc

DIRECTIONS = hc.DIRECTIONS
LIE_DEFAULTS = {"second_opinion": False, "reject_impossible": False, "backtrack": False, "max_opinions": 3, "second_opinion_radius_m": None,
                "backtrack_scope": "any",          # AUDIT.md 16.22: "disagreed" = backtrack only to a junction where the accepted answers named more than one branch
                "checkpoint": False, "checkpoint_fraction": 0.5,   # AUDIT.md 16.23 (T3): stop at this fraction of a branch leaving a decision junction and ask the checkpoint worker
                "checkpoint_scope": "any",                         # AUDIT.md 16.24 (T4): "disputed" = a checkpoint pointing back counts only when the junction's answers disagreed (a vote, not a veto)
                "checkpoint_person_radius_m": 5.0,                 # AUDIT.md 16.25: only a person within this distance of the checkpoint spot (and nearest to it, outside every junction zone) is asked there
                "checkpoint_branches": None,                       # AUDIT.md 16.25.1: the branches ("J1>LEFT") that have a checkpoint worker; None = every branch leaving a decision junction (T4 of 16.25.0.1)
                "checkpoint_s_m": None,                            # AUDIT.md 16.26 item 1: {"J1>FORWARD": 15.5, ...} the spot of a branch = this far along it from the junction (the point abeam the worker); None / absent entry = checkpoint_fraction
                "next_junction_back": False}                       # AUDIT.md 16.25.1: after a disputed junction, a BACK answer at the next junction (reached by a branch without a checkpoint worker) is a vote to go back
# AUDIT.md 16.19.2 item E: person-in-path recovery (v4 only; the v3 stop itself is unchanged). Absent block or enabled false = the v3 behaviour.
RECOVERY_DEFAULTS = {"enabled": False, "blocked_s": 15.0, "person_moved_max_m": 0.3, "back_m": 1.0, "back_speed_mps": 0.2,
                     "side_m": 1.0, "beyond_m": 1.0, "max_attempts": 2}
# AUDIT.md 16.26 item 2 (4a side view): a raised arm that fails the POINT cue on length or elbow angle is read again from a point rotated around the worker at the ask distance.
# Absent block or enabled false = no side view (every earlier behaviour).
SIDE_VIEW_DEFAULTS = {"enabled": False, "rotation_min_deg": 60.0, "rotation_max_deg": 90.0, "waypoint_step_deg": 30.0, "keep_m": None}
V4_ROADMAP = "configs/v4/roadmap.json"
START = "start"                          # roadmap kind of the start node in the v4 map (it asks, P8)


def arrival_yaw(road: hc.Roadmap, node: str) -> float | None:
    """World yaw of the direction the robot arrived from, seen from the node (junction -> arrive_from); at the start node
    the opposite of the start heading (roadmap start_yaw_deg); None if neither is known."""
    n = road.nodes[node]
    if n.get("arrive_from"):
        return hc.yaw_to(*road.pos(node), *road.pos(n["arrive_from"]))
    if "start_yaw_deg" in n:
        return hc.wrap(n["start_yaw_deg"] + 180.0)
    return None


def heading_in(road: hc.Roadmap, node: str) -> float | None:
    """World yaw of the arrival direction itself (the robot's heading when it reaches the node)."""
    a = arrival_yaw(road, node)
    return None if a is None else hc.wrap(a + 180.0)


def stand(road: hc.Roadmap, node: str) -> tuple[float, float, float]:
    """Worker stand (x, z, facing yaw) of a node: corner_offset_m ahead and to the right of the arrival direction (the
    roadmap rule; at the start node the start heading). SCENARIO side only (simulator, tests)."""
    if road.nodes[node].get("arrive_from"):
        return road.stand(node)
    a = math.radians(heading_in(road, node))
    off = road.cfg["worker_stand"]["corner_offset_m"]
    fx, fz = math.sin(a), math.cos(a)
    nx, nz = road.pos(node)
    return nx + (fx + fz) * off, nz + (fz - fx) * off, hc.wrap(math.degrees(a) + 180.0)


def check_labels_v4(road: hc.Roadmap) -> list[str]:
    """Roadmap.check_labels plus the start node's branches against its start heading."""
    bad = road.check_labels()
    for j, br in road.branches.items():
        n = road.nodes[j]
        if n.get("arrive_from") or "start_yaw_deg" not in n:
            continue
        for cmd, nxt in br.items():
            if hc.turn_command(hc.yaw_to(*road.pos(j), *road.pos(nxt)) - n["start_yaw_deg"]) != cmd:
                bad.append(f"{j} {cmd} -> {nxt}")
    return bad


def proceed_branch(road: hc.Roadmap, node: str) -> str | None:
    """The branch command PROCEED stands for at this node: FORWARD if the node has one, else None (unclear)."""
    return "FORWARD" if road.next(node, "FORWARD") is not None else None


# ---------------------------------------------------------------- resolving a pointed direction with the roadmap

@dataclass
class Resolution:
    command: str | None                  # a branch command (LEFT / FORWARD / RIGHT ...) or None
    why: str
    candidates: list = field(default_factory=list)   # per family: {family, world_deg, target, gap_deg, verdict}
    ambiguous: bool = False
    used_crosscheck: bool = False
    rel_deg: float | None = None         # the chosen candidate's direction relative to the robot's forward axis
    gap_deg: float | None = None
    views: int = 1                       # 2 when the answer rests on two viewpoints

    def to_dict(self) -> dict:
        return {"command": self.command, "why": self.why, "ambiguous": self.ambiguous, "views": self.views,
                "used_crosscheck": self.used_crosscheck, "rel_deg": self.rel_deg, "gap_deg": self.gap_deg,
                "candidates": self.candidates}


def branch_directions(road: hc.Roadmap, junction: str) -> tuple[dict, float | None]:
    """({command: world yaw of the branch}, world yaw of the arrival direction junction -> arrive_from)."""
    jx, jz = road.pos(junction)
    dirs = {cmd: hc.yaw_to(jx, jz, *road.pos(nxt)) for cmd, nxt in road.branches.get(junction, {}).items()}
    return dirs, arrival_yaw(road, junction)


def resolve_point(point, branch_yaws: dict, arrival_yaw: float | None, robot_yaw: float, max_gap_deg: float,
                  use_crosscheck: bool = False, arrival_mirror_ambiguous: bool = False) -> Resolution:
    """Resolve the pointed direction candidates (point.world_deg: {'away': yaw | None, 'toward': yaw | None}) to a branch.
    Each candidate goes to the nearest of the valid branches and the arrival direction. Arrival = dropped; beyond
    max_gap_deg from its branch = dropped; one distinct branch left = the answer; none = unclear; two = ambiguous
    (unclear), unless use_crosscheck and the MediaPipe hand cross-check prefers one of them.
    arrival_mirror_ambiguous (AUDIT.md 16.11, decided 2026-11-13; set by the reject_impossible switch): one distinct branch left, but the
    OTHER depth reading was dropped because it is the arrival road, is ambiguous too: the two readings are mirror images, so a worker who
    points back along the arrival road can be read as the branch his mirror image lands on. The existing second view then decides."""
    cands, kept = [], {}
    for fam in ("away", "toward"):
        w = point.world_deg.get(fam)
        if w is None:
            continue
        targets = [(abs(gm.wrap(w - y)), c) for c, y in branch_yaws.items()]
        if arrival_yaw is not None:
            targets.append((abs(gm.wrap(w - arrival_yaw)), "ARRIVAL"))
        gap, target = min(targets)
        row = {"family": fam, "world_deg": round(w, 2), "target": target, "gap_deg": round(gap, 2)}
        if target == "ARRIVAL":
            row["verdict"] = "dropped: nearest is the direction the robot came from"
        elif gap > max_gap_deg:
            row["verdict"] = f"dropped: {gap:.0f} deg from {target}, more than {max_gap_deg:g}"
        else:
            row["verdict"] = "ok"
            if target not in kept or gap < kept[target][0]:
                kept[target] = (gap, fam, w)
        cands.append(row)
    if not kept:
        return Resolution(None, "no candidate within reach of a valid branch" if cands else "no pointed direction", cands)
    if len(kept) == 1:
        if arrival_mirror_ambiguous and any(c["target"] == "ARRIVAL" for c in cands):
            return Resolution(None, "ambiguous: one of the two readings is the arrival road", cands, True)
        (cmd, (gap, fam, w)), = kept.items()
        return Resolution(cmd, "ok", cands, rel_deg=round(gm.wrap(w - robot_yaw), 2), gap_deg=round(gap, 2))
    pref = point.crosscheck.get("prefers") if use_crosscheck else None
    for cmd, (gap, fam, w) in kept.items():
        if pref == fam:
            return Resolution(cmd, "two branches; the hand cross-check chose one", cands, True, True,
                              round(gm.wrap(w - robot_yaw), 2), round(gap, 2))
    return Resolution(None, "ambiguous: the candidates fit two different branches", cands, True)


def resolve_two_views(view1: dict, cands2: dict, branch_yaws: dict, arrival_yaw: float | None, robot_yaw: float,
                      max_gap_deg: float, tol_deg: float, arrival_mirror_ambiguous: bool = False) -> Resolution:
    """Two-view POINT disambiguation. view1 / cands2: {'away': world yaw | None, 'toward': ...} of the first and the
    second viewpoint. The two depth readings of one view are mirror images about that view's image plane, so after the
    robot has moved only the TRUE direction stays put: a pair (one candidate per view) agrees when the two world yaws
    differ by at most tol_deg. The agreeing pairs (their circular means) are resolved with the roadmap as in
    resolve_point; no agreeing pair = unclear."""
    pairs, seen = [], set()
    for w1 in view1.values():
        for w2 in cands2.values():
            if w1 is None or w2 is None or abs(gm.wrap(w1 - w2)) > tol_deg:
                continue
            key = (round(w1, 3), round(w2, 3))
            if key not in seen:
                seen.add(key)
                pairs.append(gm.circular_mean([w1, w2]))
    if not pairs:
        return Resolution(None, "the two views do not agree on any direction", [], False, views=2)
    pseudo = type("P", (), {})()
    pseudo.world_deg = {"away": pairs[0], "toward": pairs[1] if len(pairs) > 1 else None}
    pseudo.crosscheck = {}
    res = resolve_point(pseudo, branch_yaws, arrival_yaw, robot_yaw, max_gap_deg, False, arrival_mirror_ambiguous)
    res.views = 2
    if res.command is None and res.ambiguous:
        res.why = ("two views: the agreeing candidates still fit two branches" if "arrival" not in res.why
                   else "two views: an agreeing candidate still has the arrival road as its mirror image")
    return res


# ---------------------------------------------------------------- zoom

def zoom_target(hand_box, arm_box, frame_wh, cur_fov_deg: float, z: dict) -> float:
    """Vertical field of view (deg) at which the hand box fills hand_share of the image height, but not narrower than
    keeps the arm box (shoulder, elbow, wrist) inside the image with arm_fit_margin on every side; clamped."""
    w, h = frame_wh
    tan_c = math.tan(math.radians(cur_fov_deg) / 2.0)
    hand_h = (hand_box[3] - hand_box[1]) / h
    fov_hand = 2.0 * math.degrees(math.atan(tan_c * hand_h / z["hand_share"])) if hand_h > 1e-6 else z["fov_min_deg"]
    need = max((arm_box[2] - arm_box[0]) / w, (arm_box[3] - arm_box[1]) / h) / max(1.0 - 2.0 * z["arm_fit_margin"], 1e-3)
    fov_fit = 2.0 * math.degrees(math.atan(tan_c * need))
    return min(z["fov_max_deg"], max(z["fov_min_deg"], max(fov_hand, fov_fit)))


def tilt_target(box, frame_wh, cur_fov_deg: float, cur_tilt_deg: float) -> float:
    """Tilt (deg, + = up) that puts the vertical centre of box at the image centre: the current tilt plus the elevation of
    the box centre row in the current view (pinhole, fy from the field of view)."""
    w, h = frame_wh
    fy = (h / 2.0) / math.tan(math.radians(cur_fov_deg) / 2.0)
    vc = 0.5 * (box[1] + box[3])
    return cur_tilt_deg + math.degrees(math.atan((h / 2.0 - vc) / fy))


def hand_centred(hand_box, frame_wh, margin: float) -> bool:
    w, h = frame_wh
    cx, cy = (hand_box[0] + hand_box[2]) / 2.0 / w, (hand_box[1] + hand_box[3]) / 2.0 / h
    return margin <= cx <= 1.0 - margin and margin <= cy <= 1.0 - margin


class ZoomController:
    """The zoom rule. update() returns the vertical_fov_deg to command (-1 = keep the default); the tilt to command is
    self.tilt_cmd afterwards (-1 = level, the default). The tilt part (P6) acts only when zoom.tilt_enabled is true."""

    def __init__(self, z: dict):
        self.z = z
        self.reset()

    def reset(self) -> None:
        self.fov: float | None = None          # commanded, None = default
        self.tilt: float | None = None         # commanded, None = level
        self.tilt_cmd = -1.0
        self.last_hand_t: float | None = None
        self.last_widen_t: float | None = None
        self.last_t: float | None = None

    def _update_tilt(self, reading, cur_fov: float, cur_tilt_deg: float | None, dt: float) -> None:
        z = self.z
        box = reading.fit_box if getattr(reading, "fit_box", None) is not None else reading.arm_box
        cur = cur_tilt_deg if cur_tilt_deg is not None else (self.tilt if self.tilt is not None else 0.0)
        target = min(z["tilt_max_deg"], max(z["tilt_min_deg"], tilt_target(box, reading.frame_wh, cur_fov, cur)))
        step = z["tilt_max_change_deg_per_s"] * dt
        self.tilt = cur + max(-step, min(step, target - cur)) if dt > 0 else cur

    def update(self, t: float, reading: gm.Reading | None, cur_fov_deg: float | None, active: bool,
               cur_tilt_deg: float | None = None) -> float:
        z = self.z
        if not z["enabled"] or not active:
            self.reset()
            return -1.0
        dt = 0.0 if self.last_t is None else max(0.0, t - self.last_t)
        self.last_t = t
        cur = cur_fov_deg if cur_fov_deg is not None else (self.fov if self.fov is not None else z["fov_default_deg"])
        tilting = bool(z.get("tilt_enabled", False))
        if tilting and reading is not None and reading.frame_wh is not None and (
                getattr(reading, "fit_box", None) is not None or reading.arm_box is not None):
            self._update_tilt(reading, cur, cur_tilt_deg, dt)
        self.tilt_cmd = float(min(z["tilt_max_deg"], max(z["tilt_min_deg"], self.tilt))) if tilting and self.tilt is not None else -1.0
        fit = getattr(reading, "fit_box", None) if reading is not None else None
        seen = (reading is not None and reading.hand_box is not None and reading.arm_box is not None
                and reading.frame_wh is not None and hand_centred(reading.hand_box, reading.frame_wh, z["arm_fit_margin"]))
        if seen:
            self.last_hand_t = t
            target = zoom_target(reading.hand_box, fit if tilting and fit is not None else reading.arm_box,
                                 reading.frame_wh, cur, z)
            step = z["max_change_deg_per_s"] * dt
            self.fov = cur + max(-step, min(step, target - cur)) if dt > 0 else cur
        elif self.last_hand_t is not None:
            last = max(self.last_hand_t, self.last_widen_t if self.last_widen_t is not None else self.last_hand_t)
            if t - last >= z["hand_lost_s"] - 1e-9:                             # lost: widen one step per hand_lost_s
                self.fov = min(z["fov_max_deg"], cur + z["widen_step_deg"])
                self.last_widen_t = t
            elif self.fov is None:
                return -1.0
        elif self.fov is None:
            return -1.0
        return float(min(z["fov_max_deg"], max(z["fov_min_deg"], self.fov))) if self.fov is not None else -1.0


# ---------------------------------------------------------------- controller

@dataclass
class TickInputV4(hc.TickInput):
    persons: list = field(default_factory=list)           # commander_v4.PersonReading of the pan-tilt camera's people
    persons_time_s: float | None = None                   # capture time of that pan-tilt frame
    fov_deg: float | None = None                          # vertical field of view rendered in that frame
    pan_deg: float = 0.0                                  # pan of that frame (+ = left)
    tilt_deg: float | None = None                         # tilt of that frame (+ = up; P6)


@dataclass
class CommandV4(hc.Command):
    vertical_fov_deg: float = -1.0
    tilt_deg: float = -1.0                                # P6: -1 = level (the default)
    hud: dict = field(default_factory=dict)               # commander / gesture fields for the HUD (guide_v4 adds the rest)


def load_control(path="configs/v4/control.json") -> tuple[dict, dict]:
    """(the v3 control config with the v4 dialog overrides applied, the v4 config). The v3 file is only read."""
    v4 = hc.load_json(path)
    base = hc.load_json(v4["base"])
    base["dialog"] = {**base["dialog"], **{k: v for k, v in v4["dialog"].items() if k in base["dialog"]}}
    return base, v4


class ControllerV4(hc.Controller):
    def __init__(self, base_cfg: dict, v4_cfg: dict, commander_cfg: dict, roadmap: hc.Roadmap):
        self.v4, self.ccfg = v4_cfg, commander_cfg
        self.zoom = ZoomController(v4_cfg["zoom"])
        self.ld = {**LIE_DEFAULTS, **{k: v for k, v in v4_cfg.get("lie_detection", {}).items() if k in LIE_DEFAULTS}}
        if self.ld["backtrack"] and not self.ld["reject_impossible"]:
            raise ValueError("lie_detection.backtrack needs lie_detection.reject_impossible (the rejections are its evidence)")
        if self.ld["backtrack_scope"] not in ("any", "disagreed"):
            raise ValueError(f"lie_detection.backtrack_scope must be 'any' or 'disagreed' (got {self.ld['backtrack_scope']!r})")
        if self.ld["checkpoint"]:
            if self.ld["second_opinion_radius_m"] is None:
                raise ValueError("lie_detection.checkpoint needs lie_detection.second_opinion_radius_m (the robot tells a checkpoint worker from a junction worker by it)")
            if not 0.0 < float(self.ld["checkpoint_fraction"]) < 1.0:
                raise ValueError(f"lie_detection.checkpoint_fraction must be between 0 and 1 (got {self.ld['checkpoint_fraction']!r})")
            if self.ld["checkpoint_scope"] not in ("any", "disputed"):
                raise ValueError(f"lie_detection.checkpoint_scope must be 'any' or 'disputed' (got {self.ld['checkpoint_scope']!r})")
            if not float(self.ld["checkpoint_person_radius_m"]) > 0.0:
                raise ValueError(f"lie_detection.checkpoint_person_radius_m must be above 0 (got {self.ld['checkpoint_person_radius_m']!r})")
        self.rc = {**RECOVERY_DEFAULTS, **{k: v for k, v in v4_cfg.get("recovery", {}).items() if k in RECOVERY_DEFAULTS}}
        self.sv = {**SIDE_VIEW_DEFAULTS, **{k: v for k, v in v4_cfg.get("side_view", {}).items() if k in SIDE_VIEW_DEFAULTS}}
        if not 0.0 < float(self.sv["rotation_min_deg"]) <= float(self.sv["rotation_max_deg"]) <= 180.0 or not float(self.sv["waypoint_step_deg"]) > 0.0:
            raise ValueError(f"side_view: need 0 < rotation_min_deg <= rotation_max_deg <= 180 and waypoint_step_deg > 0 (got {self.sv})")
        super().__init__(base_cfg, roadmap)
        if self.ld["checkpoint_branches"] is not None:
            # the list belongs to the deployment, not to one map: an entry for a node this map does not have is ignored (A1 and A2 run on small maps); an entry that names a
            # node of this map must be a branch of a decision junction (a typo is refused)
            valid = {f"{j}>{c}" for j, br in self.road.branches.items() if self.road.kind(j) == "junction" and len(br) >= 2 for c in br}
            bad = [b for b in self.ld["checkpoint_branches"] if ">" not in b or (b.split(">", 1)[0] in self.road.nodes and b not in valid)]
            if bad:
                raise ValueError(f"lie_detection.checkpoint_branches names branches that leave no decision junction of the map: {bad} (valid here: {sorted(valid)})")
        for key, s_m in (self.ld["checkpoint_s_m"] or {}).items():
            j, _, cmd = key.partition(">")
            nxt = self.road.next(j, cmd) if j in self.road.nodes else None
            if nxt is not None and not 0.0 < float(s_m) < math.hypot(*(a - b for a, b in zip(self.road.pos(nxt), self.road.pos(j)))):
                raise ValueError(f"lie_detection.checkpoint_s_m[{key}] = {s_m} is not inside the branch")
        rs = v4_cfg.get("dialog", {}).get("return_speed_mps")
        if rs is not None and not (0.0 < float(rs) <= self.d["cruise_speed_mps"]):
            raise ValueError(f"dialog.return_speed_mps must be above 0 and at most the cruise speed {self.d['cruise_speed_mps']} m/s (got {rs})")

    # -- bookkeeping --
    def reset(self, t):
        super().reset(t)
        self.commander_pt: int | None = None
        self.commander_360: int | None = None
        self.choice: cm.Choice | None = None
        self.waiting = False
        self.wait_since: float | None = None
        self.wait_start = 0.0
        self.waited_s = 0.0
        self.last_persons_frame: float | None = None
        self.resolution: Resolution | None = None
        self.label = "NONE"
        self.fov_cmd = -1.0
        self.commander_changes: list[dict] = []
        self.frame_log: list[dict] = []                       # one row per new pan-tilt frame read in the READ state
        self._row: dict | None = None
        self.abort_note = ""
        self.ask_serial = 0                                   # how many times the question was shown (re-asks, extra views)
        self.free_asks = 0                                    # asks that do not use up an ask (second view, re-approach)
        self.raised_since: dict[int, float] = {}              # pan-tilt person -> frame time since which the arm is raised
        self._onset_frame: float | None = None
        self._ask_logged = 0
        self.proceed_note = ""
        self.decisions: list[dict] = []                       # every decision with its reason (AUDIT.md section 16)
        self.route: list[str] = []                            # the nodes the robot arrived at, in order (backtracks included)
        self.safety_stops = 0                                 # how many times a safety stop began
        self._was_stopped = False
        self.last_choice: dict | None = None                  # the last branch taken at a decision junction (backtrack target)
        self.tried: dict[str, set] = {}                       # node -> branch commands taken there
        self.backtracked: set[str] = set()                    # junctions that used their one backtrack
        self.backtrack_target: str | None = None
        self.reject: tuple | None = None                      # (reason, detail) of the newest frame's answer, if it is impossible
        self.rej_since: float | None = None
        self.rej_key: str | None = None
        self._returned = True                                 # D: the robot is at the junction point (or needs not return to it)
        self._blk: dict | None = None                         # E: the person-in-path stop being timed
        self._rec: dict | None = None                         # E: the recovery in progress (stage "back")
        self.detour: list[tuple[float, float]] = []           # E: the waypoints the path goes through before the target
        self.rec_attempts: dict = {}                          # E: blocking person -> recoveries started
        self.recoveries = 0
        self._rec_noted: set = set()
        self.cp: dict | None = None                           # AUDIT.md 16.23: the checkpoint being driven to / asked: {junction, branch, next, point, stage}
        self.cp_done: set = set()                             # (junction, branch) whose checkpoint was handled
        self.cp_log: list[dict] = []                          # one row per checkpoint: result (proceed / back / none) and the action taken
        self.cp_backtracks = 0
        self.sv_since: float | None = None                    # AUDIT.md 16.26 item 2: since when the commander's raised arm fails the POINT cue on length / elbow (pan-tilt frame time)
        self.side_view_used = False                           # one side view per ask
        self.last_point_fail = ""                             # "length" / "elbow": why the commander's raised arm failed the POINT cue (for the log)
        self.side_views: list[dict] = []                      # the side views made (for the summary)
        self.back_ctx: dict | None = None                     # AUDIT.md 16.25.1: set at an arrival at a junction when a BACK answer counts there as a vote
        self.nj_log: list[dict] = []                          # the backtracks made on a BACK vote at the next junction
        self._new_junction()
        if hasattr(self, "zoom"):
            self.zoom.reset()

    def _new_junction(self) -> None:
        self.sv_since, self.side_view_used = None, False
        self.view1: dict | None = None                        # candidate world yaws of the first view (two-view)
        self.two_view_used = False
        self.amb_frames: list[dict] = []
        self.amb_since: float | None = None
        self.amb_why = ""
        self.approached_360: int | None = None
        self.reapproached = False
        self.commander_since: float | None = None
        self.votes: list[dict] = []                           # valid answers of this visit: {person_360, branch, serial}
        self.asked_360: set[int] = set()                      # 360 track ids already asked at this visit
        self.skipped_360: set[int] = set()                    # 360 track ids not asked because they belong to another junction (logged once)
        self.dialogs_started = 0                              # dialogs (people asked) at this visit
        self.tie_used = False                                 # the tie rule's re-ask of the first person was used
        self.rejections: list[str] = []                       # reasons of the answers rejected at this visit
        self.excluded: set[str] = set()                       # branch commands that are not an answer here (backtrack)

    def _log(self, t: float, event: str, reason: str, **detail) -> None:
        """One decision with its reason (summary()['v4']['decisions']); serial = the ask it concerns."""
        self.decisions.append({"t": round(t, 3), "node": self.node, "event": event, "reason": reason,
                               "serial": self.ask_serial, **detail})

    def _abort(self, reason, t):
        self._log(t, "abort", reason)
        super()._abort(reason, t)

    def _set(self, state: str, t: float):
        super()._set(state, t)
        if state == "execute":
            self._returned = False                            # D: not yet back at the junction point
        if state not in ("navigate", "approach", "execute"):
            self.detour = []                                  # E: a detour belongs to one drive

    def _target(self):
        if self.state == "navigate" and self.cp is not None and self.cp["stage"] == "drive":
            return self.cp["point"]                           # T3: first the checkpoint of the branch
        if self.state == "execute" and self.next_node and self._return_pending():
            return self.road.pos(self.node)                   # D: first the junction point
        if self.state == "execute" and self.next_node and self._cp_wanted(self.next_node):
            return self._cp_point(self.node, self.next_node)  # AUDIT.md 16.25.0: the next place the robot goes is the checkpoint spot (same heading), not the next node
        return super()._target()

    def _return_pending(self) -> bool:
        return bool(self.v4["dialog"].get("return_to_junction") and not self._returned and self.node in self.road.nodes)

    def _path(self, inp, tx, tz):
        base = super()._path(inp, tx, tz)
        if not self.detour:
            return base
        while self.detour and math.hypot(self.detour[0][0] - inp.x, self.detour[0][1] - inp.z) < 0.3:
            self.detour.pop(0)
        if not self.detour:
            return base
        return [(inp.x, inp.z)] + list(self.detour) + [(tx, tz)]      # E: through the waypoints, ignoring the NavMesh corners

    def _arrive(self, node, t):
        self.detour = []
        self.cp = None
        self.back_ctx = None
        self.route.append(node)
        if self.backtrack_target == node:
            self._arrive_backtrack(node, t)
            return
        if self.road.kind(node) == START:                     # P8: the start node asks like a junction
            self.node = node
            self.dialog.reset()
            self._set("scan", t)
        else:
            super()._arrive(node, t)
        if self.state == "scan":
            self._new_junction()
            self.back_ctx = self._back_context(node)

    def _navigate(self, node, t):
        if self.state == "execute" and node == self.next_node and self._cp_wanted(node):
            lc = self.last_choice
            f = float(self.ld["checkpoint_fraction"])
            self.cp = {"junction": self.node, "branch": lc["branch"], "next": node, "point": self._cp_point(self.node, node), "stage": "drive"}
            self._log(t, "checkpoint_drive", f"{lc['branch']} from {self.node}: stop at {f:g} of the way to {node} and ask the checkpoint worker",
                      point=[round(self.cp["point"][0], 2), round(self.cp["point"][1], 2)])
        super()._navigate(node, t)

    def _ask(self, t, cmd):
        super()._ask(t, cmd)
        self.ask_serial += 1
        if self.free_asks > 0:                                # a second view, a side view or a re-approach is not an unclear answer
            self.free_asks -= 1
            self.dialog.asks -= 1
        else:
            self.sv_since, self.side_view_used = None, False  # a new ask: one side view is allowed again
        self.waiting, self.wait_since, self.last_persons_frame = False, None, None
        self.amb_frames, self.amb_since = [], None
        self.rej_since = self.rej_key = None
        if self.record is not None:
            self.record.setdefault("t_ask_first", round(t, 3))

    # -- input helpers --
    def _fresh_persons(self, inp: TickInputV4) -> list:
        if inp.persons_time_s is None or inp.time_s - inp.persons_time_s > self.s["gesture_stale_s"]:
            return []
        return inp.persons

    def _aim_at(self, p: cm.PersonReading, inp: TickInputV4) -> None:
        """Aim the pan-tilt camera at this person: their world position at the bearing seen and the current distance."""
        if self.person is None:
            return
        d = max(0.5, math.hypot(self.person[0] - inp.x, self.person[1] - inp.z))
        self.person = hc.world_point(inp.x, inp.z, inp.yaw_deg, p.bearing_deg, d)

    def _link_360(self, p: cm.PersonReading, inp: TickInputV4) -> int | None:
        return cm.link_to_360(p.bearing_deg, [{"track_id": q.get("track_id", -1), "bearing_deg": q["bearing_deg"]}
                                              for q in self._fresh_people(inp)], self.ccfg["link_bearing_tol_deg"])

    def _interpret(self, inp: TickInputV4) -> str:
        """Commander + reading of the newest frame -> a dialog label: a branch command, 'WAIT' or 'NONE'."""
        self.reject = None
        persons = self._fresh_persons(inp)
        if self._cp_dialog():                                  # AUDIT.md 16.25: at a checkpoint only a qualifying person is read
            persons = [p for p in persons if self._cp_pt_ok(p, inp)]
        t_ask = self.record.get("t_ask_first") if self.record else None
        early = {p.track_id: "gesture started before the question was shown" for p in persons
                 if (p.reading.raised or p.reading.command == "PROCEED") and t_ask is not None and self.raised_since.get(p.track_id, math.inf) < t_ask - 1e-9}
        choice = cm.pick_commander(persons, self.ccfg, self.commander_pt, early)
        if choice.commander != self.commander_pt:
            self.commander_changes.append({"t": round(inp.time_s, 3), "from": self.commander_pt, "to": choice.commander,
                                           "reason": choice.reason})
            self.commander_since = inp.persons_time_s
        self.choice, self.commander_pt = choice, choice.commander
        self.resolution = None
        self._track_side_view(persons, choice.commander, inp)  # before the commander test: a held arm that fails the cue reads NONE and is never a commander (AUDIT.md 16.26.6)
        if choice.commander is None:
            self.commander_360 = None
            return "NONE"
        p = next(q for q in persons if q.track_id == choice.commander)
        self.commander_360 = self._link_360(p, inp)
        self._aim_at(p, inp)
        r = p.reading
        if self._cp_dialog():
            return self._interpret_cp(p, inp)
        if r.command == "PROCEED":                             # P2: the branch straight ahead of the arrival direction
            self.amb_frames, self.amb_since = [], None
            br = proceed_branch(self.road, self.node)
            self.proceed_note = "" if br else f"PROCEED read but {self.node} has no FORWARD branch"
            self.reject = self._rejection(br, None, self.proceed_note)
            return "NONE" if self.reject else (br or "NONE")
        if r.command == "POINT" and r.point is not None:
            dirs, arrival = branch_directions(self.road, self.node)
            dv = self.v4["dialog"]
            mirror = self.ld["reject_impossible"]                # AUDIT.md 16.11: a reading whose mirror image is the arrival road is ambiguous
            res = resolve_point(r.point, dirs, arrival, inp.yaw_deg, dv["branch_match_max_deg"],
                                dv["use_hand_crosscheck_as_tiebreak"], mirror)
            if self.view1 is not None:                         # second view: only a direction both views agree on counts
                res = resolve_two_views(self.view1, r.point.world_deg, dirs, arrival, inp.yaw_deg, dv["branch_match_max_deg"],
                                        dv["view_consistency_deg"], mirror)
            elif res.ambiguous and res.command is None and dv["two_view_enabled"] and not self.two_view_used:
                self.amb_frames.append(dict(r.point.world_deg))
                self.amb_why = res.why
                if self.amb_since is None:
                    self.amb_since = inp.persons_time_s
            else:
                self.amb_frames, self.amb_since = [], None
            self.resolution = res
            self.reject = self._rejection(res.command, res, res.why)
            return "NONE" if self.reject else (res.command or "NONE")
        self.amb_frames, self.amb_since = [], None
        return "WAIT" if r.command == "WAIT" else "NONE"

    def _track_side_view(self, persons: list, commander: int | None, inp: TickInputV4) -> None:
        """AUDIT.md 16.26 item 2 (trigger, corrected in 16.26.6): since when does the raised arm of the person being asked fail the POINT cue on length or elbow? That person is
        the commander if there is one, else (a held arm that fails the cue reads NONE, so nobody is the commander) the facing person in the direction of the worker the robot
        approached, within link_bearing_tol_deg. sv_since = the pan-tilt frame time the failure began; None when it does not hold."""
        if not self.sv["enabled"]:
            self.sv_since = None
            return

        def fails(q) -> bool:
            r = q.reading
            return bool(q.facing and r.raised and getattr(r, "point_fail", "") in ("length", "elbow") and r.command not in ("POINT", "WAIT", "STOP", "PROCEED"))
        who = next((q for q in persons if q.track_id == commander), None) if commander is not None else None
        if who is None and self.person is not None:
            toward = hc.wrap(hc.yaw_to(inp.x, inp.z, *self.person) - inp.yaw_deg)
            near = sorted((abs(hc.wrap(q.bearing_deg - toward)), q.track_id, q) for q in persons if fails(q))
            who = near[0][2] if near and near[0][0] <= self.ccfg["link_bearing_tol_deg"] else None
        if who is not None and fails(who):
            self.last_point_fail = who.reading.point_fail
            if self.sv_since is None:
                self.sv_since = inp.persons_time_s
        else:
            self.sv_since = None

    # -- rule (b): impossible answers --
    def _rejection(self, command: str | None, res: Resolution | None, why: str) -> tuple | None:
        """(reason, detail) when this resolved answer is not a way on: 'already_tried' (excluded by a backtrack, always),
        and with reject_impossible 'dead_end', 'arrival' or 'no_branch'. None = a usable answer, or an unclear one (the
        ambiguity of the two depth readings is not a rejection: the second view handles it)."""
        if command is not None:
            if command in self.excluded:
                return ("already_tried", f"{command} was taken here before and did not lead on")
            if self.ld["reject_impossible"] and self.road.kind(self.road.next(self.node, command)) == "dead_end":
                return ("dead_end", f"{command} leads to a dead end")
            return None
        if not self.ld["reject_impossible"]:
            return None
        if res is None:                                       # PROCEED where the node has no FORWARD branch
            return ("no_branch", why)
        if res.ambiguous or not res.candidates:
            return None
        arrival = any(c["target"] == "ARRIVAL" for c in res.candidates)
        return ("arrival" if arrival else "no_branch", why)

    def _reject_answer(self, inp: TickInputV4, t: float, rej: tuple) -> None:
        reason, detail = rej
        self.rejections.append(reason)
        self.rej_since = self.rej_key = None
        self.trace.append(f"{t:.2f}:reject:{reason}")
        if self.record is not None:
            self.record.setdefault("rejected", []).append(reason)
        self._log(t, "answer_rejected", reason, detail=detail, asks=self.dialog.asks, person_360=self._voter(),
                  resolution=self.resolution.to_dict() if self.resolution is not None else None)

    # -- rule (a): second opinion --
    def _voter(self) -> int | None:
        return self.commander_360 if self.commander_360 is not None else self.approached_360

    def _belongs_here(self, q: dict) -> tuple[bool, float, str]:
        """AUDIT.md 16.19 item 2: may this person give a second opinion at this node? Only a person within lie_detection.second_opinion_radius_m of the
        node whose NEAREST node of the roadmap is this one (the robot never drives toward another junction to ask). Returns (yes, distance to this node,
        nearest node). A radius that is absent or null = everybody (the earlier behaviour)."""
        r = self.ld.get("second_opinion_radius_m")
        x0, z0 = self.road.pos(self.node)
        d = math.hypot(q["x"] - x0, q["z"] - z0)
        if r is None:
            return True, d, self.node
        nearest = min(self.road.nodes, key=lambda n: math.hypot(q["x"] - self.road.pos(n)[0], q["z"] - self.road.pos(n)[1]))
        near_d = math.hypot(q["x"] - self.road.pos(nearest)[0], q["z"] - self.road.pos(nearest)[1])
        return bool(d <= r + 1e-9 and d <= near_d + 1e-9), d, nearest

    def _unasked(self, inp: TickInputV4) -> list:
        """Fresh 360 people with a track id not asked yet at this visit and belonging to this junction (_belongs_here), nearest first (without track
        ids nobody can be told apart: no second opinion). A person of another junction is skipped and logged once per visit (second_opinion_skipped)."""
        out = []
        for q in self._fresh_people(inp):
            tid = q.get("track_id", -1)
            if tid < 0 or tid in self.asked_360:
                continue
            ok, d, nearest = self._belongs_here(q)
            if ok:
                out.append(q)
            elif tid not in self.skipped_360:
                self.skipped_360.add(tid)
                self._log(inp.time_s, "second_opinion_skipped", "belongs to another junction or is too far: not asked", person_360=tid,
                          distance_to_node_m=round(d, 2), nearest_node=nearest, radius_m=self.ld.get("second_opinion_radius_m"))
        return sorted(out, key=lambda q: q["distance_m"])

    def _tally(self, inp: TickInputV4, exhausted: bool) -> tuple:
        """What to do after a dialog ended (a vote was added, or the person gave no usable answer = exhausted):
        ('go', branch, reason), ('ask', person dict, reason) or ('abort', None, reason)."""
        votes, cap = self.votes, self.ld["max_opinions"]
        n = len(votes)
        counts = Counter(v["branch"] for v in votes)
        top, top_n = counts.most_common(1)[0] if votes else (None, 0)
        if n >= 2 and top_n * 2 > n:
            return "go", top, f"{top_n} of {n} answers agree"
        more = self._unasked(inp) if self.dialogs_started < cap + 1 else []
        if n == 0:
            return ("ask", more[0], "no usable answer yet: ask the next person") if more else ("abort", None, "no usable answer from anybody")
        if n == 1:
            if more:
                return "ask", more[0], "second opinion"
            return "go", top, "one usable answer, nobody else to ask" if exhausted or self.dialogs_started > 1 else "one person only"
        if n >= cap:
            return "abort", None, f"no majority among {n} answers"
        if more:
            return "ask", more[0], "the two answers differ: ask a third person"
        if not self.tie_used:                                 # nobody else: the first person again, who then counts twice
            first = next((q for q in self._fresh_people(inp) if q.get("track_id", -1) == votes[0]["person_360"]), None)
            if first is not None:
                self.tie_used = True
                return "ask", first, "the two answers differ and nobody else is present: ask the first person again"
        return "abort", None, "the answers differ and nobody can break the tie"

    def _clear_approach_point(self, inp: TickInputV4, person: dict) -> tuple[tuple[float, float], float]:
        """Where to stand to ask this person: approach_distance_m from them, on the robot's side if no other person is within
        2 x corridor_half_width_m of that spot (a person there would hold the robot at the person-in-path stop for good), else
        at the first of +30, -30, +60, -60 ... degrees around them that is clear. Returns (point, degrees turned from the
        robot's side). Used for the people asked after the first only; the first approach is the unchanged v3 rule."""
        px, pz, r = person["x"], person["z"], self.g["approach_distance_m"]
        keep = 2.0 * self.s["corridor_half_width_m"]
        others = [(q["x"], q["z"]) for q in self._fresh_people(inp) if q.get("track_id", -1) != person.get("track_id", -1)]
        base = hc.yaw_to(px, pz, inp.x, inp.z)
        steps = [0.0] + [sgn * 30.0 * k for k in range(1, 7) for sgn in (1.0, -1.0)]
        for turn in steps:
            a = math.radians(base + turn)
            pt = (px + math.sin(a) * r, pz + math.cos(a) * r)
            if all(math.hypot(pt[0] - ox, pt[1] - oz) >= keep for ox, oz in others):
                return pt, turn
        a = math.radians(base)
        return (px + math.sin(a) * r, pz + math.cos(a) * r), 0.0

    def _start_dialog(self, inp: TickInputV4, t: float, person: dict, why: str, result: str) -> None:
        """Approach another person and ask: a dialog of its own (record with `opinion`), a fresh ask budget."""
        if self.record is not None:
            self._finish_record(result, t)
        px, pz = person["x"], person["z"]
        self.dialogs_started += 1
        tid = person.get("track_id", -1)
        self.asked_360.add(tid)
        self.approached_360 = tid
        self.person = (px, pz)
        self.approach_point, turned = self._clear_approach_point(inp, person)
        self.record = {"junction": self.node, "t_start": round(t, 3), "person_x": round(px, 3), "person_z": round(pz, 3),
                       "person_distance_m": round(person["distance_m"], 3), "opinion": self.dialogs_started, "person_360": tid}
        self.dialog.reset()
        self.view1, self.two_view_used, self.reapproached = None, False, False
        self.amb_frames, self.amb_since, self.commander_since = [], None, None
        self.commander_pt = self.commander_360 = self.choice = None
        self.waiting, self.wait_since, self.last_persons_frame = False, None, None
        self.rej_since = self.rej_key = None
        self.turning = False
        self.trace.append(f"{t:.2f}:second_opinion")
        self._log(t, "ask_next", why, person_360=tid, opinion=self.dialogs_started, approach_turned_deg=turned)
        self._set("approach", t)

    def _decide_go(self, t: float, branch: str, reason: str) -> None:
        if branch == "BACK":                                   # AUDIT.md 16.25.1: the answers at this junction decided to go back
            self._k_back(t, reason)
            return
        self.tried.setdefault(self.node, set()).add(branch)
        self.last_choice = {"node": self.node, "branch": branch, "serial": self.ask_serial,
                            "disagreed": len({v["branch"] for v in self.votes}) > 1}      # 16.22: did the accepted answers of this visit name more than one branch
        self._log(t, "go", reason, branch=branch, votes=[dict(v) for v in self.votes])
        self.next_node = self.road.next(self.node, branch)
        self._set("execute", t)

    def _after_vote(self, inp: TickInputV4, t: float, cmd, branch: str) -> bool:
        """An answer was accepted (the record is finished). True = the state was changed here (another person is asked, the
        robot goes, or it aborts); False = the caller sends the robot on as before."""
        self.votes.append({"person_360": self._voter(), "branch": branch, "serial": self.ask_serial})
        if not self.ld["second_opinion"]:
            self._decide_go(t, branch, "one answer accepted")
            return True
        act, what, why = self._tally(inp, exhausted=False)
        if act == "go":
            self._decide_go(t, what, why)
        elif act == "ask":
            self._start_dialog(inp, t, what, why, "accepted")
        else:
            self._abort(f"second opinion: {why} at {self.node}", t)
        return True

    def _exhausted(self, inp: TickInputV4, t: float, cmd) -> bool:
        """A dialog ended without a usable answer (asks used up). True = handled here (another person, a vote, a backtrack);
        False = the caller aborts as before."""
        if not (self.ld["second_opinion"] or self.ld["backtrack"]):
            return False
        if self.ld["second_opinion"]:
            act, what, why = self._tally(inp, exhausted=True)
            if act == "ask":
                self._start_dialog(inp, t, what, why, "no_answer")
                return True
            if act == "go":
                if self.record is not None:
                    self._finish_record("no_answer", t)
                self._decide_go(t, what, why)
                return True
        if self.ld["backtrack"] and self.rejections and not self.votes and self._start_backtrack(inp, t):
            return True
        return False

    # -- rule (c): backtrack --
    def _untried(self, node: str) -> list[str]:
        return [c for c in self.road.branches.get(node, {}) if c not in self.tried.get(node, set())]

    def _start_backtrack(self, inp: TickInputV4, t: float) -> bool:
        lc, here = self.last_choice, self.node
        why_not = None
        if lc is None or lc["node"] == here:
            why_not = "no earlier decision junction"
        elif self.road.nodes[here].get("arrive_from") != lc["node"]:
            why_not = f"{here} does not follow {lc['node']}"
        elif lc["node"] in self.backtracked:
            why_not = f"{lc['node']} has used its one backtrack"
        elif self.ld["backtrack_scope"] == "disagreed" and not lc.get("disagreed"):
            why_not = f"the answers at {lc['node']} did not disagree (backtrack_scope disagreed)"
        elif not self._untried(lc["node"]):
            why_not = f"{lc['node']} has no other branch"
        if why_not:
            self._log(t, "backtrack_blocked", why_not, rejections=list(self.rejections))
            return False
        back = lc["node"]
        if self.record is not None:
            self._finish_record("backtrack", t)
        self.backtracked.add(back)
        self.backtrack_target, self.waiting = back, False
        self.trace.append(f"{t:.2f}:backtrack")
        self._log(t, "backtrack", f"every answer at {here} was impossible ({', '.join(self.rejections)}): return to {back}",
                  to=back, failed_branch=lc["branch"], withdrawn_serial=lc["serial"], rejections=list(self.rejections))
        self._navigate(back, t)
        return True

    def _arrive_backtrack(self, node: str, t: float) -> None:
        self.backtrack_target = None
        self.node = node
        self.dialog.reset()
        others = self._untried(node)
        if len(others) == 1:
            self._new_junction()
            self._log(t, "take_other_branch", f"backtrack: {others[0]} is the one untried branch at {node}, no question",
                      branch=others[0])
            self._decide_go(t, others[0], "backtrack: the only untried branch")
            return
        self._set("scan", t)
        self._new_junction()
        self.excluded = set(self.tried.get(node, set()))
        self._log(t, "ask_again_after_backtrack", f"{len(others)} branches untried at {node}: ask again, excluding "
                  f"{sorted(self.excluded)}", excluded=sorted(self.excluded))

    def _track_onsets(self, inp: TickInputV4) -> None:
        """When did each person's arm go up (continuously)? Needed for 'the gesture started after the question'."""
        if inp.persons_time_s is None or inp.persons_time_s == self._onset_frame:
            return
        self._onset_frame = inp.persons_time_s
        seen = {p.track_id for p in inp.persons}
        for p in inp.persons:
            if p.reading.raised or p.reading.command == "PROCEED":      # PROCEED swings start below the raised line
                self.raised_since.setdefault(p.track_id, inp.persons_time_s)
            else:
                self.raised_since.pop(p.track_id, None)
        for k in [k for k in self.raised_since if k not in seen]:
            del self.raised_since[k]

    def _start_second_view(self, inp: TickInputV4, cmd) -> bool:
        """The two depth readings fitted two branches for gesture_hold_s: remember them and look again from one re-ask
        shift to the side (not an ask)."""
        if self.amb_since is None or inp.persons_time_s - self.amb_since < self.g["gesture_hold_s"] - 1e-6:
            return False
        view = {}
        for fam in ("away", "toward"):
            vals = [f[fam] for f in self.amb_frames if f.get(fam) is not None]
            view[fam] = gm.circular_mean(vals) if vals else None
        self.view1, self.two_view_used = view, True
        self.amb_frames, self.amb_since = [], None
        self.free_asks += 1
        self.trace.append(f"{inp.time_s:.2f}:second_view")
        self._log(inp.time_s, "second_view", self.amb_why or "the two depth readings fit two branches")
        if self.record is not None:
            self.record["second_view_t"] = round(inp.time_s, 3)
        self._reposition(inp, inp.time_s, cmd)
        return True

    def _back_axis_yaw(self) -> float | None:
        """World yaw of a BACK here: toward the junction from a checkpoint spot, else the direction the robot arrived from."""
        if self._cp_dialog():
            return hc.yaw_to(*self.cp["point"], *self.road.pos(self.cp["junction"]))
        return arrival_yaw(self.road, self.node)

    def _side_view_plan(self, inp: TickInputV4, axis_yaw: float) -> tuple[dict | None, str]:
        """(plan, why not): the viewpoint for a second reading of a worker whose arm is foreshortened. It is the point at the ask distance from the worker whose line of sight is
        PERPENDICULAR to the BACK axis, on the road side of the worker (a BACK is then 90 degrees from the camera, the middle of the readable band); the rotation around the worker from
        the present viewpoint is clamped to rotation_min_deg .. rotation_max_deg. The way follows the circle (waypoints every waypoint_step_deg at the radius that keeps the chord at the
        ask distance); the target and every waypoint keep keep_m from every other person (the clearance check of the recovery and of the second person's approach)."""
        sv = self.sv
        wx, wz = self.person
        r = float(self.g["approach_distance_m"])
        px, pz = self.cp["point"] if self._cp_dialog() else self.road.pos(self.node)
        a = math.radians(axis_yaw)
        u = (math.sin(a), math.cos(a))
        n1 = (u[1], -u[0])
        lat = (wx - px) * n1[0] + (wz - pz) * n1[1]
        side = -1.0 if lat > 1e-6 else 1.0 if lat < -1e-6 else (1.0 if ((inp.x - wx) * n1[0] + (inp.z - wz) * n1[1]) >= 0 else -1.0)      # the road side: against the worker's offset
        cur = hc.yaw_to(wx, wz, inp.x, inp.z)
        tgt0 = hc.yaw_to(wx, wz, wx + side * r * n1[0], wz + side * r * n1[1])
        delta = hc.wrap(tgt0 - cur)
        sign = 1.0 if delta >= 0 else -1.0
        mag = min(max(abs(delta), float(sv["rotation_min_deg"])), float(sv["rotation_max_deg"]))
        n_seg = max(1, math.ceil(mag / float(sv["waypoint_step_deg"]) - 1e-9))       # equal arcs of at most waypoint_step_deg
        seg = mag / n_seg
        r_way = r / math.cos(math.radians(min(seg, 170.0) / 2.0))                     # the vertices of the polygon round the ask circle: every leg touches the circle, none enters it

        def at(yaw_deg: float, radius: float) -> tuple[float, float]:
            return wx + math.sin(math.radians(yaw_deg)) * radius, wz + math.cos(math.radians(yaw_deg)) * radius
        ways = [at(cur + sign * (k + 0.5) * seg, r_way) for k in range(n_seg)]
        target = at(cur + sign * mag, r)
        keep = float(sv["keep_m"]) if sv["keep_m"] is not None else 2.0 * self.s["corridor_half_width_m"]
        others = [(q["x"], q["z"]) for q in self._fresh_people(inp) if math.hypot(q["x"] - wx, q["z"] - wz) > 0.5]
        for pt in ways + [target]:
            if any(math.hypot(pt[0] - ox, pt[1] - oz) < keep - 1e-9 for ox, oz in others):
                return None, f"somebody within {keep:g} m of the way or of the viewpoint"
        return {"target": target, "waypoints": ways, "rotation_deg": round(sign * mag, 2), "perpendicular_deg": round(delta, 2), "axis_yaw": round(axis_yaw, 2)}, ""

    def _start_side_view(self, inp: TickInputV4, t: float) -> bool:
        """The commander's raised arm has failed the POINT cue on its length or elbow for gesture_hold_s: look again from the side, once per ask (AUDIT.md 16.26 item 2)."""
        if (not self.sv["enabled"] or self.side_view_used or self.sv_since is None or self.waiting or self.person is None
                or inp.persons_time_s is None or inp.persons_time_s - self.sv_since < self.g["gesture_hold_s"] - 1e-6):
            return False
        self.side_view_used = True                             # decided once, whatever comes of it
        axis = self._back_axis_yaw()
        if axis is None:
            self._log(t, "side_view_blocked", "no arrival direction known here")
            return False
        plan, why = self._side_view_plan(inp, axis)
        if plan is None:
            self._log(t, "side_view_blocked", why, axis_yaw=round(axis, 2))
            return False
        self.approach_point = plan["target"]
        self.detour = list(plan["waypoints"])
        self.turning = False
        self.free_asks += 1                                    # not an unclear answer, as the second view
        self.waiting, self.wait_since = False, None
        self.sv_since = None
        self.trace.append(f"{t:.2f}:side_view")
        rec = {"t": round(t, 3), "node": self.node, "ask": self.dialog.asks, "serial": self.ask_serial, **{k: plan[k] for k in ("rotation_deg", "perpendicular_deg", "axis_yaw")},
               "to": [round(plan["target"][0], 2), round(plan["target"][1], 2)]}
        self.side_views.append(rec)
        if self.record is not None:
            self.record["side_view"] = rec
        self._log(t, "side_view", f"raised arm fails the POINT cue on its {self.last_point_fail}: a second reading from {abs(plan['rotation_deg']):g} degrees round the worker",
                  **{k: v for k, v in rec.items() if k != "t"})
        self._set("approach", t)
        return True

    def _start_reapproach(self, inp: TickInputV4) -> bool:
        """The commander is not the person the robot approached: go to the commander (once per junction)."""
        dv = self.v4["dialog"]
        if (not dv["reapproach_commander"] or self.reapproached or self.waiting or self.commander_360 is None
                or self.approached_360 is None or self.commander_360 == self.approached_360 or self.commander_since is None
                or inp.persons_time_s - self.commander_since < self.g["gesture_hold_s"] - 1e-6):
            return False
        tgt = next((q for q in self._fresh_people(inp) if q.get("track_id") == self.commander_360), None)
        if tgt is None or (self._cp_dialog() and not self._cp_qualifies(tgt)):                  # AUDIT.md 16.25: at a checkpoint only a qualifying person is approached
            return False
        px, pz = tgt["x"], tgt["z"]
        ax, az = inp.x - px, inp.z - pz
        n = math.hypot(ax, az) or 1.0
        r = self.g["approach_distance_m"]
        self.person, self.approach_point = (px, pz), (px + ax / n * r, pz + az / n * r)
        if self.record is not None:
            self.record["reapproach"] = {"from_360": self.approached_360, "to_360": self.commander_360, "t": round(inp.time_s, 3)}
        self.approached_360, self.reapproached, self.turning = self.commander_360, True, False
        self.asked_360.add(self.commander_360)
        self.free_asks += 1
        self.trace.append(f"{inp.time_s:.2f}:reapproach")
        self._set("approach", inp.time_s)
        return True

    def _log_frame(self, inp: TickInputV4) -> dict:
        """Everything decided for this frame, so the evaluation can score the commander choice and the readings against
        truth.jsonl: the people with their readings, the choice with its reasons, the label, the resolution."""
        row = {"t": round(inp.persons_time_s, 4), "ctrl_t": round(inp.time_s, 4), "junction": self.node,
               "mode": "wait" if self.waiting else "read", "asks": self.dialog.asks,
               "robot": {"x": round(inp.x, 3), "z": round(inp.z, 3), "yaw_deg": round(inp.yaw_deg, 2)},
               "pan_deg": round(inp.pan_deg, 2), "fov_deg": inp.fov_deg, "tilt_deg": inp.tilt_deg,
               "persons": [{"id": p.track_id, "bearing_deg": round(p.bearing_deg, 2), "facing": p.facing,
                            "distance_m": p.distance_m, "reading": p.reading.to_dict()} for p in self._fresh_persons(inp)],
               "commander": self.choice.to_dict() if self.choice is not None else None,
               "commander_360": self.commander_360, "label": self.label, "proceed_note": self.proceed_note,
               "resolution": self.resolution.to_dict() if self.resolution is not None else None}
        self.frame_log.append(row)
        return row

    def pop_frame_log(self) -> list[dict]:
        out, self.frame_log = self.frame_log, []
        return out

    # -- the READ state (and its wait mode) --
    def _tick(self, inp, cmd):
        if self.state == "read":
            self._read_tick(inp, cmd)
            return
        if self.state == "navigate" and self.cp is not None and self.cp["stage"] == "drive":
            self._cp_drive(inp, cmd)
            return
        if self.state == "scan" and self._cp_dialog():
            self._cp_scan(inp)
            return
        if self.state == "execute" and self._return_pending():     # D (AUDIT.md 16.19.2): back to the junction point, then the branch
            nx, nz = self.road.pos(self.node)
            if math.hypot(nx - inp.x, nz - inp.z) <= self.d["arrive_junction_m"] and abs(inp.v) < self.d["stopped_speed_mps"]:
                self._returned = True
                self._log(inp.time_s, "returned_to_junction", "at the junction point: now the branch",
                          distance_m=round(math.hypot(nx - inp.x, nz - inp.z), 2))
            else:
                # AUDIT.md 16.20.5: the return drives at dialog.return_speed_mps (the cruise speed); absent = the approach speed, as before
                speed = self.v4["dialog"].get("return_speed_mps") or self.d["approach_speed_mps"]
                cmd.v, cmd.omega, _ = hc.pure_pursuit(inp.x, inp.z, inp.yaw_deg, self._path(inp, nx, nz), self.d, speed, self.d["arrive_junction_m"])
                return
        before = self.state
        super()._tick(inp, cmd)
        if before == "scan" and self.state == "approach":      # remember whom the robot goes to (360-camera track id)
            people = self._fresh_people(inp)
            if people:
                self.approached_360 = min(people, key=lambda q: q["distance_m"]).get("track_id")
                self.dialogs_started = 1
                if self.approached_360 is not None:
                    self.asked_360.add(self.approached_360)
                if self.ld["second_opinion"] and self.record is not None:
                    self.record.update(opinion=1, person_360=self.approached_360)

    def _read_tick(self, inp: TickInputV4, cmd):
        t, dv = inp.time_s, self.v4["dialog"]
        new = (inp.persons_time_s is not None and inp.persons_time_s != self.last_persons_frame
               and inp.persons_time_s >= self.dialog.ask_start)
        ev = "pending"
        if new:
            self.last_persons_frame = inp.persons_time_s
            self.label = self._interpret(inp)
            self._row = self._log_frame(inp)
            if self._start_reapproach(inp) or self._start_second_view(inp, cmd) or self._start_side_view(inp, t):
                return
            if self.label == "WAIT":
                if self.wait_since is None:
                    self.wait_since = inp.persons_time_s
                if not self.waiting and inp.persons_time_s - self.wait_since >= dv["wait_hold_s"] - 1e-6:
                    self.waiting, self.wait_start = True, t
                    self.dialog.candidate = "NONE"
                    self.trace.append(f"{t:.2f}:wait")
            else:
                self.wait_since = None
            label = self.label if self.label in DIRECTIONS else "NONE"
            held = False                                        # rule (b): an impossible answer held for gesture_hold_s
            if self.reject is not None:
                if self.rej_since is None or self.rej_key != self.reject[0]:
                    self.rej_since, self.rej_key = inp.persons_time_s, self.reject[0]
                held = inp.persons_time_s - self.rej_since >= self.g["gesture_hold_s"] - 1e-6
            else:
                self.rej_since = self.rej_key = None
            if held:
                if self._cp_dialog():                           # T3: a checkpoint pointing back is the evidence, not an unclear answer
                    self._cp_back(inp, t)
                    return
                if self.back_ctx is not None and self.reject[0] == "arrival":     # AUDIT.md 16.25.1: here BACK is a vote, not a rejection
                    self._back_vote(inp, t, cmd)
                    return
                self._reject_answer(inp, t, self.reject)
                ev = self.dialog.unclear()
            else:
                ev = self.dialog.update(label, inp.persons_time_s, self.dialog.ask_start if self.waiting else t)
        elif not self.waiting and t - self.dialog.ask_start >= self.g["gesture_window_s"]:
            ev = self.dialog.unclear()
        if self.waiting and ev == "pending" and t - self.wait_start >= dv["wait_timeout_s"]:
            self.waited_s += t - self.wait_start
            self.waiting = False
            ev = self.dialog.unclear()
            self.abort_note = f"wait timeout ({dv['wait_timeout_s']:g} s) after {self.dialog.asks} asks at {self.node}"
        if ev == "accepted" and self._cp_dialog():
            self._cp_proceed(inp, t)
            return
        if ev == "accepted":
            nxt = self.road.next(self.node, self.dialog.accepted)
            if nxt is not None:
                if self.waiting:
                    self.waited_s += t - self.wait_start
                self.waiting = False
                self.record.update(t_accept=round(t, 3), waited_s=round(self.waited_s, 3), views=2 if self.view1 else 1,
                                   reapproached=self.reapproached,
                                   point=self.resolution.to_dict() if self.resolution else None,
                                   commander_pt=self.commander_pt, commander_360=self.commander_360)
                self._finish_record("accepted", t)
                self._log(t, "answer_accepted", f"{self.dialog.accepted} read for {self.g['gesture_hold_s']:g} s",
                          branch=self.dialog.accepted, asks=self.dialog.asks, person_360=self._voter(),
                          views=2 if self.view1 else 1)
                self._after_vote(inp, t, cmd, self.dialog.accepted)
                return
            ev = self.dialog.unclear()
        if ev == "ask_again":
            self.waiting, self.wait_since = False, None
            self._reposition(inp, t, cmd)
        elif ev == "abort":
            self.waiting = False
            if self._cp_dialog():                               # T3: nothing usable at a checkpoint: carry on
                self._cp_none(t, f"no usable answer after {self.dialog.asks} asks")
                return
            if self._exhausted(inp, t, cmd):
                self.abort_note = ""
                return
            note = getattr(self, "abort_note", "")
            self._abort(note or f"gesture unclear after {self.dialog.asks} asks at {self.node}", t)
            self.abort_note = ""

    def _log_ask(self, inp: TickInputV4) -> None:
        """P3/P8: at every new ask, the 360 distance estimate of the approached person (its 360 track, else the nearest
        fresh person to where the robot believes the person is) with the robot pose; record['asks_log']."""
        if self.ask_serial == self._ask_logged or self.record is None:
            return
        self._ask_logged = self.ask_serial
        people = self._fresh_people(inp)
        q = next((p for p in people if self.approached_360 is not None and p.get("track_id") == self.approached_360), None)
        if q is None and people and self.person is not None:
            q = min(people, key=lambda p: math.hypot(p["x"] - self.person[0], p["z"] - self.person[1]))
        self.record.setdefault("asks_log", []).append({
            "t": round(inp.time_s, 3), "ask": self.dialog.asks, "serial": self.ask_serial,
            "robot": {"x": round(inp.x, 3), "z": round(inp.z, 3), "yaw_deg": round(inp.yaw_deg, 2)},
            "track_360": q.get("track_id", -1) if q is not None else -1,
            "distance_est_m": round(q["distance_m"], 3) if q is not None else -1.0,
            "distance_source": q.get("distance_source", "") if q is not None else "none"})

    # -- the tick --
    def step(self, inp: TickInputV4) -> CommandV4:
        sr = self.v4.get("stop_rule", {})
        if sr.get("still_when_robot_stopped") and self.state in sr.get("states", ()) and abs(inp.v) < sr["robot_stopped_speed_mps"]:
            # C2s (AUDIT.md 16.19.7): the robot stands still, so every person's reading is the one with the short-window stillness rule for STOP; while it
            # moves the readings are the reader's own, exactly as before
            inp.persons = [replace(p, reading=p.reading_stopped) if p.reading_stopped is not None else p for p in inp.persons]
        # STOP of anybody in view stops the robot (the v3 rule reads TickInput.gesture)
        self._track_onsets(inp)
        persons = self._fresh_persons(inp)
        stop = any(p.reading.command == "STOP" for p in persons)
        inp.gesture, inp.gesture_time_s = ("STOP" if stop else "NONE"), inp.persons_time_s
        base = super().step(inp)
        self._recovery(inp, base)
        stopped = bool(self.safety_reason)
        if stopped and not self._was_stopped:
            self.safety_stops += 1
        self._was_stopped = stopped
        self._log_ask(inp)
        out = CommandV4(**{f: getattr(base, f) for f in ("v", "omega", "pan_deg", "has_target", "target_x", "target_z",
                                                          "state", "screen_text")})
        if self.state == "read" and self.person is not None:
            out.pan_deg = -hc.wrap(hc.yaw_to(inp.x, inp.z, *self.person) - inp.yaw_deg)
            if self.waiting:
                out.state = "wait" + out.state[len("read"):]
                out.screen_text = self.v4["dialog"]["wait_text"]
        reading = None
        if self.commander_pt is not None:
            reading = next((p.reading for p in persons if p.track_id == self.commander_pt), None)
        active = self.state in ("ask", "read") and not self.finished
        self.fov_cmd = self.zoom.update(inp.time_s, reading, inp.fov_deg, active, inp.tilt_deg)
        out.vertical_fov_deg = self.fov_cmd
        out.tilt_deg = self.zoom.tilt_cmd
        if self._row is not None:
            self._row["fov_cmd"], self._row["state"] = self.fov_cmd, out.state
            self._row = None
        out.hud = self.hud_fields(persons)
        return out

    # -- T3: checkpoint workers (AUDIT.md 16.23) --
    def _cp_dialog(self) -> bool:
        return self.cp is not None and self.cp["stage"] == "dialog"

    def _cp_point(self, junction: str, nxt: str) -> tuple[float, float]:
        """The checkpoint spot of the branch from `junction` to `nxt`: checkpoint_s_m along it from the junction when the branch has an entry (AUDIT.md 16.26: the point of the
        road abeam the worker), else checkpoint_fraction of the way."""
        (x0, z0), (x1, z1) = self.road.pos(junction), self.road.pos(nxt)
        length = math.hypot(x1 - x0, z1 - z0)
        table = self.ld["checkpoint_s_m"]
        if table:
            cmd = next((c for c, n in self.road.branches.get(junction, {}).items() if n == nxt), None)
            s = table.get(f"{junction}>{cmd}")
            if s is not None and length > 0:
                return x0 + float(s) / length * (x1 - x0), z0 + float(s) / length * (z1 - z0)
        f = float(self.ld["checkpoint_fraction"])
        return x0 + f * (x1 - x0), z0 + f * (z1 - z0)

    def _cp_spots(self) -> dict:
        """{(junction, command): (x, z)} of every checkpoint spot of the map: `checkpoint_fraction` of the way along a branch leaving a decision junction (the robot's own rule, roadmap only)."""
        out = {}
        for j, br in self.road.branches.items():
            if self.road.kind(j) != "junction" or len(br) < 2:
                continue
            for cmd, nxt in br.items():
                if self._cp_has(j, cmd):
                    out[(j, cmd)] = self._cp_point(j, nxt)
        return out

    def _cp_qualifies(self, q: dict) -> bool:
        """AUDIT.md 16.25: may this person (a 360 track with a world position) be asked at the checkpoint being handled? (a) within checkpoint_person_radius_m of THIS spot, (b) this spot is
        the nearest spot of the map to them, (c) outside the second-opinion zone of every asking node (every junction and the start node)."""
        cp = self.cp
        if cp is None:
            return False
        here = cp["point"]
        d = math.hypot(q["x"] - here[0], q["z"] - here[1])
        if d > float(self.ld["checkpoint_person_radius_m"]) + 1e-9:
            return False
        if any(math.hypot(q["x"] - s[0], q["z"] - s[1]) < d - 1e-9 for k, s in self._cp_spots().items() if k != (cp["junction"], cp["branch"])):
            return False
        zone = self.ld["second_opinion_radius_m"]
        return not any(math.hypot(q["x"] - self.road.pos(n)[0], q["z"] - self.road.pos(n)[1]) <= zone + 1e-9
                       for n, v in self.road.nodes.items() if v["kind"] in ("junction", START))

    def _cp_pt_ok(self, p: cm.PersonReading, inp: TickInputV4) -> bool:
        """A pan-tilt person is read at a checkpoint only when linked to a qualifying 360 track (a person who cannot be placed is not read)."""
        tid = self._link_360(p, inp)
        if tid is None:
            return False
        q = next((q for q in self._fresh_people(inp) if q.get("track_id", -1) == tid), None)
        return q is not None and self._cp_qualifies(q)

    def _cp_has(self, junction: str, command: str) -> bool:
        """Does this branch have a checkpoint worker (checkpoint on, and the branch in checkpoint_branches; None = every branch of a decision junction)?"""
        if not self.ld["checkpoint"]:
            return False
        branches = self.ld["checkpoint_branches"]
        return branches is None or f"{junction}>{command}" in branches

    def _cp_wanted(self, node: str) -> bool:
        """After a decision at a decision junction (a junction with two or more branches): is the branch to `node` one whose checkpoint is still to be asked?"""
        if not self.ld["checkpoint"]:
            return False
        lc = self.last_choice
        if lc is None or lc["node"] != self.node or self.road.kind(self.node) != "junction" or len(self.road.branches.get(self.node, {})) < 2:
            return False
        return (self._cp_has(self.node, lc["branch"]) and self.road.next(self.node, lc["branch"]) == node and (self.node, lc["branch"]) not in self.cp_done)

    def _cp_drive(self, inp: TickInputV4, cmd) -> None:
        tx, tz = self.cp["point"]
        d = self.d
        cmd.v, cmd.omega, arrived = hc.pure_pursuit(inp.x, inp.z, inp.yaw_deg, self._path(inp, tx, tz), d, d["cruise_speed_mps"], d["arrive_endpoint_m"])
        if arrived and abs(inp.v) < d["stopped_speed_mps"]:
            self.cp["stage"] = "dialog"
            self.dialog.reset()
            self._new_junction()
            self.person = self.approach_point = None
            self._log(inp.time_s, "checkpoint_arrived", f"at the checkpoint of {self.cp['junction']} {self.cp['branch']}: look for a person")
            self._set("scan", inp.time_s)

    def _cp_scan(self, inp: TickInputV4) -> None:
        """The scan of a checkpoint: the nearest person who does not belong to the junction (a junction worker is not the checkpoint); nobody within
        scan_timeout_s = carry on (never an abort)."""
        t = inp.time_s
        people = self._fresh_people(inp)
        seen = bool(people) and inp.people_time_s is not None and inp.people_time_s >= self.state_start
        cand = [q for q in people if self._cp_qualifies(q)] if seen else []                    # AUDIT.md 16.25
        if t - self.state_start >= self.g["scan_min_s"] and cand:
            p = min(cand, key=lambda q: q["distance_m"])
            self.person = (p["x"], p["z"])
            ax, az = inp.x - p["x"], inp.z - p["z"]
            n = math.hypot(ax, az) or 1.0
            r = self.g["approach_distance_m"]
            self.approach_point = (p["x"] + ax / n * r, p["z"] + az / n * r)
            self.turning = False
            self.record = {"junction": self.node, "checkpoint": f"{self.cp['junction']}>{self.cp['branch']}", "t_start": round(t, 3), "person_x": round(p["x"], 3),
                           "person_z": round(p["z"], 3), "person_distance_m": round(p["distance_m"], 3), "person_360": p.get("track_id")}
            self.approached_360 = p.get("track_id")
            self.dialogs_started = 1
            if self.approached_360 is not None:
                self.asked_360.add(self.approached_360)
            self._set("approach", t)
        elif t - self.state_start >= self.g["scan_timeout_s"]:
            self._log(t, "checkpoint_no_person", f"nobody qualifies at the checkpoint of {self.cp['junction']} {self.cp['branch']} within {self.g['scan_timeout_s']:g} s "
                      f"(within {self.ld['checkpoint_person_radius_m']:g} m of the spot, nearest to it, outside every junction zone)", people_seen=len(people))
            self._cp_none(t, "no checkpoint person", no_person=True)

    def _interpret_cp(self, p: cm.PersonReading, inp: TickInputV4) -> str:
        """The label of a checkpoint worker's gesture: PROCEED (or a point along the branch) = FORWARD; a point back along the arrival road = NONE with
        self.reject ('arrival'), the evidence; anything else = NONE. The mirror-image ambiguity (AUDIT.md 16.11) is the one of resolve_point."""
        r = p.reading
        cp = self.cp
        if r.command == "PROCEED":
            self.amb_frames, self.amb_since = [], None
            return "FORWARD"
        if r.command == "POINT" and r.point is not None:
            px, pz = cp["point"]
            dirs = {"FORWARD": hc.yaw_to(px, pz, *self.road.pos(cp["next"]))}
            arrival = hc.yaw_to(px, pz, *self.road.pos(cp["junction"]))
            dv = self.v4["dialog"]
            mirror = self.ld["reject_impossible"]
            res = resolve_point(r.point, dirs, arrival, inp.yaw_deg, dv["branch_match_max_deg"], dv["use_hand_crosscheck_as_tiebreak"], mirror)
            if self.view1 is not None:
                res = resolve_two_views(self.view1, r.point.world_deg, dirs, arrival, inp.yaw_deg, dv["branch_match_max_deg"], dv["view_consistency_deg"], mirror)
            elif res.ambiguous and res.command is None and dv["two_view_enabled"] and not self.two_view_used:
                self.amb_frames.append(dict(r.point.world_deg))
                self.amb_why = res.why
                if self.amb_since is None:
                    self.amb_since = inp.persons_time_s
            else:
                self.amb_frames, self.amb_since = [], None
            self.resolution = res
            if res.command is None and not res.ambiguous and any(c["target"] == "ARRIVAL" for c in res.candidates):
                self.reject = ("arrival", "the checkpoint worker points back along the road")
                return "NONE"
            return res.command or "NONE"
        self.amb_frames, self.amb_since = [], None
        return "NONE"

    def _cp_finish(self, t: float, result: str) -> None:
        if self.record is not None:
            self.record.update(t_accept=round(t, 3), checkpoint_result=result, point=self.resolution.to_dict() if self.resolution else None,
                               commander_pt=self.commander_pt, commander_360=self.commander_360, views=2 if self.view1 else 1)
            self._finish_record(result, t)
        self.waiting = False
        self.rej_since = self.rej_key = None

    def _cp_note(self, t: float, result: str, action: str, why: str, no_person: bool = False) -> None:
        cp = self.cp
        self.cp_log.append({"t": round(t, 3), "junction": cp["junction"], "branch": cp["branch"], "next": cp["next"], "result": result, "action": action,
                            "asks": self.dialog.asks, "person_360": self._voter(), "no_person": no_person})
        self._log(t, "checkpoint_answer", why, junction=cp["junction"], branch=cp["branch"], result=result, action=action)

    def _cp_continue(self, t: float) -> None:
        cp = self.cp
        self.cp_done.add((cp["junction"], cp["branch"]))
        cp["stage"] = "passed"
        self._navigate(cp["next"], t)

    def _cp_proceed(self, inp: TickInputV4, t: float) -> None:
        self._cp_finish(t, "accepted")
        self._cp_note(t, "proceed", "continue", f"the checkpoint of {self.cp['junction']} {self.cp['branch']} shows the way on: continue")
        self._cp_continue(t)

    def _cp_none(self, t: float, why: str, no_person: bool = False) -> None:
        self._cp_finish(t, "unclear")
        self._cp_note(t, "none", "continue", f"checkpoint of {self.cp['junction']} {self.cp['branch']}: {why}: continue", no_person=no_person)
        self._cp_continue(t)

    def _cp_back(self, inp: TickInputV4, t: float) -> None:
        """The checkpoint points back: evidence the branch is wrong. One backtrack per junction (the existing machinery); a second pointing back keeps the branch."""
        cp, j = self.cp, self.cp["junction"]
        self._cp_finish(t, "back")
        lc = self.last_choice
        disputed = bool(lc and lc["node"] == j and lc["branch"] == cp["branch"] and lc.get("disagreed"))
        if self.ld["checkpoint_scope"] == "disputed" and not disputed:        # T4: one vote against a junction whose answers agreed: logged, ignored
            self._cp_note(t, "back", "ignore_undisputed", f"the checkpoint of {j} {cp['branch']} points back but the answers at {j} agreed: ignored, keep {cp['branch']}")
            self._cp_continue(t)
        elif j in self.backtracked:
            self._cp_note(t, "back", "keep", f"{j} has used its one backtrack: keep {cp['branch']}")
            self._cp_continue(t)
        elif not self._untried(j):
            self._cp_note(t, "back", "keep", f"{j} has no other branch: keep {cp['branch']}")
            self._cp_continue(t)
        else:
            self._cp_note(t, "back", "backtrack", f"the checkpoint of {j} {cp['branch']} points back: return to {j}")
            self.backtracked.add(j)
            self.backtrack_target = j
            self.cp_backtracks += 1
            self.trace.append(f"{t:.2f}:backtrack")
            self._log(t, "backtrack", f"checkpoint pointed back on {cp['branch']}: return to {j}", to=j, failed_branch=cp["branch"],
                      withdrawn_serial=self.last_choice["serial"] if self.last_choice else None, rejections=[])
            self.cp = None
            self._navigate(j, t)

    # -- AUDIT.md 16.25.1: "back" at the next junction --
    def _back_context(self, node: str) -> dict | None:
        """Called at an arrival at junction `node`: does a BACK answer here count as a vote to go back? Only when `node` was reached by the branch just decided at J, J was DISPUTED,
        that branch has no checkpoint worker, J has not used its one backtrack and has another branch untried. Anywhere else BACK stays rejected."""
        if not self.ld["next_junction_back"] or self.road.kind(node) != "junction":
            return None
        lc = self.last_choice
        if lc is None or lc["node"] == node or self.road.next(lc["node"], lc["branch"]) != node:
            return None
        j = lc["node"]
        if not lc.get("disagreed") or j in self.backtracked or not self._untried(j) or self._cp_has(j, lc["branch"]):
            return None
        return {"junction": j, "branch": lc["branch"], "serial": lc["serial"]}

    def _back_vote(self, inp: TickInputV4, t: float, cmd) -> None:
        """A held answer pointing back along the arrival road, in a visit where it counts (back_ctx): accepted as a vote "BACK" in this junction's tally."""
        ctx = self.back_ctx
        if self.record is not None:
            self.record.update(t_accept=round(t, 3), back_vote=True, views=2 if self.view1 else 1, point=self.resolution.to_dict() if self.resolution else None,
                               commander_pt=self.commander_pt, commander_360=self.commander_360)
        self.dialog.accepted = "BACK"
        self.waiting = False
        self.rej_since = self.rej_key = None
        self._finish_record("accepted", t)
        self._log(t, "answer_accepted", f"BACK read for {self.g['gesture_hold_s']:g} s: the arrival road, counted as a vote at {self.node} (the answers at {ctx['junction']} disagreed)",
                  branch="BACK", asks=self.dialog.asks, person_360=self._voter(), back_vote=True)
        self._after_vote(inp, t, cmd, "BACK")

    def _k_back(self, t: float, reason: str) -> None:
        """The tally of this junction decided BACK: return to the junction J whose answers disagreed (the existing backtrack machinery, at most once per J)."""
        ctx = self.back_ctx
        j = ctx["junction"]
        self.nj_log.append({"t": round(t, 3), "junction": j, "branch": ctx["branch"], "at": self.node, "action": "backtrack"})
        self.backtracked.add(j)
        self.backtrack_target = j
        self.trace.append(f"{t:.2f}:backtrack")
        self._log(t, "backtrack", f"{reason}: the answers at {self.node} point back along the road from {j} (whose answers disagreed): return to {j}", to=j, failed_branch=ctx["branch"],
                  withdrawn_serial=ctx["serial"], rejections=list(self.rejections), kind="next_junction")
        self.back_ctx = None
        self._navigate(j, t)

    # -- E: person-in-path recovery (AUDIT.md 16.19.2) --
    def _blocker(self, inp) -> dict | None:
        """The person the v3 person-in-path stop is about (the same test as hri_control.Controller._safety)."""
        for q in self._fresh_people(inp):
            if hc.in_path(inp.x, inp.z, inp.yaw_deg, q["x"], q["z"], hc.stop_distance(inp.v, self.s), self.s["corridor_half_width_m"]):
                return q
        return None

    def _rear_clear(self, inp) -> bool:
        """Nobody within the stop distance behind the robot at the back-up speed plus the back-up distance (the robot has no rear bumper logic)."""
        rc = self.rc
        reach = rc["back_m"] + hc.stop_distance(rc["back_speed_mps"], self.s)
        return not any(hc.in_path(inp.x, inp.z, inp.yaw_deg + 180.0, q["x"], q["z"], reach, self.s["corridor_half_width_m"]) for q in self._fresh_people(inp))

    def _plan_detour(self, inp, person: dict, others: list) -> tuple[str, list] | None:
        """Waypoints past the blocking person on the clear side: W1 side_m to the side and beyond_m BEFORE them, W2 side_m to the side and beyond_m
        AFTER them (the leg W1 to W2 runs parallel to the road at side_m from them), then the normal path to the target. The right side unless
        somebody is within side_m of a waypoint or of the leg, else the left, else None. Never toward the person: every point of the path keeps
        about side_m from them (pure pursuit cuts the corners a little)."""
        rc, a = self.rc, math.radians(inp.yaw_deg)
        f, right = (math.sin(a), math.cos(a)), (math.cos(a), -math.sin(a))
        px, pz = person["x"], person["z"]
        for name, sgn in (("right", 1.0), ("left", -1.0)):
            lat = (px + sgn * right[0] * rc["side_m"], pz + sgn * right[1] * rc["side_m"])
            w1 = (lat[0] - f[0] * rc["beyond_m"], lat[1] - f[1] * rc["beyond_m"])
            w2 = (lat[0] + f[0] * rc["beyond_m"], lat[1] + f[1] * rc["beyond_m"])
            if all(math.hypot(q[0] - o["x"], q[1] - o["z"]) >= rc["side_m"] for o in others for q in (w1, lat, w2)):
                return name, [w1, w2]
        return None

    def _recovery(self, inp, cmd) -> None:
        rc, t = self.rc, inp.time_s
        if not rc["enabled"]:
            return
        if self._rec is not None:                                  # backing up
            r = self._rec
            if math.hypot(inp.x - r["x0"], inp.z - r["z0"]) >= rc["back_m"] - 1e-9:
                self.detour = list(r["waypoints"])
                self._log(t, "recovery_detour", f"backed {rc['back_m']:g} m: around the person on the {r['side']} side", side=r["side"],
                          waypoints=[[round(x, 2), round(z, 2)] for x, z in r["waypoints"]])
                self._rec = self._blk = None
                return
            if not self._rear_clear(inp):
                self._log(t, "recovery_interrupted", "somebody behind the robot: stopped backing")
                self._rec = None
                return
            cmd.v, cmd.omega = -rc["back_speed_mps"], 0.0
            cmd.state = f"{self.state} (recovery: backing)"
            return
        q = self._blocker(inp) if self.safety_reason == "person in path" and self.state in ("navigate", "approach", "execute") else None
        if q is None:
            self._blk = None
            return
        pos = (q["x"], q["z"])
        if self._blk is None or math.hypot(pos[0] - self._blk["last"][0], pos[1] - self._blk["last"][1]) > 0.5:
            self._blk = {"since": t, "p0": pos, "last": pos, "moved": 0.0, "pid": q.get("track_id", -1)}
        b = self._blk
        b["last"] = pos
        b["moved"] = max(b["moved"], math.hypot(pos[0] - b["p0"][0], pos[1] - b["p0"][1]))
        key = b["pid"] if b["pid"] is not None and b["pid"] >= 0 else (round(b["p0"][0], 1), round(b["p0"][1], 1))
        if (t - b["since"] < rc["blocked_s"] - 1e-9 or b["moved"] >= rc["person_moved_max_m"] or abs(inp.v) >= self.d["stopped_speed_mps"]
                or self.rec_attempts.get(key, 0) >= rc["max_attempts"]):
            return
        if not self._rear_clear(inp):
            if ("rear", key) not in self._rec_noted:
                self._rec_noted.add(("rear", key))
                self._log(t, "recovery_waiting", "somebody behind the robot: not backing up", person=list(map(lambda v: round(v, 2), pos)))
            return
        others = [o for o in self._fresh_people(inp) if math.hypot(o["x"] - pos[0], o["z"] - pos[1]) > 0.3]
        plan = self._plan_detour(inp, q, others)
        if plan is None:
            if ("side", key) not in self._rec_noted:
                self._rec_noted.add(("side", key))
                self._log(t, "recovery_waiting", "no clear side around the person: not backing up", person=list(map(lambda v: round(v, 2), pos)))
            return
        side, waypoints = plan
        self.rec_attempts[key] = self.rec_attempts.get(key, 0) + 1
        self.recoveries += 1
        self._rec = {"x0": inp.x, "z0": inp.z, "side": side, "waypoints": waypoints}
        self._log(t, "recovery_started", f"stopped {t - b['since']:.1f} s behind a person who moved {b['moved']:.2f} m: back {rc['back_m']:g} m",
                  attempt=self.rec_attempts[key], person=[round(pos[0], 2), round(pos[1], 2)], side=side)
        cmd.v, cmd.omega = -rc["back_speed_mps"], 0.0
        cmd.state = f"{self.state} (recovery: backing)"

    def hud_fields(self, persons: list) -> dict:
        """The Phase 1 HUD fields that were left at -1 / NONE: commander, gesture reading, accepted gesture, pointed angle."""
        cmdr = next((p for p in persons if p.track_id == self.commander_pt), None)
        r = cmdr.reading if cmdr is not None else None
        any_stop = any(p.reading.command == "STOP" for p in persons)
        gesture = "STOP" if any_stop else (r.command if r is not None and r.command in ("POINT", "WAIT", "PROCEED") else "NONE")
        raw = "STOP" if any_stop else (r.frame_class if r is not None else "NONE")
        accepted = "WAIT" if self.waiting else (self.dialog.accepted if self.dialog.accepted != "NONE" else "NONE")
        angle = self.resolution.rel_deg if self.resolution is not None and self.resolution.rel_deg is not None else -1.0
        return {"commander_id": self.commander_360 if self.commander_360 is not None else -1, "gesture": gesture,
                "gesture_score": float(r.score) if r is not None and gesture == r.command else (1.0 if any_stop else 0.0),
                "gesture_raw": raw, "gesture_accepted": accepted, "point_angle_deg": float(angle)}

    def summary(self) -> dict:
        s = super().summary()
        s["v4"] = {"zoom_enabled": self.zoom.z["enabled"], "commander_changes": list(self.commander_changes),
                   "waited_s": round(self.waited_s, 3), "decisions": list(self.decisions), "route": list(self.route),
                   "safety_stops": self.safety_stops, "lie_detection": dict(self.ld), "recoveries": self.recoveries,
                   "checkpoint": {"enabled": bool(self.ld["checkpoint"]), "log": list(self.cp_log), "backtracks": self.cp_backtracks + len(self.nj_log),
                                  "next_junction_back": list(self.nj_log)}, "side_views": list(self.side_views)}
        return s


def roadmap_path(v4_cfg: dict) -> str:
    """The map the v4 controller uses: control.json -> roadmap (P7), else the v4 roadmap."""
    return v4_cfg.get("roadmap", V4_ROADMAP)


def load_roadmap(path: str = V4_ROADMAP) -> hc.Roadmap:
    return hc.Roadmap(hc.load_json(path))


def make_controller_v4(control_path="configs/v4/control.json", commander_path="configs/v4/commander.json",
                       roadmap_path_override: str | None = None) -> ControllerV4:
    base, v4 = load_control(control_path)
    road = roadmap_path_override or roadmap_path(v4)
    return ControllerV4(base, v4, cm.load_config(commander_path), hc.Roadmap(hc.load_json(road)))
