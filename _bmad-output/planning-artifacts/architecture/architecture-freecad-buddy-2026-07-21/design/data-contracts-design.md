---
title: 'Data Contracts Design — contracts/ package'
status: final
date: '2026-07-21'
ad-refs: [AD-1, AD-2, AD-3, AD-5, AD-6, AD-7, AD-8, AD-10, AD-12, AD-13, AD-14, AD-17, AD-20]
sources:
  - ARCHITECTURE-SPINE.md
  - _bmad-output/specs/spec-freecad-buddy/phase-gates.md
  - _bmad-output/planning-artifacts/research/technical-headless-preview-diff-channel-research-2026-07-20.md
  - _bmad-output/planning-artifacts/research/technical-process-per-job-isolation-research-2026-07-20.md
  - _bmad-output/planning-artifacts/research/technical-undo-transaction-geometry-hashing-research-2026-07-20.md
---

# Data Contracts Design — `src/freecad_buddy/contracts/`

Implementation-ready design for the schema-owning ring. Per **AD-17**, `ResultEnvelope`, `ValidationReport`, and the audit record are owned here from Phase 0 and reused by every surface (tool results, harness reports, audit log) — no surface defines its own variant. Per **AD-1/AD-12** this package imports **stdlib only** (it runs both in-FreeCAD and in the external process).

## 1. Package layout & ground rules

```text
src/freecad_buddy/contracts/
  status.py        # TerminalStatus, JobState, ErrorDetail
  envelope.py      # ResultEnvelope, ImageRef
  report.py        # ValidationReport, ReportBanner, Check, WilsonCI
  audit.py         # AuditRecord (JSON-lines)
  diff.py          # GeometryDiff (preview payload, AD-10)
  document.py      # DocHandle, Selector types (AD-20)
  fingerprint.py   # FingerprintRecord (AD-6)
  rpc.py           # JSON-RPC frame types, Handshake (AD-2)
  assertions.py    # closed assertion vocabulary + anchor-frame types (AD-13; §5.1)
  jsonschema/      # generated *.schema.json, one per wire type
```

Rules:

- **Types:** Python 3.11-compatible `TypedDict` + `Literal` (`typing` stdlib) for wire shapes; frozen `dataclass` only where behavior (validation helpers) is attached. No pydantic — AD-12 forbids third-party deps in-FreeCAD.
- **Wire encoding:** plain JSON, UTF-8. Every top-level wire object carries a `schema` tag (§2). All numbers are SI-internal per the spine's unit convention (mm/deg) with explicit `units` fields where a value could be ambiguous.
- **JSON Schema:** each wire type has a checked-in Draft 2020-12 schema under `jsonschema/`, generated from the TypedDicts by a repo script and diff-checked in CI (drift = build failure). Per-tool MCP `outputSchema`s are composed from these by `$ref` — the adapter never hand-writes a field the contracts don't define.

## 2. Versioning & evolution rules (all schemas)

- Every top-level object carries `"schema": "fcb.<name>/<major>"`, e.g. `"fcb.result-envelope/1"`.
- **Within a major: additive-only.** (Bound by AD-28; this section owns the mechanics.) New fields must be optional with a defined default. Readers MUST ignore unknown fields. Removing/renaming a field, changing a type, or changing a closed enum = **major bump** and a new schema file (old one retained for replay of audit logs).
- A retained old major lives in `jsonschema/retained/` as `<name>-<major>.schema.json`, unchanged and outside the generator's drift check.
- **The terminal status set is frozen** (§3). Adding a member is a major bump on every schema that embeds it — that is deliberate friction (AD-17 exists to prevent status-set drift).
- The RPC channel negotiates by `protocol_version` at handshake (§10); schema majors ride inside it and are not independently negotiated.
- Audit logs are append-only history: records are **never rewritten** to a new major; readers keep old-major decoders.

## 3. Status vocabulary (`status.py`)

One closed set, used identically by tool results, validation verdicts, and job outcomes (**AD-17**).

