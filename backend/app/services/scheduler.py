"""Scheduler & refresh service.

Periodically fetches market data via yfinance, computes indicators and signals,
and upserts results into the database.
"""

import logging
from datetime import UTC, datetime

import numpy as np
import pandas as pd
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.interval import IntervalTrigger
from sqlalchemy import update
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.data.seed import SEED_FUNDS, SEED_INDICES
from app.models.market_data import (
    Fund,
    FundNAV,
    FundPerformance,
    Index,
    IndicatorData,
    OHLCVData,
    SignalData,
)
from app.services.fetcher import fetch_fund_info, fetch_fund_nav, fetch_index_ohlcv
from app.services.indicators import (
    aggregate_signals,
    calculate_indicators,
    generate_signal,
)

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Period / interval mapping (matches frontend)
# ---------------------------------------------------------------------------

PERIOD_INTERVAL_MAP: dict[str, list[str]] = {
    "1m": ["1m", "5m", "15m", "1H", "2H", "4H", "1D"],
    "3m": ["15m", "1H", "2H", "4H", "1D"],
    "6m": ["1H", "4H", "1D", "1W"],
    "1y": ["4H", "1D", "1W"],
    "5y": ["1D", "1W"],
}


# ---------------------------------------------------------------------------
# Performance metrics
# ---------------------------------------------------------------------------


def _calculate_performance_metrics(nav_df: pd.DataFrame) -> dict:
    """Calculate fund performance metrics from a NAV DataFrame.

    Args:
        nav_df: DataFrame with Date and Close columns.

    Returns:
        Dict with returns_1y/3y/5y, volatility, sharpe, max_drawdown.
    """
    result = {
        "returns_1y": None,
        "returns_3y": None,
        "returns_5y": None,
        "volatility": None,
        "sharpe": None,
        "max_drawdown": None,
    }

    if nav_df.empty or len(nav_df) < 2:
        return result

    close_series = nav_df["Close"]
    # Flatten if MultiIndex columns (e.g., from yfinance)
    if isinstance(close_series, pd.DataFrame):
        close_series = close_series.iloc[:, 0]
    navs = close_series.values.astype(float)
    n = len(navs)

    # Returns: (nav_end / nav_start - 1) * 100 for 1y/3y/5y windows
    # ~252 trading days per year
    windows = {"returns_1y": 252, "returns_3y": 756, "returns_5y": 1260}
    for key, days in windows.items():
        if n > days:
            start_nav = navs[-(days + 1)]
            end_nav = navs[-1]
            result[key] = (end_nav / start_nav - 1) * 100

    # Volatility: annualized daily std
    daily_returns = close_series.pct_change().dropna()
    if len(daily_returns) > 1:
        daily_std = daily_returns.std()
        annualized_vol = float(daily_std * np.sqrt(252) * 100)
        result["volatility"] = annualized_vol

        # Sharpe: (annualized_return - 3.0) / volatility using 1y return
        if result["returns_1y"] is not None and annualized_vol > 0:
            result["sharpe"] = float((result["returns_1y"] - 3.0) / annualized_vol)

    # Max drawdown: min((nav / cummax - 1)) * 100
    cum_max = np.maximum.accumulate(navs)
    drawdowns = (navs / cum_max - 1) * 100
    result["max_drawdown"] = float(np.min(drawdowns))

    return result


# ---------------------------------------------------------------------------
# refresh_index
# ---------------------------------------------------------------------------


