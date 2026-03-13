# Phase 3: Data Completeness & Source Diversification — Design

> Fix broken data, fill gaps, rework the data pipeline to accumulate 1m candles as the single source of truth for all intervals.

## Overview

Phase 3 has two halves: (1) straightforward seed data fixes (ticker swaps, new fund, benchmarks, currency), and (2) a data pipeline rework that changes how OHLCV data is fetched, stored, and served. The pipeline rework replaces "fetch pre-made candles at multiple intervals" with "fetch 1m candles, aggregate everything else."

## Research Findings (2026-03-13)

Full details in `docs/investiq-datasources.md`. Key outcomes:

- **yfinance stays as sole data source.** Twelve Data requires $29/mo for Nordic exchanges. Finnhub has no index-level Nordic data. Neither justifies adding.
- **Euro Bond NAV:** Not broken — `0P00000N9R.F` is the A class (distribution, ~16€). B class is `0P00000N9Q.F` (~37€). All other ÅAB funds already use B class. Simple ticker swap.
- **ÅAB Balanced:** Exists as "Varainhoito B", ticker `0P00001CPE.F`, ISIN FI0008809934. 245 data points/yr. No formal benchmark.
- **Benchmark ETF proxies found:** MSCI Europe → `IEUR`, Bloomberg Euro Aggregate Bond → `SYBA.DE`, Bloomberg Euro Green Bond → `GRON.DE`. All verified on yfinance.

---

## 1. Seed Data & Ticker Changes

### Fund updates

| Fund | Change | Old | New |
|---|---|---|---|
| Euro Bond | Swap to B class | `0P00000N9R.F` "ÅAB Euro Bond A" | `0P00000N9Q.F` "ÅAB Euro Bond B" |
| Euro Bond | Add benchmark | NULL | `SYBA.DE` "Bloomberg Euro Aggregate Bond" |
| Green Bond ESG C | Add benchmark | NULL | `GRON.DE` "Bloomberg Euro Green Bond" |
| Europa Aktie B | Fix benchmark | `^STOXX50E` "EURO STOXX 50" | `IEUR` "MSCI Europe" |
| Varainhoito B | New fund | — | `0P00001CPE.F`, ISIN FI0008809934, type "balanced", no benchmark |

After these changes: 7 funds total in `SEED_FUNDS` (6 existing + Varainhoito appended).

### Index updates

Add `currency` field to Index model:

| Index | Currency |
|---|---|
| OMXH25 | EUR |
| OMXS30 | SEK |
| OMXC25 | DKK |
| OBX | NOK |
| S&P 500 | USD |
| NASDAQ-100 | USD |
| DAX 40 | EUR |
| FTSE 100 | GBP |
| Nikkei 225 | JPY |
| MSCI World (URTH) | USD |

### Migration logic

Same pattern as existing OMXS30 ticker migration: `seed_database()` runs ticker/name/benchmark renames before inserts. Existing DB rows get corrected without a manual migration.

### Data notes cleanup

After ticker/benchmark changes, remove obsolete entries:
- `FUND_DATA_NOTES`: remove `0P00000N9R.F` entry (Euro Bond A NAV warning — obsolete after B class swap)
- `FUND_BENCHMARK_NOTES`: remove `0P00000N9R.F` and `0P0001HOZS.F` entries (both now have benchmarks)

### Frontend type update

Add `"balanced"` to `FundType` union in `frontend/src/types/funds.ts` (currently `"equity" | "bond"`).

---

## 2. Schema Migration

### OHLCVData: Date → DateTime

The current `OHLCVData.date` column is `Date` type — cannot store multiple intraday candles on the same day. Must migrate to `DateTime(timezone=True)` to support 1m candles.

**Migration steps:**
1. Add new column `timestamp: DateTime(timezone=True)`
2. Populate from existing `date` column (set time to 00:00 UTC for existing daily rows)
3. Drop old `date` column, rename `timestamp` → `date` (or keep as `timestamp` — naming TBD during implementation)
4. Update unique constraint from `(ticker, date, interval)` to `(ticker, timestamp, interval)`

Same migration needed for `IndicatorData.date` → `DateTime(timezone=True)`.

### Interval column width

`OHLCVData.interval` and `IndicatorData.interval` are `String(5)`. Custom intervals are capped at max 999 of any unit (see section 3), so longest value is `999W` (4 chars). `String(5)` is sufficient.

