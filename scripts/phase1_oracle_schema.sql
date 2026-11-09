-- ==============================================================================
-- CloudOps Sentinel - Oracle Database 23ai Multi-Tenant SaaS Schema Foundation
-- Engine: Oracle Database 23ai Free / Enterprise / Autonomous
-- Scope: Multi-tenant organization & user management, constraints & seed data
-- ==============================================================================

-- ------------------------------------------------------------------------------
-- 1. TENANTS TABLE
-- Represents isolated customer organizations subscribing to the SaaS platform.
-- ------------------------------------------------------------------------------
CREATE TABLE tenants (
    id VARCHAR2(36) DEFAULT LOWER(REGEXP_REPLACE(RAWTOHEX(SYS_GUID()), '([A-F0-9]{8})([A-F0-9]{4})([A-F0-9]{4})([A-F0-9]{4})([A-F0-9]{12})', '\1-\2-\3-\4-\5')) PRIMARY KEY,
    name VARCHAR2(128) NOT NULL,
    slug VARCHAR2(64) NOT NULL,
    plan VARCHAR2(32) DEFAULT 'FREE' NOT NULL,
    status VARCHAR2(32) DEFAULT 'ACTIVE' NOT NULL,
    max_users NUMBER(10) DEFAULT 5 NOT NULL,
    max_storage_bytes NUMBER(19) DEFAULT 1073741824 NOT NULL,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT SYSTIMESTAMP NOT NULL,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT SYSTIMESTAMP NOT NULL,

    -- Integrity Constraints
    CONSTRAINT uq_tenants_slug UNIQUE (slug),
    CONSTRAINT chk_tenants_slug_format CHECK (REGEXP_LIKE(slug, '^[a-z0-9-]+$')),
    CONSTRAINT chk_tenants_plan CHECK (plan IN ('FREE', 'STARTER', 'PRO', 'ENTERPRISE')),
    CONSTRAINT chk_tenants_status CHECK (status IN ('PENDING', 'ACTIVE', 'SUSPENDED', 'ARCHIVED')),
    CONSTRAINT chk_tenants_max_users CHECK (max_users > 0),
    CONSTRAINT chk_tenants_storage CHECK (max_storage_bytes >= 0)
);

CREATE INDEX idx_tenants_status ON tenants(status);
CREATE INDEX idx_tenants_plan ON tenants(plan);
CREATE INDEX idx_tenants_created_at ON tenants(created_at DESC);

-- ------------------------------------------------------------------------------
-- 2. APP_USERS TABLE
-- Users belonging to specific tenants with role-based access control.
-- ------------------------------------------------------------------------------
CREATE TABLE app_users (
    id VARCHAR2(36) DEFAULT LOWER(REGEXP_REPLACE(RAWTOHEX(SYS_GUID()), '([A-F0-9]{8})([A-F0-9]{4})([A-F0-9]{4})([A-F0-9]{4})([A-F0-9]{12})', '\1-\2-\3-\4-\5')) PRIMARY KEY,
    tenant_id VARCHAR2(36) NOT NULL,
    email VARCHAR2(255) NOT NULL,
    full_name VARCHAR2(128) NOT NULL,
    role VARCHAR2(32) DEFAULT 'MEMBER' NOT NULL,
    is_active NUMBER(1) DEFAULT 1 NOT NULL,
    last_login_at TIMESTAMP WITH TIME ZONE NULL,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT SYSTIMESTAMP NOT NULL,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT SYSTIMESTAMP NOT NULL,

    CONSTRAINT fk_app_users_tenant FOREIGN KEY (tenant_id)
        REFERENCES tenants(id) ON DELETE CASCADE,
    CONSTRAINT uq_tenant_user_email UNIQUE (tenant_id, email),
    CONSTRAINT chk_app_users_role CHECK (role IN ('OWNER', 'ADMIN', 'MEMBER', 'VIEWER')),
    CONSTRAINT chk_app_users_email_format CHECK (
        REGEXP_LIKE(email, '^[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}$')
    )
);

CREATE INDEX idx_app_users_tenant_id ON app_users(tenant_id);
CREATE INDEX idx_app_users_email ON app_users(email);
CREATE INDEX idx_app_users_tenant_role ON app_users(tenant_id, role);

-- ------------------------------------------------------------------------------
-- 3. SYNTHETIC SEED DATA
-- ------------------------------------------------------------------------------
INSERT INTO tenants (id, name, slug, plan, status, max_users, max_storage_bytes, created_at)
VALUES ('a0000000-0000-0000-0000-000000000001', 'Acme Cloud Technologies', 'acme-cloud', 'ENTERPRISE', 'ACTIVE', 100, 107374182400, SYSTIMESTAMP - INTERVAL '120' DAY);

