"""Check dependencies without opening a window or playing audio."""

import os
import platform
import sqlite3
import sys
from importlib.metadata import version

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtCore import qVersion
from PySide6.QtMultimedia import QAudioOutput, QMediaPlayer
from PySide6.QtWidgets import QApplication, QWidget
from pypinyin import lazy_pinyin
import mutagen


def main():
    app = QApplication([])
    widget = QWidget()
    player = QMediaPlayer()
    output = QAudioOutput()
    player.setAudioOutput(output)
    with sqlite3.connect(":memory:") as connection:
        connection.execute("SELECT 1").fetchone()
    assert lazy_pinyin("音乐") == ["yin", "yue"]
    if sys.platform == "darwin":
        import AppKit

        assert AppKit.NSApplication is not None
        print(f"PyObjC Cocoa: {version('pyobjc-framework-Cocoa')}")
    print(f"Python: {platform.python_version()}")
    print(f"Virtual environment: {sys.prefix != sys.base_prefix}")
    print(f"PySide6: {version('PySide6')} / Qt: {qVersion()}")
    print(f"Mutagen: {version('mutagen')} / pypinyin: {version('pypinyin')}")
    print("OK: Qt Widgets, Qt Multimedia, SQLite, pinyin and macOS bridge")
    player.stop()
    widget.close()
    app.processEvents()


if __name__ == "__main__":
    main()
