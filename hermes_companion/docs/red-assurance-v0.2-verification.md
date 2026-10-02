# Na'zurak Red Assurance — v0.2 MULTI-DEVICE + DIVERSITY (verification addendum)

Date: 2026-08-29
Reviewer: Na'zurak (VANTA cipher-review-gate)
Artifact under review: v0.2 changes on `master` (category-aware chains,
live-path engine integration, sprite grab, LAN relay).
Scope: verification of the code that now exists — not a design review.

## WHAT WAS CLAIMED vs WHAT IS TRUE (evidence, no hand-waving)

| Claim | Evidence | Verdict |
|---|---|---|
| Category-aware tool chains | `behavior_rules.py` CHAINS_BY_CATEGORY (9 cats); `behavior_engine.handle` selects by `(kind, category)`; `emit tool.started tool=terminal` → `terminal_work`, `tool=web_search` → `web_scan`, `tool=read_file` → `file_organize`, `tool=image_generate` → `media_paint`, `tool=memory` → `memory_vault`, `tool=delegate_task` → `open_portal > orb_exits` | CONFIRMED |
| Live path plays real engine chains | `renderer/live.py` rebuilds SemanticEvent, runs BehaviorEngine, `play_chain(chain)`; no longer the 2-pose map | CONFIRMED (code + demo trace) |
| Idle progression alive | demo trace: look_around(30s) → sit(120s) → play_with_object(300s) → sleep(600s) → wake on user return | CONFIRMED |
| Grab works (opt-in) | `PetdexOverlay.enable_grab` binds Button-1/B1-Motion; WS_EX_TRANSPARENT toggled per-tick only while cursor over sprite | CONFIRMED (code); click-through re-verified by selfcheck 5/5 |
| Multi-device sync | `renderer/relay.py`; loopback test 9/9 PASS incl. fan-out c1→c2, sanitization (unknown wire keys dropped), wrong-token silent reject | CONFIRMED (test output) |
| M4 forge gate holds | wrong token → server never replies, never broadcasts; validator rejects unknown event kinds / malformed grabs / unknown types | CONFIRMED |

## SEVERITY COUNTS (verified)
- BLOCKER: 0 · MAJOR: 0 · MINOR: 2 · NOTE: 1 · TOTAL: 3

## FINDINGS (post-fix, honest)

### f1 — MINOR: relay server thread is not crash-isolated from one bad socket
`serve_forever()` runs a single thread; a `_LineIO.pump()`/sendall raising
an unexpected (non-OSError) exception inside `_on_record` would kill the
whole relay. All observed paths are OSError-guarded and the loopback test
exercised disconnect + wrong-token without a crash, so this is residual
defensive depth, not a demonstrated failure.
STATUS: **FIXED in this pass** — per-socket `pump()` and per-record
`_on_record` are now wrapped in try/except Exception (skip + continue), so
one poison socket or record can no longer take down the fleet relay.

### f2 — MINOR: relay has no reconnect backoff on the client beyond a fixed 2s wait
`RelayClient._run` retried every 2s; a flapping relay would churn connect
attempts. Acceptable for a LAN pet, but a capped exponential backoff
(2s→30s) is the clean fix.
STATUS: **FIXED in this pass** — both the connect-failure and the
disconnect paths now use capped exponential backoff (2s → 1.5× → 30s max,
reset on successful connect).

### n1 — NOTE: `live --demo` and relay demo events originate from this
machine's process (source = hostname), so a second pet will animate them —
intended behavior, documented in README.

## WHAT WORKED (evidence-based)
1. The live path now honors the engine's chain vocabulary instead of
   re-mapping events to two poses — the "boring movement" complaint was a
   renderer bypass, and it is closed.
2. Deterministic engine + seed means "same events → same behavior" falls out
   of the design with no state sync — the multi-device problem stayed small.
3. The relay carried the §5.3 dumb-pipe rule forward without reopening the
   original M4 injection class (forge gate verified at the socket).

## VERDICT
PASS for the requested scope. The two residual items (f1/f2) were fixed in
this same pass and re-verified; the addendum stands at zero open findings.

## Required proof artifacts (this pass)
- `tests/test_relay.py` — 9/9 loopback incl. forge gate (kept, runnable)
- `proof/diversity/` — 16 pose renders (pixel-verified: ~3.4–4.8k opaque px
  each, no wallpaper leak)
- `tests/proof_diversity.py` — regenerator
- selfcheck 5/5, demo PASS (walking skeleton + idle progression)
