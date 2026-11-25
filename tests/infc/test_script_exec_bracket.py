"""In-FreeCAD tests for the ``script_exec`` observe-only bracket (stdlib unittest).

Run via ``FreeCADCmd tests/run_tests.py``. Each test names the case of the Story 13-13 I/O matrix
it pins. The FreeCAD behaviours the bracket relies on were measured in FreeCAD 1.1.4: an empty
``commitTransaction`` leaves the application-level transaction named and open
(``App/Document.cpp:330-340, 464-472``), opening a transaction while one is active commits it
(``Document.cpp:363-365``), and ``closeDocument`` clears the application-level transaction.
"""

import io
import sys
import time
import unittest
from contextlib import redirect_stderr
from unittest import mock

import FreeCAD as App
import Part

from freecad_buddy.adapters.marshal import Marshal, MarshalTimeout, ThreadExecutor
from freecad_buddy.usecases import confirm, result_projection, shim
from freecad_buddy.usecases import script_exec as script_exec_module
from freecad_buddy.usecases.documents import DocumentRegistry, ValidationError
from freecad_buddy.usecases.fingerprint import fingerprint
from freecad_buddy.usecases.script_exec import script_exec

BOX_WIDTH = 20.0
TIMING_OBJECTS = 30
TIMING_HOLES_PER_SIDE = 20
TIMING_FACES = 6 + TIMING_HOLES_PER_SIDE**2
TIMING_BUDGET_S = 30.0


class _BracketFixture(unittest.TestCase):
    """A registry holding one document with a single ``Part::Box`` named ``Box``."""

    def setUp(self):
        self._posture = confirm.set_auto_approve(True)
        self.registry = DocumentRegistry()
        self.handle = self.registry.document_create("bracket")["structured_content"]["doc"]
        self.document = self.registry.with_document(self.handle, lambda h, d: d)
        box = self.document.addObject("Part::Box", "Box")
        box.Width = BOX_WIDTH
        self.document.recompute()

    def tearDown(self):
        confirm.set_auto_approve(self._posture)
        for name in list(App.listDocuments().keys()):
            App.closeDocument(name)

    def run_script(self, code, recompute=True):
        return script_exec(self.registry, self.handle, code, recompute)

    def structured(self, envelope):
        return envelope["structured_content"]

    def undo_names(self):
        return list(self.document.UndoNames)


