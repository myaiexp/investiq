import { useTranslation } from "react-i18next";

export default function IndicesPage() {
  const { t } = useTranslation();

  return (
    <div>
      <h2>{t("nav.indices")}</h2>
      <p style={{ color: "var(--text-muted)", marginTop: "var(--gap-md)" }}>
        Index dashboard — coming soon
      </p>
    </div>
  );
}
