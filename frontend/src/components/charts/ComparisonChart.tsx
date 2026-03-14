import { useEffect } from "react";
import { LineSeries } from "lightweight-charts";
import type { UTCTimestamp } from "lightweight-charts";
import type { IndicatorId, IndicatorData, FundNAVPoint } from "../../types/index.ts";
import { useChart } from "./useChart.ts";
import { useComparisonIndicators } from "./useComparisonIndicators.ts";
import "./ComparisonChart.css";

export const FUND_COLORS = ["#3b82f6", "#22c55e", "#f59e0b", "#ef4444", "#8b5cf6"];

export interface ComparisonChartFund {
  ticker: string;
  name: string;
  data: FundNAVPoint[];
}

interface ComparisonChartProps {
  funds: ComparisonChartFund[];
  indicators?: Record<string, IndicatorData[]>;
  enabledIndicators?: Set<IndicatorId>;
  fundColors?: Record<string, string>;
}

export default function ComparisonChart({
  funds,
  indicators = {},
  enabledIndicators = new Set(),
  fundColors = {},
}: ComparisonChartProps) {
  const { chartRef, containerRef } = useChart();

  useComparisonIndicators(
    chartRef.current,
    indicators,
    enabledIndicators,
    fundColors,
  );

  useEffect(() => {
    const chart = chartRef.current;
    if (!chart || funds.length === 0) return;

    // Find the latest start date among all selected funds.
    // All funds must start from this date so lines begin at 0%.
    const startTimes = funds
      .filter((f) => f.data.length > 0)
      .map((f) => f.data[0].time);

    if (startTimes.length === 0) return;

    const sharedStart = Math.max(...startTimes);

    const seriesList = funds.map((fund, i) => {
      const color = FUND_COLORS[i % FUND_COLORS.length];

      // Only include data points at or after the shared start date
      const trimmed = fund.data.filter((p) => p.time >= sharedStart);
      if (trimmed.length === 0) return null;

      const base = trimmed[0].value;

      const series = chart.addSeries(LineSeries, {
        color,
        lineWidth: 2,
        title: "",
        priceFormat: {
          type: "custom",
          formatter: (v: number) => `${v >= 0 ? "+" : ""}${v.toFixed(2)}%`,
        },
      });

      series.setData(
        trimmed.map((p) => ({
          time: p.time as UTCTimestamp,
          value: ((p.value - base) / base) * 100,
        })),
      );

      return series;
    });

    chart.timeScale().fitContent();

    return () => {
      for (const s of seriesList) {
        if (s) chart.removeSeries(s);
      }
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [chartRef.current, funds]);

  const activeFunds = funds.filter((f) => f.data.length > 0);

  return (
    <div className="comparison-chart__wrapper">
      {activeFunds.length > 0 && (
        <div className="comparison-chart__legend">
          {activeFunds.map((fund, i) => (
            <span key={fund.ticker} className="comparison-chart__legend-item">
              <span
                className="comparison-chart__legend-dot"
                style={{ background: FUND_COLORS[i % FUND_COLORS.length] }}
              />
              {fund.name}
            </span>
          ))}
        </div>
      )}
      <div ref={containerRef} className="comparison-chart" />
    </div>
  );
}
