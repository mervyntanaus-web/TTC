import { Routes, Route, Navigate } from "react-router-dom";
import Layout from "./components/Layout";
import Login from "./pages/Login";
import CaseBrowser from "./pages/CaseBrowser";
import SearchPage from "./pages/SearchPage";
import PlayerPage from "./pages/PlayerPage";
import RedactionStudio from "./pages/RedactionStudio";
import SharingPage from "./pages/SharingPage";
import AuditPage from "./pages/AuditPage";
import RetentionPage from "./pages/RetentionPage";
import ReportsDashboard from "./pages/ReportsDashboard";

export default function App() {
  return (
    <Routes>
      <Route path="/login" element={<Login />} />
      <Route element={<Layout />}>
        <Route path="/" element={<Navigate to="/cases" replace />} />
        <Route path="/cases" element={<CaseBrowser />} />
        <Route path="/search" element={<SearchPage />} />
        <Route path="/videos/:videoId" element={<PlayerPage />} />
        <Route path="/videos/:videoId/redact" element={<RedactionStudio />} />
        <Route path="/sharing" element={<SharingPage />} />
        <Route path="/audit" element={<AuditPage />} />
        <Route path="/retention" element={<RetentionPage />} />
        <Route path="/reports" element={<ReportsDashboard />} />
      </Route>
      <Route path="*" element={<Navigate to="/" replace />} />
    </Routes>
  );
}
