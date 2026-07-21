"""The closed set of terminal status/verdict/state values shared across the contracts.

Defines the ``Literal`` status/verdict/state types; every other wire type imports
``TerminalStatus``/``JobState`` from here.
"""

from __future__ import annotations

from typing import Literal, TypedDict

TerminalStatus = Literal[
    "OK",
    "SPEC_FAILED",
    "RECOMPUTE_ERROR",
    "TIMEOUT",
    "OOM_KILLED",
    "WORKER_CRASHED",
    "INVALID_INPUT",
]

JobState = Literal["QUEUED", "RUNNING"] | TerminalStatus


class ErrorDetail(TypedDict, total=False):
    code: str
    message: str  # required
    objects: list[str]
    constraint_ids: list[dict]
    data: dict
