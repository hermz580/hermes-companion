"""MVP + category-flavored behavior chains (spec rev1 §29 + §32 walking skeleton).

Each EventKind maps to a (semantic state, chain of atomic steps). Steps may
carry a `move` so the renderer knows to translate the pet across the screen
(§10) rather than play a static pose.

v0.3 — MOVE EXPANSION:
- New vertical movement types (hop / leap / bounce / tip / creep) so the pet
  can move in 2D, not just dash right/left.
- New category flavors (web, terminal, file, development, media, memory,
  planning, delegation, design, audio, scheduling, learning, system, general)
  with distinct work + celebration + failure chains.
- TOOL_PROGRESS chain (was defined in priorities but had no chain — P5 events
  fell through silently).
- Richer idle progression + new emotes (shake_head, shrug, scratch_head,
  think, point, look_up, look_down, dance, yawn, stretch_lazy, check_watch,
  excited, smug, sneak).
Category-aware chains (spec §9): TOOL_STARTED / TOOL_FINISHED select a chain
by the tool's semantic category. Deterministic: the same (kind, category)
always yields the same chain, so the engine's determinism proof (§34.9) is
preserved — category is part of the deterministic key, never randomness.
"""
from __future__ import annotations

from hermes_companion.core.events import EventKind
from hermes_companion.core.state import State


def _mv(pose: str, ms: int, move: dict | None = None) -> dict:
    return {"pose": pose, "duration_ms": ms, "move": move}


# ---------------------------------------------------------------------------
# Movement primitives (spec §14 / §15). dx = horizontal, dy = vertical (up -).
# ---------------------------------------------------------------------------
DASH_RIGHT = {"type": "dash", "dx": +520, "dy": 0, "duration_ms": 480, "easing": "easeOutCubic"}
DASH_LONG = {"type": "dash", "dx": +640, "dy": 0, "duration_ms": 540, "easing": "easeOutCubic"}
RUN_RIGHT = {"type": "run", "dx": +520, "dy": 0, "duration_ms": 900, "easing": "easeInOutCubic"}
WALK_RIGHT = {"type": "walk", "dx": +260, "dy": 0, "duration_ms": 950, "easing": "easeInOutQuad"}
WALK_HOME = {"type": "walk", "dx": -520, "dy": 0, "duration_ms": 1200, "easing": "easeInOutQuad"}
RUN_LEFT = {"type": "run", "dx": -320, "dy": 0, "duration_ms": 800, "easing": "easeInOutCubic"}
RUN_HOME = {"type": "run", "dx": -640, "dy": 0, "duration_ms": 1000, "easing": "easeInOutCubic"}

# v0.3: vertical / 2-D moves.
HOP = {"type": "hop", "dx": +40, "dy": -110, "duration_ms": 420, "easing": "bounce"}
LEAP = {"type": "leap", "dx": +180, "dy": -150, "duration_ms": 560, "easing": "bounce"}
BOUNCE = {"type": "bounce", "dx": 0, "dy": -90, "duration_ms": 360, "easing": "bounce"}
TIP = {"type": "tip", "dx": +120, "dy": -30, "duration_ms": 700, "easing": "easeInOutQuad"}
CREEP = {"type": "creep", "dx": +200, "dy": 0, "duration_ms": 1500, "easing": "easeInOutQuad"}
SPRINT = {"type": "sprint", "dx": +800, "dy": 0, "duration_ms": 650, "easing": "easeInOutCubic"}
FLY_UP = {"type": "fly", "dx": 0, "dy": -140, "duration_ms": 700, "easing": "easeOutQuad"}
FLY_DOWN = {"type": "fly", "dx": 0, "dy": +140, "duration_ms": 700, "easing": "easeInQuad"}

