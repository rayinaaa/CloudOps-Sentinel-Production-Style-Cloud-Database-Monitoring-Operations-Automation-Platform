import React, { useEffect, useState } from "react";
import {
  AlertOctagon,
  Clock,
  CheckCircle2,
  TrendingUp,
  ShieldAlert,
  Search,
  Filter,
  Eye,
  CheckSquare,
  AlertTriangle,
  History,
} from "lucide-react";
import { StatCard } from "../components/common/StatCard";
import { Badge } from "../components/common/Badge";
import { Modal } from "../components/common/Modal";
import { LoadingSkeleton } from "../components/common/LoadingSkeleton";
import { ErrorState } from "../components/common/ErrorState";
import { EmptyState } from "../components/common/EmptyState";
import { api } from "../api/client";
import { Incident, IncidentMetrics } from "../types";

export const IncidentManagementPage: React.FC = () => {
  const [incidents, setIncidents] = useState<Incident[]>([]);
  const [metrics, setMetrics] = useState<IncidentMetrics | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  // Filters
  const [statusFilter, setStatusFilter] = useState<string>("ALL");
  const [severityFilter, setSeverityFilter] = useState<string>("ALL");
  const [searchQuery, setSearchQuery] = useState<string>("");

  // Modals state
  const [selectedIncident, setSelectedIncident] = useState<Incident | null>(null);
  const [isAckModalOpen, setIsAckModalOpen] = useState(false);
  const [isResolveModalOpen, setIsResolveModalOpen] = useState(false);
  const [isHistoryModalOpen, setIsHistoryModalOpen] = useState(false);

  // Form states
  const [engineerName, setEngineerName] = useState("sarah.connor@acmecloud.io");
  const [notes, setNotes] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const [actionSuccess, setActionSuccess] = useState<string | null>(null);

  const loadData = async () => {
    try {
      setLoading(true);
      setError(null);
      const [incRes, metRes] = await Promise.all([
        api.getIncidents(
          statusFilter === "ALL" ? undefined : statusFilter,
          severityFilter === "ALL" ? undefined : severityFilter
        ),
        api.getIncidentMetrics(),
      ]);
      setIncidents(incRes);
      setMetrics(metRes);
    } catch (err: any) {
      setError(err.message || "Failed to load incidents");
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadData();
  }, [statusFilter, severityFilter]);

  const handleAcknowledge = async () => {
    if (!selectedIncident) return;
    try {
      setSubmitting(true);
      await api.acknowledgeIncident(selectedIncident.id, engineerName, notes);
      setIsAckModalOpen(false);
      setNotes("");
      setActionSuccess(`Incident ${selectedIncident.title} successfully acknowledged.`);
      setTimeout(() => setActionSuccess(null), 4000);
      loadData();
    } catch (err: any) {
      alert(`Acknowledgement failed: ${err.message}`);
    } finally {
      setSubmitting(false);
    }
  };

  const handleResolve = async () => {
    if (!selectedIncident) return;
    if (!notes.trim()) {
      alert("Resolution notes are required for post-mortem compliance.");
      return;
    }
    try {
      setSubmitting(true);
      await api.resolveIncident(selectedIncident.id, engineerName, notes);
      setIsResolveModalOpen(false);
      setNotes("");
      setActionSuccess(`Incident ${selectedIncident.title} resolved.`);
      setTimeout(() => setActionSuccess(null), 4000);
      loadData();
    } catch (err: any) {
      alert(`Resolution failed: ${err.message}`);
    } finally {
      setSubmitting(false);
    }
  };

  const handleOpenHistory = async (incident: Incident) => {
    try {
      const detailed = await api.getIncidentDetail(incident.id);
      setSelectedIncident(detailed);
      setIsHistoryModalOpen(true);
    } catch (err: any) {
      alert(`Failed to load incident history: ${err.message}`);
    }
  };

  const handleTriggerEscalation = async () => {
    try {
      const escalated = await api.triggerEscalationEvaluation();
      alert(`Evaluated SLA thresholds across all open incidents. Escalated count: ${escalated.length}`);
      loadData();
    } catch (err: any) {
      alert(`Escalation sweep error: ${err.message}`);
    }
  };

  const filteredIncidents = incidents.filter((inc) => {
    if (!searchQuery) return true;
    const q = searchQuery.toLowerCase();
    return (
      inc.title.toLowerCase().includes(q) ||
      inc.component.toLowerCase().includes(q) ||
      inc.target_instance.toLowerCase().includes(q)
    );
  });

  return (
    <div className="space-y-6">
      {/* Toast Alert */}
      {actionSuccess && (
        <div className="flex items-center gap-3 rounded-xl border border-emerald-500/30 bg-emerald-950/20 px-5 py-3 text-emerald-300">
          <CheckCircle2 className="h-5 w-5 text-emerald-400 shrink-0" />
          <span className="text-xs font-mono">{actionSuccess}</span>
        </div>
      )}

      {/* SRE SLA Performance Metrics */}
      <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-4">
        <StatCard
          title="Mean Time To Ack (MTTA)"
          value={metrics?.mean_time_to_acknowledge_human || "7m 30s"}
          subValue="Target: &le; 15 mins"
          icon={Clock}
          status="healthy"
          trend={{ value: "SLA PASS", isPositive: true }}
        />
        <StatCard
          title="Mean Time To Resolve (MTTR)"
          value={metrics?.mean_time_to_resolve_human || "30m 0s"}
          subValue="Target: &le; 1 hour"
          icon={TrendingUp}
          status="healthy"
          trend={{ value: "SLA PASS", isPositive: true }}
        />
        <StatCard
          title="SLA Compliance Rate"
          value={metrics ? `${metrics.sla_compliance_rate_pct}%` : "100%"}
          subValue="SRE Performance Target"
          icon={ShieldAlert}
          status={metrics && metrics.sla_compliance_rate_pct < 95 ? "warning" : "healthy"}
        />
        <StatCard
          title="Active Escalations"
          value={metrics?.active_escalations_count || 0}
          subValue="Tiered paging"
          icon={AlertOctagon}
          status={metrics && metrics.active_escalations_count > 0 ? "warning" : "healthy"}
        />
      </div>

      {/* Action Bar & Filters */}
      <div className="rounded-xl border border-sentinel-800 bg-sentinel-900/80 p-5 backdrop-blur-sm space-y-4">
        <div className="flex flex-col md:flex-row md:items-center justify-between gap-4">
          {/* Search Input */}
          <div className="relative flex-1 max-w-md">
            <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-slate-400" />
            <input
              type="text"
              placeholder="Search by title, component, or target host..."
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              className="w-full rounded-lg border border-sentinel-800 bg-sentinel-950 py-2 pl-9 pr-4 text-xs text-white placeholder-slate-500 focus:border-sky-500 focus:outline-none font-mono"
            />
          </div>

          {/* Trigger SLA Escalation Sweep */}
          <button
            onClick={handleTriggerEscalation}
            className="inline-flex items-center gap-1.5 rounded-lg border border-amber-500/30 bg-amber-500/10 px-3.5 py-2 text-xs font-medium text-amber-300 hover:bg-amber-500/20 transition-colors"
          >
            <AlertTriangle className="h-3.5 w-3.5" />
            Evaluate SLA Escalation Sweep
          </button>
        </div>

        {/* Filter Pills */}
        <div className="flex flex-wrap items-center gap-4 pt-2 border-t border-sentinel-800 text-xs">
          {/* Status Filter */}
          <div className="flex items-center gap-1.5">
            <span className="text-slate-400 font-medium">Status:</span>
            {["ALL", "OPEN", "ACKNOWLEDGED", "RESOLVED"].map((st) => (
              <button
                key={st}
                onClick={() => setStatusFilter(st)}
                className={`rounded-md px-2.5 py-1 text-[11px] font-mono transition-colors ${
                  statusFilter === st
                    ? "bg-sky-500/20 text-sky-300 border border-sky-500/40"
                    : "text-slate-400 hover:text-white"
                }`}
              >
                {st}
              </button>
            ))}
          </div>

          {/* Severity Filter */}
          <div className="flex items-center gap-1.5 ml-auto">
            <span className="text-slate-400 font-medium">Severity:</span>
            {["ALL", "CRITICAL", "HIGH", "MEDIUM", "LOW"].map((sev) => (
              <button
                key={sev}
                onClick={() => setSeverityFilter(sev)}
                className={`rounded-md px-2.5 py-1 text-[11px] font-mono transition-colors ${
                  severityFilter === sev
                    ? "bg-sky-500/20 text-sky-300 border border-sky-500/40"
                    : "text-slate-400 hover:text-white"
                }`}
              >
                {sev}
              </button>
            ))}
          </div>
        </div>
      </div>

      {/* Incidents Data Table */}
      <div className="rounded-xl border border-sentinel-800 bg-sentinel-900/80 backdrop-blur-sm overflow-hidden">
        {loading ? (
          <div className="p-6">
            <LoadingSkeleton rows={5} height="h-14" />
          </div>
        ) : filteredIncidents.length === 0 ? (
          <div className="p-12">
            <EmptyState
              title="No incidents found"
              description="No operational incidents match your selected filters."
            />
          </div>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-left text-xs">
              <thead className="border-b border-sentinel-800 text-[11px] font-semibold uppercase tracking-wider text-slate-400 bg-sentinel-950/60">
                <tr>
                  <th className="py-3 px-4">Severity</th>
                  <th className="py-3 px-4">Title & Context</th>
                  <th className="py-3 px-4">Status</th>
                  <th className="py-3 px-4">Component</th>
                  <th className="py-3 px-4">Target Instance</th>
                  <th className="py-3 px-4">Timers</th>
                  <th className="py-3 px-4 text-right">Actions</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-sentinel-800 font-mono text-slate-300">
                {filteredIncidents.map((inc) => (
                  <tr key={inc.id} className="hover:bg-sentinel-850 transition-colors">
                    <td className="py-3.5 px-4">
                      <Badge label={inc.severity} variant={inc.severity} size="sm" />
                    </td>
                    <td className="py-3.5 px-4 font-sans max-w-md">
                      <div className="font-semibold text-white text-xs">
                        {inc.title}
                      </div>
                      <div className="text-[11px] text-slate-400 line-clamp-1 mt-0.5">
                        {inc.description || "Anomaly detected via automated monitoring."}
                      </div>
                    </td>
                    <td className="py-3.5 px-4">
                      <Badge label={inc.status} variant={inc.status} size="sm" />
                    </td>
                    <td className="py-3.5 px-4 text-slate-300">{inc.component}</td>
                    <td className="py-3.5 px-4 text-sky-400">{inc.target_instance}</td>
                    <td className="py-3.5 px-4 text-[11px] text-slate-400">
                      {inc.time_to_resolve_seconds ? (
                        <span className="text-emerald-400 font-bold">
                          MTTR: {inc.time_to_resolve_seconds}s
                        </span>
                      ) : inc.time_to_acknowledge_seconds ? (
                        <span className="text-amber-400">
                          Ack: {inc.time_to_acknowledge_seconds}s
                        </span>
                      ) : (
                        <span className="text-rose-400 animate-pulse">
                          Awaiting Ack
                        </span>
                      )}
                    </td>
                    <td className="py-3.5 px-4 text-right space-x-2">
                      {inc.status === "OPEN" && (
                        <button
                          onClick={() => {
                            setSelectedIncident(inc);
                            setIsAckModalOpen(true);
                          }}
                          className="rounded-md border border-amber-500/30 bg-amber-500/15 px-2.5 py-1 text-[11px] font-sans font-medium text-amber-300 hover:bg-amber-500/25 transition-colors"
                        >
                          Ack
                        </button>
                      )}
                      {inc.status !== "RESOLVED" && (
                        <button
                          onClick={() => {
                            setSelectedIncident(inc);
                            setIsResolveModalOpen(true);
                          }}
                          className="rounded-md border border-emerald-500/30 bg-emerald-500/15 px-2.5 py-1 text-[11px] font-sans font-medium text-emerald-300 hover:bg-emerald-500/25 transition-colors"
                        >
                          Resolve
                        </button>
                      )}
                      <button
                        onClick={() => handleOpenHistory(inc)}
                        className="rounded-md border border-sentinel-800 bg-sentinel-900 px-2 py-1 text-[11px] font-sans text-slate-400 hover:text-white transition-colors"
                        title="Audit History"
                      >
                        <History className="h-3 w-3 inline" />
                      </button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>

      {/* Acknowledge Modal */}
      <Modal
        isOpen={isAckModalOpen}
        onClose={() => setIsAckModalOpen(false)}
        title="Acknowledge Operational Incident"
        subtitle={selectedIncident?.title}
      >
        <div className="space-y-4">
          <div>
            <label className="text-xs text-slate-400 block mb-1">On-Call Engineer Identity</label>
            <input
              type="text"
              value={engineerName}
              onChange={(e) => setEngineerName(e.target.value)}
              className="w-full rounded-lg border border-sentinel-800 bg-sentinel-950 p-2.5 text-xs text-white font-mono"
            />
          </div>
          <div>
            <label className="text-xs text-slate-400 block mb-1">Triage Investigation Notes</label>
            <textarea
              rows={3}
              value={notes}
              onChange={(e) => setNotes(e.target.value)}
              placeholder="Acknowledged page. Inspecting active database queries and socket refusal..."
              className="w-full rounded-lg border border-sentinel-800 bg-sentinel-950 p-2.5 text-xs text-white font-sans placeholder-slate-500"
            />
          </div>
          <div className="flex justify-end gap-3 pt-3 border-t border-sentinel-800">
            <button
              onClick={() => setIsAckModalOpen(false)}
              className="px-3 py-1.5 rounded-lg border border-sentinel-800 text-xs text-slate-400 hover:text-white"
            >
              Cancel
            </button>
            <button
              onClick={handleAcknowledge}
              disabled={submitting}
              className="px-4 py-1.5 rounded-lg bg-amber-600 text-xs font-semibold text-white hover:bg-amber-500"
            >
              {submitting ? "Acknowledging..." : "Confirm Acknowledge"}
            </button>
          </div>
        </div>
      </Modal>

      {/* Resolve Modal */}
      <Modal
        isOpen={isResolveModalOpen}
        onClose={() => setIsResolveModalOpen(false)}
        title="Resolve Incident & Record Post-Mortem"
        subtitle={selectedIncident?.title}
      >
        <div className="space-y-4">
          <div>
            <label className="text-xs text-slate-400 block mb-1">Resolved By</label>
            <input
              type="text"
              value={engineerName}
              onChange={(e) => setEngineerName(e.target.value)}
              className="w-full rounded-lg border border-sentinel-800 bg-sentinel-950 p-2.5 text-xs text-white font-mono"
            />
          </div>
          <div>
            <label className="text-xs text-slate-400 block mb-1">
              Remediation Notes & Root Cause Analysis <span className="text-red-400">*</span>
            </label>
            <textarea
              rows={4}
              value={notes}
              onChange={(e) => setNotes(e.target.value)}
              placeholder="Identified leaked connections in batch worker; terminated idle transactions. Connection pool saturation dropped back to 8%."
              className="w-full rounded-lg border border-sentinel-800 bg-sentinel-950 p-2.5 text-xs text-white font-sans placeholder-slate-500"
            />
          </div>
          <div className="flex justify-end gap-3 pt-3 border-t border-sentinel-800">
            <button
              onClick={() => setIsResolveModalOpen(false)}
              className="px-3 py-1.5 rounded-lg border border-sentinel-800 text-xs text-slate-400 hover:text-white"
            >
              Cancel
            </button>
            <button
              onClick={handleResolve}
              disabled={submitting}
              className="px-4 py-1.5 rounded-lg bg-emerald-600 text-xs font-semibold text-white hover:bg-emerald-500"
            >
              {submitting ? "Resolving..." : "Complete Resolution"}
            </button>
          </div>
        </div>
      </Modal>

      {/* Audit History Modal */}
      <Modal
        isOpen={isHistoryModalOpen}
        onClose={() => setIsHistoryModalOpen(false)}
        title="Incident Audit Trail & History"
        subtitle={selectedIncident?.id}
        maxWidth="lg"
      >
        <div className="space-y-4">
          <div className="flex justify-between items-center bg-sentinel-850 p-3 rounded-lg border border-sentinel-800">
            <div>
              <span className="text-xs text-slate-400 block">Incident Title</span>
              <span className="text-xs font-bold text-white">{selectedIncident?.title}</span>
            </div>
            <Badge label={selectedIncident?.severity || "MEDIUM"} variant={selectedIncident?.severity} />
          </div>

          <div className="relative pl-6 space-y-6 before:absolute before:left-2 before:top-2 before:bottom-2 before:w-0.5 before:bg-sentinel-800">
            {selectedIncident?.history?.map((h) => (
              <div key={h.id} className="relative">
                <div className="absolute -left-6 top-0.5 h-3 w-3 rounded-full bg-sky-500 border-2 border-sentinel-900" />
                <div className="flex items-center justify-between">
                  <span className="text-xs font-mono font-bold text-sky-400">{h.action}</span>
                  <span className="text-[10px] font-mono text-slate-400">{h.created_at}</span>
                </div>
                <div className="text-[11px] text-slate-300 font-mono mt-0.5">
                  Actor: <span className="text-indigo-300">{h.actor}</span> &bull; State:{" "}
                  <span className="text-emerald-300">{h.to_status}</span>
                </div>
                {h.notes && (
                  <p className="mt-1 text-xs text-slate-400 bg-sentinel-850 p-2 rounded border border-sentinel-800 font-sans">
                    {h.notes}
                  </p>
                )}
              </div>
            ))}
          </div>
        </div>
      </Modal>
    </div>
  );
};

