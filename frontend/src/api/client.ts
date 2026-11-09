// API Client with fallback handling and typed fetchers

import {
  BackupItem,
  DatabaseOperationalSummary,
  Incident,
  IncidentMetrics,
  InfraMetrics,
  OperationalLogItem,
  TenantDetail,
} from "../types";

const API_BASE = ""; // Uses Vite proxy in development or direct host in production

async function request<T>(endpoint: string, options: RequestInit = {}): Promise<T> {
  const url = `${API_BASE}${endpoint}`;
  try {
    const response = await fetch(url, {
      ...options,
      headers: {
        "Content-Type": "application/json",
        Accept: "application/json",
        ...options.headers,
      },
    });

    if (!response.ok) {
      let errorMsg = `HTTP ${response.status}: ${response.statusText}`;
      try {
        const errorJson = await response.json();
        if (errorJson.detail) errorMsg = errorJson.detail;
        else if (errorJson.message) errorMsg = errorJson.message;
      } catch (_) {}
      throw new Error(errorMsg);
    }

    return (await response.json()) as T;
  } catch (err: any) {
    console.error(`API Error on ${endpoint}:`, err);
    throw err;
  }
}

export const api = {
  // 1. Health & Database Operational Summary
  getDatabaseSummary: () =>
    request<DatabaseOperationalSummary>("/api/v1/ops/db-summary"),

  getDatabaseHealth: () =>
    request<{ status: string; latency_ms: number; database: string }>("/api/v1/health/db"),

  // 2. Incident Management
  getIncidents: (status?: string, severity?: string) => {
    const params = new URLSearchParams();
    if (status) params.append("status", status);
    if (severity) params.append("severity", severity);
    const qs = params.toString() ? `?${params.toString()}` : "";
    return request<Incident[]>(`/api/v1/incidents/${qs}`);
  },

  getIncidentDetail: (id: string) =>
    request<Incident>(`/api/v1/incidents/${id}`),

  getIncidentMetrics: () =>
    request<IncidentMetrics>("/api/v1/incidents/metrics/sla"),

  acknowledgeIncident: (id: string, acknowledgedBy: string, notes?: string) =>
    request<Incident>(`/api/v1/incidents/${id}/acknowledge`, {
      method: "POST",
      body: JSON.stringify({
        acknowledged_by: acknowledgedBy,
        notes: notes || "Acknowledged via CloudOps Sentinel Console",
      }),
    }),

  resolveIncident: (id: string, resolvedBy: string, resolutionNotes: string) =>
    request<Incident>(`/api/v1/incidents/${id}/resolve`, {
      method: "POST",
      body: JSON.stringify({
        resolved_by: resolvedBy,
        resolution_notes: resolutionNotes,
      }),
    }),

  triggerEscalationEvaluation: () =>
    request<Incident[]>("/api/v1/incidents/escalate", { method: "POST" }),

  // 3. Multi-Tenant Fleet
  getTenants: () =>
    request<TenantDetail[]>("/api/v1/ops/tenants"),

  // 4. Infrastructure & Telemetry
  getInfraMetrics: () =>
    request<InfraMetrics>("/api/v1/ops/infra"),

  // 5. Backups & Disaster Recovery
  getBackups: () =>
    request<BackupItem[]>("/api/v1/ops/backups"),

  triggerBackup: (databaseName: string = "sentinel_db") =>
    request<BackupItem>(`/api/v1/ops/backups/trigger?database_name=${encodeURIComponent(databaseName)}`, {
      method: "POST",
    }),

  // 6. Operational Logs
  getLogs: (limit: number = 50) =>
    request<OperationalLogItem[]>(`/api/v1/ops/logs?limit=${limit}`),
};

