import { useTranslation } from "react-i18next";
import type { Period } from "../types/index.ts";
import "./PeriodSelector.css";

const PERIODS: Period[] = ["1m", "3m", "6m", "1y", "5y"];

interface PeriodSelectorProps {
  value: Period;
  onChange: (period: Period) => void;
}

/**
 * Period pills (1kk–5v). Renders a row of selectable period buttons.
 */
export default function PeriodSelector({
  value,
  onChange,
}: PeriodSelectorProps) {
  const { t } = useTranslation();

  return (
    <div className="period-selector" role="radiogroup">
      {PERIODS.map((period) => (
        <button
          key={period}
          className={`period-selector__pill${period === value ? " period-selector__pill--active" : ""}`}
          onClick={() => onChange(period)}
          role="radio"
          aria-checked={period === value}
        >
          {t(`period.${period}`)}
        </button>
      ))}
    </div>
  );
}
