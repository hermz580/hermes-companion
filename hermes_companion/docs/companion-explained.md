# Hermes Companion, explained

Written for someone opening this repository for the first time — no prior
context required. It covers what the companion is, how the pieces fit, what each
recent update changed, and how to run and verify it yourself.

Repo: `hermz580/hermes-companion` (private). Branch under development:
`companion-truth-contract-and-brain`.

**Document status:** accurate as of `b6e9f53`. The counts under "the behavior
vocabulary" are measured from the code, not remembered — if you change the
behavior tables, re-measure them. They were last re-checked and corrected on
2026-09-12 (tool categories and movement vectors were both understated; the
failure chains no longer include a `repair` pose).

---

## 1. The one-paragraph version

Hermes Companion is a **desktop pet that shows you what your AI agent is
actually doing**. Hermes (the agent) runs tools, reads files, searches the web,
delegates to subagents, waits for approvals. All of that is normally invisible —
it happens inside a terminal or behind a chat window. The companion turns those
lifecycle events into a small animated character that walks, works, celebrates,
fails, recovers, sleeps, and reacts. It is a piece of **agent observability**:
a body for the agent, not a second brain.

It is deliberately **not** a chatbot, not a mascot that talks, and not an agent.
It renders evidence; it does not produce work.

---

## 2. Why it exists (the design intent)

The product bar the project holds itself to:

- It must show what Hermes is **actually** doing, sourced from real events.
- It must never pretend. A pet that animates "working" with no work behind it
  is worse than a pet that sits still.
- It must be alive through usefulness (state, memory, responsiveness, room and
  focus awareness), not through fabricated emotion or random chatter.
- It must be safe by default: no camera, no screen reading, no network, nothing
  recorded or sent anywhere unless explicitly switched on by the user.

Every update in this repo is, at bottom, one of: making the pet *see more real
things*, making it *more expressive* about things it really saw, or *closing a
hole where it could have lied or leaked*.

---

## 3. Architecture: how an agent action becomes a pet movement

Two separate processes, connected by one file of signed records.

```
HERMES CORE  (pre/post tool call, approvals, sessions, subagents)
      |
      |  real hook callbacks, in-process
      v
plugin/__init__.py   (the observer adapter)
      |   validate + allow-list  ->  CONTENT-FREE semantic event
      v
<hermes-home>/companion/events.jsonl        <- HMAC-signed JSONL, one per line
      |
      |  a DIFFERENT process reads this file
      v
renderer/live.py  ->  EventTail   (tail the file, verify MAC, claim session)
      v
BehaviorEngine    (deterministic, seeded: event + tool category -> a Chain)
      v
Choreography      (optional truthful spectacle layered on the evidence)
      v
PetdexOverlay     (transparent, click-through Windows Tk window, sprite atlas)
```

Six things worth knowing about this pipeline:

1. **The plugin only logs.** It never draws anything. If the overlay is not
   running, the plugin keeps logging events and nothing is lost.
2. **The plugin is fail-open.** If the companion breaks, Hermes keeps working.
   A broken pet must never break the agent.
3. **Events are content-free.** No prompts, no file contents, no command
   strings, no tool results. Only *kind* of event, tool name, tool category,
   and opaque session/task identifiers. (Spec §5.)
4. **Records are authenticated.** Each JSONL line carries an HMAC-SHA-256
   signature made with a profile-local key (`companion/event-auth.key`, created
   with a current-user-only ACL). Readers **fail closed**: unsigned, modified,
   or wrong-key records are silently ignored. This proves a record came from a
   process holding that key — it is not a sandbox against malicious code already
   running as the same OS user, and the docs say so rather than overclaiming.
5. **The engine is deterministic.** Same event stream in, same behavior out.
   That is why two machines can share one event stream and behave identically
   without syncing any state.
6. **The renderer fails closed on identity.** The visible pet refuses to display
   anything unless exactly one binding maps it to a specific session. It never
   guesses from "the newest event" or "the working directory".

### The behavior vocabulary (measured from the code)

