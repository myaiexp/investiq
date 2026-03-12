import { useTranslation } from "react-i18next";
import type { SignalSummary, Signal } from "../types/index.ts";
import "./SignalSummaryCard.css";

interface SignalSummaryCardProps {
  summary: SignalSummary;
}

const SIGNAL_ORDER: Signal[] = ["buy", "hold", "sell"];

/**
 * Aggregate verdict card + per-indicator breakdown.
 * Shows the majority-vote result prominently, with a count bar
 * and individual indicator signals below.
 */
export default function SignalSummaryCard({
  summary,
}: SignalSummaryCardProps) {
  const { t } = useTranslation();

  const total =
    summary.activeCount.buy +
    summary.activeCount.sell +
    summary.activeCount.hold;

  return (
    <div className="signal-summary card">
      {/* Aggregate verdict */}
      <div className="signal-summary__verdict">
        <span className="signal-summary__label">
          {t("indicators.rsi") === "RSI" ? "Signal" : "Signaali"}
        </span>
        <span
          className={`signal-summary__aggregate signal-${summary.aggregate}`}
        >
          {t(`signal.${summary.aggregate}`)}
        </span>
      </div>

      {/* Count bar */}
      {total > 0 && (
        <div className="signal-summary__bar">
          {SIGNAL_ORDER.map((signal) => {
            const count = summary.activeCount[signal];
            if (count === 0) return null;
            const pct = (count / total) * 100;

            return (
              <div
                key={signal}
                className={`signal-summary__bar-segment signal-summary__bar-segment--${signal}`}
                style={{ width: `${pct}%` }}
                title={`${t(`signal.${signal}`)}: ${count}`}
              >
                {count}
              </div>
            );
          })}
        </div>
      )}

      {/* Per-indicator breakdown */}
      {summary.breakdown.length > 0 && (
        <ul className="signal-summary__breakdown">
          {summary.breakdown.map((ind) => (
            <li key={ind.id} className="signal-summary__item">
              <span className="signal-summary__ind-name">
                {t(`indicators.${ind.id}`)}
              </span>
              <span
                className={`signal-summary__ind-signal signal-${ind.signal}`}
              >
                {t(`signal.${ind.signal}`)}
              </span>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}
