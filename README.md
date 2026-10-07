# FreeCAD Buddy

FreeCAD addon and MCP server. An AI agent uses typed tools to read, change, verify and export
FreeCAD models. Every change runs inside a checked transaction and rolls back on failure.

## Operator setup

### Mutation approval

`FREECAD_BUDDY_AUTO_APPROVE` controls whether a mutation needs a preview first.

| Value | Posture |
|-------|---------|
| unset or `1` | **Auto-approve (default).** A `sketch_*` or `feature_*` call without `confirm` applies in one call. |
| `0` | **Confirm gate.** A mutation without a valid `confirm.preview_id` is refused with `INVALID_INPUT`. Any non-empty value other than `1` has the same effect; use `0`. |

In both postures:

- Every mutation runs the full transaction: snapshot, operation, recompute, post-verify, and
  rollback on failure.
- Every approved mutation writes an `approval` line to the audit log. An auto-approved line
  carries `"mode": "auto_approve"` and `"source": "FREECAD_BUDDY_AUTO_APPROVE"`.
- `preview_dry_run` stays available. Use it to measure a change before you apply it.
- A call that sends `confirm` is checked against its token. A stale, expired or forged
  `preview_id` is refused with `INVALID_INPUT`, also when auto-approve is on. An accepted token
  writes `"mode": "preview_token"`.
- A `feature_set_parameters` call that writes only `Visibility` needs no `confirm`. Hiding or
  showing an object changes no geometry.

A client cannot change the posture. The host reads the variable once, at start.

### Set the variable before FreeCAD starts

FreeCAD gets an environment variable only from the process that starts it. Set the variable
first, then start FreeCAD. A change made while FreeCAD runs has no effect until you restart it.

Require previews for every FreeCAD start (Windows, current user):

```powershell
setx FREECAD_BUDDY_AUTO_APPROVE 0
```

`setx` changes new processes only. Start FreeCAD from the Start menu or from a new terminal.

Return to the default (remove the variable):

```powershell
[Environment]::SetEnvironmentVariable("FREECAD_BUDDY_AUTO_APPROVE", $null, "User")
```

To turn the confirm gate on, set the value `0`. Do not use an empty value
(`setx FREECAD_BUDDY_AUTO_APPROVE ""`): a new process usually gets it as unset, so auto-approve
stays on.

Require previews for one FreeCAD start only (PowerShell):

```powershell
$env:FREECAD_BUDDY_AUTO_APPROVE = "0"
& "C:\Program Files\FreeCAD 1.1\bin\freecad.exe"
```

The same in `cmd.exe`:

```bat
set FREECAD_BUDDY_AUTO_APPROVE=0
"C:\Program Files\FreeCAD 1.1\bin\freecad.exe"
```

### Check the posture

With auto-approve on, the host writes this line at start:

```text
SECURITY: mutation auto-approve ENABLED (FREECAD_BUDDY_AUTO_APPROVE unset or 1; set it to 0 to require preview_id)
```

- GUI: in `%APPDATA%\FreeCAD\v1-1\freecad-buddy\addon.log`.
- Headless host (`freecad-buddy serve --mode inline`): on stderr.

With the confirm gate on, the line is absent.

The audit log also shows the posture. An `approval` line with `"mode": "auto_approve"` proves
auto-approve is on. Lines with `"mode": "preview_token"` (a call that sent a token) or
`"mode": "display_state"` (a `Visibility`-only write) occur in both postures, so they do not show
it.

Set `FREECAD_BUDDY_AUDIT_LOG` to a known file path before FreeCAD starts. Without it, the audit
log is `freecad-buddy-audit.jsonl` in the working directory of FreeCAD, and a Start-menu launch
has no known working directory.
