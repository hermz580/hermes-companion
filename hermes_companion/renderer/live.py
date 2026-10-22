"""Tail real Hermes Companion JSONL events and drive the user's active pet.

v0.2 (diversity + multi-device):
- Events are rebuilt as SemanticEvents and run through the real BehaviorEngine
  (same seed the plugin used), then the returned Chain is played via
  `PetdexOverlay.play_chain`. The visible pet now shows the engine's full
  movement vocabulary — including category-flavored tool chains (terminal vs
  web vs file vs media vs memory) — instead of the old coarse mapping.
- Idle progression (look_around -> sit -> play_with_object -> sleep) runs off
  the same engine's idle_tick, so the pet has a life when Hermes is quiet.
- Optional relay link: local events are forwarded to a LAN relay and remote
  events (from the other machine's pet) are played identically here. Grab
  drags are published so both pets move together. Relay is opt-in via
  --relay host:port; authentication comes from inherited environment only.
"""
from __future__ import annotations

import json
import os
import socket
import time
from pathlib import Path
from typing import Any

from hermes_companion.core.event_auth import load_or_create_event_key, verify_record
from hermes_companion.core.events import EventKind, SemanticEvent, classify_tool
from hermes_companion.renderer.petdex_overlay import PetdexOverlay


def hermes_home() -> Path:
    env = os.environ.get("HERMES_HOME")
    if env:
        return Path(env)
    return Path.home() / "AppData" / "Local" / "hermes"


def _hostname() -> str:
    try:
        return socket.gethostname()
    except Exception:
        return "unknown"


def active_pet() -> tuple[str, Path, float]:
    """Resolve display.pet from config + on-disk profile pet store."""
    home = hermes_home()
    config = home / "config.yaml"
    slug, scale = "", 0.85
    try:
        import yaml
        raw = yaml.safe_load(config.read_text(encoding="utf-8")) or {}
        pet = ((raw.get("display") or {}).get("pet") or {})
        slug = str(pet.get("slug") or "")
        scale = float(pet.get("scale") or 0.85)
    except Exception:
        # Tiny fallback parser avoids making PyYAML a runtime requirement.
        text = config.read_text(encoding="utf-8") if config.exists() else ""
        in_pet = False
        for line in text.splitlines():
            stripped = line.strip()
            if line.startswith("  pet:"):
                in_pet = True
            elif in_pet and line and not line.startswith("    "):
                in_pet = False
            elif in_pet and stripped.startswith("slug:"):
                slug = stripped.partition(":")[2].strip()
            elif in_pet and stripped.startswith("scale:"):
                try:
                    scale = float(stripped.partition(":")[2].strip())
                except ValueError:
                    pass
    if not slug:
        raise RuntimeError("no active display.pet.slug in config")
    sheet = home / "pets" / slug / "spritesheet.webp"
    if not sheet.is_file():
        sheet = home / "pets" / slug / "spritesheet.png"
    if not sheet.is_file():
        raise FileNotFoundError(f"active pet spritesheet missing: {sheet}")
    return slug, sheet, scale


def bound_session_for_companion(companion_id: str, bindings_path: Path | None = None) -> str | None:
    """Return one explicit session binding for a companion, or fail closed.

    The visible body must never infer ownership from the current directory,
    newest log entry, or a sprite label. Duplicate, malformed, missing, and
    blank bindings all resolve to ``None``.
    """
    path = bindings_path or (hermes_home() / "companion" / "bindings.json")
    try:
        doc = json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, ValueError, TypeError):
        return None
    if not isinstance(doc, dict) or doc.get("version") not in (1, 2):
        return None
    rows = doc.get("bindings")
    if not isinstance(rows, list):
        return None
    sessions = []
    for row in rows:
        if not isinstance(row, dict) or row.get("companion_id") != companion_id:
            continue
        session_id = row.get("session_id")
        if (not isinstance(session_id, str) or not session_id
                or session_id != session_id.strip() or len(session_id) > 256
                or any(not c.isprintable() for c in session_id)):
            continue
        sessions.append(session_id)
    unique = sorted(set(sessions))
    return unique[0] if len(unique) == 1 else None


