"""Pydantic schemas for operational alerts and incident tracking."""

import uuid
from datetime import datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict, Field


class AlertRuleBase(BaseModel):
    name: str = Field(..., max_length=128)
    metric_name: str = Field(..., max_length=64)
    operator: str = Field(default="GREATER_THAN", max_length=16)
    threshold_value: float
    severity: str = Field(default="WARNING", max_length=32)
    is_enabled: bool = True
    description: Optional[str] = None


class AlertRuleCreate(AlertRuleBase):
    pass


class AlertRuleRead(AlertRuleBase):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    created_at: datetime
    updated_at: datetime


class AlertIncidentRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    database_id: uuid.UUID
    rule_id: Optional[uuid.UUID] = None
    status: str
    severity: str
    title: str
    message: str
    current_value: float
    threshold_value: float
    triggered_at: datetime
    resolved_at: Optional[datetime] = None
    acknowledged_by: Optional[str] = None
