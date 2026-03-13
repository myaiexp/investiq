import type { Period } from "../types/index.ts";
import { PERIOD_INTERVAL_MAP } from "../types/index.ts";
import "./IntervalSelector.css";

/** Standard preset intervals in display order */
const PRESET_INTERVALS: string[] = [
  "5m",
  "15m",
  "1H",
  "4H",
  "1D",
  "1W",
];

interface IntervalSelectorProps {
  period: Period;
  value: string;
  onChange: (interval: string) => void;
}

/**
 * Interval selector showing standard presets constrained by PERIOD_INTERVAL_MAP.
 * Task 8 will add dropdown extras and free-form custom input.
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
      {PRESET_INTERVALS.map((interval) => {
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
            {interval}
          </button>
        );
      })}
    </div>
  );
}