INSERT INTO tenants (id, name, slug, plan, status, max_users, max_storage_bytes, created_at)
VALUES ('a0000000-0000-0000-0000-000000000002', 'Nova FinTech Group', 'nova-fintech', 'ENTERPRISE', 'ACTIVE', 50, 53687091200, SYSTIMESTAMP - INTERVAL '90' DAY);

INSERT INTO tenants (id, name, slug, plan, status, max_users, max_storage_bytes, created_at)
VALUES ('a0000000-0000-0000-0000-000000000003', 'Quantum Retail Solutions', 'quantum-retail', 'PRO', 'ACTIVE', 25, 21474836480, SYSTIMESTAMP - INTERVAL '60' DAY);

INSERT INTO tenants (id, name, slug, plan, status, max_users, max_storage_bytes, created_at)
VALUES ('a0000000-0000-0000-0000-000000000004', 'Hyperion Health Labs', 'hyperion-health', 'PRO', 'SUSPENDED', 20, 21474836480, SYSTIMESTAMP - INTERVAL '45' DAY);

INSERT INTO tenants (id, name, slug, plan, status, max_users, max_storage_bytes, created_at)
VALUES ('a0000000-0000-0000-0000-000000000005', 'Apex Robotics', 'apex-robotics', 'STARTER', 'ACTIVE', 10, 5368709120, SYSTIMESTAMP - INTERVAL '30' DAY);

INSERT INTO tenants (id, name, slug, plan, status, max_users, max_storage_bytes, created_at)
VALUES ('a0000000-0000-0000-0000-000000000006', 'Cobalt Logistics', 'cobalt-logistics', 'STARTER', 'SUSPENDED', 10, 5368709120, SYSTIMESTAMP - INTERVAL '20' DAY);

INSERT INTO tenants (id, name, slug, plan, status, max_users, max_storage_bytes, created_at)
VALUES ('a0000000-0000-0000-0000-000000000007', 'DevPulse Analytics', 'devpulse', 'FREE', 'ACTIVE', 5, 1073741824, SYSTIMESTAMP - INTERVAL '10' DAY);

INSERT INTO tenants (id, name, slug, plan, status, max_users, max_storage_bytes, created_at)
VALUES ('a0000000-0000-0000-0000-000000000008', 'ZeroLag Gaming Studios', 'zerolag', 'FREE', 'PENDING', 5, 1073741824, SYSTIMESTAMP - INTERVAL '2' DAY);

-- Insert Users for Acme Cloud
INSERT INTO app_users (tenant_id, email, full_name, role, is_active, last_login_at, created_at)
VALUES ('a0000000-0000-0000-0000-000000000001', 'sarah.connor@acmecloud.io', 'Sarah Connor', 'OWNER', 1, SYSTIMESTAMP - INTERVAL '2' HOUR, SYSTIMESTAMP - INTERVAL '120' DAY);

INSERT INTO app_users (tenant_id, email, full_name, role, is_active, last_login_at, created_at)
VALUES ('a0000000-0000-0000-0000-000000000001', 'john.doe@acmecloud.io', 'John Doe', 'ADMIN', 1, SYSTIMESTAMP - INTERVAL '5' HOUR, SYSTIMESTAMP - INTERVAL '115' DAY);

INSERT INTO app_users (tenant_id, email, full_name, role, is_active, last_login_at, created_at)
VALUES ('a0000000-0000-0000-0000-000000000001', 'elena.rostova@acmecloud.io', 'Elena Rostova', 'MEMBER', 1, SYSTIMESTAMP - INTERVAL '1' DAY, SYSTIMESTAMP - INTERVAL '90' DAY);

INSERT INTO app_users (tenant_id, email, full_name, role, is_active, last_login_at, created_at)
VALUES ('a0000000-0000-0000-0000-000000000001', 'marcus.vance@acmecloud.io', 'Marcus Vance', 'MEMBER', 1, SYSTIMESTAMP - INTERVAL '3' DAY, SYSTIMESTAMP - INTERVAL '60' DAY);

INSERT INTO app_users (tenant_id, email, full_name, role, is_active, last_login_at, created_at)
VALUES ('a0000000-0000-0000-0000-000000000001', 'auditor@acmecloud.io', 'External Auditor', 'VIEWER', 0, SYSTIMESTAMP - INTERVAL '30' DAY, SYSTIMESTAMP - INTERVAL '40' DAY);

-- Insert Users for Nova FinTech
INSERT INTO app_users (tenant_id, email, full_name, role, is_active, last_login_at, created_at)
VALUES ('a0000000-0000-0000-0000-000000000002', 'alex.chen@novafintech.com', 'Alex Chen', 'OWNER', 1, SYSTIMESTAMP - INTERVAL '1' HOUR, SYSTIMESTAMP - INTERVAL '90' DAY);

