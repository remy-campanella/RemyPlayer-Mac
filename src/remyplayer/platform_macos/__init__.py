"""Keep platform-specific imports out of business logic."""
import sys


def set_dock_visible(visible):
    if sys.platform != "darwin":
        return True
    from AppKit import NSApplication, NSApplicationActivationPolicyAccessory, NSApplicationActivationPolicyRegular

    application = NSApplication.sharedApplication()
    policy = NSApplicationActivationPolicyRegular if visible else NSApplicationActivationPolicyAccessory
    return bool(application.setActivationPolicy_(policy))
