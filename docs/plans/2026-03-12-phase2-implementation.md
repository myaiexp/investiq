# Phase 2: Backend Pipeline & Real Data — Implementation Plan

**Goal:** Replace mock data with real market data: yfinance fetching → PostgreSQL → pandas-ta indicators → FastAPI endpoints → frontend HTTP client.

**Architecture:** In-process APScheduler fetches data hourly from yfinance, computes all 10 technical indicators via pandas-ta, and stores everything in PostgreSQL. FastAPI endpoints serve pre-computed data. Frontend swaps mock client for HTTP calls.

**Tech Stack:** Python 3.12 / FastAPI / SQLAlchemy 2.0 (async) / asyncpg / yfinance / pandas-ta / APScheduler / Alembic

---

### Task 1: Update Models & Create Migration
[Mode: Direct]

**Files:**
- Modify: `backend/app/models/market_data.py`
- Create: `backend/alembic/versions/001_phase2_schema.py` (via `alembic revision --autogenerate`)

**Contracts:**

Update `Index` model — add fields:
- `price: Mapped[float | None]` (Float, nullable)
- `daily_change: Mapped[float | None]` (Float, nullable)
- `signal: Mapped[str | None]` (String(10), nullable)

Update `OHLCVData` model:
- Add `interval: Mapped[str]` (String(5), default "1D")
- Change UniqueConstraint to `("ticker", "date", "interval")`

Update `Fund` model — add fields:
- `benchmark_name: Mapped[str]` (String(100))
- `nav: Mapped[float | None]` (Float, nullable)
- `daily_change: Mapped[float | None]` (Float, nullable)
- `return_1y: Mapped[float | None]` (Float, nullable)

New model `IndicatorData`:
- `id` (PK), `ticker` (String(20), indexed), `indicator_id` (String(20)), `interval` (String(5))
- `date` (Date, indexed), `series_key` (String(20)), `value` (Float), `fetched_at` (DateTime TZ)
- UniqueConstraint: `("ticker", "indicator_id", "interval", "date", "series_key")`

New model `SignalData`:
- `id` (PK), `ticker` (String(20), indexed), `indicator_id` (String(20), nullable)
- `signal` (String(10)), `computed_at` (DateTime TZ)
- UniqueConstraint: `("ticker", "indicator_id")` — nullable indicator_id = aggregate row

New model `FundPerformance`:
- `id` (PK), `ticker` (String(30), unique)
- `returns_1y`, `returns_3y`, `returns_5y` (Float, nullable)
- `benchmark_returns_1y`, `benchmark_returns_3y`, `benchmark_returns_5y` (Float, nullable)
- `volatility`, `sharpe`, `max_drawdown`, `ter` (Float, nullable)
- `computed_at` (DateTime TZ)

**Verification:**
```bash
cd backend && uv run alembic revision --autogenerate -m "phase2 schema"
uv run alembic upgrade head
```
Expected: Migration creates/alters all tables without errors.

**Commit after passing.**

---

### Task 2: Pydantic Response Schemas
[Mode: Direct]

**Files:**
- Create: `backend/app/schemas/indices.py`
- Create: `backend/app/schemas/funds.py`

**Contracts:**

Must match frontend TypeScript types exactly (camelCase JSON output).