# ---------------------------------------------------------------------------
# v0.4: 3D move primitives
# ---------------------------------------------------------------------------
DRIFT = {"type": "drift", "dx": +320, "dy": -40, "duration_ms": 2000, "easing": "easeInOutQuad"}
POP = {"type": "pop", "dx": 0, "dy": -200, "duration_ms": 300, "easing": "bounce"}
ORBIT = {"type": "orbit", "dx": 0, "dy": 0, "duration_ms": 2400, "easing": "easeInOutQuad"}
FOLD = {"type": "fold", "dx": 0, "dy": 0, "duration_ms": 1200, "easing": "easeIn"}
UNFOLD = {"type": "unfold", "dx": 0, "dy": 0, "duration_ms": 1200, "easing": "easeOut"}
SHIMMER = {"type": "shimmer", "dx": 0, "dy": 0, "duration_ms": 800, "easing": "easeOutQuad"}

# --- martial / energy vocabulary (shapes from movement/paths.py) ------------
# Every one of these is attached to a real event, and each carries only the
# meaning that event actually evidences. None of them claims an outcome: the
# strike is "a tool started", the guard is "blocked, waiting on the user", the
# surge is "permission was granted". Nothing here means success or verification.
STRIKE = {"type": "overshoot", "dx": +520, "dy": 0, "duration_ms": 480, "easing": "easeOutCubic"}
EVADE_ROLL = {"type": "orbit", "dx": +200, "dy": -70, "duration_ms": 560, "easing": "easeInOutQuad"}
GUARD = {"type": "hover", "dx": 0, "dy": -12, "duration_ms": 900, "easing": "easeInOutSine"}
SURGE = {"type": "pop", "dx": 0, "dy": -110, "duration_ms": 520, "easing": "easeOutCubic"}
CHANNEL = {"type": "figure8", "dx": +140, "dy": -40, "duration_ms": 900, "easing": "easeInOutSine"}

# ---------------------------------------------------------------------------
# Generic chains (fallback when no category flavor exists).
# ---------------------------------------------------------------------------
CHAINS: dict[EventKind, tuple[State, list[dict]]] = {
    EventKind.TYPING_STARTED: (State.LISTENING, [
        _mv("look_at_input", 900), _mv("watch", 900),
    ]),
    EventKind.TYPING_STOPPED: (State.CURIOUS, [_mv("look_at_user", 700)]),
    EventKind.PROMPT_SUBMITTED: (State.URGENT, [
        _mv("jump", 450), _mv("attention", 500),
    ]),
    EventKind.AGENT_STARTED: (State.WORKING, [
        _mv("crack_knuckles", 600), _mv("run_to_workspace", 700, RUN_RIGHT),
    ]),
    EventKind.TOOL_STARTED: (State.WORKING, [
        _mv("notice", 400), _mv("dash_to_workspace", 480, STRIKE),
        _mv("work", 1400),
    ]),
    # v0.3: progress events now have a chain (P5 "working" pulse).
    EventKind.TOOL_PROGRESS: (State.WORKING, [
        _mv("lean_work", 500), _mv("work", 900),
    ]),
    EventKind.TOOL_FINISHED: (State.CELEBRATING, [
        _mv("close_workstation", 500), _mv("celebrate", 800),
        _mv("return_home", 1200, WALK_HOME),
    ]),
    EventKind.TOOL_FAILED: (State.FRUSTRATED, [
        _mv("shock", 300), _mv("fall", 600), _mv("sneak", 560, EVADE_ROLL),
        _mv("recover", 500),
        _mv("inspect", 800), _mv("huff", 1200),
    ]),
    EventKind.APPROVAL_REQUIRED: (State.CALLING_USER, [
        _mv("wake", 300), _mv("panic", 400), _mv("run_to_user", 800, RUN_LEFT),
        _mv("wave", 900), _mv("wait", 900, GUARD),
    ]),
    EventKind.APPROVAL_APPROVED: (State.WORKING, [
        _mv("nod", 400), _mv("hop", 520, SURGE), _mv("wait", 700),
    ]),
    EventKind.APPROVAL_REJECTED: (State.IDLE, [
        _mv("nod", 400), _mv("shrug", 600), _mv("discard", 600),
    ]),
    EventKind.TASK_COMPLETE: (State.CELEBRATING, [
        _mv("leap", 560, LEAP), _mv("celebrate", 800), _mv("double_jump", 700),
        _mv("return_home", 1200, WALK_HOME),
    ]),
    EventKind.SUBAGENT_STARTED: (State.THINKING, [
        _mv("open_portal", 700), _mv("channel", 900, CHANNEL),
        _mv("orb_exits", 800),
    ]),
    EventKind.SUBAGENT_FINISHED: (State.CELEBRATING, [
        _mv("orb_returns", 800), _mv("absorb", 500), _mv("fly_up", 700, FLY_UP),
        _mv("fly_down", 700, FLY_DOWN), _mv("excited", 700),
    ]),
    EventKind.SUBAGENT_FAILED: (State.FRUSTRATED, [
        _mv("shock", 300), _mv("sit_back", 600), _mv("huff", 600),
    ]),
    EventKind.AGENT_IDLE: (State.IDLE, [_mv("idle_bob", 2000)]),
    EventKind.USER_RETURNED: (State.CURIOUS, [
        _mv("wake", 300), _mv("stretch", 700), _mv("wave", 900),
    ]),
}