```python
TerminalStatus = Literal[
    "OK", "SPEC_FAILED", "RECOMPUTE_ERROR", "TIMEOUT",
    "OOM_KILLED", "WORKER_CRASHED", "INVALID_INPUT",
]
JobState = Literal["QUEUED", "RUNNING"] | TerminalStatus   # non-terminal states job-API-only

class ErrorDetail(TypedDict, total=False):
    code: str            # machine code, dotted namespace: "recompute.failed_objects",
                         # "tnp.unsupported", "sketch.conflicting", "rpc.handshake_mismatch"
    message: str         # human-readable explanation (spine Errors convention) — required
    objects: list[str]   # affected FreeCAD immutable Names
    constraint_ids: list[dict]  # {"solver_id": int(1-based), "name": str}  ← Constraints[id-1] map
    data: dict           # code-specific machine payload
```

Semantics fixed here: `TIMEOUT` originates only from the transport layer (marshal timeout, RPC listener unreachable — from Phase 0; see integration-mcp-freecad.md §7); `WORKER_CRASHED` and `OOM_KILLED` are reserved vocabulary with no producer (AD-17, AD-28); use-case code maps its own failures to `SPEC_FAILED | RECOMPUTE_ERROR | INVALID_INPUT`. A crashed or timed-out producer can never be reported `OK` (AD-17).

## 4. `ResultEnvelope` (`envelope.py`)

Every tool call — MCP tool result, RPC response payload, harness check — returns exactly this shape.

```python
class ImageRef(TypedDict, total=False):
    kind: Literal["resource_link", "inline"]   # resource_link preferred (AD-10)
    uri: str                # set when kind == "resource_link"
    mime_type: str          # "image/png"
    data_b64: str           # set when kind == "inline"; server enforces ≤1920 px longest edge
    audience: list[str]     # always ["user"] — never model-directed
    label: str              # "before" | "after" | free text

class ResultEnvelope(TypedDict, total=False):
    schema: Literal["fcb.result-envelope/1"]
    status: TerminalStatus                  # required
    detail: ErrorDetail | None              # required non-null unless status == "OK"
    structured_content: dict                # required; validated by the tool's outputSchema
    text: str                               # required; human-readable mirror of structured_content
    images: list[ImageRef]                  # optional, capability-gated (AD-10)
    text_blocks: list[str]                  # optional; raw text bodies, sent as extra content items
```

- `structured_content` is the machine payload; per-tool `outputSchema` constrains it (spine Tool-results convention). `text` is always generated from `structured_content` server-side — never authored independently, so the two cannot diverge.
- MCP mapping (adapter concern, defined here so both sides agree): envelope → `structuredContent`; `text` → first `content[]` text item; each `text_blocks` entry → one more raw `text` content item after the JSON one, with `text_blocks` removed from both the JSON item and `structuredContent`; `images` → `image`/`resource_link` content items with `annotations.audience:["user"]`; `status != "OK"` additionally sets MCP `isError: true`.
- Verify tools put their `ValidationReport` (§5) inside `structured_content.report` — the envelope wraps, never duplicates, report fields.

## 5. `ValidationReport` (`report.py`)

Emitted identically by `verify_*` tools and the gate runner (phase-gates global protocol step 1) (**AD-17**). Fields are backed by re-executed deterministic checks; producing-agent claims are never echoed into it.

