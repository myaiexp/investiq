"""Index API routes — list indices, OHLCV data, indicators, and signals."""

import calendar
from collections import defaultdict
from datetime import date, timedelta

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
    SignalSummaryResponse,
)

router = APIRouter(prefix="/indices", tags=["indices"])

# Period string → number of days
PERIOD_DAYS: dict[str, int] = {
    "1m": 30,
    "3m": 90,
    "6m": 180,
    "1y": 365,
    "5y": 1825,
}


def _period_start(period: str) -> date:
    """Convert a period string to a start date (today minus N days)."""
    days = PERIOD_DAYS.get(period, 365)
    return date.today() - timedelta(days=days)


def _date_to_unix(d: date) -> int:
    """Convert a date to unix timestamp (seconds since epoch, midnight UTC)."""
    return int(calendar.timegm(d.timetuple()))


async def _verify_index_exists(ticker: str, db: AsyncSession) -> None:
    """Raise 404 if ticker is not in the indices table."""
    result = await db.execute(select(Index).where(Index.ticker == ticker))
    if result.scalars().first() is None:
        raise HTTPException(status_code=404, detail=f"Index '{ticker}' not found")


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
        )
        for row in rows
    ]


@router.get("/{ticker}/ohlcv", response_model=list[OHLCVBarResponse])
async def get_ohlcv(
    ticker: str,
    period: str = "1y",
    interval: str = "1D",
    db: AsyncSession = Depends(get_db),
):
    """Query ohlcv_data filtered by ticker + interval + date range (derived from period).
    Convert date to unix timestamp for 'time' field.
    """
    await _verify_index_exists(ticker, db)

    start = _period_start(period)
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
    return [
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


@router.get("/{ticker}/indicators", response_model=list[IndicatorDataResponse])
async def get_indicators(
    ticker: str,
    period: str = "1y",
    interval: str = "1D",
    db: AsyncSession = Depends(get_db),
):
    """Query indicator_data filtered by ticker + interval + date range.
    Group rows by indicator_id, nest by series_key.
    """
    await _verify_index_exists(ticker, db)

    start = _period_start(period)
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

    # Group by indicator_id
    grouped: dict[str, dict[str, list[dict[str, float]]]] = defaultdict(lambda: defaultdict(list))
    for row in rows:
        grouped[row.indicator_id][row.series_key].append(
            {"time": float(_date_to_unix(row.date)), "value": row.value}
        )

    # Get signal per indicator (if available)
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