class BracketTest(_BracketFixture):
    def test_Should_record_one_undo_step_and_list_the_object_When_a_script_writes_one_property(
        self,
    ):
        # Arrange
        code = "doc.Box.Width = 5"

        # Act
        envelope = self.run_script(code)

        # Assert
        content = self.structured(envelope)
        self.assertEqual(envelope["status"], "OK")
        self.assertEqual([entry["name"] for entry in content["changed"]], ["Box"])
        self.assertEqual(content["undo_steps"], 1)
        self.assertEqual(self.undo_names()[0], "script_exec doc.Box.Width = 5")
        self.assertIsNone(App.getActiveTransaction())
        self.assertIsNotNone(result_projection.recall(content["fingerprint_before"]))
        self.assertIsNotNone(result_projection.recall(content["fingerprint_after"]))

    def test_Should_report_matches_pre_op_When_document_undo_runs_after_a_script_write(self):
        # Arrange
        content = self.structured(self.run_script("doc.Box.Width = 5"))

        # Act
        undone = self.registry.document_undo(
            self.handle, expect_fingerprint=content["fingerprint_before"]
        )

        # Assert
        self.assertTrue(undone["structured_content"]["matches_pre_op"])
        self.assertEqual(self.document.Box.Width, BOX_WIDTH)

    def test_Should_leave_no_transaction_open_and_report_zero_steps_When_the_script_is_read_only(
        self,
    ):
        # Arrange
        code = "result = doc.Box.Shape.Volume"

        # Act
        envelope = self.run_script(code)

        # Assert
        content = self.structured(envelope)
        self.assertEqual(envelope["status"], "OK")
        self.assertIsNone(App.getActiveTransaction())
        self.assertEqual(content["undo_steps"], 0)
        self.assertEqual(content["changed"], [])
        self.assertIn("undo_steps 0", envelope["text"])

    def test_Should_not_name_a_later_change_after_the_script_When_the_script_is_read_only(self):
        # Arrange
        self.run_script("doc.Box.Visibility = False")

        # Act
        self.document.openTransaction("later")
        self.document.Box.Height = 7
        self.document.commitTransaction()

        # Assert
        self.assertEqual(self.undo_names()[0], "later")

    def test_Should_report_nothing_changed_When_the_script_aborts_its_own_transaction(self):
        # Arrange
        code = "doc.Box.Width = 5\ndoc.abortTransaction()"

        # Act
        envelope = self.run_script(code)

        # Assert
        content = self.structured(envelope)
        self.assertEqual(envelope["status"], "OK")
        self.assertEqual(content["changed"], [])
        self.assertEqual(content["undo_steps"], 0)
        self.assertEqual(self.document.Box.Width, BOX_WIDTH)

    def test_Should_report_two_undo_steps_When_the_script_opens_its_own_transaction(self):
        # Arrange
        code = 'doc.Box.Length = 11\ndoc.openTransaction("own")\ndoc.Box.Width = 5'

        # Act
        envelope = self.run_script(code)

        # Assert
        self.assertEqual(self.structured(envelope)["undo_steps"], 2)
        self.assertEqual(self.undo_names()[0], "own")
        self.assertIsNone(App.getActiveTransaction())

    def test_Should_not_record_the_write_When_the_script_commits_the_bridge_transaction_first(
        self,
    ):
        # Arrange
        code = "doc.Box.Length = 11\ndoc.commitTransaction()\ndoc.Box.Width = 5"

        # Act
        envelope = self.run_script(code)
        self.registry.document_undo(self.handle)

        # Assert
        content = self.structured(envelope)
        self.assertEqual(content["undo_steps"], 1)
        self.assertEqual([entry["name"] for entry in content["changed"]], ["Box"])
        self.assertEqual(self.document.Box.Length, 10)
        self.assertEqual(self.document.Box.Width, 5)

    def test_Should_revert_only_the_pending_change_When_the_script_calls_doc_undo(self):
        # Arrange
        self.run_script("doc.Box.Length = 11")
        steps_before = len(self.undo_names())

        # Act
        envelope = self.run_script("doc.Box.Width = 5\ndoc.undo()")

        # Assert
        self.assertEqual(envelope["status"], "OK")
        self.assertEqual(self.document.Box.Length, 11)
        self.assertEqual(self.document.Box.Width, BOX_WIDTH)
        self.assertEqual(len(self.undo_names()), steps_before)
        self.assertEqual(self.structured(envelope)["undo_steps"], 0)

    def test_Should_recompute_When_the_handler_gets_a_null_recompute(self):
        # Arrange
        from freecad_buddy.hosts import tool_catalog

        handler = tool_catalog.SCRIPT_EXEC_SPEC.make_handler(self.registry, None, None, None, None)

        # Act
        handler(doc=self.handle, code="doc.Box.Length = 12", recompute=None)

        # Assert
        self.assertNotIn("Touched", self.document.Box.State)

    def test_Should_name_the_transaction_after_the_first_non_blank_line_When_code_has_a_leader(
        self,
    ):
        # Arrange
        code = "\n  \n  # set width   \ndoc.Box.Width = 5"

        # Act
        self.run_script(code)

        # Assert
        self.assertEqual(self.undo_names()[0], "script_exec # set width")

    def test_Should_cut_the_transaction_name_to_80_characters_When_the_line_is_long(self):
        # Arrange
        padding = "x" * 200
        code = f"doc.Box.Width = 5  # {padding}"

        # Act
        self.run_script(code)

        # Assert
        self.assertEqual(len(self.undo_names()[0]), len("script_exec ") + 80)

    def test_Should_use_the_bare_prefix_When_the_code_has_no_non_blank_line(self):
        # Arrange
        code = "  \n\t\n"

        # Act
        self.run_script(code)

        # Assert
        self.assertEqual(script_exec_module._transaction_name(code), "script_exec")

    def test_Should_refuse_When_the_code_is_empty(self):
        # Arrange
        act = lambda: self.run_script("")  # noqa: E731

        # Act / Assert
        self.assertRaises(ValidationError, act)

    def test_Should_run_the_script_with_zero_steps_When_undo_is_unavailable(self):
        # Arrange
        with mock.patch.object(shim, "enable_undo", return_value=False):
            # Act
            envelope = self.run_script("doc.Box.Width = 5")

        # Assert
        self.assertEqual(envelope["status"], "OK")
        self.assertEqual(self.structured(envelope)["undo_steps"], 0)
        self.assertEqual(self.document.Box.Width, 5)

    def test_Should_not_run_undo_setup_after_the_script_When_the_script_sets_undo_mode_zero(self):
        # Arrange
        calls = []
        real = shim.enable_undo

        def spy(document):
            calls.append(len(calls))
            return real(document)

        # Act
        with mock.patch.object(shim, "enable_undo", side_effect=spy):
            envelope = self.run_script("doc.UndoMode = 0\ndoc.Box.Width = 5")

        # Assert
        self.assertEqual(envelope["status"], "OK")
        self.assertEqual(calls, [0])


