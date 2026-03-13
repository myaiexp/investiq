export type Period = "1m" | "3m" | "6m" | "1y" | "5y";

/** Known interval presets. Custom intervals (e.g. "45m", "8H") are also valid strings. */
export type Interval =
  | "5m"
  | "15m"
  | "1H"
  | "2H"
  | "4H"
  | "8H"
  | "1D"
  | "3D"
  | "1W"
  | "2W"
  | (string & {});

export interface PeriodConfig {
  id: Period;
  intervals: string[];
  defaultInterval: string;
}

/**
 * Maps each period to its standard preset intervals and default.
 * Shorter periods allow intraday intervals; longer periods use daily/weekly.
 * Custom intervals beyond these presets are entered via the free-form input.
 */
export const PERIOD_INTERVAL_MAP: Record<Period, PeriodConfig> = {
  "1m": {
    id: "1m",
    intervals: ["5m", "15m", "1H", "4H", "1D"],
    defaultInterval: "1H",
  },
  "3m": {
    id: "3m",
    intervals: ["15m", "1H", "4H", "1D"],
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

/** Extra intervals shown in the dropdown (beyond standard presets). */
export const EXTRA_INTERVALS: string[] = ["2H", "8H", "3D", "2W"];
