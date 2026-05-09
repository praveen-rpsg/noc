import React, { useState, useEffect } from "react";
import "@/App.css";
import { BrowserRouter, Routes, Route, Navigate } from "react-router-dom";
import { AuthProvider, useAuth } from "./context/AuthContext";
import { Toaster } from "./components/ui/sonner";
import { MainLayout } from "./components/Layout";
import { VoiceAlertProvider, VoiceSettingsDialog } from "./components/VoiceAlertService";
import { getBackendUrlSync, initConfig } from "./services/config";

// Pages
import LoginPage from "./pages/LoginPage";
import ActivationPage from "./pages/ActivationPage";
import DashboardPage from "./pages/DashboardPage";
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

// License check hook
const useLicenseStatus = () => {
  const [isActivated, setIsActivated] = useState(null);
  const [loading, setLoading] = useState(true);

  const checkLicense = async () => {
    try {
      await initConfig();
      const API_URL = getBackendUrlSync();
      const response = await fetch(`${API_URL}/api/license/status`);
      const data = await response.json();
      setIsActivated(data.is_activated === true);
    } catch (error) {
      console.error('Failed to check license:', error);
      // If we can't connect, assume not activated
      setIsActivated(false);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    checkLicense();
  }, []);

  return { isActivated, loading, recheckLicense: checkLicense };
};

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
  const { isActivated, loading: licenseLoading, recheckLicense } = useLicenseStatus();

  // Show loading while checking license
  if (licenseLoading) {
    return (
      <div className="min-h-screen flex items-center justify-center bg-background">
        <div className="text-center">
          <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-primary mx-auto mb-4"></div>
          <p className="text-muted-foreground">Checking license...</p>
        </div>
      </div>
    );
  }

  // Show activation page if not activated
  if (!isActivated) {
    return <ActivationPage onActivated={recheckLicense} />;
  }

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