| Thing | Count | Meaning |
|---|---|---|
| Event kinds with chains | 17 | typing, prompt, agent start/idle, tool start/progress/finish/fail, approvals, subagents, ... |
| Tool categories | 18 | terminal, file, web, browser, docs, sheets, communication, maps, desktop, development, media, design, audio, memory, planning, scheduling, delegation, learning (`general` is the unmatched-tool fallback, not a mapped category) |
| Category-specific chains | 45 | tool.started (17) + tool.finished (17) + tool.failed (11) — failure flavors are deliberately fewer |
| Sprite rows available | 9 | idle, running-right, running-left, waving, jumping, failed, waiting, running, review (6 columns each) |
| Pose → sprite-row mappings | 80 | how named poses land on existing art |
| Emotional arcs | 12 | task_birth, task_flow, task_done, task_failed, focused, joyful, frustrated, playful, curious, resting, restful, user_back |
| Idle progression rungs | 11 | tilt → look_around → peeking → stretch → head_drop → sit → check_watch → play_with_object → dance → yawn → sleep (with real dwell times) |
| Movement vectors | 21 | walk/dash/creep/sprint/leap/hop/orbit/fold/shimmer/fly_up/fly_down/... (16 distinct move types) |

Key consequence: **the art is fixed, the behavior is not.** The sprite sheet has
9 rows; everything expressive has to be composed from those rows plus motion,
timing and posture. Category flavor is expressed by choosing different rows
(terminal → waiting, web → review, dev → waiting, tool finished → jumping, tool
failed → failed), not by adding new art.

To add a new tool flavor you touch four files: a category in `core/events.py`, a
chain in `behavior/behavior_rules.py`, a pose in `animation/animator.py`, and a
row in `POSE_ROW` in `renderer/petdex_overlay.py`.

---

## 4. The trust rules (the through-line of every update)

These rules are why the updates look the way they do. They are tested, not
aspirational.

- **It never lies.** Work, success, reading, or completion are rendered only
  from a corresponding accepted event for the pet's exact bound session. This
  is enforced down to the failure chains: a failed tool no longer plays a
  `repair` pose, and an approval no longer plays `work`, because neither event
  is evidence that a repair or a work step actually started.
- **Silence proves nothing.** The pet shows the last real event and how old it
  is, and says plainly that quiet is not evidence that nothing is running.
- **Decorative ≠ evidence.** Flourishes are allowed and encouraged, but they are
  labelled as decoration in the code and in the UI; they can never be confused
  with a receipt of work.
- **Fail closed.** Unbound, ambiguous, unsigned, mismatched, malformed — all
  refuse rather than guess.
- **No focus theft.** The overlay is click-through (`WS_EX_TRANSPARENT` toggled
  per tick) and the dock uses `WS_EX_NOACTIVATE`, so the pet never steals your
  cursor or the foreground window.
- **Sensors are off.** Camera, screen/typing awareness: default OFF, individually
  toggleable, and permission for one is never permission for another.

---

## 5. What changed, update by update

### 5.1 Walking skeleton (Aug 29, `8022fed`) and real-event drive (`79b1a0b`)

The foundation: hooks → plugin → signed JSONL → renderer → behavior engine →
overlay. Plus the headless first-demonstration proof (typing→watch, prompt→jump,
agent→dash, tool→work, finish→celebrate→return, idle→sleep, user→wake+wave,
1040 px of travel, deterministic under a seed) and the 5-check self-check suite
(determinism, storm rule, priority interrupt, content-free boundary,
click-through).

**How to see it:** `python -m hermes_companion --seed 42 selfcheck` → 5/5.

### 5.2 Diverse category-aware movement + grab + LAN relay (Aug 30, `357b84d`)

The fix for "the pet is boring". Root cause mattered: the behavior engine
already had the rich chains, but the live path ignored them and used its own
6-case map, so the visible pet only ever did about six moves no matter what
Hermes did. Rebuilding the live path to *play the engine's chains* is what made
the pet diverse. (Lesson worth keeping: that was a renderer bug, not an engine
limitation.)

This update also added sprite grabbing (drag the pet) and opt-in multi-device
sync: one token-gated relay fans the same event stream to every pet, so both
pets respond identically without syncing state — plus grab records, so dragging
one pet moves the other.

### 5.3 Relay autostart + runbook (Aug 30, `6698723`), relay close fix (`6092111`), wallpaper-leak proof gate (`cdaee31`)

