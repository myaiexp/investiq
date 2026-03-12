import { useTranslation } from "react-i18next";
import type { Signal } from "../types/index.ts";
import "./SignalBadge.css";

interface SignalBadgeProps {
  signal: Signal;
}

export default function SignalBadge({ signal }: SignalBadgeProps) {
  const { t } = useTranslation();

  return (
    <span className={`signal-badge signal-badge--${signal}`}>
      {t(`signal.${signal}`)}
    </span>
  );
}
