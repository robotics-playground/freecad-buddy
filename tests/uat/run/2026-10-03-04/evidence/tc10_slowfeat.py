"""TC-10 harness fixture: a Part::FeaturePython whose execute() sleeps `Delay` seconds, then makes a
10x20x30 box. onDocumentRestored touches it so the first recompute after an open runs the delay.
Gives a recompute of known, bounded length without building pathological geometry."""
import time


class Slow:
    def __init__(self, obj):
        obj.Proxy = self
        obj.addProperty("App::PropertyFloat", "Delay", "Slow", "seconds execute() sleeps")

    def execute(self, obj):
        import Part
        if obj.Delay > 0:
            time.sleep(obj.Delay)
        obj.Shape = Part.makeBox(10, 20, 30)

    def onDocumentRestored(self, obj):
        obj.touch()

    def dumps(self):
        return {"kind": "slow"}

    def loads(self, state):
        return None
