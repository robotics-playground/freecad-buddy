---
title: 'Release 0.0.1: installable addon, preferences page, Claude plugin, release workflow'
type: 'feature'
created: '2026-10-09'
status: 'done'
route: 'dispatch'
baseline_commit: '489d53b955d2f6fa338bd685c121eed1b51034cf'
review_loop_iteration: 0
context:
  - '{project-root}/_bmad-output/planning-artifacts/architecture/architecture-freecad-buddy-2026-07-21/design/integration-mcp-freecad.md'
  - '{project-root}/_bmad-output/planning-artifacts/architecture/architecture-freecad-buddy-2026-07-21/design/security-and-service-design.md'
---

<frozen-after-approval reason="human-owned intent — do not modify unless human renegotiates">

## Intent

**Problem:** FreeCAD Buddy works only from a cloned repo. The addon finds the MCP proxy through the repo `.venv`. Operators configure it with `FREECAD_BUDDY_*` env vars. The audit log and the workdir default to cwd-relative paths, so a Start-menu launch (cwd `Program Files\...\bin`) fails every mutation. There is no LICENSE, no product README, no plugin and no release.

**Approach:** Ship 0.0.1 as a normal FreeCAD addon zip:
- The zip bundles the wheel. On first start the addon uses `uv` to provision a private venv for the MCP proxy.
- Operators configure the addon on the Edit > Preferences page.
- A Claude Code marketplace in this repo installs only `skills/` plus the MCP HTTP entry.
- release-please on `main` publishes `v0.0.1` with the wheel, the sdist and the addon zip.
- The README is rewritten as a product README.

**Decisions (human, 2026-10-09):**
- D1: The license is MIT, holder TanNT.
- D2: The repo stays PRIVATE. There is no PyPI publish. The README states that installs need repo access.
- D3: Precedence is: env var set → env wins → preference → default. Operator settings are read once at bridge start. `RoundToDisplay` stays per call.
- D4: The released addon requires `uv`. The addon zip bundles the wheel and provisions `<UserAppData>/FreeCADBuddy/venv`.
- D5: Skills stay in the repo root `skills/`. The plugin source is `./skills`, so the plugin cache gets only that folder. The plugin also registers `freecad-buddy` → `http://127.0.0.1:8765/mcp`.
- D6: The release-please PR is merged by the user. Enabling "Allow GitHub Actions to create pull requests" is also a user action.

## Boundaries & Constraints

**Always:**
- AD-1 rings hold, and `scripts/check_imports.py` passes.
- `mcp` is never imported inside FreeCAD's interpreter (AD-12).
- New modules that pytest must import stay stdlib-only, with no Qt and no FreeCAD at import time.
- The dev setup keeps working unchanged: a repo junction or a `build_addon.py` copy with a marker finds the repo `.venv` first.
- A failed proxy spawn or provisioning never breaks the RPC listener or the GUI start.
- Provisioning never blocks the Qt main thread and never touches Qt.

**Never:**
- No PyPI publish and no repo-visibility change.
- No commit to `main`.
- No edits to `tests/uat/run/**`, which is recorded evidence.
- No removal of any env var. Env vars stay as overrides.
- No `plugin.json` or other files inside `skills/`.

## I/O & Edge-Case Matrix

| Scenario | Input / State | Expected Output / Behavior | Error Handling |
|----------|--------------|---------------------------|----------------|
| Pref only | AutoApprove pref off, env unset | `FREECAD_BUDDY_AUTO_APPROVE=0` in the overlay; a mutation needs `preview_id` | N/A |
| Env wins | env `AUTO_APPROVE=1`, pref off | overlay omits the key; auto-approve on | N/A |
| Default paths | no env, empty audit pref | audit `<appdata>/freecad-buddy/audit.jsonl`, workdir `<appdata>/freecad-buddy/workdir` | N/A |
| Release install, first start | no repo venv, uv found, wheel bundled, venv absent | background provisioning, then the proxy spawns on `:8765` | uv failure → one log line, listener stays up |
| Upgrade | venv marker ≠ bundled wheel sha | re-provision | same |
| No uv | release install, uv missing | no proxy; one log line naming the preference page | N/A |
| Two instances | two FreeCAD start together | one provisions (lock file), the other skips | stale lock is older than 10 min → ignored |

</frozen-after-approval>

## Code Map

