import { useTranslation } from "react-i18next";
import { Link } from "react-router-dom";
import type { IndexMeta, IndicatorMeta } from "../types/index.ts";
import type { OHLCVBar } from "../types/index.ts";
import MiniCandlestickChart from "./MiniCandlestickChart.tsx";
import SignalBadge from "./SignalBadge.tsx";
import "./IndexExpandedPanel.css";

interface IndexExpandedPanelProps {
  index: IndexMeta;
  ohlcvData: OHLCVBar[];
  topIndicators: IndicatorMeta[];
}

export default function IndexExpandedPanel({
  index,
  ohlcvData,
  topIndicators,
}: IndexExpandedPanelProps) {
  const { t } = useTranslation();

  return (
    <div className="index-expanded" onClick={(e) => e.stopPropagation()}>
      <div className="index-expanded__chart">
        <MiniCandlestickChart data={ohlcvData} />
      </div>
      <div className="index-expanded__signals">
        <h4 className="index-expanded__signals-title">
          {t("detail.signalSummary")}
        </h4>
        {topIndicators.map((ind) => (
          <div key={ind.id} className="index-expanded__signal-row">
            <span className="index-expanded__signal-name">
              {t(`indicators.${ind.id}`)}
            </span>
            <SignalBadge signal={ind.signal} />
          </div>
        ))}
      </div>
      <Link
        to={`/index/${encodeURIComponent(index.ticker)}`}
        className="index-expanded__link"
        onClick={(e) => e.stopPropagation()}
      >
        {t("detail.fullAnalysis")} →
      </Link>
    </div>
  );
}
