# FreeCAD Buddy

FreeCAD addon and MCP server for AI agents. An agent uses typed tools to read, build, check and
export FreeCAD models. Every change runs in a checked transaction and rolls back on failure. The
agent does not guess that a part is right: it measures it.

> **Private repository.** There is no PyPI package. To download a release, install the Claude
> Code plugin or add the skills, you need read access to
> `github.com/robotics-playground/freecad-buddy`.

## What it does

The addon runs inside the FreeCAD GUI. It serves an MCP endpoint on
`http://127.0.0.1:8765/mcp` while FreeCAD is open. Any MCP client on the same computer can
connect to it.

| Tool group | Tools | Use |
|------------|-------|-----|
| Documents | `document_create`, `document_open`, `document_save`, `document_close`, `document_list`, `document_recompute`, `document_undo` | Open and manage `.FCStd` files |
| Queries | `query_tree_summary`, `query_object`, `query_placement`, `query_mass_properties`, `query_dependencies`, `query_sketch_info`, `query_screenshot`, `query_capabilities` | Read the model and render it |
| Sketches | `sketch_create`, `sketch_add_geometry`, `sketch_add_constraint`, `sketch_set_datum`, `sketch_add_external_geometry`, `sketch_toggle_construction`, `sketch_remove_geometry`, `sketch_remove_constraint` | Build constrained sketches |
| Features | `feature_body_create`, `feature_pad`, `feature_pocket`, `feature_revolve`, `feature_hole`, `feature_fillet`, `feature_chamfer`, `feature_mirror`, `feature_pattern`, `feature_datum`, `feature_set_parameters` | Build PartDesign solids |
| Preview | `preview_dry_run` | Measure a change before you apply it |
| Verify | `verify_shape`, `verify_sketch`, `verify_recompute` | Check the model against stated expectations |
| Export | `export_step`, `export_stl`, `export_3mf` | Write exchange files |
| Export verify | `verify_export_step`, `verify_export_stl`, `verify_export_3mf` | Read the written file back and check it |
| View | `view_fit_viewport` | Fit the FreeCAD 3D view |

### The verify-first loop

1. Read the model (`query_*`).
2. Change it (`sketch_*`, `feature_*`). The bridge snapshots the document, applies the change,
   recomputes, checks the result and rolls back on failure.
3. Check it (`verify_*`). A verdict is a measured value, not a claim.
4. Export it, then verify the file. An export tool returns `verified: false`. The export is done
   only when its paired `verify_export_*` tool passes.

The `skills/` folder holds 15 agent skills: FreeCAD fundamentals, sketch strategy, PartDesign,
datums, verification, troubleshooting, URDF/SDF export and more. They teach an agent how to use
the tools well.

## Requirements