```python
class WilsonCI(TypedDict):
    rate: float; low: float; high: float; n: int; r: int   # majority-of-R rate + 95% Wilson bounds

class ReportBanner(TypedDict, total=False):
    freecad_version: str            # e.g. "1.1.3" — required
    element_map_version: int | None # required; None ⇔ no element map (gates AD-7 UNSUPPORTED)
    validator_sensitivity: dict | None  # {"sensitivity": float, "false_alarm": float,
                                        #  "n_faults": int, "suite_id": str}  (AD-13/AD-19)
    wilson_ci: WilsonCI | None      # present iff a rate is claimed (AD-14)
    anchor_frame: AnchorFrame | None  # verify_shape: the frame the checks were measured in (§5.1)

class Check(TypedDict, total=False):
    id: str                 # stable dotted id: "shape.volume", "sketch.fully_constrained",
                            # "tnp.mapped_name_diff", "export.step_roundtrip.volume"
    measured: float | str | bool | list | None
    expected: float | str | bool | list | None
    tolerance: dict | None  # {"abs": float, "rel": float, "units": str} — never tighter
                            # than Shape.getTolerance (spine Numeric-tolerance convention)
    passed: bool            # required; UNSUPPORTED (AD-7) ⇒ passed=false + detail.code="tnp.unsupported"
    detail: ErrorDetail | None

class ValidationReport(TypedDict, total=False):
    schema: Literal["fcb.validation-report/1"]
    banner: ReportBanner            # required on every report (spine Reports convention)
    subject: dict                   # {"doc": DocHandle, "fingerprint": str} — what was checked
    checks: list[Check]             # required
    warnings: list[Check]           # non-fatal findings; AD-8: redundant constraints live here
    verdict: TerminalStatus         # required; derived, never asserted
```

**Verdict derivation (normative):** `OK` ⇔ every `checks[].passed` is true. Any failed spec/geometry check → `SPEC_FAILED`; a check that could not run because recompute failed → `RECOMPUTE_ERROR`; malformed inputs → `INVALID_INPUT`. `warnings` never affect the verdict (AD-8: fully redundant constraints fail the sketch check; partially redundant constraints are a warning). An `UNSUPPORTED` TNP check is `passed: false` — never clean (AD-7) — surfacing as `SPEC_FAILED` with `detail.code="tnp.unsupported"`; an `element_map_version` bump re-baselines, it does not fail.

### 5.1 Assertion vocabulary & anchor frame (`assertions.py`)

The §7.2 primitive names (verification-design.md) form a closed vocabulary; the measurements live in
`usecases/assertions.py`, the names and frame types here (**AD-13**).

```python
AssertionFn = Literal["is_valid_solid", "count_cylindrical_holes", "hole_diameter",
                      "hole_position", "hole_spacing", "hole_through", "distance_between",
                      "angle_between", "expect_bbox", "expect_extent", "expect_volume"]
ASSERTION_FNS: frozenset[str]       # = get_args(AssertionFn); any other fn is malformed input

AnchorFrameKind = Literal["named_datum", "base_sketch_plane", "largest_planar_face"]
ANCHOR_FRAME_KINDS: frozenset[str]  # = get_args(AnchorFrameKind)

class DeclaredAnchorFrame(TypedDict, total=False):   # what a spec / verify_shape input declares
    kind: AnchorFrameKind           # required
    ref: str | None                 # object Name, else unique Label; None for largest_planar_face

class AnchorFrame(TypedDict, total=False):           # resolved; carried in ReportBanner
    kind: AnchorFrameKind | Literal["global"]   # required; "global" ⇔ no frame declared
    ref: str | None
    entity: str | None              # object Name, or the face's mapped name (indexed name
                                    #   when the shape carries no element map)
    origin: list[float]             # [3], mm, document coordinates
    axes: list[list[float]]         # frame X, Y, Z unit vectors in document coordinates
    units: Literal["mm"]
    unresolved: str | None          # why a declared frame did not resolve; origin/axes absent
```

An unresolved frame fails only the frame-dependent checks, each `passed: false` with
`detail.code="invalid_input.unsupported_assertion"` (verdict `INVALID_INPUT`); a malformed check or
frame declaration is refused before measuring (`INVALID_INPUT` envelope).

## 6. Audit record (`audit.py`) — append-only JSON-lines

Exists from Phase 0 (AD-17). One line per mutation, exec, or approval event; per session file (`audit.log` in the session workdir; spine Logging convention). Lines are never edited or deleted.

