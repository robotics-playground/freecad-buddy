"""JSON-RPC wire contract (design §11, AD-2/AD-3). Types only — framing lands in 1.8.

Both the external MCP process and the in-FreeCAD listener import this module; neither
invents framing. Channel error codes and the channel→status mapping note live here.
"""

from __future__ import annotations

from typing import Literal, TypedDict

from freecad_buddy.contracts.envelope import ResultEnvelope

SCHEMA_TAG = "fcb.result-envelope/1"

# Channel-level JSON-RPC error codes (§11). Reserved for the CALL itself — tool-level
# failures always arrive as a `result` ResultEnvelope with a non-OK status.
RPC_ERROR_WORKER_CRASHED = -32000  # listener/marshal crash or dropped connection
RPC_ERROR_NO_HANDSHAKE = -32002  # first frame was not rpc_hello
RPC_ERROR_VERSION_MISMATCH = -32004  # contract_version mismatch

# Channel error code → closed-status mapping (§11, normative). Callers embed
# {status, detail} in `error.data` so one decoder serves both paths.
CHANNEL_ERROR_STATUS: dict[int, str] = {
    RPC_ERROR_WORKER_CRASHED: "WORKER_CRASHED",
    RPC_ERROR_NO_HANDSHAKE: "INVALID_INPUT",
    RPC_ERROR_VERSION_MISMATCH: "INVALID_INPUT",
}


class RpcRequest(TypedDict, total=False):
    jsonrpc: Literal["2.0"]
    id: int
    method: str
    params: dict


class RpcSuccess(TypedDict, total=False):
    jsonrpc: Literal["2.0"]
    id: int
    result: ResultEnvelope


class RpcErrorData(TypedDict, total=False):
    status: str
    detail: dict


class RpcError(TypedDict, total=False):
    code: int
    message: str
    data: RpcErrorData


class RpcErrorFrame(TypedDict, total=False):
    jsonrpc: Literal["2.0"]
    id: int
    error: RpcError


class RpcHelloParams(TypedDict, total=False):
    contract_version: str
    client: str
    token: str


class RpcHelloRequest(TypedDict, total=False):
    jsonrpc: Literal["2.0"]
    id: int
    method: Literal["rpc_hello"]
    params: RpcHelloParams


class RpcHelloResult(TypedDict, total=False):
    contract_version: str
    freecad_version: str
    capabilities: dict


class RpcHelloResponse(TypedDict, total=False):
    jsonrpc: Literal["2.0"]
    id: int
    result: RpcHelloResult
