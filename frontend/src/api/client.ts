import type {
  IndexMeta,
  OHLCVBar,
  IndicatorData,
  SignalSummary,
} from "../types/index.ts";
import type { FundMeta, FundNAVPoint, FundPerformance } from "../types/funds.ts";
import type { Period, Interval } from "../types/charts.ts";
import {
  MOCK_INDICES,
  MOCK_FUNDS,
  MOCK_SIGNALS,
  generateOHLCV,
  generateFundNAV,
  generateFundPerformance,
  generateIndicatorData,
} from "../data/mock/index.ts";

/**
 * Simulates network latency for a more realistic dev experience.
 * Remove when switching to real API.
 */
function delay(ms = 80): Promise<void> {
  return new Promise((resolve) => setTimeout(resolve, ms));
}

export interface Api {
  getIndices: () => Promise<IndexMeta[]>;
  getOHLCV: (
    ticker: string,
    period?: Period,
    interval?: Interval,
  ) => Promise<OHLCVBar[]>;
  getIndicators: (
    ticker: string,
    period?: Period,
    interval?: Interval,
  ) => Promise<IndicatorData[]>;
  getSignal: (ticker: string) => Promise<SignalSummary>;
  getFunds: () => Promise<FundMeta[]>;
  getFundPerformance: (ticker: string) => Promise<FundPerformance>;
  getFundNAV: (ticker: string, period?: Period) => Promise<FundNAVPoint[]>;
}

/**
 * Mock API implementation — returns generated data from local mock layer.
 * Same interface as the future real API client.
 */
export const api: Api = {
  getIndices: async () => {
    await delay();
    return MOCK_INDICES;
  },

  getOHLCV: async (
    ticker: string,
    period: Period = "1y",
    interval: Interval = "1D",
  ) => {
    await delay(120);
    return generateOHLCV(ticker, period, interval);
  },

  getIndicators: async (
    ticker: string,
    period: Period = "1y",
    interval: Interval = "1D",
  ) => {
    await delay(100);
    return generateIndicatorData(ticker, period, interval);
  },

  getSignal: async (ticker: string) => {
    await delay();
    return (
      MOCK_SIGNALS[ticker] ?? {
        aggregate: "hold" as const,
        breakdown: [],
        activeCount: { buy: 0, sell: 0, hold: 0 },
      }
    );
  },

  getFunds: async () => {
    await delay();
    return MOCK_FUNDS;
  },

  getFundPerformance: async (ticker: string) => {
    await delay(100);
    return generateFundPerformance(ticker);
  },

  getFundNAV: async (ticker: string, period: Period = "1y") => {
    await delay(120);
    return generateFundNAV(ticker, period);
  },
};
