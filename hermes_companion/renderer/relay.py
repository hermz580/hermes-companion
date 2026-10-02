"""Companion relay — optional LAN fan-out of semantic events + grab control.

Why (multi-device): each pet is a fully-local singleton fed only by its own
machine's Hermes. To make two pets respond the same, one authoritative event
stream must fan out to every renderer. This module is that pipe.

Security contract (spec rev1 §5.3 carried forward from the M4 fix):
- The relay is a DUMB PIPE: it validates that every message is a semantic
  event or a grab-control record, never inspects content, never renders text.
- Clients authenticate with a per-run token on connect. A forged event from
  an unauthenticated local process is rejected at the socket.
- Renderers only ever SUBSCRIBE; they can never influence behavior upstream
  except through the grab-control channel (explicit user action).
- DEFAULT OFF: no socket is ever opened unless the user passes --relay /
  runs `relay`. A pet never phones home unless told to.

Protocol (TCP, JSON lines):
  C->S:  {"type":"auth","token":"..."}
  S->C:  {"type":"hello","host":"<relay host>","port":<port>}
  S->C:  {"type":"event","event":"tool.started","tool":"terminal",
          "category":"terminal","session_id":"...","source":"<host>"}
  S->C:  {"type":"grab","x":<px>,"y":<px>,"source":"<host>"}
  any:   {"type":"ping"} -> {"type":"pong"}
The relay re-broadcasts event/grab records to every client EXCEPT the sender
(no echo, no loop). Events carry only bounded enums + scalars — never raw
tool args, results, commands, or prompt text.

I/O model: sockets are NON-BLOCKING with select()-driven read+write
multiplexing, so a client's outbound queue is always flushed and inbound
lines are always drained — a peer blocked on recv never starves its own
writes (the classic makefile-readline deadlock is avoided entirely).
"""
from __future__ import annotations

import json
import logging
import os
import queue
import secrets
import select
import socket
import threading
import time
from typing import Callable

log = logging.getLogger("hermes_companion.relay")

DEFAULT_PORT = 49000

# Message types the relay will accept from a client and re-broadcast.
_FORWARDABLE = {"event", "grab"}

# select() poll cadence in seconds — keeps idle peers cheap.
_POLL = 0.1


def _valid_record(rec: dict) -> dict | None:
    """Allow-list validation at the wire edge (spec §5.1). Only enum/scalar
    fields survive; anything unknown is dropped. Returns the SANITIZED record
    (or None to reject). Never content."""
    if not isinstance(rec, dict):
        return None
    if rec.get("type") not in _FORWARDABLE:
        return None
    if rec["type"] == "event":
        from hermes_companion.core.events import EventKind
        kind = rec.get("event")
        if kind not in EventKind._value2member_map_:
            return None
        # Rebuild as a bounded record; drop unknown keys.
        return {
            "type": "event",
            "event": kind,
            "tool": str(rec.get("tool") or "")[:64],
            "category": str(rec.get("category") or "")[:64],
            "session_id": str(rec.get("session_id") or "")[:128],
            "source": str(rec.get("source") or "")[:64],
        }
    # grab
    try:
        x = int(rec["x"])
        y = int(rec["y"])
    except (KeyError, TypeError, ValueError):
        return None
    return {"type": "grab", "x": x, "y": y,
            "source": str(rec.get("source") or "")[:64]}


class _LineIO:
    """Non-blocking JSON-lines reader/writer over one socket.

    Holds a recv buffer and a send buffer; pump() must be called from the
    owning thread on every select tick. read() yields parsed records (list,
    possibly empty); a dead peer surfaces as read() returning records plus
    closed=True.
    """

    def __init__(self, sock: socket.socket) -> None:
        self.sock = sock
        self._rbuf = b""
        self._sbuf = b""
        self.closed = False

    def pump(self) -> list[dict]:
        """Drain readable bytes into records; flush the write buffer.
        Returns records parsed since the last pump (caller validates)."""
        records: list[dict] = []
        try:
            # Drain as much as the socket has right now.
            while True:
                try:
                    chunk = self.sock.recv(65536)
                except BlockingIOError:
                    break
                except OSError:
                    self.closed = True
                    break
                if not chunk:
                    self.closed = True
                    break
                self._rbuf += chunk
        except OSError:
            self.closed = True
        # Flush pending writes (non-blocking).
        if self._sbuf:
            try:
                sent = self.sock.send(self._sbuf)
                self._sbuf = self._sbuf[sent:]
            except BlockingIOError:
                pass
            except OSError:
                self.closed = True
        # Split complete lines.
        while b"\n" in self._rbuf:
            line, _, self._rbuf = self._rbuf.partition(b"\n")
            try:
                records.append(json.loads(line.decode("utf-8")))
            except (ValueError, UnicodeDecodeError):
                continue  # malformed line dropped, keep going
        return records

    def write(self, rec: dict) -> None:
        self._sbuf += (json.dumps(rec) + "\n").encode("utf-8")

    @property
    def writable(self) -> bool:
        return bool(self._sbuf)