# ---------------------------------------------------------------------------
# Category-aware tool chains (spec §9) — the expressive core. v0.3 adds
# design / audio / scheduling / learning / system flavors.
# ---------------------------------------------------------------------------
CATEGORY_TOOL_STARTED: dict[str, tuple[State, list[dict]]] = {
    "terminal": (State.WORKING, [
        _mv("notice", 350), _mv("dash_to_workspace", 500, DASH_RIGHT),
        _mv("terminal_work", 1700),
    ]),
    "browser": (State.WORKING, [
        _mv("notice", 350), _mv("look_at_input", 850), _mv("web_scan", 1500),
    ]),
    "docs": (State.READING, [
        _mv("notice", 350), _mv("read", 1500), _mv("file_organize", 1200),
    ]),
    "sheets": (State.WORKING, [
        _mv("notice", 350), _mv("file_organize", 900), _mv("work", 1400),
    ]),
    "communication": (State.CALLING_USER, [
        _mv("notice", 300), _mv("wave", 900), _mv("wait", 900),
    ]),
    "maps": (State.THINKING, [
        _mv("notice", 350), _mv("look_up", 700), _mv("run_to_workspace", 900, RUN_RIGHT),
    ]),
    "desktop": (State.WORKING, [
        _mv("notice", 350), _mv("crack_knuckles", 700), _mv("work", 1400),
    ]),
    "development": (State.WORKING, [
        _mv("notice", 350), _mv("dash_to_workspace", 560, DASH_LONG),
        _mv("dev_merge", 1800),
    ]),
    "media": (State.WORKING, [
        _mv("notice", 350), _mv("run_to_workspace", 850, RUN_RIGHT),
        _mv("media_paint", 1600),
    ]),
    "memory": (State.THINKING, [
        _mv("notice", 350), _mv("walk_to_workspace", 900, WALK_RIGHT),
        _mv("memory_vault", 1500),
    ]),
    "planning": (State.PLANNING, [
        _mv("notice", 350), _mv("crack_knuckles", 700),
        _mv("work", 1500),
    ]),
    "delegation": (State.THINKING, [
        _mv("open_portal", 700), _mv("orb_exits", 900), _mv("wait", 900),
    ]),
    # v0.3 new category flavors.
    "design": (State.WORKING, [
        _mv("notice", 350), _mv("run_to_workspace", 800, RUN_RIGHT),
        _mv("design_draft", 1600),
    ]),
    "audio": (State.LISTENING, [
        _mv("notice", 350), _mv("tip_to_workspace", 700, TIP),
        _mv("audio_tune", 1500),
    ]),
    "scheduling": (State.PLANNING, [
        _mv("notice", 350), _mv("check_watch", 500),
        _mv("file_organize", 1500),
    ]),
    "learning": (State.READING, [
        _mv("notice", 350), _mv("walk_to_workspace", 900, WALK_RIGHT),
        _mv("read", 1500),
    ]),
    "general": (State.WORKING, [
        _mv("notice", 350), _mv("run_to_workspace", 800, RUN_RIGHT),
        _mv("work", 1400),
    ]),
}

