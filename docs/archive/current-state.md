# InvestIQ — Current Implementation State

> Compare this against the original spec to identify gaps, deviations, and missing features.

## Core Sections

### Index Dashboard — IMPLEMENTED

Tracks 10 indices with full technical analysis:

- **Nordic:** OMXH25 (Helsinki), OMXS30 (Stockholm), OMXC25 (Copenhagen), OBX (Oslo)
- **Global:** S&P 500, NASDAQ-100, DAX 40, FTSE 100, Nikkei 225, MSCI World (via URTH ETF proxy)

**Three-level disclosure:**

1. **Grid cards** — name, live price, daily change %, signal badge (buy/sell/hold), sparkline (1-month)
2. **Expanded card** — mini candlestick chart + top indicator signal dots + "Full Analysis" link
3. **Detail page** — full interactive candlestick chart with volume, toggleable indicator overlays/sub-panes, period selector (1m/3m/6m/1y/5y), interval selector (1m–1W with per-period availability), indicator panel with on/off toggles, signal summary with aggregate verdict + per-indicator breakdown

### Technical Indicators — ALL 10 IMPLEMENTED

All calculated server-side using pandas-ta, stored in PostgreSQL, served via API:

| # | Indicator                    | Type       | Signal logic                                         |
| - | ---------------------------- | ---------- | ---------------------------------------------------- |
| 1 | RSI (14)                     | Oscillator | <30 buy, >70 sell                                    |
| 2 | MACD (12,26,9)               | Oscillator | MACD > signal = buy, < signal = sell                 |
| 3 | Bollinger Bands (20,2)       | Overlay    | Close < lower = buy, > upper = sell                  |
| 4 | Moving Averages              | Overlay    | SMA50/200 golden cross = buy, death cross = sell     |
| 5 | Stochastic (14,3,3)          | Oscillator | K < 20 = buy, K > 80 = sell                         |
| 6 | OBV                          | Oscillator | 5-day monotonic trend (rising = buy, falling = sell) |
| 7 | Fibonacci Retracement        | Overlay    | Near support = buy, near resistance = sell           |
| 8 | ATR (14)                     | Oscillator | No directional signal (volatility only → hold)       |
| 9 | Ichimoku Cloud (9,26,52)     | Overlay    | Price above cloud = buy, below = sell                |
| 10| CCI (20)                     | Oscillator | < -100 = buy, > 100 = sell                          |

Aggregate signal: majority vote across all active indicators. Ties → hold. Fully transparent — every indicator's individual signal is visible in the UI.

**Frontend rendering:** Overlays draw on the main price chart pane; oscillators get their own sub-panes below. Indicator series are managed incrementally (add/remove without chart recreation).

### Ålandsbanken Fund Analysis — IMPLEMENTED

6 funds configured:

| Fund                      | Type   | Benchmark            |
| ------------------------- | ------ | -------------------- |
| ÅAB Europa Aktie B        | Equity | EURO STOXX 50        |
| ÅAB Norden Aktie EUR      | Equity | OMXH25               |
| ÅAB Global Aktie B        | Equity | MSCI World (URTH)    |
| ÅAB Euro Bond A           | Bond   | None                 |
| ÅAB Green Bond ESG C      | Bond   | None                 |
| ÅAB Nordiska Småbolag B   | Equity | OMXS30               |

**Per fund:**

- NAV chart (line) with benchmark overlay when available — both normalized to % change
- Relative performance chart (green/red fill showing fund outperformance vs benchmark)
- Performance table: 1y/3y/5y returns for fund + benchmark side-by-side
- Metrics: volatility (%), Sharpe ratio, max drawdown (%), TER (%)
- Expandable card view with mini chart + metrics summary
- Period selector (1m–5y)

**Not applied to funds:** Technical indicators and buy/sell/hold signals. Funds only have NAV data (no OHLCV/volume), so most TA indicators can't be applied. The spec said "apply technical analysis to NAV curves where it makes sense" — currently no TA is applied to funds.

