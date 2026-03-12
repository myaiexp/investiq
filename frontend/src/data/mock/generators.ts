import type {
  OHLCVBar,
  IndicatorData,
  IndicatorId,
  Signal,
} from "../../types/index.ts";
import type { FundNAVPoint, FundPerformance } from "../../types/funds.ts";
import type { Period, Interval } from "../../types/charts.ts";

// ---------------------------------------------------------------------------
// Seeded PRNG — deterministic random walks per ticker
// ---------------------------------------------------------------------------

function hashSeed(str: string): number {
  let h = 0;
  for (let i = 0; i < str.length; i++) {
    h = (Math.imul(31, h) + str.charCodeAt(i)) | 0;
  }
  return Math.abs(h);
}

/** Simple mulberry32 PRNG */
function createRng(seed: number): () => number {
  let s = seed | 0;
  return () => {
    s = (s + 0x6d2b79f5) | 0;
    let t = Math.imul(s ^ (s >>> 15), 1 | s);
    t = (t + Math.imul(t ^ (t >>> 7), 61 | t)) ^ t;
    return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
  };
}

// ---------------------------------------------------------------------------
// Interval → seconds mapping
// ---------------------------------------------------------------------------

const INTERVAL_SECONDS: Record<Interval, number> = {
  "1m": 60,
  "5m": 300,
  "15m": 900,
  "1H": 3600,
  "2H": 7200,
  "4H": 14400,
  "1D": 86400,
  "1W": 604800,
};

const PERIOD_DAYS: Record<Period, number> = {
  "1m": 30,
  "3m": 90,
  "6m": 180,
  "1y": 365,
  "5y": 1825,
};

// ---------------------------------------------------------------------------
// Base prices for realistic starting points
// ---------------------------------------------------------------------------

const BASE_PRICES: Record<string, number> = {
  "^OMXH25": 5200,
  "^OMXS30": 2450,
  "^OMXC25": 1800,
  "OBX.OL": 1280,
  "^GSPC": 5800,
  "^NDX": 20500,
  "^GDAXI": 18400,
  "^FTSE": 8200,
  "^N225": 38000,
  URTH: 132,
  // Funds — NAV-scale prices
  "0P00000N9Y.F": 42,
  "0P00015D0H.F": 18,
  "0P0000CNVH.F": 155,
  "0P00000N9R.F": 29,
  "0P0001HOZS.F": 10,
  "0P0001JWUW.F": 86,
};

function getBasePrice(ticker: string): number {
  return BASE_PRICES[ticker] ?? 100;
}

// ---------------------------------------------------------------------------
// OHLCV Generator
// ---------------------------------------------------------------------------

export function generateOHLCV(
  ticker: string,
  period: Period,
  interval: Interval,
): OHLCVBar[] {
  const rng = createRng(hashSeed(ticker + period + interval));
  const basePrice = getBasePrice(ticker);
  const totalSeconds = PERIOD_DAYS[period] * 86400;
  const step = INTERVAL_SECONDS[interval];
  const barCount = Math.floor(totalSeconds / step);

  // Cap at 2000 bars for performance
  const maxBars = Math.min(barCount, 2000);
  const now = Math.floor(Date.now() / 1000);
  const startTime = now - maxBars * step;

  // Volatility scales with base price
  const dailyVol = basePrice * 0.012;
  const barVol = dailyVol * Math.sqrt(step / 86400);

  const bars: OHLCVBar[] = [];
  let price = basePrice * (0.92 + rng() * 0.16); // Start within ±8% of base

  for (let i = 0; i < maxBars; i++) {
    const time = startTime + i * step;
    const drift = (rng() - 0.498) * barVol; // slight upward bias
    const open = price;
    const close = Math.max(open + drift, basePrice * 0.01); // floor at 1% of base

    // High/low extend beyond open-close range
    const range = Math.abs(close - open);
    const high = Math.max(open, close) + rng() * range * 0.5 + barVol * 0.1;
    const low = Math.min(open, close) - rng() * range * 0.5 - barVol * 0.1;

    // Volume: base + random variation
    const baseVolume = basePrice > 1000 ? 5e6 : basePrice > 100 ? 2e7 : 1e8;
    const volume = Math.round(baseVolume * (0.5 + rng() * 1.0));

    bars.push({
      time,
      open: round(open),
      high: round(high),
      low: round(Math.max(low, basePrice * 0.01)),
      close: round(close),
      volume,
    });

    price = close;
  }

  return bars;
}

function round(n: number): number {
  return Math.round(n * 100) / 100;
}

// ---------------------------------------------------------------------------
// Fund NAV Generator
// ---------------------------------------------------------------------------

