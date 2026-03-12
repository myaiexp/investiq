"""Tests for the yfinance fetcher service."""

import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import pandas as pd
import pytest

from app.services.fetcher import (
    INTERVAL_MAP,
    PERIOD_MAP,
    fetch_fund_info,
    fetch_fund_nav,
    fetch_index_ohlcv,
)


# ---------------------------------------------------------------------------
# Period / interval mapping
# ---------------------------------------------------------------------------


def test_period_mapping():
    """Frontend period strings map correctly to yfinance params."""
    assert PERIOD_MAP == {
        "1m": "1mo",
        "3m": "3mo",
        "6m": "6mo",
        "1y": "1y",
        "5y": "5y",
    }


def test_interval_mapping():
    """Frontend interval strings map correctly to yfinance params."""
    assert INTERVAL_MAP == {
        "1m": "1m",
        "5m": "5m",
        "15m": "15m",
        "1H": "1h",
        "2H": "2h",
        "4H": "4h",
        "1D": "1d",
        "1W": "1wk",
    }


# ---------------------------------------------------------------------------
# Volume fill
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_missing_volume_filled():
    """DataFrame with NaN volume gets 0-filled."""
    # Build a fake DataFrame that yfinance.download would return —
    # timezone-aware DatetimeIndex, NaN in Volume column.
    dates = pd.date_range("2024-01-01", periods=3, freq="D", tz="UTC")
    df = pd.DataFrame(
        {
            "Open": [100.0, 101.0, 102.0],
            "High": [105.0, 106.0, 107.0],
            "Low": [99.0, 100.0, 101.0],
            "Close": [104.0, 105.0, 106.0],
            "Volume": [float("nan"), float("nan"), float("nan")],
        },
        index=dates,
    )
    df.index.name = "Date"

    with patch("app.services.fetcher.yf") as mock_yf:
        mock_yf.download.return_value = df

        result = await fetch_index_ohlcv("^GSPC", "1y", "1D")

    # Volume should be 0, not NaN
    assert (result["Volume"] == 0).all()


# ---------------------------------------------------------------------------
# Thread wrapping
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_fetch_wraps_in_thread():
    """yfinance calls run in executor, not blocking the event loop."""
    dates = pd.date_range("2024-01-01", periods=2, freq="D", tz="UTC")
    df = pd.DataFrame(
        {
            "Open": [100.0, 101.0],
            "High": [105.0, 106.0],
            "Low": [99.0, 100.0],
            "Close": [104.0, 105.0],
            "Volume": [1000, 2000],
        },
        index=dates,
    )
    df.index.name = "Date"

    with (
        patch("app.services.fetcher.yf") as mock_yf,
        patch("app.services.fetcher.asyncio.to_thread", wraps=asyncio.to_thread) as mock_to_thread,
    ):
        mock_yf.download.return_value = df

        await fetch_index_ohlcv("^GSPC", "1y", "1D")

    # to_thread must have been called (proving we're not blocking)
    mock_to_thread.assert_called_once()


# ---------------------------------------------------------------------------
# Timezone normalization
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_timezone_stripped_from_dates():
    """Timezone-aware dates are normalized to UTC then stripped."""
    dates = pd.date_range("2024-01-01", periods=2, freq="D", tz="US/Eastern")
    df = pd.DataFrame(
        {
            "Open": [100.0, 101.0],
            "High": [105.0, 106.0],
            "Low": [99.0, 100.0],
            "Close": [104.0, 105.0],
            "Volume": [1000, 2000],
        },
        index=dates,
    )
    df.index.name = "Date"

    with patch("app.services.fetcher.yf") as mock_yf:
        mock_yf.download.return_value = df

        result = await fetch_index_ohlcv("^GSPC", "1y", "1D")

    # Date column should be timezone-naive
    assert result["Date"].dt.tz is None


# ---------------------------------------------------------------------------
# Fund NAV
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_fetch_fund_nav_returns_date_close():
    """fetch_fund_nav returns a DataFrame with only Date and Close columns."""
    dates = pd.date_range("2024-01-01", periods=3, freq="D", tz="UTC")
    df = pd.DataFrame(
        {
            "Open": [10.0, 10.5, 11.0],
            "High": [10.5, 11.0, 11.5],
            "Low": [9.5, 10.0, 10.5],
            "Close": [10.2, 10.8, 11.1],
            "Volume": [0, 0, 0],
        },
        index=dates,
    )
    df.index.name = "Date"

    with patch("app.services.fetcher.yf") as mock_yf:
        mock_yf.download.return_value = df

        result = await fetch_fund_nav("0P00000BUF.HE", "5y")

    assert list(result.columns) == ["Date", "Close"]
    assert len(result) == 3


# ---------------------------------------------------------------------------
# Fund info
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_fetch_fund_info_returns_dict():
    """fetch_fund_info returns the .info dict from yfinance Ticker."""
    fake_info = {
        "shortName": "Test Fund",
        "annualReportExpenseRatio": 0.015,
        "totalAssets": 1_000_000,
    }

    with patch("app.services.fetcher.yf") as mock_yf:
        mock_ticker = MagicMock()
        mock_ticker.info = fake_info
        mock_yf.Ticker.return_value = mock_ticker

        result = await fetch_fund_info("0P00000BUF.HE")

    assert result == fake_info


# ---------------------------------------------------------------------------
# Error handling
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_fetch_index_ohlcv_returns_empty_on_failure():
    """On yfinance failure, returns empty DataFrame and logs warning."""
    with patch("app.services.fetcher.yf") as mock_yf:
        mock_yf.download.side_effect = Exception("Network error")

        result = await fetch_index_ohlcv("^GSPC", "1y", "1D")

    assert isinstance(result, pd.DataFrame)
    assert result.empty


@pytest.mark.asyncio
async def test_fetch_fund_info_returns_empty_on_failure():
    """On yfinance failure, returns empty dict and logs warning."""
    with patch("app.services.fetcher.yf") as mock_yf:
        mock_yf.Ticker.side_effect = Exception("Network error")

        result = await fetch_fund_info("INVALID")

    assert result == {}
