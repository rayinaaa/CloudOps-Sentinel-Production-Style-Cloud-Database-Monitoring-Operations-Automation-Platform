import React, { useState, useEffect } from "react";
import { Layout } from "./components/layout/Layout";
import { OverviewPage } from "./pages/OverviewPage";
import { DatabaseMonitoringPage } from "./pages/DatabaseMonitoringPage";
import { InfrastructurePage } from "./pages/InfrastructurePage";
import { BackupManagementPage } from "./pages/BackupManagementPage";
import { IncidentManagementPage } from "./pages/IncidentManagementPage";
import { TenantManagementPage } from "./pages/TenantManagementPage";
import { OperationalLogsPage } from "./pages/OperationalLogsPage";
import { PageId } from "./types";
import { api } from "./api/client";

export const App: React.FC = () => {
  const [activePage, setActivePage] = useState<PageId>("overview");
  const [openIncidentCount, setOpenIncidentCount] = useState<number>(0);
  const [lastUpdated, setLastUpdated] = useState<string>("");
  const [isRefreshing, setIsRefreshing] = useState<boolean>(false);
  const [refreshKey, setRefreshKey] = useState<number>(0);

  const fetchGlobalStatus = async () => {
    try {
      setIsRefreshing(true);
      const metrics = await api.getIncidentMetrics();
      setOpenIncidentCount(metrics.open_incidents);
      setLastUpdated(new Date().toLocaleTimeString());
    } catch (_) {
      // Fallback
      setLastUpdated(new Date().toLocaleTimeString());
    } finally {
      setIsRefreshing(false);
    }
  };

  useEffect(() => {
    fetchGlobalStatus();
    // Auto-refresh every 30 seconds
    const interval = setInterval(fetchGlobalStatus, 30000);
    return () => clearInterval(interval);
  }, []);

  const handleGlobalRefresh = () => {
    fetchGlobalStatus();
    setRefreshKey((k) => k + 1);
  };

  const pageMeta: Record<PageId, { title: string; subtitle: string }> = {
    overview: {
      title: "Cloud Operations Center",
      subtitle: "High-level database health, concurrency saturation, and active firing alerts",
    },
    database: {
      title: "Database Performance & Capacity",
      subtitle: "PostgreSQL 16 connection states, buffer cache hit rates, and table-level disk footprint",
    },
    infrastructure: {
      title: "Cloud Infrastructure & Telemetry",
      subtitle: "Process resource consumption, container fleet availability, and Prometheus scrape targets",
    },
    backups: {
      title: "Backup & Disaster Recovery Management",
      subtitle: "Automated compressed pg_dump snapshots with SHA256 integrity and AWS S3 storage",
    },
    incidents: {
      title: "SRE Incident Management & Escalation",
      subtitle: "Prometheus Alertmanager triage, MTTA/MTTR timers, and tiered on-call escalation",
    },
    tenants: {
      title: "Multi-Tenant SaaS Fleet Inventory",
      subtitle: "Tenant isolation, seat allocations, plan tiers, and storage quotas",
    },
    logs: {
      title: "Operational Log Stream",
      subtitle: "Real-time structured application, audit, and database engine event stream",
    },
  };

  return (
    <Layout
      activePage={activePage}
      onNavigate={setActivePage}
      pageTitle={pageMeta[activePage].title}
      pageSubtitle={pageMeta[activePage].subtitle}
      lastUpdated={lastUpdated}
      isRefreshing={isRefreshing}
      onRefresh={handleGlobalRefresh}
      openIncidentCount={openIncidentCount}
    >
      <div key={refreshKey}>
        {activePage === "overview" && <OverviewPage onNavigate={setActivePage} />}
        {activePage === "database" && <DatabaseMonitoringPage />}
        {activePage === "infrastructure" && <InfrastructurePage />}
        {activePage === "backups" && <BackupManagementPage />}
        {activePage === "incidents" && <IncidentManagementPage />}
        {activePage === "tenants" && <TenantManagementPage />}
        {activePage === "logs" && <OperationalLogsPage />}
      </div>
    </Layout>
  );
};

export default App;

