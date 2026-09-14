"""``verify_visual``: the conjunctive second leg of done (AD-21, verification-design.md §7a).

A generated part is done iff the geometry assertions PASS **and** an independent vision model
passes it against its spec. This module owns the second half: it assembles the standard visual set
(a 3D iso render, one focus view per spec-named feature, and the dimensioned front/top/right
TechDraw sheet), hands it to an injected ``JudgeClient``, validates the returned verdict before
reading any field of it, and wraps the result as check ``visual.judge`` in a ``ValidationReport``.

**Fail closed, everywhere.** Render unavailable, drawing unavailable, an image below the ≥2048 px
legibility floor, a judge that cannot be reached, a verdict that does not match the schema — each
reports ``visual.unavailable`` and the part is NOT done. There is no default-true path and no
silent pass. The only bypass is an explicit operator waiver, and the waiver is audit-logged with
its stated reason by the caller that granted it (``waiver_record`` builds that record).

**Geometry stays authoritative.** ``geometry_passed`` is an input, not something this module
measures. A caller whose geometry assertions failed gets a skipped report without a judge call:
the verdict is conjunctive, so the judge could not change the outcome, and a judge call on that
iteration would spend one of only three repair iterations for no information.

Stdlib + FreeCAD App API only. The vision client is third-party and arrives injected as a
``JudgeClient``, exactly as the renderer arrives as a ``RenderPort``.
"""

from __future__ import annotations

import os
import struct
import tempfile

from freecad_buddy.contracts import (
    MIN_JUDGE_IMAGE_WIDTH_PX,
    VISUAL_CHECK_ID,
    VISUAL_UNAVAILABLE_CODE,
    Check,
    DrawingSheet,
    FocusSpec,
    JudgeClient,
    JudgeImage,
    JudgeVerdict,
    JudgeView,
    RenderPort,
    ResultEnvelope,
    SceneSpec,
    SvgRasterPort,
    ValidationReport,
    VisualSet,
    derive_verdict,
    massprops_equal,
)
from freecad_buddy.usecases import shim
from freecad_buddy.usecases.documents import DocumentRegistry, ValidationError, temp_dir
from freecad_buddy.usecases.fingerprint import fingerprint
from freecad_buddy.usecases.screenshot import is_default_renderable
from freecad_buddy.usecases.techdraw import techdraw_for_judge

# The iso camera quaternion, taken from the same transcription of FreeCAD's ``Gui/Camera.cpp``
# the user-facing screenshot path uses. Imported by value rather than by reference to
# ``screenshot._CAMERA_QUATS`` because that mapping is private to the user-facing path; the judge's
# gestalt view is fixed at iso and takes no camera option.
_ISO_ORIENTATION = (0.424708, 0.17592, 0.339851, 0.820473)

# The judge's images are square: the sheet's own aspect is carried by the TechDraw path, and the
# 3D views have no preferred aspect. A square render at the floor keeps the shorter axis above the
# floor too, so a part that is long in one direction is not judged from a thin strip.
_JUDGE_RENDER_WIDTH_PX = MIN_JUDGE_IMAGE_WIDTH_PX
_JUDGE_RENDER_HEIGHT_PX = MIN_JUDGE_IMAGE_WIDTH_PX

_TEMP_PREFIX = "FCB_TMP_judge_"

# The 8-byte PNG signature and the fixed layout of the IHDR chunk that must follow it. Width lives
# at byte 16 as a big-endian uint32. Read from the file rather than trusted from the renderer: the
# legibility floor exists to keep callouts readable, and a gate reading a *requested* width would
# pass an image the renderer silently produced smaller.
_PNG_SIGNATURE = b"\x89PNG\r\n\x1a\n"
_PNG_HEADER_BYTES = 24
_PNG_WIDTH_OFFSET = 16


