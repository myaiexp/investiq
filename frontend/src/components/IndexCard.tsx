import type { IndexMeta } from "../types/index.ts";
import SparklineChart from "./SparklineChart.tsx";
import SignalBadge from "./SignalBadge.tsx";
import PriceChange from "./PriceChange.tsx";
import "./IndexCard.css";

interface IndexCardProps {
  index: IndexMeta;
  sparklineData: { time: number; value: number }[];
  expanded?: boolean;
}

export default function IndexCard({ index, sparklineData, expanded }: IndexCardProps) {
  return (
    <div className="index-card">
      <span className="index-card__name">
        {index.name}
        {index.dataNote && (
          <span className="data-note" title={index.dataNote}>&#8505;</span>
        )}
      </span>
      <div className="index-card__mid">
        <div className="index-card__price">
          <span className="index-card__nav number">
            {index.price.toLocaleString("fi-FI", { minimumFractionDigits: 2 })}
            {index.currency && (
              <span className="index-card__currency"> {index.currency}</span>
            )}
          </span>
          <PriceChange value={index.dailyChange} size="sm" />
        </div>
        <SignalBadge signal={index.signal} />
      </div>
      {!expanded && (
        <div className="index-card__sparkline">
          <SparklineChart data={sparklineData} />
        </div>
      )}
    </div>
  );
}
