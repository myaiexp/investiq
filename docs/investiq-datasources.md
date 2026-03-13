# InvestIQ – Data Sources Reference

## Index Data: Yahoo Finance via yfinance

All 10 indices are confirmed working on Yahoo Finance. Free, no API key needed, good historical depth, covers everything including Nordic indices.

### Verified Tickers

| Index | Yahoo Ticker | Notes |
|-------|-------------|-------|
| OMXH25 (Helsinki) | `^OMXH25` | |
| OMXS30 (Stockholm) | `^OMX` | NOT `^OMXS30` — that ticker is broken in yfinance (returns 1 data point) |
| OMXC25 (Copenhagen) | `^OMXC25` | |
| OBX (Oslo) | `OBX.OL` | Total return index (includes dividends). Price-only `OBXP.OL` broken in yfinance. |
| S&P 500 | `^GSPC` | |
| NASDAQ-100 | `^NDX` | |
| DAX 40 | `^GDAXI` | |
| FTSE 100 | `^FTSE` | |
| Nikkei 225 | `^N225` | |
| MSCI World | `URTH` (ETF proxy) | No direct index ticker available free. `IWDA.AS` is another option. |

### yfinance Usage

```python
import yfinance as yf
ticker = yf.Ticker("^OMXH25")
hist = ticker.history(period="1y")  # OHLCV data
```

**Rate limits:** Unofficial, ~2000/hr practical. Cache in postgres. Daily candles: fetch once per day per index.

**Intraday data retention:** 1m = 7 days, 5m/15m = 60 days, 1H = 730 days. Daily+ = full history.

**Caveats:**
- Not an official API. Can break if Yahoo changes their site.
- Intended for personal use per Yahoo's ToS.
- yfinance 1.2+ returns MultiIndex columns — flatten via `_flatten_columns()`.

---

## Ålandsbanken Fund Data: Yahoo Finance (Morningstar tickers)

ÅAB funds are available via Yahoo Finance using Morningstar-style tickers (`0P...` format with `.F` suffix for Frankfurt-listed fund data).

### Share Class Convention

ÅAB funds have multiple share classes. **Always use B class (kasvuosuus / accumulation)** — these reinvest income, have higher NAV, and are what Nordnet and Ålandsbanken's website highlight as the default.

A class (tuotto-osuus / distribution) pays out income, resulting in lower NAV over time. If you see a ticker returning unexpectedly low NAV, check if you have the A class by mistake.

### Verified Fund Tickers

| Fund | Yahoo Ticker | ISIN | Type | Benchmark Ticker | Benchmark Name |
|------|-------------|------|------|-----------------|----------------|
| ÅAB Europa Aktie B | `0P00000N9Y.F` | FI0008805031 | Equity (Europe) | `IEUR` | MSCI Europe |
| ÅAB Norden Aktie EUR | `0P00015D0H.F` | FI4000123179 | Equity (Nordic) | `^OMXH25` | OMXH25 |
| ÅAB Global Aktie B | `0P0000CNVH.F` | FI0008812607 | Equity (Global) | `URTH` | MSCI World |
| ÅAB Euro Bond B | `0P00000N9Q.F` | FI0008804992 | Bond | `SYBA.DE` | Bloomberg Euro Aggregate Bond |
| ÅAB Green Bond ESG C | `0P0001HOZS.F` | — | Bond (ESG) | `GRON.DE` | Bloomberg Euro Green Bond |
| ÅAB Nordiska Småbolag B | `0P0001JWUW.F` | — | Equity (Nordic SC) | `^OMX` | OMXS30 |
| ÅAB Varainhoito B | `0P00001CPE.F` | FI0008809934 | Balanced | — | None |

### Euro Bond Share Class Detail

| Share Class | Morningstar ID | Yahoo Ticker | ISIN | NAV (Mar 2026) |
|---|---|---|---|---|
| A (tuotto-osuus) | `0P00000N9R` | `0P00000N9R.F` | FI0008805007 | ~16€ |
| B (kasvuosuus) | `0P00000N9Q` | `0P00000N9Q.F` | FI0008804992 | ~37€ |

### Benchmark ETF Proxies

| Benchmark Index | ETF Ticker | ETF Name | Exchange | Currency | Data Since |
|---|---|---|---|---|---|
| MSCI Europe | `IEUR` | iShares Core MSCI Europe ETF | NYSE Arca | USD | 2014 |
| Bloomberg Euro Aggregate Bond | `SYBA.DE` | SPDR Bloomberg Euro Aggregate Bond UCITS ETF | XETRA | EUR | 2019 |
| Bloomberg Euro Green Bond | `GRON.DE` | iShares EUR Green Bond UCITS ETF | XETRA | EUR | Mar 2021 |
| MSCI World | `URTH` | iShares MSCI World ETF | NYSE Arca | USD | 2012 |

