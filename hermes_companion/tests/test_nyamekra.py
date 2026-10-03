"""Nyamekra: one form, the largest repertoire, and meaning stays accurate."""
import importlib.util
import pathlib
import random

from hermes_companion.animation.characters import COMPANIONS, extra_flourishes
from hermes_companion.animation.nyamekra import (
    NYAMEKRA_MOVES, NYAMEKRA_PALETTES, SYMBOLS, nyamekra_flourishes, performance_space,
)
from hermes_companion.behavior.behavior_rules import CHAINS, CHAINS_BY_CATEGORY
from hermes_companion.behavior.move_grammar import FLOURISH_POSES, MoveGrammar, signature_of
from hermes_companion.core.state import State

_SCRIPT = pathlib.Path(__file__).resolve().parents[1] / "scripts" / "render_pose_sheet.py"
_spec = importlib.util.spec_from_file_location("render_pose_sheet", _SCRIPT)
_sheet = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_sheet)


def test_one_form_only():
    # every energy style is the same body; only the energy around it differs
    bodies = {tuple(sorted(v.items())) for v in NYAMEKRA_PALETTES.values()}
    assert len(bodies) == 1
    assert len(NYAMEKRA_PALETTES) == 10
    # unknown names fall back to the default energy, never a different being
    assert _sheet.signatures("nyamekra", "idle_bob", None) == \
        _sheet.signatures("nyamekra", "idle_bob", "anything-else")


def test_energy_styles_differ():
    sigs = {_sheet.signatures("nyamekra", "idle_bob", e) for e in NYAMEKRA_PALETTES}
    assert len(sigs) == len(NYAMEKRA_PALETTES)


def test_largest_repertoire_and_millions_of_performances():
    counts = {n: sum(len(v) for v in extra_flourishes(n).values()) for n in COMPANIONS}
    assert max(counts, key=counts.get) == "nyamekra"
    assert len(NYAMEKRA_MOVES) >= 90
    assert performance_space() >= 1_000_000


def test_every_symbol_is_channelled_by_every_gesture():
    names = set(NYAMEKRA_MOVES)
    for s in SYMBOLS:
        assert sum(1 for n in names if n.endswith("_" + s)) >= 8


def test_every_move_renders_distinctly():
    fallback = _sheet.signatures("nyamekra", _sheet.FALLBACK_PROBE)
    seen = {}
    for move in NYAMEKRA_MOVES:
        sig = _sheet.signatures("nyamekra", move)
        assert sig != fallback, move
        assert sig not in seen, (move, seen.get(sig))
        seen[sig] = move


def test_own_moves_never_carry_hermes_meaning():
    used = {s["pose"] for _k, (_st, steps) in list(CHAINS.items()) + list(CHAINS_BY_CATEGORY.items())
            for s in steps}
    assert not used & set(NYAMEKRA_MOVES)
    assert set(nyamekra_flourishes()) <= set(FLOURISH_POSES)


def test_signatures_survive_with_the_crow_repertoire():
    extra = nyamekra_flourishes()
    steps = [{"pose": "terminal_work", "duration_ms": 900}]
    for state, mood in ((State.CELEBRATING, "bright"), (State.FRUSTRATED, "uneasy"),
                        (State.IDLE, "calm"), (State.CODING, "focused")):
        allowed = set(FLOURISH_POSES[mood]) | set(extra.get(mood, ()))
        for seed in range(300):
            out = MoveGrammar(random.Random(seed), extra=extra).decorate(steps, state)
            assert signature_of(out) == [("terminal_work", 900)]
            assert {s["pose"] for s in out if s["role"] == "flourish"} <= allowed


def test_turnaround_sheet_scenes_exist():
    for move in ("commanding_presence", "cosmic_control", "storyteller_read",
                 "glyph_weave", "turn_back"):
        assert move in NYAMEKRA_MOVES


def test_faces_the_way_it_travels():
    from hermes_companion.renderer.smooth import FrameRenderer
    r = FrameRenderer("nyamekra", glow=False, squash=False)

    def beak_side(pose):
        a = r.frame(pose, 0.3).getchannel("A")
        mass = lambda x0, x1: sum(1 for y in range(55, 72) for x in range(x0, x1)
                                  if a.getpixel((x, y)) > 128)
        return "right" if mass(110, 140) > mass(60, 90) else "left"

    assert beak_side("idle_bob") == "right"
    assert beak_side("run_to_user") == "left"
    assert beak_side("return_home") == "left"


def test_expressions_follow_meaning():
    from hermes_companion.animation.nyamekra import EXPRESSIONS, expression_of
    assert len(EXPRESSIONS) == 9
    assert expression_of("terminal_work", "work", False) == "focused"
    assert expression_of("shock", "fail", False) == "sad"
    assert expression_of("wave", "approve", False) == "protective"
    assert expression_of("celebrate", "joy", False) == "joyful"
    assert expression_of("wing_spread", "joy", True) == "playful"
    assert expression_of("peeking", "curious", False) == "curious"
    assert expression_of("meditate", "calm", True) == "wise"
    assert expression_of("defense_shield", "fail", True) == "fierce"


def test_role_looks_only_on_real_hermes_work():
    from hermes_companion.animation.nyamekra import ROLE_OF, ROLE_TOOL
    engine = set(_sheet.engine_poses())
    assert set(ROLE_OF) <= engine            # every role is triggered by a real engine pose
    assert not set(ROLE_OF) & set(NYAMEKRA_MOVES)   # decoration never wears a role
    assert set(ROLE_OF.values()) <= set(ROLE_TOOL)
    tech, travel = (_sheet.signatures("nyamekra", p) for p in ("terminal_work", "web_scan"))
    assert tech != travel


def test_dynamic_poses_exist():
    for move in ("flight", "landing", "casting", "perch_crouch", "sprint_dash",
                 "defense_shield", "interact"):
        assert move in NYAMEKRA_MOVES


def test_sizes_render():
    from hermes_companion.renderer.smooth import FrameRenderer
    for scale, w in ((0.6, 120), (1.0, 200), (1.4, 280)):
        assert FrameRenderer("nyamekra", scale=scale).frame("idle_bob", 0.2).size[0] == w