Operational hardening: relay auto-starts at boot hidden (Startup VBS), the token
lives in `%LOCALAPPDATA%\hermes\secrets\companion-relay-token.txt`, and the
multi-device runbook documents the two-machine acceptance test. The relay now
handles concurrent close cleanly (select on a closed fd). The proof generator was
tightened because a headless Tk capture of a withdrawn window photographs the
*wallpaper* instead of the pet — it now rejects renders by opaque-pixel count
(~3.5–5k pixels = a real pet; ~44k = wallpaper).

### 5.4 Truthful live state, durable identity/memory, gated brain bridge (Sep 11, `29278fd`)

The biggest update. Four things landed together:

**a) Truthful live state.** The pet now states what it is showing and refuses to
show anything it cannot attribute. New commands:

```
python -m hermes_companion bind                    # bind to the session running NOW
python -m hermes_companion bind --follow           # follow whichever session is active
python -m hermes_companion bind --pinned           # back to one exact session (default)
python -m hermes_companion bind --show             # list bindings + mode
```

Binding is **always an explicit user action**. The renderer re-reads
`bindings.json` and fails closed, so a stale or ambiguous file stops the pet
rather than letting it guess.

**b) Durable identity and memory, separate from the sprite.** Stored in a local
SQLite library (`%LOCALAPPDATA%\hermes\companion\library.sqlite3`). Important
distinction the code keeps explicit: the *sprite* (art, `display.pet.slug`) and
the *identity* (companion ID + memory) are different namespaces; an ID is an
explicit stable key, never inferred from a sprite name. Memory has scopes
(companion-private, shared, project), requires explicit approval, supports
inspect / correct / approve / revoke / hard-delete, is isolated per companion by
default, and every snapshot carries `authorizes_actions: False`. A correction
resets approval. Derived memory (`source='curated_note'`) raises unless a
consent ceremony is confirmed. It is local plaintext, not an encrypted vault,
and the UI says so. **It is not model training** and it does not grant authority.

**c) A visible library.** `launch\companion-library.cmd` opens a real Tk window:
create/archive/reopen profiles, inspect and correct memory, build a
point-in-time **context preview**. Profiles are saved records, not running
agents — nothing is launched, rebound, or given authority.

**d) A gated brain bridge.** `plugin_context` is a separate, thin Hermes plugin
that subscribes to exactly one hook, `pre_llm_call`, and can inject *validated*
companion memory into a real model call. It appends to the **user message**,
never the system prompt (the system prompt must stay byte-stable for prompt
caching). It is gated twice: a companion is used **only** when an explicit
user-authored binding maps the exact `(session_id, task_id)` tuple to a
companion ID, and a block is emitted only after the snapshot is re-validated for
that same tuple. It returns `None` on every other path, never raises, never
reads `user_message`, and every injection decision writes a content-free audit
line (counts and IDs only). The block is framed as **untrusted reference data,
not instructions**, and states it is memory, not authority.

**e) Multi-companion dock.** `python -m hermes_companion multi --bind
Scout=SESSION_A --bind Builder=SESSION_B --bind Guide` shows 1–4 companions side
by side, each tied to an exact session ID (no wildcards, no auto-selection). This
is how handoffs and concurrent subagents become visible. Statuses are honest by
construction: UNBOUND, DISCONNECTED (file unavailable — explicitly *not* agent
health), AWAITING SESSION EVENT, RECENT, STALE / ACTIVITY UNKNOWN after 30 s.
A QUIET control suppresses motion **without discarding evidence**. More pets do
not create agents, and camera/screen/context stay off. Motion is bounded inside
each card (25 px horizontally, 14 px vertically) so a busy fleet is readable
rather than chaotic.

### 5.5 Explicit bind command + one-click start launcher (Sep 11, `bc6382a`)

`launch\companion-start.cmd` is the daily double-click: it binds the Alpha to the
session Hermes is running right now, then starts the visible overlay with grab
and relay. Flags: `--no-bind` (keep the existing binding), `--no-relay` (no fleet
sync), `--scale N`.

Two details that are deliberate:

- The relay token is exported **through the environment**, never passed on the
  command line, so it cannot be read out of a process listing.
