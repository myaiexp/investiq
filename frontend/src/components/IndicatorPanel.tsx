import { useTranslation } from "react-i18next";
import type { IndicatorId, IndicatorMeta } from "../types/index.ts";
import "./IndicatorPanel.css";

interface IndicatorPanelProps {
  indicators: IndicatorMeta[];
  enabled: Set<IndicatorId>;
  onToggle: (id: IndicatorId) => void;
}

/**
 * Toggle list for all indicators. Each row shows the indicator name (i18n)
 * and a signal dot. Renders as a sidebar on desktop, prepared for
 * drawer layout on mobile via CSS.
 */
export default function IndicatorPanel({
  indicators,
  enabled,
  onToggle,
}: IndicatorPanelProps) {
  const { t } = useTranslation();

  return (
    <div className="indicator-panel">
      <h3 className="indicator-panel__title">
        {t("indicators.rsi") === "RSI" ? "Indicators" : "Indikaattorit"}
      </h3>
      <ul className="indicator-panel__list">
        {indicators.map((ind) => {
          const isEnabled = enabled.has(ind.id);

          return (
            <li key={ind.id} className="indicator-panel__item">
              <button
                className={`indicator-panel__toggle${isEnabled ? " indicator-panel__toggle--active" : ""}`}
                onClick={() => onToggle(ind.id)}
                aria-pressed={isEnabled}
              >
                <span
                  className={`indicator-panel__dot signal-dot--${ind.signal}`}
                  aria-label={t(`signal.${ind.signal}`)}
                />
                <span className="indicator-panel__name">
                  {t(`indicators.${ind.id}`)}
                </span>
                <span className="indicator-panel__category">
                  {ind.category === "overlay" ? "OVL" : "OSC"}
                </span>
              </button>
            </li>
          );
        })}
      </ul>
    </div>
  );
}
