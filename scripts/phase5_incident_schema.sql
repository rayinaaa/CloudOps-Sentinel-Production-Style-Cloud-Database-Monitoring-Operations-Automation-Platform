-- ==============================================================================
-- CloudOps Sentinel - Phase 5: Incident Management & Escalation Schema
-- Engine: PostgreSQL 16
-- Scope: Incidents table, lifecycle states, audit history & operational indexes
-- ==============================================================================

CREATE EXTENSION IF NOT EXISTS "pgcrypto";

-- Clean teardown if rebuilding
DROP TABLE IF EXISTS incident_history CASCADE;
DROP TABLE IF EXISTS incidents CASCADE;

-- ------------------------------------------------------------------------------
-- 1. INCIDENTS TABLE
-- Tracks operational anomalies, SLA timers, assignees, and resolution notes.
-- ------------------------------------------------------------------------------
CREATE TABLE incidents (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    title VARCHAR(255) NOT NULL,
    description TEXT NULL,
    severity VARCHAR(32) NOT NULL DEFAULT 'MEDIUM',
    status VARCHAR(32) NOT NULL DEFAULT 'OPEN',
    source VARCHAR(64) NOT NULL DEFAULT 'ALERTMANAGER',
    component VARCHAR(64) NOT NULL DEFAULT 'DATABASE',
    target_instance VARCHAR(128) NOT NULL DEFAULT 'primary-postgres',
    fingerprint VARCHAR(128) NULL,
    escalation_level INT NOT NULL DEFAULT 0,
    assigned_to VARCHAR(128) NULL,
    acknowledged_by VARCHAR(128) NULL,
    resolved_by VARCHAR(128) NULL,
    resolution_notes TEXT NULL,
    metadata_json JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    acknowledged_at TIMESTAMPTZ NULL,
    resolved_at TIMESTAMPTZ NULL,
    escalated_at TIMESTAMPTZ NULL,

    -- Integrity Constraints
    CONSTRAINT chk_incidents_severity CHECK (severity IN ('CRITICAL', 'HIGH', 'MEDIUM', 'LOW')),
    CONSTRAINT chk_incidents_status CHECK (status IN ('OPEN', 'ACKNOWLEDGED', 'RESOLVED')),
    CONSTRAINT chk_incidents_source CHECK (source IN ('ALERTMANAGER', 'HEALTH_CHECK_PROBE', 'DISK_MONITOR', 'CONNECTION_MONITOR', 'MANUAL', 'SIMULATION')),
    CONSTRAINT chk_incidents_escalation_level CHECK (escalation_level >= 0 AND escalation_level <= 3)
);

-- Operational Performance Indexes for Incidents
CREATE INDEX idx_incidents_status_severity ON incidents(status, severity);
CREATE INDEX idx_incidents_fingerprint ON incidents(fingerprint) WHERE status != 'RESOLVED';
CREATE INDEX idx_incidents_created_at ON incidents(created_at DESC);
CREATE INDEX idx_incidents_component ON incidents(component);
CREATE INDEX idx_incidents_target_instance ON incidents(target_instance);
CREATE INDEX idx_incidents_escalation ON incidents(status, escalation_level) WHERE status = 'OPEN';

-- ------------------------------------------------------------------------------
-- 2. INCIDENT_HISTORY TABLE
-- Immutable chronological audit log of all status transitions and actions.
-- ------------------------------------------------------------------------------
CREATE TABLE incident_history (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    incident_id UUID NOT NULL REFERENCES incidents(id) ON DELETE CASCADE,
    from_status VARCHAR(32) NULL,
    to_status VARCHAR(32) NOT NULL,
    action VARCHAR(64) NOT NULL,
    actor VARCHAR(128) NOT NULL,
    notes TEXT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    CONSTRAINT chk_history_to_status CHECK (to_status IN ('OPEN', 'ACKNOWLEDGED', 'RESOLVED'))
);

-- Operational Index for Incident History
CREATE INDEX idx_incident_history_incident ON incident_history(incident_id, created_at DESC);