```python
class AuditRecord(TypedDict, total=False):
    schema: Literal["fcb.audit-record/1"]
    ts: str                         # RFC 3339 UTC, required
    actor: str                      # "ai:<model-or-client-id>" | "human:<operator>" |
                                    # "harness:<run-id>" | "agent"
    event: Literal["mutation", "exec", "preview", "approval", "rollback"]
    tool: str                       # wire tool name ("feature_pocket", "debug_exec", …)
    doc: DocHandle                  # §9 — required for document-touching events
    params_digest: str              # "sha256:<hex>" over canonical-JSON params (params
                                    #   themselves may be large/sensitive; digest is mandatory,
                                    #   inline params optional under a size cap)
    fingerprint_before: str | None  # FingerprintRecord.digest (§9), serializer-tagged
    fingerprint_after: str | None
    verify_verdict: TerminalStatus | None   # verdict of the AD-5 post-verify report
    verify_report_ref: str | None   # path/uri of the full ValidationReport
    approval: dict | None           # {"mode": "elicitation" | "client_confirm" |
                                    #   "auto_approve" | "operator_flag",
                                    #   "source": str,           # client id / env var name
                                    #   "diff_digest": str}      # sha256 of the GeometryDiff shown
    rollback: dict | None           # {"path": "abort" | "snapshot_restore",
                                    #   "verified": bool}        # AD-5: measured, never assumed
```

Vocabulary reuse (spine Deferred table: preview must reuse this vocabulary): `fingerprint_before/after`, `verify_verdict`, `params_digest`, and the diff's `touched/new/deleted` naming (§7) are shared identifiers — the preview channel and any revision diff introduce **no synonyms** for these concepts. Every AD-10 auto-approval writes an `approval` record with `mode:"auto_approve"` and `source:"FREECAD_BUDDY_AUTO_APPROVE"`. The posture is on by default in every host.

## 7. Geometry diff (`diff.py`) — preview payload (AD-10)

The mandatory `preview_dry_run` payload and its `outputSchema`; also the revision-diff shape. Field list fixed from the preview-channel research (Finding 3) — the spine defers only tolerance defaults, not fields.

```python
class ScalarDelta(TypedDict):
    before: float; after: float; delta: float; units: str

class CountDelta(TypedDict):
    before: int; after: int; delta: int

class GeometryDiff(TypedDict, total=False):
    schema: Literal["fcb.geometry-diff/2"]
    op: dict                        # {"tool": str} — the args are not echoed; the confirm
                                    #   token signs their digest
    doc: DocHandle                  # live target document (§9)
    deltas: dict                    # required: {"volume": ScalarDelta, "area": ScalarDelta,
                                    #  "bbox": {"before": [6]float, "after": [6]float,
                                    #           "center_shift": [3]float, "units": "mm"},
                                    #  "com": {"before": [3]float, "after": [3]float,
                                    #          "shift": [3]float, "units": "mm"}}
    counts: dict                    # required: {"faces": CountDelta, "edges": CountDelta,
                                    #            "vertices": CountDelta, "solids": CountDelta}
    touched: list[str]              # immutable Names of modified feature-tree nodes
    new: list[str]                  # Names created by the op (on the TempDoc copy)
    deleted: list[str]              # Names removed by the op
    validity: dict                  # required: {"is_valid": bool, "recompute_clean": bool,
                                    #  "recompute_errors": [{"object": str, "error": str}]}
    tnp_precheck: dict              # required: {"status": "CLEAN"|"FLAGGED"|"UNSUPPORTED",
                                    #  "element_map_version": str,
                                    #  "counts": {<verdict>: int},
                                    #  "findings": [non-PASS only, verification-design §3.3 shape]}
    fingerprint_before: str         # live-doc FingerprintRecord.digest — audit-vocabulary reuse (§6)
    render: dict | None             # {"available": bool, "reason": str|None} — images travel in
                                    #   the envelope (§4), never inside the diff
```

The shipped code returned every finding, PASS included (`usecases/preview.py:587`); `/2` restores the summarized shape.

