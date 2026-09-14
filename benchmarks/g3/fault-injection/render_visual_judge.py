"""Build and render the eight ``visual-judge/`` fault fixtures for a judge to grade.

Run under FreeCADCmd from the repository root::

    FCB="$USERPROFILE/micromamba/envs/fcb"
    PYTHONPATH="$FCB/Library/bin;$FCB/Library/lib" PATH="$FCB/Library/bin:$PATH" \\
      "$FCB/python.exe" benchmarks/g3/fault-injection/render_visual_judge.py

For every case in ``visual-judge/``: resolve its ``planted_op`` in ``visual_parts.REGISTRY``, drive
the plan it returns through ``usecases.designer_loop.run_designer_loop``, then render the AD-21
standard visual set from the part the loop built — a 3D iso render through
``usecases.screenshot.query_screenshot`` and the dimensioned three-view sheet through
``usecases.techdraw.techdraw_for_judge``. Images land at
``visual-judge/<case-id>/render/{iso,sheet}.png``, and one ``render-manifest.json`` beside them
records what a grader needs to work from the manifest plus the images alone.

**This script produces no verdict.** It builds the evidence; a vision-capable judge grades the
images afterwards by looking at them. Nothing here calls a model, and
``_registry/validators.yaml``'s ``visual_judge`` row stays ``not_scored`` until a judge actually
grades them.

The geometry leg is measured and recorded, because two cases assert that it must NOT catch their
defect (``must_not_be_caught_by: geometry_assertions_pass``). A manifest that claimed a
geometry-invisible fault without measuring the geometry would be asserting exactly the thing the
case exists to establish.

pyyaml is an external-process dependency (AD-12); this script runs inside FreeCADCmd and parses the
small fixed ``case.yaml`` shape itself, reusing ``score_g3_infc``'s parser.
"""

from __future__ import annotations

import json
import shutil
import sys
import traceback
from pathlib import Path

HERE = Path(__file__).resolve().parent
G3_ROOT = HERE.parent
REPO_ROOT = HERE.parents[2]
SRC = REPO_ROOT / "src"
for _path in (str(SRC), str(REPO_ROOT), str(HERE)):
    if _path not in sys.path:
        sys.path.insert(0, _path)

import visual_parts  # noqa: E402
from score_g3_infc import _scalar, _spec_assertions, _unavailable_visual  # noqa: E402

from benchmarks.harness import assertions  # noqa: E402
from freecad_buddy.adapters.render_probe import OffscreenRenderPort, QtSvgRasterPort  # noqa: E402
from freecad_buddy.usecases import confirm, designer_loop, screenshot, techdraw  # noqa: E402

SUITE_DIR = HERE / "visual-judge"
MANIFEST_PATH = SUITE_DIR / "render-manifest.json"
DEV_DIR = G3_ROOT / "dev"

# AD-21's legibility floor. A callout the judge cannot read fails a correct part for a reason no
# assertion reports, so the renders are produced at the floor rather than below it.
RENDER_PX = 2048

# The cosmetic-difference control's render options. Its whole point is that these differ from every
# other case's while the geometry does not, so a judge keying on pixel similarity rather than on
# the spec checklist flags it. The colour is a warm tone against the default grey.
#
# The quaternion ORBITS the iso camera 55 degrees about the world vertical axis: each of the iso
# basis vectors is rotated by that spin and the result is rebuilt as a rotation. That construction
# is what holds the ELEVATION fixed — the view direction's z stays 0.5774, exactly iso's — so every
# principal face keeps the same readable slant and only the azimuth moves.
#
# Two wrong constructions were rendered and rejected before this one, and neither was visible in
# the numbers (DW-128). ``Rotation(Vector(0,0,1), d).multiply(iso)`` gives the right view-direction
# elevation on paper and renders the pad dead flat and axis-aligned, with no depth at all.
# ``iso.multiply(Rotation(Vector(0,0,1), d))`` spins about the camera's own axis, which tilts it:
# at 60 degrees the pad is seen nearly end-on. The original hand-written value
# (0.306186, 0.176777, 0.739199, 0.573223) had view direction (0.655, -0.090, 0.750) — steeper
# than iso and almost along a principal plane — and rendered the pad nearly edge-on with the rib
# ambiguous. A control whose subject cannot be read cannot measure tolerance of cosmetic variation:
# a judge can only grade it CANNOT ASSESS, which then counts against the false-alarm bar.
#
# DW-44 records the shipped non-iso camera presets as unverified quaternions with no render-leg
# assertion behind them. This one is derived, checked by ``_assert_cosmetic_camera_derived``, and
# was confirmed by looking at the render — which is the only step that caught the two failures.
_ISO_ORIENTATION = (0.424708, 0.17592, 0.339851, 0.820473)
_COSMETIC_SPIN_DEGREES = 55.0
_COSMETIC_ORIENTATION = (0.29549, 0.352151, 0.680304, 0.570843)
_COSMETIC_COLOR = (0.78, 0.52, 0.24)


