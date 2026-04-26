from __future__ import annotations

from collections import OrderedDict
from PyQt6.QtGui import QPixmap


class PixmapLRUCache:
    """LRU-кэш QPixmap с лимитом по суммарному размеру в байтах."""

    def __init__(self, max_bytes: int = 256 * 1024 * 1024) -> None:
        self._max_bytes = max_bytes
        self._items: "OrderedDict[str, QPixmap]" = OrderedDict()
        self._total = 0

    @staticmethod
    def _size_of(pix: QPixmap) -> int:
        try:
            n = pix.sizeInBytes()
            if n > 0:
                return int(n)
        except Exception:
            pass
        return max(1, pix.width() * pix.height() * (pix.depth() // 8 or 4))

    def get(self, key: str) -> QPixmap | None:
        pix = self._items.get(key)
        if pix is not None:
            self._items.move_to_end(key)
        return pix

    def put(self, key: str, pix: QPixmap) -> None:
        if key in self._items:
            self._total -= self._size_of(self._items[key])
            del self._items[key]
        self._items[key] = pix
        self._total += self._size_of(pix)
        while self._total > self._max_bytes and self._items:
            _, victim = self._items.popitem(last=False)
            self._total -= self._size_of(victim)

    def clear(self) -> None:
        self._items.clear()
        self._total = 0

    def __len__(self) -> int:
        return len(self._items)
