import type { IndexMeta } from "../types/index.ts";
import SparklineChart from "./SparklineChart.tsx";
import SignalBadge from "./SignalBadge.tsx";
import PriceChange from "./PriceChange.tsx";
import "./IndexCard.css";

interface IndexCardProps {
  index: IndexMeta;
  sparklineData: { time: number; value: number }[];
}

export default function IndexCard({ index, sparklineData }: IndexCardProps) {
  return (
    <div className="index-card">
      <span className="index-card__name">{index.name}</span>
      <div className="index-card__mid">
        <div className="index-card__price">
          <span className="index-card__nav number">
            {index.price.toLocaleString("fi-FI", { minimumFractionDigits: 2 })}
          </span>
          <PriceChange value={index.dailyChange} size="sm" />
        </div>
        <SignalBadge signal={index.signal} />
      </div>
      <div className="index-card__sparkline">
        <SparklineChart
          data={sparklineData}
          width={280}
          height={36}
        />
      </div>
    </div>
  );
}
