"""The live G2 case driver: run one command case through preview -> confirm -> apply -> undo.

Runs inside FreeCAD (``FreeCADCmd``), beside ``benchmarks/g1/actor_run.py`` — the same role for a
different gate. For each case it opens the case's input document, mints a real ``preview_id`` via
``preview_dry_run``, applies the mutation with that token as ``confirm``, collects the ``mutation``
block, undoes with the pre-op fingerprint as ``expect_fingerprint``, and grades the result with
``assertions.evaluate``. One ``CaseOutcome`` is returned per case per repeat.

The confirm gate is driven, never bypassed: the token is minted by a real preview so approval
records read ``mode: "preview_token"``. ``preview_dry_run`` and the apply must run in one process,
because the token secret is per-process and the token signs the fully defaulted arguments.

A case supplies no tool call. ``dev/*/case.yaml`` carries a natural-language ``spec`` and its
assertions, so translating a command into a tool call is the actor's job, not this module's: an
``operation`` resolver is injected by the caller. Without one, every case reports
``UNRESOLVED`` — an honest "no actor supplied a command", never a pass.

Stdlib + FreeCAD API only.
"""

from __future__ import annotations

import sys
from dataclasses import dataclass, field
from pathlib import Path

HERE = Path(__file__).resolve().parent
_REPO_ROOT = HERE.parents[1]
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))
_SRC = _REPO_ROOT / "src"
if str(_SRC) not in sys.path:
    sys.path.insert(0, str(_SRC))

DEV_DIR = HERE / "dev"

# A case whose command no actor translated into a tool call. Distinct from a graded failure: it
# means the benchmark was never driven, so it must never be scored as an attempt that failed a
# geometry assertion.
UNRESOLVED = "UNRESOLVED"


@dataclass
class CaseOutcome:
    """One case's measured result for one repeat, holding what each G2 criterion reads.

    :param case_id: the case's declared id.
    :param op_type: the case's declared op type.
    :param status: the apply envelope's status, or ``UNRESOLVED`` when no command was resolved.
    :param checks: the ``assertions.evaluate`` results over the mutated document.
    :param mutation: the apply envelope's ``mutation`` block, or ``None``.
    :param undo: the ``document_undo`` structured content, or ``None``.
    :param error: the reason this case could not be driven, or ``None``.
    :param fault_kind: a fault case's declared ``fault.kind``, or ``None`` for a command case.
        ``clean_control`` marks a case that must not be flagged; anything else is a planted defect.
    """

    case_id: str
    op_type: str
    status: str
    checks: list = field(default_factory=list)
    mutation: dict | None = None
    undo: dict | None = None
    error: str | None = None
    fault_kind: str | None = None

    @property
    def passed(self) -> bool:
        """Whether the apply succeeded and every geometry assertion passed."""
        return (
            self.status == "OK"
            and bool(self.checks)
            and all(check.get("passed") is True for check in self.checks)
        )


def load_cases(split_dir: Path) -> list[dict]:
    """Load every ``case.yaml`` under ``split_dir`` at any depth, ordered by path.

    Recursive because splits nest at different depths: ``dev/<case-id>/case.yaml`` is one level
    while ``fault-injection/<suite>/<case-id>/case.yaml`` is two, and a one-level glob silently
    returns nothing for a fault split rather than failing.

    :param split_dir: a split directory holding ``case.yaml`` entries at any depth.
    """
    import yaml

    cases = []
    for case_yaml in sorted(split_dir.rglob("case.yaml")):
        data = yaml.safe_load(case_yaml.read_text(encoding="utf-8"))
        if isinstance(data, dict):
            data["dir"] = case_yaml.parent
            cases.append(data)
    return cases


def _fault_kind(case: dict) -> str | None:
    """The case's declared ``fault.kind``, or ``None`` when it is a command case."""
    fault = case.get("fault")
    return fault.get("kind") if isinstance(fault, dict) else None


def _unresolved(case: dict, reason: str) -> CaseOutcome:
    return CaseOutcome(
        case_id=case.get("id", "?"),
        op_type=case.get("op_type", "?"),
        status=UNRESOLVED,
        error=reason,
        fault_kind=_fault_kind(case),
    )


