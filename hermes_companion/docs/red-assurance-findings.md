# Na'zurak Red Assurance — HERMES PET ENGINE v0.1 Build Spec
Review type: DESIGN-STAGE RED ASSURANCE (non-destructive)
Date: 2026-08-29
Reviewer: Na'zurak (VANTA cipher-review-gate)
Artifact under review: spec_frozen.md (SHA-256 88da0713115d01a2aa39dcdcfd2d368b9e50a990f3f6e0147d91c50706c8fc52)
Scope: review of the design document BEFORE it is handed to Hermes as a build specification. No build exists.

## IMPORTANT SCOPE STATEMENT (anti-false-positive discipline)
This is a design-stage audit. Severities are assigned against (a) the spec text,
(b) verified facts about the installed Hermes architecture, and (c) verified facts
about the Codex Hatch Pet format. Behavioral findings (DPI, resource cost, animation
quality) are PROJECTED from the spec, not observed from a running system — no build
exists. No screenshots are available or claimed. The first build milestone must produce
the screenshot set defined in "Required Proof on First Build" below.

## VERIFIED ARCHITECTURAL FACTS (grounding)
1. Installed Hermes source at C:/Users/HarpStar/AppData/Local/hermes/hermes-agent/ contains:
   - agent/agent_runtime_helpers.py: _dispatch_pre_tool_call_hooks, _emit_post_tool_call_hook
   - agent/codex_runtime.py: _fire_tool_started(item)  [tool_started event already in core]
   - agent/tool_executor.py: _emit_terminal_post_tool_call
   - cli-config.yaml.example: documented pre_tool_call, post_tool_call, pre_llm_call, post_llm_call hooks
   - AGENTS.md contribution rules: "extend, don't duplicate"; "plugins live in their own
     directory and work within the ABCs/hooks we provide"; no "speculative infrastructure";
     no plugins that "touch core files"; new model tools are the last resort.
2. Langfuse observability plugin (installed under plugins/observability/langfuse/) consumes
   pre/post tool-call hooks and emits per-tool observations.
3. NeMo Relay observability plugin (docs) consumes core-emitted lifecycle events for provider
   and tool execution, and adds session, turn, approval, and subagent mark events.
4. Gateway event hooks (HOOK.yaml) fire on lifecycle events (e.g. events: [agent:end]).
5. Codex Hatch Pet format is REAL (verified via web): hatch-pet skill; manifest with
   displayName, spriteVersionNumber, spritesheetPath; /hatch command; community custom-pet guides.

## SEVERITY COUNTS (VERIFIED)
- BLOCKER: 0
- MAJOR:   7  (M1-M7)
- MINOR:   4  (m1-m4)
- NOTE:    4  (n1-n4)
- TOTAL:  15

====================================================================
MAJOR FINDINGS
====================================================================

