"""Fund API routes — list funds, NAV history, performance metrics, and indicators."""

import calendar
from datetime import date, datetime, timedelta, timezone

import pandas as pd
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.constants import PERIOD_DAYS
from app.core.database import get_db
from app.data.seed import INDICATOR_CATEGORIES
from app.models.market_data import Fund, FundNAV, FundPerformance
from app.schemas.funds import (
    FundMetaResponse,
    FundNAVPointResponse,
    FundPerformanceResponse,
)
from app.schemas.indices import (
    IndicatorDataResponse,
    IndicatorMetaResponse,
    SignalSummaryResponse,
)
from app.services.indicators import (
    aggregate_signals,
    calculate_indicators,
    generate_signal,
)

router = APIRouter(prefix="/funds", tags=["funds"])

# Known data quality issues — temporary until better data sources are added
FUND_DATA_NOTES: dict[str, str] = {
    "0P0001HOZS.F": "Shows C share class NAV, official default class NAV differs slightly",
}

FUND_PERF_NOTES: dict[str, dict[str, str]] = {
    "_all": {
        "ter": "Unavailable from current data source",
        "5y": "Insufficient historical data",
    },
}

# Funds with broken benchmark data
FUND_BENCHMARK_NOTES: dict[str, str] = {}

# Indicators applicable to fund NAV data (no volume-dependent or H/L-dependent indicators)
FUND_INDICATORS: set[str] = {"rsi", "macd", "ma", "cci", "bollinger"}



def _period_start(period: str) -> date:
    """Convert a period string to a start date (today minus N days)."""
    days = PERIOD_DAYS.get(period, 365)
    return date.today() - timedelta(days=days)


def _date_to_unix(d: date) -> int:
    """Convert a date to unix timestamp (seconds since epoch, midnight UTC)."""
    return int(calendar.timegm(d.timetuple()))


async def _verify_fund_exists(ticker: str, db: AsyncSession) -> None:
    """Raise 404 if ticker is not in the funds table."""
    result = await db.execute(select(Fund).where(Fund.ticker == ticker))
    if result.scalars().first() is None:
        raise HTTPException(status_code=404, detail=f"Fund '{ticker}' not found")


@router.get("/", response_model=list[FundMetaResponse])
async def list_funds(db: AsyncSession = Depends(get_db)):
    """SELECT * FROM funds ORDER BY fund_type, name."""
    result = await db.execute(select(Fund).order_by(Fund.fund_type, Fund.name))
    rows = result.scalars().all()
    return [
        FundMetaResponse(
            name=row.name,
            ticker=row.ticker,
            isin=row.isin,
            fund_type=row.fund_type,
            benchmark_ticker=row.benchmark_ticker,
            benchmark_name=row.benchmark_name or "",
            nav=row.nav or 0.0,
            daily_change=row.daily_change or 0.0,
            return_1y=row.return_1y or 0.0,
            data_note=FUND_DATA_NOTES.get(row.ticker),
        )
        for row in rows
    ]


@router.get("/{ticker}/performance", response_model=FundPerformanceResponse)
async def get_fund_performance(ticker: str, db: AsyncSession = Depends(get_db)):
    """Query fund_performance for ticker. Structure returns/benchmarkReturns as nested dicts."""
    await _verify_fund_exists(ticker, db)

    result = await db.execute(
        select(FundPerformance).where(FundPerformance.ticker == ticker)
    )
    perf = result.scalars().first()
    if perf is None:
        raise HTTPException(status_code=404, detail=f"No performance data for fund '{ticker}'")

    notes: dict[str, str] = {}
    notes.update(FUND_PERF_NOTES.get("_all", {}))
    notes.update(FUND_PERF_NOTES.get(ticker, {}))
    if ticker in FUND_BENCHMARK_NOTES:
        notes["benchmark"] = FUND_BENCHMARK_NOTES[ticker]

    return FundPerformanceResponse(
        returns={
            "1y": perf.returns_1y or 0.0,
            "3y": perf.returns_3y or 0.0,
            "5y": perf.returns_5y or 0.0,
        },
        benchmark_returns={
            "1y": perf.benchmark_returns_1y or 0.0,
            "3y": perf.benchmark_returns_3y or 0.0,
            "5y": perf.benchmark_returns_5y or 0.0,
        },
        volatility=perf.volatility or 0.0,
        sharpe=perf.sharpe or 0.0,
        max_drawdown=perf.max_drawdown or 0.0,
        ter=perf.ter or 0.0,
        data_notes=notes or None,
    )