```python
# indices.py
class IndexMetaResponse(BaseModel):
    model_config = ConfigDict(populate_by_name=True)
    name: str
    ticker: str
    region: str
    price: float = Field(alias="price")
    daily_change: float = Field(serialization_alias="dailyChange")
    signal: str

class OHLCVBarResponse(BaseModel):
    time: int  # unix seconds
    open: float
    high: float
    low: float
    close: float
    volume: float

class IndicatorDataResponse(BaseModel):
    id: str
    series: dict[str, list[dict[str, float]]]  # key → [{time, value}]
    signal: str

class IndicatorMetaResponse(BaseModel):
    id: str
    category: str  # "overlay" | "oscillator"
    signal: str

class SignalSummaryResponse(BaseModel):
    aggregate: str
    breakdown: list[IndicatorMetaResponse]
    active_count: dict[str, int] = Field(serialization_alias="activeCount")

# funds.py
class FundMetaResponse(BaseModel):
    name: str
    ticker: str
    isin: str | None
    fund_type: str = Field(serialization_alias="fundType")
    benchmark_ticker: str | None = Field(serialization_alias="benchmarkTicker")
    benchmark_name: str = Field(serialization_alias="benchmarkName")
    nav: float
    daily_change: float = Field(serialization_alias="dailyChange")
    return_1y: float = Field(serialization_alias="return1Y")

class FundNAVPointResponse(BaseModel):
    time: int  # unix seconds
    value: float

class FundPerformanceResponse(BaseModel):
    returns: dict[str, float]  # {"1y", "3y", "5y"}
    benchmark_returns: dict[str, float] = Field(serialization_alias="benchmarkReturns")
    volatility: float
    sharpe: float
    max_drawdown: float = Field(serialization_alias="maxDrawdown")
    ter: float
```

**Constraints:**
- All responses must use camelCase serialization to match frontend expectations
- Use `model.model_dump(by_alias=True)` or FastAPI's `response_model` for automatic serialization

**Verification:**
```bash
cd backend && uv run python -c "from app.schemas.indices import *; from app.schemas.funds import *; print('schemas OK')"
```

**Commit after passing.**

---

### Task 3: Seed Data & Startup Seeding
[Mode: Direct]

**Files:**
- Create: `backend/app/data/seed.py`
- Modify: `backend/app/main.py` (add startup event)

**Contracts:**

`seed.py` contains:
- `SEED_INDICES: list[dict]` — 10 indices with name, ticker, region (from MOCK_INDICES)
- `SEED_FUNDS: list[dict]` — 6 funds with name, ticker, isin, fund_type, benchmark_ticker, benchmark_name (from MOCK_FUNDS)
- `async def seed_database(session: AsyncSession)` — inserts missing indices/funds (skip existing by ticker)

Indicator category mapping (needed for signal breakdown):
- `INDICATOR_CATEGORIES: dict[str, str]` mapping indicator_id → "overlay"|"oscillator"
  - overlay: bollinger, ma, fibonacci, ichimoku
  - oscillator: rsi, macd, stochastic, obv, atr, cci

`main.py` adds `@app.on_event("startup")` (or lifespan) that calls `seed_database`.

**Verification:**
```bash
cd backend && uv run python -c "from app.data.seed import SEED_INDICES, SEED_FUNDS; assert len(SEED_INDICES) == 10; assert len(SEED_FUNDS) == 6; print('seed data OK')"
```

**Commit after passing.**

---

### Task 4: Fetcher Service (yfinance)
[Mode: Delegated]

**Files:**
- Create: `backend/app/services/fetcher.py`
- Create: `backend/tests/test_fetcher.py`

**Contracts:**

```python
async def fetch_index_ohlcv(ticker: str, period: str, interval: str) -> pd.DataFrame:
    """Fetch OHLCV data from yfinance. Returns DataFrame with columns: Date, Open, High, Low, Close, Volume.
    Runs yfinance in thread executor (it's sync/blocking)."""

async def fetch_fund_nav(ticker: str, period: str = "5y") -> pd.DataFrame:
    """Fetch fund NAV history. Returns DataFrame with Date, Close columns."""

async def fetch_fund_info(ticker: str) -> dict:
    """Fetch fund metadata from yfinance .info dict. Returns available fields (TER, etc.)."""
```

**Constraints:**
- yfinance is synchronous — wrap calls in `asyncio.to_thread()` or `loop.run_in_executor()`
- Handle missing volume (common for indices) — fill with 0
- Normalize timezone-aware dates to UTC, then strip timezone for Date columns
- Map frontend period strings ("1m","3m","6m","1y","5y") to yfinance period params
- Map frontend interval strings ("1m","5m","15m","1H","2H","4H","1D","1W") to yfinance interval params ("1m","5m","15m","1h","2h","4h","1d","1wk")
- Log warnings on fetch failures, don't crash the whole refresh

