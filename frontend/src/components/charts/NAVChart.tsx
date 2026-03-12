import { useEffect, useRef, useState, useCallback } from "react";
import {
  createChart,
  LineSeries,
  ColorType,
} from "lightweight-charts";
import type { IChartApi, ISeriesApi, SeriesType, UTCTimestamp } from "lightweight-charts";
import type { FundNAVPoint } from "../../types/index.ts";
import "./NAVChart.css";

interface NAVChartProps {
  fundData: FundNAVPoint[];
  benchmarkData?: FundNAVPoint[];
  fundName: string;
  benchmarkName?: string;
}

interface TooltipData {
  visible: boolean;
  x: number;
  y: number;
  fundPrice?: string;
  fundPct?: string;
  benchPrice?: string;
  benchPct?: string;
}

export default function NAVChart({
  fundData,
  benchmarkData,
  fundName,
  benchmarkName,
}: NAVChartProps) {
  const containerRef = useRef<HTMLDivElement>(null);
  const chartRef = useRef<IChartApi | null>(null);
  const tooltipRef = useRef<HTMLDivElement>(null);
  const [tooltip, setTooltip] = useState<TooltipData>({ visible: false, x: 0, y: 0 });

  const fmtPrice = useCallback(
    (v: number) => v.toLocaleString("fi-FI", { minimumFractionDigits: 2, maximumFractionDigits: 2 }),
    [],
  );
  const fmtPct = useCallback(
    (v: number) => `${v >= 0 ? "+" : ""}${v.toFixed(2)}%`,
    [],
  );

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

    const hasBenchmark = benchmarkData && benchmarkData.length > 0;
    const normalize = hasBenchmark && fundData.length > 0;
    const fundBase = fundData[0]?.value ?? 1;
    const benchBase = benchmarkData?.[0]?.value ?? 1;

    // Build lookup maps for absolute prices
    const fundAbsolute = new Map<number, number>();
    for (const p of fundData) fundAbsolute.set(p.time, p.value);
    const benchAbsolute = new Map<number, number>();
    if (hasBenchmark) {
      for (const p of benchmarkData!) benchAbsolute.set(p.time, p.value);
    }

    const fundSeries = chart.addSeries(LineSeries, {
      color: "#3b82f6",
      lineWidth: 2,
      title: "",
      priceFormat: normalize
        ? { type: "custom", formatter: (v: number) => `${v >= 0 ? "+" : ""}${v.toFixed(2)}%` }
        : { type: "price", precision: 2, minMove: 0.01 },
    });

    fundSeries.setData(
      fundData.map((p) => ({
        time: p.time as UTCTimestamp,
        value: normalize ? ((p.value - fundBase) / fundBase) * 100 : p.value,
      })),
    );

    let benchSeries: ISeriesApi<SeriesType> | null = null;
    if (hasBenchmark) {
      benchSeries = chart.addSeries(LineSeries, {
        color: "#64748b",
        lineWidth: 1,
        lineStyle: 2,
        title: "",
        priceFormat: {
          type: "custom",
          formatter: (v: number) => `${v >= 0 ? "+" : ""}${v.toFixed(2)}%`,
        },
      });

      benchSeries.setData(
        benchmarkData!.map((p) => ({
          time: p.time as UTCTimestamp,
          value: ((p.value - benchBase) / benchBase) * 100,
        })),
      );
    }

    // Tooltip with absolute prices on hover
    if (normalize) {
      chart.subscribeCrosshairMove((param) => {
        if (!param.point || !param.time || param.point.x < 0 || param.point.y < 0) {
          setTooltip((prev) => (prev.visible ? { ...prev, visible: false } : prev));
          return;
        }

        const time = param.time as number;
        const fundPrice = fundAbsolute.get(time);
        const fundPctData = param.seriesData.get(fundSeries);
        const benchPrice = benchAbsolute.get(time);
        const benchPctData = benchSeries ? param.seriesData.get(benchSeries) : null;

        if (fundPrice == null && benchPrice == null) {
          setTooltip((prev) => (prev.visible ? { ...prev, visible: false } : prev));
          return;
        }

        const next: TooltipData = {
          visible: true,
          x: param.point.x,
          y: param.point.y,
        };

        if (fundPrice != null && fundPctData && "value" in fundPctData) {
          next.fundPrice = `${fmtPrice(fundPrice)} €`;
          next.fundPct = fmtPct((fundPctData as { value: number }).value);
        }
        if (benchPrice != null && benchPctData && "value" in benchPctData) {
          next.benchPrice = fmtPrice(benchPrice);
          next.benchPct = fmtPct((benchPctData as { value: number }).value);
        }

        setTooltip(next);
      });
    }

    chart.timeScale().fitContent();

    return () => {
      chart.remove();
      chartRef.current = null;
    };
  }, [fundData, benchmarkData, fundName, benchmarkName, fmtPrice, fmtPct]);

  // Position tooltip within chart bounds
  const tooltipStyle: React.CSSProperties = { display: "none" };
  if (tooltip.visible && tooltipRef.current && containerRef.current) {
    const chartWidth = containerRef.current.offsetWidth;
    const tipWidth = tooltipRef.current.offsetWidth || 200;
    let left = tooltip.x + 16;
    if (left + tipWidth > chartWidth) left = tooltip.x - tipWidth - 16;
    tooltipStyle.display = "block";
    tooltipStyle.left = `${left}px`;
    tooltipStyle.top = `${tooltip.y - 16}px`;
  }

  return (
    <div className="nav-chart__wrapper">
      <div ref={containerRef} className="nav-chart" />
      <div ref={tooltipRef} className="nav-tooltip" style={tooltipStyle}>
        {tooltip.fundPrice && (
          <div className="nav-tooltip__row">
            <span className="nav-tooltip__dot nav-tooltip__dot--fund" />
            <span className="nav-tooltip__name">{fundName}</span>
            <span className="nav-tooltip__price">{tooltip.fundPrice}</span>
            <span className="nav-tooltip__pct">{tooltip.fundPct}</span>
          </div>
        )}
        {tooltip.benchPrice && (
          <div className="nav-tooltip__row">
            <span className="nav-tooltip__dot nav-tooltip__dot--bench" />
            <span className="nav-tooltip__name">{benchmarkName ?? "Benchmark"}</span>
            <span className="nav-tooltip__price">{tooltip.benchPrice}</span>
            <span className="nav-tooltip__pct">{tooltip.benchPct}</span>
          </div>
        )}
      </div>
    </div>
  );
}
