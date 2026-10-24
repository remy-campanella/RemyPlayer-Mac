"""Briefly show, hide and restore the app using native macOS desktop APIs."""
from pathlib import Path
import sys
from tempfile import TemporaryDirectory

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from PySide6.QtCore import QTimer
from PySide6.QtWidgets import QApplication
from remyplayer.app import AppController


def main():
    application = QApplication([])
    application.setApplicationName("RemyPlayer")
    application.setOrganizationName("Remygrad")
    failures = []
    completed = []
    with TemporaryDirectory(prefix="remyplayer-desktop-") as temporary:
        controller = AppController(application, temporary)

        def check(callback):
            try:
                callback()
            except Exception as error:
                failures.append(str(error))
                controller.quit()

        def hide():
            assert controller.tray and controller.tray.isVisible(), "菜单栏图标不可用"
            controller.window.close()
            assert not controller.window.isVisible(), "窗口未隐藏"
            if sys.platform == "darwin":
                from AppKit import NSApplication, NSApplicationActivationPolicyAccessory
                assert NSApplication.sharedApplication().activationPolicy() == NSApplicationActivationPolicyAccessory, "Dock 未隐藏"
            QTimer.singleShot(250, lambda: check(restore))

        def restore():
            controller.show()
            assert controller.window.isVisible(), "主窗口未恢复"
            if sys.platform == "darwin":
                from AppKit import NSApplication, NSApplicationActivationPolicyRegular
                assert NSApplication.sharedApplication().activationPolicy() == NSApplicationActivationPolicyRegular, "Dock 未恢复"
            print("OK: native menu bar, close-to-hide, Dock hide/restore and explicit quit")
            completed.append(True)
            QTimer.singleShot(250, controller.quit)

        controller.show()
        QTimer.singleShot(250, lambda: check(hide))
        QTimer.singleShot(8000, controller.quit)
        application.exec()
        controller.shutdown()
    if failures:
        print("\n".join(failures), file=sys.stderr)
        return 1
    if not completed:
        print("Desktop check did not complete before its deadline", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