CATEGORY_TOOL_FINISHED: dict[str, tuple[State, list[dict]]] = {
    "terminal": (State.CELEBRATING, [
        _mv("close_workstation", 500), _mv("celebrate", 800),
        _mv("return_home", 1200, WALK_HOME),
    ]),
    "browser": (State.CELEBRATING, [
        _mv("close_workstation", 450), _mv("double_jump", 850),
        _mv("return_home", 1150, WALK_HOME),
    ]),
    "docs": (State.CELEBRATING, [
        _mv("close_workstation", 500), _mv("nod", 400),
        _mv("return_home", 1100, WALK_HOME),
    ]),
    "sheets": (State.CELEBRATING, [
        _mv("check_watch", 400), _mv("celebrate", 800),
        _mv("return_home", 1100, WALK_HOME),
    ]),
    "communication": (State.CELEBRATING, [
        _mv("wave", 900), _mv("nod", 400), _mv("return_home", 1000, WALK_HOME),
    ]),
    "maps": (State.CELEBRATING, [
        _mv("double_jump", 800), _mv("return_home", 1200, WALK_HOME),
    ]),
    "desktop": (State.CELEBRATING, [
        _mv("close_workstation", 450), _mv("celebrate", 800),
        _mv("return_home", 1200, WALK_HOME),
    ]),
    "development": (State.CELEBRATING, [
        _mv("close_workstation", 450), _mv("spin", 900),
        _mv("return_home", 1200, WALK_HOME),
    ]),
    "media": (State.CELEBRATING, [
        _mv("close_workstation", 500), _mv("bounce", 900, BOUNCE),
        _mv("celebrate", 500), _mv("return_home", 1200, WALK_HOME),
    ]),
    "memory": (State.CELEBRATING, [
        _mv("close_workstation", 500), _mv("nod", 400),
        _mv("return_home", 1200, WALK_HOME),
    ]),
    "delegation": (State.CELEBRATING, [
        _mv("orb_returns", 800), _mv("absorb", 500),
        _mv("celebrate", 600), _mv("return_home", 1200, WALK_HOME),
    ]),
    "planning": (State.CELEBRATING, [
        _mv("close_workstation", 450), _mv("celebrate", 800),
        _mv("return_home", 1200, WALK_HOME),
    ]),
    # v0.3 new finish flavors.
    "design": (State.CELEBRATING, [
        _mv("close_workstation", 450), _mv("excited", 700),
        _mv("spin", 800), _mv("return_home", 1200, WALK_HOME),
    ]),
    "audio": (State.CELEBRATING, [
        _mv("close_workstation", 450), _mv("double_jump", 800),
        _mv("return_home", 1200, WALK_HOME),
    ]),
    "scheduling": (State.CELEBRATING, [
        _mv("check_watch", 400), _mv("nod", 400),
        _mv("return_home", 1100, WALK_HOME),
    ]),
    "learning": (State.CELEBRATING, [
        _mv("close_workstation", 450), _mv("nod", 400), _mv("look_up", 500),
        _mv("return_home", 1100, WALK_HOME),
    ]),
    "general": (State.CELEBRATING, [
        _mv("close_workstation", 500), _mv("celebrate", 800),
        _mv("return_home", 1200, WALK_HOME),
    ]),
}

# v0.3: per-category failure chains (spec §22 severity ladder).
CATEGORY_TOOL_FAILED: dict[str, tuple[State, list[dict]]] = {
    "terminal": (State.FRUSTRATED, [
        _mv("shock", 300), _mv("shake_head", 600),
        _mv("inspect", 800), _mv("huff", 1200),
    ]),
    "browser": (State.CONFUSED, [
        _mv("shock", 300), _mv("look_up", 500), _mv("shrug", 600),
        _mv("think", 900),
    ]),
    "docs": (State.CONFUSED, [
        _mv("shock", 300), _mv("scratch_head", 600),
        _mv("inspect", 800), _mv("think", 900),
    ]),
    "sheets": (State.FRUSTRATED, [
        _mv("shock", 300), _mv("shake_head", 500),
        _mv("inspect", 800), _mv("huff", 1200),
    ]),
    "communication": (State.CALLING_USER, [
        _mv("panic", 400), _mv("wave", 900), _mv("wait", 900),
    ]),
    "maps": (State.CONFUSED, [
        _mv("shock", 300), _mv("look_up", 500), _mv("think", 900),
    ]),
    "desktop": (State.FRUSTRATED, [
        _mv("shock", 300), _mv("fall", 600), _mv("recover", 500),
        _mv("inspect", 800), _mv("huff", 1200),
    ]),
    "development": (State.FRUSTRATED, [
        _mv("shock", 300), _mv("fall", 600), _mv("recover", 500),
        _mv("inspect", 800), _mv("huff", 1200), _mv("nod", 400),
    ]),
    "media": (State.CONFUSED, [
        _mv("shock", 300), _mv("shake_head", 500),
        _mv("scratch_head", 600), _mv("think", 900),
    ]),
    "memory": (State.THINKING, [
        _mv("shock", 300), _mv("think", 700), _mv("look_up", 500),
        _mv("think", 900),
    ]),
    "general": (State.FRUSTRATED, [
        _mv("shock", 300), _mv("shake_head", 500), _mv("huff", 1200),
    ]),
}

