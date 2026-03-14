import { useEffect, useRef, useState, useCallback } from "react";
import { LineSeries } from "lightweight-charts";
import type { ISeriesApi, SeriesType, UTCTimestamp } from "lightweight-charts";
import type { FundNAVPoint, IndicatorData, IndicatorId } from "../../types/index.ts";
import { useChart } from "./useChart.ts";
import { useIndicatorSeries } from "./useIndicatorSeries.ts";
import "./NAVChart.css";

interface NAVChartProps {
  fundData: FundNAVPoint[];
  benchmarkData?: FundNAVPoint[];
  fundName: string;
  benchmarkName?: string;
  indicators?: IndicatorData[];
  enabledIndicators?: Set<IndicatorId>;
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
  indicators = [],
  enabledIndicators = new Set(),
}: NAVChartProps) {
  const { chartRef, containerRef } = useChart();
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

  // Data effect — creates/removes fund + benchmark series on each data change.
  // Cleanup removes series only (NOT the chart).
  useEffect(() => {
    const chart = chartRef.current;
    if (!chart || fundData.length === 0) return;

    const hasBenchmark = benchmarkData && benchmarkData.length > 0;
    const normalize = hasBenchmark && fundData.length > 0;
    const fundBase = fundData[0]?.value ?? 1;
    const benchBase = benchmarkData?.[0]?.value ?? 1;

    // Build lookup maps for absolute prices (used in tooltip)
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

    // Tooltip with absolute prices on hover (only in normalized/benchmark mode)
    let unsubscribe: (() => void) | null = null;
    if (normalize) {
      const handler = (param: Parameters<Parameters<typeof chart.subscribeCrosshairMove>[0]>[0]) => {
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
      };

      chart.subscribeCrosshairMove(handler);
      unsubscribe = () => chart.unsubscribeCrosshairMove(handler);
    }

    chart.timeScale().fitContent();

    return () => {
      unsubscribe?.();
      // Hide tooltip on cleanup to avoid stale display
      setTooltip({ visible: false, x: 0, y: 0 });
      // Remove series only — chart lifecycle is managed by useChart()
      chart.removeSeries(fundSeries);
      if (benchSeries) chart.removeSeries(benchSeries);
    };
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [chartRef.current, fundData, benchmarkData, fmtPrice, fmtPct]);

  // Delegate indicator overlays/oscillators to the shared hook
  useIndicatorSeries(chartRef.current, indicators, enabledIndicators);

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
