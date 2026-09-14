"""The driving-dimension facade: one named, intent-bearing parameter surface per part.

A part's driving dimensions live on a single holder object named
``contracts.parameters.PARAMETER_OBJECT_NAME``, backed by an ``App::VarSet`` or a
``Spreadsheet::Sheet`` behind one surface. The backend is chosen by ``shim.varset_probe`` — a
capability probe, never a version string (AD-11) — and the choice travels on every report banner
so a leg that silently fell back is visible in the evidence.

**A declared parameter DRIVES something.** :func:`declare` binds each driven feature property to
the parameter with ``setExpression``, which is what makes the property read-only in FreeCAD and
so gives the dimension exactly one owner. A parameter that drove nothing would recompute
perfectly cleanly forever while the part it claims to parameterise ignored it — the failure
decision 018's editability test exists to catch, and one the facade refuses to create in the
first place.

**Names are intent-bearing.** ``plate_thickness``, never ``d1`` or ``Param003``.
:func:`declare` refuses the latter shapes rather than accepting them and leaving the judgement to
a reader of the finished part.

Every write goes through ``transaction.run_mutation`` and the document it returns is rebound
(DW-71). Stdlib + FreeCAD App modules only.
"""

from __future__ import annotations

import re
from typing import Callable

from freecad_buddy.contracts import (
    PARAMETER_GROUP,
    PARAMETER_OBJECT_NAME,
    DrivingParameter,
    ParameterBackend,
    ParameterSurface,
    ResultEnvelope,
)
from freecad_buddy.usecases import shim, transaction
from freecad_buddy.usecases.documents import DocumentRegistry, ValidationError

_VARSET_TYPE = "App::VarSet"
_SPREADSHEET_TYPE = "Spreadsheet::Sheet"

# The property type a driving dimension is declared as. A length carries its unit, so a value read
# back is a Quantity in millimetres rather than a bare float that could mean anything.
_LENGTH_PROPERTY = "App::PropertyLength"

_LENGTH_UNITS = frozenset({"mm"})

# FreeCAD rewrites any character outside this set when it names a property, so a name failing the
# pattern would silently become a different parameter than the caller declared.
_PARAMETER_NAME = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")

# The base properties every FreeCAD object carries. A parameter is identified by exclusion of
# these rather than by its property group, so a holder whose parameters were grouped differently
# is still read whole. ``usecases/techdraw.py`` reads the same surface by the same rule; the two
# must stay in step or a drawing silently loses callouts.
_BASE_PROPERTIES = frozenset({"ExpressionEngine", "Label", "Label2", "Visibility"})

# Names that carry no intent: a bare letter-and-digits stub (``d1``, ``p2``) or FreeCAD's own
# auto-generated ``Param003`` shape. Refused at declaration, because a name describing the value's
# role is the difference between a parametric model and a blob carrying variables, and no later
# check can recover an intent the name never stated.
_ANONYMOUS_NAME = re.compile(r"^(?:[A-Za-z]\d*|[Pp]aram\d*|[Vv]ar\d*|[Vv]alue\d*)$")

# A driven property is named ``Feature.Property``: the object's immutable Name, then the property
# the parameter drives on it.
_DRIVEN_PATH = re.compile(r"^([A-Za-z_][A-Za-z0-9_]*)\.([A-Za-z_][A-Za-z0-9_]*)$")


def _holder(document: object) -> object | None:
    """Return the document's parameter holder, or ``None`` when it has none yet."""
    return document.getObject(PARAMETER_OBJECT_NAME)


def _holder_backend(holder: object) -> ParameterBackend:
    """Which backend ``holder`` is: what it IS, never what the probe would choose today.

    A document built on one leg and read on another must report the backend actually holding its
    parameters. Deriving this from the live probe instead would let a VarSet-backed part read as
    ``spreadsheet`` on a build without VarSet, which is the reverse of the truth.
    """
    return "varset" if str(getattr(holder, "TypeId", "")) == _VARSET_TYPE else "spreadsheet"


def _parameter_names(holder: object) -> list[str]:
    """Every driving-parameter property on ``holder``, in the order the build reports them."""
    return [prop for prop in holder.PropertiesList if prop not in _BASE_PROPERTIES]


def _magnitude(raw: object) -> float | None:
    """Return ``raw`` as a millimetre magnitude, or ``None`` when it carries none.

    An ``App::PropertyLength`` reads back as a ``Quantity`` carrying its unit, so the magnitude
    comes from ``.Value`` when present. A bool is rejected explicitly: it is a ``float`` subclass
    in Python and would otherwise be reported as the dimension ``1.0``.
    """
    if isinstance(raw, bool):
        return None
    value = getattr(raw, "Value", raw)
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return None
    return float(value)


