from datetime import datetime
from decimal import Decimal
from typing import Any
from uuid import UUID

from sqlalchemy import or_, select
from sqlalchemy.sql import func
from sqlalchemy.orm import Session

from backend.app.models.runtime import MemoryItem


class MemoryItemRepository:
    def __init__(self, session: Session) -> None:
        self.session = session

    def create(
        self,
        user_id: UUID,
        memory_type: str,
        key: str,
        value_json: dict[str, Any],
        text: str | None,
        confidence: Decimal,
        source_run_id: UUID | None,
        source_langsmith_trace_id: str | None,
        expires_at: datetime | None,
        status: str,
    ) -> MemoryItem:
        memory_item = MemoryItem(
            user_id=user_id,
            memory_type=memory_type,
            key=key,
            value_json=value_json,
            text=text,
            confidence=confidence,
            source_run_id=source_run_id,
            source_langsmith_trace_id=source_langsmith_trace_id,
            expires_at=expires_at,
            status=status,
        )
        self.session.add(memory_item)
        self.session.flush()
        self.session.refresh(memory_item)
        return memory_item

    def get_by_id(self, memory_id: UUID) -> MemoryItem | None:
        return self.session.get(MemoryItem, memory_id)

    def list_active_for_user(self, user_id: UUID) -> list[MemoryItem]:
        statement = (
            select(MemoryItem)
            .where(
                MemoryItem.user_id == user_id,
                MemoryItem.status == "active",
                or_(MemoryItem.expires_at.is_(None), MemoryItem.expires_at > func.now()),
            )
            .order_by(MemoryItem.created_at, MemoryItem.memory_id)
        )
        return list(self.session.scalars(statement).all())

    def list_governable_for_user(self, user_id: UUID) -> list[MemoryItem]:
        statement = (
            select(MemoryItem)
            .where(
                MemoryItem.user_id == user_id,
                MemoryItem.status == "active",
            )
            .order_by(MemoryItem.created_at, MemoryItem.memory_id)
        )
        return list(self.session.scalars(statement).all())
