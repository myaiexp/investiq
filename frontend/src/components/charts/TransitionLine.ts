/**
 * Series primitive that draws a vertical dashed line at the data transition
 * point, with resolution labels on each side (e.g. "5m" | "1m").
 *
 * Attached to the candlestick series via `attachPrimitive()`.
 */
import type { UTCTimestamp } from "lightweight-charts";

interface MediaScope {
  context: CanvasRenderingContext2D;
  mediaSize: { width: number; height: number };
}

interface RenderTarget {
  useMediaCoordinateSpace(cb: (scope: MediaScope) => void): void;
}

interface TransitionLineOptions {
  time: UTCTimestamp;
  leftLabel: string;
  rightLabel: string;
}

interface SeriesAttachedParams {
  chart: { timeScale(): { timeToCoordinate(t: UTCTimestamp): number | null } };
}

class TransitionLineRenderer {
  private _x: number | null;
  private _leftLabel: string;
  private _rightLabel: string;

  constructor(x: number | null, leftLabel: string, rightLabel: string) {
    this._x = x;
    this._leftLabel = leftLabel;
    this._rightLabel = rightLabel;
  }

  draw(target: RenderTarget) {
    if (this._x === null) return;

    const x = this._x;
    const leftLabel = this._leftLabel;
    const rightLabel = this._rightLabel;

    target.useMediaCoordinateSpace((scope) => {
      const ctx = scope.context;
      const { height } = scope.mediaSize;
      const xr = Math.round(x);

      ctx.save();

      // Dashed vertical line
      ctx.setLineDash([4, 4]);
      ctx.strokeStyle = "rgba(148, 163, 184, 0.5)";
      ctx.lineWidth = 1;
      ctx.beginPath();
      ctx.moveTo(xr, 0);
      ctx.lineTo(xr, height);
      ctx.stroke();

      // Resolution labels at the top
      ctx.setLineDash([]);
      ctx.font = "10px monospace";
      ctx.textBaseline = "top";
      ctx.fillStyle = "rgba(148, 163, 184, 0.7)";

      const labelY = 6;
      const pad = 6;

      // Left label (backfill resolution)
      ctx.textAlign = "right";
      ctx.fillText(leftLabel, xr - pad, labelY);

      // Right label (current interval resolution)
      ctx.textAlign = "left";
      ctx.fillText(rightLabel, xr + pad, labelY);

      ctx.restore();
    });
  }
}

export class TransitionLinePrimitive {
  private _options: TransitionLineOptions;
  private _chart: SeriesAttachedParams["chart"] | null = null;
  private _paneViews: {
    renderer: () => TransitionLineRenderer;
    zOrder: () => "top";
  }[];

  constructor(options: TransitionLineOptions) {
    this._options = options;
    this._paneViews = [
      {
        zOrder: () => "top" as const,
        renderer: () => {
          const x = this._chart
            ? this._chart.timeScale().timeToCoordinate(this._options.time)
            : null;
          return new TransitionLineRenderer(
            x,
            this._options.leftLabel,
            this._options.rightLabel,
          );
        },
      },
    ];
  }

  attached(params: SeriesAttachedParams) {
    this._chart = params.chart;
  }

  detached() {
    this._chart = null;
  }

  updateAllViews() {
    // Called when viewport changes — renderer recalculates x on next draw
  }

  paneViews() {
    return this._paneViews;
  }
}
