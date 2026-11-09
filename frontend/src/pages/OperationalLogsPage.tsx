import React, { useEffect, useState } from "react";
import {
  Terminal,
  Search,
  Download,
  RefreshCw,
  Filter,
  CheckCircle2,
  AlertTriangle,
  Info,
} from "lucide-react";
import { Badge } from "../components/common/Badge";
import { LoadingSkeleton } from "../components/common/LoadingSkeleton";
import { ErrorState } from "../components/common/ErrorState";
import { EmptyState } from "../components/common/EmptyState";
import { api } from "../api/client";
import { OperationalLogItem } from "../types";

export const OperationalLogsPage: React.FC = () => {
  const [logs, setLogs] = useState<OperationalLogItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const [searchQuery, setSearchQuery] = useState("");
  const [levelFilter, setLevelFilter] = useState("ALL");

  const loadLogs = async () => {
    try {
      setLoading(true);
      setError(null);
      const res = await api.getLogs(50);
      setLogs(res);
    } catch (err: any) {
      setError(err.message || "Failed to stream operational logs");
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadLogs();
  }, []);

  const filteredLogs = logs.filter((log) => {
    const matchesSearch =
      log.message.toLowerCase().includes(searchQuery.toLowerCase()) ||
      log.component.toLowerCase().includes(searchQuery.toLowerCase()) ||
      (log.details && log.details.toLowerCase().includes(searchQuery.toLowerCase()));
    const matchesLevel = levelFilter === "ALL" || log.level === levelFilter;
    return matchesSearch && matchesLevel;
  });

  const exportLogsAsJson = () => {
    const dataStr = "data:text/json;charset=utf-8," + encodeURIComponent(JSON.stringify(filteredLogs, null, 2));
    const downloadAnchor = document.createElement("a");
    downloadAnchor.setAttribute("href", dataStr);
    downloadAnchor.setAttribute("download", `cloudops_sentinel_logs_${new Date().toISOString().slice(0, 10)}.json`);
    document.body.appendChild(downloadAnchor);
    downloadAnchor.click();
    downloadAnchor.remove();
  };

  const getLevelStyle = (level: string) => {
    switch (level) {
      case "ERROR":
        return "text-red-400 bg-red-500/10 border-red-500/20";
      case "WARN":
        return "text-amber-400 bg-amber-500/10 border-amber-500/20";
      default:
        return "text-sky-400 bg-sky-500/10 border-sky-500/20";
    }
  };

  if (loading) {
    return (
      <div className="space-y-6">
        <LoadingSkeleton rows={10} height="h-12" />
      </div>
    );
  }

  if (error) {
    return <ErrorState message={error} onRetry={loadLogs} />;
  }

  return (
    <div className="space-y-6">
      {/* Controls & Search Header */}
      <div className="rounded-xl border border-sentinel-800 bg-sentinel-900/80 p-5 backdrop-blur-sm space-y-4">
        <div className="flex flex-col md:flex-row md:items-center justify-between gap-4">
          <div className="relative flex-1 max-w-md">
            <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-slate-400" />
            <input
              type="text"
              placeholder="Search logs by keyword, query, or component..."
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              className="w-full rounded-lg border border-sentinel-800 bg-sentinel-950 py-2 pl-9 pr-4 text-xs text-white placeholder-slate-500 focus:border-sky-500 focus:outline-none font-mono"
            />
          </div>

          <div className="flex items-center gap-3">
            <button
              onClick={exportLogsAsJson}
              className="inline-flex items-center gap-1.5 rounded-lg border border-sentinel-800 bg-sentinel-900 px-3 py-1.5 text-xs font-medium text-slate-300 hover:text-white transition-colors"
            >
              <Download className="h-3.5 w-3.5" />
              Export JSON
            </button>
            <button
              onClick={loadLogs}
              className="inline-flex items-center gap-1.5 rounded-lg bg-sky-600 px-3 py-1.5 text-xs font-semibold text-white hover:bg-sky-500 transition-colors"
            >
              <RefreshCw className="h-3.5 w-3.5" />
              Live Refresh
            </button>
          </div>
        </div>

        {/* Level Filters */}
        <div className="flex items-center gap-2 pt-2 border-t border-sentinel-800 text-xs font-mono">
          <span className="text-slate-400">Log Level:</span>
          {["ALL", "INFO", "WARN", "ERROR"].map((lvl) => (
            <button
              key={lvl}
              onClick={() => setLevelFilter(lvl)}
              className={`rounded-md px-2.5 py-1 text-[11px] transition-colors ${
                levelFilter === lvl
                  ? "bg-sky-500/20 text-sky-300 border border-sky-500/40"
                  : "text-slate-400 hover:text-white"
              }`}
            >
              {lvl}
            </button>
          ))}
          <span className="ml-auto text-slate-400 text-[11px]">
            {filteredLogs.length} entries matched
          </span>
        </div>
      </div>

      {/* Terminal Monospace Stream View */}
      <div className="rounded-xl border border-sentinel-800 bg-sentinel-950 p-4 font-mono text-xs overflow-hidden shadow-2xl">
        <div className="flex items-center justify-between pb-3 border-b border-sentinel-800 mb-3 text-slate-400 text-[11px]">
          <div className="flex items-center gap-2">
            <Terminal className="h-4 w-4 text-sky-400" />
            <span>Structured Operational Stream &bull; CloudWatch &amp; Container Ingress</span>
          </div>
          <span className="text-emerald-400 text-[10px]">Credential Masking: ACTIVE</span>
        </div>

        {filteredLogs.length === 0 ? (
          <div className="py-12">
            <EmptyState
              title="No logs found"
              description="No operational entries match your search query."
            />
          </div>
        ) : (
          <div className="space-y-2 max-h-[600px] overflow-y-auto pr-2">
            {filteredLogs.map((item) => (
              <div
                key={item.id}
                className="group flex flex-col md:flex-row md:items-start gap-2.5 p-2 rounded hover:bg-sentinel-900/80 transition-colors border border-transparent hover:border-sentinel-800"
              >
                <span className="text-slate-400 shrink-0 text-[11px]">
                  {item.timestamp}
                </span>
                <span
                  className={`inline-flex items-center px-1.5 py-0.2 rounded border text-[10px] font-bold shrink-0 ${getLevelStyle(
                    item.level
                  )}`}
                >
                  {item.level}
                </span>
                <span className="text-indigo-300 font-semibold shrink-0 text-[11px]">
                  [{item.component}]
                </span>
                <span className="text-slate-200 break-words flex-1">
                  {item.message}
                </span>
                {item.details && (
                  <span className="text-slate-400 text-[10px] bg-sentinel-900 px-2 py-0.5 rounded border border-sentinel-800 shrink-0">
                    {item.details}
                  </span>
                )}
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  );
};

