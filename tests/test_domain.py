from pathlib import Path
import random
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from remyplayer.domain.library import Track, format_time, group_tracks, natural_key
from remyplayer.domain.queue import PlayMode, QueueController


def track(name, artist="作者", album="专辑"):
    return Track(f"/music/{name}", name, Path(name).stem, artist, album, 65, 100, 1)


class SortingTests(unittest.TestCase):
    def test_prompt_examples(self):
        expected = [
            "01", "1", "2", "2.1.1", "2.1.2", "2.1.3", "2.1.8", "2.1.9",
            "2.1.10", "2.1.11", "3.1.1", "3.1.1a", "3.1.1b", "a", "aa", "ab",
            "abc1er", "abc2er", "abc9er", "abc10er",
        ]
        self.assertEqual(sorted(reversed(expected), key=natural_key), expected)

    def test_chinese_and_case(self):
        self.assertEqual(sorted(["中国", "北京", "上海"], key=natural_key), ["北京", "上海", "中国"])
        self.assertEqual(natural_key("ABC2"), natural_key("abc2"))
        self.assertEqual(natural_key("ＡＢＣ２"), natural_key("abc2"))

    def test_direct_folder_membership(self):
        groups = group_tracks([track("2.wav"), track("suite/1.wav"), track("suite/more/3.wav")], "folder")
        self.assertEqual([t.relative_path for t in groups["."]], ["2.wav"])
        self.assertEqual([t.relative_path for t in groups["suite"]], ["suite/1.wav"])

    def test_artist_and_album_grouping(self):
        tracks = [track("10.wav", "乙"), track("2.wav", "甲"), track("1.wav", "甲")]
        self.assertEqual([t.filename for t in group_tracks(tracks, "artist")["甲"]], ["1.wav", "2.wav"])
        self.assertEqual(len(group_tracks(tracks, "album")["专辑"]), 3)

    def test_time_over_one_hour(self):
        self.assertEqual(format_time(3661), "1:01:01")
        self.assertEqual(format_time(-1), "0:00")


class QueueTests(unittest.TestCase):
    def setUp(self):
        self.tracks = [track(f"{i}.wav") for i in range(4)]
        self.queue = QueueController(random.Random(8))
        self.queue.start(self.tracks, 0)

    def test_once_and_repeat(self):
        self.queue.set_mode(PlayMode.ONCE)
        self.assertIsNone(self.queue.next(automatic=True))
        self.assertEqual(self.queue.current, self.tracks[0])
        self.queue.set_mode(PlayMode.REPEAT_ONE)
        self.assertEqual(self.queue.next(automatic=True), self.tracks[0])
        self.assertEqual(self.queue.next(), self.tracks[1])

    def test_order_stops_and_loop_wraps(self):
        self.queue.start(self.tracks, 3)
        self.assertIsNone(self.queue.next(automatic=True))
        self.queue.set_mode(PlayMode.LOOP)
        self.assertEqual(self.queue.next(automatic=True), self.tracks[0])
        self.assertEqual(self.queue.previous(), self.tracks[-1])

    def test_shuffle_no_repeats_and_history(self):
        self.queue.set_mode(PlayMode.SHUFFLE)
        played = [self.queue.current]
        played.extend(self.queue.next(automatic=True) for _ in range(3))
        self.assertEqual(len(set(played)), 4)
        self.assertEqual(self.queue.previous(), played[-2])
        self.assertEqual(self.queue.next(), played[-1])
        second_round = [self.queue.next() for _ in range(4)]
        self.assertNotEqual(second_round[0], played[-1])
        self.assertEqual(set(second_round), set(played))

    def test_empty_and_one_track(self):
        empty = QueueController()
        self.assertIsNone(empty.next())
        self.assertIsNone(empty.previous())
        self.assertIsNone(empty.start([], 0))
        self.queue.start(self.tracks[:1], 0)
        self.queue.set_mode(PlayMode.SHUFFLE)
        self.assertEqual(self.queue.next(), self.tracks[0])

    def test_queue_is_snapshot(self):
        self.tracks.clear()
        self.assertEqual(len(self.queue.tracks), 4)
        self.assertIsNotNone(self.queue.next())


if __name__ == "__main__":
    unittest.main()
