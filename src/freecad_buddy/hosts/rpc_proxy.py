"""Proxy registry shared by the hosts that reach FreeCAD over RPC.

The GUI-external server and the headless front both serve the catalog's tool surface from a
process without FreeCAD and forward each call to a listener. This module holds no transport, so
the stdio front does not load the HTTP server stack.
"""

from __future__ import annotations

import threading

from freecad_buddy.adapters import export_oracle, export_verdict
from freecad_buddy.adapters.rpc_client import RpcClient
from freecad_buddy.adapters.rpc_dispatch import MethodRegistry, RpcMethod
from freecad_buddy.contracts import DEFAULT_DISPLAY_DECIMALS
from freecad_buddy.hosts.tool_catalog import SCRIPT_EXEC_SPEC, tool_specs
from freecad_buddy.usecases.capabilities import Capabilities, exec_registered

# Mesh verifiers whose oracle legs (trimesh/lib3mf) must run in this external process, never in
# FreeCAD (AD-9/AD-12). The proxy RPCs only the FreeCAD self-read leg and assembles locally.
_MESH_VERIFY_SELF_READ = {
    "verify_export_stl": "export_self_read_stl",
    "verify_export_3mf": "export_self_read_3mf",
}


def _mesh_verify_proxy_handler(client: RpcClient, lock, tool_name: str):
    """Handler for a mesh verifier: RPC the FreeCAD self-read leg, run oracles here, assemble.

    This process has no FreeCAD, so the display precision comes from the self-read envelope.
    """
    fmt = "stl" if tool_name.endswith("stl") else "3mf"
    self_read_method = _MESH_VERIFY_SELF_READ[tool_name]

    def handler(**params):
        with lock:
            self_read = client.call(self_read_method, params)
        if self_read.get("status") != "OK":
            return self_read
        facts = self_read["structured_content"]
        source = facts["source"]
        band = facts["volume_band"]
        path = facts["path"]
        decimals = self_read.get("display_decimals", DEFAULT_DISPLAY_DECIMALS)
        if fmt == "stl":
            oracle_legs = [
                export_oracle.safe_oracle(
                    "trimesh_stl",
                    lambda: export_oracle.stl_oracle(path, source["volume"], band, decimals),
                ),
                export_oracle.safe_oracle(
                    "stdlib_stl", lambda: export_oracle.StdlibStlOracle().check(path)
                ),
            ]
        else:
            oracle_legs = [
                export_oracle.safe_oracle(
                    "lib3mf",
                    lambda: export_oracle.mesh3mf_oracle(
                        path, source["is_mm"], source["volume"], band, decimals
                    ),
                ),
            ]
        envelope = export_verdict.assemble_export_verdict(oracle_legs, facts, facts["banner"])
        envelope["display_decimals"] = decimals
        return envelope

    return handler


def call_budgets() -> dict[str, float]:
    """The ``timeout_s`` of each RPC method the proxy calls, by method name.

    A mesh verifier's self-read leg gets the budget of its verify tool.
    """
    budgets = {spec.name: spec.timeout_s for spec in (*tool_specs(), SCRIPT_EXEC_SPEC)}
    for tool_name, self_read_method in _MESH_VERIFY_SELF_READ.items():
        budgets[self_read_method] = budgets[tool_name]
    return budgets


def build_proxy_registry(client: RpcClient, caps: Capabilities) -> MethodRegistry:
    """Build a registry whose handlers forward each call to the listener via ``client``.

    Most tools forward wholesale; the mesh verifiers run their third-party oracle legs in this
    process and RPC only the FreeCAD self-read leg (AD-9). ``RpcClient.call`` never raises, so
    every proxy handler returns a wire envelope directly. A single lock serializes the shared
    client.
    """
    lock = threading.Lock()
    methods = MethodRegistry()

    def make(name):
        def handler(**params):
            with lock:
                return client.call(name, params)

        return handler

    specs = list(tool_specs())
    if exec_registered(caps):
        specs.append(SCRIPT_EXEC_SPEC)

    for spec in specs:
        if spec.name in _MESH_VERIFY_SELF_READ:
            handler = _mesh_verify_proxy_handler(client, lock, spec.name)
        else:
            handler = make(spec.name)
        methods.register(
            RpcMethod(
                name=spec.name,
                handler=handler,
                input_schema=spec.input_schema,
                description=spec.description,
                timeout_s=spec.timeout_s,
                mutating=spec.mutating,
                audit_event=spec.audit_event,
                structured_output=spec.structured_output,
            )
        )
    return methods
