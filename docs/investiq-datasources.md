# InvestIQ – Data Sources Reference

## Index Data: Yahoo Finance via yfinance

All 10 indices are confirmed working on Yahoo Finance. This is the path of least resistance: free, no API key needed, good historical depth, and covers everything including the Nordic indices.

### Verified Tickers

| Index | Yahoo Ticker | Confirmed |
|-------|-------------|-----------|
| OMXH25 (Helsinki) | `^OMXH25` | ✅ |
| OMXS30 (Stockholm) | `^OMXS30` | ✅ |
| OMXC25 (Copenhagen) | `^OMXC25` | ✅ |
| OBX (Oslo) | `OBX.OL` | ✅ |
| S&P 500 | `^GSPC` | ✅ |
| NASDAQ-100 | `^NDX` | ✅ |
| DAX 40 | `^GDAXI` | ✅ |
| FTSE 100 | `^FTSE` | ✅ |
| Nikkei 225 | `^N225` | ✅ |
| MSCI World | `URTH` (ETF proxy) | ✅ |

**Note on MSCI World:** There's no direct Yahoo index ticker for MSCI World. `URTH` (iShares MSCI World ETF) is the best free proxy. `IWDA.AS` (iShares Core MSCI World on Euronext Amsterdam) is another option. The raw MSCI index data requires a paid license.

**Note on OBX:** Oslo Børs moved from Nasdaq Nordic to Euronext in 2019. The `OBX.OL` ticker works fine on Yahoo Finance despite this.

### yfinance Usage

Python library, install with `pip install yfinance`. No API key needed. It scrapes Yahoo Finance's public endpoints.

```python
import yfinance as yf
ticker = yf.Ticker("^OMXH25")
hist = ticker.history(period="1y")  # OHLCV data
```

**Rate limits:** Unofficial, but generally tolerant for moderate usage. Cache data in postgres to avoid hammering it. Daily candles are fine to fetch once per day per index.

**Caveats:** 
- Not an official API. Can break if Yahoo changes their site.
- Intended for personal use per Yahoo's ToS.
- For a banker's internal tool, this is fine. For a commercial product, you'd need a licensed data provider.

---

## Ålandsbanken Fund Data: Yahoo Finance (Morningstar tickers)

ÅAB funds are available via Yahoo Finance using Morningstar-style tickers (the `0P...` format with `.F` suffix for Frankfurt-listed fund data).

### Verified Fund Tickers

| Fund | Yahoo Ticker | ISIN | Type | Confirmed |
|------|-------------|------|------|-----------|
| ÅAB Europa Aktie B | `0P00000N9Y.F` | FI0008805031 | Equity (Europe) | ✅ |
| ÅAB Norden Aktie EUR | `0P00015D0H.F` | FI4000123179 | Equity (Nordic) | ✅ |
| ÅAB Global Aktie B | `0P0000CNVH.F` | FI0008812607 | Equity (Global) | ✅ |
| ÅAB Euro Bond A | `0P00000N9R.F` | FI0008805007 | Bond | ✅ |
| ÅAB Green Bond ESG C | `0P0001HOZS.F` | — | Bond (ESG) | ✅ |
| ÅAB Nordiska Småbolag B | `0P0001JWUW.F` | — | Equity (Nordic SC) | ✅ |

### Missing Funds

The original spec mentions "ÅAB Finland" (Suomi equity), "ÅAB Obligaatio" (bond), and "ÅAB Balanced" (Varainhoito). These didn't surface in Yahoo Finance search. 

Possible reasons: Ålandsbanken merged their standalone Finland equity fund into the Nordic fund a few years back (Morningstar confirms this). "ÅAB Obligaatio" might be the same as "Euro Bond" (which IS available). "Varainhoito" (balanced/allocation fund) may not be listed on international fund platforms.

**Practical approach:** Use the 6 confirmed funds above. That covers equity (Europe, Nordic, Global, Nordic small-cap), bonds (Euro Bond, Green Bond ESG). If the banker specifically needs the Varainhoito fund, its NAV data might need to be scraped from Ålandsbanken's own website or pulled from Nordnet.

### Finding More ÅAB Fund Tickers

Search by ISIN using yfinance:
```python
import yfinance as yf
result = yf.Search("FI0008805031", news_count=0)
# Returns matching Morningstar tickers
```

---

## Alternative/Backup APIs

If yfinance breaks or isn't sufficient:

### Alpha Vantage
- **Free tier:** 25 requests/day (was recently reduced)
- **Nordic coverage:** Supports HEL (Helsinki), STO (Stockholm), CPH (Copenhagen) exchanges for individual stocks. Index-level data is more limited.
- **Key:** Free at alphavantage.co/support
- **Best for:** Individual stock data, built-in technical indicator calculations
- **Downside:** Free tier is very restrictive now. Nordic INDEX data (as opposed to individual stocks) may not be available.

### Twelve Data
- **Free tier:** 800 requests/day, 8 per minute
- **Claims 5000+ indices globally** including Nordic
- **Has built-in technical indicators** via API (RSI, MACD, Bollinger, etc.)
- **WebSocket support** for real-time streaming
- **Key:** Free at twelvedata.com
- **Best for:** If you want the API to calculate indicators server-side rather than doing it yourself
- **Worth checking:** Verify actual Nordic index coverage on their free tier before committing

### Finnhub
- **Free tier:** 60 calls/minute
- **Has aggregate technical indicator endpoint** that returns combined buy/sell/hold signals
- **Helsinki exchange confirmed supported**
- **Key:** Free at finnhub.io
- **Best for:** The aggregate indicator feature is interesting since InvestIQ needs exactly that. Could supplement yfinance for signal generation.

---

## Technical Indicator Calculation

Two approaches:

### Option A: Calculate client-side / in your backend
Fetch raw OHLCV data from yfinance, calculate indicators yourself. Libraries like `ta-lib` or `pandas-ta` handle all 10 indicators. This gives full control and no extra API dependency.

### Option B: Use an API with built-in indicators
Both Twelve Data and Finnhub offer technical indicator endpoints. Twelve Data in particular has endpoints for all 10 indicators in the spec. Finnhub has an aggregate indicator endpoint that returns a combined signal.

**Recommendation:** Option A is more reliable long-term and doesn't add rate limit pressure. The calculations aren't complex and there are well-tested libraries for all of them. Option B is a nice shortcut if you want to ship fast.

---

## Chart Library

**TradingView Lightweight Charts** is the obvious pick for the frontend. It's free, open-source (Apache 2.0), purpose-built for financial charts, and handles candlesticks with indicator overlays natively. The npm package is `lightweight-charts`.

Recharts (mentioned in the original spec) is fine for the fund comparison charts but not ideal for candlestick/indicator overlays.

---

## Summary: Recommended Stack for Data

| Need | Source | Notes |
|------|--------|-------|
| Index OHLCV data | yfinance (Yahoo Finance) | All 10 indices confirmed. Cache in postgres. |
| Fund NAV data | yfinance (Morningstar tickers) | 6 of ~8 funds confirmed. |
| Technical indicators | Calculate in backend (pandas-ta or ta-lib) | Full control, no extra API calls. |
| Aggregate signals | Calculate yourself (majority vote) | Simple logic, transparent to user. |
| Real-time-ish updates | Cron job fetching daily, or Finnhub WebSocket for intraday | Daily is probably fine for v1. |
| Charts | TradingView Lightweight Charts | npm: lightweight-charts |
