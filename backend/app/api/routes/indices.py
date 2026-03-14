"""Index API routes — list indices, OHLCV data, indicators, and signals."""

import calendar
from collections import defaultdict
from datetime import datetime, timedelta, timezone

import pandas as pd
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.data.seed import INDICATOR_CATEGORIES
from app.models.market_data import Index, IndicatorData, OHLCVData, SignalData
from app.schemas.indices import (
    IndexMetaResponse,
    IndicatorDataResponse,
    IndicatorMetaResponse,
    OHLCVBarResponse,
    OHLCVResponse,
    SignalSummaryResponse,
)
from app.services.aggregator import aggregate_candles, validate_interval
from app.services.indicators import calculate_indicators, generate_signal

router = APIRouter(prefix="/indices", tags=["indices"])

# Known data quality issues — temporary until better data sources are added
INDEX_DATA_NOTES: dict[str, str] = {
    "URTH": "ETF proxy — price shown is URTH ETF ($), not the MSCI World index value (~4,350)",
    "OBX.OL": "Total return index (includes dividends), not the price-only OBX",
}

# Period string → number of days
PERIOD_DAYS: dict[str, int] = {
    "1m": 30,
    "3m": 90,
    "6m": 180,
    "1y": 365,
    "5y": 1825,
}

# Pre-aggregated intervals stored in ohlcv_data (from backfill + scheduler)
STANDARD_INTERVALS = {"1m", "5m", "15m", "1H", "4H", "1D", "1W"}

# Nearest standard interval for backfill stitching (smallest to largest)
_BACKFILL_PREFERENCE = ["5m", "15m", "1H", "4H", "1D", "1W"]

# Module-level cache: {ticker: earliest_1m_unix_timestamp}
_earliest_1m_cache: dict[str, int | None] = {}


def _period_start(period: str) -> datetime:
    """Convert a period string to a start datetime (now minus N days, UTC)."""
    days = PERIOD_DAYS.get(period, 365)
    return datetime.now(timezone.utc) - timedelta(days=days)


def _date_to_unix(d: datetime) -> int:
    """Convert a datetime to unix timestamp (seconds since epoch)."""
    return int(calendar.timegm(d.timetuple()))


async def _verify_index_exists(ticker: str, db: AsyncSession) -> None:
    """Raise 404 if ticker is not in the indices table."""
    result = await db.execute(select(Index).where(Index.ticker == ticker))
    if result.scalars().first() is None:
        raise HTTPException(status_code=404, detail=f"Index '{ticker}' not found")


async def get_earliest_1m(ticker: str, db: AsyncSession) -> int | None:
    """Query earliest 1m row for ticker. Cache result. Return unix timestamp or None."""
    if ticker in _earliest_1m_cache:
        return _earliest_1m_cache[ticker]

    result = await db.execute(
        select(OHLCVData)
        .where(OHLCVData.ticker == ticker, OHLCVData.interval == "1m")
        .order_by(OHLCVData.date)
    )
    row = result.scalars().first()
    if row is None:
        _earliest_1m_cache[ticker] = None
        return None

    ts = _date_to_unix(row.date)
    _earliest_1m_cache[ticker] = ts
    return ts


def _rows_to_bar_dicts(rows: list) -> list[dict]:
    """Convert ORM rows to bar dicts for the aggregator."""
    return [
        {
            "time": _date_to_unix(row.date),
            "open": row.open,
            "high": row.high,
            "low": row.low,
            "close": row.close,
            "volume": row.volume or 0.0,
        }
        for row in rows
    ]


def _bar_dicts_to_response(bars: list[dict]) -> list[OHLCVBarResponse]:
    """Convert raw bar dicts to OHLCVBarResponse instances."""
    return [
        OHLCVBarResponse(
            time=b["time"],
            open=b["open"],
            high=b["high"],
            low=b["low"],
            close=b["close"],
            volume=b["volume"],
        )
        for b in bars
    ]


def _bars_to_dataframe(bars: list[dict]) -> pd.DataFrame:
    """Convert bar dicts to a pandas DataFrame suitable for indicator calculation.

    Returns DataFrame with DatetimeIndex and columns: Open, High, Low, Close, Volume.
    """
    df = pd.DataFrame(bars)
    df["datetime"] = pd.to_datetime(df["time"], unit="s", utc=True)
    df = df.set_index("datetime").sort_index()
    df = df.rename(columns={
        "open": "Open",
        "high": "High",
        "low": "Low",
        "close": "Close",
        "volume": "Volume",
    })
    return df[["Open", "High", "Low", "Close", "Volume"]]


