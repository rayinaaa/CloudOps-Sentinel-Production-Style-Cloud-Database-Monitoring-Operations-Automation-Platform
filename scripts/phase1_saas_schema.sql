-- ==============================================================================
-- CloudOps Sentinel - Phase 1: Multi-Tenant SaaS Database Foundation
-- Engine: PostgreSQL 16
-- Scope: Multi-tenant tenant & user management, constraints, indexes & seed data
-- ==============================================================================

-- 1. Ensure extensions for cryptographic UUID generation
CREATE EXTENSION IF NOT EXISTS "pgcrypto";

-- Clean teardown if rebuilding schema
DROP TABLE IF EXISTS app_users CASCADE;
DROP TABLE IF EXISTS tenants CASCADE;

-- ------------------------------------------------------------------------------
-- 2. TENANTS TABLE
-- Represents isolated customer organizations subscribing to the SaaS platform.
-- ------------------------------------------------------------------------------
CREATE TABLE tenants (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name VARCHAR(128) NOT NULL,
    slug VARCHAR(64) NOT NULL,
    plan VARCHAR(32) NOT NULL DEFAULT 'FREE',
    status VARCHAR(32) NOT NULL DEFAULT 'ACTIVE',
    max_users INT NOT NULL DEFAULT 5,
    max_storage_bytes BIGINT NOT NULL DEFAULT 1073741824, -- 1 GiB default
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    -- Integrity Constraints
    CONSTRAINT uq_tenants_slug UNIQUE (slug),
    CONSTRAINT chk_tenants_slug_format CHECK (slug ~* '^[a-z0-9-]+$'),
    CONSTRAINT chk_tenants_plan CHECK (plan IN ('FREE', 'STARTER', 'PRO', 'ENTERPRISE')),
    CONSTRAINT chk_tenants_status CHECK (status IN ('PENDING', 'ACTIVE', 'SUSPENDED', 'ARCHIVED')),
    CONSTRAINT chk_tenants_max_users CHECK (max_users > 0),
    CONSTRAINT chk_tenants_storage CHECK (max_storage_bytes >= 0)
);

-- Performance & Operational Indexes on tenants
CREATE INDEX idx_tenants_status ON tenants(status);
CREATE INDEX idx_tenants_plan ON tenants(plan);
CREATE INDEX idx_tenants_created_at ON tenants(created_at DESC);

-- ------------------------------------------------------------------------------
-- 3. APP_USERS TABLE
-- Users belonging to specific tenants with role-based access control.
-- ------------------------------------------------------------------------------
CREATE TABLE app_users (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id UUID NOT NULL,
    email VARCHAR(255) NOT NULL,
    full_name VARCHAR(128) NOT NULL,
    role VARCHAR(32) NOT NULL DEFAULT 'MEMBER',
    is_active BOOLEAN NOT NULL DEFAULT TRUE,
    last_login_at TIMESTAMPTZ NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    -- Relational Integrity & Business Constraints
    CONSTRAINT fk_app_users_tenant FOREIGN KEY (tenant_id) 
        REFERENCES tenants(id) ON DELETE CASCADE,
    CONSTRAINT uq_tenant_user_email UNIQUE (tenant_id, email),
    CONSTRAINT chk_app_users_role CHECK (role IN ('OWNER', 'ADMIN', 'MEMBER', 'VIEWER')),
    CONSTRAINT chk_app_users_email_format CHECK (
        email ~* '^[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}$'
    )
);

-- Performance & Multi-Tenant Query Indexes on app_users
-- Crucial: Foreign key index prevents sequential table scan on joins and cascades
CREATE INDEX idx_app_users_tenant_id ON app_users(tenant_id);
CREATE INDEX idx_app_users_email ON app_users(email);
CREATE INDEX idx_app_users_tenant_role ON app_users(tenant_id, role);
-- Partial index: Optimizes seat allocation queries for active accounts only
CREATE INDEX idx_app_users_active_tenant ON app_users(tenant_id) WHERE is_active = TRUE;

