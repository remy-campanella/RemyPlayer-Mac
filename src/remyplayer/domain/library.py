"""Library values and sorting rules, independent of Qt and storage."""
from dataclasses import dataclass
from functools import lru_cache
from pathlib import PurePath
import re
import unicodedata

from pypinyin import lazy_pinyin


@dataclass(frozen=True)
class Track:
    """扫描得到的不可变曲目快照；duration 以秒计，mtime_ns 为纳秒修改时间。

    path 是本机绝对路径；relative_path 相对于音乐库根目录，用于索引和分组。
    """
    path: str
    relative_path: str
    title: str
    artist: str
    album: str
    duration: float
    size: int
    mtime_ns: int

    @property
    def filename(self):
        return PurePath(self.relative_path).name

    @property
    def folder(self):
        """返回直接父目录的相对路径；根目录曲目返回 "."，不向祖先目录重复归类。"""
        return str(PurePath(self.relative_path).parent)


@lru_cache(maxsize=20000)
def natural_key(value: str):
    """生成兼容中文拼音、大小写和数字段的自然排序键。

    先做 NFKC 规范化和大小写折叠，再使用 pypinyin 默认读音。
    数字按数值比较；数值相等时前导零较多的在前，例如 01 排在 1 前。
    """
    normalized = unicodedata.normalize("NFKC", value).casefold()
    transliterated = "".join(lazy_pinyin(normalized))
    # Longer numeric spellings precede shorter ones when values are equal: 01 < 1.
    return tuple(
        (0, int(part), -len(part)) if part.isdecimal() else (1, part)
        for part in re.split(r"(\d+)", transliterated) if part
    )


def track_key(track: Track):
    """按包含扩展名的文件名排序，再以原始文件名和相对路径确定稳定次序。"""
    return natural_key(track.filename), track.filename, track.relative_path


def group_tracks(tracks, category):
    """按 folder、artist 或 album 分组，并对组名及组内曲目自然排序。

    文件夹键保留完整相对路径以区分同名目录；同名作者或专辑合并。
    未知 category 会引发 KeyError。
    """
    fields = {"folder": "folder", "artist": "artist", "album": "album"}
    field = fields[category]
    groups = {}
    for track in tracks:
        groups.setdefault(getattr(track, field), []).append(track)
    return {
        key: sorted(groups[key], key=track_key)
        for key in sorted(groups, key=lambda value: (natural_key(value), value))
    }


def format_time(seconds):
    """将秒数截断并限制为非负值，格式化为 M:SS 或 H:MM:SS。"""
    seconds = max(0, int(seconds))
    hours, rest = divmod(seconds, 3600)
    minutes, seconds = divmod(rest, 60)
    return f"{hours}:{minutes:02}:{seconds:02}" if hours else f"{minutes}:{seconds:02}"
