import { BrowserRouter, Routes, Route, NavLink } from "react-router-dom";
import { useTranslation } from "react-i18next";
import "./i18n";
import "./App.css";

import IndicesPage from "./pages/IndicesPage";
import FundsPage from "./pages/FundsPage";
import IndexDetailPage from "./pages/IndexDetailPage";
import FundDetailPage from "./pages/FundDetailPage";
import FundComparisonPage from "./pages/FundComparisonPage";
import UpdateTracker from "./components/UpdateTracker";

function App() {
  const { t, i18n } = useTranslation();

  const toggleLang = () => {
    i18n.changeLanguage(i18n.language === "fi" ? "en" : "fi");
  };

  return (
    <BrowserRouter basename="/investiq">
      <div className="app">
        <header className="header">
          <div className="header-left">
            <h1 className="logo">{t("app.title")}</h1>
            <span className="subtitle">{t("app.subtitle")}</span>
          </div>
          <nav className="nav">
            <NavLink to="/" end>
              {t("nav.indices")}
            </NavLink>
            <NavLink to="/funds">{t("nav.funds")}</NavLink>
          </nav>
          <button className="lang-toggle" onClick={toggleLang}>
            {i18n.language === "fi" ? "EN" : "FI"}
          </button>
        </header>

        <main className="main">
          <Routes>
            <Route path="/" element={<IndicesPage />} />
            <Route path="/funds" element={<FundsPage />} />
            <Route path="/index/:ticker" element={<IndexDetailPage />} />
            <Route path="/funds/compare" element={<FundComparisonPage />} />
            <Route path="/funds/:ticker" element={<FundDetailPage />} />
          </Routes>
        </main>
        <UpdateTracker />
      </div>
    </BrowserRouter>
  );
}

export default App;
