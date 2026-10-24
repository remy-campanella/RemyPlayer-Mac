"""Render our SVG into the macOS icon format using Qt and iconutil."""
from pathlib import Path
import subprocess
from tempfile import TemporaryDirectory

from PySide6.QtCore import QRectF, Qt
from PySide6.QtGui import QImage, QPainter
from PySide6.QtSvg import QSvgRenderer

resources = Path(__file__).resolve().parents[1] / "src" / "remyplayer" / "resources"
renderer = QSvgRenderer(str(resources / "icon.svg"))
if not renderer.isValid():
    raise SystemExit("Invalid SVG icon")
with TemporaryDirectory(prefix="remyplayer-icon-") as temporary:
    iconset = Path(temporary) / "RemyPlayer.iconset"
    iconset.mkdir()
    for size in (16, 32, 128, 256, 512):
        for scale in (1, 2):
            pixels = size * scale
            image = QImage(pixels, pixels, QImage.Format.Format_ARGB32_Premultiplied)
            image.fill(Qt.GlobalColor.transparent)
            painter = QPainter(image)
            renderer.render(painter, QRectF(0, 0, pixels, pixels))
            painter.end()
            suffix = "@2x" if scale == 2 else ""
            image.save(str(iconset / f"icon_{size}x{size}{suffix}.png"))
    subprocess.run(["iconutil", "-c", "icns", str(iconset), "-o", str(resources / "icon.icns")], check=True)
print(resources / "icon.icns")
