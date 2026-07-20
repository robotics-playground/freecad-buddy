---
stepsCompleted: [1, 2, 3, 4, 5]
inputDocuments:
  - docs/intent.md
  - docs/references/FreeCAD/src/App/Document.cpp
  - docs/references/FreeCAD/src/App/Transactions.cpp
  - docs/references/FreeCAD/src/App/TransactionalObject.cpp
  - docs/references/FreeCAD/src/Mod/Part/App/TopoShape.cpp
workflowType: 'research'
lastStep: 5
research_type: 'technical'
research_topic: 'FreeCAD undo/transaction reliability headless + deterministic geometry hashing for rollback verification'
research_goals: 'Recommend a concrete rollback + geometry-state-verification mechanism for Phase 2 (undo restores prior state exactly, verified by geometry hash, automatic rollback on failed verification), grounded in FreeCAD transaction API behavior headless and deterministic shape-state hashing options.'
user_name: 'TanNT'
date: '2026-07-20'
web_research_enabled: true
source_verification: true
---

# Research Report: Technical — FreeCAD Undo/Transaction Reliability (Headless) & Deterministic Geometry Hashing for Rollback Verification

**Date:** 2026-07-20
**Author:** TanNT
**Research Type:** Technical (deep dive)

---

## Research Overview

**Question.** Phase 2 of `docs/intent.md` (Copilot) requires three trust-foundation guarantees that are currently only stated, not designed:

1. *"Undo after any AI operation restores previous document state exactly (verified by geometry hash) in 100% of benchmark cases."*
2. *"100% of executed operations run post-verification automatically; any failed verification triggers automatic rollback and a human-readable explanation."*
3. Everything must work **headless under `FreeCADCmd`** (Phase 0/CI constraint, reaffirmed in the Risks table: *"Every phase's suite runs headless in CI from Phase 0 onward"*).

This report answers, from primary evidence: (a) how FreeCAD's transaction/undo machinery actually behaves — especially headless — and where it will bite us; (b) what a **deterministic geometry hash** can and cannot be built from; and (c) a **concrete, buildable rollback + state-verification mechanism** that satisfies the Phase 2 exit criteria.

