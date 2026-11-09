"""Incident Lifecycle Management & Escalation Engine for CloudOps Sentinel."""

import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
from fastapi import HTTPException, status
from sqlalchemy import desc, func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.logging import logger
from app.models.base import utc_now
from app.models.incident import (
    Incident,
    IncidentHistory,
    IncidentSeverity,
    IncidentSource,
    IncidentStatus,
)
from app.schemas.incident import (
    AlertmanagerWebhookPayload,
    IncidentAcknowledgeRequest,
    IncidentCreate,
    IncidentMetricsResponse,
    IncidentReportSummary,
    IncidentResolveRequest,
)

# SRE Response & Resolution SLAs in seconds
SLA_ACKNOWLEDGE_LIMITS = {
    IncidentSeverity.CRITICAL.value: 900,     # 15 minutes
    IncidentSeverity.HIGH.value: 1800,        # 30 minutes
    IncidentSeverity.MEDIUM.value: 3600,      # 1 hour
    IncidentSeverity.LOW.value: 86400,        # 24 hours
}

SLA_RESOLVE_LIMITS = {
    IncidentSeverity.CRITICAL.value: 3600,     # 1 hour
    IncidentSeverity.HIGH.value: 14400,        # 4 hours
    IncidentSeverity.MEDIUM.value: 86400,      # 24 hours
    IncidentSeverity.LOW.value: 259200,        # 72 hours
}


def _format_duration_human(seconds: Optional[float]) -> str:
    """Formats numeric seconds into clean human-readable duration."""
    if seconds is None:
        return "N/A"
    seconds = int(seconds)
    if seconds < 60:
        return f"{seconds}s"
    minutes, sec = divmod(seconds, 60)
    if minutes < 60:
        return f"{minutes}m {sec}s"
    hours, minutes = divmod(minutes, 60)
    return f"{hours}h {minutes}m"