### Index.currency

Add `currency: Mapped[str] = mapped_column(String(3), nullable=True)` to Index model.

---

## 3. Data Pipeline Rework

### Core concept

1m candles are the atomic unit. All larger intervals (5m, 15m, 1H, 4H, 1D, 1W) are aggregated from stored 1m data. This gives us:
- Arbitrary interval support (any grouping of 1m bars)
- Accumulating historical depth independent of yfinance retention
- A single fetch target (1m) instead of multiple interval-specific fetches

### One-time backfill

Fetch maximum available history at each interval from yfinance. This populates history from before we started collecting 1m data.

| Interval | yfinance period | Expected depth |
|---|---|---|
| 1m | 7d | ~7 days |
| 5m | 60d | ~60 days |
| 15m | 60d | ~60 days |
| 1H | 730d | ~2 years |
| 4H | max | years (varies) |
| 1D | max | decades |
| 1W | max | decades |

**Execution:**
- **CLI management command only** (not an HTTP endpoint) — avoids accidental triggers. e.g., `uv run python -m app.cli.backfill`
- Sequential per index with ~2s delays between yfinance calls
- Estimated runtime: 5-15 minutes for all 10 indices × 7 intervals (70 calls, some large downloads)
- Lock file prevents concurrent runs
- Idempotent — upserts into existing rows, safe to re-run
- After backfill: pre-compute indicators for standard intervals (trailing 2 years of data, not full history)

### Ongoing fetch (every 15 min)

- Fetch 1m data for all 10 indices (7-day window from yfinance, upsert into DB)
- This is the only recurring OHLCV fetch for indices
- 10 yfinance calls per cycle (40/hr) — well within practical ~2000/hr rate limit
- Fund NAV stays on hourly cycle (daily NAV only, no intraday for mutual funds)

**Error handling:**
- Partial yfinance responses: upsert whatever we get. Partial data is better than no data.
- Per-ticker failures: catch, log, continue to next ticker (existing pattern).
- Consecutive failures: after 3 consecutive failed refreshes for any ticker, set a `stale` flag on the index record. Frontend can show a staleness indicator.
- yfinance downtime: the scheduler just keeps trying every 15 min. No exponential backoff needed — the calls are cheap and non-blocking.

### Scheduler structure

Two jobs:
- **Every 15 min:** fetch 1m OHLCV for 10 indices, aggregate to standard intervals, pre-compute indicators
- **Every 60 min:** fetch daily NAV for 7 funds + benchmark ETFs, recalculate fund performance metrics

---

## 4. Aggregation Engine

New service: `services/aggregator.py`

### Interface

```python
def aggregate_candles(bars_1m: list[OHLCVBar], interval: str) -> list[OHLCVBar]:
    """Aggregate 1m bars into candles of any interval.

    interval: string like '5m', '1H', '4H', '1D', '1W', or custom ('2H', '3D', '45m')
    """
```

### Aggregation logic per group

- **Open:** first bar's open
- **High:** max of all highs
- **Low:** min of all lows
- **Close:** last bar's close
- **Volume:** sum of all volumes

### Grouping

Align to interval boundaries in UTC:
- Minutes: align to clock minutes (e.g., 15m → :00, :15, :30, :45)
- Hours: align to midnight UTC (e.g., 4H → 00:00, 04:00, 08:00, 12:00, 16:00, 20:00)
- Days: calendar days (UTC)
- Weeks: ISO weeks (Monday start)

**Timezone note:** UTC alignment means hourly candle boundaries don't match exchange trading hours (Helsinki trades 10:00-18:25 EET, Tokyo 09:00-15:30 JST, etc.). This is the standard approach for multi-market dashboards — exchange-local alignment would require per-index timezone logic and make cross-market comparison harder. UTC is what TradingView uses for multi-market views. Outside-hours candles with zero volume are naturally excluded since no 1m bars exist for those times.

### Custom interval validation

Format: positive integer (1-999) followed by m/H/D/W. Case-sensitive (uppercase H/D/W, lowercase m).

- Valid: `5m`, `2H`, `4H`, `3D`, `2W`, `45m`, `999W`
- Invalid: `0m`, `1h` (lowercase), `1000D` (over 999), `1M` (month not supported), empty string
- `1m` as a custom request short-circuits to raw 1m data (no aggregation)
- Rejected if the interval would produce fewer than 10 candles for the selected period

