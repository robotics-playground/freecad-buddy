#!/bin/bash
# usage: mutant.sh <label> <python-sed-script> <tests,comma> [timeout_s]
S=/c/Users/thuan/AppData/Local/Temp/claude/3d3814eab912640f/50958ed8-8fcb-4d26-a32d-c7025b2780ae/scratchpad/verifier-13-18/r2
F=/d/Work/Personal/Sources/fcb-verify-13-18/src/freecad_buddy/usecases/features.py
label=$1; edit=$2; tests=$3; to=${4:-600}
cp $F $S/features.orig
python - "$F" "$edit" <<'PY'
import sys
p, edit = sys.argv[1], sys.argv[2]
old, new = edit.split("|||")
src = open(p, encoding="utf-8").read()
assert src.count(old) == 1, ("count", src.count(old), old)
open(p, "w", encoding="utf-8", newline="").write(src.replace(old, new))
PY
(cd /d/Work/Personal/Sources/fcb-verify-13-18 && git diff --stat)
cd /d/Work/Personal/Sources/fcb-verify-13-18
start=$(date +%s)
FCB_TESTS="$tests" FREECAD_USER_HOME="$(cygpath -w $S/fchome)" timeout $to "/c/Program Files/FreeCAD 1.1/bin/freecadcmd.exe" -u "$(cygpath -w $S/cfg/user.cfg)" -s "$(cygpath -w $S/cfg/system.cfg)" "$(cygpath -w $S/run_selected.py)" > $S/mut-$label.raw 2>&1
rc=$?
end=$(date +%s)
cp $S/features.orig $F
(cd /d/Work/Personal/Sources/fcb-verify-13-18 && git status --porcelain src)
{ echo "label=$label rc=$rc elapsed=$((end-start))s"; tr '\r\t' '\n\n' < $S/mut-$label.raw | grep -a -E "^FEATURES_FILE|^RESULT|^RED|^(FAIL|ERROR):|Error: |AssertionError" | head -30; } > $S/mut-$label.out
cat $S/mut-$label.out
