# Phase 3: Data Completeness & Source Diversification — Implementation Plan

**Goal:** Fix broken data (ticker swaps, missing fund, benchmarks, currency), rework the data pipeline to collect 1m candles and aggregate all larger intervals, and update the frontend interval selector with presets + dropdown + free-form input.

**Architecture:** Schema migration (Date→DateTime for intraday support), new aggregation service, backfill CLI for historical data, scheduler split into 15-min index fetch + hourly fund fetch, API hybrid serving from backfilled + aggregated data, frontend interval selector rework.

**Tech Stack:** Python 3.12 / FastAPI / SQLAlchemy 2.0 (async) / Alembic / pandas / React 19 / TypeScript / lightweight-charts 5.1

**Naming note:** In this project, `"1m"` as a Period means **1 month** (matching the `Period` type). `"1m"` as an Interval means **1 minute**. Context always disambiguates — periods are in period selectors/maps, intervals are in interval selectors/maps.

**Deploy strategy:** `git deployboth` deploys atomically — the post-receive hook builds the frontend and restarts the backend in a single operation. No window where old frontend talks to new backend. Backend and frontend changes can land in the same commit safely.

---

## Chunk 1: Backend Data Foundation

### Task 1: Schema Migration — DateTime + Currency
[Mode: Direct]

**Files:**
- Modify: `backend/app/models/market_data.py`
- Create: Alembic migration via `uv run alembic revision --autogenerate -m "phase3 datetime and currency"`

**Contracts:**

Model changes:
```python
# OHLCVData: change date column
date: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
# UniqueConstraint stays: ("ticker", "date", "interval")

# IndicatorData: change date column
date: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
# UniqueConstraint stays: ("ticker", "indicator_id", "interval", "date", "series_key")

# Index: add currency
currency: Mapped[str | None] = mapped_column(String(3), nullable=True)
```

Migration must handle existing data: existing `Date` values converted to `DateTime` at 00:00 UTC. Use Alembic `op.alter_column()` with `type_=DateTime(timezone=True)` and a server_default or explicit data migration step (PostgreSQL handles Date→Timestamp implicitly by assuming 00:00:00).

**Constraints:**
- Existing daily data must survive the migration (no data loss)
- All downstream code that queries by date needs DateTime-compatible comparisons:
  - `indices.py` route: `_period_start()` must return `datetime` not `date`
  - `indices.py` route: `_date_to_unix()` must handle `datetime` input (already works via `.timetuple()`)
  - Scheduler upserts: change `row["Date"].date()` to `row["Date"].to_pydatetime()` (or equivalent) to preserve time component for intraday data, while daily rows stay at 00:00 UTC
- FundNAV.date stays as `Date` — funds are daily-only, no change needed

**Verification:**
```bash
cd backend && uv run alembic revision --autogenerate -m "phase3 datetime and currency"
uv run alembic upgrade head
uv run python -c "from app.models.market_data import OHLCVData, IndicatorData, Index; print('models OK')"
```

**Commit after passing.**

---

### Task 2: Seed Data Updates
[Mode: Direct]

**Files:**
- Modify: `backend/app/data/seed.py`
- Modify: `backend/app/api/routes/funds.py` (data notes cleanup)
- Modify: `backend/app/schemas/indices.py` (add currency field)

**Contracts:**

`seed.py` — update SEED_FUNDS static data:
- Euro Bond: ticker `0P00000N9R.F` → `0P00000N9Q.F`, name → "ÅAB Euro Bond B", benchmark_ticker → `SYBA.DE`, benchmark_name → "Bloomberg Euro Aggregate Bond"
- Green Bond ESG C: benchmark_ticker → `GRON.DE`, benchmark_name → "Bloomberg Euro Green Bond"
- Europa Aktie B: benchmark_ticker → `IEUR`, benchmark_name → "MSCI Europe"
- Append to SEED_FUNDS: `{"name": "ÅAB Varainhoito B", "ticker": "0P00001CPE.F", "isin": "FI0008809934", "fund_type": "balanced", "benchmark_ticker": None, "benchmark_name": ""}`
- Add currency to each SEED_INDICES entry: `"currency": "EUR"` / `"SEK"` / etc.

`seed.py` — add DB migration queries in `seed_database()` (before inserts, same section as existing OMXS30 migration):

