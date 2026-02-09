from __future__ import annotations
import math
from .errors import LuaRuntimeError


class LuaTable:
    __slots__ = ("_data", "_metatable", "_sequence_hint", "_next_keys")

    def __init__(self):
        self._data: dict = {}
        self._metatable: LuaTable | None = None
        self._sequence_hint: int = 0
        self._next_keys: list | None = None

    @staticmethod
    def _normalize_key(key):
        if isinstance(key, float):
            if math.isnan(key):
                raise LuaRuntimeError("table index is NaN")
            ik = int(key)
            if float(ik) == key:
                return ik
        return key

    def rawget(self, key):
        key = self._normalize_key(key)
        if key is None:
            return None
        return self._data.get(key)

    def rawset(self, key, value):
        key = self._normalize_key(key)
        if key is None:
            raise LuaRuntimeError("table index is nil")
        self._next_keys = None  # invalidate iteration cache
        if value is None:
            self._data.pop(key, None)
        else:
            self._data[key] = value
        # Update sequence hint
        if isinstance(key, int) and key >= 1:
            if value is not None and key == self._sequence_hint + 1:
                self._sequence_hint = key
                while (self._sequence_hint + 1) in self._data:
                    self._sequence_hint += 1
            elif value is None and key <= self._sequence_hint:
                self._sequence_hint = key - 1

    def length(self) -> int:
        """Return the length of the sequence part (# operator)."""
        # Fast path using hint
        if self._sequence_hint >= 0:
            n = self._sequence_hint
            if (n + 1) not in self._data:
                return n
        # Binary search fallback
        if 1 not in self._data:
            return 0
        j = 1
        while j in self._data:
            j *= 2
        lo, hi = j // 2, j
        while hi - lo > 1:
            mid = (lo + hi) // 2
            if mid in self._data:
                lo = mid
            else:
                hi = mid
        self._sequence_hint = lo
        return lo

    def next(self, key=None):
        """Return the next key-value pair after 'key', or the first if key is None."""
        if self._next_keys is None:
            self._next_keys = list(self._data.keys())
        keys = self._next_keys
        if key is None:
            if not keys:
                return None, None
            k = keys[0]
            return k, self._data[k]
        key = self._normalize_key(key)
        try:
            idx = keys.index(key)
        except ValueError:
            raise LuaRuntimeError("invalid key to 'next'")
        if idx + 1 >= len(keys):
            return None, None
        k = keys[idx + 1]
        return k, self._data.get(k)

    def to_list(self) -> list:
        """Extract the sequence part as a Python list."""
        result = []
        i = 1
        while True:
            v = self._data.get(i)
            if v is None:
                break
            result.append(v)
            i += 1
        return result

    @staticmethod
    def from_list(items: list) -> LuaTable:
        t = LuaTable()
        for i, v in enumerate(items, 1):
            t._data[i] = v
        t._sequence_hint = len(items)
        return t

    @staticmethod
    def from_dict(d: dict) -> LuaTable:
        t = LuaTable()
        for k, v in d.items():
            nk = LuaTable._normalize_key(k)
            if nk is not None and v is not None:
                t._data[nk] = v
        # Recompute sequence hint
        n = 0
        while (n + 1) in t._data:
            n += 1
        t._sequence_hint = n
        return t

    def __repr__(self):
        return f"table: 0x{id(self):016x}"