**Methodology & evidence priority.**
1. **Primary — local FreeCAD C++ source** at `docs/references/FreeCAD` (transaction machinery in `src/App/Document.cpp`, `src/App/Transactions.cpp`, `src/App/TransactionalObject.*`; shape serialization in `src/Mod/Part/App/TopoShape.cpp`). Two dedicated source-diving passes; all claims cited to file + method/line.
2. **Secondary — web corroboration**: FreeCAD issue tracker (#6031 / tracker #4265), FreeCAD DeepWiki transactions page, OCCT BinTools/BRep format docs. Used to confirm behavior and surface the community-known undo pitfall.

**Bottom line up front.** FreeCAD's undo works headless, but **only if the script opens/commits transactions itself** — there is no App-level "undo on" default, and a known bug (#6031) means undo does not always restore the state that existed *before* `openTransaction`. Therefore the design must **not trust undo alone**: pair it with an independent, deterministic **BRep-binary geometry hash** (`TopoShape::exportBinary` → SHA-256) captured *before* the mutation, and use **`abortTransaction` for planned rollback** plus a **saved snapshot restore** as the guaranteed fallback. This gives a rollback path whose success is *verified*, not assumed — exactly the "verify, don't trust" principle the intent demands.

---

## Part 1 — FreeCAD Transaction / Undo Machinery (headless reality)

All paths under `docs/references/FreeCAD/`. Line numbers approximate to the vendored revision.

### 1.1 Architecture

Three cooperating classes:

- **`Document`** (`src/App/Document.cpp` / `.h`) owns the undo/redo stacks, the *active* transaction, and the public API. Stacks: `std::list<Transaction*> mUndoTransactions` (`Document.h:1465`) and `mRedoTransactions` (`Document.h:1467`); active transaction pointer `activeUndoTransaction` (`private/DocumentP.h:85`).
- **`Transaction`** (`src/App/Transactions.cpp`) — one atomic undo step; a container of `TransactionObject` entries keyed by affected object.
- **`TransactionObject` / `TransactionDocumentObject`** — per-object snapshot record (New / Del / Chn) that knows how to apply/restore.

### 1.2 CRITICAL: is undo ON headless? (the "no App-level default" finding)

**There is no `App::Document`-level "undo disabled" default, and no GUI-vs-headless difference baked into the kernel.** The legacy `UndoMode` on/off switch is a **dead Python-compat shim**: `DocumentPy::getUndoMode()` is hardcoded to return `1` and `setUndoMode()` is a no-op (`src/App/DocumentPyImp.cpp:982-988`). The C++ `Document` has no `UndoMode` enum and no `doTransactions` member anymore.

What actually controls whether an undo step is *retained* is **whether a transaction is open when a change happens**. Changes auto-open a transaction via `_checkTransaction()` (`Document.cpp:489-539`) and `changePropertyOfObject()` (`Document.cpp:283-291`), but the gate is the presence of a *booked* or *global application* transaction, not a mode flag:

```cpp
// Document.cpp (~489-539), paraphrased gate
if (!testStatus(Restoring) || testStatus(Importing)) {
    if (!d->bookedTransaction)
        d->bookedTransaction = GetApplication().getGlobalTransaction();
    if (d->bookedTransaction != NullTransaction) { ... _openTransaction(...) }
}
```

**Practical consequence for `FreeCADCmd`/scripts:** In the GUI, `Gui::Command` wraps every operation in `openTransaction`/`commitTransaction`, so `bookedTransaction` is set and undo steps accumulate. Under `FreeCADCmd`, **nothing opens transactions unless the script does**; `bookedTransaction` stays `0`, `_checkTransaction` opens nothing, and **no undo history accumulates**. Headless *looks* like "undo off" but the mechanism is "no transaction was ever opened."

> **Design rule #1:** Our bridge MUST call `Doc.openTransaction(name)` before, and `Doc.commitTransaction()` after, every AI mutation. Without this, undo is silently a no-op headless. (Corroborated by FreeCAD DeepWiki: property snapshots are only captured "if an active transaction exists.")

### 1.3 open / commit / abort semantics, IDs, stacks, limits

- **Opening while one is open auto-commits the previous and clears redo.** `_openTransaction` (`Document.cpp:370-421`): if `activeUndoTransaction` exists it calls `_commitTransaction(true)` (line ~396), then `_clearRedos()` (line 399), then allocates a new `Transaction(id)`. So a stray un-committed transaction is silently folded into history, and **any new transaction wipes the entire redo stack**.
- **Transaction IDs = cross-document grouping.** A monotonically increasing app-wide integer (`Transaction::getNewID()`, atomic, `Transactions.cpp:93-103`). Passing the *same* id to `openTransaction` in several documents groups them so they undo/redo together (assemblies/links). `id == 0` (`NullTransaction`, `TransactionDefs.h:35`) = fresh id = single-document behavior. **We should pass `0`** unless deliberately grouping.
- **Undo/redo mechanics** (`Document.cpp:174-274`): `undo(id)` commits any active transaction, pops `mUndoTransactions.back()`, builds a mirror `Transaction`, `apply(*this, false)` (reverse), pushes onto redo. `redo` is symmetric with `apply(*this, true)`. `getAvailableUndos/Redos` (`Document.cpp:771-813`) return counts.
- **Limits.** The real cap is **stack size, default `20`** (`DocumentP.h:95`; enforced in `_commitTransaction`, `Document.cpp:602-606` — oldest dropped silently). The memory limit `UndoMemSize` (default `0`, `DocumentP.h:94`; `setUndoLimit`, `Document.cpp:815-823`) is **stored but not enforced** in this revision — `Transaction::getMemSize()` / `TransactionObject::getMemSize()` both return `0`.

### 1.4 What `abortTransaction` actually restores

`abortTransaction()` → `_abortTransaction()` (`Document.cpp:622-670`): sets `d->rollback`, calls `activeUndoTransaction->apply(*this, false)` (reverse-apply), deletes the active transaction. It does **not** touch the committed undo stack — only the in-progress transaction is rolled back.

Snapshots are captured **lazily, once per property per transaction**, as a deep **Copy** of the property *before* it changes (`TransactionObject::setProperty`, `Transactions.cpp:390-401`: `data.property = pcProp->Copy();`); restore does `prop->Paste(*data.property)` (`applyChn`, `Transactions.cpp:305-388`). Object add is undone by delete; object remove is undone by re-add (the removed object is kept alive inside the transaction, `~Transaction`, `Transactions.cpp:57-91`). Apply order is **delete → add → property-restore** (`Transaction::apply`, `Transactions.cpp:179-207`).

**So in principle abort fully restores prior state** — created objects removed, deleted objects re-inserted with backlinks repaired, changed properties pasted back.

### 1.5 Pitfalls (the reasons we must verify, not trust)

1. **Known bug — undo restores the WRONG boundary.** FreeCAD **issue #6031 / tracker #4265**: *"Undo doesn't restore the state as it was before opening a transaction."* Reproduction: create a sketch on a plane in PartDesign, undo → body and origin are removed but **the sketch persists**, leaving an inconsistent document. Root causes cited: transaction IDs stored independently of documents, some GUI property changes not recorded, unordered property application colliding with the attachment engine, nested transactions interfering. This is *precisely* the failure our Phase 2 criterion #3 targets — and it is real and reported. Workaround per the tracker: avoid nested transactions and **verify document state manually rather than relying on undo for critical operations**.
2. **Only changes made while a transaction is open are captured.** No open transaction (the headless default) → nothing recorded (`Document.cpp:292, 912`). Silent.
3. **Nothing recorded during undo/redo/rollback** (`isPerformingTransaction()` gate: `d->undoing || d->rollback`, `Document.cpp:283, 3425, 3557`).
4. **Property restore is best-effort and swallows exceptions.** `applyChn` wraps `Paste` in try/catch and only logs `FC_ERR("exception while restoring …")` (`Transactions.cpp:374-385`); a failed restore leaves that property *un-restored* and does **not** abort the undo. A partial, silent restore is possible.
5. **Redo silently destroyed** by opening a new transaction (`_clearRedos`, `Document.cpp:399`); **oldest undo silently dropped** past 20 steps.
6. **Undo history is in-memory only** — `Transaction::Save/Restore` are `assert(0)` stubs (`Transactions.cpp:115-123`). It does not survive save/reload.
7. **Dynamic-property fragility** — removed+recreated dynamic props are matched by *name*, may be re-created, type mismatches deliberately not enforced (`Transactions.cpp:328-373`).

### 1.6 Undo × recompute

**Recompute is skipped during undo/redo** (`Document::recompute` bails when `d->undoing || d->rollback`: `FC_WARN("Ignore document recompute on undo/redo")`, `Document.cpp:2840-2845`). Undo pastes stored property values; it does **not** recompute. After undo, objects flagged `PendingTransactionUpdate` get `onUndoRedoFinished()` called (`Document.cpp:214-219, 264-269`), then `signalUndo` fires.

> **Design rule #2:** After a programmatic undo/abort, **explicitly call `Document.recompute()`** before hashing/verifying, so derived geometry is brought current. Verify the recompute returns clean (no errored objects) as part of rollback success.

---

## Part 2 — Deterministic Geometry Hashing (what to hash)

### 2.1 The requirement, precisely

We need a **fingerprint of document geometry state** such that:
- capturing it before a mutation and after a rollback yields **identical** values iff the geometry was restored (the Phase 2 "verified by geometry hash" clause), and
- it is **deterministic within a single process/run for an unchanged shape** (the exact undo case), and ideally stable enough to serve as a golden reference.

Note the scope: we are verifying that undo restored *the same representation*, not proving two independently-built shapes are geometrically equivalent. That distinction decides which candidate wins.

### 2.2 Candidate A — BRep binary bytes (RECOMMENDED primary)

`src/Mod/Part/App/TopoShape.cpp` exposes a true **binary** BRep export:

```cpp
// TopoShape::exportBinary(std::ostream& out)  ~line 964
BinTools_ShapeSet theShapeSet;
theShapeSet.SetFormatNb(BinTools_FormatVersion_VERSION_3);
Standard_Integer shapeId = theShapeSet.Add(this->_Shape);
Standard_Integer locId   = theShapeSet.Locations().Index(this->_Shape.Location());
Standard_Integer orient  = static_cast<int>(this->_Shape.Orientation());
theShapeSet.Write(out);
BinTools::PutInteger(out, shapeId); /* locId; orient */
```

Location and orientation are serialized explicitly (`~985-993`); the inverse `importBinary` (~825) re-applies them. There is also ASCII `exportBrep(std::ostream&)` (~948) using `BRepTools_ShapeSet`; both **exclude triangulation** (OCC ≥ 7.6 format flags pin `TopTools_FormatVersion_VERSION_1`, triangles/normals off — `exportBrep(filename)` ~929-940).

**Determinism analysis (from OCCT behavior + code):**
- `BinTools_ShapeSet::Add` builds the shape set by **recursive topological DFS** over `TopoDS_Iterator`, assigning IDs in **traversal order**. The children list is an ordered `TopTools_ListOfShape`; order does **not** depend on pointer values. **For the same in-memory `TopoDS_TShape` that was not rebuilt — exactly the undo-restore case — re-serialization is byte-identical.**
- OCCT's `HashCode` (pointer/`TShape`-based, `ShapeMapHasher.h:43`; `WireJoiner.cpp:2742` prints `shape.TShape().get()`) is **not** run-stable — **but it is never written into the byte stream** (IDs are positional). So that non-determinism does not leak into the hash.
- Location indices are assigned in encounter order → stable for a fixed shape. Raw doubles are written verbatim (no tolerance rounding) → identical in-memory doubles ⇒ identical bytes.
- **Caveat (accepted):** two *geometrically equal but independently rebuilt* shapes (different vertex ordering / parameterization / ULP-level doubles) can hash differently. For **undo verification this is correct behavior** — undo restores the same representation, so equal-representation is exactly the property we want to assert.

**Precedent:** FreeCAD's own dev tool `src/Tools/fcinfo` already SHA-1s serialized shape bytes. No content-hash API exists on `TopoShape`/`ComplexGeoData` (the only `hashCode()` on `TopoShapePyImp.cpp:1721` is the non-stable OCCT pointer hash), so we build it: **SHA-256 over `exportBinary()` output per shape-bearing object.**

### 2.3 Candidate B — mass-property tuple (RECOMMENDED as fast pre-check / cross-oracle)

`TopoShape.cpp` offers canonical, order-independent scalars: `getBoundBox()` (~1130, `BRepBndLib::Add`), volume/area/length + center of mass via `getShapeProperties()` (~1180, `BRepGProp`), `getCenterOfGravity()` (~1224), plus inertia/principal moments (Python `getMatrixOfInertia`, `getPrincipalProperties`).

Tuple `{volume, area, bbox(6), centerOfMass(3), principalMoments(3)}` **rounded to a fixed tolerance** is robust (invariant to how the shape was built, order-independent) but **lossy** (distinct shapes can collide) and requires float quantization (last ULPs may differ across CPU/parallel BLAS). **Use as a cheap pre-filter and as an independent cross-check on the BRep hash — not as the sole oracle.**

### 2.4 Candidate C — document XML / FCStd whole-file hash (REJECT)

`Document::Save` (`Document.cpp:1097`) embeds **build-version strings** and, per object, **random UUIDs** (`Base::Uuid::createUuid()`, e.g. `Document.cpp:1335`), a session-specific **TransientDir**, and the whole thing is a **zip** carrying file **timestamps**. Object order is deterministic, but the incidental metadata churn (uuids, transient dir, build header, zip mtimes) defeats a whole-file/whole-XML hash for "geometry unchanged." Reject.

### 2.5 Candidate D — tessellation mesh hash (REJECT for identity)

`TopoShape::tessellate` → `getFaces` runs `BRepMesh_IncrementalMesh(..., isInParallel = true)` (`TopoShape.cpp:~3671`) with a **bbox-derived default deflection** (`getAccuracy`, ~3647) that self-changes if the bbox changes. Parallel, non-contractually-deterministic meshing → vertex/facet order and counts can vary for the same shape. Reject for identity; at best a coarse quantized fingerprint.

### 2.6 Ranking

| Rank | Approach | Determinism (unchanged shape, same run) | Verdict |
|------|----------|------------------------------------------|---------|
| 1 | **BRep binary → SHA-256** (`exportBinary`) | Byte-identical; captures topology+geometry+location+orientation | **Primary oracle** |
| 2 | **Mass-property tuple** (quantized) | Canonical, order-independent; lossy | **Fast pre-check + cross-oracle** |
| 3 | Document XML / FCStd hash | Defeated by uuids/build-version/zip mtimes | Reject |
| 4 | Tessellation mesh hash | Parallel, param-dependent, non-deterministic | Reject for identity |

---

## Part 3 — Recommended Rollback + State-Verification Mechanism (Phase 2)

The mechanism combines FreeCAD's transaction as the *fast* rollback with an independent hash as the *verifier* and a saved snapshot as the *guaranteed* fallback — because §1.5 proves undo is not 100% trustworthy on its own.

### 3.1 Document geometry fingerprint (the "geometry hash")

```
def document_geohash(doc) -> str:
    entries = []
    for obj in sorted(doc.Objects, key=lambda o: o.Name):   # deterministic order
        shape = getattr(obj, "Shape", None)
        if shape is None or shape.isNull():
            continue
        buf = io.BytesIO()
        shape.exportBinary(buf)            # TopoShape::exportBinary → OCCT BinTools VERSION_3
        h = hashlib.sha256(buf.getvalue()).hexdigest()
        mp = _massprops(shape)             # (V, A, bbox6, com3, moments3), rounded to 1e-6
        entries.append((obj.Name, h, mp))
    return hashlib.sha256(repr(entries).encode()).hexdigest()
```

- Primary equality = per-object BRep SHA-256 (§2.2); the rounded mass-property tuple travels alongside as an independent cross-oracle and human-readable diff aid (§2.3). Sort by `obj.Name` for order-independence.
- Verify `exportBinary` is exposed to Python in the pinned build; if not, fall back to `exportBrep(stream)` (ASCII) — same determinism argument. (Confirm during Phase 0 tool bring-up.)

### 3.2 The mutation transaction (per AI operation)

```
h_before = document_geohash(doc)                 # (A) independent pre-state fingerprint

doc.openTransaction("AI: <command>")             # Design rule #1 — REQUIRED headless
try:
    apply_typed_mutation(doc, op)                # no free-form exec in mutation path (intent risk row)
    doc.recompute()                              # bring derived geometry current
    ok, report = post_verify(doc, op)            # recompute clean? shape valid? DoF? TNP re-resolve?
except Exception as e:
    ok, report = False, structured_error(e)

if ok:
    doc.commitTransaction()
else:
    rollback(doc, h_before)                       # see 3.3
```

`post_verify` implements the intent's Phase 2 checks deterministically: recompute returned no errored objects, `Shape.isValid()` / watertight, sketch `DoF == 0` where applicable, and the **TNP guard** (all existing feature references re-resolve). Any failure ⇒ rollback + human-readable explanation.

### 3.3 Rollback with verification (the core guarantee)

```
def rollback(doc, h_before):
    doc.abortTransaction()          # fast path: reverse-apply active transaction (§1.4)
    doc.recompute()                 # undo skips recompute (§1.6) — must redo it
    if document_geohash(doc) == h_before:
        return "rolled_back_verified"
    # abort/undo did NOT restore exact state (bug #6031 class of failure)
    restore_from_snapshot(doc, h_before)   # guaranteed fallback (§3.4)
    assert document_geohash(doc) == h_before, "ROLLBACK FAILED — geometry hash mismatch"
    return "rolled_back_via_snapshot"
```

This is what makes criterion #3 ("undo restores previous state exactly, verified by geometry hash, 100%") *provable* rather than *assumed*: we do not claim rollback succeeded because `abortTransaction()` returned — we **re-hash and compare**. If FreeCAD's undo hits the #6031 boundary bug and leaves a stray object, the hash mismatches and we escalate to the snapshot restore, then re-verify.

### 3.4 Guaranteed fallback — saved-document snapshot

Because undo is in-memory-only (§1.5 #6), best-effort on restore (§1.5 #4), and has a real boundary bug (§1.5 #1), keep a **hard snapshot** for every mutation:

- Before the transaction, `doc.saveCopy(tmp_path)` (or save to an in-memory FCStd) — a full serialized document.
- On rollback-hash-mismatch, close and reopen from `tmp_path` (or `Document.restore()`), then re-hash to confirm.

This is slower, so it is the fallback, not the default path — but it is the only mechanism that is *guaranteed* to restore exact geometry state, and it backstops the 100% requirement. (Snapshot bytes differ due to uuids/zip mtimes — §2.4 — which is why the **verifier is the geometry hash, not file equality**.)

### 3.5 Validating the validator (intent's "validate the validator" mandate)

The Validation Design Gate requires the rollback/hash mechanism itself be fault-tested before Phase 2 code:

- **Fault injection for the hash:** mutate one dimension by 1 µm, delete/add a hole, mirror a part → the geohash MUST differ (sensitivity ≥ 95%). Feed known-good round-trips (export→reimport of the *same* shape within a run) → geohash MUST match (false-alarm ≤ 5%).
- **Fault injection for rollback:** deliberately reproduce the #6031 pattern (nested transaction / sketch-on-plane) → confirm the hash-mismatch path fires and the snapshot fallback restores exact state.
- **Determinism check:** hash the same unchanged document N times in one process → identical (guards against accidental non-determinism, e.g. object ordering or a stray triangulation flag).
- **Cross-oracle agreement:** BRep-hash equality and quantized mass-property equality must agree on the benchmark; disagreement is a validator bug to investigate.

---

## Key Findings & Recommendation (summary)

1. **Undo is not free headless.** There is no App-level undo default; `FreeCADCmd` records nothing unless the bridge calls `openTransaction`/`commitTransaction` itself (`Document.cpp` `_checkTransaction`; `DocumentPyImp.cpp:982-988` shim). **Design rule #1.**
2. **Undo cannot be trusted blindly.** Real bug #6031/#4265 ("undo doesn't restore the state before openTransaction"), best-effort exception-swallowing restore (`Transactions.cpp:374-385`), 20-step silent cap, in-memory-only history. The intent's "verify, don't trust" applies to rollback itself.
3. **Undo skips recompute** (`Document.cpp:2840`) — always `recompute()` after abort/undo before verifying. **Design rule #2.**
4. **Hash the BRep binary bytes.** `TopoShape::exportBinary` (OCCT `BinTools_ShapeSet` VERSION_3) is byte-deterministic for an unchanged shape (positional IDs, no pointer-hash in the stream); SHA-256 it per object. Reject document-XML/FCStd hashing (uuids, zip mtimes) and tessellation (parallel, non-deterministic).
5. **Recommended mechanism:** per-operation `openTransaction` → typed mutation → `recompute` → deterministic `post_verify` → on success `commit`, on failure `abortTransaction` + `recompute` + **re-hash to verify rollback**, escalating to a **saved-document snapshot restore** whenever the geohash does not match `h_before`. This makes Phase 2 criteria #2 and #3 *verified*, not assumed, and is fully headless-compatible.

---

## Sources

**Primary (local FreeCAD source, `docs/references/FreeCAD/`):**
- `src/App/Document.cpp` — undo/redo, `_openTransaction`/`_commitTransaction`/`_abortTransaction`, `_checkTransaction`, recompute-skip (~2840), save/uuid.
- `src/App/Transactions.cpp` / `.h`, `src/App/TransactionalObject.*`, `src/App/private/DocumentP.h`, `src/App/DocumentPyImp.cpp` (UndoMode shim ~982-988), `src/App/TransactionDefs.h`.
- `src/Mod/Part/App/TopoShape.cpp` (`exportBinary` ~964, `exportBrep` ~929/948, `getBoundBox`/`getShapeProperties`/`getCenterOfGravity`, `tessellate`/`getFaces` ~3657) and `TopoShapePyImp.cpp` (~1721 pointer hashCode).
- `src/Tools/fcinfo` (precedent: SHA-1 over serialized shape bytes).

**Secondary (web, corroboration):**
- FreeCAD issue #6031 — "Undo doesn't restore the state as it was before opening a transaction": https://github.com/FreeCAD/FreeCAD/issues/6031 (mirror: FreeCAD tracker #4265).
- FreeCAD DeepWiki — Transactions and Undo/Redo: https://deepwiki.com/FreeCAD/FreeCAD/2.3-transactions-and-undoredo
- App::Document class reference: https://freecad.github.io/SourceDoc/d8/d3e/classApp_1_1Document.html
- OCCT BRep binary format / BinTools changes (7.6.0): https://unlimited3d.wordpress.com/2021/09/08/xcaf-b-rep-changes-in-occt-7-6-0/ and OCCT BRep format spec: https://dev.opencascade.org/doc/occt-7.5.0/overview/html/specification__brep_format.html
