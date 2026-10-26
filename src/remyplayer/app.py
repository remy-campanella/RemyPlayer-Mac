"""Application composition, settings and desktop lifecycle."""
import argparse
from pathlib import Path
import sys

from PySide6.QtCore import QObject, QSettings, QStandardPaths, QTimer
from PySide6.QtGui import QAction, QFont, QIcon, QKeySequence, QPainter, QPainterPath, QPixmap
from PySide6.QtCore import Qt
from PySide6.QtWidgets import QApplication, QFileDialog, QMenu, QMessageBox, QSystemTrayIcon

from remyplayer import __version__
from remyplayer.domain.queue import PlayMode
from remyplayer.infrastructure.library import TrackRepository
from remyplayer.platform_macos import activate_application, set_dock_visible
from remyplayer.services.library import LibraryService
from remyplayer.services.playback import PlaybackService
from remyplayer.ui.window import MainWindow


def tray_icon():
    pixmap = QPixmap(36, 36)
    pixmap.fill(Qt.GlobalColor.transparent)
    painter = QPainter(pixmap)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing)
    font = QFont("Times New Roman")
    font.setBold(True)
    font.setPixelSize(38)
    letter = QPainterPath()
    letter.addText(0, 0, font, "R")
    bounds = letter.boundingRect()
    letter.translate(18 - bounds.center().x(), 18 - bounds.center().y())
    painter.fillPath(letter, Qt.GlobalColor.black)
    painter.end()
    icon = QIcon(pixmap)
    icon.setIsMask(True)
    return icon


