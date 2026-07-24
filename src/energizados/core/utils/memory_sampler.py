"""Process-memory sampling utilities for the ``-vv`` profiling feature.

This module provides :class:`MemorySampler`, a context manager that tracks the
peak resident set size (RSS) of the current process while a block of code runs.

Design notes
------------
* **RSS via psutil** — pandas/numpy DataFrames live in C-level memory that
  ``tracemalloc`` cannot see. RSS reflects the real footprint the OS hands to
  the process, which is the metric that matters for ETL/training memory budgets.
* **Daemon sampler thread** — a lightweight thread polls RSS every
  ``interval_ms`` and keeps the maximum. It is a daemon so it never blocks
  interpreter shutdown, and it is joined on context exit to guarantee no
  sampling outlives the measured block.
* **Gated by callers** — sampling has a small cost, so callers (the CLI) must
  opt in via ``profile_memory=True``. Without ``-vv`` this module is never used
  and the overhead is exactly zero.
"""

from __future__ import annotations

import gc
import logging
import threading
from typing import Dict, Optional

import psutil

logger = logging.getLogger(__name__)


def format_bytes(num_bytes: Optional[int]) -> str:
    """Format a byte count as a compact human-readable string.

    Examples
    --------
    >>> format_bytes(0)
    '0B'
    >>> format_bytes(5 * 1024 ** 2)
    '5.0MB'
    >>> format_bytes(-(1024 ** 3))
    '-1.0GB'
    >>> format_bytes(None)
    '—'

    Parameters
    ----------
    num_bytes:
        Byte count, or ``None`` (rendered as an em dash).

    Returns:
        Compact representation with the largest fitting binary unit.
    """
    if num_bytes is None:
        return "—"
    if num_bytes == 0:
        return "0B"
    sign = "-" if num_bytes < 0 else ""
    magnitude = abs(num_bytes)
    for unit, divisor in (("GB", 1024**3), ("MB", 1024**2), ("KB", 1024)):
        if magnitude >= divisor:
            return f"{sign}{magnitude / divisor:.1f}{unit}"
    return f"{num_bytes}B"


class MemorySampler:
    """Context manager that samples process RSS to track peak memory.

    On enter it records ``rss_start`` and launches a daemon thread that polls
    :func:`psutil.Process.memory_info` every ``interval_ms`` milliseconds,
    keeping the highest RSS seen. On exit it stops the thread, runs
    :func:`gc.collect` (to attribute freed C-level buffers before the final
    reading), and records ``rss_end``.

    Attributes are also exposed through :attr:`stats` for convenient unpacking.

    Parameters
    ----------
    interval_ms:
        Sampling period in milliseconds. Default 100.
    process:
        Optional :class:`psutil.Process` instance. Defaults to the current
        process. Injected mainly for testing.

    Example
    -------
    >>> with MemorySampler() as s:
    ...     df = pd.read_parquet("big.parquet")
    >>> s.stats
    {'rss_start': 120_000_000, 'rss_end': 980_000_000,
     'delta': 860_000_000, 'peak': 1_200_000_000}
    """

    def __init__(
        self,
        interval_ms: int = 100,
        process: Optional[psutil.Process] = None,
    ) -> None:
        self.interval: float = max(interval_ms, 1) / 1000.0
        self._process = process
        self._proc: Optional[psutil.Process] = None
        self._thread: Optional[threading.Thread] = None
        self._stop = threading.Event()
        self._peak: int = 0
        self.rss_start: int = 0
        self.rss_end: int = 0

    def __enter__(self) -> "MemorySampler":
        self._proc = self._process or psutil.Process()
        self.rss_start = self._proc.memory_info().rss
        self._peak = self.rss_start
        self._stop.clear()
        self._thread = threading.Thread(target=self._sample, daemon=True)
        self._thread.start()
        return self

    def __exit__(self, *exc_info) -> None:
        self._stop.set()
        if self._thread is not None:
            self._thread.join(timeout=self.interval * 2 + 1.0)
            # Keep the reference so callers can inspect the (now-dead) thread;
            # __enter__ replaces it with a fresh instance on reuse.
        # Reclaim unreferenced buffers before the final reading so rss_end
        # reflects memory actually retained by the measured block.
        gc.collect()
        if self._proc is not None:
            try:
                self.rss_end = self._proc.memory_info().rss
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                self.rss_end = self.rss_start
        if self.rss_end > self._peak:
            self._peak = self.rss_end

    def _sample(self) -> None:
        """Poll RSS until :attr:`_stop` is set, keeping the peak."""
        while not self._stop.wait(self.interval):
            if self._proc is None:
                break
            try:
                rss = self._proc.memory_info().rss
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                logger.debug("MemorySampler: process vanished, stopping sampler")
                break
            if rss > self._peak:
                self._peak = rss

    @property
    def peak(self) -> int:
        """Highest RSS observed between enter and exit (bytes)."""
        return self._peak

    @property
    def delta(self) -> int:
        """Net memory retained by the block: ``rss_end - rss_start``."""
        return self.rss_end - self.rss_start

    @property
    def stats(self) -> Dict[str, int]:
        """All four measurements as a dict (start/end/delta/peak in bytes)."""
        return {
            "rss_start": self.rss_start,
            "rss_end": self.rss_end,
            "delta": self.delta,
            "peak": self.peak,
        }
