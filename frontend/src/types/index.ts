// TypeScript types for CloudOps Sentinel

export interface ConnectionMetrics {
  active_connections: number;
  idle_connections: number;
  idle_in_transaction: number;
  total_connections: number;
  max_connections: number;
  usable_connections_limit: number;
  pool_saturation_pct: number;
  connection_status: "HEALTHY" | "WARNING" | "CRITICAL";
}

export interface TableStorageMetric {
  table_name: string;
  approximate_row_count: number | null;
  table_data_size: string;
  index_size: string;
  total_disk_size: string;
  pct_of_public_schema: number | null;
}

export interface StorageMetrics {
  total_database_size_bytes: number;
  total_database_size_human: string;
  tables: TableStorageMetric[];
}

export interface TenancySummary {
  total_tenants: number;
  active_tenants: number;
  suspended_tenants: number;
  total_users: number;
}

export interface DatabaseOperationalSummary {
  database_name: string;
  server_version: string;
  connection_metrics: ConnectionMetrics;
  storage_metrics: StorageMetrics;
  tenancy_summary: TenancySummary;
  timestamp: string;
}

export interface IncidentHistoryItem {
  id: string;
  incident_id: string;
  from_status: string | null;
  to_status: string;
  action: string;
  actor: string;
  notes: string | null;
  created_at: string;
}

export interface Incident {
  id: string;
  title: string;
  description: string | null;
  severity: "CRITICAL" | "HIGH" | "MEDIUM" | "LOW";
  status: "OPEN" | "ACKNOWLEDGED" | "RESOLVED";
  source: string;
  component: string;
  target_instance: string;
  fingerprint: string | null;
  escalation_level: number;
  assigned_to: string | null;
  acknowledged_by: string | null;
  resolved_by: string | null;
  resolution_notes: string | null;
  metadata_json: Record<string, any>;
  created_at: string;
  updated_at: string;
  acknowledged_at: string | null;
  resolved_at: string | null;
  escalated_at: string | null;
  time_to_acknowledge_seconds: number | null;
  time_to_resolve_seconds: number | null;
  history?: IncidentHistoryItem[];
}

export interface IncidentMetrics {
  total_incidents: number;
  open_incidents: number;
  acknowledged_incidents: number;
  resolved_incidents: number;
  by_severity: Record<string, number>;
  by_status: Record<string, number>;
  mean_time_to_acknowledge_seconds: number | null;
  mean_time_to_resolve_seconds: number | null;
  mean_time_to_acknowledge_human: string;
  mean_time_to_resolve_human: string;
  sla_compliance_rate_pct: number;
  active_escalations_count: number;
}

export interface TenantDetail {
  id: string;
  name: string;
  slug: string;
  plan: "ENTERPRISE" | "PRO" | "STARTER" | "FREE";
  status: "ACTIVE" | "SUSPENDED" | "PENDING" | "ARCHIVED";
  max_users: number;
  max_storage_bytes: number;
  current_users: number;
  created_at: string;
}

export interface InfraServiceStatus {
  name: string;
  component: string;
  status: "HEALTHY" | "DEGRADED" | "DOWN";
  port: number;
  latency_ms?: number;
}

export interface InfraMetrics {
  process_cpu_pct: number;
  memory_rss_bytes: number;
  memory_rss_human: string;
  memory_vms_bytes: number;
  memory_vms_human: string;
  open_file_descriptors: number;
  uptime_seconds: number;
  python_version: string;
  services: InfraServiceStatus[];
  timestamp: string;
}

export interface BackupItem {
  id: string;
  task_id: string;
  database_name: string;
  task_type: string;
  status: "COMPLETED" | "RUNNING" | "FAILED";
  size_bytes: number;
  size_human: string;
  s3_url: string;
  checksum_sha256: string;
  started_at: string;
  completed_at: string | null;
  duration_seconds: number | null;
}

export interface OperationalLogItem {
  id: string;
  timestamp: string;
  level: "INFO" | "WARN" | "ERROR";
  component: string;
  message: string;
  details: string | null;
}

export type PageId =
  | "overview"
  | "database"
  | "infrastructure"
  | "backups"
  | "incidents"
  | "tenants"
  | "logs";