class IncidentService:
    """Service implementing the full Incident lifecycle, alerting webhooks, and escalation."""

    @staticmethod
    async def create_incident(
        db: AsyncSession,
        payload: IncidentCreate,
        actor: str = "system",
    ) -> Incident:
        """Creates a new operational incident and logs the creation in history."""
        # Normalize severity and status values
        severity_val = (
            payload.severity.value
            if isinstance(payload.severity, IncidentSeverity)
            else str(payload.severity).upper()
        )
        source_val = (
            payload.source.value
            if isinstance(payload.source, IncidentSource)
            else str(payload.source).upper()
        )

        incident = Incident(
            title=payload.title,
            description=payload.description,
            severity=severity_val,
            status=IncidentStatus.OPEN.value,
            source=source_val,
            component=payload.component.upper(),
            target_instance=payload.target_instance,
            fingerprint=payload.fingerprint,
            assigned_to=payload.assigned_to,
            metadata_json=payload.metadata_json or {},
        )
        db.add(incident)
        await db.flush()
        await db.refresh(incident)

        # Record initial history entry
        history_entry = IncidentHistory(
            incident_id=incident.id,
            from_status=None,
            to_status=IncidentStatus.OPEN.value,
            action="CREATED",
            actor=actor,
            notes=payload.description or f"Incident opened with {severity_val} severity.",
        )
        db.add(history_entry)
        await db.flush()

        logger.info(
            "Incident created",
            incident_id=str(incident.id),
            title=incident.title,
            severity=incident.severity,
            source=incident.source,
            actor=actor,
        )
        return incident

    @staticmethod
    async def get_incident(
        db: AsyncSession,
        incident_id: uuid.UUID,
    ) -> Incident:
        """Retrieves an incident with all historical audit records loaded."""
        result = await db.execute(
            select(Incident)
            .options(selectinload(Incident.history))
            .where(Incident.id == incident_id)
        )
        incident = result.scalar_one_or_none()
        if not incident:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Incident {incident_id} not found",
            )
        return incident

    @staticmethod
    async def list_incidents(
        db: AsyncSession,
        status_filter: Optional[str] = None,
        severity_filter: Optional[str] = None,
        source_filter: Optional[str] = None,
        component_filter: Optional[str] = None,
        limit: int = 50,
        offset: int = 0,
    ) -> List[Incident]:
        """Lists incidents according to filters ordered newest first."""
        query = select(Incident).order_by(desc(Incident.created_at))
        if status_filter:
            query = query.where(Incident.status == status_filter.upper())
        if severity_filter:
            query = query.where(Incident.severity == severity_filter.upper())
        if source_filter:
            query = query.where(Incident.source == source_filter.upper())
        if component_filter:
            query = query.where(Incident.component == component_filter.upper())

        query = query.limit(limit).offset(offset)
        result = await db.execute(query)
        return list(result.scalars().all())

    @staticmethod
    async def acknowledge_incident(
        db: AsyncSession,
        incident_id: uuid.UUID,
        payload: IncidentAcknowledgeRequest,
    ) -> Incident:
        """Acknowledges an open incident, setting acknowledged_at and adding audit log."""
        incident = await IncidentService.get_incident(db, incident_id)
        if incident.status == IncidentStatus.RESOLVED.value:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Cannot acknowledge an incident that is already RESOLVED",
            )

        previous_status = incident.status
        incident.status = IncidentStatus.ACKNOWLEDGED.value
        incident.acknowledged_at = utc_now()
        incident.acknowledged_by = payload.acknowledged_by
        if not incident.assigned_to:
            incident.assigned_to = payload.acknowledged_by

        history = IncidentHistory(
            incident_id=incident.id,
            from_status=previous_status,
            to_status=IncidentStatus.ACKNOWLEDGED.value,
            action="ACKNOWLEDGED",
            actor=payload.acknowledged_by,
            notes=payload.notes or "Incident acknowledged by on-call engineer.",
        )
        db.add(history)
        await db.flush()
        await db.refresh(incident)

        logger.info(
            "Incident acknowledged",
            incident_id=str(incident.id),
            actor=payload.acknowledged_by,
            duration_to_ack=incident.time_to_acknowledge_seconds,
        )
        return incident

    @staticmethod
    async def resolve_incident(
        db: AsyncSession,
        incident_id: uuid.UUID,
        payload: IncidentResolveRequest,
    ) -> Incident:
        """Resolves an incident, requiring remediation notes and computing MTTR."""
        incident = await IncidentService.get_incident(db, incident_id)
        if incident.status == IncidentStatus.RESOLVED.value:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Incident is already RESOLVED",
            )

        previous_status = incident.status
        incident.status = IncidentStatus.RESOLVED.value
        incident.resolved_at = utc_now()
        incident.resolved_by = payload.resolved_by
        incident.resolution_notes = payload.resolution_notes

        history = IncidentHistory(
            incident_id=incident.id,
            from_status=previous_status,
            to_status=IncidentStatus.RESOLVED.value,
            action="RESOLVED",
            actor=payload.resolved_by,
            notes=payload.resolution_notes,
        )
        db.add(history)
        await db.flush()
        await db.refresh(incident)

        logger.info(
            "Incident resolved",
            incident_id=str(incident.id),
            actor=payload.resolved_by,
            total_duration_sec=incident.time_to_resolve_seconds,
        )
        return incident

    @staticmethod
    async def escalate_incident(
        db: AsyncSession,
        incident_id: uuid.UUID,
        new_level: int,
        actor: str,
        reason: str,
    ) -> Incident:
        """Manually or automatically advances incident escalation level."""
        incident = await IncidentService.get_incident(db, incident_id)
        if incident.status == IncidentStatus.RESOLVED.value:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Cannot escalate a resolved incident",
            )

        old_level = incident.escalation_level
        incident.escalation_level = new_level
        incident.escalated_at = utc_now()

        history = IncidentHistory(
            incident_id=incident.id,
            from_status=incident.status,
            to_status=incident.status,
            action="ESCALATED",
            actor=actor,
            notes=f"Escalated from Level {old_level} to Level {new_level}. Reason: {reason}",
        )
        db.add(history)
        await db.flush()
        await db.refresh(incident)

        logger.warning(
            "Incident escalated",
            incident_id=str(incident.id),
            old_level=old_level,
            new_level=new_level,
            actor=actor,
            reason=reason,
        )
        return incident

    @staticmethod
    async def process_alertmanager_webhook(
        db: AsyncSession,
        payload: AlertmanagerWebhookPayload,
    ) -> Dict[str, Any]:
        """Ingests Alertmanager dispatches, deduplicating firing alerts and auto-resolving."""
        processed_summary = {
            "firing_created": 0,
            "firing_updated": 0,
            "auto_resolved": 0,
            "incident_ids": [],
        }

        for alert in payload.alerts:
            # Generate deterministic deduplication fingerprint
            alert_name = alert.labels.get("alertname", "UnknownAlert")
            instance = alert.labels.get("instance", "default-instance")
            fingerprint = alert.fingerprint or f"{alert_name}:{instance}"

            if alert.status.lower() == "firing":
                # Check for existing active (OPEN or ACKNOWLEDGED) incident with same fingerprint
                existing_res = await db.execute(
                    select(Incident).where(
                        Incident.fingerprint == fingerprint,
                        Incident.status != IncidentStatus.RESOLVED.value,
                    )
                )
                existing_incident = existing_res.scalar_one_or_none()

                if existing_incident:
                    # Deduplicate: update metadata and record update in history
                    existing_incident.metadata_json = {
                        **existing_incident.metadata_json,
                        "last_firing_payload": alert.model_dump(),
                        "last_updated_at": utc_now().isoformat(),
                    }
                    history = IncidentHistory(
                        incident_id=existing_incident.id,
                        from_status=existing_incident.status,
                        to_status=existing_incident.status,
                        action="ALERT_UPDATE",
                        actor="alertmanager_webhook",
                        notes=f"Subsequent firing dispatch received for alert {alert_name}.",
                    )
                    db.add(history)
                    processed_summary["firing_updated"] += 1
                    processed_summary["incident_ids"].append(str(existing_incident.id))
                else:
                    # Map severity from Alertmanager label
                    label_sev = alert.labels.get("severity", "medium").upper()
                    if label_sev == "CRITICAL":
                        mapped_severity = IncidentSeverity.CRITICAL
                    elif label_sev in ["HIGH", "WARNING"]:
                        mapped_severity = IncidentSeverity.HIGH
                    elif label_sev == "LOW":
                        mapped_severity = IncidentSeverity.LOW
                    else:
                        mapped_severity = IncidentSeverity.MEDIUM

                    # Create new incident
                    summary_text = (
                        alert.annotations.get("summary")
                        or alert.annotations.get("description")
                        or f"Alert firing: {alert_name}"
                    )
                    desc_text = alert.annotations.get("description") or alert.annotations.get("runbook") or ""

                    create_schema = IncidentCreate(
                        title=summary_text,
                        description=desc_text,
                        severity=mapped_severity,
                        source=IncidentSource.ALERTMANAGER,
                        component=alert.labels.get("category", "DATABASE").upper(),
                        target_instance=instance,
                        fingerprint=fingerprint,
                        metadata_json={
                            "alertmanager_labels": alert.labels,
                            "alertmanager_annotations": alert.annotations,
                            "startsAt": alert.startsAt,
                        },
                    )
                    new_incident = await IncidentService.create_incident(
                        db=db,
                        payload=create_schema,
                        actor="alertmanager_webhook",
                    )
                    processed_summary["firing_created"] += 1
                    processed_summary["incident_ids"].append(str(new_incident.id))

            elif alert.status.lower() == "resolved":
                # Find matching active incident to automatically resolve
                existing_res = await db.execute(
                    select(Incident).where(
                        Incident.fingerprint == fingerprint,
                        Incident.status != IncidentStatus.RESOLVED.value,
                    )
                )
                active_incident = existing_res.scalar_one_or_none()
                if active_incident:
                    resolve_payload = IncidentResolveRequest(
                        resolved_by="alertmanager_webhook",
                        resolution_notes=(
                            f"Automatically resolved by Alertmanager webhook. "
                            f"Alert '{alert_name}' returned to normal state."
                        ),
                    )
                    await IncidentService.resolve_incident(
                        db=db,
                        incident_id=active_incident.id,
                        payload=resolve_payload,
                    )
                    processed_summary["auto_resolved"] += 1
                    processed_summary["incident_ids"].append(str(active_incident.id))

        await db.commit()
        return processed_summary

    @staticmethod
    async def evaluate_escalations(
        db: AsyncSession,
        evaluation_time: Optional[datetime] = None,
    ) -> List[Incident]:
        """Scans unacknowledged OPEN incidents and applies SLA escalation rules."""
        now = evaluation_time or utc_now()
        result = await db.execute(
            select(Incident).where(Incident.status == IncidentStatus.OPEN.value)
        )
        open_incidents = list(result.scalars().all())
        escalated_incidents: List[Incident] = []

        for incident in open_incidents:
            unacked_seconds = (now - incident.created_at).total_seconds()
            new_tier: Optional[int] = None
            reason = ""

            if incident.severity == IncidentSeverity.CRITICAL.value:
                # Level 1 after 5 mins, Level 2 after 15 mins
                if unacked_seconds >= 900 and incident.escalation_level < 2:
                    new_tier = 2
                    reason = f"CRITICAL incident unacknowledged for {int(unacked_seconds/60)}m (Breached 15m L2 SLA threshold)"
                elif unacked_seconds >= 300 and incident.escalation_level < 1:
                    new_tier = 1
                    reason = f"CRITICAL incident unacknowledged for {int(unacked_seconds/60)}m (Breached 5m L1 SLA threshold)"

            elif incident.severity == IncidentSeverity.HIGH.value:
                # Level 1 after 15 mins, Level 2 after 30 mins
                if unacked_seconds >= 1800 and incident.escalation_level < 2:
                    new_tier = 2
                    reason = f"HIGH incident unacknowledged for {int(unacked_seconds/60)}m (Breached 30m L2 SLA threshold)"
                elif unacked_seconds >= 900 and incident.escalation_level < 1:
                    new_tier = 1
                    reason = f"HIGH incident unacknowledged for {int(unacked_seconds/60)}m (Breached 15m L1 SLA threshold)"

            elif incident.severity == IncidentSeverity.MEDIUM.value:
                if unacked_seconds >= 3600 and incident.escalation_level < 1:
                    new_tier = 1
                    reason = f"MEDIUM incident unacknowledged for {int(unacked_seconds/60)}m (Breached 1h SLA threshold)"

            elif incident.severity == IncidentSeverity.LOW.value:
                if unacked_seconds >= 14400 and incident.escalation_level < 1:
                    new_tier = 1
                    reason = f"LOW incident unacknowledged for {int(unacked_seconds/60)}m (Breached 4h SLA threshold)"

            if new_tier is not None and new_tier > incident.escalation_level:
                await IncidentService.escalate_incident(
                    db=db,
                    incident_id=incident.id,
                    new_level=new_tier,
                    actor="sla_escalation_engine",
                    reason=reason,
                )
                escalated_incidents.append(incident)

        return escalated_incidents

    @staticmethod
    async def calculate_metrics(db: AsyncSession) -> IncidentMetricsResponse:
        """Calculates MTTA, MTTR, SLA compliance rates, and breakdown by severity/status."""
        # Query all incidents
        result = await db.execute(select(Incident))
        incidents = list(result.scalars().all())

        total = len(incidents)
        open_count = sum(1 for i in incidents if i.status == IncidentStatus.OPEN.value)
        acked_count = sum(1 for i in incidents if i.status == IncidentStatus.ACKNOWLEDGED.value)
        resolved_count = sum(1 for i in incidents if i.status == IncidentStatus.RESOLVED.value)

        by_severity = {
            IncidentSeverity.CRITICAL.value: sum(1 for i in incidents if i.severity == IncidentSeverity.CRITICAL.value),
            IncidentSeverity.HIGH.value: sum(1 for i in incidents if i.severity == IncidentSeverity.HIGH.value),
            IncidentSeverity.MEDIUM.value: sum(1 for i in incidents if i.severity == IncidentSeverity.MEDIUM.value),
            IncidentSeverity.LOW.value: sum(1 for i in incidents if i.severity == IncidentSeverity.LOW.value),
        }

        by_status = {
            IncidentStatus.OPEN.value: open_count,
            IncidentStatus.ACKNOWLEDGED.value: acked_count,
            IncidentStatus.RESOLVED.value: resolved_count,
        }

        # Calculate Mean Time To Acknowledge (MTTA)
        ack_durations = [i.time_to_acknowledge_seconds for i in incidents if i.time_to_acknowledge_seconds is not None]
        mtta_sec = round(sum(ack_durations) / len(ack_durations), 2) if ack_durations else None

        # Calculate Mean Time To Resolve (MTTR)
        resolve_durations = [i.time_to_resolve_seconds for i in incidents if i.time_to_resolve_seconds is not None]
        mttr_sec = round(sum(resolve_durations) / len(resolve_durations), 2) if resolve_durations else None

        # Evaluate SLA compliance
        sla_compliant_count = 0
        sla_evaluated_count = 0

        for inc in incidents:
            ack_limit = SLA_ACKNOWLEDGE_LIMITS.get(inc.severity, 3600)
            resolve_limit = SLA_RESOLVE_LIMITS.get(inc.severity, 86400)

            # Check acknowledgement SLA
            if inc.time_to_acknowledge_seconds is not None:
                sla_evaluated_count += 1
                if inc.time_to_acknowledge_seconds <= ack_limit:
                    sla_compliant_count += 1
            elif inc.status == IncidentStatus.OPEN.value:
                # If currently open and already breached ack limit, counts as violation
                unacked = (utc_now() - inc.created_at).total_seconds()
                sla_evaluated_count += 1
                if unacked <= ack_limit:
                    sla_compliant_count += 1

            # Check resolution SLA for resolved incidents
            if inc.time_to_resolve_seconds is not None:
                sla_evaluated_count += 1
                if inc.time_to_resolve_seconds <= resolve_limit:
                    sla_compliant_count += 1

        sla_rate = (
            round((sla_compliant_count / sla_evaluated_count) * 100, 1)
            if sla_evaluated_count > 0
            else 100.0
        )

        active_escalations = sum(
            1 for i in incidents if i.escalation_level > 0 and i.status != IncidentStatus.RESOLVED.value
        )

        return IncidentMetricsResponse(
            total_incidents=total,
            open_incidents=open_count,
            acknowledged_incidents=acked_count,
            resolved_incidents=resolved_count,
            by_severity=by_severity,
            by_status=by_status,
            mean_time_to_acknowledge_seconds=mtta_sec,
            mean_time_to_resolve_seconds=mttr_sec,
            mean_time_to_acknowledge_human=_format_duration_human(mtta_sec),
            mean_time_to_resolve_human=_format_duration_human(mttr_sec),
            sla_compliance_rate_pct=sla_rate,
            active_escalations_count=active_escalations,
        )

    @staticmethod
    async def generate_report(db: AsyncSession) -> IncidentReportSummary:
        """Generates comprehensive executive incident and reliability report."""
        metrics = await IncidentService.calculate_metrics(db)

        # Retrieve active critical incidents
        crit_res = await db.execute(
            select(Incident)
            .where(
                Incident.severity == IncidentSeverity.CRITICAL.value,
                Incident.status != IncidentStatus.RESOLVED.value,
            )
            .order_by(desc(Incident.created_at))
            .limit(5)
        )
        active_critical = list(crit_res.scalars().all())

        # Retrieve recent resolved incidents
        res_res = await db.execute(
            select(Incident)
            .where(Incident.status == IncidentStatus.RESOLVED.value)
            .order_by(desc(Incident.resolved_at))
            .limit(5)
        )
        recent_resolved = list(res_res.scalars().all())

        return IncidentReportSummary(
            generated_at=utc_now(),
            metrics=metrics,
            active_critical_incidents=active_critical,
            recent_resolved_incidents=recent_resolved,
        )

