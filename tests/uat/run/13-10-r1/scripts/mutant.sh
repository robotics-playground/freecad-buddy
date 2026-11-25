#!/bin/bash
# usage: mutant.sh <label> <file> <python-old> <python-new> <tests>
S=/c/Users/thuan/AppData/Local/Temp/claude/3d3814eab912640f/50958ed8-8fcb-4d26-a32d-c7025b2780ae/scratchpad/verifier-13-10
R=/d/Work/Personal/Sources/fcb-verify-13-10
label=$1; file=$2; old=$3; new=$4; tests=$5
cd $R
python - "$file" "$old" "$new" <<'PY'
import sys
path, old, new = sys.argv[1:4]
text = open(path, encoding="utf-8").read()
assert text.count(old) == 1, f"old text found {text.count(old)} times"
open(path, "w", encoding="utf-8", newline="\n").write(text.replace(old, new))
PY
[ $? -ne 0 ] && { echo "$label: APPLY FAILED"; exit 1; }
git diff --stat | tail -1
FCB_REPO="$(cygpath -w $R)" FCB_TESTS="$tests" FCB_OUT="$(cygpath -w $S/mut-$label.out)" FREECAD_USER_HOME="$(cygpath -w $S/home)" "/c/Program Files/FreeCAD 1.1/bin/freecadcmd.exe" -u "$(cygpath -w $S/home/user.cfg)" -s "$(cygpath -w $S/home/system.cfg)" "$(cygpath -w $S/run_selected.py)" > $S/mut-$label.log 2>&1
echo "$label freecadcmd exit=$?"
git checkout -- "$file"; git status --short
cat $S/mut-$label.out 2>/dev/null || echo "(no result file)"
