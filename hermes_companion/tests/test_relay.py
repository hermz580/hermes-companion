"""Relay loopback test (headless, no Tk) — M4 forge-gate proof.

Asserts:
1. Two clients authenticate with the right token and one client's event
   reaches the other (fan-out works).
2. A client presenting the WRONG token is rejected at the socket (no echo,
   no broadcast) — the forged-event injection class stays closed.
3. Events are sanitized on the wire (unknown keys dropped, types bounded).
"""
from __future__ import annotations

import json
import socket
import threading
import time

from hermes_companion.renderer.relay import RelayServer, RelayClient, _valid_record


def _sock_auth(port: int, token: str, timeout: float = 2.0) -> tuple[bytes | None, bool]:
    """Open a raw socket, send auth. Returns (reply, timed_out). A correct
    token gets a hello; a wrong token gets NOTHING (the server's fail-closed
    reject — silence is the proof), so reply is None + timed_out=True."""
    s = socket.create_connection(("127.0.0.1", port), timeout=timeout)
    s.sendall(json.dumps({"type": "auth", "token": token}).encode() + b"\n")
    s.settimeout(timeout)
    try:
        return s.recv(4096), False
    except socket.timeout:
        return None, True
    finally:
        s.close()


def main() -> int:
    results: list[tuple[str, bool]] = []

    # 1 + 2: server on a random port, two real clients, wrong-token raw socket.
    server = RelayServer(host="127.0.0.1", port=0, token="secret123")
    server.start()
    bound_port = server._sock.getsockname()[1]
    t = threading.Thread(target=server.serve_forever, daemon=True)
    t.start()

    c1 = RelayClient("127.0.0.1", bound_port, token="secret123")
    c2 = RelayClient("127.0.0.1", bound_port, token="secret123")
    c1.start()
    c2.start()
    time.sleep(0.6)

    results.append(("clients authenticate with correct token",
                    c1.connected and c2.connected))

    c1.send({"type": "event", "event": "tool.started", "tool": "terminal",
             "category": "terminal", "session_id": "sess-1", "source": "A",
             "evil_key": "drop-me"})
    deadline = time.time() + 3.0
    got = None
    while time.time() < deadline and got is None:
        for rec in c2.drain():
            if rec.get("type") == "event":
                got = rec
        time.sleep(0.1)
    results.append(("event fans out c1 -> c2",
                    got is not None and got.get("event") == "tool.started"))
    results.append(("unknown keys dropped at the wire (sanitization)",
                    got is not None and "evil_key" not in got))

    # 3: correct token gets a hello; wrong token gets silent reject (timeout).
    ok_hello, _ = _sock_auth(bound_port, "secret123", timeout=2.0)
    _bad, bad_timed_out = _sock_auth(bound_port, "WRONG", timeout=1.0)
    results.append(("correct token greeted (hello received)",
                    ok_hello is not None and b"hello" in ok_hello))
    results.append(("wrong token rejected at the socket (M4 forge gate)",
                    bad_timed_out is True))

    # Sanitizer unit checks.
    results.append(("validator accepts bounded event",
                    _valid_record({"type": "event", "event": "tool.started"}) is not None))
    results.append(("validator rejects unknown event kind",
                    _valid_record({"type": "event", "event": "evil.injected"}) is None))
    results.append(("validator rejects non-numeric grab",
                    _valid_record({"type": "grab", "x": "boom", "y": 4}) is None))
    results.append(("validator rejects unknown type",
                    _valid_record({"type": "approval.approved"}) is None))

    c1.close()
    c2.close()
    server.close()

    ok = all(ok for _, ok in results)
    for name, passed in results:
        print(f"  [{'PASS' if passed else 'FAIL'}] {name}")
    print(f"\nrelay loopback {'PASSED' if ok else 'FAILED'}")
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
