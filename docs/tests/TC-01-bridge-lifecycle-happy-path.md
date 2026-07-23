# TC-01: Bridge Lifecycle & Happy-Path Tool Sweep

Validates the Epic-1 tool surface end-to-end over MCP against real golden geometry: document
lifecycle, read-only queries, verification, exports with paired verify, and offscreen screenshots.
Executed by `scripts/automation/run_mcp_e2e.py`; this file documents the plan and checkpoints.

## Prerequisites

- [ ] micromamba `fcb` env is H1-capable (verify: `"$USERPROFILE/micromamba/envs/fcb/python.exe" -c "import FreeCAD, mcp"`)
- [ ] Golden models present (verify: `ls benchmarks/g0/golden-models/*.FCStd | wc -l` ≥ 5)

---

### TC-01-01: Full golden-model sweep over MCP

**Priority**: Critical
**Design Ref**: `mcp-tools-design.md` (tool surface), `verification-design.md` §6 (exports)

**Preconditions**:
- [ ] No stale H1 server holding the golden files

**Steps**:
1. Run the happy-path sweep (spawns H1, drives all tools over MCP stdio):
   ```bash
   uv run python scripts/automation/run_mcp_e2e.py
   ```

**Checkpoints**:
- [ ] CP1: All checks pass — verify: `python3 -c "import json;print(json.load(open('_automation/e2e_report.json'))['all_passed'])"` returns `True`
- [ ] CP2: 23 tools listed — verify: `grep -c '"tool": "tools/list"' _automation/e2e_report.json` and detail shows `23 tools`
- [ ] CP3: box volume within 0.1 % — verify: report `query_mass_properties:box-10-20-30` detail shows `volume=6000.0`
- [ ] CP4: STEP round-trip verified — verify: report `verify_export_step:*` all `status=OK`
- [ ] CP5: STL/3MF oracles agree — verify: report `verify_export_stl:*` all `status=OK`
- [ ] CP6: screenshots rendered non-empty — verify: report `query_screenshot:*` all `status=OK` with a `link=...png`
- [ ] CP7: server stderr free of unhandled tracebacks — verify: `grep -iE "traceback|access violation" _automation/server.stderr.log | grep -vE "INFO|audit"` returns nothing

**Cleanup**:
```bash
rm -f _automation/*.step _automation/*.stl _automation/scratch.FCStd
```
