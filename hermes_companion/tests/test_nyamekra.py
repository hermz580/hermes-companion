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
    assert list(NYAMEKRA_PALETTES) == ["nyamekra"]
    # asking for any palette still draws the same being
    a = _sheet.signatures("nyamekra", "idle_bob", None)
    b = _sheet.signatures("nyamekra", "idle_bob", "anything-else")
    assert a == b


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
