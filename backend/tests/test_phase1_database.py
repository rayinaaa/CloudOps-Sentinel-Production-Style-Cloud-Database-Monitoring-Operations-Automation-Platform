"""CloudOps Sentinel - Phase 1 Database & Multi-Tenant Schema Test Suite.

Validates:
- PostgreSQL 16 connectivity
- Multi-tenant SaaS schema initialization
- Primary keys, foreign keys with ON DELETE CASCADE
- Check constraints (status, plan, role, slug)
- Multi-tenant email uniqueness constraint
- Operational query execution (active/suspended tenants, users per tenant, db size, connections)
"""

import os
import uuid

import psycopg2
import pytest
from psycopg2 import errors

# Database connection parameters for testing
DB_HOST = os.getenv("POSTGRES_SERVER", "localhost")
DB_PORT = int(os.getenv("POSTGRES_PORT", "5434"))
DB_NAME = os.getenv("POSTGRES_DB", "sentinel_db")
DB_USER = os.getenv("POSTGRES_USER", "sentinel_admin")
DB_PASS = os.getenv("POSTGRES_PASSWORD", "sentinel_secret_dev_pass")


@pytest.fixture(scope="module")
def db_conn():
    """Provides a PostgreSQL connection for integration testing."""
    conn = psycopg2.connect(
        host=DB_HOST,
        port=DB_PORT,
        dbname=DB_NAME,
        user=DB_USER,
        password=DB_PASS,
    )
    conn.autocommit = False
    yield conn
    conn.close()


def test_schema_tables_exist(db_conn):
    """Verifies that tenants and app_users tables are created."""
    with db_conn.cursor() as cur:
        cur.execute("""
            SELECT table_name 
            FROM information_schema.tables 
            WHERE table_schema = 'public' 
              AND table_name IN ('tenants', 'app_users');
        """)
        tables = {row[0] for row in cur.fetchall()}
        assert "tenants" in tables
        assert "app_users" in tables


def test_tenants_seed_data(db_conn):
    """Verifies synthetic tenant data was seeded properly."""
    with db_conn.cursor() as cur:
        cur.execute("SELECT count(*) FROM tenants;")
        count = cur.fetchone()[0]
        assert count >= 8, f"Expected at least 8 seeded tenants, got {count}"


def test_app_users_seed_data(db_conn):
    """Verifies synthetic users were seeded properly."""
    with db_conn.cursor() as cur:
        cur.execute("SELECT count(*) FROM app_users;")
        count = cur.fetchone()[0]
        assert count >= 16, f"Expected at least 16 seeded users, got {count}"


def test_unique_tenant_slug_constraint(db_conn):
    """Verifies that duplicate tenant slug violates unique constraint."""
    with db_conn.cursor() as cur:
        with pytest.raises(errors.UniqueViolation):
            cur.execute("""
                INSERT INTO tenants (name, slug, plan) 
                VALUES ('Duplicate Slug Corp', 'acme-cloud', 'STARTER');
            """)
    db_conn.rollback()


def test_tenant_plan_check_constraint(db_conn):
    """Verifies check constraint rejects invalid subscription plan."""
    with db_conn.cursor() as cur:
        with pytest.raises(errors.CheckViolation):
            cur.execute("""
                INSERT INTO tenants (name, slug, plan) 
                VALUES ('Invalid Plan Co', 'invalid-plan', 'PLATINUM_TIER');
            """)
    db_conn.rollback()


def test_tenant_status_check_constraint(db_conn):
    """Verifies check constraint rejects invalid lifecycle status."""
    with db_conn.cursor() as cur:
        with pytest.raises(errors.CheckViolation):
            cur.execute("""
                INSERT INTO tenants (name, slug, status) 
                VALUES ('Invalid Status Co', 'invalid-status', 'BANNED_FOREVER');
            """)
    db_conn.rollback()


def test_app_users_role_check_constraint(db_conn):
    """Verifies check constraint rejects invalid role."""
    with db_conn.cursor() as cur:
        cur.execute("SELECT id FROM tenants LIMIT 1;")
        tenant_id = cur.fetchone()[0]
        with pytest.raises(errors.CheckViolation):
            cur.execute(
                """
                INSERT INTO app_users (tenant_id, email, full_name, role) 
                VALUES (%s, 'super@example.com', 'Super Hacker', 'SUPER_ADMIN');
            """,
                (tenant_id,),
            )
    db_conn.rollback()


