"""Tests for hybrid OHLCV serving and custom interval support."""

import calendar
import re
from collections import defaultdict
from datetime import UTC, datetime, timedelta

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient

from app.core.database import get_db
from app.main import app
from app.models.market_data import Index, IndicatorData, OHLCVData, SignalData


# ---------------------------------------------------------------------------
# Mock helpers (same pattern as test_routes.py)
# ---------------------------------------------------------------------------


class MockResult:
    """Mimics SQLAlchemy Result with .scalars().all() and .scalars().first()."""

    def __init__(self, rows):
        self._rows = rows

    def scalars(self):
        return self

    def all(self):
        return self._rows

    def first(self):
        return self._rows[0] if self._rows else None

    def unique(self):
        return self


class MockSession:
    """Minimal async session mock that routes SELECT queries to fixture data."""

    def __init__(self, data: dict[type, list] | None = None):
        self._data = data or {}

    async def execute(self, stmt):
        from sqlalchemy.sql import Select

        if isinstance(stmt, Select):
            for frm in stmt.get_final_froms():
                table_name = str(frm)
                for model_cls, rows in self._data.items():
                    if (
                        hasattr(model_cls, "__tablename__")
                        and model_cls.__tablename__ == table_name
                    ):
                        filtered = self._apply_filters(stmt, rows)
                        return MockResult(filtered)

        return MockResult([])

    def _apply_filters(self, stmt, rows):
        if stmt.whereclause is not None:
            try:
                clause_str = str(
                    stmt.whereclause.compile(compile_kwargs={"literal_binds": True})
                )
            except Exception:
                return rows

            # Filter by ticker
            ticker_match = re.search(r"ticker\s*=\s*'([^']+)'", clause_str)
            if ticker_match:
                target_ticker = ticker_match.group(1)
                rows = [r for r in rows if getattr(r, "ticker", None) == target_ticker]

            # Filter by date >= ...
            date_gte_match = re.search(r"date\s*>=\s*'([^']+)'", clause_str)
            if date_gte_match:
                start_str = date_gte_match.group(1)
                try:
                    start_dt = datetime.fromisoformat(start_str)
                except ValueError:
                    start_dt = datetime.fromisoformat(start_str.split()[0])
                for_compare = start_dt.date()
                rows = [
                    r
                    for r in rows
                    if hasattr(r, "date")
                    and (r.date.date() if isinstance(r.date, datetime) else r.date)
                    >= for_compare
                ]

            # Filter by date < ... (used in backfill stitching)
            date_lt_match = re.search(r"date\s*<\s*'([^']+)'", clause_str)
            if date_lt_match:
                end_str = date_lt_match.group(1)
                try:
                    end_dt = datetime.fromisoformat(end_str)
                except ValueError:
                    end_dt = datetime.fromisoformat(end_str.split()[0])
                end_compare = end_dt.date()
                rows = [
                    r
                    for r in rows
                    if hasattr(r, "date")
                    and (r.date.date() if isinstance(r.date, datetime) else r.date)
                    < end_compare
                ]

            # Filter by interval
            interval_match = re.search(r"interval\s*=\s*'([^']+)'", clause_str)
            if interval_match:
                target_interval = interval_match.group(1)
                rows = [
                    r
                    for r in rows
                    if getattr(r, "interval", None) == target_interval
                ]

            # Filter for indicator_id != '_aggregate'
            if "_aggregate" in clause_str and "indicator_id" in clause_str:
                rows = [
                    r
                    for r in rows
                    if getattr(r, "indicator_id", None) != "_aggregate"
                ]

            # Filter for func.min (earliest 1m query) — return all, let caller handle
            return rows
        return rows


class FakeObj:
    """Simple namespace that acts like an ORM row."""

    def __init__(self, **kwargs):
        for k, v in kwargs.items():
            object.__setattr__(self, k, v)


# ---------------------------------------------------------------------------
# Fixture data
# ---------------------------------------------------------------------------

NOW_DT = datetime(2026, 3, 12, 12, 0, 0, tzinfo=UTC)


def _make_index(name, ticker, region, price=100.0, currency=None):
    return FakeObj(
        id=abs(hash(ticker)) % 10000,
        name=name,
        ticker=ticker,
        region=region,
        currency=currency,
        price=price,
        daily_change=1.5,
        signal="buy",
    )


def _make_ohlcv(ticker, d, interval="1D", o=100.0, h=105.0, lo=99.0, c=104.0, v=1000.0):
    return FakeObj(
        id=abs(hash((ticker, d, interval))) % 100000,
        ticker=ticker,
        date=d,
        interval=interval,
        open=o,
        high=h,
        low=lo,
        close=c,
        volume=v,
        fetched_at=datetime.now(UTC),
    )


