"""Tests for the OHLCV candle aggregation engine."""

import pytest

from app.services.aggregator import aggregate_candles, parse_interval, validate_interval


# ---------------------------------------------------------------------------
# parse_interval
# ---------------------------------------------------------------------------


def test_parse_interval():
    """'15m' -> (15, 'm'), '4H' -> (4, 'H'), '1D' -> (1, 'D')."""
    assert parse_interval("15m") == (15, "m")
    assert parse_interval("4H") == (4, "H")
    assert parse_interval("1D") == (1, "D")
    assert parse_interval("1W") == (1, "W")
    assert parse_interval("2H") == (2, "H")
    assert parse_interval("45m") == (45, "m")
    assert parse_interval("999W") == (999, "W")


def test_parse_interval_invalid():
    """Invalid formats raise ValueError."""
    with pytest.raises(ValueError):
        parse_interval("")
    with pytest.raises(ValueError):
        parse_interval("abc")
    with pytest.raises(ValueError):
        parse_interval("0m")
    with pytest.raises(ValueError):
        parse_interval("1h")  # lowercase h not allowed
    with pytest.raises(ValueError):
        parse_interval("1M")  # month not supported
    with pytest.raises(ValueError):
        parse_interval("1000D")  # >999
    with pytest.raises(ValueError):
        parse_interval("-1m")


# ---------------------------------------------------------------------------
# validate_interval
# ---------------------------------------------------------------------------


def test_validate_interval_valid():
    """Valid intervals: '1m', '5m', '15m', '1H', '4H', '1D', '1W', '2H', '45m', '999W'."""
    valid = ["1m", "5m", "15m", "1H", "4H", "1D", "1W", "2H", "45m", "999W"]
    for iv in valid:
        result = validate_interval(iv)
        assert result == iv, f"Expected {iv!r}, got {result!r}"


def test_validate_interval_invalid():
    """Invalid: '0m', '1h' (lowercase h), '1000D', '1M' (month not supported), '', 'abc'."""
    invalid = ["0m", "1h", "1000D", "1M", "", "abc"]
    for iv in invalid:
        with pytest.raises(ValueError, match=iv if iv else "Invalid interval"):
            validate_interval(iv)


# ---------------------------------------------------------------------------
# Helpers for building test bars
# ---------------------------------------------------------------------------


def _bar(time: int, o: float, h: float, l: float, c: float, v: int) -> dict:
    return {"time": time, "open": o, "high": h, "low": l, "close": c, "volume": v}


def _minute_ts(year: int, month: int, day: int, hour: int, minute: int) -> int:
    """Return a UTC unix timestamp for the given datetime components."""
    import calendar
    import datetime

    dt = datetime.datetime(year, month, day, hour, minute, tzinfo=datetime.timezone.utc)
    return int(calendar.timegm(dt.timetuple()))


# ---------------------------------------------------------------------------
# aggregate_candles — 5m from 1m
# ---------------------------------------------------------------------------


def test_aggregate_5m_from_1m():
    """5 consecutive 1m bars aggregate into one 5m candle with correct OHLCV."""
    base = _minute_ts(2026, 3, 10, 10, 0)  # 10:00 UTC, a Tuesday
    bars = [
        _bar(base + 0 * 60, 100, 102, 99, 101, 1000),
        _bar(base + 1 * 60, 101, 105, 100, 103, 1500),
        _bar(base + 2 * 60, 103, 104, 98, 99, 800),
        _bar(base + 3 * 60, 99, 100, 97, 98, 1200),
        _bar(base + 4 * 60, 98, 101, 96, 100, 900),
    ]
    result = aggregate_candles(bars, "5m")

    assert len(result) == 1
    candle = result[0]
    assert candle["time"] == base  # aligned to :00
    assert candle["open"] == 100  # first bar's open
    assert candle["high"] == 105  # max high
    assert candle["low"] == 96  # min low
    assert candle["close"] == 100  # last bar's close
    assert candle["volume"] == 5400  # sum


