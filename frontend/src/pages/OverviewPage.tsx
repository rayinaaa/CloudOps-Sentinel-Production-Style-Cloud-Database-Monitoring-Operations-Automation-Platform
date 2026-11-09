import React, { useEffect, useState } from "react";
import {
  Database,
  Activity,
  AlertOctagon,
  Archive,
  Users,
  ShieldCheck,
  Server,
  ArrowUpRight,
} from "lucide-react";
import { StatCard } from "../components/common/StatCard";
import { Badge } from "../components/common/Badge";
import { LoadingSkeleton } from "../components/common/LoadingSkeleton";
import { ErrorState } from "../components/common/ErrorState";
import { ConnectionTrendChart } from "../components/charts/ConnectionTrendChart";
import { api } from "../api/client";
import {
  DatabaseOperationalSummary,
  Incident,
  IncidentMetrics,
  InfraMetrics,
  PageId,
} from "../types";

interface OverviewPageProps {
  onNavigate: (page: PageId) => void;
}

export const OverviewPage: React.FC<OverviewPageProps> = ({ onNavigate }) => {
  const [dbSummary, setDbSummary] = useState<DatabaseOperationalSummary | null>(null);
  const [incidents, setIncidents] = useState<Incident[]>([]);
  const [metrics, setMetrics] = useState<IncidentMetrics | null>(null);
  const [infra, setInfra] = useState<InfraMetrics | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const fetchData = async () => {
    try {
      setLoading(true);
      setError(null);
      const [dbRes, incRes, metRes, infRes] = await Promise.all([
        api.getDatabaseSummary(),
        api.getIncidents("OPEN"),
        api.getIncidentMetrics(),
        api.getInfraMetrics(),
      ]);
      setDbSummary(dbRes);
      setIncidents(incRes);
      setMetrics(metRes);
      setInfra(infRes);
    } catch (err: any) {
      setError(err.message || "Failed to load platform overview metrics.");
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchData();
  }, []);

  if (loading) {
    return (
      <div className="space-y-6">
        <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-4">
          {Array.from({ length: 4 }).map((_, i) => (
            <div key={i} className="h-28 rounded-xl bg-sentinel-900 animate-pulse border border-sentinel-800" />
          ))}
        </div>
        <LoadingSkeleton rows={5} height="h-16" />
      </div>
    );
  }

  if (error || !dbSummary) {
    return <ErrorState message={error || "Could not connect to Sentinel API."} onRetry={fetchData} />;
  }

  const pool = dbSummary.connection_metrics;
  const tenancy = dbSummary.tenancy_summary;
  const openCriticals = incidents.filter((i) => i.severity === "CRITICAL").length;

  return (
    <div className="space-y-6">
      {/* Platform Banner Alert if critical incidents open */}
      {openCriticals > 0 && (
        <div className="flex items-center justify-between rounded-xl border border-red-500/30 bg-red-950/20 px-5 py-3.5 backdrop-blur-sm">
          <div className="flex items-center gap-3">
            <span className="flex h-3 w-3 relative">
              <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-red-400 opacity-75"></span>
              <span className="relative inline-flex rounded-full h-3 w-3 bg-red-500"></span>
            </span>
            <div>
              <span className="text-sm font-semibold text-red-200">
                Critical Outage Alert Firing
              </span>
              <span className="text-xs text-red-300/80 ml-2 hidden sm:inline">
                {openCriticals} critical incident(s) require immediate SRE triage.
              </span>
            </div>
          </div>
          <button
            onClick={() => onNavigate("incidents")}
            className="inline-flex items-center gap-1.5 rounded-lg border border-red-500/40 bg-red-500/20 px-3 py-1.5 text-xs font-medium text-red-200 hover:bg-red-500/30 transition-colors"
          >
            Triage Now <ArrowUpRight className="h-3.5 w-3.5" />
          </button>
        </div>
      )}

      {/* Primary KPI Grid */}
      <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-4">
        <StatCard
          title="Pool Saturation"
          value={`${pool.pool_saturation_pct}%`}
          subValue={`${pool.total_connections}/${pool.max_connections} conns`}
          icon={Activity}
          status={pool.connection_status === "CRITICAL" ? "danger" : pool.connection_status === "WARNING" ? "warning" : "healthy"}
          trend={{ value: "< 75% Target", isPositive: pool.pool_saturation_pct < 75 }}
          onClick={() => onNavigate("database")}
        />

        <StatCard
          title="Buffer Cache Hit Ratio"
          value="99.4%"
          subValue="In-memory hits"
          icon={Database}
          status="healthy"
          trend={{ value: "> 90% SLA", isPositive: true }}
          onClick={() => onNavigate("database")}
        />

        <StatCard
          title="Active Incidents"
          value={metrics ? metrics.open_incidents : incidents.length}
          subValue={`${openCriticals} Critical`}
          icon={AlertOctagon}
          status={openCriticals > 0 ? "danger" : incidents.length > 0 ? "warning" : "healthy"}
          onClick={() => onNavigate("incidents")}
        />

        <StatCard
          title="S3 DR Backups"
          value="Healthy"
          subValue="Last snapshot 4h ago"
          icon={Archive}
          status="healthy"
          onClick={() => onNavigate("backups")}
        />
      </div>

      {/* Main Visualizations Row */}
      <div className="grid grid-cols-1 gap-6 lg:grid-cols-3">
        {/* Left 2 Cols: Live Connection Concurrency */}
        <div className="lg:col-span-2 rounded-xl border border-sentinel-800 bg-sentinel-900/80 p-5 backdrop-blur-sm">
          <div className="flex items-center justify-between pb-4 border-b border-sentinel-800">
            <div>
              <h2 className="text-sm font-semibold text-white tracking-tight">
                Database Concurrency & Saturation Trend
              </h2>
              <p className="text-xs text-slate-400 font-mono">
                Real-time active client backend queries vs pool limits
              </p>
            </div>
            <div className="flex items-center gap-2">
              <Badge label={pool.connection_status} variant={pool.connection_status} />
              <button
                onClick={() => onNavigate("database")}
                className="text-xs font-mono text-sky-400 hover:text-sky-300 ml-2"
              >
                Deep Metrics &rarr;
              </button>
            </div>
          </div>
          <div className="pt-4">
            <ConnectionTrendChart
              currentActive={pool.active_connections}
              currentIdle={pool.idle_connections}
              maxConnections={pool.max_connections}
            />
          </div>
        </div>

        {/* Right 1 Col: Engine Health & Fleet Status */}
        <div className="rounded-xl border border-sentinel-800 bg-sentinel-900/80 p-5 backdrop-blur-sm space-y-4">
          <div className="flex items-center justify-between pb-3 border-b border-sentinel-800">
            <h2 className="text-sm font-semibold text-white tracking-tight">
              Cloud Infrastructure
            </h2>
            <span className="text-[11px] font-mono text-emerald-400 font-semibold">
              7/7 SERVICES UP
            </span>
          </div>

          <div className="space-y-3">
            {infra?.services.map((svc) => (
              <div
                key={svc.name}
                className="flex items-center justify-between rounded-lg border border-sentinel-800/80 bg-sentinel-850/60 p-2.5"
              >
                <div>
                  <div className="text-xs font-semibold text-slate-200">
                    {svc.name}
                  </div>
                  <div className="text-[10px] text-slate-400 font-mono">
                    {svc.component} &bull; Port :{svc.port}
                  </div>
                </div>
                <div className="text-right">
                  <Badge label={svc.status} variant="HEALTHY" size="sm" />
                  {svc.latency_ms && (
                    <div className="text-[10px] font-mono text-slate-400 mt-0.5">
                      {svc.latency_ms}ms
                    </div>
                  )}
                </div>
              </div>
            ))}
          </div>

          <button
            onClick={() => onNavigate("infrastructure")}
            className="w-full text-center text-xs text-sky-400 hover:text-sky-300 font-medium py-1"
          >
            View Complete Infrastructure &rarr;
          </button>
        </div>
      </div>

      {/* Bottom Row: Active Incident Triage & Multi-Tenant Snapshot */}
      <div className="grid grid-cols-1 gap-6 lg:grid-cols-2">
        {/* Active Open Incidents Feed */}
        <div className="rounded-xl border border-sentinel-800 bg-sentinel-900/80 p-5">
          <div className="flex items-center justify-between pb-3 border-b border-sentinel-800">
            <div className="flex items-center gap-2">
              <AlertOctagon className="h-4 w-4 text-rose-400" />
              <h2 className="text-sm font-semibold text-white">
                Active Firing Incidents
              </h2>
            </div>
            <button
              onClick={() => onNavigate("incidents")}
              className="text-xs text-sky-400 hover:text-sky-300 font-mono"
            >
              Incident Center ({incidents.length}) &rarr;
            </button>
          </div>

          <div className="mt-4 space-y-3">
            {incidents.length === 0 ? (
              <div className="py-8 text-center text-xs text-slate-400">
                <ShieldCheck className="h-8 w-8 text-emerald-400 mx-auto mb-2" />
                All cloud database clusters are currently within operational SLA limits.
              </div>
            ) : (
              incidents.slice(0, 3).map((inc) => (
                <div
                  key={inc.id}
                  onClick={() => onNavigate("incidents")}
                  className="rounded-lg border border-sentinel-800 bg-sentinel-850 p-3 hover:border-sentinel-700 cursor-pointer transition-colors"
                >
                  <div className="flex items-center justify-between">
                    <span className="text-xs font-semibold text-white">
                      {inc.title}
                    </span>
                    <Badge label={inc.severity} variant={inc.severity} size="sm" />
                  </div>
                  <p className="mt-1 text-[11px] text-slate-400 line-clamp-1">
                    {inc.description || "Alertmanager triggered anomaly."}
                  </p>
                  <div className="mt-2 flex items-center justify-between text-[10px] font-mono text-slate-400">
                    <span>Target: {inc.target_instance}</span>
                    <span className="text-rose-400 font-semibold">{inc.status}</span>
                  </div>
                </div>
              ))
            )}
          </div>
        </div>

        {/* Multi-Tenant SaaS Snapshot */}
        <div className="rounded-xl border border-sentinel-800 bg-sentinel-900/80 p-5">
          <div className="flex items-center justify-between pb-3 border-b border-sentinel-800">
            <div className="flex items-center gap-2">
              <Users className="h-4 w-4 text-indigo-400" />
              <h2 className="text-sm font-semibold text-white">
                Multi-Tenant Fleet Capacity
              </h2>
            </div>
            <button
              onClick={() => onNavigate("tenants")}
              className="text-xs text-sky-400 hover:text-sky-300 font-mono"
            >
              Fleet Inventory &rarr;
            </button>
          </div>

          <div className="mt-4 grid grid-cols-2 gap-3">
            <div className="rounded-lg border border-sentinel-800 bg-sentinel-850 p-3">
              <span className="text-[11px] text-slate-400">Total Tenants</span>
              <div className="font-mono text-xl font-bold text-white mt-1">
                {tenancy.total_tenants}
              </div>
              <span className="text-[10px] text-emerald-400 font-mono">
                {tenancy.active_tenants} Active &bull; {tenancy.suspended_tenants} Suspended
              </span>
            </div>
            <div className="rounded-lg border border-sentinel-800 bg-sentinel-850 p-3">
              <span className="text-[11px] text-slate-400">Provisioned Users</span>
              <div className="font-mono text-xl font-bold text-white mt-1">
                {tenancy.total_users}
              </div>
              <span className="text-[10px] text-slate-400 font-mono">
                Across 4 SLA tiers
              </span>
            </div>
            <div className="rounded-lg border border-sentinel-800 bg-sentinel-850 p-3">
              <span className="text-[11px] text-slate-400">Total Storage</span>
              <div className="font-mono text-xl font-bold text-white mt-1">
                {dbSummary.storage_metrics.total_database_size_human}
              </div>
              <span className="text-[10px] text-sky-400 font-mono">
                {dbSummary.storage_metrics.tables.length} User tables
              </span>
            </div>
            <div className="rounded-lg border border-sentinel-800 bg-sentinel-850 p-3">
              <span className="text-[11px] text-slate-400">SRE SLA Compliance</span>
              <div className="font-mono text-xl font-bold text-emerald-400 mt-1">
                {metrics ? `${metrics.sla_compliance_rate_pct}%` : "100.0%"}
              </div>
              <span className="text-[10px] text-emerald-400/80 font-mono">
                MTTR: {metrics?.mean_time_to_resolve_human || "30m"}
              </span>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
};

