import { useEffect, useRef } from "react";
import type { IChartApi, ISeriesApi, Time } from "lightweight-charts";
import type { IndicatorId, IndicatorData } from "../../types/index.ts";
import {
  getIndicatorSeriesConfigs,
  INDICATOR_CATEGORIES,
} from "./indicatorRenderers.ts";
import type { SeriesConfig } from "./indicatorRenderers.ts";

// eslint-disable-next-line @typescript-eslint/no-explicit-any
type AnySeries = ISeriesApi<any>;

/** Tracks all series belonging to a single indicator */
interface IndicatorSeriesGroup {
  indicatorId: IndicatorId;
  /** Pane index used by this indicator (0 for overlays) */
  pane: number;
  /** Map of seriesKey -> series API */
  series: Map<string, AnySeries>;
  /** The configs used to create these series */
  configs: SeriesConfig[];
}

/** Ordered list of oscillator IDs for deterministic pane assignment */
const OSCILLATOR_ORDER: IndicatorId[] = [
  "rsi",
  "macd",
  "stochastic",
  "cci",
  "obv",
  "atr",
];

/**
 * Hook: diffs the enabled indicator set against what's currently rendered,
 * incrementally adding/removing series and sub-panes without recreating the chart.
 *
 * Overlays go to pane 0 (main chart). Each oscillator gets its own sub-pane.
 */
export function useIndicatorSeries(
  chart: IChartApi | null,
  indicators: IndicatorData[],
  enabledIndicators: Set<IndicatorId>,
) {
  const groupsRef = useRef<Map<IndicatorId, IndicatorSeriesGroup>>(new Map());
  const prevEnabledRef = useRef<Set<IndicatorId>>(new Set());

  useEffect(() => {
    if (!chart) return;

    const prev = prevEnabledRef.current;
    const curr = enabledIndicators;
    const groups = groupsRef.current;

    // Determine which indicators to add/remove
    const toAdd = new Set<IndicatorId>();
    const toRemove = new Set<IndicatorId>();

    for (const id of curr) {
      if (!prev.has(id)) toAdd.add(id);
    }
    for (const id of prev) {
      if (!curr.has(id)) toRemove.add(id);
    }

    // Remove series for disabled indicators
    for (const id of toRemove) {
      const group = groups.get(id);
      if (group) {
        for (const series of group.series.values()) {
          chart.removeSeries(series);
        }
        groups.delete(id);
      }
    }

    // Compute pane assignments for currently enabled oscillators
    const enabledOscillators = OSCILLATOR_ORDER.filter(
      (id) => curr.has(id) && INDICATOR_CATEGORIES[id] === "oscillator",
    );
    const paneAssignment = new Map<IndicatorId, number>();
    enabledOscillators.forEach((id, index) => {
      paneAssignment.set(id, index + 1); // pane 0 is main
    });

    // Add series for newly enabled indicators
    for (const id of toAdd) {
      const category = INDICATOR_CATEGORIES[id];
      const pane = category === "overlay" ? 0 : (paneAssignment.get(id) ?? 1);
      const configs = getIndicatorSeriesConfigs(id, pane);
      const seriesMap = new Map<string, AnySeries>();

      for (const config of configs) {
        // addSeries requires SeriesDefinition<T> — cast through unknown
        // because SeriesConfig stores it as a union type
        const series = chart.addSeries(
          config.seriesType as Parameters<typeof chart.addSeries>[0],
          {
            ...config.options,
            lastValueVisible: false,
            priceLineVisible: false,
          },
        );

        // Move to the correct pane
        if (config.pane > 0) {
          series.moveToPane(config.pane);
        }

        seriesMap.set(config.seriesKey, series);
      }

      groups.set(id, {
        indicatorId: id,
        pane: category === "overlay" ? 0 : (paneAssignment.get(id) ?? 1),
        series: seriesMap,
        configs,
      });
    }

    // Reposition existing oscillators if pane assignments changed
    for (const [id, group] of groups) {
      if (INDICATOR_CATEGORIES[id] === "oscillator") {
        const newPane = paneAssignment.get(id);
        if (newPane !== undefined && newPane !== group.pane) {
          for (const series of group.series.values()) {
            series.moveToPane(newPane);
          }
          group.pane = newPane;
        }
      }
    }

    // Update pane stretch factors
    const panes = chart.panes();
    if (panes.length > 0) {
      // Main pane gets ~0.6 stretch, oscillator panes share the rest
      const oscCount = enabledOscillators.length;
      const mainStretch = oscCount > 0 ? 0.6 : 1;
      const oscStretch = oscCount > 0 ? 0.4 / oscCount : 0;

      panes[0].setStretchFactor(mainStretch);
      for (let i = 1; i < panes.length; i++) {
        panes[i].setStretchFactor(oscStretch);
      }
    }

    prevEnabledRef.current = new Set(curr);
  }, [chart, enabledIndicators]);

  // Separate effect for data updates — runs whenever indicator data changes
  useEffect(() => {
    if (!chart) return;

    const groups = groupsRef.current;
    const indicatorMap = new Map(indicators.map((ind) => [ind.id, ind]));

    for (const [id, group] of groups) {
      const data = indicatorMap.get(id);
      if (!data) continue;

      for (const config of group.configs) {
        const series = group.series.get(config.seriesKey);
        if (!series) continue;

        if (config.isLevel && config.levelValue !== undefined) {
          // Level lines: generate constant-value data spanning the time range
          const anySeries = data.series[Object.keys(data.series)[0]];
          if (anySeries && anySeries.length > 0) {
            const levelData = [
              {
                time: anySeries[0].time as Time,
                value: config.levelValue,
              },
              {
                time: anySeries[anySeries.length - 1].time as Time,
                value: config.levelValue,
              },
            ];
            series.setData(levelData);
          }
        } else {
          const seriesData = data.series[config.seriesKey];
          if (seriesData) {
            series.setData(
              seriesData.map((d) => ({ time: d.time as Time, value: d.value })),
            );
          }
        }
      }
    }
  }, [chart, indicators]);
}