class OtherDocumentTest(_BracketFixture):
    def setUp(self):
        super().setUp()
        other_handle = self.registry.document_create("other")["structured_content"]["doc"]
        self.other = self.registry.with_document(other_handle, lambda h, d: d)
        self.other_handle = other_handle
        self.other.UndoMode = 1
        box = self.other.addObject("Part::Box", "Box")
        box.Width = BOX_WIDTH
        self.other.recompute()

    def test_Should_keep_the_other_documents_change_undoable_When_the_script_changes_only_it(self):
        # Arrange
        code = f'App.getDocument("{self.other.Name}").Box.Width = 5'

        # Act
        envelope = self.run_script(code)

        # Assert
        content = self.structured(envelope)
        self.assertEqual(envelope["status"], "OK")
        self.assertEqual(content["changed"], [])
        self.assertEqual(content["undo_steps"], 0)
        self.assertIsNone(App.getActiveTransaction())
        self.assertFalse(self.other.HasPendingTransaction)
        self.assertEqual(self.other.UndoNames[0], f"script_exec {code}")
        self.assertEqual(self.other.Box.Width, 5)

    def test_Should_revert_the_other_documents_change_When_document_undo_runs_on_it(self):
        # Arrange
        code = f'App.getDocument("{self.other.Name}").Box.Width = 5'
        self.run_script(code)

        # Act
        undone = self.registry.document_undo(self.other_handle)

        # Assert
        self.assertEqual(undone["status"], "OK")
        self.assertEqual(self.other.Box.Width, BOX_WIDTH)


