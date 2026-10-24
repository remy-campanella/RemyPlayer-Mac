"""Keep platform-specific imports out of business logic."""
import sys


def set_dock_visible(visible):
    if sys.platform != "darwin":
        return True
    from AppKit import NSApplication, NSApplicationActivationPolicyAccessory, NSApplicationActivationPolicyRegular

    application = NSApplication.sharedApplication()
    policy = NSApplicationActivationPolicyRegular if visible else NSApplicationActivationPolicyAccessory
    if application.activationPolicy() == policy:
        return True
    return bool(application.setActivationPolicy_(policy))


def activate_application():
    if sys.platform == "darwin":
        from AppKit import NSApplication

        application = NSApplication.sharedApplication()
        application.unhide_(None)
        application.activateIgnoringOtherApps_(True)
