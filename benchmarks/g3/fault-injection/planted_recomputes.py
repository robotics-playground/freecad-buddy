"""The ``planted_op`` callables the ``recompute/`` fault cases name.

``verify_recompute`` is a DOCUMENT-STATE validator, not a geometry one, so its fault suite cannot
reuse ``planted_plans.py``. A corrupted-plan case asks whether the part matches its spec; a
recompute case asks whether the document was left in a state the dependency graph never resolved.
Those are different questions over different evidence, so the op shape differs too: an op here
takes the live document through the production mutation bracket and returns nothing, rather than
returning a plan for the designer loop to execute.

**Every fault is planted through ``transaction.run_mutation``.** That is the same production
bracket ``usecases.features`` and ``usecases.parameters`` write through — the same transaction,
the same recompute, the same ``post_verify``, the same commit-or-rollback. DW-73/DW-93 record what
hand-carving a fixture costs, and a ``.FCStd`` edited into an error state would measure nothing
about a validator that exists to grade what the production path leaves behind.

**Why ``RecomputesFrozen`` is the planting mechanism.** ``post_verify`` blocks a commit on
``_invalid_objects``, which reads ``obj.isValid()`` over the whole document
(``usecases/transaction.py:157``). ``verify_recompute`` reads ``obj.State`` against
``{"Invalid", "Error", "Touched"}`` (``usecases/verify.py:24``). The two disagree on exactly one
state: an object left **Touched** is ``isValid() == True``, so the bracket commits it while the
dependency graph never resolved it. Measured on FreeCAD 1.1.0: a frozen document commits ``OK``
and leaves ``Box`` at ``State=['Touched'], isValid()=True, getStatusString()='Touched'``. That
silent skip IS the defect class ``verify_recompute`` is cited for by G3.2 (recompute-clean) and
G3.3 (edit a parameter, recompute without errors), and it is the only class reachable past the
bracket — a hard-invalid object is rolled back before any validator sees it.

``UNDRIVEABLE`` names the ops whose fault cannot be planted at all, each with the measurement that
established it. Scoring those as misses would blame the validator for a defect the suite never
managed to create.
"""

from __future__ import annotations

# The base plate every single-object case builds: a plain parametric box, the smallest shape that
# carries a real recompute dependency without needing the Sketcher solver.
BOX_LENGTH = 10.0
BOX_WIDTH = 10.0
BOX_HEIGHT = 5.0

# The cut chain the dependency-order cases build: a base plate, a cutter that passes through it,
# and the boolean that depends on both. Three objects is the smallest graph with a real upstream
# and downstream, which is what a dependency-order fault needs.
BASE_LENGTH = 20.0
BASE_WIDTH = 20.0
BASE_HEIGHT = 6.0
CUTTER_SIDE = 4.0
CUTTER_HEIGHT = 20.0
CUTTER_OFFSET = 3.0
CUTTER_SINK = -2.0

# The second cutter of the deep-chain control, offset clear of the first so the two bores do not
# merge — the control must exercise a genuine four-deep graph, not two coincident cuts.
CUTTER2_SIDE = 3.0
CUTTER2_OFFSET = 12.0

# The fully-constrained rectangle the sketch cases build, and the conflicting datum that breaks
# its solve. 25 mm against the declared 10 mm is a contradiction the solver cannot satisfy, so the
# sketch reports dof=-1 rather than merely losing a degree of freedom.
SKETCH_WIDTH = 10.0
SKETCH_HEIGHT = 6.0
SKETCH_CONFLICTING_WIDTH = 25.0

# The driving parameter the editability cases declare, and the value the clean edit writes. The
# name is intent-bearing because ``parameters.declare`` refuses anonymous names outright.
PARAMETER_NAME = "plate_thickness"
PARAMETER_VALUE = 5.0
PARAMETER_EDITED_VALUE = 12.0