`tnp_precheck.status == "UNSUPPORTED"` (no element map, AD-7/AD-11) is surfaced to the confirmer verbatim — the preview never claims clean. The diff is computed on a `copyObject` TempDoc (AD-20 lifecycle); `before` values come from the live document, `after` from the copy. Confirmation gates on this object; renders are optional overlay (AD-10).

## 8. Document handle & sub-element selectors (`document.py`)

**AD-20:** every tool call carries an explicit handle; `ActiveDocument` is never an implicit target.

```python
class DocHandle(TypedDict, total=False):
    handle: str             # opaque id issued by document_open/document_create; required.
                            #   Only document_* use cases mint or resolve handles.
    name: str               # FreeCAD immutable document Name — display/debug aid, never the key
    transient: bool         # True for preview TempDocs (reserved name prefix "FCB_TMP_",
                            #   cleaned only by their creator — AD-20)

# Sub-element selectors (spine Sub-element addressing convention): two kinds, tagged union.
class GeometricSelector(TypedDict, total=False):
    kind: Literal["geometric"]
    object: str                     # owning object's immutable Name — required
    element_type: Literal["face", "edge", "vertex"]
    query: dict                     # closed query vocabulary (extends additively):
                                    #  {"surface_type": "Plane"|"Cylinder"|...,
                                    #   "axis": [3]float, "radius": float,
                                    #   "nearest_point": [3]float, "largest": bool,
                                    #   "normal": [3]float}
    expect: Literal["one", "many"]  # "one" (default): ambiguous match = INVALID_INPUT, never a guess

class MappedNameSelector(TypedDict, total=False):
    kind: Literal["mapped_name"]
    object: str                     # owning object's immutable Name — required
    mapped_name: str                # TNP element-map name — required
    element_map_version: int        # version the name was captured under; mismatch triggers
                                    #   re-resolution, not blind use (AD-7 re-baseline rule)

Selector = GeometricSelector | MappedNameSelector
```

Bare indexed names (`Face6`) are accepted **only** as call-time input sugar: the use case resolves them to a `MappedNameSelector` immediately; contracts objects (audit records, diffs, reports, specs) never store an indexed name (spine convention; AD-13 bans them in specs outright).

## 9. Fingerprint record (`fingerprint.py`) — AD-6

Produced by the single `fingerprint()` implementation in `usecases/`; the contracts ring owns only the record shape.

```python
class MassProps(TypedDict):
    volume: float; area: float
    bbox: list[float]               # [xmin, ymin, zmin, xmax, ymax, zmax], mm
    com: list[float]                # [3]
    principal_moments: list[float]  # [3], from the shape's solids; per-object step (below)
    inertia: list[float]            # [6] Ixx, Iyy, Izz, Ixy, Ixz, Iyz about com, document axes,
                                    #   from the solids; optional (additive, AD-28);
                                    #   per-object step (below); off-diagonals are the
                                    #   negated products of inertia (Ixy = −∫xy dm), as in
                                    #   OCC's MatrixOfInertia
    quantum: float                  # always 1e-6 (spine Numeric-tolerance convention): the
                                    #   step of volume, area, bbox and com

class ObjectFingerprint(TypedDict):
    name: str                       # immutable Name (sort key)
    brep_sha256: str                # sha256(b"") when the object's Shape is null
    massprops: MassProps            # independent cross-oracle (hashing research §2.3);
                                    #   every field 0.0 when the object's Shape is null

class FingerprintRecord(TypedDict):
    schema: Literal["fcb.fingerprint/1"]
    serializer: Literal["exportBinary", "exportBrep"]   # shim-probed tag — required
    objects: list[ObjectFingerprint]                    # sorted by name
    digest: str                     # "sha256:<hex>" over canonical serialization of
                                    #   (serializer, objects); the value stored in
                                    #   audit fingerprint_before/after and diff fields
```

