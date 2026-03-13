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
from app.services.aggregator import aggregate_candles
from app.services.fetcher import fetch_fund_info, fetch_fund_nav, fetch_index_ohlcv
from app.services.indicators import (
    aggregate_signals,
    calculate_indicators,
    generate_signal,
)

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

STANDARD_INTERVALS = ["5m", "15m", "1H", "4H", "1D", "1W"]

# Legacy reference — kept for potential future use
PERIOD_INTERVAL_MAP: dict[str, list[str]] = {
    "1m": ["1m", "5m", "15m", "1H", "2H", "4H", "1D"],
    "3m": ["15m", "1H", "2H", "4H", "1D"],
    "6m": ["1H", "4H", "1D", "1W"],
    "1y": ["4H", "1D", "1W"],
    "5y": ["1D", "1W"],
}

# ---------------------------------------------------------------------------
# Stale data / failure tracking (in-memory)
# ---------------------------------------------------------------------------

_failure_counts: dict[str, int] = {}
_FAILURE_WARN_THRESHOLD = 3


def _record_failure(key: str) -> None:
    """Increment consecutive failure count and log warning at threshold."""
    _failure_counts[key] = _failure_counts.get(key, 0) + 1
    count = _failure_counts[key]
    if count >= _FAILURE_WARN_THRESHOLD:
        logger.warning(
            "%s has %d consecutive failures — data may be stale", key, count
        )


def _record_success(key: str) -> None:
    """Reset consecutive failure counter on success."""
    _failure_counts.pop(key, None)


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

    # Build a DatetimeIndex from the Date column for calendar-based lookups
    dates = pd.DatetimeIndex(nav_df["Date"])
    end_date = dates[-1]
    end_nav = navs[-1]

    # Returns: (nav_end / nav_start - 1) * 100 for 1y/3y/5y windows
    # Use calendar years (DateOffset) and find the nearest available trading date
    windows = {"returns_1y": 1, "returns_3y": 3, "returns_5y": 5}
    for key, years in windows.items():
        target_date = end_date - pd.DateOffset(years=years)
        if target_date < dates[0]:
            # Not enough history for this window
            continue
        # Find the index of the date closest to target_date
        idx = dates.get_indexer([target_date], method="nearest")[0]
        start_nav = navs[idx]
        if start_nav > 0:
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
# refresh_indices_1m — new 1m-based index refresh
# ---------------------------------------------------------------------------


