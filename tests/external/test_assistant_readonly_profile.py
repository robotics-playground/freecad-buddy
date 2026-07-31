"""Read-only assistant profile tests (external / pytest).

Prove the G1.6 read-only guarantee at the profile level: the ``READ_ONLY_PROFILE`` allow-list is
exactly the read-only queries + read-only verifiers + non-geometry document lifecycle, and the
built profile registry registers ZERO geometry-mutation tools. The absence set is the
geometry/model-mutation set (``feature_*``/``sketch_*``/``preview_*``/``document_create``/
``document_save``/``debug_exec``), asserted explicitly — not ``all(not mutating)`` — because
``document_open``/``close`` carry ``mutating=True`` yet are non-geometry lifecycle the assistant
needs.
"""

from __future__ import annotations

from freecad_buddy.adapters.marshal import InlineExecutor, Marshal
from freecad_buddy.adapters.mcp_server import Capabilities
from freecad_buddy.hosts.tool_catalog import (
    DEBUG_EXEC_SPEC,
    READ_ONLY_PROFILE,
    ToolSpec,
    build_readonly_profile,
    tool_specs,
)
from freecad_buddy.adapters.render_probe import OffscreenRenderPort
from freecad_buddy.usecases.documents import DocumentRegistry
from freecad_buddy.usecases.exports import ExportRegistry

# Read-only (`mutating=False`) catalog tools intentionally EXCLUDED from the profile: the export
# verifiers need an `export_id` from a prior (mutating) export, and the screenshot render is not
# needed by the text-QA assistant. Pinned so a future catalog change cannot silently drop or add
# one without updating this expectation.
EXCLUDED_READ_ONLY_TOOLS = {
    "query_screenshot",
    "verify_export_step",
    "verify_export_stl",
    "verify_export_3mf",
    # `preview_dry_run` leaves the live document untouched — it mutates a saveCopy'd TempDoc and
    # closes it — so it is correctly `mutating=False`. It is excluded because it previews a
    # Phase-2 sketch_/feature_ mutation, which the Phase-1 read-only assistant cannot issue.
    "preview_dry_run",
}

EXPECTED_ALLOW_LIST = {
    "query_capabilities",
    "query_tree_summary",
    "query_object",
    "query_mass_properties",
    "query_dependencies",
    "query_sketch_info",
    "query_placement",
    "verify_shape",
    "verify_sketch",
    "verify_recompute",
    "document_open",
    "document_close",
    "document_list",
}

# The geometry/model-mutation set that G1.6 requires ABSENT from the profile.
GEOMETRY_MUTATION_TOOLS = {
    "document_create",
    "document_save",
    "document_recompute",
    "export_step",
    "export_stl",
    "export_3mf",
    "debug_exec",
}


def _catalog_names() -> set[str]:
    return {spec.name for spec in tool_specs()} | {DEBUG_EXEC_SPEC.name}


def test_allow_list_matches_expected_read_only_set():
    assert set(READ_ONLY_PROFILE) == EXPECTED_ALLOW_LIST


def test_allow_list_names_exist_in_catalog():
    catalog = _catalog_names()
    for name in READ_ONLY_PROFILE:
        assert name in catalog, f"allow-list names a tool not in the catalog: {name}"


def test_profile_registers_zero_geometry_mutation_tools():
    for name in GEOMETRY_MUTATION_TOOLS:
        assert name not in READ_ONLY_PROFILE, f"geometry-mutation tool leaked into profile: {name}"


def test_geometry_mutation_tools_exist_in_catalog():
    """Pin that every name in the mutation absence set is a real catalog tool.

    Without this the exclusion assertions below are vacuous: a renamed mutation tool would match
    nothing in ``GEOMETRY_MUTATION_TOOLS`` and still pass green while entering the surface.
    """
    catalog = _catalog_names()
    for name in GEOMETRY_MUTATION_TOOLS:
        assert name in catalog, f"absence set names a non-existent catalog tool: {name}"


def test_profile_excludes_every_mutating_geometry_spec():
    """Every catalog spec that mutates geometry/model state is absent from the allow-list.

    Geometry mutation is the geometry/model-changing set (creates, saves, recomputes, exports,
    exec) — the document lifecycle tools ``document_open``/``close``/``list`` are ``mutating=True``
    but are the non-geometry lifecycle the assistant is explicitly allowed. So the assertion is
    scoped to the geometry-mutation names, not all ``mutating=True`` specs.
    """
    specs: list[ToolSpec] = [*tool_specs(), DEBUG_EXEC_SPEC]
    for spec in specs:
        if spec.name in GEOMETRY_MUTATION_TOOLS:
            assert spec.name not in READ_ONLY_PROFILE, spec.name


def test_read_only_surface_is_allow_list_plus_pinned_exclusions():
    """The catalog's full read-only (``mutating=False``) surface partitions exactly into the
    allow-listed read-only tools and the pinned excluded set — nothing read-only is unaccounted for.

    ``document_open``/``close`` are allow-listed but ``mutating=True`` lifecycle, so they are not in
    the read-only surface; the comparison is against the allow-list minus those lifecycle tools.
    """
    read_only = {spec.name for spec in tool_specs() if not spec.mutating}
    allow_listed_read_only = EXPECTED_ALLOW_LIST - {"document_open", "document_close"}
    assert read_only == allow_listed_read_only | EXCLUDED_READ_ONLY_TOOLS


def _real_profile():
    return build_readonly_profile(
        DocumentRegistry(),
        ExportRegistry(),
        Capabilities(allow_exec=False),
        Marshal(InlineExecutor()),
        OffscreenRenderPort(),
    )


def test_build_readonly_profile_registers_exactly_the_allow_list():
    """The real builder (not a test stub) filters the production catalog registry to the allow-list.

    ``build_readonly_profile`` is what enforces G1.6 on the surface the assistant actually drives;
    a filter bug or a leaked mutation tool would be invisible if only the frozenset were tested.
    """
    profile = _real_profile()
    assert set(profile.names()) == EXPECTED_ALLOW_LIST
    for name in GEOMETRY_MUTATION_TOOLS:
        assert name not in profile.names(), f"mutation tool leaked into built profile: {name}"


def test_document_open_is_allowed_despite_mutating_flag():
    """The assistant needs ``document_open`` to load a fixture; a naive mutating filter would strip
    it. The explicit allow-list keeps it while excluding geometry mutation."""
    by_name = {spec.name: spec for spec in tool_specs()}
    assert by_name["document_open"].mutating is True
    assert "document_open" in READ_ONLY_PROFILE