class ErrorPathTest(_BracketFixture):
    def test_Should_return_invalid_input_and_keep_the_bridge_serving_When_a_script_exits(self):
        # Arrange
        for exception in ("SystemExit(3)", "KeyboardInterrupt()", "GeneratorExit()"):
            with self.subTest(exception=exception):
                # Act
                envelope = self.run_script(f"raise {exception}")
                follow_up = self.run_script("result = 1")

                # Assert
                self.assertEqual(envelope["status"], "INVALID_INPUT")
                self.assertEqual(envelope["detail"]["code"], "exec.python_error")
                self.assertEqual(envelope["detail"]["data"]["exception"], exception.split("(")[0])
                self.assertEqual(follow_up["status"], "OK")

    def test_Should_report_the_partial_change_and_no_stderr_When_a_script_raises_after_a_write(
        self,
    ):
        # Arrange
        code = "doc.Box.Width = 5\nraise ValueError('boom')"
        captured = io.StringIO()

        # Act
        with redirect_stderr(captured):
            envelope = self.run_script(code)

        # Assert
        content = self.structured(envelope)
        self.assertEqual(envelope["status"], "INVALID_INPUT")
        self.assertEqual(envelope["detail"]["code"], "exec.python_error")
        self.assertEqual(envelope["detail"]["data"]["exception"], "ValueError")
        self.assertIn("boom", envelope["detail"]["data"]["traceback"])
        self.assertLessEqual(len(envelope["detail"]["data"]["traceback"]), 4000)
        self.assertEqual([entry["name"] for entry in content["changed"]], ["Box"])
        self.assertEqual(content["undo_steps"], 1)
        self.assertEqual(captured.getvalue(), "")
        self.assertEqual(self.document.Box.Width, 5)

    def test_Should_keep_the_exception_line_and_drop_the_bridge_frame_When_the_traceback_is_long(
        self,
    ):
        # Arrange
        code = "def down(n):\n    return down(n - 1) if n else 1 / 0\ndown(150)"

        # Act
        envelope = self.run_script(code)

        # Assert
        trace = envelope["detail"]["data"]["traceback"]
        self.assertLessEqual(len(trace), 4000)
        self.assertTrue(trace.endswith("ZeroDivisionError: division by zero\n"))
        self.assertNotIn("script_exec.py", trace)

    def test_Should_cut_to_the_tail_When_distinct_frames_make_the_traceback_exceed_the_limit(self):
        # Arrange
        lines = [f"def f{index}():\n    f{index + 1}()" for index in range(200)]
        lines.append("def f200():\n    raise ValueError('deep')")
        code = "\n".join(lines) + "\nf0()"

        # Act
        envelope = self.run_script(code)

        # Assert
        trace = envelope["detail"]["data"]["traceback"]
        self.assertEqual(len(trace), 4000)
        self.assertTrue(trace.endswith("ValueError: deep\n"))
        self.assertNotIn("Traceback (most recent call last)", trace)

    def test_Should_drop_the_bridge_frame_When_the_script_has_a_syntax_error(self):
        # Arrange
        code = "def ("

        # Act
        envelope = self.run_script(code)

        # Assert
        trace = envelope["detail"]["data"]["traceback"]
        self.assertEqual(envelope["detail"]["code"], "exec.python_error")
        self.assertIn("SyntaxError", trace)
        self.assertNotIn("script_exec.py", trace)

    def test_Should_return_recompute_error_and_keep_the_change_When_a_script_invalidates_a_box(
        self,
    ):
        # Arrange
        code = "doc.Box.Length = 0"

        # Act
        envelope = self.run_script(code)

        # Assert
        content = self.structured(envelope)
        self.assertEqual(envelope["status"], "RECOMPUTE_ERROR")
        self.assertEqual(content["new_errors"], ["Box"])
        self.assertEqual(content["undo_steps"], 1)
        self.assertEqual(self.document.Box.Length, 0)
        self.assertIn("Box", envelope["detail"]["message"])

    def test_Should_return_recompute_error_and_keep_the_change_When_a_script_breaks_a_pad(self):
        # Arrange
        body = self.document.addObject("PartDesign::Body", "Body")
        sketch = body.newObject("Sketcher::SketchObject", "Sketch")
        corners = ((0, 0, 0), (10, 0, 0), (10, 10, 0), (0, 10, 0))
        for index, start in enumerate(corners):
            end = corners[(index + 1) % len(corners)]
            sketch.addGeometry(Part.LineSegment(App.Vector(*start), App.Vector(*end)), False)
        pad = body.newObject("PartDesign::Pad", "Pad")
        pad.Profile = sketch
        pad.Length = 5
        self.document.recompute()

        # Act
        envelope = self.run_script("doc.Pad.Length = 0")

        # Assert
        content = self.structured(envelope)
        self.assertEqual(envelope["status"], "RECOMPUTE_ERROR")
        self.assertIn("Pad", content["new_errors"])
        self.assertEqual(self.document.Pad.Length, 0)

    def test_Should_not_count_an_already_invalid_object_When_the_script_leaves_it_invalid(self):
        # Arrange
        self.run_script("doc.Box.Length = 0")

        # Act
        envelope = self.run_script("doc.Box.Height = 3")

        # Assert
        self.assertEqual(envelope["status"], "OK")
        self.assertEqual(self.structured(envelope)["new_errors"], [])

    def test_Should_leave_the_object_touched_When_recompute_is_false(self):
        # Arrange
        code = "doc.Box.Length = 12"

        # Act
        envelope = self.run_script(code, recompute=False)

        # Assert
        self.assertEqual(envelope["status"], "OK")
        self.assertIn("Touched", self.document.Box.State)


