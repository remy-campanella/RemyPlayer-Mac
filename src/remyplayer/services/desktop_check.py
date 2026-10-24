"""Exercise the actual native recovery action, including in the compiled app."""
import gc
import sys

from PySide6.QtCore import QTimer


def schedule_desktop_check(controller):
    result = {"completed": False, "error": ""}

    def checked(callback):
        try:
            callback()
        except Exception as error:
            result["error"] = str(error)
            print(f"Desktop check failed: {error}", file=sys.stderr, flush=True)
            controller.quit()

    def hide():
        assert controller.tray_accessible(), "菜单栏没有可点击的屏幕入口"
        controller.window.close()
        assert not controller.window.isVisible(), "窗口未隐藏"
        if sys.platform == "darwin":
            from AppKit import NSApplication, NSApplicationActivationPolicyAccessory
            assert NSApplication.sharedApplication().activationPolicy() == NSApplicationActivationPolicyAccessory, "Dock 未隐藏"
        QTimer.singleShot(350, lambda: checked(restore))

    def restore():
        gc.collect()
        assert controller.tray_accessible(), "窗口关闭后菜单栏按钮丢失或被刘海遮挡"
        if sys.platform == "darwin":
            from AppKit import NSApplication, NSApplicationActivationPolicyRegular
            action = controller.tray.menu.itemAtIndex_(0)
            assert NSApplication.sharedApplication().sendAction_to_from_(
                action.action(), action.target(), action,
            ), "菜单栏恢复操作没有目标"
            assert NSApplication.sharedApplication().activationPolicy() == NSApplicationActivationPolicyRegular, "Dock 未恢复"
        else:
            controller.show()
        assert controller.window.isVisible(), "原生菜单操作未恢复窗口"
        result["completed"] = True
        print("OK: onscreen status item, hidden window, Dock and native menu recovery", flush=True)
        QTimer.singleShot(200, controller.quit)

    def timeout():
        if not result["completed"]:
            result["error"] = "桌面验证超时"
            controller.quit()

    QTimer.singleShot(350, lambda: checked(hide))
    QTimer.singleShot(8000, timeout)
    return result
