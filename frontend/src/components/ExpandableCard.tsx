import type { ReactNode } from "react";
import "./ExpandableCard.css";

interface ExpandableCardProps {
  expanded: boolean;
  onClick: () => void;
  header: ReactNode;
  expandedContent: ReactNode;
}

export default function ExpandableCard({
  expanded,
  onClick,
  header,
  expandedContent,
}: ExpandableCardProps) {
  return (
    <div
      className={`expandable-card card${expanded ? " expandable-card--expanded" : ""}`}
      onClick={onClick}
    >
      <div className="expandable-card__header">{header}</div>
      {expanded && (
        <div className="expandable-card__content">{expandedContent}</div>
      )}
    </div>
  );
}