class SuiteError(SystemExit):
    """A malformed visual-judge suite — exit non-zero with a clean message, never write."""


def load_cases() -> list[dict]:
    """Parse every ``visual-judge/*/case.yaml`` into the fields this script drives."""
    cases = []
    for case_yaml in sorted(SUITE_DIR.glob("*/case.yaml")):
        text = case_yaml.read_text(encoding="utf-8")
        case_id = _scalar(text, "id")
        if not case_id:
            raise SuiteError(f"{case_yaml}: no 'id'")
        kind = _scalar(text, "  kind") or _scalar(text, "kind")
        expectation = _scalar(text, "  expectation") or _scalar(text, "expectation")
        if (kind == "planted_defect") != (expectation == "DETECT"):
            raise SuiteError(
                f"case {case_id!r}: fault.kind {kind!r} disagrees with expectation {expectation!r}"
            )
        planted_op = _scalar(text, "planted_op")
        if not planted_op:
            raise SuiteError(f"case {case_id!r}: no 'planted_op'")
        spec_ref = _scalar(text, "spec_ref")
        if not spec_ref:
            raise SuiteError(f"case {case_id!r}: no 'spec_ref'")
        cases.append(
            {
                "id": case_id,
                "dir": case_yaml.parent,
                "expectation": expectation,
                "planted_op": planted_op,
                "spec_ref": spec_ref,
                "fault_description": _block_scalar(text, "description"),
                "must_not_be_caught_by": _scalar(text, "must_not_be_caught_by"),
            }
        )
    if len(cases) != 8:
        raise SuiteError(f"expected 8 visual-judge cases, found {len(cases)}")
    return cases


def _block_scalar(text: str, key: str) -> str:
    """Join a ``key: >-`` folded block into one line."""
    lines = text.splitlines()
    for index, line in enumerate(lines):
        if line.strip().startswith(f"{key}:") and ">" in line:
            indent = len(line) - len(line.lstrip())
            body = []
            for following in lines[index + 1 :]:
                if not following.strip():
                    break
                if len(following) - len(following.lstrip()) <= indent:
                    break
                body.append(following.strip())
            return " ".join(body)
    return ""


def _spec_text(spec_ref: str) -> str:
    """The referenced dev case's own ``spec:`` text, folded to one line."""
    case_yaml = DEV_DIR / spec_ref / "case.yaml"
    if not case_yaml.is_file():
        raise SuiteError(f"spec {spec_ref!r}: no case at {case_yaml}")
    return _block_scalar(case_yaml.read_text(encoding="utf-8"), "spec")


