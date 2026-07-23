# TC-09: Error Contract, Edge/Boundary & Fault Detection

Validates that invalid inputs, boundary values, stale/mismatched ids, and planted-fault fixtures
each produce the correct closed terminal status over MCP — and that nothing crashes the H1 server.
Executed by `scripts/automation/run_mcp_edge_cases.py`.

## Prerequisites

- [ ] micromamba `fcb` env is H1-capable
- [ ] Fault fixtures present (verify: `ls benchmarks/g0/fault-injection/wrong-volume/fixture.FCStd`)

---

### TC-09-01: Edge/corner/error sweep over MCP

**Priority**: Critical
**Design Ref**: `data-contracts-design.md` §status (closed set), `verification-design.md` §6.3 (fault detection)

**Preconditions**:
- [ ] No stale H1 server holding the fixtures

**Steps**:
1. Run the edge sweep:
   ```bash
   uv run python scripts/automation/run_mcp_edge_cases.py
   ```

**Checkpoints** (each is one recorded sweep check):
- [ ] CP1: unknown doc handle → `INVALID_INPUT`
- [ ] CP2: unknown object name → `INVALID_INPUT`
- [ ] CP3: open nonexistent path → `INVALID_INPUT`
- [ ] CP4: export missing schema-required `path` → MCP protocol rejection (`isError`, no envelope)
- [ ] CP5: export of >1 object to a single-shape writer → `INVALID_INPUT`
- [ ] CP6: `query_tree_summary max_nodes=0` → `OK`, empty nodes, `truncated=true`
- [ ] CP7: verify with a stale/unknown `export_id` → `INVALID_INPUT`
- [ ] CP8: `verify_export_step` on an STL `export_id` → `INVALID_INPUT`
- [ ] CP9: screenshot is read-only (volume identical before/after) → `OK`
- [ ] CP10: double `document_close` (stale handle) → `INVALID_INPUT`, no crash
- [ ] CP11: two-box compound mass-properties → `OK` with `com=null`
- [ ] CP12: `wrong-volume` fixture (given its reference checks) → `SPEC_FAILED`
- [ ] CP13: `non-watertight-open-shell` fixture → `SPEC_FAILED`
- [ ] CP14: all-pass gate — verify: `python3 -c "import json;print(json.load(open('_automation/edge_report.json'))['all_passed'])"` returns `True`
- [ ] CP15: no genuine crash — verify: `grep -iE "access violation|swig|segfault|fatal" _automation/edge.stderr.log` returns nothing (deliberate `ValidationError` tracebacks are expected, one per case)

**Cleanup**:
```bash
rm -f _automation/edge.stl _automation/edge_multi.step
```
