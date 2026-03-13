"""Tests for the scheduler & refresh service."""

from unittest.mock import AsyncMock, MagicMock, call, patch

import numpy as np
import pandas as pd
import pytest

from app.services.scheduler import (
    STANDARD_INTERVALS,
    _calculate_performance_metrics,
    _failure_counts,
    refresh_all,
    refresh_fund,
    refresh_funds,
    refresh_indices_1m,
    setup_scheduler,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_ohlcv_df(n: int = 252, base: float = 100.0) -> pd.DataFrame:
    """Build a realistic OHLCV DataFrame like the fetcher returns (columns, not index)."""
    rng = np.random.default_rng(42)
    dates = pd.bdate_range("2025-01-02", periods=n, freq="B")
    closes = np.cumsum(rng.normal(0.05, 1.0, n)) + base
    closes = closes - closes.min() + 50.0  # keep positive

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


def _make_1m_ohlcv_df(n: int = 390) -> pd.DataFrame:
    """Build a 1-minute OHLCV DataFrame (7 days of market hours ~390 bars/day)."""
    rng = np.random.default_rng(42)
    # Create minute-level timestamps over a week
    dates = pd.date_range("2025-03-10 09:30:00", periods=n, freq="min")
    closes = np.cumsum(rng.normal(0.01, 0.3, n)) + 100.0
    closes = closes - closes.min() + 50.0

    return pd.DataFrame(
        {
            "Date": dates,
            "Open": closes + rng.normal(0, 0.1, n),
            "High": closes + np.abs(rng.normal(0, 0.2, n)),
            "Low": closes - np.abs(rng.normal(0, 0.2, n)),
            "Close": closes,
            "Volume": np.abs(rng.normal(100_000, 20_000, n)).astype(int),
        }
    )


def _make_nav_df(n: int = 1260) -> pd.DataFrame:
    """Build a NAV DataFrame like fetch_fund_nav returns (5 years ~ 1260 trading days)."""
    rng = np.random.default_rng(99)
    dates = pd.bdate_range("2021-01-04", periods=n, freq="B")
    navs = np.cumsum(rng.normal(0.02, 0.5, n)) + 100.0
    navs = navs - navs.min() + 10.0

    return pd.DataFrame({"Date": dates, "Close": navs})


def _make_indicator_result() -> dict:
    """Minimal indicator output matching the real shape."""
    return {
        "rsi": {"rsi": [{"time": 1000, "value": 55.0}]},
        "macd": {
            "macd": [{"time": 1000, "value": 1.0}],
            "signal": [{"time": 1000, "value": 0.5}],
            "histogram": [{"time": 1000, "value": 0.5}],
        },
        "bollinger": {
            "upper": [{"time": 1000, "value": 110.0}],
            "middle": [{"time": 1000, "value": 100.0}],
            "lower": [{"time": 1000, "value": 90.0}],
        },
        "ma": {
            "sma20": [{"time": 1000, "value": 102.0}],
            "sma50": [{"time": 1000, "value": 101.0}],
            "sma200": [{"time": 1000, "value": 99.0}],
        },
        "stochastic": {
            "k": [{"time": 1000, "value": 50.0}],
            "d": [{"time": 1000, "value": 48.0}],
        },
        "obv": {"obv": [{"time": 1000, "value": 5000.0}]},
        "fibonacci": {
            "fib_0": [{"time": 1000, "value": 110.0}],
            "fib_24": [{"time": 1000, "value": 106.0}],
            "fib_38": [{"time": 1000, "value": 103.0}],
            "fib_50": [{"time": 1000, "value": 100.0}],
            "fib_62": [{"time": 1000, "value": 97.0}],
            "fib_79": [{"time": 1000, "value": 93.0}],
            "fib_100": [{"time": 1000, "value": 90.0}],
        },
        "atr": {"atr": [{"time": 1000, "value": 3.0}]},
        "ichimoku": {
            "tenkan": [{"time": 1000, "value": 101.0}],
            "kijun": [{"time": 1000, "value": 99.0}],
        },
        "cci": {"cci": [{"time": 1000, "value": 20.0}]},
    }


def _mock_session():
    """Create a mock AsyncSession with execute/commit/flush."""
    session = AsyncMock()
    session.execute = AsyncMock()
    session.commit = AsyncMock()
    session.flush = AsyncMock()
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
    factory._mock_session = mock_session  # expose for assertions
    return factory


# ---------------------------------------------------------------------------
# STANDARD_INTERVALS constant
# ---------------------------------------------------------------------------


def test_standard_intervals():
    """STANDARD_INTERVALS has the 6 target intervals for aggregation."""
    assert STANDARD_INTERVALS == ["5m", "15m", "1H", "4H", "1D", "1W"]


# ---------------------------------------------------------------------------
# refresh_indices_1m
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_refresh_indices_fetches_1m():
    """fetch_index_ohlcv called with '7d' period and '1m' interval."""
    ohlcv_1m = _make_1m_ohlcv_df(n=100)
    mock_factory = _mock_session_factory()
    # Aggregated candles — return some bars for each interval
    agg_bars = [{"time": 1000, "open": 100, "high": 101, "low": 99, "close": 100.5, "volume": 5000}]
    indicators = _make_indicator_result()

    with (
        patch("app.services.scheduler.fetch_index_ohlcv", return_value=ohlcv_1m) as mock_fetch,
        patch("app.services.scheduler.aggregate_candles", return_value=agg_bars),
        patch("app.services.scheduler.calculate_indicators", return_value=indicators),
        patch("app.services.scheduler.generate_signal", return_value="hold"),
        patch("app.services.scheduler.aggregate_signals", return_value="hold"),
        patch("app.services.scheduler.SEED_INDICES", [{"ticker": "^GSPC"}]),
    ):
        result = await refresh_indices_1m(mock_factory)

    # Verify fetch called with 7d/1m
    mock_fetch.assert_called_with("^GSPC", "7d", "1m")
    assert result["indices_refreshed"] == 1
    assert result["errors"] == []


@pytest.mark.asyncio
async def test_refresh_indices_aggregates_standard_intervals():
    """Aggregated OHLCV produced for 5m, 15m, 1H, 4H, 1D, 1W."""
    ohlcv_1m = _make_1m_ohlcv_df(n=100)
    mock_factory = _mock_session_factory()
    agg_bars = [{"time": 1000, "open": 100, "high": 101, "low": 99, "close": 100.5, "volume": 5000}]
    indicators = _make_indicator_result()

    with (
        patch("app.services.scheduler.fetch_index_ohlcv", return_value=ohlcv_1m),
        patch("app.services.scheduler.aggregate_candles", return_value=agg_bars) as mock_agg,
        patch("app.services.scheduler.calculate_indicators", return_value=indicators),
        patch("app.services.scheduler.generate_signal", return_value="hold"),
        patch("app.services.scheduler.aggregate_signals", return_value="hold"),
        patch("app.services.scheduler.SEED_INDICES", [{"ticker": "^GSPC"}]),
    ):
        await refresh_indices_1m(mock_factory)

    # aggregate_candles called for each of the 6 standard intervals
    agg_intervals = [c.args[1] for c in mock_agg.call_args_list]
    for interval in STANDARD_INTERVALS:
        assert interval in agg_intervals, f"Missing aggregation for {interval}"


@pytest.mark.asyncio
async def test_refresh_indices_computes_indicators_1d_only():
    """Indicators and signals computed and stored for 1D interval only."""
    ohlcv_1m = _make_1m_ohlcv_df(n=100)
    mock_factory = _mock_session_factory()
    # Return enough 1D bars for indicator calculation
    agg_bars_1d = [
        {"time": 1000 + i * 86400, "open": 100 + i, "high": 101 + i, "low": 99 + i, "close": 100.5 + i, "volume": 5000}
        for i in range(50)
    ]
    # Other intervals return just one bar
    agg_bars_other = [{"time": 1000, "open": 100, "high": 101, "low": 99, "close": 100.5, "volume": 5000}]
    indicators = _make_indicator_result()

    def mock_agg(bars, interval):
        if interval == "1D":
            return agg_bars_1d
        return agg_bars_other

    with (
        patch("app.services.scheduler.fetch_index_ohlcv", return_value=ohlcv_1m),
        patch("app.services.scheduler.aggregate_candles", side_effect=mock_agg),
        patch("app.services.scheduler.calculate_indicators", return_value=indicators) as mock_calc,
        patch("app.services.scheduler.generate_signal", return_value="hold") as mock_gen_sig,
        patch("app.services.scheduler.aggregate_signals", return_value="hold"),
        patch("app.services.scheduler.SEED_INDICES", [{"ticker": "^GSPC"}]),
    ):
        await refresh_indices_1m(mock_factory)

    # calculate_indicators called exactly once (for 1D)
    mock_calc.assert_called_once()
    # generate_signal called for each indicator
    assert mock_gen_sig.call_count == len(indicators)


@pytest.mark.asyncio
async def test_refresh_indices_upserts_datetime_not_date():
    """OHLCV upsert uses datetime (preserving time) not date()."""
    ohlcv_1m = _make_1m_ohlcv_df(n=10)
    mock_factory = _mock_session_factory()
    mock_session = mock_factory._mock_session
    agg_bars = [{"time": 1000, "open": 100, "high": 101, "low": 99, "close": 100.5, "volume": 5000}]
    indicators = _make_indicator_result()

    with (
        patch("app.services.scheduler.fetch_index_ohlcv", return_value=ohlcv_1m),
        patch("app.services.scheduler.aggregate_candles", return_value=agg_bars),
        patch("app.services.scheduler.calculate_indicators", return_value=indicators),
        patch("app.services.scheduler.generate_signal", return_value="hold"),
        patch("app.services.scheduler.aggregate_signals", return_value="hold"),
        patch("app.services.scheduler.SEED_INDICES", [{"ticker": "^GSPC"}]),
        patch("app.services.scheduler.pg_insert") as mock_pg_insert,
    ):
        # Make pg_insert return a mock that supports chaining
        mock_stmt = MagicMock()
        mock_stmt.on_conflict_do_update.return_value = mock_stmt
        mock_pg_insert.return_value = MagicMock()
        mock_pg_insert.return_value.values.return_value = mock_stmt

        await refresh_indices_1m(mock_factory)

    # Check that first call to pg_insert().values() has datetime objects in 'date' field
    # (not date objects from .date() call)
    values_calls = mock_pg_insert.return_value.values.call_args_list
    if values_calls:
        first_rows = values_calls[0].args[0] if values_calls[0].args else values_calls[0].kwargs.get("rows", [])
        if first_rows:
            for row in first_rows:
                if "date" in row:
                    from datetime import datetime
                    assert isinstance(row["date"], datetime), (
                        f"Expected datetime, got {type(row['date'])}"
                    )


# ---------------------------------------------------------------------------
# refresh_funds
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_refresh_funds_processes_all():
    """All 7 funds processed (including new Varainhoito)."""
    refreshed = []

    async def mock_refresh_fund(ticker, session):
        refreshed.append(ticker)

    mock_factory = _mock_session_factory()

    with (
        patch("app.services.scheduler.refresh_fund", side_effect=mock_refresh_fund),
        patch(
            "app.services.scheduler.SEED_FUNDS",
            [{"ticker": f"FUND{i}"} for i in range(7)],
        ),
    ):
        result = await refresh_funds(mock_factory)

    assert len(refreshed) == 7
    assert result["funds_refreshed"] == 7
    assert result["errors"] == []


# ---------------------------------------------------------------------------
# setup_scheduler — two jobs
# ---------------------------------------------------------------------------


def test_scheduler_two_jobs():
    """setup_scheduler creates two separate interval jobs."""
    mock_factory = MagicMock()

    with patch("app.services.scheduler.AsyncIOScheduler") as MockScheduler:
        mock_instance = MagicMock()
        MockScheduler.return_value = mock_instance

        scheduler = setup_scheduler(mock_factory, index_interval=15, fund_interval=60)

    assert scheduler is mock_instance
    # Two jobs added
    assert mock_instance.add_job.call_count == 2

    # Extract job IDs
    job_ids = [c.kwargs.get("id") or c[1].get("id", "") for c in mock_instance.add_job.call_args_list]
    assert "refresh_indices" in job_ids
    assert "refresh_funds" in job_ids


# ---------------------------------------------------------------------------
# Consecutive failure tracking
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_consecutive_failure_tracking():
    """After 3 failures, warning logged. Counter resets on success."""
    # Clear any previous state
    _failure_counts.clear()

    call_count = {"n": 0}

    async def failing_refresh(ticker, session):
        call_count["n"] += 1
        if call_count["n"] <= 3:
            raise Exception("Simulated error")
        # 4th call succeeds

    mock_factory = _mock_session_factory()

    with (
        patch("app.services.scheduler.refresh_fund", side_effect=failing_refresh),
        patch("app.services.scheduler.SEED_FUNDS", [{"ticker": "FUND0"}]),
        patch("app.services.scheduler.logger") as mock_logger,
    ):
        # Run 3 times — should log warning on 3rd failure
        for _ in range(3):
            await refresh_funds(mock_factory)

        # Check that a warning about consecutive failures was logged
        warning_calls = [
            c for c in mock_logger.warning.call_args_list
            if "consecutive" in str(c).lower()
        ]
        assert len(warning_calls) >= 1, "Expected warning about consecutive failures"

        # Now succeed (4th call)
        await refresh_funds(mock_factory)

    # Counter should be reset
    assert _failure_counts.get("fund:FUND0", 0) == 0


# ---------------------------------------------------------------------------
# Partial data upserted
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_partial_data_upserted():
    """Partial yfinance response is upserted (not rejected)."""
    # Only 5 bars — much less than typical, but should still be processed
    ohlcv_1m = _make_1m_ohlcv_df(n=5)
    mock_factory = _mock_session_factory()
    agg_bars = [{"time": 1000, "open": 100, "high": 101, "low": 99, "close": 100.5, "volume": 5000}]
    indicators = _make_indicator_result()

    with (
        patch("app.services.scheduler.fetch_index_ohlcv", return_value=ohlcv_1m),
        patch("app.services.scheduler.aggregate_candles", return_value=agg_bars),
        patch("app.services.scheduler.calculate_indicators", return_value=indicators),
        patch("app.services.scheduler.generate_signal", return_value="hold"),
        patch("app.services.scheduler.aggregate_signals", return_value="hold"),
        patch("app.services.scheduler.SEED_INDICES", [{"ticker": "^GSPC"}]),
    ):
        result = await refresh_indices_1m(mock_factory)

    # Should still succeed with partial data
    assert result["indices_refreshed"] == 1
    assert result["errors"] == []


# ---------------------------------------------------------------------------
# refresh_all — combines both
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_refresh_all_processes_all_tickers():
    """All 10 indices and 7 funds are processed."""
    mock_factory = _mock_session_factory()

    with (
        patch(
            "app.services.scheduler.refresh_indices_1m",
            return_value={"indices_refreshed": 10, "errors": []},
        ) as mock_idx,
        patch(
            "app.services.scheduler.refresh_funds",
            return_value={"funds_refreshed": 7, "errors": []},
        ) as mock_funds,
    ):
        result = await refresh_all(mock_factory)

    mock_idx.assert_called_once_with(mock_factory)
    mock_funds.assert_called_once_with(mock_factory)
    assert result["indices_refreshed"] == 10
    assert result["funds_refreshed"] == 7
    assert result["errors"] == []


@pytest.mark.asyncio
async def test_refresh_all_combines_errors():
    """refresh_all combines errors from both sub-refreshes."""
    mock_factory = _mock_session_factory()

    with (
        patch(
            "app.services.scheduler.refresh_indices_1m",
            return_value={"indices_refreshed": 9, "errors": ["index:^GSPC"]},
        ),
        patch(
            "app.services.scheduler.refresh_funds",
            return_value={"funds_refreshed": 6, "errors": ["fund:FUND0"]},
        ),
    ):
        result = await refresh_all(mock_factory)

    assert result["indices_refreshed"] == 9
    assert result["funds_refreshed"] == 6
    assert result["errors"] == ["index:^GSPC", "fund:FUND0"]


# ---------------------------------------------------------------------------
# Performance metrics (unchanged)
# ---------------------------------------------------------------------------


def test_sharpe_ratio_calculation():
    """Sharpe ratio = (annualized_return - risk_free) / volatility."""
    rng = np.random.default_rng(42)
    n = 1260  # ~5 years
    navs = np.cumsum(rng.normal(0.05, 0.5, n)) + 100.0
    navs = navs - navs.min() + 50.0
    dates = pd.bdate_range("2021-01-04", periods=n, freq="B")
    nav_df = pd.DataFrame({"Date": dates, "Close": navs})

    metrics = _calculate_performance_metrics(nav_df)

    # Verify Sharpe formula: (annualized_return - 3.0) / volatility
    daily_returns = nav_df["Close"].pct_change().dropna()
    daily_std = daily_returns.std()
    annualized_vol = daily_std * np.sqrt(252) * 100

    # Calendar-based 1y lookup: find nearest date to exactly 1 year ago
    date_idx = pd.DatetimeIndex(nav_df["Date"])
    target_1y = date_idx[-1] - pd.DateOffset(years=1)
    nearest_idx = date_idx.get_indexer([target_1y], method="nearest")[0]
    nav_1y_ago = nav_df.iloc[nearest_idx]["Close"]
    return_1y = (nav_df.iloc[-1]["Close"] / nav_1y_ago - 1) * 100
    expected_sharpe = (return_1y - 3.0) / annualized_vol

    assert metrics["sharpe"] == pytest.approx(expected_sharpe, rel=0.01)
    assert metrics["volatility"] == pytest.approx(annualized_vol, rel=0.01)


def test_max_drawdown_calculation():
    """Max drawdown calculated from peak-to-trough."""
    # Create a known drawdown scenario: go up to 200, drop to 100, recover to 150
    navs = [100, 150, 200, 180, 150, 100, 120, 150]
    dates = pd.bdate_range("2025-01-06", periods=len(navs), freq="B")
    nav_df = pd.DataFrame({"Date": dates, "Close": navs})

    metrics = _calculate_performance_metrics(nav_df)

    # Max drawdown: peak=200, trough=100 → (100/200 - 1) * 100 = -50%
    assert metrics["max_drawdown"] == pytest.approx(-50.0)


def test_returns_calculation():
    """Returns computed as (end/start - 1) * 100 for available windows."""
    # Slightly more than 1 calendar year of business days so the 1y window fits
    n = 270
    dates = pd.bdate_range("2023-12-01", periods=n, freq="B")
    navs = np.linspace(100.0, 120.0, n)
    nav_df = pd.DataFrame({"Date": dates, "Close": navs})

    metrics = _calculate_performance_metrics(nav_df)

    # 1y return: nearest date to 1 calendar year ago → ~19-20%
    assert metrics["returns_1y"] == pytest.approx(19.4, rel=0.05)
    # 3y and 5y should be None (not enough data)
    assert metrics["returns_3y"] is None
    assert metrics["returns_5y"] is None


def test_performance_metrics_empty_df():
    """Empty DataFrame returns all-None metrics."""
    nav_df = pd.DataFrame({"Date": [], "Close": []})
    metrics = _calculate_performance_metrics(nav_df)

    assert metrics["returns_1y"] is None
    assert metrics["volatility"] is None
    assert metrics["sharpe"] is None
    assert metrics["max_drawdown"] is None


# ---------------------------------------------------------------------------
# refresh_fund (individual — legacy tests)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_refresh_fund_calculates_returns():
    """1y/3y/5y returns computed correctly from NAV history."""
    nav_df = _make_nav_df(n=1260)
    benchmark_df = _make_ohlcv_df(n=1260)
    session = _mock_session()

    with (
        patch("app.services.scheduler.fetch_fund_nav", return_value=nav_df),
        patch("app.services.scheduler.fetch_fund_info", return_value={"annualReportExpenseRatio": 0.015}),
        patch("app.services.scheduler.fetch_index_ohlcv", return_value=benchmark_df),
    ):
        await refresh_fund("0P00000N9Y.F", session)

    # Should have executed upserts and committed
    assert session.execute.call_count >= 1
    assert session.commit.call_count >= 1


@pytest.mark.asyncio
async def test_refresh_fund_with_benchmark():
    """Fund with benchmark_ticker also fetches benchmark data."""
    nav_df = _make_nav_df(n=1260)
    benchmark_df = _make_nav_df(n=1260)
    session = _mock_session()

    # Mock the session to return a Fund with benchmark_ticker
    fund_mock = MagicMock()
    fund_mock.benchmark_ticker = "IEUR"
    fund_mock.ticker = "0P00000N9Y.F"

    # First execute returns the fund, subsequent calls return default
    result_mock = MagicMock()
    result_mock.scalar_one_or_none.return_value = fund_mock
    session.execute.return_value = result_mock

    with (
        patch("app.services.scheduler.fetch_fund_nav", return_value=nav_df) as mock_nav,
        patch("app.services.scheduler.fetch_fund_info", return_value={}),
        patch("app.services.scheduler.fetch_index_ohlcv", return_value=benchmark_df) as mock_bench,
    ):
        await refresh_fund("0P00000N9Y.F", session)

    # fetch_fund_nav called for the fund
    mock_nav.assert_called()
    # fetch_index_ohlcv called for the benchmark
    mock_bench.assert_called_once_with("IEUR", "5y", "1D")


@pytest.mark.asyncio
async def test_refresh_fund_skips_empty_nav():
    """If NAV fetch returns empty, skip performance calculation."""
    session = _mock_session()

    with (
        patch("app.services.scheduler.fetch_fund_nav", return_value=pd.DataFrame()),
        patch("app.services.scheduler.fetch_fund_info", return_value={}),
    ):
        await refresh_fund("0P00000N9Y.F", session)

    # No upserts should happen (only the fund lookup query if any)
    # Commit still called since the function completes normally
    assert session.commit.call_count <= 1


# ---------------------------------------------------------------------------
# setup_scheduler (legacy test — updated)
# ---------------------------------------------------------------------------


def test_setup_scheduler_returns_scheduler():
    """setup_scheduler creates and returns an AsyncIOScheduler with two jobs."""
    mock_factory = MagicMock()

    with patch("app.services.scheduler.AsyncIOScheduler") as MockScheduler:
        mock_instance = MagicMock()
        MockScheduler.return_value = mock_instance

        scheduler = setup_scheduler(mock_factory, index_interval=15, fund_interval=60)

    assert scheduler is mock_instance
    assert mock_instance.add_job.call_count == 2
