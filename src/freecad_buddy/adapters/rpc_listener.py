"""In-FreeCAD RPC listener. Runs inside the FreeCAD process; stdlib only.

NDJSON JSON-RPC over a localhost TCP socket. The first frame on every connection must be
``rpc_hello`` (token via ``hmac.compare_digest``, ``contract_version`` checked); afterwards each
request is dispatched through **exactly one** ``marshal.call`` — the registry it dispatches holds
un-marshaled handlers, because a second marshal layer on the single Qt main thread would
deadlock. Requests run strictly sequentially per connection. A malformed frame never kills the
accept loop: it yields an ``INVALID_INPUT`` envelope where decodable, otherwise closes just that
connection.
"""

from __future__ import annotations

import hmac
import json
import logging
import os
import socket
import threading
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable

from freecad_buddy.adapters.marshal import Marshal, MarshalTimeout
from freecad_buddy.adapters.rpc_dispatch import MethodRegistry
from freecad_buddy.contracts import ResultEnvelope, mirror_text
from freecad_buddy.contracts.rpc import (
    RPC_ERROR_NO_HANDSHAKE,
    RPC_ERROR_VERSION_MISMATCH,
    RPC_ERROR_WORKER_CRASHED,
)

logger = logging.getLogger("freecad_buddy.rpc_listener")

_MAX_FRAME_BYTES = 16 * 1024 * 1024
_SUPPORTED_VERSIONS = ["1"]


def _appdata_dir() -> Path:
    """FreeCAD user appdata dir, resolved lazily inside FreeCAD; stdlib fallback otherwise.

    Importing FreeCAD is deferred to call time so the module stays importable (and stdlib-clean)
    in the external test environment where FreeCAD is absent.
    """
    try:
        import FreeCAD  # noqa: F401 - probing availability

        return Path(FreeCAD.getUserAppDataDir())
    except Exception:  # noqa: BLE001 - no FreeCAD (external/tests): fall back to a stdlib path
        base = os.environ.get("APPDATA") or os.environ.get("XDG_DATA_HOME")
        if base:
            return Path(base)
        return Path.home() / ".local" / "share"


class _FrameReader:
    """Buffered NDJSON reader over a socket: yields UTF-8 lines, enforcing the 16 MiB cap."""

    def __init__(self, conn: socket.socket) -> None:
        self._conn = conn
        self._buf = bytearray()

    def read_line(self) -> str | None:
        """Return the next ``\\n``-terminated line decoded UTF-8, or ``None`` at EOF.

        Raises ``ValueError`` on an over-cap frame or non-UTF-8 bytes so the caller can reply
        ``INVALID_INPUT`` / close the connection without killing the accept loop.
        """
        while True:
            nl = self._buf.find(b"\n")
            if nl != -1:
                raw = bytes(self._buf[:nl])
                del self._buf[: nl + 1]
                return raw.decode("utf-8")
            if len(self._buf) > _MAX_FRAME_BYTES:
                raise ValueError("frame exceeds 16 MiB cap")
            chunk = self._conn.recv(65536)
            if not chunk:
                if self._buf:
                    raise ValueError("connection closed mid-frame")
                return None
            self._buf.extend(chunk)


def _envelope(status: str, message: str) -> ResultEnvelope:
    structured: dict = {}
    return {
        "schema": "fcb.result-envelope/1",
        "status": status,  # type: ignore[typeddict-item]
        "detail": {"code": status, "message": message, "data": {}},  # type: ignore[typeddict-item]
        "structured_content": structured,
        "text": mirror_text(structured),
    }


def _invalid_input(message: str) -> ResultEnvelope:
    return _envelope("INVALID_INPUT", message)