def _assert_cosmetic_camera_derived() -> None:
    """Check the committed cosmetic quaternion really is the iso camera spun about the vertical.

    The constant is a literal so the module stays importable without FreeCAD, and a literal that
    claims a derivation has to be checkable or it is just another magic quaternion (DW-44). This
    recomputes it and also pins the property the fix turns on: equal elevation to iso, so the spin
    changes azimuth only.
    """
    import FreeCAD as App

    iso = App.Rotation(*_ISO_ORIENTATION)
    spin = App.Rotation(App.Vector(0, 0, 1), _COSMETIC_SPIN_DEGREES)
    spun = App.Rotation(
        spin.multVec(iso.multVec(App.Vector(1, 0, 0))),
        spin.multVec(iso.multVec(App.Vector(0, 1, 0))),
        spin.multVec(iso.multVec(App.Vector(0, 0, 1))),
    )
    for derived, committed in zip(spun.Q, _COSMETIC_ORIENTATION):
        if abs(derived - committed) > 1e-6:
            raise SuiteError(
                f"_COSMETIC_ORIENTATION is not the iso camera spun {_COSMETIC_SPIN_DEGREES} deg "
                f"about the vertical axis: derived {tuple(round(v, 6) for v in spun.Q)}, "
                f"committed {_COSMETIC_ORIENTATION}"
            )
    up = App.Vector(0, 0, 1)
    if abs(spun.multVec(up).z - iso.multVec(up).z) > 1e-6:
        raise SuiteError(
            "the cosmetic camera's elevation differs from iso's; a spin about the vertical axis "
            "must change azimuth only, or the control renders its subject at a new and possibly "
            "unreadable angle"
        )


def _render_options(case_id: str, rendered: list[str]) -> dict:
    """The ``view`` options for one case's iso render.

    Every case but the cosmetic control renders through the same shared camera and default tone, so
    an image difference between any two of them is a geometry difference. The control deliberately
    departs from both.
    """
    if not case_id.endswith("cosmetic-render-difference"):
        return {"camera": "iso", "width": RENDER_PX, "height": RENDER_PX}
    return {
        "camera": "custom",
        "custom_orientation": list(_COSMETIC_ORIENTATION),
        "width": RENDER_PX,
        "height": RENDER_PX,
        "styles": [{"object": name, "color": list(_COSMETIC_COLOR)} for name in rendered],
    }


def _analytic_facts(document, subject) -> dict:
    """The measurable facts a grader checks the images against.

    Read off the produced solid rather than off the plan: the manifest describes the part that was
    actually built, and a fact taken from the plan would agree with the plan however wrong the
    build was.
    """
    shape = subject.Shape
    bbox = shape.BoundBox
    holder = document.getObject("Parameters")
    declared = {}
    if holder is not None:
        for prop in holder.PropertiesList:
            if prop in ("ExpressionEngine", "Label", "Label2", "Visibility"):
                continue
            value = getattr(holder, prop, None)
            magnitude = getattr(value, "Value", value)
            if isinstance(magnitude, (int, float)) and not isinstance(magnitude, bool):
                declared[prop] = round(float(magnitude), 4)
    return {
        "declared_parameters_mm": declared,
        "measured_volume_mm3": round(shape.Volume, 3),
        "measured_bbox_mm": [
            round(bbox.XLength, 3),
            round(bbox.YLength, 3),
            round(bbox.ZLength, 3),
        ],
        "cylindrical_face_count": sum(
            1 for face in shape.Faces if face.Surface.__class__.__name__ == "Cylinder"
        ),
        "is_valid_solid": bool(shape.isValid()),
    }


def _geometry_outcome(iteration: dict) -> dict:
    """Whether the geometry leg caught anything, and which check it was."""
    violation = designer_loop.detect_spec_violation(iteration["checks"])
    return {
        "geometry_assertions_pass": violation is None,
        "geometry_caught_by": violation["check_id"] if violation else None,
        "checks": [
            {"id": check["id"], "passed": bool(check["passed"])} for check in iteration["checks"]
        ],
    }