def test_tenant_scoped_user_email_uniqueness(db_conn):
    """Verifies that the same email cannot exist twice within the same tenant."""
    with db_conn.cursor() as cur:
        cur.execute("SELECT tenant_id, email FROM app_users LIMIT 1;")
        tenant_id, email = cur.fetchone()
        with pytest.raises(errors.UniqueViolation):
            cur.execute(
                """
                INSERT INTO app_users (tenant_id, email, full_name, role) 
                VALUES (%s, %s, 'Duplicate Person', 'MEMBER');
            """,
                (tenant_id, email),
            )
    db_conn.rollback()


def test_foreign_key_cascade_deletion(db_conn):
    """Verifies that deleting a tenant cascades and deletes its app_users."""
    temp_tenant_id = str(uuid.uuid4())
    temp_slug = f"cascade-test-{uuid.uuid4().hex[:6]}"

    with db_conn.cursor() as cur:
        # Create temporary tenant
        cur.execute(
            """
            INSERT INTO tenants (id, name, slug, plan, status) 
            VALUES (%s, 'Cascade Test Org', %s, 'STARTER', 'ACTIVE');
        """,
            (temp_tenant_id, temp_slug),
        )

        # Create two temporary users
        cur.execute(
            """
            INSERT INTO app_users (tenant_id, email, full_name) 
            VALUES 
                (%s, 'u1@cascade.test', 'User One'),
                (%s, 'u2@cascade.test', 'User Two');
        """,
            (temp_tenant_id, temp_tenant_id),
        )
        db_conn.commit()

        # Confirm users exist
        cur.execute(
            "SELECT count(*) FROM app_users WHERE tenant_id = %s;", (temp_tenant_id,)
        )
        assert cur.fetchone()[0] == 2

        # Delete tenant
        cur.execute("DELETE FROM tenants WHERE id = %s;", (temp_tenant_id,))
        db_conn.commit()

        # Verify users were automatically cascaded
        cur.execute(
            "SELECT count(*) FROM app_users WHERE tenant_id = %s;", (temp_tenant_id,)
        )
        assert cur.fetchone()[0] == 0


def test_operational_query_active_suspended_tenants(db_conn):
    """Verifies Query 1: Active vs. Suspended Tenants Breakdown."""
    with db_conn.cursor() as cur:
        cur.execute("""
            SELECT
                status,
                plan,
                COUNT(*) AS tenant_count,
                ROUND(COUNT(*)::numeric / SUM(COUNT(*)) OVER () * 100, 2) AS pct_of_total_fleet,
                SUM(max_users) AS allocated_user_capacity
            FROM tenants
            GROUP BY status, plan
            ORDER BY status, plan;
        """)
        rows = cur.fetchall()
        assert len(rows) > 0
        statuses = {r[0] for r in rows}
        assert "ACTIVE" in statuses
        assert "SUSPENDED" in statuses


def test_operational_query_users_per_tenant(db_conn):
    """Verifies Query 2: Users per Tenant & Capacity Utilization."""
    with db_conn.cursor() as cur:
        cur.execute("""
            SELECT
                t.name,
                t.max_users,
                COUNT(u.id) AS total_users,
                ROUND((COUNT(u.id)::numeric / t.max_users) * 100, 2) AS seat_utilization_pct
            FROM tenants t
            LEFT JOIN app_users u ON t.id = u.tenant_id
            GROUP BY t.id, t.name, t.max_users
            ORDER BY seat_utilization_pct DESC;
        """)
        rows = cur.fetchall()
        assert len(rows) >= 8
        for r in rows:
            assert r[1] > 0  # max_users > 0
            assert r[3] >= 0.0  # utilization >= 0%


def test_operational_query_database_size(db_conn):
    """Verifies Query 3: Database & Table Storage Footprint."""
    with db_conn.cursor() as cur:
        cur.execute("SELECT pg_database_size(current_database());")
        db_size_bytes = cur.fetchone()[0]
        assert db_size_bytes > 0


def test_operational_query_active_connections(db_conn):
    """Verifies Query 4: Active Connections vs. Max Connections."""
    with db_conn.cursor() as cur:
        cur.execute("""
            SELECT
                count(*) FILTER (WHERE state = 'active') AS active_connections,
                count(*) AS total_checked_out,
                current_setting('max_connections')::int AS max_connections
            FROM pg_stat_activity;
        """)
        row = cur.fetchone()
        assert row[0] >= 1  # at least this test query is active
        assert row[1] >= 1
        assert row[2] > 0
