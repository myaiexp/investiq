import { useEffect, useRef } from "react";
import { LineSeries } from "lightweight-charts";
import type { IChartApi, ISeriesApi, Time } from "lightweight-charts";
import type { IndicatorId, IndicatorData } from "../../types/index.ts";

// eslint-disable-next-line @typescript-eslint/no-explicit-any
type AnySeries = ISeriesApi<any>;

/** Only oscillators are meaningful in comparison mode (no overlays on a % chart) */
export const COMPARISON_OSCILLATORS: IndicatorId[] = ["rsi", "macd", "cci"];

/** Level line definitions per indicator */
const LEVEL_LINES: Record<
  string,
  { levelValue: number; color: string }[]
> = {
  rsi: [
    { levelValue: 70, color: "rgba(239, 68, 68, 0.4)" },
    { levelValue: 30, color: "rgba(34, 197, 94, 0.4)" },
  ],
  cci: [
    { levelValue: 100, color: "rgba(239, 68, 68, 0.4)" },
    { levelValue: -100, color: "rgba(34, 197, 94, 0.4)" },
  ],
};

/**
 * Data series keys to render per indicator in comparison mode.
 * MACD skips histogram — too cluttered with N funds on one pane.
 */
const COMPARISON_SERIES_KEYS: Record<string, string[]> = {
  rsi: ["rsi"],
  macd: ["macd", "signal"],
  cci: ["cci"],
};

/** Tracks series for a single fund's oscillator line */
interface FundSeriesEntry {
  series: AnySeries;
  indicatorId: IndicatorId;
  seriesKey: string;
  ticker: string;
}

/** Tracks level lines created once per indicator pane */
interface LevelLineEntry {
  series: AnySeries;
  levelValue: number;
  indicatorId: IndicatorId;
}

/**
 * Hook: renders per-fund oscillator sub-panes on the comparison chart.
 *
 * Each enabled oscillator gets its own sub-pane. Per pane:
 * - One line per fund (color-matched to NAV line)
 * - Level lines created once (not per fund)
 *
 * Series tracking key: `${ticker}__${indicatorId}__${seriesKey}`
 */
