"""Driving-parameter facade contract, and the editability verdict the G3.3 test produces.

A part's driving dimensions live on one holder object named by ``PARAMETER_OBJECT_NAME``, backed
by an ``App::VarSet`` or a ``Spreadsheet::Sheet`` behind one surface (decision 004). The backend
is chosen by capability probe, never by version string (AD-11), and the choice is reported so a
silent switch between CI legs is visible rather than invisible.

The editability types carry the two-part verdict decision 018 defines: a parameter change passes
only when the document recomputes clean **and** the changed dimension actually moved. A parameter
nothing references recomputes perfectly cleanly forever, so a verdict read from the recompute
alone would score a blob with variables as a parametric part.

Stdlib only; no FreeCAD import.
"""

from __future__ import annotations

from typing import Literal, TypedDict

# The object every part exposes its driving parameters on. This name is the contract between the
# facade that writes it (story 4.6) and ``usecases/techdraw.py``, which sources its judge callouts
# from it (story 4.3) — the two must agree or the drawing silently carries no dimensions.
PARAMETER_OBJECT_NAME = "Parameters"

# The property group driving parameters land in on a VarSet holder. A reader identifies parameters
# by excluding the base properties rather than by this group, so a holder grouped differently is
# still read; the group is what makes the set legible in the FreeCAD property editor.
PARAMETER_GROUP = "Driving"

ParameterBackend = Literal["varset", "spreadsheet"]


class DrivingParameter(TypedDict, total=False):
    """One named driving dimension, as the facade reports it.

    ``name`` is intent-bearing by construction — the facade refuses ``d1``-shaped names — because
    a name that describes the value's role is what separates a parametric model from a blob
    carrying variables.
    """

    name: str  # required
    value: float  # required
    unit: Literal["mm"]  # required


class ParameterSurface(TypedDict, total=False):
    """Every driving parameter a document exposes, plus which backend is holding them.

    ``backend`` is the probe result, not a request: a caller that asked for a VarSet on a build
    without one reads ``spreadsheet`` here.
    """

    schema: Literal["fcb.parameter-surface/1"]  # required
    backend: ParameterBackend  # required
    holder: str  # required; the holder object's immutable Name
    parameters: list[DrivingParameter]  # required


# Why a change failed, when it did. ``recompute_error`` means the document did not come back
# clean; ``ignored`` means it did and the dimension did not move, which is the case that matters:
# the parameter drives nothing, and only measuring the geometry can tell the two apart.
EditabilityFailure = Literal["recompute_error", "ignored", "invalid_solid", "no_parameter"]


class EditabilityResult(TypedDict, total=False):
    """The verdict of one driving-parameter change on one part (decision 018).

    ``editable`` is the conjunction of all three measured legs, never any one of them:
    ``recompute_clean`` ∧ ``valid_solid`` ∧ ``dimension_moved``. ``measured_before`` and
    ``measured_after`` are the geometric measurement the movement leg reads — the part's own
    extent along the changed parameter's axis, not the property read back, because a property
    reads back whatever was written whether or not any feature consumed it.
    """

    schema: Literal["fcb.editability-result/1"]  # required
    part: str  # required
    parameter: str  # required
    value_before: float  # required
    value_after: float  # required
    recompute_clean: bool  # required
    valid_solid: bool  # required
    dimension_moved: bool  # required
    measured_before: float | None  # required; None ⇔ the part could not be measured
    measured_after: float | None  # required
    editable: bool  # required
    failure: EditabilityFailure | None  # required; None ⇔ editable
    detail: str | None  # required


__all__ = [
    "PARAMETER_GROUP",
    "PARAMETER_OBJECT_NAME",
    "DrivingParameter",
    "EditabilityFailure",
    "EditabilityResult",
    "ParameterBackend",
    "ParameterSurface",
]