INSERT INTO app_users (tenant_id, email, full_name, role, is_active, last_login_at, created_at)
VALUES ('a0000000-0000-0000-0000-000000000002', 'priya.sharma@novafintech.com', 'Priya Sharma', 'ADMIN', 1, SYSTIMESTAMP - INTERVAL '4' HOUR, SYSTIMESTAMP - INTERVAL '85' DAY);

INSERT INTO app_users (tenant_id, email, full_name, role, is_active, last_login_at, created_at)
VALUES ('a0000000-0000-0000-0000-000000000002', 'david.kim@novafintech.com', 'David Kim', 'MEMBER', 1, SYSTIMESTAMP - INTERVAL '8' HOUR, SYSTIMESTAMP - INTERVAL '70' DAY);

-- Insert Users for Quantum Retail
INSERT INTO app_users (tenant_id, email, full_name, role, is_active, last_login_at, created_at)
VALUES ('a0000000-0000-0000-0000-000000000003', 'rachel.green@quantumretail.com', 'Rachel Green', 'OWNER', 1, SYSTIMESTAMP - INTERVAL '12' HOUR, SYSTIMESTAMP - INTERVAL '60' DAY);

INSERT INTO app_users (tenant_id, email, full_name, role, is_active, last_login_at, created_at)
VALUES ('a0000000-0000-0000-0000-000000000003', 'ross.geller@quantumretail.com', 'Ross Geller', 'MEMBER', 1, SYSTIMESTAMP - INTERVAL '1' DAY, SYSTIMESTAMP - INTERVAL '50' DAY);

-- Insert Users for Hyperion Health
INSERT INTO app_users (tenant_id, email, full_name, role, is_active, last_login_at, created_at)
VALUES ('a0000000-0000-0000-0000-000000000004', 'dr.house@hyperionhealth.org', 'Gregory House', 'OWNER', 0, SYSTIMESTAMP - INTERVAL '40' DAY, SYSTIMESTAMP - INTERVAL '45' DAY);

INSERT INTO app_users (tenant_id, email, full_name, role, is_active, last_login_at, created_at)
VALUES ('a0000000-0000-0000-0000-000000000004', 'dr.cameron@hyperionhealth.org', 'Allison Cameron', 'ADMIN', 0, SYSTIMESTAMP - INTERVAL '42' DAY, SYSTIMESTAMP - INTERVAL '44' DAY);

-- Insert Users for Apex Robotics
INSERT INTO app_users (tenant_id, email, full_name, role, is_active, last_login_at, created_at)
VALUES ('a0000000-0000-0000-0000-000000000005', 'miles.dyson@apexrobotics.ai', 'Miles Dyson', 'OWNER', 1, SYSTIMESTAMP - INTERVAL '30' MINUTE, SYSTIMESTAMP - INTERVAL '30' DAY);

INSERT INTO app_users (tenant_id, email, full_name, role, is_active, last_login_at, created_at)
VALUES ('a0000000-0000-0000-0000-000000000005', 't800.admin@apexrobotics.ai', 'Model 101', 'ADMIN', 1, SYSTIMESTAMP - INTERVAL '10' MINUTE, SYSTIMESTAMP - INTERVAL '28' DAY);

-- Insert Users for Cobalt Logistics
INSERT INTO app_users (tenant_id, email, full_name, role, is_active, last_login_at, created_at)
VALUES ('a0000000-0000-0000-0000-000000000006', 'dispatch@cobaltlogistics.net', 'Dispatcher Dan', 'OWNER', 0, SYSTIMESTAMP - INTERVAL '15' DAY, SYSTIMESTAMP - INTERVAL '20' DAY);

-- Insert Users for DevPulse Analytics
INSERT INTO app_users (tenant_id, email, full_name, role, is_active, last_login_at, created_at)
VALUES ('a0000000-0000-0000-0000-000000000007', 'dev.solo@devpulse.dev', 'Solo Developer', 'OWNER', 1, SYSTIMESTAMP - INTERVAL '6' HOUR, SYSTIMESTAMP - INTERVAL '10' DAY);

-- Insert Users for ZeroLag Gaming
INSERT INTO app_users (tenant_id, email, full_name, role, is_active, last_login_at, created_at)
VALUES ('a0000000-0000-0000-0000-000000000008', 'lead.streamer@zerolag.gg', 'Streamer Alpha', 'OWNER', 1, NULL, SYSTIMESTAMP - INTERVAL '2' DAY);

COMMIT;

