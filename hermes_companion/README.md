# Hermes Companion — Event-Reactive Desktop Character

A visible embodiment of Hermes: the character communicates what Hermes is
doing through movement, posture, location, expression, and interaction with
the desktop. It is a form of **agent observability** — it makes normally
invisible agent behavior visible.

This is the Phase 1 walking skeleton from the frozen build spec
(`spec_rev1_build_ready.md`, SHA-256 `b4aafd1168bc47438c5a410f4f5009100fba3abf675eed55bed41fd3480b2eb6`).

## Architecture

```
HERMES CORE (existing hooks: pre/post_tool_call, approval, session, subagent)
        ↓  plugin boundary (VALID_HOOKS dispatch, in-process)
HERMES_COMPANION PLUGIN
    adapter (validate + allow-list → semantic events)   ← real-hook integration
        ↓
    CONTEXT INTERPRETER
        ↓
    BEHAVIOR ENGINE  (deterministic, priority-aware, cooldown/storm rule)
        ↓
    EMOTION / INTENT STATE
        ↓
    MOVEMENT PLANNER  (easing, DPI-aware)
        ↓
    ANIMATION RENDERER  (procedural poses + transparent click-through overlay)
```

## Layout

- `core/` — semantic events (typed, content-free), behavior states
- `behavior/` — behavior engine, event→chain rules, priorities, idle progression
- `movement/` — easing curves
- `animation/` — procedural sprite animator + chain director (atomic-step interruption)
- `renderer/` — transparent click-through overlay (Windows), headless surface for QA
- `cli/` — `emit` / `demo` / `selfcheck` / `scene` commands
- `plugin/` — the real Hermes observer hook plugin (manifest + adapter + installer)
- `plugin_context/` — separately installable, self-contained `pre_llm_call` plugin

## Run

From the repo root with the package on the path:

```
hermes-companion --seed 42 demo
hermes-companion --seed 42 selfcheck
hermes-companion emit tool.started tool=github
hermes-companion --seed 7 scene --shots proof/
```

### Run your existing Hermes pet from real events

`live` resolves `display.pet.slug` from the active Hermes config and renders
that exact installed Petdex/Codex spritesheet — no replacement character.
**v0.2** rebuilt the live path to play the real behavior-engine chains
(category-flavored: terminal ≠ web ≠ file ≠ dev ≠ media ≠ memory) plus idle
progression, and added opt-in multi-device sync and sprite grabbing.

```
hermes-companion live
```

Current verified pet: `The Alpha And` (`the-alpha-and`), a 1536×1872
8-column × 9-row Codex atlas. Real semantic events map to its existing rows:

- tool started → directional run → category work pose (terminal/web/file/dev/media/memory)
- tool finished → close workstation → celebrate / double-jump / spin → run home
- tool failed → failed → review → repair → idle
- approval required → wake → panic → run to user → wave → wait
- subagent start/finish → portal → orb exit/return → absorb
- idle progression → look_around → sit → play_with_object → sleep

### v0.2 — multi-device sync (relay) + grab (both opt-in)

Each pet is otherwise a fully-local singleton fed only by its own machine's
Hermes. To make two pets respond the same, one authoritative event stream
must fan out to every renderer:

```bash
# machine A — one relay for the fleet (token-gated, prints its token once)
hermes-companion relay --token <SAME> --port 49000

# machine A and B — each pet joins the relay and animates the SAME events
hermes-companion live \
    --grab --relay 192.168.0.174:49000 --token <SAME>
```

- Both pets animate from the same semantic event stream (engine is
  deterministic + seed-fixed, so identical input → identical behavior).
- Dragging a pet (`--grab`) publishes its position to the relay; the other
  pet moves with it.
- The relay is a dumb, token-gated pipe (spec §5.3 carried forward): wrong
  token = silent reject, events are allow-list sanitized at the wire, and a
  renderer can never influence behavior upstream. Off by default — a pet
  never phones home unless told to.
- `HERMES_COMPANION_TOKEN` env var works as the shared key.

`python -m hermes_companion live --demo` plays a local visual sequence without
waiting for events. Tool-specific artwork (terminal, web orb, file stack,
git branch, palette, memory vault) is drawn procedurally by the animator;
the event/behavior engine does not change.

## Plugin install

```
python plugin/install.py          # assembles + enables the hook plugin
hermes plugins enable hermes-companion
python plugin_context/install.py  # assembles the optional context plugin
hermes plugins enable hermes-companion-context
```

The plugin consumes real Hermes lifecycle hooks (`pre_tool_call`,
`post_tool_call`, approval, session, subagent) and logs semantic events to
`<hermes-home>/companion/events.jsonl`. Raw payloads (args, results, command
strings) never cross the adapter boundary (spec §5).

Every local JSONL record is authenticated with HMAC-SHA-256. The observer
creates `<hermes-home>/companion/event-auth.key` with a current-user-only ACL
(mode `0600` on POSIX); single- and multi-pet renderers verify the MAC before
session routing and silently reject unsigned, modified, or wrong-key records.
This proves records came from a process holding that profile-local key; it is
not a sandbox against malicious code already running as the same OS account.

## Proof

- Headless first-demonstration: typing→watch → prompt→jump → agent→dash →
  tool→dash+work → finish→celebrate→return → idle→sleep → user→wake+wave,
  1040px travel, deterministic under seed.
- Self-check suite (5/5): determinism, storm rule (50 events→1 chain),
  priority interrupt, content-free boundary, overlay click-through.
- Real-session events logged via the plugin (agent.started → tool.started →
  tool.finished → agent.idle with correct chains).
- Proof screenshots: `proof/` (gitignored, regenerated via `scene --shots`).

## Security / privacy (spec §27-28)

- Content-free events only; no raw text rendered.
- Local event records are MAC-authenticated; renderers fail closed on unsigned
  or forged JSONL records.
- Desktop curiosity (`live --notice`) reads only content-free signals:
  positions, counters and on/off states, never keys, titles or clipboard text.
  `--notice off` disables it; `ambient` excludes typing, clicks and clipboard.
- All sensors individually toggleable.
- Fail-open plugin: a broken companion never breaks Hermes.
