# InvestIQ Frontend Implementation Plan

**Goal:** Build the complete frontend dashboard with mock data — index overview grid, fund analysis, interactive charts with 10 toggleable technical indicators, and an update tracker widget. Deploy-ready.

**Architecture:** Three-level progressive disclosure (grid → expanded panel → full detail page) for both indices and funds. Chart rendering via TradingView Lightweight Charts v5. Mock data generated from seeded random walks. No state management library — React useState at page level. Vanilla CSS with custom properties.

**Tech Stack:** React 19, TypeScript, Vite 8, lightweight-charts 5.1, react-router-dom 7, react-i18next, vanilla CSS

---

### Task 1: TypeScript Types + Mock Data Layer [Mode: Delegated]

**Files:**
- Create: `frontend/src/types/index.ts` (barrel)
- Create: `frontend/src/types/market.ts` (Index, OHLCV, indicator, signal types)
- Create: `frontend/src/types/funds.ts` (Fund, NAV, performance types)
- Create: `frontend/src/types/charts.ts` (period/interval config, PERIOD_INTERVAL_MAP)
- Create: `frontend/src/data/mock/index.ts` (barrel)
- Create: `frontend/src/data/mock/indices.ts` (10 index metadata with real tickers)
- Create: `frontend/src/data/mock/funds.ts` (6 fund metadata with real tickers/ISINs)
- Create: `frontend/src/data/mock/generators.ts` (OHLCV + NAV + indicator data generators)
- Create: `frontend/src/data/mock/signals.ts` (pre-computed signals per index)
- Create: `frontend/src/data/updates.json` (initial update tracker entries)
- Modify: `frontend/src/api/client.ts` (add types, add mock implementation)

**Contracts:**

```typescript
// types/market.ts
type Signal = 'buy' | 'sell' | 'hold';
type Region = 'nordic' | 'global';
type Period = '1m' | '3m' | '6m' | '1y' | '5y';
type Interval = '1m' | '5m' | '15m' | '1H' | '2H' | '4H' | '1D' | '1W';
type IndicatorId = 'rsi' | 'macd' | 'bollinger' | 'ma' | 'stochastic' | 'obv' | 'fibonacci' | 'atr' | 'ichimoku' | 'cci';
type IndicatorCategory = 'overlay' | 'oscillator';

interface IndexMeta {
  name: string; ticker: string; region: Region;
  price: number; dailyChange: number; signal: Signal;
}

interface OHLCVBar {
  time: number; // unix seconds, matches lightweight-charts Time
  open: number; high: number; low: number; close: number; volume: number;
}

interface IndicatorMeta { id: IndicatorId; category: IndicatorCategory; signal: Signal; }

interface IndicatorData {
  id: IndicatorId;
  series: Record<string, { time: number; value: number }[]>;
  signal: Signal;
}

interface SignalSummary {
  aggregate: Signal;
  breakdown: IndicatorMeta[];
  activeCount: { buy: number; sell: number; hold: number };
}

// types/funds.ts
type FundType = 'equity' | 'bond';

interface FundMeta {
  name: string; ticker: string; isin: string | null;
  fundType: FundType; benchmarkTicker: string | null; benchmarkName: string;
  nav: number; dailyChange: number; return1Y: number;
}

interface FundNAVPoint { time: number; value: number; }

interface FundPerformance {
  returns: { '1y': number; '3y': number; '5y': number };
  benchmarkReturns: { '1y': number; '3y': number; '5y': number };
  volatility: number; sharpe: number; maxDrawdown: number; ter: number;
}

// types/charts.ts
interface PeriodConfig { id: Period; intervals: Interval[]; defaultInterval: Interval; }
```

**Mock data approach:** `generators.ts` uses seeded random walks from realistic base prices. Given a ticker + period + interval, produces OHLCV bars. Indicator values derived from simplified formulas (14-period RSI, 20-period Bollinger, etc.). Doesn't need to be financially exact — needs to look realistic in charts.

**Index tickers:** ^OMXH25, ^OMXS30, ^OMXC25, OBX.OL, ^GSPC, ^NDX, ^GDAXI, ^FTSE, ^N225, URTH
**Fund tickers:** 0P00000N9Y.F, 0P00015D0H.F, 0P0000CNVH.F, 0P00000N9R.F, 0P0001HOZS.F, 0P0001JWUW.F

**Constraints:**
- All types must be importable by every subsequent task
- Mock API must match the same interface as the real API client
- Generated OHLCV must have monotonically increasing timestamps, no NaN/negative prices

**Verification:** `cd frontend && npx tsc --noEmit && npm run build`

**Commit after passing.**

---

### Task 2: Shared UI Components [Mode: Direct]