- FreeCAD 1.1.x.
- [uv](https://docs.astral.sh/uv/getting-started/installation/). The addon uses `uv` once, at
  first start, to build a private Python environment for the MCP server. FreeCAD's own Python
  cannot hold the MCP libraries.
- Internet access at first start: `uv` downloads Python 3.11 or later and the dependencies.

## Install the addon

1. Download `FreeCADBuddy-<version>.zip` from the
   [GitHub releases](https://github.com/robotics-playground/freecad-buddy/releases).
2. Extract it into the FreeCAD user `Mod` folder. The result must be `Mod/FreeCADBuddy/`.
   - Windows: `%APPDATA%\FreeCAD\v1-1\Mod\`
   - Linux: `~/.local/share/FreeCAD/v1-1/Mod/`
   - macOS: `~/Library/Application Support/FreeCAD/v1-1/Mod/`
3. Install `uv` if it is not on `PATH`.
4. Start FreeCAD.

At first start the addon builds the environment in the background. When `uv` must download
Python and the dependencies, this can take some minutes. The GUI does not wait for it. Then the
MCP server starts on `:8765`. Progress goes to the addon log in the FreeCAD user data folder, for
example `%APPDATA%\FreeCAD\v1-1\freecad-buddy\addon.log`:

```text
provisioning the MCP proxy venv at ...\FreeCADBuddy\venv from freecad_buddy-0.0.1-py3-none-any.whl; log: ...\freecad-buddy\provision.log
MCP proxy venv ready at ...\FreeCADBuddy\venv
spawned MCP proxy (pid 12345) -> http://127.0.0.1:8765/mcp; proxy log: ...\freecad-buddy\mcp-proxy.log
```

Later starts reuse the environment. A new addon version builds it again.

If `uv` is not found, the addon log says so and names the preference page. Set the **uv path**
field there, then restart FreeCAD.

### If the environment build fails

- Read `freecad-buddy/provision.log` in the FreeCAD user data folder. It holds the `uv` output.
- The next FreeCAD start tries again.
- To force a full rebuild, close FreeCAD and delete the `FreeCADBuddy/venv` folder in the FreeCAD
  user data folder.
- If the addon log says the lock `FreeCADBuddy/venv.lock` is held, another FreeCAD is building
  the environment, or a FreeCAD that was stopped left the lock. The lock expires after
  10 minutes. If no other FreeCAD runs, delete the lock file and restart FreeCAD.

### Upgrade

Close FreeCAD. Delete the old `Mod/FreeCADBuddy` folder, then extract the new zip. Do not extract
over the old folder: files that the new version removed would stay. At the next start the addon
builds the environment again for the new version.

### Uninstall

Close FreeCAD, then delete these folders. Paths are in the FreeCAD user data folder, for example
`%APPDATA%\FreeCAD\v1-1\` on Windows.

- `Mod/FreeCADBuddy`: the addon.
- `FreeCADBuddy`: the private Python environment.
- `freecad-buddy`: the logs and the audit log. Keep a copy of `audit.jsonl` if you need the
  record.

## Connect an agent

Start FreeCAD first. The MCP server runs only while FreeCAD is open.

### Claude Code (plugin)

The plugin installs the 15 skills and the `freecad-buddy` MCP server entry.

```text
/plugin marketplace add robotics-playground/freecad-buddy
/plugin install freecad-buddy@freecad-buddy
```

Start a new session. `/mcp` lists `freecad-buddy`.

Without the plugin, add only the server:

```bash
claude mcp add --transport http freecad-buddy http://127.0.0.1:8765/mcp
```

### Skills for other agents

```bash
npx skills add https://github.com/robotics-playground/freecad-buddy/tree/main/skills
```

### MCP server for other clients

All snippets point at `http://127.0.0.1:8765/mcp` (streamable HTTP).

Codex (`~/.codex/config.toml`):

```toml
[mcp_servers.freecad-buddy]
url = "http://127.0.0.1:8765/mcp"
```

Cursor (`~/.cursor/mcp.json` or `.cursor/mcp.json`):

```json
{ "mcpServers": { "freecad-buddy": { "url": "http://127.0.0.1:8765/mcp" } } }
```

opencode (`opencode.json`):

```json
{
  "$schema": "https://opencode.ai/config.json",
  "mcp": {
    "freecad-buddy": { "type": "remote", "url": "http://127.0.0.1:8765/mcp", "enabled": true }
  }
}
```

Gemini CLI (`~/.gemini/settings.json`):

```json
{ "mcpServers": { "freecad-buddy": { "httpUrl": "http://127.0.0.1:8765/mcp" } } }
```

Claude Desktop (`claude_desktop_config.json`). Claude Desktop starts local servers as commands,
so `mcp-remote` bridges to the HTTP endpoint. It needs Node.js.

```json
{
  "mcpServers": {
    "freecad-buddy": { "command": "npx", "args": ["-y", "mcp-remote", "http://127.0.0.1:8765/mcp"] }
  }
}
```

## Preferences

Open Edit > Preferences > **FreeCAD Buddy**.

| Field | Default | Effect |
|-------|---------|--------|
| Round numbers to FreeCAD display precision | on | Round result numbers to the **Decimals** setting in General > Units. Applies at the next tool call. |
| Auto-approve mutations | on | On: a `sketch_*` or `feature_*` call applies in one call. Off: every mutation needs the `preview_id` of a `preview_dry_run`. |
| Allow debug_exec | off | Registers `debug_exec`, which runs any Python inside FreeCAD. Only for trusted bring-up. Never for an unattended agent. |
| Start the MCP server with FreeCAD | on | Serve `http://127.0.0.1:8765/mcp` while FreeCAD runs. |
| MCP command | empty | A command that starts the MCP server. Empty: found automatically. Split on spaces with no quoting, so a path that contains a space is not supported. |
| uv path | empty | Path to the `uv` executable. Empty: `uv` on `PATH`. A path that is not a file is ignored with a warning in the addon log. |
| Audit log file | empty | Empty: `audit.jsonl` in the `freecad-buddy` folder of the FreeCAD user data folder. |

Restart FreeCAD to apply a change. Only rounding applies at once.

At start the addon writes the effective settings to `addon.log`, one line:

```text
operator settings: FREECAD_BUDDY_AUTO_APPROVE='1' (preference), FREECAD_BUDDY_ALLOW_EXEC='0' (preference), ...
```

Each value names its source: `env` (an environment variable), `preference`, `default`, or
`unset`.

### Mutation approval

| Posture | Behaviour |
|---------|-----------|
| **Auto-approve (default)** | A `sketch_*` or `feature_*` call without `confirm` applies in one call. |
| **Confirm gate** | A mutation without a valid `confirm.preview_id` is refused with `INVALID_INPUT`. |

In both postures:

- Every mutation runs the full transaction: snapshot, operation, recompute, post-verify, and
  rollback on failure.
- Every approved mutation writes an `approval` line to the audit log. An auto-approved line
  carries `"mode": "auto_approve"` and `"source": "FREECAD_BUDDY_AUTO_APPROVE"`, also when the
  preference set it.
- A call that sends `confirm` is checked against its token. A stale, expired or forged
  `preview_id` is refused, also when auto-approve is on. An accepted token writes
  `"mode": "preview_token"`.
- A `feature_set_parameters` call that writes only `Visibility` needs no `confirm`.

A client cannot change the posture. With auto-approve on, the addon log has this line:

```text
SECURITY: mutation auto-approve ENABLED (to require preview_id, clear Auto-approve mutations in the FreeCAD GUI: Edit > Preferences > FreeCAD Buddy, or set FREECAD_BUDDY_AUTO_APPROVE=0)
```

## Environment variable overrides

A variable that is set wins over the preference. Use variables for scripted and test runs. FreeCAD
gets a variable only from the process that starts it, so set it before FreeCAD starts.

`FREECAD_BUDDY_AUTO_APPROVE` and `FREECAD_BUDDY_ALLOW_EXEC` count as set when they exist, also
with an empty value. The other variables count as set only when they are not empty. The
preference page disables each field that a variable sets, and names the variable.

| Variable | Overrides | Values |
|----------|-----------|--------|
| `FREECAD_BUDDY_AUTO_APPROVE` | Auto-approve mutations | `1` on; `0` confirm gate |
| `FREECAD_BUDDY_ALLOW_EXEC` | Allow debug_exec | exactly `1` enables; any other value is off |
| `FREECAD_BUDDY_NO_AUTO_MCP` | Start the MCP server with FreeCAD | any non-empty value: do not start |
| `FREECAD_BUDDY_MCP_CMD` | MCP command | space-separated command |
| `FREECAD_BUDDY_AUDIT_LOG` | Audit log file | file path |
| `FREECAD_BUDDY_WORKDIR` | — | session work folder; default `freecad-buddy/workdir` in the FreeCAD user data folder |
| `FREECAD_BUDDY_LOG_FILE` | — | addon log path |

Require previews for every FreeCAD start (Windows, current user):

```powershell
setx FREECAD_BUDDY_AUTO_APPROVE 0
```

`setx` changes new processes only. Remove the variable with:

```powershell
[Environment]::SetEnvironmentVariable("FREECAD_BUDDY_AUTO_APPROVE", $null, "User")
```

Require previews for one FreeCAD start only (PowerShell):

```powershell
$env:FREECAD_BUDDY_AUTO_APPROVE = "0"
& "C:\Program Files\FreeCAD 1.1\bin\freecad.exe"
```

Do not use an empty value to turn the confirm gate on. A new process usually gets it as unset.

## Security

- The only path for an agent to change a model is a typed tool over MCP.
- The MCP endpoint and the internal RPC listener bind `127.0.0.1` only. The RPC listener checks a
  per-session token.
- `debug_exec` is off by default. It is not even listed when off. Turn it on only when you are
  present and trust the caller.
- Every mutation and every `debug_exec` call is written to the append-only audit log.
- The bridge runs with your user rights inside your FreeCAD. It ships no sandbox. If you run an
  unattended agent, give it an isolated computer or account.

## Headless

For CI and scripts, run the server without the GUI in a Python environment that can
`import FreeCAD` (for example conda-forge `freecad`):

```bash
freecad-buddy serve --mode inline --transport stdio
```

The headless host reads environment variables only. It has no preference page, and its audit log
and workdir default to the current folder.

## Development

```bash
uv sync --all-extras
uv run python scripts/check_imports.py
uv run ruff check .
uv run pytest tests/external
```

Run the in-FreeCAD suite with FreeCAD's own command-line interpreter:

```powershell
& "C:\Program Files\FreeCAD 1.1\bin\freecadcmd.exe" tests/run_tests.py
```

For a dev install, link the source package into the FreeCAD `Mod` folder, or build a copy with
`uv run python scripts/build_addon.py`. A dev install finds the repository `.venv` and starts the
MCP server from it. It does not build the private environment.

`uv run python scripts/build_addon.py --release` builds the wheel and writes
`dist/FreeCADBuddy-<version>.zip`. release-please on `main` publishes the wheel, the sdist and
the addon zip to a GitHub release.

## License

MIT. See [LICENSE](LICENSE).