```python
# Euro Bond: swap ticker across all tables
old_eb, new_eb = "0P00000N9R.F", "0P00000N9Q.F"
await session.execute(update(Fund).where(Fund.ticker == old_eb).values(
    ticker=new_eb, name="ÅAB Euro Bond B",
    benchmark_ticker="SYBA.DE", benchmark_name="Bloomberg Euro Aggregate Bond"
))
await session.execute(update(OHLCVData).where(OHLCVData.ticker == old_eb).values(ticker=new_eb))
await session.execute(update(IndicatorData).where(IndicatorData.ticker == old_eb).values(ticker=new_eb))
await session.execute(update(SignalData).where(SignalData.ticker == old_eb).values(ticker=new_eb))
await session.execute(update(FundNAV).where(FundNAV.ticker == old_eb).values(ticker=new_eb))
await session.execute(update(FundPerformance).where(FundPerformance.ticker == old_eb).values(ticker=new_eb))

# Europa Aktie B: update benchmark
await session.execute(update(Fund).where(Fund.ticker == "0P00000N9Y.F").values(
    benchmark_ticker="IEUR", benchmark_name="MSCI Europe"
))

# Green Bond ESG C: add benchmark
await session.execute(update(Fund).where(Fund.ticker == "0P0001HOZS.F").values(
    benchmark_ticker="GRON.DE", benchmark_name="Bloomberg Euro Green Bond"
))

# Index currency: update all
for idx in SEED_INDICES:
    await session.execute(update(Index).where(Index.ticker == idx["ticker"]).values(currency=idx["currency"]))
```

`funds.py` data notes cleanup:
- Remove `0P00000N9R.F` from `FUND_DATA_NOTES` (Euro Bond A NAV warning — obsolete after B class swap)
- Keep `0P0001HOZS.F` in `FUND_DATA_NOTES` (Green Bond C share class note — still relevant)
- Remove `0P00000N9R.F` and `0P0001HOZS.F` from `FUND_BENCHMARK_NOTES` (both now have benchmarks)

`indices.py` schema:
- Add `currency: str | None = Field(None, serialization_alias="currency")` to `IndexMetaResponse`
- Include `currency` in the list endpoint response construction

**Constraints:**
- All ticker migrations must be idempotent (safe to re-run if already applied)
- Ticker migration runs before inserts — existing pattern

**Verification:**
```bash
cd backend && uv run python -c "
from app.data.seed import SEED_INDICES, SEED_FUNDS
assert len(SEED_INDICES) == 10
assert len(SEED_FUNDS) == 7
assert any(f['ticker'] == '0P00001CPE.F' for f in SEED_FUNDS)
assert any(f['ticker'] == '0P00000N9Q.F' for f in SEED_FUNDS)
assert all('currency' in i for i in SEED_INDICES)
print('seed data OK')
"
```

**Commit after passing.**

---

### Task 3: Aggregation Engine
[Mode: Delegated]

**Files:**
- Create: `backend/app/services/aggregator.py`
- Create: `backend/tests/test_aggregator.py`

**Contracts:**

```python
def parse_interval(interval: str) -> tuple[int, str]:
    """Parse interval string like '5m', '4H', '1D', '2W' into (count, unit).

    Valid: positive integer 1-999 followed by m/H/D/W (case-sensitive).
    Raises ValueError for invalid formats.
    """

def aggregate_candles(bars: list[dict], interval: str) -> list[dict]:
    """Aggregate 1m (or any smaller) OHLCV bars into candles of the target interval.

    Input bars: list of dicts with keys {time (unix seconds), open, high, low, close, volume}
    Output: same structure, aggregated per interval boundary.

    Grouping alignment (UTC):
    - Minutes: clock-aligned (15m → :00, :15, :30, :45)
    - Hours: midnight-aligned (4H → 00:00, 04:00, 08:00, ...)
    - Days: calendar days
    - Weeks: ISO weeks (Monday start)

    Aggregation per group:
    - open: first bar's open
    - high: max of all highs
    - low: min of all lows
    - close: last bar's close
    - volume: sum of all volumes

    Skips groups with no bars (e.g., outside market hours).
    Returns bars sorted by time ascending.
    """

def validate_interval(interval: str) -> str:
    """Validate and normalize interval string. Returns normalized form.
    Raises ValueError if invalid (0 count, >999, wrong unit, wrong case).
    '1m' is valid (returns raw 1m data, no aggregation needed).
    """
```

**Test Cases:**