**Test Cases:**

```python
def test_period_mapping():
    """Frontend period strings map correctly to yfinance params."""

def test_interval_mapping():
    """Frontend interval strings map correctly to yfinance params."""

def test_missing_volume_filled():
    """DataFrame with NaN volume gets 0-filled."""

def test_fetch_wraps_in_thread():
    """yfinance calls run in executor, not blocking the event loop."""
```

**Verification:**
```bash
cd backend && uv run pytest tests/test_fetcher.py -v
```

**Commit after passing.**

---

### Task 5: Indicators Service (pandas-ta)
[Mode: Delegated]

**Files:**
- Create: `backend/app/services/indicators.py`
- Create: `backend/tests/test_indicators.py`

**Contracts:**

```python
def calculate_indicators(df: pd.DataFrame) -> dict[str, dict[str, list[dict]]]:
    """Calculate all 10 indicators from OHLCV DataFrame.
    Returns: {indicator_id: {series_key: [{time: unix_s, value: float}]}}

    Series keys per indicator (must match frontend exactly):
    - rsi: {rsi}
    - macd: {macd, signal, histogram}
    - bollinger: {upper, middle, lower}
    - ma: {sma20, sma50, sma200}
    - stochastic: {k, d}
    - obv: {obv}
    - fibonacci: {fib_0, fib_24, fib_38, fib_50, fib_62, fib_79, fib_100}
    - atr: {atr}
    - ichimoku: {tenkan, kijun}
    - cci: {cci}
    """

def generate_signal(indicator_id: str, series_data: dict) -> str:
    """Evaluate indicator output against thresholds. Returns 'buy'|'sell'|'hold'.

    Rules:
    - RSI: <30 buy, >70 sell, else hold
    - MACD: macd > signal buy, macd < signal sell, else hold
    - Bollinger: close < lower buy, close > upper sell, else hold
    - MA: price > sma200 and sma50 > sma200 buy, opposite sell, else hold
    - Stochastic: k < 20 buy, k > 80 sell, else hold
    - OBV: rising trend buy, falling sell, else hold
    - Fibonacci: near support buy, near resistance sell, else hold
    - ATR: low volatility (trending) context-dependent → hold by default
    - Ichimoku: price > cloud buy, price < cloud sell, else hold
    - CCI: < -100 buy, > 100 sell, else hold
    """

def aggregate_signals(signals: dict[str, str]) -> str:
    """Majority vote across all indicator signals. Returns 'buy'|'sell'|'hold'."""
```

**Constraints:**
- Use pandas-ta for RSI, MACD, Bollinger, SMA, Stochastic, OBV, ATR, Ichimoku, CCI
- Fibonacci is calculated from high/low range (not a pandas-ta indicator)
- Drop NaN rows from indicator output (leading NaN from lookback periods)
- Convert dates to unix timestamps (int, seconds) for frontend compatibility
- Run in thread executor if called from async context (pandas-ta is CPU-bound)

**Test Cases:**

```python
def test_calculate_all_indicators_returns_correct_keys():
    """All 10 indicator IDs present in output with correct series keys."""

def test_indicator_series_keys_match_frontend():
    """Each indicator produces exactly the series keys the frontend expects."""

def test_rsi_signal_overbought():
    """RSI > 70 generates sell signal."""

def test_rsi_signal_oversold():
    """RSI < 30 generates buy signal."""

def test_macd_signal_crossover():
    """MACD > signal line generates buy signal."""

def test_aggregate_majority_vote():
    """Majority buy/sell/hold wins. Ties go to hold."""

def test_nan_rows_dropped():
    """Leading NaN from lookback periods are stripped from output."""

def test_fibonacci_levels():
    """Fibonacci generates 7 levels from high/low range."""
```