- `src/freecad_buddy/hosts/gui_addon/bootstrap.py` -- `start_bridge` (`:85`). Calls in order: `_configure_file_logging`, `sweep_temp_dir` (uses the workdir), `Capabilities.from_env` (`:97`), `AuditSink(default_audit_path())` (`:120`). Apply the overlay right after logging config, before the sweep. `_discover_external_python` (`:162`), `_mcp_proxy_command` (`:214`), `_start_mcp_proxy` (`:244`), `_no_window_kwargs` (`:282`), `stop_bridge` (`:299`).
- `src/freecad_buddy/hosts/gui_addon/preferences.py` -- the existing page with `RoundToDisplay`. Extend it.
- `src/freecad_buddy/usecases/shim.py:27-28` -- `BUDDY_PARAM_PATH`, `ROUND_TO_DISPLAY_KEY`. Add the key constants and `read_operator_preferences()` here.
- `src/freecad_buddy/usecases/capabilities.py:11-38` -- `AUTO_APPROVE_VARIABLE`, the warning, `from_env`. Keep it env-driven.
- `src/freecad_buddy/usecases/confirm.py:255` -- `"source": AUTO_APPROVE_VARIABLE`. Keep it; it stays true.
- `src/freecad_buddy/adapters/audit_log.py:26`, `usecases/documents.py:42-50` -- the cwd-relative defaults. Do not change them; the overlay sets the env.
- `src/freecad_buddy/hosts/gui_external/entry.py:185` -- the proxy reads caps from the env it inherits. Unchanged.
- `scripts/build_addon.py` -- `build()`, `_INITGUI_SHIM`, `REPO_ROOT_MARKER`. Add the release mode and the zip.
- `tests/external/test_build_addon.py` (pytest), `tests/infc/test_bootstrap_discovery.py` (unittest under FreeCADCmd) -- the test patterns.
- `addon/package.xml`, `src/freecad_buddy/__init__.py`, `pyproject.toml`, `uv.lock` -- the version `0.0.1`.
- `.github/workflows/ci.yml` -- runs `pytest tests/external`. New tests run there automatically.
- Docs that tell operators to set env vars:
  - `README.md`
  - `CLAUDE.md`/`AGENTS.md` §16
  - `.knowledge-base/technical/standards/testing/freecad-gui-e2e-harness.md`
  - `tests/uat/APPENDIX-B-environment-setup.md`, `tests/uat/test-plan.md`, TC-01/05/08/11/16
  - design: `integration-mcp-freecad.md`, `security-and-service-design.md`, `integration-mcp-clients.md`, `project-structure.md`
  - spine AD-10 (`:118`), Config row (`:385`), open-conflict row (`:493`)

## Tasks & Acceptance

**Execution:**
- [x] `src/freecad_buddy/usecases/operator_settings.py` -- new. Frozen `PreferenceValues` (auto_approve=True, allow_exec=False, auto_start_mcp=True, mcp_command="", uv_path="", audit_log_path=""). `resolve_env_overlay(environ, prefs, default_dir)` returns only the missing `FREECAD_BUDDY_*` keys: AUTO_APPROVE, ALLOW_EXEC, NO_AUTO_MCP, MCP_CMD, AUDIT_LOG, WORKDIR. -- one pure, testable precedence rule.
- [x] `src/freecad_buddy/usecases/shim.py` -- key constants plus `read_operator_preferences()`. Defaults when FreeCAD is absent.
- [x] `src/freecad_buddy/hosts/gui_addon/managed_venv.py` -- new, stdlib only:
  - `find_uv`, `bundled_wheel`, `venv_python`, `is_current`, `provision` (lock file, marker).
  - `no_window_kwargs` moves here from bootstrap, so bootstrap and provisioning share it.
- [x] `src/freecad_buddy/hosts/gui_addon/bootstrap.py`:
  - apply the overlay and log the effective settings;
  - command order: MCP_CMD → repo venv → REPO+uv → current managed venv → provision in a daemon thread (cancel event, joined in `stop_bridge`) → none, with one log line.
- [x] `src/freecad_buddy/hosts/gui_addon/preferences.py` -- add the five new fields plus the note "Restart FreeCAD to apply (rounding applies at once)". The AllowExec warning shows in red.
- [x] `src/freecad_buddy/usecases/capabilities.py` -- the warning names the preference.
- [x] `scripts/build_addon.py`:
  - `build(dist_dir, release=False, wheel=None)`: in release mode, the wheel goes in `wheels/` and no marker is written;
  - `package_zip(tree, version)` writes `dist/FreeCADBuddy-<ver>.zip` with top folder `FreeCADBuddy/`;
  - CLI option `--release [--wheel PATH]`.