### Missing funds from spec

The original spec listed 5 funds:

- ÅAB Finland (equity, benchmark OMXH25) — **NOT in app** (replaced by ÅAB Norden Aktie EUR)
- ÅAB Nordic (equity, benchmark MSCI Nordic) — **NOT in app** (replaced by ÅAB Nordiska Småbolag B)
- ÅAB Europe (equity) — **IN APP** as ÅAB Europa Aktie B
- ÅAB Obligaatio (bond) — **NOT in app** (replaced by ÅAB Euro Bond A + ÅAB Green Bond ESG C)
- ÅAB Balanced (mixed allocation) — **NOT in app**

So the current fund selection diverged from the spec. There are 6 funds instead of 5, with different specific picks. The ÅAB Balanced mixed allocation fund is entirely absent.

## Market Data — IMPLEMENTED

- **Source:** yfinance (Yahoo Finance) for all indices + funds (Morningstar tickers for funds)
- **Storage:** PostgreSQL on db.mase.fi — OHLCV, NAV, indicators, signals, performance metrics all cached
- **Refresh:** APScheduler, configurable interval (default 60 minutes), runs on backend startup + hourly
- **Current limitation:** Only 1y/1D OHLCV is fetched per refresh cycle. The full period/interval matrix is defined but not populated — shorter intervals (1m, 5m, 15m, 1H, etc.) will return empty results from the API even though the UI shows the selectors.

## Data Storage — IMPLEMENTED

PostgreSQL on db.mase.fi with 7 tables: indices, ohlcv_data, funds, fund_nav, indicator_data, signal_data, fund_performance.

**Not implemented:** User preferences storage. The spec mentioned storing "selected indices, active indicators, notification settings." Currently there is no user model, no authentication, and no persisted preferences. Active indicator selections reset on page reload.

## UI — IMPLEMENTED

- **Dark theme:** Professional financial aesthetic (slate/zinc palette, green/red signal colors)
- **Bilingual:** Finnish primary, English secondary. Language toggle in header. Covers all UI text.
- **Mobile-responsive:** Desktop sidebar for indicators, mobile bottom drawer via floating button. Breakpoints at 720px and 1024px.
- **Charts:** TradingView Lightweight Charts v5 — candlestick + volume + indicator overlays/sub-panes
- **Additional UI:** In-app update tracker (floating pill with pulsing dot for new entries, updates + changelog tabs)

## Signal Logic — IMPLEMENTED

Transparent majority vote as spec requested. Aggregate + per-indicator breakdown both visible in UI. Not a black-box — user can see exactly what each indicator says and how they combine.

## Nice-to-haves from Spec

| Feature                                    | Status          |
| ------------------------------------------ | --------------- |
| Push notifications for signal changes      | NOT implemented |
| ML-based short-term price prediction       | NOT implemented |
| Swedish language support                   | NOT implemented |
| Fund-to-fund comparison charts side by side | NOT implemented |

## Additional Features NOT in Original Spec

These were added during development:

- **Sparkline charts** on grid cards (mini preview before expanding)
- **Three-level progressive disclosure** (grid → expanded → full detail)
- **Update tracker widget** (floating pill with changelog from git commits)
- **Relative performance chart** for funds (green/red fill showing outperformance)
- **Period + interval selectors** with constraint logic (only shows valid intervals per period)
- **Signal badges** on index grid cards (instant overview without expanding)

## Summary of Gaps

1. **Fund selection diverged** — different specific funds than spec, missing ÅAB Finland, ÅAB Balanced
2. **No TA on fund NAV curves** — spec said "where it makes sense," currently none applied
3. **No user preferences** — no auth, no saved indicator selections, no watched indices
4. **No notifications** — no push notifications for signal changes
5. **Sub-daily data not fetched** — interval selectors exist in UI but only 1D data is actually populated
6. **No ML prediction** — spec acknowledged this as a v1 skip
7. **No Swedish** — only fi/en
8. **No fund-to-fund comparison** — individual fund pages only, no side-by-side
