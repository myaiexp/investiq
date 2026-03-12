import { useTranslation } from "react-i18next";
import type { FundPerformance } from "../types/index.ts";
import "./MetricsRow.css";

interface MetricsRowProps {
  metrics: FundPerformance;
}

export default function MetricsRow({ metrics }: MetricsRowProps) {
  const { t } = useTranslation();

  const items = [
    { label: t("funds.volatility"), value: `${metrics.volatility.toFixed(1)}%` },
    { label: t("funds.sharpe"), value: metrics.sharpe.toFixed(2) },
    {
      label: t("funds.maxDrawdown"),
      value: `${metrics.maxDrawdown.toFixed(1)}%`,
      negative: true,
    },
    { label: t("funds.ter"), value: `${metrics.ter.toFixed(2)}%` },
  ];

  return (
    <div className="metrics-row">
      {items.map((item) => (
        <div key={item.label} className="metrics-row__item">
          <span className="metrics-row__label">{item.label}</span>
          <span
            className={`metrics-row__value number${item.negative ? " metrics-row__value--negative" : ""}`}
          >
            {item.value}
          </span>
        </div>
      ))}
    </div>
  );
}
