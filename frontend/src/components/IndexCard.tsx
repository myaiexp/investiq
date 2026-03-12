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
    <div className="index-card__header">
      <div className="index-card__info">
        <span className="index-card__name">{index.name}</span>
        <span className="index-card__price number">
          {index.price.toLocaleString("fi-FI", { minimumFractionDigits: 2 })}
        </span>
      </div>
      <PriceChange value={index.dailyChange} size="sm" />
      <SparklineChart data={sparklineData} />
      <SignalBadge signal={index.signal} />
    </div>
  );
}
