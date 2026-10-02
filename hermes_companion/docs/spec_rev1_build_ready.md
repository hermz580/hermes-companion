# HERMES EMBODIED COMPANION RUNTIME — REVISION 1 (BUILD-READY)

## Event-Reactive Desktop Character / Visual Agent Interface

### Working name: HERMES PET ENGINE v0.1
### Spec status: REVISION 1 after Na'zurak red assurance (2026-08-29). Supersedes the original build spec for build purposes.

---

## REVISION LOG — HOW THIS SPEC CHANGED (finding → resolution)

| ID | Finding (severity) | Resolution in this revision |
|----|--------------------|------------------------------|
| M1 | No trust boundary; raw event data reaches an always-on renderer | NEW §5 Trust Boundary. Companion is a plugin; events validated + allow-listed at the edge; renderer treats ALL content as untrusted; nothing is rendered as text |
| M2 | "Build an event bus" reimplements the existing hook surface | NEW §6 Event Surface maps every event to a REAL installed hook (verified in C:/Users/HarpStar/AppData/Local/hermes/hermes-agent/). No new bus. Only typing/prompt events need new instrumentation |
| M3 | "No keylogger" vs default-on typing awareness contradiction | §7 defines the input surface precisely (TUI prompt buffer only) and defaults ALL typing awareness OFF; prompt derivation happens in-core, only derived scalars cross the boundary |
| M4 | Event bus has no integrity model; local processes can inject events | §5.3 in-process plugin path eliminates the class; if a separate renderer process is ever added, per-run token + validated IPC + renderer-is-dumb rule. Forge test in acceptance gate |
| M5 | Compound-chain interruption undefined | NEW §10 Chain Interruption. Finish-current-atomic-step then jump; commit points; per-event cooldown; P0/P1 storms cannot starve completion visuals |
| M6 | MVP depends on telemetry the permission set forbids; no overlay pointer policy | §13 MVP input reference = Hermes window bounds only. NEW §33 Overlay Pointer Policy: click-through overlay except sprite hitbox |
| M7 | Build order contradicts the vertical-slice advice | §32 Build Order reversed: walking skeleton first (renderer + one wired event end-to-end) |
| m1 | DPI/multi-monitor math unspecified | §14 movement in physical pixels, per-monitor work-area clamp, DPI test matrix |
| m2 | No resource/energy budget | NEW §31 Resource Budget: fps cap, frame-skip when idle, pause on no activity, CPU/GPU gate |
| m3 | Weighted randomness makes behavior untestable | §17 determinism flag + seed; §26 Companion Emit CLI (synthetic event injection); variance OFF in QA |
| m4 | No session scoping; cron/gateway/CLI conflation | §30 Session Scoping — session_id already present in every hook envelope |
| n1 | Hatch export underspecified | §28 scoped to Milestone 4 with a real-manifest spike and explicit exportable set |
| n2 | No source-level debounce | §31 coalescing in the sensor layer |
| n3 | No reduced-motion consideration | §17.1 OS reduced-motion → extravagance 0 |
| n4 | Memory events could render content | §5.4 memory events carry op + entity-class only, never content |

Verdict context: this revision is the REPAIR PASS artifact. Per the review gate, it requires a fresh independent VANTA review before the build is authorized. It is written to be buildable as specified.

---

## CORE IDEA (unchanged — this is the product)

Do not treat the companion as a decorative animated pet. Build it as a visible
embodiment of Hermes. The character communicates what Hermes is doing through
movement, posture, location, expression, animation, sound cues when enabled,
and interaction with the desktop. The user should be able to look at the
companion and understand:

* Hermes is listening. * Hermes noticed me typing. * Hermes received my instruction.
* Hermes is thinking. * Hermes is searching. * Hermes is using a tool.
* Hermes is reading a file. * Hermes is writing code. * Hermes is testing something.
* Hermes hit an error. * Hermes needs my approval. * Hermes is waiting on something.
* Hermes completed a task. * Hermes has been idle. * Hermes noticed something important.
* Hermes is handling multiple operations. * Hermes recovered from an error.

