# Companion Context Plugin (`hermes-companion-context`)

A **standalone Hermes hook plugin** that injects *validated* companion memory
into real LLM calls. It subscribes to exactly one real hook — `pre_llm_call` —
and returns a bounded, framed companion-memory block that Hermes appends to the
**user message** (never the system prompt, which must stay byte-stable for
prompt caching).

It is intentionally thin. All of the real work — resolving an explicit,
user-authored `(session_id, task_id)` binding, building a memory snapshot,
re-validating that exact snapshot, framing it as untrusted reference data, and
writing a content-free audit line — lives in the fail-closed adapter
`hermes_companion.core.companion_execution`. This plugin only bridges that
adapter to the hook and swallows every failure.

## Files

| Path | Role |
|---|---|
| `plugin_context/plugin.yaml` | Manifest: `name` + `hooks: [pre_llm_call]` |
| `plugin_context/__init__.py` | `register(ctx)` + the `pre_llm_call` callback |
| `plugin_context/install.py` | Builds the self-contained installed plugin |
| `tests/test_plugin_context.py` | Stdlib `unittest` contract tests |
| `docs/companion-context-plugin.md` | This document |

## How the hook works (verified against the Hermes source)

- `pre_llm_call` is a real hook in `VALID_HOOKS` (`hermes_cli/plugins.py`).
- Callbacks receive kwargs: `session_id`, `task_id`, `turn_id`, `user_message`,
  `conversation_history`, `is_first_turn`, `model`, `platform`,
  `parent_session_id`, `sender_id`.
- A callback may return `{'context': '<str>'}` (or a plain non-empty string).
  The host joins all such returns with a blank line and appends them to the
  **user message** — see `agent/turn_context.py::_collect_pre_llm_call_context`.
  Oversized output is spilled to disk by the host.
- Registration is `ctx.register_hook('pre_llm_call', fn)`.

## Callback contract

`provide_companion_context(*, session_id="", task_id="", **_)`

1. Imports the bundled `hermes_companion.core.companion_execution` package and
   opens the local companion memory store.
2. Calls the adapter with the **real** `session_id` and `task_id`:
   `build_context_block(session_id, task_id, store=store)`.
3. Returns `{'context': block}` **only** when the block is a non-empty string.
4. Returns `None` on **every** other path: adapter import failure, store-open
   failure, adapter exception, empty/whitespace/non-string block.
5. **Never raises** — the whole body is wrapped so a broken adapter can never
   break a user's LLM call.
6. **Never reads `user_message`** (or any other hook kwarg beyond
   `session_id`/`task_id`) into a log or an audit.

## Configuration (read-only here)

- **Package location** — `plugin_context/install.py` copies the required
  `hermes_companion/core` package beside the installed adapter and injects a
  plugin-relative bootstrap after the future import. There is no repository or
  user-home path baked into the installed plugin.
- **Companion home** — `HERMES_COMPANION_HOME` if set, else the active,
  profile-aware Hermes home plus `companion/` (resolved by
  `hermes_constants.get_hermes_home()`, with an environment/platform fallback).
  The plugin reads `library.sqlite3` there; the adapter reads `bindings.json` /
  writes `injection_audit.jsonl` in the same directory. A companion is injected
  **only** when a binding maps the exact `(session_id, task_id)` tuple to a
  `companion_id`.

## Install and enable

Do these by hand when you actually want the hook live:

1. **Assemble the plugin** under the active Hermes home:

   ```bash
   python plugin_context/install.py --hermes-home <hermes-home>
   ```

   The installer creates `plugins/hermes-companion-context`, copies the
   manifest and adapter, and bundles its required core modules. Re-running it
   refreshes the bundled package without relying on the source checkout.

2. **Enable it** (this is opt-in; it writes `plugins.enabled` and the entry
   config):

   ```bash
   hermes plugins enable hermes-companion-context
   ```

3. **Verify it is enabled:**

   ```bash
   hermes plugins list --plain
   ```

   If it does not appear enabled immediately after enabling, the loader pruned
   it on a load error — re-run with `HERMES_PLUGINS_DEBUG=1` to see the real
   cause.

No model call is needed to validate packaging. `tests/test_plugin_loader.py`
builds both plugins into a temporary `HERMES_HOME`, loads them through
`hermes_cli.plugins.PluginManager.discover_and_load`, validates manifest hook
declarations against `VALID_HOOKS`, fires the installed observer callback, and
forces the context plugin's bundled lazy import. A real context-injection proof
still requires an explicitly bound session/task with memory plus a real agent
turn; that paid/model-call step is intentionally outside the local test suite.

## Testing

```bash
PYTHONPATH=<repo-parent>;<hermes-source> python -m pytest \
  tests/test_plugin_context.py tests/test_plugin_loader.py -o 'addopts=' -q
```

The suite covers: registration registers exactly `pre_llm_call`; the callback
returns `None` for an empty block; returns `{'context': ...}` (and only that
key) for a non-empty block; returns `None` and does not raise when the adapter
import fails or the adapter raises; `session_id`/`task_id` are passed through
verbatim; the manifest declares only the real `pre_llm_call` hook; and both
installed manifests/modules pass the real local Hermes loader.
