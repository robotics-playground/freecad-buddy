"""Offline reader: the kernel part of a probe snapshot, read from a saved ``.FCStd``.

    freecadcmd tests/uat/probe/read_fcstd.py --pass <in.FCStd> <out.json>

FreeCADCmd imports this file as a module (``__name__`` is the file stem) and hides stdout, so
the code runs at import and the result goes to ``out.json``. Nothing may raise out of the
import: FreeCADCmd would then run the file a second time and exit 0. Exit codes: 0 read, 1
missing or unreadable file or ``out.json`` not written, 2 wrong arguments. On 1 and 2
``out.json`` is ``{"error": "<message>"}`` when its path is known. The document is opened, read
and closed, never saved.
"""

import json
import os
import sys

import FreeCAD
import snapshot

USAGE = "usage: freecadcmd read_fcstd.py --pass <in.FCStd> <out.json>"


def read(source):
    if not os.path.isfile(source):
        raise FileNotFoundError(f"no such file: {source}")
    doc = FreeCAD.openDocument(source)
    try:
        return {
            "freecad_version": snapshot.freecad_version(FreeCAD),
            "documents": [snapshot.read_document(doc)],
        }
    finally:
        FreeCAD.closeDocument(doc.Name)


def main(argv):
    passed = argv[argv.index("--pass") + 1 :] if "--pass" in argv else []
    if len(passed) == 2:
        source, out = passed
        try:
            result, code = read(source), 0
        except Exception as exc:
            result, code = {"error": f"{type(exc).__name__}: {exc}"}, 1
    else:
        out = passed[-1] if len(passed) > 2 else None
        result, code = {"error": f"{USAGE}; got {passed}"}, 2
    if out is None:
        return code
    try:
        with open(out, "w", encoding="utf-8") as handle:
            json.dump(result, handle, indent=1)
    except Exception:
        return code or 1
    return code


sys.exit(main(sys.argv))
