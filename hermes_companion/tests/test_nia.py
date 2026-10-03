"""Nia: the biggest move set, and every extra move is pure body language."""
import importlib.util
import pathlib
import random

from hermes_companion.animation.characters import COMPANIONS, extra_flourishes
from hermes_companion.animation.nia import NIA_MOVES, NIA_PALETTES, nia_flourishes
from hermes_companion.behavior.behavior_engine import BehaviorEngine
from hermes_companion.behavior.behavior_rules import CHAINS, CHAINS_BY_CATEGORY
from hermes_companion.behavior.move_grammar import FLOURISH_POSES, MoveGrammar, signature_of
from hermes_companion.core.events import EventKind, SemanticEvent
from hermes_companion.core.state import State

_SCRIPT = pathlib.Path(__file__).resolve().parents[1] / "scripts" / "render_pose_sheet.py"
_spec = importlib.util.spec_from_file_location("render_pose_sheet", _SCRIPT)
_sheet = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_sheet)


def test_nia_outmoves_the_original_companions():
    shared = len(_sheet.engine_poses())
    counts = {name: shared + sum(len(v) for v in extra_flourishes(name).values())
              for name in COMPANIONS}
    for other in ("pet", "samurai", "astro", "herald"):
        assert counts["nia"] > counts[other]
    assert counts["nia"] >= shared + 20


def test_every_nia_move_is_distinct_on_every_palette():
    fallback = _sheet.signatures("nia", _sheet.FALLBACK_PROBE)
    for palette in NIA_PALETTES:
        seen = {}
        for move in NIA_MOVES:
            sig = _sheet.signatures("nia", move, palette)
            assert sig != fallback, (palette, move)
            assert sig not in seen, (palette, move, seen.get(sig))
            seen[sig] = move


def test_extra_moves_never_carry_hermes_meaning():
    used = {s["pose"] for _k, (_st, steps) in list(CHAINS.items()) + list(CHAINS_BY_CATEGORY.items())
            for s in steps}
    assert not used & set(NIA_MOVES)
    assert set(nia_flourishes()) <= set(FLOURISH_POSES)


def test_grammar_uses_extras_only_in_their_own_mood():
    extra = nia_flourishes()
    for state, mood in ((State.CELEBRATING, "bright"), (State.FRUSTRATED, "uneasy"),
                        (State.IDLE, "calm"), (State.CODING, "focused")):
        allowed = set(FLOURISH_POSES[mood]) | set(extra.get(mood, ()))
        steps = [{"pose": "nod", "duration_ms": 400}]
        for seed in range(300):
            out = MoveGrammar(random.Random(seed), extra=extra).decorate(steps, state)
            assert signature_of(out) == [("nod", 400)]
            assert {s["pose"] for s in out if s["role"] == "flourish"} <= allowed


def test_nia_engine_actually_dances():
    e = BehaviorEngine(seed=3, variety=True, clock=lambda: 0.0,
                       extra_flourishes=extra_flourishes("nia"))
    seen = set()
    for _ in range(200):
        chain = e.handle(SemanticEvent(EventKind.TASK_COMPLETE))
        seen |= set(chain.poses)
        e._cooldown_until.clear()
    assert seen & set(nia_flourishes()["bright"])
