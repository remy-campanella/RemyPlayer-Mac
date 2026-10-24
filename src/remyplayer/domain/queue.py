"""Playback order is independent of the currently browsed library view."""
from enum import StrEnum
import random


class PlayMode(StrEnum):
    ONCE = "不循环"
    REPEAT_ONE = "单曲循环"
    ORDER = "顺序播放"
    LOOP = "循环播放"
    SHUFFLE = "随机播放"


class QueueController:
    def __init__(self, rng=None):
        self.tracks = ()
        self.index = -1
        self.mode = PlayMode.ORDER
        self.rng = rng or random.Random()
        self._history = []
        self._cursor = -1
        self._bag = []

    @property
    def current(self):
        return self.tracks[self.index] if 0 <= self.index < len(self.tracks) else None

    def start(self, tracks, index):
        if not 0 <= index < len(tracks):
            return None
        self.tracks = tuple(tracks)
        self.index = index
        self.set_mode(self.mode)
        return self.current

    def set_mode(self, mode):
        self.mode = PlayMode(mode)
        self._history = [self.index] if self.current else []
        self._cursor = len(self._history) - 1
        self._refill()

    def _refill(self, first_round=True):
        self._bag = [i for i in range(len(self.tracks)) if not first_round or i != self.index]
        self.rng.shuffle(self._bag)
        if not first_round and len(self._bag) > 1 and self._bag[-1] == self.index:
            self._bag[0], self._bag[-1] = self._bag[-1], self._bag[0]

    def next(self, automatic=False):
        if not self.current:
            return None
        if automatic and self.mode == PlayMode.ONCE:
            return None
        if automatic and self.mode == PlayMode.REPEAT_ONE:
            return self.current
        if self.mode == PlayMode.SHUFFLE:
            if self._cursor + 1 < len(self._history):
                self._cursor += 1
                self.index = self._history[self._cursor]
            else:
                if not self._bag:
                    self._refill(first_round=False)
                if self._bag:
                    self.index = self._bag.pop()
                self._history.append(self.index)
                self._cursor += 1
            return self.current
        if self.index + 1 < len(self.tracks):
            self.index += 1
        elif self.mode == PlayMode.LOOP:
            self.index = 0
        else:
            return None
        return self.current

    def previous(self):
        if not self.current:
            return None
        if self.mode == PlayMode.SHUFFLE:
            if self._cursor > 0:
                self._cursor -= 1
                self.index = self._history[self._cursor]
        elif self.index > 0:
            self.index -= 1
        elif self.mode == PlayMode.LOOP:
            self.index = len(self.tracks) - 1
        return self.current
