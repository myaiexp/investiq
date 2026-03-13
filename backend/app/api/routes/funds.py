"""Fund API routes — list funds, NAV history, and performance metrics."""

import calendar
from datetime import date, timedelta

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.models.market_data import Fund, FundNAV, FundPerformance
from app.schemas.funds import (
    FundMetaResponse,
    FundNAVPointResponse,
    FundPerformanceResponse,
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
