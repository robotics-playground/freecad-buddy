---
title: 'Story 9.4: Temp Files the Sweep Can See'
type: 'feature'
created: '2026-09-13'
status: 'done'
baseline_revision: '306aa7bd569a3faacbe2ece8585730a6959bcf4f'
review_loop_iteration: 0
followup_review_recommended: false
context:
  - '{project-root}/_bmad-output/implementation-artifacts/epic-9-context.md'
warnings: [scope-larger-than-epic]
deferred: []
---

<intent-contract>

## Intent

**Problem:** Every temp file the bridge writes lands in the OS temp directory. `screenshot.py:172`
and `fingerprint.py:73` both call `tempfile.mkstemp` with no `dir=`, so their output falls outside
any tree the bridge owns. R2-04 counted 392 orphaned `FCB_TMP_shot_*` files across already-exited
sessions; the directory holds **500** today. Separately, `transaction.py` removes a snapshot's
files, then catches `OSError` on the directory removal and passes, so empty `FCB_TMP_snap_*`
directories survive silently.

**Scope note, verified before planning:** AD-25 specifies a session-scoped workdir
(`snap/`, `exports/`, `audit.log`, `tmp/`) and a session-start sweep, and **neither exists in the
code**. A search of `src/` for `workdir`, `session_root`, `artifact_dir` and any sweep returns
nothing. So this story builds the workdir and the sweep, then redirects the temp files into them —
it is not the one-line `dir=` change the epic's AC1 reads like.

**Approach:** Introduce the session workdir owned by the documents use case, add the session-start
sweep scoped to exactly that directory, pass `dir=` at both `mkstemp` sites, and surface the
swallowed cleanup failure instead of discarding it.

## Boundaries & Constraints

**Always:**
- Every temp file the bridge creates is created **inside the session workdir** (`<workdir>/tmp`).
- The sweep's scope stays **exactly the session workdir**. It must never scan the OS temp
  directory: on a shared or multi-user host that is another session's territory, and deleting from
  it would break the guarantee that a caller may still be reading a returned link.
- The sweep runs at **session start**, never as an immediate unlink, because a render link may
  still be being read when the call returns.
- The reserved `FCB_TMP_` prefix marks **files only**. `FCB_TMP_prev_`, `FCB_TMP_varset_probe`,
  `FCB_TMP_partdesign_probe` and `FCB_TMP_type_probe` name **in-memory FreeCAD documents**,
  released with `closeDocument`, and must never be handed to `unlink`. A sweep written against
  "every reserved prefix" fails on the first probe document it meets.
- A swallowed cleanup failure must still leave the artifact **sweepable at next session start**
  rather than orphaned, and the failure must be **logged** so the next occurrence is diagnosable.
- Pre-existing strays outside the workdir are a one-time operator cleanup, never a bridge
  responsibility. Do not delete them.

**Never:**
- Do not scan or delete anything in the OS temp directory, under any flag.
- Do not convert the swallowed `OSError` into a raised exception that fails a completed mutation.
  Cleanup failure is reported, not fatal.
- Do not unlink any path whose basename matches an in-memory-document prefix.
- Do not change the export path contract: an explicit operator-supplied export path is written
  where the operator said, outside the workdir.
- Do not make the workdir location an unconfigurable constant baked into a use case; the audit log
  already reads `FREECAD_BUDDY_AUDIT_LOG`, so follow that precedent for overridability.

## I/O & Edge-Case Matrix

| Scenario | Input / State | Expected Output / Behavior | Error Handling |
|----------|--------------|---------------------------|----------------|
| Render temp | `query_screenshot` runs | PNG created under `<workdir>/tmp`, not OS temp | No error expected |
| Fingerprint temp | A fingerprint is computed | Temp created under `<workdir>/tmp` | No error expected |
| Sweep at start | Prior session's files remain in `<workdir>/tmp` | Removed at next session start | Failures logged, not raised |
| Sweep scope | OS temp holds `FCB_TMP_*` strays | **Untouched** | Out of scope by contract |
| Probe documents | `FCB_TMP_prev_` etc. are open documents | Never passed to `unlink` | Closed via `closeDocument` only |
| Snapshot rmdir fails | Directory removal raises `OSError` | Failure logged; directory still sweepable next start | Not raised to the caller |
| No workdir yet | First run on a clean machine | Workdir created; sweep finds nothing | Creation failure is a stated reason |

</intent-contract>

## Code Map

- `src/freecad_buddy/usecases/documents.py` -- AD-25 names the documents use case as the workdir's
  owner. There is **no** `workdir` symbol here today; the accessor and the session-start sweep are
  new. `DocumentRegistry` and `with_document():155` are the existing shapes to fit alongside.
- `src/freecad_buddy/usecases/screenshot.py:172` --
  `fd, out_path = tempfile.mkstemp(prefix="FCB_TMP_shot_", suffix=".png")`, no `dir=`. One of the
  two leak sites; `is_default_renderable():51` in the same module is unrelated and read-only here.
