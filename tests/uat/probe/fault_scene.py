"""Clean scene and done marker for the plant macros in ``faults/``. The probe never imports it.

A plant macro runs inside the FreeCAD that ``run_faults.py`` started, which put this folder on
``sys.path`` through ``-M``.
"""

import os

import FreeCAD
import FreeCADGui


def open_clean_scene():
    doc = FreeCAD.openDocument(os.environ["FCB_PROBE_SCENE"])
    # FreeCAD hides every object of a file saved without a GUI. Show the box, then clear the
    # modified flag, so the scene is the clean one the expectation describes.
    doc.getObject("Box").Visibility = True
    FreeCADGui.getDocument(doc.Name).Modified = False
    return doc


def mark_planted(error=""):
    """Write the done marker; its text is the plant error, empty when the fault is planted."""
    marker = os.environ["FCB_PROBE_PLANT_DONE"]
    # Write then rename, so the runner never reads a marker whose error text is still missing.
    with open(marker + ".tmp", "w", encoding="utf-8") as handle:
        handle.write(error)
    os.replace(marker + ".tmp", marker)
