"""Checks of the container's accessibility chain, against the running `fcb-desktop` container.

Runs on the host, like `journey_box.py` (see tests/close-loop/README.md); it needs the container
with FreeCAD started, so it belongs to neither pytest nor CI:
    uv run python tests/close-loop/check_harness.py

Each check prints one line `PASS|FAIL <name>: <measured value>` and the exit code is 1 when any
check fails.

- mcp-session-env (C1): `fcb-cua-mcp` started while the desktop session is still absent ends with
  the session's `DBUS_SESSION_BUS_ADDRESS` in the `cua-driver mcp` process environment.
- registry-childcount (C2): the AT-SPI registry answers `ChildCount` with no `NoReply`.
- gtk-elements-serve / gtk-elements-mcp (C2): `get_window_state` on a GTK window beside FreeCAD
  returns more than 1 element and no `atspi_walk_failed`, through `cua-driver serve` and through
  the MCP server.
- freecad-logging-rule: the running FreeCAD's `QT_LOGGING_RULES` ends with the rule that
  silences the AT-SPI warning whose handling deadlocks FreeCAD's notification area
  (`fcb-freecad start` sets it).
- freecad-elements (C3): the FreeCAD main window tree has more than 1 element and holds the menu
  bar items File, Edit and View.
"""

from __future__ import annotations

import asyncio
import json
import subprocess
import sys

from mcp import ClientSession
from mcp.client.stdio import StdioServerParameters, stdio_client

CONTAINER = "fcb-desktop"
CUA_DRIVER = "/usr/local/bin/cua-driver"
GTK_APP = "Xfce4-panel"
MENU_ITEMS = ("File", "Edit", "View")
ATSPI_RULE = "qt.accessibility.atspi.warning=false"
# The shim `fcb-session-env` of the late-session check refuses for this long before it answers.
LATE_SESSION_DELAY_S = 5

# Starts `fcb-cua-mcp` with a session probe that fails for the first LATE_SESSION_DELAY_S seconds,
# waits until the process has become `cua-driver mcp`, and prints its address and the session's.
LATE_SESSION_SCRIPT = r"""
set -u
mcp_pid=""
shim_dir="$(mktemp -d)"
trap '[ -n "$mcp_pid" ] && kill "$mcp_pid" 2>/dev/null; rm -rf "$shim_dir"' EXIT
cat >"$shim_dir/fcb-session-env" <<SHIM
#!/bin/bash
marker="$shim_dir/first-call"
[ -f "\$marker" ] || date +%s >"\$marker"
if [ \$(( \$(date +%s) - \$(cat "\$marker") )) -lt $1 ]; then exit 1; fi
exec /usr/local/bin/fcb-session-env
SHIM
chmod +x "$shim_dir/fcb-session-env"
session_pid="$(pgrep -u cua -x xfce4-session | head -n 1)"
session_address="$(tr '\0' '\n' </proc/$session_pid/environ \
    | sed -n 's/^DBUS_SESSION_BUS_ADDRESS=//p')"
PATH="$shim_dir:$PATH" fcb-cua-mcp < <(sleep 60) >/dev/null 2>&1 &
mcp_pid=$!
for _ in $(seq 1 60); do
    if tr '\0' ' ' <"/proc/$mcp_pid/cmdline" 2>/dev/null | grep -q 'cua-driver mcp'; then
        sleep 1
        address="$(tr '\0' '\n' <"/proc/$mcp_pid/environ" \
            | sed -n 's/^DBUS_SESSION_BUS_ADDRESS=//p')"
        echo "mcp=$address"
        echo "session=$session_address"
        exit 0
    fi
    sleep 0.5
done
echo "mcp=<cua-driver mcp did not start>"
echo "session=$session_address"
"""

# busctl and gdbus register on the bus before they call. `dbus-send --address=<a11y bus>` does not:
# the bus answers it "Client tried to send a message other than Hello without being registered"
# and the call ends as NoReply, which reads like a dead registry.
REGISTRY_SCRIPT = r"""
set -eu
eval "$(fcb-session-env)"
bus="$(busctl --user call org.a11y.Bus /org/a11y/bus org.a11y.Bus GetAddress \
    | sed -n 's/^s "\(.*\)"$/\1/p')"
busctl --address="$bus" get-property org.a11y.atspi.Registry /org/a11y/atspi/accessible/root \
    org.a11y.atspi.Accessible ChildCount
"""

LOGGING_RULE_SCRIPT = r"""
pid="$(pgrep -u cua -f '^/opt/freecad/usr/bin/freecad( |$)' | head -n 1)"
tr '\0' '\n' </proc/$pid/environ | sed -n 's/^QT_LOGGING_RULES=//p'
"""