```python
def test_aggregate_5m_from_1m():
    """5 consecutive 1m bars aggregate into one 5m candle with correct OHLCV."""

def test_aggregate_1h_alignment():
    """1m bars at 09:50-10:10 produce two 1H candles (09:xx and 10:xx)."""

def test_aggregate_4h_alignment():
    """Bars are grouped into 4H boundaries aligned to midnight UTC."""

def test_aggregate_daily():
    """All bars on same calendar day (UTC) aggregate into one daily candle."""

def test_aggregate_weekly():
    """Bars spanning Mon-Sun aggregate into one weekly candle."""

def test_aggregate_skips_empty_groups():
    """No output candle for time groups with no input bars."""

def test_aggregate_preserves_order():
    """Output candles are sorted by time ascending."""

def test_aggregate_volume_sum():
    """Volume is summed across all bars in a group."""

def test_validate_interval_valid():
    """Valid intervals: '1m', '5m', '15m', '1H', '4H', '1D', '1W', '2H', '45m', '999W'."""

def test_validate_interval_invalid():
    """Invalid: '0m', '1h' (lowercase h), '1000D', '1M' (month not supported), '', 'abc'."""

def test_parse_interval():
    """'15m' → (15, 'm'), '4H' → (4, 'H'), '1D' → (1, 'D')."""

def test_aggregate_single_bar():
    """Single bar returns itself (trivial aggregation)."""
```

**Constraints:**
- Must handle bars with gaps (weekends, holidays, market closed) gracefully
- Input bars assumed sorted by time ascending
- Performance: should handle 100K+ 1m bars efficiently (use pandas internally if needed)

**Verification:**
```bash
cd backend && uv run pytest tests/test_aggregator.py -v
```

**Commit after passing.**

---

### Task 4: Backfill CLI
[Mode: Delegated]

**Files:**
- Create: `backend/app/cli/__init__.py`
- Create: `backend/app/cli/backfill.py`
- Create: `backend/tests/test_backfill.py`

**Contracts:**

```python
# backfill.py — runnable as: uv run python -m app.cli.backfill

# Intervals use app convention (uppercase H/D). The fetcher's INTERVAL_MAP
# translates to yfinance format (lowercase) via .get(interval, interval).
# Periods use raw yfinance values (not in PERIOD_MAP) — they fall through.
BACKFILL_INTERVALS: list[tuple[str, str]] = [
    ("7d", "1m"),      # 1m: ~7 days retention
    ("60d", "5m"),     # 5m: ~60 days retention
    ("60d", "15m"),    # 15m: ~60 days retention
    ("730d", "1H"),    # 1H: ~2 years retention
    ("max", "4H"),     # 4H+: full history
    ("max", "1D"),
    ("max", "1W"),
]
# The interval values ("1H", "4H", "1D", "1W") match what's stored in ohlcv_data.interval
# and what the API/frontend use. fetcher.py handles translation to yfinance format.

LOCK_FILE = "/tmp/investiq-backfill.lock"

async def backfill_index(ticker: str, session: AsyncSession) -> dict:
    """Fetch all intervals for one index and upsert into ohlcv_data.
    Returns: {interval: row_count} summary.
    Uses fetcher.fetch_index_ohlcv() for each interval.
    Stores intervals using app convention (1H, 4H, 1D, 1W) in the DB.
    Delays 2s between yfinance calls.
    """

async def backfill_all(session_factory) -> dict:
    """Backfill all 10 indices. Acquires lock file, runs sequentially.
    After all indices: triggers indicator pre-computation for standard intervals.
    Returns summary with per-index results.
    Raises if lock file exists (concurrent run prevention).
    """

async def precompute_indicators_after_backfill(session_factory) -> None:
    """For each index, for each standard interval (5m, 15m, 1H, 4H, 1D, 1W):
    aggregate stored OHLCV to that interval, compute indicators, store results.
    Only processes trailing 2 years of data (not full history).
    """

if __name__ == "__main__":
    # Entry point: uv run python -m app.cli.backfill
    asyncio.run(backfill_all(async_session))
```

**Important:** After running backfill on VPS, restart the investiq service (`systemctl restart investiq`) to clear any in-memory caches (e.g., the earliest-1m-row cache in the API routes).

**Test Cases:**

