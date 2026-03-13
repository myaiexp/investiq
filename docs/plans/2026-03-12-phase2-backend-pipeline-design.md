# Phase 2: Backend Pipeline & Real Data — Design

> Wire up real market data: yfinance fetching, PostgreSQL caching, FastAPI endpoints, replace mock API.

## Decisions

- **Data refresh**: In-process APScheduler (hourly) + manual POST `/api/refresh` endpoint
- **Indicator calculation**: Compute on fetch, store in DB. API endpoints just read.
- **Frontend swap**: Replace mock client with HTTP calls in-place, delete mock generators once confirmed
- **Period/interval support**: Full PERIOD_INTERVAL_MAP as-is (intraday included)
- **DB seeding**: App self-seeds indices/funds on startup from hardcoded ticker lists
- **Fund metrics**: Pull TER etc. from yfinance `.info` where available, calculate Sharpe/volatility/drawdown from NAV, hardcode what's missing
- **Deployment**: Straight to VPS, test against deployed version

## Data Pipeline Flow

```
App Startup
  ├─ Run Alembic migrations (ensure schema is current)
  ├─ Seed indices/funds if missing (hardcoded ticker lists)
  ├─ Trigger initial data fetch for any stale/missing data
  └─ Start APScheduler (hourly refresh cycle)

Hourly Refresh (APScheduler job)
  ├─ For each index ticker:
  │   ├─ Fetch OHLCV from yfinance (all supported periods/intervals)
  │   ├─ Upsert into ohlcv_data table
  │   ├─ Run pandas-ta on the OHLCV data (all 10 indicators)
  │   ├─ Store indicator series in indicator_data table
  │   └─ Compute signal per indicator + aggregate → signal_data table
  ├─ For each fund ticker:
  │   ├─ Fetch NAV history from yfinance
  │   ├─ Upsert into fund_nav table
  │   ├─ Fetch fund info (TER, etc.) from yfinance if available
  │   └─ Calculate performance metrics (Sharpe, volatility, drawdown) from NAV
  └─ Log results, record last_refreshed timestamp

Manual Refresh
  └─ POST /api/refresh → triggers the same job immediately
```

All computation at fetch time. API endpoints query postgres and return JSON.

## Database Schema

### Existing tables (tweaked)

**indices** — id, name, ticker (unique), region, price, daily_change, signal
- Added price, daily_change, signal for grid view without joining OHLCV

**ohlcv_data** — id, ticker, date, interval, open, high, low, close, volume, fetched_at
- Added `interval` column (UniqueConstraint: ticker + date + interval)

**funds** — id, name, ticker (unique), isin, fund_type, benchmark_ticker, benchmark_name, nav, daily_change, return_1y
- Added benchmark_name + summary fields for grid view

**fund_nav** — id, ticker, date, nav, fetched_at (unchanged)

### New tables

**indicator_data** — id, ticker, indicator_id, interval, date, series_key, value, fetched_at
- Flat row-per-point. ~500K rows for full dataset — trivial for postgres with indexes on (ticker, date, interval).

**signal_data** — id, ticker, indicator_id (nullable for aggregate), signal, computed_at
- One row per indicator per ticker + one aggregate row (indicator_id = null).

**fund_performance** — id, ticker, returns_1y, returns_3y, returns_5y, benchmark_returns_1y/3y/5y, volatility, sharpe, max_drawdown, ter, computed_at
- Denormalized, one row per fund, recalculated on refresh.

## API Endpoints

All under `/api/`, response shapes match frontend TypeScript types 1:1.

| Endpoint                       | Method | Response          | Notes                                                        |
| ------------------------------ | ------ | ----------------- | ------------------------------------------------------------ |
| `/indices`                     | GET    | `IndexMeta[]`     | From indices table                                           |
| `/indices/{ticker}/ohlcv`      | GET    | `OHLCVBar[]`      | Params: period, interval. Filtered by date range + interval  |
| `/indices/{ticker}/indicators` | GET    | `IndicatorData[]` | Params: period, interval. Grouped by indicator_id+series_key |
| `/indices/{ticker}/signal`     | GET    | `SignalSummary`    | Individual + aggregate from signal_data                      |
| `/funds`                       | GET    | `FundMeta[]`      | From funds table                                             |
| `/funds/{ticker}/performance`  | GET    | `FundPerformance` | From fund_performance table                                  |
| `/funds/{ticker}/nav`          | GET    | `FundNAVPoint[]`  | Param: period. Filtered by date range                        |
| `/refresh`                     | POST   | `{status, msg}`   | Triggers immediate refresh                                   |
| `/health`                      | GET    | `{status}`        | Already exists                                               |

CamelCase JSON via Pydantic alias config.

## Services Layer

**`services/fetcher.py`** — yfinance data fetching
- `fetch_index_ohlcv(ticker, period, interval)` → DataFrame
- `fetch_fund_nav(ticker, period)` → DataFrame
- `fetch_fund_info(ticker)` → dict (TER, metadata)
- Handles: missing volume, timezone normalization, rate limit backoff

**`services/indicators.py`** — pandas-ta calculations
- `calculate_indicators(ohlcv_df)` → dict of indicator_id → series data
- `generate_signal(indicator_id, series_data)` → buy/sell/hold
- `aggregate_signals(signals)` → majority vote

**`services/scheduler.py`** — refresh orchestration
- `refresh_all()` — main job: iterate tickers, fetch → compute → store
- `refresh_index(ticker, session)` — single index
- `refresh_fund(ticker, session)` — single fund
- APScheduler on startup + callable from `/api/refresh`

All services async, receive DB session from caller, no global state.

## Frontend Changes

- Replace `api/client.ts` mock implementation with HTTP calls (fetch/axios)
- Delete `data/mock/` directory once backend is confirmed working
- Keep the `Api` interface unchanged — same contract