async def refresh_index(ticker: str, session: AsyncSession) -> None:
    """Fetch OHLCV for 1y/1D, compute indicators, store signals.

    Only fetches the 1y/1D combination for now (to limit API calls).
    The full PERIOD_INTERVAL_MAP is defined for future use.

    Steps:
      1. fetch_index_ohlcv(ticker, "1y", "1D")
      2. Upsert OHLCV rows into ohlcv_data
      3. calculate_indicators(ohlcv_df)
      4. Upsert indicator_data rows
      5. Generate per-indicator signals, aggregate, upsert signal_data
      6. Update index row: price, daily_change, signal
    """
    logger.info("Refreshing index %s", ticker)

    # Step 1: Fetch OHLCV
    ohlcv_df = await fetch_index_ohlcv(ticker, "1y", "1D")
    if ohlcv_df.empty:
        logger.warning("No OHLCV data for %s, skipping", ticker)
        return

    # Step 2: Upsert OHLCV rows
    now = datetime.now(UTC)
    ohlcv_rows = []
    for _, row in ohlcv_df.iterrows():
        ohlcv_rows.append(
            {
                "ticker": ticker,
                "date": row["Date"].date() if hasattr(row["Date"], "date") else row["Date"],
                "interval": "1D",
                "open": float(row["Open"]),
                "high": float(row["High"]),
                "low": float(row["Low"]),
                "close": float(row["Close"]),
                "volume": float(row.get("Volume", 0)),
                "fetched_at": now,
            }
        )

    if ohlcv_rows:
        stmt = pg_insert(OHLCVData).values(ohlcv_rows)
        stmt = stmt.on_conflict_do_update(
            index_elements=["ticker", "date", "interval"],
            set_={
                "open": stmt.excluded.open,
                "high": stmt.excluded.high,
                "low": stmt.excluded.low,
                "close": stmt.excluded.close,
                "volume": stmt.excluded.volume,
                "fetched_at": stmt.excluded.fetched_at,
            },
        )
        await session.execute(stmt)

    # Step 3: Calculate indicators (needs DatetimeIndex)
    calc_df = ohlcv_df.copy()
    calc_df["Date"] = pd.to_datetime(calc_df["Date"])
    calc_df.set_index("Date", inplace=True)

    indicators = calculate_indicators(calc_df)

    # Step 4: Upsert indicator_data rows
    indicator_rows = []
    for ind_id, series_dict in indicators.items():
        for series_key, points in series_dict.items():
            for pt in points:
                ts = pd.Timestamp(pt["time"], unit="s")
                indicator_rows.append(
                    {
                        "ticker": ticker,
                        "indicator_id": ind_id,
                        "interval": "1D",
                        "date": ts.date(),
                        "series_key": series_key,
                        "value": float(pt["value"]),
                        "fetched_at": now,
                    }
                )

    if indicator_rows:
        # Batch in chunks to avoid overly large statements
        chunk_size = 1000
        for i in range(0, len(indicator_rows), chunk_size):
            chunk = indicator_rows[i : i + chunk_size]
            stmt = pg_insert(IndicatorData).values(chunk)
            stmt = stmt.on_conflict_do_update(
                index_elements=["ticker", "indicator_id", "interval", "date", "series_key"],
                set_={
                    "value": stmt.excluded.value,
                    "fetched_at": stmt.excluded.fetched_at,
                },
            )
            await session.execute(stmt)

    # Step 5: Generate signals per indicator, aggregate, upsert
    signals: dict[str, str] = {}
    for ind_id, series_data in indicators.items():
        sig = generate_signal(ind_id, series_data, calc_df)
        signals[ind_id] = sig

    aggregate = aggregate_signals(signals)

    # Upsert per-indicator signals
    signal_rows = []
    for ind_id, sig in signals.items():
        signal_rows.append(
            {
                "ticker": ticker,
                "indicator_id": ind_id,
                "signal": sig,
                "computed_at": now,
            }
        )
    # Aggregate signal (indicator_id=None)
    signal_rows.append(
        {
            "ticker": ticker,
            "indicator_id": None,
            "signal": aggregate,
            "computed_at": now,
        }
    )

    for row in signal_rows:
        stmt = pg_insert(SignalData).values(row)
        stmt = stmt.on_conflict_do_update(
            index_elements=["ticker", "indicator_id"],
            set_={
                "signal": stmt.excluded.signal,
                "computed_at": stmt.excluded.computed_at,
            },
        )
        await session.execute(stmt)

    # Step 6: Update index row
    latest_close = float(ohlcv_df.iloc[-1]["Close"])
    daily_change = None
    if len(ohlcv_df) >= 2:
        prev_close = float(ohlcv_df.iloc[-2]["Close"])
        if prev_close != 0:
            daily_change = round((latest_close / prev_close - 1) * 100, 4)

    await session.execute(
        update(Index)
        .where(Index.ticker == ticker)
        .values(price=latest_close, daily_change=daily_change, signal=aggregate)
    )

    await session.commit()
    logger.info("Index %s refreshed: price=%.2f, signal=%s", ticker, latest_close, aggregate)


# ---------------------------------------------------------------------------
# refresh_fund
# ---------------------------------------------------------------------------


