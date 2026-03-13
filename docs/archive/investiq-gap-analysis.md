# InvestIQ — Spec vs. Implementation Gap Analysis

Comparing the original Finnish spec (from toivonsydan.fi/tuomo/investiq.html) against the current implementation state.

## Yleiskuvaus (Overview)

**Spec says:** "Verkkosovellus, joka tarjoaa reaaliaikaisen teknisen analyysin" (real-time technical analysis)

**Reality:** Data refreshes hourly via APScheduler. Not real-time. The spec's "reaaliaikainen" implies WebSocket or at least frequent polling, but 60-minute intervals is closer to delayed batch processing. For a v1 this is fine, but worth noting the spec explicitly used the word "reaaliaikainen."

**Spec says:** Target users are "yksityissijoittajat, salkunhoitajat, finanssikonsultantit" (private investors, portfolio managers, financial consultants)

**Reality:** No user model, no authentication, no roles. The app is a single open dashboard. The spec's tech stack section explicitly mentioned "Supabase Auth – roolit: vierailija, sijoittaja, admin" (roles: visitor, investor, admin). None of this exists.

---

## 10 Teknistä Indikaattoria (Technical Indicators)

All 10 indicators are implemented. Signal logic matches the spec descriptions. No gaps here. This section is complete.

---

## 10 Seurattavaa Indeksiä (Tracked Indices)

All 10 implemented. Tickers confirmed working. MSCI World uses URTH ETF proxy which is a reasonable compromise since the raw MSCI index isn't freely available.

One minor deviation: the spec describes OBX as "Norjan 25 vaihdetuinta – öljysektoripaino merkittävä" (Norway's 25 most traded, significant oil sector weight). The implementation tracks it but doesn't surface any sector composition context. Not a gap per se, just missing color that the spec provided.

---

## Ålandsbanken Rahastot (Funds)

This is where the biggest deviations are.

### Fund selection mismatch

| Spec fund | Spec benchmark | In app? | What's there instead |
|-----------|---------------|---------|---------------------|
| ÅAB Finland | OMXH25 | ❌ | ÅAB Norden Aktie EUR (different fund, broader scope) |
| ÅAB Nordic | MSCI Nordic Countries | ❌ | ÅAB Nordiska Småbolag B (small-cap, not the same thing) |
| ÅAB Europe | MSCI Europe | ✅ | ÅAB Europa Aktie B (correct, but benchmark is EURO STOXX 50 instead of spec's MSCI Europe) |
| ÅAB Obligaatio | — | ❌ | ÅAB Euro Bond A + Green Bond ESG C (two funds replacing one, reasonable) |
| ÅAB Balanced | — | ❌ | Missing entirely |

So 2 of 5 spec funds are genuinely missing (Finland equity was merged, Balanced doesn't exist in the app). The Nordic fund is a small-cap variant instead of the broad Nordic fund the spec intended. The Europe fund exists but with a different benchmark than spec'd.

### Missing fund metrics

**Spec says these metrics should be analyzed:**
- Vuosituotto (1v, 3v, 5v) — ✅ implemented
- Volatiliteetti (σ) — ✅ implemented
- Sharpe-luku — ✅ implemented
- Max Drawdown — ✅ implemented
- Expense Ratio (TER) — ✅ implemented
- Suhteellinen tuotto vs. benchmark — ✅ implemented (relative performance chart)
- Tekninen analyysi NAV-käyrästä — ❌ not implemented

That last one is explicitly called out in the current state doc. The spec said to apply TA to NAV curves. Even basic indicators like RSI or moving averages could be applied to daily NAV data (it's just a time series of closing prices). The implementation skipped this entirely.

---

## Tekniset Ominaisuudet (Features)

### Reaaliaikadata
**Spec:** "WebSocket-yhteys pörssidataan (esim. Yahoo Finance API, Alpha Vantage, tai Twelve Data)"
**Reality:** Hourly batch fetch via yfinance. No WebSocket. No real-time streaming.

### Interaktiiviset kaaviot
**Spec:** "TradingView Lightweight Charts tai Recharts — candlestick + indikaattorikerrokset"
**Reality:** ✅ TradingView Lightweight Charts v5 with candlestick + indicator overlays. Matches spec.

### Signaalidashboard
**Spec:** "Yhdistetty signaali kaikista 10 indikaattorista: OSTA / MYY / PIDÄ"
**Reality:** ✅ Aggregate signal with per-indicator breakdown. Matches spec.

### Ennustemalli
**Spec:** "ML-pohjainen lyhyen aikavälin ennuste (esim. LSTM tai lineaarinen regressio indikaattoreilla)"
**Reality:** ❌ Not implemented. Was deferred to nice-to-haves in the concept doc, which is the right call.

### Rahastovertailu
**Spec:** "Ålandsbanken-rahastojen rinnakkaisvertailu, tuottokäyrät, riskimittarit" (side-by-side comparison)
**Reality:** ❌ Individual fund pages only. The spec explicitly says "rinnakkaisvertailu" (side-by-side comparison). No way to compare two funds against each other in the current UI.

### Ilmoitukset
**Spec:** "Push-notifikaatiot RSI/MACD-signaaleista käyttäjän valitsemille indekseille"
**Reality:** ❌ Not implemented. Requires user accounts (which also don't exist).

### Responsiivinen UI
**Spec:** "Mobile-first design, dark mode, suomi/ruotsi/englanti"
**Reality:** Partially. Dark mode ✅, responsive ✅, Finnish ✅, English ✅, Swedish ❌. The spec explicitly lists three languages (suomi/ruotsi/englanti). Swedish is missing.

---

## Teknologiapino (Tech Stack)

| Spec | Reality | Match? |
|------|---------|--------|
| React + TypeScript | Presumably yes (not stated in current doc) | Likely ✅ |
| Tailwind CSS | Not stated | Unknown |
| Recharts / TradingView | TradingView Lightweight Charts | ✅ |
| Node.js / FastAPI (Python) | Not stated but pandas-ta implies Python backend | Likely ✅ |
| Supabase (PostgreSQL + Realtime) | PostgreSQL on db.mase.fi (no Supabase) | Deviated (intentionally, better) |
| Alpha Vantage / Yahoo Finance / Twelve Data | yfinance (Yahoo Finance) | ✅ |
| Supabase Auth with roles | No auth at all | ❌ |
| Vercel (frontend) + Supabase (backend) | Not stated | Unknown |

The Supabase deviation is intentional and correct since Mase is migrating to self-hosted Postgres. The auth gap is real though.

---

## Priority Summary

### Actually matters

1. **Fund-to-fund comparison view** — spec explicitly says "rinnakkaisvertailu" and this is genuinely useful for the banker's workflow
2. **Sub-daily data population** — the UI has interval selectors that return empty data, which is worse than not having them at all
3. **TA on fund NAV curves** — at minimum, moving averages and RSI on the NAV time series would be trivial to add and the spec asked for it
4. **ÅAB Balanced fund missing** — if the Yahoo ticker exists, add it. If not, document why it's absent.

### Would be nice but not blocking

5. **Swedish language** — spec says three languages, only two exist
6. **Europe fund benchmark mismatch** — should be MSCI Europe per spec, currently EURO STOXX 50
7. **Real-time data** — hourly is fine for v1 but doesn't match the spec's "reaaliaikainen" claim

### Intentionally skipped (correct to skip)

8. **ML prediction model** — rabbit hole, skip
9. **Auth and user roles** — overkill for a single-user tool unless notifications get built
10. **Push notifications** — depends on auth, skip for now
