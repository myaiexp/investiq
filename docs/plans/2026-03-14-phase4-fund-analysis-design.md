# Phase 4: Fund Analysis Depth — Design

> Technical indicators on fund NAV curves + fund-to-fund comparison view.

## Feature 1: TA Indicators on Fund NAV

### OHLCV Proxy Strategy

Fund NAV data is a single daily price — no Open/High/Low/Volume. To reuse the existing generic indicator engine (`calculate_indicators`), we construct a proxy DataFrame:

- Open = High = Low = Close = NAV
- Volume = 0

**Decision:** Proxy approach with indicator filtering. Alternatives considered:

| Approach | Description | Verdict |
| --- | --- | --- |
| **A) Proxy + filter (chosen)** | Set O=H=L=C=NAV, expose only indicators that produce meaningful output | Reuses existing engine, curated UX |
| B) Close-only subset | Only run indicators that use Close internally | Requires forking indicator engine or adding Close-only mode |
| C) Benchmark OHLCV hybrid | Use benchmark ETF OHLCV for range-based indicators | Confusing — mixes data sources in same view |

**Why A:** The indicator engine is generic and tested. Proxying lets us pass data through unchanged. The filtering happens at a higher level (which indicators to compute and display), not inside the engine. If the proxy approach proves suboptimal for specific indicators, we can revisit B or C without architectural changes.

### Fund-Eligible Indicators

| Indicator | Works on NAV? | Reason |
| --- | --- | --- |
| RSI | Yes | Pure close-based momentum |
| MACD | Yes | EMA of close prices |
| MA | Yes | SMA of close prices |
| CCI | Yes | Uses close (H=L=C makes typical price = close) |
| Bollinger | Yes | Rolling std dev of close — bands show meaningful spread |
| Stochastic | No | Degenerate (H=L=C locks %K at extremes) |
| ATR | No | Zero output (H-L=0 every day) |
| Fibonacci | No | Needs real intraday range |
| Ichimoku | No | Cloud collapses (conversion/base lines identical) |
| OBV | No | No volume data |

Defined as `FUND_INDICATORS = {"rsi", "macd", "ma", "cci", "bollinger"}` in the backend.

### Backend

**No new models.** Existing `IndicatorData` and `SignalData` tables store by `ticker` + `interval` — work for both indices and funds.

**On-the-fly computation** instead of pre-computing in the scheduler:

- Fund NAV is daily-only (~250 points/year, ~1250 for 5Y)
- Computing 5 indicators on that takes milliseconds
- Avoids scheduler complexity; data is always fresh with latest NAV

**Date type conversion:** `FundNAV.date` is `sqlalchemy.Date` (Python `date`), but `calculate_indicators()` expects a `pd.DatetimeIndex`. The proxy DataFrame builder must convert `date` → `datetime` (midnight UTC, tz-aware) to match the existing `IndicatorData.date` which is `DateTime(timezone=True)`.

**New endpoints on the funds router:**

```
GET /funds/{ticker}/indicators?period=1y
```

- Fetches FundNAV rows for the period
- Converts `date` to UTC midnight `datetime`, builds proxy OHLCV DataFrame (O=H=L=C=NAV, Volume=0)
- Calls `calculate_indicators()`, filters output to `FUND_INDICATORS` keys only
- Generates per-indicator signals via `generate_signal()`
- Populates `category` from `INDICATOR_CATEGORIES` (same lookup as index routes, from `seed.py`)
- Returns `list[IndicatorDataResponse]` (same schema as index indicators)

```
GET /funds/{ticker}/signal
```

- Computes indicators for full available NAV history (typically ~1250 points for 5Y — fast enough for on-the-fly)
- Aggregates signals via `aggregate_signals()`
- Populates breakdown with `category` from `INDICATOR_CATEGORIES`, filtered to `FUND_INDICATORS`
- Returns `SignalSummaryResponse` (same schema as index signals)

**Shared constants:** Extract `PERIOD_DAYS` dict to a shared location (e.g., `app/core/constants.py`) since it's duplicated between `indices.py` and `funds.py` and this phase adds another consumer.

### Frontend

**FundDetailPage additions:**

- `IndicatorPanel` component (already exists, used by IndexDetailPage) — filtered to `FUND_INDICATORS`
- `useIndicatorSeries` hook wired to NAVChart for overlay/oscillator pane management
- `SignalSummaryCard` component for aggregate signal display
- New API client methods: `getFundIndicators(ticker, period)`, `getFundSignal(ticker)`

**NAVChart refactor required:**

- Currently renders a single `LineSeries` and destroys/recreates the chart on every data change (the `useEffect` returns `chart.remove()` in cleanup, re-runs when `fundData`/`benchmarkData` change)
- `useIndicatorSeries` needs a stable chart reference — if the chart is destroyed on period change, the hook loses all its series references
- **Refactor:** Separate chart creation (once, on mount) from data updates (on prop changes). Update the NAV LineSeries data in place rather than recreating the chart. This matches how PriceChart works for indices and is required before `useIndicatorSeries` can be connected.
- Once the chart instance is stable, `useIndicatorSeries` adds overlay series (MA, Bollinger) to the main pane and oscillators (RSI, MACD, CCI) to sub-panes below — same mechanism as PriceChart on index detail

