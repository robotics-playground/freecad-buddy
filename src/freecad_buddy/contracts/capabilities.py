"""Capability-banner payload returned by ``query_capabilities``."""

from __future__ import annotations

from typing import Literal, TypedDict


class CapabilityBanner(TypedDict, total=False):
    freecad_version: str  # required
    element_map_available: bool  # required
    serializer: Literal["exportBinary", "exportBrep"]  # required
    varset_backend: Literal["varset", "spreadsheet"]  # required
    render: Literal["gui_constructed", "offscreen", "none"]  # required
    sketcher_available: bool  # required
    exec_enabled: bool  # required
