"""Document handle and sub-element selector types.

Every tool call carries an explicit ``DocHandle``; ``ActiveDocument`` is never an
implicit target. Selectors are a tagged union: geometric query or TNP mapped name.
"""

from __future__ import annotations

from typing import Literal, TypedDict


class DocHandle(TypedDict, total=False):
    handle: str  # required
    name: str
    transient: bool


class GeometricSelector(TypedDict, total=False):
    kind: Literal["geometric"]  # required
    object: str  # required
    element_type: Literal["face", "edge", "vertex"]
    query: dict
    expect: Literal["one", "many"]


class MappedNameSelector(TypedDict, total=False):
    kind: Literal["mapped_name"]  # required
    object: str  # required
    mapped_name: str  # required
    element_map_version: int  # required


Selector = GeometricSelector | MappedNameSelector