The companion is a form of AGENT OBSERVABILITY: it makes normally invisible AI
behavior visible. That is the product, not the animation.

The design rule from the original spec stands: the character must never merely
represent "loading." The animation reveals the category of work Hermes is
performing. The user learns Hermes's movement language the way people learn
another person's body language.

---

## 1. ARCHITECTURAL PRINCIPLE

The pipeline is preserved, but its first stage is now grounded in the REAL
Hermes extension surface instead of a bespoke bus:

```
HERMES CORE (existing hooks: pre/post_tool_call, approval, session, subagent, stream, api_error...)
        ↓  plugin boundary — VALID_HOOKS dispatch, in-process
HERMES_COMPANION PLUGIN
    event adapter (validate + allow-list → semantic events)
        ↓
    CONTEXT INTERPRETER
        ↓
    BEHAVIOR ENGINE
        ↓
    EMOTION / INTENT STATE
        ↓
    MOVEMENT PLANNER
        ↓
    ANIMATION RENDERER
        ↓
    DESKTOP COMPANION (overlay window)
```

Two hard rules:

1. **Hermes core is NOT modified.** The companion is a plugin installed into
   `~/.hermes/plugins/` (standalone plugin repo per AGENTS.md — a product, not
   a core contribution). It subscribes to existing hooks declared in its
   `plugin.yaml` and registers callbacks via `hermes_cli.plugins`.
2. **No event field is ever rendered as text.** The renderer displays the
   character only. Semantic states, not content.

This preserves the original abstraction goal: animation packs and characters
can be swapped without changing Hermes.

---

## 2. WHY A PLUGIN AND NOT AN EVENT BUS (replaces old §2)

The original spec proposed building an event bus. The installed Hermes core
already has a richer event surface than the spec proposed, with the exact
semantic events needed. Building a parallel bus would duplicate the
observability pipeline, fork the event story, and be rejected upstream
(AGENTS.md: "extend, don't duplicate"; "no speculative infrastructure").

**The event bus for v0.1 IS the existing hook system.** The companion plugin
declares which hooks it subscribes to and receives structured callbacks. The
only genuinely missing instrumentation — user typing and prompt submission in
the CLI input path — is added in-core as two additive, non-breaking emits.

Verified ground truth this revision relies on (all present in the installed
source at C:/Users/HarpStar/AppData/Local/hermes/hermes-agent/):

- `hermes_cli/plugins.py` — `VALID_HOOKS` set; plugins register callbacks and
  declare subscriptions in `plugin.yaml`.
- `agent/agent_runtime_helpers.py` — dispatches `pre_tool_call` /
  `post_tool_call`; envelope includes `function_name, function_args, result,
  task_id, session_id, tool_call_id, turn_id, api_request_id, duration_ms,
  status, error_type, error_message`.
- `agent/codex_runtime.py` — `_fire_tool_started` (tool.started) and a
  structured `tool_start_callback(stable_id, name, args)` already feeding a
  tool-card surface in TUI/desktop.
- `plugins/observability/langfuse/` — reference implementation of a hook
  plugin with a capture-mode ladder (metadata | sanitized | full) and
  secret redaction via `agent.redact.redact_sensitive_text`.
- `cli-config.yaml.example` — documents the hook names.

The Langfuse plugin is the pattern to copy for plugin structure, sanitization,
and fail-open behavior. The companion differs in one way: its hooks are the
ONLY source of truth for behavior (Langfuse is an optional exporter).

---

## 3. EVENT STRUCTURE (unchanged shape, tightened contract)

```json
{
  "event": "tool.started",
  "source": "hermes",
  "tool": "browser",
  "timestamp": 1788000000,
  "session_id": "20260829_...",
  "task_id": "task_123",
  "turn_id": "turn_7",
  "importance": 0.6,
  "metadata": {}
}
```

**Contract change (M1):** `metadata` is restricted to an allow-list of
non-sensitive keys per event type (see §5). Unknown keys are dropped at the
plugin edge, not forwarded. `session_id` and `task_id` are populated from the
hook envelope — no new instrumentation needed.

---

## 4. EVENT CATEGORIES (unchanged taxonomy)

