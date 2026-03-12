# InvestIQ Frontend Design

## Overview

Frontend-first build with mock data. Three-level progressive disclosure for both indices and funds. Dark financial theme, responsive from day one, Finnish primary language.

## Page Structure

### Header (shared)
- App logo + subtitle, nav links (Indeksit / Rahastot), language toggle (FI/EN)
- Sticky on desktop, fixed on mobile

### Index Dashboard (`/`)

**Level 1 — Overview grid:**
- 10 index cards in a grid (2 columns desktop, 1 column mobile)
- Grouped: Nordic (4) then Global (6) with subtle group labels
- Each card: index name, current price, daily % change (green/red), 30-day sparkline, signal badge (Osta/Myy/Pidä)

**Level 2 — Expanded panel:**
- Clicking a card expands an inline detail panel below it (pushes cards down)
- Medium candlestick chart (3 months default), top 3-4 key indicators with signals
- "Täysi analyysi" button navigates to full detail

**Level 3 — Full detail page (`/index/:ticker`):**
- Large interactive candlestick chart, full viewport width
- Two chart controls above the chart:
  - Time period pills: 1kk / 3kk / 6kk / 1v / 5v
  - Candlestick interval selector: dynamically constrained by period (see table below)
- Volume bar chart always visible below candlesticks
- Indicator toggle panel: sidebar on desktop, bottom drawer on mobile
  - Lists all 10 indicators as toggle switches
  - Each shows indicator name + current signal (color-coded dot)
  - Overlays (Bollinger, MAs, Ichimoku) draw on price chart
  - Oscillators (RSI, MACD, Stochastic, CCI, OBV, ATR) render as sub-charts below
- Signal summary card: aggregated verdict + breakdown of active indicators' individual signals
  - Updates live as indicators are toggled (only active ones count)

**Candlestick interval constraints:**

| Time Period | Available Intervals           |
| ----------- | ----------------------------- |
| 1M          | 1m, 5m, 15m, 1H, 2H, 4H, 1D |
| 3M          | 15m, 1H, 2H, 4H, 1D          |
| 6M          | 1H, 4H, 1D, 1W               |
| 1Y          | 4H, 1D, 1W                    |
| 5Y          | 1D, 1W                        |

Note: yfinance intraday data has retention limits (1m = 7 days, 5m/15m = 60 days, 1H = 730 days). Backend will enforce actual availability; UI greys out unavailable intervals.

### Funds Page (`/funds`)

Mirrors index dashboard structure — same card → panel → detail flow, deviates only for fund-specific features.

**Level 1 — Fund cards:**
- 6 cards grouped: Equity (4), Bond (2)
- Each card: fund name, type badge (Osake/Korko), NAV + daily % change, 1Y return % (prominent, color-coded), NAV sparkline, benchmark name

**Level 2 — Expanded panel:**
- NAV line chart with benchmark overlay (two lines)
- Performance table: 1Y / 3Y / 5Y returns for fund and benchmark
- Key metrics row: Volatility, Sharpe ratio, Max drawdown, TER
- "Täysi analyysi" button

**Level 3 — Full detail page (`/funds/:ticker`):**
- Large NAV chart with benchmark overlay, time period selector (1M–5Y, no candlestick intervals — NAV is daily)
- Full metrics panel
- Relative performance chart (fund return minus benchmark over time)
- Technical analysis on NAV curve: same toggleable indicators where applicable (MAs, RSI, Bollinger work; volume-based ones like OBV don't apply)

### Update Tracker Widget

- Floating pill, bottom-right corner
- Subtle pulse/badge on new updates
- Resting state shows latest update date
- Click to expand scrollable panel (~300px max) with recent updates (newest first)
- Data: `frontend/src/data/updates.json` — array of `{date, message_fi, message_en}`, respects active language
- Footer clearance: ~80px bottom padding on main content, smaller widget on mobile positioned away from thumb zone
- Future: widget stays in codebase — either repurposed (notifications, signal alerts) or kept as update tracker if product is handed off to the end user

## Technical Decisions

- **Styling**: Vanilla CSS with custom properties (dark financial theme). No Tailwind.
- **Charts**: TradingView Lightweight Charts for candlesticks and line charts. Sparklines as simple SVG/canvas.
- **Routing**: react-router-dom. `/` (indices), `/index/:ticker` (index detail), `/funds` (funds), `/funds/:ticker` (fund detail).
- **i18n**: react-i18next, Finnish primary, English secondary.
- **Mock data**: Separate `mock/` directory with realistic static data for all indices and funds. API client has a mock implementation that returns static data; swap for real API calls when backend is ready.
- **Cache busting**: Vite's content-hashed filenames preserved in production builds. No long-term caching on index.html.
- **Responsive**: Mobile and desktop are equal priorities. Charts full-width on mobile, indicator panel as bottom drawer, cards stack single-column.
