import { useTranslation } from "react-i18next";
import type { FundPerformance } from "../types/index.ts";
import "./MetricsRow.css";

interface MetricsRowProps {
  metrics: FundPerformance;
  dataNotes?: Record<string, string> | null;
}

export default function MetricsRow({ metrics, dataNotes }: MetricsRowProps) {
  const { t } = useTranslation();

  const terNote = dataNotes?.ter;

  const items = [
    { label: t("funds.volatility"), value: `${metrics.volatility.toFixed(1)}%` },
    { label: t("funds.sharpe"), value: metrics.sharpe.toFixed(2) },
    {
      label: t("funds.maxDrawdown"),
      value: `${metrics.maxDrawdown.toFixed(1)}%`,
      negative: true,
    },
    {
      label: t("funds.ter"),
      value: terNote ? "N/A" : `${metrics.ter.toFixed(2)}%`,
      note: terNote,
    },
  ];

  return (
    <div className="metrics-row">
      {items.map((item) => (
        <div key={item.label} className="metrics-row__item">
          <span className="metrics-row__label">{item.label}</span>
          <span
            className={`metrics-row__value number${item.negative ? " metrics-row__value--negative" : ""}${item.note ? " metrics-row__value--noted" : ""}`}
            title={item.note}
          >
            {item.value}
          </span>
        </div>
      ))}
    </div>
  );
}
