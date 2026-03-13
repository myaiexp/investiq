"""OHLCV candle aggregation engine.

Aggregates fine-grained (e.g. 1-minute) OHLCV bars into larger intervals
with proper time alignment (clock-aligned minutes, midnight-aligned hours,
calendar days, ISO weeks).
"""

import re

import pandas as pd

_INTERVAL_RE = re.compile(r"^([1-9]\d{0,2})([mHDW])$")


def parse_interval(interval: str) -> tuple[int, str]:
    """Parse interval string like '5m', '4H', '1D', '2W' into (count, unit).

    Valid: positive integer 1-999 followed by m/H/D/W (case-sensitive).
    Raises ValueError for invalid formats.
    """
    match = _INTERVAL_RE.match(interval)
    if not match:
        raise ValueError(f"Invalid interval: {interval!r}")
    return int(match.group(1)), match.group(2)


def validate_interval(interval: str) -> str:
    """Validate and normalize interval string. Returns normalized form.

    Raises ValueError if invalid (0 count, >999, wrong unit, wrong case).
    '1m' is valid (returns raw 1m data, no aggregation needed).
    """
    parse_interval(interval)
    return interval


def _to_unix_seconds(dt_series: pd.Series) -> pd.Series:
    """Convert a timezone-aware datetime Series to unix seconds (int64).

    Works correctly regardless of the underlying datetime64 resolution
    (nanoseconds in older pandas, seconds in pandas 2.2+).
    """
    # Subtracting the epoch gives a timedelta, .dt.total_seconds() is
    # resolution-agnostic, and we floor to int for clean grouping keys.
    epoch = pd.Timestamp("1970-01-01", tz="UTC")
    return ((dt_series - epoch).dt.total_seconds()).astype("int64")


def _compute_group_key(ts: pd.Series, count: int, unit: str) -> pd.Series:
    """Compute the group boundary timestamp for each bar.

    Args:
        ts: Series of UTC datetime64 timestamps.
        count: Interval count (e.g. 5 for '5m').
        unit: Interval unit: 'm', 'H', 'D', or 'W'.

    Returns:
        Series of unix timestamps (int) representing the group boundary.
    """
    if unit == "m":
        # Clock-aligned: floor to nearest (count) minutes
        total_minutes = ts.dt.hour * 60 + ts.dt.minute
        floored_minutes = (total_minutes // count) * count
        group_dt = ts.dt.normalize() + pd.to_timedelta(floored_minutes, unit="m")
        return _to_unix_seconds(group_dt)

    elif unit == "H":
        # Midnight-aligned: floor to nearest (count) hours
        floored_hours = (ts.dt.hour // count) * count
        group_dt = ts.dt.normalize() + pd.to_timedelta(floored_hours, unit="h")
        return _to_unix_seconds(group_dt)

    elif unit == "D":
        # Calendar days: floor to start of day
        group_dt = ts.dt.normalize()
        return _to_unix_seconds(group_dt)

    elif unit == "W":
        # ISO weeks: Monday start. Shift to Monday 00:00.
        # dayofweek: Monday=0, Sunday=6
        days_since_monday = ts.dt.dayofweek
        group_dt = (ts - pd.to_timedelta(days_since_monday, unit="D")).dt.normalize()
        return _to_unix_seconds(group_dt)

    else:
        raise ValueError(f"Unsupported unit: {unit!r}")


def aggregate_candles(bars: list[dict], interval: str) -> list[dict]:
    """Aggregate OHLCV bars into candles of the target interval.

    Input bars: list of dicts with keys {time (unix seconds), open, high,
    low, close, volume}.
    Output: same structure, aggregated per interval boundary.

    Grouping alignment (UTC):
    - Minutes: clock-aligned (15m -> :00, :15, :30, :45)
    - Hours: midnight-aligned (4H -> 00:00, 04:00, 08:00, ...)
    - Days: calendar days
    - Weeks: ISO weeks (Monday start)

    Aggregation per group:
    - open: first bar's open
    - high: max of all highs
    - low: min of all lows
    - close: last bar's close
    - volume: sum of all volumes

    Skips groups with no bars (e.g., outside market hours).
    Returns bars sorted by time ascending.
    """
    if not bars:
        return []

    count, unit = parse_interval(interval)

    df = pd.DataFrame(bars)
    df = df.sort_values("time")

    # Convert unix seconds to UTC datetime for grouping
    dt = pd.to_datetime(df["time"], unit="s", utc=True)

    # Compute group key (unix timestamp of group boundary)
    group_key = _compute_group_key(dt, count, unit)
    # Give the group key a distinct name so it doesn't clash with df columns
    group_key.name = "_boundary"

    # Aggregate with groupby, preserving first/last order
    # group_key becomes the index after groupby (boundary timestamps)
    grouped = df.groupby(group_key, sort=True)
    result = grouped.agg(
        open=("open", "first"),
        high=("high", "max"),
        low=("low", "min"),
        close=("close", "last"),
        volume=("volume", "sum"),
    )

    # Index (_boundary) holds the group boundary unix timestamp — use as time
    result = result.reset_index()
    result = result.rename(columns={"_boundary": "time"})

    # Reorder columns to match input format
    result = result[["time", "open", "high", "low", "close", "volume"]]

    # Convert to list of dicts with native Python types
    records = result.to_dict("records")
    for rec in records:
        rec["time"] = int(rec["time"])
        rec["volume"] = int(rec["volume"])

    return records
