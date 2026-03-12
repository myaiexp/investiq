import { useEffect, useRef } from "react";
import { createChart } from "lightweight-charts";
import type { IChartApi } from "lightweight-charts";
import { chartLayoutOptions } from "./chartTheme.ts";

/**
 * Hook: creates a lightweight-charts instance on mount, enables autoSize
 * for responsive behavior, and cleans up on unmount.
 *
 * Returns refs to the chart API and the container DOM element.
 */
export function useChart() {
  const chartRef = useRef<IChartApi | null>(null);
  const containerRef = useRef<HTMLDivElement | null>(null);

  useEffect(() => {
    const container = containerRef.current;
    if (!container) return;

    const chart = createChart(container, {
      ...chartLayoutOptions,
      autoSize: true,
    });

    chart.timeScale().fitContent();
    chartRef.current = chart;

    return () => {
      chart.remove();
      chartRef.current = null;
    };
  }, []);

  return { chartRef, containerRef };
}