class BracketFailureTest(_BracketFixture):
    def test_Should_return_spec_failed_and_not_run_the_script_When_fingerprint_before_raises(self):
        # Arrange
        failing = mock.Mock(side_effect=RuntimeError("no serializer"))
        with mock.patch.object(script_exec_module, "fingerprint", failing):
            # Act
            envelope = self.run_script("doc.Box.Width = 5")

        # Assert
        self.assertEqual(envelope["status"], "SPEC_FAILED")
        self.assertEqual(envelope["detail"]["code"], "exec.bracket_failed")
        self.assertEqual(envelope["detail"]["data"]["phase"], "fingerprint_before")
        self.assertEqual(self.document.Box.Width, BOX_WIDTH)
        self.assertIsNone(App.getActiveTransaction())

    def test_Should_return_recompute_error_and_keep_changes_When_fingerprint_after_raises(self):
        # Arrange
        real = fingerprint
        calls = []

        def second_call_raises(document):
            calls.append(document)
            if len(calls) == 2:
                raise RuntimeError("serializer died")
            return real(document)

        with mock.patch.object(script_exec_module, "fingerprint", second_call_raises):
            # Act
            envelope = self.run_script("doc.Box.Width = 5")

        # Assert
        content = self.structured(envelope)
        self.assertEqual(envelope["status"], "RECOMPUTE_ERROR")
        self.assertEqual(envelope["detail"]["code"], "exec.bracket_failed")
        self.assertEqual(envelope["detail"]["data"]["phase"], "fingerprint_after")
        self.assertIsNone(content["fingerprint_after"])
        self.assertEqual(content["undo_steps"], 1)
        self.assertEqual(self.document.Box.Width, 5)

    def test_Should_return_recompute_error_When_the_commit_phase_raises(self):
        # Arrange
        failing = mock.Mock(side_effect=RuntimeError("commit refused"))
        with mock.patch.object(shim, "commit_active_transaction", failing):
            # Act
            envelope = self.run_script("doc.Box.Width = 5")

        # Assert
        self.assertEqual(envelope["status"], "RECOMPUTE_ERROR")
        self.assertEqual(envelope["detail"]["data"]["phase"], "commit")
        self.assertEqual(self.document.Box.Width, 5)

    def test_Should_return_recompute_error_When_the_recompute_phase_raises(self):
        # Arrange
        self.document.UndoMode = 1
        document = _RaisingDocument(self.document, "recompute")

        # Act
        envelope = script_exec_module._run_bracket(self.handle, document, "doc.Box.Width = 5", True)

        # Assert
        self.assertEqual(envelope["status"], "RECOMPUTE_ERROR")
        self.assertEqual(envelope["detail"]["data"]["phase"], "recompute")
        self.assertIsNone(App.getActiveTransaction())
        self.assertFalse(self.document.HasPendingTransaction)
        self.assertEqual(self.undo_names()[0], "script_exec doc.Box.Width = 5")

    def test_Should_prefer_invalid_input_When_the_script_raised_and_the_bracket_also_failed(self):
        # Arrange
        real = fingerprint
        calls = []

        def second_call_raises(document):
            calls.append(document)
            if len(calls) == 2:
                raise RuntimeError("serializer died")
            return real(document)

        with mock.patch.object(script_exec_module, "fingerprint", second_call_raises):
            # Act
            envelope = self.run_script("doc.Box.Width = 5\nraise ValueError('boom')")

        # Assert
        self.assertEqual(envelope["status"], "INVALID_INPUT")
        self.assertEqual(envelope["detail"]["data"]["bracket_phase"], "fingerprint_after")

    def test_Should_return_ok_with_null_fingerprint_after_When_the_script_closes_its_document(
        self,
    ):
        # Arrange
        code = "FreeCAD.closeDocument(doc.Name)"

        # Act
        envelope = self.run_script(code)

        # Assert
        content = self.structured(envelope)
        self.assertEqual(envelope["status"], "OK")
        self.assertIsNone(content["fingerprint_after"])
        self.assertEqual(content["changed"], [])
        self.assertEqual(content["new_errors"], [])
        self.assertIn(self.handle, envelope["text"])
        self.assertIsNone(App.getActiveTransaction())

    def test_Should_not_break_the_bracket_When_the_script_patches_the_fingerprint_module(self):
        # Arrange
        code = (
            "import freecad_buddy.usecases.fingerprint as module\n"
            "module.fingerprint = lambda document: 1 / 0"
        )

        # Act
        try:
            envelope = self.run_script(code)
        finally:
            from freecad_buddy.usecases import fingerprint as module

            module.fingerprint = fingerprint

        # Assert
        self.assertEqual(envelope["status"], "OK")

    def test_Should_return_spec_failed_When_a_pre_script_read_raises(self):
        # Arrange
        failing = mock.Mock(side_effect=RuntimeError("isValid died"))
        with mock.patch.object(script_exec_module, "invalid_objects", failing):
            # Act
            envelope = self.run_script("doc.Box.Width = 5")

        # Assert
        self.assertEqual(envelope["status"], "SPEC_FAILED")
        self.assertEqual(envelope["detail"]["data"]["phase"], "observe_before")
        self.assertIn("observe_before", envelope["text"])
        self.assertEqual(self.document.Box.Width, BOX_WIDTH)

    def test_Should_report_the_script_error_and_keep_the_changes_When_a_post_script_read_raises(
        self,
    ):
        # Arrange
        failing = mock.Mock(side_effect=RuntimeError("diff died"))
        with mock.patch.object(result_projection, "changed_objects", failing):
            # Act
            envelope = self.run_script("doc.Box.Width = 5\nraise ValueError('boom')")

        # Assert
        self.assertEqual(envelope["status"], "INVALID_INPUT")
        self.assertEqual(envelope["detail"]["data"]["bracket_phase"], "observe")
        self.assertEqual(self.document.Box.Width, 5)
        self.assertIsNone(App.getActiveTransaction())

    def test_Should_say_undo_is_unavailable_When_the_document_cannot_enable_undo(self):
        # Arrange
        with mock.patch.object(shim, "enable_undo", return_value=False):
            # Act
            envelope = self.run_script("doc.Box.Width = 5")

        # Assert
        self.assertIn("undo is unavailable", envelope["text"])
        self.assertNotIn("would revert an earlier step", envelope["text"])

    def test_Should_close_the_transaction_and_name_the_commit_When_the_document_commit_raises(self):
        # Arrange
        self.document.UndoMode = 1
        document = _RaisingDocument(self.document, "commitTransaction")

        # Act
        envelope = script_exec_module._run_bracket(self.handle, document, "doc.Box.Width = 5", True)

        # Assert
        self.assertEqual(envelope["status"], "RECOMPUTE_ERROR")
        self.assertEqual(envelope["detail"]["data"]["phase"], "commit")
        self.assertIsNone(App.getActiveTransaction())
        self.assertFalse(self.document.HasPendingTransaction)

    def test_Should_name_both_failures_When_the_recompute_and_the_commit_raise(self):
        # Arrange
        self.document.UndoMode = 1
        document = _FailsRecomputeAndCommit(self.document)

        # Act
        with mock.patch.object(script_exec_module, "_any_touched", return_value=True):
            envelope = script_exec_module._run_bracket(
                self.handle, document, "doc.Box.Width = 5", True
            )

        # Assert
        self.assertEqual(envelope["detail"]["data"]["phase"], "recompute")
        self.assertIn("commitTransaction died", envelope["detail"]["message"])
        self.assertIsNone(App.getActiveTransaction())

    def test_Should_keep_undo_steps_and_skip_the_zero_note_When_a_post_script_read_raises(self):
        # Arrange
        real = script_exec_module.invalid_objects
        calls = []

        def second_call_raises(document):
            calls.append(document)
            if len(calls) == 2:
                raise RuntimeError("isValid died")
            return real(document)

        with mock.patch.object(script_exec_module, "invalid_objects", second_call_raises):
            # Act
            envelope = self.run_script("doc.Box.Width = 5")

        # Assert
        self.assertEqual(envelope["status"], "RECOMPUTE_ERROR")
        self.assertEqual(self.structured(envelope)["undo_steps"], 1)
        self.assertNotIn("undo_steps 0", envelope["text"])

    def test_Should_return_an_envelope_When_the_script_closed_its_document_and_the_close_raises(
        self,
    ):
        # Arrange
        failing = mock.Mock(side_effect=RuntimeError("close died"))
        with mock.patch.object(shim, "commit_active_transaction", failing):
            # Act
            envelope = self.run_script("FreeCAD.closeDocument(doc.Name)")

        # Assert
        self.assertEqual(envelope["status"], "RECOMPUTE_ERROR")
        self.assertEqual(envelope["detail"]["data"]["phase"], "commit")
        self.assertIsNone(self.structured(envelope)["fingerprint_after"])


