"""Pydantic schemas for Incident Management, Alertmanager webhooks, and SLA metrics."""

import uuid
from datetime import datetime
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, ConfigDict, Field

from app.models.incident import IncidentSeverity, IncidentSource, IncidentStatus


class IncidentHistoryRead(BaseModel):
    """Schema for individual audit history entries."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    incident_id: uuid.UUID
    from_status: Optional[str] = None
    to_status: str
    action: str
    actor: str
    notes: Optional[str] = None
    created_at: datetime


class IncidentBase(BaseModel):
    """Base incident properties."""

    title: str = Field(..., max_length=255, description="Short incident title")
    description: Optional[str] = Field(None, description="Detailed diagnostic context")
    severity: IncidentSeverity = Field(
        default=IncidentSeverity.MEDIUM,
        description="Severity: CRITICAL, HIGH, MEDIUM, LOW",
    )
    source: IncidentSource = Field(
        default=IncidentSource.ALERTMANAGER,
        description="Source of detection",
    )
    component: str = Field(
        default="DATABASE",
        description="Impacted infrastructure component",
    )
    target_instance: str = Field(
        default="primary-postgres",
        description="Identifier of target database or host",
    )
    fingerprint: Optional[str] = Field(
        None,
        description="Deduplication key for firing alerts",
    )
    assigned_to: Optional[str] = None
    metadata_json: Dict[str, Any] = Field(default_factory=dict)


class IncidentCreate(IncidentBase):
    """Schema for manually or programmatically opening an incident."""

    status: IncidentStatus = Field(
        default=IncidentStatus.OPEN,
        description="Initial incident state",
    )


class IncidentAcknowledgeRequest(BaseModel):
    """Schema for on-call engineer acknowledging an open incident."""

    acknowledged_by: str = Field(..., min_length=2, description="Engineer name or user ID")
    notes: Optional[str] = Field(None, description="Initial triage or investigation notes")


class IncidentResolveRequest(BaseModel):
    """Schema for resolving an incident with root cause and remediation notes."""

    resolved_by: str = Field(..., min_length=2, description="Engineer name or user ID")
    resolution_notes: str = Field(
        ...,
        min_length=5,
        description="Remediation steps, root cause analysis, or verification evidence",
    )


class IncidentEscalateRequest(BaseModel):
    """Schema for manually escalating an incident tier."""

    actor: str = Field(default="on_call_engineer", description="Engineer initiating escalation")
    new_level: int = Field(..., ge=1, le=3, description="Target escalation tier (1=L2, 2=L3, 3=Exec)")
    reason: str = Field(..., min_length=5, description="Justification for escalation")


class IncidentRead(IncidentBase):
    """Schema for incident output representation."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    status: str
    severity: str
    source: str
    escalation_level: int
    acknowledged_by: Optional[str] = None
    resolved_by: Optional[str] = None
    resolution_notes: Optional[str] = None
    created_at: datetime
    updated_at: datetime
    acknowledged_at: Optional[datetime] = None
    resolved_at: Optional[datetime] = None
    escalated_at: Optional[datetime] = None
    time_to_acknowledge_seconds: Optional[float] = None
    time_to_resolve_seconds: Optional[float] = None


class IncidentDetailRead(IncidentRead):
    """Extended incident output with full historical audit log."""

    history: List[IncidentHistoryRead] = Field(default_factory=list)


# ------------------------------------------------------------------------------
# Alertmanager Webhook Ingestion Schemas
# ------------------------------------------------------------------------------
class AlertmanagerAlert(BaseModel):
    """Single alert payload inside an Alertmanager webhook dispatch."""

    status: str = Field(..., description="Alert status: 'firing' or 'resolved'")
    labels: Dict[str, str] = Field(default_factory=dict)
    annotations: Dict[str, str] = Field(default_factory=dict)
    startsAt: Optional[str] = None
    endsAt: Optional[str] = None
    generatorURL: Optional[str] = None
    fingerprint: Optional[str] = None


class AlertmanagerWebhookPayload(BaseModel):
    """Standard Prometheus Alertmanager webhook POST payload."""

    version: str = "4"
    groupKey: Optional[str] = None
    truncatedAlerts: int = 0
    status: str = Field(..., description="'firing' or 'resolved'")
    receiver: Optional[str] = None
    groupLabels: Dict[str, str] = Field(default_factory=dict)
    commonLabels: Dict[str, str] = Field(default_factory=dict)
    commonAnnotations: Dict[str, str] = Field(default_factory=dict)
    externalURL: Optional[str] = None
    alerts: List[AlertmanagerAlert] = Field(default_factory=list)


# ------------------------------------------------------------------------------
# Metrics & Reporting Schemas
# ------------------------------------------------------------------------------
class IncidentMetricsResponse(BaseModel):
    """SRE Incident SLA response and resolution metrics."""

    total_incidents: int
    open_incidents: int
    acknowledged_incidents: int
    resolved_incidents: int
    by_severity: Dict[str, int]
    by_status: Dict[str, int]
    mean_time_to_acknowledge_seconds: Optional[float] = None
    mean_time_to_resolve_seconds: Optional[float] = None
    mean_time_to_acknowledge_human: str = "N/A"
    mean_time_to_resolve_human: str = "N/A"
    sla_compliance_rate_pct: float
    active_escalations_count: int


class IncidentReportSummary(BaseModel):
    """Executive & SRE operational incident summary report."""

    report_title: str = "CloudOps Sentinel Incident & Reliability Report"
    generated_at: datetime
    metrics: IncidentMetricsResponse
    active_critical_incidents: List[IncidentRead]
    recent_resolved_incidents: List[IncidentRead]

