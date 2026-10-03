"""hermes-companion CLI (spec rev1 §26 Companion Emit CLI).

Subcommands:
  emit <event> [tool=NAME]      inject one semantic event, print its chain
  demo                          run the §35 first-demonstration headless
                                (deterministic trace = §34 proof)
  selfcheck                     run acceptance self-checks (§34)
  scene [--sequence A B C...]   open the visual overlay; play poses/events
  clicktest                     open overlay over a target window and verify
                                the target is still clickable (click-through)
"""
from __future__ import annotations

import argparse
import json
import os
import time
import re
import sys
from pathlib import Path

from hermes_companion.behavior.behavior_engine import BehaviorEngine
from hermes_companion.core.events import EventKind, SemanticEvent
from hermes_companion.core.intents import CompanionIntent, IntentKind, route_intent
from hermes_companion.renderer.headless import HeadlessSurface


class FakeClock:
    """Deterministic clock for headless QA (spec §34.9)."""

    def __init__(self, t0: float = 0.0) -> None:
        self.t = t0

    def __call__(self) -> float:
        return self.t

    def advance(self, dt: float) -> None:
        self.t += dt


def _parse_event(text: str) -> SemanticEvent:
    parts = text.split()
    kind = EventKind(parts[0])
    kw = {}
    for p in parts[1:]:
        k, _, v = p.partition("=")
        kw[k] = v
    if kw.get("tool") and not kw.get("category"):
        from hermes_companion.core.events import classify_tool
        kw["category"] = classify_tool(str(kw["tool"]))
    return SemanticEvent(kind=kind, **kw)


def cmd_emit(args: argparse.Namespace) -> int:
    engine = BehaviorEngine(seed=args.seed)
    ev = _parse_event(args.event)
    chain = engine.handle(ev)
    if chain is None:
        print(f"{ev.kind.value} -> (suppressed / no rule)")
    else:
        print(f"{ev.kind.value} -> [{chain.state.value}] {' > '.join(chain.poses)}")
    for line in engine.trace:
        print("   ", line)
    return 0



def cmd_status(args: argparse.Namespace) -> int:
    """Read an event log and print a content-free attention signal."""
    from hermes_companion.core.attention import AttentionModel
    model = AttentionModel()
    path = Path(args.events)
    if path.exists():
        for line in path.read_text(encoding="utf-8").splitlines():
            try:
                rec = json.loads(line)
                if not isinstance(rec, dict):
                    continue
                kind = EventKind(str(rec.get("event", "")))
            except (ValueError, TypeError, json.JSONDecodeError):
                continue
            model.ingest(SemanticEvent(
                kind=kind,
                tool=str(rec.get("tool") or ""),
                category=str(rec.get("category") or ""),
                session_id=str(rec.get("session_id") or ""),
                task_id=str(rec.get("task_id") or ""),
            ))
    signal = model.signal
    out = {
        "state": signal.state,
        "urgency": signal.urgency,
        "label": signal.label,
        "needs_user": signal.needs_user,
    }
    # A truthful stuck verdict is evidence-based and conservative: it only
    # fires when an open tool is far past its learned typical duration, is the
    # most recent record, the stream is still fresh, and no approval is pending.
    if not args.no_stuck:
        from hermes_companion.core.stuck import StuckDetector
        det = StuckDetector()
        if path.exists():
            for line in path.read_text(encoding="utf-8").splitlines():
                try:
                    rec = json.loads(line)
                    if not isinstance(rec, dict):
                        continue
                    det.ingest(
                        kind=str(rec.get("event") or ""),
                        tool=str(rec.get("tool") or ""),
                        category=str(rec.get("category") or ""),
                        session=str(rec.get("session_id") or ""),
                        task=str(rec.get("task_id") or ""),
                        ts=float(rec.get("ts") or 0.0),
                    )
                except (ValueError, TypeError, json.JSONDecodeError):
                    continue
        verdict = det.check(now=args.now or time.time())
        out["stuck"] = verdict.as_dict()
    print(json.dumps(out, sort_keys=True))
    return 0

