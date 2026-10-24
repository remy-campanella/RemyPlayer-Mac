"""A retained, native macOS menu-bar item, independent of Qt window policy."""
from AppKit import (
    NSImage, NSMenu, NSMenuItem, NSObject, NSScreen,
    NSSquareStatusItemLength, NSStatusBar,
)
from Foundation import NSUserDefaults


class RemyStatusMenuTarget(NSObject):
    def invoke_(self, sender):
        callback = self.callbacks.get(sender.tag())
        if callback:
            callback()


def rect_contains(outer, inner):
    """Compare NSRects without depending on screen-coordinate conversions."""
    return (
        inner.size.width > 0 and inner.size.height > 0
        and outer.origin.x <= inner.origin.x
        and outer.origin.y <= inner.origin.y
        and inner.origin.x + inner.size.width <= outer.origin.x + outer.size.width
        and inner.origin.y + inner.size.height <= outer.origin.y + outer.size.height
    )


class NativeStatusItem:
    def __init__(self, show, toggle, previous, next_track, quit_app):
        self.bar = NSStatusBar.systemStatusBar()
        autosave_name = "RemyPlayer.MenuBar"
        defaults = NSUserDefaults.standardUserDefaults()
        position_key = f"NSStatusItem Preferred Position {autosave_name}"
        # Best-effort AppKit autosave hint for first launch. It affects only our
        # own item, leaves later user positioning intact, and is not relied on
        # for safety: is_accessible() still checks the actual screen geometry.
        if defaults.objectForKey_(position_key) is None:
            defaults.setFloat_forKey_(0.0, position_key)
        self.item = self.bar.statusItemWithLength_(NSSquareStatusItemLength)
        if self.item is None or self.item.button() is None:
            raise RuntimeError("系统没有创建菜单栏按钮")
        self.item.setAutosaveName_(autosave_name)
        self.target = RemyStatusMenuTarget.alloc().init()
        self.target.callbacks = {}
        self.menu = NSMenu.alloc().initWithTitle_("RemyPlayer")
        self.menu.setAutoenablesItems_(False)
        for tag, (title, callback) in enumerate((
            ("显示主窗口", show), ("播放 / 暂停", toggle),
            ("上一首", previous), ("下一首", next_track), ("退出 RemyPlayer", quit_app),
        )):
            if tag == 4:
                self.menu.addItem_(NSMenuItem.separatorItem())
            action = NSMenuItem.alloc().initWithTitle_action_keyEquivalent_(title, "invoke:", "")
            action.setTag_(tag)
            action.setTarget_(self.target)
            self.target.callbacks[tag] = callback
            self.menu.addItem_(action)
        self.item.setMenu_(self.menu)
        image = NSImage.imageWithSystemSymbolName_accessibilityDescription_("music.note", "RemyPlayer")
        button = self.item.button()
        if image:
            image.setSize_((18, 18))
            image.setTemplate_(True)
            button.setImage_(image)
        else:
            button.setTitle_("♫")
        button.setToolTip_("RemyPlayer · 点击显示播放菜单")
        button.setAccessibilityLabel_("RemyPlayer")
        self.item.setVisible_(True)

    def isVisible(self):
        return bool(self.item and self.item.isVisible())

    def is_accessible(self):
        """Require a real onscreen button, not just a requested visibility flag.

        In particular, an item behind a screen notch is not a recovery path.
        macOS can also suppress status items through system menu-bar settings.
        """
        if not self.isVisible():
            return False
        button = self.item.button()
        window = button.window() if button else None
        if window is None or button.isHidden():
            return False
        frame = window.convertRectToScreen_(button.convertRect_toView_(button.bounds(), None))
        for screen in NSScreen.screens():
            if not rect_contains(screen.frame(), frame):
                continue
            if screen.safeAreaInsets().top > 0:
                return any(rect_contains(area, frame) for area in (
                    screen.auxiliaryTopLeftArea(), screen.auxiliaryTopRightArea(),
                ))
            return True
        return False

    def setToolTip(self, text):
        if self.item and self.item.button():
            self.item.button().setToolTip_(text)

    def hide(self):
        if self.item:
            self.bar.removeStatusItem_(self.item)
            self.item = None
        self.target.callbacks.clear()
