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
    <div className="fund-card__header">
      <div className="fund-card__info">
        <div className="fund-card__name-row">
          <span className="fund-card__name">{fund.name}</span>
          <TypeBadge fundType={fund.fundType} />
        </div>
        <div className="fund-card__meta">
          <span className="fund-card__nav number">
            {fund.nav.toFixed(2)} €
          </span>
          <PriceChange value={fund.dailyChange} size="sm" />
        </div>
      </div>
      <div className="fund-card__right">
        <div className="fund-card__return">
          <span className="fund-card__return-label">1v</span>
          <PriceChange value={fund.return1Y} size="md" />
        </div>
        <SparklineChart
          data={sparklineData}
          color={fund.return1Y >= 0 ? "var(--green)" : "var(--red)"}
        />
      </div>
      <div className="fund-card__benchmark">
        <span className="fund-card__benchmark-text">{fund.benchmarkName}</span>
      </div>
    </div>
  );
}