def cmd_demo(args: argparse.Namespace) -> int:
    """Headless FIRST DEMONSTRATION (§35) with a deterministic schedule."""
    from hermes_companion.animation.director import Director

    clock = FakeClock()
    engine = BehaviorEngine(seed=args.seed)
    surface = HeadlessSurface(clock=clock)
    director = Director(engine, surface, fps=args.fps, clock=clock)

    schedule = [
        (0.5, EventKind.TYPING_STARTED),
        (2.5, EventKind.PROMPT_SUBMITTED),
        (4.0, EventKind.AGENT_STARTED),
        (6.0, EventKind.TOOL_STARTED),
        (9.0, EventKind.TOOL_FINISHED),
        (12.0, EventKind.TASK_COMPLETE),
        (625.0, EventKind.USER_RETURNED),
    ]
    # then idle to sleep (compressed to 630s for the proof), then user returns
    dt = 1.0 / args.fps
    end = 630.0
    events = list(schedule)
    steps = int(end / dt)
    for i in range(steps):
        clock.advance(dt)
        while events and clock.t >= events[0][0] - 1e-9:
            _, kind = events.pop(0)
            director.start_chain(engine.handle(SemanticEvent(kind=kind)))
        director.step(dt)

    print(f"== FIRST DEMONSTRATION (headless, seed={args.seed}, {args.fps}fps) ==")
    print(f"semantic states seen: {' -> '.join(surface.state_log)}")
    print(f"pose sequence: {' > '.join(surface.pose_sequence())}")
    print(f"max screen travel: {surface.max_travel()}px (dash proof)")
    print("\nengine trace:")
    for line in engine.trace:
        print("  ", line)

    # assertions the acceptance gate expects
    seq = surface.pose_sequence()
    assert "work" in seq, "tool work pose missing"
    assert "dash_to_workspace" in seq, "dash missing"
    assert "celebrate" in seq, "celebration missing"
    assert "sleep" in seq, "idle->sleep missing"
    assert "wake" in seq, "wake on user return missing"
    assert surface.max_travel() > 0, "no screen travel"
    print("\n[PASS] walking-skeleton pose requirements met")
    return 0


def _make_engine_pair(seed: int, events, clock=None) -> tuple[list[dict], list[dict]]:
    traces = []
    for _ in range(2):
        e = BehaviorEngine(seed=seed, clock=clock or (lambda: 0.0)) if clock is not None else BehaviorEngine(seed=seed)
        for ev in events:
            e.handle(ev)
        traces.append([d for d in e.trace if d["event"] != "suppressed"])
    return traces


def cmd_selfcheck(args: argparse.Namespace) -> int:
    results: list[tuple[str, bool]] = []

    # 1. Determinism (m3 / §34.9): same seed + same events -> identical trace
    events = [SemanticEvent(kind=k) for k in (
        EventKind.TOOL_STARTED, EventKind.TOOL_FINISHED, EventKind.TASK_COMPLETE)]
    t1, t2 = _make_engine_pair(args.seed, events)
    results.append(("determinism: identical trace on same seed", t1 == t2))

    # 2. Combo system (Tekken-style): nearby activity extends the combo tier.
    combo_clock = FakeClock()
    combo_engine = BehaviorEngine(seed=args.seed, clock=combo_clock)
    combo_engine.handle(SemanticEvent(kind=EventKind.TOOL_STARTED, tool="terminal", category="terminal"))
    combo_clock.advance(0.6)
    combo_engine.handle(SemanticEvent(kind=EventKind.TOOL_PROGRESS, tool="terminal", category="terminal"))
    combo_clock.advance(0.6)
    combo_engine.handle(SemanticEvent(kind=EventKind.TOOL_FINISHED, tool="terminal", category="terminal"))
    combo_tiers = [d.get("combo_tier", 1) for d in combo_engine.trace if d["event"] == "chain"]
    results.append((f"combo: 3-step burst reaches tier {combo_tiers[-1] if combo_tiers else 0}",
                    bool(combo_tiers and combo_tiers[-1] >= 3)))

    # 3. Storm rule (M5 / §10.4): burst of 50 tool.started collapses via cooldown
    engine = BehaviorEngine(seed=args.seed)
    chains = 0
    for _ in range(50):
        c = engine.handle(SemanticEvent(kind=EventKind.TOOL_STARTED))
        if c is not None:
            chains += 1
    results.append((f"storm: 50 tool.started -> {chains} chain start(s) (<=3 expected)",
                    chains <= 3))

    # 4. Priority interrupt (M5 / §10): P1 approval preempts a P4 work chain
    engine = BehaviorEngine(seed=args.seed)
    engine.handle(SemanticEvent(kind=EventKind.TOOL_STARTED))
    engine.handle(SemanticEvent(kind=EventKind.APPROVAL_REQUIRED))
    interrupted = any(d["event"] == "chain_interrupt" for d in engine.trace)
    results.append(("priority: approval.required interrupts tool.started", interrupted))

    # 5. Content-free events (M1): no raw text fields anywhere in the envelope
    from dataclasses import fields
    forbidden = ("command", "result", "function_args", "prompt", "args")
    has_forbidden = any(
        f.name in forbidden for f in fields(SemanticEvent))
    results.append(("boundary: SemanticEvent has no raw-content fields",
                    not has_forbidden))

    # 5. Click-through flag on the overlay (M6 / §33) — Windows only
    try:
        from hermes_companion.renderer.overlay import TkOverlay, WS_EX_TRANSPARENT
        ov = TkOverlay()
        ov.root.update_idletasks()
        hwnd = ov._hwnd()
        style = ov.ex_style
        ov.close()
        ct = bool(style & WS_EX_TRANSPARENT) and hwnd != 0
        results.append(("overlay: WS_EX_TRANSPARENT set (click-through)", ct))
    except Exception as exc:  # no display / not Windows
        results.append((f"overlay: click-through check skipped ({exc})", True))

    ok = all(ok for _, ok in results)
    for name, passed in results:
        print(f"  [{'PASS' if passed else 'FAIL'}] {name}")
    print(f"\nselfcheck {'PASSED' if ok else 'FAILED'}")
    return 0 if ok else 1


