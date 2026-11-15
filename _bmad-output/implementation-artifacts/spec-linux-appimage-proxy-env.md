---
title: 'Linux AppImage: GUI addon MCP proxy starts and pins its FreeCAD'
type: 'bugfix'
created: '2026-11-15'
status: 'done'
route: 'oneshot'
review_loop_iteration: 0
context: []
---

<frozen-after-approval reason="human-owned intent — do not modify unless human renegotiates">

## Intent

**Problem:** The FreeCAD 1.1.4 Linux AppImage `AppRun` exports `PYTHONHOME=${HERE}/usr`. The GUI addon starts the MCP proxy and the `uv` provisioning steps with FreeCAD's whole environment (`bootstrap.py:498`, `managed_venv.py` `_run`). The external venv interpreter then reads FreeCAD's bundled standard library and stops: `Fatal Python error: Failed to import encodings module`. No MCP endpoint comes up. Container `fcb-desktop` reproduced this, and the same venv python starts once `PYTHONHOME` is removed.

**Approach:** Children that the addon starts in the background get FreeCAD's environment without `PYTHONHOME` and `PYTHONPATH`. These two variables point at FreeCAD's own interpreter and never apply to an external one. One shared change covers both the proxy spawn and the `uv` runs. A test starts a real child interpreter with a bogus `PYTHONHOME` to reproduce the defect.

**Decision (owner, 2026-11-15):** this spec also fixes the second Linux defect. With `APPDATA` and `XDG_DATA_HOME` unset, `rpc_client._appdata_dir` returns `~/.local/share` before it probes `FreeCAD/v*`, while the listener writes `~/.local/share/FreeCAD/v1-1/freecad-buddy/rpc-<pid>.json`; the proxy pins `None` and every tool call fails. The client uses `~/.local/share` as the base and still probes `FreeCAD/v*`. Done when a real MCP tool call through the container relay succeeds.

</frozen-after-approval>

## Code Map

- `src/freecad_buddy/hosts/gui_addon/managed_venv.py` -- `no_window_kwargs`: shared Popen kwargs for the proxy spawn and the uv runs; now strips `_FREECAD_PYTHON_VARS`.
- `src/freecad_buddy/adapters/rpc_client.py:40-62` -- `_appdata_dir`: on Linux with `APPDATA` and `XDG_DATA_HOME` unset it returns `~/.local/share` before the `FreeCAD/v*` probe.
- `src/freecad_buddy/adapters/rpc_listener.py:58-72` -- `_appdata_dir`: writes discovery under `FreeCAD.getUserAppDataDir()` (`~/.local/share/FreeCAD/v1-1/` on Linux). Not changed.
- `tests/external/test_managed_venv.py` -- two new tests (real child with bogus PYTHONHOME; operator variables kept).

## Implementation Notes

- Change point: `managed_venv.no_window_kwargs`. Both background-child call sites already build their `Popen` kwargs there (`bootstrap._spawn_mcp_proxy`, `managed_venv._run`).
- Every other variable is kept, because the proxy reads the operator settings that `bootstrap` writes into `os.environ`.
- PYTHONHOME fix done and verified: tests red then green (30 pass); in container `fcb-desktop` the proxy now answers `/healthz` 15 s after FreeCAD start, also from the host via `127.0.0.1:18765`.
- Replan trigger: the proxy log says `pinned to FreeCAD pid None` while the listener wrote `~/.local/share/FreeCAD/v1-1/freecad-buddy/rpc-174.json`. `rpc_client._appdata_dir` never probes `FreeCAD/v*` when `XDG_DATA_HOME` is unset. That is a second defect outside the frozen intent.
- Not in scope either way: macOS (`~/Library/Application Support/FreeCAD`) is also not probed by `rpc_client._appdata_dir`; unverified, no macOS host.
- Discovery fix done: `rpc_client._appdata_dir` uses `~/.local/share` as the base when `APPDATA` and `XDG_DATA_HOME` are unset, and still probes `FreeCAD/v*`. Test red then green. In container `fcb-desktop` the proxy pins its FreeCAD (`freecad_pid` set in `/healthz`), and a real tool call through the relay succeeds: `tests/close-loop/journey_box.py` PASS with screenshot read.
- Close-loop harness: `tests/close-loop/` (Docker image, helpers, journey, README). Falsified with `FREECAD_BUDDY_SCRIPT_EXEC=0`: FAIL with a fresh screenshot.

## Review Triage Log

Blind Hunter, one pass, 14 findings:
- medium, patched: `no_window_kwargs` docstring said AppRun sets `PYTHONPATH`; AppRun sets only `PYTHONHOME`. Docstring corrected.
- low, patched: no assert that `PYTHONPATH` is stripped. Assert added.
- low, deferred: strip also applies to the verbatim `FREECAD_BUDDY_MCP_CMD` route, undocumented; the fix edits CLAUDE.md section 16.
- low, patched: `_appdata_dir` comment described Windows only. The `v*` string sort existed before this change: deferred.
- low, rejected: no test for the `XDG_DATA_HOME`-set and no-FreeCAD-folder branches; the change touched only the unset-base line, and `monkeypatch` restores `Path.home` after the test.
- medium, patched: `ARG ADDON_VERSION=0.1.1` would install a stale zip after a version bump. The image now copies the current `dist/addon/` release tree and stops when it has no `wheels/`.
- medium, patched: a screenshot left in the container could be measured as the current run's. Deleted before capture; a missing file is a FAIL. Verified by a falsified run with the old PASS screenshot present.
- medium, patched: comments claimed cua-driver reads FreeCAD widgets over AT-SPI. Comments now match the measurement; the no-effect `QT_*ACCESSIBILITY` exports removed.
- medium, patched: README relied on the git-ignored `.mcp.json`. README now carries the two JSON entries.
- medium, patched: the journey left an unsaved document, so `fcb-freecad stop` ended in a kill. The journey closes it; verified `stop` closes gracefully, `bridge stopped` logged, no `rpc-*.json` left.
- low, patched: `_cua` spliced JSON into shell text. Now positional arguments; a missing JSON reply raises a clear error.
- low, patched: deprecated `streamablehttp_client`. Now `streamable_http_client`.
- low, deferred: `tests/close-loop/` missing from the documented test layout; the fix edits the design doc and CLAUDE.md.
- low, patched: README held dated run records. Dates removed.