# The expression targets the binding faults write. The first names an object the document does not
# carry; the second names a real object and a property it does not have. Both are unresolvable, and
# they fail at different points in FreeCAD's expression resolution, so they are separate cases.
MISSING_OBJECT_EXPRESSION = "Missing.thickness"
MISSING_PROPERTY_EXPRESSION = "Box.NoSuchProperty"


class PlanNotDriveable(RuntimeError):
    """A fault with no reachable trigger on this build; the case is not scorable."""


def _freeze(document) -> None:
    """Stop the document resolving its dependency graph, leaving touched objects unrecomputed.

    This is what makes a planted fault survive the mutation bracket. ``run_mutation`` recomputes
    before ``post_verify``, and on a frozen document that recompute is a no-op, so the objects the
    op touched stay ``Touched`` and commit clean.
    """
    document.RecomputesFrozen = True


# ------------------------------------------------------------------------------------------
# The builders each case's fixture starts from. Each runs inside the production bracket.
# ------------------------------------------------------------------------------------------


def build_box(document) -> list[str]:
    """One parametric box: the base fixture for the single-object cases."""
    box = document.addObject("Part::Box", "Box")
    box.Length = BOX_LENGTH
    box.Width = BOX_WIDTH
    box.Height = BOX_HEIGHT
    return [box.Name]


def build_cut_chain(document) -> list[str]:
    """A base plate, a cutter, and the boolean depending on both.

    The cutter sinks below the base and overshoots it, so the boolean produces a clean through
    bore rather than a coincident-face result that would make the chain's validity depend on
    tolerance rather than on the dependency order the case measures.
    """
    base = document.addObject("Part::Box", "Base")
    base.Length = BASE_LENGTH
    base.Width = BASE_WIDTH
    base.Height = BASE_HEIGHT
    cutter = _cutter(document, "Tool", CUTTER_SIDE, CUTTER_OFFSET)
    cut = document.addObject("Part::Cut", "Cut")
    cut.Base = base
    cut.Tool = cutter
    return [base.Name, cutter.Name, cut.Name]


def build_deep_chain(document) -> list[str]:
    """The cut chain with a second boolean stacked on the first: a four-deep dependency graph."""
    names = build_cut_chain(document)
    cutter = _cutter(document, "Tool2", CUTTER2_SIDE, CUTTER2_OFFSET)
    cut2 = document.addObject("Part::Cut", "Cut2")
    cut2.Base = document.getObject("Cut")
    cut2.Tool = cutter
    return names + [cutter.Name, cut2.Name]


def _cutter(document, name: str, side: float, offset: float):
    """One cutting prism, sunk below the base plate and overshooting its top face."""
    import FreeCAD as App

    cutter = document.addObject("Part::Box", name)
    cutter.Length = side
    cutter.Width = side
    cutter.Height = CUTTER_HEIGHT
    cutter.Placement.Base = App.Vector(offset, offset, CUTTER_SINK)
    return cutter


def build_sketch(document) -> list[str]:
    """A fully-constrained rectangle: the fixture the sketch-solve cases start from.

    Fully constrained on purpose. ``post_verify`` rejects an under-constrained sketch outright
    (``verify_sketch`` requires ``FullyConstrained``), so a fixture that did not solve to zero
    degrees of freedom would be rolled back before any fault could be planted on top of it.
    """
    import FreeCAD as App
    import Part
    import Sketcher

    sketch = document.addObject("Sketcher::SketchObject", "Sk")
    corners = [
        (0.0, 0.0),
        (SKETCH_WIDTH, 0.0),
        (SKETCH_WIDTH, SKETCH_HEIGHT),
        (0.0, SKETCH_HEIGHT),
    ]
    for index in range(4):
        start = corners[index]
        end = corners[(index + 1) % 4]
        sketch.addGeometry(
            Part.LineSegment(App.Vector(*start, 0.0), App.Vector(*end, 0.0)),
            False,
        )
    for index in range(4):
        sketch.addConstraint(Sketcher.Constraint("Coincident", index, 2, (index + 1) % 4, 1))
    for index in (0, 2):
        sketch.addConstraint(Sketcher.Constraint("Horizontal", index))
    for index in (1, 3):
        sketch.addConstraint(Sketcher.Constraint("Vertical", index))
    sketch.addConstraint(Sketcher.Constraint("DistanceX", 0, 1, 0, 2, SKETCH_WIDTH))
    sketch.addConstraint(Sketcher.Constraint("DistanceY", 1, 1, 1, 2, SKETCH_HEIGHT))
    sketch.addConstraint(Sketcher.Constraint("Coincident", 0, 1, -1, 1))
    return [sketch.Name]


