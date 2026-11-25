# Story 13-5 triage: round 2 (verifier + red team)

Base: 3527cc2 on `story/13-5-multi-object-export`. Sources (this folder): `verify-13-5.md` (D-1, low L-1), `redteam-13-5.md` (RT-1 .. RT-8). Use their reproductions as the failing tests.

| Id | Source | Required fix |
| --- | --- | --- |
| D-1 (high) | verifier, container UAT | Multi-object 3MF written in the GUI host is not a valid 3MF: GUI FreeCAD adds one thumbnail per mesh (`Mesh/Gui/ThumbnailExtension.cpp:105-111`) and `Writer3MF.cpp:206-207` writes one `<Default Extension="png">` per thumbnail; lib3mf refuses "A content type is duplicated". In the post-write rewrite (`exports.py` ~:407, which today copies `[Content_Types].xml` unchanged), de-duplicate `Default` entries by `Extension` in `[Content_Types].xml`. Add a test with a fixture archive that has duplicate `Default` lines (headless FreeCAD cannot produce it) and prove lib3mf reads the fixed file. Regression: one-object 3MF unchanged. |
| RT-1 (high) | red team | Default selection (omitted `objects`): a hidden Body hides its tip feature too — a feature inside a Body counts as visible only through its Body (GUI: hiding a Body does not set feature visibility, `ViewProviderGeoFeatureGroupExtension.h:63-70`). Test: Part Cut of two Bodies exports only the Cut. |
| RT-2 (medium) | red team | Default selection: a visible `Part::Mirroring` source is not "consumed"; export it with the mirror. Re-check the consumed rule against FreeCAD source for which features hide/consume their inputs (the GUI command, not the link). Test. |
| RT-3 (medium) + RT-6 (low) | red team | 3MF name: lib3mf rejects every numeric character reference and raw control characters break the XML. Replace or drop control characters (`\x00-\x1f`, incl. tab/newline) in the `name` attribute (e.g. with a space) and escape only `& < > "`. Fix the test at `test_exports_3mf_names.py:104` to read the file back with lib3mf, not compare strings. |
| RT-4 (medium) | red team | Two objects sharing one shape (simple copy, `App::Link`) get the same STEP product name. Each object's `Label` must be its product name (T-5 STEP row). Fix so each object gets its own product, or — if OCCT cannot separate shared shapes — make the product name unique per object and record the decision in the spec. Test. |
| RT-5 (medium) | red team | Selecting an `App::Part` with a hidden child writes the hidden child to STEP (more solids than recorded, verify always fails, names the wrong object). The recorded solids and the written shape must come from the same rule (export only visible children, or record hidden ones too — choose the rule the GUI export uses and state it). Test. |
| RT-7 (low) | red team | A compound with a solid plus a loose face: the face becomes a 0-solid product and the per-object volume check compares against `Shape.Volume` of the mixed compound. Use the solids' volume for the per-object check. BooleanFragments `topology_counts` failure is pre-existing on the single path: leave it, note in spec. |
| L-1 (low) | verifier | `verify_export_step` never reads the STEP product names, although decision 20 asks for a name check. Add a per-object product-name check in `verify_export_step`. |

## Not fixed, with the reason

- RT-8 (low): OCCT writes non-ASCII Labels as raw UTF-8, not ISO 10303-21 `\X2\`. FreeCAD reads it back correctly; fixing the encoding is inside the OCCT writer. Leader records it in `deferred-work.md`.

## After the fixes

1. Commit on your branch (no trailer).
2. The product change is large (two highs, four mediums): run `bmad-build`'s three lenses again as fresh subagents (round 2) on 3527cc2..HEAD with `quality-bar-13-5.md` (this folder). Patch high/medium; commit.
3. Run `uv run pytest tests/external -q` and the infc suite; reply with SHA, lens ids, counts in at most 10 lines. The verifier re-runs the container UAT afterwards.
4. Apply the verifier's case change `tests/uat/run/13-5-r1/tc07-case-change.diff` (main repo path) to `tests/uat/testcases/TC-07-verification-and-export-pairing.md` in your branch, and add a step for the GUI multi-object 3MF.
