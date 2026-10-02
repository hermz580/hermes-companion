"""Opt-in session-bound companion dock. Never spawns agents or reads content."""
from __future__ import annotations

from dataclasses import dataclass, field
import time
from hermes_companion.behavior.behavior_engine import BehaviorEngine


@dataclass
class PetBinding:
    label: str
    session_id: str = ''
    last_event: str = ''
    last_seen: float | None = None
    category: str = ''
    combo: int = 0
    engine: BehaviorEngine = field(default_factory=lambda: BehaviorEngine(seed=0))

    def status(self, now, source_available):
        if not self.session_id:
            return 'UNBOUND'
        if not source_available:
            return 'DISCONNECTED'
        if self.last_seen is None:
            return 'AWAITING SESSION EVENT'
        if now - self.last_seen > 30:
            return 'STALE / ACTIVITY UNKNOWN'
        return 'RECENT: ' + self.last_event


class FleetModel:
    def __init__(self, pets):
        pets = list(pets)
        if not 1 <= len(pets) <= 4:
            raise ValueError('choose 1-4 companions')
        labels, sessions = set(), set()
        for pet in pets:
            parse_binding(pet.label + ('=' + pet.session_id if pet.session_id else ''))
            if pet.label in labels or (pet.session_id and pet.session_id in sessions):
                raise ValueError('labels and bound sessions must be distinct')
            labels.add(pet.label)
            sessions.add(pet.session_id)
        self.pets = pets
        from hermes_companion.core.companion_registry import AgentBinding, CompanionConfig, CompanionRegistry
        from hermes_companion.core.companion_routing import CompanionEventRouter
        self.registry = CompanionRegistry(tuple(
            CompanionConfig(f'dock-{i}', pet.label, 'observer', 'active-profile-atlas',
                            AgentBinding(pet.session_id) if pet.session_id else None,
                            context_permissions=())
            for i, pet in enumerate(pets)))
        self.router = CompanionEventRouter(self.registry)
        self._indices = {c.companion_id: i for i, c in enumerate(self.registry.companions)}

    def accept(self, record, now=None):
        from hermes_companion.behavior.choreography import compile_delivery
        decision = self.router.route_record(record)
        result = {}
        for delivery in decision.deliveries:
            i = self._indices[delivery.companion_id]
            pet = self.pets[i]
            event = delivery.event
            pet.last_event = event.kind.value
            pet.last_seen = time.monotonic() if now is None else now
            pet.category = event.category
            chain = pet.engine.handle(event)
            if chain:
                pet.combo = pet.engine.trace[-1].get('combo_tier', 1)
                result[i] = compile_delivery(delivery, chain)
            # Renderer needs no unbounded event history.
            pet.engine.trace[:] = pet.engine.trace[-32:]
        return result


def parse_binding(text):
    import re
    parts = text.split('=')
    if len(parts) > 2 or not re.fullmatch(r'[A-Za-z0-9 _-]{1,24}', parts[0]):
        raise ValueError('binding must be Label or Label=session_id')
    session = parts[1] if len(parts) == 2 else ''
    if len(parts) == 2 and not re.fullmatch(r'[A-Za-z0-9_.:-]{1,128}', session):
        raise ValueError('session_id must be a bounded identifier')
    return PetBinding(parts[0], session)


class BoundedTail:
    """Read only newly appended complete, bounded records; never replay history."""
    def __init__(self, path, *, auth_key=None):
        from hermes_companion.core.event_auth import load_or_create_event_key
        self.path = path
        self.auth_key = auth_key or load_or_create_event_key(path.parent / 'event-auth.key')
        self.available = False
        self.offset = 0
        self.identity = None
        self.pending = b''
        self.dropping = False
        try:
            stat = path.stat()
            self.identity = (stat.st_dev, stat.st_ino)
            self.offset = stat.st_size
        except OSError:
            pass

    def poll(self):
        import json
        try:
            stat = self.path.stat()
            identity = (stat.st_dev, stat.st_ino)
            if identity != self.identity or stat.st_size < self.offset:
                self.offset, self.pending, self.dropping = 0, b'', False
            self.identity = identity
            with self.path.open('rb') as stream:
                stream.seek(self.offset)
                data = stream.read(65536)
                self.offset = stream.tell()
            self.available = True
        except OSError:
            self.available = False
            return []
        lines = (self.pending + data).split(b'\n')
        self.pending = lines.pop()
        records = []
        for line in lines:
            if self.dropping:
                self.dropping = False
                continue
            if len(line) > 8192:
                continue
            try:
                value = json.loads(line)
                if isinstance(value, dict):
                    from hermes_companion.core.event_auth import verify_record
                    authenticated = verify_record(value, self.auth_key)
                    if authenticated is not None:
                        records.append(authenticated)
            except (ValueError, UnicodeError):
                pass
        if len(self.pending) > 8192:
            self.pending = b''
            self.dropping = True
        return records


