"""The G3.3 editability runner: change one driving parameter, prove the part rebuilt AND moved.

Implements decision 018 (``docs/decisions/018-editability-test-definition.md``), which is where
the selection rule, the change magnitude and the pass condition are defined — this module is the
execution of that definition and never a second statement of it.

Two halves, split by where they can run:

- :func:`probe_part` runs **inside FreeCAD**, over one already-built part document. It selects the
  parameter, applies the change through ``usecases.parameters.set_value`` (so the write goes
  through ``run_mutation`` like every other mutation), and measures all three legs.
- :func:`collect_g3_3` is **FreeCAD-free**. It turns a list of probe results into the G3.3
  ``ValidationReport``, reading its bar from the criterion's own ``pass_rule`` in ``gate.yaml``
  rather than restating it.

The split matters: a criterion that recomputed its own bar, or that measured editability from
anything other than the produced geometry, could not fail the way the gate needs it to.
"""

from __future__ import annotations

from benchmarks.harness.g2_collect import rate_bar
from benchmarks.harness.report_build import evidence_report, not_collected_report
from freecad_buddy.contracts import EditabilityResult
from freecad_buddy.contracts.report import require_wilson_ci_for_rates

# Decision 018 §2: the change is +10 % of the current value, floored at an absolute 0.5 mm so the
# step always clears the ±0.05 mm linear band the movement leg is measured against
# (verification-design.md §8). The two move together — loosening the band without raising this
# floor would let a real change disappear into the tolerance and report `ignored`.
CHANGE_FRACTION = 0.10
MIN_CHANGE_MM = 0.5

# The bands the movement leg compares against, from verification-design.md §8: a linear dimension
# at 0.05 mm absolute, a volume at 1 % relative. A part whose extents and volume both sit inside
# these after the change did not move.
_LINEAR_BAND_MM = 0.05
_VOLUME_BAND_REL = 0.01


def change_for(value_before: float) -> float:
    """The value decision 018 changes ``value_before`` to."""
    return value_before + max(CHANGE_FRACTION * abs(value_before), MIN_CHANGE_MM)


def _result(
    part: str,
    parameter: str,
    value_before: float,
    value_after: float,
    recompute_clean: bool,
    valid_solid: bool,
    dimension_moved: bool,
    measured_before,
    measured_after,
    failure,
    detail: str | None,
) -> EditabilityResult:
    return {
        "schema": "fcb.editability-result/1",
        "part": part,
        "parameter": parameter,
        "value_before": value_before,
        "value_after": value_after,
        "recompute_clean": recompute_clean,
        "valid_solid": valid_solid,
        "dimension_moved": dimension_moved,
        "measured_before": measured_before,
        "measured_after": measured_after,
        "editable": recompute_clean and valid_solid and dimension_moved,
        "failure": failure,
        "detail": detail,
    }


def _shape_measure(document: object):
    """The part's geometric signature: ``(volume, x_extent, y_extent, z_extent)``, or ``None``.

    Taken over every shape-bearing object so a multi-solid part is measured whole. ``None`` means
    the document carries no measurable shape at all, which the caller reports rather than reading
    as "unchanged" — an unmeasurable part is not a part that held still.
    """
    volume = 0.0
    box = None
    for obj in sorted(document.Objects, key=lambda o: o.Name):
        shape = getattr(obj, "Shape", None)
        is_null = getattr(shape, "isNull", None)
        if shape is None or (is_null is not None and is_null()):
            continue
        volume += float(getattr(shape, "Volume", 0.0) or 0.0)
        bound = getattr(shape, "BoundBox", None)
        if bound is None:
            continue
        box = bound if box is None else box.united(bound)
    if box is None:
        return None
    return (volume, float(box.XLength), float(box.YLength), float(box.ZLength))


def _moved(before, after) -> bool:
    """Whether the part's geometry changed by more than the measurement bands.

    Either an extent moving past the ±0.05 mm linear band or the volume moving past the 1 %
    relative band counts: a change that grew one dimension and a change that added material are
    both the parameter driving something, and requiring both would report `ignored` for a
    thickness change on a part whose bounding box is fixed by other dimensions.
    """
    if before is None or after is None:
        return False
    volume_band = max(_VOLUME_BAND_REL * abs(before[0]), _LINEAR_BAND_MM)
    if abs(after[0] - before[0]) > volume_band:
        return True
    return any(abs(a - b) > _LINEAR_BAND_MM for b, a in zip(before[1:], after[1:]))