### M1 — Trust boundary undefined between Hermes core and companion runtime
EVIDENCE: Spec S2 (free-form "metadata": {}), S5 (operation names in metadata), S30/S40
(event API). Hermes core handles credentials, prompts, file contents, and reads untrusted
web/subagent output. The spec routes event metadata toward an always-on local renderer
without defining a process boundary, sanitization, or validation.
IMPACT: If the companion is a separate process, any unsanitized event field (file path,
window title, tool arg, subagent summary) that reaches animation/render/log code is both a
data-leak vector and a prompt-injection / UI-spoofing vector (content from a hostile page
visited by the browser tool could steer the pet's behavior and mislead the user).
FIX: Implement the companion as a Hermes plugin (per AGENTS.md: plugins live in their own
directory). Events pass a schema validator at the core boundary; metadata is restricted to
an allow-list of non-sensitive keys; the renderer treats ALL event content as untrusted;
no event field is ever rendered as text.
VERIFY: Threat-model review of every event field; grep renderer for string-render of event data.

### M2 — "Build an event bus" reimplements the existing hook/event surface
EVIDENCE: Spec Phase 1 (event bus), Phase 5 (Hermes event integration), S29 clause
"do not force this layout if Hermes already has equivalent modules." Verified: core already
emits tool_started (_fire_tool_started), dispatches pre/post_tool_call hooks, and the
Langfuse/NeMo Relay plugins already consume these; gateway HOOK.yaml fires on lifecycle events.
IMPACT: A parallel bus duplicates the observability pipeline, forks the event story, and would
be rejected upstream ("extend, don't duplicate"; "no speculative infrastructure"). The companion
and Langfuse/NeMo Relay would drift apart instead of sharing one event source.
FIX: Companion = plugin consuming the existing pre/post_tool_call + lifecycle hooks. Only
genuinely missing emitters get new instrumentation: user.typing_started / user.prompt_submitted
in the CLI input path. Before committing the event mapping, read the real hook payload schemas
in agent_runtime_helpers.py / model_tools.py (presence verified, signatures not fully audited).
VERIFY: grep hook payloads; confirm each MVP event maps to an existing emitter.

### M3 — Internal privacy contradiction: "no keylogger" vs default-on typing awareness
EVIDENCE: S3 forbids a hidden global keylogger; S27.1 "input monitoring should default to
Hermes-owned windows," S27.2 global keyboard needs opt-in. But S28 defaults "[X] Hermes
text-input awareness" ON, and S12's "stand beside the text field while the user types" +
S13's prompt_length/urgency/complexity derivation require reading raw input and caret/window
position. "Hermes-owned input surface" is never defined. On Windows the CLI runs in Windows
Terminal / mintty / VS Code, where the window also hosts other content.
IMPACT: The system ships (by default config) closer to a keylogger than the spec's own rules
allow, and the flagship demo sequence depends on telemetry the spec lists as opt-in.
FIX: Define the input surface precisely (Hermes TUI buffer only, not the terminal window).
Make ALL typing awareness default-OFF. Pin the prompt-derivation step inside core so only
derived scalars (prompt_length, typing_speed) cross the boundary. State explicitly that even
ephemeral typing events leak input length/cadence — acceptable with consent, must be disclosed.
VERIFY: settings-panel defaults diff; unit test that raw prompt text never leaves core.

### M4 — Event-bus integrity: no transport/auth, local injection + UI spoofing
EVIDENCE: S2/S30 specify an event bus with no transport or auth model. If the bus is a file or
socket, any local process can write to it.
IMPACT: Fake approval_required / error / task_complete events can manipulate the user into
approving an action or into panic; spoofed completion destroys the system's core value
(truthful observability). This is the most security-relevant design gap.
FIX: Prefer the in-process plugin path (no cross-process bus at all — eliminates the class).
If a separate process is required, bind IPC to the Hermes process identity with a per-run token
and validate source on every event.
VERIFY: attempt to inject a forged event from an unprivileged local process; assert reject.

### M5 — Compound-chain interruption semantics undefined
EVIDENCE: S8 defines chained animations; S19 priorities; S20 "some actions should finish before
interruption" (landing, teleport_reappear, stand_up). No behavior is defined for interrupting a
chain mid-way (abort? checkpoint? replay?).
IMPACT: Under bursty tool traffic the pet constantly restarts chains → flicker, completion
never shown — which breaks the observability purpose the spec itself states.
FIX: Define chain interruption as "finish current atomic step, then jump to interrupt target."
Add per-chain commit points, per-event-type cooldown, and a rule that P1/P2 storms cannot
starve recovery/completion visuals.
VERIFY: inject a burst of 50 alternating tool events; assert the pet reaches a terminal
state without unbounded restart.

### M6 — MVP dependency hole: "look_at_input" needs telemetry the MVP permission set forbids
EVIDENCE: S34 MVP includes look_at_input; the demo's first beat is "Hermes looks toward the
prompt box"; but S28 active-window/caret awareness is default-OFF and S12 gates it on
"permission-safe." In the default permission state the opening beat is impossible.
Also: no overlay pointer policy — an always-on overlay must be click-through except on the
sprite, or it blocks UI underneath (S9 safe/blocked zones do not cover mouse routing).
FIX: MVP input-reference = the Hermes window bounds (available from the plugin/hook context,
no extra sensor). Defer caret-level positioning to the opt-in window-awareness milestone.
Specify click-through transparency for the overlay in the renderer requirements.
VERIFY: with all sensors off, the pet still performs the demo's first beat; overlay does not
steal clicks anywhere except the sprite.

### M7 — Build order contradicts the spec's own vertical-slice advice
EVIDENCE: BUILD ORDER Phase 1 = event bus, Phase 2 = overlay, ... Phase 5 = integration, vs
the FIRST DEMONSTRATION acceptance criterion ("Build that before expanding further").
IMPACT: Months of invisible infrastructure before any proof; this is the classic
infrastructure-built-no-demo project death. The spec itself identifies the right path.
FIX: Reorder to a walking skeleton first: renderer + ONE wired event end-to-end
(type→submit→wake→dash→work→celebrate→return). Grow the bus/hooks behind it.

====================================================================
MINOR FINDINGS
====================================================================

### m1 — Windows DPI/multi-monitor math unspecified
EVIDENCE: S9 (x=200→x=1450), S32 (distance: 700) assume logical pixels / single monitor.
IMPACT: Per-monitor DPI virtualization and mixed-DPI setups will misplace the pet; taskbar
occlusion unhandled.
FIX: Physical-pixel mapping per monitor, clamp to work area, detect the monitor under the
active window, multi-monitor DPI test matrix. Movement controller core should be DPI-aware
from the start even though multi-monitor ships in Milestone 3.

### m2 — No resource/energy budget
EVIDENCE: S14/S18 cover behavior cost (annoyance) but not power: always-on transparent overlay
+ 24fps + movement has real CPU/GPU cost on Windows (DWM composition).
FIX: fps cap + frame-skip when idle/sleeping; overlay pauses when no Hermes activity; resource
telemetry (CPU/GPU%) as an acceptance gate.

### m3 — Non-determinism vs observability + QA
EVIDENCE: S15 personality + S16 weighted random selection make event→behavior mapping
non-deterministic, conflicting with the stated purpose (user learns a stable "movement
language") and making the mapping untestable.
FIX: Seed + determinism flag; synthetic event-injection CLI (companion emit tool.started
tool=github — the S30 API already hints at this); variance OFF during QA.

### m4 — Event schema lacks session scoping; multi-session conflation
EVIDENCE: S2 event carries task_id but no source session/profile. Cron jobs, gateway sessions,
and CLI sessions run under one Hermes home.
IMPACT: Two concurrent sessions interleave events → incoherent pet behavior.
FIX: Add session_id/profile to the event envelope; scope the companion to the active session.

====================================================================
NOTES
====================================================================

### n1 — Hatch export claim underspecified (format verified real)
Verified the Codex Hatch Pet format exists (hatch-pet skill; manifest fields displayName,
spriteVersionNumber, spritesheetPath; /hatch command). But S39 asserts "convert compatible
animations" without defining the format's constraints (spritesheet grid, fps cap, static vs
compound). Compound/behavioral sequences (S8-S10) almost certainly do not translate 1:1.
FIX: Defer to Milestone 4; add a spike importing one real hatch manifest; state explicitly
which behaviors are Hatch-exportable.

### n2 — No bus-level aggregation for high-frequency sources
S3 typing / progress events have no debounce at the source; S18 motion budget throttles
animation, not ingestion. Fix: coalesce in the sensor layer.

### n3 — No reduced-motion / accessibility consideration
No mention of honoring the OS reduce-animation setting or avoiding motion near the active
window. Fix: one line in the settings panel; tie extravagance 0 to OS reduced-motion.

### n4 — Memory events must never render content
S5 memory-vault animations imply it but never state it. Fix: explicit rule — memory.* events
carry only op + entity-class, never content (ties into M1 sanitization).

====================================================================
WHAT WORKED (evidence-based, not generic praise)
====================================================================
1. The event→state→behavior→animation layering (S1/S31) is architecturally correct and
   matches how the existing observability hooks are structured. Keep it.
2. S29's "do not force this layout if Hermes already has equivalent modules" is the right
   rule — it just needs to be applied (see M2).
3. The MVP event list (S34) maps cleanly onto the verified hook surface: tool.started/finished/
   failed, approval_required, task_complete all have real emitters today. Only typing/prompt
   events need new instrumentation.
4. The privacy intent (S27: ephemeral events, no raw content, toggleable sensors) is the right
   stance; it must be enforced by architecture, not asserted.

====================================================================
REQUIRED PROOF ON FIRST BUILD (screenshot set — none available at design stage)
====================================================================
The walking-skeleton milestone must produce and retain:
1. Overlay rendered + click-through verified (UI under the pet is clickable except on sprite)
2. Typing awareness OFF-by-default state, and ON state showing only derived scalars
3. tool.started → dash → work sequence (one screenshot per chain step)
4. tool.failed → recovery chain, and the P0 approval interrupt of a sleep animation
5. task_complete celebration + return_home
6. Sleep/wake on idle/user-return
7. A forged-event injection test result (assert rejected — M4)
8. DPI sanity check on at least one non-100% scale monitor (m1)

====================================================================
VERDICT
====================================================================
Verdict: FAIL as build-ready. (VANTA: unresolved MAJORs for the requested action = no
authorization.) The concept and most of the behavior design are sound; the security model
(M1/M3/M4) and the architecture plan (M2/M7) are not ready to hand to Hermes for build.
Action token: DO_NOT_PROCEED on the build.
Required before handing to Hermes: revise spec to resolve M1, M2, M3, M4, M6, M7
(M5 + all minors can land in the same revision, they are cheap text changes).
After revision, re-review is required (approval never transfers to the revised artifact).
