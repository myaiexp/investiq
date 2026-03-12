import { useState } from "react";
import { useTranslation } from "react-i18next";
import updates from "../data/updates.json";
import "./UpdateTracker.css";

interface UpdateEntry {
  id: number;
  date: string;
  category: string;
  titleKey: string;
  descriptionKey: string;
}

export default function UpdateTracker() {
  const { t } = useTranslation();
  const [expanded, setExpanded] = useState(false);

  const entries = updates as UpdateEntry[];
  const latest = entries[0];

  if (!latest) return null;

  return (
    <div className={`update-tracker${expanded ? " update-tracker--expanded" : ""}`}>
      <button
        className="update-tracker__pill"
        onClick={() => setExpanded(!expanded)}
      >
        <span className="update-tracker__dot" />
        <span className="update-tracker__date">{latest.date}</span>
        <span className="update-tracker__label">{t("updates.title")}</span>
      </button>

      {expanded && (
        <div className="update-tracker__panel">
          {entries.map((entry) => (
            <div key={entry.id} className="update-tracker__entry">
              <div className="update-tracker__entry-header">
                <span className="update-tracker__entry-date">{entry.date}</span>
                <span
                  className={`update-tracker__entry-category update-tracker__entry-category--${entry.category}`}
                >
                  {entry.category}
                </span>
              </div>
              <h4 className="update-tracker__entry-title">
                {t(entry.titleKey)}
              </h4>
              <p className="update-tracker__entry-desc">
                {t(entry.descriptionKey)}
              </p>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