```
user.*   agent.*  tool.*  memory.*  file.*  code.*  web.*
system.* task.*   approval.*  error.*  notification.*  desktop.*
```

---

## 5. TRUST BOUNDARY & DATA POLICY (NEW — resolves M1, M3, M4)

Hermes core handles credentials, prompts, file contents, and reads untrusted
web/subagent output. The companion is an always-on surface. This boundary is
the most important design decision in the system.

### 5.1 Boundary definition
- All event data crosses from core to plugin through the hook dispatch. The
  plugin's **event adapter** is the only reader of raw hook payloads.
- The adapter validates the payload against a per-hook schema, applies an
  allow-list projection, and emits only **semantic events** (typed, bounded
  enums + scalar metadata) to the behavior engine.
- The renderer and behavior engine receive semantic events only. They never
  see `function_args`, `result`, `command`, file paths, window titles, or
  prompt text.
- Nothing below the adapter may render an event field as text. A semantic
  event may carry an enum like `tool="github"` — it is mapped to a behavior,
  not displayed.

### 5.2 Sanitization
- Raw payload fields (`function_args`, `result`) are dropped unless a specific
  allow-listed key is needed, and then redacted first using the project-wide
  `agent.redact.redact_sensitive_text` primitive (50+ credential patterns).
- The plugin ships with a **capture mode** defaulting to `metadata` (lowest
  capture): tool name, category, status, duration, task/session id. No args,
  no result content. `sanitized` mode may add operation-class only. `full` is
  a debugging mode, default OFF, and must warn in the UI when enabled.

### 5.3 Integrity (resolves M4)
- v0.1 runs the behavior engine in-process with the plugin. There is no
  cross-process event bus, so the local-injection class does not exist.
- If a separate renderer process is ever needed (Milestone 3+, e.g. for
  crash isolation), it is spawned BY the plugin, authenticated with a
  per-run random token, and the renderer is a **dumb display**: it receives
  already-decided semantic states and can never influence behavior or emit
  events upstream.
- The acceptance gate includes a forged-event test (see §34).

### 5.4 Memory events (resolves n4)
- `memory.*` events carry only `operation` (store | retrieve | conflict) and
  `entity_class` (enum). They never carry content, keys, or values.

---

## 6. EVENT SURFACE — REAL HOOK MAPPING (NEW — resolves M2, m4)

This table is the single source of truth for v0.1 integration. Each semantic
event maps to a verified hook or to explicitly-new instrumentation.

### 6.1 Tool lifecycle
| Semantic event | Source | Notes |
|---|---|---|
| tool.started | `pre_tool_call` | tool name + category from function_name |
| tool.finished | `post_tool_call` (status ok) | + duration_ms |
| tool.failed | `post_tool_call` (status error) | + error_type; no error content |
| tool.blocked | `post_tool_call` (status blocked) | approval-adjacent |

### 6.2 Agent / session lifecycle
| Semantic event | Source |
|---|---|
| agent.awake / agent.idle / agent.sleep | `on_session_start` / `on_session_end` / idle sensor |
| agent.responding | `on_stream_start` / `on_stream_end` (streaming) |
| agent.thinking | `post_llm_call` + reasoning heuristic (bounded) |
| agent.testing | `pre_verify` |
| agent.delegating / subagent_spawned / subagent_finished | `subagent_start` / `subagent_stop` |
| agent.error | `api_request_error` / `transform_api_error_classification` (semantic severity only) |

### 6.3 Approval (resolves M1's approval-command leak)
| Semantic event | Source | Notes |
|---|---|---|
| approval.required | `pre_approval_request` | emit ONLY `surface` enum + presence; the `command` kwarg is DROPPED at the adapter, never forwarded |
| approval.approved / approval.rejected | `post_approval_response` | emit `choice` enum only |

### 6.4 New instrumentation (the ONLY core additions — additive, non-breaking)
| Semantic event | Where | Notes |
|---|---|---|
| user.typing_started / user.typing_speed / user.typing_stopped | CLI input path (prompt_toolkit buffer) | derived scalars only (see §7) |
| user.prompt_submitted | CLI input path | on Enter; length + category scalar only |

