#!/bin/bash
# usage: tc-07-fcbread.sh <file>...  (fcb env FreeCAD 1.1.3, outside the bridge)
FCB="$USERPROFILE/micromamba/envs/fcb"
cd "$(dirname "$0")"
PYTHONPATH="$FCB/Library/bin;$FCB/Library/lib" PATH="$FCB/Library/bin:$PATH" "$FCB/python.exe" tc-07-fcbread.py "$@" 2>/dev/null | grep '^{'