**Files:**
- Create: `frontend/src/components/SparklineChart.tsx` + `.css` — SVG polyline sparkline (NOT a lightweight-charts instance — too heavy for 16 cards). Props: `data: {time: number; value: number}[]`, `width?`, `height?`, `color?`
- Create: `frontend/src/components/SignalBadge.tsx` + `.css` — Pill badge: Osta/Myy/Pidä with signal color. Props: `signal: Signal`
- Create: `frontend/src/components/PriceChange.tsx` + `.css` — Formatted % with arrow and green/red color. Props: `value: number`, `size?: 'sm' | 'md'`
- Create: `frontend/src/components/GroupLabel.tsx` + `.css` — Section header for card groups. Props: `children: string`
- Create: `frontend/src/components/CardGrid.tsx` + `.css` — CSS Grid: `repeat(auto-fill, minmax(340px, 1fr))`. Handles expanded card spanning full row.
- Create: `frontend/src/components/ExpandableCard.tsx` + `.css` — Card with expand/collapse. Props: `expanded`, `onClick`, `header: ReactNode`, `expandedContent: ReactNode`. Expanded = spans full grid row.
- Create: `frontend/src/components/TypeBadge.tsx` + `.css` — Fund type badge (Osake/Korko). Props: `fundType: FundType`
- Modify: `frontend/src/i18n/fi.json` + `en.json` — Add keys: group labels (Pohjoismaat, Maailma, Osake, Korko), "Täysi analyysi", metric labels, interval labels

**Constraints:**
- BEM-style class naming scoped by component
- All colors from CSS custom properties, no hardcoded values
- Responsive: cards stack single column below 720px
- SVG sparklines: normalize data to viewBox, stroke only, no fill

**Verification:** `cd frontend && npx tsc --noEmit && npm run dev` (visual check at 1440px and 375px)

**Commit after passing.**

---

### Task 3: Index Dashboard — Level 1 + Level 2 [Mode: Direct]

**Files:**
- Modify: `frontend/src/pages/IndicesPage.tsx` + create `IndicesPage.css` — Replace stub. Renders CardGrid with 10 IndexCards grouped Nordic/Global.
- Create: `frontend/src/components/IndexCard.tsx` + `.css` — Card header content: name, price (.number), PriceChange, SparklineChart, SignalBadge. Wraps in ExpandableCard.
- Create: `frontend/src/components/IndexExpandedPanel.tsx` + `.css` — Medium candlestick chart (3 months), top 3-4 indicator signals, Link to `/index/${ticker}` ("Täysi analyysi")
- Create: `frontend/src/components/MiniCandlestickChart.tsx` + `.css` — Simplified lightweight-charts wrapper: candlestick + volume, fixed 3-month period, no indicator overlays, resize-aware

**Contracts:**
- `IndicesPage` state: `expandedTicker: string | null`. Click card → set. Click again → clear. Click different → switch.
- IndexCard receives `IndexMeta` + 30-day close data for sparkline
- MiniCandlestickChart receives `OHLCVBar[]`, renders in a container div with `ResizeObserver`

**Verification:** `cd frontend && npx tsc --noEmit && npm run dev` — 10 cards in 2 groups, expand/collapse works, chart renders in panel

**Commit after passing.**

---

### Task 4: Funds Page — Level 1 + Level 2 [Mode: Direct]

**Files:**
- Modify: `frontend/src/pages/FundsPage.tsx` + create `FundsPage.css` — Replace stub. CardGrid with 6 FundCards grouped Equity/Bond.
- Create: `frontend/src/components/FundCard.tsx` + `.css` — Name, TypeBadge, NAV, PriceChange (daily), 1Y return (prominent), SparklineChart, benchmark name
- Create: `frontend/src/components/FundExpandedPanel.tsx` + `.css` — NAV line chart + benchmark overlay, PerformanceTable, MetricsRow, "Täysi analyysi" link
- Create: `frontend/src/components/PerformanceTable.tsx` + `.css` — Fund vs benchmark returns table (1Y/3Y/5Y). Props: `fundReturns`, `benchmarkReturns`, `benchmarkName`
- Create: `frontend/src/components/MetricsRow.tsx` + `.css` — Horizontal metric cards. Props: `metrics: FundPerformance`

**Contracts:**
- Same expand/collapse pattern as IndicesPage
- NAV chart in expanded panel: lightweight-charts with two `addLineSeries` calls (fund + benchmark), different colors

**Verification:** `cd frontend && npx tsc --noEmit && npm run dev` — 6 cards in 2 groups, NAV chart shows two lines

**Commit after passing.**

---

### Task 5: Full Chart + Indicator System [Mode: Delegated]

The most complex task. Self-contained chart system with multi-pane indicators.

**Files:**
- Create: `frontend/src/components/charts/PriceChart.tsx` + `.css` — Main chart component. Candlestick on pane 0, volume histogram on pane 0 (separate price scale). Props: `data: OHLCVBar[]`, `indicators: IndicatorData[]`, `enabledIndicators: Set<IndicatorId>`. Resize via ResizeObserver.
- Create: `frontend/src/components/charts/useChart.ts` — Hook: create chart on mount, handle resize, cleanup on unmount. Returns `{ chartRef, containerRef }`.
- Create: `frontend/src/components/charts/useIndicatorSeries.ts` — Hook: diffs enabled indicator set, adds/removes series and sub-panes incrementally (not recreating chart). Overlays → pane 0. Oscillators → own sub-panes.
- Create: `frontend/src/components/charts/indicatorRenderers.ts` — Pure functions returning series configs per indicator type:
  - Overlays (pane 0): Bollinger (3 lines), MAs (SMA50/200, EMA50/200), Ichimoku (5 series), Fibonacci (horizontal lines)
  - Oscillators (sub-panes): RSI (line + 30/70 levels), MACD (line + signal + histogram), Stochastic (%K/%D + 20/80), CCI (line + +/-100), OBV (line), ATR (line)