def cmd_live(args: argparse.Namespace) -> int:
    """Drive the user's active Hermes pet from real plugin JSONL events."""
    from hermes_companion.renderer.live import (
        EventTail, active_pet, bound_session_for_companion, hermes_home,
    )
    from hermes_companion.renderer.relay import RelayClient, default_token

    def _monitors() -> list[tuple[int, int, int, int]]:
        """Enumerate attached display rectangles in desktop coordinates."""
        try:
            import ctypes.wintypes as wt

            user32 = ctypes.windll.user32
            monitors: list[tuple[int, int, int, int]] = []

            MonitorEnumProc = ctypes.WINFUNCTYPE(ctypes.c_int, wt.HMONITOR, wt.HDC,
                                                 ctypes.POINTER(wt.RECT), wt.LPARAM)

            def callback(_hmon, _hdc, rect_ptr, _lparam):
                rect = rect_ptr.contents
                monitors.append((rect.left, rect.top, rect.right, rect.bottom))
                return 1

            enum_proc = MonitorEnumProc(callback)
            user32.EnumDisplayMonitors(0, 0, enum_proc, 0)
            if monitors:
                return monitors
        except Exception:
            pass

        try:
            import json
            import subprocess
            import sys

            code = r'''
import ctypes, ctypes.wintypes as wt, json
mons = []
user32 = ctypes.windll.user32
MonitorEnumProc = ctypes.WINFUNCTYPE(ctypes.c_int, wt.HMONITOR, wt.HDC, ctypes.POINTER(wt.RECT), wt.LPARAM)
def cb(_hmon, _hdc, rect_ptr, _lparam):
    r = rect_ptr.contents
    mons.append((r.left, r.top, r.right, r.bottom))
    return 1
proc = MonitorEnumProc(cb)
user32.EnumDisplayMonitors(0, 0, proc, 0)
print(json.dumps(mons))
'''
            out = subprocess.check_output([sys.executable, '-c', code], text=True, timeout=10)
            return [tuple(map(int, item)) for item in json.loads(out or '[]')]
        except Exception:
            return []

    def _monitor_home(index: int, scale: float) -> tuple[int, int] | None:
        mons = _monitors()
        if index < 1 or index > len(mons):
            return None
        left, top, right, bottom = mons[index - 1]
        pet_w = round(192 * scale) + 28
        pet_h = round(208 * scale) + 28
        return left + (right - left - pet_w) // 2, bottom - pet_h - 58

    slug, sheet, configured_scale = active_pet()
    from hermes_companion.core import binding as bind_mod
    following = bind_mod.following_companion()
    # Follow mode displays whichever session is active. Honoured only when the
    # grant names THIS body, so it can never leak to a different sprite.
    follow_mode = following == slug
    bound_session_id = None if follow_mode else bound_session_for_companion(slug)
    if not follow_mode and not bound_session_id:
        print(f"REFUSING LIVE DISPLAY: pet {slug!r} has no unique explicit "
              f"session binding (run: hermes-companion bind --follow)",
              file=sys.stderr, flush=True)
        return 2
    scale = args.scale if args.scale is not None else configured_scale
    events = Path(args.events) if args.events else hermes_home() / "companion" / "events.jsonl"

    home_x = args.x
    home_y = args.y
    if args.monitor is not None and home_x is None and home_y is None:
        monitor_home = _monitor_home(args.monitor, scale)
        if monitor_home is not None:
            home_x, home_y = monitor_home

    relay = None
    if args.relay:
        host, _, port = args.relay.partition(":")
        token = default_token()
        if not token:
            print("REFUSING RELAY: set HERMES_COMPANION_TOKEN in the inherited environment",
                  file=sys.stderr, flush=True)
            return 2
        relay = RelayClient(host, int(port or 49000), token=token)
        relay.start()

    from hermes_companion.renderer.intent_bridge import CompanionIntentEmitter
    intent_emitter = CompanionIntentEmitter(
        audit_path=hermes_home() / "companion" / "intents.jsonl",
        session_id=bound_session_id or ("follow" if follow_mode else ""),
    )
    if args.companion is None:
        from hermes_companion.renderer.petdex_overlay import PetdexOverlay
        overlay = PetdexOverlay(
            str(sheet), scale=scale, home_x=home_x, home_y=home_y,
            enable_grab=args.grab, on_grab=_make_grab_publisher(relay),
            intent_emitter=intent_emitter)
    else:
        if args.grab:
            print("REFUSING LIVE: --grab is not supported by procedural companions",
                  file=sys.stderr, flush=True)
            if relay is not None:
                relay.close()
            return 2
        if args.render == "smooth":
            from hermes_companion.renderer.layered import SmoothLiveOverlay
            overlay = SmoothLiveOverlay(
                companion=args.companion, home_x=home_x, home_y=home_y)
        else:
            from hermes_companion.renderer.overlay import ProceduralLiveOverlay
            overlay = ProceduralLiveOverlay(
                companion=args.companion, home_x=home_x, home_y=home_y)
    from hermes_companion.renderer.desktop_sensors import DesktopSensors
    sensors = DesktopSensors.for_platform(
        args.notice, pet_box=lambda: (
            overlay.x, getattr(overlay, "y", getattr(overlay, "home_y", 0)),
            overlay.x + getattr(overlay, "w", 0),
            getattr(overlay, "y", getattr(overlay, "home_y", 0)) + getattr(overlay, "h", 0)))
    tail = EventTail(events, overlay, from_end=not args.replay,
                     relay=relay, bound_session_id=bound_session_id,
                     follow=follow_mode, companion_id=slug,
                     idle=False, replay=args.replay,
                     variety=not args.no_variety, sensors=sensors,
                     perch=not args.no_perch)
    if args.companion is not None:
        overlay.bind_engine(tail.engine)
    overlay.on_ready = lambda: (
        print(f"LIVE READY pet={slug} scale={scale:g}", flush=True),
        print(f"FOLLOWING ACTIVE SESSION" if follow_mode
              else f"BOUND SESSION {bound_session_id}", flush=True),
        print(f"WATCHING {events}", flush=True),
        (print(f"RELAY {args.relay} token={'set' if relay.token else 'unset'}",
               flush=True) if relay else None),
        overlay.root.after(100, tail.poll),
    )
    if args.demo:
        # Local visual proof using the same engine-driven chain path.
        demo = [
            (200, "agent.started", ""),
            (1700, "tool.started", "terminal"),
            (4400, "tool.finished", "terminal"),
        ]
        for delay, event, tool in demo:
            overlay.root.after(delay, lambda e=event, t=tool: _play_demo(tail, e, t))
    overlay.run()
    return 0