def probe_part(registry, doc: str | None, part: str) -> EditabilityResult:
    """Apply decision 018's parameter change to ``doc`` and measure all three legs.

    ``doc`` must already be a **copy** of the graded part (decision 018 §4): this call mutates the
    document it is handed, and the graded artifact is still read by G3.2.

    :param registry: the ``DocumentRegistry`` holding the copy.
    :param doc: the copy's handle.
    :param part: the part id the result is recorded under.
    """
    from freecad_buddy.usecases import parameters, verify

    surface = parameters.list_parameters(registry, doc)
    declared = surface["parameters"]
    if not declared:
        return _result(
            part,
            "",
            0.0,
            0.0,
            False,
            False,
            False,
            None,
            None,
            "no_parameter",
            "the part exposes no driving parameter, so it is not editable (decision 018 §1)",
        )

    # Decision 018 §1: the first parameter in surface order, never a per-part choice.
    selected = declared[0]
    name = selected["name"]
    value_before = float(selected["value"])
    value_after = change_for(value_before)

    before = registry.with_document(doc, lambda _handle, document: _shape_measure(document))

    envelope = parameters.set_value(registry, doc=doc, name=name, value=value_after, unit="mm")
    if envelope.get("status") != "OK":
        detail = (envelope.get("detail") or {}).get("message") or envelope.get("status")
        return _result(
            part,
            name,
            value_before,
            value_after,
            False,
            False,
            False,
            before,
            None,
            "recompute_error",
            f"the change to {value_after} was rejected and rolled back: {detail}",
        )

    recompute = verify.verify_recompute(registry, doc=doc)
    recompute_clean = recompute.get("status") == "OK"

    after = registry.with_document(doc, lambda _handle, document: _shape_measure(document))
    valid_solid, solid_detail = _valid_solid(registry, doc)
    dimension_moved = _moved(before, after)

    failure = None
    detail = None
    if not recompute_clean:
        failure = "recompute_error"
        detail = (recompute.get("detail") or {}).get("message") or (
            "the recompute left an object in an error state"
        )
    elif not valid_solid:
        failure = "invalid_solid"
        detail = f"the value {value_after} left the part an invalid solid: {solid_detail}"
    elif not dimension_moved:
        failure = "ignored"
        detail = (
            f"{name} moved from {value_before} to {value_after} and the geometry did not change, "
            "so the parameter drives nothing (decision 018 §3)"
        )

    return _result(
        part,
        name,
        value_before,
        value_after,
        recompute_clean,
        valid_solid,
        dimension_moved,
        before,
        after,
        failure,
        detail,
    )


def _valid_solid(registry, doc: str | None) -> tuple[bool, str]:
    """Whether every shape-bearing object in ``doc`` still grades as a valid solid.

    Read through ``verify_shape``, the same deterministic gate ``post_verify`` uses, so the
    editability verdict and the mutation protocol cannot disagree about what a valid solid is.
    """
    from freecad_buddy.usecases import verify

    names = registry.with_document(doc, lambda _handle, document: _shape_bearing(document))
    if not names:
        return False, "the part carries no shape to grade"
    for name in names:
        envelope = verify.verify_shape(registry, doc=doc, object=name)
        if envelope.get("status") != "OK":
            message = (envelope.get("detail") or {}).get("message") or envelope.get("status")
            return False, f"{name}: {message}"
    return True, ""


def _shape_bearing(document: object) -> list[str]:
    """The names of every object in ``document`` carrying a non-null shape."""
    names = []
    for obj in sorted(document.Objects, key=lambda o: o.Name):
        shape = getattr(obj, "Shape", None)
        is_null = getattr(shape, "isNull", None)
        if shape is not None and not (is_null is not None and is_null()):
            names.append(obj.Name)
    return names


def collect_g3_3(criterion: dict, results: list) -> dict:
    """Build the G3.3 ``ValidationReport`` from the parts a run probed.

    The bar comes from ``criterion["pass_rule"]`` (">=90% recompute without errors"), never from a
    constant here, so editing the gate changes what decides the criterion.

    The denominator is every passing part handed in, including parts with no parameter
    (decision 018 §1) — a criterion that dropped those would let the rate be raised by shipping
    parts with no driving dimensions at all.
    """
    if not results:
        return not_collected_report(
            "G3.3",
            "no part was probed: editability changes one driving parameter per part that PASSED "
            "G3.1, and no passing part was produced to change",
        )
    bar = rate_bar(criterion.get("pass_rule") or "")
    if bar is None:
        return not_collected_report(
            "G3.3", f"G3.3 declares no pass rate: {criterion.get('pass_rule')!r}"
        )

    editable = [r for r in results if r.get("editable")]
    rate = len(editable) / len(results)
    failures = {}
    for result in results:
        cause = result.get("failure")
        if cause:
            failures.setdefault(cause, []).append(result.get("part"))

    checks = [
        {
            "id": "G3.3.editable",
            "measured": round(rate, 4),
            "measured_kind": "rate",
            "expected": f">={bar}",
            "passed": rate >= bar,
            "detail": {
                "code": "ok" if rate >= bar else "invalid_input.below_pass_rule",
                "message": (
                    f"{len(editable)} of {len(results)} part(s) survived a driving-parameter "
                    f"change with the dimension proven moved (decision 018); failures by cause: "
                    f"{failures or 'none'}"
                ),
            },
        }
    ]
    report = evidence_report("G3.3", checks, banner=_banner(results))
    require_wilson_ci_for_rates(report)
    return report


def _banner(results: list) -> dict:
    """The report banner, carrying the Wilson interval the rate check needs and the backend.

    The backend travels on the banner because the same part must yield the same verdict on both
    CI legs, and a rate measured on two backends is not one number — a reader has to be able to
    see which one produced it without re-probing.
    """
    from freecad_buddy.usecases.stats import wilson_ci

    editable = sum(1 for r in results if r.get("editable"))
    banner = {
        "freecad_version": "headless",
        "element_map_version": None,
        "wilson_ci": wilson_ci(editable, len(results)),
    }
    try:
        from freecad_buddy.usecases import shim

        banner["varset_backend"] = shim.varset_backend()
    except Exception:  # noqa: BLE001 - outside FreeCAD the backend is unknown, never assumed
        banner["varset_backend"] = None
    return banner