# ------------------------------------------------------------------------------------------
# The planted defects. Each runs in its own mutation bracket, after its fixture is built.
# ------------------------------------------------------------------------------------------


def stale_single_object(document) -> list[str]:
    """Leave one object touched and unresolved: the minimal silent recompute skip."""
    document.getObject("Box").enforceRecompute()
    _freeze(document)
    return ["Box"]


def stale_upstream_and_dependent(document) -> list[str]:
    """Edit an upstream feature and leave both it and its dependent unresolved.

    The base plate's length changes, so the boolean that consumes it is stale by construction. The
    document commits with two objects carrying the old geometry under new inputs.
    """
    document.getObject("Base").Length = BASE_LENGTH + 10.0
    document.getObject("Cut").enforceRecompute()
    _freeze(document)
    return ["Base", "Cut"]


def stale_dependent_only(document) -> list[str]:
    """Leave only the DOWNSTREAM boolean unresolved while its inputs are up to date.

    The dependency-order failure with nothing else wrong: every input computed, and the object
    that consumes them never re-ran. A validator that only checked the objects an op wrote would
    miss this, because the op wrote none of them.
    """
    document.getObject("Cut").touch()
    _freeze(document)
    return []


def stale_after_upstream_edit(document) -> list[str]:
    """Edit the cutter and leave both it and the boolean consuming it unresolved."""
    document.getObject("Tool").Length = CUTTER_SIDE * 2.0
    document.getObject("Cut").enforceRecompute()
    _freeze(document)
    return ["Tool"]


def stale_whole_chain(document) -> list[str]:
    """Leave every object in the dependency chain unresolved at once.

    The multi-object case: ``verify_recompute`` must report all three, not merely the first it
    meets, because its report drives a per-object repair.
    """
    for name in ("Base", "Tool", "Cut"):
        document.getObject(name).enforceRecompute()
    _freeze(document)
    return ["Base"]


def broken_expression_missing_object(document) -> list[str]:
    """Bind a feature property to an expression naming an object the document does not carry."""
    box = document.getObject("Box")
    box.setExpression("Height", MISSING_OBJECT_EXPRESSION)
    _freeze(document)
    return [box.Name]


def broken_expression_missing_property(document) -> list[str]:
    """Bind a feature property to a real object's property that does not exist."""
    box = document.getObject("Box")
    box.setExpression("Width", MISSING_PROPERTY_EXPRESSION)
    _freeze(document)
    return [box.Name]


def feature_errors_on_rebuild(document) -> list[str]:
    """Point a boolean's Tool at a datum, so the feature errors whenever it rebuilds.

    An ``App::Placement`` carries no ``Shape``, so ``Part::Cut`` cannot consume it. FreeCAD reports
    "Linked object is not a Part object" on the rebuild.
    """
    holder = document.addObject("App::Placement", "Datum")
    cut = document.addObject("Part::Cut", "Cut")
    cut.Base = document.getObject("Box")
    cut.Tool = holder
    _freeze(document)
    return [cut.Name]


def dangling_dependency(document) -> list[str]:
    """Clear a boolean's Tool link, leaving the feature depending on nothing."""
    document.getObject("Cut").Tool = None
    _freeze(document)
    return ["Cut"]


