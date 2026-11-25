"""Verifier probes at 73b9fe0f: RT notes and attacks on the new undo/text code. FACT lines are the evidence."""

import sys
import time
import unittest
from pathlib import Path

import FreeCAD as App

sys.path.insert(0, str(Path(r"C:\Users\thuan\AppData\Local\Temp\claude\3d3814eab912640f\17c8e5ee-89aa-4e27-ba05-1fe1774e804a\scratchpad\verifier-13-13\rt2\probes")))
from probe_a import _Fixture, log  # noqa: E402

from freecad_buddy.usecases import script_exec as se  # noqa: E402


def facts(env, label):
    c = env.get("structured_content") or {}
    log(label, "status", env.get("status"), "undo_steps", c.get("undo_steps"),
        "changed", [x.get("name") for x in c.get("changed") or []])
    log(label, "notes", [ln for ln in (env.get("text") or "").splitlines() if ":" not in ln[:30] or ln.startswith("undo_steps") or ln.startswith("the script") or ln.startswith("result")][-4:])


def note_in(env, note):
    return note in (env.get("text") or "")


class RTNotes(_Fixture):
    def test_RT2_full_stack_one_name_gives_null_and_note(self):
        for i in range(21):
            self.run_script(f"import Part\ndoc.Box.Height = {10 + i}")
        log("names", len(self.document.UndoNames), set(self.document.UndoNames))
        env = self.run_script("import Part\ndoc.Box.Height = 50")
        facts(env, "RT2")
        self.assertIsNone(env["structured_content"]["undo_steps"])
        self.assertTrue(note_in(env, se._UNDO_UNKNOWN_NOTE))

    def test_RT3_script_undo_gives_note(self):
        self.run_script("doc.Box.Height = 12")
        env = self.run_script("doc.undo()\ndoc.Box.Width = 7")
        facts(env, "RT3")
        self.assertTrue(note_in(env, se._SCRIPT_UNDID_NOTE))

    def test_RT4_stdout_kept_after_close(self):
        env = self.run_script("print('kept line')\nimport sys\nsys.stdout.close()\ndoc.Box.Width = 6")
        facts(env, "RT4")
        log("RT4 stdout", repr(env["structured_content"]["stdout"]))
        self.assertEqual(env["status"], "OK")
        self.assertIn("kept line", env["structured_content"]["stdout"])

    def test_RT6_clear_undos_note(self):
        self.run_script("doc.Box.Height = 12")
        env = self.run_script("doc.Box.Width = 6\ndoc.clearUndos()")
        facts(env, "RT6a")
        self.assertTrue(note_in(env, se._UNDO_CLEARED_NOTE))

    def test_RT6_undo_mode_zero_note(self):
        env = self.run_script("doc.Box.Width = 6\ndoc.UndoMode = 0")
        facts(env, "RT6b")
        self.assertTrue(note_in(env, se._UNDO_CLEARED_NOTE))