def _validate_name(name: object) -> str:
    """Return ``name`` as a legal, intent-bearing parameter name, or raise.

    :raises ValidationError: the name is absent, would be rewritten by FreeCAD, or carries no
        intent.
    """
    if not isinstance(name, str) or not name:
        raise ValidationError("missing required parameter 'name'")
    if not _PARAMETER_NAME.match(name):
        raise ValidationError(
            f"parameter name must be a Python identifier, so FreeCAD stores it unchanged: {name!r}"
        )
    if _ANONYMOUS_NAME.match(name):
        raise ValidationError(
            f"parameter name carries no intent: {name!r}. A driving dimension is named for its "
            "role, such as 'plate_thickness' or 'bore_diameter'"
        )
    return name


def _validate_value(value: object, unit: object) -> float:
    """Return the millimetre magnitude ``value`` states, or raise.

    :raises ValidationError: the unit is not ``mm``, or the value is not a finite number.
    """
    if unit not in _LENGTH_UNITS:
        raise ValidationError(f"driving dimensions are millimetre lengths; got unit {unit!r}")
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValidationError(f"parameter value must be a number; got {value!r}")
    return float(value)


def _validate_drives(document: object, drives: object) -> list[tuple[object, str]]:
    """Resolve every ``Feature.Property`` path in ``drives`` against ``document``.

    :raises ValidationError: ``drives`` is empty, malformed, or names an object or property that
        does not exist. Empty is refused deliberately: a parameter driving nothing is the exact
        blob-with-variables case the facade exists to prevent, and declaring one would put a
        callout on the judge's drawing for a dimension the part does not have.
    """
    if not isinstance(drives, (list, tuple)) or not drives:
        raise ValidationError(
            "a driving parameter must drive at least one feature property, named as "
            "'Feature.Property'; a parameter that drives nothing is not a driving dimension"
        )
    resolved = []
    for path in drives:
        match = _DRIVEN_PATH.match(path) if isinstance(path, str) else None
        if match is None:
            raise ValidationError(f"driven property must be named 'Feature.Property'; got {path!r}")
        owner_name, prop = match.groups()
        owner = document.getObject(owner_name)
        if owner is None:
            raise ValidationError(f"unknown object in drives: {owner_name}")
        if prop not in owner.PropertiesList:
            raise ValidationError(f"{owner_name} has no property {prop}")
        resolved.append((owner, prop))
    return resolved


def _create_holder(document: object) -> object:
    """Create the parameter holder on the probed backend and return it.

    The VarSet path is the measured one on both supported legs. The Spreadsheet path exists
    because decision 004 makes it authoritative wherever VarSet's Python surface is not exposed
    (upstream #12531), and it is unexercised: no environment available to this repository selects
    it, so its behaviour is written from the API contract rather than from a measurement.
    """
    backend = shim.varset_backend()
    type_id = _VARSET_TYPE if backend == "varset" else _SPREADSHEET_TYPE
    holder = document.addObject(type_id, PARAMETER_OBJECT_NAME)
    if holder is None:
        raise ValidationError(f"the running build could not create a {type_id} parameter holder")
    holder.Label = PARAMETER_OBJECT_NAME
    return holder


def _declare_on_holder(holder: object, name: str, value: float) -> None:
    """Add ``name`` to ``holder`` as a millimetre length and write ``value``.

    Both backends expose ``addProperty``: a ``Spreadsheet::Sheet`` is an ordinary
    ``DocumentObject``, so a parameter declared on one is a property exactly as it is on a VarSet.
    Declaring it as a cell instead would give the two backends two different surfaces, which is
    the one thing a facade selected by probe must not do — a downstream reader would have to know
    which leg it was running on.
    """
    if name not in holder.PropertiesList:
        holder.addProperty(_LENGTH_PROPERTY, name, PARAMETER_GROUP, "driving dimension")
    setattr(holder, name, value)


def _bind(driven: list[tuple[object, str]], name: str) -> None:
    """Bind every driven property to the parameter, making the parameter its single owner.

    ``setExpression`` is what enforces the one-owner rule: FreeCAD marks an expression-bound
    property read-only, so the same dimension cannot also be written as a raw feature property.
    """
    expression = f"{PARAMETER_OBJECT_NAME}.{name}"
    for owner, prop in driven:
        owner.setExpression(prop, expression)


def _mutate(
    registry: DocumentRegistry,
    doc: str | None,
    label: str,
    tool: str,
    params: dict,
    op: Callable[[object], list[str]],
    audit_sink: object = None,
    precheck: Callable[[object], None] | None = None,
) -> tuple[ResultEnvelope, object]:
    """Run ``op`` through the mutation bracket and rebind the document it returns.

    The document is resolved once and handed to ``run_mutation``; re-resolving inside would
    re-enter the registry's non-reentrant lock and deadlock. The returned document is rebound on
    every exit path, because the snapshot-restore rollback closes and reopens the document and a
    handle left pointing at the original object would address a closed one (DW-71).
    """
    rebound: list = []

    def call(handle: str, document: object):
        if precheck is not None:
            precheck(document)
        rebound.append(document)
        result = transaction.run_mutation(
            document, handle, label, op, audit_sink=audit_sink, tool=tool, params=params
        )
        rebound.append(result[0])
        return result

    try:
        _, envelope = registry.with_document(doc, call)
    finally:
        if rebound:
            try:
                registry.rebind(doc, rebound[-1])
            except Exception:  # noqa: BLE001 - a failed rebind must not mask the real outcome
                pass
    return envelope, rebound[-1] if rebound else None


