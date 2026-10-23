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
import sys
from collections.abc import Iterator
from pathlib import Path

from freecad_buddy.contracts import ResultEnvelope, mirror_text
from freecad_buddy.contracts.rpc import (
    CHANNEL_ERROR_STATUS,
    RPC_BUSY_MESSAGE,
    RPC_ERROR_WORKER_CRASHED,
)
from freecad_buddy.usecases.process import pid_alive

logger = logging.getLogger("freecad_buddy.rpc_client")

_CONNECT_TIMEOUT_S = 2.0
_HELLO_TIMEOUT_S = 5.0
# How long a re-asked probe waits for the listener's answer. Measured on Windows: an idle listener
# accepts a hello in 0.16 ms at most (300 runs), so 0.1 s leaves room for a loaded worker. A busy
# listener answers only after its 0.2 s grace (rpc_listener._BUSY_GRACE_S), so the probe stays
# pending and the quarantined call is refused after at most this wait.
_PROBE_REASK_WAIT_S = 0.1
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
    if base:
        base_path = Path(base)
    elif sys.platform == "darwin":
        base_path = Path.home() / "Library" / "Application Support"
    else:
        base_path = Path.home() / ".local" / "share"
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


def _live_records(appdata_dir: str | Path | None) -> Iterator[dict]:
    """The discovery records whose ``pid`` is alive, newest first."""
    base = Path(appdata_dir) if appdata_dir is not None else _appdata_dir()
    directory = base / "freecad-buddy"
    try:
        files = sorted(directory.glob("rpc-*.json"), key=lambda p: p.stat().st_mtime, reverse=True)
    except OSError:
        return
    for path in files:
        try:
            record = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            continue
        pid = record.get("pid")
        if not isinstance(pid, int) or not pid_alive(pid):
            continue
        yield record


def discover(appdata_dir: str | Path | None = None) -> dict | None:
    """Return the newest live listener discovery record, or ``None`` if none is reachable."""
    return next(_live_records(appdata_dir), None)


class RpcClient:
    """One connection to a discovered listener; ``call`` never raises.

    ``endpoint`` (``host``, ``port``, ``token``) replaces discovery when the caller already knows
    its listener. ``read_timeout_s=None`` makes a read block until the reply arrives. ``pin=True``
    binds the client to the first record it connects to: it then reconnects only to a live record
    with that record's ``pid`` and ``token``, never to a newer FreeCAD (AD-2).
    """

    def __init__(
        self,
        appdata_dir: str | Path | None = None,
        contract_version: str = "1",
        client: str = "freecad-buddy-external",
        read_timeout_s: float | None = _DEFAULT_READ_TIMEOUT_S,
        endpoint: dict | None = None,
        pin: bool = False,
    ) -> None:
        self._appdata_dir = appdata_dir
        self._endpoint = endpoint
        self._pin = pin
        self._pinned: dict | None = None
        self._contract_version = contract_version
        self._client = client
        self._read_timeout_s = read_timeout_s
        self._sock: socket.socket | None = None
        self._buf = bytearray()
        self._next_id = 0
        self._connect_error: str | None = None
        self._probe: socket.socket | None = None
        self._probe_buf = bytearray()

    @property
    def pinned_record(self) -> dict | None:
        """The discovery record this client is pinned to, or ``None`` while nothing is pinned."""
        return self._pinned

    def pin(self) -> dict | None:
        """Pin the newest live record now, unless a record is pinned already; return the pin."""
        if self._pinned is None:
            self._pinned = discover(self._appdata_dir)
        return self._pinned

    def _record(self) -> dict | None:
        if self._endpoint is not None:
            return self._endpoint
        if self._pinned is not None:
            pid, token = self._pinned.get("pid"), self._pinned.get("token")
            return next(
                (
                    record
                    for record in _live_records(self._appdata_dir)
                    if record.get("pid") == pid and record.get("token") == token
                ),
                None,
            )
        if self._pin:
            return self.pin()
        return discover(self._appdata_dir)

    def _connect(self) -> tuple[socket.socket, object] | None:
        """Open a TCP connection to the listener; return it with the record's token."""
        record = self._record()
        if record is None:
            if self._pinned is not None:
                self._connect_error = (
                    f"the pinned listener (FreeCAD pid {self._pinned.get('pid')}) is gone"
                )
            else:
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
            rejection = self._handshake(token)
            if rejection is not None:
                self._close()
                self._connect_error = rejection
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

    def _handshake(self, token) -> str | None:
        """Send ``rpc_hello``; ``None`` when accepted, else why it was not."""
        self._send(self._hello_request(token))
        try:
            resp = self._read_frame()
        except (ValueError, OSError):
            return "handshake rejected"
        if _is_hello_accepted(resp):
            return None
        if _is_busy(resp):
            return RPC_BUSY_MESSAGE
        return "handshake rejected"

    def reconnect_answered(self) -> bool:
        """Reconnect without waiting for the hello reply; True once the listener has accepted it.

        The first call connects and sends ``rpc_hello``; each later call reads what has arrived.
        The listener accepts this hello only after the previous session has ended, and that
        session's serving loop ends only after the call it is running returns, so an accepted
        hello proves that call returned. A busy refusal is only as recent as the probe that got
        it, and the call may have returned since, so a refused probe is replaced by a new one that
        gets a short wait for its answer. One probe at most is pending. The accepted connection
        becomes this client's connection.
        """
        if self._sock is not None:
            return True
        if self._probe is None and not self._open_probe():
            return False
        accepted = self._probe_accepted(0.0)
        if accepted is False:
            if not self._open_probe():
                return False
            accepted = self._probe_accepted(_PROBE_REASK_WAIT_S)
        if not accepted:
            return False
        assert self._probe is not None
        rest = bytes(self._probe_buf).partition(b"\n")[2]
        self._sock, self._probe = self._probe, None
        self._buf = bytearray(rest)
        self._probe_buf = bytearray()
        self._sock.settimeout(self._read_timeout_s)
        return True

    def _probe_accepted(self, wait_s: float) -> bool | None:
        """Whether the probe's hello was accepted; ``None`` while no reply arrives in ``wait_s``.

        A refused or failed probe is closed.
        """
        assert self._probe is not None
        self._probe.settimeout(wait_s)
        try:
            while b"\n" not in self._probe_buf:
                chunk = self._probe.recv(65536)
                if not chunk:
                    self._close_probe()
                    return False
                self._probe_buf.extend(chunk)
        except (BlockingIOError, socket.timeout):
            return None
        except OSError:
            self._close_probe()
            return False
        line = bytes(self._probe_buf).partition(b"\n")[0]
        try:
            accepted = _is_hello_accepted(json.loads(line.decode("utf-8")))
        except ValueError:
            accepted = False
        if not accepted:
            self._close_probe()
        return accepted

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
                # A busy bridge is reachable; only its session slot is taken.
                busy = self._connect_error == RPC_BUSY_MESSAGE
                return _worker_crashed(self._connect_error or "unreachable", unreachable=not busy)
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
        except (ValueError, OSError) as exc:
            self._close()
            logger.warning("listener connection dropped during %s: %s", method, exc)
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


def _is_busy(resp) -> bool:
    error = resp.get("error") if isinstance(resp, dict) else None
    return (
        isinstance(error, dict)
        and error.get("code") == RPC_ERROR_WORKER_CRASHED
        and error.get("message") == RPC_BUSY_MESSAGE
    )


__all__ = ["RpcClient", "discover"]
