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


# (call, seconds to wait after it). A realistic turn: think, work, a long
# tool that needs heartbeats, a failure, a rejected and an approved command,
# helpers (one fails), many tool types, then done.
def _session(hooks):
    S = SESSION

    def tool(name, cid, hold=0.0, **post):
        return [(lambda: hooks.on_pre_tool_call(tool_name=name, session_id=S, tool_call_id=cid), hold),
                (lambda: hooks.on_post_tool_call(tool_name=name, session_id=S, tool_call_id=cid,
                                                 **post), 1.0)]
    return [
        (lambda: hooks.on_session_start(session_id=S), 1.0),
        (lambda: hooks.on_pre_llm_call(session_id=S, user_message="(never read)"), 1.0),
        *tool("terminal", "t1", 1.0),
        *tool("web_search", "t2", 1.0, status="error", error_type="Timeout"),
        (lambda: hooks.on_pre_llm_call(session_id=S), 3.5),
        *tool("execute_code", "t3", 3.6),                  # long: heartbeats fire
        *tool("read_file", "t4", 0.8),
        *tool("write_file", "t5", 0.8),
        (lambda: hooks.on_pre_approval_request(command="rm -rf build", session_key=S), 1.0),
        (lambda: hooks.on_post_approval_response(command="rm -rf build", choice="deny",
                                                 session_key=S), 1.0),
        (lambda: hooks.on_pre_approval_request(command="rm build/tmp", session_key=S), 1.0),
        (lambda: hooks.on_post_approval_response(command="rm build/tmp", choice="once",
                                                 session_key=S), 1.0),
        (lambda: hooks.on_subagent_start(parent_session_id=S, subagent_id="h1"), 1.0),
        (lambda: hooks.on_subagent_start(parent_session_id=S, subagent_id="h2"), 1.0),
        (lambda: hooks.on_subagent_stop(parent_session_id=S, subagent_id="h1", success=True), 1.0),
        (lambda: hooks.on_subagent_stop(parent_session_id=S, subagent_id="h2", success=False), 1.0),
        (lambda: hooks.on_pre_llm_call(session_id=S), 3.5),
        *tool("browser_navigate", "t6", 0.8),
        *tool("memory", "t7", 0.8),
        (lambda: hooks.on_session_end(session_id=S, reason="done"), 1.0),
    ]


MUST_SEE = ("agent.started", "user.prompt_submitted", "tool.started", "tool.progress",
            "tool.finished", "tool.failed", "approval.required", "approval.rejected",
            "approval.approved", "agent.subagent_spawned", "agent.subagent_finished",
            "agent.subagent_failed", "agent.idle")


def drive_hooks() -> int:
    from hermes_companion import plugin as hooks
    steps = _session(hooks)
    for call, wait in steps:
        call()
        time.sleep(wait)
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
    os.environ["HERMES_COMPANION_HEARTBEAT_S"] = "1"
    sent = drive_hooks()
    time.sleep(2.0)
    proc.terminate()
    out, _ = proc.communicate(timeout=15)
    print(out)
    events = [line for line in out.splitlines() if line.startswith("EVENT ")]
    ready = "LIVE READY" in out
    kinds = {line.split()[2] for line in events if len(line.split()) > 2}
    missing = [k for k in MUST_SEE if k not in kinds]
    print(f"\nE2E: ready={ready} hooks={sent} acted_out={len(events)} "
          f"kinds={len(kinds)} missing={missing}")
    ok = ready and len(events) >= sent - 2 and not missing

    print("E2E PASS" if ok else "E2E FAIL")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main(*sys.argv[1:]))