class JudgeUnavailable(RuntimeError):
    """No vision backend answered. Fail-closed: the part is not done.

    Mirrors ``benchmarks/g3/judge.py`` ``JudgeUnavailable`` so a client written against the
    benchmark seam and one written against this ring raise the same class of failure. The two are
    distinct types on purpose — ``benchmarks/`` is outermost tooling and this ring may not import
    it — and ``_judge_verdict`` catches both by name.
    """


class VerdictSchemaError(ValueError):
    """A verdict does not match ``{pass, findings:[{view, observation, severity}]}``.

    A ``ValueError`` rather than a bare ``Exception``: a malformed verdict is bad input from an
    untrusted source, and the dispatch boundary maps it to ``INVALID_INPUT``.
    """


# The severities and views a verdict may carry. Restated from ``contracts/visual.py``'s Literals
# rather than imported from ``benchmarks/g3/judge.py``: this ring may not import benchmark tooling,
# and ``tests/external/test_verify_visual.py`` asserts the two sets are equal so they cannot drift.
_SEVERITIES = frozenset({"blocking", "advisory"})
_VIEWS = frozenset({"iso", "focus", "front", "top", "right"})


def validate_verdict(verdict: object) -> JudgeVerdict:
    """Return ``verdict`` when it matches the judge schema; raise ``VerdictSchemaError`` if not.

    Model output is untrusted. A verdict missing its ``pass`` field, or carrying a finding with no
    view, would be read as a pass by any caller doing ``verdict.get("pass")``, so validation
    happens here — before any field is read — rather than at each call site.

    :param verdict: the mapping a judge backend returned.
    :raises VerdictSchemaError: the verdict is not a mapping, declares no boolean ``pass``, carries
        a ``findings`` value that is not a list, or carries a finding missing a non-empty
        ``view``/``observation``/``severity`` or naming one outside the closed vocabulary.
    """
    if not isinstance(verdict, dict):
        raise VerdictSchemaError(f"verdict must be a mapping, got {type(verdict).__name__}")
    if "pass" not in verdict:
        raise VerdictSchemaError("verdict declares no 'pass'")
    if not isinstance(verdict["pass"], bool):
        raise VerdictSchemaError(f"verdict 'pass' must be a bool, got {verdict['pass']!r}")
    findings = verdict.get("findings")
    if not isinstance(findings, list):
        raise VerdictSchemaError(f"verdict 'findings' must be a list, got {findings!r}")
    for index, finding in enumerate(findings):
        if not isinstance(finding, dict):
            raise VerdictSchemaError(f"findings[{index}] must be a mapping, got {finding!r}")
        for field in ("view", "observation", "severity"):
            value = finding.get(field)
            if not isinstance(value, str) or not value.strip():
                raise VerdictSchemaError(f"findings[{index}] has no non-empty '{field}'")
        if finding["view"] not in _VIEWS:
            raise VerdictSchemaError(
                f"findings[{index}] view {finding['view']!r} is outside {sorted(_VIEWS)}"
            )
        if finding["severity"] not in _SEVERITIES:
            raise VerdictSchemaError(
                f"findings[{index}] severity {finding['severity']!r} is outside "
                f"{sorted(_SEVERITIES)}"
            )
    return verdict  # type: ignore[return-value]