These two emissions follow AGENTS.md ("extend, don't duplicate"; additive
hooks with a real consumer = this plugin). They fire only in the CLI/TUI
input path, not globally.

### 6.5 Deferred to milestones (exist today, wired later)
`on_skill_lifecycle` (skill use), kanban task hooks (long-running jobs),
`on_interim_message` (live listening), `pre_gateway_dispatch` (gateway input).

---

## 7. USER EVENTS & TYPING AWARENESS (resolves M3)

### 7.1 Input-surface definition (was undefined — now precise)
"Hermes-owned input surface" = **the Hermes TUI prompt buffer (the
prompt_toolkit session), and nothing else.** Not the terminal window, not the
OS. The terminal window on Windows hosts other content and is NOT in scope.

### 7.2 Derived scalars only
Core derives, then emits:
```
typing_started (bool)
typing_speed (chars/sec, coarse buckets: slow | normal | fast)
typing_paused (bool)
prompt_length (coarse: short | medium | long)
prompt_category (enum, from tool-requirement heuristics, never content)
```
Raw prompt text NEVER leaves core. Typing events are ephemeral, coalesced at
the source (n2), and never stored.

### 7.3 Permission
- `hermes_text_input_awareness` is **DEFAULT OFF** (resolves M3).
- Global keyboard / cursor awareness: require explicit opt-in, remain OFF in
  v0.1, and are only milestones 2+.
- The pet's input-awareness behaviors (look at input, watch, lean) are gated
  on the toggle. With it OFF, the pet reacts only to the window-bounds
  reference (§13) — enough for the demo's first beat without any keylogging.

### 7.4 Pointer events
`pet_clicked`, `pet_double_clicked`, `pet_dragged` are local to the plugin's
overlay window (see §33). `mouse_near_pet`/`hover`/`leave` require pointer
sensor, default OFF.

---

## 8. HERMES AGENT EVENTS (unchanged from original intent, now mapped in §6)

```text
agent.awake  agent.received_prompt  agent.thinking  agent.planning
agent.delegating  agent.subagent_spawned  agent.subagent_finished
agent.waiting  agent.responding  agent.task_complete  agent.task_cancelled
agent.confused  agent.recovering
```
Internal hidden reasoning is NOT exposed as raw text. The companion receives
only high-level operational state: `reasoning, planning, searching, waiting,
checking, testing, recovering`.

---

## 9. TOOL EVENTS (kept — the expressive core)

Every tool has a behavioral family. `tool.started`, `tool.progress`,
`tool.completed`, `tool.failed` per tool category:

- Browser / web → binoculars, scan horizon, search cards, portal fly, pace.
- Terminal → miniature terminal, rapid typing, floating command lines,
  crouch-process, hammer Enter.
- GitHub → glowing branch tree, inspect/combine branches, stamp commit, push
  cube into cloud.
- File system → open folders, dig drawers, carry docs, stack files, tray.
- Code generation → glow blocks, assemble structures, weld fragments,
  miniature workstation.
- Testing → goggles, inspect machine, press TEST, watch indicators. PASS =
  jump/fist-pump/fireworks; FAIL = sparks, fall-back, recovery.
- Memory → carry glowing object to vault / retrieve / compare artifacts
  (content never rendered — §5.4).
- Image generation → canvas/paint/light. Audio → headphones/waveform.
  Calendar → clock/scroll. Email → envelope/messenger bird.

---

## 10. CHAIN INTERRUPTION SEMANTICS (NEW — resolves M5)

Compound movements (§ of original; retained) chain atomic steps:
`notice → look_right → crouch → dash_right → summon_hologram → scan → inspect →
close_hologram → return_home`.

Rules:

1. **Interruption granularity = atomic step.** A higher-priority event
   interrupts only between steps. The current atomic step finishes; the chain
   aborts at the next commit point; the interrupt's own chain starts from a
   neutral pose (never mid-step).
