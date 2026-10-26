from pathlib import Path

from PySide6.QtCore import QObject, QTimer, QUrl, Signal
from PySide6.QtMultimedia import QAudioOutput, QMediaDevices, QMediaPlayer

from remyplayer.domain.queue import QueueController


class PlaybackService(QObject):
    trackChanged = Signal(object)
    stateChanged = Signal(bool)
    positionChanged = Signal("qlonglong")
    durationChanged = Signal("qlonglong")
    error = Signal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.queue = QueueController()
        self._generation = 0
        self._output_id = None
        self.player = QMediaPlayer(self)
        self.output = QAudioOutput(self)
        self.player.setAudioOutput(self.output)
        self.devices = QMediaDevices(self)
        self.devices.audioOutputsChanged.connect(self._sync_output_device)
        self._sync_output_device()
        self.player.positionChanged.connect(self.positionChanged)
        self.player.durationChanged.connect(self.durationChanged)
        self.player.playbackStateChanged.connect(
            lambda state: self.stateChanged.emit(state == QMediaPlayer.PlaybackState.PlayingState)
        )
        self.player.mediaStatusChanged.connect(self._status)
        self.player.errorOccurred.connect(lambda code, message: self.error.emit(message))
        self.output.setVolume(0.7)

    def _sync_output_device(self):
        # QAudioOutput retains a device snapshot; explicitly follow later system
        # default changes, including changes with the same device list.
        device = QMediaDevices.defaultAudioOutput()
        identifier = None if device.isNull() else bytes(device.id())
        changed = self._output_id is not None and identifier != self._output_id
        interrupted = changed and self.player.playbackState() == QMediaPlayer.PlaybackState.PlayingState
        if changed:
            # Pause before routing to a replacement (possibly loudspeakers).
            # Invalidate a queued end-of-media advance as well.
            self._generation += 1
            self.player.pause()
        self._output_id = identifier
        if device.isNull():
            if not changed:
                self.player.pause()
            return False
        if self.output.device().id() != device.id():
            self.output.setDevice(device)
        return not interrupted

    def seek_relative(self, milliseconds):
        if not self.queue.current or not self.player.isSeekable():
            return
        duration = self.player.duration()
        if duration > 0:
            position = max(0, min(duration, self.player.position() + milliseconds))
            self.player.setPosition(position)

    def start(self, tracks, index):
        track = self.queue.start(tracks, index)
        if track:
            self._load(track)

    def _load(self, track):
        self._generation += 1
        self.player.stop()
        self.trackChanged.emit(track)
        if not Path(track.path).is_file():
            self.player.setSource(QUrl())
            self.error.emit(f"文件不可用：{track.path}")
            return
        self.player.setSource(QUrl.fromLocalFile(track.path))
        self.player.setPosition(0)
        if self._sync_output_device():
            self.player.play()

    def toggle(self):
        if self.player.playbackState() == QMediaPlayer.PlaybackState.PlayingState:
            self.player.pause()
        elif self.queue.current:
            if self.player.mediaStatus() == QMediaPlayer.MediaStatus.EndOfMedia:
                self.player.setPosition(0)
            if self._sync_output_device():
                self.player.play()

    def next(self, automatic=False):
        track = self.queue.next(automatic)
        if track:
            self._load(track)

    def previous(self):
        if self.player.position() > 3000:
            self.player.setPosition(0)
        elif track := self.queue.previous():
            self._load(track)

    def _status(self, status):
        if status == QMediaPlayer.MediaStatus.EndOfMedia:
            generation = self._generation
            # Never replace/stop media reentrantly from the backend's end callback.
            QTimer.singleShot(0, lambda: self._advance_after_end(generation))

    def _advance_after_end(self, generation):
        if generation == self._generation and self.player.mediaStatus() == QMediaPlayer.MediaStatus.EndOfMedia:
            self.next(automatic=True)

    def stop(self):
        self._generation += 1
        self.player.stop()
