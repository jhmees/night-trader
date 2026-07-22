"""Rolling transcript buffer. The app is the memory; the LLM has none."""

from __future__ import annotations

import threading
import time

from transcriber import Segment


class RollingBuffer:
    def __init__(self, retention_sec: float = 300.0):
        self.retention_sec = retention_sec
        self._entries: list[tuple[float, Segment]] = []  # (wall_time, segment)
        self._lock = threading.Lock()

    def append(self, segment: Segment, wall_time: float | None = None) -> None:
        now = wall_time if wall_time is not None else time.time()
        with self._lock:
            self._entries.append((now, segment))
            cutoff = time.time() - self.retention_sec
            while self._entries and self._entries[0][0] < cutoff:
                self._entries.pop(0)

    def purge(self) -> None:
        with self._lock:
            self._entries.clear()

    def window(self, seconds: float, now: float | None = None) -> str:
        """Last `seconds` of transcript as tagged lines, oldest first."""
        now = now if now is not None else time.time()
        cutoff = now - seconds
        with self._lock:
            recent = [(t, s) for t, s in self._entries if t >= cutoff]
        lines = []
        for t, seg in recent:
            ago = int(now - t)
            who = "THEM" if seg.channel == "them" else "ME"
            lines.append(f"[-{ago:>3}s {who}] {seg.text}")
        return "\n".join(lines)