# Idle progression (spec §14, compressed for demo): elapsed → pose.
# v0.3: richer idle life — look, sit, play, dance, yawn, sleep.
IDLE_PROGRESSION: list[tuple[float, str, int]] = [
    (30.0, "look_around", 1500),
    (60.0, "stretch_lazy", 1600),
    (120.0, "sit", 2500),
    (180.0, "check_watch", 1200),
    (240.0, "play_with_object", 3000),
    (300.0, "dance", 2200),
    (420.0, "yawn", 1500),
    (600.0, "sleep", 0),
]

# ---------------------------------------------------------------------------
# v0.4 EMOTIONAL ARC CHAINS — pose selection by emotional state, not just category
# ---------------------------------------------------------------------------
# Each emotional arc is a sequence of poses that tells a story:
# curiosity → focus → joy → frustration → rest → interaction
# These chains give the pet a *personality arc* across its day.

EMOTIONAL_ARCS: dict[str, list[str]] = {
    # When a new task appears: curiosity → focus → work
    "task_birth": ["tilt", "peeking", "head_tilt", "notice", "deep_gaze"],
    # When something is working: focus → engagement
    "task_flow": ["brow_furrow", "screen_scan", "chin_stroke",
                   "finger_tap", "deep_gaze"],
    # When task completes: joy celebration
    "task_done": ["eyebrow_raise", "full_bounce", "spin_joy",
                   "wiggle", "celebrate"],
    # When task fails: frustration arc
    "task_failed": ["arm_flap", "sit_back", "huff", "desk_bonk",
                     "growl", "huff"],
    # When idle too long: rest arc
    "resting": ["head_drop", "sleepy_nod", "curl_up", "chin_on_paws"],
    # When user returns: interaction arc
    "user_back": ["wave_gentle", "beckon", "wave_excited", "come_here"],
    # Curiosity about something interesting
    "curious": ["tilt", "periscope", "lip_quirk", "eyebrow_raise"],
    # Deep focus (coding, analyzing)
    "focused": ["deep_gaze", "brow_furrow", "chin_stroke",
                 "screen_scan"],
    # Joyful celebration
    "joyful": ["eyebrow_raise", "full_bounce", "leap_double_joy",
                "spin_joy", "wiggle"],
    # Frustration
    "frustrated": ["arm_flap", "huff", "growl", "sit_back"],
    # Restful
    "restful": ["head_drop", "soft_blink", "curl_up", "chin_on_paws"],
    # Playful
    "playful": ["peeking", "tilt", "skip", "drift", "pop"],
}

# v0.4: 3D move primitives (drift, pop, orbit, fold, unfold, shimmer)
# Defined above near the movement primitives section.
MOVES_3D = {}

# v0.4: Move the pet across the screen with 3D moves instead of
# simple dash/walk
MOVES_3D_REPLACE: dict[str, dict] = {
    "orbit": ORBIT,
    "fold": FOLD,
    "unfold": UNFOLD,
    "shimmer": SHIMMER,
    "strike": STRIKE,
    "evade_roll": EVADE_ROLL,
    "guard": GUARD,
    "surge": SURGE,
    "channel": CHANNEL,
}

