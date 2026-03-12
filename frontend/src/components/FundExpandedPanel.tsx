import { useState, useEffect, useRef } from "react";
import { useTranslation } from "react-i18next";
import { Link } from "react-router-dom";
import {
  createChart,
  LineSeries,
  ColorType,
} from "lightweight-charts";
import type { IChartApi, UTCTimestamp } from "lightweight-charts";
import type { FundMeta, FundPerformance, FundNAVPoint } from "../types/index.ts";
import { api } from "../api/client.ts";
import PerformanceTable from "./PerformanceTable.tsx";
import MetricsRow from "./MetricsRow.tsx";
import "./FundExpandedPanel.css";

interface FundExpandedPanelProps {
  fund: FundMeta;
}

export default function FundExpandedPanel({ fund }: FundExpandedPanelProps) {
  const { t } = useTranslation();
  const containerRef = useRef<HTMLDivElement>(null);
  const chartRef = useRef<IChartApi | null>(null);
  const [performance, setPerformance] = useState<FundPerformance | null>(null);
  const [navData, setNavData] = useState<FundNAVPoint[]>([]);
  const [benchmarkData, setBenchmarkData] = useState<FundNAVPoint[]>([]);

  useEffect(() => {
    api.getFundPerformance(fund.ticker).then(setPerformance);
    api.getFundNAV(fund.ticker, "1y").then(setNavData);

    if (fund.benchmarkTicker) {
      api.getFundNAV(fund.benchmarkTicker, "1y").then(setBenchmarkData);
    }
  }, [fund.ticker, fund.benchmarkTicker]);

  useEffect(() => {
    if (!containerRef.current || navData.length === 0) return;
    if (fund.benchmarkTicker && benchmarkData.length === 0) return;

    const chart = createChart(containerRef.current, {
      autoSize: true,
      layout: {
        background: { type: ColorType.Solid, color: "transparent" },
        textColor: "#94a3b8",
        fontFamily: '"Inter", system-ui, -apple-system, sans-serif',
        fontSize: 11,
      },
      grid: {
        vertLines: { color: "rgba(30, 41, 59, 0.5)" },
        horzLines: { color: "rgba(30, 41, 59, 0.5)" },
      },
      timeScale: { borderColor: "#1e293b" },
      rightPriceScale: { borderColor: "#1e293b" },
    });

    chartRef.current = chart;

    // Normalize to percentage change when benchmark is present
    const hasBenchmark = benchmarkData.length > 0;
    const fundBase = navData[0]?.value ?? 1;
    const benchBase = benchmarkData[0]?.value ?? 1;
    const pctFormatter = (v: number) => `${v >= 0 ? "+" : ""}${v.toFixed(1)}%`;

    const fundSeries = chart.addSeries(LineSeries, {
      color: "#3b82f6",
      lineWidth: 2,
      title: "",
      priceFormat: hasBenchmark
        ? { type: "custom", formatter: pctFormatter }
        : { type: "price", precision: 2, minMove: 0.01 },
    });

    fundSeries.setData(
      navData.map((p) => ({
        time: p.time as UTCTimestamp,
        value: hasBenchmark ? ((p.value - fundBase) / fundBase) * 100 : p.value,
      })),
    );

    if (hasBenchmark) {
      const benchSeries = chart.addSeries(LineSeries, {
        color: "#64748b",
        lineWidth: 1,
        lineStyle: 2,
        title: "",
        priceFormat: { type: "custom", formatter: pctFormatter },
      });

      benchSeries.setData(
        benchmarkData.map((p) => ({
          time: p.time as UTCTimestamp,
          value: ((p.value - benchBase) / benchBase) * 100,
        })),
      );
    }

    chart.timeScale().fitContent();

    return () => {
      chart.remove();
      chartRef.current = null;
    };
  }, [navData, benchmarkData, fund.name, fund.benchmarkName]);

  return (
    <div className="fund-expanded" onClick={(e) => e.stopPropagation()}>
      <div className="fund-expanded__chart" ref={containerRef} />
      <div className="fund-expanded__details">
        {performance && (
          <>
            <PerformanceTable
              fundReturns={performance.returns}
              benchmarkReturns={performance.benchmarkReturns}
              benchmarkName={fund.benchmarkName}
            />
            <MetricsRow metrics={performance} />
          </>
        )}
      </div>
      <Link
        to={`/funds/${encodeURIComponent(fund.ticker)}`}
        className="fund-expanded__link"
        onClick={(e) => e.stopPropagation()}
      >
        {t("detail.fullAnalysis")} →
      </Link>
    </div>
  );
}
