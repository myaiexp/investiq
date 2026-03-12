/**
 * Pure functions returning series configurations per indicator type.
 * Each renderer returns an array of SeriesConfig objects describing
 * what series to create and how to configure them.
 */

import {
  LineSeries,
  HistogramSeries,
} from "lightweight-charts";
import type {
  SeriesDefinition,
  SeriesType,
} from "lightweight-charts";
import type { IndicatorId } from "../../types/index.ts";
import { indicatorColors } from "./chartTheme.ts";

export interface SeriesConfig {
  /** Key within the IndicatorData.series record */
  seriesKey: string;
  /** lightweight-charts series definition (e.g. LineSeries, HistogramSeries) */
  seriesType: SeriesDefinition<SeriesType>;
  /** Series options (color, lineWidth, etc.) */
  options: Record<string, unknown>;
  /** Pane index: 0 = overlay on main chart, >0 = sub-pane */
  pane: number;
  /** Whether this is a horizontal level line (not data-driven) */
  isLevel?: boolean;
  /** For level lines: the fixed value */
  levelValue?: number;
}

/**
 * Category of each indicator — determines pane placement.
 * Overlays go on pane 0, oscillators get their own sub-panes.
 */
export const INDICATOR_CATEGORIES: Record<
  IndicatorId,
  "overlay" | "oscillator"
> = {
  bollinger: "overlay",
  ma: "overlay",
  ichimoku: "overlay",
  fibonacci: "overlay",
  rsi: "oscillator",
  macd: "oscillator",
  stochastic: "oscillator",
  cci: "oscillator",
  obv: "oscillator",
  atr: "oscillator",
};

const LINE_WIDTH = 1;
const THIN_LINE = 1;

/**
 * Returns series configs for a given indicator.
 * @param id - The indicator identifier
 * @param pane - The pane index to use (0 for overlays, assigned dynamically for oscillators)
 */