def verify_visual(
    registry: DocumentRegistry,
    render_port: RenderPort,
    raster_port: SvgRasterPort,
    judge_client: JudgeClient,
    spec_text: str,
    checklist: list[str],
    doc: str | None = None,
    geometry_passed: bool = False,
    focus_objects: list[str] | None = None,
    waiver: dict | None = None,
) -> ResultEnvelope:
    """Judge ``doc``'s part against ``spec_text`` and report the verdict as ``visual.judge``.

    Returns an envelope whose structured content is a ``ValidationReport`` carrying exactly one
    ``visual.judge`` check. The check passes only when the geometry leg passed, the full visual set
    was assembled above the legibility floor, the judge answered, the verdict validated, and the
    verdict says ``pass``. Every other outcome fails the check with a ``visual.unavailable`` detail
    code, so the part is not done.

    :param spec_text: the written spec the part is judged against.
    :param checklist: the structured checklist derived from that spec, one requirement per entry.
    :param geometry_passed: whether this iteration's geometry assertions ALL passed. False skips
        the judge call entirely — the verdict is conjunctive, so a judge call could not change the
        outcome, and it would spend one of the ≤3 repair iterations for no information.
    :param focus_objects: the spec-named features to render a focus view of; ``None`` renders none.
    :param waiver: an explicit operator waiver ``{"granted": True, "reason": str}``. A waiver lets
        the part proceed WITHOUT a judge verdict; it is echoed into the report so the caller can
        audit-log it, and it never turns an obtained ``pass: False`` verdict into a pass.
    :raises ValidationError: the handle is unknown, ``checklist`` is empty, or ``waiver`` is
        granted without a stated reason.
    """
    _require_checklist(checklist)
    waiver_block = _validated_waiver(waiver)

    subject = {"geometry_passed": geometry_passed}

    if not geometry_passed:
        # Reported without resolving the handle at all: the judge is not called on an iteration
        # geometry already failed, so nothing about the document is read.
        return _finish(
            _skipped_check(
                "geometry assertions did not all pass on this iteration, so the conjunctive "
                "visual leg could not change the outcome and no judge call was made"
            ),
            subject,
            None,
            waiver_block,
        )

    # The drawing sheet is composed FIRST, through its own registry call. ``with_document`` holds a
    # non-reentrant lock, so the 3D renders below cannot be nested inside a call that itself
    # re-enters the registry; the sheet owns its TempDoc build and its own fingerprint guard.
    sheet = _drawing_sheet(registry, raster_port, doc)

    def run(_handle: str, document: object) -> ResultEnvelope:
        subject["document"] = document.Name
        before = fingerprint(document)
        visual_set = _assemble_visual_set(
            render_port, document, sheet, spec_text, checklist, focus_objects or []
        )
        _assert_unchanged(document, before)

        if not visual_set["complete"]:
            return _finish(
                _unavailable_check(visual_set["reason"] or "the visual set is incomplete"),
                subject,
                visual_set,
                waiver_block,
            )

        return _finish(_judged_check(judge_client, visual_set), subject, visual_set, waiver_block)

    return registry.with_document(doc, run)


def waiver_record(report: ValidationReport) -> dict | None:
    """Build the audit payload for the operator waiver ``report`` carries, or ``None`` if it has
    none.

    Reads the waiver off the report rather than taking it again as an argument: the report is what
    the leg actually produced, and a record built from a separately-passed waiver could describe a
    different one than the report shows. Kept out of the report itself so the caller writes one
    record through the shared ``AuditSink`` rather than this ring growing an audit dependency.

    The reason is always a real sentence: ``_validated_waiver`` refuses a waiver without one before
    it can reach a report.
    """
    subject = report.get("subject") or {}
    waiver = subject.get("waiver")
    if not waiver:
        return None
    return {
        "waived_check": VISUAL_CHECK_ID,
        "document": subject.get("document"),
        "reason": waiver["reason"],
        "granted_by": waiver.get("granted_by"),
    }


# ------------------------------------------------------------------------------------------
# Inputs
# ------------------------------------------------------------------------------------------


def _require_checklist(checklist: list[str]) -> None:
    """Reject an empty or non-textual checklist.

    The checklist is what the judge measures the images against. Judging with none would ask a
    vision model to decide for itself what the part should look like, and its answer would be
    reported with the same weight as one measured against the spec.

    :raises ValidationError: ``checklist`` is not a non-empty list of non-empty strings.
    """
    if not isinstance(checklist, list) or not checklist:
        raise ValidationError(
            "checklist must be a non-empty list: the judge measures the images against it, and "
            "judging with no checklist reports an unanchored opinion as a verdict"
        )
    for index, item in enumerate(checklist):
        if not isinstance(item, str) or not item.strip():
            raise ValidationError(f"checklist[{index}] must be a non-empty string: {item!r}")