- The launcher is contract-tested against the real CLI parser
  (`build_parser()` is exported for exactly this), because a launcher passing an
  argument the parser dropped looks like "the pet won't start" instead of a flag
  mismatch.

### 5.6 Truthful choreography, social-signal plane, camera consent gate (Sep 12, `c71f1a1`)

**a) Truthful choreography** (`behavior/choreography.py`). Compiles spectacle
from evidence that has already been authenticated and routed — it does not
authenticate anything itself. It adds a deterministic `correlation_key` per
delivery so two pets can show the same event as *one* coordinated moment, and it
implements handoffs: the source pet opens a portal, emits an orb and flies up;
the target pet (a **distinct** peer, enforced) flies down, absorbs the orb and
reacts. The target reacts to an *observed* handoff and never claims child work it
did not do. Airborne movement during `tool.started`/`tool.progress` is decoration
on top of observed work, and the code comments say exactly that.

**b) Social-signal plane** (`core/social_signals.py`). A dedicated, authenticated
plane for *purely decorative* pet-to-pet gestures (wave, boop, play_bow,
happy_hop, sleepy_blink, mirror_pose) — explicitly not work evidence, not agent
messages, not intents, not memory. The schema has no free-text, no task or
session fields; unknown fields cause rejection. Each signal is HMAC-signed with
the source companion's key, checks source and exact target attribution, carries a
created/expires window (clock skew beyond 2 s rejected), and passes a gate that
blocks replay by signal ID and by monotonic sequence per source, plus a 2 s
pair cooldown. **A receipt never emits a reply** — that rule is what stops two
pets cheerfully talking to each other forever.

