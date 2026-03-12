"""Tests for API route handlers."""

import calendar
import re
from collections import defaultdict
from datetime import UTC, date, datetime, timedelta

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient

from app.core.database import get_db
from app.main import app
from app.models.market_data import (
    Fund,
    FundNAV,
    FundPerformance,
    Index,
    IndicatorData,
    OHLCVData,
    SignalData,
)


# ---------------------------------------------------------------------------
# Mock session helper
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
        """Route queries based on the model being selected from."""
        from sqlalchemy.sql import Select

        if isinstance(stmt, Select):
            for frm in stmt.get_final_froms():
                table_name = str(frm)
                for model_cls, rows in self._data.items():
                    if hasattr(model_cls, "__tablename__") and model_cls.__tablename__ == table_name:
                        filtered = self._apply_filters(stmt, rows)
                        return MockResult(filtered)

        return MockResult([])

    def _apply_filters(self, stmt, rows):
        """Attempt basic WHERE clause filtering for ticker and date range."""
        if stmt.whereclause is not None:
            try:
                clause_str = str(stmt.whereclause.compile(compile_kwargs={"literal_binds": True}))
            except Exception:
                return rows

            # Filter by ticker if present
            ticker_match = re.search(r"ticker\s*=\s*'([^']+)'", clause_str)
            if ticker_match:
                target_ticker = ticker_match.group(1)
                rows = [r for r in rows if getattr(r, "ticker", None) == target_ticker]

            # Filter by date if present (>= comparison)
            date_match = re.search(r"date\s*>=\s*'([^']+)'", clause_str)
            if date_match:
                start_str = date_match.group(1)
                start_date = date.fromisoformat(start_str)
                rows = [r for r in rows if hasattr(r, "date") and r.date >= start_date]

            # Filter by interval if present
            interval_match = re.search(r"interval\s*=\s*'([^']+)'", clause_str)
            if interval_match:
                target_interval = interval_match.group(1)
                rows = [r for r in rows if getattr(r, "interval", None) == target_interval]

            # Filter for indicator_id != '_aggregate'
            if "_aggregate" in clause_str and "indicator_id" in clause_str:
                rows = [r for r in rows if getattr(r, "indicator_id", None) != "_aggregate"]

            return rows
        return rows


# ---------------------------------------------------------------------------
# Plain data objects (avoid SQLAlchemy instrumentation issues in tests)
# ---------------------------------------------------------------------------


class FakeObj:
    """Simple namespace that acts like an ORM row for attribute access."""

    def __init__(self, **kwargs):
        for k, v in kwargs.items():
            object.__setattr__(self, k, v)


# ---------------------------------------------------------------------------
# Fixtures — test data
# ---------------------------------------------------------------------------

TODAY = date(2026, 3, 12)


def _make_index(name, ticker, region, price=100.0):
    return FakeObj(
        id=abs(hash(ticker)) % 10000,
        name=name, ticker=ticker, region=region,
        price=price, daily_change=1.5, signal="buy",
    )


def _make_ohlcv(ticker, d, interval="1D"):
    return FakeObj(
        id=abs(hash((ticker, d))) % 100000,
        ticker=ticker, date=d, interval=interval,
        open=100.0, high=105.0, low=99.0, close=104.0,
        volume=1000.0, fetched_at=datetime.now(UTC),
    )


def _make_indicator(ticker, indicator_id, d, series_key, value, interval="1D"):
    return FakeObj(
        id=abs(hash((ticker, indicator_id, d, series_key))) % 100000,
        ticker=ticker, indicator_id=indicator_id, interval=interval,
        date=d, series_key=series_key, value=value,
        fetched_at=datetime.now(UTC),
    )


def _make_signal(ticker, indicator_id, signal):
    return FakeObj(
        id=abs(hash((ticker, indicator_id))) % 100000,
        ticker=ticker, indicator_id=indicator_id, signal=signal,
        computed_at=datetime.now(UTC),
    )


def _make_fund(name, ticker, fund_type="equity"):
    return FakeObj(
        id=abs(hash(ticker)) % 10000,
        name=name, ticker=ticker, isin="FI0008805031",
        fund_type=fund_type, benchmark_ticker="^STOXX50E",
        benchmark_name="EURO STOXX 50", nav=42.5,
        daily_change=-0.3, return_1y=8.5,
    )


def _make_fund_nav(ticker, d, nav=42.0):
    return FakeObj(
        id=abs(hash((ticker, d))) % 100000,
        ticker=ticker, date=d, nav=nav,
        fetched_at=datetime.now(UTC),
    )