```python
def test_backfill_index_fetches_all_intervals():
    """All 7 interval/period combos are fetched for one index."""

def test_backfill_index_upserts_data():
    """Fetched OHLCV rows are upserted (not duplicated on re-run)."""

def test_backfill_stores_app_convention_intervals():
    """Stored interval values use app convention: '1H' not '1h', '1D' not '1d'."""

def test_backfill_all_processes_all_indices():
    """All 10 indices are processed."""

def test_backfill_lock_prevents_concurrent():
    """Second backfill_all raises if lock file exists."""

def test_backfill_lock_cleaned_up():
    """Lock file removed after successful completion."""

def test_backfill_lock_cleaned_up_on_error():
    """Lock file removed even if backfill fails."""
```

**Constraints:**
- 2s delay between yfinance calls to avoid rate limiting
- Lock file at `/tmp/investiq-backfill.lock` — created on start, removed on completion (including on error via try/finally)
- Reuses existing `fetch_index_ohlcv()` from fetcher service
- Reuses existing upsert pattern from scheduler (pg_insert + on_conflict_do_update)
- Upsert stores `datetime` in the `date` column (not `date()` — preserves intraday timestamps)
- Logs progress: "Backfilling {ticker} {interval}... {row_count} rows"
- Estimated runtime: 5-15 minutes for 10 indices × 7 intervals

**Verification:**
```bash
cd backend && uv run pytest tests/test_backfill.py -v
```

**Commit after passing.**

---

### Task 5: Scheduler Rework
[Mode: Delegated]

**Files:**
- Modify: `backend/app/services/scheduler.py`
- Modify: `backend/app/main.py` (lifespan changes)
- Modify: `backend/app/core/config.py` (add index_refresh_interval setting)
- Modify: `backend/tests/test_scheduler.py`

**Contracts:**

`scheduler.py` changes:

```python
STANDARD_INTERVALS = ["5m", "15m", "1H", "4H", "1D", "1W"]

async def refresh_indices_1m(session_factory) -> dict:
    """Fetch 1m data for all 10 indices (7-day window).
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

async def refresh_funds(session_factory) -> dict:
    """Fetch daily NAV for all 7 funds + benchmarks. Same logic as current
    refresh_fund(), handling 7 funds (including Varainhoito).
    Returns: {funds_refreshed: int, errors: list[str]}
    """

async def refresh_all(session_factory) -> dict:
    """Run both refresh_indices_1m and refresh_funds.
    Returns combined summary."""

def setup_scheduler(session_factory, index_interval: int = 15, fund_interval: int = 60) -> AsyncIOScheduler:
    """Two jobs:
    - 'refresh_indices': every index_interval minutes
    - 'refresh_funds': every fund_interval minutes
    """
```

**Signal storage clarification:** Signals are only stored for the 1D interval (used by index grid cards for the aggregate buy/sell/hold badge). The `signal_data` table keeps its existing schema with no interval column. When the API serves indicators for other intervals, signals are computed on the fly from the indicator data — not stored.

`config.py` addition:
```python
index_refresh_interval: int = 15  # minutes (for 1m OHLCV fetch)
# existing data_refresh_interval stays as fund refresh interval
```

`main.py` lifespan update:
- Pass both `settings.index_refresh_interval` and `settings.data_refresh_interval` to `setup_scheduler()`
- Initial refresh still triggers `refresh_all()` as background task

**DateTime upsert change:** The existing upsert in `refresh_index()` converts dates via `row["Date"].date()`. After Task 1's migration, this must change to preserve the full datetime:
- For 1m data: `row["Date"].to_pydatetime()` (preserves time)
- For daily aggregated data: the aggregator outputs timestamps at 00:00 UTC, which is correct

**Stale data handling:**
- Track consecutive failures per ticker in memory (dict)
- After 3 consecutive failures: log warning
- Reset counter on success

**Test Cases:**

```python
def test_refresh_indices_fetches_1m():
    """fetch_index_ohlcv called with '7d' period and '1m' interval."""

def test_refresh_indices_aggregates_standard_intervals():
    """Aggregated OHLCV produced for 5m, 15m, 1H, 4H, 1D, 1W."""

def test_refresh_indices_computes_indicators_1d_only():
    """Indicators and signals computed and stored for 1D interval only."""

def test_refresh_indices_upserts_datetime_not_date():
    """OHLCV upsert uses datetime (preserving time) not date()."""

def test_refresh_funds_processes_all():
    """All 7 funds processed (including new Varainhoito)."""

def test_scheduler_two_jobs():
    """setup_scheduler creates two separate interval jobs."""

def test_consecutive_failure_tracking():
    """After 3 failures, warning logged. Counter resets on success."""

def test_partial_data_upserted():
    """Partial yfinance response is upserted (not rejected)."""
```