def _validated_waiver(waiver: dict | None) -> dict | None:
    """Return the normalized waiver block, or ``None`` when no waiver was granted.

    :raises ValidationError: a waiver is granted without a non-empty stated reason. An unreasoned
        waiver is exactly the silent bypass AD-21 forbids — it would look identical in the audit
        log to one an operator thought about.
    """
    if waiver is None:
        return None
    if not isinstance(waiver, dict):
        raise ValidationError(f"waiver must be a mapping: {waiver!r}")
    if not waiver.get("granted"):
        return None
    reason = waiver.get("reason")
    if not isinstance(reason, str) or not reason.strip():
        raise ValidationError(
            "an operator waiver must carry a stated reason: a waiver with none is "
            "indistinguishable in the audit log from one nobody thought about"
        )
    return {"granted": True, "reason": reason, "granted_by": waiver.get("granted_by")}


# ------------------------------------------------------------------------------------------
# The standard visual set
# ------------------------------------------------------------------------------------------


def _assemble_visual_set(
    render_port: RenderPort,
    document: object,
    sheet: DrawingSheet,
    spec_text: str,
    checklist: list[str],
    focus_objects: list[str],
) -> VisualSet:
    """Render the iso and focus views, add the composed sheet, and gate every image's width.

    Returns an incomplete set — rather than raising — whenever a leg is a missing *capability*:
    no renderer, no TechDraw, no rasterizer. Unavailability is a reported state, and the caller's
    fail-closed rule turns it into ``visual.unavailable``. A leg that is present but produced an
    illegible image is also incomplete, for the same reason: judging it would fail a correct part
    for a reason no assertion reports.
    """
    if not sheet.get("available", False):
        return _incomplete_set(spec_text, checklist, f"no judge drawing: {sheet.get('reason')}", [])

    available, reason = render_port.available()
    if not available:
        return _incomplete_set(spec_text, checklist, f"no render capability: {reason}", [])

    images: list[JudgeImage] = []
    try:
        images.append(_render_view(render_port, document, "iso", None))
        for target in focus_objects:
            images.append(_render_view(render_port, document, "focus", target))
    except _RenderFailed as exc:
        _discard(images)
        return _incomplete_set(spec_text, checklist, str(exc), [])

    images.extend(_sheet_images(sheet))

    illegible = _below_floor(images)
    if illegible:
        _discard(images)
        return _incomplete_set(
            spec_text,
            checklist,
            f"image(s) below the {MIN_JUDGE_IMAGE_WIDTH_PX} px legibility floor: {illegible}",
            [],
        )

    return {
        "schema": "fcb.visual-set/1",
        "complete": True,
        "reason": None,
        "images": images,
        "spec_text": spec_text,
        "checklist": list(checklist),
    }


class _RenderFailed(RuntimeError):
    """One leg of the visual set could not be produced; the set is reported incomplete."""


