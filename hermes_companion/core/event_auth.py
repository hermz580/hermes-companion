"""Authenticate content-free local event records with a profile-local key.

The JSONL file is writable by local processes, so records carry an HMAC. The
key is created once beside the log and restricted to the current OS account.
Readers fail closed: malformed, unsigned, wrong-key, or modified records return
``None``.
"""
from __future__ import annotations

import getpass
import hashlib
import hmac
import json
import os
import secrets
import stat
import subprocess
from pathlib import Path
from typing import Any, Mapping

AUTH_FIELD = "auth"
AUTH_VERSION = 1
AUTH_ALGORITHM = "hmac-sha256"
KEY_BYTES = 32
_DOMAIN = b"hermes-companion-local-event-v1\x00"


def _canonical(payload: Mapping[str, Any]) -> bytes:
    return json.dumps(
        payload,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    ).encode("utf-8")


def _protect_windows(path: Path) -> None:
    """Remove inherited ACLs and grant only the current account full access."""
    user = getpass.getuser()
    result = subprocess.run(
        ["icacls", str(path), "/inheritance:r", "/grant:r", f"{user}:(F)"],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        check=False,
        timeout=10,
    )
    if result.returncode != 0:
        raise PermissionError(f"could not restrict event key ACL: {path}")


def _protect_key(path: Path) -> None:
    if os.name == "nt":
        _protect_windows(path)
        return
    os.chmod(path, stat.S_IRUSR | stat.S_IWUSR)
    if stat.S_IMODE(path.stat().st_mode) != 0o600:
        raise PermissionError(f"event key permissions are not private: {path}")


def load_or_create_event_key(path: Path | str) -> bytes:
    """Load a 256-bit key, atomically creating and protecting it if absent."""
    key_path = Path(path)
    key_path.parent.mkdir(parents=True, exist_ok=True)
    try:
        fd = os.open(str(key_path), os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    except FileExistsError:
        fd = None
    if fd is not None:
        try:
            with os.fdopen(fd, "wb") as stream:
                stream.write(secrets.token_bytes(KEY_BYTES))
                stream.flush()
                os.fsync(stream.fileno())
            _protect_key(key_path)
        except BaseException:
            try:
                key_path.unlink()
            except OSError:
                pass
            raise
    key = key_path.read_bytes()
    if len(key) != KEY_BYTES:
        raise ValueError(f"invalid local event key length: {key_path}")
    return key


def sign_record(record: Mapping[str, Any], key: bytes) -> dict[str, Any]:
    """Return a copy of ``record`` with a versioned HMAC envelope."""
    if not isinstance(record, Mapping) or AUTH_FIELD in record:
        raise ValueError("event record must be an unsigned mapping")
    if not isinstance(key, bytes) or len(key) != KEY_BYTES:
        raise ValueError("event authentication key must be exactly 32 bytes")
    payload = dict(record)
    mac = hmac.new(key, _DOMAIN + _canonical(payload), hashlib.sha256).hexdigest()
    return {
        **payload,
        AUTH_FIELD: {"v": AUTH_VERSION, "alg": AUTH_ALGORITHM, "mac": mac},
    }


def verify_record(record: Any, key: bytes) -> dict[str, Any] | None:
    """Return the authenticated payload, or ``None`` for every invalid record."""
    if not isinstance(record, dict) or not isinstance(key, bytes) or len(key) != KEY_BYTES:
        return None
    auth = record.get(AUTH_FIELD)
    if not isinstance(auth, dict) or set(auth) != {"v", "alg", "mac"}:
        return None
    if auth.get("v") != AUTH_VERSION or auth.get("alg") != AUTH_ALGORITHM:
        return None
    supplied = auth.get("mac")
    if not isinstance(supplied, str) or len(supplied) != 64:
        return None
    payload = {name: value for name, value in record.items() if name != AUTH_FIELD}
    try:
        expected = hmac.new(key, _DOMAIN + _canonical(payload), hashlib.sha256).hexdigest()
    except (TypeError, ValueError):
        return None
    return payload if hmac.compare_digest(supplied, expected) else None