- [x] `.claude-plugin/marketplace.json` -- the marketplace with one plugin: `source: "./skills"`, `strict: false`, `skills: "./"`, `mcpServers`, `version`, MIT.
- [x] `release-please-config.json`, `.release-please-manifest.json` (`0.0.0`), `.github/workflows/release.yml`:
  - `release-as: "0.0.1"`, `bootstrap-sha` 489d53b955d2f6fa338bd685c121eed1b51034cf, `include-component-in-tag: false`.
  - `extra-files`: `__init__.py`, `package.xml` (generic marker), `marketplace.json` (`$.plugins[0].version`), `uv.lock` (toml).
  - On `release_created`: build the wheel, sdist and addon zip, then `gh release upload`.
- [x] `pyproject.toml` -- `description`, `readme`, `license`, `authors`, `[project.urls]`, and a sdist include list. Add the version markers to `__init__.py` and `addon/package.xml`.
- [x] `LICENSE` -- MIT, 2026, TanNT.
- [x] `README.md` -- product rewrite:
  - pitch and what it does (tool groups, verify-first loop; the export tools return `verified:false`, so pair them with `verify_export_*`);
  - requirements, addon install, connect agents (Claude plugin; `npx skills add` with the skills subpath; MCP snippets for Codex, Cursor, opencode, Gemini CLI, Claude Desktop);
  - Preferences, then env overrides; security, headless, development, license, private-access note.
- [x] Docs in the Code Map -- state current behaviour: preferences first, env overrides, the release install path.
- [x] Tests:
  - `tests/external/test_operator_settings.py`, `test_managed_venv.py`, `test_version_consistency.py`;
  - extend `test_build_addon.py`;
  - `tests/infc/test_bootstrap_settings.py` (the overlay applied before the capability read).

**Acceptance Criteria:**
- Given a release zip extracted into a clean `Mod/FreeCADBuddy` with uv installed, when FreeCAD starts from its install dir, then `:8765/mcp` serves and `feature_body_create` returns `OK` with the audit log under user data.
- Given the repo junction dev install, when FreeCAD starts, then the proxy runs from the repo `.venv` with no provisioning.
- Given the plugin installed from the local marketplace, when a new Claude Code session starts, then 15 skills and the `freecad-buddy` MCP server are listed.
- Given pyproject, `__init__`, package.xml and marketplace.json, when the version test runs, then all four match.

## Implementation Notes

## Spec Change Log

## Review Triage Log

Pass 1 (2026-10-09). Layers: blind-hunter (BH), edge-case-hunter (EC), verification-gap (VG).