class _RaisingDocument:
    """A document proxy whose ``member`` raises; every other member is the real document's."""

    def __init__(self, document, member):
        self._document = document
        self._member = member

    def __getattr__(self, name):
        if name == self._member:

            def raises(*args, **kwargs):
                raise RuntimeError(f"{name} died")

            return raises
        return getattr(self._document, name)


class _FailsRecomputeAndCommit(_RaisingDocument):
    """A document proxy whose ``recompute`` and ``commitTransaction`` both raise."""

    def __init__(self, document):
        super().__init__(document, "commitTransaction")

    def recompute(self, *args, **kwargs):
        raise RuntimeError("recompute died")


class UndoStackTest(_BracketFixture):
    def test_Should_count_one_added_step_When_the_undo_stack_is_full(self):
        # Arrange
        for index in range(25):
            self.run_script(f"doc.Box.Width = {index + 1}")
        stack_size = len(self.undo_names())

        # Act
        envelope = self.run_script("doc.Box.Width = 99")

        # Assert
        self.assertEqual(stack_size, 20)
        self.assertEqual(self.structured(envelope)["undo_steps"], 1)

    def test_Should_count_one_added_step_When_the_script_undoes_one_and_records_one(self):
        # Arrange
        self.run_script("doc.Box.Length = 11")
        self.run_script("doc.Box.Height = 12")

        # Act
        envelope = self.run_script("doc.undo()")

        # Assert
        self.assertEqual(self.structured(envelope)["undo_steps"], 1)

    def test_Should_count_one_added_step_When_the_head_was_replaced_and_the_tail_is_kept(self):
        # Arrange
        before = ["C", "B", "A"]

        # Act
        added = script_exec_module._added_undo_steps(before, ["S", "B", "A"])

        # Assert
        self.assertEqual(added, 1)

    def test_Should_count_one_added_step_When_the_full_stack_dropped_its_oldest_entry(self):
        # Arrange
        before = [f"n{index}" for index in range(20)]
        after = ["S", *before[:19]]

        # Act
        added = script_exec_module._added_undo_steps(before, after)

        # Assert
        self.assertEqual(added, 1)

    def test_Should_report_zero_added_When_the_newest_entries_were_removed(self):
        # Arrange
        before = ["c", "b", "a"]

        # Act
        added = script_exec_module._added_undo_steps(before, ["b", "a"])

        # Assert
        self.assertEqual(added, 0)

    def test_Should_count_added_steps_by_aligning_names_When_entries_repeat_in_order(self):
        # Arrange
        before = ["b", "a"]

        # Act
        added = script_exec_module._added_undo_steps(before, ["c", "b", "a"])

        # Assert
        self.assertEqual(added, 1)


