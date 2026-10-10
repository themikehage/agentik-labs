from __future__ import annotations

import time
from typing import Protocol, runtime_checkable


@runtime_checkable
class Clock(Protocol):
    """Protocol for time sources, allowing zero-latency simulation of timeouts and latencies."""

    def now(self) -> float:
        """Returns the current timestamp in fractional seconds."""
        ...

    def sleep(self, seconds: float) -> None:
        """Pauses or advances time by the given duration in seconds."""
        ...


class RealClock:
    """Real-world clock backed by Python's standard time module."""

    def now(self) -> float:
        return time.time()

    def sleep(self, seconds: float) -> None:
        if seconds > 0:
            time.sleep(seconds)


class VirtualClock:
    """Injectable virtual clock that advances instantaneously without real CPU sleep."""

    def __init__(self, initial_time: float = 0.0) -> None:
        self._current_time: float = float(initial_time)

    def now(self) -> float:
        return self._current_time

    def sleep(self, seconds: float) -> None:
        if seconds < 0:
            raise ValueError(f"Cannot sleep for negative duration: {seconds}")
        self._current_time += seconds

    def set_time(self, new_time: float) -> None:
        if new_time < self._current_time:
            raise ValueError("Time cannot flow backwards in VirtualClock")
        self._current_time = new_time
