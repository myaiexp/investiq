import { useTranslation } from "react-i18next";
import type { FundType } from "../types/index.ts";
import "./TypeBadge.css";

interface TypeBadgeProps {
  fundType: FundType;
}

export default function TypeBadge({ fundType }: TypeBadgeProps) {
  const { t } = useTranslation();

  return (
    <span className={`type-badge type-badge--${fundType}`}>
      {t(`group.${fundType}`)}
    </span>
  );
}
