"""In-FreeCAD tests for the scratch documents the capability probes open (stdlib unittest).

Run via ``FreeCADCmd tests/run_tests.py``.
"""

import unittest

import FreeCAD as App

from freecad_buddy.usecases import shim
from infc.notification_console import NotificationAreaConsole


class ScratchDocumentNotificationTest(unittest.TestCase):
    """A probe's deliberate failures never reach the human's notification area."""

    def setUp(self):
        self.mock_console = NotificationAreaConsole()
        real_console = App.Console
        App.Console = self.mock_console
        self.addCleanup(setattr, App, "Console", real_console)

    def test_should_mute_the_notification_area_when_a_scratch_probe_runs(self):
        # Arrange
        read = lambda obj: dict(self.mock_console.levels)  # noqa: E731, ARG005

        # Act
        seen = shim.probe_object("Part::Box", read)

        # Assert
        self.assertEqual(seen, dict.fromkeys(shim._NOTIFICATION_LEVELS, False))

    def test_should_restore_the_notification_area_when_the_scratch_probe_returns(self):
        # Arrange
        original = dict(self.mock_console.levels)
        read = lambda obj: obj.Name  # noqa: E731

        # Act
        shim.probe_object("Part::Box", read)

        # Assert
        self.assertEqual(self.mock_console.levels, original)

    def test_should_restore_the_notification_area_when_the_scratch_probe_raises(self):
        # Arrange
        original = dict(self.mock_console.levels)

        def exploding_read(obj):  # noqa: ARG001
            raise RuntimeError("probe blew up")

        # Act
        act = lambda: shim.probe_object("Part::Box", exploding_read)  # noqa: E731

        # Assert
        with self.assertRaises(RuntimeError):
            act()
        self.assertEqual(self.mock_console.levels, original)

    def test_should_keep_every_level_muted_until_the_outer_mute_exits_when_a_probe_nests(self):
        # Arrange
        original = dict(self.mock_console.levels)
        read = lambda obj: dict(self.mock_console.levels)  # noqa: E731, ARG005

        # Act
        with shim.notifications_muted():
            during_probe = shim.probe_object("Part::Box", read)
            after_probe = dict(self.mock_console.levels)
        after_both = dict(self.mock_console.levels)

        # Assert
        muted = dict.fromkeys(shim._NOTIFICATION_LEVELS, False)
        self.assertEqual(during_probe, muted)
        self.assertEqual(after_probe, muted)
        self.assertEqual(after_both, original)


if __name__ == "__main__":
    unittest.main()
