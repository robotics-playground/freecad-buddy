# r2_shot.sh <stem> (from r1_shot.sh, from 2026-10-23-02 p7_shot.sh): when the physical pointer is inside the FreeCAD
# main window frame (0,0 1600x1000), move it out with move_cursor scope desktop to (1800,300), wait
# 1 s, then capture the main window to <stem>.png. Pointer positions go to <stem>-pointer.txt.
cd "$(dirname "$0")"
stem=$1
pos() { cua-driver get_cursor_position '{}' | tr -d '\n '; }
inside() { p=$(pos); x=$(echo "$p" | sed 's/.*"x":\(-\?[0-9]*\).*/\1/'); y=$(echo "$p" | sed 's/.*"y":\(-\?[0-9]*\).*/\1/'); echo "$(date +%T) $p" >> "$stem-pointer.txt"; [ "$x" -ge 0 ] && [ "$x" -lt 1600 ] && [ "$y" -ge 0 ] && [ "$y" -lt 1000 ]; }
if inside; then echo '{"x":1800,"y":300,"scope":"desktop"}' | cua-driver call move_cursor > /dev/null; echo "$(date +%T) moved pointer out" >> "$stem-pointer.txt"; fi
sleep 1
uv run python r2_gui1.py shot "$stem" | sed -n 1,6p
inside && echo "WARNING pointer inside the window after capture" | tee -a "$stem-pointer.txt"