-- ------------------------------------------------------------------------------
-- 4. SYNTHETIC SEED DATA
-- Generates realistic multi-tenant data covering all tiers, statuses, and roles.
-- ------------------------------------------------------------------------------

-- Insert Diverse Tenants
INSERT INTO tenants (id, name, slug, plan, status, max_users, max_storage_bytes, created_at)
VALUES
    ('a0000000-0000-0000-0000-000000000001', 'Acme Cloud Technologies', 'acme-cloud', 'ENTERPRISE', 'ACTIVE', 100, 107374182400, NOW() - INTERVAL '120 days'),
    ('a0000000-0000-0000-0000-000000000002', 'Nova FinTech Group', 'nova-fintech', 'ENTERPRISE', 'ACTIVE', 50, 53687091200, NOW() - INTERVAL '90 days'),
    ('a0000000-0000-0000-0000-000000000003', 'Quantum Retail Solutions', 'quantum-retail', 'PRO', 'ACTIVE', 25, 21474836480, NOW() - INTERVAL '60 days'),
    ('a0000000-0000-0000-0000-000000000004', 'Hyperion Health Labs', 'hyperion-health', 'PRO', 'SUSPENDED', 20, 21474836480, NOW() - INTERVAL '45 days'),
    ('a0000000-0000-0000-0000-000000000005', 'Apex Robotics', 'apex-robotics', 'STARTER', 'ACTIVE', 10, 5368709120, NOW() - INTERVAL '30 days'),
    ('a0000000-0000-0000-0000-000000000006', 'Cobalt Logistics', 'cobalt-logistics', 'STARTER', 'SUSPENDED', 10, 5368709120, NOW() - INTERVAL '20 days'),
    ('a0000000-0000-0000-0000-000000000007', 'DevPulse Analytics', 'devpulse', 'FREE', 'ACTIVE', 5, 1073741824, NOW() - INTERVAL '10 days'),
    ('a0000000-0000-0000-0000-000000000008', 'ZeroLag Gaming Studios', 'zerolag', 'FREE', 'PENDING', 5, 1073741824, NOW() - INTERVAL '2 days');

-- Insert Users for Acme Cloud Technologies (Tenant 1 - Active Enterprise)
INSERT INTO app_users (tenant_id, email, full_name, role, is_active, last_login_at, created_at)
VALUES
    ('a0000000-0000-0000-0000-000000000001', 'sarah.connor@acmecloud.io', 'Sarah Connor', 'OWNER', TRUE, NOW() - INTERVAL '2 hours', NOW() - INTERVAL '120 days'),
    ('a0000000-0000-0000-0000-000000000001', 'john.doe@acmecloud.io', 'John Doe', 'ADMIN', TRUE, NOW() - INTERVAL '5 hours', NOW() - INTERVAL '115 days'),
    ('a0000000-0000-0000-0000-000000000001', 'elena.rostova@acmecloud.io', 'Elena Rostova', 'MEMBER', TRUE, NOW() - INTERVAL '1 day', NOW() - INTERVAL '90 days'),
    ('a0000000-0000-0000-0000-000000000001', 'marcus.vance@acmecloud.io', 'Marcus Vance', 'MEMBER', TRUE, NOW() - INTERVAL '3 days', NOW() - INTERVAL '60 days'),
    ('a0000000-0000-0000-0000-000000000001', 'auditor@acmecloud.io', 'External Auditor', 'VIEWER', FALSE, NOW() - INTERVAL '30 days', NOW() - INTERVAL '40 days');

