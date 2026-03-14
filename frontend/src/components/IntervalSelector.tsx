import { useState } from "react";
import type { Period } from "../types/index.ts";
import { PERIOD_INTERVAL_MAP, EXTRA_INTERVALS } from "../types/index.ts";
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

/** All known presets (standard + extras) for checking if a value is custom */
const ALL_KNOWN = new Set([...PRESET_INTERVALS, ...EXTRA_INTERVALS]);

/** Client-side validation for custom interval strings */
const CUSTOM_INTERVAL_RE = /^[1-9]\d{0,2}[mHDW]$/;

interface IntervalSelectorProps {
  period: Period;
  value: string;
  onChange: (interval: string) => void;
}

/**
 * Two-tier interval selector:
 * 1. Buttons for standard presets + extras (5m…1W + 2H, 8H, 3D, 2W)
 * 2. Free-form text input for custom intervals
 *
 * Standard presets are gated by PERIOD_INTERVAL_MAP (greyed out if the period
 * is too short). Extras are always enabled — the backend validates and rejects
 * intervals that produce too few candles.
 */
export default function IntervalSelector({
  period,
  value,
  onChange,
}: IntervalSelectorProps) {
  const config = PERIOD_INTERVAL_MAP[period];
  const available = new Set(config.intervals);
  const [customInput, setCustomInput] = useState("");
  const [customError, setCustomError] = useState("");

  const isCustomValue = !ALL_KNOWN.has(value);

  const submitCustom = (raw: string) => {
    const trimmed = raw.trim();
    if (!trimmed) {
      setCustomError("");
      return;
    }
    if (!CUSTOM_INTERVAL_RE.test(trimmed)) {
      setCustomError("Format: 1-999 + m/H/D/W (e.g. 45m, 2D)");
      return;
    }
    setCustomError("");
    setCustomInput("");
    onChange(trimmed);
  };

  const handleCustomKeyDown = (e: React.KeyboardEvent<HTMLInputElement>) => {
    if (e.key === "Enter") {
      e.preventDefault();
      submitCustom(customInput);
    }
  };

  const handleCustomBlur = () => {
    submitCustom(customInput);
  };

  return (
    <div className="interval-selector">
      {/* Standard preset buttons */}
      <div className="interval-selector__presets" role="radiogroup">
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

        {/* Separator */}
        <span className="interval-selector__sep" aria-hidden="true" />

        {/* Extra interval buttons — always enabled */}
        {EXTRA_INTERVALS.map((interval) => {
          const isActive = interval === value;
          return (
            <button
              key={interval}
              className={`interval-selector__btn interval-selector__btn--extra${isActive ? " interval-selector__btn--active" : ""}`}
              onClick={() => onChange(interval)}
              role="radio"
              aria-checked={isActive}
            >
              {interval}
            </button>
          );
        })}
      </div>

      {/* Free-form custom input */}
      <div className="interval-selector__custom">
        <input
          type="text"
          className={`interval-selector__input${isCustomValue ? " interval-selector__input--active" : ""}${customError ? " interval-selector__input--error" : ""}`}
          placeholder={isCustomValue ? value : "Custom"}
          value={customInput}
          onChange={(e) => {
            setCustomInput(e.target.value);
            if (customError) setCustomError("");
          }}
          onKeyDown={handleCustomKeyDown}
          onBlur={handleCustomBlur}
          maxLength={5}
          aria-label="Custom interval"
        />
        {customError && (
          <span className="interval-selector__error">{customError}</span>
        )}
      </div>
    </div>
  );
}
