from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import Any, Literal
from uuid import UUID

from pydantic import BaseModel, Field


MemoryUserControlAction = Literal["disable", "suppress"]


class MemoryControlEvent(BaseModel):
    schema_version: str = "memory_user_control_v0"
    action: MemoryUserControlAction
    from_status: str
    to_status: str
    actor: str = "user"
    source: str = "internal_memory_api_v0"
    reason: str | None = None
    acted_at: datetime


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
    created_at: datetime
    updated_at: datetime
    metadata_json: dict[str, Any] = Field(default_factory=dict)


class MemoryControlListResponse(BaseModel):
    schema_version: str = "memory_user_control_list_v0"
    user_id: UUID
    items: list[MemoryControlItemSummary]


class MemoryControlRequest(BaseModel):
    action: MemoryUserControlAction
    reason: str | None = None


class MemoryControlMutationResponse(BaseModel):
    schema_version: str = "memory_user_control_item_v0"
    operation: MemoryUserControlAction
    applied: bool
    item: MemoryControlItemSummary
