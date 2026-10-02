# Multi-companion event dock

Opt-in Windows Tk mode, separate from `live`. Does NOT create agents or enable
camera/screen/context capture. No plugin installation, gateway restart, relay,
or production event injection. Existing active pet art is reused, not new art.

From `C:/Users/HarpStar`:

```bash
python -m hermes_companion multi --bind Scout=EXACT_SESSION_ID --bind Builder=OTHER_SESSION_ID --bind Guide
```

Replace IDs with exact sessions reaching the selected profile's events.jsonl.
Labels and bound IDs must be distinct. `Label` alone is unbound. No wildcard or
automatic session selection. Supports 1-4 companions. Close via X or --duration.
--events PATH changes the read-only source; existing history is not replayed.

Bounded isolated simulation (no live stream reads or writes):

```bash
python -m hermes_companion multi --bind Scout=simulation-a --bind Builder=simulation-b --bind Guide --simulation --duration 5
```

Truthful status: UNBOUND; DISCONNECTED (file unavailable, not agent health);
AWAITING SESSION EVENT; RECENT (last observed event); STALE / ACTIVITY UNKNOWN
(after 30 seconds). Click a card for its binding, event, age, category and combo.
More pets do not create agents. Camera/screen/context remain OFF.

The QUIET control suppresses and clears motion without discarding accepted event
evidence. Bound cards are marked QUIET while it is enabled; unbound cards remain
visibly UNBOUND. Missing, mismatched, and unbound session records never animate.

Per-session engines select existing category-aware chains. Motion is bounded
inside cards (25 px horizontally, 14 vertically). No fake work on idle/unbound
pets. WS_EX_NOACTIVATE prevents foreground theft on Windows. The dock is
clickable, not a desktop-wide click-through overlay.

Verification:

```bash
python -m unittest hermes_companion.tests.test_multi_pet -v
python -m unittest hermes_companion.tests.test_multi_pet_ui -v
MULTI_PET_UI_TEST=1 python -m unittest hermes_companion.tests.test_multi_pet_ui -v
PYTHONPATH=C:/Users/HarpStar python -m pytest hermes_companion/tests -q -o addopts=''
```

The routine UI test keeps its Tk root withdrawn, transparent, and off-screen.
Only the explicit `MULTI_PET_UI_TEST=1` proof opens a labeled short simulation,
checks motion, bounds, programmatic card clicks, status isolation and foreground
preservation, captures the actual mapped window to
`proof/multi-pet/simulation-dock.png`, and closes only itself.

Integration: uses core CompanionRegistry and CompanionEventRouter directly;
there is no duplicate routing policy. All context_permissions are empty. Wrong
agent IDs, malformed timestamps and unbound handoff targets are rejected by the
shared router. Observed content is discarded, never treated as instructions.
Click selection changes inspection attention only, never task authority.

Limits: registry persistence, agent-ID binding/handoff UI, permission controls,
optional context display, per-pet art selection and agent spawning are not wired
here. Binding is CLI-explicit and session-only. Source availability is not
session liveness. PermissionedContext was inspected, but not instantiated or
granted permissions: no sensing or content access is enabled. Verified on this
Windows primary display, not other OSes or tiny screens. Existing live pet and
gateway are left unchanged.
