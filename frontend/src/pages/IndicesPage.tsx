import { useState, useEffect, useRef } from "react";
import { useTranslation } from "react-i18next";
import type { IndexMeta, OHLCVBar, IndicatorMeta, SignalSummary } from "../types/index.ts";
import { api } from "../api/client.ts";
import CardGrid from "../components/CardGrid.tsx";
import GroupLabel from "../components/GroupLabel.tsx";
import ExpandableCard from "../components/ExpandableCard.tsx";
import IndexCard from "../components/IndexCard.tsx";
import IndexExpandedPanel from "../components/IndexExpandedPanel.tsx";
import "./IndicesPage.css";

export default function IndicesPage() {
  const { t } = useTranslation();
  const [indices, setIndices] = useState<IndexMeta[]>([]);
  const [expandedTicker, setExpandedTicker] = useState<string | null>(null);
  const [expandedOHLCV, setExpandedOHLCV] = useState<OHLCVBar[]>([]);
  const [sparklines, setSparklines] = useState<Record<string, { time: number; value: number }[]>>({});
  const [signals, setSignals] = useState<Record<string, SignalSummary>>({});
  const fetchedSparklines = useRef<Set<string>>(new Set());

  useEffect(() => {
    api.getIndices().then(setIndices);
  }, []);

  // Fetch sparklines and signals for all indices once they're loaded
  useEffect(() => {
    for (const index of indices) {
      if (fetchedSparklines.current.has(index.ticker)) continue;
      fetchedSparklines.current.add(index.ticker);
      api.getOHLCV(index.ticker, "1m", "1D").then((res) => {
        setSparklines((prev) => ({
          ...prev,
          [index.ticker]: res.bars.map((b) => ({ time: b.time, value: b.close })),
        }));
      }).catch(() => {});
      api.getSignal(index.ticker).then((sig) => {
        setSignals((prev) => ({ ...prev, [index.ticker]: sig }));
      }).catch(() => {});
    }
  }, [indices]);

  const handleCardClick = (ticker: string) => {
    if (expandedTicker === ticker) {
      setExpandedTicker(null);
      setExpandedOHLCV([]);
    } else {
      setExpandedTicker(ticker);
      api.getOHLCV(ticker, "3m", "1D").then((res) => setExpandedOHLCV(res.bars));
    }
  };

  const nordicIndices = indices.filter((i) => i.region === "nordic");
  const globalIndices = indices.filter((i) => i.region === "global");

  const getSparklineData = (ticker: string) => sparklines[ticker] ?? [];

  const getTopIndicators = (ticker: string): IndicatorMeta[] => {
    const summary = signals[ticker];
    if (!summary) return [];
    return summary.breakdown;
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
