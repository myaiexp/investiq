import { useState, useEffect, useCallback } from "react";
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

const STORAGE_KEY = "investiq-last-seen-update";

function getLastSeenId(latestId: number): number {
  try {
    const stored = localStorage.getItem(STORAGE_KEY);
    if (stored === null) {
      // First visit — mark everything as seen
      localStorage.setItem(STORAGE_KEY, String(latestId));
      return latestId;
    }
    return Number(stored) || 0;
  } catch {
    return latestId;
  }
}

function setLastSeenId(id: number) {
  try {
    localStorage.setItem(STORAGE_KEY, String(id));
  } catch {}
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

  const entries = updates as UpdateEntry[];
  const latest = entries[0];
  const latestId = latest?.id ?? 0;
  const [lastSeenId, setLastSeen] = useState(() => getLastSeenId(latestId));
  // Track which entries to highlight — frozen when panel opens
  const [highlightBelow, setHighlightBelow] = useState(0);

  const hasNew = latest && latest.id > lastSeenId;

  useEffect(() => {
    if (tab !== "changelog" || commits.length > 0) return;
    fetch(`${import.meta.env.BASE_URL}commits.json`)
      .then((r) => r.json())
      .then(setCommits)
      .catch(() => {});
  }, [tab, commits.length]);

  const handleToggle = useCallback(() => {
    if (!expanded) {
      // Opening: freeze the highlight threshold, then mark as seen
      setHighlightBelow(lastSeenId);
      if (hasNew && latest) {
        setLastSeenId(latest.id);
        setLastSeen(latest.id);
      }
    }
    setExpanded(!expanded);
  }, [expanded, hasNew, latest, lastSeenId]);

  if (!latest) return null;

  return (
    <div className={`update-tracker${expanded ? " update-tracker--expanded" : ""}`}>
      <button className="update-tracker__pill" onClick={handleToggle}>
        <span className={`update-tracker__dot${hasNew ? " update-tracker__dot--pulse" : ""}`} />
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
                <div
                  key={entry.id}
                  className={`update-tracker__entry${entry.id > highlightBelow ? " update-tracker__entry--new" : ""}`}
                >
                  <h4 className="update-tracker__entry-title">
                    {t(entry.titleKey)}
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
