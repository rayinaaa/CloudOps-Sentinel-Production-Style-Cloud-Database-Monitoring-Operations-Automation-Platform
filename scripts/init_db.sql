-- ==============================================================================
-- CloudOps Sentinel - Target Database Initialization Script
-- Executed on container creation to enable observability extensions and sample schemas
-- ==============================================================================

-- 1. Enable Performance & Query Telemetry Extensions
CREATE EXTENSION IF NOT EXISTS pg_stat_statements;
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

-- 2. Create Monitoring Agent User with Read-Only Analytics Role (Least Privilege)
DO
$do$
BEGIN
   IF NOT EXISTS (
      SELECT FROM pg_catalog.pg_roles WHERE rolname = 'monitor_agent'
   ) THEN
      CREATE ROLE monitor_agent WITH LOGIN PASSWORD 'CHANGE_ME_TARGET_SECURE_PASSWORD';
   END IF;
END
$do$;

-- Grant monitor_agent rights to view server activity and stats
GRANT pg_monitor TO monitor_agent;
GRANT pg_read_all_stats TO monitor_agent;

-- 3. Create sample production business tables to simulate live workload
CREATE TABLE IF NOT EXISTS customer_orders (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    customer_id UUID NOT NULL,
    order_status VARCHAR(32) NOT NULL DEFAULT 'PENDING',
    order_amount NUMERIC(12, 2) NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_customer_orders_status ON customer_orders(order_status);
CREATE INDEX IF NOT EXISTS idx_customer_orders_created_at ON customer_orders(created_at);

-- 4. Seed simulated sample records
INSERT INTO customer_orders (customer_id, order_status, order_amount)
SELECT 
    uuid_generate_v4(),
    (ARRAY['PENDING', 'PROCESSING', 'COMPLETED', 'CANCELLED', 'REFUNDED'])[floor(random() * 5 + 1)],
    round((random() * 500 + 10)::numeric, 2)
FROM generate_series(1, 100)
ON CONFLICT DO NOTHING;

