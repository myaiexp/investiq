import { useTranslation } from "react-i18next";
import "./PerformanceTable.css";

interface PerformanceTableProps {
  fundReturns: { "1y": number; "3y": number; "5y": number };
  benchmarkReturns: { "1y": number; "3y": number; "5y": number };
  benchmarkName: string;
}

export default function PerformanceTable({
  fundReturns,
  benchmarkReturns,
  benchmarkName,
}: PerformanceTableProps) {
  const { t } = useTranslation();

  const periods = ["1y", "3y", "5y"] as const;

  const formatReturn = (val: number) => {
    const sign = val > 0 ? "+" : "";
    return `${sign}${val.toFixed(1)}%`;
  };

  const colorClass = (val: number) =>
    val > 0 ? "perf-table__positive" : val < 0 ? "perf-table__negative" : "";

  return (
    <table className="perf-table">
      <thead>
        <tr>
          <th></th>
          {periods.map((p) => (
            <th key={p} className="perf-table__period">
              {t(`funds.return${p}`)}
            </th>
          ))}
        </tr>
      </thead>
      <tbody>
        <tr>
          <td className="perf-table__label">{t("funds.fund")}</td>
          {periods.map((p) => (
            <td
              key={p}
              className={`perf-table__value number ${colorClass(fundReturns[p])}`}
            >
              {formatReturn(fundReturns[p])}
            </td>
          ))}
        </tr>
        <tr>
          <td className="perf-table__label">{benchmarkName}</td>
          {periods.map((p) => (
            <td
              key={p}
              className={`perf-table__value number ${colorClass(benchmarkReturns[p])}`}
            >
              {formatReturn(benchmarkReturns[p])}
            </td>
          ))}
        </tr>
      </tbody>
    </table>
  );
}
