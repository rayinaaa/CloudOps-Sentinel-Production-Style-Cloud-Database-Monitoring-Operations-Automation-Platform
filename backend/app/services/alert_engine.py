"""CloudOps Alert Engine & Anomaly Detection Service.

Evaluates database telemetry against threshold rules, maintains incident
lifecycles (OPEN, ACKNOWLEDGED, RESOLVED), and dispatches webhook notifications
to operational channels (Slack, Microsoft Teams, PagerDuty).
"""

from datetime import datetime, timezone
from typing import List, Optional
import httpx
from sqlalchemy import and_, select
from sqlalchemy.ext.asyncio import AsyncSession
from app.core.config import settings
from app.core.logging import logger
from app.models.alert import AlertIncident, AlertRule
from app.models.database_instance import DatabaseInstance
from app.services.db_inspector import TargetInspectionResult


class AlertEngine:
    """Evaluates rules against metric snapshots and coordinates incident response."""

    @staticmethod
    async def evaluate_target(
        db: AsyncSession,
        instance: DatabaseInstance,
        telemetry: TargetInspectionResult,
    ) -> List[AlertIncident]:
        """Evaluates active alert rules against a freshly harvested telemetry snapshot."""
        # 1. Handle Unreachable Target Special Case
        if not telemetry.is_reachable:
            return await AlertEngine._handle_unreachable_target(db, instance, telemetry.error_message)

        # 2. Fetch all enabled rules
        rules_res = await db.execute(select(AlertRule).where(AlertRule.is_enabled == True))  # noqa: E712
        rules = rules_res.scalars().all()

        modified_incidents: List[AlertIncident] = []

        # Map metric name to telemetry attribute
        metric_values = {
            "connection_pool_usage_pct": telemetry.connection_pool_usage_pct,
            "cache_hit_ratio": telemetry.cache_hit_ratio,
            "slow_queries_count": float(telemetry.slow_queries_count),
            "deadlocks_count": float(telemetry.deadlocks_count),
            "replication_lag_seconds": telemetry.replication_lag_seconds,
        }

        for rule in rules:
            current_val = metric_values.get(rule.metric_name)
            if current_val is None:
                continue

            is_breached = AlertEngine._is_condition_breached(
                current_val, rule.operator, rule.threshold_value
            )

            # Query existing open incident for this instance + rule
            incident_res = await db.execute(
                select(AlertIncident).where(
                    and_(
                        AlertIncident.database_id == instance.id,
                        AlertIncident.rule_id == rule.id,
                        AlertIncident.status.in_(["OPEN", "ACKNOWLEDGED"]),
                    )
                )
            )
            existing_incident = incident_res.scalar_one_or_none()

            if is_breached:
                if not existing_incident:
                    # Trigger new incident
                    title = f"Alert: {rule.name} breached on {instance.name}"
                    message = (
                        f"Database '{instance.name}' ({instance.environment}) breached threshold for "
                        f"{rule.metric_name}. Current: {current_val:.3f}, Threshold: {rule.threshold_value:.3f}."
                    )
                    incident = AlertIncident(
                        database_id=instance.id,
                        rule_id=rule.id,
                        status="OPEN",
                        severity=rule.severity,
                        title=title,
                        message=message,
                        current_value=current_val,
                        threshold_value=rule.threshold_value,
                        triggered_at=datetime.now(timezone.utc),
                    )
                    db.add(incident)
                    modified_incidents.append(incident)
                    logger.warning(
                        "Operational alert triggered",
                        instance=instance.name,
                        rule=rule.name,
                        severity=rule.severity,
                        value=current_val,
                    )
                    # Dispatch webhook notification asynchronously
                    await AlertEngine.dispatch_webhook(incident, instance)
                else:
                    # Update current value on existing incident
                    existing_incident.current_value = current_val

            else:
                # Metric returned to normal: auto-resolve open incident
                if existing_incident:
                    existing_incident.status = "RESOLVED"
                    existing_incident.resolved_at = datetime.now(timezone.utc)
                    modified_incidents.append(existing_incident)
                    logger.info(
                        "Operational alert auto-resolved",
                        instance=instance.name,
                        rule=rule.name,
                        current_value=current_val,
                    )

        return modified_incidents

    @staticmethod
    def _is_condition_breached(current_val: float, operator: str, threshold: float) -> bool:
        """Compares value against threshold with given operator."""
        op = operator.upper()
        if op == "GREATER_THAN":
            return current_val > threshold
        if op == "GREATER_THAN_OR_EQUAL":
            return current_val >= threshold
        if op == "LESS_THAN":
            return current_val < threshold
        if op == "LESS_THAN_OR_EQUAL":
            return current_val <= threshold
        if op == "EQUALS":
            return current_val == threshold
        return False

    @staticmethod
    async def _handle_unreachable_target(
        db: AsyncSession,
        instance: DatabaseInstance,
        error_message: Optional[str],
    ) -> List[AlertIncident]:
        """Special handler when an active target cannot be reached via network/auth."""
        incident_res = await db.execute(
            select(AlertIncident).where(
                and_(
                    AlertIncident.database_id == instance.id,
                    AlertIncident.title.like("%Target Unreachable%"),
                    AlertIncident.status.in_(["OPEN", "ACKNOWLEDGED"]),
                )
            )
        )
        existing = incident_res.scalar_one_or_none()
        if not existing:
            incident = AlertIncident(
                database_id=instance.id,
                status="OPEN",
                severity="CRITICAL",
                title=f"Target Unreachable: {instance.name}",
                message=f"Database '{instance.name}' is unreachable: {error_message or 'Connection timed out'}",
                current_value=0.0,
                threshold_value=1.0,
                triggered_at=datetime.now(timezone.utc),
            )
            db.add(incident)
            await AlertEngine.dispatch_webhook(incident, instance)
            return [incident]
        return []

    @staticmethod
    async def dispatch_webhook(incident: AlertIncident, instance: DatabaseInstance) -> None:
        """Dispatches structured incident notification payload to configured webhook."""
        if not settings.ALERT_WEBHOOK_URL or "CHANGE" in settings.ALERT_WEBHOOK_URL:
            return

        payload = {
            "text": f"🚨 *[CloudOps Sentinel]* {incident.severity} - {incident.title}",
            "attachments": [
                {
                    "color": "#dc2626" if incident.severity == "CRITICAL" else "#f59e0b",
                    "fields": [
                        {"title": "Target Instance", "value": instance.name, "short": True},
                        {"title": "Environment", "value": instance.environment, "short": True},
                        {"title": "Current Value", "value": str(incident.current_value), "short": True},
                        {"title": "Threshold", "value": str(incident.threshold_value), "short": True},
                        {"title": "Details", "value": incident.message, "short": False},
                    ],
                    "footer": "CloudOps Sentinel Operations Automation",
                    "ts": int(incident.triggered_at.timestamp()),
                }
            ],
        }

        try:
            async with httpx.AsyncClient(timeout=5.0) as client:
                resp = await client.post(settings.ALERT_WEBHOOK_URL, json=payload)
                if resp.status_code >= 400:
                    logger.warning("Webhook dispatch returned error status", status_code=resp.status_code)
        except Exception as ex:
            logger.warning("Failed to dispatch alert webhook", error=str(ex))