class MultiPetDock:
    """One bounded no-activate dock, one independent engine per binding.

    Existing atlas rows express chains, not new artwork. All status is local
    event evidence; no process-health inference, sensor, or agent creation.
    """
    def __init__(self, bindings, sheets, events, *, simulation=False, visible=True,
                 root=None):
        import tkinter as tk
        from PIL import Image, ImageTk
        from hermes_companion.renderer.petdex_overlay import STATE_ROWS, POSE_ROW
        self.tk, self.pose_rows = tk, POSE_ROW
        self.model = FleetModel(bindings)
        self.tail = BoundedTail(events)
        self.simulation = simulation
        self.visible = bool(visible)
        self.quiet = False
        # An injected root lets a host app (or the test harness) own the Tk
        # interpreter while this dock still gets its own window. Sharing the
        # interpreter avoids re-initialising Tcl per dock; sharing the *window*
        # would let two docks fight over geometry and visibility.
        self._owns_root = root is None
        self.root = tk.Tk() if root is None else tk.Toplevel(root)
        self.root.withdraw()
        self.root.title('Hermes companions - ' + ('SIMULATION' if simulation else 'event observers'))
        self.root.overrideredirect(True)
        self.root.configure(bg='#101a2c')
        self.root.attributes('-topmost', True)
        self.root.protocol('WM_DELETE_WINDOW', self.close)
        self._tick_id = None
        self.width = 230 * len(bindings)
        self.height = 368
        if self.visible:
            x = max(0, (self.root.winfo_screenwidth() - self.width) // 2)
            y = max(0, self.root.winfo_screenheight() - self.height - 70)
        else:
            x = y = 10000
            self.root.attributes('-alpha', 0.0)
        self.root.geometry(f'{self.width}x{self.height}+{x}+{y}')
        self.canvas = tk.Canvas(self.root, width=self.width, height=self.height,
                                bg='#101a2c', highlightthickness=0, takefocus=0)
        self.canvas.pack()
        title = 'SIMULATION - NOT AGENT ACTIVITY' if simulation else 'SESSION OBSERVERS - click a companion for status'
        self.canvas.create_text(12, 17, text=title, anchor='w', fill='#c2d7ee', font=('Segoe UI', 10, 'bold'))
        self.quiet_control = self.canvas.create_text(
            self.width-76, 17, text='QUIET: OFF', fill='#8ce0b0',
            font=('Segoe UI', 9, 'bold'))
        self.canvas.tag_bind(self.quiet_control, '<Button-1>', self.toggle_quiet)
        close = self.canvas.create_text(self.width-16, 17, text='X', fill='#ffffff')
        self.canvas.tag_bind(close, '<Button-1>', lambda e: self.root.destroy())
        self.frames, self.items, self.labels, self.animations = [], [], [], {}
        colors = ['#70d6ff', '#f6b96b', '#bca3ff', '#8ce0b0']
        for i, (pet, sheet) in enumerate(zip(bindings, sheets)):
            x = i * 230
            self.canvas.create_rectangle(x+6, 36, x+224, 254, fill='#19263c', outline=colors[i])
            self.canvas.create_text(x+115, 53, text=pet.label, fill=colors[i], font=('Segoe UI', 12, 'bold'))
            frames = {}
            with Image.open(sheet) as image:
                image = image.convert('RGBA')
                if image.width < 192*6 or image.height < 208*9:
                    raise ValueError('sprite atlas must contain at least 6 x 9 cells')
                for r, row in enumerate(STATE_ROWS):
                    frames[row] = [ImageTk.PhotoImage(image.crop((c*192, r*208, (c+1)*192, (r+1)*208)).resize((132,143)), master=self.root) for c in range(6)]
            self.frames.append(frames)
            self.items.append(self.canvas.create_image(x+115, 146, image=frames['idle'][0]))
            self.labels.append(self.canvas.create_text(x+115, 230, text='', fill='#dce8f5', width=205, font=('Segoe UI', 9)))
        self.detail = self.canvas.create_text(14, 270, anchor='nw', fill='#dce8f5', font=('Segoe UI', 9), width=self.width-28)
        self.selected = 0
        self.canvas.bind('<Button-1>', self._click)
        self.root.update_idletasks()
        # Tk may recreate its wrapper or request activation while deiconifying.
        # Disable input during that mapping only; reapply NOACTIVATE to the final
        # wrapper before enabling clicks. Never repair focus by stealing it back.
        if self.visible:
            import os
            if os.name == 'nt':
                self.root.attributes('-disabled', True)
            self._no_activate()
            self.root.deiconify()
            self.root.update()
            self._no_activate()
            if os.name == 'nt':
                self.root.attributes('-disabled', False)
        self.root.after(0, self.tick)

    def _no_activate(self):
        import os
        if os.name == 'nt':
            import ctypes
            user32 = ctypes.windll.user32
            hwnd = user32.GetParent(self.root.winfo_id())
            style = user32.GetWindowLongW(hwnd, -20)
            user32.SetWindowLongW(hwnd, -20, style | 0x08000000 | 0x00000080)

    def _click(self, event):
        if 36 <= event.y <= 254:
            self.selected = min(len(self.model.pets)-1, max(0, event.x // 230))
            self.refresh_status(time.monotonic())

    def toggle_quiet(self, _event=None):
        """Suppress motion without discarding accepted event evidence."""
        self.quiet = not self.quiet
        if self.quiet:
            self.animations.clear()
            for pet in self.model.pets:
                pet.engine.end_chain()
        self.canvas.itemconfigure(
            self.quiet_control,
            text='QUIET: ON' if self.quiet else 'QUIET: OFF',
            fill='#f6b96b' if self.quiet else '#8ce0b0')
        self.refresh_status(time.monotonic())

    def accept(self, record):
        for index, chain in self.model.accept(record).items():
            if self.quiet:
                self.model.pets[index].engine.end_chain()
            else:
                self.animations[index] = (list(chain.steps), time.monotonic())

    def refresh_status(self, now):
        for i, pet in enumerate(self.model.pets):
            status = pet.status(now, self.tail.available or self.simulation)
            if self.quiet and status != 'UNBOUND':
                status = 'QUIET · ' + status
            self.canvas.itemconfigure(self.labels[i], text=status)
        pet = self.model.pets[self.selected]
        age = 'none' if pet.last_seen is None else f'{max(0, now-pet.last_seen):.1f}s ago'
        text = (f'{pet.label} | session: {pet.session_id or "UNBOUND (no agent attached)"}\n'
                f'Last observed: {pet.last_event or "none"} | {age} | category: {pet.category or "none"} | combo tier: {pet.combo}\n'
                'Event evidence only; silence is not proof of running or stopped.\n'
                'More pets do NOT create agents. Camera / screen / context: OFF.')
        if self.simulation:
            text = 'SIMULATION - synthetic fixture, not live session evidence\n' + text
        self.canvas.itemconfigure(self.detail, text=text)

    def tick(self):
        import math
        now = time.monotonic()
        if not self.simulation:
            for record in self.tail.poll():
                self.accept(record)
        for i, pet in enumerate(self.model.pets):
            row, dx, dy = 'idle', 0, 0
            animation = self.animations.get(i)
            if animation:
                steps, start = animation
                while steps and now-start >= max(0.16, steps[0].get('duration_ms', 800)/1000):
                    start += max(0.16, steps.pop(0).get('duration_ms', 800)/1000)
                if steps:
                    self.animations[i] = steps, start
                    step = steps[0]
                    row = self.pose_rows.get(step.get('pose'), 'idle')
                    progress = min(1, (now-start)/max(.16, step.get('duration_ms', 800)/1000))
                    move = step.get('move') or {}
                    dx = max(-25, min(25, move.get('dx', 0))) * math.sin(progress*math.pi)
                    dy = -min(14, abs(move.get('dy', 0)) or (12 if row == 'jumping' else 0))*math.sin(progress*math.pi)
                else:
                    self.animations.pop(i, None)
                    pet.engine.end_chain()
            # Unbound/quiet companions stay in idle; no synthetic work loops.
            frame = int(now*8) % 6 if animation else 0
            self.canvas.itemconfigure(self.items[i], image=self.frames[i][row][frame])
            self.canvas.coords(self.items[i], i*230+115+dx, 146+dy)
        self.refresh_status(now)
        self._tick_id = self.root.after(80, self.tick)

    def close(self):
        """Stop this dock's animation loop and release its window."""
        if self._tick_id is not None:
            try:
                self.root.after_cancel(self._tick_id)
            except Exception:
                pass
            self._tick_id = None
        self.root.destroy()


def cmd_multi(args):
    import math
    from pathlib import Path
    from hermes_companion.renderer.live import active_pet, hermes_home
    bindings = [parse_binding(v) for v in (args.bind or ['Scout', 'Builder', 'Guide'])]
    if not 1 <= len(bindings) <= 4 or len({p.label for p in bindings}) != len(bindings):
        raise ValueError('choose 1-4 companions with distinct labels')
    if not math.isfinite(args.duration) or not 0 <= args.duration <= 86400:
        raise ValueError('duration must be finite, 0 (until closed) or at most 86400 seconds')
    if args.simulation and args.duration == 0:
        raise ValueError('simulation requires a bounded --duration')
    sheet = active_pet()[1]
    sheets = [sheet] * len(bindings)
    dock = MultiPetDock(bindings, sheets, Path(args.events) if args.events else hermes_home() / 'companion' / 'events.jsonl', simulation=args.simulation)
    if args.simulation:
        for i, pet in enumerate(bindings):
            if not pet.session_id:
                continue
            for delay, event, tool in [(400, 'tool.started', 'terminal'), (1400, 'tool.finished', 'terminal'), (2100, 'tool.started', 'web_search'), (3100, 'tool.failed', 'web_search')]:
                dock.root.after(delay+i*200, lambda p=pet, e=event, t=tool: dock.accept({'session_id': p.session_id, 'event': e, 'tool': t}))
    if args.duration:
        dock.root.after(int(args.duration*1000), dock.root.destroy)
    print('MULTI READY: observers only; no agents spawned; context OFF' + ('; SIMULATION' if args.simulation else ''), flush=True)
    dock.root.mainloop()
    return 0
