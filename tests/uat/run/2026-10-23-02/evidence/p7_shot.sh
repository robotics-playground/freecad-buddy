# p7_shot.sh <stem>: capture the FreeCAD main window only while the physical mouse pointer is outside
# it (a pointer over the 3D view makes FreeCAD draw a preselection highlight). Waits up to 120 s,
# records the pointer position before and after the capture in <stem>-pointer.txt.
stem=$1
inside() { p=$(cua-driver get_cursor_position '{}' | tr -d '\n '); x=$(echo "$p" | sed 's/.*"x":\(-\?[0-9]*\).*/\1/'); y=$(echo "$p" | sed 's/.*"y":\(-\?[0-9]*\).*/\1/'); echo "$(date +%T) $p" >> "$stem-pointer.txt"; [ "$x" -ge 0 ] && [ "$x" -lt 1600 ] && [ "$y" -ge 0 ] && [ "$y" -lt 1000 ]; }
for i in $(seq 1 60); do inside || break; sleep 2; done
sleep 1
uv run python p1_gui.py shot "$stem" | sed -n 2,4p
inside && echo "WARNING pointer inside the window after capture" | tee -a "$stem-pointer.txt"
cat "$stem-pointer.txt" | tail -3
