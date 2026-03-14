import { useState, useEffect, useCallback } from "react";
import { useParams } from "react-router-dom";
import { useTranslation } from "react-i18next";
import type {
  IndexMeta,
  OHLCVBar,
  IndicatorData,
  IndicatorId,
  SignalSummary,
} from "../types/index.ts";
import type { Period } from "../types/index.ts";
import { PERIOD_INTERVAL_MAP } from "../types/index.ts";
import { api } from "../api/client.ts";
import BackButton from "../components/BackButton.tsx";
import PriceChart from "../components/charts/PriceChart.tsx";
import PeriodSelector from "../components/PeriodSelector.tsx";
import IntervalSelector from "../components/IntervalSelector.tsx";
import IndicatorPanel from "../components/IndicatorPanel.tsx";
import SignalSummaryCard from "../components/SignalSummaryCard.tsx";
import BottomDrawer from "../components/BottomDrawer.tsx";
import "./IndexDetailPage.css";

export default function IndexDetailPage() {
  const { ticker } = useParams<{ ticker: string }>();
  const { t } = useTranslation();
  const [index, setIndex] = useState<IndexMeta | null>(null);
  const [ohlcv, setOhlcv] = useState<OHLCVBar[]>([]);
  const [dataTransitionTimestamp, setDataTransitionTimestamp] = useState<
    number | null
  >(null);
  const [backfillInterval, setBackfillInterval] = useState<string | null>(
    null,
  );
  const [indicators, setIndicators] = useState<IndicatorData[]>([]);
  const [signal, setSignal] = useState<SignalSummary | null>(null);
  const [period, setPeriod] = useState<Period>("1y");
  const [interval, setInterval] = useState<string>("1D");
  const [enabledIndicators, setEnabledIndicators] = useState<Set<IndicatorId>>(
    new Set(),
  );
  const [drawerOpen, setDrawerOpen] = useState(false);

  // Load index metadata
  useEffect(() => {
    if (!ticker) return;
    api.getIndices().then((indices) => {
      const found = indices.find((i) => i.ticker === ticker);
      setIndex(found ?? null);
    });
    api.getSignal(ticker).then(setSignal);
  }, [ticker]);

  // Load OHLCV + indicators when period/interval changes
  useEffect(() => {
    if (!ticker) return;
    api
      .getOHLCV(ticker, period, interval)
      .then((res) => {
        setOhlcv(res.bars);
        setDataTransitionTimestamp(res.dataTransitionTimestamp ?? null);
        setBackfillInterval(res.backfillInterval ?? null);
      })
      .catch(() => {
        setOhlcv([]);
        setDataTransitionTimestamp(null);
        setBackfillInterval(null);
      });
    api.getIndicators(ticker, period, interval).then(setIndicators).catch(() => setIndicators([]));
  }, [ticker, period, interval]);

  // When period changes, reset interval to default if current preset isn't available.
  // Custom intervals (not in any period's preset list) are kept as-is.
  const handlePeriodChange = useCallback(
    (newPeriod: Period) => {
      setPeriod(newPeriod);
      const config = PERIOD_INTERVAL_MAP[newPeriod];
      // Check if current interval is a standard preset in some period
      const isStandardPreset = Object.values(PERIOD_INTERVAL_MAP).some(
        (c) => c.intervals.includes(interval),
      );
      if (isStandardPreset && !config.intervals.includes(interval)) {
        setInterval(config.defaultInterval);
      }
    },
    [interval],
  );

  const handleToggleIndicator = useCallback((id: IndicatorId) => {
    setEnabledIndicators((prev) => {
      const next = new Set(prev);
      if (next.has(id)) next.delete(id);
      else next.add(id);
      return next;
    });
  }, []);

  if (!index) {
    return (
      <div className="index-detail">
        <BackButton />
        <p className="index-detail__loading">{t("nav.indices")}...</p>
      </div>
    );
  }

  const indicatorMetas = indicators.map((ind) => ({
    id: ind.id,
    category: ind.id === "bollinger" || ind.id === "ma" || ind.id === "fibonacci" || ind.id === "ichimoku"
      ? ("overlay" as const)
      : ("oscillator" as const),
    signal: ind.signal,
  }));

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
    <div className="index-detail">
      <BackButton />
      <header className="index-detail__header">
        <h2 className="index-detail__title">{index.name}</h2>
        <span className="index-detail__price number">
          {index.price.toLocaleString("fi-FI", { minimumFractionDigits: 2 })}
          {index.currency && (
            <span className="index-detail__currency"> {index.currency}</span>
          )}
        </span>
      </header>

      <div className="index-detail__controls">
        <PeriodSelector value={period} onChange={handlePeriodChange} />
        <span className="index-detail__controls-sep" aria-hidden="true" />
        <IntervalSelector
          period={period}
          value={interval}
          onChange={setInterval}
        />
      </div>

      <div className="index-detail__layout">
        <div className="index-detail__chart-area">
          <PriceChart
            data={ohlcv}
            indicators={indicators}
            enabledIndicators={enabledIndicators}
            dataTransitionTimestamp={dataTransitionTimestamp ?? undefined}
            backfillInterval={backfillInterval ?? undefined}
            interval={interval}
          />
          {filteredSignal && (
            <div className="index-detail__signal-mobile">
              <SignalSummaryCard summary={filteredSignal} />
            </div>
          )}
        </div>
        <aside className="index-detail__sidebar">
          <IndicatorPanel
            indicators={indicatorMetas}
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
        className="index-detail__drawer-btn"
        onClick={() => setDrawerOpen(true)}
        aria-label={t("detail.indicatorPanel")}
      >
        ⚙
      </button>

      <BottomDrawer open={drawerOpen} onClose={() => setDrawerOpen(false)}>
        <IndicatorPanel
          indicators={indicatorMetas}
          enabled={enabledIndicators}
          onToggle={handleToggleIndicator}
        />
        {filteredSignal && <SignalSummaryCard summary={filteredSignal} />}
      </BottomDrawer>
    </div>
  );
}