class AppController(QObject):
    def __init__(self, application, data_dir=None, desktop=True):
        super().__init__(application)
        self.application = application
        self.desktop = desktop
        self._shutting_down = False
        data_dir = Path(data_dir or QStandardPaths.writableLocation(QStandardPaths.StandardLocation.AppDataLocation))
        data_dir.mkdir(parents=True, exist_ok=True)
        self.settings = QSettings(str(data_dir / "settings.ini"), QSettings.Format.IniFormat)
        self.repository = TrackRepository(data_dir / "library.sqlite3")
        self.library = LibraryService(self.repository, self)
        self.playback = PlaybackService(self)
        self.window = MainWindow()
        self.root = str(self.settings.value("library/root", ""))
        self.errors = []
        self.scan_root = ""
        self.tray = None
        self.dock_icon = None
        self.reopen_handler = None
        self.dock_sync = QTimer(self)
        self.dock_sync.setSingleShot(True)
        self.dock_sync.timeout.connect(self.sync_dock)
        self.tray_watchdog = QTimer(self)
        self.tray_watchdog.setInterval(2000)
        self.tray_watchdog.timeout.connect(self.ensure_background_access)
        if sys.platform != "darwin":
            icon = QIcon(str(Path(__file__).parent / "resources" / "icon.svg"))
            self.window.setWindowIcon(icon)
            self.application.setWindowIcon(icon)
        elif desktop:
            from remyplayer.platform_macos.application_icon import ApplicationIcon
            self.dock_icon = ApplicationIcon(Path(__file__).parent / "resources" / "icon.icns")
        self._connect()
        self._restore()
        if desktop:
            self._desktop_menu()
            # Register after Cocoa/Qt have installed their launch-time handlers.
            QTimer.singleShot(0, self.install_reopen_handler)
        self.application.aboutToQuit.connect(self.shutdown)

    def _connect(self):
        window, player, library = self.window, self.playback, self.library
        window.chooseRequested.connect(self.choose_library)
        window.rescanRequested.connect(self.rescan)
        window.cancelRequested.connect(library.cancel)
        window.playRequested.connect(player.start)
        window.toggleRequested.connect(player.toggle)
        window.nextRequested.connect(player.next)
        window.previousRequested.connect(player.previous)
        window.seekRequested.connect(player.player.setPosition)
        window.seekRelativeRequested.connect(player.seek_relative)
        window.volumeRequested.connect(self.set_volume)
        window.modeRequested.connect(self.set_mode)
        window.dockRequested.connect(self.set_dock_preference)
        window.hidden.connect(self.hide_dock)
        window.errorsRequested.connect(self.show_errors)
        player.trackChanged.connect(window.set_track)
        player.stateChanged.connect(window.set_playing)
        player.positionChanged.connect(window.set_position)
        player.durationChanged.connect(window.set_duration)
        player.error.connect(self.playback_error)
        library.loaded.connect(self.scanned)
        library.failed.connect(self.scan_failed)
        library.busyChanged.connect(window.set_busy)
        library.progress.connect(lambda count, path: window.status.setText(f"已检查 {count} 个音频文件 · {path}"))

    def _restore(self):
        try:
            volume = max(0, min(100, int(self.settings.value("playback/volume", 70))))
        except (ValueError, TypeError):
            volume = 70
        self.window.volume.setValue(volume)
        self.playback.output.setVolume(volume / 100)
        mode = str(self.settings.value("playback/mode", PlayMode.ORDER.value))
        if mode not in [item.value for item in PlayMode]:
            mode = PlayMode.ORDER.value
        self.window.mode.setCurrentText(mode)
        self.playback.queue.set_mode(mode)
        self.window.keep_dock.setChecked(self.settings.value("desktop/keep_dock", False, type=bool))
        geometry = self.settings.value("window/geometry")
        if geometry:
            self.window.restoreGeometry(geometry)
        if self.root:
            self.window.set_library(self.root, self.repository.load(self.root))
            self.window.rescan.setEnabled(True)

    def _desktop_menu(self):
        menu = self.window.menuBar().addMenu("文件")
        for title, shortcut, callback in (
            ("选择音乐文件夹…", QKeySequence.StandardKey.Open, self.choose_library),
            ("退出 RemyPlayer", QKeySequence.StandardKey.Quit, self.quit),
        ):
            action = QAction(title, self)
            # Open's shortcut already belongs to the window action.
            if shortcut == QKeySequence.StandardKey.Quit:
                action.setShortcut(QKeySequence(shortcut))
            action.triggered.connect(callback)
            menu.addAction(action)
        if sys.platform == "darwin":
            try:
                from remyplayer.platform_macos.status_item import NativeStatusItem
                self.tray = NativeStatusItem(
                    self.request_show, self.window._play, self.playback.previous,
                    self.playback.next, self.quit,
                )
            except Exception as error:
                self.window.status.setText(f"菜单栏入口创建失败，将保留主窗口：{error}")
        elif QSystemTrayIcon.isSystemTrayAvailable():
            self._qt_tray()
        if self.tray is None:
            self.application.setQuitOnLastWindowClosed(True)
            self.window.status.setText(self.window.status.text() + "；关闭窗口将退出程序。")
            return
        self.application.setQuitOnLastWindowClosed(False)
        self.window.allow_hide = True
        self.playback.trackChanged.connect(lambda track: self.tray.setToolTip(f"RemyPlayer · {track.title}"))
        self.tray_watchdog.start()

    def _qt_tray(self):
        self.tray = QSystemTrayIcon(tray_icon(), self)
        self.tray.setToolTip(f"RemyPlayer {__version__}")
        self.tray_menu = QMenu()
        self.tray_menu.addAction("显示主窗口", self.request_show)
        self.tray_toggle = self.tray_menu.addAction("播放 / 暂停", self.window._play)
        self.tray_menu.addAction("上一首", self.playback.previous)
        self.tray_menu.addAction("下一首", self.playback.next)
        self.tray_menu.addSeparator()
        self.tray_menu.addAction("退出 RemyPlayer", self.quit)
        self.tray.setContextMenu(self.tray_menu)
        self.tray.show()

    def tray_accessible(self):
        if self.tray is None:
            return False
        try:
            check = getattr(self.tray, "is_accessible", self.tray.isVisible)
            return bool(check())
        except Exception:
            return False

    def ensure_background_access(self):
        self.sync_dock()
        if not self._shutting_down and not self.window.isVisible() and not self.tray_accessible():
            self.show()
            self.window.status.setText("菜单栏入口不可用，已恢复窗口和 Dock，防止无法找回播放器。")

    def install_reopen_handler(self):
        if self._shutting_down or sys.platform != "darwin" or self.reopen_handler:
            return
        from remyplayer.platform_macos.reopen import ReopenHandler
        self.reopen_handler = ReopenHandler(self.request_show)

    def request_show(self):
        # Finish the native status-menu / AppleEvent callback before changing
        # activation policy or activating Qt windows.
        QTimer.singleShot(0, self.show)

    def show(self):
        if self._shutting_down:
            return
        if self.desktop:
            self._dock(True)
        self.window.showNormal()
        if self.desktop:
            activate_application()
        self.window.raise_()
        self.window.activateWindow()
        self.sync_dock()
        if self.desktop and self.dock_icon:
            self.dock_icon.apply(force=True)
        self.dock_sync.start(200)

    def sync_dock(self):
        if self.desktop and not self._shutting_down:
            # A visible (including minimized) main window always owns a Dock
            # entry. The preference applies only while the window is closed.
            self._dock(self.window.isVisible() or self.window.keep_dock.isChecked())

    def hide_dock(self):
        if not self.desktop:
            return
        if self.window.isVisible():
            self.sync_dock()
            return
        if not self.tray_accessible():
            self.ensure_background_access()
        else:
            self.sync_dock()
            self.dock_sync.start(200)
            # Activation-policy changes can affect the native menu-bar layout.
            QTimer.singleShot(250, self.ensure_background_access)

    def _dock(self, visible):
        try:
            if not set_dock_visible(visible):
                self.window.status.setText("系统未接受 Dock 显示设置。")
            elif visible and self.dock_icon:
                self.dock_icon.apply()
        except Exception as error:
            self.window.status.setText(f"Dock 设置失败：{error}")

    def set_dock_preference(self, keep):
        self.settings.setValue("desktop/keep_dock", keep)
        if self.desktop:
            self.sync_dock()
            self.dock_sync.start(200)

    def set_volume(self, volume):
        self.playback.output.setVolume(volume / 100)
        self.settings.setValue("playback/volume", volume)

    def set_mode(self, mode):
        self.playback.queue.set_mode(mode)
        self.settings.setValue("playback/mode", mode)

    def choose_library(self):
        if self.library.task:
            return
        path = QFileDialog.getExistingDirectory(self.window, "选择音乐库文件夹", self.root or str(Path.home()))
        if path:
            self.scan(path)

    def rescan(self):
        if self.root and not self.library.task:
            self.scan(self.root)

    def scan(self, root):
        if self.library.task:
            return
        self.scan_root = str(Path(root).expanduser().resolve())
        self.window.error_button.hide()
        self.library.scan(self.scan_root)

    def scanned(self, result):
        if result.cancelled:
            self.window.status.setText("扫描已取消，保留原来的音乐库。")
            self.window.rescan.setEnabled(bool(self.root))
            return
        self.root = result.root
        self.settings.setValue("library/root", self.root)
        self.window.set_library(self.root, result.tracks)
        self.window.rescan.setEnabled(True)
        self.errors = result.errors
        self.window.error_button.setVisible(bool(self.errors))
        self.window.status.setText(
            f"扫描完成 · {len(result.tracks)} 首曲目 · {len(self.errors)} 个问题 · 音乐库只读"
        )

    def scan_failed(self, message):
        self.errors = [message]
        self.window.error_button.show()
        self.window.status.setText(f"扫描失败：{message}")
        self.window.rescan.setEnabled(bool(self.root))

    def playback_error(self, message):
        self.window.status.setText(f"播放失败：{message}。可尝试下一首。")

    def show_errors(self):
        dialog = QMessageBox(self.window)
        dialog.setWindowTitle("音乐库扫描问题")
        dialog.setIcon(QMessageBox.Icon.Warning)
        dialog.setText(f"{len(self.errors)} 个文件或目录未能正常读取。原文件未被修改。")
        dialog.setDetailedText("\n".join(self.errors))
        dialog.exec()

    def quit(self):
        self.window.quitting = True
        self.application.quit()

    def shutdown(self):
        if self._shutting_down:
            return
        self._shutting_down = True
        self.tray_watchdog.stop()
        self.dock_sync.stop()
        if self.reopen_handler:
            self.reopen_handler.close()
        self.window.quitting = True
        self.settings.setValue("window/geometry", self.window.saveGeometry())
        self.settings.sync()
        self.playback.stop()
        self.library.shutdown()
        if self.tray:
            self.tray.hide()