def declare(
    registry: DocumentRegistry,
    doc: str | None = None,
    name: str | None = None,
    value: object = None,
    unit: str = "mm",
    drives: list | None = None,
    audit_sink: object = None,
) -> ResultEnvelope:
    """Declare ``name`` as a driving dimension and bind the feature properties it drives.

    Creates the parameter holder on first use, on whichever backend the probe selected. Every
    entry in ``drives`` is bound by expression, so the parameter becomes that property's only
    writer.

    :param name: an intent-bearing identifier such as ``plate_thickness``.
    :param value: the dimension's millimetre magnitude.
    :param unit: the value's unit; ``mm`` is the only one a length accepts.
    :param drives: ``Feature.Property`` paths this parameter drives; at least one.
    :raises ValidationError: the name carries no intent or would be rewritten, the value or unit
        is wrong, or a driven path names an object or property that does not exist.
    """
    parameter = _validate_name(name)
    magnitude = _validate_value(value, unit)

    def precheck(document: object) -> None:
        _validate_drives(document, drives)

    def op(document: object) -> list[str]:
        driven = _validate_drives(document, drives)
        holder = _holder(document) or _create_holder(document)
        _declare_on_holder(holder, parameter, magnitude)
        _bind(driven, parameter)
        return [holder.Name] + sorted({owner.Name for owner, _ in driven})

    params = {"doc": doc, "name": name, "value": value, "unit": unit, "drives": drives}
    envelope, document = _mutate(
        registry,
        doc,
        f"declare parameter {parameter}",
        "parameter_declare",
        params,
        op,
        audit_sink,
        precheck,
    )
    _attach_surface(envelope, document)
    return envelope


def set_value(
    registry: DocumentRegistry,
    doc: str | None = None,
    name: str | None = None,
    value: object = None,
    unit: str = "mm",
    audit_sink: object = None,
) -> ResultEnvelope:
    """Write ``value`` to the already-declared parameter ``name``.

    The write goes through the mutation bracket like every other mutation, so a value that breaks
    the part rolls back with proof rather than leaving a broken document behind.

    :raises ValidationError: the document exposes no parameter surface, the parameter is not
        declared on it, or the value or unit is wrong.
    """
    parameter = _validate_name(name)
    magnitude = _validate_value(value, unit)

    def precheck(document: object) -> None:
        _require_declared(document, parameter)

    def op(document: object) -> list[str]:
        holder = _require_declared(document, parameter)
        setattr(holder, parameter, magnitude)
        return [holder.Name]

    params = {"doc": doc, "name": name, "value": value, "unit": unit}
    envelope, document = _mutate(
        registry,
        doc,
        f"set parameter {parameter}",
        "parameter_set",
        params,
        op,
        audit_sink,
        precheck,
    )
    _attach_surface(envelope, document)
    return envelope


def _require_declared(document: object, parameter: str) -> object:
    """Return the holder carrying ``parameter``, or raise ``ValidationError``."""
    holder = _holder(document)
    if holder is None:
        raise ValidationError(
            f"{document.Name} exposes no driving-parameter surface; declare one before writing it"
        )
    if parameter not in _parameter_names(holder):
        raise ValidationError(f"{document.Name} declares no driving parameter {parameter!r}")
    return holder


def read_surface(document: object) -> ParameterSurface:
    """Return every driving parameter ``document`` exposes, and the backend holding them.

    A document with no holder reports an empty surface on the probed backend rather than raising:
    "this part exposes no driving dimensions" is a measurement the editability test needs, and an
    exception would make it indistinguishable from a document that could not be read.
    """
    holder = _holder(document)
    if holder is None:
        return {
            "schema": "fcb.parameter-surface/1",
            "backend": shim.varset_backend(),
            "holder": PARAMETER_OBJECT_NAME,
            "parameters": [],
        }
    parameters: list[DrivingParameter] = []
    for prop in _parameter_names(holder):
        magnitude = _magnitude(getattr(holder, prop, None))
        if magnitude is not None:
            parameters.append({"name": prop, "value": magnitude, "unit": "mm"})
    return {
        "schema": "fcb.parameter-surface/1",
        "backend": _holder_backend(holder),
        "holder": holder.Name,
        "parameters": parameters,
    }


def list_parameters(registry: DocumentRegistry, doc: str | None = None) -> ParameterSurface:
    """Read the document's parameter surface through the registry. Read-only."""
    return registry.with_document(doc, lambda _handle, document: read_surface(document))


def _attach_surface(envelope: ResultEnvelope, document: object) -> None:
    """Attach the post-mutation parameter surface to ``envelope``'s structured content.

    Read here, inside the window the mutation produced, rather than by a second registry call:
    a concurrent mutation landing in between would leave the reported surface describing a
    document generation the mutation block did not create.
    """
    if document is None:
        return
    content = envelope.get("structured_content")
    if not isinstance(content, dict):
        content = {}
        envelope["structured_content"] = content
    content["parameters"] = read_surface(document)
