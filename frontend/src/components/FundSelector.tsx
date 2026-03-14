import { useTranslation } from "react-i18next";
import type { FundMeta } from "../types/index.ts";
import "./FundSelector.css";

interface FundSelectorProps {
  allFunds: FundMeta[];
  selectedTickers: string[];
  onAdd: (ticker: string) => void;
  onRemove: (ticker: string) => void;
  maxFunds?: number;
}

export default function FundSelector({
  allFunds,
  selectedTickers,
  onAdd,
  onRemove,
  maxFunds = 5,
}: FundSelectorProps) {
  const { t } = useTranslation();

  const availableFunds = allFunds.filter(
    (f) => !selectedTickers.includes(f.ticker),
  );
  const atMax = selectedTickers.length >= maxFunds;

  const handleSelectChange = (e: React.ChangeEvent<HTMLSelectElement>) => {
    const ticker = e.target.value;
    if (ticker) {
      onAdd(ticker);
      e.target.value = "";
    }
  };

  return (
    <div className="fund-selector">
      <div className="fund-selector__chips">
        {selectedTickers.map((ticker) => {
          const fund = allFunds.find((f) => f.ticker === ticker);
          return (
            <span key={ticker} className="fund-selector__chip">
              <span className="fund-selector__chip-name">
                {fund?.name ?? ticker}
              </span>
              <button
                className="fund-selector__chip-remove"
                onClick={() => onRemove(ticker)}
                aria-label={t("funds.removeFund")}
                title={t("funds.removeFund")}
              >
                ×
              </button>
            </span>
          );
        })}

        {!atMax && (
          <select
            className="fund-selector__add-select"
            onChange={handleSelectChange}
            defaultValue=""
            disabled={availableFunds.length === 0}
          >
            <option value="" disabled>
              {t("funds.addFund")}…
            </option>
            {availableFunds.map((f) => (
              <option key={f.ticker} value={f.ticker}>
                {f.name}
              </option>
            ))}
          </select>
        )}

        {atMax && (
          <span className="fund-selector__max-label">
            {t("funds.maxFundsReached", { max: maxFunds })}
          </span>
        )}
      </div>
    </div>
  );
}