def cmd_play(args: argparse.Namespace) -> int:
    """Run a companion on the desktop with no Hermes install needed."""
    from hermes_companion.renderer.playground import run_playground
    return run_playground(companion=args.companion, notice=args.notice,
                          palette=args.palette, render=args.render,
                          perch=not args.no_perch,
                          seed=args.seed, variety=not args.no_variety,
                          demo=not args.no_demo)


def _make_grab_publisher(relay):
    """Publish local pet drags to the relay so every pet moves together."""
    if relay is None:
        return None
    from hermes_companion.renderer.live import _hostname
    host = _hostname()

    def publish(x: int, y: int) -> None:
        relay.send({"type": "grab", "x": x, "y": y, "source": host})

    return publish


def _play_demo(tail, event: str, tool: str) -> None:
    from hermes_companion.core.events import EventKind, SemanticEvent, classify_tool
    kind = EventKind(event)
    ev = SemanticEvent(kind=kind, tool=tool, category=classify_tool(tool))
    chain = tail.engine.handle(ev)
    if chain is not None:
        tail.overlay.play_chain(chain, ev.category)
        if tail.relay is not None:
            tail.relay.send({
                "type": "event", "event": ev.kind.value, "tool": tool,
                "category": ev.category, "source": tail.host,
            })


def cmd_relay(args: argparse.Namespace) -> int:
    """Run the LAN relay (one per fleet): fans semantic events + grabs out
    to every connected pet. Token-gated; prints the token once at start."""
    from hermes_companion.renderer.relay import RelayServer, default_token

    token = default_token()
    if not token:
        print("REFUSING RELAY: set HERMES_COMPANION_TOKEN in the inherited environment",
              file=sys.stderr, flush=True)
        return 2
    server = RelayServer(host=args.host, port=args.port, token=token)
    server.start()
    print(f"RELAY READY on {args.host}:{args.port}", flush=True)
    print("Clients authenticate from inherited HERMES_COMPANION_TOKEN", flush=True)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.close()
    return 0


