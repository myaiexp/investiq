"""Tests for the backfill CLI module."""

import os
from unittest.mock import AsyncMock, MagicMock, patch

import numpy as np
import pandas as pd
import pytest

from app.cli.backfill import (
    BACKFILL_INTERVALS,
    LOCK_FILE,
    backfill_all,
    backfill_index,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_ohlcv_df(n: int = 50, base: float = 100.0) -> pd.DataFrame:
    """Build a realistic OHLCV DataFrame like the fetcher returns."""
    rng = np.random.default_rng(42)
    dates = pd.bdate_range("2025-01-02", periods=n, freq="B")
    closes = np.cumsum(rng.normal(0.05, 1.0, n)) + base
    closes = closes - closes.min() + 50.0

    return pd.DataFrame(
        {
            "Date": dates,
            "Open": closes + rng.normal(0, 0.3, n),
            "High": closes + np.abs(rng.normal(0, 0.5, n)),
            "Low": closes - np.abs(rng.normal(0, 0.5, n)),
            "Close": closes,
            "Volume": np.abs(rng.normal(1_000_000, 200_000, n)).astype(int),
        }
    )


def _mock_session():
    """Create a mock AsyncSession with execute/commit."""
    session = AsyncMock()
    session.execute = AsyncMock()
    session.commit = AsyncMock()
    return session


def _mock_session_factory():
    """Create a mock session factory that works as: async with factory() as session."""
    mock_session = _mock_session()

    class _FakeCtx:
        async def __aenter__(self):
            return mock_session

        async def __aexit__(self, *args):
            pass

    factory = MagicMock(side_effect=lambda: _FakeCtx())
    factory._mock_session = mock_session
    return factory


# ---------------------------------------------------------------------------
# backfill_index
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_backfill_index_fetches_all_intervals():
    """All 7 interval/period combos are fetched for one index."""
    ohlcv_df = _make_ohlcv_df()
    session = _mock_session()
    fetch_calls = []

    async def mock_fetch(ticker, period, interval):
        fetch_calls.append((ticker, period, interval))
        return ohlcv_df

    with (
        patch("app.cli.backfill.fetch_index_ohlcv", side_effect=mock_fetch),
        patch("app.cli.backfill.asyncio.sleep", new_callable=AsyncMock),
    ):
        result = await backfill_index("^GSPC", session)

    assert len(fetch_calls) == 7
    # All calls should be for the same ticker
    assert all(t == "^GSPC" for t, _, _ in fetch_calls)
    # Verify all period/interval combos from BACKFILL_INTERVALS
    fetched_combos = [(p, i) for _, p, i in fetch_calls]
    for period, interval in BACKFILL_INTERVALS:
        assert (period, interval) in fetched_combos
    # Result should have row counts per interval
    assert len(result) == 7


@pytest.mark.asyncio
async def test_backfill_index_upserts_data():
    """Fetched OHLCV rows are upserted (not duplicated on re-run)."""
    ohlcv_df = _make_ohlcv_df(n=10)
    session = _mock_session()

    with (
        patch("app.cli.backfill.fetch_index_ohlcv", return_value=ohlcv_df),
        patch("app.cli.backfill.asyncio.sleep", new_callable=AsyncMock),
    ):
        await backfill_index("^GSPC", session)

    # session.execute should have been called for upserts (at least once per interval)
    assert session.execute.call_count >= 7


@pytest.mark.asyncio
async def test_backfill_stores_app_convention_intervals():
    """Stored interval values use app convention: '1H' not '1h', '1D' not '1d'."""
    ohlcv_df = _make_ohlcv_df(n=5)
    session = _mock_session()

    # Capture the values passed to session.execute
    executed_stmts = []
    original_execute = session.execute

    async def capture_execute(stmt):
        executed_stmts.append(stmt)
        return await original_execute(stmt)

    session.execute = AsyncMock(side_effect=capture_execute)

    with (
        patch("app.cli.backfill.fetch_index_ohlcv", return_value=ohlcv_df),
        patch("app.cli.backfill.asyncio.sleep", new_callable=AsyncMock),
    ):
        result = await backfill_index("^GSPC", session)

    # The result keys should use app convention intervals
    for interval in result:
        assert interval in {"1m", "5m", "15m", "1H", "4H", "1D", "1W"}
    # Specifically check uppercase conventions
    assert "1H" in result
    assert "4H" in result
    assert "1D" in result
    assert "1W" in result
    # No lowercase yfinance variants
    assert "1h" not in result
    assert "4h" not in result
    assert "1d" not in result
    assert "1wk" not in result


# ---------------------------------------------------------------------------
# backfill_all
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_backfill_all_processes_all_indices():
    """All 10 indices are processed."""
    backfilled_tickers = []

    async def mock_backfill_index(ticker, session):
        backfilled_tickers.append(ticker)
        return {"1D": 50}

    mock_factory = _mock_session_factory()

    with (
        patch("app.cli.backfill.backfill_index", side_effect=mock_backfill_index),
        patch("app.cli.backfill.precompute_indicators_after_backfill", new_callable=AsyncMock),
        patch("app.cli.backfill.os.path.exists", return_value=False),
        patch("builtins.open", MagicMock()),
        patch("app.cli.backfill.os.remove"),
    ):
        result = await backfill_all(mock_factory)

    assert len(backfilled_tickers) == 10
    assert len(result) == 10


# ---------------------------------------------------------------------------
# Lock file
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_backfill_lock_prevents_concurrent():
    """Second backfill_all raises if lock file exists."""
    mock_factory = _mock_session_factory()

    with patch("app.cli.backfill.os.path.exists", return_value=True):
        with pytest.raises(RuntimeError, match="lock"):
            await backfill_all(mock_factory)


@pytest.mark.asyncio
async def test_backfill_lock_cleaned_up():
    """Lock file removed after successful completion."""
    async def mock_backfill_index(ticker, session):
        return {"1D": 50}

    mock_factory = _mock_session_factory()
    removed_files = []

    with (
        patch("app.cli.backfill.backfill_index", side_effect=mock_backfill_index),
        patch("app.cli.backfill.precompute_indicators_after_backfill", new_callable=AsyncMock),
        patch("app.cli.backfill.os.path.exists", return_value=False),
        patch("builtins.open", MagicMock()),
        patch("app.cli.backfill.os.remove", side_effect=lambda f: removed_files.append(f)),
    ):
        await backfill_all(mock_factory)

    assert LOCK_FILE in removed_files


@pytest.mark.asyncio
async def test_backfill_lock_cleaned_up_on_error():
    """Lock file removed even if backfill fails."""
    async def mock_backfill_index(ticker, session):
        raise Exception("yfinance exploded")

    mock_factory = _mock_session_factory()
    removed_files = []

    with (
        patch("app.cli.backfill.backfill_index", side_effect=mock_backfill_index),
        patch("app.cli.backfill.precompute_indicators_after_backfill", new_callable=AsyncMock),
        patch("app.cli.backfill.os.path.exists", return_value=False),
        patch("builtins.open", MagicMock()),
        patch("app.cli.backfill.os.remove", side_effect=lambda f: removed_files.append(f)),
    ):
        # backfill_all should not raise — it catches per-index errors
        await backfill_all(mock_factory)

    assert LOCK_FILE in removed_files