def sketch_fails_to_solve(document) -> list[str]:
    """Add a datum contradicting the rectangle's declared width, so the solver cannot converge.

    The freeze is load-bearing here, and measurably so. Without it the bracket recomputes, sees an
    over-constrained sketch, aborts and restores ``Sk`` to ``['Up-to-date'] 'Valid'`` — measured
    identically on three consecutive trials, so the defect never reaches the document and there is
    nothing for a validator to find. With it the bracket reports ``SPEC_FAILED`` and leaves the
    sketch at ``['Touched'] 'Touched'``: a rollback that did not clear its own residue, which is a
    real state a part can be found in and one only ``verify_recompute`` reports.
    """
    import Sketcher

    sketch = document.getObject("Sk")
    sketch.addConstraint(Sketcher.Constraint("DistanceX", 0, 1, 0, 2, SKETCH_CONFLICTING_WIDTH))
    _freeze(document)
    return [sketch.Name]


def parameter_removed_under_binding(document) -> list[str]:
    """Drop a driving parameter from its holder while a feature is still bound to it.

    Listed in ``UNDRIVEABLE``: it is written and resolvable so the exclusion names a real op that
    was run and measured, rather than a name nothing backs (DW-73). What it plants is nothing —
    see the recorded measurement.
    """
    holder = document.getObject("Parameters")
    holder.removeProperty(PARAMETER_NAME)
    _freeze(document)
    return ["Box"]


def circular_dependency(document) -> list[str]:
    """Make a feature depend on the boolean that consumes it, so the graph has no evaluation order.

    Listed in ``UNDRIVEABLE``: FreeCAD refuses the cycle at ``setExpression`` time, so the op
    raises before any state lands. It is written and resolvable so the exclusion names an op that
    was actually attempted.
    """
    base = document.getObject("Base")
    base.setExpression("Height", "Cut.Shape.BoundBox.ZLength")
    _freeze(document)
    return [base.Name]


# ------------------------------------------------------------------------------------------
# The clean controls. Each must leave the document recompute-clean.
# ------------------------------------------------------------------------------------------


def control_clean_document(document) -> list[str]:
    """No fault at all: the box its fixture built, recomputed and up to date."""
    return []


def control_touched_then_cleared(document) -> list[str]:
    """Unfreeze a document whose object was touched, so the pending recompute resolves.

    The discriminating control the task names: the object WAS touched, and by the time the
    validator reads it the graph has resolved. An implementation that recorded "was ever touched"
    rather than reading the current state would flag this correct document.
    """
    document.RecomputesFrozen = False
    return []


def control_frozen_but_clean(document) -> list[str]:
    """Freeze the document without touching anything: the flag alone is not a defect.

    Separates the mechanism from the fault. Every planted case here freezes recomputes, so a
    validator keying off ``RecomputesFrozen`` would score a perfect sensitivity while measuring the
    planting mechanism rather than the document state. This control is what makes that cheat fail.
    """
    _freeze(document)
    return []


def control_empty_feature(document) -> list[str]:
    """Add a legitimately empty feature beside a real solid.

    The second control the task names. A ``Part::Feature`` with a null shape is a normal scaffold
    object; it recomputes clean and carries no error state, so flagging it would be a false alarm
    on a correct document.
    """
    document.addObject("Part::Feature", "Scaffold")
    return []


def control_deep_chain(document) -> list[str]:
    """Nothing: the four-deep dependency graph its fixture built, fully resolved.

    Depth is the discriminator. A validator that gave up partway through a dependency chain, or
    that read only leaf objects, would report an error on a graph that resolved correctly.
    """
    return []


def control_parameter_edited(document) -> list[str]:
    """Nothing: the fixture already drove a parameter change through the production path.

    This is G3.3's happy path — declare a driving dimension, write a new value, recompute — which
    is the exact scenario the criterion cites ``verify_recompute`` for. A false alarm here would
    fail every correct part in the editability leg.
    """
    return []


