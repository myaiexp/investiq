import { useState, useEffect } from "react";
import { useTranslation } from "react-i18next";
import type { IndexMeta, OHLCVBar, IndicatorMeta } from "../types/index.ts";
import { api } from "../api/client.ts";
import CardGrid from "../components/CardGrid.tsx";
import GroupLabel from "../components/GroupLabel.tsx";
import ExpandableCard from "../components/ExpandableCard.tsx";
import IndexCard from "../components/IndexCard.tsx";
import IndexExpandedPanel from "../components/IndexExpandedPanel.tsx";
import { generateOHLCV } from "../data/mock/index.ts";
import { MOCK_SIGNALS } from "../data/mock/signals.ts";
import "./IndicesPage.css";

export default function IndicesPage() {
  const { t } = useTranslation();
  const [indices, setIndices] = useState<IndexMeta[]>([]);
  const [expandedTicker, setExpandedTicker] = useState<string | null>(null);
  const [expandedOHLCV, setExpandedOHLCV] = useState<OHLCVBar[]>([]);

  useEffect(() => {
    api.getIndices().then(setIndices);
  }, []);

  const handleCardClick = (ticker: string) => {
    if (expandedTicker === ticker) {
      setExpandedTicker(null);
      setExpandedOHLCV([]);
    } else {
      setExpandedTicker(ticker);
      // Load 3-month daily data for expanded panel chart
      api.getOHLCV(ticker, "3m", "1D").then(setExpandedOHLCV);
    }
  };

  const nordicIndices = indices.filter((i) => i.region === "nordic");
  const globalIndices = indices.filter((i) => i.region === "global");

  const getSparklineData = (ticker: string) => {
    // 30-day close data for sparkline
    const bars = generateOHLCV(ticker, "1m", "1D");
    return bars.map((b) => ({ time: b.time, value: b.close }));
  };

  const getTopIndicators = (ticker: string): IndicatorMeta[] => {
    const summary = MOCK_SIGNALS[ticker];
    if (!summary) return [];
    return summary.breakdown.slice(0, 4);
  };

  const renderGroup = (label: string, items: IndexMeta[]) => {
    if (items.length === 0) return null;
    return (
      <section className="indices-page__group">
        <GroupLabel>{label}</GroupLabel>
        <CardGrid>
          {items.map((index) => (
            <ExpandableCard
              key={index.ticker}
              expanded={expandedTicker === index.ticker}
              onClick={() => handleCardClick(index.ticker)}
              header={
                <IndexCard
                  index={index}
                  sparklineData={getSparklineData(index.ticker)}
                  expanded={expandedTicker === index.ticker}
                />
              }
              expandedContent={
                <IndexExpandedPanel
                  index={index}
                  ohlcvData={expandedOHLCV}
                  topIndicators={getTopIndicators(index.ticker)}
                />
              }
            />
          ))}
        </CardGrid>
      </section>
    );
  };

  return (
    <div className="indices-page">
      <h2 className="indices-page__title">{t("nav.indices")}</h2>
      {renderGroup(t("group.nordic"), nordicIndices)}
      {renderGroup(t("group.global"), globalIndices)}
    </div>
  );
}
