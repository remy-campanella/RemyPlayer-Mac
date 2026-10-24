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
        connection = sqlite3.connect(self.database)
        try:
            with connection:
                yield connection
        finally:
            connection.close()

    def load(self, root):
        root = str(Path(root).expanduser().resolve())
        with self.connect() as connection:
            rows = connection.execute("SELECT data FROM tracks WHERE root = ?", (str(root),)).fetchall()
        return [Track(**json.loads(row[0])) for row in rows]

    def replace(self, root, tracks):
        root = str(Path(root).expanduser().resolve())
        with self.connect() as connection:
            connection.execute("DELETE FROM tracks WHERE root = ?", (str(root),))
            connection.executemany(
                "INSERT INTO tracks(root, relative_path, data) VALUES (?, ?, ?)",
                [(str(root), track.relative_path, json.dumps(asdict(track), ensure_ascii=False)) for track in tracks],
            )


def read_track(path, root, stat):
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
    root: str
    tracks: list
    errors: list
    cancelled: bool = False


class LibraryScanner:
    def __init__(self, repository):
        self.repository = repository

    def scan(self, root, cancelled=lambda: False, progress=lambda count, path: None):
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
            # Keep cached entries for unreadable subdirectories; never treat them as deleted.
            seen = {track.relative_path for track in tracks}
            tracks.extend(t for key, t in cached.items() if key not in seen)
            errors.extend(str(error) for error in walk_errors)
        else:
            self.repository.replace(root, tracks)
        progress(count, "完成")
        return ScanResult(str(root), sorted(tracks, key=track_key), errors)
