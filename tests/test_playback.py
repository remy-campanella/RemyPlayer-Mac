"""Output routing regressions use fake devices and never open an audio stream."""
from pathlib import Path
import sys
import unittest
from unittest.mock import Mock, patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from PySide6.QtCore import QObject, Signal
from PySide6.QtMultimedia import QMediaPlayer

from remyplayer.services.playback import PlaybackService


class DeviceMonitor(QObject):
    audioOutputsChanged = Signal()


def device(identifier):
    result = Mock()
    result.id.return_value = identifier
    result.isNull.return_value = not identifier
    return result


class OutputRoutingTests(unittest.TestCase):
    def setUp(self):
        self.speaker = device(b"speaker")
        self.headphones = device(b"headphones")
        self.monitor = DeviceMonitor()
        self.player = Mock()
        self.player.playbackState.return_value = QMediaPlayer.PlaybackState.PausedState
        self.output = Mock()
        self.output.device.return_value = self.speaker
        for name, replacement in (
            ("QMediaPlayer", Mock(return_value=self.player, PlaybackState=QMediaPlayer.PlaybackState,
                                  MediaStatus=QMediaPlayer.MediaStatus)),
            ("QAudioOutput", Mock(return_value=self.output)),
            ("QMediaDevices", Mock(return_value=self.monitor)),
        ):
            patcher = patch(f"remyplayer.services.playback.{name}", replacement)
            patcher.start()
            self.addCleanup(patcher.stop)
        from remyplayer.services.playback import QMediaDevices
        self.devices = QMediaDevices
        self.devices.defaultAudioOutput.return_value = self.speaker
        self.service = PlaybackService()
        self.output.reset_mock()
        self.player.reset_mock()

    def test_default_change_routes_to_headphones_without_play_or_volume_change(self):
        self.devices.defaultAudioOutput.return_value = self.headphones
        self.monitor.audioOutputsChanged.emit()
        self.output.setDevice.assert_called_once_with(self.headphones)
        self.output.setVolume.assert_not_called()
        self.output.setMuted.assert_not_called()
        self.player.play.assert_not_called()
        self.player.pause.assert_called_once()
        self.player.setPosition.assert_not_called()

    def test_unrelated_device_notification_does_not_reopen_output(self):
        self.monitor.audioOutputsChanged.emit()
        self.output.setDevice.assert_not_called()

    def test_no_default_device_pauses_without_falling_back(self):
        self.devices.defaultAudioOutput.return_value = device(b"")
        self.monitor.audioOutputsChanged.emit()
        self.player.pause.assert_called_once()
        self.output.setDevice.assert_not_called()
        self.player.play.assert_not_called()

    def test_resume_refreshes_device_before_play(self):
        self.service.queue.start([Mock()], 0)
        self.devices.defaultAudioOutput.return_value = self.headphones
        calls = Mock()
        calls.attach_mock(self.output.setDevice, "route")
        calls.attach_mock(self.player.play, "play")
        self.service.toggle()
        self.assertEqual([call[0] for call in calls.mock_calls], ["route", "play"])

    def test_headphone_disconnect_pauses_before_routing_and_cancels_advance(self):
        self.devices.defaultAudioOutput.return_value = self.headphones
        self.service._sync_output_device()
        self.output.device.return_value = self.headphones
        self.player.reset_mock()
        self.player.playbackState.return_value = QMediaPlayer.PlaybackState.PlayingState
        self.devices.defaultAudioOutput.return_value = self.speaker
        generation = self.service._generation
        calls = Mock()
        calls.attach_mock(self.player.pause, "pause")
        calls.attach_mock(self.output.setDevice, "route")
        self.monitor.audioOutputsChanged.emit()
        self.assertEqual([call[0] for call in calls.mock_calls], ["pause", "route"])
        self.assertGreater(self.service._generation, generation)
        with patch.object(self.service, "next") as advance:
            self.service._advance_after_end(generation)
        advance.assert_not_called()
        self.player.play.assert_not_called()
        self.output.setVolume.assert_not_called()
        self.output.setMuted.assert_not_called()

    def test_seek_relative_clamps_and_does_not_start_playback(self):
        self.service.queue.start([Mock()], 0)
        self.player.isSeekable.return_value = True
        self.player.duration.return_value = 60000
        for position, offset, expected in ((25000, -10000, 15000), (25000, 10000, 35000),
                                           (5000, -10000, 0), (55000, 10000, 60000)):
            with self.subTest(position=position, offset=offset):
                self.player.position.return_value = position
                self.service.seek_relative(offset)
                self.player.setPosition.assert_called_with(expected)
        self.player.play.assert_not_called()
        self.player.pause.assert_not_called()

    def test_seek_without_track_or_seekable_media_is_ignored(self):
        self.service.seek_relative(10000)
        self.service.queue.start([Mock()], 0)
        self.player.isSeekable.return_value = False
        self.service.seek_relative(10000)
        self.player.setPosition.assert_not_called()

    def test_resume_without_output_does_not_play(self):
        self.service.queue.start([Mock()], 0)
        self.devices.defaultAudioOutput.return_value = device(b"")
        self.service.toggle()
        self.player.play.assert_not_called()


if __name__ == "__main__":
    unittest.main()