async def _refresh_single_index(ticker: str, session: AsyncSession) -> None:
    """Fetch 1m OHLCV for one index, aggregate, compute indicators/signals.

    Steps:
      1. fetch_index_ohlcv(ticker, "7d", "1m")
      2. Upsert 1m OHLCV rows (datetime in date column, not date())
      3. Aggregate to STANDARD_INTERVALS using aggregator.aggregate_candles()
      4. Upsert aggregated OHLCV rows
      5. Compute indicators for 1D interval only, store in indicator_data
      6. Generate signals per indicator + aggregate for 1D, store in signal_data
      7. Update Index row (price, daily_change, signal from latest 1D data)
    """
    logger.info("Refreshing index %s (1m)", ticker)

    # Step 1: Fetch 1m OHLCV (7-day window)
    ohlcv_df = await fetch_index_ohlcv(ticker, "7d", "1m")
    if ohlcv_df.empty:
        logger.warning("No 1m OHLCV data for %s, skipping", ticker)
        return

    now = datetime.now(UTC)

    # Step 2: Upsert raw 1m OHLCV rows (preserve full datetime)
    ohlcv_1m_rows = []
    for _, row in ohlcv_df.iterrows():
        dt = row["Date"].to_pydatetime() if hasattr(row["Date"], "to_pydatetime") else row["Date"]
        ohlcv_1m_rows.append(
            {
                "ticker": ticker,
                "date": dt,
                "interval": "1m",
                "open": float(row["Open"]),
                "high": float(row["High"]),
                "low": float(row["Low"]),
                "close": float(row["Close"]),
                "volume": float(row.get("Volume", 0)),
                "fetched_at": now,
            }
        )

    if ohlcv_1m_rows:
        stmt = pg_insert(OHLCVData).values(ohlcv_1m_rows)
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

    # Step 3: Convert 1m data to bar dicts for aggregator
    bars_1m = []
    for _, row in ohlcv_df.iterrows():
        ts = row["Date"]
        if hasattr(ts, "timestamp"):
            unix_s = int(ts.timestamp())
        else:
            unix_s = int(pd.Timestamp(ts).timestamp())
        bars_1m.append(
            {
                "time": unix_s,
                "open": float(row["Open"]),
                "high": float(row["High"]),
                "low": float(row["Low"]),
                "close": float(row["Close"]),
                "volume": int(row.get("Volume", 0)),
            }
        )

    # Aggregate to each standard interval and upsert
    aggregated_by_interval: dict[str, list[dict]] = {}
    for interval in STANDARD_INTERVALS:
        agg_bars = aggregate_candles(bars_1m, interval)
        aggregated_by_interval[interval] = agg_bars

        # Build OHLCV rows for this interval
        if agg_bars:
            interval_rows = []
            for bar in agg_bars:
                bar_dt = datetime.fromtimestamp(bar["time"], tz=UTC)
                interval_rows.append(
                    {
                        "ticker": ticker,
                        "date": bar_dt,
                        "interval": interval,
                        "open": float(bar["open"]),
                        "high": float(bar["high"]),
                        "low": float(bar["low"]),
                        "close": float(bar["close"]),
                        "volume": float(bar["volume"]),
                        "fetched_at": now,
                    }
                )

            stmt = pg_insert(OHLCVData).values(interval_rows)
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

    # Step 5: Compute indicators for 1D only
    daily_bars = aggregated_by_interval.get("1D", [])
    if not daily_bars:
        logger.warning("No 1D aggregated bars for %s, skipping indicators", ticker)
        # Still update price from raw 1m data
        latest_close = float(ohlcv_df.iloc[-1]["Close"])
        await session.execute(
            update(Index).where(Index.ticker == ticker).values(price=latest_close)
        )
        await session.commit()
        return

    # Build DataFrame for indicator calculation (needs DatetimeIndex)
    calc_df = pd.DataFrame(daily_bars)
    calc_df["Date"] = pd.to_datetime(calc_df["time"], unit="s")
    calc_df = calc_df.rename(
        columns={"open": "Open", "high": "High", "low": "Low", "close": "Close", "volume": "Volume"}
    )
    calc_df.set_index("Date", inplace=True)

    indicators = calculate_indicators(calc_df)

    # Step 5b: Upsert indicator_data rows (1D only)
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
                        "date": ts.to_pydatetime(),
                        "series_key": series_key,
                        "value": float(pt["value"]),
                        "fetched_at": now,
                    }
                )

    if indicator_rows:
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

    # Step 6: Generate signals per indicator, aggregate, upsert
    signals: dict[str, str] = {}
    for ind_id, series_data in indicators.items():
        sig = generate_signal(ind_id, series_data, calc_df)
        signals[ind_id] = sig

    aggregate = aggregate_signals(signals)

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
    signal_rows.append(
        {
            "ticker": ticker,
            "indicator_id": "_aggregate",
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

    # Step 7: Update index row from latest 1D bar
    latest_bar = daily_bars[-1]
    latest_close = float(latest_bar["close"])
    daily_change = None
    if len(daily_bars) >= 2:
        prev_close = float(daily_bars[-2]["close"])
        if prev_close != 0:
            daily_change = round((latest_close / prev_close - 1) * 100, 4)

    await session.execute(
        update(Index)
        .where(Index.ticker == ticker)
        .values(price=latest_close, daily_change=daily_change, signal=aggregate)
    )

    await session.commit()
    logger.info("Index %s refreshed (1m→agg): price=%.2f, signal=%s", ticker, latest_close, aggregate)


async def refresh_indices_1m(session_factory) -> dict:
    """Fetch 1m data for all indices (7-day window), aggregate, compute indicators.

    For each index:
      1. fetch_index_ohlcv(ticker, "7d", "1m")
      2. Upsert 1m OHLCV rows (datetime in date column, not date())
      3. Aggregate to STANDARD_INTERVALS using aggregator.aggregate_candles()
      4. Upsert aggregated OHLCV rows (store with app-convention interval names)
      5. Compute indicators for 1D interval only, store in indicator_data
      6. Generate signals per indicator + aggregate for 1D, store in signal_data
      7. Update Index row (price, daily_change, signal from latest 1D data)

    Returns: {indices_refreshed: int, errors: list[str]}
    """
    logger.info("Starting index refresh (1m)")
    indices_ok = 0
    errors: list[str] = []

    for idx_data in SEED_INDICES:
        ticker = idx_data["ticker"]
        key = f"index:{ticker}"
        try:
            async with session_factory() as session:
                await _refresh_single_index(ticker, session)
            indices_ok += 1
            _record_success(key)
            logger.info("Index %s: OK", ticker)
        except Exception:
            logger.exception("Index %s: FAILED", ticker)
            _record_failure(key)
            errors.append(key)

    logger.info("Index refresh complete: %d OK, %d errors", indices_ok, len(errors))
    return {"indices_refreshed": indices_ok, "errors": errors}


# ---------------------------------------------------------------------------
# refresh_fund (single fund — unchanged logic)
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
# refresh_funds — all funds
# ---------------------------------------------------------------------------


async def refresh_funds(session_factory) -> dict:
    """Fetch daily NAV for all funds + benchmarks.

    Returns: {funds_refreshed: int, errors: list[str]}
    """
    logger.info("Starting fund refresh")
    funds_ok = 0
    errors: list[str] = []

    for fund_data in SEED_FUNDS:
        ticker = fund_data["ticker"]
        key = f"fund:{ticker}"
        try:
            async with session_factory() as session:
                await refresh_fund(ticker, session)
            funds_ok += 1
            _record_success(key)
            logger.info("Fund %s: OK", ticker)
        except Exception:
            logger.exception("Fund %s: FAILED", ticker)
            _record_failure(key)
            errors.append(key)

    logger.info("Fund refresh complete: %d OK, %d errors", funds_ok, len(errors))
    return {"funds_refreshed": funds_ok, "errors": errors}


# ---------------------------------------------------------------------------
# refresh_all — combined
# ---------------------------------------------------------------------------


async def refresh_all(session_factory) -> dict:
    """Run both refresh_indices_1m and refresh_funds.

    Returns combined summary:
        {"indices_refreshed": int, "funds_refreshed": int, "errors": list[str]}
    """
    logger.info("Starting full refresh")

    idx_result = await refresh_indices_1m(session_factory)
    fund_result = await refresh_funds(session_factory)

    combined = {
        "indices_refreshed": idx_result["indices_refreshed"],
        "funds_refreshed": fund_result["funds_refreshed"],
        "errors": idx_result["errors"] + fund_result["errors"],
    }

    logger.info(
        "Refresh complete: %d indices, %d funds, %d errors",
        combined["indices_refreshed"],
        combined["funds_refreshed"],
        len(combined["errors"]),
    )
    return combined


# ---------------------------------------------------------------------------
# Scheduler setup
# ---------------------------------------------------------------------------


def setup_scheduler(
    session_factory,
    index_interval: int = 15,
    fund_interval: int = 60,
) -> AsyncIOScheduler:
    """Create and configure APScheduler with two jobs.

    Args:
        session_factory: Async session factory.
        index_interval: Minutes between index refreshes (1m OHLCV fetch).
        fund_interval: Minutes between fund refreshes (daily NAV).

    Returns:
        Configured scheduler (caller starts it).
    """
    scheduler = AsyncIOScheduler()

    async def _refresh_indices_job():
        await refresh_indices_1m(session_factory)

    async def _refresh_funds_job():
        await refresh_funds(session_factory)

    scheduler.add_job(
        _refresh_indices_job,
        trigger=IntervalTrigger(minutes=index_interval),
        id="refresh_indices",
        name="Refresh index OHLCV (1m)",
        replace_existing=True,
    )

    scheduler.add_job(
        _refresh_funds_job,
        trigger=IntervalTrigger(minutes=fund_interval),
        id="refresh_funds",
        name="Refresh fund NAV data",
        replace_existing=True,
    )

    return scheduler
