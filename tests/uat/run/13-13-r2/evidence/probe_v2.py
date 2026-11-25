"""Verifier probes 2: script undo that empties the earlier stack; same-name undo."""
import sys
import unittest
from pathlib import Path
sys.path.insert(0, str(Path(r"C:\Users\thuan\AppData\Local\Temp\claude\3d3814eab912640f\17c8e5ee-89aa-4e27-ba05-1fe1774e804a\scratchpad\verifier-13-13\rt2\probes")))
from probe_a import _Fixture, log  # noqa: E402
from freecad_buddy.usecases import script_exec as se  # noqa: E402


class Empty(_Fixture):
    def _run(self, setup, code, label):
        for s in setup:
            self.run_script(s)
        before = list(self.document.UndoNames)
        env = self.run_script(code)
        c = env["structured_content"]
        after = list(self.document.UndoNames)
        undo = self.registry.document_undo(self.handle, expect_fingerprint=c["fingerprint_before"])
        log(label, "before", before, "after", after, "status", env["status"], "undo_steps", c["undo_steps"],
            "undid_note", se._SCRIPT_UNDID_NOTE in env["text"], "zero_note", se._NO_UNDO_STEP_NOTE in env["text"],
            "matches_pre_op", undo["structured_content"].get("matches_pre_op"),
            "H", self.document.Box.Height, "W", self.document.Box.Width)
        return env, undo

    def test_E1_undo_the_only_entry_then_write(self):
        env, undo = self._run(["doc.Box.Height = 12"], "doc.undo()\ndoc.Box.Width = 7", "E1")
        self.assertTrue(se._SCRIPT_UNDID_NOTE in env["text"] or undo["structured_content"].get("matches_pre_op"))

    def test_E2_undo_both_entries_then_write(self):
        env, undo = self._run(["doc.Box.Height = 12", "doc.Box.Height = 13"], "doc.undo()\ndoc.undo()\ndoc.Box.Width = 7", "E2")
        self.assertTrue(se._SCRIPT_UNDID_NOTE in env["text"] or undo["structured_content"].get("matches_pre_op"))

    def test_E3_undo_the_only_entry_no_write(self):
        env, undo = self._run(["doc.Box.Height = 12"], "doc.undo()", "E3")
        self.assertTrue(se._SCRIPT_UNDID_NOTE in env["text"] or undo["structured_content"].get("matches_pre_op"))

    def test_E4_same_name_undo_then_write(self):
        env, undo = self._run(["# same name probe\ndoc.Box.Height = 3"], "# same name probe\ndoc.undo()\ndoc.Box.Width = 7", "E4")
        self.assertTrue(se._SCRIPT_UNDID_NOTE in env["text"] or undo["structured_content"].get("matches_pre_op"))