# ---------------------------------------------------------------------------
# aggregate_candles — 1H alignment
# ---------------------------------------------------------------------------


def test_aggregate_1h_alignment():
    """1m bars at 09:50-10:10 produce two 1H candles (09:xx and 10:xx)."""
    bars = []
    # 09:50 to 09:59 — 10 bars in the 09:00 bucket
    for m in range(50, 60):
        t = _minute_ts(2026, 3, 10, 9, m)
        bars.append(_bar(t, 100, 101, 99, 100, 100))
    # 10:00 to 10:10 — 11 bars in the 10:00 bucket
    for m in range(0, 11):
        t = _minute_ts(2026, 3, 10, 10, m)
        bars.append(_bar(t, 200, 201, 199, 200, 200))

    result = aggregate_candles(bars, "1H")

    assert len(result) == 2
    assert result[0]["time"] == _minute_ts(2026, 3, 10, 9, 0)
    assert result[0]["open"] == 100
    assert result[0]["volume"] == 1000  # 10 * 100
    assert result[1]["time"] == _minute_ts(2026, 3, 10, 10, 0)
    assert result[1]["open"] == 200
    assert result[1]["volume"] == 2200  # 11 * 200


# ---------------------------------------------------------------------------
# aggregate_candles — 4H alignment
# ---------------------------------------------------------------------------


def test_aggregate_4h_alignment():
    """Bars are grouped into 4H boundaries aligned to midnight UTC."""
    # Bars at 03:00, 04:00, 07:00, 08:00
    bars = [
        _bar(_minute_ts(2026, 3, 10, 3, 0), 10, 11, 9, 10, 100),  # 00:00 bucket
        _bar(_minute_ts(2026, 3, 10, 4, 0), 20, 21, 19, 20, 200),  # 04:00 bucket
        _bar(_minute_ts(2026, 3, 10, 7, 0), 30, 31, 29, 30, 300),  # 04:00 bucket
        _bar(_minute_ts(2026, 3, 10, 8, 0), 40, 41, 39, 40, 400),  # 08:00 bucket
    ]
    result = aggregate_candles(bars, "4H")

    assert len(result) == 3
    # 00:00-03:59 bucket
    assert result[0]["time"] == _minute_ts(2026, 3, 10, 0, 0)
    assert result[0]["open"] == 10
    assert result[0]["close"] == 10
    # 04:00-07:59 bucket
    assert result[1]["time"] == _minute_ts(2026, 3, 10, 4, 0)
    assert result[1]["open"] == 20
    assert result[1]["high"] == 31
    assert result[1]["low"] == 19
    assert result[1]["close"] == 30
    assert result[1]["volume"] == 500
    # 08:00-11:59 bucket
    assert result[2]["time"] == _minute_ts(2026, 3, 10, 8, 0)
    assert result[2]["open"] == 40


# ---------------------------------------------------------------------------
# aggregate_candles — daily
# ---------------------------------------------------------------------------


def test_aggregate_daily():
    """All bars on same calendar day (UTC) aggregate into one daily candle."""
    bars = [
        _bar(_minute_ts(2026, 3, 10, 9, 0), 100, 110, 95, 105, 1000),
        _bar(_minute_ts(2026, 3, 10, 12, 0), 105, 115, 100, 110, 2000),
        _bar(_minute_ts(2026, 3, 10, 15, 0), 110, 120, 105, 115, 1500),
    ]
    result = aggregate_candles(bars, "1D")

    assert len(result) == 1
    assert result[0]["time"] == _minute_ts(2026, 3, 10, 0, 0)
    assert result[0]["open"] == 100
    assert result[0]["high"] == 120
    assert result[0]["low"] == 95
    assert result[0]["close"] == 115
    assert result[0]["volume"] == 4500


# ---------------------------------------------------------------------------
# aggregate_candles — weekly
# ---------------------------------------------------------------------------


