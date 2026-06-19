from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import Any, Literal
from uuid import UUID

from pydantic import BaseModel, Field

from backend.app.memory_governance_audit import MemoryGovernanceAudit


MemoryUserControlAction = Literal["activate", "disable", "suppress", "expire", "mark_candidate"]
MemoryMutationOperation = Literal["create", "update", "activate", "disable", "suppress", "expire", "mark_candidate"]


class MemoryControlEvent(BaseModel):
    schema_version: str = "memory_crud_governance_v0"
    action: str
    from_status: str | None
    to_status: str
    actor: str = "user"
    source: str = "internal_memory_api_v1"
    reason: str | None = None
    acted_at: datetime
    changed_fields: list[str] = Field(default_factory=list)


class MemoryControlItemSummary(BaseModel):
    memory_id: UUID
    memory_type: str
    key: str
    value_json: dict[str, Any]
    text: str | None
    confidence: Decimal
    status: str
    lifecycle_state: str
    expires_at: datetime | None
    last_used_at: datetime | None
    source_run_id: UUID | None
    source_langsmith_trace_id: str | None
    created_at: datetime
    updated_at: datetime
    metadata_json: dict[str, Any] = Field(default_factory=dict)
    governance_audit: MemoryGovernanceAudit


class MemoryDetailResponse(MemoryControlItemSummary):
    pass


class MemoryControlListResponse(BaseModel):
    schema_version: str = "memory_user_control_list_v0"
    user_id: UUID
    items: list[MemoryControlItemSummary]


class MemoryCreateRequest(BaseModel):
    memory_type: str
    key: str
    value_json: dict[str, Any] = Field(default_factory=dict)
    text: str | None = None
    confidence: Decimal
    status: str
    expires_at: datetime | None = None
    source_run_id: UUID | None = None
    source_langsmith_trace_id: str | None = None
    reason: str | None = None


class MemoryUpdateRequest(BaseModel):
    value_json: dict[str, Any] = Field(default_factory=dict)
    text: str | None = None
    confidence: Decimal
    expires_at: datetime | None = None
    reason: str | None = None


class MemoryControlRequest(BaseModel):
    action: MemoryUserControlAction
    reason: str | None = None


class MemoryDeleteRequest(BaseModel):
    reason: str | None = None


class MemoryControlMutationResponse(BaseModel):
    schema_version: str = "memory_user_control_item_v0"
    operation: MemoryMutationOperation
    applied: bool
    item: MemoryControlItemSummary
