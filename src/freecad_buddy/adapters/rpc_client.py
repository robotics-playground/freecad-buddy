"""External NDJSON RPC client for the in-FreeCAD listener.

Discovers the newest live listener via its 0600 discovery file, connects, performs the
``rpc_hello`` handshake, and turns tool calls into ``ResultEnvelope``s. This runs in the external
uv process, so third-party imports are permitted — but ``call`` NEVER raises: every decode,
parse, lookup, or socket failure is synthesized into an envelope (``WORKER_CRASHED`` for an
unreachable/crashed listener) so the caller always gets a wire-shaped result.
"""

from __future__ import annotations

import json
import logging
import os
import socket
from pathlib import Path

from freecad_buddy.contracts import ResultEnvelope, mirror_text
from freecad_buddy.contracts.rpc import CHANNEL_ERROR_STATUS

logger = logging.getLogger("freecad_buddy.rpc_client")

_CONNECT_TIMEOUT_S = 2.0
_HELLO_TIMEOUT_S = 5.0
_DEFAULT_READ_TIMEOUT_S = 130.0
_MAX_FRAME_BYTES = 16 * 1024 * 1024


def _appdata_dir() -> Path:
    base = os.environ.get("APPDATA") or os.environ.get("XDG_DATA_HOME")
    if base:
        return Path(base)
    return Path.home() / ".local" / "share"


def _pid_alive(pid: int) -> bool:
    """Cross-platform best-effort liveness check for a discovery-file ``pid``."""
    if pid <= 0:
        return False
    if os.name == "nt":
        try:
            import ctypes

            process = ctypes.windll.kernel32.OpenProcess(0x1000, False, pid)
            if not process:
                return False
            ctypes.windll.kernel32.CloseHandle(process)
            return True
        except Exception:  # noqa: BLE001 - liveness is best-effort
            return True
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    except PermissionError:
        return True
    except OSError:
        return False
    return True


def _worker_crashed(message: str, *, unreachable: bool = False) -> ResultEnvelope:
    structured: dict = {}
    data: dict = {}
    if unreachable:
        data["rpc"] = "unreachable"
    return {
        "schema": "fcb.result-envelope/1",
        "status": "WORKER_CRASHED",
        "detail": {"code": "WORKER_CRASHED", "message": message, "data": data},
        "structured_content": structured,
        "text": mirror_text(structured),
    }


def _channel_error_envelope(error: object) -> ResultEnvelope:
    """Map a JSON-RPC channel error frame to the status the wire contract assigns its code.

    A version/handshake rejection is ``INVALID_INPUT`` per ``CHANNEL_ERROR_STATUS``; an unmapped
    code (e.g. a dropped/auth-failed connection) falls back to ``WORKER_CRASHED``.
    """
    code = error.get("code") if isinstance(error, dict) else None
    message = (
        error.get("message", "listener protocol error")
        if isinstance(error, dict)
        else "listener protocol error"
    )
    status = CHANNEL_ERROR_STATUS.get(code) if isinstance(code, int) else None
    if status is None:
        return _worker_crashed(str(message), unreachable=True)
    structured: dict = {}
    return {
        "schema": "fcb.result-envelope/1",
        "status": status,  # type: ignore[typeddict-item]
        "detail": {"code": status, "message": str(message), "data": {}},
        "structured_content": structured,
        "text": mirror_text(structured),
    }


def _timeout_envelope(message: str) -> ResultEnvelope:
    structured: dict = {}
    return {
        "schema": "fcb.result-envelope/1",
        "status": "TIMEOUT",
        "detail": {
            "code": "TIMEOUT",
            "message": message,
            "data": {"marshal_timeout": False, "maybe_still_running": True},
        },
        "structured_content": structured,
        "text": mirror_text(structured),
    }


def discover(appdata_dir: str | Path | None = None) -> dict | None:
    """Return the newest live listener discovery record, or ``None`` if none is reachable."""
    base = Path(appdata_dir) if appdata_dir is not None else _appdata_dir()
    directory = base / "freecad-buddy"
    try:
        files = sorted(directory.glob("rpc-*.json"), key=lambda p: p.stat().st_mtime, reverse=True)
    except OSError:
        return None
    for path in files:
        try:
            record = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            continue
        pid = record.get("pid")
        if not isinstance(pid, int) or not _pid_alive(pid):
            continue
        return record
    return None


