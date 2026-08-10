import React from "react";
import "@/App.css";
import { BrowserRouter, Routes, Route, Navigate } from "react-router-dom";
import { AuthProvider, useAuth } from "./context/AuthContext";
import { Toaster } from "./components/ui/sonner";
import { MainLayout } from "./components/Layout";
import { VoiceAlertProvider, VoiceSettingsDialog } from "./components/VoiceAlertService";

// Pages
import LoginPage from "./pages/LoginPage";
import DashboardPage from "./pages/DashboardPage";
import DashboardEditorPage from "./pages/DashboardEditorPage";
import UserManagementPage from "./pages/UserManagementPage";
import MonitoringPage from "./pages/MonitoringPage";
import TopologyPage from "./pages/TopologyPage";
import AlertsPage from "./pages/AlertsPage";
import IncidentsPage from "./pages/IncidentsPage";
import PerformancePage from "./pages/PerformancePage";
import AssetsPage from "./pages/AssetsPage";
import SSHTerminalPage from "./pages/SSHTerminalPage";
import ReportsPage from "./pages/ReportsPage";
import ConfigurationPage from "./pages/ConfigurationPage";
import SLAPage from "./pages/SLAPage";
import AgentsPage from "./pages/AgentsPage";
import EscalationPage from "./pages/EscalationPage";
import SettingsPage from "./pages/SettingsPage";
import NetworkDiscoveryPage from "./pages/NetworkDiscoveryPage";
import AuditLogsPage from "./pages/AuditLogsPage";
import ConfigBackupPage from "./pages/ConfigBackupPage";
import FirmwareUpgrade from './pages/FirmwareUpgrade';
import CMDBPage from "./pages/CMDBPage";

const ProtectedRoute = ({ children }) => {
  const { user, loading } = useAuth();

  if (loading) {
    return (
      <div className="min-h-screen flex items-center justify-center bg-background">
        <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-primary"></div>
      </div>
    );
  }

  if (!user) {
    return <Navigate to="/login" replace />;
  }

  return <MainLayout>{children}</MainLayout>;
};

const PublicRoute = ({ children }) => {
  const { user, loading } = useAuth();

  if (loading) {
    return (
      <div className="min-h-screen flex items-center justify-center bg-background">
        <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-primary"></div>
      </div>
    );
  }

  if (user) {
    return <Navigate to="/dashboard" replace />;
  }

  return children;
};

function AppRoutes() {
  return (
    <Routes>
      <Route
        path="/login"
        element={
          <PublicRoute>
            <LoginPage />
          </PublicRoute>
        }
      />
      <Route
        path="/dashboard"
        element={
          <ProtectedRoute>
            <DashboardPage />
          </ProtectedRoute>
        }
      />
      <Route
        path="/monitoring"
        element={
          <ProtectedRoute>
            <MonitoringPage />
          </ProtectedRoute>
        }
      />
      <Route
        path="/topology"
        element={
          <ProtectedRoute>
            <TopologyPage />
          </ProtectedRoute>
        }
      />
      <Route
        path="/alerts"
        element={
          <ProtectedRoute>
            <AlertsPage />
          </ProtectedRoute>
        }
      />
      <Route
        path="/incidents"
        element={
          <ProtectedRoute>
            <IncidentsPage />
          </ProtectedRoute>
        }
      />
      <Route
        path="/performance"
        element={
          <ProtectedRoute>
            <PerformancePage />
          </ProtectedRoute>
        }
      />
      <Route
        path="/assets"
        element={
          <ProtectedRoute>
            <AssetsPage />
          </ProtectedRoute>
        }
      />
      <Route
        path="/ssh-terminal"
        element={
          <ProtectedRoute>
            <SSHTerminalPage />
          </ProtectedRoute>
        }
        />
      <Route
        path="/firmware-upgrade"
        element={
          <ProtectedRoute>
            <FirmwareUpgrade />
          </ProtectedRoute>
        }
      />
      <Route
        path="/reports"
        element={
          <ProtectedRoute>
            <ReportsPage />
          </ProtectedRoute>
        }
      />
      <Route
        path="/configuration"
        element={
          <ProtectedRoute>
            <ConfigurationPage />
          </ProtectedRoute>
        }
      />
      <Route
        path="/sla"
        element={
          <ProtectedRoute>
            <SLAPage />
          </ProtectedRoute>
        }
      />
      <Route
        path="/agents"
        element={
          <ProtectedRoute>
            <AgentsPage />
          </ProtectedRoute>
        }
      />
      <Route
        path="/escalation"
        element={
          <ProtectedRoute>
            <EscalationPage />
          </ProtectedRoute>
        }
      />
      <Route
        path="/settings"
        element={
          <ProtectedRoute>
            <SettingsPage />
          </ProtectedRoute>
        }
      />
      <Route
        path="/network-discovery"
        element={
          <ProtectedRoute>
            <NetworkDiscoveryPage />
          </ProtectedRoute>
        }
      />
      <Route
        path="/dashboard-editor"
        element={
          <ProtectedRoute>
            <DashboardEditorPage />
          </ProtectedRoute>
        }
      />
      <Route
        path="/user-management"
        element={
          <ProtectedRoute>
            <UserManagementPage />
          </ProtectedRoute>
        }
      />
      <Route
        path="/audit-logs"
        element={
          <ProtectedRoute>
            <AuditLogsPage />
          </ProtectedRoute>
        }
      />
      <Route
        path="/cmdb"
        element={
          <ProtectedRoute>
            <CMDBPage />
          </ProtectedRoute>
        }
      />
      <Route
        path="/config-backup"
        element={
          <ProtectedRoute>
            <ConfigBackupPage />
          </ProtectedRoute>
        }
      />
      <Route path="/" element={<Navigate to="/dashboard" replace />} />
      <Route path="*" element={<Navigate to="/dashboard" replace />} />
    </Routes>
  );
}

function App() {
  return (
    <BrowserRouter>
      <AuthProvider>
        <VoiceAlertProvider>
          <AppRoutes />
          <VoiceSettingsDialog />
          <Toaster position="top-right" richColors />
        </VoiceAlertProvider>
      </AuthProvider>
    </BrowserRouter>
  );
}

export default App;