class Attacks(_Fixture):
    def test_A1_redo_after_document_undo_then_script_redo(self):
        self.run_script("doc.Box.Height = 12")
        before = self.run_script("doc.Box.Height = 13")
        self.registry.document_undo(self.handle)
        log("A1 names", list(self.document.UndoNames), "redo", list(self.document.RedoNames))
        env = self.run_script("doc.redo()")
        facts(env, "A1")
        log("A1 names after", list(self.document.UndoNames), "Height", self.document.Box.Height)
        content = env["structured_content"]
        undo = self.registry.document_undo(self.handle, expect_fingerprint=content["fingerprint_before"])
        log("A1 document_undo matches", undo["structured_content"].get("matches_pre_op"), "Height", self.document.Box.Height)
        self.assertFalse(note_in(env, se._SCRIPT_UNDID_NOTE))
        del before

    def test_A2_undo_then_redo_inside_script(self):
        self.run_script("doc.Box.Height = 12")
        env = self.run_script("doc.undo()\ndoc.redo()")
        facts(env, "A2")
        log("A2 names", list(self.document.UndoNames), "Height", self.document.Box.Height)

    def test_A3_undo_two_steps_then_write(self):
        self.run_script("doc.Box.Height = 12")
        self.run_script("doc.Box.Height = 13")
        self.run_script("doc.Box.Length = 14")
        env = self.run_script("doc.undo()\ndoc.undo()\ndoc.Box.Width = 7")
        facts(env, "A3")
        log("A3 names", list(self.document.UndoNames))
        self.assertEqual(env["structured_content"]["undo_steps"], 1)
        self.assertTrue(note_in(env, se._SCRIPT_UNDID_NOTE))

    def test_A4_undo_two_steps_no_write(self):
        self.run_script("doc.Box.Height = 12")
        self.run_script("doc.Box.Height = 13")
        env = self.run_script("doc.undo()\ndoc.undo()")
        facts(env, "A4")
        self.assertTrue(note_in(env, se._SCRIPT_UNDID_NOTE))

    def test_A5_undo_then_write_with_the_same_name(self):
        first = "# same name probe"
        d = self.document
        d.openTransaction(f"script_exec {first}")
        d.Box.Height = 3
        d.commitTransaction()
        names_before = list(d.UndoNames)
        env = self.run_script(f"{first}\ndoc.undo()\ndoc.Box.Width = 7")
        facts(env, "A5")
        log("A5 names before", names_before, "after", list(d.UndoNames), "Height", d.Box.Height, "Width", d.Box.Width)
        undo = self.registry.document_undo(self.handle, expect_fingerprint=env["structured_content"]["fingerprint_before"])
        log("A5 document_undo matches", undo["structured_content"].get("matches_pre_op"), "Height", d.Box.Height, "Width", d.Box.Width)

    def test_A6_huge_repr(self):
        t0 = time.time()
        env = self.run_script("class R:\n    def __repr__(self):\n        return 'x' * 5_000_000\nresult = R()")
        log("A6 status", env["status"], "len value_repr", len(env["structured_content"]["value_repr"] or ""), "seconds", round(time.time() - t0, 2))

    def test_A7_non_str_repr(self):
        env = self.run_script("class R:\n    def __repr__(self):\n        return 42\nresult = R()\ndoc.Box.Width = 8")
        facts(env, "A7")
        log("A7 value_repr", env["structured_content"]["value_repr"])
        self.assertEqual(env["status"], "OK")

    def test_A8_keyboard_interrupt_during_commit(self):
        code = (
            "from freecad_buddy.usecases import shim\n"
            "_orig = shim.commit_active_transaction\n"
            "def _boom():\n"
            "    shim.commit_active_transaction = _orig\n"
            "    raise KeyboardInterrupt('during commit')\n"
            "shim.commit_active_transaction = _boom\n"
            "doc.Box.Width = 9"
        )
        methods = self.methods()
        escaped = None
        env = None
        try:
            env = methods.dispatch("script_exec", {"doc": self.handle, "code": code})
        except BaseException as exc:  # noqa: BLE001
            escaped = repr(exc)
        log("A8 escaped", escaped, "status", env and env.get("status"), "detail", env and env.get("detail"))
        log("A8 active", App.getActiveTransaction(), "names", list(self.document.UndoNames), "Width", self.document.Box.Width)
        second = methods.dispatch("script_exec", {"doc": self.handle, "code": "result = 2"})
        log("A8 next call", second["status"])
        self.assertIsNone(escaped)

    def test_A9_keyboard_interrupt_in_document_commit_via_recompute(self):
        # A FeaturePython whose execute raises KeyboardInterrupt runs inside the bracket recompute.
        code = (
            "class K:\n"
            "    def __init__(self, obj):\n"
            "        obj.Proxy = self\n"
            "    def execute(self, obj):\n"
            "        raise KeyboardInterrupt('in recompute')\n"
            "K(doc.addObject('Part::FeaturePython', 'K'))"
        )
        methods = self.methods()
        escaped = None
        env = None
        try:
            env = methods.dispatch("script_exec", {"doc": self.handle, "code": code})
        except BaseException as exc:  # noqa: BLE001
            escaped = repr(exc)
        log("A9 escaped", escaped, "status", env and env.get("status"), "detail", env and str(env.get("detail"))[:200])
        log("A9 active", App.getActiveTransaction(), "names", list(self.document.UndoNames))
