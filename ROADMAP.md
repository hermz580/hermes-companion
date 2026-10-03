# Roadmap

Where Hermes Companion goes next, ranked by how much it improves the
experience for the effort. Every item keeps the core rule: what Hermes is
really doing always reads correctly, and decoration never replaces it.

## Now: get it running everywhere
- [x] One-click `Start-Companion.cmd` that retries a failed install and forwards options
- [x] `hermes-companion doctor` to say exactly what a PC is missing
- [x] CI that installs from scratch and opens the real window on Windows
- [ ] A one-file `.exe` release (PyInstaller) so no Python install is needed
- [x] A demo GIF for the README (`docs/demo.gif`, rendered from real chains)

## Next: make it feel alive
1. ✅ **Live Hermes by default.** Make `live` work with Nyamekra without a Petdex
   pet configured, so real agent events drive the crow in one command.
2. ✅ **Personality memory.** Learn the user's rhythms (work hours, break
   patterns) from the same content-free counters, and let Nyamekra greet,
   rest and celebrate in step with them.
3. ✅ **Speech bubbles.** Short readable status lines ("Running a terminal
   command...", "Need your OK") from the existing content-free labels.
4. ✅ **Sound (opt-in).** Soft wing and chime cues per mood; off by default.
5. **Tray icon + settings panel.** Switch energy, size and character, and
   pause curiosity without a terminal.

## Later: grow the world
- **Multi-companion scenes.** Nyamekra, Nia and Herald on screen together,
  handing delegated work through portals (signed social signals already exist).
- ✅ **Custom art packs.** Load hand-painted frames that match the character
  sheets, with the procedural rig as the fallback.
- ✅ **macOS / Linux** (windowed mode; transparent overlay stays Windows-only) (sensors and transparency per platform).
- ✅ **Accessibility.** A reduced-motion mode and a high-contrast mood ring.

## Guardrails that stay
- Content-free sensing only: positions, counters, on/off. Never keys,
  titles, clipboard text or pixels.
- Hermes chains outrank curiosity, and decoration never changes a
  signature move. Both are enforced by tests.
