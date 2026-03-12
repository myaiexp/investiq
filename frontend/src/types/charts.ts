export type Period = "1m" | "3m" | "6m" | "1y" | "5y";
export type Interval =
  | "1m"
  | "5m"
  | "15m"
  | "1H"
  | "2H"
  | "4H"
  | "1D"
  | "1W";

export interface PeriodConfig {
  id: Period;
  intervals: Interval[];
  defaultInterval: Interval;
}

/**
 * Maps each period to its available intervals and default.
 * Shorter periods allow intraday intervals; longer periods use daily/weekly.
 */
export const PERIOD_INTERVAL_MAP: Record<Period, PeriodConfig> = {
  "1m": {
    id: "1m",
    intervals: ["1m", "5m", "15m", "1H", "2H", "4H", "1D"],
    defaultInterval: "1H",
  },
  "3m": {
    id: "3m",
    intervals: ["15m", "1H", "2H", "4H", "1D"],
    defaultInterval: "1D",
  },
  "6m": {
    id: "6m",
    intervals: ["1H", "4H", "1D", "1W"],
    defaultInterval: "1D",
  },
  "1y": {
    id: "1y",
    intervals: ["4H", "1D", "1W"],
    defaultInterval: "1D",
  },
  "5y": {
    id: "5y",
    intervals: ["1D", "1W"],
    defaultInterval: "1W",
  },
};