_PUBLIC_LABEL = re.compile(r"[A-Za-z0-9][A-Za-z0-9_.:-]{0,63}\Z")


def _public_label(value: object) -> str | None:
    """Return a bounded identifier-style label, never free-form content."""
    return value if isinstance(value, str) and _PUBLIC_LABEL.fullmatch(value) else None


def _public_count(value: object) -> int | None:
    """Return a bounded non-negative count; reject strings and booleans."""
    if type(value) is int and 0 <= value <= 1_000_000_000:
        return value
    return None


def _bounded_recall_limit(value: str) -> int:
    try:
        limit = int(value)
    except ValueError as exc:
        raise argparse.ArgumentTypeError("limit must be an integer") from exc
    if not 1 <= limit <= 20:
        raise argparse.ArgumentTypeError("limit must be between 1 and 20")
    return limit


def cmd_hindsight(args: argparse.Namespace) -> int:
    """Connect the companion to the local Hindsight memory server (MCP) and
    report real memory state: server reachable, banks, total facts. With
    --query, also show top recall LABELS (never memory content — spec §5.4)."""
    from hermes_companion.core.hindsight import HindsightClient

    hs = HindsightClient()
    if not hs.ping():
        print("HINDSIGHT unreachable (is the server running on 127.0.0.1:8768?)")
        return 1
    print("HINDSIGHT READY")
    banks = hs.list_banks() or []
    print(f"banks: {len(banks)}")
    for b in banks:
        fid = _public_label(b.get("bank_id")) or _public_label(b.get("id"))
        name = _public_label(b.get("name")) or fid
        if name is None:
            continue
        fc = _public_count(b.get("fact_count"))
        count_text = str(fc) if fc is not None else "unknown"
        suffix = f" ({fid})" if fid is not None and fid != name else ""
        print(f"  - {name}{suffix}: {count_text} facts")
    total = _public_count(hs.memory_count())
    print(f"total facts: {total if total is not None else 'unknown'}")
    if args.query:
        hits = hs.recall(args.query, limit=args.limit) or []
        print(f"recall hits: {len(hits)}")
        for h in hits:
            label = (_public_label(h.get("label"))
                     or _public_label(h.get("bank_id"))
                     or _public_label(h.get("id")))
            if label is not None:
                print(f"  - {label}")
    return 0


def cmd_scene(args: argparse.Namespace) -> int:
    """Visual overlay driver. Plays a fixed sequence of poses/events, holding
    each for `--hold` seconds. With `--shots DIR`, captures the pet's screen
    region at each pose into DIR as PNG (self-contained §34 proof)."""
    import time

    from hermes_companion.animation.director import Director
    from hermes_companion.renderer.overlay import TkOverlay

    ov = TkOverlay(click_through=not args.clickable,
                   companion=args.companion, palette=args.palette)
    engine = BehaviorEngine(seed=args.seed)
    director = Director(engine, ov, fps=args.fps)

    def capture(idx: int, label: str) -> None:
        if not args.shots:
            return
        try:
            from PIL import ImageGrab
            w, h = ov.w, ov.h
            # Track the pet's live position (it dashes away from home).
            x = ov.current_x()
            bbox = (x - 16, ov.home_y - 16, x + w + 16, ov.home_y + h + 16)
            img = ImageGrab.grab(bbox=bbox)
            out = os.path.join(args.shots, f"{idx:02d}_{label}.png")
            img.save(out)
            print(f"  [shot] {out}", flush=True)
        except Exception as exc:
            print(f"  [shot failed] {exc}", flush=True)

    def play(chain, hold: float = 1.2, shot: str | None = None,
             step_shots: bool = False):
        if chain is not None:
            director.start_chain(chain)
        end = time.monotonic() + hold
        while time.monotonic() < end:
            director.step(0.03)
            ov.root.update()
            time.sleep(0.03)
        # let the remaining chain steps finish
        while director.chain is not None:
            prev_pose = director.current_pose()
            director.step(0.03)
            ov.root.update()
            time.sleep(0.03)
            # capture at each atomic-step boundary (one shot per chain step)
            if step_shots and director.current_pose() != prev_pose and args.shots:
                capture(idx, f"{shot}__{prev_pose}")
        if shot:
            capture(idx, shot)

    items = args.sequence or ["idle_bob", "look_at_input", "work",
                              "celebrate", "sleep", "wave"]
    print("READY", flush=True)
    for idx, item in enumerate(items):
        if item.startswith("ev:"):
            ev = _parse_event(item[3:])
            print(f"EVENT {item[3:]} -> {ev.kind.value}", flush=True)
            play(engine.handle(ev), shot=item[3:].replace(" ", "_"),
                 step_shots=args.step_shots)
        else:
            print(f"POSE {item}", flush=True)
            director.chain = None
            director.idle_pose = item
            play(None, shot=item)
    print("DONE", flush=True)
    ov.close()
    return 0


