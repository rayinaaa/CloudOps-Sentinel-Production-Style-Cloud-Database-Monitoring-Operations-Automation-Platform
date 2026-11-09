import React, { useEffect, useState } from "react";
import {
  Users,
  Search,
  Building,
  Shield,
  HardDrive,
  CheckCircle2,
  AlertCircle,
} from "lucide-react";
import { StatCard } from "../components/common/StatCard";
import { Badge } from "../components/common/Badge";
import { LoadingSkeleton } from "../components/common/LoadingSkeleton";
import { ErrorState } from "../components/common/ErrorState";
import { EmptyState } from "../components/common/EmptyState";
import { api } from "../api/client";
import { TenantDetail } from "../types";

export const TenantManagementPage: React.FC = () => {
  const [tenants, setTenants] = useState<TenantDetail[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const [searchQuery, setSearchQuery] = useState("");
  const [planFilter, setPlanFilter] = useState("ALL");
  const [statusFilter, setStatusFilter] = useState("ALL");

  const loadTenants = async () => {
    try {
      setLoading(true);
      setError(null);
      const res = await api.getTenants();
      setTenants(res);
    } catch (err: any) {
      setError(err.message || "Failed to load tenant fleet");
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadTenants();
  }, []);

  const formatStorage = (bytes: number) => {
    const gb = Math.round(bytes / (1024 * 1024 * 1024));
    return `${gb} GB`;
  };

  const filteredTenants = tenants.filter((t) => {
    const matchesSearch =
      t.name.toLowerCase().includes(searchQuery.toLowerCase()) ||
      t.slug.toLowerCase().includes(searchQuery.toLowerCase());
    const matchesPlan = planFilter === "ALL" || t.plan === planFilter;
    const matchesStatus = statusFilter === "ALL" || t.status === statusFilter;
    return matchesSearch && matchesPlan && matchesStatus;
  });

  const activeCount = tenants.filter((t) => t.status === "ACTIVE").length;
  const suspendedCount = tenants.filter((t) => t.status === "SUSPENDED").length;
  const totalUsers = tenants.reduce((acc, t) => acc + t.current_users, 0);

  if (loading) {
    return (
      <div className="space-y-6">
        <LoadingSkeleton rows={4} height="h-28" />
        <LoadingSkeleton rows={8} height="h-16" />
      </div>
    );
  }

  if (error) {
    return <ErrorState message={error} onRetry={loadTenants} />;
  }

  return (
    <div className="space-y-6">
      {/* Fleet Overview KPIs */}
      <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-4">
        <StatCard
          title="Total Organizations"
          value={tenants.length}
          subValue="Registered SaaS tenants"
          icon={Building}
          status="neutral"
        />
        <StatCard
          title="Active Accounts"
          value={activeCount}
          subValue={`${Math.round((activeCount / Math.max(1, tenants.length)) * 100)}% active rate`}
          icon={CheckCircle2}
          status="healthy"
        />
        <StatCard
          title="Suspended Accounts"
          value={suspendedCount}
          subValue="Due to billing / audit"
          icon={AlertCircle}
          status={suspendedCount > 0 ? "warning" : "healthy"}
        />
        <StatCard
          title="Provisioned Users"
          value={totalUsers}
          subValue="Across all tenant tiers"
          icon={Users}
          status="healthy"
        />
      </div>

      {/* Filter and Search Bar */}
      <div className="rounded-xl border border-sentinel-800 bg-sentinel-900/80 p-5 backdrop-blur-sm space-y-4">
        <div className="flex flex-col md:flex-row md:items-center justify-between gap-4">
          <div className="relative flex-1 max-w-md">
            <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-slate-400" />
            <input
              type="text"
              placeholder="Search by company name or tenant slug..."
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              className="w-full rounded-lg border border-sentinel-800 bg-sentinel-950 py-2 pl-9 pr-4 text-xs text-white placeholder-slate-500 focus:border-sky-500 focus:outline-none font-mono"
            />
          </div>

          <div className="flex items-center gap-2 text-xs font-mono text-slate-400">
            <span>Showing {filteredTenants.length} of {tenants.length} tenants</span>
          </div>
        </div>

        {/* Filter Pills */}
        <div className="flex flex-wrap items-center gap-4 pt-2 border-t border-sentinel-800 text-xs">
          <div className="flex items-center gap-1.5">
            <span className="text-slate-400 font-medium">Plan:</span>
            {["ALL", "ENTERPRISE", "PRO", "STARTER", "FREE"].map((p) => (
              <button
                key={p}
                onClick={() => setPlanFilter(p)}
                className={`rounded-md px-2.5 py-1 text-[11px] font-mono transition-colors ${
                  planFilter === p
                    ? "bg-sky-500/20 text-sky-300 border border-sky-500/40"
                    : "text-slate-400 hover:text-white"
                }`}
              >
                {p}
              </button>
            ))}
          </div>

          <div className="flex items-center gap-1.5 ml-auto">
            <span className="text-slate-400 font-medium">Status:</span>
            {["ALL", "ACTIVE", "SUSPENDED", "PENDING"].map((s) => (
              <button
                key={s}
                onClick={() => setStatusFilter(s)}
                className={`rounded-md px-2.5 py-1 text-[11px] font-mono transition-colors ${
                  statusFilter === s
                    ? "bg-sky-500/20 text-sky-300 border border-sky-500/40"
                    : "text-slate-400 hover:text-white"
                }`}
              >
                {s}
              </button>
            ))}
          </div>
        </div>
      </div>

      {/* Tenants Table */}
      <div className="rounded-xl border border-sentinel-800 bg-sentinel-900/80 backdrop-blur-sm overflow-hidden">
        {filteredTenants.length === 0 ? (
          <div className="p-12">
            <EmptyState
              title="No tenants found"
              description="No tenant accounts match your current search filters."
            />
          </div>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-left text-xs">
              <thead className="border-b border-sentinel-800 text-[11px] font-semibold uppercase tracking-wider text-slate-400 bg-sentinel-950/60">
                <tr>
                  <th className="py-3 px-4">Organization Name</th>
                  <th className="py-3 px-4">Tenant Slug</th>
                  <th className="py-3 px-4">SLA Plan</th>
                  <th className="py-3 px-4">Account Status</th>
                  <th className="py-3 px-4">Seat Allocation</th>
                  <th className="py-3 px-4">Storage Quota</th>
                  <th className="py-3 px-4">Provisioned</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-sentinel-800 font-mono text-slate-300">
                {filteredTenants.map((t) => {
                  const seatPct = Math.round((t.current_users / t.max_users) * 100);
                  return (
                    <tr key={t.id} className="hover:bg-sentinel-850 transition-colors">
                      <td className="py-3 px-4 font-semibold text-white font-sans">
                        {t.name}
                      </td>
                      <td className="py-3 px-4 text-sky-400">{t.slug}</td>
                      <td className="py-3 px-4">
                        <Badge label={t.plan} variant={t.plan} size="sm" />
                      </td>
                      <td className="py-3 px-4">
                        <Badge label={t.status} variant={t.status} size="sm" />
                      </td>
                      <td className="py-3 px-4">
                        <div className="flex items-center gap-2">
                          <div className="h-1.5 w-16 rounded-full bg-sentinel-800 overflow-hidden">
                            <div
                              className={`h-full rounded-full ${
                                seatPct >= 90
                                  ? "bg-rose-500"
                                  : seatPct >= 70
                                  ? "bg-amber-500"
                                  : "bg-emerald-500"
                              }`}
                              style={{ width: `${seatPct}%` }}
                            />
                          </div>
                          <span className="text-[11px] text-slate-300">
                            {t.current_users} / {t.max_users}
                          </span>
                        </div>
                      </td>
                      <td className="py-3 px-4 text-slate-400">
                        {formatStorage(t.max_storage_bytes)}
                      </td>
                      <td className="py-3 px-4 text-slate-400 text-[11px]">
                        {t.created_at.split(" ")[0]}
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        )}
      </div>
    </div>
  );
};