def test_aggregate_weekly():
    """Bars spanning Mon-Sun aggregate into one weekly candle."""
    # 2026-03-09 is Monday, 2026-03-15 is Sunday (ISO week 11)
    bars = [
        _bar(_minute_ts(2026, 3, 9, 10, 0), 100, 105, 98, 103, 500),   # Monday
        _bar(_minute_ts(2026, 3, 11, 10, 0), 103, 110, 101, 108, 600),  # Wednesday
        _bar(_minute_ts(2026, 3, 13, 10, 0), 108, 112, 106, 111, 700),  # Friday
    ]
    result = aggregate_candles(bars, "1W")

    assert len(result) == 1
    # Week starts Monday 2026-03-09
    assert result[0]["time"] == _minute_ts(2026, 3, 9, 0, 0)
    assert result[0]["open"] == 100
    assert result[0]["high"] == 112
    assert result[0]["low"] == 98
    assert result[0]["close"] == 111
    assert result[0]["volume"] == 1800


# ---------------------------------------------------------------------------
# aggregate_candles — edge cases
# ---------------------------------------------------------------------------


def test_aggregate_skips_empty_groups():
    """No output candle for time groups with no input bars."""
    # Two bars in different 1H groups with a gap between
    bars = [
        _bar(_minute_ts(2026, 3, 10, 9, 30), 100, 101, 99, 100, 500),
        _bar(_minute_ts(2026, 3, 10, 11, 30), 200, 201, 199, 200, 600),
    ]
    result = aggregate_candles(bars, "1H")

    # Should produce exactly 2 candles (09:00 and 11:00), not 3
    assert len(result) == 2
    assert result[0]["time"] == _minute_ts(2026, 3, 10, 9, 0)
    assert result[1]["time"] == _minute_ts(2026, 3, 10, 11, 0)


def test_aggregate_preserves_order():
    """Output candles are sorted by time ascending."""
    bars = [
        _bar(_minute_ts(2026, 3, 10, 14, 0), 300, 301, 299, 300, 300),
        _bar(_minute_ts(2026, 3, 10, 10, 0), 100, 101, 99, 100, 100),
        _bar(_minute_ts(2026, 3, 10, 12, 0), 200, 201, 199, 200, 200),
    ]
    result = aggregate_candles(bars, "1H")

    assert len(result) == 3
    assert result[0]["time"] < result[1]["time"] < result[2]["time"]


def test_aggregate_volume_sum():
    """Volume is summed across all bars in a group."""
    base = _minute_ts(2026, 3, 10, 10, 0)
    bars = [
        _bar(base + 0 * 60, 100, 101, 99, 100, 1000),
        _bar(base + 1 * 60, 100, 101, 99, 100, 2000),
        _bar(base + 2 * 60, 100, 101, 99, 100, 3000),
    ]
    result = aggregate_candles(bars, "15m")

    assert len(result) == 1
    assert result[0]["volume"] == 6000


def test_aggregate_single_bar():
    """Single bar returns itself (trivial aggregation)."""
    bar = _bar(_minute_ts(2026, 3, 10, 10, 30), 100, 105, 95, 102, 5000)
    result = aggregate_candles([bar], "1H")

    assert len(result) == 1
    assert result[0]["open"] == 100
    assert result[0]["high"] == 105
    assert result[0]["low"] == 95
    assert result[0]["close"] == 102
    assert result[0]["volume"] == 5000
    assert result[0]["time"] == _minute_ts(2026, 3, 10, 10, 0)


def test_aggregate_empty_input():
    """Empty input returns empty output."""
    assert aggregate_candles([], "5m") == []


# ---------------------------------------------------------------------------
# Performance sanity check
# ---------------------------------------------------------------------------


def test_aggregate_100k_bars_performance():
    """100K+ bars aggregate without error (performance sanity check)."""
    base = _minute_ts(2026, 1, 1, 0, 0)
    bars = [
        _bar(base + i * 60, 100, 101, 99, 100, 100) for i in range(100_000)
    ]
    result = aggregate_candles(bars, "1H")

    # 100K minutes = ~1667 hours → ~1667 candles
    assert len(result) > 1000
    assert all(r["time"] <= r2["time"] for r, r2 in zip(result, result[1:]))
