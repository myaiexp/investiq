import { useState, useEffect, useRef } from "react";
import { useTranslation } from "react-i18next";
import type { FundMeta, FundNAVPoint } from "../types/index.ts";
import { api } from "../api/client.ts";
import CardGrid from "../components/CardGrid.tsx";
import GroupLabel from "../components/GroupLabel.tsx";
import ExpandableCard from "../components/ExpandableCard.tsx";
import FundCard from "../components/FundCard.tsx";
import FundExpandedPanel from "../components/FundExpandedPanel.tsx";
import "./FundsPage.css";

export default function FundsPage() {
  const { t } = useTranslation();
  const [funds, setFunds] = useState<FundMeta[]>([]);
  const [expandedTicker, setExpandedTicker] = useState<string | null>(null);
  const [sparklines, setSparklines] = useState<Record<string, FundNAVPoint[]>>({});
  const fetchedSparklines = useRef<Set<string>>(new Set());

  useEffect(() => {
    api.getFunds().then(setFunds);
  }, []);

  // Fetch sparklines for all funds once loaded
  useEffect(() => {
    for (const fund of funds) {
      if (fetchedSparklines.current.has(fund.ticker)) continue;
      fetchedSparklines.current.add(fund.ticker);
      api.getFundNAV(fund.ticker, "3m").then((points) => {
        setSparklines((prev) => ({ ...prev, [fund.ticker]: points }));
      }).catch(() => {});
    }
  }, [funds]);

  const handleCardClick = (ticker: string) => {
    setExpandedTicker(expandedTicker === ticker ? null : ticker);
  };

  const equityFunds = funds.filter((f) => f.fundType === "equity");
  const bondFunds = funds.filter((f) => f.fundType === "bond");

  const getSparklineData = (ticker: string) => {
    const points = sparklines[ticker] ?? [];
    return points.map((p) => ({ time: p.time, value: p.value }));
  };

  const renderGroup = (label: string, items: FundMeta[]) => {
    if (items.length === 0) return null;
    return (
      <section className="funds-page__group">
        <GroupLabel>{label}</GroupLabel>
        <CardGrid>
          {items.map((fund) => (
            <ExpandableCard
              key={fund.ticker}
              expanded={expandedTicker === fund.ticker}
              onClick={() => handleCardClick(fund.ticker)}
              header={
                <FundCard
                  fund={fund}
                  sparklineData={getSparklineData(fund.ticker)}
                  expanded={expandedTicker === fund.ticker}
                />
              }
              expandedContent={<FundExpandedPanel fund={fund} />}
            />
          ))}
        </CardGrid>
      </section>
    );
  };

  return (
    <div className="funds-page">
      <h2 className="funds-page__title">{t("nav.funds")}</h2>
      {renderGroup(t("group.equity"), equityFunds)}
      {renderGroup(t("group.bond"), bondFunds)}
    </div>
  );
}
