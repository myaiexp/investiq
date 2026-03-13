"""Fetcher service — wraps yfinance for async OHLCV and fund data retrieval."""

import asyncio
import logging

import pandas as pd
import yfinance as yf

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Period / interval mappings (frontend strings → yfinance params)
# ---------------------------------------------------------------------------

PERIOD_MAP: dict[str, str] = {
    "1m": "1mo",
    "3m": "3mo",
    "6m": "6mo",
    "1y": "1y",
    "5y": "5y",
}

INTERVAL_MAP: dict[str, str] = {
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
# Internal helpers
# ---------------------------------------------------------------------------


def _normalize_dates(df: pd.DataFrame) -> pd.DataFrame:
    """Convert timezone-aware DatetimeIndex to UTC then strip timezone."""
    if df.index.tz is not None:
        df.index = df.index.tz_convert("UTC").tz_localize(None)
    return df


def _flatten_columns(df: pd.DataFrame) -> pd.DataFrame:
    """Flatten MultiIndex columns from yfinance (e.g. ('Open', '^GSPC') → 'Open')."""
    if isinstance(df.columns, pd.MultiIndex):
        df.columns = df.columns.get_level_values(0)
    return df


def _download_sync(ticker: str, period: str, interval: str) -> pd.DataFrame:
    """Synchronous yfinance download — meant to be called via to_thread."""
    df = yf.download(ticker, period=period, interval=interval, progress=False)
    return _flatten_columns(df)


def _ticker_info_sync(ticker: str) -> dict:
    """Synchronous yfinance Ticker.info — meant to be called via to_thread."""
    return yf.Ticker(ticker).info


# ---------------------------------------------------------------------------
# Public async API
# ---------------------------------------------------------------------------


async def fetch_index_ohlcv(ticker: str, period: str, interval: str) -> pd.DataFrame:
    """Fetch OHLCV data from yfinance.

    Returns DataFrame with columns: Date, Open, High, Low, Close, Volume.
    Runs yfinance in a thread executor (it's sync/blocking).
    """
    yf_period = PERIOD_MAP.get(period, period)
    yf_interval = INTERVAL_MAP.get(interval, interval)

    try:
        df = await asyncio.to_thread(_download_sync, ticker, yf_period, yf_interval)
    except Exception:
        logger.warning("Failed to fetch OHLCV for %s (period=%s, interval=%s)", ticker, period, interval, exc_info=True)
        return pd.DataFrame()

    if df.empty:
        return df

    # Normalize dates
    df = _normalize_dates(df)

    # Fill missing volume with 0
    if "Volume" in df.columns:
        df["Volume"] = df["Volume"].fillna(0).astype(int)

    # Move Date from index to column
    df = df.reset_index()

    # yfinance uses "Datetime" for intraday data, "Date" for daily — normalize
    if "Datetime" in df.columns and "Date" not in df.columns:
        df = df.rename(columns={"Datetime": "Date"})

    # Keep only the columns we need
    cols = ["Date", "Open", "High", "Low", "Close", "Volume"]
    df = df[[c for c in cols if c in df.columns]]

    return df


async def fetch_fund_nav(ticker: str, period: str = "5y") -> pd.DataFrame:
    """Fetch fund NAV history.

    Returns DataFrame with Date, Close columns.
    """
    yf_period = PERIOD_MAP.get(period, period)

    try:
        df = await asyncio.to_thread(_download_sync, ticker, yf_period, "1d")
    except Exception:
        logger.warning("Failed to fetch NAV for %s (period=%s)", ticker, period, exc_info=True)
        return pd.DataFrame()

    if df.empty:
        return df

    # Normalize dates
    df = _normalize_dates(df)

    # Move Date from index to column, keep only Date + Close
    df = df.reset_index()
    df = df[["Date", "Close"]]

    return df


async def fetch_fund_info(ticker: str) -> dict:
    """Fetch fund metadata from yfinance .info dict.

    Returns available fields (TER, etc.) or empty dict on failure.
    """
    try:
        info = await asyncio.to_thread(_ticker_info_sync, ticker)
    except Exception:
        logger.warning("Failed to fetch info for %s", ticker, exc_info=True)
        return {}

    return info