export function generateFundNAV(
  ticker: string,
  period: Period,
): FundNAVPoint[] {
  const rng = createRng(hashSeed(ticker + period + "nav"));
  const basePrice = getBasePrice(ticker);
  const totalDays = PERIOD_DAYS[period];
  const step = 86400; // daily
  const now = Math.floor(Date.now() / 1000);
  const startTime = now - totalDays * step;

  const dailyVol = basePrice * 0.006; // funds are less volatile
  const points: FundNAVPoint[] = [];
  let value = basePrice * (0.94 + rng() * 0.12);

  for (let i = 0; i < totalDays; i++) {
    // Skip weekends (rough approximation)
    const dayOfWeek = new Date((startTime + i * step) * 1000).getDay();
    if (dayOfWeek === 0 || dayOfWeek === 6) continue;

    const time = startTime + i * step;
    const drift = (rng() - 0.497) * dailyVol;
    value = Math.max(value + drift, basePrice * 0.1);

    points.push({ time, value: round(value) });
  }

  return points;
}

// ---------------------------------------------------------------------------
// Fund Performance Generator
// ---------------------------------------------------------------------------

export function generateFundPerformance(ticker: string): FundPerformance {
  const rng = createRng(hashSeed(ticker + "perf"));
  const isBond = ticker === "0P00000N9R.F" || ticker === "0P0001HOZS.F";

  if (isBond) {
    return {
      returns: {
        "1y": round(2 + rng() * 3),
        "3y": round(1 + rng() * 4),
        "5y": round(1.5 + rng() * 5),
      },
      benchmarkReturns: {
        "1y": round(1.5 + rng() * 3),
        "3y": round(0.5 + rng() * 4),
        "5y": round(1 + rng() * 5),
      },
      volatility: round(2 + rng() * 4),
      sharpe: round(0.3 + rng() * 1.2),
      maxDrawdown: round(-(2 + rng() * 6)),
      ter: round(0.3 + rng() * 0.5),
    };
  }

  return {
    returns: {
      "1y": round(5 + rng() * 20),
      "3y": round(10 + rng() * 40),
      "5y": round(20 + rng() * 60),
    },
    benchmarkReturns: {
      "1y": round(4 + rng() * 18),
      "3y": round(8 + rng() * 35),
      "5y": round(18 + rng() * 55),
    },
    volatility: round(10 + rng() * 10),
    sharpe: round(0.5 + rng() * 1.5),
    maxDrawdown: round(-(10 + rng() * 25)),
    ter: round(0.8 + rng() * 1.2),
  };
}

// ---------------------------------------------------------------------------
// Indicator Data Generator
// ---------------------------------------------------------------------------


function generateSignalForIndicator(rng: () => number): Signal {
  const r = rng();
  if (r < 0.35) return "buy";
  if (r < 0.7) return "sell";
  return "hold";
}

export function generateIndicatorData(
  ticker: string,
  period: Period,
  interval: Interval,
): IndicatorData[] {
  const bars = generateOHLCV(ticker, period, interval);
  const indicators: IndicatorId[] = [
    "rsi",
    "macd",
    "bollinger",
    "ma",
    "stochastic",
    "obv",
    "fibonacci",
    "atr",
    "ichimoku",
    "cci",
  ];

  return indicators.map((id) => {
    const rng = createRng(hashSeed(ticker + period + interval + id));
    const signal = generateSignalForIndicator(rng);
    const series = generateIndicatorSeries(id, bars, rng);

    return { id, series, signal };
  });
}

function generateIndicatorSeries(
  id: IndicatorId,
  bars: OHLCVBar[],
  rng: () => number,
): Record<string, { time: number; value: number }[]> {
  const times = bars.map((b) => b.time);
  const closes = bars.map((b) => b.close);

  switch (id) {
    case "rsi":
      return { rsi: generateRSI(times, closes) };

    case "macd":
      return generateMACD(times, closes);

    case "bollinger":
      return generateBollinger(times, closes);

    case "ma":
      return {
        sma20: sma(times, closes, 20),
        sma50: sma(times, closes, 50),
        sma200: sma(times, closes, 200),
      };

    case "stochastic":
      return generateStochastic(times, bars, rng);

    case "obv":
      return { obv: generateOBV(times, bars) };

    case "fibonacci":
      return generateFibonacci(times, closes);

    case "atr":
      return { atr: generateATR(times, bars) };

    case "ichimoku":
      return generateIchimoku(times, closes);

    case "cci":
      return { cci: generateCCI(times, bars) };
  }
}

