export type Signal = "buy" | "sell" | "hold";
export type Region = "nordic" | "global";
export type IndicatorId =
  | "rsi"
  | "macd"
  | "bollinger"
  | "ma"
  | "stochastic"
  | "obv"
  | "fibonacci"
  | "atr"
  | "ichimoku"
  | "cci";
export type IndicatorCategory = "overlay" | "oscillator";

export interface IndexMeta {
  name: string;
  ticker: string;
  region: Region;
  price: number;
  dailyChange: number;
  signal: Signal;
  currency?: string | null;
  dataNote?: string | null;
}

export interface OHLCVBar {
  /** Unix seconds — matches lightweight-charts Time */
  time: number;
  open: number;
  high: number;
  low: number;
  close: number;
  volume: number;
}

export interface OHLCVResponse {
  bars: OHLCVBar[];
  dataTransitionTimestamp?: number | null;
  lastUpdated?: number | null;
}

export interface IndicatorMeta {
  id: IndicatorId;
  category: IndicatorCategory;
  signal: Signal;
}

export interface IndicatorData {
  id: IndicatorId;
  series: Record<string, { time: number; value: number }[]>;
  signal: Signal;
}

export interface SignalSummary {
  aggregate: Signal;
  breakdown: IndicatorMeta[];
  activeCount: { buy: number; sell: number; hold: number };
}