**Verification:**
```bash
cd backend && uv run pytest tests/test_indicators.py -v
```

**Commit after passing.**

---

### Task 6: Scheduler & Refresh Service
[Mode: Delegated]

**Files:**
- Create: `backend/app/services/scheduler.py`
- Create: `backend/tests/test_scheduler.py`

**Contracts:**

```python
async def refresh_index(ticker: str, session: AsyncSession) -> None:
    """Fetch OHLCV for all relevant period/interval combos, compute indicators, store signals.

    For each (period, interval) in PERIOD_INTERVAL_MAP:
      1. fetch_index_ohlcv(ticker, period, interval)
      2. Upsert OHLCV rows into ohlcv_data
      3. calculate_indicators(ohlcv_df)
      4. Upsert indicator_data rows

    Then: generate_signal per indicator on latest data, aggregate, upsert signal_data.
    Update index row: price (latest close), daily_change, signal (aggregate).
    """

async def refresh_fund(ticker: str, session: AsyncSession) -> None:
    """Fetch NAV history, fund info, compute performance metrics.

    1. fetch_fund_nav(ticker, "5y")
    2. Upsert fund_nav rows
    3. fetch_fund_info(ticker) — get TER etc.
    4. Calculate performance metrics from NAV: returns (1y/3y/5y), volatility, sharpe, max_drawdown
    5. Upsert fund_performance row
    6. Update fund row: nav (latest), daily_change, return_1y

    If fund has benchmark_ticker:
      - Also fetch benchmark NAV/OHLCV for relative performance calculation
      - Calculate benchmark_returns (1y/3y/5y)
    """

async def refresh_all(session_factory) -> dict:
    """Main refresh job. Iterates all indices and funds, calls refresh_index/refresh_fund.
    Returns summary: {indices_refreshed, funds_refreshed, errors}."""

def setup_scheduler(session_factory, interval_minutes: int) -> AsyncIOScheduler:
    """Create and configure APScheduler. Returns scheduler (caller starts it)."""
```

**Constraints:**
- PERIOD_INTERVAL_MAP must match frontend's map (defined in seed data or constants):
  - 1m: [1m, 5m, 15m, 1H, 2H, 4H, 1D]
  - 3m: [15m, 1H, 2H, 4H, 1D]
  - 6m: [1H, 4H, 1D, 1W]
  - 1y: [4H, 1D, 1W]
  - 5y: [1D, 1W]
- Upsert strategy: use `INSERT ... ON CONFLICT DO UPDATE` via SQLAlchemy
- Performance metrics calculation:
  - Returns: `(nav_end / nav_start - 1) * 100` for 1y/3y/5y windows
  - Volatility: annualized std dev of daily returns (`daily_std * sqrt(252) * 100`)
  - Sharpe: `(annualized_return - risk_free) / volatility` (use 3% risk-free)
  - Max drawdown: `min((nav / cummax - 1)) * 100`
- Log each ticker refresh (success/failure), continue on individual failures
- Catch and log yfinance errors per ticker — don't abort the entire refresh

**Test Cases:**

```python
def test_refresh_all_processes_all_tickers():
    """All 10 indices and 6 funds are processed."""

def test_refresh_index_upserts_ohlcv():
    """OHLCV data is inserted/updated, not duplicated."""

def test_refresh_fund_calculates_returns():
    """1y/3y/5y returns computed correctly from NAV history."""

def test_sharpe_ratio_calculation():
    """Sharpe ratio = (return - risk_free) / volatility."""

def test_max_drawdown_calculation():
    """Max drawdown calculated from peak-to-trough."""

def test_individual_failure_doesnt_abort():
    """If one ticker fails, others still process."""
```

**Verification:**
```bash
cd backend && uv run pytest tests/test_scheduler.py -v
```

**Commit after passing.**

---

### Task 7: API Routes Implementation
[Mode: Delegated]