// ---------------------------------------------------------------------------
// Simplified indicator formulas
// ---------------------------------------------------------------------------

function sma(
  times: number[],
  values: number[],
  windowSize: number,
): { time: number; value: number }[] {
  const result: { time: number; value: number }[] = [];
  for (let i = windowSize - 1; i < values.length; i++) {
    let sum = 0;
    for (let j = i - windowSize + 1; j <= i; j++) sum += values[j];
    result.push({ time: times[i], value: round(sum / windowSize) });
  }
  return result;
}

function generateRSI(
  times: number[],
  closes: number[],
): { time: number; value: number }[] {
  const lookback = 14;
  const result: { time: number; value: number }[] = [];
  if (closes.length < lookback + 1) return result;

  let avgGain = 0;
  let avgLoss = 0;

  // Initial average
  for (let i = 1; i <= lookback; i++) {
    const change = closes[i] - closes[i - 1];
    if (change > 0) avgGain += change;
    else avgLoss -= change;
  }
  avgGain /= lookback;
  avgLoss /= lookback;

  for (let i = lookback; i < closes.length; i++) {
    if (i > lookback) {
      const change = closes[i] - closes[i - 1];
      avgGain = (avgGain * (lookback - 1) + Math.max(change, 0)) / lookback;
      avgLoss = (avgLoss * (lookback - 1) + Math.max(-change, 0)) / lookback;
    }
    const rs = avgLoss === 0 ? 100 : avgGain / avgLoss;
    const rsi = 100 - 100 / (1 + rs);
    result.push({ time: times[i], value: round(rsi) });
  }

  return result;
}

function generateMACD(
  times: number[],
  closes: number[],
): Record<string, { time: number; value: number }[]> {
  const ema12 = ema(closes, 12);
  const ema26 = ema(closes, 26);
  const macdLine: { time: number; value: number }[] = [];

  const offset = 26 - 1; // ema26 starts at index 25
  for (let i = 0; i < ema26.length; i++) {
    const idx12 = i + (26 - 12); // align ema12 with ema26
    if (idx12 >= 0 && idx12 < ema12.length) {
      macdLine.push({
        time: times[i + offset],
        value: round(ema12[idx12] - ema26[i]),
      });
    }
  }

  // Signal line: 9-period EMA of MACD
  const macdValues = macdLine.map((p) => p.value);
  const signalEma = ema(macdValues, 9);
  const signalLine: { time: number; value: number }[] = [];
  const histogram: { time: number; value: number }[] = [];

  for (let i = 0; i < signalEma.length; i++) {
    const macdIdx = i + 8; // signal starts after 8 values
    if (macdIdx < macdLine.length) {
      signalLine.push({
        time: macdLine[macdIdx].time,
        value: round(signalEma[i]),
      });
      histogram.push({
        time: macdLine[macdIdx].time,
        value: round(macdLine[macdIdx].value - signalEma[i]),
      });
    }
  }

  return { macd: macdLine, signal: signalLine, histogram };
}

function ema(values: number[], windowSize: number): number[] {
  if (values.length < windowSize) return [];
  const k = 2 / (windowSize + 1);
  const result: number[] = [];

  // First value is SMA
  let sum = 0;
  for (let i = 0; i < windowSize; i++) sum += values[i];
  result.push(sum / windowSize);

  for (let i = windowSize; i < values.length; i++) {
    result.push(values[i] * k + result[result.length - 1] * (1 - k));
  }

  return result;
}

function generateBollinger(
  times: number[],
  closes: number[],
): Record<string, { time: number; value: number }[]> {
  const windowSize = 20;
  const upper: { time: number; value: number }[] = [];
  const middle: { time: number; value: number }[] = [];
  const lower: { time: number; value: number }[] = [];

  for (let i = windowSize - 1; i < closes.length; i++) {
    let sum = 0;
    for (let j = i - windowSize + 1; j <= i; j++) sum += closes[j];
    const avg = sum / windowSize;

    let sqSum = 0;
    for (let j = i - windowSize + 1; j <= i; j++)
      sqSum += (closes[j] - avg) ** 2;
    const std = Math.sqrt(sqSum / windowSize);

    middle.push({ time: times[i], value: round(avg) });
    upper.push({ time: times[i], value: round(avg + 2 * std) });
    lower.push({ time: times[i], value: round(avg - 2 * std) });
  }

  return { upper, middle, lower };
}

