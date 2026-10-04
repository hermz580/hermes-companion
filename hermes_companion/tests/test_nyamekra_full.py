"""Nyamekra uses its whole repertoire, and every part of it means something."""
from hermes_companion.animation.characters import traits
from hermes_companion.animation.nyamekra import (
    CATEGORY_SYMBOLS, GESTURES, NYAMEKRA_MOVES, SYMBOLS, VOICE,
)
from hermes_companion.behavior.behavior_engine import BehaviorEngine
from hermes_companion.core.curiosity import CuriosityModel, Observation, Seen
from hermes_companion.core.events import EventKind, SemanticEvent
from hermes_companion.renderer.voice import SAY, Voice

T = traits("nyamekra")


def _engine(seed=1):
    clock = [0.0]
    e = BehaviorEngine(seed=seed, variety=True, clock=lambda: clock[0],
                       extra_flourishes=T["extra_flourishes"], flourish_hints=T["flourish_hints"])
    return e, clock


def _symbols(poses):
    """Symbols channelled by gesture moves (e.g. 'bless_pyramid' -> 'pyramid')."""
    out = set()
    for p in poses:
        gesture, _, symbol = p.partition("_")
        if gesture in GESTURES and symbol in SYMBOLS:
            out.add(symbol)
    return out


def test_symbols_follow_the_kind_of_work():
    for category, tool, kind in (("terminal", "terminal", EventKind.TOOL_STARTED),
                                 ("web", "web_search", EventKind.TOOL_STARTED),
                                 ("memory", "memory", EventKind.TOOL_FINISHED)):
        hits = total = 0
        for seed in range(80):
            e, _ = _engine(seed)
            chain = e.handle(SemanticEvent(kind, tool=tool, category=category))
            syms = _symbols(chain.poses)
            total += len(syms)
            hits += len(syms & set(CATEGORY_SYMBOLS[category]))
        assert total and hits / total > 0.7, (category, hits, total)


def test_helpers_channel_delegation_symbols():
    syms = set()
    for seed in range(60):
        e, _ = _engine(seed)
        syms |= _symbols(e.handle(SemanticEvent(EventKind.SUBAGENT_STARTED, category="general")).poses)
    assert syms and syms <= set(CATEGORY_SYMBOLS["delegation"]) | {"adinkra", "baobab"}


def test_quiet_time_uses_its_own_calm_moves():
    e, _ = _engine(3)
    poses = []
    for _ in range(400):
        p = e.idle_tick(1.0)
        if p:
            poses.append(p)
    calm = set(T["extra_flourishes"]["calm"])
    assert any(p in calm for p in poses)
    assert poses[-1] == "sleep"                          # still falls asleep in the end


def test_curiosity_answers_in_its_own_body_language():
    m = CuriosityModel(seed=5)
    m.own_moves = T["curious_moves"]
    seen = set()
    for i in range(80):
        r = m.observe(Observation(Seen.CURSOR_NEAR_PET, i * 60.0, 5, 5), "quiet")
        if r:
            seen |= {s["pose"] for s in r.steps}
    assert seen & set(T["curious_moves"])


def test_voice_keeps_meaning_but_speaks_as_nyamekra():
    assert set(VOICE) <= set(SAY)
    shown = []
    v = Voice(shown.append, lines=T["voice"])
    v.on_attention("complete", "Task complete")
    v.on_attention("working", "Working with terminal")    # truthful label kept
    assert shown == ["Done. Every path leads here.", "Working with terminal…"]
    assert T["greeting"]