@router.get("/", response_model=list[IndexMetaResponse])
async def list_indices(db: AsyncSession = Depends(get_db)):
    """SELECT * FROM indices ORDER BY region, name."""
    result = await db.execute(select(Index).order_by(Index.region, Index.name))
    rows = result.scalars().all()
    return [
        IndexMetaResponse(
            name=row.name,
            ticker=row.ticker,
            region=row.region,
            price=row.price or 0.0,
            daily_change=row.daily_change or 0.0,
            signal=row.signal or "hold",
            currency=row.currency,
            data_note=INDEX_DATA_NOTES.get(row.ticker),
        )
        for row in rows
    ]


@router.get("/{ticker}/ohlcv", response_model=OHLCVResponse)
async def get_ohlcv(
    ticker: str,
    period: str = "1y",
    interval: str = "1D",
    db: AsyncSession = Depends(get_db),
):
    """Hybrid data serving:
    1. Validate interval with aggregator.validate_interval()
    2. Determine date range from period (using datetime, not date)
    3. For standard intervals (1m, 5m, 15m, 1H, 4H, 1D, 1W):
       query pre-aggregated data from ohlcv_data directly
    4. For custom intervals:
       a. Find earliest 1m row for this ticker (cached)
       b. Query 1m data for the date range
       c. Aggregate on the fly using aggregator.aggregate_candles()
       d. For dates before 1m data exists, query backfilled data at nearest
          standard interval and serve as-is
    5. Return OHLCVResponse with bars + metadata

    Reject if interval produces < 10 candles for the period (HTTP 400).
    """
    # Validate interval format
    try:
        validate_interval(interval)
    except ValueError:
        raise HTTPException(status_code=400, detail=f"Invalid interval: {interval!r}")

    await _verify_index_exists(ticker, db)

    start = _period_start(period)
    now_unix = _date_to_unix(datetime.now(timezone.utc))

    if interval in STANDARD_INTERVALS:
        # Standard path: query pre-aggregated data directly
        result = await db.execute(
            select(OHLCVData)
            .where(
                OHLCVData.ticker == ticker,
                OHLCVData.interval == interval,
                OHLCVData.date >= start,
            )
            .order_by(OHLCVData.date)
        )
        rows = result.scalars().all()
        bars = [
            OHLCVBarResponse(
                time=_date_to_unix(row.date),
                open=row.open,
                high=row.high,
                low=row.low,
                close=row.close,
                volume=row.volume or 0.0,
            )
            for row in rows
        ]
        return OHLCVResponse(
            bars=bars,
            data_transition_timestamp=None,
            last_updated=now_unix,
        )

    # Custom interval path: aggregate from 1m data
    earliest_1m = await get_earliest_1m(ticker, db)
    transition_ts: int | None = earliest_1m

    all_bars: list[dict] = []

    # Part A: Backfill data for dates before 1m coverage
    if earliest_1m is not None:
        earliest_1m_dt = datetime.fromtimestamp(earliest_1m, tz=timezone.utc)
        if start < earliest_1m_dt:
            # Find nearest standard interval for backfill
            for std_interval in _BACKFILL_PREFERENCE:
                result = await db.execute(
                    select(OHLCVData)
                    .where(
                        OHLCVData.ticker == ticker,
                        OHLCVData.interval == std_interval,
                        OHLCVData.date >= start,
                        OHLCVData.date < earliest_1m_dt,
                    )
                    .order_by(OHLCVData.date)
                )
                backfill_rows = result.scalars().all()
                if backfill_rows:
                    raw = _rows_to_bar_dicts(backfill_rows)
                    all_bars.extend(aggregate_candles(raw, interval))
                    break

    # Part B: Aggregate 1m data within the date range
    query_start = start
    if earliest_1m is not None:
        earliest_1m_dt = datetime.fromtimestamp(earliest_1m, tz=timezone.utc)
        if earliest_1m_dt > start:
            query_start = earliest_1m_dt

    result = await db.execute(
        select(OHLCVData)
        .where(
            OHLCVData.ticker == ticker,
            OHLCVData.interval == "1m",
            OHLCVData.date >= query_start,
        )
        .order_by(OHLCVData.date)
    )
    minute_rows = result.scalars().all()

    if minute_rows:
        minute_bars = _rows_to_bar_dicts(minute_rows)
        aggregated = aggregate_candles(minute_bars, interval)
        all_bars.extend(aggregated)

    # Sort by time and deduplicate
    all_bars.sort(key=lambda b: b["time"])
    seen_times: set[int] = set()
    unique_bars: list[dict] = []
    for b in all_bars:
        if b["time"] not in seen_times:
            seen_times.add(b["time"])
            unique_bars.append(b)

    if len(unique_bars) < 10:
        raise HTTPException(
            status_code=400,
            detail=f"Interval {interval!r} produces only {len(unique_bars)} candles "
            f"for period {period!r} (minimum 10 required)",
        )

    return OHLCVResponse(
        bars=_bar_dicts_to_response(unique_bars),
        data_transition_timestamp=transition_ts,
        last_updated=now_unix,
    )