function generateStochastic(
  times: number[],
  bars: OHLCVBar[],
  _rng: () => number,
): Record<string, { time: number; value: number }[]> {
  const lookback = 14;
  const kLine: { time: number; value: number }[] = [];

  for (let i = lookback - 1; i < bars.length; i++) {
    let high = -Infinity;
    let low = Infinity;
    for (let j = i - lookback + 1; j <= i; j++) {
      if (bars[j].high > high) high = bars[j].high;
      if (bars[j].low < low) low = bars[j].low;
    }
    const k = high === low ? 50 : ((bars[i].close - low) / (high - low)) * 100;
    kLine.push({ time: times[i], value: round(k) });
  }

  // %D is 3-period SMA of %K
  const dLine: { time: number; value: number }[] = [];
  for (let i = 2; i < kLine.length; i++) {
    const avg =
      (kLine[i].value + kLine[i - 1].value + kLine[i - 2].value) / 3;
    dLine.push({ time: kLine[i].time, value: round(avg) });
  }

  return { k: kLine, d: dLine };
}

function generateOBV(
  times: number[],
  bars: OHLCVBar[],
): { time: number; value: number }[] {
  const result: { time: number; value: number }[] = [];
  let obv = 0;

  for (let i = 0; i < bars.length; i++) {
    if (i > 0) {
      if (bars[i].close > bars[i - 1].close) obv += bars[i].volume;
      else if (bars[i].close < bars[i - 1].close) obv -= bars[i].volume;
    }
    result.push({ time: times[i], value: obv });
  }

  return result;
}

function generateFibonacci(
  times: number[],
  closes: number[],
): Record<string, { time: number; value: number }[]> {
  if (closes.length < 2) return {};

  const max = Math.max(...closes);
  const min = Math.min(...closes);
  const diff = max - min;

  const levels = [0, 0.236, 0.382, 0.5, 0.618, 0.786, 1];
  const series: Record<string, { time: number; value: number }[]> = {};

  for (const level of levels) {
    const key = `fib_${(level * 100).toFixed(0)}`;
    series[key] = times.map((time) => ({
      time,
      value: round(max - diff * level),
    }));
  }

  return series;
}

function generateATR(
  times: number[],
  bars: OHLCVBar[],
): { time: number; value: number }[] {
  const lookback = 14;
  if (bars.length < lookback + 1) return [];

  const trueRanges: number[] = [];
  for (let i = 1; i < bars.length; i++) {
    const tr = Math.max(
      bars[i].high - bars[i].low,
      Math.abs(bars[i].high - bars[i - 1].close),
      Math.abs(bars[i].low - bars[i - 1].close),
    );
    trueRanges.push(tr);
  }

  const result: { time: number; value: number }[] = [];
  let atr = 0;
  for (let i = 0; i < lookback; i++) atr += trueRanges[i];
  atr /= lookback;
  result.push({ time: times[lookback], value: round(atr) });

  for (let i = lookback; i < trueRanges.length; i++) {
    atr = (atr * (lookback - 1) + trueRanges[i]) / lookback;
    result.push({ time: times[i + 1], value: round(atr) });
  }

  return result;
}

function generateIchimoku(
  times: number[],
  closes: number[],
): Record<string, { time: number; value: number }[]> {
  const tenkan: { time: number; value: number }[] = [];
  const kijun: { time: number; value: number }[] = [];

  // Tenkan-sen: (9-period high + 9-period low) / 2
  for (let i = 8; i < closes.length; i++) {
    const slice = closes.slice(i - 8, i + 1);
    const mid = (Math.max(...slice) + Math.min(...slice)) / 2;
    tenkan.push({ time: times[i], value: round(mid) });
  }

  // Kijun-sen: (26-period high + 26-period low) / 2
  for (let i = 25; i < closes.length; i++) {
    const slice = closes.slice(i - 25, i + 1);
    const mid = (Math.max(...slice) + Math.min(...slice)) / 2;
    kijun.push({ time: times[i], value: round(mid) });
  }

  return { tenkan, kijun };
}

function generateCCI(
  times: number[],
  bars: OHLCVBar[],
): { time: number; value: number }[] {
  const lookback = 20;
  const result: { time: number; value: number }[] = [];

  for (let i = lookback - 1; i < bars.length; i++) {
    const typicals: number[] = [];
    for (let j = i - lookback + 1; j <= i; j++) {
      typicals.push((bars[j].high + bars[j].low + bars[j].close) / 3);
    }
    const avg = typicals.reduce((a, b) => a + b, 0) / lookback;
    const meanDev =
      typicals.reduce((a, b) => a + Math.abs(b - avg), 0) / lookback;
    const cci = meanDev === 0 ? 0 : (typicals[typicals.length - 1] - avg) / (0.015 * meanDev);
    result.push({ time: times[i], value: round(cci) });
  }

  return result;
}
