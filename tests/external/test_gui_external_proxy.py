"""GUI proxy display precision: the proxy has no FreeCAD, so it keeps the value FreeCAD sent."""

from __future__ import annotations

from freecad_buddy.adapters import export_oracle, export_verdict
from freecad_buddy.adapters.mcp_server import Capabilities, _to_call_result
from freecad_buddy.hosts.gui_external.entry import build_proxy_registry
from freecad_buddy.usecases import shim


class _FakeClient:
    """Answers every RPC with the self-read envelope the FreeCAD listener would send."""

    def __init__(self, envelope: dict) -> None:
        self.envelope = envelope

    def call(self, method: str, params: dict | None = None) -> dict:
        return dict(self.envelope)


def _self_read_envelope(decimals: int) -> dict:
    return {
        "schema": "fcb.result-envelope/1",
        "status": "OK",
        "detail": None,
        "structured_content": {
            "source": {"volume": 1000.0, "is_mm": True},
            "volume_band": 0.5,
            "path": "part.stl",
            "banner": {},
        },
        "text": "",
        "display_decimals": decimals,
    }


def test_should_run_the_oracle_and_round_at_freecad_decimals_when_a_proxy_verifies_a_mesh(
    monkeypatch,
):
    # Arrange
    seen = {}

    def stl_oracle(path, expected_volume, volume_band, decimals):
        seen["decimals"] = decimals
        return {"oracle": "trimesh_stl", "checks": [], "ok": True}

    monkeypatch.setattr(shim, "display_decimals", lambda: 2)
    monkeypatch.setattr(export_oracle, "stl_oracle", stl_oracle)
    monkeypatch.setattr(
        export_oracle.StdlibStlOracle,
        "check",
        lambda _self, _path: {"oracle": "stdlib_stl", "checks": [], "ok": True},
    )
    monkeypatch.setattr(
        export_verdict,
        "assemble_export_verdict",
        lambda _legs, _facts, _banner: {
            "schema": "fcb.result-envelope/1",
            "status": "OK",
            "detail": None,
            "structured_content": {"measured": 999.123456},
            "text": "",
        },
    )
    registry = build_proxy_registry(
        _FakeClient(_self_read_envelope(4)), Capabilities(allow_exec=False)
    )

    # Act
    result = _to_call_result(registry.dispatch("verify_export_stl", {"export_id": "e1"}))

    # Assert
    assert seen["decimals"] == 4
    assert result.structuredContent["structured_content"] == {"measured": 999.1235}
