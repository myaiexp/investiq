import { useState, useEffect } from "react";
import { useSearchParams } from "react-router-dom";
import { useTranslation } from "react-i18next";
import type { FundMeta, FundNAVPoint, FundPerformance, Period } from "../types/index.ts";
import { api } from "../api/client.ts";
import BackButton from "../components/BackButton.tsx";
import PeriodSelector from "../components/PeriodSelector.tsx";
import FundSelector from "../components/FundSelector.tsx";
import ComparisonChart from "../components/charts/ComparisonChart.tsx";
import ComparisonTable from "../components/ComparisonTable.tsx";
import "./FundComparisonPage.css";

export default function FundComparisonPage() {
  const { t } = useTranslation();
  const [searchParams, setSearchParams] = useSearchParams();

  const selectedTickers = (searchParams.get("tickers") ?? "")
    .split(",")
    .filter(Boolean);

  const [period, setPeriod] = useState<Period>("1y");
  const [allFunds, setAllFunds] = useState<FundMeta[]>([]);
  const [fundData, setFundData] = useState<Record<string, FundNAVPoint[]>>({});
  const [fundPerformance, setFundPerformance] = useState<Record<string, FundPerformance>>({});

  // Load fund metadata once on mount
  useEffect(() => {
    api.getFunds().then(setAllFunds).catch(() => {});
  }, []);

  // Fetch NAV data for each selected ticker when tickers or period changes
  useEffect(() => {
    if (selectedTickers.length === 0) {
      setFundData({});
      return;
    }

    const controller = new AbortController();

    Promise.all(
      selectedTickers.map((ticker) =>
        api.getFundNAV(ticker, period).then((data) => ({ ticker, data })).catch(() => ({ ticker, data: [] as FundNAVPoint[] })),
      ),
    ).then((results) => {
      if (controller.signal.aborted) return;
      const map: Record<string, FundNAVPoint[]> = {};
      for (const { ticker, data } of results) map[ticker] = data;
      setFundData(map);
    });

    return () => controller.abort();
    // selectedTickers is a derived array — join it to get a stable dep value
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [selectedTickers.join(","), period]);

  // Fetch performance data for each selected ticker when tickers change
  useEffect(() => {
    if (selectedTickers.length === 0) {
      setFundPerformance({});
      return;
    }

    const controller = new AbortController();

    Promise.all(
      selectedTickers.map((ticker) =>
        api.getFundPerformance(ticker).then((perf) => ({ ticker, perf })).catch(() => null),
      ),
    ).then((results) => {
      if (controller.signal.aborted) return;
      const map: Record<string, FundPerformance> = {};
      for (const r of results) {
        if (r) map[r.ticker] = r.perf;
      }
      setFundPerformance(map);
    });

    return () => controller.abort();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [selectedTickers.join(",")]);

  const handleAddFund = (ticker: string) => {
    const next = [...selectedTickers, ticker];
    setSearchParams({ tickers: next.join(",") });
  };

  const handleRemoveFund = (ticker: string) => {
    const next = selectedTickers.filter((t) => t !== ticker);
    setSearchParams({ tickers: next.join(",") });
  };

  // Build chart funds — only tickers with data
  const chartFunds = selectedTickers
    .map((ticker) => {
      const meta = allFunds.find((f) => f.ticker === ticker);
      return {
        ticker,
        name: meta?.name ?? ticker,
        data: fundData[ticker] ?? [],
      };
    })
    .filter((f) => f.data.length > 0);

  // Build table funds — only tickers with performance data
  const tableFunds = selectedTickers
    .map((ticker) => {
      const meta = allFunds.find((f) => f.ticker === ticker);
      const performance = fundPerformance[ticker];
      if (!performance) return null;
      return {
        ticker,
        name: meta?.name ?? ticker,
        performance,
      };
    })
    .filter((f): f is { ticker: string; name: string; performance: FundPerformance } => f !== null);

  const hasEnoughFunds = selectedTickers.length >= 2;

  return (
    <div className="fund-comparison">
      <BackButton />

      <header className="fund-comparison__header">
        <h2 className="fund-comparison__title">{t("funds.comparisonTitle")}</h2>
      </header>

      <div className="fund-comparison__controls">
        <FundSelector
          allFunds={allFunds}
          selectedTickers={selectedTickers}
          onAdd={handleAddFund}
          onRemove={handleRemoveFund}
          maxFunds={5}
        />
        {hasEnoughFunds && (
          <PeriodSelector value={period} onChange={setPeriod} />
        )}
      </div>

      {!hasEnoughFunds ? (
        <p className="fund-comparison__empty">
          {t("funds.noFundsSelected")}
        </p>
      ) : (
        <>
          {chartFunds.length >= 2 && (
            <section className="fund-comparison__chart-section">
              <ComparisonChart funds={chartFunds} />
            </section>
          )}

          {tableFunds.length >= 2 && (
            <section className="fund-comparison__table-section">
              <ComparisonTable funds={tableFunds} />
            </section>
          )}
        </>
      )}
    </div>
  );
}
