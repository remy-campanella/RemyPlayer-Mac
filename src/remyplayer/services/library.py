from threading import Event

from PySide6.QtCore import QObject, QRunnable, QThreadPool, Signal

from remyplayer.infrastructure.library import LibraryScanner


class ScanSignals(QObject):
    done = Signal(object)
    failed = Signal(str)
    progress = Signal(int, str)


class ScanTask(QRunnable):
    def __init__(self, repository, root):
        super().__init__()
        self.signals = ScanSignals()
        self.cancelled = Event()
        self.repository = repository
        self.root = root

    def run(self):
        try:
            result = LibraryScanner(self.repository).scan(
                self.root, self.cancelled.is_set, self.signals.progress.emit,
            )
            self.signals.done.emit(result)
        except Exception as error:
            self.signals.failed.emit(str(error))


class LibraryService(QObject):
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
        if self.task is not None:
            return
        self.task = ScanTask(self.repository, root)
        self.task.signals.done.connect(self._done)
        self.task.signals.failed.connect(self._failed)
        self.task.signals.progress.connect(self.progress)
        self.busyChanged.emit(True)
        self.pool.start(self.task)

    def cancel(self):
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
        self.cancel()
        self.pool.waitForDone()