@router.get("/{ticker}/indicators", response_model=list[IndicatorDataResponse])
async def get_indicators(
    ticker: str,
    period: str = "1y",
    interval: str = "1D",
    db: AsyncSession = Depends(get_db),
):
    """Standard intervals: serve pre-computed from indicator_data table.
    Custom intervals: aggregate OHLCV from 1m, compute indicators on the fly,
    generate per-indicator signals from the computed data.
    """
    # Validate interval format
    try:
        validate_interval(interval)
    except ValueError:
        raise HTTPException(status_code=400, detail=f"Invalid interval: {interval!r}")

    await _verify_index_exists(ticker, db)

    start = _period_start(period)

    if interval in STANDARD_INTERVALS:
        # Standard path: serve pre-computed indicator data
        result = await db.execute(
            select(IndicatorData)
            .where(
                IndicatorData.ticker == ticker,
                IndicatorData.interval == interval,
                IndicatorData.date >= start,
            )
            .order_by(IndicatorData.indicator_id, IndicatorData.date)
        )
        rows = result.scalars().all()

        grouped: dict[str, dict[str, list[dict[str, float]]]] = defaultdict(
            lambda: defaultdict(list)
        )
        for row in rows:
            grouped[row.indicator_id][row.series_key].append(
                {"time": float(_date_to_unix(row.date)), "value": row.value}
            )

        # Get stored signals
        signal_result = await db.execute(
            select(SignalData).where(
                SignalData.ticker == ticker,
                SignalData.indicator_id != "_aggregate",
            )
        )
        signal_rows = signal_result.scalars().all()
        signal_map = {s.indicator_id: s.signal for s in signal_rows}

        return [
            IndicatorDataResponse(
                id=indicator_id,
                series=dict(series),
                signal=signal_map.get(indicator_id, "hold"),
            )
            for indicator_id, series in grouped.items()
        ]

    # Custom interval path: aggregate 1m OHLCV, compute indicators on the fly
    result = await db.execute(
        select(OHLCVData)
        .where(
            OHLCVData.ticker == ticker,
            OHLCVData.interval == "1m",
            OHLCVData.date >= start,
        )
        .order_by(OHLCVData.date)
    )
    minute_rows = result.scalars().all()

    if not minute_rows:
        return []

    # Aggregate 1m bars to the requested interval
    minute_bars = _rows_to_bar_dicts(minute_rows)
    aggregated = aggregate_candles(minute_bars, interval)

    if not aggregated:
        return []

    # Build DataFrame for indicator calculation
    ohlcv_df = _bars_to_dataframe(aggregated)

    # Calculate indicators
    indicator_data = calculate_indicators(ohlcv_df)

    # Generate signals from computed indicators
    responses: list[IndicatorDataResponse] = []
    for indicator_id, series_data in indicator_data.items():
        # Skip indicators with no data points
        if all(len(points) == 0 for points in series_data.values()):
            continue
        signal = generate_signal(indicator_id, series_data, ohlcv_df)
        responses.append(
            IndicatorDataResponse(
                id=indicator_id,
                series=series_data,
                signal=signal,
            )
        )

    return responses


@router.get("/{ticker}/signal", response_model=SignalSummaryResponse)
async def get_signal(ticker: str, db: AsyncSession = Depends(get_db)):
    """Query signal_data for ticker. Build breakdown with indicator categories.
    Count buy/sell/hold for activeCount.
    """
    await _verify_index_exists(ticker, db)

    result = await db.execute(
        select(SignalData).where(SignalData.ticker == ticker)
    )
    rows = result.scalars().all()

    if not rows:
        raise HTTPException(status_code=404, detail=f"No signals found for '{ticker}'")

    # Separate aggregate (indicator_id="_aggregate") from per-indicator signals
    aggregate = "hold"
    breakdown: list[IndicatorMetaResponse] = []
    counts: dict[str, int] = {"buy": 0, "sell": 0, "hold": 0}

    for row in rows:
        if row.indicator_id == "_aggregate":
            aggregate = row.signal
        else:
            category = INDICATOR_CATEGORIES.get(row.indicator_id, "oscillator")
            breakdown.append(
                IndicatorMetaResponse(
                    id=row.indicator_id,
                    category=category,
                    signal=row.signal,
                )
            )
            signal_key = row.signal.lower()
            if signal_key in counts:
                counts[signal_key] += 1

    return SignalSummaryResponse(
        aggregate=aggregate,
        breakdown=breakdown,
        active_count=counts,
    )
