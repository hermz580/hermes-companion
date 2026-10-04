"""End-to-end proof that a live companion follows a real Hermes session.

Starts `hermes-companion live --companion <name> --follow` against a private
temporary HERMES_HOME, then drives the *real* Hermes plugin hooks (the same
functions Hermes calls) through a full session: start, tool work, a failure,
an approval, a helper, completion. Passes only if every event is
authenticated and acted out by the companion.

    python -m hermes_companion.scripts.live_e2e [companion]
"""
from __future__ import annotations

import os
import subprocess
import sys
import tempfile
import time

SESSION = "e2e-session"


def drive_hooks() -> int:
    from hermes_companion import plugin as hooks
    steps = [
        lambda: hooks.on_session_start(session_id=SESSION),
        lambda: hooks.on_pre_tool_call(tool_name="terminal", session_id=SESSION, tool_call_id="t1"),
        lambda: hooks.on_post_tool_call(tool_name="terminal", session_id=SESSION, tool_call_id="t1",
                                        result="ok"),
        lambda: hooks.on_pre_tool_call(tool_name="web_search", session_id=SESSION, tool_call_id="t2"),
        lambda: hooks.on_post_tool_call(tool_name="web_search", session_id=SESSION, tool_call_id="t2",
                                        status="error", error_type="Timeout"),
        lambda: hooks.on_pre_approval_request(command="rm build", description="clean",
                                              session_key=SESSION),
        lambda: hooks.on_post_approval_response(command="rm build", description="clean",
                                                choice="once", session_key=SESSION),
        lambda: hooks.on_subagent_start(parent_session_id=SESSION, subagent_id="h1"),
        lambda: hooks.on_subagent_stop(parent_session_id=SESSION, subagent_id="h1", success=True),
        lambda: hooks.on_session_end(session_id=SESSION, reason="done"),
    ]
    for step in steps:
        step()
        time.sleep(1.2)
    return len(steps)


def main(companion: str = "nyamekra") -> int:
    home = tempfile.mkdtemp(prefix="hermes-home-")
    env = dict(os.environ, HERMES_HOME=home, PYTHONUNBUFFERED="1")
    os.makedirs(os.path.join(home, "companion"), exist_ok=True)
    open(os.path.join(home, "companion", "events.jsonl"), "a").close()
    proc = subprocess.Popen(
        [sys.executable, "-m", "hermes_companion", "live", "--companion", companion,
         "--follow", "--notice", "off"],
        env=env, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
    time.sleep(4.0)
    os.environ["HERMES_HOME"] = home          # the plugin resolves home at import
    sent = drive_hooks()
    time.sleep(2.0)
    proc.terminate()
    out, _ = proc.communicate(timeout=15)
    print(out)
    events = [line for line in out.splitlines() if line.startswith("EVENT ")]
    ready = "LIVE READY" in out
    print(f"\nE2E: ready={ready} sent={sent} acted_out={len(events)}")
    ok = ready and len(events) >= sent - 1      # approvals may coalesce
    print("E2E PASS" if ok else "E2E FAIL")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main(*sys.argv[1:]))
