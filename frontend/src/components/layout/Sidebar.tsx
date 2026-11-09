import React from "react";
import {
  LayoutDashboard,
  Database,
  Server,
  Archive,
  AlertOctagon,
  Users,
  Terminal,
  ShieldAlert,
  Activity,
} from "lucide-react";
import { PageId } from "../../types";

interface SidebarProps {
  activePage: PageId;
  onNavigate: (page: PageId) => void;
  openIncidentCount?: number;
}

export const Sidebar: React.FC<SidebarProps> = ({
  activePage,
  onNavigate,
  openIncidentCount = 0,
}) => {
  const navItems = [
    { id: "overview" as PageId, label: "Overview", icon: LayoutDashboard },
    { id: "database" as PageId, label: "Database Ops", icon: Database },
    { id: "infrastructure" as PageId, label: "Infrastructure", icon: Server },
    { id: "backups" as PageId, label: "Backups & DR", icon: Archive },
    {
      id: "incidents" as PageId,
      label: "Incident Center",
      icon: AlertOctagon,
      badge: openIncidentCount > 0 ? openIncidentCount : undefined,
    },
    { id: "tenants" as PageId, label: "Multi-Tenant Fleet", icon: Users },
    { id: "logs" as PageId, label: "Operational Logs", icon: Terminal },
  ];

  return (
    <aside className="w-64 border-r border-sentinel-800 bg-sentinel-950 flex flex-col h-screen select-none shrink-0">
      {/* Brand Header */}
      <div className="h-16 border-b border-sentinel-800 px-5 flex items-center gap-3">
        <div className="h-9 w-9 rounded-lg bg-sky-500/10 border border-sky-500/30 flex items-center justify-center text-sky-400">
          <ShieldAlert className="h-5 w-5" />
        </div>
        <div>
          <div className="flex items-center gap-2">
            <span className="font-bold text-sm tracking-tight text-white">
              CloudOps Sentinel
            </span>
            <span className="rounded bg-sky-500/20 px-1 py-0.2 text-[10px] font-mono text-sky-300 font-semibold">
              v0.1
            </span>
          </div>
          <span className="text-[11px] text-slate-400 font-medium block">
            Cloud SRE Automation
          </span>
        </div>
      </div>

      {/* Navigation Menu */}
      <div className="flex-1 py-4 px-3 space-y-1 overflow-y-auto">
        <div className="px-3 pb-2 text-[11px] font-semibold uppercase tracking-wider text-slate-400">
          Platform Operations
        </div>
        {navItems.map((item) => {
          const Icon = item.icon;
          const isActive = activePage === item.id;
          return (
            <button
              key={item.id}
              onClick={() => onNavigate(item.id)}
              className={`w-full flex items-center justify-between px-3 py-2.5 rounded-lg text-xs font-medium transition-all ${
                isActive
                  ? "bg-sky-500/15 text-sky-300 border border-sky-500/30"
                  : "text-slate-400 hover:text-slate-200 hover:bg-sentinel-900 border border-transparent"
              }`}
            >
              <div className="flex items-center gap-3">
                <Icon
                  className={`h-4 w-4 ${
                    isActive ? "text-sky-400" : "text-slate-400"
                  }`}
                />
                <span>{item.label}</span>
              </div>
              {item.badge !== undefined && (
                <span className="rounded-full bg-rose-500/20 border border-rose-500/30 px-2 py-0.5 text-[10px] font-mono text-rose-300 font-semibold">
                  {item.badge}
                </span>
              )}
            </button>
          );
        })}
      </div>

      {/* Cluster Footer Status */}
      <div className="p-4 border-t border-sentinel-800 bg-sentinel-900/40">
        <div className="rounded-lg border border-sentinel-800 bg-sentinel-900 p-3 text-xs space-y-2">
          <div className="flex items-center justify-between text-slate-400">
            <span className="flex items-center gap-1.5 font-medium">
              <Activity className="h-3.5 w-3.5 text-emerald-400 animate-pulse" />
              Engine Cluster
            </span>
            <span className="font-mono text-[10px] text-emerald-400 font-semibold">
              LIVE
            </span>
          </div>
          <div className="text-[11px] text-slate-400 font-mono flex justify-between">
            <span>Primary DB:</span>
            <span className="text-slate-300">sentinel_db :5434</span>
          </div>
          <div className="text-[11px] text-slate-400 font-mono flex justify-between">
            <span>Target RDS:</span>
            <span className="text-slate-300">ecommerce :5433</span>
          </div>
        </div>
      </div>
    </aside>
  );
};