class RpcClient:
    """One connection to a discovered listener; ``call`` never raises."""

    def __init__(
        self,
        appdata_dir: str | Path | None = None,
        contract_version: str = "1",
        client: str = "freecad-buddy-external",
        read_timeout_s: float = _DEFAULT_READ_TIMEOUT_S,
    ) -> None:
        self._appdata_dir = appdata_dir
        self._contract_version = contract_version
        self._client = client
        self._read_timeout_s = read_timeout_s
        self._sock: socket.socket | None = None
        self._buf = bytearray()
        self._next_id = 0
        self._connect_error: str | None = None

    def _record(self) -> dict | None:
        return discover(self._appdata_dir)

    def _ensure_connected(self) -> bool:
        if self._sock is not None:
            return True
        record = self._record()
        if record is None:
            self._connect_error = "no live listener discovery file"
            return False
        host = record.get("host")
        port = record.get("port")
        token = record.get("token")
        if not isinstance(host, str) or not isinstance(port, int):
            self._connect_error = "discovery record missing host/port"
            return False
        try:
            sock = socket.create_connection((host, port), timeout=_CONNECT_TIMEOUT_S)
        except OSError:
            self._connect_error = "connect refused"
            return False
        try:
            sock.settimeout(_HELLO_TIMEOUT_S)
            self._sock = sock
            self._buf = bytearray()
            if not self._handshake(token):
                self._close()
                self._connect_error = "handshake rejected"
                return False
        except OSError:
            self._close()
            self._connect_error = "handshake failed"
            return False
        sock.settimeout(self._read_timeout_s)
        return True

    def _handshake(self, token) -> bool:
        req = {
            "jsonrpc": "2.0",
            "id": self._alloc_id(),
            "method": "rpc_hello",
            "params": {
                "contract_version": self._contract_version,
                "client": self._client,
                "token": token if isinstance(token, str) else "",
            },
        }
        self._send(req)
        try:
            resp = self._read_frame()
        except (ValueError, OSError):
            return False
        return isinstance(resp, dict) and "result" in resp and "error" not in resp

    def call(self, method: str, params: dict | None = None) -> ResultEnvelope:
        """Call a tool and return its envelope. Never raises."""
        try:
            if not self._ensure_connected():
                return _worker_crashed(self._connect_error or "unreachable", unreachable=True)
            req = {
                "jsonrpc": "2.0",
                "id": self._alloc_id(),
                "method": method,
                "params": params or {},
            }
            self._send(req)
            resp = self._read_frame()
        except socket.timeout:
            self._close()
            return _timeout_envelope("listener read timed out")
        except (ValueError, OSError):
            self._close()
            return _worker_crashed("listener connection dropped", unreachable=True)
        except (KeyError, TypeError):
            self._close()
            return _worker_crashed("malformed listener response")

        if not isinstance(resp, dict):
            return _worker_crashed("malformed listener response")
        if "error" in resp:
            return _channel_error_envelope(resp["error"])
        result = resp.get("result")
        if not isinstance(result, dict):
            return _worker_crashed("malformed listener response")
        return result  # type: ignore[return-value]

    def close(self) -> None:
        self._close()

    # -- framing -----------------------------------------------------------------------------

    def _alloc_id(self) -> int:
        self._next_id += 1
        return self._next_id

    def _send(self, obj: dict) -> None:
        assert self._sock is not None
        self._sock.sendall((json.dumps(obj, ensure_ascii=False) + "\n").encode("utf-8"))

    def _read_frame(self):
        assert self._sock is not None
        while True:
            nl = self._buf.find(b"\n")
            if nl != -1:
                raw = bytes(self._buf[:nl])
                del self._buf[: nl + 1]
                return json.loads(raw.decode("utf-8"))
            if len(self._buf) > _MAX_FRAME_BYTES:
                raise ValueError("frame exceeds 16 MiB cap")
            chunk = self._sock.recv(65536)
            if not chunk:
                raise OSError("connection closed")
            self._buf.extend(chunk)

    def _close(self) -> None:
        if self._sock is not None:
            try:
                self._sock.close()
            except OSError:
                pass
            self._sock = None
        self._buf = bytearray()


__all__ = ["RpcClient", "discover"]
