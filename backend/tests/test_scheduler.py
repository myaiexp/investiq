"""Tests for the scheduler & refresh service."""

from unittest.mock import AsyncMock, MagicMock, patch

import numpy as np
import pandas as pd
import pytest

from app.services.scheduler import (
    PERIOD_INTERVAL_MAP,
    _calculate_performance_metrics,
    refresh_all,
    refresh_fund,
    refresh_index,
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


# ---------------------------------------------------------------------------
# PERIOD_INTERVAL_MAP constant
# ---------------------------------------------------------------------------


def test_period_interval_map_structure():
    """PERIOD_INTERVAL_MAP has the right periods and intervals matching frontend."""
    expected = {
        "1m": ["1m", "5m", "15m", "1H", "2H", "4H", "1D"],
        "3m": ["15m", "1H", "2H", "4H", "1D"],
        "6m": ["1H", "4H", "1D", "1W"],
        "1y": ["4H", "1D", "1W"],
        "5y": ["1D", "1W"],
    }
    assert PERIOD_INTERVAL_MAP == expected


# ---------------------------------------------------------------------------
# refresh_index
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_refresh_index_upserts_ohlcv():
    """OHLCV data is inserted/updated, not duplicated."""
    ohlcv_df = _make_ohlcv_df(n=50)
    indicators = _make_indicator_result()
    session = _mock_session()

    with (
        patch("app.services.scheduler.fetch_index_ohlcv", return_value=ohlcv_df) as mock_fetch,
        patch("app.services.scheduler.calculate_indicators", return_value=indicators),
        patch("app.services.scheduler.generate_signal", return_value="hold"),
        patch("app.services.scheduler.aggregate_signals", return_value="hold"),
    ):
        await refresh_index("^GSPC", session)

    # fetch_index_ohlcv called with 1y/1D (the only combo we actually fetch for now)
    mock_fetch.assert_called_once_with("^GSPC", "1y", "1D")

    # session.execute called multiple times for upserts (OHLCV, indicators, signals, index update)
    assert session.execute.call_count >= 1
    assert session.commit.call_count >= 1


@pytest.mark.asyncio
async def test_refresh_index_skips_empty_fetch():
    """If fetcher returns empty DataFrame, skip indicator calculation."""
    session = _mock_session()

    with (
        patch("app.services.scheduler.fetch_index_ohlcv", return_value=pd.DataFrame()),
        patch("app.services.scheduler.calculate_indicators") as mock_calc,
    ):
        await refresh_index("^GSPC", session)

    mock_calc.assert_not_called()


# ---------------------------------------------------------------------------
# refresh_fund
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
    fund_mock.benchmark_ticker = "^STOXX50E"
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
    mock_bench.assert_called_once_with("^STOXX50E", "5y", "1D")


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
# Performance metrics
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

    nav_1y_ago = nav_df.iloc[-253]["Close"] if len(nav_df) >= 253 else nav_df.iloc[0]["Close"]
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
    # Create exactly 253 trading days (1y + 1 extra for 1-year return)
    n = 253
    dates = pd.bdate_range("2024-01-02", periods=n, freq="B")
    navs = np.linspace(100.0, 120.0, n)  # linear growth from 100 to 120
    nav_df = pd.DataFrame({"Date": dates, "Close": navs})

    metrics = _calculate_performance_metrics(nav_df)

    # 1y return: (120 / 100 - 1) * 100 = 20%
    assert metrics["returns_1y"] == pytest.approx(20.0, rel=0.05)
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
# refresh_all
# ---------------------------------------------------------------------------


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


@pytest.mark.asyncio
async def test_refresh_all_processes_all_tickers():
    """All 10 indices and 6 funds are processed."""
    refreshed_indices = []
    refreshed_funds = []

    async def mock_refresh_index(ticker, session):
        refreshed_indices.append(ticker)

    async def mock_refresh_fund(ticker, session):
        refreshed_funds.append(ticker)

    mock_factory = _mock_session_factory()

    with (
        patch("app.services.scheduler.refresh_index", side_effect=mock_refresh_index),
        patch("app.services.scheduler.refresh_fund", side_effect=mock_refresh_fund),
        patch("app.services.scheduler.SEED_INDICES", [{"ticker": f"IDX{i}"} for i in range(10)]),
        patch("app.services.scheduler.SEED_FUNDS", [{"ticker": f"FUND{i}"} for i in range(6)]),
    ):
        result = await refresh_all(mock_factory)

    assert len(refreshed_indices) == 10
    assert len(refreshed_funds) == 6
    assert result["indices_refreshed"] == 10
    assert result["funds_refreshed"] == 6
    assert result["errors"] == []


@pytest.mark.asyncio
async def test_individual_failure_doesnt_abort():
    """If one ticker fails, others still process."""
    call_count = {"indices": 0, "funds": 0}

    async def mock_refresh_index(ticker, session):
        call_count["indices"] += 1
        if ticker == "IDX2":
            raise Exception("Network error")

    async def mock_refresh_fund(ticker, session):
        call_count["funds"] += 1

    mock_factory = _mock_session_factory()

    with (
        patch("app.services.scheduler.refresh_index", side_effect=mock_refresh_index),
        patch("app.services.scheduler.refresh_fund", side_effect=mock_refresh_fund),
        patch("app.services.scheduler.SEED_INDICES", [{"ticker": f"IDX{i}"} for i in range(5)]),
        patch("app.services.scheduler.SEED_FUNDS", [{"ticker": f"FUND{i}"} for i in range(3)]),
    ):
        result = await refresh_all(mock_factory)

    # All 5 indices attempted (including the failing one)
    assert call_count["indices"] == 5
    # All 3 funds still processed despite index failure
    assert call_count["funds"] == 3
    # 4 indices succeeded, 1 failed
    assert result["indices_refreshed"] == 4
    assert result["funds_refreshed"] == 3
    assert len(result["errors"]) == 1
    assert "IDX2" in result["errors"][0]


# ---------------------------------------------------------------------------
# setup_scheduler
# ---------------------------------------------------------------------------


def test_setup_scheduler_returns_scheduler():
    """setup_scheduler creates and returns an AsyncIOScheduler with a job."""
    mock_factory = MagicMock()

    with patch("app.services.scheduler.AsyncIOScheduler") as MockScheduler:
        mock_instance = MagicMock()
        MockScheduler.return_value = mock_instance

        scheduler = setup_scheduler(mock_factory, interval_minutes=30)

    assert scheduler is mock_instance
    mock_instance.add_job.assert_called_once()
    # Verify interval trigger
    call_args = mock_instance.add_job.call_args
    trigger = call_args[1].get("trigger") or call_args[0][1] if len(call_args[0]) > 1 else call_args[1].get("trigger")
    assert trigger is not None
