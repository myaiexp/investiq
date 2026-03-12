import { useState, useEffect } from "react";
import { useTranslation } from "react-i18next";
import type { FundMeta } from "../types/index.ts";
import { api } from "../api/client.ts";
import CardGrid from "../components/CardGrid.tsx";
import GroupLabel from "../components/GroupLabel.tsx";
import ExpandableCard from "../components/ExpandableCard.tsx";
import FundCard from "../components/FundCard.tsx";
import FundExpandedPanel from "../components/FundExpandedPanel.tsx";
import { generateFundNAV } from "../data/mock/index.ts";
import "./FundsPage.css";

export default function FundsPage() {
  const { t } = useTranslation();
  const [funds, setFunds] = useState<FundMeta[]>([]);
  const [expandedTicker, setExpandedTicker] = useState<string | null>(null);

  useEffect(() => {
    api.getFunds().then(setFunds);
  }, []);

  const handleCardClick = (ticker: string) => {
    setExpandedTicker(expandedTicker === ticker ? null : ticker);
  };

  const equityFunds = funds.filter((f) => f.fundType === "equity");
  const bondFunds = funds.filter((f) => f.fundType === "bond");

  const getSparklineData = (ticker: string) => {
    const points = generateFundNAV(ticker, "3m");
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