def _render_view(
    render_port: RenderPort, document: object, view: JudgeView, focus_object: str | None
) -> JudgeImage:
    """Render one 3D view at the judge's floor width and return it with its measured width.

    The width is the judge floor, not the user-facing render cap: AD-21 puts judge images outside
    the ``usecases/screenshot.py`` budget because they travel straight to the judge API rather than
    through client context. This path therefore builds its own ``SceneSpec`` rather than calling
    ``query_screenshot``, whose ``_clamp_dim`` would floor the request back down to 1920 px and
    hand the judge an image below the legibility floor.

    :raises _RenderFailed: the scene held no drawable geometry, the focus target is not in it, or
        the port wrote no image.
    """
    objects = [obj.Name for obj in document.Objects if is_default_renderable(obj)]
    if not objects:
        raise _RenderFailed(f"the {view} view has no drawable geometry to render")
    if focus_object is not None and focus_object not in objects:
        raise _RenderFailed(
            f"focus target {focus_object!r} is not in the rendered scene ({objects})"
        )

    scene = SceneSpec(
        objects=objects,
        orientation=_ISO_ORIENTATION,
        width=_JUDGE_RENDER_WIDTH_PX,
        height=_JUDGE_RENDER_HEIGHT_PX,
        focus=FocusSpec(object=focus_object) if focus_object is not None else None,
    )
    fd, path = tempfile.mkstemp(prefix=_TEMP_PREFIX, suffix=".png", dir=temp_dir())
    os.close(fd)
    try:
        result = render_port.render(document, scene, path)
        if result.empty_scene:
            raise _RenderFailed(f"the {view} view rendered an empty scene")
        width = _png_width(path)
    except BaseException:
        _remove(path)
        raise
    return {
        "view": view,
        "path": path,
        "width_px": width,
        "media_type": "image/png",
    }


def _drawing_sheet(
    registry: DocumentRegistry, raster_port: SvgRasterPort, doc: str | None
) -> DrawingSheet:
    """Compose the dimensioned front/top/right sheet for the document ``doc`` names.

    Calls ``techdraw_for_judge`` rather than re-implementing the TempDoc build: the sheet's
    parameter-sourced callouts are the only check that can catch a spec-to-assertion
    mistranslation, and a second composer would drift from the one story 4.3 fault-tested.

    A part that exposes no driving parameters, or carries no shape to draw, raises inside the
    drawing. That is a real missing input, but it must not fail the whole call: the visual leg's
    contract is that an unbuildable drawing leaves the part NOT done under ``visual.unavailable``,
    and an exception here would instead report a broken tool call. Those failures are therefore
    converted to an unavailable sheet carrying the raised message as its reason.

    The handle is resolved first, so an unknown or stale handle still raises ``ValidationError`` —
    that is a caller error, not a missing capability, and must not be reported as an unjudgeable
    part.
    """
    registry.with_document(doc, _resolved)
    try:
        envelope = techdraw_for_judge(
            registry, raster_port, doc=doc, page_width_px=MIN_JUDGE_IMAGE_WIDTH_PX
        )
    except (ValidationError, RuntimeError) as exc:
        return _unavailable_sheet(f"the judge drawing could not be built: {exc}")
    return envelope["structured_content"]  # type: ignore[return-value]


def _resolved(handle: str, document: object) -> str:
    """Registry callback that only proves the handle resolves; returns the handle unchanged."""
    return handle


def _unavailable_sheet(reason: str) -> DrawingSheet:
    """A drawing sheet reporting that nothing was drawn, and why."""
    return {
        "schema": "fcb.drawing-sheet/1",
        "available": False,
        "reason": reason,
        "svg_path": None,
        "png_path": None,
        "page_width_px": 0,
        "page_height_px": 0,
        "views": [],
        "callouts": [],
    }


def _sheet_images(sheet: DrawingSheet) -> list[JudgeImage]:
    """The drawing sheet as one judge image per projection it carries.

    The three views share one composed PNG — the sheet is a single canvas — so each entry points at
    the same file under its own view name. That spelling is what lets a finding attribute itself to
    ``front`` rather than to an unnamed sheet, which is what the repair loop reads.
    """
    return [
        {
            "view": view,  # type: ignore[typeddict-item]
            "path": sheet["png_path"],
            "width_px": sheet["page_width_px"],
            "media_type": "image/png",
        }
        for view in sheet.get("views") or []
    ]


def _below_floor(images: list[JudgeImage]) -> list[str]:
    """The view names whose image is narrower than the legibility floor."""
    return [image["view"] for image in images if image["width_px"] < MIN_JUDGE_IMAGE_WIDTH_PX]