**Notes on benchmark selection:**
- `IEUR` vs `IMEU.L`: both track MSCI Europe. IEUR has better volume and USD pricing.
- `SYBA.DE` vs `EAGG.PA`: same fund, different exchanges. SYBA.DE has much better data quality (0.2% vs 6.8% zero-volume days).
- `GRON.DE` vs `GRON.MI`: same fund. GRON.DE has better data quality and longer history.
- `IEAG.L` is NOT plain Euro Aggregate — it's an ESG-filtered version. Don't use as Euro Aggregate proxy.
- `MEUD.PA` tracks STOXX Europe 600, NOT MSCI Europe. Don't confuse them.
- ÅAB Varainhoito has no formal benchmark (50/50 equity/bond allocation fund).

### Spec Fund Mapping

The original spec listed 5 funds. Here's what happened to each:

| Spec Fund | Status | What's in the app |
|---|---|---|
| ÅAB Finland (equity, OMXH25) | Merged into Nordic fund years ago | ÅAB Norden Aktie EUR |
| ÅAB Nordic (equity, MSCI Nordic) | Different fund available | ÅAB Nordiska Småbolag B (small-cap) |
| ÅAB Europe (equity, MSCI Europe) | Available | ÅAB Europa Aktie B |
| ÅAB Obligaatio (bond) | Same as Euro Bond | ÅAB Euro Bond B |
| ÅAB Balanced (mixed) | Found, now called Varainhoito | ÅAB Varainhoito B |

### Finding More ÅAB Fund Tickers

Search by ISIN using yfinance:
```python
import yfinance as yf
result = yf.Search("FI0008805031", news_count=0)
# Returns matching Morningstar tickers
```

---

## Alternative/Backup APIs — Evaluation (2026-03-13)

yfinance is the sole data source. Alternatives were evaluated for gaps but none justified adding:

### Twelve Data
- **Free tier:** 800 req/day, 8/min. No daily cap concerns for light usage.
- **Nordic coverage on free tier: NO.** Free tier only covers US, Forex, Crypto. Nordic exchanges require Grow plan ($29/mo).
- **100+ built-in technical indicators** on all plans — strongest differentiator, but not needed when pandas-ta handles everything locally.
- **WebSocket:** 8 trial credits on free tier (useless). Real WebSocket requires Pro ($79/mo).
- **Fund coverage:** ETFs and mutual funds supported. ISIN lookup available. Nordic fund depth uncertain.
- **Verdict:** Not useful for free Nordic data. Only worth reconsidering if yfinance breaks entirely.

### Finnhub
- **Free tier:** 60 req/min, no daily cap. More generous burst capacity than Twelve Data.
- **Nordic coverage:** Individual stocks on Helsinki (HE), Stockholm (SS), Copenhagen (CO), Oslo (OL) exchanges. **No Nordic index-level data** — only individual stocks.
- **Aggregate TA endpoint:** Confirmed working (`/api/v1/scan/technical-indicator`). Returns combined buy/sell/neutral signal from MACD, RSI, MAs. Works on individual stocks only, not indices.
- **WebSocket:** Free, 50 symbols. Real-time trade data for US (IEX), forex, crypto.
- **Verdict:** Could supplement if InvestIQ expands to individual stock analysis. Not useful for current index-focused scope.

### Alpha Vantage
- **Free tier:** 25 req/day (severely reduced). Not practical for 10 indices + 7 funds.
- **Nordic coverage:** HEL, STO, CPH exchanges for individual stocks. Index data limited.
- **Verdict:** Too restrictive. Skip.

### Other Sources (not APIs)
- **Nordnet:** Lists all ÅAB funds. Has an API but requires authentication. Not practical for automated fetching.
- **Morningstar.fi:** Fund pages available. No free API.
- **Ålandsbanken.fi:** Official fund pages. No public API. Scraping possible but fragile.
- **FT.com:** Securities API exists but likely requires subscription.

---

## Technical Indicator Calculation

**Chosen approach: Calculate in backend with pandas-ta.** Full control, no API dependency, no rate limits. All 10 spec indicators are well-supported.

Twelve Data has 100+ indicator endpoints and Finnhub has an aggregate signal endpoint, but neither adds enough value to justify the dependency when pandas-ta handles everything locally for free.

---

## Chart Library

**TradingView Lightweight Charts** (npm: `lightweight-charts`, Apache 2.0). Purpose-built for financial charts, handles candlesticks + indicator overlays natively.

---

## Summary: Data Stack

| Need | Source | Notes |
|------|--------|-------|
| Index OHLCV data | yfinance | All 10 indices. Cache in postgres. |
| Fund NAV data | yfinance (Morningstar tickers) | 7 funds confirmed. |
| Benchmark data | yfinance (ETF proxies) | 5 of 7 funds have benchmarks. |
| Technical indicators | pandas-ta (backend) | Full control, no extra API calls. |
| Aggregate signals | Majority vote (backend) | Simple, transparent logic. |
| Refresh cycle | APScheduler (hourly) | Daily candles sufficient for v1. |
| Charts | TradingView Lightweight Charts | Frontend rendering. |