- `src/freecad_buddy/usecases/fingerprint.py:73` --
  `fd, path = tempfile.mkstemp(prefix="FCB_TMP_fp_", suffix=".bin")`, no `dir=`. The second leak
  site.
- `src/freecad_buddy/usecases/transaction.py:39` -- `_SNAPSHOT_PREFIX = "FCB_TMP_snap_"`.
  `:105-118` is the cleanup: it removes the directory's files, then `os.rmdir(directory)` inside a
  `try` whose `except OSError: pass` is the silent-orphan path. The non-snapshot branch at
  `:107-111` swallows its own `os.remove` failure the same way.
- `src/freecad_buddy/usecases/preview.py:33` -- `_TEMPDOC_PREFIX = "FCB_TMP_prev_"`, an **in-memory
  document** prefix. This is the class the sweep must never unlink; grep the tree for the other
  three (`varset_probe`, `partdesign_probe`, `type_probe`) and treat them the same.
- `src/freecad_buddy/adapters/audit_log.py:23` -- reads `FREECAD_BUDDY_AUDIT_LOG` with a
  cwd-relative default. The shipped precedent for an overridable artifact location; follow it
  rather than inventing a second convention.
- `src/freecad_buddy/usecases/exports.py:11` -- re-imports a written STEP into a fresh `FCB_TMP_`
  **document** for verification. Another in-memory case to keep away from `unlink`.
- `src/freecad_buddy/hosts/gui_addon/bootstrap.py` -- where the GUI session starts; the
  session-start sweep needs a call site here and in the headless host. Read both before choosing.

## Tasks & Acceptance

**Execution:**

- `src/freecad_buddy/usecases/documents.py` -- add the session workdir: an accessor returning the
  session-scoped root, creating `tmp/` on demand, overridable by environment variable following the
  `FREECAD_BUDDY_AUDIT_LOG` precedent -- AD-25 gives the documents use case ownership and nothing
  implements it yet.
- `src/freecad_buddy/usecases/documents.py` -- add the session-start sweep over exactly
  `<workdir>/tmp`, removing files only and never recursing outside the workdir; log each failure
  rather than discarding it -- the sweep is what makes a session-scoped temp file self-cleaning.
- `src/freecad_buddy/usecases/documents.py` -- make the sweep treat `FCB_TMP_` as marking **files**:
  it walks a directory of real files, so an in-memory-document name can never reach it. Assert that
  in a test rather than relying on the directory's contents to stay lucky.
- `src/freecad_buddy/usecases/screenshot.py` -- pass `dir=` to the `mkstemp` at `:172` so renders
  land in `<workdir>/tmp` -- this is the site that produced the 392 orphans R2-04 counted.
- `src/freecad_buddy/usecases/fingerprint.py` -- pass `dir=` to the `mkstemp` at `:73` for the same
  reason.
- `src/freecad_buddy/usecases/transaction.py` -- surface the swallowed cleanup failure: log the
  `OSError` from the snapshot directory removal (and the non-snapshot `os.remove`) instead of
  `pass`, and leave the artifact inside the workdir so the next session's sweep reaches it -- a
  silently orphaned directory is undiagnosable, which is why 10 of them survived.
- `src/freecad_buddy/hosts/` -- call the sweep once at session start from the GUI addon bootstrap
  and from the headless host, so both hosts honour the contract.
- `tests/external/` -- cover the matrix: both temp files land under the workdir, the sweep clears
  the previous session's files, the sweep leaves an OS-temp stray untouched, an in-memory-document
  name is never unlinked, and a failing `rmdir` logs and leaves the directory sweepable.

**Acceptance Criteria:**

- Given a render and a fingerprint, when each creates its temp file, then the path is under the
  session workdir and no new file appears in the OS temp directory.
- Given files left in `<workdir>/tmp` by a prior session, when a session starts, then they are
  removed.
- Given a `FCB_TMP_*` file in the **OS** temp directory, when the sweep runs, then that file still
  exists -- the sweep never reaches outside the workdir.
- Given a name matching an in-memory-document prefix, when the sweep runs, then `unlink` is never
  called with it.
- Given a snapshot directory whose `rmdir` raises, when cleanup runs, then the failure is logged,
  the call does not raise, and the directory is still removable at next session start.
- Given `grep -n "mkstemp" src/freecad_buddy/usecases/*.py`, when the change is done, then every
  hit passes a `dir=` argument.

## Verification

**Commands:**
- `uv run ruff check <the changed files>` -- expected: clean.
- `uv run pytest -q` -- expected: no new failures; stories 9.1-9.3 stay green.
- `uv run python scripts/check_imports.py` -- expected: clean.
- `grep -n "mkstemp" src/freecad_buddy/usecases/*.py` -- expected: every hit carries `dir=`.

**Manual checks (if no CLI):**
- The live-GUI reproducer (R2-04) is a UAT step: count `FCB_TMP_*` in the OS temp directory, run N
  renders through the bridge, and count again. The count must not grow. Then restart the session
  and confirm the workdir's own `tmp/` is empty. The 500 pre-existing strays are operator cleanup
  and must **not** be deleted by the bridge.
