"""Initial database schema for CloudOps Sentinel

Revision ID: 0001_initial_schema
Revises: 
Create Date: 2026-11-07 23:55:00.000000

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = '0001_initial_schema'
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 1. database_instances
    op.create_table(
        'database_instances',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('name', sa.String(length=128), nullable=False, unique=True),
        sa.Column('engine', sa.String(length=32), nullable=False, server_default='postgresql'),
        sa.Column('host', sa.String(length=255), nullable=False),
        sa.Column('port', sa.Integer(), nullable=False, server_default='5432'),
        sa.Column('database_name', sa.String(length=64), nullable=False),
        sa.Column('username', sa.String(length=64), nullable=False),
        sa.Column('environment', sa.String(length=32), nullable=False, server_default='production'),
        sa.Column('is_active', sa.Boolean(), nullable=False, server_default='true'),
        sa.Column('health_status', sa.String(length=32), nullable=False, server_default='UNKNOWN'),
        sa.Column('ssl_mode', sa.String(length=32), nullable=False, server_default='require'),
        sa.Column('last_checked_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('tags', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.text('now()')),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.text('now()')),
    )
    op.create_index('idx_database_instances_environment', 'database_instances', ['environment'])
    op.create_index('idx_database_instances_health_status', 'database_instances', ['health_status'])

    # 2. metric_snapshots
    op.create_table(
        'metric_snapshots',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('database_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('database_instances.id', ondelete='CASCADE'), nullable=False),
        sa.Column('recorded_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.text('now()')),
        sa.Column('active_connections', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('idle_connections', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('max_connections', sa.Integer(), nullable=False, server_default='100'),
        sa.Column('connection_pool_usage_pct', sa.Float(), nullable=False, server_default='0.0'),
        sa.Column('cache_hit_ratio', sa.Float(), nullable=False, server_default='1.0'),
        sa.Column('transactions_committed', sa.BigInteger(), nullable=False, server_default='0'),
        sa.Column('transactions_rolled_back', sa.BigInteger(), nullable=False, server_default='0'),
        sa.Column('deadlocks_count', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('slow_queries_count', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('replication_lag_seconds', sa.Float(), nullable=False, server_default='0.0'),
        sa.Column('database_size_bytes', sa.BigInteger(), nullable=False, server_default='0'),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.text('now()')),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.text('now()')),
    )
    op.create_index('idx_metric_db_time', 'metric_snapshots', ['database_id', 'recorded_at'])

    # 3. alert_rules
    op.create_table(
        'alert_rules',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('name', sa.String(length=128), nullable=False, unique=True),
        sa.Column('metric_name', sa.String(length=64), nullable=False),
        sa.Column('operator', sa.String(length=16), nullable=False, server_default='GREATER_THAN'),
        sa.Column('threshold_value', sa.Float(), nullable=False),
        sa.Column('severity', sa.String(length=32), nullable=False, server_default='WARNING'),
        sa.Column('is_enabled', sa.Boolean(), nullable=False, server_default='true'),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.text('now()')),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.text('now()')),
    )

    # 4. alert_incidents
    op.create_table(
        'alert_incidents',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('database_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('database_instances.id', ondelete='CASCADE'), nullable=False),
        sa.Column('rule_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('alert_rules.id', ondelete='SET NULL'), nullable=True),
        sa.Column('status', sa.String(length=32), nullable=False, server_default='OPEN'),
        sa.Column('severity', sa.String(length=32), nullable=False, server_default='WARNING'),
        sa.Column('title', sa.String(length=255), nullable=False),
        sa.Column('message', sa.Text(), nullable=False),
        sa.Column('current_value', sa.Float(), nullable=False),
        sa.Column('threshold_value', sa.Float(), nullable=False),
        sa.Column('triggered_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.text('now()')),
        sa.Column('resolved_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('acknowledged_by', sa.String(length=128), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.text('now()')),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.text('now()')),
    )
    op.create_index('idx_incident_db_status', 'alert_incidents', ['database_id', 'status'])

    # 5. maintenance_tasks
    op.create_table(
        'maintenance_tasks',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('database_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('database_instances.id', ondelete='CASCADE'), nullable=False),
        sa.Column('task_type', sa.String(length=64), nullable=False),
        sa.Column('status', sa.String(length=32), nullable=False, server_default='PENDING'),
        sa.Column('started_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.text('now()')),
        sa.Column('completed_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('artifact_s3_url', sa.String(length=512), nullable=True),
        sa.Column('backup_size_bytes', sa.BigInteger(), nullable=True),
        sa.Column('execution_logs', sa.Text(), nullable=True),
        sa.Column('initiated_by', sa.String(length=128), nullable=False, server_default='system_scheduler'),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.text('now()')),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.text('now()')),
    )
    op.create_index('idx_maintenance_db_status', 'maintenance_tasks', ['database_id', 'status'])


def downgrade() -> None:
    op.drop_table('maintenance_tasks')
    op.drop_table('alert_incidents')
    op.drop_table('alert_rules')
    op.drop_table('metric_snapshots')
    op.drop_table('database_instances')