def _make_fund_performance(ticker):
    return FakeObj(
        id=abs(hash(ticker)) % 10000,
        ticker=ticker,
        returns_1y=8.5, returns_3y=25.0, returns_5y=45.0,
        benchmark_returns_1y=7.0, benchmark_returns_3y=20.0, benchmark_returns_5y=40.0,
        volatility=15.0, sharpe=1.2, max_drawdown=-12.0, ter=0.015,
        computed_at=datetime.now(UTC),
    )


# Seed data used across tests
SEED_INDICES = [
    _make_index("OMXH25", "^OMXH25", "nordic"),
    _make_index("S&P 500", "^GSPC", "global", 5200.0),
]

SEED_OHLCV = [
    _make_ohlcv("^GSPC", TODAY - timedelta(days=10)),
    _make_ohlcv("^GSPC", TODAY - timedelta(days=200)),
    _make_ohlcv("^GSPC", TODAY - timedelta(days=400)),  # outside 1y
]

SEED_INDICATORS = [
    _make_indicator("^GSPC", "rsi", TODAY - timedelta(days=5), "rsi", 65.0),
    _make_indicator("^GSPC", "rsi", TODAY - timedelta(days=10), "rsi", 55.0),
    _make_indicator("^GSPC", "macd", TODAY - timedelta(days=5), "macd", 1.5),
    _make_indicator("^GSPC", "macd", TODAY - timedelta(days=5), "signal", 1.2),
    _make_indicator("^GSPC", "macd", TODAY - timedelta(days=5), "histogram", 0.3),
]

SEED_SIGNALS = [
    _make_signal("^GSPC", "_aggregate", "buy"),  # aggregate
    _make_signal("^GSPC", "rsi", "buy"),
    _make_signal("^GSPC", "macd", "sell"),
    _make_signal("^GSPC", "bollinger", "hold"),
]

SEED_FUNDS = [
    _make_fund("ÅAB Europa Aktie B", "0P00000N9Y.F", "equity"),
    _make_fund("ÅAB Euro Bond A", "0P00000N9R.F", "bond"),
]

SEED_FUND_NAV = [
    _make_fund_nav("0P00000N9Y.F", TODAY - timedelta(days=5), 42.0),
    _make_fund_nav("0P00000N9Y.F", TODAY - timedelta(days=100), 40.0),
    _make_fund_nav("0P00000N9Y.F", TODAY - timedelta(days=400), 38.0),  # outside 1y
]

SEED_FUND_PERF = [
    _make_fund_performance("0P00000N9Y.F"),
]


def _build_session_data():
    return {
        Index: SEED_INDICES,
        OHLCVData: SEED_OHLCV,
        IndicatorData: SEED_INDICATORS,
        SignalData: SEED_SIGNALS,
        Fund: SEED_FUNDS,
        FundNAV: SEED_FUND_NAV,
        FundPerformance: SEED_FUND_PERF,
    }


@pytest_asyncio.fixture
async def client():
    """Async test client with mocked DB session."""

    async def mock_get_db():
        yield MockSession(_build_session_data())

    app.dependency_overrides[get_db] = mock_get_db
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test", follow_redirects=True) as ac:
        yield ac
    app.dependency_overrides.clear()


# ---------------------------------------------------------------------------
# Index routes
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_list_indices_returns_all(client):
    """GET /api/indices returns seeded indices with correct shape."""
    resp = await client.get("/api/indices")
    assert resp.status_code == 200
    data = resp.json()
    assert isinstance(data, list)
    assert len(data) == 2
    assert "name" in data[0]
    assert "ticker" in data[0]
    assert "region" in data[0]
    assert "signal" in data[0]


@pytest.mark.asyncio
async def test_get_ohlcv_filters_by_period(client):
    """OHLCV response only includes data within the requested period."""
    resp = await client.get("/api/indices/^GSPC/ohlcv?period=1y&interval=1D")
    assert resp.status_code == 200
    data = resp.json()
    assert isinstance(data, list)
    # 1y = 365 days. We have data at 10d and 200d (within), 400d (outside).
    # The mock filters by ticker, then the route filters by date >= start.
    # But our mock also filters by date, so we should get only the 2 within range.
    assert len(data) == 2
    for bar in data:
        assert "time" in bar
        assert "open" in bar
        assert "close" in bar
        assert isinstance(bar["time"], int)