Quantization (normative, AD-6): `volume`, `area`, `bbox` and `com` round to `quantum` (1e-6). `principal_moments` and `inertia` round to a per-object step `10^(floor(log10(s) + 1e-9) − 9)`, where `s` is the largest absolute diagonal component of that object's tensor; when `s` is 0 or not finite, the step is 1e-6. The `+ 1e-9` moves each step boundary from `s = 10^k` to `s = 10^k·(1 − 2.3e-9)`: round dimensions put `s` exactly on a power of ten (a 6 x 10 x 10 mm box has `s = 10000.0`), where last-bit jitter would flip the step 10x. The tensor and its eigenvalues jitter in their last bits after a recompute, so a fixed 1e-6 step crosses rounding boundaries on large parts. A fixed coarser step is rejected: it hides the rotation of a small part.

Comparison rule (normative, AD-6): two records are comparable **iff `serializer` tags are equal**; a helper `fingerprints_equal(a, b)` raises on tag mismatch rather than returning False — cross-tag comparison is a programming error, never a "changed" verdict. Equality = `digest` equality; on mismatch, `massprops` provides the human-diffable cross-oracle. Document-XML/FCStd and tessellation hashes are banned as identity oracles and have no contract type.

**Read-only-after-render verdict (normative):** a check that a read-only operation (a render/screenshot) did not mutate the document compares `massprops_equal(before, after)` — the geometric invariants — **not** the `digest`. OCCT re-lays-out a freshly loaded shape's BRep bytes the first time a render touches it, so the digest legitimately shifts while the geometry is unchanged; a digest comparison here yields a false "changed" verdict. The invariants compared are `volume`, `area`, `com`, `principal_moments` and `inertia`; `bbox` is excluded because `Shape.BoundBox` is tessellation-derived and shifts when a render/export refines the mesh. A genuine mutation still changes the mass-properties.

**Snapshot-restore rollback verdict (normative):** `run_mutation`'s snapshot-restore path proves the rollback with `massprops_equal(fp_before, fingerprint(restored))` over the same object-name set, not with the digest. Reopening the `saveCopy` file re-serializes every shape, so the B-rep bytes never match the in-memory shapes the snapshot was saved from. The abort path proves rollback by digest equality first, then by `massprops_equal` when the digest differs: a recompute after `abortTransaction` writes new B-rep bytes for shapes whose geometry it restored (measured 2026-10-06 on `kiwibox-drawer.FCStd`: 33 objects with new bytes, 0 with changed mass properties). Only an invariant mismatch escalates to the snapshot restore. A null-shape entry carries zeroed mass properties, so it equals another null-shape entry and differs from a real shape.

### 9.1 Wire projection

The full `FingerprintRecord` never travels in a tool result. A `MutationBlock` (`fcb.mutation/2`) carries `fingerprint_before` / `fingerprint_after` as `{"digest": str, "serializer": str}`, and `changed: [{name, volume, area, com}]` for each object whose invariants (`volume`, `area`, `com`, `principal_moments`, `inertia`) differ. On a failed or rolled-back mutation each `changed` entry adds `before` and `after` `MassProps`. The server keeps full records in a digest-keyed in-process cache; `document_undo` resolves `expect_fingerprint` digests through it. `/1` stays for audit replay (AD-28).

## 10. RPC wire contract (`rpc.py`) — AD-2/AD-3

Frames between the external MCP process and the in-FreeCAD RPC listener. Both sides import this module; neither invents framing. Transport: newline-delimited JSON-RPC 2.0 frames over localhost TCP; stdlib-encodable only (both ends must run without third-party deps — AD-12 on the listener side).

Frame layout, method registry, error codes, timeouts, and the discovery file are designed in integration-mcp-freecad.md §2 (the authoritative wire design); `rpc.py` carries its types. Aligned essentials:

