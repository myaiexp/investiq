/**
 * Chart theme configuration matching CSS custom properties.
 * Colors are hardcoded (not var() references) because lightweight-charts
 * operates on a canvas, not DOM — CSS variables don't apply.
 */

import { ColorType } from "lightweight-charts";
import type { DeepPartial, TimeChartOptions } from "lightweight-charts";

export const chartColors = {
  background: "#1a2332", // --bg-card
  backgroundSecondary: "#111827", // --bg-secondary
  text: "#e2e8f0", // --text-primary
  textSecondary: "#94a3b8", // --text-secondary
  textMuted: "#64748b", // --text-muted
  border: "#1e293b", // --border
  accent: "#3b82f6", // --accent
  green: "#22c55e", // --green
  red: "#ef4444", // --red
  yellow: "#eab308", // --yellow
} as const;

export const chartLayoutOptions: DeepPartial<TimeChartOptions> = {
  layout: {
    background: { type: ColorType.Solid, color: chartColors.background },
    textColor: chartColors.textSecondary,
    fontFamily: '"Inter", system-ui, -apple-system, sans-serif',
    fontSize: 11,
  },
  grid: {
    vertLines: { color: chartColors.border },
    horzLines: { color: chartColors.border },
  },
  crosshair: {
    vertLine: {
      color: chartColors.textMuted,
      width: 1,
      style: 2, // Dashed
      labelBackgroundColor: chartColors.backgroundSecondary,
    },
    horzLine: {
      color: chartColors.textMuted,
      width: 1,
      style: 2,
      labelBackgroundColor: chartColors.backgroundSecondary,
    },
  },
  timeScale: {
    borderColor: chartColors.border,
    timeVisible: true,
    secondsVisible: false,
  },
  rightPriceScale: {
    borderColor: chartColors.border,
  },
};

/** Candlestick colors */
export const candlestickOptions = {
  upColor: chartColors.green,
  downColor: chartColors.red,
  borderVisible: false,
  wickUpColor: chartColors.green,
  wickDownColor: chartColors.red,
} as const;

/** Volume histogram colors */
export const volumeOptions = {
  color: "rgba(59, 130, 246, 0.3)", // accent at 30% opacity
  priceFormat: { type: "volume" as const },
  priceScaleId: "volume",
} as const;

/** Indicator color palette — deterministic per indicator */
export const indicatorColors = {
  rsi: { main: "#8b5cf6" }, // purple
  macd: { line: "#3b82f6", signal: "#f59e0b", histogram: "#6366f1" },
  bollinger: { upper: "#ef4444", middle: "#f59e0b", lower: "#22c55e" },
  ma: {
    sma50: "#f59e0b",
    sma200: "#ef4444",
    ema50: "#22c55e",
    ema200: "#8b5cf6",
  },
  stochastic: { k: "#3b82f6", d: "#f59e0b" },
  obv: { main: "#06b6d4" }, // cyan
  fibonacci: { levels: "#f59e0b" },
  atr: { main: "#ec4899" }, // pink
  ichimoku: {
    tenkan: "#ef4444",
    kijun: "#3b82f6",
    senkouA: "rgba(34, 197, 94, 0.4)",
    senkouB: "rgba(239, 68, 68, 0.4)",
    chikou: "#8b5cf6",
  },
  cci: { main: "#14b8a6" }, // teal
} as const;