2. **Commit points** are declared per chain (e.g. after `land`, after
   `teleport_reappear`, after `stand_up`). Only commit points are safe jump
   boundaries; the engine refuses to abort inside non-interruptible steps
   (landing, teleport_reappear, stand_up).
3. **Per-event-type cooldown** (part of motion budget §17): the same semantic
   event cannot restart its chain within `cooldown_ms` unless it is P0/P1.
4. **Storm rule:** bursts of P2+ events coalesce into ONE state change, not N
   chain restarts. A P0/P1 interrupt (e.g. approval while sleeping) always
   wins and always reaches its terminal state — completion/recovery visuals
   are never starved.
5. **Deterministic under test:** with a fixed seed and a synthetic event
   stream, chain selection and interruption outcomes are reproducible (§26).

---

## 11. BEHAVIOR STATES (kept)

```
idle curious attentive listening reading thinking planning searching building
coding testing organizing remembering retrieving waiting confused concerned
focused celebrating frustrated recovering sleeping urgent calling_user
following traveling observing
```
These are semantic states, each mapping to many animations.

## 12. EMOTES (kept)

wave nod shake_head shrug look_left/right/up/down blink double_blink scratch_head
cross_arms tap_foot sit sleep wake stretch laugh celebrate facepalm panic glitch
recover inspect scan point beckon listen think type read write build hammer run
dash jump double_jump spin fly hover teleport slide crawl peek hide fall trip land

A state selects among emotes with weighted variety (§17).

---

## 13. ACTIVE WINDOW AWARENESS — MVP BOUND (resolves M6)

**MVP:** the companion knows only the Hermes active window bounds. This is
available to the plugin from the hook/session context and the existing
tool-card surface — no extra sensor, no permission change. "Look at input" =
look toward the Hermes window. This makes the demo's first beat possible with
ALL sensors off.

**Milestone 2+ (opt-in):** caret position, cursor, window contents awareness —
each gated behind explicit permission, matching §23's settings.

Possible sequence (unchanged, now gated):
```
typing_started → pet looks toward input box
typing_continues → pet watches
typing_fast → pet leans forward
typing_pause → pet looks at user
prompt_submitted → pet jumps
agent_started → pet runs toward workspace
```

---

## 14. MOVEMENT CONTROLLER (kept + DPI-aware — resolves m1)

Home/current/target position, screen bounds, safe zones, blocked zones,
taskbar, active-window bounds, monitor bounds.

Commands: move_to, walk_to, run_to, dash_to, fly_to, jump_to, teleport_to,
return_home, follow_cursor (opt-in), move_near_window, peek_from_edge.

**DPI rule (m1):** all coordinates are PHYSICAL pixels per monitor. The
controller maps logical→physical using the per-monitor DPI, clamps to the
monitor work area (excludes taskbar), and picks the monitor under the active
window for "move_near_window." A multi-monitor mixed-DPI test matrix is part
of the acceptance gate.

Dash easing: easeInQuad, easeOutQuad, easeInOutCubic, spring, bounce,
overshoot — preserved.

## 15. FLYING (kept)
takeoff hover fly_left/right/up/down bank_left/right land crash_land; orbit
active window, hover near notification, descend on tool finish, shoot upward
on major operation start.

## 16. PROMPT-AWARE BEHAVIOR (kept, content-free)
Only derived properties: prompt_length, typing_speed, task_category, urgency,
complexity_estimate, tool_requirement. Short prompt → casual reaction; large
complex prompt → read upward, gulp, crack knuckles, go to work.

## 17. PERSONALITY, VARIATION & MOTION BUDGET (kept + determinism — m3, n3)

Personality config, weighted animation selection, extravagance level 0-5, and
motion budget are retained from the original.

**Additions:**
- **Determinism flag (m3):** when enabled (default in QA), all weighted
  selections use a fixed seed. The behavior engine's PRNG is injectable.
- **Reduced motion (n3):** OS reduced-motion setting forces extravagance 0.
  Extravagance 0 = almost motionless (blink, look, no travel).
- Motion budget from the original: `max_major_motion_per_minute`,
  `max_screen_crossings_per_minute`, `idle_animation_interval`, celebration
  probability. P0/P1 events may override; P2+ cannot.

