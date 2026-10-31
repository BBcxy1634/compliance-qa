"""Tests for benchmark pricing and peak-period selection."""

from datetime import datetime
from zoneinfo import ZoneInfo

from src.benchmark import CN_TZ, is_peak, request_cost


def _pricing() -> dict:
    return {
        "off_peak": {
            "input_cache_hit": 0.02,
            "input_cache_miss": 1.0,
            "output": 4.0,
        },
        "peak": {
            "input_cache_hit": 0.04,
            "input_cache_miss": 2.0,
            "output": 8.0,
        },
    }


def test_peak_period_uses_china_weekdays() -> None:
    assert is_peak(datetime(2026, 10, 31, 10, 0, tzinfo=CN_TZ)) is False
    assert is_peak(datetime(2026, 11, 2, 10, 0, tzinfo=CN_TZ)) is True
    assert is_peak(datetime(2026, 11, 2, 13, 0, tzinfo=CN_TZ)) is False


def test_cost_uses_cache_hit_miss_and_output_rates() -> None:
    usage = {
        "prompt_tokens": 2_000_000,
        "prompt_cache_hit_tokens": 1_000_000,
        "prompt_cache_miss_tokens": 1_000_000,
        "completion_tokens": 1_000_000,
    }
    timestamp = datetime(2026, 10, 31, 10, 0, tzinfo=CN_TZ)
    cost, basis = request_cost(usage, _pricing(), timestamp)
    assert cost == 5.02
    assert basis["period"] == "off_peak"
