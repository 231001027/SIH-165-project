import { Routes, Route, Navigate } from "react-router-dom";
import { useAuth } from "./context/AuthContext";
import AppLayout from "./layouts/AppLayout";

import LoginPage from "./pages/LoginPage";
import DashboardPage from "./pages/DashboardPage";
import ReportsListPage from "./pages/ReportsListPage";
import NewReportPage from "./pages/NewReportPage";
import ReportDetailPage from "./pages/ReportDetailPage";
import UploadPage from "./pages/UploadPage";
import ReviewQueuePage from "./pages/ReviewQueuePage";
import ClustersPage from "./pages/ClustersPage";
import TrendsPage from "./pages/TrendsPage";
import RankingsPage from "./pages/RankingsPage";
import EvaluationPage from "./pages/EvaluationPage";
import AuditPage from "./pages/AuditPage";
import AboutPage from "./pages/AboutPage";
import RoutingPage from "./pages/RoutingPage";
import NotFoundPage from "./pages/NotFoundPage";

function ProtectedRoute({ children, roles }) {
  const { isAuthenticated, hasRole } = useAuth();
  if (!isAuthenticated) return <Navigate to="/login" replace />;
  if (roles && !hasRole(...roles)) return <Navigate to="/dashboard" replace />;
  return children;
}

export default function App() {
  const { isAuthenticated } = useAuth();

  return (
    <Routes>
      <Route path="/login" element={isAuthenticated ? <Navigate to="/dashboard" replace /> : <LoginPage />} />

      <Route
        element={
          <ProtectedRoute>
            <AppLayout />
          </ProtectedRoute>
        }
      >
        <Route path="/dashboard" element={<DashboardPage />} />
        <Route path="/reports" element={<ReportsListPage />} />
        <Route path="/reports/new" element={<NewReportPage />} />
        <Route path="/reports/:id" element={<ReportDetailPage />} />
        <Route path="/upload" element={<UploadPage />} />
        <Route path="/review" element={
          <ProtectedRoute roles={["ADMIN", "HSE_ANALYST"]}>
            <ReviewQueuePage />
          </ProtectedRoute>
        } />
        <Route path="/clusters" element={<ClustersPage />} />
        <Route path="/trends" element={<TrendsPage />} />
        <Route path="/rankings" element={<RankingsPage />} />
        <Route path="/evaluation" element={<EvaluationPage />} />
        <Route
          path="/audit"
          element={
            <ProtectedRoute roles={["ADMIN"]}>
              <AuditPage />
            </ProtectedRoute>
          }
        />
        <Route
          path="/routing"
          element={
            <ProtectedRoute roles={["ADMIN"]}>
              <RoutingPage />
            </ProtectedRoute>
          }
        />
        <Route path="/about" element={<AboutPage />} />
      </Route>

      <Route path="/" element={<Navigate to={isAuthenticated ? "/dashboard" : "/login"} replace />} />
      <Route path="*" element={<NotFoundPage />} />
    </Routes>
  );
}
