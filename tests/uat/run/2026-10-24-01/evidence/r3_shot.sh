# r3_shot.sh <stem>: when the physical pointer is inside the FreeCAD main window rectangle
# (x 154..2406, y 65..1354 in this session), move it out with move_cursor scope desktop to (2480,700),
# wait 1 s, then capture the main window to <stem>.png. Pointer positions go to <stem>-pointer.txt.
cd "$(dirname "$0")"
stem=$1
pos() { cua-driver get_cursor_position '{}' | tr -d '\n '; }
inside() { p=$(pos); x=$(echo "$p" | sed 's/.*"x":\(-\?[0-9]*\).*/\1/'); y=$(echo "$p" | sed 's/.*"y":\(-\?[0-9]*\).*/\1/'); echo "$(date +%T) $p" >> "$stem-pointer.txt"; [ "$x" -ge 154 ] && [ "$x" -lt 2406 ] && [ "$y" -ge 65 ] && [ "$y" -lt 1354 ]; }
if inside; then echo '{"x":2480,"y":700,"scope":"desktop"}' | cua-driver call move_cursor > /dev/null; echo "$(date +%T) moved pointer out" >> "$stem-pointer.txt"; fi
sleep 1
uv run python r3_gui1.py shot "$stem" | sed -n 1,6p
inside && echo "WARNING pointer inside the window after capture" | tee -a "$stem-pointer.txt"
