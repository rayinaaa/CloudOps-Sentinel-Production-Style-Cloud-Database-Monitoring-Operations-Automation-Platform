"""Add tenants, app_users, incidents, and incident_history

Revision ID: 0002_tenants_and_incidents
Revises: 0001_initial_schema
Create Date: 2026-11-09 18:50:00.000000

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0002_tenants_and_incidents"
down_revision: Union[str, None] = "0001_initial_schema"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    existing_tables = inspector.get_table_names()

    # 1. Tenants table
    if "tenants" not in existing_tables:
        op.create_table(
            "tenants",
            sa.Column(
                "id",
                postgresql.UUID(as_uuid=True),
                primary_key=True,
                server_default=sa.text("gen_random_uuid()"),
            ),
            sa.Column("name", sa.String(length=128), nullable=False),
            sa.Column("slug", sa.String(length=64), nullable=False, unique=True),
            sa.Column(
                "plan", sa.String(length=32), nullable=False, server_default="FREE"
            ),
            sa.Column(
                "status", sa.String(length=32), nullable=False, server_default="ACTIVE"
            ),
            sa.Column("max_users", sa.Integer(), nullable=False, server_default="5"),
            sa.Column(
                "max_storage_bytes",
                sa.BigInteger(),
                nullable=False,
                server_default="1073741824",
            ),
            sa.Column(
                "created_at",
                sa.DateTime(timezone=True),
                nullable=False,
                server_default=sa.text("now()"),
            ),
            sa.Column(
                "updated_at",
                sa.DateTime(timezone=True),
                nullable=False,
                server_default=sa.text("now()"),
            ),
            sa.CheckConstraint(
                "slug ~* '^[a-z0-9-]+$'", name="chk_tenants_slug_format"
            ),
            sa.CheckConstraint(
                "plan IN ('FREE', 'STARTER', 'PRO', 'ENTERPRISE')",
                name="chk_tenants_plan",
            ),
            sa.CheckConstraint(
                "status IN ('PENDING', 'ACTIVE', 'SUSPENDED', 'ARCHIVED')",
                name="chk_tenants_status",
            ),
            sa.CheckConstraint("max_users > 0", name="chk_tenants_max_users"),
            sa.CheckConstraint("max_storage_bytes >= 0", name="chk_tenants_storage"),
        )
        op.create_index("idx_tenants_status", "tenants", ["status"])
        op.create_index("idx_tenants_plan", "tenants", ["plan"])
        op.create_index("idx_tenants_created_at", "tenants", ["created_at"])
        op.create_index("idx_tenants_slug", "tenants", ["slug"])

    # 2. App Users table
    if "app_users" not in existing_tables:
        op.create_table(
            "app_users",
            sa.Column(
                "id",
                postgresql.UUID(as_uuid=True),
                primary_key=True,
                server_default=sa.text("gen_random_uuid()"),
            ),
            sa.Column(
                "tenant_id",
                postgresql.UUID(as_uuid=True),
                sa.ForeignKey("tenants.id", ondelete="CASCADE"),
                nullable=False,
            ),
            sa.Column("email", sa.String(length=255), nullable=False),
            sa.Column("full_name", sa.String(length=128), nullable=False),
            sa.Column(
                "role", sa.String(length=32), nullable=False, server_default="MEMBER"
            ),
            sa.Column("is_active", sa.Boolean(), nullable=False, server_default="true"),
            sa.Column("last_login_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column(
                "created_at",
                sa.DateTime(timezone=True),
                nullable=False,
                server_default=sa.text("now()"),
            ),
            sa.Column(
                "updated_at",
                sa.DateTime(timezone=True),
                nullable=False,
                server_default=sa.text("now()"),
            ),
            sa.UniqueConstraint("tenant_id", "email", name="uq_tenant_user_email"),
            sa.CheckConstraint(
                "role IN ('OWNER', 'ADMIN', 'MEMBER', 'VIEWER')",
                name="chk_app_users_role",
            ),
            sa.CheckConstraint(
                "email ~* '^[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\\.[A-Za-z]{2,}$'",
                name="chk_app_users_email_format",
            ),
        )
        op.create_index("idx_app_users_tenant_id", "app_users", ["tenant_id"])
        op.create_index("idx_app_users_email", "app_users", ["email"])
        op.create_index("idx_app_users_tenant_role", "app_users", ["tenant_id", "role"])

    # 3. Seed data if tenants table is empty
    tenant_count = conn.execute(sa.text("SELECT count(*) FROM tenants")).scalar()
    if tenant_count == 0:
        conn.execute(
            sa.text("""
            INSERT INTO tenants (id, name, slug, plan, status, max_users, max_storage_bytes, created_at)
            VALUES
                ('a0000000-0000-0000-0000-000000000001', 'Acme Cloud Technologies', 'acme-cloud', 'ENTERPRISE', 'ACTIVE', 100, 107374182400, NOW() - INTERVAL '120 days'),
                ('a0000000-0000-0000-0000-000000000002', 'Nova FinTech Group', 'nova-fintech', 'ENTERPRISE', 'ACTIVE', 50, 53687091200, NOW() - INTERVAL '90 days'),
                ('a0000000-0000-0000-0000-000000000003', 'Quantum Retail Solutions', 'quantum-retail', 'PRO', 'ACTIVE', 25, 21474836480, NOW() - INTERVAL '60 days'),
                ('a0000000-0000-0000-0000-000000000004', 'Hyperion Health Labs', 'hyperion-health', 'PRO', 'SUSPENDED', 20, 21474836480, NOW() - INTERVAL '45 days'),
                ('a0000000-0000-0000-0000-000000000005', 'Apex Robotics', 'apex-robotics', 'STARTER', 'ACTIVE', 10, 5368709120, NOW() - INTERVAL '30 days'),
                ('a0000000-0000-0000-0000-000000000006', 'Cobalt Logistics', 'cobalt-logistics', 'STARTER', 'SUSPENDED', 10, 5368709120, NOW() - INTERVAL '20 days'),
                ('a0000000-0000-0000-0000-000000000007', 'DevPulse Analytics', 'devpulse', 'FREE', 'ACTIVE', 5, 1073741824, NOW() - INTERVAL '10 days'),
                ('a0000000-0000-0000-0000-000000000008', 'ZeroLag Gaming Studios', 'zerolag', 'FREE', 'PENDING', 5, 1073741824, NOW() - INTERVAL '2 days')
            ON CONFLICT (slug) DO NOTHING;
        """)
        )
        conn.execute(
            sa.text("""
            INSERT INTO app_users (tenant_id, email, full_name, role, is_active, last_login_at, created_at)
            VALUES
                ('a0000000-0000-0000-0000-000000000001', 'sarah.connor@acmecloud.io', 'Sarah Connor', 'OWNER', TRUE, NOW() - INTERVAL '2 hours', NOW() - INTERVAL '120 days'),
                ('a0000000-0000-0000-0000-000000000001', 'john.doe@acmecloud.io', 'John Doe', 'ADMIN', TRUE, NOW() - INTERVAL '5 hours', NOW() - INTERVAL '115 days'),
                ('a0000000-0000-0000-0000-000000000001', 'elena.rostova@acmecloud.io', 'Elena Rostova', 'MEMBER', TRUE, NOW() - INTERVAL '1 day', NOW() - INTERVAL '90 days'),
                ('a0000000-0000-0000-0000-000000000001', 'marcus.vance@acmecloud.io', 'Marcus Vance', 'MEMBER', TRUE, NOW() - INTERVAL '3 days', NOW() - INTERVAL '60 days'),
                ('a0000000-0000-0000-0000-000000000001', 'auditor@acmecloud.io', 'External Auditor', 'VIEWER', FALSE, NOW() - INTERVAL '30 days', NOW() - INTERVAL '40 days'),
                ('a0000000-0000-0000-0000-000000000002', 'alex.chen@novafintech.com', 'Alex Chen', 'OWNER', TRUE, NOW() - INTERVAL '1 hour', NOW() - INTERVAL '90 days'),
                ('a0000000-0000-0000-0000-000000000002', 'priya.sharma@novafintech.com', 'Priya Sharma', 'ADMIN', TRUE, NOW() - INTERVAL '4 hours', NOW() - INTERVAL '85 days'),
                ('a0000000-0000-0000-0000-000000000002', 'david.kim@novafintech.com', 'David Kim', 'MEMBER', TRUE, NOW() - INTERVAL '8 hours', NOW() - INTERVAL '70 days'),
                ('a0000000-0000-0000-0000-000000000003', 'rachel.green@quantumretail.com', 'Rachel Green', 'OWNER', TRUE, NOW() - INTERVAL '12 hours', NOW() - INTERVAL '60 days'),
                ('a0000000-0000-0000-0000-000000000003', 'ross.geller@quantumretail.com', 'Ross Geller', 'MEMBER', TRUE, NOW() - INTERVAL '1 day', NOW() - INTERVAL '50 days'),
                ('a0000000-0000-0000-0000-000000000004', 'dr.house@hyperionhealth.org', 'Gregory House', 'OWNER', FALSE, NOW() - INTERVAL '40 days', NOW() - INTERVAL '45 days'),
                ('a0000000-0000-0000-0000-000000000004', 'dr.cameron@hyperionhealth.org', 'Allison Cameron', 'ADMIN', FALSE, NOW() - INTERVAL '42 days', NOW() - INTERVAL '44 days'),
                ('a0000000-0000-0000-0000-000000000005', 'miles.dyson@apexrobotics.ai', 'Miles Dyson', 'OWNER', TRUE, NOW() - INTERVAL '30 minutes', NOW() - INTERVAL '30 days'),
                ('a0000000-0000-0000-0000-000000000005', 't800.admin@apexrobotics.ai', 'Model 101', 'ADMIN', TRUE, NOW() - INTERVAL '10 minutes', NOW() - INTERVAL '28 days'),
                ('a0000000-0000-0000-0000-000000000006', 'dispatch@cobaltlogistics.net', 'Dispatcher Dan', 'OWNER', FALSE, NOW() - INTERVAL '15 days', NOW() - INTERVAL '20 days'),
                ('a0000000-0000-0000-0000-000000000007', 'dev.solo@devpulse.dev', 'Solo Developer', 'OWNER', TRUE, NOW() - INTERVAL '6 hours', NOW() - INTERVAL '10 days'),
                ('a0000000-0000-0000-0000-000000000008', 'lead.streamer@zerolag.gg', 'Streamer Alpha', 'OWNER', TRUE, NULL, NOW() - INTERVAL '2 days')
            ON CONFLICT (tenant_id, email) DO NOTHING;
        """)
        )

    # 4. Incidents table
    if "incidents" not in existing_tables:
        op.create_table(
            "incidents",
            sa.Column(
                "id",
                postgresql.UUID(as_uuid=True),
                primary_key=True,
                server_default=sa.text("gen_random_uuid()"),
            ),
            sa.Column("title", sa.String(length=255), nullable=False),
            sa.Column("description", sa.Text(), nullable=True),
            sa.Column(
                "severity",
                sa.String(length=32),
                nullable=False,
                server_default="MEDIUM",
            ),
            sa.Column(
                "status", sa.String(length=32), nullable=False, server_default="OPEN"
            ),
            sa.Column(
                "source",
                sa.String(length=64),
                nullable=False,
                server_default="ALERTMANAGER",
            ),
            sa.Column(
                "component",
                sa.String(length=64),
                nullable=False,
                server_default="DATABASE",
            ),
            sa.Column(
                "target_instance",
                sa.String(length=128),
                nullable=False,
                server_default="primary-postgres",
            ),
            sa.Column("fingerprint", sa.String(length=128), nullable=True),
            sa.Column(
                "escalation_level", sa.Integer(), nullable=False, server_default="0"
            ),
            sa.Column("assigned_to", sa.String(length=128), nullable=True),
            sa.Column("acknowledged_by", sa.String(length=128), nullable=True),
            sa.Column("resolved_by", sa.String(length=128), nullable=True),
            sa.Column("resolution_notes", sa.Text(), nullable=True),
            sa.Column(
                "metadata_json",
                postgresql.JSONB(astext_type=sa.Text()),
                nullable=False,
                server_default=sa.text("'{}'::jsonb"),
            ),
            sa.Column(
                "created_at",
                sa.DateTime(timezone=True),
                nullable=False,
                server_default=sa.text("now()"),
            ),
            sa.Column(
                "updated_at",
                sa.DateTime(timezone=True),
                nullable=False,
                server_default=sa.text("now()"),
            ),
            sa.Column("acknowledged_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("resolved_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("escalated_at", sa.DateTime(timezone=True), nullable=True),
            sa.CheckConstraint(
                "severity IN ('CRITICAL', 'HIGH', 'MEDIUM', 'LOW')",
                name="chk_incidents_severity",
            ),
            sa.CheckConstraint(
                "status IN ('OPEN', 'ACKNOWLEDGED', 'RESOLVED')",
                name="chk_incidents_status",
            ),
            sa.CheckConstraint(
                "source IN ('ALERTMANAGER', 'HEALTH_CHECK_PROBE', 'DISK_MONITOR', 'CONNECTION_MONITOR', 'MANUAL', 'SIMULATION')",
                name="chk_incidents_source",
            ),
            sa.CheckConstraint(
                "escalation_level >= 0 AND escalation_level <= 3",
                name="chk_incidents_escalation_level",
            ),
        )
        op.create_index(
            "idx_incidents_status_severity", "incidents", ["status", "severity"]
        )
        op.create_index("idx_incidents_fingerprint", "incidents", ["fingerprint"])
        op.create_index("idx_incidents_created_at", "incidents", ["created_at"])
        op.create_index("idx_incidents_component", "incidents", ["component"])

    # 5. Incident History table
    if "incident_history" not in existing_tables:
        op.create_table(
            "incident_history",
            sa.Column(
                "id",
                postgresql.UUID(as_uuid=True),
                primary_key=True,
                server_default=sa.text("gen_random_uuid()"),
            ),
            sa.Column(
                "incident_id",
                postgresql.UUID(as_uuid=True),
                sa.ForeignKey("incidents.id", ondelete="CASCADE"),
                nullable=False,
            ),
            sa.Column("event_type", sa.String(length=64), nullable=False),
            sa.Column("previous_status", sa.String(length=32), nullable=True),
            sa.Column("new_status", sa.String(length=32), nullable=True),
            sa.Column("previous_severity", sa.String(length=32), nullable=True),
            sa.Column("new_severity", sa.String(length=32), nullable=True),
            sa.Column(
                "actor", sa.String(length=128), nullable=False, server_default="SYSTEM"
            ),
            sa.Column("notes", sa.Text(), nullable=True),
            sa.Column(
                "metadata_json",
                postgresql.JSONB(astext_type=sa.Text()),
                nullable=False,
                server_default=sa.text("'{}'::jsonb"),
            ),
            sa.Column(
                "created_at",
                sa.DateTime(timezone=True),
                nullable=False,
                server_default=sa.text("now()"),
            ),
        )
        op.create_index(
            "idx_incident_history_incident_id", "incident_history", ["incident_id"]
        )
        op.create_index(
            "idx_incident_history_created_at", "incident_history", ["created_at"]
        )


def downgrade() -> None:
    op.drop_table("incident_history")
    op.drop_table("incidents")
    op.drop_table("app_users")
    op.drop_table("tenants")