## 18. EVENT PRIORITY (kept)
P0 critical · P1 user attention · P2 failure · P3 completion · P4 active task ·
P5 information · P6 idle. Sleep → approval-required interrupt: wake → panic →
run toward user → wave.

## 19. TOOL PERSONALITIES (kept — §9 details)

## 20. MULTI-AGENT MODE (kept — now mapped to subagent hooks)
Main Hermes stays on-screen. On `subagent_start`: open portal → small
agent-orb exits → orb travels to task zone (color-coded by subagent). On
`subagent_stop`: orb returns, Hermes absorbs result.

## 21. TASK ZONES (kept)
Left = memory, right = tools, top = network, bottom = user interaction.

## 22. ERROR BEHAVIOR & RECOVERY (kept)
Severity ladder: minor → shake_head; tool failure → spark/inspect; repeated →
frustrated/repair; serious → alarm/red state/call user. Animation reflects
ACTUAL severity; never imply the computer itself is failing. Recovery is its
own state: tool_failed → fall → stand → inspect → retry → small celebration.

## 23. APPROVAL MODE (kept, content-free — M1)
Hermes visibly stops, turns toward user, walks near the input area, waves,
points, waits. Approved → nod → run back. Rejected → nod → discard action.
**The approval payload's raw command string is dropped at the adapter (§5.1).**
The pet never indicates what the command was — only that approval is needed.

---

## 24. SECURITY & PRIVACY POLICY (consolidated — resolves M1, M3, M4)

1. The companion is a plugin; it never modifies Hermes core.
2. Input monitoring is limited to the Hermes TUI prompt buffer and defaults OFF.
3. Global keyboard/cursor/microphone events require explicit opt-in; not in v0.1.
4. Keystrokes are never stored. Typing emits only ephemeral derived scalars.
5. Raw prompt text, tool args, results, commands, file paths, and window titles
   never cross the adapter's allow-list. Sensitive data never enters animation
   or renderer logic.
6. All sensors are individually toggleable (§25).
7. The renderer treats every input as untrusted; nothing is rendered as text.
8. Memory events carry op + entity-class only.
9. In-process plugin path in v0.1; any future separate process uses a per-run
   token and a dumb renderer (§5.3).
10. Local forge test in acceptance gate (§34).

## 25. SENSOR SETTINGS (revised defaults — resolves M3, M6)

```
[X] Hermes activity              (default ON — from existing hooks, no new sensor)
[X] Tool activity                (default ON — from existing hooks)
[ ] Pointer interaction          (default OFF)
[ ] Hermes text-input awareness  (default OFF — NEW, was ON)
[ ] Idle detection               (default ON — from session hooks)
[ ] Active application awareness (default OFF, opt-in, Milestone 2+)
[ ] Global cursor awareness      (default OFF, opt-in, Milestone 2+)
[ ] Global keyboard awareness    (default OFF, opt-in, never in v0.1)
[ ] Microphone reactions         (default OFF, opt-in)
```
With defaults, the pet is fully functional using only existing hooks +
window-bounds reference — no surveillance surface.

---

## 26. COMPANION EMIT CLI (NEW — resolves m3; the S30 API, made real)

For development, QA, and user demos, the plugin ships a CLI:

```
hermes-companion emit tool.started tool=github --seed 42
hermes-companion emit approval.required
hermes-companion emit task.complete
hermes-companion inject tests/event_burst_50.json   # storm test
```

This is the synthetic event-injection path that makes the behavior engine
deterministically testable and is the ONLY way to drive the pet without a
live Hermes session.

---

## 27. IMPLEMENTATION LAYERS (revised layout — resolves M2)

