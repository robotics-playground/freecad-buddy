#!/bin/bash
# Run the container's `cua-driver` (0.28.1, in the XFCE session) from a host shell, for the UAT test
# cases:
#   echo '{"pid":<pid>,"window_id":<wid>}' | "$FCB_CUA" get_window_state
#   "$FCB_CUA" status
# `status`, `doctor`, `list-tools` and `describe` are passed on as they are and read no standard input;
# any other first word is a tool name and runs as `cua-driver call <tool>` with standard input as the
# tool's JSON. A single-quoted test-case line leaves `$RUN_DIR` and `$PROJECT_ROOT` unexpanded, so the
# literal tokens are replaced by the exported values first. Every JSON string that then holds the host
# repository path is rewritten to the container's `/repo` (fcb_paths.sh), because the tool runs in the
# container and writes under `/repo/tests/uat/run`.
# The session environment (`DISPLAY`, the D-Bus address) comes from `fcb-session-env`: without it the
# accessibility walk is empty for every window.
set -euo pipefail
export MSYS_NO_PATHCONV=1
# shellcheck source=fcb_paths.sh
source "$(dirname "${BASH_SOURCE[0]}")/fcb_paths.sh"

if [ "$#" -lt 1 ]; then
    echo "usage: fcb_cua.sh <tool>|status|doctor|list-tools|describe [args]" >&2
    exit 64
fi
case "$1" in
status | doctor | list-tools | describe)
    exec docker exec -u cua fcb-desktop bash -c \
        'eval "$(fcb-session-env)"; exec /usr/local/bin/cua-driver "$@"' _ "$@"
    ;;
esac

# `&` in a replacement string would stand for the matched text (bash 5.2); a path may hold one.
shopt -u patsub_replacement 2>/dev/null || true
raw="$(cat)"
raw="${raw//\$PROJECT_ROOT/$root}"
if [[ "$raw" == *'$RUN_DIR'* ]]; then
    if [ -z "${RUN_DIR:-}" ]; then
        echo "$(basename "$0"): the JSON holds \$RUN_DIR and RUN_DIR is not set" >&2
        exit 2
    fi
    # `$RUN_DIR_C` already names the container path; replace it first so `$RUN_DIR` does not match
    # its prefix.
    raw="${raw//\$RUN_DIR_C//repo${RUN_DIR#"$root"}}"
    raw="${raw//\$RUN_DIR/$RUN_DIR}"
fi
# The JSON is cut at every quote, so a string with an escaped quote is cut inside the string; only a
# path that touches an escaped quote is affected, and no tool payload of the test cases has one.
mapfile -d '"' -t parts < <(printf '%s' "$raw")
input=""
for index in "${!parts[@]}"; do
    fcb_rewrite_json_string "${parts[$index]}"
    [ "$index" -gt 0 ] && input+='"'
    input+="$REPLY"
done
# mapfile drops the empty piece after a final quote.
[[ "$raw" == *'"' ]] && input+='"'
printf '%s' "$input" | exec docker exec -i -u cua fcb-desktop bash -c \
    'eval "$(fcb-session-env)"; exec /usr/local/bin/cua-driver call "$@"' _ "$@"
