#!/bin/bash
# Run the container's `fcb-py` (the AppImage's Python 3.11 with FreeCAD and the pinned `mcp`) from a
# host shell, for the UAT test cases that start the headless H1 host:
#   "$FCB_PYTHON" -m freecad_buddy.hosts.main serve --transport stdio --mode inline
# The host shell expands `$PROJECT_ROOT` and `$RUN_DIR` before this script runs, so every argument and
# every `FREECAD_BUDDY_*` variable has the host repository prefix rewritten to the container's
# `/repo`: the prefix counts only when it ends the value or is followed by `/` or `\`, so a sibling
# folder such as `<root>-other` is left alone. A value that starts with the backslash spelling of
# the prefix (same boundary rule) has its backslashes turned into slashes, also after a `--flag=`. A `FREECAD_BUDDY_*` value that still looks like
# a host path afterwards is passed on with a warning on stderr.
# Standard input and output are the container process's, so an MCP client on the host can talk to it.
# `PYTHONPATH` names the addon the image installs: `freecad_buddy` cannot be imported before
# `import FreeCAD` adds that folder.
set -euo pipefail
export MSYS_NO_PATHCONV=1
# shellcheck source=fcb_paths.sh
source "$(dirname "${BASH_SOURCE[0]}")/fcb_paths.sh"

args=()
for argument in "$@"; do
    fcb_rewrite "$argument"
    args+=("$REPLY")
done
envs=(-e "PYTHONPATH=${FCB_ADDON:-/home/cua/.local/share/FreeCAD/v1-1/Mod/FreeCADBuddy}")
while IFS= read -r line; do
    name="${line%%=*}"
    case "$name" in
    FREECAD_BUDDY_*)
        fcb_rewrite "${line#*=}"
        case "$REPLY" in
        [A-Za-z]:[\\/]* | *\\*) echo "fcb_py.sh: $name=$REPLY looks like a host path" >&2 ;;
        esac
        envs+=(-e "$name=$REPLY")
        ;;
    esac
done < <(env)
exec docker exec -i -u cua "${envs[@]}" fcb-desktop fcb-py "${args[@]}"
