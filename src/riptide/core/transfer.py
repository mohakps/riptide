"""Transfer progress for a whole transfer batch.

Speed is an exponential moving average over properly spaced
updates, so a burst of callbacks cannot inflate it.
"""
from __future__ import annotations

import hashlib
import time
from pathlib import Path


def format_bytes(n: int) -> str:
    n = float(n)
    for unit in ("B", "KB", "MB", "GB", "TB"):
        if n < 1024 or unit == "TB":
            return f"{n:.1f} {unit}" if unit != "B" else f"{int(n)} B"
        n /= 1024
    return f"{n} B"


def format_eta(seconds: float | None) -> str:
    if seconds is None or seconds != seconds or seconds == float("inf"):
        return "--"
    seconds = int(seconds)
    if seconds < 60:
        return f"{seconds}s"
    minutes, secs = divmod(seconds, 60)
    if minutes < 60:
        return f"{minutes}m {secs:02d}s"
    hours, minutes = divmod(minutes, 60)
    return f"{hours}h {minutes:02d}m"


class TransferProgress:
    """EMA speed, remaining size, and ETA for one whole transfer."""

    def __init__(self, total: int):
        self.total = int(total)
        self.sent = 0
        self.started = time.monotonic()
        self._last_time = self.started
        self._last_sent = 0
        self.speed_ema = 0.0

    def update(self, sent: int) -> None:
        now = time.monotonic()
        self.sent = int(sent)
        dt = now - self._last_time
        # Guard against burst callbacks: if a caller floods updates
        # faster than the UI can process them, dt collapses to
        # microseconds while sent still jumps a full chunk, which
        # inflates speed by several times. Below 10ms, keep the
        # sent count for the progress bar, but do not feed the
        # speed EMA; the next, properly spaced update will then
        # average over the whole interval instead.
        if dt < 0.01:
            return
        instant = (self.sent - self._last_sent) / dt
        if self.speed_ema == 0:
            self.speed_ema = instant
        else:
            self.speed_ema = 0.7 * self.speed_ema + 0.3 * instant
        self._last_time = now
        self._last_sent = self.sent

    @property
    def remaining(self) -> int:
        return max(0, self.total - self.sent)

    @property
    def fraction(self) -> float:
        if self.total <= 0:
            return 1.0
        return min(1.0, self.sent / self.total)

    @property
    def eta_seconds(self) -> float | None:
        if self.speed_ema <= 0:
            return None
        return self.remaining / self.speed_ema