class RelayServer:
    """One process on one machine fans events out to every connected pet."""

    def __init__(self, host: str = "0.0.0.0", port: int = DEFAULT_PORT,
                 token: str = "") -> None:
        self.host = host
        self.port = port
        self.token = token or secrets.token_hex(16)
        self._sock: socket.socket | None = None
        self._clients: dict[socket.socket, _LineIO] = {}
        self._authed: set[_LineIO] = set()
        self._lock = threading.Lock()

    def token_to_print(self) -> str:
        return self.token

    def start(self) -> None:
        self._sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self._sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self._sock.bind((self.host, self.port))
        self._sock.listen(8)
        self._sock.setblocking(False)

    def serve_forever(self) -> None:
        assert self._sock is not None
        while True:
            try:
                readable, writable, _ = select.select(
                    [self._sock] + list(self._clients),
                    [io.sock for io in self._clients.values() if io.writable],
                    [], _POLL)
            except (OSError, ValueError, TypeError):
                # A concurrent close() invalidates the listener (fd -1) —
                # exit cleanly instead of crashing the serve loop.
                break
            if self._sock in readable:
                try:
                    conn, _addr = self._sock.accept()
                except (BlockingIOError, OSError):
                    pass
                else:
                    conn.setblocking(False)
                    self._clients[conn] = _LineIO(conn)  # pre-auth: reader only
                    readable.remove(self._sock)
            for sock in readable:
                io = self._clients.get(sock)
                if io is None:
                    continue
                try:
                    records = io.pump()
                except Exception:
                    # One bad socket must never kill the whole relay (f1).
                    records = []
                if io.closed:
                    with self._lock:
                        self._clients.pop(sock, None)
                    try:
                        sock.close()
                    except OSError:
                        pass
                    continue
                for rec in records:
                    try:
                        self._on_record(sock, io, rec)
                    except Exception:
                        # Per-record isolation: skip a poison record, keep
                        # the peer and the relay alive.
                        continue
            # flush writable clients
            for sock in writable:
                io = self._clients.get(sock)
                if io is None:
                    continue
                io.pump()
                if io.closed:
                    with self._lock:
                        self._clients.pop(sock, None)
                    try:
                        sock.close()
                    except OSError:
                        pass
            # drop dead clients not caught by select (closed sockets)
            for sock, io in list(self._clients.items()):
                if io.closed:
                    with self._lock:
                        self._clients.pop(sock, None)
                    try:
                        sock.close()
                    except OSError:
                        pass

    def _on_record(self, sock: socket.socket, io: _LineIO, rec: dict) -> None:
        # AUTH is the first message and grants membership.
        if rec.get("type") == "auth":
            if rec.get("token") == self.token:
                self._authed.add(io)
                io.write({"type": "hello", "host": self.host, "port": self.port})
                io.pump()
            # Wrong token: never reply, never broadcast to — forged peers die.
            return
        if rec.get("type") == "ping":
            io.write({"type": "pong"})
            io.pump()
            return
        clean = _valid_record(rec)
        if clean is None or io not in self._authed:
            return
        with self._lock:
            targets = [io2 for s2, io2 in self._clients.items()
                       if s2 is not sock and io2 in self._authed]
        for io2 in targets:
            io2.write(clean)
        for io2 in targets:
            io2.pump()

    def close(self) -> None:
        if self._sock is not None:
            try:
                self._sock.close()
            except OSError:
                pass
            self._sock = None
        with self._lock:
            for sock in list(self._clients):
                try:
                    sock.close()
                except OSError:
                    pass
            self._clients.clear()


class RelayClient:
    """One pet's link to a relay. Thread-safe: send() from any thread; the
    Tk mainloop drains inbound records via drain()."""

    def __init__(self, host: str, port: int = DEFAULT_PORT, token: str = "") -> None:
        self.host = host
        self.port = port
        self.token = token
        self._in: queue.Queue[dict] = queue.Queue()
        self._out: queue.Queue[dict] = queue.Queue()
        self._stop = threading.Event()
        self._thread: threading.Thread | None = None
        self.connected = False

    def start(self) -> None:
        self._thread = threading.Thread(target=self._run, daemon=True)
        self._thread.start()

    def _run(self) -> None:
        backoff = 2.0  # capped exponential backoff on reconnect (f2)
        while not self._stop.is_set():
            try:
                s = socket.create_connection((self.host, self.port), timeout=3.0)
            except OSError:
                self.connected = False
                self._stop.wait(backoff)
                backoff = min(backoff * 1.5, 30.0)
                continue
            backoff = 2.0  # connected — reset backoff
            s.setblocking(False)
            io = _LineIO(s)
            io.write({"type": "auth", "token": self.token})
            authenticated = False
            while not self._stop.is_set():
                try:
                    readable, writable, _ = select.select(
                        [s], [s] if io.writable else [], [], _POLL)
                except (OSError, ValueError, TypeError):
                    # Concurrent close() invalidated the socket — exit loop.
                    break
                if s in readable:
                    records = io.pump()
                    if io.closed:
                        break
                    for rec in records:
                        if not authenticated and rec.get("type") == "hello":
                            authenticated = True
                            self.connected = True
                            log.debug("relay: authenticated to %s:%s",
                                      self.host, self.port)
                            continue
                        clean = _valid_record(rec)
                        if clean is not None:
                            self._in.put(clean)
                if s in writable:
                    io.pump()
                    if io.closed:
                        break
                # Always drain the outbound queue into the write buffer so
                # events sent from the Tk thread reach the wire promptly.
                try:
                    while True:
                        rec = self._out.get_nowait()
                        io.write(rec)
                except queue.Empty:
                    pass
            self.connected = False
            try:
                s.close()
            except OSError:
                pass
            if not self._stop.is_set():
                self._stop.wait(backoff)
                backoff = min(backoff * 1.5, 30.0)

    def send(self, rec: dict) -> None:
        if not self.connected:
            return
        self._out.put(rec)

    def drain(self) -> list[dict]:
        out = []
        while True:
            try:
                out.append(self._in.get_nowait())
            except queue.Empty:
                return out

    def close(self) -> None:
        self._stop.set()
        if self._thread is not None:
            self._thread.join(timeout=2.0)


def default_token() -> str:
    """Token from env or a fresh one — lets two pets share an env-set key
    without passing secrets on the command line."""
    return os.environ.get("HERMES_COMPANION_TOKEN", "")