class EventTail:
    def __init__(self, path: Path, overlay: PetdexOverlay, *,
                 from_end: bool = True, relay=None,
                 bound_session_id: str | None = None, follow: bool = False,
                 companion_id: str = "active-companion",
                 follow_dwell_s: float = 2.5, clock=None,
                 idle: bool = False, replay: bool = False,
                 auth_key: bytes | None = None, variety: bool = False,
                 sensors=None, perch: bool = False) -> None:
        """Drive one companion from the signed event log.

        Exactly one source of ownership is required: a pinned
        ``bound_session_id`` (display that session only) or ``follow=True``
        (display whichever session is active, switching as activity moves).
        Anything else fails closed rather than guessing.
        """
        if follow:
            if bound_session_id:
                raise ValueError("pass either bound_session_id or follow, not both")
        elif (not isinstance(bound_session_id, str) or not bound_session_id
                or bound_session_id != bound_session_id.strip()):
            raise ValueError("an exact companion session binding is required")
        self.path = path
        self.overlay = overlay
        self.relay = relay
        self.bound_session_id = bound_session_id
        self.follow = bool(follow)
        self._clock = clock or time.monotonic
        self._dwell = float(follow_dwell_s)
        self._last_seen: dict[str, float] = {}
        # Sessions that have shown delegated work. Their own lifecycle records
        # (agent.started / agent.idle) carry no task id, so per-record detection
        # alone lets a worker claim the display on those two events.
        self._worker_sessions: set[str] = set()
        self._worker_sessions_max = 64
        if (not isinstance(companion_id, str) or not companion_id
                or len(companion_id) > 64 or companion_id != companion_id.strip()):
            raise ValueError("invalid companion_id")
        self.companion_id = companion_id
        self.following_session: str | None = None
        self.auth_key = auth_key or load_or_create_event_key(
            hermes_home() / "companion" / "event-auth.key")
        self.host = _hostname()
        self.seen = 0
        self._last_event = ""
        self._last_tool = ""
        self._last_event_at: float | None = None
        # Rebuild events through the same deterministic engine the plugin
        # uses (seed 0 unless overridden), so chains match what was logged.
        from hermes_companion.behavior.behavior_engine import BehaviorEngine
        from hermes_companion.core.attention import AttentionModel
        from hermes_companion.core.stuck import StuckDetector
        seed = int(os.environ.get("HERMES_COMPANION_SEED", "0") or "0")
        from hermes_companion.animation.characters import traits
        self.traits = traits(getattr(overlay, "companion", None))
        self.engine = BehaviorEngine(
            seed=seed or None, variety=variety,
            extra_flourishes=self.traits["extra_flourishes"],
            flourish_hints=self.traits["flourish_hints"], travel=self.traits["travel"])
        self.attention = AttentionModel()
        from hermes_companion.core.curiosity import CuriosityModel
        self.sensors = sensors
        self.curiosity = CuriosityModel(seed=seed or None) if sensors is not None else None
        if self.curiosity is not None:
            self.curiosity.own_moves = self.traits["curious_moves"]
        self._want_perch = perch
        self.perch = None
        self.stuck = StuckDetector()
        self._stuck_state = None
        self._offset = 0 if replay else (
            path.stat().st_size if from_end and path.exists() else 0)
        self._last_poll = time.monotonic()
        self._idle_on = idle
        # The overlay may offer a status panel; if so it asks US for state, so
        # the panel can only ever describe what this tail actually observed.
        if hasattr(overlay, "panel_state_provider"):
            overlay.panel_state_provider = self.panel_state

    # -- status panel -------------------------------------------------------
    def _library_identity(self) -> tuple[str, str, tuple[str, ...]]:
        """Approved name/role/memory for this companion, or empty on any error.

        Read-only, local, and fail-closed: a missing or unreadable library shows
        the panel with no memory rather than guessing at any.
        """
        try:
            from hermes_companion.core.companion_memory import CompanionMemoryStore
            path = hermes_home() / "companion" / "library.sqlite3"
            if not path.is_file():
                return "", "", ()
            store = CompanionMemoryStore(path)
            try:
                profile = next((c for c in store.list_companions()
                                if c.get("companion_id") == self.companion_id), None)
                name = str((profile or {}).get("name") or "")
                role = str((profile or {}).get("role") or "")
                memories = tuple(
                    str(r.get("content") or "")
                    for r in store.list_memories(self.companion_id)
                    if r.get("state") == "approved"
                )
            finally:
                store.close()
            return name, role, memories
        except Exception:
            return "", "", ()

    def panel_state(self):
        """Exactly what the double-click panel may display right now."""
        from hermes_companion.renderer.companion_panel import build_panel_state

        name, role, memories = self._library_identity()
        age = (None if self._last_event_at is None
               else max(0.0, time.monotonic() - self._last_event_at))
        return build_panel_state(
            companion_id=self.companion_id,
            display_name=name or self.companion_id,
            role=role,
            mode="follow" if self.follow else "pinned",
            session_id=(self.following_session if self.follow
                        else (self.bound_session_id or "")),
            last_event=self._last_event,
            last_tool=self._last_tool,
            last_event_age_s=age,
            events_seen=self.seen,
            engine_state=self.engine.state.value,
            memories=memories,
        )

    # -- event source ------------------------------------------------------
    def _poll_file(self) -> None:
        try:
            if self.path.exists():
                size = self.path.stat().st_size
                if size < self._offset:  # log rotated/truncated
                    self._offset = 0
                with self.path.open("r", encoding="utf-8") as f:
                    f.seek(self._offset)
                    for line in f:
                        try:
                            rec: dict[str, Any] = json.loads(line)
                        except (ValueError, TypeError):
                            continue
                        self._handle_record(rec)
                    self._offset = f.tell()
        except OSError as exc:
            print(f"event tail error: {exc}", flush=True)

    @staticmethod
    def _session_of(rec: dict[str, Any]) -> str:
        return str(rec.get("session_id") or rec.get("session_key") or "")

    def _classify(self, rec: dict[str, Any], session: str) -> bool:
        """True when this record is delegated (subagent) work.

        Two signals, because one is not enough: the record's own ``sa-N-<hex>``
        task id, and the sticky fact that this session has produced delegated
        work before. A subagent's ``agent.started``/``agent.idle`` carry no task
        id at all, and those two events were enough to hand it the display.
        A record that identifies as a top-level turn of its own session clears
        the mark, so a session can never be permanently mislabelled.
        """
        from hermes_companion.core.events import is_delegated_task

        task = rec.get("task_id")
        if is_delegated_task(task):
            if session and len(self._worker_sessions) < self._worker_sessions_max:
                self._worker_sessions.add(session)
            return True
        if session and isinstance(task, str) and task and task == session:
            self._worker_sessions.discard(session)
            return False
        return bool(session) and session in self._worker_sessions

    def _claim_session(self, session: str) -> bool:
        """True when this record belongs to the session being displayed.

        Pinned mode demands an exact match. Follow mode adopts whichever
        session is producing activity and announces the switch; playing the
        new chain replaces the queue, so the previous session's animation stops
        rather than overlapping.
        """
        return self._claim(session, delegated=False)

    def _claim(self, session: str, *, delegated: bool) -> bool:
        if not session:
            return False
        now = self._clock()
        self._last_seen[session] = now
        if not self.follow:
            return session == self.bound_session_id
        if self.following_session is None:
            # A delegated worker may not open the show: the user's own session
            # is the one worth watching, and workers are usually the noisiest.
            if delegated:
                return False
            self.following_session = session
            print(f"FOLLOWING {session}", flush=True)
            return True
        if session == self.following_session:
            return True
        # Nor may a worker take the show over from a merely-quiet chat.
        if delegated:
            return False
        # More than one session is routinely live at once (subagents, background
        # turns), so switching on every unfamiliar session id makes the pet flap
        # between them — the "looks wild with many things running" failure. Hold
        # the displayed session while it is still producing activity and adopt
        # another only once this one has gone quiet.
        if now - self._last_seen.get(self.following_session, now) < self._dwell:
            return False
        previous, self.following_session = self.following_session, session
        reset = getattr(self.engine, "reset_context", None)
        if callable(reset):
            reset()
        print(f"FOLLOW SWITCH {previous} -> {session}", flush=True)
        return True

    def _handle_record(self, rec: dict[str, Any]) -> None:
        authenticated = verify_record(rec, self.auth_key)
        if authenticated is None:
            return
        rec = authenticated
        session = self._session_of(rec)
        if not self._claim(session, delegated=self._classify(rec, session)):
            return
        kind_name = str(rec.get("event") or "")
        try:
            kind = EventKind(kind_name)
        except ValueError:
            return
        tool = str(rec.get("tool") or "")
        category = str(rec.get("category") or "") or classify_tool(tool)
        ev = SemanticEvent(
            kind=kind, tool=tool, category=category,
            session_id=str(rec.get("session_id") or ""),
            task_id=str(rec.get("task_id") or ""),
        )
        signal = self.attention.ingest(ev)
        if hasattr(self.overlay, "set_attention"):
            self.overlay.set_attention(signal.state, signal.label)
        if self.traits.get("observe"):
            self.traits["observe"](ev)          # Masque: cracks, colour, tendrils, eyes
        self.stuck.ingest(
            kind=kind.value, tool=tool, category=category,
            session=ev.session_id, task=ev.task_id,
            ts=float(rec.get("ts") or 0.0),
        )
        chain = self.engine.handle(ev)
        if chain is None:
            return
        from hermes_companion.behavior.choreography import compile_delivery
        from hermes_companion.core.companion_routing import CompanionDelivery
        plan = compile_delivery(CompanionDelivery(self.companion_id, ev), chain)
        chain = plan.to_chain()
        self.seen += 1
        self._last_event = kind.value
        self._last_tool = tool
        self._last_event_at = time.monotonic()
        print(f"EVENT {self.seen}: {kind.value} tool={tool} "
              f"cat={category} -> {chain.state.value} "
              f"({' > '.join(chain.poses)})", flush=True)
        self.overlay.play_chain(chain, category)
        if self.relay is not None:
            self.relay.send({
                "type": "event",
                "event": kind.value,
                "tool": tool,
                "category": category,
                "session_id": ev.session_id,
                "source": self.host,
            })

    # -- idle progression (same engine, same thresholds) --------------------
    def _poll_idle(self) -> None:
        if not self._idle_on:
            return
        if getattr(self, "attention", None) is not None and self.attention.signal.state != "quiet":
            self._last_poll = time.monotonic()
            return
        now = time.monotonic()
        dt = now - self._last_poll
        self._last_poll = now
        pose = self.engine.idle_tick(dt)
        if pose and pose != "sleep":
            print(f"IDLE {pose}", flush=True)
            self.overlay.enqueue([self.overlay._beat_from_pose(pose)], replace=True)

    # -- relay (remote pet) --------------------------------------------------
    def _poll_relay(self) -> None:
        if self.relay is None:
            return
        for rec in self.relay.drain():
            rtype = rec.get("type")
            source = str(rec.get("source") or "")
            if source == self.host:
                continue  # our own echo — already played locally
            if rtype == "event":
                session = self._session_of(rec)
                if not self._claim(session, delegated=self._classify(rec, session)):
                    continue
                try:
                    kind = EventKind(rec["event"])
                except (KeyError, ValueError):
                    continue
                ev = SemanticEvent(
                    kind=kind,
                    tool=str(rec.get("tool") or ""),
                    category=str(rec.get("category") or ""),
                    session_id=str(rec.get("session_id") or ""),
                )
                signal = self.attention.ingest(ev)
                if hasattr(self.overlay, "set_attention"):
                    self.overlay.set_attention(signal.state, signal.label)
                # Remote events should not reset local idle the same way, but
                # seeing the fleet work is still activity — reset idle so the
                # pet stays awake while its twin works.
                chain = self.engine.handle(ev)
                if chain is not None:
                    print(f"REMOTE {ev.kind.value} tool={ev.tool} "
                          f"cat={ev.category} ({source})", flush=True)
                    self.overlay.play_chain(chain, ev.category)
            elif rtype == "grab":
                try:
                    x, y = int(rec["x"]), int(rec["y"])
                except (KeyError, TypeError, ValueError):
                    continue
                print(f"REMOTE GRAB {x},{y} ({source})", flush=True)
                self.overlay.place_at(x, y)

    def _poll_stuck(self) -> None:
        """Raise an evidence-backed 'stuck' attention label, never a guess.

        Runs each cycle but only changes the label when the verdict actually
        flips, so it does not spam set_attention on every 100ms tick.
        """
        if getattr(self, "stuck", None) is None:
            return
        verdict = self.stuck.check(now=time.time())
        state = verdict.state
        if state == self._stuck_state:
            return
        self._stuck_state = state
        if state == "stuck" and hasattr(self.overlay, "set_attention"):
            self.overlay.set_attention("stuck", verdict.label)

    def _overlay_busy(self) -> bool:
        return bool(getattr(self.overlay, "_queue", None)) \
            or getattr(self.overlay, "_beat", None) is not None

    def _poll_curiosity(self) -> None:
        """Let the pet notice the desktop without ever hiding Hermes's truth.

        Glances (Hermes busy) only play when nothing else is on screen; quiet
        mode investigations may walk toward what was noticed.
        """
        if self.sensors is None or self.curiosity is None:
            return
        director = getattr(self.overlay, "_director", None)
        if director is not None:
            self._poll_curiosity_director(director)
            return
        if not hasattr(self.overlay, "_beats_for_step"):
            return
        try:
            observations = self.sensors.sample()
        except Exception:
            return  # a sensor hiccup must never break the live pet
        state = self.attention.signal.state
        for obs in observations:
            if obs.kind.value in ("user.back", "input.typing_started", "cursor.moved"):
                # The user is here: don't drift off to sleep in front of them.
                self.engine.idle_elapsed = 0.0
                self.engine._idle_fired.clear()
            reaction = self.curiosity.observe(obs, state)
            if reaction is None:
                continue
            if reaction.glance and self._overlay_busy():
                continue
            if not reaction.glance and self._overlay_busy() and state != "quiet":
                continue
            beats = []
            if reaction.target is not None:
                tx = reaction.target[0] - self.overlay.w // 2
                dx = max(-400, min(400, tx - self.overlay.x))
                if abs(dx) > 40:
                    beats.extend(self.overlay._beats_for_step({
                        "pose": "walk_to_workspace", "duration_ms": 700,
                        "move": {"type": "walk", "dx": dx, "dy": 0,
                                 "duration_ms": 700, "easing": "easeInOutQuad"}}))
            for i, step in enumerate(reaction.steps):
                beats.extend(self.overlay._beats_for_step(step, "idle", i))
            print(f"CURIOUS {obs.kind.value} {[s['pose'] for s in reaction.steps]}", flush=True)
            self.overlay.enqueue(beats, replace=not self._overlay_busy())
            break

    def _poll_curiosity_director(self, director) -> None:
        from hermes_companion.renderer.playground import reaction_chain
        if self._want_perch and self.perch is None and hasattr(self.overlay, "set_y"):
            from hermes_companion.behavior.perch import make_driver
            self.perch = make_driver(self.overlay, director, self.sensors, self.traits)
            rect = getattr(self.overlay, "_home_rect", None)
            if self.traits["entrance"] and rect is not None:
                self.perch.enter(time.monotonic(), rect[1])    # drops in from the top of the screen
        try:
            observations = self.sensors.sample()
        except Exception:
            return
        if self.perch is not None:
            self.perch.tick(time.monotonic(), self.attention.signal.state)
        for obs in observations:
            reaction = self.curiosity.observe(obs, self.attention.signal.state)
            if reaction is None or director.chain is not None:
                continue
            if self.perch is not None and (self.perch.perched or self.perch.motion):
                reaction.target = None
            director.start_chain(reaction_chain(reaction, int(self.overlay.x),
                                                int(self.overlay.w)))
            return

    def poll(self) -> None:
        self._poll_file()
        self._poll_relay()
        self._poll_curiosity()
        self._poll_idle()
        self._poll_stuck()
        self.overlay.root.after(100, self.poll)