def run_case(case: dict, resolver, *, audit_sink=None) -> CaseOutcome:
    """Drive one case end to end and return what it measured.

    :param case: a loaded ``case.yaml`` mapping carrying ``id``, ``inputs.document`` and
        ``assertions.checks``.
    :param resolver: a callable taking the case and returning ``{"tool": name, "args": {...}}``,
        or ``None`` when it cannot translate the case's command.
    :param audit_sink: an ``AuditSink`` installed for the approval records this run writes.
    """
    import FreeCAD as App

    from freecad_buddy.hosts.tool_catalog import preview_op_table
    from freecad_buddy.usecases import confirm, preview
    from freecad_buddy.usecases.documents import DocumentRegistry, ValidationError
    from freecad_buddy.usecases.fingerprint import fingerprint

    from benchmarks.harness import assertions

    if resolver is None:
        return _unresolved(case, "no command resolver supplied")
    operation = resolver(case)
    if not operation:
        return _unresolved(case, "resolver produced no tool call for this command")

    document_path = (case["dir"] / case["inputs"]["document"]).resolve()
    if not document_path.is_file():
        return _unresolved(case, f"input document not found: {document_path.name}")

    previous_sink = confirm.set_approval_sink(audit_sink) if audit_sink else None
    registry = DocumentRegistry()
    pre_open = set(App.listDocuments())
    try:
        try:
            opened = registry.document_open(str(document_path))
        except ValidationError as exc:
            return _unresolved(case, f"input document could not be opened: {exc}")
        handle = opened["structured_content"]["doc"]
        document = registry.with_document(handle, lambda _h, d: d)
        pre_digest = fingerprint(document)["digest"]

        tool = operation["tool"]
        args = dict(operation.get("args") or {})
        try:
            preview_envelope = preview.preview_dry_run(
                registry,
                preview_op_table(),
                None,
                doc=handle,
                operation={"tool": tool, "args": args},
                render="off",
            )
        except ValidationError as exc:
            return _unresolved(case, f"preview refused the command: {exc}")
        if preview_envelope["status"] != "OK":
            return _unresolved(case, f"preview failed: {preview_envelope['status']}")

        token = preview_envelope["structured_content"]["preview_id"]
        applied = _apply(registry, tool, handle, args, token, audit_sink)
        mutation = (applied.get("structured_content") or {}).get("mutation")

        checks = assertions.evaluate(document, case.get("assertions", {}).get("checks") or [])
        # A refused apply commits no transaction, so undoing would revert whatever sits below it
        # on the stack — or raise on an empty one, aborting every case still to run. An op that
        # never applied has nothing to undo, and the criterion reads that as the failure it is.
        undo_content = None
        if applied["status"] == "OK":
            try:
                undo = registry.document_undo(doc=handle, expect_fingerprint=pre_digest)
                undo_content = undo.get("structured_content")
            except ValidationError as exc:
                undo_content = {"matches_pre_op": False, "errors": [{"error": str(exc)}]}

        return CaseOutcome(
            case_id=case.get("id", "?"),
            op_type=case.get("op_type", "?"),
            status=applied["status"],
            checks=checks,
            mutation=mutation,
            undo=undo_content,
            fault_kind=_fault_kind(case),
        )
    finally:
        if audit_sink:
            confirm.set_approval_sink(previous_sink)
        for name in set(App.listDocuments()) - pre_open:
            App.closeDocument(name)


def _apply(registry, tool: str, handle: str, args: dict, token: str, audit_sink=None) -> dict:
    """Apply ``tool`` with the minted ``token`` as its confirm; return the result envelope.

    The arguments are the ones the preview measured, byte for byte: the token signs the fully
    defaulted parameters, so any divergence here is refused by the gate rather than applied.

    ``audit_sink`` is passed into the mutation itself, not only installed for the approval record:
    ``run_mutation`` is what writes the before/after lines carrying ``fingerprint_before/after``
    and the rollback outcome, and G2.2 reads the audit log as one of its two declared evidence
    sources. Without it those lines carry nulls and half the criterion's evidence is missing.
    """
    from freecad_buddy.usecases import features, sketches
    from freecad_buddy.usecases.documents import ValidationError

    module = sketches if tool.startswith("sketch_") else features
    fn = getattr(module, tool, None)
    if fn is None:
        return {"status": "INVALID_INPUT", "structured_content": {}}
    try:
        return fn(
            registry,
            doc=handle,
            confirm={"preview_id": token, "elicitation_action": "accept"},
            audit_sink=audit_sink,
            **args,
        )
    except ValidationError as exc:
        return {
            "status": "INVALID_INPUT",
            "structured_content": {},
            "detail": {"message": str(exc)},
        }


def run_split(split_dir: Path, resolver, *, repeats: int, audit_sink=None) -> list[CaseOutcome]:
    """Drive every case under ``split_dir`` ``repeats`` times; return one outcome per repeat.

    :param split_dir: the split whose cases are driven.
    :param resolver: the command resolver passed through to :func:`run_case`.
    :param repeats: how many times each case is driven (R).
    :param audit_sink: an ``AuditSink`` installed for the run.
    """
    outcomes: list[CaseOutcome] = []
    for case in load_cases(split_dir):
        for _ in range(repeats):
            outcomes.append(run_case(case, resolver, audit_sink=audit_sink))
    return outcomes
