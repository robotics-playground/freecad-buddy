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
from freecad_buddy.usecases.process import pid_alive

logger = logging.getLogger("freecad_buddy.rpc_client")

_CONNECT_TIMEOUT_S = 2.0
_HELLO_TIMEOUT_S = 5.0
_DEFAULT_READ_TIMEOUT_S = 130.0
_MAX_FRAME_BYTES = 16 * 1024 * 1024


def _appdata_dir() -> Path:
    # The listener writes its discovery file under FreeCAD.getUserAppDataDir(), which on Windows
    # is the versioned ...\FreeCAD\v1-1\ dir — not the bare %APPDATA%. The external client cannot
    # import FreeCAD to resolve that, so FREECAD_BUDDY_RPC_DIR overrides the base directory that
    # holds the "freecad-buddy/" discovery folder; otherwise the known FreeCAD-versioned appdata
    # layout is probed before the bare %APPDATA% fallback.
    override = os.environ.get("FREECAD_BUDDY_RPC_DIR")
    if override:
        return Path(override)
    base = os.environ.get("APPDATA") or os.environ.get("XDG_DATA_HOME")
    if not base:
        return Path.home() / ".local" / "share"
    base_path = Path(base)
    freecad_root = base_path / "FreeCAD"
    if freecad_root.is_dir():
        # Newest versioned dir (e.g. v1-1) whose freecad-buddy/ discovery folder exists.
        versioned = sorted(
            (d for d in freecad_root.glob("v*") if (d / "freecad-buddy").is_dir()),
            reverse=True,
        )
        if versioned:
            return versioned[0]
    return base_path


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
        if not isinstance(pid, int) or not pid_alive(pid):
            continue
        return record
    return None


class RpcClient:
    """One connection to a discovered listener; ``call`` never raises.

    ``endpoint`` (``host``, ``port``, ``token``) replaces discovery when the caller already knows
    its listener. ``read_timeout_s=None`` makes a read block until the reply arrives.
    """

    def __init__(
        self,
        appdata_dir: str | Path | None = None,
        contract_version: str = "1",
        client: str = "freecad-buddy-external",
        read_timeout_s: float | None = _DEFAULT_READ_TIMEOUT_S,
        endpoint: dict | None = None,
    ) -> None:
        self._appdata_dir = appdata_dir
        self._endpoint = endpoint
        self._contract_version = contract_version
        self._client = client
        self._read_timeout_s = read_timeout_s
        self._sock: socket.socket | None = None
        self._buf = bytearray()
        self._next_id = 0
        self._connect_error: str | None = None
        self._probe: socket.socket | None = None
        self._probe_buf = bytearray()

    def _record(self) -> dict | None:
        if self._endpoint is not None:
            return self._endpoint
        return discover(self._appdata_dir)

    def _connect(self) -> tuple[socket.socket, object] | None:
        """Open a TCP connection to the listener; return it with the record's token."""
        record = self._record()
        if record is None:
            self._connect_error = "no live listener discovery file"
            return None
        host = record.get("host")
        port = record.get("port")
        if not isinstance(host, str) or not isinstance(port, int):
            self._connect_error = "discovery record missing host/port"
            return None
        try:
            sock = socket.create_connection((host, port), timeout=_CONNECT_TIMEOUT_S)
        except OSError:
            self._connect_error = "connect refused"
            return None
        return sock, record.get("token")

    def _ensure_connected(self) -> bool:
        if self._sock is not None:
            return True
        connected = self._connect()
        if connected is None:
            return False
        sock, token = connected
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

    def _hello_request(self, token) -> dict:
        return {
            "jsonrpc": "2.0",
            "id": self._alloc_id(),
            "method": "rpc_hello",
            "params": {
                "contract_version": self._contract_version,
                "client": self._client,
                "token": token if isinstance(token, str) else "",
            },
        }

    def _handshake(self, token) -> bool:
        self._send(self._hello_request(token))
        try:
            resp = self._read_frame()
        except (ValueError, OSError):
            return False
        return _is_hello_accepted(resp)

    def reconnect_answered(self) -> bool:
        """Reconnect without waiting for the hello reply; True once the listener has answered it.

        The first call connects and sends ``rpc_hello``; each later call reads what has arrived
        and never blocks. A listener that serves one connection at a time accepts this one only
        after it has finished the call it is running, so the answer proves that call returned.
        One such connection at most is pending: a new one per call would queue stale connections
        in the listener's backlog. The answered connection becomes this client's connection.
        """
        if self._sock is not None:
            return True
        if self._probe is None and not self._open_probe():
            return False
        assert self._probe is not None
        try:
            while b"\n" not in self._probe_buf:
                chunk = self._probe.recv(65536)
                if not chunk:
                    self._close_probe()
                    return False
                self._probe_buf.extend(chunk)
        except BlockingIOError:
            return False
        except OSError:
            self._close_probe()
            return False
        line, _newline, rest = bytes(self._probe_buf).partition(b"\n")
        try:
            accepted = _is_hello_accepted(json.loads(line.decode("utf-8")))
        except ValueError:
            accepted = False
        if not accepted:
            self._close_probe()
            return False
        self._sock, self._probe = self._probe, None
        self._buf = bytearray(rest)
        self._probe_buf = bytearray()
        self._sock.settimeout(self._read_timeout_s)
        return True

    def _open_probe(self) -> bool:
        connected = self._connect()
        if connected is None:
            return False
        sock, token = connected
        try:
            sock.sendall(_encode(self._hello_request(token)))
        except OSError:
            sock.close()
            return False
        sock.setblocking(False)
        self._probe = sock
        self._probe_buf = bytearray()
        return True

    def _close_probe(self) -> None:
        if self._probe is not None:
            try:
                self._probe.close()
            except OSError:
                pass
            self._probe = None
        self._probe_buf = bytearray()

    def call(
        self, method: str, params: dict | None = None, *, read_timeout_s: float | None = None
    ) -> ResultEnvelope:
        """Call a tool and return its envelope. Never raises.

        ``read_timeout_s`` replaces the client's read timeout for this call only.
        """
        try:
            if not self._ensure_connected():
                return _worker_crashed(self._connect_error or "unreachable", unreachable=True)
            assert self._sock is not None
            self._sock.settimeout(
                self._read_timeout_s if read_timeout_s is None else read_timeout_s
            )
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
        self._close_probe()

    # -- framing -----------------------------------------------------------------------------

    def _alloc_id(self) -> int:
        self._next_id += 1
        return self._next_id

    def _send(self, obj: dict) -> None:
        assert self._sock is not None
        self._sock.sendall(_encode(obj))

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


def _encode(obj: dict) -> bytes:
    return (json.dumps(obj, ensure_ascii=False) + "\n").encode("utf-8")


def _is_hello_accepted(resp) -> bool:
    return isinstance(resp, dict) and "result" in resp and "error" not in resp


__all__ = ["RpcClient", "discover"]