**Files:**
- Modify: `backend/app/api/routes/indices.py`
- Modify: `backend/app/api/routes/funds.py`
- Create: `backend/app/api/routes/system.py` (refresh + health)
- Modify: `backend/app/main.py` (register system router)
- Create: `backend/tests/test_routes.py`

**Contracts:**

```python
# indices.py
@router.get("/", response_model=list[IndexMetaResponse])
async def list_indices(db: AsyncSession = Depends(get_db)):
    """SELECT * FROM indices ORDER BY region, name."""

@router.get("/{ticker}/ohlcv", response_model=list[OHLCVBarResponse])
async def get_ohlcv(ticker: str, period: str = "1y", interval: str = "1D", db = Depends(get_db)):
    """Query ohlcv_data filtered by ticker + interval + date range (derived from period).
    Convert date to unix timestamp for 'time' field."""

@router.get("/{ticker}/indicators", response_model=list[IndicatorDataResponse])
async def get_indicators(ticker: str, period: str = "1y", interval: str = "1D", db = Depends(get_db)):
    """Query indicator_data filtered by ticker + interval + date range.
    Group rows by indicator_id, nest by series_key."""

@router.get("/{ticker}/signal", response_model=SignalSummaryResponse)
async def get_signal(ticker: str, db = Depends(get_db)):
    """Query signal_data for ticker. Build breakdown with indicator categories.
    Count buy/sell/hold for activeCount."""

# funds.py
@router.get("/", response_model=list[FundMetaResponse])
async def list_funds(db = Depends(get_db)):
    """SELECT * FROM funds ORDER BY fund_type, name."""

@router.get("/{ticker}/performance", response_model=FundPerformanceResponse)
async def get_fund_performance(ticker: str, db = Depends(get_db)):
    """Query fund_performance for ticker. Structure returns/benchmarkReturns as nested dicts."""

@router.get("/{ticker}/nav", response_model=list[FundNAVPointResponse])
async def get_fund_nav(ticker: str, period: str = "1y", db = Depends(get_db)):
    """Query fund_nav filtered by ticker + date range. Convert date to unix timestamp."""

# system.py
@router.post("/refresh")
async def trigger_refresh():
    """Trigger immediate refresh_all(). Return {status, message, summary}."""
```

**Constraints:**
- Period-to-date-range conversion: "1m" → 30 days ago, "3m" → 90, "6m" → 180, "1y" → 365, "5y" → 1825
- All date fields converted to unix timestamps (int seconds) in responses
- 404 if ticker not found in DB
- Use `by_alias=True` / `response_model` for camelCase output

**Test Cases:**

```python
def test_list_indices_returns_all():
    """GET /api/indices returns 10 indices with correct shape."""

def test_get_ohlcv_filters_by_period():
    """OHLCV response only includes data within the requested period."""

def test_get_indicators_groups_by_id():
    """Indicators response groups series by indicator_id with correct series_keys."""

def test_get_signal_includes_breakdown():
    """Signal response has aggregate + 10-item breakdown + activeCount."""

def test_list_funds_returns_all():
    """GET /api/funds returns 6 funds."""

def test_unknown_ticker_404():
    """Requesting unknown ticker returns 404."""

def test_camelcase_output():
    """Response JSON uses camelCase keys (dailyChange, not daily_change)."""
```

**Verification:**
```bash
cd backend && uv run pytest tests/test_routes.py -v
```

**Commit after passing.**

---

### Task 8: App Lifecycle (Startup + Scheduler)
[Mode: Direct]

**Files:**
- Modify: `backend/app/main.py`

**Contracts:**

Replace `@app.on_event` with lifespan context manager:

```python
@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    async with async_session() as session:
        await seed_database(session)
    scheduler = setup_scheduler(async_session, settings.data_refresh_interval)
    scheduler.start()
    # Trigger initial refresh for stale data
    asyncio.create_task(refresh_all(async_session))
    yield
    # Shutdown
    scheduler.shutdown()
```

