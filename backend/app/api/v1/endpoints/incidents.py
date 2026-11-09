"""Endpoints for CloudOps Sentinel Incident Management, Alertmanager Webhooks, and SLA Reports."""

import uuid
from typing import Any, Dict, List, Optional
from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.schemas.incident import (
    AlertmanagerWebhookPayload,
    IncidentAcknowledgeRequest,
    IncidentCreate,
    IncidentDetailRead,
    IncidentEscalateRequest,
    IncidentMetricsResponse,
    IncidentRead,
    IncidentReportSummary,
    IncidentResolveRequest,
)
from app.services.incident_service import IncidentService

router = APIRouter(prefix="/incidents", tags=["Incident Management"])


@router.post(
    "/",
    response_model=IncidentRead,
    status_code=status.HTTP_201_CREATED,
    summary="Create a new incident",
)
async def create_incident(
    payload: IncidentCreate,
    db: AsyncSession = Depends(get_db),
) -> Any:
    """Creates a new operational incident (from automated monitor, probe, or manual)."""
    incident = await IncidentService.create_incident(
        db=db,
        payload=payload,
        actor="ops_api",
    )
    await db.commit()
    await db.refresh(incident)
    return incident


@router.get(
    "/",
    response_model=List[IncidentRead],
    summary="List all incidents with filters",
)
async def list_incidents(
    status: Optional[str] = Query(None, description="Filter by status (OPEN, ACKNOWLEDGED, RESOLVED)"),
    severity: Optional[str] = Query(None, description="Filter by severity (CRITICAL, HIGH, MEDIUM, LOW)"),
    source: Optional[str] = Query(None, description="Filter by source (ALERTMANAGER, HEALTH_CHECK_PROBE, etc.)"),
    component: Optional[str] = Query(None, description="Filter by component (DATABASE, API, etc.)"),
    limit: int = Query(50, ge=1, le=100),
    offset: int = Query(0, ge=0),
    db: AsyncSession = Depends(get_db),
) -> Any:
    """Returns a list of incidents filtered by status, severity, source, or component."""
    return await IncidentService.list_incidents(
        db=db,
        status_filter=status,
        severity_filter=severity,
        source_filter=source,
        component_filter=component,
        limit=limit,
        offset=offset,
    )


@router.get(
    "/metrics/sla",
    response_model=IncidentMetricsResponse,
    summary="Retrieve SRE incident SLA response and resolution metrics",
)
async def get_incident_metrics(
    db: AsyncSession = Depends(get_db),
) -> Any:
    """Calculates Mean Time To Acknowledge (MTTA), Mean Time To Resolve (MTTR), and SLA compliance rate."""
    return await IncidentService.calculate_metrics(db=db)


@router.get(
    "/reports/summary",
    response_model=IncidentReportSummary,
    summary="Generate executive incident summary report",
)
async def get_incident_report(
    db: AsyncSession = Depends(get_db),
) -> Any:
    """Generates an executive report containing overall KPIs, active critical incidents, and recent resolutions."""
    return await IncidentService.generate_report(db=db)


@router.post(
    "/webhook/alertmanager",
    status_code=status.HTTP_200_OK,
    summary="Ingest Alertmanager webhook dispatches",
)
async def alertmanager_webhook(
    payload: AlertmanagerWebhookPayload,
    db: AsyncSession = Depends(get_db),
) -> Dict[str, Any]:
    """Ingests firing and resolved alerts from Prometheus Alertmanager with deduplication and auto-resolution."""
    summary = await IncidentService.process_alertmanager_webhook(db=db, payload=payload)
    return {
        "status": "PROCESSED",
        "alerts_received": len(payload.alerts),
        "details": summary,
    }


@router.post(
    "/escalate",
    response_model=List[IncidentRead],
    summary="Evaluate SLA breach escalation rules",
)
async def trigger_escalation_evaluation(
    db: AsyncSession = Depends(get_db),
) -> Any:
    """Evaluates all unacknowledged OPEN incidents and applies automatic tiered escalation."""
    escalated = await IncidentService.evaluate_escalations(db=db)
    await db.commit()
    return escalated


@router.get(
    "/{incident_id}",
    response_model=IncidentDetailRead,
    summary="Get incident detail with full chronological history",
)
async def get_incident(
    incident_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
) -> Any:
    """Retrieves an incident by UUID including its complete audit trail."""
    return await IncidentService.get_incident(db=db, incident_id=incident_id)


@router.post(
    "/{incident_id}/acknowledge",
    response_model=IncidentRead,
    summary="Acknowledge an open incident",
)
async def acknowledge_incident(
    incident_id: uuid.UUID,
    payload: IncidentAcknowledgeRequest,
    db: AsyncSession = Depends(get_db),
) -> Any:
    """Marks an incident as ACKNOWLEDGED, recording on-call engineer and timestamp."""
    incident = await IncidentService.acknowledge_incident(
        db=db,
        incident_id=incident_id,
        payload=payload,
    )
    await db.commit()
    await db.refresh(incident)
    return incident


@router.post(
    "/{incident_id}/resolve",
    response_model=IncidentRead,
    summary="Resolve an incident with remediation notes",
)
async def resolve_incident(
    incident_id: uuid.UUID,
    payload: IncidentResolveRequest,
    db: AsyncSession = Depends(get_db),
) -> Any:
    """Marks an incident as RESOLVED, recording resolution notes and MTTR duration."""
    incident = await IncidentService.resolve_incident(
        db=db,
        incident_id=incident_id,
        payload=payload,
    )
    await db.commit()
    await db.refresh(incident)
    return incident


@router.post(
    "/{incident_id}/escalate",
    response_model=IncidentRead,
    summary="Manually escalate incident tier",
)
async def escalate_incident_manual(
    incident_id: uuid.UUID,
    payload: IncidentEscalateRequest,
    db: AsyncSession = Depends(get_db),
) -> Any:
    """Manually elevates the escalation tier of an incident with required justification."""
    incident = await IncidentService.escalate_incident(
        db=db,
        incident_id=incident_id,
        new_level=payload.new_level,
        actor=payload.actor,
        reason=payload.reason,
    )
    await db.commit()
    await db.refresh(incident)
    return incident