-- ------------------------------------------------------------------------------
-- 3. SYNTHETIC INITIAL INCIDENTS SEED DATA
-- Pre-populates realistic incidents across all severities and statuses.
-- ------------------------------------------------------------------------------
INSERT INTO incidents (
    id, title, description, severity, status, source, component,
    target_instance, fingerprint, escalation_level, assigned_to,
    acknowledged_by, resolved_by, resolution_notes, metadata_json,
    created_at, acknowledged_at, resolved_at
) VALUES
(
    'b0000000-0000-0000-0000-000000000001',
    'PostgreSQL High Connection Pool Saturation',
    'Active connections reached 92% of maximum limit on monitored target database.',
    'CRITICAL',
    'RESOLVED',
    'ALERTMANAGER',
    'DATABASE',
    'monitored-postgres:5432',
    'DatabaseConnectionPoolCritical:monitored-postgres:5432',
    0,
    'sarah.connor@acmecloud.io',
    'sarah.connor@acmecloud.io',
    'sarah.connor@acmecloud.io',
    'Identified and terminated 14 leaked idle-in-transaction connections from analytics batch job.',
    '{"active_connections": 92, "max_connections": 100, "threshold_pct": 90}'::jsonb,
    NOW() - INTERVAL '3 hours',
    NOW() - INTERVAL '2 hours 55 minutes',
    NOW() - INTERVAL '2 hours 30 minutes'
),
(
    'b0000000-0000-0000-0000-000000000002',
    'Database Buffer Cache Hit Ratio Below SLA Threshold',
    'Buffer cache hit ratio degraded to 84.2% over a 15-minute evaluation window.',
    'HIGH',
    'ACKNOWLEDGED',
    'ALERTMANAGER',
    'DATABASE',
    'monitored-postgres:5432',
    'LowBufferCacheHitRatio:monitored-postgres:5432',
    1,
    'john.doe@acmecloud.io',
    'john.doe@acmecloud.io',
    NULL,
    NULL,
    '{"cache_hit_ratio_pct": 84.2, "threshold_pct": 90.0}'::jsonb,
    NOW() - INTERVAL '45 minutes',
    NOW() - INTERVAL '35 minutes',
    NULL
),
(
    'b0000000-0000-0000-0000-000000000003',
    'PostgreSQL Disk Storage Mount Exceeding 75% Warning Threshold',
    'Mount /var/lib/postgresql/data reached 78.4% utilization.',
    'MEDIUM',
    'OPEN',
    'DISK_MONITOR',
    'STORAGE',
    'sentinel-postgres:5432',
    'DiskUsageWarning:sentinel-postgres',
    0,
    NULL,
    NULL,
    NULL,
    NULL,
    '{"mount_used_pct": 78.4, "free_space_gb": 4.2}'::jsonb,
    NOW() - INTERVAL '15 minutes',
    NULL,
    NULL
),
(
    'b0000000-0000-0000-0000-000000000004',
    'Elevated API Latency on /ops/db-summary',
    'FastAPI p95 latency reached 620ms exceeding 500ms operational warning target.',
    'LOW',
    'OPEN',
    'ALERTMANAGER',
    'API',
    'sentinel-backend:8000',
    'HighApiLatencyP95:sentinel-backend',
    0,
    NULL,
    NULL,
    NULL,
    NULL,
    '{"p95_latency_ms": 620, "threshold_ms": 500}'::jsonb,
    NOW() - INTERVAL '5 minutes',
    NULL,
    NULL
);

-- Seed Corresponding Incident History
INSERT INTO incident_history (incident_id, from_status, to_status, action, actor, notes, created_at)
VALUES
(
    'b0000000-0000-0000-0000-000000000001',
    NULL,
    'OPEN',
    'CREATED',
    'alertmanager_webhook',
    'Incident created automatically via Alertmanager webhook for DatabaseConnectionPoolCritical.',
    NOW() - INTERVAL '3 hours'
),
(
    'b0000000-0000-0000-0000-000000000001',
    'OPEN',
    'ACKNOWLEDGED',
    'ACKNOWLEDGED',
    'sarah.connor@acmecloud.io',
    'Acknowledged alert. Investigating active queries in pg_stat_activity.',
    NOW() - INTERVAL '2 hours 55 minutes'
),
(
    'b0000000-0000-0000-0000-000000000001',
    'ACKNOWLEDGED',
    'RESOLVED',
    'RESOLVED',
    'sarah.connor@acmecloud.io',
    'Terminated rogue batch job connections. Connection pool saturation dropped to 8%.',
    NOW() - INTERVAL '2 hours 30 minutes'
),
(
    'b0000000-0000-0000-0000-000000000002',
    NULL,
    'OPEN',
    'CREATED',
    'alertmanager_webhook',
    'Incident created automatically via Alertmanager webhook for LowBufferCacheHitRatio.',
    NOW() - INTERVAL '45 minutes'
),
(
    'b0000000-0000-0000-0000-000000000002',
    'OPEN',
    'ACKNOWLEDGED',
    'ACKNOWLEDGED',
    'john.doe@acmecloud.io',
    'Reviewing missing indexes on table orders.',
    NOW() - INTERVAL '35 minutes'
),
(
    'b0000000-0000-0000-0000-000000000003',
    NULL,
    'OPEN',
    'CREATED',
    'disk_monitor_daemon',
    'Mount utilization warning detected by disk_monitor.sh script.',
    NOW() - INTERVAL '15 minutes'
),
(
    'b0000000-0000-0000-0000-000000000004',
    NULL,
    'OPEN',
    'CREATED',
    'alertmanager_webhook',
    'Incident created automatically via Alertmanager webhook for HighApiLatencyP95.',
    NOW() - INTERVAL '5 minutes'
);