def _png_width(path: str) -> int:
    """Return the real pixel width of the PNG at ``path``.

    Read from the IHDR chunk rather than taken from the render request: the floor exists to keep
    the image legible, so the gate must measure what was produced. A file that is not a PNG, or is
    truncated before its header, reports width 0 and is therefore refused by the floor gate rather
    than raising — an unreadable image is exactly as unjudgeable as a small one.
    """
    try:
        with open(path, "rb") as handle:
            header = handle.read(_PNG_HEADER_BYTES)
    except OSError:
        return 0
    if len(header) < _PNG_HEADER_BYTES or not header.startswith(_PNG_SIGNATURE):
        return 0
    return struct.unpack(">I", header[_PNG_WIDTH_OFFSET : _PNG_WIDTH_OFFSET + 4])[0]


def _incomplete_set(
    spec_text: str, checklist: list[str], reason: str, images: list[JudgeImage]
) -> VisualSet:
    """The no-judge visual set: what is missing, named, and never handed to a judge."""
    return {
        "schema": "fcb.visual-set/1",
        "complete": False,
        "reason": reason,
        "images": images,
        "spec_text": spec_text,
        "checklist": list(checklist),
    }


def _discard(images: list[JudgeImage]) -> None:
    """Remove the images of a set that will never be judged.

    A set reported incomplete is not sent anywhere, so its files have no reader; leaving them
    behind outlives the session that could explain them.
    """
    for image in images:
        _remove(image.get("path"))


def _remove(path: str | None) -> None:
    """Remove ``path`` if present, swallowing an already-gone file."""
    if path is None:
        return
    try:
        os.remove(path)
    except OSError:
        pass


def _assert_unchanged(document: object, before: dict) -> None:
    """Assert the judged document is geometrically identical to ``before``.

    Compares mass properties rather than the raw digest for the reason the screenshot and drawing
    paths do: OCCT re-lays-out a shape's serialization the first time something copies it, so the
    bytes can change while the geometry does not. A real mutation still moves the mass properties.

    :raises ValidationError: assembling the visual set changed the part.
    """
    if not massprops_equal(before, fingerprint(document)):
        raise ValidationError(
            "verify_visual mutated the part document (geometry changed); the visual leg is a "
            "read-only measurement and a judged part must be the part the geometry leg measured"
        )


# ------------------------------------------------------------------------------------------
# The judge call and the report
# ------------------------------------------------------------------------------------------


def _judged_check(judge_client: JudgeClient, visual_set: VisualSet) -> Check:
    """Call the judge, validate its verdict, and build the ``visual.judge`` check.

    Every failure mode collapses to the same outcome — the check fails — but each names itself in
    the detail so the repair loop can tell an unreachable judge from a part the judge rejected. A
    malformed verdict is reported as malformed rather than as a fail: the two demand different
    responses, and treating a broken client as a wrong part would send the loop rebuilding
    correct geometry.
    """
    available, reason = judge_client.available()
    if not available:
        return _unavailable_check(f"the judge is unavailable: {reason}")

    try:
        raw = judge_client.judge(visual_set)
    except JudgeUnavailable as exc:
        return _unavailable_check(f"the judge did not answer: {exc}")
    except Exception as exc:  # noqa: BLE001 - any client failure is fail-closed, never a pass
        return _unavailable_check(f"the judge call raised {exc.__class__.__name__}: {exc}")

    verdict = validate_verdict(raw)
    return _verdict_check(verdict)


def _verdict_check(verdict: JudgeVerdict) -> Check:
    """Wrap a validated verdict as the ``visual.judge`` check.

    ``measured`` carries the findings verbatim rather than a count: the repair loop reads them as
    its diagnostics alongside the geometry discrepancy vector, and a count would tell it something
    is wrong without telling it where to look.
    """
    findings = verdict.get("findings") or []
    passed = bool(verdict["pass"])
    check: Check = {
        "id": VISUAL_CHECK_ID,
        "measured": findings,
        "measured_kind": "text",
        "expected": True,
        "tolerance": None,
        "passed": passed,
        "detail": None,
    }
    if not passed:
        blocking = [f for f in findings if f.get("severity") == "blocking"]
        check["detail"] = {
            "code": "visual.judge_failed",
            "message": _findings_message(blocking or findings),
            "objects": [],
        }
    return check


