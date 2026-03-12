import { useState, useEffect } from "react";
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

interface CommitEntry {
  hash: string;
  date: string;
  message: string;
}

function formatFinnishDateTime(isoDate: string): string {
  const d = new Date(isoDate);
  const day = String(d.getDate()).padStart(2, "0");
  const month = String(d.getMonth() + 1).padStart(2, "0");
  const year = d.getFullYear();
  const hours = String(d.getHours()).padStart(2, "0");
  const mins = String(d.getMinutes()).padStart(2, "0");
  return `${day}.${month}.${year} ${hours}:${mins}`;
}

function formatFinnishDate(isoDate: string): string {
  const d = new Date(isoDate);
  const day = String(d.getDate()).padStart(2, "0");
  const month = String(d.getMonth() + 1).padStart(2, "0");
  const year = d.getFullYear();
  return `${day}.${month}.${year}`;
}

type Tab = "updates" | "changelog";

export default function UpdateTracker() {
  const { t } = useTranslation();
  const [expanded, setExpanded] = useState(false);
  const [tab, setTab] = useState<Tab>("updates");
  const [commits, setCommits] = useState<CommitEntry[]>([]);

  useEffect(() => {
    if (tab !== "changelog" || commits.length > 0) return;
    fetch(`${import.meta.env.BASE_URL}commits.json`)
      .then((r) => r.json())
      .then(setCommits)
      .catch(() => {});
  }, [tab, commits.length]);

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
        <span className="update-tracker__label">{t("updates.title")}</span>
      </button>

      {expanded && (
        <div className="update-tracker__panel">
          <div className="update-tracker__tabs">
            <button
              className={`update-tracker__tab${tab === "updates" ? " update-tracker__tab--active" : ""}`}
              onClick={(e) => { e.stopPropagation(); setTab("updates"); }}
            >
              {t("updates.title")}
            </button>
            <button
              className={`update-tracker__tab${tab === "changelog" ? " update-tracker__tab--active" : ""}`}
              onClick={(e) => { e.stopPropagation(); setTab("changelog"); }}
            >
              Changelog
            </button>
          </div>

          <div className="update-tracker__content">
            {tab === "updates" &&
              entries.map((entry) => (
                <div key={entry.id} className="update-tracker__entry">
                  <h4 className="update-tracker__entry-title">
                    {t(entry.titleKey)}
                    <span
                      className={`update-tracker__entry-category update-tracker__entry-category--${entry.category}`}
                    >
                      {entry.category}
                    </span>
                  </h4>
                  <span className="update-tracker__entry-date">
                    {formatFinnishDate(entry.date)}
                  </span>
                  <p className="update-tracker__entry-desc">
                    {t(entry.descriptionKey)}
                  </p>
                </div>
              ))}

            {tab === "changelog" &&
              (commits.length === 0 ? (
                <p className="update-tracker__empty">Loading...</p>
              ) : (
                commits.map((c) => (
                  <div key={c.hash} className="update-tracker__commit">
                    <span className="update-tracker__commit-meta">
                      {formatFinnishDateTime(c.date)}
                    </span>
                    {" "}
                    <span className="update-tracker__commit-msg">{c.message}</span>
                  </div>
                ))
              ))}
          </div>
        </div>
      )}
    </div>
  );
}