@pytest.mark.asyncio
async def test_get_indicators_groups_by_id(client):
    """Indicators response groups series by indicator_id with correct series_keys."""
    resp = await client.get("/api/indices/^GSPC/indicators?period=1y&interval=1D")
    assert resp.status_code == 200
    data = resp.json()
    assert isinstance(data, list)
    ids = {item["id"] for item in data}
    assert "rsi" in ids
    assert "macd" in ids
    # macd should have multiple series keys
    macd_item = next(item for item in data if item["id"] == "macd")
    assert "series" in macd_item
    assert isinstance(macd_item["series"], dict)
    # macd has macd, signal, histogram series keys
    assert len(macd_item["series"]) == 3


@pytest.mark.asyncio
async def test_get_signal_includes_breakdown(client):
    """Signal response has aggregate + breakdown + activeCount."""
    resp = await client.get("/api/indices/^GSPC/signal")
    assert resp.status_code == 200
    data = resp.json()
    assert "aggregate" in data
    assert "breakdown" in data
    assert "activeCount" in data
    assert data["aggregate"] == "buy"
    assert isinstance(data["breakdown"], list)
    assert len(data["breakdown"]) == 3  # rsi, macd, bollinger
    ac = data["activeCount"]
    assert ac["buy"] == 1
    assert ac["sell"] == 1
    assert ac["hold"] == 1


# ---------------------------------------------------------------------------
# Fund routes
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_list_funds_returns_all(client):
    """GET /api/funds returns seeded funds."""
    resp = await client.get("/api/funds")
    assert resp.status_code == 200
    data = resp.json()
    assert isinstance(data, list)
    assert len(data) == 2


@pytest.mark.asyncio
async def test_get_fund_performance(client):
    """GET /api/funds/{ticker}/performance returns structured performance data."""
    resp = await client.get("/api/funds/0P00000N9Y.F/performance")
    assert resp.status_code == 200
    data = resp.json()
    assert "returns" in data
    assert "benchmarkReturns" in data
    assert "volatility" in data
    assert "sharpe" in data
    assert "maxDrawdown" in data
    assert "ter" in data
    assert data["returns"]["1y"] == 8.5
    assert data["benchmarkReturns"]["1y"] == 7.0


@pytest.mark.asyncio
async def test_get_fund_nav(client):
    """GET /api/funds/{ticker}/nav returns NAV points with unix timestamps."""
    resp = await client.get("/api/funds/0P00000N9Y.F/nav?period=1y")
    assert resp.status_code == 200
    data = resp.json()
    assert isinstance(data, list)
    # 1y filter: 5d and 100d within, 400d outside
    assert len(data) == 2
    for point in data:
        assert "time" in point
        assert "value" in point
        assert isinstance(point["time"], int)


# ---------------------------------------------------------------------------
# Error handling
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_unknown_ticker_404(client):
    """Requesting unknown ticker returns 404."""
    resp = await client.get("/api/indices/NONEXISTENT/ohlcv")
    assert resp.status_code == 404

    resp = await client.get("/api/indices/NONEXISTENT/signal")
    assert resp.status_code == 404

    resp = await client.get("/api/funds/NONEXISTENT/performance")
    assert resp.status_code == 404

    resp = await client.get("/api/funds/NONEXISTENT/nav")
    assert resp.status_code == 404


# ---------------------------------------------------------------------------
# camelCase output
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_camelcase_output(client):
    """Response JSON uses camelCase keys (dailyChange, not daily_change)."""
    # Index list should have dailyChange
    resp = await client.get("/api/indices")
    data = resp.json()
    assert len(data) > 0
    assert "dailyChange" in data[0]
    assert "daily_change" not in data[0]

    # Fund list should have fundType, benchmarkTicker, etc.
    resp = await client.get("/api/funds")
    data = resp.json()
    assert len(data) > 0
    assert "fundType" in data[0]
    assert "fund_type" not in data[0]
    assert "benchmarkTicker" in data[0]
    assert "dailyChange" in data[0]
    assert "return1Y" in data[0]

    # Signal should have activeCount
    resp = await client.get("/api/indices/^GSPC/signal")
    data = resp.json()
    assert "activeCount" in data
    assert "active_count" not in data

    # Fund performance should have benchmarkReturns, maxDrawdown
    resp = await client.get("/api/funds/0P00000N9Y.F/performance")
    data = resp.json()
    assert "benchmarkReturns" in data
    assert "maxDrawdown" in data
