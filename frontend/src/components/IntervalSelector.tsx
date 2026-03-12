import type { Period, Interval } from "../types/index.ts";
import { PERIOD_INTERVAL_MAP } from "../types/index.ts";
import "./IntervalSelector.css";

/** Display labels for intervals */
const INTERVAL_LABELS: Record<Interval, string> = {
  "1m": "1m",
  "5m": "5m",
  "15m": "15m",
  "1H": "1H",
  "2H": "2H",
  "4H": "4H",
  "1D": "1D",
  "1W": "1W",
};

/** All intervals in display order */
const ALL_INTERVALS: Interval[] = [
  "1m",
  "5m",
  "15m",
  "1H",
  "2H",
  "4H",
  "1D",
  "1W",
];

interface IntervalSelectorProps {
  period: Period;
  value: Interval;
  onChange: (interval: Interval) => void;
}

/**
 * Interval selector constrained by the active period via PERIOD_INTERVAL_MAP.
 * Unavailable intervals are greyed out and non-interactive.
 */
export default function IntervalSelector({
  period,
  value,
  onChange,
}: IntervalSelectorProps) {
  const config = PERIOD_INTERVAL_MAP[period];
  const available = new Set(config.intervals);

  return (
    <div className="interval-selector" role="radiogroup">
      {ALL_INTERVALS.map((interval) => {
        const isAvailable = available.has(interval);
        const isActive = interval === value;

        return (
          <button
            key={interval}
            className={`interval-selector__btn${isActive ? " interval-selector__btn--active" : ""}${!isAvailable ? " interval-selector__btn--disabled" : ""}`}
            onClick={() => isAvailable && onChange(interval)}
            disabled={!isAvailable}
            role="radio"
            aria-checked={isActive}
            aria-disabled={!isAvailable}
          >
            {INTERVAL_LABELS[interval]}
          </button>
        );
      })}
    </div>
  );
}
