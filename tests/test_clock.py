from __future__ import annotations

import pytest
from labkit.clock import Clock, RealClock, VirtualClock


def test_virtual_clock_advancement() -> None:
    clock = VirtualClock(initial_time=42.0)
    assert isinstance(clock, Clock)
    assert clock.now() == 42.0

    clock.sleep(10.5)
    assert clock.now() == 52.5


def test_virtual_clock_negative_sleep_rejected() -> None:
    clock = VirtualClock()
    with pytest.raises(ValueError, match="Cannot sleep for negative duration"):
        clock.sleep(-1.0)


def test_virtual_clock_time_cannot_flow_backward() -> None:
    clock = VirtualClock(initial_time=100.0)
    with pytest.raises(ValueError, match="Time cannot flow backwards"):
        clock.set_time(50.0)


def test_real_clock_protocol() -> None:
    clock = RealClock()
    assert isinstance(clock, Clock)
    t1 = clock.now()
    assert t1 > 0
