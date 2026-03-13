# InvestIQ – Specification v1.0

> Source: https://toivonsydan.fi/tuomo/investiq.html
> Language: Originally Finnish, preserved as-is below.

---

## 1. Yleiskuvaus (Overview)

- **Projektin nimi:** InvestIQ – Teknisen analyysin sijoitusplattformi
- **Tavoite:** Verkkosovellus, joka tarjoaa reaaliaikaisen teknisen analyysin 10 tärkeimmällä indikaattorilla, markkinaennusteet 10 globaalille indeksille (ml. pohjoismaiset), sekä kattavan analyysin Ålandsbankenin rahastoista.
- **Kohdekäyttäjä:** Yksityissijoittajat, salkunhoitajat, finanssikonsultantit

---

## 2. 10 Teknistä Indikaattoria (Technical Indicators)

| # | Indicator | Description (FI) |
|---|-----------|-------------------|
| 1 | **RSI (Relative Strength Index)** | Mittaa overbought/oversold-tiloja (0–100). Signaali: <30 = osta, >70 = myy. |
| 2 | **MACD** | Liukuvan keskiarvon konvergenssi/divergenssi. Näyttää trendin voimakkuuden ja käänteen. |
| 3 | **Bollinger Bands** | Volatiliteettikaistale. Hinnan osuessa yläkaistaan = yliosto, alakaistaan = ylimyynti. |
| 4 | **Moving Average (SMA/EMA)** | Lyhyen ja pitkän aikavälin (50/200 pv) risteytyksistä osto-/myyntisignaalit (Golden/Death Cross). |
| 5 | **Stochastic Oscillator** | Vertaa sulkuhintaa hintaväliin. 0–100 asteikko, >80 yliosto, <20 ylimyynti. |
| 6 | **Volume Analysis (OBV)** | On-Balance Volume paljastaa volyymitrendit hinnan liikkeen takana. |
| 7 | **Fibonacci Retracement** | Tuki- ja vastustasot (23.6%, 38.2%, 61.8%). Hinnan odotettavat palautumispisteet. |
| 8 | **ATR (Average True Range)** | Volatiliteetin mitta. Auttaa stop-loss-tasojen asettamisessa. |
| 9 | **Ichimoku Cloud** | Japanilainen indikaattori: tuki/vastus, trendi ja momentum yhdessä näkymässä. |
| 10 | **CCI (Commodity Channel Index)** | Mittaa poikkeamia hinnan keskiarvosta. >100 = nouseva trendi, <-100 = laskeva. |

---

## 3. 10 Seurattavaa Indeksiä (Tracked Indices)

| Index | Market | Description (FI) |
|-------|--------|-------------------|
| **OMXH25** | Helsinki | Suomen 25 vaihdetuinta osaketta – kotimaan päämittari. |
| **OMXS30** | Tukholma | Ruotsin 30 suurinta – Pohjoismaiden suurin pörssi. |
| **OMXC25** | Kööpenhamina | Tanskan 25 suurinta, sisältää vahvoja farmayrityksiä (Novo Nordisk). |
| **OBX** | Oslo | Norjan 25 vaihdetuinta – öljysektoripaino merkittävä. |
| **S&P 500** | USA | 500 suurinta amerikkalaista – globaalin markkinan ankkuri. |
| **NASDAQ-100** | USA | Teknologiapainotteiset USA-jätit – kasvumarkkinan barometri. |
| **DAX 40** | Saksa | Euroopan suurin kansallinen indeksi, teollisuuspainotteinen. |
| **FTSE 100** | UK | Lontoon 100 suurinta – globaali hajauttaminen. |
| **Nikkei 225** | Japani | Aasian markkinan seuranta, yöaikainen volatiliteetti. |
| **MSCI World** | Global | Globaali vertailuindeksi, 23 kehittynyttä markkinaa. |

---

## 4. Ålandsbanken Rahastot (Funds)

**Analysoitavat rahastot (Ålandsbanken Fund Management):**

| Fund | Type | Analysis Focus (FI) |
|------|------|---------------------|
| **ÅAB Finland** | Osakerahasto (Equity) | Tuotto vs. OMXH25, volatiliteetti, Sharpe-luku. |
| **ÅAB Nordic** | Osakerahasto (Equity) | Pohjoismaiset osakkeet. Benchmark: MSCI Nordic Countries. |
| **ÅAB Europe** | Osakerahasto (Equity) | Eurooppalaiset osakkeet. Benchmark: MSCI Europe. |
| **ÅAB Obligaatio** | Korkorahasto (Bond) | Duraatio, luottoriski, koron herkkyysanalyysi. |
| **ÅAB Balanced** | Yhdistelmärahasto (Balanced) | Asset allocation -analyysi, riskiprofiili. |

**Analysoitavat mittarit (Metrics):**

Vuosituotto (1v, 3v, 5v), Volatiliteetti (σ), Sharpe-luku, Max Drawdown, Expense Ratio (TER), Suhteellinen tuotto vs. benchmark, Tekninen analyysi NAV-käyrästä.

---

## 5. Tekniset Ominaisuudet (Features)

| Feature | Description (FI) |
|---------|-------------------|
| **Reaaliaikadata** | WebSocket-yhteys pörssidataan (esim. Yahoo Finance API, Alpha Vantage, tai Twelve Data). |
| **Interaktiiviset kaaviot** | TradingView Lightweight Charts tai Recharts — candlestick + indikaattorikerrokset. |
| **Signaalidashboard** | Yhdistetty signaali kaikista 10 indikaattorista: OSTA / MYY / PIDÄ. |
| **Ennustemalli** | ML-pohjainen lyhyen aikavälin ennuste (esim. LSTM tai lineaarinen regressio indikaattoreilla). |
| **Rahastovertailu** | Ålandsbanken-rahastojen rinnakkaisvertailu, tuottokäyrät, riskimittarit. |
| **Ilmoitukset** | Push-notifikaatiot RSI/MACD-signaaleista käyttäjän valitsemille indekseille. |
| **Responsiivinen UI** | Mobile-first design, dark mode, suomi/ruotsi/englanti. |

---

## 6. Teknologiapino / Tech Stack (Suggested)

| Layer | Stack |
|-------|-------|
| **Frontend** | React + TypeScript, Tailwind CSS, Recharts / TradingView |
| **Backend** | Node.js / FastAPI (Python) – data-aggregaattori ja ML-ennusteet |
| **Tietokanta** | Supabase (PostgreSQL + Realtime) |
| **Data-API** | Alpha Vantage (ilmainen tier), Yahoo Finance, tai Twelve Data |
| **Autentikaatio** | Supabase Auth – roolit: vierailija, sijoittaja, admin |
| **Hosting** | Vercel (frontend) + Supabase (backend/db) |

---

*Note: The original spec includes a comment referencing Supabase familiarity from a "kalastusappi" (fishing app), suggesting this was written with your dad's existing experience in mind.*