```
hermes_companion/                      (standalone plugin repo, installed to ~/.hermes/plugins/)
    plugin.yaml                        # declares hook subscriptions (pre_tool_call, post_tool_call,
                                       # pre_approval_request, post_approval_response, on_session_start/end,
                                       # subagent_start/stop, on_stream_start/end, api_request_error, pre_verify)
    __init__.py                        # plugin entry; registers callbacks via hermes_cli.plugins
    adapter/
        schemas.py                     # per-hook validation + allow-list projection  (M1/M4)
        redact.py                      # wraps agent.redact.redact_sensitive_text
        map_hooks.py                   # hook → semantic event table (§6)
    core/
        event_bus.py                   # INTERNAL bus of the plugin (post-adapter semantic events only)
        events.py                      # semantic event dataclasses (typed, bounded)
        state.py
    behavior/
        behavior_engine.py             # deterministic w/ injectable PRNG (m3)
        behavior_rules.py
        priorities.py                  # P0-P6 + chain interruption (§10)
    personality/
        personality.py
        emotion.py
    movement/
        movement_controller.py         # physical-pixel, per-monitor DPI (m1)
        pathfinding.py
        easing.py
    animation/
        animator.py
        animation_registry.py
        sprite_loader.py
    sensors/
        hermes_sensor.py               # from hooks
        idle_sensor.py
        pointer_sensor.py              # OFF by default
        input_sensor.py                # OFF by default; TUI-buffer only (§7)
    renderer/
        overlay.py                     # click-through policy (§33)
        window.py
    cli/
        emit.py                        # §26
    config/
        companion.json  animations.json  behavior.json
    tests/                             # includes forge test, storm test, DPI matrix, determinism
```

Names adapt to existing Hermes conventions. The plugin MUST follow the
reference pattern of plugins/observability/langfuse for structure and
fail-open behavior.

---

## 28. EVENT API (kept — now the plugin's internal API)

```python
companion.emit("tool.started", tool="github")       # internal, post-adapter
events.publish(ToolStarted(tool="github", task_id=task.id))
```
Hermes core sends semantic events via hooks; the companion decides what they
mean visually. The renderer never sees the API.

## 29. BEHAVIOR RULES & ANIMATION DEFINITIONS & COMBOS (kept from original §§31-33)
JSON behavior rules (event+match → state → behavior chain), animation
definitions (sprite, fps, loop, movement with easing), and combo macros
(SEARCH_COMBO, BUILD_COMBO, FAIL_COMBO) are unchanged.

---

## 30. SESSION SCOPING (NEW — resolves m4)

Every hook envelope carries `session_id` (verified). The companion is scoped
to the active Hermes session: events from other sessions/profiles (cron runs,
other profiles) are ignored unless a dedicated "show all activity" toggle is
enabled (default OFF). This prevents cron/gateway/CLI conflation from making
the pet behave incoherently. Long-running cron jobs may later opt into a
separate "background job" pet via the kanban/session hooks (Milestone 3).

---

## 31. RESOURCE BUDGET (NEW — resolves m2, n2)

- FPS cap (config: default 24, drops to 8 when sleeping/idle).
- Frame skipping when the pet is static or sleeping.
- Overlay renderer PAUSES when no Hermes activity and no user interaction for
  `inactivity_ms` (default 120s).
- CPU/GPU budget is an acceptance gate: idle < 0.5% CPU, active animation
  < 5% on a reference machine.
- Coalescing: typing/progress events are debounced at the source (n2) — at
  most one typing event per 300ms crosses the adapter.

---

## 32. BUILD ORDER (REVERSED — resolves M7)

**Phase 1 — WALKING SKELETON (the proof, not the infra):**
1. Overlay window with click-through (§33) + one idle sprite.
2. One wired event end-to-end: `pre_tool_call` → tool.started → dash → work
   → celebrate → return_home.
3. The FIRST DEMONSTRATION below, exactly.

**Phase 2 — Behavior engine:** states, priorities, chains, interruption (§10),
emote library, determinism flag + Companion Emit CLI (§26).

**Phase 3 — Tool-specific behavior:** the §9 families; motion budget; variation.

**Phase 4 — Input awareness:** typing events in-core (OFF default), window-bounds
reference, prompt-derived scalars.

**Phase 5 — Personality:** personality params, extravagance, reduced-motion.

**Phase 6 — Deep integrations:** memory events, subagent visuals, skill
lifecycle, long-running job status, multi-monitor movement.

**Phase 7 — Companion Studio** (authoring UI, Milestone 4).

