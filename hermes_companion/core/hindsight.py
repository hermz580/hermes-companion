"""Hindsight MCP client for the Hermes Companion (memory vault feed).

Connects to the local Hindsight memory server over streamable HTTP MCP
(`http://127.0.0.1:8768/mcp/` by default — the port Hermes registers for
hindsight). The companion uses it for the `memory_vault` behavior: memory
events show the vault glow and, when reachable, the pet can reflect real
memory activity (bank list, memory count) instead of a purely cosmetic prop.

Protocol: MCP "streamable HTTP" (JSON-RPC 2.0, one POST per message, session
id header). We keep it dependency-free (stdlib urllib) and FAIL SOFT: if the
server is unreachable or unconfigured, every call returns None/False and the
pet simply shows a closed vault. Nothing here ever renders memory CONTENT —
counts and bank names only (spec rev1 §5.4 / finding n4).
"""
from __future__ import annotations

import json
import os
import urllib.error
import urllib.request
from typing import Any

DEFAULT_URL = os.environ.get(
    "HERMES_COMPANION_HINDSIGHT_URL", "http://127.0.0.1:8768/mcp/")
DEFAULT_TIMEOUT = 3.0

_HEADERS = {
    "Content-Type": "application/json",
    "Accept": "application/json, text/event-stream",
}


class HindsightClient:
    """Minimal MCP streamable-HTTP client for the Hindsight server.

    Usage (all calls fail soft — None on any error):
        hs = HindsightClient()
        hs.ping()                 -> True/False
        hs.list_banks()           -> [{"id","name",...}] or None
        hs.memory_count(bank)     -> int or None
    """

    def __init__(self, url: str | None = None, timeout: float = DEFAULT_TIMEOUT,
                 name: str = "hermes-companion", version: str = "0.1") -> None:
        self.url = url or DEFAULT_URL
        self.timeout = timeout
        self._name = name
        self._version = version
        self._session: str | None = None
        self._ready = False

    # -- transport ----------------------------------------------------------
    def _post(self, payload: dict[str, Any]) -> dict[str, Any] | None:
        headers = dict(_HEADERS)
        if self._session:
            headers["Mcp-Session-Id"] = self._session
        req = urllib.request.Request(
            self.url, data=json.dumps(payload).encode("utf-8"),
            headers=headers, method="POST")
        try:
            with urllib.request.urlopen(req, timeout=self.timeout) as resp:
                sid = resp.headers.get("Mcp-Session-Id")
                if sid:
                    self._session = sid
                body = resp.read().decode("utf-8", "replace")
        except (urllib.error.URLError, OSError, ValueError):
            self._ready = False
            return None
        # streamable HTTP returns SSE-framed JSON: `event: message\ndata: {...}`
        for line in body.splitlines():
            if line.startswith("data:"):
                data = line[5:].strip()
                try:
                    return json.loads(data)
                except ValueError:
                    continue
        try:
            return json.loads(body)
        except ValueError:
            return None

    def _call(self, method: str, params: dict[str, Any] | None = None,
              req_id: int = 1) -> dict[str, Any] | None:
        payload: dict[str, Any] = {"jsonrpc": "2.0", "method": method}
        if params is not None:
            payload["params"] = params
        if method not in ("notifications/initialized",):
            payload["id"] = req_id
        return self._post(payload)

    # -- lifecycle ----------------------------------------------------------
    def connect(self) -> bool:
        """Run the MCP initialize handshake. Returns True when ready."""
        init = self._call("initialize", {
            "protocolVersion": "2025-03-26",
            "capabilities": {},
            "clientInfo": {"name": self._name, "version": self._version},
        }, req_id=1)
        if init is None or "result" not in init:
            self._ready = False
            return False
        self._call("notifications/initialized")
        self._ready = True
        return True

    def ping(self) -> bool:
        if not self._ready:
            self.connect()
        return self._ready

    # -- read tools (counts / names only — never content) --------------------
    def list_banks(self) -> list[dict[str, Any]] | None:
        """List memory banks. Returns [{'id','name',...}] or None."""
        if not self.ping():
            return None
        res = self._call("tools/call", {
            "name": "list_banks", "arguments": {},
        }, req_id=2)
        return _result_list(res)

    def memory_count(self, bank_id: str | None = None) -> int | None:
        """Number of stored facts, from list_banks' fact_count (metadata only)."""
        if not self.ping():
            return None
        banks = self.list_banks()
        if not banks:
            return None
        if bank_id:
            for b in banks:
                if b.get("bank_id") == bank_id and "fact_count" in b:
                    return int(b["fact_count"])
        # total across banks
        counts = [int(b["fact_count"]) for b in banks
                  if isinstance(b.get("fact_count"), (int, float))]
        return sum(counts) if counts else None

    def recall(self, query: str, limit: int = 3) -> list[dict[str, Any]] | None:
        """Recall matching memories (metadata only — callers must NOT render
        the content field; the companion only uses counts/labels)."""
        if not self.ping():
            return None
        res = self._call("tools/call", {
            "name": "recall",
            "arguments": {"query": query, "limit": limit},
        }, req_id=4)
        return _result_list(res)


def _result_list(res: dict[str, Any] | None) -> list[dict[str, Any]] | None:
    """Best-effort: MCP tools return {content:[{text: json}], structuredContent}."""
    if res is None or "result" not in res:
        return None
    result = res["result"]
    if isinstance(result, dict) and result.get("structuredContent"):
        sc = result["structuredContent"]
        if isinstance(sc, dict) and "results" in sc and isinstance(sc["results"], list):
            return [x for x in sc["results"] if isinstance(x, dict)]
    try:
        text = result["content"][0]["text"]
        data = json.loads(text)
        if isinstance(data, list):
            return [x for x in data if isinstance(x, dict)]
        if isinstance(data, dict):
            for key in ("banks", "results", "memories", "data"):
                if key in data and isinstance(data[key], list):
                    return [x for x in data[key] if isinstance(x, dict)]
            return [data]
    except (KeyError, IndexError, TypeError, ValueError):
        pass
    return None
