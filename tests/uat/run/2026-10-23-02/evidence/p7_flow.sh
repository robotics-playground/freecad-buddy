# Phase P7 GUI flow helpers (bash, run from evidence/):
#   p7_flow.sh begin <tag> <golden stem> [prev doc ...]   close prev docs, open golden, Show All, fit, capture <tag>-before
#   p7_flow.sh end <tag> <doc>                             Show All, fit, capture <tag>-after, pixel diff against <tag>-before
set -e
action=$1; tag=$2
if [ "$action" = begin ]; then
  stem=$3; shift 3
  [ $# -gt 0 ] && uv run python p7_tc09.py close "$tag" "$@" | grep CHECK
  H=$(uv run python p7_tc09.py open "$tag" "$stem" | grep '^H=')
  echo "$H"; doc=$(echo "$H" | sed 's/^H=\([^ ]*\).*/\1/')
  uv run python p1_gui.py showall | tail -1
  uv run python p7_tc09.py fit "$tag" "$doc" | tail -1 | cut -c1-160
  bash p7_shot.sh "$tag-before"
else
  doc=$3
  uv run python p1_gui.py showall | tail -1
  uv run python p7_tc09.py fit "$tag" "$doc" | tail -1 | cut -c1-160
  bash p7_shot.sh "$tag-after"
  uv run python p0_diff.py "$tag-before.png" "$tag-after.png"
fi