def run_case(case: dict) -> dict:
    """Build one case's part, render its visual set, and return its manifest row."""
    import FreeCAD as App

    from freecad_buddy.usecases.documents import DocumentRegistry

    plan = visual_parts.resolve(case["planted_op"])()
    checks, anchor_frame = _spec_assertions(case["spec_ref"])

    render_dir = case["dir"] / "render"
    if render_dir.exists():
        shutil.rmtree(render_dir)
    render_dir.mkdir(parents=True)

    registry = DocumentRegistry()
    handle = registry.document_create(label=case["id"])["structured_content"]["doc"]
    previous = confirm.set_auto_approve(True)
    try:
        record = designer_loop.run_designer_loop(
            registry,
            plan,
            checks,
            assertions.evaluate,
            _unavailable_visual,
            doc=handle,
            run_id=case["id"],
            anchor_frame=anchor_frame,
            extra_tools={"plan_visual_part": visual_parts.visual_step},
        )
        iteration = record["iterations"][0]
        if iteration.get("step_failure") or not iteration.get("executed_steps"):
            raise SuiteError(
                f"case {case['id']!r}: the plan did not build: {iteration.get('step_failure')}"
            )

        document = registry.with_document(handle, lambda _handle, doc: doc)
        subject = techdraw._subject_object(document)

        shot = screenshot.query_screenshot(
            registry,
            OffscreenRenderPort(),
            doc=handle,
            view=_render_options(case["id"], [subject.Name]),
        )["structured_content"]
        if not shot["render"]["available"] or not shot["render"]["resource_link"]:
            raise SuiteError(f"case {case['id']!r}: no iso render: {shot['render']['reason']}")
        iso_path = render_dir / "iso.png"
        shutil.copyfile(shot["render"]["resource_link"], iso_path)

        sheet = techdraw.techdraw_for_judge(
            registry, QtSvgRasterPort(), doc=handle, page_width_px=RENDER_PX
        )["structured_content"]
        if not sheet.get("available"):
            raise SuiteError(f"case {case['id']!r}: no sheet: {sheet.get('reason')}")
        sheet_path = render_dir / "sheet.png"
        shutil.copyfile(sheet["png_path"], sheet_path)

        return {
            "case_id": case["id"],
            "expectation": case["expectation"],
            "planted_op": case["planted_op"],
            "fault": case["fault_description"],
            "must_not_be_caught_by": case["must_not_be_caught_by"],
            "spec_ref": case["spec_ref"],
            "spec": _spec_text(case["spec_ref"]),
            "images": {
                "iso": f"{case['id']}/render/iso.png",
                "sheet": f"{case['id']}/render/sheet.png",
            },
            "render": {
                "iso_camera": "custom" if "cosmetic" in case["id"] else "iso",
                "width_px": RENDER_PX,
                "sheet_page_px": [sheet.get("page_width_px"), sheet.get("page_height_px")],
                "sheet_views": list(sheet.get("views", [])),
            },
            "sheet_callouts": sheet.get("callouts", []),
            "analytic_facts": _analytic_facts(document, subject),
            "geometry_leg": _geometry_outcome(iteration),
        }
    finally:
        confirm.set_auto_approve(previous)
        for name in list(App.listDocuments().keys()):
            App.closeDocument(name)


def main() -> int:
    _assert_cosmetic_camera_derived()
    rows = []
    failures = []
    for case in load_cases():
        try:
            row = run_case(case)
        except Exception:
            failures.append(case["id"])
            print(f"FAIL {case['id']}\n{traceback.format_exc()}")
            continue
        rows.append(row)
        facts = row["analytic_facts"]
        print(
            f"OK   {row['case_id']:52s} {row['expectation']:11s} "
            f"vol={facts['measured_volume_mm3']:9.3f} bbox={facts['measured_bbox_mm']} "
            f"geom_pass={row['geometry_leg']['geometry_assertions_pass']}"
        )

    manifest = {
        "schema": "fcb.g3.visual-judge-render-manifest/1",
        "suite": "benchmarks/g3/fault-injection/visual-judge",
        "criterion": "G3.7",
        "targets_validator": "visual_judge@benchmarks.g3.judge",
        "regenerate_with": (
            "FreeCADCmd benchmarks/g3/fault-injection/render_visual_judge.py "
            "(see the module docstring for the full environment)"
        ),
        "purpose": (
            "Evidence for a judge to grade by inspection. This manifest carries NO verdict: "
            "the images have not been graded, and visual_judge stays not_scored until they are."
        ),
        "image_width_px": RENDER_PX,
        "cases": rows,
    }
    MANIFEST_PATH.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    print(f"\nwrote {MANIFEST_PATH} ({len(rows)}/8 cases)")
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
