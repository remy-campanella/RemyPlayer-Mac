from pathlib import Path
import sys
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch
import wave

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from remyplayer.infrastructure.library import LibraryScanner, TrackRepository


def make_wav(path, seconds=0.4):
    path.parent.mkdir(parents=True, exist_ok=True)
    with wave.open(str(path), "wb") as output:
        output.setnchannels(1)
        output.setsampwidth(2)
        output.setframerate(8000)
        output.writeframes(b"\0\0" * int(8000 * seconds))


class ScannerTests(unittest.TestCase):
    def setUp(self):
        self.temp = TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        base = Path(self.temp.name)
        self.root = base / "music"
        self.root.mkdir()
        self.repository = TrackRepository(base / "data" / "library.sqlite3")
        self.scanner = LibraryScanner(self.repository)

    def test_scan_read_only_tags_and_cached_refresh(self):
        first = self.root / "01.wav"
        second = self.root / "suite" / "10.wav"
        make_wav(first)
        make_wav(second)
        before = {path: (path.read_bytes(), path.stat().st_mtime_ns) for path in self.root.rglob("*") if path.is_file()}
        result = self.scanner.scan(self.root)
        self.assertFalse(result.errors)
        self.assertEqual(len(result.tracks), 2)
        self.assertEqual(result.tracks[0].artist, "未知作者")
        self.assertAlmostEqual(result.tracks[0].duration, 0.4)
        self.assertEqual(len(self.repository.load(self.root)), 2)
        self.assertEqual(before, {path: (path.read_bytes(), path.stat().st_mtime_ns) for path in self.root.rglob("*") if path.is_file()})
        with patch("remyplayer.infrastructure.library.read_track", side_effect=AssertionError("cache miss")):
            cached = self.scanner.scan(self.root)
        self.assertEqual(cached.tracks, result.tracks)
        first.unlink()
        self.assertEqual(len(self.scanner.scan(self.root).tracks), 1)
        self.assertEqual(len(self.repository.load(self.root)), 1)

    def test_invalid_file_and_symlink_are_safe(self):
        (self.root / "broken.mp3").write_bytes(b"not audio")
        make_wav(self.root / "ok.wav")
        (self.root / "alias.wav").symlink_to(self.root / "ok.wav")
        result = self.scanner.scan(self.root)
        self.assertEqual(len(result.tracks), 1)
        self.assertEqual(len(result.errors), 1)
        self.assertIn("broken.mp3", result.errors[0])

    def test_cancellation_preserves_index(self):
        make_wav(self.root / "1.wav")
        original = self.scanner.scan(self.root)
        make_wav(self.root / "2.wav")
        cancelled = self.scanner.scan(self.root, cancelled=lambda: True)
        self.assertTrue(cancelled.cancelled)
        self.assertEqual(self.repository.load(self.root), original.tracks)

    def test_unavailable_root_preserves_index(self):
        make_wav(self.root / "1.wav")
        original = self.scanner.scan(self.root)
        offline = self.root.with_name("offline")
        self.root.rename(offline)
        with self.assertRaises(FileNotFoundError):
            self.scanner.scan(self.root)
        self.assertEqual(self.repository.load(self.root), original.tracks)

    def test_id3_tags_in_wav(self):
        from mutagen.wave import WAVE
        from mutagen.id3 import TIT2, TPE1, TALB
        path = self.root / "song.wav"
        make_wav(path)
        audio = WAVE(path)
        audio.add_tags()
        audio.tags.add(TIT2(encoding=3, text="标题"))
        audio.tags.add(TPE1(encoding=3, text="作者甲"))
        audio.tags.add(TALB(encoding=3, text="专辑甲"))
        audio.save()
        result = self.scanner.scan(self.root)
        self.assertEqual((result.tracks[0].title, result.tracks[0].artist, result.tracks[0].album), ("标题", "作者甲", "专辑甲"))


if __name__ == "__main__":
    unittest.main()