**Constraints:**
- Each 15-min cycle: 10 yfinance calls (one per index, 1m data). ~40 calls/hr, well within limits.
- Aggregation + indicator computation must complete within 15 minutes (should be < 30 seconds total)
- Fund refresh unchanged except: now processes 7 funds, uses updated tickers/benchmarks
- Existing `refresh_index()` and `refresh_fund()` can be preserved as internal helpers or refactored — implementer's choice

**Verification:**
```bash
cd backend && uv run pytest tests/test_scheduler.py -v
```

**Commit after passing.**

---

### Task 6: API — Hybrid Serving & Custom Intervals
[Mode: Delegated]

**Files:**
- Modify: `backend/app/api/routes/indices.py`
- Modify: `backend/app/schemas/indices.py` (add response wrapper)
- Create: `backend/tests/test_hybrid_serving.py`

**Contracts:**

`indices.py` route changes:

```python
@router.get("/{ticker}/ohlcv")
async def get_ohlcv(ticker: str, period: str = "1y", interval: str = "1D", db = Depends(get_db)):
    """Hybrid data serving:
    1. Validate interval with aggregator.validate_interval()
    2. Determine date range from period (using datetime, not date)
    3. For standard intervals (5m, 15m, 1H, 4H, 1D, 1W):
       query pre-aggregated data from ohlcv_data directly
    4. For custom intervals:
       a. Find earliest 1m row for this ticker (cached)
       b. Query 1m data for the date range
       c. Aggregate on the fly using aggregator.aggregate_candles()
       d. For dates before 1m data exists, query backfilled data at nearest
          standard interval and serve as-is
    5. Return OHLCVResponse with bars + metadata

    Reject if interval produces < 10 candles for the period (HTTP 400).
    """

@router.get("/{ticker}/indicators")
async def get_indicators(ticker: str, period: str = "1y", interval: str = "1D", db = Depends(get_db)):
    """Standard intervals: serve pre-computed from indicator_data table.
    Custom intervals: aggregate OHLCV from 1m, compute indicators on the fly,
    generate per-indicator signals from the computed data.
    """
```

**Date/time query changes:** `_period_start()` must return `datetime` (not `date`) since `OHLCVData.date` is now `DateTime`. Update comparisons accordingly. `_date_to_unix()` already works with datetime via `.timetuple()`.

New response schema:
```python
class OHLCVResponse(BaseModel):
    """Wrapper for OHLCV data with metadata."""
    bars: list[OHLCVBarResponse]
    data_transition_timestamp: int | None = Field(None, serialization_alias="dataTransitionTimestamp")
    last_updated: int | None = Field(None, serialization_alias="lastUpdated")
```

This changes the OHLCV endpoint from returning `list[OHLCVBarResponse]` to `OHLCVResponse`. Deployed atomically with frontend changes via `git deployboth`.

**Transition point cache:**
```python
# Module-level cache: {ticker: earliest_1m_unix_timestamp}
_earliest_1m_cache: dict[str, int | None] = {}

async def get_earliest_1m(ticker: str, db: AsyncSession) -> int | None:
    """Query earliest 1m row for ticker. Cache result. Return unix timestamp or None.
    Cache is cleared on app restart (after backfill, restart the service).
    """
```

**Test Cases:**

```python
def test_ohlcv_standard_interval_serves_precomputed():
    """Request for '1D' interval serves from ohlcv_data directly."""

def test_ohlcv_custom_interval_aggregates_from_1m():
    """Request for '2H' aggregates from 1m data on the fly."""

def test_ohlcv_hybrid_stitches_data():
    """Response combines backfilled + aggregated data seamlessly."""

def test_ohlcv_response_has_bars_wrapper():
    """Response is OHLCVResponse with bars array, not raw array."""

def test_ohlcv_transition_timestamp_present():
    """Response includes dataTransitionTimestamp when hybrid data is served."""

def test_ohlcv_last_updated_present():
    """Response includes lastUpdated timestamp."""

def test_ohlcv_rejects_too_few_candles():
    """Custom interval producing < 10 candles returns 400."""

def test_ohlcv_invalid_interval_returns_400():
    """Invalid interval format returns 400 with error message."""

def test_indicators_custom_interval_computed_on_fly():
    """Custom interval indicators are computed from aggregated OHLCV."""

def test_period_start_returns_datetime():
    """_period_start() returns datetime, not date, for DateTime column queries."""
```

