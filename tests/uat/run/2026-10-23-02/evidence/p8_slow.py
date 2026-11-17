"""A FeaturePython proxy whose recompute sleeps for ``Seconds`` (TC-10-05: a body that takes a
measurable time to recompute). It lives in a module, not in the script_exec source, because
``preview_dry_run`` saves the document and reopens the copy, and FreeCAD restores a proxy by
importing its module and class."""

import time

import Part


class Slow:
    def __init__(self, obj, seconds):
        obj.addProperty("App::PropertyFloat", "Seconds")
        obj.Seconds = seconds
        obj.Proxy = self

    def execute(self, obj):
        time.sleep(obj.Seconds)
        obj.Shape = Part.makeBox(10, 10, 10)

    def dumps(self):
        return None

    def loads(self, state):
        return None
