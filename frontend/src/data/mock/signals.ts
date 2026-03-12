import type {
  SignalSummary,
  IndicatorMeta,
  Signal,
  IndicatorId,
} from "../../types/index.ts";

/**
 * Pre-computed signal summaries for each index.
 * These are deterministic — same result every time for a given ticker.
 * Uses a simple hash to distribute buy/sell/hold across indicators.
 */

function hashCode(s: string): number {
  let h = 0;
  for (let i = 0; i < s.length; i++) {
    h = (Math.imul(31, h) + s.charCodeAt(i)) | 0;
  }
  return Math.abs(h);
}

const ALL_INDICATORS: { id: IndicatorId; category: "overlay" | "oscillator" }[] = [
  { id: "rsi", category: "oscillator" },
  { id: "macd", category: "oscillator" },
  { id: "bollinger", category: "overlay" },
  { id: "ma", category: "overlay" },
  { id: "stochastic", category: "oscillator" },
  { id: "obv", category: "oscillator" },
  { id: "fibonacci", category: "overlay" },
  { id: "atr", category: "oscillator" },
  { id: "ichimoku", category: "overlay" },
  { id: "cci", category: "oscillator" },
];

const SIGNAL_MAP: Signal[] = ["buy", "sell", "hold"];

function computeSignalSummary(ticker: string): SignalSummary {
  const seed = hashCode(ticker);
  const counts = { buy: 0, sell: 0, hold: 0 };
  const breakdown: IndicatorMeta[] = [];

  for (let i = 0; i < ALL_INDICATORS.length; i++) {
    const indicator = ALL_INDICATORS[i];
    const signalIdx = (seed + i * 7 + i * i) % 3;
    const signal = SIGNAL_MAP[signalIdx];
    counts[signal]++;
    breakdown.push({
      id: indicator.id,
      category: indicator.category,
      signal,
    });
  }

  // Aggregate: majority vote
  let aggregate: Signal = "hold";
  if (counts.buy > counts.sell && counts.buy > counts.hold) {
    aggregate = "buy";
  } else if (counts.sell > counts.buy && counts.sell > counts.hold) {
    aggregate = "sell";
  }

  return {
    aggregate,
    breakdown,
    activeCount: counts,
  };
}

/** Pre-computed signal summaries keyed by ticker */
export const MOCK_SIGNALS: Record<string, SignalSummary> = {
  "^OMXH25": computeSignalSummary("^OMXH25"),
  "^OMXS30": computeSignalSummary("^OMXS30"),
  "^OMXC25": computeSignalSummary("^OMXC25"),
  "OBX.OL": computeSignalSummary("OBX.OL"),
  "^GSPC": computeSignalSummary("^GSPC"),
  "^NDX": computeSignalSummary("^NDX"),
  "^GDAXI": computeSignalSummary("^GDAXI"),
  "^FTSE": computeSignalSummary("^FTSE"),
  "^N225": computeSignalSummary("^N225"),
  URTH: computeSignalSummary("URTH"),
};
