import { useNavigate } from "react-router-dom";
import { useTranslation } from "react-i18next";
import "./BackButton.css";

export default function BackButton() {
  const navigate = useNavigate();
  const { t } = useTranslation();

  return (
    <button className="back-button" onClick={() => navigate(-1)}>
      ← {t("detail.back")}
    </button>
  );
}
