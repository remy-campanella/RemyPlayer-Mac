"""Read-only scanning and transactional, per-root index storage."""
from dataclasses import asdict, dataclass
from contextlib import contextmanager
import json
import os
from pathlib import Path
import sqlite3

import mutagen

from remyplayer.domain.library import Track, track_key

EXTENSIONS = {".mp3", ".flac", ".m4a", ".aac", ".ogg", ".opus", ".wav", ".aif", ".aiff", ".wma"}


class TrackRepository:
    """按规范化音乐库根路径隔离 SQLite 索引，不写入音乐文件。"""
    def __init__(self, database):
        self.database = Path(database)
        self.database.parent.mkdir(parents=True, exist_ok=True)
        with self.connect() as connection:
            version = connection.execute("PRAGMA user_version").fetchone()[0]
            if version not in (0, 1):
                raise RuntimeError(f"不支持的索引版本：{version}")
            connection.execute(
                "CREATE TABLE IF NOT EXISTS tracks "
                "(root TEXT NOT NULL, relative_path TEXT NOT NULL, data TEXT NOT NULL, "
                "PRIMARY KEY(root, relative_path))"
            )
            connection.execute("PRAGMA user_version = 1")

    @contextmanager
    def connect(self):
        """为一次操作创建连接，成功时提交、异常时回滚，并始终关闭连接。

        扫描在线程池执行，因此不能复用主线程创建的 SQLite 连接。
        """
        connection = sqlite3.connect(self.database)
        try:
            with connection:
                yield connection
        finally:
            connection.close()

    def load(self, root):
        """读取指定根目录的缓存快照；不检查原音频是否仍然存在。"""
        root = str(Path(root).expanduser().resolve())
        with self.connect() as connection:
            rows = connection.execute("SELECT data FROM tracks WHERE root = ?", (str(root),)).fetchall()
        return [Track(**json.loads(row[0])) for row in rows]

    def replace(self, root, tracks):
        """在同一事务中替换一个音乐库的完整索引，不影响其他音乐库。"""
        root = str(Path(root).expanduser().resolve())
        with self.connect() as connection:
            connection.execute("DELETE FROM tracks WHERE root = ?", (str(root),))
            connection.executemany(
                "INSERT INTO tracks(root, relative_path, data) VALUES (?, ?, ?)",
                [(str(root), track.relative_path, json.dumps(asdict(track), ensure_ascii=False)) for track in tracks],
            )


def read_track(path, root, stat):
    """只读解析音频及标签，返回 Track；无法识别的文件引发 ValueError。

    root 用于生成相对路径，stat 是调用方读取的文件状态。
    标题缺失时使用文件名，作者和专辑缺失时使用“未知”占位。
    """
    audio = mutagen.File(path, easy=True)
    if audio is None:
        raise ValueError("无法识别音频或标签格式")
    tags = audio.tags or {}

    def tag(key, fallback):
        values = tags.get(key)
        if not values:
            return fallback
        value = values[0] if isinstance(values, (list, tuple)) else values
        return str(value).strip() or fallback

    # WAV/AIFF use ID3 frame keys even when easy=True.
    def text(easy, id3, fallback):
        return tag(easy, tag(id3, fallback))

    return Track(
        str(path), str(path.relative_to(root)), text("title", "TIT2", path.stem),
        text("artist", "TPE1", "未知作者"), text("album", "TALB", "未知专辑"),
        float(getattr(audio.info, "length", 0) or 0), stat.st_size, stat.st_mtime_ns,
    )


@dataclass
class ScanResult:
    """一次扫描的结果；errors 为可展示的问题列表，cancelled 表示放弃本次结果。"""
    root: str
    tracks: list
    errors: list
    cancelled: bool = False


class LibraryScanner:
    """只读遍历音频目录，复用未变化文件的标签，并提交完整扫描索引。"""
    def __init__(self, repository):
        self.repository = repository

    def scan(self, root, cancelled=lambda: False, progress=lambda count, path: None):
        """扫描 root，返回包含自然排序曲目和逐文件错误的 ScanResult。

        Args:
            root: 音乐库根目录；不存在时引发 FileNotFoundError。
            cancelled: 无参数回调，返回真时取消，保留原索引。
            progress: 接收已检查的候选文件数及相对路径，在扫描线程调用。

        不跟随目录或文件符号链接。以文件大小和纳秒修改时间判断缓存命中。
        目录遍历失败时合并旧缓存且不提交，避免将暂时不可读的文件误判为删除。
        单个文件解析失败则记入 errors，其余可读目录继续扫描。
        """
        root = Path(root).expanduser().resolve()
        if not root.is_dir():
            raise FileNotFoundError(f"音乐库文件夹不可用：{root}")
        cached = {t.relative_path: t for t in self.repository.load(root)}
        tracks, errors, walk_errors = [], [], []
        count = 0
        for directory, dirs, files in os.walk(root, followlinks=False, onerror=walk_errors.append):
            dirs[:] = [d for d in dirs if not Path(directory, d).is_symlink()]
            for name in files:
                if cancelled():
                    return ScanResult(str(root), [], errors, True)
                path = Path(directory, name)
                if path.suffix.lower() not in EXTENSIONS or path.is_symlink():
                    continue
                count += 1
                try:
                    stat = path.stat()
                    old = cached.get(str(path.relative_to(root)))
                    if old and (old.size, old.mtime_ns) == (stat.st_size, stat.st_mtime_ns):
                        tracks.append(old)
                    else:
                        tracks.append(read_track(path, root, stat))
                except Exception as error:
                    errors.append(f"{path.relative_to(root)}：{error}")
                if count % 25 == 0:
                    progress(count, str(path.relative_to(root)))
        if cancelled():
            return ScanResult(str(root), [], errors, True)
        if walk_errors:
            # 遍历不完整时无法判断哪些曲目真正被删除，保留缺失缓存且不覆盖数据库。
            seen = {track.relative_path for track in tracks}
            tracks.extend(t for key, t in cached.items() if key not in seen)
            errors.extend(str(error) for error in walk_errors)
        else:
            self.repository.replace(root, tracks)
        progress(count, "完成")
        return ScanResult(str(root), sorted(tracks, key=track_key), errors)