class TimeoutTest(_BracketFixture):
    def test_Should_commit_the_late_body_When_the_caller_already_timed_out(self):
        # Arrange
        bounded = Marshal(ThreadExecutor())
        code = "import time\ntime.sleep(1.5)\ndoc.Box.Length = 12"

        def call():
            return script_exec(self.registry, self.handle, code)

        # Act
        started = time.monotonic()
        with self.assertRaises(MarshalTimeout):
            bounded.call(call, 0.5)
        waited = time.monotonic() - started
        deadline = time.monotonic() + 10
        while time.monotonic() < deadline:
            if self.document.Box.Length == 12 and not self.document.HasPendingTransaction:
                break
            time.sleep(0.05)

        # Assert
        self.assertLess(waited, 1.2)
        self.assertFalse(self.document.HasPendingTransaction)
        self.assertEqual(self.document.Box.Length, 12)
        self.assertTrue(self.undo_names()[0].startswith("script_exec"))
        self.assertIsNone(App.getActiveTransaction())


class CostTest(unittest.TestCase):
    def setUp(self):
        self._posture = confirm.set_auto_approve(True)

    def tearDown(self):
        confirm.set_auto_approve(self._posture)
        for name in list(App.listDocuments().keys()):
            App.closeDocument(name)

    def test_Should_finish_within_the_budget_When_the_document_holds_30_heavy_objects(self):
        # Arrange
        registry = DocumentRegistry()
        handle = registry.document_create("heavy")["structured_content"]["doc"]
        document = registry.with_document(handle, lambda h, d: d)
        pitch = 10.0
        side = TIMING_HOLES_PER_SIDE * pitch
        plate = Part.makeBox(side, side, 5)
        holes = [
            Part.makeCylinder(2, 5, App.Vector(pitch / 2 + i * pitch, pitch / 2 + j * pitch, 0))
            for i in range(TIMING_HOLES_PER_SIDE)
            for j in range(TIMING_HOLES_PER_SIDE)
        ]
        shape = plate.cut(Part.makeCompound(holes))
        for index in range(TIMING_OBJECTS):
            feature = document.addObject("Part::Feature", f"Plate{index}")
            feature.Shape = shape
        document.recompute()
        face_count = len(shape.Faces)

        # Act
        started = time.monotonic()
        envelope = script_exec(registry, handle, "doc.Plate0.Placement.Base.x = 1")
        elapsed = time.monotonic() - started
        sys.stderr.write(
            f"script_exec on {TIMING_OBJECTS} objects x {face_count} faces took {elapsed:.2f} s\n"
        )

        # Assert
        self.assertEqual(face_count, TIMING_FACES)
        self.assertEqual(envelope["status"], "OK")
        self.assertLess(elapsed, TIMING_BUDGET_S)


