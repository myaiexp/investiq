import { useState, useEffect } from "react";
import { useParams } from "react-router-dom";
import { useTranslation } from "react-i18next";
import type { FundMeta, FundPerformance, FundNAVPoint } from "../types/index.ts";
import type { Period } from "../types/index.ts";
import { api } from "../api/client.ts";
import BackButton from "../components/BackButton.tsx";
import NAVChart from "../components/charts/NAVChart.tsx";
import RelativePerformanceChart from "../components/charts/RelativePerformanceChart.tsx";
import PerformanceTable from "../components/PerformanceTable.tsx";
import MetricsRow from "../components/MetricsRow.tsx";
import PeriodSelector from "../components/PeriodSelector.tsx";
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

  useEffect(() => {
    if (!ticker) return;
    api.getFunds().then((funds) => {
      const found = funds.find((f) => f.ticker === ticker);
      setFund(found ?? null);
    });
    api.getFundPerformance(ticker).then(setPerformance).catch(() => {});
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
  }, [ticker, period, fund?.benchmarkTicker]);

  if (!fund) {
    return (
      <div className="fund-detail">
        <BackButton />
        <p className="fund-detail__loading">{t("nav.funds")}...</p>
      </div>
    );
  }

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

      <section className="fund-detail__chart-section">
        {navData.length > 0 && (benchmarkData.length > 0 || !fund.benchmarkTicker || benchmarkFailed) && (
          <NAVChart
            fundData={navData}
            benchmarkData={benchmarkData}
            fundName={fund.name}
            benchmarkName={fund.benchmarkName}
          />
        )}
      </section>

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
