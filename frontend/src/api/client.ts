import type {
  IndexMeta,
  OHLCVResponse,
  IndicatorData,
  SignalSummary,
} from "../types/index.ts";
import type { FundMeta, FundNAVPoint, FundPerformance } from "../types/funds.ts";
import type { Period } from "../types/charts.ts";

const BASE = import.meta.env.DEV ? "/api" : "/investiq/api";

async function get<T>(path: string): Promise<T> {
  const res = await fetch(`${BASE}${path}`);
  if (!res.ok) throw new Error(`API ${res.status}: ${path}`);
  return res.json();
}

export interface Api {
  getIndices: () => Promise<IndexMeta[]>;
  getOHLCV: (
    ticker: string,
    period?: Period,
    interval?: string,
  ) => Promise<OHLCVResponse>;
  getIndicators: (
    ticker: string,
    period?: Period,
    interval?: string,
  ) => Promise<IndicatorData[]>;
  getSignal: (ticker: string) => Promise<SignalSummary>;
  getFunds: () => Promise<FundMeta[]>;
  getFundPerformance: (ticker: string) => Promise<FundPerformance>;
  getFundNAV: (ticker: string, period?: Period) => Promise<FundNAVPoint[]>;
}

export const api: Api = {
  getIndices: () => get<IndexMeta[]>("/indices/"),

  getOHLCV: (ticker: string, period: Period = "1y", interval: string = "1D") =>
    get<OHLCVResponse>(
      `/indices/${encodeURIComponent(ticker)}/ohlcv?period=${period}&interval=${interval}`,
    ),

  getIndicators: (ticker: string, period: Period = "1y", interval: string = "1D") =>
    get<IndicatorData[]>(
      `/indices/${encodeURIComponent(ticker)}/indicators?period=${period}&interval=${interval}`,
    ),

  getSignal: (ticker: string) =>
    get<SignalSummary>(`/indices/${encodeURIComponent(ticker)}/signal`),

  getFunds: () => get<FundMeta[]>("/funds/"),

  getFundPerformance: (ticker: string) =>
    get<FundPerformance>(`/funds/${encodeURIComponent(ticker)}/performance`),

  getFundNAV: (ticker: string, period: Period = "1y") =>
    get<FundNAVPoint[]>(
      `/funds/${encodeURIComponent(ticker)}/nav?period=${period}`,
    ),
};