### Hybrid data serving

For any API request:
1. Query the earliest 1m row for the requested ticker (cached per-ticker after first lookup, invalidated on backfill)
2. For dates after the 1m start date → aggregate from 1m data
3. For dates before the 1m start date → serve backfilled pre-aggregated data from `ohlcv_data`
4. Stitch the two together in the response

**Transition point:** stored as a lightweight cache (dict in memory, populated on first query per ticker). The API response includes a `dataTransitionTimestamp` field so the frontend knows where to draw the boundary marker.

**Gaps in 1m data** (yfinance was down): show as missing candles in the aggregated output. Don't fall back to backfilled data for recent gaps — that would mix data sources confusingly.

**Indicators spanning the transition boundary** (e.g., SMA-200 where 190 days are backfilled and 10 are aggregated): compute from the stitched OHLCV data. The candle values are the same regardless of source — the indicator math doesn't care whether the candle was pre-aggregated or built from 1m bars.

### Data freshness

API responses include a `lastUpdated` timestamp (latest fetched_at for the requested ticker). Frontend can display "Last updated: 14:30 UTC" and distinguish between "market closed, data current" and "fetch failing, data stale."

---

## 5. Indicator Pre-computation

### Standard intervals

After each 15-min 1m fetch, aggregate to standard intervals and compute all 10 indicators:

**Standard presets:** 5m, 15m, 1H, 4H, 1D, 1W

Pre-computed indicators stored in `indicator_data` table (existing schema, just more interval values). Signals recomputed and stored in `signal_data`.

After backfill: compute indicators for standard intervals on trailing 2 years of data (not full history — decades of daily RSI is not useful and would be slow).

### Custom intervals

When a custom interval is requested (e.g., `2H`, `45m`):
1. Aggregate 1m data to the custom interval
2. Compute indicators on the fly
3. Return without storing (not worth caching one-off intervals)

### Index summary signals

The index grid cards show aggregate signals. These are based on the 1D interval indicators (unchanged from current behavior).

---

## 6. Frontend Changes

### Interval selector rework

Replace current interval selector with three tiers:

1. **Standard preset buttons:** 5m, 15m, 1H, 4H, 1D, 1W
2. **Dropdown with extras:** 2H, 8H, 3D, 2W (and other common alternatives)
3. **Free-form input:** text field below, validates format (number + m/H/D/W)

### Period/interval constraint mapping

| Period | Available Standard Intervals |
|---|---|
| 1M | 5m, 15m, 1H, 4H, 1D |
| 3M | 15m, 1H, 4H, 1D |
| 6M | 1H, 4H, 1D, 1W |
| 1Y | 4H, 1D, 1W |
| 5Y | 1D, 1W |

Note: 1m candles are excluded from presets (1M period × 1m interval = ~117K candles, too heavy for charts). Available via custom input if someone really wants it.

Custom intervals follow the same constraint logic — rejected if they'd produce fewer than ~10 candles for the selected period.

Greyed-out presets where insufficient accumulated data exists, with tooltip explaining why.

### Historical data boundary

Subtle visual marker on the chart where data transitions from backfilled to aggregated-from-1m. Uses `dataTransitionTimestamp` from the API response. Informational only — a faint vertical line or small label.

### Currency labels

Display currency code next to price on index cards and detail pages. Data comes from new `currency` field in API response.

### Fund pages

No interval selector — funds are daily-only. No changes needed beyond adding "balanced" to FundType.

---

## 7. Table Growth Estimate

With 10 indices × 1m candles × ~390 bars/trading day = ~3,900 rows/day for 1m data. ~1.4M rows/year. Plus backfilled history (decades of daily data ≈ ~60K rows). The `ohlcv_data` table will reach a few million rows within a year. PostgreSQL handles this fine with proper indexes on `(ticker, interval, timestamp)`. Partitioning can be considered later if query performance degrades.

---

## 8. What's NOT in Phase 3

- Real-time WebSocket streaming (Phase 5)
- Swedish language (Phase 6)
- Fund-to-fund comparison view (Phase 4)
- TA on fund NAV curves (Phase 4)
- Authentication / user preferences (Phase 7)
- ML prediction (Phase 8)
- Benchmark ETF backfill / intraday benchmark data (not needed for fund comparison which is daily-only)
