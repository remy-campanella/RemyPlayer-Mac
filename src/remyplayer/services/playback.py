from pathlib import Path

from PySide6.QtCore import QObject, QTimer, QUrl, Signal
from PySide6.QtMultimedia import QAudioOutput, QMediaPlayer

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
        self.player = QMediaPlayer(self)
        self.output = QAudioOutput(self)
        self.player.setAudioOutput(self.output)
        self.player.positionChanged.connect(self.positionChanged)
        self.player.durationChanged.connect(self.durationChanged)
        self.player.playbackStateChanged.connect(
            lambda state: self.stateChanged.emit(state == QMediaPlayer.PlaybackState.PlayingState)
        )
        self.player.mediaStatusChanged.connect(self._status)
        self.player.errorOccurred.connect(lambda code, message: self.error.emit(message))
        self.output.setVolume(0.7)

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
        self.player.play()

    def toggle(self):
        if self.player.playbackState() == QMediaPlayer.PlaybackState.PlayingState:
            self.player.pause()
        elif self.queue.current:
            if self.player.mediaStatus() == QMediaPlayer.MediaStatus.EndOfMedia:
                self.player.setPosition(0)
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
