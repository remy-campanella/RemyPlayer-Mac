"""扫描任务的线程边界；后台只访问文件／索引，通过信号通知界面。"""
from threading import Event

from PySide6.QtCore import QObject, QRunnable, QThreadPool, Signal

from remyplayer.infrastructure.library import LibraryScanner


class ScanSignals(QObject):
    done = Signal(object)
    failed = Signal(str)
    progress = Signal(int, str)


class ScanTask(QRunnable):
    """在线程池中执行扫描；通过独立 QObject 的信号将结果交给界面线程。"""
    def __init__(self, repository, root):
        super().__init__()
        self.signals = ScanSignals()
        self.cancelled = Event()
        self.repository = repository
        self.root = root

    def run(self):
        """执行一次扫描并转发进度；异常转为 failed 信号，不直接操作控件。"""
        try:
            result = LibraryScanner(self.repository).scan(
                self.root, self.cancelled.is_set, self.signals.progress.emit,
            )
            self.signals.done.emit(result)
        except Exception as error:
            self.signals.failed.emit(str(error))


class LibraryService(QObject):
    """串行调度音乐库扫描，将后台结果通过 Qt 信号转发给主线程。"""
    loaded = Signal(object)
    failed = Signal(str)
    progress = Signal(int, str)
    busyChanged = Signal(bool)

    def __init__(self, repository, parent=None):
        super().__init__(parent)
        self.repository = repository
        self.pool = QThreadPool(self)
        self.pool.setMaxThreadCount(1)
        self.task = None

    def scan(self, root):
        """没有活动任务时启动扫描；忙碌时忽略请求，不并发替换索引。"""
        if self.task is not None:
            return
        self.task = ScanTask(self.repository, root)
        self.task.signals.done.connect(self._done)
        self.task.signals.failed.connect(self._failed)
        self.task.signals.progress.connect(self.progress)
        self.busyChanged.emit(True)
        self.pool.start(self.task)

    def cancel(self):
        """设置线程安全取消标记，由扫描循环在检查点协作退出。"""
        if self.task:
            self.task.cancelled.set()

    def _done(self, result):
        self.task = None
        self.busyChanged.emit(False)
        self.loaded.emit(result)

    def _failed(self, message):
        self.task = None
        self.busyChanged.emit(False)
        self.failed.emit(message)

    def shutdown(self):
        """请求取消并等待工作线程结束，避免退出时销毁仍在运行的任务。"""
        self.cancel()
        self.pool.waitForDone()
