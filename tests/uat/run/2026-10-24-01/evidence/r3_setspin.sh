# r3_setspin.sh "<current label>" "<new text>": focus the task-panel spin box through a background UIA type_text, then replace its text with foreground keys, then Tab to commit.
cd "$(dirname "$0")"; source r3_env.sh
uv run python r3_gui.py type "$1" Spinner "$2" > /dev/null
sleep 0.6
echo "{\"pid\":$PID,\"window_id\":$WID,\"keys\":[\"ctrl\",\"a\"],\"delivery_mode\":\"foreground\"}" | cua-driver call hotkey > /dev/null; sleep 0.6
echo "{\"pid\":$PID,\"window_id\":$WID,\"text\":\"$2\",\"delivery_mode\":\"foreground\"}" | cua-driver call type_text > /dev/null; sleep 0.6
key Tab fg > /dev/null; sleep 1.2
cua-driver call move_cursor '{"x":2480,"y":700,"scope":"desktop"}' > /dev/null