# Category chains updated with v0.4 emotional depth
CATEGORY_TOOL_STARTED["general"] = (State.WORKING, [
    _mv("notice", 350), _mv("tilt", 500),
    _mv("run_to_workspace", 800, DRIFT), _mv("work", 1400),
])

CATEGORY_TOOL_STARTED["terminal"] = (State.WORKING, [
    _mv("notice", 350), _mv("head_tilt", 400),
    _mv("dash_to_workspace", 500, DASH_RIGHT),
    _mv("terminal_work", 1700),
])

# v0.4: category chains now include emotional entry poses
CATEGORY_TOOL_FINISHED["terminal"] = (State.CELEBRATING, [
    _mv("close_workstation", 500), _mv("eyebrow_raise", 300),
    _mv("full_bounce", 500), _mv("celebrate", 800),
    _mv("return_home", 1200, WALK_HOME),
])

CATEGORY_TOOL_FINISHED["browser"] = (State.CELEBRATING, [
    _mv("close_workstation", 450), _mv("leap_double_joy", 800),
    _mv("return_home", 1150, WALK_HOME),
])

CATEGORY_TOOL_FINISHED["development"] = (State.CELEBRATING, [
    _mv("close_workstation", 450), _mv("spin_joy", 900),
    _mv("return_home", 1200, WALK_HOME),
])

# v0.4: failure chains now have emotional arcs
CATEGORY_TOOL_FAILED["terminal"] = (State.FRUSTRATED, [
    _mv("shock", 300), _mv("arm_flap", 500),
    _mv("sit_back", 600), _mv("inspect", 800),
    _mv("huff", 1200),
])

CATEGORY_TOOL_FAILED["browser"] = (State.CONFUSED, [
    _mv("shock", 300), _mv("peeking", 500), _mv("squint", 600),
    _mv("head_tilt", 400), _mv("think", 900),
])

CATEGORY_TOOL_FAILED["development"] = (State.FRUSTRATED, [
    _mv("shock", 300), _mv("arm_flap", 500), _mv("sit_back", 600),
    _mv("inspect", 800), _mv("huff", 1200), _mv("nod", 400),
])

# v0.4: idle progression now includes emotional arc poses
IDLE_PROGRESSION = [
    (15.0, "tilt", 1200),
    (30.0, "look_around", 1500),
    (45.0, "peeking", 1000),
    (60.0, "stretch_lazy", 1600),
    (90.0, "head_drop", 2000),
    (120.0, "sit", 2500),
    (150.0, "check_watch", 1200),
    (180.0, "play_with_object", 3000),
    (210.0, "dance", 2200),
    (240.0, "yawn", 1500),
    (300.0, "sleep", 0),
]

# ---------------------------------------------------------------------------
# v0.5 — repertoire expansion.
#
# Three problems, all of them "the sprite has less range than it appears to":
#   1. six movement types were drawable but no chain ever asked for them
#      (creep, sprint, hop, shimmer, pounce, zigzag were unreachable),
#   2. some tool categories animated IDENTICALLY to unrelated ones,
#   3. six categories had no failure animation at all, so a failed calendar
#      call or a failed delegation rendered as nothing happening.
#
# Nothing here changes what a chain may CLAIM: these are entry/exit flavour and
# failure reactions only. Success and verification stay where they were.
# ---------------------------------------------------------------------------
POUNCE = {"type": "pounce", "dx": +320, "dy": -130, "duration_ms": 460, "easing": "easeInQuad"}
ZIGZAG = {"type": "zigzag", "dx": +300, "dy": -34, "duration_ms": 900, "easing": "easeInOutQuad"}
PACE = {"type": "creep", "dx": +220, "dy": 0, "duration_ms": 1500, "easing": "easeInOutQuad"}

# The one event with no chain at all. Idle says only "nothing is happening" -
# no work, no progress, no outcome - which is exactly what it evidences.
CHAINS[EventKind.IDLE] = (State.IDLE, [
    _mv("look_around", 1500), _mv("stretch_lazy", 1400), _mv("tilt", 1200, HOP),
])

