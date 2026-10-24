"""Library values and sorting rules, independent of Qt and storage."""
from dataclasses import dataclass
from functools import lru_cache
from pathlib import PurePath
import re
import unicodedata

from pypinyin import lazy_pinyin


@dataclass(frozen=True)
class Track:
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
        return str(PurePath(self.relative_path).parent)


@lru_cache(maxsize=20000)
def natural_key(value: str):
    normalized = unicodedata.normalize("NFKC", value).casefold()
    transliterated = "".join(lazy_pinyin(normalized))
    # Longer numeric spellings precede shorter ones when values are equal: 01 < 1.
    return tuple(
        (0, int(part), -len(part)) if part.isdecimal() else (1, part)
        for part in re.split(r"(\d+)", transliterated) if part
    )


def track_key(track: Track):
    return natural_key(track.filename), track.filename, track.relative_path


def group_tracks(tracks, category):
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
    seconds = max(0, int(seconds))
    hours, rest = divmod(seconds, 3600)
    minutes, seconds = divmod(rest, 60)
    return f"{hours}:{minutes:02}:{seconds:02}" if hours else f"{minutes}:{seconds:02}"
