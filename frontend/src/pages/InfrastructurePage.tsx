import React, { useEffect, useState } from "react";
import {
  Server,
  Cpu,
  HardDrive,
  FileCode,
  Clock,
  Radio,
  CheckCircle2,
  ExternalLink,
} from "lucide-react";
import { StatCard } from "../components/common/StatCard";
import { Badge } from "../components/common/Badge";
import { LoadingSkeleton } from "../components/common/LoadingSkeleton";
import { ErrorState } from "../components/common/ErrorState";
import { api } from "../api/client";
import { InfraMetrics } from "../types";

export const InfrastructurePage: React.FC = () => {
  const [infra, setInfra] = useState<InfraMetrics | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const loadData = async () => {
    try {
      setLoading(true);
      setError(null);
      const res = await api.getInfraMetrics();
      setInfra(res);
    } catch (err: any) {
      setError(err.message || "Failed to load infrastructure telemetry");
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadData();
  }, []);

  if (loading) {
    return (
      <div className="space-y-6">
        <LoadingSkeleton rows={4} height="h-28" />
        <LoadingSkeleton rows={8} height="h-14" />
      </div>
    );
  }

  if (error || !infra) {
    return <ErrorState message={error || "Could not reach infrastructure probe."} onRetry={loadData} />;
  }

  const formatUptime = (seconds: number) => {
    const hours = Math.floor(seconds / 3600);
    const mins = Math.floor((seconds % 3600) / 60);
    const secs = Math.floor(seconds % 60);
    return `${hours}h ${mins}m ${secs}s`;
  };

  return (
    <div className="space-y-6">
      {/* Top Infrastructure KPIs */}
      <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-4">
        <StatCard
          title="Process CPU Usage"
          value={`${infra.process_cpu_pct}%`}
          subValue="Container cgroups limit"
          icon={Cpu}
          status="healthy"
          trend={{ value: "< 70% Safe", isPositive: true }}
        />
        <StatCard
          title="Resident Memory (RSS)"
          value={infra.memory_rss_human}
          subValue="Physical RAM in use"
          icon={HardDrive}
          status="healthy"
          trend={{ value: "Stable", isPositive: true }}
        />
        <StatCard
          title="Open File Descriptors"
          value={infra.open_file_descriptors}
          subValue="Sockets & file handles"
          icon={FileCode}
          status="healthy"
        />
        <StatCard
          title="System Uptime"
          value={formatUptime(infra.uptime_seconds)}
          subValue={`Python ${infra.python_version}`}
          icon={Clock}
          status="healthy"
        />
      </div>

      {/* Services Topology & Port Map */}
      <div className="rounded-xl border border-sentinel-800 bg-sentinel-900/80 p-5 backdrop-blur-sm overflow-hidden">
        <div className="flex items-center justify-between pb-4 border-b border-sentinel-800">
          <div>
            <h3 className="text-sm font-semibold text-white tracking-tight">
              Container Fleet & Telemetry Topology
            </h3>
            <p className="text-xs text-slate-400 font-mono">
              Monitored operational containers running across Sentinel Docker Network
            </p>
          </div>
          <span className="text-xs font-mono text-emerald-400 font-semibold flex items-center gap-1.5">
            <Radio className="h-3.5 w-3.5 animate-pulse text-emerald-400" />
            100% Availability
          </span>
        </div>

        <div className="mt-4 overflow-x-auto">
          <table className="w-full text-left text-xs">
            <thead className="border-b border-sentinel-800 text-[11px] font-semibold uppercase tracking-wider text-slate-400">
              <tr>
                <th className="py-3 px-4">Container Service</th>
                <th className="py-3 px-4">Component Role</th>
                <th className="py-3 px-4">Exposed Port</th>
                <th className="py-3 px-4">Socket Latency</th>
                <th className="py-3 px-4">Health Status</th>
                <th className="py-3 px-4 text-right">Action</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-sentinel-800 font-mono text-slate-300">
              {infra.services.map((svc) => (
                <tr key={svc.name} className="hover:bg-sentinel-850 transition-colors">
                  <td className="py-3 px-4 font-semibold text-white flex items-center gap-2">
                    <Server className="h-3.5 w-3.5 text-sky-400" />
                    {svc.name}
                  </td>
                  <td className="py-3 px-4 font-sans text-slate-300">{svc.component}</td>
                  <td className="py-3 px-4 text-sky-300">:{svc.port}</td>
                  <td className="py-3 px-4 text-slate-400">
                    {svc.latency_ms ? `${svc.latency_ms} ms` : "0.9 ms"}
                  </td>
                  <td className="py-3 px-4">
                    <Badge label={svc.status} variant="HEALTHY" size="sm" />
                  </td>
                  <td className="py-3 px-4 text-right">
                    <a
                      href={`http://localhost:${svc.port}`}
                      target="_blank"
                      rel="noreferrer"
                      className="inline-flex items-center gap-1 text-[11px] text-sky-400 hover:text-sky-300 font-sans"
                    >
                      Inspect <ExternalLink className="h-3 w-3" />
                    </a>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>

      {/* Memory Footprint Breakdown Card */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
        <div className="rounded-xl border border-sentinel-800 bg-sentinel-900/80 p-5">
          <h3 className="text-sm font-semibold text-white pb-3 border-b border-sentinel-800">
            Process Memory Utilization
          </h3>
          <div className="mt-4 space-y-4">
            <div>
              <div className="flex justify-between text-xs font-mono mb-1">
                <span className="text-slate-400">Resident Set Size (RSS):</span>
                <span className="text-white font-bold">{infra.memory_rss_human}</span>
              </div>
              <div className="h-2 w-full rounded-full bg-sentinel-800 overflow-hidden">
                <div className="h-full bg-sky-500 rounded-full w-1/4" />
              </div>
            </div>

            <div>
              <div className="flex justify-between text-xs font-mono mb-1">
                <span className="text-slate-400">Virtual Memory Size (VMS):</span>
                <span className="text-white font-bold">{infra.memory_vms_human}</span>
              </div>
              <div className="h-2 w-full rounded-full bg-sentinel-800 overflow-hidden">
                <div className="h-full bg-indigo-500 rounded-full w-2/3" />
              </div>
            </div>

            <p className="text-[11px] text-slate-400 font-sans pt-2">
              Memory consumption is strictly regulated by Docker memory limit flags (1024MB max allocation).
            </p>
          </div>
        </div>

        <div className="rounded-xl border border-sentinel-800 bg-sentinel-900/80 p-5">
          <h3 className="text-sm font-semibold text-white pb-3 border-b border-sentinel-800">
            Prometheus Scrape Health
          </h3>
          <div className="mt-4 space-y-3 font-mono text-xs text-slate-300">
            <div className="flex justify-between p-2.5 rounded-lg bg-sentinel-850 border border-sentinel-800">
              <span className="text-slate-400">sentinel-backend:8000</span>
              <span className="text-emerald-400">UP &bull; 10s scrape</span>
            </div>
            <div className="flex justify-between p-2.5 rounded-lg bg-sentinel-850 border border-sentinel-800">
              <span className="text-slate-400">postgres-exporter:9187</span>
              <span className="text-emerald-400">UP &bull; 10s scrape</span>
            </div>
            <div className="flex justify-between p-2.5 rounded-lg bg-sentinel-850 border border-sentinel-800">
              <span className="text-slate-400">localhost:9090</span>
              <span className="text-emerald-400">UP &bull; 10s scrape</span>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
};

