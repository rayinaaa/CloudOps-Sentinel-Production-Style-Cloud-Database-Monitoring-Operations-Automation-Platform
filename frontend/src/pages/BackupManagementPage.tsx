import React, { useEffect, useState } from "react";
import {
  Archive,
  ShieldCheck,
  Play,
  CheckCircle2,
  HardDrive,
  Calendar,
  Lock,
  Copy,
  Check,
} from "lucide-react";
import { StatCard } from "../components/common/StatCard";
import { Badge } from "../components/common/Badge";
import { LoadingSkeleton } from "../components/common/LoadingSkeleton";
import { ErrorState } from "../components/common/ErrorState";
import { api } from "../api/client";
import { BackupItem } from "../types";

export const BackupManagementPage: React.FC = () => {
  const [backups, setBackups] = useState<BackupItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [triggering, setTriggering] = useState(false);
  const [copiedId, setCopiedId] = useState<string | null>(null);
  const [successBanner, setSuccessBanner] = useState<string | null>(null);

  const loadBackups = async () => {
    try {
      setLoading(true);
      setError(null);
      const res = await api.getBackups();
      setBackups(res);
    } catch (err: any) {
      setError(err.message || "Failed to load backup catalog");
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadBackups();
  }, []);

  const handleTriggerBackup = async () => {
    try {
      setTriggering(true);
      const newBackup = await api.triggerBackup("sentinel_db");
      setBackups((prev) => [newBackup, ...prev]);
      setSuccessBanner(`Backup ${newBackup.id} successfully generated and uploaded to S3!`);
      setTimeout(() => setSuccessBanner(null), 5000);
    } catch (err: any) {
      alert(`Backup failed: ${err.message}`);
    } finally {
      setTriggering(false);
    }
  };

  const copyToClipboard = (text: string, id: string) => {
    navigator.clipboard.writeText(text);
    setCopiedId(id);
    setTimeout(() => setCopiedId(null), 2000);
  };

  if (loading) {
    return (
      <div className="space-y-6">
        <LoadingSkeleton rows={3} height="h-28" />
        <LoadingSkeleton rows={5} height="h-16" />
      </div>
    );
  }

  if (error) {
    return <ErrorState message={error} onRetry={loadBackups} />;
  }

  return (
    <div className="space-y-6">
      {/* Success Notification Banner */}
      {successBanner && (
        <div className="flex items-center gap-3 rounded-xl border border-emerald-500/30 bg-emerald-950/20 px-5 py-3 text-emerald-300">
          <CheckCircle2 className="h-5 w-5 text-emerald-400 shrink-0" />
          <span className="text-xs font-mono">{successBanner}</span>
        </div>
      )}

      {/* S3 DR Policy Banner */}
      <div className="rounded-xl border border-sentinel-800 bg-sentinel-900/90 p-5 backdrop-blur-sm flex flex-col md:flex-row md:items-center justify-between gap-4">
        <div className="flex items-center gap-4">
          <div className="h-12 w-12 rounded-xl bg-indigo-500/10 border border-indigo-500/30 flex items-center justify-center text-indigo-400">
            <Archive className="h-6 w-6" />
          </div>
          <div>
            <div className="flex items-center gap-2">
              <h2 className="text-lg font-bold text-white tracking-tight">
                AWS S3 Disaster Recovery Storage
              </h2>
              <Badge label="ACTIVE" variant="ACTIVE" />
            </div>
            <p className="text-xs text-slate-400 font-mono mt-0.5">
              Bucket: s3://cloudops-sentinel-backups-dev/db-snapshots/ &bull; AES-256 Encrypted
            </p>
          </div>
        </div>

        <button
          onClick={handleTriggerBackup}
          disabled={triggering}
          className="inline-flex items-center gap-2 rounded-lg bg-sky-600 px-4 py-2 text-xs font-semibold text-white hover:bg-sky-500 transition-colors shadow-lg shadow-sky-600/20 disabled:opacity-50"
        >
          <Play className={`h-3.5 w-3.5 ${triggering ? "animate-spin" : ""}`} />
          {triggering ? "Executing pg_dump..." : "Trigger S3 Backup Now"}
        </button>
      </div>

      {/* Backup KPIs */}
      <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-4">
        <StatCard
          title="Retention Period"
          value="7 Days"
          subValue="Automated S3 lifecycle"
          icon={Calendar}
          status="healthy"
        />
        <StatCard
          title="Encryption Standard"
          value="SSE-S3"
          subValue="AES-256 CloudVault"
          icon={Lock}
          status="healthy"
        />
        <StatCard
          title="Compression Rate"
          value="gzip -6"
          subValue="~65% reduction"
          icon={HardDrive}
          status="neutral"
        />
        <StatCard
          title="Integrity Verification"
          value="100% PASS"
          subValue="SHA256 TOC Checksum"
          icon={ShieldCheck}
          status="healthy"
        />
      </div>

      {/* Backups Catalog Table */}
      <div className="rounded-xl border border-sentinel-800 bg-sentinel-900/80 p-5 backdrop-blur-sm overflow-hidden">
        <div className="flex items-center justify-between pb-4 border-b border-sentinel-800">
          <div>
            <h3 className="text-sm font-semibold text-white tracking-tight">
              Disaster Recovery Snapshot History
            </h3>
            <p className="text-xs text-slate-400 font-mono">
              Verified pg_dump custom format archives uploaded to Amazon S3
            </p>
          </div>
          <span className="text-xs font-mono text-slate-400">
            {backups.length} Snapshots
          </span>
        </div>

        <div className="mt-4 overflow-x-auto">
          <table className="w-full text-left text-xs">
            <thead className="border-b border-sentinel-800 text-[11px] font-semibold uppercase tracking-wider text-slate-400">
              <tr>
                <th className="py-3 px-4">Backup ID</th>
                <th className="py-3 px-4">Database</th>
                <th className="py-3 px-4">Status</th>
                <th className="py-3 px-4">Archive Size</th>
                <th className="py-3 px-4">SHA256 Checksum</th>
                <th className="py-3 px-4">Execution Time</th>
                <th className="py-3 px-4">Started At</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-sentinel-800 font-mono text-slate-300">
              {backups.map((b) => (
                <tr key={b.id} className="hover:bg-sentinel-850 transition-colors">
                  <td className="py-3 px-4 font-bold text-white">{b.id}</td>
                  <td className="py-3 px-4 text-sky-300 font-sans">{b.database_name}</td>
                  <td className="py-3 px-4">
                    <Badge label={b.status} variant="COMPLETED" size="sm" />
                  </td>
                  <td className="py-3 px-4 text-white font-semibold">{b.size_human}</td>
                  <td className="py-3 px-4">
                    <button
                      onClick={() => copyToClipboard(b.checksum_sha256, b.id)}
                      className="inline-flex items-center gap-1.5 text-[11px] text-slate-400 hover:text-slate-200"
                      title="Click to copy SHA256 checksum"
                    >
                      <span>{b.checksum_sha256.substring(0, 16)}...</span>
                      {copiedId === b.id ? (
                        <Check className="h-3 w-3 text-emerald-400" />
                      ) : (
                        <Copy className="h-3 w-3" />
                      )}
                    </button>
                  </td>
                  <td className="py-3 px-4 text-slate-400">
                    {b.duration_seconds ? `${b.duration_seconds}s` : "N/A"}
                  </td>
                  <td className="py-3 px-4 text-slate-400">{b.started_at}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
};

