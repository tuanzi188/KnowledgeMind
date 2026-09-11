import json
import time
from typing import Any, Optional


class TimedLRUCache:
    """带 TTL 的简易 LRU 缓存。

    使用 JSON 序列化构造 key，支持任意可 JSON 序列化的位置/关键字参数。
    非线程安全，需在单线程/协程内使用，或配合外部锁。
    """

    def __init__(self, maxsize: int = 128, ttl_seconds: float = 300):
        self._maxsize = maxsize
        self._ttl = ttl_seconds
        self._cache: dict[str, tuple[Any, float]] = {}
        self._order: list[str] = []

    def _make_key(self, *args, **kwargs) -> str:
        return json.dumps({"args": args, "kwargs": kwargs}, sort_keys=True, ensure_ascii=False)

    def get(self, *args, **kwargs) -> Optional[Any]:
        key = self._make_key(*args, **kwargs)
        if key not in self._cache:
            return None
        value, expires_at = self._cache[key]
        if time.time() > expires_at:
            self._delete(key)
            return None
        self._order.remove(key)
        self._order.append(key)
        return value

    def set(self, value: Any, *args, **kwargs):
        key = self._make_key(*args, **kwargs)
        now = time.time()
        if key in self._cache:
            self._order.remove(key)
        self._cache[key] = (value, now + self._ttl)
        self._order.append(key)
        if len(self._order) > self._maxsize:
            oldest = self._order.pop(0)
            del self._cache[oldest]

    def _delete(self, key: str):
        self._order.remove(key)
        del self._cache[key]

    def clear(self):
        self._cache.clear()
        self._order.clear()
