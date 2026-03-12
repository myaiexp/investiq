import { useEffect } from "react";
import { CandlestickSeries, HistogramSeries } from "lightweight-charts";
import type { UTCTimestamp } from "lightweight-charts";
import type { OHLCVBar, IndicatorData, IndicatorId } from "../../types/index.ts";
import { useChart } from "./useChart.ts";
import { useIndicatorSeries } from "./useIndicatorSeries.ts";
import { candlestickOptions, volumeOptions } from "./chartTheme.ts";
import "./PriceChart.css";

interface PriceChartProps {
  data: OHLCVBar[];
  indicators: IndicatorData[];
  enabledIndicators: Set<IndicatorId>;
}

/**
 * Main chart component. Renders candlestick on pane 0 with volume histogram
 * on a separate price scale (also pane 0). Delegates indicator rendering
 * to useIndicatorSeries.
 *
 * Data-agnostic: receives all data as props, does not fetch.
 */
export default function PriceChart({
  data,
  indicators,
  enabledIndicators,
}: PriceChartProps) {
  const { chartRef, containerRef } = useChart();

  // Set up candlestick + volume series on chart creation
  useEffect(() => {
    const chart = chartRef.current;
    if (!chart || data.length === 0) return;

    // Candlestick series (pane 0, right price scale)
    const candleSeries = chart.addSeries(CandlestickSeries, {
      ...candlestickOptions,
    });

    // Volume histogram (pane 0, separate price scale)
    const volSeries = chart.addSeries(HistogramSeries, {
      ...volumeOptions,
    });

    // Configure the volume price scale
    chart.priceScale("volume").applyOptions({
      scaleMargins: { top: 0.8, bottom: 0 },
    });

    // Map OHLCV data to candlestick format (cast time to lightweight-charts Time)
    const candleData = data.map((bar) => ({
      time: bar.time as UTCTimestamp,
      open: bar.open,
      high: bar.high,
      low: bar.low,
      close: bar.close,
    }));

    // Map OHLCV data to volume format with color coding
    const volData = data.map((bar) => ({
      time: bar.time as UTCTimestamp,
      value: bar.volume,
      color:
        bar.close >= bar.open
          ? "rgba(34, 197, 94, 0.3)"
          : "rgba(239, 68, 68, 0.3)",
    }));

    candleSeries.setData(candleData);
    volSeries.setData(volData);
    chart.timeScale().fitContent();

    return () => {
      // Cleanup: remove series when data changes (effect re-runs)
      try {
        chart.removeSeries(candleSeries);
        chart.removeSeries(volSeries);
      } catch {
        // Chart may already be destroyed
      }
    };
  }, [chartRef, data]);

  // Delegate indicator series management
  useIndicatorSeries(chartRef.current, indicators, enabledIndicators);

  return (
    <div className="price-chart">
      <div className="price-chart__container" ref={containerRef} />
      {data.length === 0 && (
        <div className="price-chart__empty">
          <span className="price-chart__empty-text">{"\u2014"}</span>
        </div>
      )}
    </div>
  );
}