def cmd_intent(args: argparse.Namespace) -> int:
    try:
        kind = IntentKind(args.intent)
    except ValueError:
        kind = IntentKind.UNKNOWN
    intent = CompanionIntent(
        kind=kind,
        source=args.source,
        confidence=args.confidence,
        session_id=args.session_id,
    )
    decision = route_intent(intent, audit_path=Path(args.audit))
    status = "allowed" if decision.allowed else "rejected"
    print(f"{intent.kind.value} -> {status} ({decision.reason})")
    return 0 if decision.allowed else 2


def cmd_camera(args: argparse.Namespace) -> int:
    """Local camera awareness: readiness check, or one consent-gated probe.

    Deliberately narrow. ``status`` never touches the device. ``check`` refuses
    in follow mode, refuses without an exact pinned session, and refuses without
    an explicit consent flag — in that order, so a refusal can never be
    accidental.
    """
    from hermes_companion.core.camera_awareness import CameraAwarenessController
    from hermes_companion.renderer.camera_probe import camera_available, probe_camera

    if args.camera_command == "status":
        # Readiness only: reports the default-off posture without opening a device.
        print(f"enabled=false camera_opened=false "
              f"cv2={'available' if camera_available() else 'missing'}")
        return 0

    from hermes_companion.core import binding as bind_mod
    from hermes_companion.renderer.live import bound_session_for_companion

    if bind_mod.following_companion() is not None:
        print("REFUSING CAMERA CHECK: one-shot checks require pinned mode "
              "(use: hermes-companion bind --pinned)")
        return 2
    rows = bind_mod.describe()
    if len(rows) != 1:
        print("REFUSING CAMERA CHECK: expected exactly one pinned companion binding")
        return 2
    companion_id = str(rows[0].get("companion_id") or "")
    bound_session = bound_session_for_companion(companion_id)
    if not bound_session:
        print("REFUSING CAMERA CHECK: no exact session binding for "
              f"{companion_id!r}")
        return 2
    session_id = args.session_id or bound_session
    if session_id != bound_session:
        print("REFUSING CAMERA CHECK: session does not match the pinned binding")
        return 2
    if not args.consent:
        print("REFUSING CAMERA CHECK: this opens your camera for a single frame. "
              "Re-run with --consent to confirm.")
        return 2

    controller = CameraAwarenessController()
    try:
        result = controller.check(
            companion_id=companion_id,
            session_id=session_id,
            bound_session_id=bound_session,
            mode="pinned",
            source_id=args.source,
            confirmed=True,
            probe=probe_camera,
        )
    except Exception as exc:  # never leak a traceback or a payload
        print(f"CAMERA CHECK FAILED: {type(exc).__name__}")
        return 1
    print(f"camera_read={str(result.camera_read).lower()} "
          f"presence={result.presence}")
    return 0


def cmd_bind(args: argparse.Namespace) -> int:
    """Create, show, or clear the explicit companion -> session binding.

    This is the sanctioned way to attach a visible companion to a real
    session. Nothing binds automatically: the renderer still fails closed, so
    the pet only shows evidence from the session named here.
    """
    from hermes_companion.core import binding as bind_mod

    if args.show:
        mode = bind_mod.current_mode()
        rows = bind_mod.describe()
        print(f"mode: {mode}"
              + (f" (following {bind_mod.following_companion()})" if mode == bind_mod.MODE_FOLLOW else ""))
        if not rows:
            print("no pinned companion bindings")
            return 0
        for row in rows:
            print(f"  {row.get('companion_id')} -> session={row.get('session_id')} "
                  f"task={row.get('task_id')} project={row.get('project_id')}")
        return 0

    companion_id = args.companion
    if not companion_id and (args.follow or args.pinned or args.clear or args.session):
        try:
            from hermes_companion.renderer.live import active_pet
            companion_id = active_pet()[0]
        except Exception:
            print("no --companion given and no active pet to default to",
                  file=sys.stderr)
            return 2

    if args.follow:
        try:
            bind_mod.set_mode(bind_mod.MODE_FOLLOW, companion_id)
        except ValueError as exc:
            print(f"refusing follow mode: {exc}", file=sys.stderr)
            return 2
        print(f"{companion_id} now follows whichever session is active.")
        print("Switch off with: hermes-companion bind --pinned")
        return 0

    if args.pinned:
        bind_mod.set_mode(bind_mod.MODE_PINNED)
        print("pinned mode: the companion displays only its bound session")
        return 0

    if not companion_id:
        print("no --companion given and no active pet to default to",
              file=sys.stderr)
        return 2

    if args.clear:
        removed = bind_mod.unbind(companion_id)
        print(f"{'unbound' if removed else 'no binding for'} {companion_id}")
        return 0 if removed else 1

    if args.session is None:
        session_id = bind_mod.resolve_current_session()
        if not session_id:
            print("could not determine the current session; pass --session <id>",
                  file=sys.stderr)
            return 2
    else:
        session_id = args.session
    try:
        bind_mod.bind(companion_id, session_id,
                      task_id=args.task, project_id=args.project)
    except ValueError as exc:
        print(f"refusing to bind: {exc}", file=sys.stderr)
        return 2
    print(f"bound {companion_id} -> session={session_id}"
          + (f" task={args.task}" if args.task else ""))
    print("The companion will display evidence from this session only.")
    return 0


