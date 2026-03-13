"""Backfill CLI — fetch historical OHLCV data for all indices at all intervals.

Usage:
    cd backend && uv run python -m app.cli.backfill
"""

import asyncio
import logging
import os
from datetime import UTC, datetime

from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.data.seed import SEED_INDICES
from app.models.market_data import OHLCVData
from app.services.fetcher import fetch_index_ohlcv

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Backfill interval definitions
# ---------------------------------------------------------------------------

# Intervals use app convention (uppercase H/D). The fetcher's INTERVAL_MAP
# translates to yfinance format (lowercase) via .get(interval, interval).
# Periods use raw yfinance values (not in PERIOD_MAP) — they fall through.
BACKFILL_INTERVALS: list[tuple[str, str]] = [
    ("7d", "1m"),       # 1m: ~7 days retention
    ("60d", "5m"),      # 5m: ~60 days retention
    ("60d", "15m"),     # 15m: ~60 days retention
    ("730d", "1H"),     # 1H: ~2 years retention
    ("max", "4H"),      # 4H+: full history
    ("max", "1D"),
    ("max", "1W"),
]

LOCK_FILE = "/tmp/investiq-backfill.lock"

# Delay between yfinance calls to avoid rate limiting
_CALL_DELAY_SECONDS = 2


# ---------------------------------------------------------------------------
# backfill_index
# ---------------------------------------------------------------------------


async def backfill_index(ticker: str, session: AsyncSession) -> dict:
    """Fetch all intervals for one index and upsert into ohlcv_data.

    Returns: {interval: row_count} summary.
    Uses fetcher.fetch_index_ohlcv() for each interval.
    Stores intervals using app convention (1H, 4H, 1D, 1W) in the DB.
    Delays 2s between yfinance calls.
    """
    summary: dict[str, int] = {}

    for i, (period, interval) in enumerate(BACKFILL_INTERVALS):
        if i > 0:
            await asyncio.sleep(_CALL_DELAY_SECONDS)

        logger.info("Backfilling %s %s (period=%s)...", ticker, interval, period)

        ohlcv_df = await fetch_index_ohlcv(ticker, period, interval)
        if ohlcv_df.empty:
            logger.warning("No data for %s %s (period=%s), skipping", ticker, interval, period)
            summary[interval] = 0
            continue

        # Build upsert rows — store full datetime, not .date()
        now = datetime.now(UTC)
        rows = []
        for _, row in ohlcv_df.iterrows():
            rows.append(
                {
                    "ticker": ticker,
                    "date": row["Date"],  # full datetime, preserves intraday timestamps
                    "interval": interval,  # app convention: 1H, 4H, 1D, 1W
                    "open": float(row["Open"]),
                    "high": float(row["High"]),
                    "low": float(row["Low"]),
                    "close": float(row["Close"]),
                    "volume": float(row.get("Volume", 0)),
                    "fetched_at": now,
                }
            )

        # Upsert in chunks (same pattern as scheduler.py)
        chunk_size = 1000
        for ci in range(0, len(rows), chunk_size):
            chunk = rows[ci : ci + chunk_size]
            stmt = pg_insert(OHLCVData).values(chunk)
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

        await session.commit()
        row_count = len(rows)
        summary[interval] = row_count
        logger.info("Backfilling %s %s... %d rows", ticker, interval, row_count)

    return summary


# ---------------------------------------------------------------------------
# precompute_indicators_after_backfill
# ---------------------------------------------------------------------------


async def precompute_indicators_after_backfill(session_factory) -> None:
    """For each index, for each standard interval (5m, 15m, 1H, 4H, 1D, 1W):
    aggregate stored OHLCV to that interval, compute indicators, store results.
    Only processes trailing 2 years of data (not full history).

    TODO: Implement full indicator precomputation pipeline.
    Currently a placeholder — the scheduler's refresh_index handles 1D indicators.
    """
    logger.info("Indicator precomputation after backfill — not yet implemented")


# ---------------------------------------------------------------------------
# backfill_all
# ---------------------------------------------------------------------------


async def backfill_all(session_factory) -> dict:
    """Backfill all 10 indices. Acquires lock file, runs sequentially.

    After all indices: triggers indicator pre-computation for standard intervals.
    Returns summary with per-index results.
    Raises RuntimeError if lock file exists (concurrent run prevention).
    """
    # Check lock
    if os.path.exists(LOCK_FILE):
        raise RuntimeError(
            f"Backfill lock file exists: {LOCK_FILE}. "
            "Another backfill may be running. Remove manually if stale."
        )

    # Acquire lock
    with open(LOCK_FILE, "w") as f:
        f.write(str(os.getpid()))

    try:
        summary: dict[str, dict[str, int]] = {}

        for idx_data in SEED_INDICES:
            ticker = idx_data["ticker"]
            try:
                async with session_factory() as session:
                    result = await backfill_index(ticker, session)
                summary[ticker] = result
                logger.info("Backfill %s: OK — %s", ticker, result)
            except Exception:
                logger.exception("Backfill %s: FAILED", ticker)
                summary[ticker] = {}

        # Post-backfill indicator computation
        await precompute_indicators_after_backfill(session_factory)

        total_rows = sum(sum(v.values()) for v in summary.values())
        logger.info(
            "Backfill complete: %d indices, %d total rows",
            len(summary),
            total_rows,
        )

        return summary

    finally:
        # Always clean up lock file
        os.remove(LOCK_FILE)


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )

    from app.core.database import async_session

    asyncio.run(backfill_all(async_session))
