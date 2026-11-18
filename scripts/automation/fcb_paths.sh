# Sourced by fcb_py.sh and fcb_cua.sh: maps the host repository path to the container's `/repo`.
# Needs `PROJECT_ROOT`; exits 2 when it is unset. Defines `fcb_rewrite VALUE` (result in `REPLY`) and
# `fcb_rewrite_json_string VALUE` for a string taken from a JSON text.
# The prefix counts only when it ends the value or is followed by `/` or `\`, so a sibling folder
# such as `<root>-other` or `<root>2` is left alone. A value that starts with the backslash spelling
# of the prefix (same boundary rule) has its backslashes turned into slashes, also after a `--flag=`.
root="${PROJECT_ROOT:-}"
if [ -z "$root" ]; then
    echo "$(basename "$0"): PROJECT_ROOT is not set; the test-plan environment block exports it" >&2
    exit 2
fi
root="${root%/}"
root_backslash="${root//\//\\}"

fcb_rewrite() {
    local value="$1"
    if [ "$value" = "$root" ]; then
        REPLY=/repo
        return
    fi
    if [[ "$value" == "$root_backslash" || "$value" == "$root_backslash"\\* ]]; then
        value="/repo${value#"$root_backslash"}"
        REPLY="${value//\\//}"
        return
    fi
    if [[ "$value" == --*=* ]]; then
        local flag="${value%%=*}"
        fcb_rewrite "${value#*=}"
        REPLY="$flag=$REPLY"
        return
    fi
    value="${value//"$root"\//\/repo\/}"
    value="${value//"$root"\\//repo/}"
    if [[ "$value" == *"$root" ]]; then
        value="${value%"$root"}/repo"
    fi
    REPLY="$value"
}

# JSON writes one backslash as two (`D:\\work\\repo\\x`). Only a string that is the backslash root, or
# starts with it, is read in its plain form; any other `\\` is kept as written.
fcb_rewrite_json_string() {
    local value="$1"
    local two='\\' one='\'
    local plain="${value//"$two"/"$one"}"
    if [[ "$plain" == "$root_backslash" || "$plain" == "$root_backslash"\\* ]]; then
        fcb_rewrite "$plain"
    else
        fcb_rewrite "$value"
    fi
}