- Create: `frontend/src/components/charts/chartTheme.ts` — Colors matching CSS custom properties (--bg-card, --green, --red, etc.)
- Create: `frontend/src/components/PeriodSelector.tsx` + `.css` — Period pills (1kk–5v). Props: `value`, `onChange`.
- Create: `frontend/src/components/IntervalSelector.tsx` + `.css` — Interval selector constrained by period via PERIOD_INTERVAL_MAP. Greys out unavailable. Props: `period`, `value`, `onChange`.
- Create: `frontend/src/components/IndicatorPanel.tsx` + `.css` — Toggle list for all 10 indicators. Each shows name (i18n) + signal dot. Sidebar on desktop, prepared for drawer on mobile. Props: `indicators: IndicatorMeta[]`, `enabled: Set<IndicatorId>`, `onToggle`.
- Create: `frontend/src/components/SignalSummaryCard.tsx` + `.css` — Aggregate verdict + per-indicator breakdown. Updates as toggles change. Props: `summary: SignalSummary`.

**Constraints:**
- PriceChart is data-agnostic — receives data as props, does not fetch
- Sub-pane layout: main pane stretch ~0.6, each oscillator ~0.15. Max 7 panes if all oscillators active.
- `useIndicatorSeries` must diff previous/current enabled sets to avoid flickering on toggle

**Verification:** `cd frontend && npx tsc --noEmit && npm run dev` — render chart with mock data, toggle all indicators on/off individually

**Commit after passing.**

---

### Task 6: Detail Pages (Index + Fund) [Mode: Direct]

**Files:**
- Create: `frontend/src/pages/IndexDetailPage.tsx` + `.css` — Route: `/index/:ticker`. PriceChart + PeriodSelector + IntervalSelector + IndicatorPanel (sidebar desktop / drawer mobile) + SignalSummaryCard. Loads mock data by ticker.
- Create: `frontend/src/pages/FundDetailPage.tsx` + `.css` — Route: `/funds/:ticker`. NAVChart + benchmark overlay, PeriodSelector (no intervals), full metrics panel, RelativePerformanceChart, optional indicators on NAV.
- Create: `frontend/src/components/charts/NAVChart.tsx` + `.css` — Line variant of PriceChart. Two line series (fund + benchmark), no volume. Shares useChart hook.
- Create: `frontend/src/components/charts/RelativePerformanceChart.tsx` + `.css` — Area chart: fund return minus benchmark. Positive green, negative red. Uses baseline series.
- Create: `frontend/src/components/BottomDrawer.tsx` + `.css` — Mobile drawer for indicator panel. Slide up, drag handle, dimmed backdrop.
- Create: `frontend/src/components/BackButton.tsx` + `.css` — Navigate back to overview grid
- Modify: `frontend/src/App.tsx` — Add routes: `/index/:ticker` → IndexDetailPage, `/funds/:ticker` → FundDetailPage

**Responsive layout:**
- Desktop (≥1024px): Chart ~75% width, IndicatorPanel sidebar ~25% right
- Mobile (<1024px): Chart full width, IndicatorPanel in BottomDrawer via floating button, SignalSummaryCard below chart

**Verification:** `cd frontend && npx tsc --noEmit && npm run dev` — navigate to `/index/OMXH25` and `/funds/0P00000N9Y.F`, all controls work

**Commit after passing.**

---

### Task 7: Update Tracker + Final Polish [Mode: Direct]

**Files:**
- Create: `frontend/src/components/UpdateTracker.tsx` + `.css` — Floating pill bottom-right. Latest update date at rest. Click → scrollable panel (~300px max). Reads `src/data/updates.json`. Respects i18n language. Smaller on mobile, avoids thumb zone.
- Modify: `frontend/src/App.tsx` — Render `<UpdateTracker />` outside `<main>` (fixed position overlay)
- Modify: `frontend/src/App.css` — `padding-bottom: 80px` on `.main`. Sticky header on desktop.
- Modify: `frontend/index.html` — `<title>InvestIQ</title>`, `lang="fi"`

**Polish (bundled):**
- Sticky header: `position: sticky; top: 0; z-index: 100`
- Card expand/collapse CSS transitions (max-height or grid-template-rows animation)
- Drawer slide-up transition (transform: translateY)
- Mobile nav: simplify at small viewports if needed
- Crosshair tooltip verification on charts

**Verification:** `cd frontend && npx tsc --noEmit && npm run build && npm run preview` — full production build, verify all pages, widget, mobile layout, cache-busted asset filenames in dist/

**Commit after passing.**

---

## Execution
**Skill:** superpowers:subagent-driven-development
- Mode A tasks (2, 3, 4, 6, 7): Opus implements directly
- Mode B tasks (1, 5): Dispatched to subagents