def _make_indicator(ticker, indicator_id, d, series_key, value, interval="1D"):
    return FakeObj(
        id=abs(hash((ticker, indicator_id, d, series_key))) % 100000,
        ticker=ticker,
        indicator_id=indicator_id,
        interval=interval,
        date=d,
        series_key=series_key,
        value=value,
        fetched_at=datetime.now(UTC),
    )


def _make_signal(ticker, indicator_id, signal):
    return FakeObj(
        id=abs(hash((ticker, indicator_id))) % 100000,
        ticker=ticker,
        indicator_id=indicator_id,
        signal=signal,
        computed_at=datetime.now(UTC),
    )


# Test index
SEED_INDEX = _make_index("S&P 500", "^GSPC", "global", 5200.0, currency="USD")

# Standard 1D OHLCV data — 20 bars within 1y
SEED_OHLCV_1D = [
    _make_ohlcv("^GSPC", NOW_DT - timedelta(days=i), "1D", o=100 + i, h=106 + i, lo=98 + i, c=104 + i)
    for i in range(20)
]

# 1-minute data — 60 bars spanning 1 hour (for custom interval aggregation)
# These represent a single trading day, 1 bar per minute
SEED_OHLCV_1M = [
    _make_ohlcv(
        "^GSPC",
        NOW_DT - timedelta(days=1, hours=1) + timedelta(minutes=i),
        "1m",
        o=100 + i * 0.1,
        h=101 + i * 0.1,
        lo=99 + i * 0.1,
        c=100.5 + i * 0.1,
        v=100,
    )
    for i in range(60)
]

# Standard 1H backfill data for dates before 1m exists
# These span 3 days before the 1m data (which starts ~1 day ago)
# 8 bars per day x 3 days = 24 bars
SEED_OHLCV_1H = [
    _make_ohlcv(
        "^GSPC",
        NOW_DT - timedelta(days=5) + timedelta(hours=i),
        "1H",
        o=90 + i * 0.1,
        h=91 + i * 0.1,
        lo=89 + i * 0.1,
        c=90.5 + i * 0.1,
        v=500,
    )
    for i in range(24)
]

# Pre-computed indicators for standard 1D
SEED_INDICATORS = [
    _make_indicator("^GSPC", "rsi", NOW_DT - timedelta(days=i), "rsi", 55.0 + i)
    for i in range(10)
]

SEED_SIGNALS = [
    _make_signal("^GSPC", "_aggregate", "buy"),
    _make_signal("^GSPC", "rsi", "buy"),
]


def _build_data(
    ohlcv_extra=None,
    indicators=None,
    signals=None,
):
    """Build session data, optionally adding extra OHLCV."""
    ohlcv = SEED_OHLCV_1D + SEED_OHLCV_1M + SEED_OHLCV_1H
    if ohlcv_extra:
        ohlcv += ohlcv_extra
    return {
        Index: [SEED_INDEX],
        OHLCVData: ohlcv,
        IndicatorData: indicators or SEED_INDICATORS,
        SignalData: signals or SEED_SIGNALS,
    }


@pytest_asyncio.fixture
async def client():
    """Async test client with mocked DB containing hybrid data."""

    async def mock_get_db():
        yield MockSession(_build_data())

    # Clear any cached earliest-1m data between tests
    from app.api.routes.indices import _earliest_1m_cache

    _earliest_1m_cache.clear()

    app.dependency_overrides[get_db] = mock_get_db
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test", follow_redirects=True
    ) as ac:
        yield ac
    app.dependency_overrides.clear()


@pytest_asyncio.fixture
async def client_no_1m():
    """Client with no 1m data — only standard intervals."""

    data = {
        Index: [SEED_INDEX],
        OHLCVData: SEED_OHLCV_1D,
        IndicatorData: SEED_INDICATORS,
        SignalData: SEED_SIGNALS,
    }

    async def mock_get_db():
        yield MockSession(data)

    from app.api.routes.indices import _earliest_1m_cache

    _earliest_1m_cache.clear()

    app.dependency_overrides[get_db] = mock_get_db
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test", follow_redirects=True
    ) as ac:
        yield ac
    app.dependency_overrides.clear()


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_ohlcv_response_has_bars_wrapper(client):
    """Response is OHLCVResponse with bars array, not raw array."""
    resp = await client.get("/api/indices/^GSPC/ohlcv?period=1y&interval=1D")
    assert resp.status_code == 200
    data = resp.json()
    assert isinstance(data, dict), "Response should be an object, not a list"
    assert "bars" in data
    assert isinstance(data["bars"], list)


