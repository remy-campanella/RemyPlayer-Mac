"""Playback order is independent of the currently browsed library view."""
from enum import StrEnum
import random


class PlayMode(StrEnum):
    """播放模式的持久化值；ONCE 表示当前单曲结束后停止。"""
    ONCE = "不循环"
    REPEAT_ONE = "单曲循环"
    ORDER = "顺序播放"
    LOOP = "循环播放"
    SHUFFLE = "随机播放"


class QueueController:
    """管理独立于界面筛选的播放快照、当前位置及随机历史。

    本类只决定下一首，不调用音频设备；可传入 rng 以复现随机行为。
    """
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
        """复制曲目序列并从 index 开始；无效索引返回 None，保留原队列。"""
        if not 0 <= index < len(tracks):
            return None
        self.tracks = tuple(tracks)
        # 只在显式开始播放时建立快照；之后界面筛选、排序或扫描不会改写队列。
        self.index = index
        self.set_mode(self.mode)
        return self.current

    def set_mode(self, mode):
        """切换模式并重置随机历史及待播袋，保留当前曲目。"""
        self.mode = PlayMode(mode)
        self._history = [self.index] if self.current else []
        self._cursor = len(self._history) - 1
        self._refill()

    def _refill(self, first_round=True):
        """重建随机待播袋；首轮排除当前项，后续轮避免与上一轮末尾重复。"""
        self._bag = [i for i in range(len(self.tracks)) if not first_round or i != self.index]
        self.rng.shuffle(self._bag)
        # pop() 从袋尾取曲目，因此需要将上轮末曲从尾部移开，避免跨轮连播同一首。
        if not first_round and len(self._bag) > 1 and self._bag[-1] == self.index:
            self._bag[0], self._bag[-1] = self._bag[-1], self._bag[0]

    def next(self, automatic=False):
        """返回下一首，无法继续时返回 None。

        automatic=True 用于自然播完，遵守单曲一次／单曲循环；手动切歌可越过它们。
        随机模式优先沿已有历史前进，再从本轮待播袋取曲目。
        """
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
        """返回上一首；随机模式回退播放历史，仅列表循环模式允许首尾回绕。"""
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