def control_rollback_clean(document) -> list[str]:
    """Nothing: the fixture already had a bad mutation rolled back cleanly.

    The strongest control in the suite. The mutation that ran reported ``RECOMPUTE_ERROR`` and its
    rollback restored the document, so the document IS clean while the run that produced it failed.
    An implementation that read the mutation's status instead of the document's state would flag
    it.
    """
    return []


def control_underconstrained_sketch_rolled_back(document) -> list[str]:
    """Nothing: the fixture's under-constrained sketch was rejected and rolled back cleanly.

    Pairs with :func:`sketch_fails_to_solve`. Both are sketches ``post_verify`` refused; this one's
    rollback left no residue and the other's did. Only reading the document separates them, which
    is what the case measures.
    """
    return []


# Faults whose trigger is UNREACHABLE on this build, each with the measurement that established
# it. Excluded from the population rather than counted as misses: a defect that was never planted
# says nothing about the validator's sensitivity (AD-19).
UNDRIVEABLE: dict[str, str] = {
    "parameter_removed_under_binding": (
        "removing a driving parameter from its holder plants no fault. Measured on FreeCAD 1.1.0 "
        "by running the op through score_recompute_infc.run_case: `parameters.declare` binds "
        "Box.Height by expression to Parameters.plate_thickness, then "
        "`holder.removeProperty('plate_thickness')` inside the production bracket commits OK and "
        "leaves the document at Box=['Up-to-date'] 'Valid', Parameters=['Up-to-date'] 'Valid' with "
        "verify_recompute reporting verdict=OK and failing_objects=[]. FreeCAD does not "
        "re-evaluate a bound expression when the property it names is dropped, so no object enters "
        "error state. Scoring this as a miss would blame verify_recompute for a defect that was "
        "never created; the real gap is that removeProperty leaves a stale binding silently, which "
        "is a finding about parameters.py and not about this validator"
    ),
    "circular_dependency": (
        "a circular dependency cannot be planted through the production path. Measured on FreeCAD "
        "1.1.0 by running the op through score_recompute_infc.run_case: Cut already consumes Base, "
        "so `Base.setExpression('Height', 'Cut.Shape.BoundBox.ZLength')` closes the loop, and "
        "FreeCAD raises RuntimeError: cyclic reference to <doc>#Cut at setExpression time, inside "
        "the op. The bracket maps that to SPEC_FAILED and rolls back, leaving Base, Tool and Cut "
        "all ['Up-to-date'] 'Valid' and verify_recompute reporting verdict=OK with "
        "failing_objects=[]. The cycle is refused before it exists, so there is no document state "
        "for the validator to read. This is FreeCAD's own guard working, not a validator miss"
    ),
}


# The fixture each planted op runs against: the brackets that build the document BEFORE the fault
# is planted. Each entry is a list of (label, builder) run as its own `run_mutation`, so the
# starting document is produced by the production path exactly as a real part would be.
#
# `parameter_edit` and `rollback_clean` are not plain builders: they drive `usecases.parameters`
# and a deliberately failing mutation respectively, which the driver runs specially because both
# need the registry rather than the bare document.
FIXTURES: dict[str, str] = {
    "circular_dependency": "cut_chain",
    "parameter_removed_under_binding": "parameter_edit",
    "broken_expression_missing_object": "box",
    "broken_expression_missing_property": "box",
    "control_clean_document": "box",
    "control_deep_chain": "deep_chain",
    "control_empty_feature": "box",
    "control_frozen_but_clean": "box",
    "control_parameter_edited": "parameter_edit",
    "control_rollback_clean": "rollback_clean",
    "control_touched_then_cleared": "box_touched_frozen",
    "control_underconstrained_sketch_rolled_back": "underconstrained_sketch_rejected",
    "dangling_dependency": "cut_chain",
    "feature_errors_on_rebuild": "box",
    "sketch_fails_to_solve": "sketch",
    "stale_after_upstream_edit": "cut_chain",
    "stale_dependent_only": "cut_chain",
    "stale_single_object": "box",
    "stale_upstream_and_dependent": "cut_chain",
    "stale_whole_chain": "cut_chain",
}