export function getIndicatorSeriesConfigs(
  id: IndicatorId,
  pane: number,
): SeriesConfig[] {
  switch (id) {
    case "bollinger":
      return [
        {
          seriesKey: "upper",
          seriesType: LineSeries,
          options: {
            color: indicatorColors.bollinger.upper,
            lineWidth: THIN_LINE,
            lineStyle: 2,
          },
          pane,
        },
        {
          seriesKey: "middle",
          seriesType: LineSeries,
          options: {
            color: indicatorColors.bollinger.middle,
            lineWidth: THIN_LINE,
          },
          pane,
        },
        {
          seriesKey: "lower",
          seriesType: LineSeries,
          options: {
            color: indicatorColors.bollinger.lower,
            lineWidth: THIN_LINE,
            lineStyle: 2,
          },
          pane,
        },
      ];

    case "ma":
      return [
        {
          seriesKey: "sma50",
          seriesType: LineSeries,
          options: {
            color: indicatorColors.ma.sma50,
            lineWidth: LINE_WIDTH,
          },
          pane,
        },
        {
          seriesKey: "sma200",
          seriesType: LineSeries,
          options: {
            color: indicatorColors.ma.sma200,
            lineWidth: LINE_WIDTH,
          },
          pane,
        },
        {
          seriesKey: "ema50",
          seriesType: LineSeries,
          options: {
            color: indicatorColors.ma.ema50,
            lineWidth: LINE_WIDTH,
            lineStyle: 2,
          },
          pane,
        },
        {
          seriesKey: "ema200",
          seriesType: LineSeries,
          options: {
            color: indicatorColors.ma.ema200,
            lineWidth: LINE_WIDTH,
            lineStyle: 2,
          },
          pane,
        },
      ];

    case "ichimoku":
      return [
        {
          seriesKey: "tenkan",
          seriesType: LineSeries,
          options: {
            color: indicatorColors.ichimoku.tenkan,
            lineWidth: THIN_LINE,
          },
          pane,
        },
        {
          seriesKey: "kijun",
          seriesType: LineSeries,
          options: {
            color: indicatorColors.ichimoku.kijun,
            lineWidth: THIN_LINE,
          },
          pane,
        },
        {
          seriesKey: "senkouA",
          seriesType: LineSeries,
          options: {
            color: indicatorColors.ichimoku.senkouA,
            lineWidth: THIN_LINE,
          },
          pane,
        },
        {
          seriesKey: "senkouB",
          seriesType: LineSeries,
          options: {
            color: indicatorColors.ichimoku.senkouB,
            lineWidth: THIN_LINE,
          },
          pane,
        },
        {
          seriesKey: "chikou",
          seriesType: LineSeries,
          options: {
            color: indicatorColors.ichimoku.chikou,
            lineWidth: THIN_LINE,
            lineStyle: 2,
          },
          pane,
        },
      ];

    case "fibonacci":
      return [
        {
          seriesKey: "levels",
          seriesType: LineSeries,
          options: {
            color: indicatorColors.fibonacci.levels,
            lineWidth: THIN_LINE,
            lineStyle: 2,
          },
          pane,
        },
      ];

    case "rsi":
      return [
        {
          seriesKey: "rsi",
          seriesType: LineSeries,
          options: {
            color: indicatorColors.rsi.main,
            lineWidth: LINE_WIDTH,
          },
          pane,
        },
        // Level lines for overbought/oversold
        {
          seriesKey: "_rsi_70",
          seriesType: LineSeries,
          options: {
            color: "rgba(239, 68, 68, 0.4)",
            lineWidth: THIN_LINE,
            lineStyle: 2,
          },
          pane,
          isLevel: true,
          levelValue: 70,
        },
        {
          seriesKey: "_rsi_30",
          seriesType: LineSeries,
          options: {
            color: "rgba(34, 197, 94, 0.4)",
            lineWidth: THIN_LINE,
            lineStyle: 2,
          },
          pane,
          isLevel: true,
          levelValue: 30,
        },
      ];

    case "macd":
      return [
        {
          seriesKey: "macd",
          seriesType: LineSeries,
          options: {
            color: indicatorColors.macd.line,
            lineWidth: LINE_WIDTH,
          },
          pane,
        },
        {
          seriesKey: "signal",
          seriesType: LineSeries,
          options: {
            color: indicatorColors.macd.signal,
            lineWidth: LINE_WIDTH,
          },
          pane,
        },
        {
          seriesKey: "histogram",
          seriesType: HistogramSeries,
          options: {
            color: indicatorColors.macd.histogram,
          },
          pane,
        },
      ];

    case "stochastic":
      return [
        {
          seriesKey: "k",
          seriesType: LineSeries,
          options: {
            color: indicatorColors.stochastic.k,
            lineWidth: LINE_WIDTH,
          },
          pane,
        },
        {
          seriesKey: "d",
          seriesType: LineSeries,
          options: {
            color: indicatorColors.stochastic.d,
            lineWidth: LINE_WIDTH,
          },
          pane,
        },
        {
          seriesKey: "_stoch_80",
          seriesType: LineSeries,
          options: {
            color: "rgba(239, 68, 68, 0.4)",
            lineWidth: THIN_LINE,
            lineStyle: 2,
          },
          pane,
          isLevel: true,
          levelValue: 80,
        },
        {
          seriesKey: "_stoch_20",
          seriesType: LineSeries,
          options: {
            color: "rgba(34, 197, 94, 0.4)",
            lineWidth: THIN_LINE,
            lineStyle: 2,
          },
          pane,
          isLevel: true,
          levelValue: 20,
        },
      ];

    case "cci":
      return [
        {
          seriesKey: "cci",
          seriesType: LineSeries,
          options: {
            color: indicatorColors.cci.main,
            lineWidth: LINE_WIDTH,
          },
          pane,
        },
        {
          seriesKey: "_cci_100",
          seriesType: LineSeries,
          options: {
            color: "rgba(239, 68, 68, 0.4)",
            lineWidth: THIN_LINE,
            lineStyle: 2,
          },
          pane,
          isLevel: true,
          levelValue: 100,
        },
        {
          seriesKey: "_cci_n100",
          seriesType: LineSeries,
          options: {
            color: "rgba(34, 197, 94, 0.4)",
            lineWidth: THIN_LINE,
            lineStyle: 2,
          },
          pane,
          isLevel: true,
          levelValue: -100,
        },
      ];

    case "obv":
      return [
        {
          seriesKey: "obv",
          seriesType: LineSeries,
          options: {
            color: indicatorColors.obv.main,
            lineWidth: LINE_WIDTH,
          },
          pane,
        },
      ];

    case "atr":
      return [
        {
          seriesKey: "atr",
          seriesType: LineSeries,
          options: {
            color: indicatorColors.atr.main,
            lineWidth: LINE_WIDTH,
          },
          pane,
        },
      ];
  }
}
