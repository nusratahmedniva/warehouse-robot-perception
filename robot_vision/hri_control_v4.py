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
from dataclasses import dataclass, field

import commander_v4 as cm
import gesture_motion as gm
import hri_control as hc

DIRECTIONS = hc.DIRECTIONS
LIE_DEFAULTS = {"second_opinion": False, "reject_impossible": False, "backtrack": False, "max_opinions": 3}
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
        super().__init__(base_cfg, roadmap)

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
        self._new_junction()
        if hasattr(self, "zoom"):
            self.zoom.reset()

    def _new_junction(self) -> None:
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

    def _arrive(self, node, t):
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

    def _ask(self, t, cmd):
        super()._ask(t, cmd)
        self.ask_serial += 1
        if self.free_asks > 0:                                # a second view or a re-approach is not an unclear answer
            self.free_asks -= 1
            self.dialog.asks -= 1
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
        if choice.commander is None:
            self.commander_360 = None
            return "NONE"
        p = next(q for q in persons if q.track_id == choice.commander)
        self.commander_360 = self._link_360(p, inp)
        self._aim_at(p, inp)
        r = p.reading
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

    def _unasked(self, inp: TickInputV4) -> list:
        """Fresh 360 people with a track id not asked yet at this visit, nearest first (without track ids nobody can be told
        apart: no second opinion)."""
        out = [q for q in self._fresh_people(inp) if q.get("track_id", -1) >= 0 and q["track_id"] not in self.asked_360]
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
        self.tried.setdefault(self.node, set()).add(branch)
        self.last_choice = {"node": self.node, "branch": branch, "serial": self.ask_serial}
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

    def _start_reapproach(self, inp: TickInputV4) -> bool:
        """The commander is not the person the robot approached: go to the commander (once per junction)."""
        dv = self.v4["dialog"]
        if (not dv["reapproach_commander"] or self.reapproached or self.waiting or self.commander_360 is None
                or self.approached_360 is None or self.commander_360 == self.approached_360 or self.commander_since is None
                or inp.persons_time_s - self.commander_since < self.g["gesture_hold_s"] - 1e-6):
            return False
        tgt = next((q for q in self._fresh_people(inp) if q.get("track_id") == self.commander_360), None)
        if tgt is None:
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
            if self._start_reapproach(inp) or self._start_second_view(inp, cmd):
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
        # STOP of anybody in view stops the robot (the v3 rule reads TickInput.gesture)
        self._track_onsets(inp)
        persons = self._fresh_persons(inp)
        stop = any(p.reading.command == "STOP" for p in persons)
        inp.gesture, inp.gesture_time_s = ("STOP" if stop else "NONE"), inp.persons_time_s
        base = super().step(inp)
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
                   "safety_stops": self.safety_stops, "lie_detection": dict(self.ld)}
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