| # | Finding | Verdict | Evidence | Route |
|---|---------|---------|----------|-------|
| EC1 | An empty env var counts as set, so it blocks the preference | medium | `operator_settings.py:68` `if key not in environ`. `FREECAD_BUDDY_AUDIT_LOG=""` gives `Path("")` (`audit_log.py:26`). `NO_AUTO_MCP=""` means "start" for the host (`bootstrap.py` truthiness) but blocks the preference. The user's HKCU has empty `MCP_CMD`/`REPO` | patch: string keys count as set only when non-empty; flags keep key presence, as `Capabilities.from_env` does |
| BH1 / EC3 | `bundled_wheel` sorts as strings and can pick an old wheel when a new zip is extracted over an old folder | medium | `managed_venv.py:55-58` `sorted(...)[-1]`: `0.0.9` sorts after `0.0.10` | patch: pick the wheel of the running `freecad_buddy.__version__`; README upgrade step deletes the old folder |
| BH3 / EC5 | A lock left by a killed FreeCAD blocks the proxy for 10 min, and the log blames "another instance" | medium | `provision` returns `False` on a fresh lock, `_provision_and_spawn` returns, info line only. The skip itself is the frozen matrix row | patch: warning names the lock path, its expiry, and "delete it if no other FreeCAD runs" |
| BH2 / EC6 | Lock mtime is not refreshed during a run over 10 min | low | Needs a run over 10 min AND a second start during it; the fix adds a heartbeat parameter | reject |
| EC7 / EC8 | Stale-lock takeover race; `finally` unlinks another owner's lock | low | Needs two concurrent takeovers of a stale lock; the fix adds an ownership token | reject |
| BH4 | Release venv resolves dependencies fresh, not from `uv.lock` | low | Ranges are major-bounded (`mcp>=1.28,<2`, `trimesh==4.*`, `lib3mf==2.*`); the fix adds a constraints artifact plus a build step | reject (named in the final report as a known limit) |
| BH5 / EC15 | `release-as: "0.0.1"` stays after the first release | medium | `release-please-config.json:7`; needed for v0.0.1, wrong afterwards | defer: remove after v0.0.1 is tagged |
| BH6 | Version test skips `uv.lock` | low | `test_version_consistency.py` reads 4 files; the config bumps 5 | patch |
| BH7 | Preferences page does not show that an env var overrides a field | medium | `preferences.py` tooltips only; this user's env sets AUDIT_LOG/WORKDIR | patch: in `loadSettings`, disable an overridden field and say which variable sets it |
| BH8 / EC4 | A uv path preference that is not a file falls back silently | low | `managed_venv.py:47-52`; the log shows the raw preference | patch: warn once, log the uv actually used; neutral tooltip |
| BH9 / EC2 | The MCP command is space-split, so a path with spaces breaks | low | `bootstrap.py:275` `explicit.split()`, pre-existing env semantics | patch: tooltip + README say no quoting, no spaces in paths |
| BH10 | `gh release upload` without `--clobber` fails on a re-run | low | `release.yml` upload step | patch: add `--clobber` |
| BH11 | Spawn after `stop_bridge` checked the proxy | false | `stop_bridge` sets the event and joins the thread before it reads `_mcp_proxy`; a spawn inside the join is visible after it | reject |
| EC11 | `start_bridge` after a timed-out join orphans the old thread | low | `start_bridge` runs once per FreeCAD process; `stop_bridge` runs on quit | reject |
| BH12 | Security doc omits that AutoApprove/AllowExec persist in `user.cfg` | low | `security-and-service-design.md` has no `user.cfg`; no typed tool writes parameters | patch (doc sentence) |
| BH13 | Two data folders; no uninstall section | low | D4 fixes the venv folder; README has no uninstall | patch (README uninstall lists both folders) |
| BH14 | README says "FreeCAD 1.1 or later" and only `v1-1` paths | low | `README.md:44`; decision 016 and `freecadmin 1.1` mean 1.1.x | patch |
| BH15 | README log sample, provisioning recovery, `uv sync` extra, bash block with a Windows path | low | `README.md` Install/Development | patch |
| EC12 | `build(release=True, wheel=None)` raises `TypeError` | low | `main` always passes a wheel; the fix is a new guard | reject |
| EC13 | Pre-release wheel names are normalized | low | release-please emits plain semver here | reject |
| EC14 | `--wheel` of another version is zipped under this version | low | The workflow builds both from one version | reject |
| EC9 | uv hang with no overall timeout | false | uv applies its own HTTP read timeout (`UV_HTTP_TIMEOUT`, default 30 s) | reject |
| EC10 | Marker current but uv base Python removed | low | Needs `uv python uninstall`; the fix adds an import probe | reject |
| EC16 | Log labels WORKDIR/AUDIT_LOG defaults as "(preference)" | low | `bootstrap.py:185` labels every overlay key "preference" | patch: label "default" when no preference supplied the value |
| VG1 | `_provision_and_spawn` untested | medium | Only mocked in `StartMcpProxyTest` | patch: test success, failure, raise |
| VG2 | `_addon_root` not tied to the `build_addon` layout | medium | No test; `parents[2]` would pass | patch: infc assertion |
| VG3 | `read_operator_preferences` key mapping/defaults untested | medium | Always patched; a swapped `AllowExec` default ships unseen | patch: infc test over `ParamGet` |
| VG4 | Real `_run` and `stop_bridge` cancel untested | medium | `_run` always faked | patch: `_run` slow-child cancel + non-zero exit; `stop_bridge` sets the event |
| VG5 | `build_addon.main --release` untested | medium | The workflow path; dropping `release=True` passes every test | patch |
| VG6 | REPO+uv branch untested | low | `McpProxyCommandOrderTest` pops REPO, passes `uv=None` | patch |
| VG7 | Headless warning names a GUI-only page | low | `capabilities.py:12-15`, logged by `mcp_server.py:221` | patch: wording says the page is in the GUI addon |

## Verification

**Commands:**
- `uv run python scripts/check_imports.py && uv run python scripts/check_skill_shape.py && uv run ruff check .` -- expected: exit 0
- `uv run pytest tests/external` -- expected: all pass
- `freecadcmd tests/run_tests.py` -- expected: all pass
- `uv build` then list the wheel -- expected: `contracts/jsonschema/*.json` present; sdist has no `_bmad-output`
- `uv run python scripts/build_addon.py --release` -- expected: `dist/FreeCADBuddy-0.0.1.zip`
- `claude plugin validate .` -- expected: valid

**Manual checks (if no CLI):**
- GUI UAT with `cua-driver`, per `freecad-gui-e2e-harness.md`:
  - release-zip install;
  - first-start provisioning in `addon.log`;
  - an MCP mutation returns OK;
  - Preferences page screenshot;
  - auto-approve off plus restart makes a mutation require `preview_id`;
  - an env override wins;
  - the dev junction is restored afterwards.