@router.get("/{ticker}/nav", response_model=list[FundNAVPointResponse])
async def get_fund_nav(
    ticker: str,
    period: str = "1y",
    db: AsyncSession = Depends(get_db),
):
    """Query fund_nav filtered by ticker + date range. Convert date to unix timestamp."""
    await _verify_fund_exists(ticker, db)

    start = _period_start(period)
    result = await db.execute(
        select(FundNAV)
        .where(
            FundNAV.ticker == ticker,
            FundNAV.date >= start,
        )
        .order_by(FundNAV.date)
    )
    rows = result.scalars().all()
    return [
        FundNAVPointResponse(
            time=_date_to_unix(row.date),
            value=row.nav,
        )
        for row in rows
    ]


def _build_nav_ohlcv_df(nav_rows: list) -> pd.DataFrame:
    """Build proxy OHLCV DataFrame from FundNAV rows.

    Converts date → UTC midnight datetime. O=H=L=C=NAV, Volume=0.
    Returns DataFrame with DatetimeIndex and columns: Open, High, Low, Close, Volume.
    """
    records = []
    for row in nav_rows:
        # FundNAV.date is Date type — convert to UTC midnight datetime
        dt = datetime.combine(row.date, datetime.min.time(), tzinfo=timezone.utc)
        records.append({
            "datetime": dt,
            "Open": row.nav,
            "High": row.nav,
            "Low": row.nav,
            "Close": row.nav,
            "Volume": 0.0,
        })

    df = pd.DataFrame(records)
    df["datetime"] = pd.to_datetime(df["datetime"], utc=True)
    df = df.set_index("datetime").sort_index()
    return df


@router.get("/{ticker}/indicators", response_model=list[IndicatorDataResponse])
async def get_fund_indicators(
    ticker: str,
    period: str = "1y",
    db: AsyncSession = Depends(get_db),
):
    """Compute indicators on-the-fly from fund NAV data (proxy OHLCV)."""
    await _verify_fund_exists(ticker, db)

    start = _period_start(period)
    result = await db.execute(
        select(FundNAV)
        .where(FundNAV.ticker == ticker, FundNAV.date >= start)
        .order_by(FundNAV.date)
    )
    rows = result.scalars().all()
    if not rows:
        return []

    df = _build_nav_ohlcv_df(rows)
    all_indicators = calculate_indicators(df)

    responses: list[IndicatorDataResponse] = []
    for indicator_id, series_data in all_indicators.items():
        if indicator_id not in FUND_INDICATORS:
            continue
        if all(len(pts) == 0 for pts in series_data.values()):
            continue
        signal = generate_signal(indicator_id, series_data, df)
        responses.append(
            IndicatorDataResponse(id=indicator_id, series=series_data, signal=signal)
        )

    return responses


@router.get("/{ticker}/signal", response_model=SignalSummaryResponse)
async def get_fund_signal(ticker: str, db: AsyncSession = Depends(get_db)):
    """Compute aggregate signal on-the-fly from fund NAV data (full history)."""
    await _verify_fund_exists(ticker, db)

    result = await db.execute(
        select(FundNAV)
        .where(FundNAV.ticker == ticker)
        .order_by(FundNAV.date)
    )
    rows = result.scalars().all()
    if not rows:
        raise HTTPException(status_code=404, detail=f"No NAV data for fund '{ticker}'")

    df = _build_nav_ohlcv_df(rows)
    all_indicators = calculate_indicators(df)

    signals: dict[str, str] = {}
    breakdown: list[IndicatorMetaResponse] = []

    for indicator_id in FUND_INDICATORS:
        if indicator_id not in all_indicators:
            continue
        series_data = all_indicators[indicator_id]
        if all(len(pts) == 0 for pts in series_data.values()):
            continue
        sig = generate_signal(indicator_id, series_data, df)
        signals[indicator_id] = sig
        category = INDICATOR_CATEGORIES.get(indicator_id, "oscillator")
        breakdown.append(
            IndicatorMetaResponse(id=indicator_id, category=category, signal=sig)
        )

    aggregate = aggregate_signals(signals)
    counts: dict[str, int] = {"buy": 0, "sell": 0, "hold": 0}
    for sig in signals.values():
        key = sig.lower()
        if key in counts:
            counts[key] += 1

    return SignalSummaryResponse(
        aggregate=aggregate, breakdown=breakdown, active_count=counts
    )
