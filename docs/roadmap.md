# InvestIQ — Roadmap

> Derived from the Finnish spec (investiq-spec.md), gap analysis, and verified against deployed code as of 2026-03-13.

## Completed

**Phase 1 — Frontend Dashboard** ✅ Deployed
Three-level progressive disclosure, all 10 indicators with chart rendering, dark financial theme, FI/EN i18n, TradingView Lightweight Charts v5, responsive layout.

**Phase 2 — Backend Pipeline & Real Data** ✅ Deployed
yfinance fetching (10 indices + 6 funds), pandas-ta indicator calculations, PostgreSQL storage, APScheduler hourly refresh, FastAPI endpoints, VPS deployment at mase.fi/investiq. Includes: OMXS30 ticker fix (`^OMX`), display name clarifications (URTH, OBX TR), fund return calculation fix (calendar years), data quality notes API (`dataNote`/`dataNotes` fields).

**Phase 3 — Data Completeness & Source Diversification** ✅ Deployed
Schema migration (Date→DateTime for intraday), 1m candle pipeline with aggregation to all standard intervals, backfill CLI (254K rows), Euro Bond B ticker swap, 3 new benchmarks (IEUR, SYBA.DE, GRON.DE), Varainhoito B fund, currency labels, three-tier interval selector (presets + dropdown + custom input), OHLCVResponse wrapper, data transition marker on charts.

---

## Phase 4 — Fund Analysis Depth

**Priority: HIGH** — Core spec features that don't exist yet.

| Task | Spec Reference | Notes |
| --- | --- | --- |
| TA on fund NAV curves | §4 "Tekninen analyysi NAV-käyrästä" | Apply MA, RSI, Bollinger to daily NAV. Frontend detail page design already has a slot for this. |
| Fund-to-fund comparison view | §5 "Rahastovertailu — rinnakkaisvertailu" | New page or overlay — side-by-side NAV curves, returns, risk metrics for 2+ selected funds. |

---

## Phase 5 — Real-Time & Streaming

**Priority: MEDIUM** — Spec says "reaaliaikainen" and "WebSocket-yhteys pörssidataan." Hourly batch is fine but the spec envisions more.

| Task | Spec Reference | Notes |
| --- | --- | --- |
| Intraday data refresh | §5 "WebSocket-yhteys" | Increase refresh frequency for intraday intervals. 5-15 min cron for intraday, hourly for daily. |
| WebSocket or SSE for live updates | §5 "Reaaliaikadata" | Push price/signal updates to frontend without polling. Finnhub WebSocket is a candidate data source. |
| Live signal alerts in UI | §5 "Signaalidashboard" | Visual/audio cue when aggregate signal changes (buy→sell etc.) |

---

## Phase 6 — Localization & UX Polish

**Priority: MEDIUM** — Spec explicitly lists three languages.

| Task | Spec Reference | Notes |
| --- | --- | --- |
| Swedish language | §5 "suomi/ruotsi/englanti" | i18next infrastructure exists — needs sv.json. Important: ÅAB is a Swedish-speaking Finnish bank. |
| Mobile UX audit | §5 "Mobile-first design" | Verify all flows on real devices. Responsive framework exists but hasn't been dog-fooded. |

---

## Phase 7 — User Accounts & Notifications

**Priority: LOW** — Only valuable if the tool will be shared beyond a single user.

| Task | Spec Reference | Notes |
| --- | --- | --- |
| Authentication & roles | §6 "roolit: vierailija, sijoittaja, admin" | Simple auth (token/basic) unless multi-user is confirmed. |
| User preferences persistence | §5 implied | Save selected indicators, watched indices, language pref. |
| Push notifications for signals | §5 "Push-notifikaatiot RSI/MACD-signaaleista" | Requires user accounts. Browser push, email, or Telegram. |

---

## Phase 8 — ML Prediction

**Priority: LOW** — Spec lists it but wisely deferred. Only if core analysis is solid and the user wants it.

| Task | Spec Reference | Notes |
| --- | --- | --- |
| ML short-term forecast | §5 "Ennustemalli — LSTM tai lineaarinen regressio" | Start simple: linear regression on indicator features. Display as direction + confidence, not price target. |

---

## Priority Summary

```
NOW   (Phase 4)  ━━━━━━━━━━━━━━━━━  Fund analysis depth — core spec features
NEXT  (Phase 5)  ━━━━━━━━━━━━━━━    Real-time streaming
THEN  (Phase 6)  ━━━━━━━━━━━━━      Swedish + mobile polish
LATER (Phase 7-8)━━━━━━━━           Auth, notifications, ML
```
