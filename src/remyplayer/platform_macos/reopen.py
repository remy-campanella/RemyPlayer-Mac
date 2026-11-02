"""Handle the same reopen AppleEvent sent by a Dock click or Finder launch.

Only the reopen event is handled here. Qt keeps its application delegate and
continues handling termination, file-open events and all other Cocoa callbacks.
"""
import objc
from Foundation import NSAppleEventManager, NSObject

CORE_EVENT_CLASS = int.from_bytes(b"aevt", "big")
REOPEN_APPLICATION = int.from_bytes(b"rapp", "big")


class RemyReopenTarget(NSObject):
    @objc.typedSelector(b"v@:@@")
    def reopen_withReply_(self, event, reply):
        if self.callback:
            self.callback()


class ReopenHandler:
    """持有原生 reopen 事件目标，不替换 Qt 的应用代理；退出时需调用 close。"""
    def __init__(self, callback):
        self.target = RemyReopenTarget.alloc().init()
        self.target.callback = callback
        self.manager = NSAppleEventManager.sharedAppleEventManager()
        self.manager.setEventHandler_andSelector_forEventClass_andEventID_(
            self.target, "reopen:withReply:", CORE_EVENT_CLASS, REOPEN_APPLICATION,
        )

    def close(self):
        """注销 reopen 事件并清除 Python 回调，防止退出期间再次请求恢复窗口。"""
        self.manager.removeEventHandlerForEventClass_andEventID_(CORE_EVENT_CLASS, REOPEN_APPLICATION)
        self.target.callback = None