**Constraints:**
- For standard intervals where pre-computed data exists, skip aggregation entirely (performance)
- Cache cleared on app restart — after backfill, restart the service
- The response shape change is atomic with frontend deployment

**Verification:**
```bash
cd backend && uv run pytest tests/test_hybrid_serving.py -v
```

**Commit after passing.**

---

## Chunk 2: Frontend Updates

### Task 7: Frontend Types, API Client & FundType
[Mode: Direct]

**Files:**
- Modify: `frontend/src/types/charts.ts` (PERIOD_INTERVAL_MAP, Interval type)
- Modify: `frontend/src/types/funds.ts` (FundType)
- Modify: `frontend/src/types/market.ts` (IndexMeta, OHLCVResponse wrapper)
- Modify: `frontend/src/api/client.ts` (handle new response shape, interval type)
- Modify: `frontend/src/pages/IndexDetailPage.tsx` (unwrap .bars)
- Modify: `frontend/src/pages/IndicesPage.tsx` (unwrap .bars)
- Modify: `frontend/src/components/IndexExpandedPanel.tsx` (unwrap .bars if applicable)
- Modify: `frontend/src/i18n/fi.json` (new translations)
- Modify: `frontend/src/i18n/en.json` (new translations)

**Contracts:**

```typescript
// charts.ts updates
// Interval type widened to accept custom strings:
type Interval = "5m" | "15m" | "1H" | "2H" | "4H" | "8H" | "1D" | "3D" | "1W" | "2W" | string;

// Updated PERIOD_INTERVAL_MAP (standard presets only):
// "1m" (1-month period): ["5m", "15m", "1H", "4H", "1D"]
// "3m" period: ["15m", "1H", "4H", "1D"]
// "6m" period: ["1H", "4H", "1D", "1W"]
// "1y" period: ["4H", "1D", "1W"]
// "5y" period: ["1D", "1W"]

// New export: extra intervals for dropdown
export const EXTRA_INTERVALS: string[] = ["2H", "8H", "3D", "2W"];

// funds.ts
type FundType = "equity" | "bond" | "balanced";

// market.ts
interface IndexMeta {
  // ... existing fields
  currency?: string;  // new
}

interface OHLCVResponse {
  bars: OHLCVBar[];
  dataTransitionTimestamp?: number;
  lastUpdated?: number;
}

// client.ts
// getOHLCV now accepts string interval (not just Interval type) and returns OHLCVResponse
getOHLCV: (ticker: string, period?: Period, interval?: string) => Promise<OHLCVResponse>;
```

All callers of `api.getOHLCV()` updated to use `response.bars`:
- `IndexDetailPage.tsx`: `setOhlcv(data.bars)` instead of `setOhlcv(data)`
- `IndicesPage.tsx`: sparkline data from `data.bars`
- `IndexExpandedPanel.tsx`: if it calls getOHLCV, unwrap `.bars`

i18n additions:
- `group.balanced`: "Yhdistelmä" (fi) / "Balanced" (en)
- Interval labels for dropdown extras if not already present

**Constraints:**
- TypeScript compilation must pass with widened Interval type
- All getOHLCV callers must be updated — search for `getOHLCV` across frontend

**Verification:**
```bash
cd frontend && npx tsc --noEmit && npm run build
```

**Commit after passing.**

---

### Task 8: Interval Selector Rework
[Mode: Delegated]

**Files:**
- Modify: `frontend/src/components/IntervalSelector.tsx` + `.css`
- Modify: `frontend/src/pages/IndexDetailPage.tsx` (interval state type change)

**Contracts:**

```typescript
// IntervalSelector.tsx — new props
interface IntervalSelectorProps {
  period: Period;
  value: string;  // was Interval, now string to support custom
  onChange: (interval: string) => void;
}

// Three-tier layout:
// 1. Standard preset buttons: 5m, 15m, 1H, 4H, 1D, 1W
//    (constrained by PERIOD_INTERVAL_MAP — greyed out if not in current period's list)
// 2. Dropdown (<select> or custom dropdown) with extras from EXTRA_INTERVALS: 2H, 8H, 3D, 2W
//    (same constraint logic — disabled options if too few candles for period)
// 3. Free-form input: text field, validates on submit (Enter key or blur)
//    Client-side regex: /^[1-9]\d{0,2}[mHDW]$/
//    Server validates further; show error message on 400 response
```

