"""
Unit tests for MemorySampler.

Tests the daemon-thread RSS sampler used by the -vv memory profiling feature.
Covers: format_bytes, peak capture, thread lifecycle, and delta coherence.
"""

import time

import psutil
import pytest

from energizados.core.utils.memory_sampler import MemorySampler, format_bytes


class TestFormatBytes:
    def test_zero(self):
        assert format_bytes(0) == "0B"

    def test_small_bytes(self):
        assert format_bytes(512) == "512B"

    def test_kilobytes(self):
        assert format_bytes(2048) == "2.0KB"

    def test_megabytes(self):
        assert format_bytes(5 * 1024**2) == "5.0MB"

    def test_gigabytes(self):
        assert format_bytes(2 * 1024**3) == "2.0GB"

    def test_none(self):
        assert format_bytes(None) == "—"

    def test_negative_delta(self):
        assert format_bytes(-2048) == "-2.0KB"

    def test_negative_gigabytes(self):
        assert format_bytes(-(1024**3)) == "-1.0GB"


class TestMemorySamplerPeak:
    def test_peak_at_least_rss_start(self):
        proc = psutil.Process()
        with MemorySampler(interval_ms=20, process=proc) as s:
            _ = bytearray(30 * 1024 * 1024)  # 30MB
            time.sleep(0.15)
        assert s.rss_start > 0
        assert s.peak >= s.rss_start

    def test_stats_has_all_keys(self):
        proc = psutil.Process()
        with MemorySampler(interval_ms=20, process=proc) as s:
            time.sleep(0.05)
        stats = s.stats
        assert set(stats.keys()) == {"rss_start", "rss_end", "delta", "peak"}
        assert stats["peak"] == s.peak
        assert stats["delta"] == s.delta

    def test_peak_grows_when_allocating(self):
        """Allocating inside the block must raise peak above the start."""
        proc = psutil.Process()
        with MemorySampler(interval_ms=15, process=proc) as s:
            # Hold a large allocation long enough for several samples.
            big = bytearray(100 * 1024 * 1024)  # 100MB
            time.sleep(0.2)
            assert big  # keep reference alive inside the block
        # peak must clearly exceed the start baseline (100MB >> noise)
        assert s.peak > s.rss_start

    def test_delta_positive_when_retained(self):
        """A retained large allocation raises rss_end above rss_start."""
        proc = psutil.Process()
        retained = []
        with MemorySampler(interval_ms=20, process=proc) as s:
            retained.append(bytearray(100 * 1024 * 1024))  # 100MB held
            time.sleep(0.15)
        assert retained  # reference survives past __exit__
        assert s.rss_end > s.rss_start
        assert s.delta > 0


class TestMemorySamplerLifecycle:
    def test_thread_stops_after_exit(self):
        s = MemorySampler(interval_ms=20)
        with s:
            time.sleep(0.05)
        assert s._thread is not None
        assert not s._thread.is_alive()

    def test_reusable_context_manager(self):
        s = MemorySampler(interval_ms=20)
        with s:
            time.sleep(0.03)
        first_thread = s._thread
        assert not first_thread.is_alive()
        # second use creates a fresh thread
        with s:
            time.sleep(0.03)
        assert s._thread is not first_thread
        assert not s._thread.is_alive()


class TestMemorySamplerFastExit:
    def test_zero_interval_still_captures_start_and_end(self):
        """Even with no meaningful sampling window, start/end are recorded."""
        proc = psutil.Process()
        with MemorySampler(interval_ms=1000, process=proc) as s:
            pass  # exit immediately
        assert s.rss_start > 0
        assert s.rss_end > 0
        assert s.peak >= s.rss_start


if __name__ == "__main__":
    pytest.main([__file__, "-vv"])