# The plain builder fixtures, each a list of (bracket label, builder) run in order.
BUILDERS: dict[str, list[tuple[str, object]]] = {
    "box": [("build box", build_box)],
    "cut_chain": [("build cut chain", build_cut_chain)],
    "deep_chain": [("build deep chain", build_deep_chain)],
    "sketch": [("build sketch", build_sketch)],
    "box_touched_frozen": [
        ("build box", build_box),
        ("touch and freeze", stale_single_object),
    ],
}


def underconstrained_sketch(document) -> list[str]:
    """One unconstrained line: a sketch ``post_verify`` must reject and roll back.

    The fixture half of ``control_underconstrained_sketch_rolled_back``. It is expected to FAIL its
    bracket — that failure is the control's whole point, so the driver does not treat it as an
    error.
    """
    import FreeCAD as App
    import Part

    sketch = document.addObject("Sketcher::SketchObject", "Sk")
    sketch.addGeometry(
        Part.LineSegment(App.Vector(0.0, 0.0, 0.0), App.Vector(SKETCH_WIDTH, 0.0, 0.0)),
        False,
    )
    return [sketch.Name]


def rejected_expression(document) -> list[str]:
    """Bind an unresolvable expression WITHOUT freezing, so the bracket rolls the damage back.

    The fixture half of ``control_rollback_clean``. Identical to
    :func:`broken_expression_missing_object` except that it does not freeze recomputes, which is
    what lets ``post_verify`` see the invalid object and abort. It is expected to FAIL its bracket.
    """
    box = document.getObject("Box")
    box.setExpression("Height", MISSING_OBJECT_EXPRESSION)
    return [box.Name]


# Fixtures whose bracket is EXPECTED to fail: the control measures what the rollback left behind,
# so a failing mutation status is the fixture working, not a broken case.
EXPECTED_FAILING_FIXTURES = frozenset({"rollback_clean", "underconstrained_sketch_rejected"})

BUILDERS["rollback_clean"] = [
    ("build box", build_box),
    ("bind unresolvable expression", rejected_expression),
]
BUILDERS["underconstrained_sketch_rejected"] = [
    ("build underconstrained sketch", underconstrained_sketch)
]


REGISTRY = {
    "circular_dependency": circular_dependency,
    "parameter_removed_under_binding": parameter_removed_under_binding,
    "broken_expression_missing_object": broken_expression_missing_object,
    "broken_expression_missing_property": broken_expression_missing_property,
    "control_clean_document": control_clean_document,
    "control_deep_chain": control_deep_chain,
    "control_empty_feature": control_empty_feature,
    "control_frozen_but_clean": control_frozen_but_clean,
    "control_parameter_edited": control_parameter_edited,
    "control_rollback_clean": control_rollback_clean,
    "control_touched_then_cleared": control_touched_then_cleared,
    "control_underconstrained_sketch_rolled_back": control_underconstrained_sketch_rolled_back,
    "dangling_dependency": dangling_dependency,
    "feature_errors_on_rebuild": feature_errors_on_rebuild,
    "sketch_fails_to_solve": sketch_fails_to_solve,
    "stale_after_upstream_edit": stale_after_upstream_edit,
    "stale_dependent_only": stale_dependent_only,
    "stale_single_object": stale_single_object,
    "stale_upstream_and_dependent": stale_upstream_and_dependent,
    "stale_whole_chain": stale_whole_chain,
}


def resolve(name: str):
    """The planted op ``name`` denotes.

    :raises KeyError: no op carries that name.
    """
    return REGISTRY[name]