def _findings_message(findings: list) -> str:
    """Render findings as one line: each view and what was observed there."""
    if not findings:
        return "the judge failed the part but reported no finding"
    return "; ".join(f"{f.get('view')}: {f.get('observation')}" for f in findings)


def _unavailable_check(reason: str) -> Check:
    """The fail-closed check: the leg could not be measured, so the part is not done."""
    return {
        "id": VISUAL_CHECK_ID,
        "measured": None,
        "measured_kind": None,
        "expected": True,
        "tolerance": None,
        "passed": False,
        "detail": {
            "code": VISUAL_UNAVAILABLE_CODE,
            "message": reason,
            "objects": [],
        },
    }


def _skipped_check(reason: str) -> Check:
    """The not-called check: geometry already failed, so the judge was deliberately not run.

    Fails like every other non-pass — the part is not done either way — but carries its own code so
    a reader can tell a deliberately skipped leg from an unreachable judge. Reporting a skip as a
    pass would let a geometry failure produce a green visual leg.
    """
    return {
        "id": VISUAL_CHECK_ID,
        "measured": None,
        "measured_kind": None,
        "expected": True,
        "tolerance": None,
        "passed": False,
        "detail": {
            "code": "visual.not_run",
            "message": reason,
            "objects": [],
        },
    }


def _finish(
    check: Check,
    subject: dict,
    visual_set: VisualSet | None,
    waiver: dict | None,
) -> ResultEnvelope:
    """Build the report around ``check``, derive its verdict, and wrap it in an envelope.

    A waiver is recorded on the report but never applied to the check: the check reports what was
    measured, and a waiver is the operator's decision to proceed in spite of it. Folding the waiver
    into ``passed`` would make a waived part indistinguishable from a judged one in every
    downstream reader.
    """
    report: ValidationReport = {
        "schema": "fcb.validation-report/1",
        "banner": {
            "freecad_version": shim.freecad_version(),
            "element_map_version": shim.element_map_version(),
        },
        "subject": dict(subject),
        "checks": [check],
    }
    if visual_set is not None:
        report["subject"]["visual_set"] = visual_set
    if waiver is not None:
        report["subject"]["waiver"] = waiver
    report["verdict"] = derive_verdict(report)
    return _report_envelope(report, check, waiver)


def _report_envelope(report: ValidationReport, check: Check, waiver: dict | None) -> ResultEnvelope:
    """Wrap the report; the envelope status mirrors the derived verdict."""
    verdict = report["verdict"]
    detail = check.get("detail")
    return {
        "schema": "fcb.result-envelope/1",
        "status": verdict,
        "detail": None if verdict == "OK" else detail,
        "structured_content": report,
        "text": summarize_visual(report),
    }


def summarize_visual(report: ValidationReport) -> str:
    """One-line summary: the judge's answer, or why there is none."""
    checks = report.get("checks") or []
    check = checks[0] if checks else {}
    waiver = (report.get("subject") or {}).get("waiver")
    suffix = f" Operator waiver: {waiver['reason']}" if waiver else ""
    if check.get("passed"):
        return f"Visual judge PASS: the part matches the spec on every view.{suffix}"
    detail = check.get("detail") or {}
    return f"Visual judge NOT PASSED ({detail.get('code')}): {detail.get('message')}{suffix}"


__all__ = [
    "JudgeUnavailable",
    "VerdictSchemaError",
    "summarize_visual",
    "validate_verdict",
    "verify_visual",
    "waiver_record",
]
