export type FundType = "equity" | "bond";

export interface FundMeta {
  name: string;
  ticker: string;
  isin: string | null;
  fundType: FundType;
  benchmarkTicker: string | null;
  benchmarkName: string;
  nav: number;
  dailyChange: number;
  return1Y: number;
}

export interface FundNAVPoint {
  /** Unix seconds */
  time: number;
  value: number;
}

export interface FundPerformance {
  returns: { "1y": number; "3y": number; "5y": number };
  benchmarkReturns: { "1y": number; "3y": number; "5y": number };
  volatility: number;
  sharpe: number;
  maxDrawdown: number;
  /** Total expense ratio */
  ter: number;
}