Do NOT begin with 100 animations. Prove:
```
TYPE → SUBMIT → HERMES WAKES → DASHES → WORKS → TOOL RUNS →
RESULT ARRIVES → CELEBRATES → RETURNS HOME
```

---

## 33. OVERLAY POINTER POLICY (NEW — resolves M6)

- The overlay window is an always-on-top, transparent window.
- **Click-through by default:** the OS routes all mouse input through the
  overlay except where the pet sprite's hitbox is. UI under the pet remains
  fully clickable.
- Only the sprite hitbox receives `pet_clicked` / `pet_double_clicked` /
  `pet_dragged` (§7.4). The pet must never block the user's access to any
  application.
- The overlay never captures focus for keyboard input.

---

## 34. ACCEPTANCE GATE — REQUIRED PROOF ON BUILD (no false "done")

Phase 1 (walking skeleton) is not done until these are captured and kept in
`docs/proof/`:

1. Overlay rendered + click-through verified (UI under the pet is clickable
   except on the sprite hitbox).
2. Typing awareness OFF by default; with it ON, only derived scalars visible
   (no raw text anywhere).
3. tool.started → dash → work sequence (one screenshot per chain step).
4. tool.failed → recovery chain; P0 approval interrupt of a sleep animation.
5. task_complete celebration + return_home.
6. Sleep/wake on idle/user-return.
7. **Forge test (M4):** a synthetic event injected from outside the plugin is
   rejected; the pet ignores it.
8. Storm test (M5): 50 alternating events → the pet reaches a terminal state,
   no unbounded chain restarts.
9. Determinism (m3): same seed + same event stream → identical behavior trace.
10. DPI check on at least one non-100% scale monitor (m1).
11. Resource check within budget (§31) on the reference machine.

---

## 35. FIRST DEMONSTRATION (unchanged — now the Phase 1 acceptance)

User begins typing. Hermes looks toward the prompt box (window-bounds ref —
works with sensors OFF). User continues typing. Hermes watches. User pauses.
Hermes tilts its head. User hits Enter. Hermes jumps. Hermes dashes across the
bottom of the screen. Agent execution starts. Hermes opens a holographic
workstation. A tool call begins. Hermes operates the workstation. Tool
succeeds. Hermes closes the station. Task completes. Hermes performs a brief
celebration. Hermes walks back to its resting position. After prolonged
inactivity Hermes falls asleep. When the user returns Hermes wakes and waves.

---

## 36. HATCH COMPATIBILITY (scoped — resolves n1)

- Deferred to Milestone 4, NOT v0.1.
- Before building the exporter, run a SPIKE: import one real Hatch manifest
  (verified format: `displayName`, `spriteVersionNumber`, `spritesheetPath`;
  spritesheet grid; `/hatch` command) and document which animation types
  survive 1:1 (single spritesheet loops) vs which do not (compound chains,
  spatial movement — §9/§10 behaviors are Hermes-mode only).
- Ship only the exportable subset; state it explicitly in the manifest.

---

## 37. CHARACTER PACKS (kept — §38 of original)
`character/manifest.json` (name, version, default_state, home_anchor,
personality) + sprites/ + animations.json + sounds/. Swappable characters
over the same behavioral engine.

---

## 38. LONG-TERM POSSIBILITY (kept)
Embodied agent observability: searching looks like searching, waiting like
waiting, thinking like thinking, failure like failure, recovery like recovery,
delegation like delegation, completion like completion. The companion is the
front-end visualization of the whole agent architecture — memory, cron,
subagents, approvals, retries, scheduled wakes.

---

## 39. DELIVERY & REPO

- Plugin repo: `hermz580/hermes-companion` (private-first, per the private-
  repo discipline). Installed via `~/.hermes/plugins/`.
- Docs reference the hook taxonomy at `hermes_cli/plugins.py` VALID_HOOKS and
  `docs/plugins/hook-taxonomy.md` as the contract to build against.
- QA pipeline: Nazurak red assurance of the walking skeleton → Vonta build →
  deploy to the private repo. Screenshots + forge test + storm test from §34
  are the acceptance artifacts.