**Constraints:**
- Initial refresh runs as background task (don't block startup)
- Scheduler uses `AsyncIOScheduler` from APScheduler
- Import and register the system router (refresh endpoint)

**Verification:**
```bash
cd backend && uv run uvicorn app.main:app --host 0.0.0.0 --port 8000 &
sleep 5 && curl http://localhost:8000/api/health
curl http://localhost:8000/api/indices
kill %1
```
Expected: health returns OK, indices returns seeded data (may be empty prices until first refresh completes).

**Commit after passing.**

---

### Task 9: VPS Deployment
[Mode: Direct]

**Files:**
- Create: `backend/deploy/investiq.service` (systemd unit)
- Modify: VPS nginx config (add /api proxy)
- Modify: VPS post-receive hook (add backend setup)

**Contracts:**

systemd service:
- `ExecStart`: uvicorn with `--host 127.0.0.1 --port 8000`
- WorkingDirectory: `/var/www/investiq-backend/`
- Environment: load from `/var/www/investiq-backend/.env`
- Restart: always

nginx: Add `location /investiq/api/` proxy_pass to `127.0.0.1:8000/api/`

post-receive hook: `cd backend && uv sync && uv run alembic upgrade head`, copy to deploy path, restart service.

**Constraints:**
- Backend runs alongside the static frontend (same domain, different paths)
- Database must exist on db.mase.fi — create `investiq` database and user if not exists
- `.env` on VPS with production CORS origins

**Verification:**
```bash
ssh vps "systemctl status investiq"
curl https://mase.fi/investiq/api/health
```

**Commit after passing.**

---

### Task 10: Frontend API Swap
[Mode: Delegated]

**Files:**
- Modify: `frontend/src/api/client.ts`
- Delete: `frontend/src/data/mock/` (after confirmation)

**Contracts:**

Replace mock `api` object with HTTP implementation:

```typescript
const BASE = import.meta.env.DEV ? '/api' : '/investiq/api';

export const api: Api = {
  getIndices: () => fetch(`${BASE}/indices`).then(r => r.json()),
  getOHLCV: (ticker, period = '1y', interval = '1D') =>
    fetch(`${BASE}/indices/${encodeURIComponent(ticker)}/ohlcv?period=${period}&interval=${interval}`).then(r => r.json()),
  getIndicators: (ticker, period = '1y', interval = '1D') =>
    fetch(`${BASE}/indices/${encodeURIComponent(ticker)}/indicators?period=${period}&interval=${interval}`).then(r => r.json()),
  getSignal: (ticker) =>
    fetch(`${BASE}/indices/${encodeURIComponent(ticker)}/signal`).then(r => r.json()),
  getFunds: () => fetch(`${BASE}/funds`).then(r => r.json()),
  getFundPerformance: (ticker) =>
    fetch(`${BASE}/funds/${encodeURIComponent(ticker)}/performance`).then(r => r.json()),
  getFundNAV: (ticker, period = '1y') =>
    fetch(`${BASE}/funds/${encodeURIComponent(ticker)}/nav?period=${period}`).then(r => r.json()),
};
```

**Constraints:**
- Keep the `Api` interface unchanged
- `encodeURIComponent` for tickers with special chars (`^OMXH25`, `0P00000N9Y.F`)
- Base URL: dev proxy handles `/api` → backend; production uses `/investiq/api`
- Delete mock data directory only after confirming real data works end-to-end
- Remove delay function, mock imports

**Verification:**
- Deploy frontend, open https://mase.fi/investiq
- Verify: indices grid loads with real prices, charts render real OHLCV, indicators display, fund cards show real NAV
- Check network tab: all API calls return 200 with correct data shapes

**Commit after passing.**

---

## Execution
**Skill:** superpowers:subagent-driven-development
- Mode A tasks (Direct): Tasks 1, 2, 3, 8, 9
- Mode B tasks (Delegated): Tasks 4, 5, 6, 7, 10