**Behavior:**
- Selecting any option (preset, dropdown, or custom) calls onChange
- Active state shown on whichever tier contains the current interval
- Period change resets interval to period's default if current is a standard preset not in new period's list
- Custom intervals are NOT reset on period change (user chose them deliberately)

**Test Cases:**

```typescript
// Validation logic tests (can be in a separate util or inline)
test("validates correct intervals", () => {
  expect(isValidCustomInterval("5m")).toBe(true);
  expect(isValidCustomInterval("2H")).toBe(true);
  expect(isValidCustomInterval("999W")).toBe(true);
});

test("rejects invalid intervals", () => {
  expect(isValidCustomInterval("0m")).toBe(false);
  expect(isValidCustomInterval("1h")).toBe(false);  // lowercase
  expect(isValidCustomInterval("1000D")).toBe(false);
  expect(isValidCustomInterval("")).toBe(false);
});
```

**Constraints:**
- IndexDetailPage state: `interval` changes from `Interval` type to `string`
- The handlePeriodChange logic (line 55-64 in IndexDetailPage) needs updating for string interval type

**Verification:**
```bash
cd frontend && npx tsc --noEmit && npm run dev
# Visual: interval selector shows three tiers, custom input works, presets grey out correctly
```

**Commit after passing.**

---

### Task 9: Currency Labels & Data Transition Marker
[Mode: Direct]

**Files:**
- Modify: `frontend/src/components/IndexCard.tsx` (show currency)
- Modify: `frontend/src/pages/IndexDetailPage.tsx` (show currency, pass dataTransitionTimestamp to chart)
- Modify: `frontend/src/components/charts/PriceChart.tsx` (render transition marker)
- Modify: `frontend/src/components/TypeBadge.tsx` + `.css` (add balanced style)

**Contracts:**

Currency display:
- IndexCard: show currency code after price (e.g., "2,450.30 SEK")
- IndexDetailPage: show currency in header next to price

Data transition marker:
- PriceChart receives optional `dataTransitionTimestamp?: number` prop
- If present: render a vertical line at that timestamp using lightweight-charts markers or a custom series
- Subtle styling: dashed line, muted color, optional tooltip "Historical data before this point"

TypeBadge balanced:
- Add CSS class `type-badge--balanced` with appropriate color (distinct from equity green / bond blue)

**Constraints:**
- Currency display is informational only — no conversion logic
- Transition marker must not interfere with chart interaction (crosshair, zoom)
- If `dataTransitionTimestamp` is null/undefined, no marker rendered

**Verification:**
```bash
cd frontend && npx tsc --noEmit && npm run build
```

**Commit after passing.**

---

## Chunk 3: Integration & Deployment

### Task 10: Integration Testing & Deployment
[Mode: Direct]

**Files:**
- Modify: VPS `.env` (add `INVESTIQ_INDEX_REFRESH_INTERVAL=15` if not using default)

**Steps:**

1. Run full backend test suite:
```bash
cd backend && uv run pytest tests/ -v
```

2. Start backend locally, verify endpoints:
```bash
cd backend && uv run uvicorn app.main:app --port 8000
# In another terminal:
curl localhost:8000/api/indices | jq '.[0].currency'
curl localhost:8000/api/funds | jq 'length'  # should return 7
curl "localhost:8000/api/indices/%5EOMXH25/ohlcv?period=1y&interval=1D" | jq '.lastUpdated'
```

3. Build frontend:
```bash
cd frontend && npm run build
```

4. Deploy via `git deployboth`

5. Run backfill on VPS, then restart service to clear caches:
```bash
ssh vps "cd /var/www/investiq-backend && uv run python -m app.cli.backfill && sudo systemctl restart investiq"
```

6. Verify live:
- Index cards show currency labels
- Fund page shows 7 funds (including Varainhoito B)
- Euro Bond B shows ~37€ NAV
- Interval selector has three tiers (presets, dropdown, custom input)
- Custom interval (e.g., "2H") returns data
- Charts render with transition marker (after backfill data exists)

**Commit after passing.**

---

## Execution
**Skill:** superpowers:subagent-driven-development
- Mode A tasks (Direct): Tasks 1, 2, 7, 9, 10
- Mode B tasks (Delegated): Tasks 3, 4, 5, 6, 8
