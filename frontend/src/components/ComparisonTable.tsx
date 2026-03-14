import { useTranslation } from "react-i18next";
import type { FundPerformance } from "../types/index.ts";
import "./ComparisonTable.css";

interface ComparisonTableFund {
  ticker: string;
  name: string;
  performance: FundPerformance;
}

interface ComparisonTableProps {
  funds: ComparisonTableFund[];
}

type MetricKey = "return1y" | "return3y" | "return5y" | "volatility" | "sharpe" | "maxDrawdown";

interface MetricDef {
  key: MetricKey;
  labelKey: string;
  getValue: (p: FundPerformance) => number;
  /** Higher is better (true) or lower is better (false) */
  higherIsBetter: boolean;
  format: (v: number) => string;
}

const METRICS: MetricDef[] = [
  {
    key: "return1y",
    labelKey: "funds.return1y",
    getValue: (p) => p.returns["1y"],
    higherIsBetter: true,
    format: (v) => `${v >= 0 ? "+" : ""}${v.toFixed(2)}%`,
  },
  {
    key: "return3y",
    labelKey: "funds.return3y",
    getValue: (p) => p.returns["3y"],
    higherIsBetter: true,
    format: (v) => `${v >= 0 ? "+" : ""}${v.toFixed(2)}%`,
  },
  {
    key: "return5y",
    labelKey: "funds.return5y",
    getValue: (p) => p.returns["5y"],
    higherIsBetter: true,
    format: (v) => `${v >= 0 ? "+" : ""}${v.toFixed(2)}%`,
  },
  {
    key: "volatility",
    labelKey: "funds.volatility",
    getValue: (p) => p.volatility,
    higherIsBetter: false,
    format: (v) => `${v.toFixed(2)}%`,
  },
  {
    key: "sharpe",
    labelKey: "funds.sharpe",
    getValue: (p) => p.sharpe,
    higherIsBetter: true,
    format: (v) => v.toFixed(2),
  },
  {
    key: "maxDrawdown",
    labelKey: "funds.maxDrawdown",
    getValue: (p) => p.maxDrawdown,
    higherIsBetter: false,
    format: (v) => `${v.toFixed(2)}%`,
  },
];

export default function ComparisonTable({ funds }: ComparisonTableProps) {
  const { t } = useTranslation();

  if (funds.length === 0) return null;

  return (
    <div className="comparison-table__wrapper">
      <table className="comparison-table">
        <thead>
          <tr>
            <th className="comparison-table__metric-col">{t("funds.performanceComparison")}</th>
            {funds.map((f) => (
              <th key={f.ticker} className="comparison-table__fund-col">
                {f.name}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {METRICS.map((metric) => {
            const values = funds.map((f) => metric.getValue(f.performance));
            const best = metric.higherIsBetter
              ? Math.max(...values)
              : Math.min(...values);

            return (
              <tr key={metric.key} className="comparison-table__row">
                <td className="comparison-table__label">{t(metric.labelKey)}</td>
                {funds.map((f, i) => {
                  const value = values[i];
                  const isBest = value === best;
                  return (
                    <td
                      key={f.ticker}
                      className={`comparison-table__value number${isBest ? " comparison-table__value--best" : ""}`}
                    >
                      {metric.format(value)}
                    </td>
                  );
                })}
              </tr>
            );
          })}
        </tbody>
      </table>
    </div>
  );
}
