# Companion Library

Double-click `launch\companion-library.cmd` to open the local Tk library. It uses the existing Hermes Python installation and Python's Tk/SQLite standard library; no new dependencies or network service.

Alternatively, from `C:\Users\HarpStar`:

```console
python -m hermes_companion.renderer.companion_library
```

The default persistent database is `%LOCALAPPDATA%\hermes\companion\library.sqlite3`. Override it explicitly with `--db "C:\path\library.sqlite3"`. Closing the window does not erase it. The database is **local plaintext, not an encrypted vault**; do not put passwords, tokens, raw recordings, or sensitive captures in it.

## Identity

- Enter a name and optional role, then **Create profile**. A new unique stable ID is persisted; names do not imply identity or memory inheritance.
- Select a row and **Reopen selected** (or double-click). The same saved ID and its memory are loaded, including after restarting the app.
- **Archive open profile** hides it from the default list, retaining its identity and memories. Use **Include archived profiles**, **Refresh**, **Reopen selected**, then **Restore open profile** to restore it.
- These are saved profiles, **not running agents**. No agent is launched, stopped, rebound, or given execution authority. The existing live pet remains separate and untouched.

## Inspectable, deliberate memory

Select a memory row to inspect full text, source, scope, approval state, version, and last-updated time. The text box can contain a new preference or a corrected version of the selected memory.

Saving requires checking **I approve saving this text...** for the current operation, then **Add approved memory** or **Correct selected + approve**. The approval box resets after saving, inspection, refresh, or changing profiles. The UI only adds explicitly user-approved, companion-private records. No other companion inherits them. Shared/project grants are intentionally not exposed here.

A correction first makes the record tentative in the core, then explicitly approves it following the user's checkbox consent. If either step fails, the status reports the error; rebuild/refresh to inspect current state. **Forget selected permanently** hard-deletes that record from the local store without a content tombstone. This cannot recall previously exported snapshots, backups, or other copies.

## Context preview, not execution

The second tab accepts an explicit task ID and session ID. **Build preview** calls the real local store's `build_execution_context` and shows its JSON snapshot. No session lookup, connection, automatic dispatch, or execution occurs. Project sharing is not requested. Local memory changes, profile changes, and edits to the task/session identifiers clear the displayed preview. Other processes may change the store: previews are point-in-time, so rebuild them before inspection.

The library never reads camera/screen/microphone data, calls an external API, or imports permissioned observations. It does not implement automatic Hermes execution integration.

## Tests

From the repository parent:

```console
python -m unittest hermes_companion.tests.test_companion_library -v
```

The GUI tests use real mapped Tk widgets and real SQLite databases inside temporary test directories. They invoke the actual button commands and assert persisted results, consent gates, identity restoration, memory isolation, corrections/deletion, and explicit preview binding. They do not substitute a mock store.
