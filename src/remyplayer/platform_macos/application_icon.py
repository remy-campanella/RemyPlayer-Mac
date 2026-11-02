"""Keep the full ICNS image in the Dock instead of Qt's flattened QIcon."""
from pathlib import Path

from AppKit import NSApplication, NSImage
from Foundation import NSBundle


class ApplicationIcon:
    """保留含完整分辨率表示的原生 ICNS 图像，避免 Qt 转换造成 Dock 模糊。"""
    def __init__(self, fallback_path):
        """优先从正式应用包读取 ICNS，源码运行时使用 fallback_path；读取失败引发 RuntimeError。"""
        bundle = NSBundle.mainBundle()
        path = None
        if bundle.bundleIdentifier() == "app.remygrad.remyplayer":
            name = str(bundle.objectForInfoDictionaryKey_("CFBundleIconFile") or "icon.icns")
            path = bundle.pathForResource_ofType_(Path(name).stem, "icns")
        self.path = str(path or Path(fallback_path).resolve())
        self.image = NSImage.alloc().initWithContentsOfFile_(self.path)
        if self.image is None:
            raise RuntimeError(f"无法读取应用图标：{self.path}")
        self.maximum_size = max(int(rep.pixelsWide()) for rep in self.image.representations())
        # Retain every scale/DPI representation. In particular, do not resize
        # this NSImage to a menu-bar size or round-trip it through QPixmap.

    def apply(self, force=False):
        """在 AppKit 主线程应用保留的图像；force 为真时跳过尺寸检查强制刷新 Dock。"""
        application = NSApplication.sharedApplication()
        current = application.applicationIconImage()
        # AppKit's getter can return a raster snapshot rather than our original
        # NSImage, so pointer identity is not a useful change detector.
        if not force and current and current.size() == self.image.size():
            sizes = [int(rep.pixelsWide()) for rep in current.representations()]
            if sizes and max(sizes) >= self.maximum_size:
                return
        application.setApplicationIconImage_(self.image)
        application.dockTile().display()