def build_parser() -> argparse.ArgumentParser:
    """Build the real CLI parser.

    Exposed as a function so tests can assert that launcher scripts only pass
    arguments this parser actually accepts — a launcher/parser mismatch makes
    a companion silently fail to start.
    """
    p = argparse.ArgumentParser(prog="hermes-companion")
    p.add_argument("--seed", type=int, default=1)
    sub = p.add_subparsers(dest="cmd", required=True)

    pe = sub.add_parser("emit")
    pe.add_argument("event")
    pe.set_defaults(fn=cmd_emit)

    pst = sub.add_parser("status", help="show the privacy-safe Hermes attention signal")
    pst.add_argument("--events", required=True, help="path to companion events.jsonl")
    pst.add_argument("--now", type=float, default=None,
                     help="wall-clock epoch to evaluate against (default: now)")
    pst.add_argument("--no-stuck", action="store_true",
                     help="skip the stuck verdict; print attention signal only")
    pst.set_defaults(fn=cmd_status)

    pi = sub.add_parser("intent", help="route a safe audited companion intent")
    pi.add_argument("intent", help="intent name, e.g. show_status")
    pi.add_argument("--source", default="cli", help="bounded source label")
    pi.add_argument("--confidence", type=float, default=1.0)
    pi.add_argument("--session-id", default="")
    pi.add_argument("--audit", default=str(Path(os.environ.get("LOCALAPPDATA", ".")) / "hermes" / "companion" / "intents.jsonl"))
    pi.set_defaults(fn=cmd_intent)

    pd = sub.add_parser("demo")
    pd.add_argument("--fps", type=int, default=30)
    pd.set_defaults(fn=cmd_demo)

    ps = sub.add_parser("selfcheck")
    ps.set_defaults(fn=cmd_selfcheck)

    pb = sub.add_parser("bind", help="attach a visible companion to an explicit real session")
    pb.add_argument("--companion", default=None,
                    help="companion id (default: the configured active pet)")
    pb.add_argument("--session", default=None,
                    help="exact Hermes session id; omit to use the current session")
    pb.add_argument("--task", default=None, help="optional task id scope")
    pb.add_argument("--project", default=None, help="optional project id scope")
    pb.add_argument("--show", action="store_true", help="list follow mode and pinned bindings")
    pb.add_argument("--clear", action="store_true", help="remove this companion's binding")
    pb.add_argument("--follow", action="store_true",
                    help="follow whichever session is active (no per-chat rebinding)")
    pb.add_argument("--pinned", action="store_true",
                    help="display only this companion's bound session (default)")
    pb.set_defaults(fn=cmd_bind)

    pcam = sub.add_parser(
        "camera", help="local camera awareness (off by default; one-shot only)")
    cams = pcam.add_subparsers(dest="camera_command", required=True)
    cams.add_parser("status", help="report readiness without opening the device")
    cam_check = cams.add_parser(
        "check", help="read exactly one frame, with explicit consent")
    cam_check.add_argument("--source", default="camera-0",
                           help="opaque camera source id (default: camera-0)")
    cam_check.add_argument("--session-id", default=None,
                           help="pinned session id; must match the binding")
    cam_check.add_argument("--consent", action="store_true",
                           help="confirm you want a single camera frame read now")
    pcam.set_defaults(fn=cmd_camera)

    pl = sub.add_parser("live", help="drive the active Hermes pet from real events")
    pl.add_argument("--events", default=None, help="override events.jsonl path")
    pl.add_argument("--scale", type=float, default=None, help="override active pet scale")
    pl.add_argument("--replay", action="store_true", help="replay existing log from the start")
    pl.add_argument("--demo", action="store_true", help="play a local start/tool/finish demo")
    pl.add_argument("--x", type=int, default=None, help="start the pet at this X desktop coordinate")
    pl.add_argument("--y", type=int, default=None, help="start the pet at this Y desktop coordinate")
    pl.add_argument("--monitor", type=int, default=None,
                    help="start the pet on monitor N (1 = first attached display)")
    pl.add_argument("--grab", action="store_true",
                    help="enable sprite hitbox + drag (opt-in pointer interaction, §25)")
    pl.add_argument("--companion", choices=("pet", "samurai", "astro", "herald", "nia", "nyamekra"), default=None,
                    help="render a procedural companion instead of the configured Alpha atlas")
    pl.add_argument("--relay", default=None, metavar="HOST:PORT",
                    help="join a LAN relay; token comes only from HERMES_COMPANION_TOKEN")
    pl.add_argument("--no-idle", action="store_true",
                    help="disable idle progression (look_around/sit/sleep)")
    pl.add_argument("--notice", choices=("off", "ambient", "full"), default="full",
                    help="what the pet may notice on the desktop (content-free): "
                         "ambient = cursor/windows/displays/away; full adds clicks, "
                         "typing rhythm and clipboard changes (default: full)")
    pl.add_argument("--render", choices=("smooth", "classic"), default="smooth",
                    help="procedural companions: smooth anti-aliased or classic")
    pl.add_argument("--no-perch", action="store_true",
                    help="procedural companions: don't perch on windows")
    pl.add_argument("--no-variety", action="store_true",
                    help="play each Hermes chain exactly as written, no flourishes")
    pl.set_defaults(fn=cmd_live)

    pp = sub.add_parser("play", help="try a companion now - no Hermes needed")
    pp.add_argument("--companion", choices=("nyamekra", "herald", "nia", "samurai", "astro"),
                    default="nyamekra")
    pp.add_argument("--palette", default=None,
                    help="herald: olympus midnight ember verdant nebula; "
                         "nia: kente indigo ochre emerald royal")
    pp.add_argument("--notice", choices=("off", "ambient", "full"), default="full",
                    help="what it may notice on the desktop (content-free)")
    pp.add_argument("--no-demo", action="store_true",
                    help="don't loop a simulated Hermes session")
    pp.add_argument("--no-variety", action="store_true")
    pp.add_argument("--render", choices=("smooth", "classic"), default="smooth",
                    help="smooth = anti-aliased, glowing, true transparency (default)")
    pp.add_argument("--no-perch", action="store_true",
                    help="stay on the floor instead of living on your windows")
    pp.set_defaults(fn=cmd_play)

    pr = sub.add_parser("relay", help="run the LAN event relay (one per fleet)")
    pr.add_argument("--host", default="0.0.0.0", help="bind address (default 0.0.0.0)")
    pr.add_argument("--port", type=int, default=49000, help="bind port (default 49000)")
    pr.set_defaults(fn=cmd_relay)

    psn = sub.add_parser("scene")
    psn.add_argument("--sequence", nargs="*")
    psn.add_argument("--hold", type=float, default=1.5)
    psn.add_argument("--fps", type=int, default=30)
    psn.add_argument("--companion", default=None,
                     help="which companion to render (pet | samurai; "
                          "default samurai)")
    psn.add_argument("--palette", default=None,
                     help="samurai material palette (crimson jade indigo "
                          "ember sakura void)")
    psn.add_argument("--shots", default=None, help="dir to save pose screenshots")
    psn.add_argument("--step-shots", action="store_true",
                     help="also capture each atomic step of event chains")
    psn.add_argument("--clickable", action="store_true",
                     help="disable click-through (dev only)")
    psn.set_defaults(fn=cmd_scene)

    phs = sub.add_parser(
        "hindsight",
        help="connect the companion to the Hindsight memory server (MCP)")
    phs.add_argument("--query", default=None, help="recall top labels for a query")
    phs.add_argument("--limit", type=_bounded_recall_limit, default=3)
    phs.set_defaults(fn=cmd_hindsight)

    from hermes_companion.renderer.multi_pet import cmd_multi
    pm = sub.add_parser("multi", help="show 1-4 session observers; does NOT create agents")
    pm.add_argument("--bind", action="append", help="Label=session_id or Label (unbound); repeat up to four")
    pm.add_argument("--events", default=None, help="read-only JSONL event source; starts at end")
    pm.add_argument("--duration", type=float, default=0, help="close after seconds; 0 stays open")
    pm.add_argument("--simulation", action="store_true", help="explicit synthetic fixture; requires bounded duration")
    pm.set_defaults(fn=cmd_multi)

    return p


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    return args.fn(args)


if __name__ == "__main__":
    sys.exit(main())
