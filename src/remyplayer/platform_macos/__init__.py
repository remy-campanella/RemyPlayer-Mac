"""Keep platform-specific imports out of business logic."""
import sys


def set_dock_visible(visible):
    """在主线程切换 macOS Regular／Accessory 策略，返回系统是否接受；其他平台返回 True。"""
    if sys.platform != "darwin":
        return True
    from AppKit import NSApplication, NSApplicationActivationPolicyAccessory, NSApplicationActivationPolicyRegular

    application = NSApplication.sharedApplication()
    policy = NSApplicationActivationPolicyRegular if visible else NSApplicationActivationPolicyAccessory
    if application.activationPolicy() == policy:
        return True
    return bool(application.setActivationPolicy_(policy))


def activate_application():
    """在 macOS 主线程取消隐藏并激活应用；其他平台不操作。"""
    if sys.platform == "darwin":
        from AppKit import NSApplication

        application = NSApplication.sharedApplication()
        application.unhide_(None)
        application.activateIgnoringOtherApps_(True)
