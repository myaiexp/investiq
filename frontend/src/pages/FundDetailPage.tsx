import { useState, useEffect, useCallback } from "react";
import { useParams } from "react-router-dom";
import { useTranslation } from "react-i18next";
import type { FundMeta, FundPerformance, FundNAVPoint } from "../types/index.ts";
import type { Period } from "../types/index.ts";
import type { IndicatorData, IndicatorId, SignalSummary } from "../types/index.ts";
import { api } from "../api/client.ts";
import BackButton from "../components/BackButton.tsx";
import NAVChart from "../components/charts/NAVChart.tsx";
import RelativePerformanceChart from "../components/charts/RelativePerformanceChart.tsx";
import PerformanceTable from "../components/PerformanceTable.tsx";
import MetricsRow from "../components/MetricsRow.tsx";
import PeriodSelector from "../components/PeriodSelector.tsx";
import IndicatorPanel from "../components/IndicatorPanel.tsx";
import SignalSummaryCard from "../components/SignalSummaryCard.tsx";
import BottomDrawer from "../components/BottomDrawer.tsx";
import "./FundDetailPage.css";

export default function FundDetailPage() {
  const { ticker } = useParams<{ ticker: string }>();
  const { t } = useTranslation();
  const [fund, setFund] = useState<FundMeta | null>(null);
  const [performance, setPerformance] = useState<FundPerformance | null>(null);
  const [navData, setNavData] = useState<FundNAVPoint[]>([]);
  const [benchmarkData, setBenchmarkData] = useState<FundNAVPoint[]>([]);
  const [benchmarkFailed, setBenchmarkFailed] = useState(false);
  const [period, setPeriod] = useState<Period>("1y");
  const [indicators, setIndicators] = useState<IndicatorData[]>([]);
  const [signal, setSignal] = useState<SignalSummary | null>(null);
  const [enabledIndicators, setEnabledIndicators] = useState<Set<IndicatorId>>(new Set());
  const [drawerOpen, setDrawerOpen] = useState(false);

  useEffect(() => {
    if (!ticker) return;
    api.getFunds().then((funds) => {
      const found = funds.find((f) => f.ticker === ticker);
      setFund(found ?? null);
    });
    api.getFundPerformance(ticker).then(setPerformance).catch(() => {});
    api.getFundSignal(ticker).then(setSignal).catch(() => {});
  }, [ticker]);

  useEffect(() => {
    if (!ticker) return;
    api.getFundNAV(ticker, period).then(setNavData).catch(() => {});
    if (fund?.benchmarkTicker) {
      setBenchmarkFailed(false);
      api.getFundNAV(fund.benchmarkTicker, period)
        .then(setBenchmarkData)
        .catch(() => setBenchmarkFailed(true));
    }
    api.getFundIndicators(ticker, period).then(setIndicators).catch(() => setIndicators([]));
  }, [ticker, period, fund?.benchmarkTicker]);

  const handleToggleIndicator = useCallback((id: IndicatorId) => {
    setEnabledIndicators((prev) => {
      const next = new Set(prev);
      if (next.has(id)) next.delete(id);
      else next.add(id);
      return next;
    });
  }, []);

  if (!fund) {
    return (
      <div className="fund-detail">
        <BackButton />
        <p className="fund-detail__loading">{t("nav.funds")}...</p>
      </div>
    );
  }

  // For fund indicators, only "bollinger" and "ma" are overlays
  const indicatorMetas = indicators.map((ind) => ({
    id: ind.id,
    category: (ind.id === "bollinger" || ind.id === "ma") ? ("overlay" as const) : ("oscillator" as const),
    signal: ind.signal,
  }));

  // When benchmark is present, chart is in % change mode — overlay indicators
  // (MA, Bollinger) use absolute NAV scale and would be on the wrong axis.
  // Filter them out when benchmark data is available.
  const displayMetas = benchmarkData.length > 0
    ? indicatorMetas.filter((m) => m.category === "oscillator")
    : indicatorMetas;
  const displayIndicators = benchmarkData.length > 0
    ? indicators.filter((i) => i.id !== "bollinger" && i.id !== "ma")
    : indicators;

  // Filter signal summary to only show enabled indicators
  const filteredSignal: SignalSummary | null =
    signal && enabledIndicators.size > 0
      ? (() => {
          const filtered = signal.breakdown.filter((b) =>
            enabledIndicators.has(b.id),
          );
          const counts = { buy: 0, sell: 0, hold: 0 };
          for (const b of filtered) counts[b.signal]++;
          let aggregate: "buy" | "sell" | "hold" = "hold";
          if (counts.buy > counts.sell && counts.buy > counts.hold)
            aggregate = "buy";
          else if (counts.sell > counts.buy && counts.sell > counts.hold)
            aggregate = "sell";
          return { aggregate, breakdown: filtered, activeCount: counts };
        })()
      : signal;

  return (
    <div className="fund-detail">
      <BackButton />
      <header className="fund-detail__header">
        <h2 className="fund-detail__title">{fund.name}</h2>
        <span className="fund-detail__nav number">{fund.nav.toFixed(2)} €</span>
      </header>

      <div className="fund-detail__controls">
        <PeriodSelector value={period} onChange={setPeriod} />
      </div>

      <div className="fund-detail__layout">
        <div className="fund-detail__chart-area">
          <section className="fund-detail__chart-section">
            {navData.length > 0 && (benchmarkData.length > 0 || !fund.benchmarkTicker || benchmarkFailed) && (
              <NAVChart
                fundData={navData}
                benchmarkData={benchmarkData}
                fundName={fund.name}
                benchmarkName={fund.benchmarkName}
                indicators={displayIndicators}
                enabledIndicators={enabledIndicators}
              />
            )}
          </section>
          {filteredSignal && (
            <div className="fund-detail__signal-mobile">
              <SignalSummaryCard summary={filteredSignal} />
            </div>
          )}
        </div>
        <aside className="fund-detail__sidebar">
          <IndicatorPanel
            indicators={displayMetas}
            enabled={enabledIndicators}
            onToggle={handleToggleIndicator}
          />
          {filteredSignal && (
            <SignalSummaryCard summary={filteredSignal} />
          )}
        </aside>
      </div>

      {/* Mobile floating button for indicator drawer */}
      <button
        className="fund-detail__drawer-btn"
        onClick={() => setDrawerOpen(true)}
        aria-label={t("detail.indicatorPanel")}
      >
        ⚙
      </button>

      <BottomDrawer open={drawerOpen} onClose={() => setDrawerOpen(false)}>
        <IndicatorPanel
          indicators={displayMetas}
          enabled={enabledIndicators}
          onToggle={handleToggleIndicator}
        />
        {filteredSignal && <SignalSummaryCard summary={filteredSignal} />}
      </BottomDrawer>

      {benchmarkData.length > 0 && (
        <section className="fund-detail__relative">
          <h3 className="fund-detail__section-title">
            {t("funds.relativePerformance")}
          </h3>
          <RelativePerformanceChart
            fundData={navData}
            benchmarkData={benchmarkData}
          />
        </section>
      )}

      {performance && (
        <section className="fund-detail__metrics">
          <PerformanceTable
            fundReturns={performance.returns}
            benchmarkReturns={performance.benchmarkReturns}
            benchmarkName={fund.benchmarkName}
            dataNotes={performance.dataNotes}
          />
          <MetricsRow metrics={performance} dataNotes={performance.dataNotes} />
        </section>
      )}
    </div>
  );
}
