#!/bin/bash
# usage: tc-07-topshot.sh <png> : click the navigation cube TOP face (pixel, background), FreeCAD Fit All, capture
cd "$(dirname "$0")"
P=$(python -c "import json;print(json.load(open('fc.json'))['pid'])"); W=$(python -c "import json;print(json.load(open('fc.json'))['window_id'])")
echo "{\"pid\":$P,\"window_id\":$W,\"x\":1487,\"y\":268}" | cua-driver click | tr -d '\n '; echo
sleep 1.5
uv run python gui.py fitshot "$1"