async def refresh_fund(ticker: str, session: AsyncSession) -> None:
    """Fetch NAV history, fund info, compute performance metrics.

    Steps:
      1. fetch_fund_nav(ticker, "5y")
      2. Upsert fund_nav rows
      3. fetch_fund_info(ticker) for TER
      4. Calculate performance metrics
      5. Upsert fund_performance row
      6. Update fund row: nav, daily_change, return_1y
      7. If fund has benchmark_ticker, fetch benchmark and compute relative returns
    """
    logger.info("Refreshing fund %s", ticker)

    # Step 1: Fetch NAV
    nav_df = await fetch_fund_nav(ticker, "5y")
    if nav_df.empty:
        logger.warning("No NAV data for %s, skipping", ticker)
        return

    # Step 2: Upsert fund_nav rows
    now = datetime.now(UTC)
    nav_rows = []
    for _, row in nav_df.iterrows():
        nav_rows.append(
            {
                "ticker": ticker,
                "date": row["Date"].date() if hasattr(row["Date"], "date") else row["Date"],
                "nav": float(row["Close"]),
                "fetched_at": now,
            }
        )

    if nav_rows:
        # Batch in chunks
        chunk_size = 1000
        for i in range(0, len(nav_rows), chunk_size):
            chunk = nav_rows[i : i + chunk_size]
            stmt = pg_insert(FundNAV).values(chunk)
            stmt = stmt.on_conflict_do_update(
                index_elements=["ticker", "date"],
                set_={
                    "nav": stmt.excluded.nav,
                    "fetched_at": stmt.excluded.fetched_at,
                },
            )
            await session.execute(stmt)

    # Step 3: Fetch fund info for TER
    info = await fetch_fund_info(ticker)
    ter = info.get("annualReportExpenseRatio")
    if ter is not None:
        ter = float(ter) * 100  # Convert to percentage

    # Step 4: Calculate performance metrics
    metrics = _calculate_performance_metrics(nav_df)

    # Step 5: Upsert fund_performance
    perf_row = {
        "ticker": ticker,
        "returns_1y": metrics["returns_1y"],
        "returns_3y": metrics["returns_3y"],
        "returns_5y": metrics["returns_5y"],
        "volatility": metrics["volatility"],
        "sharpe": metrics["sharpe"],
        "max_drawdown": metrics["max_drawdown"],
        "ter": ter,
        "computed_at": now,
    }

    # Check for benchmark — look up in SEED_FUNDS
    benchmark_ticker = None
    for fund_data in SEED_FUNDS:
        if fund_data["ticker"] == ticker:
            benchmark_ticker = fund_data.get("benchmark_ticker")
            break

    benchmark_returns = {"benchmark_returns_1y": None, "benchmark_returns_3y": None, "benchmark_returns_5y": None}

    if benchmark_ticker:
        # Fetch benchmark data
        bench_df = await fetch_index_ohlcv(benchmark_ticker, "5y", "1D")
        if not bench_df.empty:
            # Rename Close for metrics calculation
            bench_nav_df = bench_df[["Date", "Close"]].copy()
            bench_metrics = _calculate_performance_metrics(bench_nav_df)
            benchmark_returns["benchmark_returns_1y"] = bench_metrics["returns_1y"]
            benchmark_returns["benchmark_returns_3y"] = bench_metrics["returns_3y"]
            benchmark_returns["benchmark_returns_5y"] = bench_metrics["returns_5y"]

    perf_row.update(benchmark_returns)

    stmt = pg_insert(FundPerformance).values(perf_row)
    stmt = stmt.on_conflict_do_update(
        index_elements=["ticker"],
        set_={k: stmt.excluded[k] for k in perf_row if k != "ticker"},
    )
    await session.execute(stmt)

    # Step 6: Update fund row
    latest_nav = float(nav_df.iloc[-1]["Close"])
    daily_change = None
    if len(nav_df) >= 2:
        prev_nav = float(nav_df.iloc[-2]["Close"])
        if prev_nav != 0:
            daily_change = round((latest_nav / prev_nav - 1) * 100, 4)

    await session.execute(
        update(Fund)
        .where(Fund.ticker == ticker)
        .values(
            nav=latest_nav,
            daily_change=daily_change,
            return_1y=metrics["returns_1y"],
        )
    )

    await session.commit()
    logger.info("Fund %s refreshed: nav=%.4f, return_1y=%s", ticker, latest_nav, metrics["returns_1y"])


# ---------------------------------------------------------------------------
# refresh_all
# ---------------------------------------------------------------------------


async def refresh_all(session_factory) -> dict:
    """Main refresh job. Iterates all indices and funds.

    Returns:
        {"indices_refreshed": int, "funds_refreshed": int, "errors": list[str]}
    """
    logger.info("Starting full refresh")
    indices_ok = 0
    funds_ok = 0
    errors: list[str] = []

    # Refresh indices
    for idx_data in SEED_INDICES:
        ticker = idx_data["ticker"]
        try:
            async with session_factory() as session:
                await refresh_index(ticker, session)
            indices_ok += 1
            logger.info("Index %s: OK", ticker)
        except Exception:
            logger.exception("Index %s: FAILED", ticker)
            errors.append(f"index:{ticker}")

    # Refresh funds
    for fund_data in SEED_FUNDS:
        ticker = fund_data["ticker"]
        try:
            async with session_factory() as session:
                await refresh_fund(ticker, session)
            funds_ok += 1
            logger.info("Fund %s: OK", ticker)
        except Exception:
            logger.exception("Fund %s: FAILED", ticker)
            errors.append(f"fund:{ticker}")

    summary = {
        "indices_refreshed": indices_ok,
        "funds_refreshed": funds_ok,
        "errors": errors,
    }
    logger.info(
        "Refresh complete: %d indices, %d funds, %d errors",
        indices_ok,
        funds_ok,
        len(errors),
    )
    return summary


# ---------------------------------------------------------------------------
# Scheduler setup
# ---------------------------------------------------------------------------


def setup_scheduler(session_factory, interval_minutes: int = 60):
    """Create and configure APScheduler. Returns scheduler (caller starts it)."""
    scheduler = AsyncIOScheduler()

    async def _refresh_job():
        await refresh_all(session_factory)

    scheduler.add_job(
        _refresh_job,
        trigger=IntervalTrigger(minutes=interval_minutes),
        id="refresh_all",
        name="Refresh all market data",
        replace_existing=True,
    )

    return scheduler