export function useComparisonIndicators(
  chart: IChartApi | null,
  fundIndicators: Record<string, IndicatorData[]>,
  enabledIndicators: Set<IndicatorId>,
  fundColors: Record<string, string>,
): void {
  /** Map of `${ticker}__${indicatorId}__${seriesKey}` → series */
  const dataSeriesRef = useRef<Map<string, FundSeriesEntry>>(new Map());
  /** Map of `${indicatorId}__${levelValue}` → level line entry */
  const levelSeriesRef = useRef<Map<string, LevelLineEntry>>(new Map());
  const prevEnabledRef = useRef<Set<IndicatorId>>(new Set());

  // Effect 1: manage series lifecycle when enabled indicators change
  useEffect(() => {
    if (!chart) return;

    const prev = prevEnabledRef.current;
    const curr = enabledIndicators;
    const dataSeries = dataSeriesRef.current;
    const levelSeries = levelSeriesRef.current;

    const toAdd = new Set<IndicatorId>();
    const toRemove = new Set<IndicatorId>();

    for (const id of curr) {
      if (!prev.has(id) && COMPARISON_OSCILLATORS.includes(id)) toAdd.add(id);
    }
    for (const id of prev) {
      if (!curr.has(id) && COMPARISON_OSCILLATORS.includes(id)) toRemove.add(id);
    }

    // Remove series for disabled indicators
    for (const id of toRemove) {
      // Remove all fund data series for this indicator
      for (const [key, entry] of dataSeries) {
        if (entry.indicatorId === id) {
          chart.removeSeries(entry.series);
          dataSeries.delete(key);
        }
      }
      // Remove level lines for this indicator
      for (const [key, entry] of levelSeries) {
        if (entry.indicatorId === id) {
          chart.removeSeries(entry.series);
          levelSeries.delete(key);
        }
      }
    }

    // Compute pane assignments for enabled oscillators (in COMPARISON_OSCILLATORS order)
    const enabledOscs = COMPARISON_OSCILLATORS.filter((id) => curr.has(id));
    const paneOf = new Map<IndicatorId, number>();
    enabledOscs.forEach((id, index) => {
      paneOf.set(id, index + 1); // pane 0 is the main NAV chart
    });

    // Reposition existing series if pane numbers shifted (another osc was toggled off)
    for (const [, entry] of dataSeries) {
      const newPane = paneOf.get(entry.indicatorId);
      if (newPane !== undefined) {
        entry.series.moveToPane(newPane);
      }
    }
    for (const [, entry] of levelSeries) {
      const newPane = paneOf.get(entry.indicatorId);
      if (newPane !== undefined) {
        entry.series.moveToPane(newPane);
      }
    }

    // Add series for newly enabled indicators
    for (const id of toAdd) {
      const pane = paneOf.get(id) ?? 1;
      const seriesKeys = COMPARISON_SERIES_KEYS[id] ?? [];
      const tickers = Object.keys(fundIndicators);

      // Create one data series per fund per series key
      for (const ticker of tickers) {
        const color = fundColors[ticker] ?? "#94a3b8";
        for (const sk of seriesKeys) {
          const mapKey = `${ticker}__${id}__${sk}`;
          if (dataSeries.has(mapKey)) continue;

          const series = chart.addSeries(LineSeries, {
            color,
            lineWidth: 1,
            lastValueVisible: false,
            priceLineVisible: false,
            title: "",
          });
          series.moveToPane(pane);

          dataSeries.set(mapKey, { series, indicatorId: id, seriesKey: sk, ticker });
        }
      }

      // Create level lines (once per indicator, not per fund)
      const levels = LEVEL_LINES[id] ?? [];
      for (const { levelValue, color } of levels) {
        const levelKey = `${id}__${levelValue}`;
        if (levelSeries.has(levelKey)) continue;

        const lvlSeries = chart.addSeries(LineSeries, {
          color,
          lineWidth: 1,
          lineStyle: 2,
          lastValueVisible: false,
          priceLineVisible: false,
          title: "",
        });
        lvlSeries.moveToPane(pane);

        levelSeries.set(levelKey, { series: lvlSeries, levelValue, indicatorId: id });
      }
    }

    // Update pane stretch factors
    const panes = chart.panes();
    if (panes.length > 0) {
      const oscCount = enabledOscs.length;
      const mainStretch = oscCount > 0 ? 0.6 : 1;
      const oscStretch = oscCount > 0 ? 0.4 / oscCount : 0;

      panes[0].setStretchFactor(mainStretch);
      for (let i = 1; i < panes.length; i++) {
        panes[i].setStretchFactor(oscStretch);
      }
    }

    prevEnabledRef.current = new Set(curr);
  }, [chart, enabledIndicators, fundIndicators, fundColors]);

  // Effect 2: update data on existing series when fundIndicators or enabled set changes
  useEffect(() => {
    if (!chart) return;

    const dataSeries = dataSeriesRef.current;
    const levelSeries = levelSeriesRef.current;

    // Update data series
    for (const [key, entry] of dataSeries) {
      const { ticker, indicatorId, seriesKey, series } = entry;
      const indicators = fundIndicators[ticker];
      if (!indicators) continue;

      const indData = indicators.find((d) => d.id === indicatorId);
      if (!indData) continue;

      const seriesData = indData.series[seriesKey];
      if (seriesData && seriesData.length > 0) {
        series.setData(
          seriesData.map((d) => ({ time: d.time as Time, value: d.value })),
        );
      }
      // suppress unused variable warning for key
      void key;
    }

    // Update level lines — use time range from any available fund data
    for (const [, entry] of levelSeries) {
      const { series, levelValue, indicatorId } = entry;

      // Find time range from any fund that has this indicator
      let timeRange: { first: number; last: number } | null = null;
      for (const [, indicators] of Object.entries(fundIndicators)) {
        const indData = indicators.find((d) => d.id === indicatorId);
        if (!indData) continue;
        const seriesKeys = COMPARISON_SERIES_KEYS[indicatorId] ?? [];
        const firstKey = seriesKeys[0];
        if (!firstKey) continue;
        const pts = indData.series[firstKey];
        if (pts && pts.length > 0) {
          timeRange = { first: pts[0].time, last: pts[pts.length - 1].time };
          break;
        }
      }

      if (timeRange) {
        series.setData([
          { time: timeRange.first as Time, value: levelValue },
          { time: timeRange.last as Time, value: levelValue },
        ]);
      }
    }
  }, [chart, fundIndicators, enabledIndicators]);

  // Effect 3: add series for funds that were added after indicators were already enabled
  useEffect(() => {
    if (!chart) return;

    const dataSeries = dataSeriesRef.current;
    const curr = prevEnabledRef.current;
    const enabledOscs = COMPARISON_OSCILLATORS.filter((id) => curr.has(id));
    const paneOf = new Map<IndicatorId, number>();
    enabledOscs.forEach((id, index) => {
      paneOf.set(id, index + 1);
    });

    for (const id of enabledOscs) {
      const pane = paneOf.get(id) ?? 1;
      const seriesKeys = COMPARISON_SERIES_KEYS[id] ?? [];
      const tickers = Object.keys(fundIndicators);

      for (const ticker of tickers) {
        const color = fundColors[ticker] ?? "#94a3b8";
        for (const sk of seriesKeys) {
          const mapKey = `${ticker}__${id}__${sk}`;
          if (dataSeries.has(mapKey)) continue;

          const series = chart.addSeries(LineSeries, {
            color,
            lineWidth: 1,
            lastValueVisible: false,
            priceLineVisible: false,
            title: "",
          });
          series.moveToPane(pane);

          dataSeries.set(mapKey, { series, indicatorId: id, seriesKey: sk, ticker });
        }
      }
    }
  }, [chart, fundIndicators, fundColors]);
}