def main(argv=None):
    parser = argparse.ArgumentParser(description="RemyPlayer · 本地音乐播放器")
    parser.add_argument("--version", action="version", version=__version__)
    parser.add_argument("--data-dir", type=Path, help="独立的设置与索引目录")
    parser.add_argument("--library", type=Path, help="启动时扫描指定音乐库")
    parser.add_argument("--smoke-test", action="store_true", help="无桌面集成地初始化界面并退出")
    parser.add_argument("--screenshot", type=Path, help="保存界面截图（可与 --smoke-test 合用）")
    parser.add_argument("--check-desktop", action="store_true", help="验证真实菜单栏恢复入口后退出")
    args = parser.parse_args(argv)
    if args.check_desktop and (args.smoke_test or not args.data_dir):
        parser.error("--check-desktop 需要独立的 --data-dir，且不能与 --smoke-test 合用")
    application = QApplication([sys.argv[0]])
    application.setApplicationName("RemyPlayer")
    application.setOrganizationName("Remygrad")
    application.setApplicationVersion(__version__)
    controller = AppController(application, args.data_dir, desktop=not args.smoke_test)
    controller.show()
    desktop_result = None
    if args.check_desktop:
        from remyplayer.services.desktop_check import schedule_desktop_check
        desktop_result = schedule_desktop_check(controller)

    def capture_and_quit():
        if args.screenshot:
            args.screenshot.parent.mkdir(parents=True, exist_ok=True)
            if not controller.window.grab().save(str(args.screenshot)):
                print("无法保存截图", file=sys.stderr)
                controller.quit()
                return
        if args.smoke_test:
            controller.quit()

    if args.library:
        if args.smoke_test or args.screenshot:
            controller.library.loaded.connect(lambda result: QTimer.singleShot(200, capture_and_quit))
            controller.library.failed.connect(lambda error: QTimer.singleShot(200, capture_and_quit))
        QTimer.singleShot(0, lambda: controller.scan(args.library))
    elif args.smoke_test or args.screenshot:
        QTimer.singleShot(250, capture_and_quit)
    elif controller.root:
        QTimer.singleShot(0, controller.rescan)
    result = application.exec()
    if desktop_result is not None and not desktop_result["completed"]:
        return 1
    return result


if __name__ == "__main__":
    raise SystemExit(main())
