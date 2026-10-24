"""Exercise Dock reopen AppleEvents and delayed native menu recovery."""
import gc
import os
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

    def policy(visible):
        if sys.platform == "darwin":
            from AppKit import NSApplication, NSApplicationActivationPolicyAccessory, NSApplicationActivationPolicyRegular
            expected = NSApplicationActivationPolicyRegular if visible else NSApplicationActivationPolicyAccessory
            assert NSApplication.sharedApplication().activationPolicy() == expected, f"Dock visibility should be {visible}"

    def dock_reopen():
        assert controller.tray_accessible(), "菜单栏没有可点击的屏幕入口"
        controller.window.keep_dock.setChecked(True)
        controller.window.close()
        assert not controller.window.isVisible(), "窗口未隐藏"
        policy(True)
        if sys.platform == "darwin":
            from Foundation import NSAppleEventDescriptor
            from remyplayer.platform_macos.reopen import CORE_EVENT_CLASS, REOPEN_APPLICATION
            assert controller.reopen_handler is not None, "未注册 Dock reopen 事件"
            target = NSAppleEventDescriptor.descriptorWithProcessIdentifier_(os.getpid())
            event = NSAppleEventDescriptor.appleEventWithEventClass_eventID_targetDescriptor_returnID_transactionID_(
                CORE_EVENT_CLASS, REOPEN_APPLICATION, target, -1, 0,
            )
            # kAENoReply: deliver the real event asynchronously to this process.
            _, error = event.sendEventWithOptions_timeout_error_(1, 1.0, None)
            assert error is None, f"Dock reopen AppleEvent failed: {error}"
        else:
            controller.request_show()
        QTimer.singleShot(450, lambda: checked(after_dock_reopen))

    def after_dock_reopen():
        assert controller.window.isVisible(), "Dock reopen 事件未恢复窗口"
        policy(True)
        controller.window.keep_dock.setChecked(False)
        policy(True)
        controller.window.close()
        assert not controller.window.isVisible(), "窗口未隐藏"
        policy(False)
        QTimer.singleShot(350, lambda: checked(menu_reopen))

    def menu_reopen():
        gc.collect()
        assert controller.tray_accessible(), "关闭窗口后菜单栏按钮丢失或被遮挡"
        if sys.platform == "darwin":
            from AppKit import NSApplication
            action = controller.tray.menu.itemAtIndex_(0)
            assert NSApplication.sharedApplication().sendAction_to_from_(
                action.action(), action.target(), action,
            ), "菜单栏恢复操作没有目标"
        else:
            controller.request_show()
        # Check after deferred activation and the background watchdog have run.
        QTimer.singleShot(2300, lambda: checked(finish))

    def finish():
        assert controller.window.isVisible(), "菜单栏未恢复窗口"
        policy(True)
        assert controller.tray_accessible(), "恢复窗口后菜单栏入口丢失"
        result["completed"] = True
        print("OK: actual Dock reopen event, retained Dock, menu restore and persistent foreground Dock", flush=True)
        QTimer.singleShot(100, controller.quit)

    def timeout():
        if not result["completed"]:
            result["error"] = "桌面验证超时"
            controller.quit()

    QTimer.singleShot(350, lambda: checked(dock_reopen))
    QTimer.singleShot(8000, timeout)
    return result