def in_container(*command: str, stdin: str | None = None) -> str:
    done = subprocess.run(
        ["docker", "exec", "-i", "-u", "cua", CONTAINER, *command],
        input=stdin,
        capture_output=True,
        text=True,
        timeout=180,
    )
    if done.returncode != 0:
        raise RuntimeError(f"{command[:2]} exited {done.returncode}: {done.stderr.strip()[-300:]}")
    return done.stdout


def serve_call(tool: str, arguments: dict) -> dict:
    """One `cua-driver call` through the daemon `fcb-cua-serve` started."""
    out = in_container(
        "bash",
        "-c",
        f'eval "$(fcb-session-env)"; exec {CUA_DRIVER} call "$1" "$2"',
        "cua-driver",
        tool,
        json.dumps(arguments),
    )
    return json.loads(out[out.find("{") :])


def find_window(app_name: str) -> dict:
    windows = serve_call("list_windows", {})["windows"]
    candidates = [w for w in windows if w["app_name"] == app_name and w["is_on_screen"]]
    if not candidates:
        raise RuntimeError(f"no on-screen window of {app_name}")
    return max(candidates, key=lambda w: w["bounds"]["width"] * w["bounds"]["height"])


def tree_of(state: dict) -> tuple[int, str, str | None]:
    return state.get("element_count", 0), state.get("tree_markdown", ""), state.get("error")


async def mcp_state(arguments: dict) -> dict:
    parameters = StdioServerParameters(
        command="docker", args=["exec", "-i", "-u", "cua", CONTAINER, "fcb-cua-mcp"]
    )
    async with stdio_client(parameters) as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()
            reply = await session.call_tool("get_window_state", arguments)
            if reply.structuredContent is not None:
                return reply.structuredContent
            text = "".join(block.text for block in reply.content if block.type == "text")
            return {"element_count": 0, "tree_markdown": "", "error": text[:300]}


def check_mcp_session_env() -> tuple[bool, str]:
    out = in_container("bash", "-c", LATE_SESSION_SCRIPT, "check", str(LATE_SESSION_DELAY_S))
    values = dict(line.split("=", 1) for line in out.strip().splitlines())
    held = values["mcp"] == values["session"] and values["session"].startswith("unix:")
    return held, f"cua-driver mcp address={values['mcp']!r} session address={values['session']!r}"


def check_registry() -> tuple[bool, str]:
    try:
        out = in_container("bash", "-c", REGISTRY_SCRIPT)
    except RuntimeError as exc:
        return False, str(exc)
    count = int(out.split()[-1])
    return count > 0, f"Registry ChildCount={count}"


def check_gtk_serve() -> tuple[bool, str]:
    window = find_window(GTK_APP)
    count, _, error = tree_of(
        serve_call("get_window_state", {"pid": window["pid"], "window_id": window["window_id"]})
    )
    return count > 1 and not error, f"{GTK_APP} element_count={count} error={error}"


def check_gtk_mcp() -> tuple[bool, str]:
    window = find_window(GTK_APP)
    count, _, error = tree_of(
        asyncio.run(mcp_state({"pid": window["pid"], "window_id": window["window_id"]}))
    )
    return count > 1 and not error, f"{GTK_APP} element_count={count} error={error}"


def check_logging_rule() -> tuple[bool, str]:
    rules = in_container("bash", "-c", LOGGING_RULE_SCRIPT).strip()
    return rules.endswith(ATSPI_RULE), f"FreeCAD QT_LOGGING_RULES={rules!r}"


def check_freecad() -> tuple[bool, str]:
    window = find_window("FreeCAD")
    count, tree, error = tree_of(
        serve_call("get_window_state", {"pid": window["pid"], "window_id": window["window_id"]})
    )
    missing = [item for item in MENU_ITEMS if f'"{item}"' not in tree]
    return count > 1 and not missing and not error, (
        f"FreeCAD element_count={count} missing menu items={missing} error={error}"
    )


CHECKS = (
    ("mcp-session-env", check_mcp_session_env),
    ("registry-childcount", check_registry),
    ("gtk-elements-serve", check_gtk_serve),
    ("gtk-elements-mcp", check_gtk_mcp),
    ("freecad-logging-rule", check_logging_rule),
    ("freecad-elements", check_freecad),
)


def main() -> int:
    failed = 0
    for name, check in CHECKS:
        try:
            passed, detail = check()
        except Exception as exc:
            passed, detail = False, f"{type(exc).__name__}: {exc}"
        failed += not passed
        print(f"{'PASS' if passed else 'FAIL'} {name}: {detail}")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