```json
// request — method names mirror the use-case surface directly (no call_usecase wrapper)
{"jsonrpc": "2.0", "id": 41, "method": "feature_pocket",
 "params": {"doc": {"handle": "d1"}, "...": "tool params"}}

// success — result IS a ResultEnvelope (no second result vocabulary)
{"jsonrpc": "2.0", "id": 41, "result": {"schema": "fcb.result-envelope/1", "status": "OK", ...}}

// marshal timeout is a DOMAIN outcome — an envelope, never a JSON-RPC error (§3)
{"jsonrpc": "2.0", "id": 41, "result": {"schema": "fcb.result-envelope/1", "status": "TIMEOUT",
  "detail": {"marshal_timeout": true, "maybe_still_running": true}}}

// failure of the TRANSPORT itself (auth -32000, handshake -32002) — no envelope exists yet
{"jsonrpc": "2.0", "id": 41, "error": {"code": -32000, "message": "auth failed"}}
```

**Handshake** — first frame on every connection MUST be `rpc_hello` (else `-32002`, closed):

```json
// -> {"jsonrpc":"2.0","id":0,"method":"rpc_hello","params":{
//      "contract_version": "1", "client": "fcb-mcp/<pkg-version>",
//      "token": "<per-session, from discovery file>"}}
// <- {"jsonrpc":"2.0","id":0,"result":{
//      "contract_version": "1", "freecad_version": "1.1.0",
//      "capabilities": {"element_map": true, "render": "gui_constructed",
//                       "export_binary": true, "varset": true, "exec_enabled": false}}}
```

- `contract_version` mismatch → `-32004` with supported versions in `error.data`; connection closed. Capability flags are runtime probes (AD-11 — never version-string comparisons); the server gates render/TNP behavior on them.
- **Error mapping (normative):** tool-level failures always arrive as a `result` `ResultEnvelope` with non-OK status — JSON-RPC `error` is reserved for the channel itself (codes: integration doc §2.3). Channel errors map to the closed set: listener/marshal crash or dropped connection → `WORKER_CRASHED`; marshal deadline exceeded → `TIMEOUT`; malformed frame, bad token, unknown method, version mismatch → `INVALID_INPUT`. `error.data` always embeds `{status, detail}` so callers run one decoder for both paths.
- Localhost bind + per-session `token` (discovery file, mode 0600) per AD-3; token travels in `params`, never in a URL.

## 11. Cross-contract invariants (checked by contract tests)

1. One status vocabulary: no `Literal` status/verdict/state type outside `status.py` (grep-enforced in CI alongside the AD-1 no-Gui-import check).
2. Every `ValidationReport` has a `banner`; `wilson_ci` present whenever any check `measured` is a rate (AD-14).
3. `ResultEnvelope.text` is derived from `structured_content` — a round-trip test regenerates and compares.
4. `GeometryDiff` field names `touched/new/deleted/fingerprint_before` and `AuditRecord` fingerprint/digest fields are the same identifiers (vocabulary-reuse test — spine Deferred note on AD-10).
5. `FingerprintRecord` comparison across differing `serializer` tags raises (AD-6).
6. JSON Schemas under `jsonschema/` regenerate byte-identical from the TypedDicts.
7. `DocHandle.handle` is required on every document-touching wire object (AD-20).

## 12. Resolved-here vs deferred

| Decision | This doc | Deferred to |
| --- | --- | --- |
| Diff field list | Fixed (§7) — spine deferred only the Phase 2 lock-in moment; fields follow the preview research verbatim | Tolerance defaults per assertion → fault-injection calibration (AD-19) |
| Status set | Frozen (§3) | — |
| RPC framing | Newline-delimited JSON-RPC 2.0 + handshake (§10) | Marshal timeout values → Phase 0 spike |
| Fingerprint serializer | Tagged union `exportBinary`/`exportBrep` (§9) | Which tag a given build uses → Phase 0 `exportBinary` exposure spike |
| Approval modes | Closed list (§6) | Elicitation-unsupported client UX detail → Phase 2 UX design |

**Conflicts with the spine:** none found. One deliberate refinement: the spine's AD-10 deferred row leaves the diff `outputSchema` field list to "Phase 2 UX design"; this document fixes the field *names and shapes* now (they are fully determined by the research and the AD-17 audit vocabulary) and leaves only tolerances/thresholds to Phase 2 — locking names early is what the AD-17 reuse rule requires.
