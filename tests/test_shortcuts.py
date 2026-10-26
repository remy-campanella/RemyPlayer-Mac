"""Keyboard tests create only widgets, with no multimedia player or audio."""
import os
from pathlib import Path
import sys
import unittest
from unittest.mock import Mock

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from PySide6.QtCore import QEvent, Qt
from PySide6.QtGui import QKeyEvent
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication

from remyplayer.ui.window import MainWindow
from remyplayer.services.playback import PlaybackService


class ShortcutTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.application = QApplication.instance() or QApplication([])

    def setUp(self):
        self.window = MainWindow()
        self.window.model.current_path = "/virtual/music.wav"
        self.toggle = Mock()
        self.seek = Mock()
        self.window.toggleRequested.connect(self.toggle)
        self.window.seekRelativeRequested.connect(self.seek)
        self.window.show()
        self.window.activateWindow()
        self.application.processEvents()

    def test_clicking_background_releases_search_and_restores_all_keys(self):
        for target in (self.window.heading, self.window.centralWidget(), self.window.now_title):
            with self.subTest(target=target.objectName()):
                self.window.search.setFocus()
                self.application.processEvents()
                self.assertTrue(self.window.search.hasFocus())
                QTest.mouseClick(target, Qt.MouseButton.LeftButton)
                self.assertFalse(self.window.search.hasFocus())
                self.toggle.reset_mock()
                self.seek.reset_mock()
                focused = self.application.focusWidget()
                self.assertIsNotNone(focused)
                QTest.keyClick(focused, Qt.Key.Key_Space)
                QTest.keyClick(focused, Qt.Key.Key_Left)
                QTest.keyClick(focused, Qt.Key.Key_Right)
                self.toggle.assert_called_once_with()
                self.assertEqual([call.args for call in self.seek.call_args_list], [(-10000,), (10000,)])

    def tearDown(self):
        self.application.removeEventFilter(self.window)
        self.window.quitting = True
        self.window.close()
        self.window.theme.assets.cleanup()
        self.window.deleteLater()
        self.application.sendPostedEvents(None, QEvent.Type.DeferredDelete)

    def test_playback_keys_work_in_child_controls(self):
        for widget in (self.window.table, self.window.group_list,
                       self.window.play_button, self.window.seek, self.window.keep_dock):
            with self.subTest(widget=type(widget).__name__):
                self.toggle.reset_mock()
                self.seek.reset_mock()
                QTest.keyClick(widget, Qt.Key.Key_Space)
                self.toggle.assert_called_once_with()
                QTest.keyClick(widget, Qt.Key.Key_Left)
                QTest.keyClick(widget, Qt.Key.Key_Right)
                self.assertEqual([call.args for call in self.seek.call_args_list], [(-10000,), (10000,)])

    def test_search_keys_edit_text_without_controlling_playback(self):
        self.window.search.setText("ab")
        self.window.search.setCursorPosition(1)
        QTest.keyClick(self.window.search, Qt.Key.Key_Space)
        self.assertEqual(self.window.search.text(), "a b")
        QTest.keyClick(self.window.search, Qt.Key.Key_Left)
        self.assertEqual(self.window.search.cursorPosition(), 1)
        self.toggle.assert_not_called()
        self.seek.assert_not_called()

    def test_held_space_does_not_toggle_repeatedly(self):
        event = QKeyEvent(QEvent.Type.KeyPress, Qt.Key.Key_Space,
                          Qt.KeyboardModifier.NoModifier, " ", True)
        self.application.sendEvent(self.window.table, event)
        self.toggle.assert_not_called()

    def test_arrows_seek_ten_seconds_after_leaving_search(self):
        # Exercise the real seek calculation against a simulated media backend.
        backend = Mock()
        backend.player.isSeekable.return_value = True
        backend.player.duration.return_value = 60000
        backend.player.position.return_value = 30000
        backend.player.setPosition.side_effect = lambda value: setattr(
            backend.player.position, "return_value", value
        )
        self.window.seekRelativeRequested.connect(lambda offset: PlaybackService.seek_relative(backend, offset))
        self.window.search.setFocus()
        QTest.mouseClick(self.window.heading, Qt.MouseButton.LeftButton)
        focused = self.application.focusWidget()
        QTest.keyClick(focused, Qt.Key.Key_Left)
        self.assertEqual(backend.player.position(), 20000)
        QTest.keyClick(focused, Qt.Key.Key_Right)
        self.assertEqual(backend.player.position(), 30000)
        backend.player.play.assert_not_called()
        backend.player.pause.assert_not_called()

    def test_modified_arrow_is_not_a_playback_command(self):
        QTest.keyClick(self.window.table, Qt.Key.Key_Left, Qt.KeyboardModifier.ControlModifier)
        self.seek.assert_not_called()

    def test_macos_arrow_keypad_flag_is_not_a_shortcut_modifier(self):
        for key, offset in ((Qt.Key.Key_Left, -10000), (Qt.Key.Key_Right, 10000)):
            with self.subTest(key=key):
                self.seek.reset_mock()
                QTest.keyClick(self.window.table, key, Qt.KeyboardModifier.KeypadModifier)
                self.seek.assert_called_once_with(offset)

    def test_modified_macos_arrow_still_preserves_combination(self):
        modifiers = Qt.KeyboardModifier.KeypadModifier | Qt.KeyboardModifier.ControlModifier
        QTest.keyClick(self.window.table, Qt.Key.Key_Left, modifiers)
        self.seek.assert_not_called()


if __name__ == "__main__":
    unittest.main()