class DispatchTest(_BracketFixture):
    def test_Should_serve_the_next_call_When_a_script_raises_system_exit_through_the_registry(self):
        # Arrange
        from freecad_buddy.adapters.rpc_dispatch import MethodRegistry, RpcMethod
        from freecad_buddy.hosts import tool_catalog

        methods = MethodRegistry()
        spec = tool_catalog.SCRIPT_EXEC_SPEC
        handler = spec.make_handler(self.registry, None, None, None, None)
        methods.register(
            RpcMethod(
                name=spec.name,
                handler=handler,
                input_schema=spec.input_schema,
                description=spec.description,
                timeout_s=spec.timeout_s,
                mutating=spec.mutating,
                audit_event=spec.audit_event,
            )
        )
        stderr = io.StringIO()

        # Act
        with redirect_stderr(stderr):
            first = methods.dispatch(
                "script_exec", {"doc": self.handle, "code": "raise SystemExit"}
            )
        second = methods.dispatch("script_exec", {"doc": self.handle, "code": "result = 2"})

        # Assert
        self.assertEqual(first["status"], "INVALID_INPUT")
        self.assertEqual(first["detail"]["code"], "exec.python_error")
        self.assertEqual(stderr.getvalue(), "")
        self.assertEqual(second["status"], "OK")
        self.assertEqual(second["structured_content"]["value_repr"], "2")

    def test_Should_pass_recompute_false_through_the_handler_When_the_caller_sets_it(self):
        # Arrange
        from freecad_buddy.hosts import tool_catalog

        spec = tool_catalog.SCRIPT_EXEC_SPEC
        handler = spec.make_handler(self.registry, None, None, None, None)

        # Act
        handler(doc=self.handle, code="doc.Box.Length = 12", recompute=False)

        # Assert
        self.assertIn("Touched", self.document.Box.State)
