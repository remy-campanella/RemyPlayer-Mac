"""播放服务：连接纯业务队列、Qt 媒体后端和系统输出设备。"""
from pathlib import Path

from PySide6.QtCore import QObject, QTimer, QUrl, Signal
from PySide6.QtMultimedia import QAudioOutput, QMediaDevices, QMediaPlayer

from remyplayer.domain.queue import QueueController


class PlaybackService(QObject):
    """在 Qt 主线程协调播放队列、媒体后端和系统输出设备。

    positionChanged、durationChanged 及跳转参数均以毫秒计；曲目元数据时长以秒计。
    界面通过信号获知状态，服务本身不修改控件。
    """
    trackChanged = Signal(object)
    stateChanged = Signal(bool)
    positionChanged = Signal("qlonglong")
    durationChanged = Signal("qlonglong")
    error = Signal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.queue = QueueController()
        self._generation = 0
        # 保存上次明确选择的设备 ID；后端自身的 device 快照可能已在设备变更时更新。
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
        """同步系统默认输出；返回当前调用是否可以继续启动播放。

        已有输出改变时先暂停并使待执行的自动切歌失效，再设置替代设备。
        无设备，或本次切换打断正在播放的音频时返回 False；不主动恢复播放，
        也不改动音量和静音状态。首次绑定设备不视为断开。
        """
        # 默认设备变化也会发出通知，即使可用设备列表没有增减，也需要重新核对。
        device = QMediaDevices.defaultAudioOutput()
        identifier = None if device.isNull() else bytes(device.id())
        changed = self._output_id is not None and identifier != self._output_id
        interrupted = changed and self.player.playbackState() == QMediaPlayer.PlaybackState.PlayingState
        if changed:
            # 顺序不能颠倒：替代设备可能是扬声器，必须先暂停再更换输出。
            # 同时使已排队的播完回调失效，避免保护性暂停被自动切歌绕过。
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
        """按有符号毫秒偏移跳转，并限制在当前曲目范围内。

        无曲目、不可定位或时长未知时忽略；不主动改变播放／暂停状态。
        """
        if not self.queue.current or not self.player.isSeekable():
            return
        duration = self.player.duration()
        if duration > 0:
            position = max(0, min(duration, self.player.position() + milliseconds))
            self.player.setPosition(position)

    def start(self, tracks, index):
        """建立曲目快照并播放指定索引；无效索引不会替换正在使用的队列。"""
        track = self.queue.start(tracks, index)
        if track:
            self._load(track)

    def _load(self, track):
        """替换媒体源并尝试播放；文件缺失时清空源并发出 error 信号。"""
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
        """切换播放／暂停；播完的曲目从头开始，无当前曲目时不操作。"""
        if self.player.playbackState() == QMediaPlayer.PlaybackState.PlayingState:
            self.player.pause()
        elif self.queue.current:
            if self.player.mediaStatus() == QMediaPlayer.MediaStatus.EndOfMedia:
                self.player.setPosition(0)
            if self._sync_output_device():
                self.player.play()

    def next(self, automatic=False):
        """依据队列模式切歌；automatic 用于自然播完，无后续曲目时不加载。"""
        track = self.queue.next(automatic)
        if track:
            self._load(track)

    def previous(self):
        """已播超过三秒则回到开头，否则请求队列中的上一首。"""
        if self.player.position() > 3000:
            self.player.setPosition(0)
        elif track := self.queue.previous():
            self._load(track)

    def _status(self, status):
        """将自然播完后的切歌延迟到下一轮事件循环，避免重入媒体后端。"""
        if status == QMediaPlayer.MediaStatus.EndOfMedia:
            generation = self._generation
            # 不在媒体后端的结束回调栈内 stop/setSource，防止后端重入或锁等待。
            QTimer.singleShot(0, lambda: self._advance_after_end(generation))

    def _advance_after_end(self, generation):
        """仅处理仍属于当前媒体代次的结束事件，忽略已停止或切歌后的回调。"""
        if generation == self._generation and self.player.mediaStatus() == QMediaPlayer.MediaStatus.EndOfMedia:
            self.next(automatic=True)

    def stop(self):
        """停止播放并使排队中的自动切歌回调失效，保留队列快照。"""
        self._generation += 1
        self.player.stop()