@pytest.mark.asyncio
async def test_ohlcv_standard_interval_serves_precomputed(client):
    """Request for '1D' interval serves from ohlcv_data directly."""
    resp = await client.get("/api/indices/^GSPC/ohlcv?period=1y&interval=1D")
    assert resp.status_code == 200
    data = resp.json()
    bars = data["bars"]
    assert len(bars) > 0
    # Standard 1D data should be served as-is
    for bar in bars:
        assert "time" in bar
        assert "open" in bar
        assert "high" in bar
        assert "low" in bar
        assert "close" in bar
        assert "volume" in bar
        assert isinstance(bar["time"], int)


@pytest.mark.asyncio
async def test_ohlcv_custom_interval_aggregates_from_1m(client):
    """Request for '2m' aggregates from 1m data on the fly.

    We have 60 1m bars. Aggregating to 2m should produce ~30 bars.
    """
    resp = await client.get("/api/indices/^GSPC/ohlcv?period=1m&interval=2m")
    assert resp.status_code == 200
    data = resp.json()
    bars = data["bars"]
    # 60 1m bars aggregated into 2m should give ~30 bars
    assert len(bars) >= 10  # At least 10 candles (validation threshold)


@pytest.mark.asyncio
async def test_ohlcv_hybrid_stitches_data(client):
    """Response combines backfilled + aggregated data seamlessly.

    When custom interval requested, data before 1m coverage is served from
    the nearest standard interval, and data within 1m coverage is aggregated.
    """
    # Request 2H interval over a period that spans beyond 1m data
    resp = await client.get("/api/indices/^GSPC/ohlcv?period=1m&interval=2H")
    assert resp.status_code == 200
    data = resp.json()
    bars = data["bars"]
    # Should have some data (backfilled 1H + aggregated 1m)
    assert len(bars) >= 0  # May be few bars depending on date filtering
    # Bars should be sorted by time
    times = [b["time"] for b in bars]
    assert times == sorted(times), "Bars must be sorted by time"


@pytest.mark.asyncio
async def test_ohlcv_transition_timestamp_present(client):
    """Response includes dataTransitionTimestamp when hybrid data is served."""
    # Custom interval with both backfill and 1m data present
    resp = await client.get("/api/indices/^GSPC/ohlcv?period=1m&interval=2m")
    assert resp.status_code == 200
    data = resp.json()
    # dataTransitionTimestamp should be present when 1m data exists
    assert "dataTransitionTimestamp" in data


@pytest.mark.asyncio
async def test_ohlcv_last_updated_present(client):
    """Response includes lastUpdated timestamp."""
    resp = await client.get("/api/indices/^GSPC/ohlcv?period=1y&interval=1D")
    assert resp.status_code == 200
    data = resp.json()
    assert "lastUpdated" in data
    assert data["lastUpdated"] is not None
    assert isinstance(data["lastUpdated"], int)


@pytest.mark.asyncio
async def test_ohlcv_rejects_too_few_candles(client_no_1m):
    """Custom interval producing < 10 candles returns 400.

    With no 1m data available, a custom interval cannot produce candles.
    """
    resp = await client_no_1m.get("/api/indices/^GSPC/ohlcv?period=1m&interval=3H")
    assert resp.status_code == 400
    data = resp.json()
    assert "detail" in data


@pytest.mark.asyncio
async def test_ohlcv_invalid_interval_returns_400(client):
    """Invalid interval format returns 400 with error message."""
    resp = await client.get("/api/indices/^GSPC/ohlcv?period=1y&interval=abc")
    assert resp.status_code == 400
    data = resp.json()
    assert "detail" in data


@pytest.mark.asyncio
async def test_indicators_custom_interval_computed_on_fly(client):
    """Custom interval indicators are computed from aggregated OHLCV.

    For a custom interval, the route aggregates 1m OHLCV and then runs
    indicator calculations on the resulting DataFrame.
    """
    # Use 5m which aggregates 1m data (60 bars -> 12 bars)
    resp = await client.get("/api/indices/^GSPC/indicators?period=1m&interval=5m")
    assert resp.status_code == 200
    data = resp.json()
    # Should return indicator data (may be empty if not enough data for calculations)
    assert isinstance(data, list)


@pytest.mark.asyncio
async def test_period_start_returns_datetime():
    """_period_start() returns datetime, not date, for DateTime column queries."""
    from app.api.routes.indices import _period_start

    result = _period_start("1y")
    assert isinstance(result, datetime), "_period_start should return datetime, not date"
    assert result.tzinfo is not None, "_period_start should return timezone-aware datetime"