class RpcListener:
    """NDJSON JSON-RPC listener that dispatches through a single main-thread marshal."""

    def __init__(
        self,
        registry: MethodRegistry,
        marshal: Marshal,
        token: str,
        host: str = "127.0.0.1",
        port: int = 0,
        contract_version: str = "1",
        freecad_version: str = "unknown",
        capabilities: dict | None = None,
        appdata_dir: str | Path | None = None,
        audit=None,
    ) -> None:
        self._registry = registry
        self._marshal = marshal
        self._token = token
        self._host = host
        self._port = port
        self._contract_version = contract_version
        self._freecad_version = freecad_version
        self._capabilities = capabilities or {}
        self._appdata_dir = Path(appdata_dir) if appdata_dir is not None else None
        self._audit = audit

        self._sock: socket.socket | None = None
        self._thread: threading.Thread | None = None
        self._stop = threading.Event()
        self._suspect_docs: set[str] = set()
        self._suspect_no_doc = False
        self._discovery_path: Path | None = None

    # -- lifecycle ---------------------------------------------------------------------------

    def _bind(self) -> tuple[str, int]:
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        sock.bind((self._host, self._port))
        sock.listen(1)
        self._sock = sock
        host, port = sock.getsockname()[:2]
        self._port = port
        self._write_discovery(host, port)
        return host, port

    def start_threaded(self) -> tuple[str, int]:
        """Bind, write the discovery file, and run the accept loop on a daemon thread."""
        host, port = self._bind()
        self._thread = threading.Thread(target=self._accept_loop, name="fcb-rpc", daemon=True)
        self._thread.start()
        return host, port

    def serve_forever_inline(self) -> tuple[str, int]:
        """Bind and run the accept loop on the calling (main) thread until ``stop``."""
        host, port = self._bind()
        self._accept_loop()
        return host, port

    def stop(self) -> None:
        """Stop accepting, close the socket, and delete the discovery file."""
        self._stop.set()
        sock = self._sock
        if sock is not None:
            try:
                sock.close()
            except OSError:
                pass
        self._delete_discovery()

    # -- discovery ---------------------------------------------------------------------------

    def _discovery_dir(self) -> Path:
        base = self._appdata_dir if self._appdata_dir is not None else _appdata_dir()
        return base / "freecad-buddy"

    def _write_discovery(self, host: str, port: int) -> None:
        record = {
            "schema": 1,
            "pid": os.getpid(),
            "host": host,
            "port": port,
            "token": self._token,
            "contract_version": self._contract_version,
            "freecad_version": self._freecad_version,
            "started": datetime.now(timezone.utc).isoformat(),
        }
        directory = self._discovery_dir()
        directory.mkdir(parents=True, exist_ok=True)
        path = directory / f"rpc-{os.getpid()}.json"
        path.write_text(json.dumps(record), encoding="utf-8")
        # 0600 is best-effort: on Windows chmod only toggles the read-only bit, so the loopback
        # bind + per-session token remain the enforced posture.
        try:
            os.chmod(path, 0o600)
        except OSError:
            pass
        self._discovery_path = path

    def _delete_discovery(self) -> None:
        path = self._discovery_path
        if path is None:
            return
        try:
            path.unlink()
        except OSError:
            pass
        self._discovery_path = None

    # -- accept / serve ----------------------------------------------------------------------

    def _accept_loop(self) -> None:
        sock = self._sock
        assert sock is not None
        while not self._stop.is_set():
            try:
                conn, _addr = sock.accept()
            except OSError:
                # Socket closed by stop(), or a transient accept error: end the loop cleanly.
                return
            try:
                self._serve_conn(conn)
            except Exception:  # noqa: BLE001 - one bad connection must not stop the listener
                logger.exception("connection handler crashed")
            finally:
                try:
                    conn.close()
                except OSError:
                    pass

    def _serve_conn(self, conn: socket.socket) -> None:
        reader = _FrameReader(conn)
        if not self._handshake(conn, reader):
            return
        while not self._stop.is_set():
            try:
                line = reader.read_line()
            except (ValueError, OSError):
                # Over-cap / non-UTF-8 / dropped mid-frame: close just this connection.
                logger.exception("frame read failed; closing connection")
                return
            if line is None:
                return
            try:
                env = self._handle_request(json.loads(line))
            except Exception:  # noqa: BLE001 - one bad frame never kills the loop
                logger.exception("malformed request")
                env = _invalid_input("malformed request")
            self._write_frame(conn, {"jsonrpc": "2.0", "id": _safe_id(line), "result": env})

    # -- handshake ---------------------------------------------------------------------------

    def _handshake(self, conn: socket.socket, reader: _FrameReader) -> bool:
        try:
            line = reader.read_line()
        except (ValueError, OSError):
            logger.exception("handshake frame read failed")
            return False
        if line is None:
            return False
        try:
            req = json.loads(line)
        except ValueError:
            self._write_error(conn, None, RPC_ERROR_NO_HANDSHAKE, "handshake required")
            return False
        req_id = req.get("id") if isinstance(req, dict) else None
        if not isinstance(req, dict) or req.get("method") != "rpc_hello":
            logger.warning("first frame was not rpc_hello; closing")
            self._write_error(conn, req_id, RPC_ERROR_NO_HANDSHAKE, "handshake required")
            return False
        params = req.get("params")
        params = params if isinstance(params, dict) else {}
        # Authenticate before disclosing anything (including the supported-version list) to an
        # unauthenticated caller.
        token = params.get("token") or ""
        if not hmac.compare_digest(str(token), self._token):
            logger.warning("token mismatch; closing")
            self._write_error(conn, req_id, RPC_ERROR_WORKER_CRASHED, "auth failed")
            return False
        if params.get("contract_version") != self._contract_version:
            self._write_error(
                conn,
                req_id,
                RPC_ERROR_VERSION_MISMATCH,
                "contract version unsupported",
                data={"supported": list(_SUPPORTED_VERSIONS)},
            )
            return False
        result = {
            "contract_version": self._contract_version,
            "freecad_version": self._freecad_version,
            "capabilities": dict(self._capabilities),
        }
        self._write_frame(conn, {"jsonrpc": "2.0", "id": req_id, "result": result})
        return True

    # -- request handling --------------------------------------------------------------------

    def _handle_request(self, req: dict) -> ResultEnvelope:
        if not isinstance(req, dict):
            return _invalid_input("request must be a JSON object")
        name = req.get("method")
        params = req.get("params", {})
        if not isinstance(params, dict):
            return _invalid_input("params must be an object")

        method = self._registry.get(name) if isinstance(name, str) else None
        mutating = bool(method is not None and method.mutating)
        doc = params.get("doc")

        if doc is not None and not isinstance(doc, str):
            return _invalid_input("doc handle must be a string")

        if mutating and self._is_suspect(doc):
            return _invalid_input(
                "document-suspect: a prior call timed out on this document; "
                "run a query_* read to confirm state before mutating"
            )

        audited = method is not None and (method.mutating or method.name == "debug_exec")
        event = method.audit_event if method is not None else "mutation"
        doc_str = doc if isinstance(doc, str) else None
        if audited and self._audit is not None:
            self._audit_safe(self._audit.before, event, name, doc_str, params)

        timeout_s = method.timeout_s if method is not None else 30.0
        try:
            env = self._marshal.call(lambda: self._registry.dispatch(name, params), timeout_s)
        except MarshalTimeout:
            env = self._timeout_envelope()
            if mutating:
                self._mark_suspect(doc)

        if audited and self._audit is not None:
            self._audit_safe(self._audit.after, event, name, doc_str, params, env.get("status"))

        self._update_suspect(method, mutating, doc, env)
        return env

    def _timeout_envelope(self) -> ResultEnvelope:
        env = _envelope("TIMEOUT", "marshaled call timed out")
        env["detail"]["data"]["marshal_timeout"] = True  # type: ignore[index]
        env["detail"]["data"]["maybe_still_running"] = True  # type: ignore[index]
        return env

    def _update_suspect(self, method, mutating: bool, doc, env: ResultEnvelope) -> None:
        """Clear a document-suspect flag only on a non-mutating OK that re-read the same doc."""
        if method is None or mutating or env.get("status") != "OK":
            return
        if doc is None:
            self._suspect_no_doc = False
        elif isinstance(doc, str):
            self._suspect_docs.discard(doc)

    def _is_suspect(self, doc) -> bool:
        if doc is None:
            return self._suspect_no_doc
        return isinstance(doc, str) and doc in self._suspect_docs

    def _mark_suspect(self, doc) -> None:
        if doc is None:
            self._suspect_no_doc = True
        elif isinstance(doc, str):
            self._suspect_docs.add(doc)

    def _audit_safe(self, fn: Callable, *args) -> None:
        try:
            fn(*args)
        except Exception:  # noqa: BLE001 - audit failure must not break a served call
            logger.exception("audit write failed")

    # -- framing -----------------------------------------------------------------------------

    def _write_frame(self, conn: socket.socket, obj: dict) -> None:
        data = (json.dumps(obj, ensure_ascii=False) + "\n").encode("utf-8")
        try:
            conn.sendall(data)
        except OSError:
            logger.exception("failed to write frame")

    def _write_error(
        self, conn: socket.socket, req_id, code: int, message: str, data: dict | None = None
    ) -> None:
        error: dict = {"code": code, "message": message}
        if data is not None:
            error["data"] = data
        self._write_frame(conn, {"jsonrpc": "2.0", "id": req_id, "error": error})


def _safe_id(line: str):
    """Best-effort request id echo from a possibly-malformed line."""
    try:
        obj = json.loads(line)
        if isinstance(obj, dict):
            return obj.get("id")
    except ValueError:
        pass
    return None
