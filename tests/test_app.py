import os
from pathlib import Path
import sys
from tempfile import TemporaryDirectory
import time
import unittest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from PySide6.QtMultimedia import QMediaDevices, QMediaPlayer
from PySide6.QtCore import QEventLoop, QTimer
from PySide6.QtWidgets import QApplication

from remyplayer.app import AppController
from remyplayer.domain.queue import PlayMode
from test_library import make_wav


class AppTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.application = QApplication.instance() or QApplication([])
        cls.application.setApplicationName("RemyPlayerTest")

    def setUp(self):
        self.temp = TemporaryDirectory()
        self.base = Path(self.temp.name)
        self.root = self.base / "music"
        make_wav(self.root / "2.wav", 0.8)
        make_wav(self.root / "nested" / "10.wav", 0.8)
        self.controller = AppController(self.application, self.base / "data", desktop=False)
        self.controller.playback.output.setMuted(True)
        self.controller.window.show()

    def tearDown(self):
        self.controller.shutdown()
        self.controller.window.close()
        self.application.processEvents()
        self.controller.deleteLater()
        self.application.processEvents()
        self.temp.cleanup()

    def wait_until(self, predicate, timeout=8):
        deadline = time.monotonic() + timeout
        while not predicate() and time.monotonic() < deadline:
            # A real event loop releases the GIL; QTest.qWait can block Python
            # callbacks from multimedia renderer threads while waiting for them.
            loop = QEventLoop()
            QTimer.singleShot(20, loop.quit)
            loop.exec()
        self.assertTrue(predicate(), "Timed out waiting for Qt event")

    def scan(self):
        self.controller.scan(self.root)
        self.wait_until(lambda: self.controller.library.task is None)
        self.assertEqual(len(self.controller.window.tracks), 2)

    def test_scan_browse_search_and_hidden_window_preserve_queue(self):
        self.scan()
        window = self.controller.window
        window.play_visible()
        self.assertEqual(len(self.controller.playback.queue.tracks), 2)
        first = self.controller.playback.queue.current
        window.category.setCurrentIndex(1)
        window.search.setText("10.wav")
        self.assertEqual(window.model.rowCount(), 1)
        self.assertEqual(self.controller.playback.queue.current, first)
        window.allow_hide = True
        window.close()
        self.assertFalse(window.isVisible())
        self.assertEqual(self.controller.playback.queue.current, first)
        self.assertFalse(window.quitting)

    def test_real_audio_end_advances_and_stops_at_end(self):
        if not QMediaDevices.audioOutputs():
            self.skipTest("No audio output device; run desktop checks outside the sandbox")
        self.scan()
        playback = self.controller.playback
        seen, errors = [], []
        playback.trackChanged.connect(lambda track: seen.append(track.filename))
        playback.error.connect(errors.append)
        playback.start(self.controller.window.tracks, 0)
        self.wait_until(lambda: len(seen) == 2)
        self.wait_until(lambda: playback.player.playbackState() == QMediaPlayer.PlaybackState.StoppedState)
        self.assertEqual(seen, ["2.wav", "10.wav"])
        self.assertFalse(errors)

    def test_pause_seek_volume_and_once(self):
        if not QMediaDevices.audioOutputs():
            self.skipTest("No audio output device; run desktop checks outside the sandbox")
        self.scan()
        playback = self.controller.playback
        self.controller.set_mode(PlayMode.ONCE)
        playback.start(self.controller.window.tracks, 0)
        self.wait_until(lambda: playback.player.duration() > 0)
        playback.player.pause()
        self.assertEqual(playback.player.playbackState(), QMediaPlayer.PlaybackState.PausedState)
        playback.player.setPosition(200)
        self.assertEqual(playback.player.position(), 200)
        self.controller.window.volume.setValue(25)
        self.assertAlmostEqual(playback.output.volume(), 0.25)
        playback.toggle()
        self.wait_until(lambda: playback.player.playbackState() == QMediaPlayer.PlaybackState.StoppedState)
        self.assertEqual(playback.queue.index, 0)

    def test_repeat_one_then_loop_wraps(self):
        if not QMediaDevices.audioOutputs():
            self.skipTest("No audio output device; run desktop checks outside the sandbox")
        self.scan()
        playback = self.controller.playback
        seen = []
        playback.trackChanged.connect(lambda track: seen.append(track.filename))
        self.controller.set_mode(PlayMode.REPEAT_ONE)
        playback.start(self.controller.window.tracks, 0)
        self.wait_until(lambda: len(seen) >= 2)
        self.assertEqual(seen[:2], ["2.wav", "2.wav"])
        self.controller.set_mode(PlayMode.LOOP)
        playback.next()
        self.assertEqual(playback.queue.index, 1)
        self.wait_until(lambda: playback.queue.index == 0)
        playback.stop()


if __name__ == "__main__":
    unittest.main()