-- Insert Users for Nova FinTech Group (Tenant 2 - Active Enterprise)
INSERT INTO app_users (tenant_id, email, full_name, role, is_active, last_login_at, created_at)
VALUES
    ('a0000000-0000-0000-0000-000000000002', 'alex.chen@novafintech.com', 'Alex Chen', 'OWNER', TRUE, NOW() - INTERVAL '1 hour', NOW() - INTERVAL '90 days'),
    ('a0000000-0000-0000-0000-000000000002', 'priya.sharma@novafintech.com', 'Priya Sharma', 'ADMIN', TRUE, NOW() - INTERVAL '4 hours', NOW() - INTERVAL '85 days'),
    ('a0000000-0000-0000-0000-000000000002', 'david.kim@novafintech.com', 'David Kim', 'MEMBER', TRUE, NOW() - INTERVAL '8 hours', NOW() - INTERVAL '70 days');

-- Insert Users for Quantum Retail (Tenant 3 - Active Pro)
INSERT INTO app_users (tenant_id, email, full_name, role, is_active, last_login_at, created_at)
VALUES
    ('a0000000-0000-0000-0000-000000000003', 'rachel.green@quantumretail.com', 'Rachel Green', 'OWNER', TRUE, NOW() - INTERVAL '12 hours', NOW() - INTERVAL '60 days'),
    ('a0000000-0000-0000-0000-000000000003', 'ross.geller@quantumretail.com', 'Ross Geller', 'MEMBER', TRUE, NOW() - INTERVAL '1 day', NOW() - INTERVAL '50 days');

-- Insert Users for Hyperion Health (Tenant 4 - Suspended Pro)
INSERT INTO app_users (tenant_id, email, full_name, role, is_active, last_login_at, created_at)
VALUES
    ('a0000000-0000-0000-0000-000000000004', 'dr.house@hyperionhealth.org', 'Gregory House', 'OWNER', FALSE, NOW() - INTERVAL '40 days', NOW() - INTERVAL '45 days'),
    ('a0000000-0000-0000-0000-000000000004', 'dr.cameron@hyperionhealth.org', 'Allison Cameron', 'ADMIN', FALSE, NOW() - INTERVAL '42 days', NOW() - INTERVAL '44 days');

-- Insert Users for Apex Robotics (Tenant 5 - Active Starter)
INSERT INTO app_users (tenant_id, email, full_name, role, is_active, last_login_at, created_at)
VALUES
    ('a0000000-0000-0000-0000-000000000005', 'miles.dyson@apexrobotics.ai', 'Miles Dyson', 'OWNER', TRUE, NOW() - INTERVAL '30 minutes', NOW() - INTERVAL '30 days'),
    ('a0000000-0000-0000-0000-000000000005', 't800.admin@apexrobotics.ai', 'Model 101', 'ADMIN', TRUE, NOW() - INTERVAL '10 minutes', NOW() - INTERVAL '28 days');

-- Insert Users for Cobalt Logistics (Tenant 6 - Suspended Starter)
INSERT INTO app_users (tenant_id, email, full_name, role, is_active, last_login_at, created_at)
VALUES
    ('a0000000-0000-0000-0000-000000000006', 'dispatch@cobaltlogistics.net', 'Dispatcher Dan', 'OWNER', FALSE, NOW() - INTERVAL '15 days', NOW() - INTERVAL '20 days');

-- Insert Users for DevPulse Analytics (Tenant 7 - Active Free)
INSERT INTO app_users (tenant_id, email, full_name, role, is_active, last_login_at, created_at)
VALUES
    ('a0000000-0000-0000-0000-000000000007', 'dev.solo@devpulse.dev', 'Solo Developer', 'OWNER', TRUE, NOW() - INTERVAL '6 hours', NOW() - INTERVAL '10 days');

-- Insert Users for ZeroLag Gaming (Tenant 8 - Pending Free)
INSERT INTO app_users (tenant_id, email, full_name, role, is_active, last_login_at, created_at)
VALUES
    ('a0000000-0000-0000-0000-000000000008', 'lead.streamer@zerolag.gg', 'Streamer Alpha', 'OWNER', TRUE, NULL, NOW() - INTERVAL '2 days');