**c) Camera consent gate** (`core/camera_awareness.py` +
`core/permissioned_context.py`). No camera library is imported by the
controller. It refuses unless, in this order: consent was explicitly confirmed,
mode is `pinned` (never follow), the session ID exactly equals the pinned bound
session, the companion ID is valid, and the source is an opaque handle. It then
grants a 30-second scope, runs **one** probe, and revokes the grant in a
`finally`. Frames never enter the controller — it accepts only a strict coarse
result (`camera_read`, `person_detected`). The permissioned-context layer is
memory-only, performs no I/O on import, treats `confirmed` as a caller assertion
rather than proof of a consent ceremony, grants one exact source (never "all
documents" or "the foreground window"), stamps observations with acquisition
time, and flags stale observations. The CLI mirrors the refusal ladder:

```
python -m hermes_companion camera status     # readiness only; never opens a device
python -m hermes_companion camera check --consent --session-id <pinned-session>
```

### 5.7 Plugin bundle drift guard (Sep 12, `3a656ab`)

A regression test (`tests/test_plugin_bundle_shadowing.py`) for a nasty
real-world failure: two plugins shipping the same top-level package name collide
on `sys.path`, and whichever loads later owns that name process-wide. A *partial*
bundle (one plugin shipping only `core/`) shadowed the complete one, so the next
import raised `ModuleNotFoundError`, the fail-open handler ate it, and the pet
received nothing while looking perfectly healthy. The test asserts the engine
imports with either plugin directory first on `sys.path`.

### 5.8 Follow mode stops flapping (Sep 12, `6e55a3b`)

Replaying real signed records exposed it: with three subagent sessions live at
once, follow mode switched on every unfamiliar session ID — dozens of switches a
second, ending with no coherent animation. Fix: hold the displayed session while
it is still producing activity, and adopt another only once it has been quiet for
a dwell (2.5 s default, injectable clock). Records from a session that is not
being displayed are **rejected rather than rendered**, so the pet never animates
something it is not showing. Measured against 400 real records replayed at their
true arrival times: 35 events played, one follow start, 18 legitimate handovers
across 54 minutes of genuinely concurrent sessions.

---

## 6. How someone else runs it

Prerequisites: Windows, the Hermes Python environment, this repo checked out at
`%USERPROFILE%\hermes_companion`.

```bash
# 1. Put the package on the path
cd C:/Users/<you>            # the PARENT of hermes_companion
set PYTHONPATH=C:/Users/<you>

# 2. Assemble and enable the observer plugin (needed for real events)
cd hermes_companion && python plugin/install.py
hermes plugins enable hermes-companion

# 3. Health checks
python -m hermes_companion --seed 42 selfcheck     # 5/5
python -m hermes_companion --seed 42 demo          # walking-skeleton proof

# 4. Daily use: double-click launch\companion-start.cmd
#    (binds to the current session, then starts the pet with grab + relay)
```

Optional extras:

```
launch\companion-library.cmd      # identities + memory library
python -m hermes_companion multi --bind A=<session> --bind B=<session>
python -m hermes_companion live --grab --relay <host>:49000
```

Re-running `plugin/install.py` is required after pulling repo changes — the
plugin is *assembled* into the Hermes home, so editing repo code does not reach
the running plugin by itself.

**Verifying it is really up** (the event log alone cannot tell you): check the
process exists, check the relay connection is Established on the port, check
`events.jsonl` is growing rather than stale, and confirm the right sprite is
rendering (a healthy process with the wrong `display.pet.slug` shows the wrong
character convincingly).

---

## 7. Verified state

At commit `6e55a3b` (`companion-truth-contract-and-brain`, pushed to origin):

```
178 passed, 1 skipped, 80 subtests passed   (pytest tests/, ~17s)
```

That run was made in a clean `git worktree` of HEAD so it reflects the commit,
not an edited working tree. Test coverage includes: behavior integrity, binding,
camera awareness, choreography, execution/memory, library GUI, registry, routing,
event auth, follow mode, intents + bridge, launcher contract, live truth,
multi-pet + dock UI, permissioned context, plugin bundle shadowing, plugin
context, plugin loader, privacy/launcher checks, relay, social signals, and
truthful spectacle.

---

## 8. Known limits (stated, not hidden)

- **Sprite art is fixed.** No new art; everything composes from the existing 9
  rows plus motion, timing and posing.
- **`live --grab` is opt-in**, and pointer interaction is default-OFF per spec.
- **The memory library is local plaintext**, not an encrypted vault. Do not put
  passwords, tokens or raw recordings in it.
- **Event MACs are not a sandbox** against malware running as the same OS user.
- **The context bridge is deliberately not an execution bridge.** It grants no
  authority and starts nothing; a real end-to-end injection proof requires an
  explicitly bound session/task with approved memory plus a real (paid) model
  turn, which is outside the local test suite.
- **Relay is LAN-only by design** — there is no internet relay, because a pet
  should never phone home.
- **Verified on the primary Windows display**, not other operating systems and
  not tiny screens.
- **Multi-pet UI extras** (registry persistence UI, agent-ID binding/handoff UI,
  per-pet art selection, agent spawning) are not wired; binding there is
  CLI-explicit and session-only.
- **Follow mode is a UX trade-off**: it shows whichever session is speaking,
  which is the point, but a pinned binding is the way to watch one exact session.
  Delegated (subagent) work is excluded from claiming the display: a worker
  session runs under its own id, so without that rule three parallel workers
  would drag the pet back and forth while you sat in one chat. Workers can
  still animate a session that is already on screen.
- **Staleness caveat:** memory snapshots carry `store_id` and `revision` but no
  build timestamp, so a block cannot state its own age — staleness is only
  detectable through revision invalidation. Add a build time before claiming a
  freshness guarantee.

---

## 9. Glossary

| Term | Meaning |
|---|---|
| Semantic event | A content-free record of *what kind* of thing happened (e.g. `tool.started`, tool=terminal), never the content |
| Chain | A named sequence of poses the pet plays in response to an event |
| Category | The flavor of a tool (terminal, browser, docs, ...) used to pick a different chain and sprite row |
| Pose | A named body configuration; maps onto one of the 9 sprite rows |
| Binding | An explicit, user-authored mapping from a companion ID to an exact session (pinned), or a live "follow the active session" grant |
| Evidence | An authenticated event that a rendering decision is allowed to be based on |
| Fail closed | On any doubt, refuse (show nothing) rather than guess |
| Fail open | A broken companion never breaks Hermes |
| MAC / HMAC | Keyed signature on each record, so forged or edited records are rejected |
| Permissioned context | Memory-only boundary that grants one exact source, with TTL and revocation |
| Intent | A bounded, content-free request from the pet back toward Hermes, routed through policy and audit |
