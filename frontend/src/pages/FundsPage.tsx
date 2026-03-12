import { useTranslation } from "react-i18next";

export default function FundsPage() {
  const { t } = useTranslation();

  return (
    <div>
      <h2>{t("nav.funds")}</h2>
      <p style={{ color: "var(--text-muted)", marginTop: "var(--gap-md)" }}>
        Fund analysis — coming soon
      </p>
    </div>
  );
}
