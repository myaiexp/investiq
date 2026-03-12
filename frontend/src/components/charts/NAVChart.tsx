import { useEffect, useRef } from "react";
import {
  createChart,
  LineSeries,
  ColorType,
} from "lightweight-charts";
import type { IChartApi, UTCTimestamp } from "lightweight-charts";
import type { FundNAVPoint } from "../../types/index.ts";
import "./NAVChart.css";

interface NAVChartProps {
  fundData: FundNAVPoint[];
  benchmarkData?: FundNAVPoint[];
  fundName: string;
  benchmarkName?: string;
}

export default function NAVChart({
  fundData,
  benchmarkData,
  fundName,
  benchmarkName,
}: NAVChartProps) {
  const containerRef = useRef<HTMLDivElement>(null);
  const chartRef = useRef<IChartApi | null>(null);

  useEffect(() => {
    if (!containerRef.current || fundData.length === 0) return;

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
      crosshair: {
        vertLine: { color: "rgba(59, 130, 246, 0.3)" },
        horzLine: { color: "rgba(59, 130, 246, 0.3)" },
      },
      timeScale: { borderColor: "#1e293b" },
      rightPriceScale: { borderColor: "#1e293b" },
    });

    chartRef.current = chart;

    const fundSeries = chart.addSeries(LineSeries, {
      color: "#3b82f6",
      lineWidth: 2,
      title: fundName,
    });

    fundSeries.setData(
      fundData.map((p) => ({
        time: p.time as UTCTimestamp,
        value: p.value,
      })),
    );

    if (benchmarkData && benchmarkData.length > 0) {
      const benchSeries = chart.addSeries(LineSeries, {
        color: "#64748b",
        lineWidth: 1,
        lineStyle: 2,
        title: benchmarkName ?? "Benchmark",
      });

      benchSeries.setData(
        benchmarkData.map((p) => ({
          time: p.time as UTCTimestamp,
          value: p.value,
        })),
      );
    }

    chart.timeScale().fitContent();

    return () => {
      chart.remove();
      chartRef.current = null;
    };
  }, [fundData, benchmarkData, fundName, benchmarkName]);

  return <div ref={containerRef} className="nav-chart" />;
}