# De-duplicate: different tools that did different work must not play the same
# animation. These pairs/triples previously rendered identically.
CATEGORY_TOOL_FINISHED["desktop"] = (State.CELEBRATING, [
    _mv("close_workstation", 450), _mv("spin", 800),
    _mv("return_home", 1200, WALK_HOME),
])
CATEGORY_TOOL_FINISHED["planning"] = (State.CELEBRATING, [
    _mv("check_watch", 400), _mv("nod", 400), _mv("smug", 600),
    _mv("return_home", 1200, WALK_HOME),
])
CATEGORY_TOOL_FINISHED["general"] = (State.CELEBRATING, [
    _mv("close_workstation", 500), _mv("shrug", 500),
    _mv("return_home", 1200, WALK_HOME),
])
CATEGORY_TOOL_FINISHED["docs"] = (State.CELEBRATING, [
    _mv("close_workstation", 500), _mv("nod", 400), _mv("look_up", 500, HOP),
    _mv("return_home", 1100, WALK_HOME),
])
CATEGORY_TOOL_FINISHED["memory"] = (State.CELEBRATING, [
    _mv("close_workstation", 500), _mv("point", 500), _mv("excited", 700),
    _mv("return_home", 1200, WALK_HOME),
])

# Reach the movement types that had no caller, on categories where the motion
# is the honest description of the work.
CATEGORY_TOOL_STARTED["browser"] = (State.WORKING, [
    _mv("notice", 350), _mv("leap", 460, POUNCE), _mv("work", 1400),
])
CATEGORY_TOOL_STARTED["scheduling"] = (State.PLANNING, [
    _mv("notice", 350), _mv("sprint_to_workspace", 600, SPRINT),
    _mv("file_organize", 1500),
])
CATEGORY_TOOL_STARTED["learning"] = (State.READING, [
    _mv("notice", 350), _mv("walk_to_workspace", 1500, PACE), _mv("read", 1500),
])
# desktop and planning shared a start long enough to look like the same tool.
CATEGORY_TOOL_STARTED["planning"] = (State.PLANNING, [
    _mv("notice", 350), _mv("crack_knuckles", 700), _mv("head_tilt", 500),
    _mv("work", 1500),
])

# The six categories that had no failure animation. Each one fails in a way
# that reads as its own kind of "that did not work" - no celebration, no
# success, and no pretending a repair began.
CATEGORY_TOOL_FAILED["audio"] = (State.CONFUSED, [
    _mv("shock", 300), _mv("head_tilt", 500), _mv("squint", 600),
    _mv("think", 700, SHIMMER),
])
CATEGORY_TOOL_FAILED["delegation"] = (State.FRUSTRATED, [
    _mv("shock", 300), _mv("arm_flap", 500), _mv("sit_back", 600),
    _mv("huff", 1200),
])
CATEGORY_TOOL_FAILED["design"] = (State.CONFUSED, [
    _mv("shock", 300), _mv("scratch_head", 600), _mv("shrug", 600),
    _mv("think", 900, ZIGZAG),
])
CATEGORY_TOOL_FAILED["learning"] = (State.THINKING, [
    _mv("shock", 300), _mv("look_up", 500), _mv("think", 700),
    _mv("nod", 600, PACE),
])
CATEGORY_TOOL_FAILED["planning"] = (State.FRUSTRATED, [
    _mv("shock", 300), _mv("shake_head", 500), _mv("inspect", 800),
    _mv("huff", 1200, ZIGZAG),
])
CATEGORY_TOOL_FAILED["scheduling"] = (State.CONFUSED, [
    _mv("shock", 300), _mv("check_watch", 500), _mv("shrug", 600),
    _mv("think", 900, PACE),
])

# Build the lookup only after every category override above is final.  Building
# this index earlier captured stale tuple objects for overridden categories.
CHAINS_BY_CATEGORY: dict[tuple[EventKind, str], tuple[State, list[dict]]] = {
    (kind, category): spec
    for kind, specs in (
        (EventKind.TOOL_STARTED, CATEGORY_TOOL_STARTED),
        (EventKind.TOOL_FINISHED, CATEGORY_TOOL_FINISHED),
        (EventKind.TOOL_FAILED, CATEGORY_TOOL_FAILED),
    )
    for category, spec in specs.items()
}
