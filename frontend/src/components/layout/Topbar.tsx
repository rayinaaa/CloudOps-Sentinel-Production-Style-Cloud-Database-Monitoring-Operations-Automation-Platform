import React from "react";
import {
  RefreshCw,
  Bell,
  Clock,
  Radio,
  UserCheck,
} from "lucide-react";

interface TopbarProps {
  pageTitle: string;
  pageSubtitle: string;
  lastUpdated?: string;
  isRefreshing?: boolean;
  onRefresh: () => void;
  openIncidentCount?: number;
}

export const Topbar: React.FC<TopbarProps> = ({
  pageTitle,
  pageSubtitle,
  lastUpdated,
  isRefreshing = false,
  onRefresh,
  openIncidentCount = 0,
}) => {
  return (
    <header className="h-16 border-b border-sentinel-800 bg-sentinel-950/80 backdrop-blur-md px-6 flex items-center justify-between shrink-0 sticky top-0 z-30">
      {/* Title & context */}
      <div>
        <h1 className="text-base font-semibold text-white tracking-tight">
          {pageTitle}
        </h1>
        <p className="text-xs text-slate-400 font-mono hidden sm:block">
          {pageSubtitle}
        </p>
      </div>

      {/* Cluster telemetry pills & Actions */}
      <div className="flex items-center gap-3">
        {/* Live Socket Status */}
        <div className="hidden md:flex items-center gap-2 rounded-full border border-sentinel-800 bg-sentinel-900/90 px-3 py-1 text-xs">
          <span className="relative flex h-2 w-2">
            <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-emerald-400 opacity-75"></span>
            <span className="relative inline-flex rounded-full h-2 w-2 bg-emerald-500"></span>
          </span>
          <span className="font-mono text-slate-300 text-[11px]">
            Prometheus 10s Scrape
          </span>
        </div>

        {/* Timestamp */}
        {lastUpdated && (
          <div className="hidden lg:flex items-center gap-1.5 text-slate-400 text-xs font-mono">
            <Clock className="h-3.5 w-3.5" />
            <span>Updated {lastUpdated}</span>
          </div>
        )}

        {/* Global Refresh Button */}
        <button
          onClick={onRefresh}
          disabled={isRefreshing}
          className="inline-flex items-center gap-1.5 rounded-lg border border-sentinel-800 bg-sentinel-900 px-3 py-1.5 text-xs font-medium text-slate-300 hover:border-sentinel-700 hover:text-white transition-colors disabled:opacity-50"
          title="Refresh operational telemetry"
        >
          <RefreshCw
            className={`h-3.5 w-3.5 text-sky-400 ${
              isRefreshing ? "animate-spin" : ""
            }`}
          />
          <span className="hidden sm:inline">Refresh</span>
        </button>

        {/* On-Call User Pill */}
        <div className="flex items-center gap-2 rounded-lg border border-sentinel-800 bg-sentinel-900 px-2.5 py-1.5 text-xs text-slate-300">
          <div className="h-6 w-6 rounded-full bg-indigo-500/20 text-indigo-300 flex items-center justify-center font-bold text-[10px] border border-indigo-500/30">
            SC
          </div>
          <div className="hidden sm:block text-left">
            <div className="text-[11px] font-medium leading-none text-slate-200">
              Sarah Connor
            </div>
            <div className="text-[10px] text-sky-400 font-mono leading-tight flex items-center gap-1">
              <UserCheck className="h-2.5 w-2.5" /> Primary SRE
            </div>
          </div>
        </div>
      </div>
    </header>
  );
};

