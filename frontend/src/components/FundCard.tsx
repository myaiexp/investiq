import type { FundMeta } from "../types/index.ts";
import SparklineChart from "./SparklineChart.tsx";
import TypeBadge from "./TypeBadge.tsx";
import PriceChange from "./PriceChange.tsx";
import "./FundCard.css";

interface FundCardProps {
  fund: FundMeta;
  sparklineData: { time: number; value: number }[];
}

export default function FundCard({ fund, sparklineData }: FundCardProps) {
  return (
    <div className="fund-card">
      <div className="fund-card__top">
        <span className="fund-card__name">{fund.name}</span>
        <TypeBadge fundType={fund.fundType} />
      </div>
      <div className="fund-card__mid">
        <div className="fund-card__price">
          <span className="fund-card__nav number">{fund.nav.toFixed(2)} €</span>
          <PriceChange value={fund.dailyChange} size="sm" />
        </div>
        <div className="fund-card__return">
          <span className="fund-card__return-label">1v</span>
          <PriceChange value={fund.return1Y} size="md" />
        </div>
      </div>
      <div className="fund-card__sparkline">
        <SparklineChart
          data={sparklineData}
          width={280}
          height={36}
          color={fund.return1Y >= 0 ? "var(--green)" : "var(--red)"}
        />
      </div>
      <span className="fund-card__benchmark-text">vs. {fund.benchmarkName}</span>
    </div>
  );
}
