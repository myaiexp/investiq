import { useEffect, useRef } from "react";
import {
  createChart,
  BaselineSeries,
  ColorType,
} from "lightweight-charts";
import type { IChartApi, UTCTimestamp } from "lightweight-charts";
import type { FundNAVPoint } from "../../types/index.ts";
import "./RelativePerformanceChart.css";

interface RelativePerformanceChartProps {
  fundData: FundNAVPoint[];
  benchmarkData: FundNAVPoint[];
}

export default function RelativePerformanceChart({
  fundData,
  benchmarkData,
}: RelativePerformanceChartProps) {
  const containerRef = useRef<HTMLDivElement>(null);
  const chartRef = useRef<IChartApi | null>(null);

  useEffect(() => {
    if (
      !containerRef.current ||
      fundData.length === 0 ||
      benchmarkData.length === 0
    )
      return;

    // Build a map of benchmark values by time
    const benchMap = new Map<number, number>();
    for (const p of benchmarkData) {
      benchMap.set(p.time, p.value);
    }

    // Calculate relative returns (fund - benchmark) normalized to first point
    const fundStart = fundData[0].value;
    const benchStart = benchmarkData[0]?.value ?? fundStart;

    const relativeData = fundData
      .filter((p) => benchMap.has(p.time))
      .map((p) => {
        const fundReturn = ((p.value - fundStart) / fundStart) * 100;
        const benchReturn =
          ((benchMap.get(p.time)! - benchStart) / benchStart) * 100;
        return {
          time: p.time as UTCTimestamp,
          value: Math.round((fundReturn - benchReturn) * 100) / 100,
        };
      });

    if (relativeData.length === 0) return;

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
      rightPriceScale: {
        borderColor: "#1e293b",
      },
    });

    chartRef.current = chart;

    const series = chart.addSeries(BaselineSeries, {
      baseValue: { type: "price", price: 0 },
      topLineColor: "#22c55e",
      bottomLineColor: "#ef4444",
      topFillColor1: "rgba(34, 197, 94, 0.2)",
      topFillColor2: "rgba(34, 197, 94, 0.0)",
      bottomFillColor1: "rgba(239, 68, 68, 0.0)",
      bottomFillColor2: "rgba(239, 68, 68, 0.2)",
    });

    series.setData(relativeData);
    chart.timeScale().fitContent();

    return () => {
      chart.remove();
      chartRef.current = null;
    };
  }, [fundData, benchmarkData]);

  return <div ref={containerRef} className="relative-perf-chart" />;
}
