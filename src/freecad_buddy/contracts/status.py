"""Status vocabulary (design §3). The single closed status/verdict/state set (AD-17).

This is the ONLY module allowed to define a ``Literal`` status/verdict/state type.
Every other wire type imports ``TerminalStatus``/``JobState`` from here.
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