**Filtering is data-driven:** The API only returns indicators in `FUND_INDICATORS`. `IndicatorPanel` receives `indicators: IndicatorMeta[]` from the API response, so it automatically only shows eligible indicators — no frontend filtering logic needed. The `useIndicatorSeries` hook's internal `OSCILLATOR_ORDER` array includes all 10 indicators but only processes those actually present in the data, so excluded indicators are harmless.

## Feature 2: Fund Comparison View

### Routing & Navigation

**Route:** `/funds/compare?tickers=TICKER1,TICKER2,...`

Tickers in URL search params — bookmarkable and shareable.

**Entry points:**

1. **Fund grid (FundsPage):** Checkbox on each fund card. When 2+ selected, a "Compare" button appears. Clicking navigates to comparison page with pre-selected tickers.
2. **Comparison page standalone:** Fund selector widget to add/remove funds directly on the page.

### Page Layout

```
┌─────────────────────────────────────────────────────┐
│  Fund Selector (add/remove, max ~5)  │  Period: [1m 3m 6m 1y 5y]  │
├─────────────────────────────────────────────────────┤
│                                                     │
│  Multi-line % Change Chart                          │
│  (normalized from period start)                     │
│  Legend: Fund A ── Fund B ── Fund C ──              │
│                                                     │
├ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─┤
│  [Oscillator panes, hidden by default]              │
│  RSI: Fund A ── Fund B ── Fund C ──                │
├─────────────────────────────────────────────────────┤
│  Performance Comparison Table                       │
│  Metric      │ Fund A  │ Fund B  │ Fund C          │
│  Return 1Y   │  12.3%  │   8.1%  │  15.7%          │
│  Volatility  │   0.14  │   0.09  │   0.18          │
│  Sharpe      │   0.87  │   0.90  │   0.87          │
│  ...         │   ...   │   ...   │   ...           │
└─────────────────────────────────────────────────────┘
```

### Indicators on Comparison View

- **Off by default.** IndicatorPanel available but collapsed.
- **Oscillators only** (RSI, MACD, CCI): one line per fund, color-matched to NAV lines.
- **Overlays (MA, Bollinger) deferred:** multiple sets of overlay bands on a multi-fund chart creates too much visual noise. Noted for future expansion if users want it.
- **Scale note:** With 5 funds and MACD (3 sub-series each: line, signal, histogram), a single oscillator pane could have 15 series. At 2-3 funds this is fine; at 5 it gets dense. The UI should work but may warrant a visual density warning or fund count advisory in practice.

**Decision:** Oscillators per fund now, overlay expansion later. The indicator panel filters to oscillator-only indicators on the comparison page.

**Indicator management:** `ComparisonChart` gets its own indicator rendering logic rather than reusing `useIndicatorSeries` directly. The existing hook assumes a single-ticker chart (one set of series per indicator). The comparison chart needs N sets of series per indicator (one per fund), each color-matched. A new `useComparisonIndicators` hook or inline logic in `ComparisonChart` handles this.

### Shared Period Selector

All funds share a single period selector. Comparing funds over different time windows would be misleading. The chart normalizes all NAV curves to % change from the first date where all selected funds have data.

### Backend

**No new endpoints.** The comparison page fetches existing endpoints in parallel per fund:

- `GET /funds/{ticker}/nav?period=X` (existing)
- `GET /funds/{ticker}/performance` (existing)
- `GET /funds/{ticker}/indicators?period=X` (new from Feature 1)

No server-side comparison logic — the frontend handles normalization and multi-fund rendering.

### Frontend Components

**New:**

- `FundComparisonPage` — route handler, manages selected funds + period state
- `ComparisonChart` — multi-line normalized % change chart with optional oscillator panes
- `ComparisonTable` — side-by-side metrics (reuses `FundPerformance` data)
- `FundSelector` — add/remove funds widget on comparison page

**Modified:**

- `FundsPage` — add compare checkbox + "Compare selected" button
- `App.tsx` — add `/funds/compare` route
- `api/client.ts` — add `getFundIndicators`, `getFundSignal` methods
- `types/funds.ts` — add comparison-related types if needed
- `i18n/fi.json` + `en.json` — comparison page translations

## Data Flow Summary

```
Fund Detail Page (single fund TA):
  FundNAV rows → proxy OHLCV DataFrame → calculate_indicators() → filter to FUND_INDICATORS
  → generate signals → API response → useIndicatorSeries on NAVChart

Fund Comparison Page:
  Selected tickers → parallel fetch (NAV + perf + optional indicators) per fund
  → normalize to % change from shared start date → multi-line chart + metrics table
  → toggle oscillator → color-matched lines per fund in sub-pane
```
